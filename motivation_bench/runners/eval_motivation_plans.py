#!/usr/bin/env python3
"""
eval_motivation_plans.py — Score motivation_outputs plans against a reference

For each case in motivation_outputs/run_*/plans/:
  - Reference plan : the chosen reference model's plan for that case
                     (default: claude-opus-4-7, treated as "gold")
  - Candidates     : other models' plans for the same case
  - Judge          : a strong model (default: claude-opus-4-7) using a
                     reference-anchored, anchored-rubric grading prompt
                     (8 categories, 1-5 scale each)
  - Output         : per-plan JSON under <run>/grades/, aggregate CSV at
                     <run>/grades/summary.csv

Methodological note
-------------------
Using opus-4-7 as the reference means grading measures agreement with the
opus-4-7 plan, not absolute plan quality. By default we SKIP the reference
model itself from the candidate set; if you want to grade it as a sanity
check it should score near 5/5 across the board.

Usage
-----
    # Grade every candidate plan in a run
    python eval_motivation_plans.py \\
        --run-dir /home/jye/publications/motivation_outputs/run_20260505T170532

    # Single case only
    python eval_motivation_plans.py \\
        --run-dir <run> --case multi_gen_omp_26_reduce_product_of_inverses

    # Different reference / judge
    python eval_motivation_plans.py \\
        --run-dir <run> \\
        --reference-model claude-opus-4-7 \\
        --judge-model     claude-opus-4-7

    # Include the reference model as a candidate (sanity check)
    python eval_motivation_plans.py --run-dir <run> --include-reference

    # Re-run only failed grades
    python eval_motivation_plans.py --run-dir <run> --skip-existing
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("eval_motivation_plans")


# ─────────────────────────────────────────────────────────────────────────────
# Anchored rubric (8 categories, with 1/3/5 anchors so the judge is calibrated
# even though a reference plan is also shown)
# ─────────────────────────────────────────────────────────────────────────────

RUBRIC: dict[str, dict[str, str]] = {
    "completeness": {
        "what": (
            "Coverage of every deliverable named in the objective: "
            "implementation, oracle + test harness, build recipe, Slurm "
            "submission script, performance writeup, review/audit note."
        ),
        "5": (
            "All six deliverables are addressed by named subtasks with "
            "concrete artifacts."
        ),
        "3": (
            "Most deliverables addressed; one or two are thin or implicit."
        ),
        "1": (
            "Several deliverables missing or only the implementation is "
            "covered."
        ),
    },
    "correctness": {
        "what": (
            "Are the proposed steps, algorithm, and MPI/OpenMP usage "
            "technically sound? Would executing them actually achieve the "
            "objective?"
        ),
        "5": (
            "Algorithm is correct; MPI/OpenMP idioms are appropriate; "
            "pseudocode and flags would compile and run."
        ),
        "3": (
            "Mostly correct, with minor issues a reviewer would catch."
        ),
        "1": (
            "Significant errors — wrong algorithm, broken MPI semantics, "
            "or build steps that won't work."
        ),
    },
    "specificity": {
        "what": (
            "Are decisions concrete (file names, function signatures, "
            "module names, compiler flags, R x T layout, fabric, storage "
            "tier, walltime) rather than vague intentions?"
        ),
        "5": (
            "Concrete throughout: named files, exact flags, specific "
            "module loads, named hostnames, specific R x T values."
        ),
        "3": (
            "Mix of concrete and vague; some TBDs left unresolved."
        ),
        "1": (
            "Mostly vague (`use appropriate compiler`, `test thoroughly`)."
        ),
    },
    "ordering_and_dependencies": {
        "what": (
            "Is the subtask DAG well-formed? Are dependencies correctly "
            "identified? Is the order logical and parallelism noted where "
            "it exists?"
        ),
        "5": (
            "Explicit `depends_on` chain; topological order respected; "
            "parallel branches called out."
        ),
        "3": (
            "Order works but rationale or parallel opportunities are "
            "missing."
        ),
        "1": (
            "Sequencing errors, dangling dependencies, or impossible "
            "ordering."
        ),
    },
    "error_handling": {
        "what": (
            "Are edge cases enumerated explicitly (empty input, "
            "singleton, degenerate, overflow / NaN where applicable) and "
            "tied to specific tests with explicit tolerance?"
        ),
        "5": (
            "All required edge cases enumerated, mapped to named tests, "
            "with concrete tolerance (exact == for int, |a-b|<eps for "
            "float)."
        ),
        "3": (
            "Some enumerated, others implied; tolerance partly stated."
        ),
        "1": (
            "No edge case treatment, or only generic mention of "
            "`handle errors`."
        ),
    },
    "testability": {
        "what": (
            "Does the plan include a usable testing strategy: oracle, "
            "harness with small/medium/large sizes, deterministic seed, "
            "explicit pass/fail criteria?"
        ),
        "5": (
            "Oracle named; harness sizes specified; seed fixed; "
            "tolerance + exit-code semantics defined."
        ),
        "3": (
            "Strategy sketched but missing one of: oracle, sizes, seed, "
            "tolerance."
        ),
        "1": (
            "`Write tests` with no detail — not actionable."
        ),
    },
    "clarity": {
        "what": (
            "Could another engineer execute this plan without "
            "ambiguity? Are subtask sections well-organized and "
            "self-contained?"
        ),
        "5": (
            "Subtask sections clear, deliverables named, dependencies "
            "explicit; an engineer could pick up any subtask cold."
        ),
        "3": (
            "Readable but requires interpretation in places."
        ),
        "1": (
            "Ambiguous or disorganized; hard to act on."
        ),
    },
    "grounding": {
        "what": (
            "Are cluster-facing decisions (toolchain, hostname, fabric, "
            "storage tier, R x T, walltime, memory) cited to specific "
            "files / sections in the staged context "
            "(cluster_ares.yaml, slurm_usage.md, storage_decision_guide.md)?"
        ),
        "5": (
            "Every cluster decision has a precise citation "
            "(e.g. `cluster_ares.yaml:fabric.notes`, "
            "`slurm_usage.md` section name)."
        ),
        "3": (
            "Some decisions cited, others ungrounded or cite only the "
            "filename."
        ),
        "1": (
            "No citations or invented cluster facts."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PlanFile:
    case_name: str
    framework: str          # e.g. "multi_gen" — kept for traceability
    model_name: str
    repeat: int
    path: Path


@dataclass
class GradeResult:
    case_name: str
    model_name: str
    reference_model: str
    judge_model: str
    grades: dict[str, Any] = field(default_factory=dict)
    overall_score: float | None = None
    summary: str = ""
    error: str | None = None
    timestamp: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Plan discovery
# ─────────────────────────────────────────────────────────────────────────────

# Filenames look like:
#   multi_gen_mpi+omp_41_sort_k-th_smallest_element__claude-opus-4-7__r1.md
# Split on the literal `__` separator. We accept any number of repeats.
_PLAN_RE = re.compile(r"^(?P<case>.+?)__(?P<model>[^_].+?)__r(?P<rep>\d+)$")


def discover_plans(plans_dir: Path) -> list[PlanFile]:
    found: list[PlanFile] = []
    for p in sorted(plans_dir.glob("*.md")):
        m = _PLAN_RE.match(p.stem)
        if not m:
            log.warning("Skipping unparseable filename: %s", p.name)
            continue
        case = m.group("case")
        model = m.group("model")
        rep = int(m.group("rep"))
        # `framework` is the leading token of the case name; we keep the
        # full case name for grouping and just record the leading token.
        framework = case.split("_", 1)[0]
        found.append(
            PlanFile(case_name=case, framework=framework,
                     model_name=model, repeat=rep, path=p)
        )
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Grading prompt
# ─────────────────────────────────────────────────────────────────────────────

def _format_rubric() -> str:
    lines: list[str] = []
    for cat, body in RUBRIC.items():
        lines.append(f"### {cat}")
        lines.append(body["what"])
        lines.append("")
        lines.append(f"  - 5 — {body['5']}")
        lines.append(f"  - 3 — {body['3']}")
        lines.append(f"  - 1 — {body['1']}")
        lines.append("  - 2 and 4 are interpolated between adjacent anchors.")
        lines.append("")
    return "\n".join(lines)


def build_grading_prompt(
    objective: str,
    reference_plan: str,
    candidate_plan: str,
) -> str:
    cat_keys = list(RUBRIC.keys())
    json_template_lines = [
        f'    "{k}": {{"score": <1-5>, "reasoning": "<1-2 sentences>"}},'
        for k in cat_keys
    ]
    # drop trailing comma on last entry to keep strict JSON
    json_template_lines[-1] = json_template_lines[-1].rstrip(",")
    json_template = "\n".join(json_template_lines)

    return f"""\
