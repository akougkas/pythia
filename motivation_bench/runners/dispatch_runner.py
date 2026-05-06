"""Top-level dispatcher.

Reads a workload's requests JSON, fans out across (case × model × repeat),
invokes the plan-mode provider, archives plans, and logs JSONL. The workload
is selected by the path passed to --requests; the case factory derives the
workload directory from that path and stages any context files that workload
ships next to its requests JSON.

Supported workloads (and the requests file shape they expect — see
`motivation_bench/workloads/<name>/`):
- hpc_cg_complex   (rich brief + cluster_ares.yaml staged into each working dir)
- hpc_cg_multi     (rich brief, all context inline in the prompt — no staging)

Usage:
    python -m motivation_bench.runners.dispatch_runner \\
        --requests motivation_bench/workloads/hpc_cg_multi/hpc_cg_multi_requests_verify.json \\
        --models claude-haiku-4-5 claude-sonnet-4-6 claude-opus-4-7 gpt-oss:20b \\
        --repeats 3 \\
        --out motivation_bench/runners/results/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

from .case_factory import build_cases
from .models import CaseSpec, ModelSpec, PlanOutput
from .providers.agent_sdk import AgentSDKPlanMode
from .providers.base import PlanningProvider
from .registry import ALL_MODELS, get_model

log = logging.getLogger(__name__)


# ── Output layout ─────────────────────────────────────────────────────


def make_run_dir(out_root: Path, requests_path: Path) -> Path:
    workload = requests_path.parent.name
    stamp = time.strftime("%Y%m%dT%H%M%S")
    run = out_root / workload / f"run_{stamp}"
    (run / "plans").mkdir(parents=True, exist_ok=True)
    (run / "prompts").mkdir(parents=True, exist_ok=True)
    (run / "workdirs").mkdir(parents=True, exist_ok=True)
    return run


def archive_prompt(run_dir: Path, case: CaseSpec, prompt: str) -> Path:
    """Write the composed prompt for a case to prompts/<case_id>.md.

    Useful for cross-provider manual comparison (e.g., paste into Gemini
    CLI) and as a reproducibility record of exactly what was sent.
    """
    path = run_dir / "prompts" / f"{case.case_id}.md"
    path.write_text(prompt)
    return path


def archive_plan(run_dir: Path, output: PlanOutput) -> None:
    fname = f"{output.case_id}__{output.model_name.replace(':', '_')}__r{output.repeat}.md"
    (run_dir / "plans" / fname).write_text(output.plan_markdown or "")


def append_jsonl(run_dir: Path, output: PlanOutput) -> None:
    with open(run_dir / "runs.jsonl", "a") as f:
        f.write(json.dumps(asdict(output), default=str) + "\n")


# ── Single-cell dispatch ──────────────────────────────────────────────


async def run_one(
    provider: PlanningProvider,
    case: CaseSpec,
    model: ModelSpec,
    repeat: int,
    run_dir: Path,
) -> PlanOutput:
    output = await provider.generate_plan(case, model)
    output.repeat = repeat
    archive_plan(run_dir, output)
    append_jsonl(run_dir, output)
    log.info(
        "  %s × %s × r%d: %.1fs, %d tool calls, plan=%d chars%s%s",
        case.case_id, model.name, repeat,
        output.duration_wall_s, output.num_tool_calls,
        len(output.plan_markdown or ""),
        " (FALLBACK)" if output.used_fallback else "",
        f" ERR: {output.error}" if output.error else "",
    )
    return output


# ── Main loop ─────────────────────────────────────────────────────────


async def main_async(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    run_dir = make_run_dir(Path(args.out), Path(args.requests))
    log.info("Run directory: %s", run_dir)

    cases = build_cases(Path(args.requests), run_dir / "workdirs")
    if args.case_id:
        cases = [c for c in cases if c.case_id == args.case_id]
        if not cases:
            raise SystemExit(f"No case matched --case-id {args.case_id!r}")
    if args.limit:
        cases = cases[: args.limit]
    if "all" in args.models:
        models = list(ALL_MODELS)
    else:
        models = [get_model(n) for n in args.models]
    log.info("Models: %s", ", ".join(f"{m.name} ({m.provider})" for m in models))
    log.info(
        "Dispatching %d cases × %d models × %d repeats = %d runs",
        len(cases), len(models), args.repeats,
        len(cases) * len(models) * args.repeats,
    )

    provider = AgentSDKPlanMode()

    for case in cases:
        log.info("\n=== %s ===", case.case_id)
        prompt_path = archive_prompt(run_dir, case, provider.compose_prompt(case))
        log.info("  prompt → %s", prompt_path)
        for model in models:
            for repeat in range(1, args.repeats + 1):
                try:
                    await run_one(provider, case, model, repeat, run_dir)
                except Exception:
                    log.exception(
                        "Dispatch failed: %s × %s × r%d",
                        case.case_id, model.name, repeat,
                    )

    log.info("\nDone. Results: %s", run_dir)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests", required=True, type=Path,
                   help="Path to a workload's requests JSON "
                        "(e.g. workloads/hpc_cg_multi/hpc_cg_multi_requests_verify.json). "
                        "The workload directory is derived from this path.")
    p.add_argument("--models", required=True, nargs="+",
                   help="Model names from registry.py (e.g. claude-opus-4-7 "
                        "gpt-oss:20b), or the literal token 'all' to expand "
                        "to every model registered in registry.ALL_MODELS.")
    p.add_argument("--repeats", type=int, default=3,
                   help="Repeats per (case, model) cell")
    p.add_argument("--limit", type=int, default=None,
                   help="Take the first N cases from the requests JSON")
    p.add_argument("--case-id", type=str, default=None,
                   help="Only run this specific case_id")
    p.add_argument("--out", required=True, type=Path,
                   help="Output root; a timestamped subdir is created under it")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