You are an expert plan evaluator for parallel-computing implementation
plans on the IIT Ares HPC cluster. You will grade a CANDIDATE plan
against a REFERENCE plan that was selected (out-of-band) as a strong
example of a good plan for this task.

The reference is a calibration anchor — it shows what a well-formed
plan for this objective looks like. The candidate may legitimately
differ in approach; do NOT penalize a candidate just for taking a
different but equally valid route. Penalize when the candidate is
less complete, less correct, less specific, less grounded, or harder
to act on than the rubric anchors require.

## Objective (verbatim from the planning prompt)

{objective}

## Reference plan (calibration anchor — not the only valid solution)

{reference_plan}

## Candidate plan (the one you are grading)

{candidate_plan}

## Rubric (8 categories, 1-5 scale, anchored)

{_format_rubric()}

## Output

Respond with ONLY a JSON object — no markdown fences, no preamble:

{{
  "grades": {{
{json_template}
  }},
  "overall_score": <float, unweighted mean of the 8 scores, 2 decimals>,
  "summary": "<2-3 sentences: where this candidate is stronger or weaker than the reference, in rubric terms>"
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Judge call (Claude Agent SDK)
# ─────────────────────────────────────────────────────────────────────────────

async def grade_one(
    objective: str,
    reference_plan: str,
    candidate: PlanFile,
    reference_model: str,
    judge_model: str,
    cwd: Path,
) -> GradeResult:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        query,
    )

    res = GradeResult(
        case_name=candidate.case_name,
        model_name=candidate.model_name,
        reference_model=reference_model,
        judge_model=judge_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    candidate_text = candidate.path.read_text()

    prompt = build_grading_prompt(
        objective=objective,
        reference_plan=reference_plan,
        candidate_plan=candidate_text,
    )

    options = ClaudeAgentOptions(
        model=judge_model,
        permission_mode="plan",      # judge does not execute anything
        cwd=str(cwd),
        disallowed_tools=["AskUserQuestion"],
    )

    response_text = ""
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
    except Exception as e:
        res.error = f"{type(e).__name__}: {e}"
        return res

    # Be forgiving with markdown fences
    clean = response_text.strip()
    if clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:])
    if clean.endswith("```"):
        clean = "\n".join(clean.split("\n")[:-1])
    clean = clean.strip()

    try:
        parsed = json.loads(clean)
        res.grades = parsed.get("grades", {})
        res.overall_score = parsed.get("overall_score")
        res.summary = parsed.get("summary", "")
        # Recompute mean if the judge omitted or fudged it
        scores = [
            v["score"] for v in res.grades.values()
            if isinstance(v, dict) and isinstance(v.get("score"), (int, float))
        ]
        if scores:
            recomputed = round(sum(scores) / len(scores), 2)
            if (
                res.overall_score is None
                or abs(float(res.overall_score) - recomputed) > 0.05
            ):
                res.overall_score = recomputed
    except json.JSONDecodeError as e:
        res.error = f"Failed to parse judge JSON: {e}"
        res.summary = response_text[:2000]

    return res


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────

def _save_grade(grade_dir: Path, res: GradeResult) -> Path:
    grade_dir.mkdir(parents=True, exist_ok=True)
    safe_model = res.model_name.replace("/", "_").replace(":", "_")
    out = grade_dir / f"{res.case_name}__{safe_model}__graded.json"
    out.write_text(json.dumps({
        "case_name": res.case_name,
        "model_name": res.model_name,
        "reference_model": res.reference_model,
        "judge_model": res.judge_model,
        "timestamp": res.timestamp,
        "grades": res.grades,
        "overall_score": res.overall_score,
        "summary": res.summary,
        "error": res.error,
    }, indent=2))
    return out


def _write_summary_csv(grade_dir: Path, results: list[GradeResult]) -> Path:
    out = grade_dir / "summary.csv"
    cats = list(RUBRIC.keys())
    fieldnames = (
        ["case_name", "model_name", "reference_model", "judge_model",
         "overall_score"]
        + cats
        + ["error"]
    )
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = {
                "case_name": r.case_name,
                "model_name": r.model_name,
                "reference_model": r.reference_model,
                "judge_model": r.judge_model,
                "overall_score": r.overall_score,
                "error": r.error or "",
            }
            for c in cats:
                row[c] = (r.grades.get(c) or {}).get("score")
            w.writerow(row)
    return out


async def run(args: argparse.Namespace) -> int:
    run_dir: Path = args.run_dir.resolve()
    plans_dir = run_dir / "plans"
    prompts_dir = run_dir / "prompts"
    workdirs_dir = run_dir / "workdirs"
    grade_dir = run_dir / "grades"

    if not plans_dir.is_dir():
        log.error("No plans dir at %s", plans_dir)
        return 2
    if not prompts_dir.is_dir():
        log.error("No prompts dir at %s", prompts_dir)
        return 2

    plans = discover_plans(plans_dir)
    if args.case:
        plans = [p for p in plans if p.case_name == args.case]
        if not plans:
            log.error("No plans match --case %s", args.case)
            return 2

    # Group by case
    by_case: dict[str, list[PlanFile]] = {}
    for p in plans:
        by_case.setdefault(p.case_name, []).append(p)

    results: list[GradeResult] = []
    for case_name, case_plans in by_case.items():
        # Find the reference plan for this case
        ref_candidates = [p for p in case_plans
                          if p.model_name == args.reference_model]
        if not ref_candidates:
            log.warning(
                "Case %s: no plan for reference model %s — skipping case",
                case_name, args.reference_model,
            )
            continue
        # If multiple repeats exist, take r1 deterministically
        ref = sorted(ref_candidates, key=lambda p: p.repeat)[0]
        reference_text = ref.path.read_text()

        # Objective from the prompt file
        prompt_path = prompts_dir / f"{case_name}.md"
        if not prompt_path.exists():
            log.warning("Case %s: missing prompt %s — skipping",
                        case_name, prompt_path)
            continue
        objective = prompt_path.read_text()

        # Working dir for the judge's `cwd` (read-only context)
        case_workdir = workdirs_dir / case_name
        if not case_workdir.exists():
            case_workdir = run_dir  # harmless fallback

        # Candidate set
        candidates = [p for p in case_plans
                      if p.model_name != args.reference_model
                      or args.include_reference]

        log.info("Case %s: reference=%s, %d candidate(s)",
                 case_name, args.reference_model, len(candidates))

        for cand in candidates:
            grade_path = (
                grade_dir
                / f"{cand.case_name}__"
                  f"{cand.model_name.replace('/', '_').replace(':', '_')}"
                  f"__graded.json"
            )
            if args.skip_existing and grade_path.exists():
                try:
                    existing = json.loads(grade_path.read_text())
                    if not existing.get("error"):
                        log.info("  skip (cached): %s", cand.model_name)
                        # Reload into results so summary.csv stays consistent
                        results.append(GradeResult(
                            case_name=existing["case_name"],
                            model_name=existing["model_name"],
                            reference_model=existing["reference_model"],
                            judge_model=existing["judge_model"],
                            grades=existing.get("grades", {}),
                            overall_score=existing.get("overall_score"),
                            summary=existing.get("summary", ""),
                            error=existing.get("error"),
                            timestamp=existing.get("timestamp", ""),
                        ))
                        continue
                except Exception:
                    pass  # fall through and re-grade

            log.info("  grading: %s", cand.model_name)
            res = await grade_one(
                objective=objective,
                reference_plan=reference_text,
                candidate=cand,
                reference_model=args.reference_model,
                judge_model=args.judge_model,
                cwd=case_workdir,
            )
            saved = _save_grade(grade_dir, res)
            log.info("    -> %s (overall=%s)",
                     saved.name, res.overall_score)
            results.append(res)

    if not results:
        log.error("No grades produced.")
        return 1

    summary = _write_summary_csv(grade_dir, results)
    log.info("Summary: %s  (%d rows)", summary, len(results))

    # Per-model mean across cases
    per_model: dict[str, list[float]] = {}
    for r in results:
        if r.overall_score is not None:
            per_model.setdefault(r.model_name, []).append(float(r.overall_score))
    log.info("Per-model mean overall score:")
    for m, scores in sorted(per_model.items(),
                            key=lambda kv: -sum(kv[1]) / len(kv[1])):
        log.info("  %-30s  mean=%.2f  n=%d",
                 m, sum(scores) / len(scores), len(scores))

    return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-dir", type=Path, required=True,
                   help="motivation_outputs/run_<TS> directory containing "
                        "plans/, prompts/, workdirs/")
    p.add_argument("--case", type=str, default=None,
                   help="Grade only this case (default: all cases)")
    p.add_argument("--reference-model", type=str, default="claude-opus-4-7",
                   help="Model whose plan is used as the reference "
                        "(default: claude-opus-4-7)")
    p.add_argument("--judge-model", type=str, default="claude-opus-4-7",
                   help="Model used as the judge (default: claude-opus-4-7)")
    p.add_argument("--include-reference", action="store_true",
                   help="Also grade the reference model's plan against "
                        "itself (sanity check; should score ~5/5)")
    p.add_argument("--skip-existing", action="store_true",
                   help="Skip grades that already exist on disk without "
                        "an error field")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Verbose logging")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
