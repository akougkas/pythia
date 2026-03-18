#!/usr/bin/env python3
"""
eval1.py — Plan Generation & Evaluation Harness
=================================================

Loops through:
    C cases  ×  F frameworks  ×  M models  =  C·F·M plans

Phase 1: Generate plans (planning mode, no execution)
Phase 2: Human picks reference plan per case (best F×M combo)
Phase 3: Semantic grading — Opus judges each plan against the reference

Directory structure:
    cases/
      case_001_add_numbers/
        PROMPT.md
        WorkingDir/
    results/
      case_001_add_numbers/
        plans/
          claude_code__claude-sonnet-4-6.md
          claude_code__glm-4.7-flash.md
          aider__claude-sonnet-4-6.md          # future framework
        grades/
          claude_code__glm-4.7-flash__graded.json
        reference_plan.md                       # human-selected best
    eval_summary.json

Usage:
    # Phase 1 — generate all plans
    python eval1.py generate --cases-dir ./cases

    # Phase 1 — generate for one case only
    python eval1.py generate --cases-dir ./cases --case case_001_add_numbers

    # Phase 1 — with Ollama models included
    python eval1.py generate --cases-dir ./cases --include-ollama

    # Phase 2 — mark a reference plan
    python eval1.py set-reference \\
        --case case_001_add_numbers \\
        --plan claude_code__claude-sonnet-4-6.md

    # Phase 3 — grade all plans against references
    python eval1.py grade --cases-dir ./cases

    # Full report
    python eval1.py report
"""

from __future__ import annotations

import abc
import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# We import claude_agent_sdk lazily so the file can be read/linted without it
# ---------------------------------------------------------------------------

log = logging.getLogger("eval1")


# ═══════════════════════════════════════════════════════════════════════════
# §1  DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CaseSpec:
    """A single evaluation case loaded from disk."""

    name: str              # e.g. "case_001_add_numbers"
    prompt: str            # contents of PROMPT.md
    working_dir: Path      # absolute path to WorkingDir/
    case_dir: Path         # absolute path to the case root


@dataclass
class ModelSpec:
    """A model to test."""

    name: str              # e.g. "claude-sonnet-4-6", "glm-4.7-flash"
    provider: str          # "anthropic" | "ollama"
    api_base_url: str = ""  # e.g. Ollama or LM Studio endpoint


@dataclass
class PlanOutput:
    """Result of a single planning run."""

    case_name: str
    framework_name: str
    model_name: str
    provider: str
    plan_text: str | None = None
    reasoning_text: str = ""
    thinking_text: str = ""
    session_id: str | None = None
    duration_ms: int = 0
    duration_wall_s: float = 0.0
    total_cost_usd: float | None = None
    num_turns: int = 0
    error: str | None = None
    timestamp: str = ""


@dataclass
class GradeResult:
    """Semantic grade of a plan vs. the reference."""

    case_name: str
    framework_name: str
    model_name: str
    grades: dict[str, Any] = field(default_factory=dict)
    overall_score: float | None = None
    judge_reasoning: str = ""
    error: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# §2  GRADING CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════

GRADING_CATEGORIES: dict[str, str] = {
    "completeness": (
        "Does the plan cover ALL deliverables and requirements stated in the "
        "objective? Are any steps or outputs missing?"
    ),
    "correctness": (
        "Are the proposed steps technically sound? Would following them "
        "actually achieve the objective without errors?"
    ),
    "specificity": (
        "Does the plan give concrete, actionable steps (file names, function "
        "signatures, library choices) rather than vague intentions?"
    ),
    "ordering_and_dependencies": (
        "Are steps in a logical order? Are dependencies between steps "
        "correctly identified and sequenced?"
    ),
    "error_handling": (
        "Does the plan account for edge cases, input validation, and error "
        "handling as required by the objective?"
    ),
    "testability": (
        "Does the plan include a testing strategy? Are the proposed tests "
        "sufficient to validate the deliverables?"
    ),
    "clarity": (
        "Is the plan well-organized and easy to follow? Could another "
        "developer execute it without ambiguity?"
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# §3  FRAMEWORK ABSTRACTION  (the extensibility point)
# ═══════════════════════════════════════════════════════════════════════════

class PlanningFramework(abc.ABC):
    """
    Abstract base for any agentic coding framework that can produce a plan.

    To add a new framework (Aider, OpenHands, SWE-agent, etc.):
      1. Subclass PlanningFramework
      2. Implement `generate_plan()`
      3. Register it in FRAMEWORK_REGISTRY
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'claude_code', 'aider', 'openhands'."""
        ...

    @abc.abstractmethod
    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        """Run the framework in planning mode and return the plan."""
        ...


# ── Claude Code (Agent SDK) ──────────────────────────────────────────────

class ClaudeCodeFramework(PlanningFramework):
    """
    Uses the Claude Agent SDK (`claude-agent-sdk`) in planning mode.

    - permission_mode="plan" → no file writes, produces ExitPlanMode tool call
    - For Ollama models: injects ANTHROPIC_BASE_URL via env
    """

    @property
    def name(self) -> str:
        return "claude_code"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
            query,
        )

        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # ── Build options ──
        opts_kwargs: dict[str, Any] = {
            "permission_mode": "plan",
            "model": model.name,
            "cwd": str(case.working_dir),
        }

        if model.provider in ("ollama", "lm_studio"):
            opts_kwargs["env"] = {
                "ANTHROPIC_BASE_URL": model.api_base_url,
                "ANTHROPIC_AUTH_TOKEN": "local",
                "ANTHROPIC_API_KEY": "local",
            }

        options = ClaudeAgentOptions(**opts_kwargs)

        # ── Compose prompt ──
        prompt = (
            f"You are in planning mode. Read the objective below and produce "
            f"a detailed, step-by-step implementation plan. Do NOT execute "
            f"anything — only plan.\n\n"
            f"## Objective\n\n{case.prompt}\n\n"
            f"## Working Directory\n\n"
            f"The working directory is: {case.working_dir}\n"
            f"Inspect it if needed for context materials."
        )

        # ── Run ──
        t0 = time.monotonic()
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result.reasoning_text += block.text + "\n"
                        elif isinstance(block, ThinkingBlock):
                            result.thinking_text += block.thinking + "\n"
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "ExitPlanMode":
                                result.plan_text = block.input.get("plan", "")

                elif isinstance(message, ResultMessage):
                    result.session_id = message.session_id
                    result.duration_ms = message.duration_ms
                    result.total_cost_usd = message.total_cost_usd
                    result.num_turns = message.num_turns

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        return result


# ── Stub: Aider ──────────────────────────────────────────────────────────

class AiderFramework(PlanningFramework):
    """
    Placeholder for Aider integration.

    Aider has an `--architect` mode that produces plans.
    Implementation would shell out to `aider --architect --yes ...`
    and parse the output.
    """

    @property
    def name(self) -> str:
        return "aider"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        # TODO: Implement aider --architect mode
        return PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error="Aider framework not yet implemented",
        )


# ── Stub: OpenHands / SWE-agent / etc. ──────────────────────────────────

class OpenHandsFramework(PlanningFramework):
    """Placeholder for OpenHands (formerly OpenDevin) integration."""

    @property
    def name(self) -> str:
        return "openhands"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        return PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error="OpenHands framework not yet implemented",
        )


# ── Registry ─────────────────────────────────────────────────────────────

FRAMEWORK_REGISTRY: dict[str, PlanningFramework] = {
    "claude_code": ClaudeCodeFramework(),
    "aider": AiderFramework(),
    "openhands": OpenHandsFramework(),
}

# Default active frameworks (override with --frameworks)
DEFAULT_FRAMEWORKS = ["claude_code"]


# ═══════════════════════════════════════════════════════════════════════════
# §4  MODEL CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════

ANTHROPIC_MODELS: list[ModelSpec] = [
    ModelSpec(name="claude-sonnet-4-6", provider="anthropic"),
    ModelSpec(name="claude-opus-4-6", provider="anthropic"),
    ModelSpec(name="claude-haiku-4-5-20251001", provider="anthropic"),
]

OLLAMA_MODELS: list[ModelSpec] = [
    ModelSpec(name="glm-4.7-flash", provider="ollama", api_base_url="http://localhost:11434"),
    # ModelSpec(name="qwen3-coder", provider="ollama", api_base_url="http://localhost:11434"),
    # ModelSpec(name="devstral-small", provider="ollama", api_base_url="http://localhost:11434"),
]

LM_STUDIO_MODELS: list[ModelSpec] = [
    ModelSpec(name="your-model-name", provider="lm_studio", api_base_url="http://localhost:1234/v1"),
    
]


# ═══════════════════════════════════════════════════════════════════════════
# §5  CASE LOADER
# ═══════════════════════════════════════════════════════════════════════════

def load_cases(cases_dir: Path, case_filter: str | None = None) -> list[CaseSpec]:
    """
    Load cases from the cases/ directory.

    Each case is a subdirectory containing PROMPT.md and optionally WorkingDir/.
    """
    cases = []
    if not cases_dir.is_dir():
        log.error(f"Cases directory does not exist: {cases_dir}")
        return cases

    for entry in sorted(cases_dir.iterdir()):
        if not entry.is_dir():
            continue
        if case_filter and entry.name != case_filter:
            continue

        prompt_file = entry / "PROMPT.md"
        if not prompt_file.exists():
            log.warning(f"Skipping {entry.name}: no PROMPT.md")
            continue

        working_dir = entry / "WorkingDir"
        if not working_dir.exists():
            working_dir.mkdir(parents=True)

        cases.append(CaseSpec(
            name=entry.name,
            prompt=prompt_file.read_text(),
            working_dir=working_dir.resolve(),
            case_dir=entry.resolve(),
        ))

    log.info(f"Loaded {len(cases)} case(s)")
    return cases


# ═══════════════════════════════════════════════════════════════════════════
# §6  PLAN PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════

def plan_filename(framework: str, model: str) -> str:
    """Deterministic filename for a plan: framework__model.md"""
    safe_model = model.replace("/", "_").replace(":", "_")
    return f"{framework}__{safe_model}.md"


def save_plan(results_dir: Path, output: PlanOutput) -> Path:
    """Write a plan to disk as Markdown with YAML-ish front matter."""
    plan_dir = results_dir / output.case_name / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)

    fname = plan_filename(output.framework_name, output.model_name)
    path = plan_dir / fname

    lines = [
        f"---",
        f"case: {output.case_name}",
        f"framework: {output.framework_name}",
        f"model: {output.model_name}",
        f"provider: {output.provider}",
        f"session_id: {output.session_id}",
        f"duration_ms: {output.duration_ms}",
        f"duration_wall_s: {output.duration_wall_s:.1f}",
        f"cost_usd: {output.total_cost_usd}",
        f"num_turns: {output.num_turns}",
        f"timestamp: {output.timestamp}",
        f"error: {output.error}",
        f"---",
        f"",
    ]

    if output.error:
        lines.append(f"# ERROR\n\n{output.error}\n")
    elif output.plan_text:
        lines.append(f"# Plan\n\n{output.plan_text}\n")
    else:
        lines.append("# No Plan Captured\n\n")
        if output.reasoning_text.strip():
            lines.append(f"## Reasoning Output\n\n{output.reasoning_text}\n")

    path.write_text("\n".join(lines))
    log.info(f"  Saved plan → {path}")
    return path


def save_plan_metadata(results_dir: Path, output: PlanOutput) -> Path:
    """Save full metadata as JSON alongside the Markdown plan."""
    meta_dir = results_dir / output.case_name / "plans"
    meta_dir.mkdir(parents=True, exist_ok=True)

    safe_model = output.model_name.replace("/", "_").replace(":", "_")
    fname = f"{output.framework_name}__{safe_model}.json"
    path = meta_dir / fname

    data = {
        "case_name": output.case_name,
        "framework_name": output.framework_name,
        "model_name": output.model_name,
        "provider": output.provider,
        "plan_text": output.plan_text,
        "reasoning_text": output.reasoning_text,
        "thinking_text": output.thinking_text,
        "session_id": output.session_id,
        "duration_ms": output.duration_ms,
        "duration_wall_s": output.duration_wall_s,
        "total_cost_usd": output.total_cost_usd,
        "num_turns": output.num_turns,
        "error": output.error,
        "timestamp": output.timestamp,
    }
    path.write_text(json.dumps(data, indent=2))
    return path


# ═══════════════════════════════════════════════════════════════════════════
# §7  PHASE 1 — PLAN GENERATION
# ═══════════════════════════════════════════════════════════════════════════

async def phase1_generate(
    cases: list[CaseSpec],
    frameworks: list[PlanningFramework],
    models: list[ModelSpec],
    results_dir: Path,
    skip_existing: bool = True,
) -> list[PlanOutput]:
    """
    The big triple loop:  C cases × F frameworks × M models

    Generates C·F·M plans total.
    """
    all_outputs: list[PlanOutput] = []
    total = len(cases) * len(frameworks) * len(models)
    i = 0

    for case in cases:
        for fw in frameworks:
            for model in models:
                i += 1
                tag = f"[{i}/{total}] {case.name} | {fw.name} | {model.name}"

                # ── Skip if already generated ──
                existing = (
                    results_dir / case.name / "plans"
                    / plan_filename(fw.name, model.name)
                )
                if skip_existing and existing.exists():
                    log.info(f"  {tag} — SKIP (exists)")
                    continue

                log.info(f"  {tag} — generating...")

                output = await fw.generate_plan(case=case, model=model)
                save_plan(results_dir, output)
                save_plan_metadata(results_dir, output)
                all_outputs.append(output)

                # ── Progress summary ──
                status = "ERROR" if output.error else "OK"
                cost_str = (
                    f"${output.total_cost_usd:.4f}"
                    if output.total_cost_usd is not None
                    else "n/a"
                )
                log.info(
                    f"  {tag} — {status} | "
                    f"{output.duration_wall_s:.1f}s wall | "
                    f"{output.duration_ms}ms api | "
                    f"{cost_str}"
                )

    return all_outputs


# ═══════════════════════════════════════════════════════════════════════════
# §8  PHASE 2 — SET REFERENCE PLAN
# ═══════════════════════════════════════════════════════════════════════════

def set_reference_plan(
    results_dir: Path,
    case_name: str,
    plan_filename_str: str,
) -> None:
    """
    Mark a specific plan as the reference (best) for a case.

    Copies it to results/<case>/reference_plan.md
    """
    src = results_dir / case_name / "plans" / plan_filename_str
    if not src.exists():
        log.error(f"Plan not found: {src}")
        sys.exit(1)

    dst = results_dir / case_name / "reference_plan.md"
    shutil.copy2(src, dst)
    log.info(f"Set reference plan for {case_name}: {plan_filename_str} → {dst}")


def list_plans_for_case(results_dir: Path, case_name: str) -> list[str]:
    """List available .md plan files for a case."""
    plan_dir = results_dir / case_name / "plans"
    if not plan_dir.exists():
        return []
    return sorted(f.name for f in plan_dir.glob("*.md"))


# ═══════════════════════════════════════════════════════════════════════════
# §9  PHASE 3 — SEMANTIC GRADING VIA OPUS
# ═══════════════════════════════════════════════════════════════════════════

def build_grading_prompt(
    objective: str,
    reference_plan: str,
    candidate_plan: str,
    categories: dict[str, str],
) -> str:
    """
    Construct the prompt for Opus to grade a candidate plan.

    Returns a prompt that asks for JSON output with scores and reasoning.
    """
    cat_block = "\n".join(
        f"  - **{name}**: {desc}" for name, desc in categories.items()
    )

    return f"""\
You are an expert plan evaluator. You will grade a candidate implementation
plan against a reference plan that was selected as the best by human reviewers.

## Objective (what the plan is supposed to achieve)

{objective}

## Reference Plan (the gold standard)

{reference_plan}

## Candidate Plan (the one you are grading)

{candidate_plan}

## Grading Categories

Grade the candidate plan on each of the following categories using a scale
of 1–5 (1 = very poor, 5 = excellent):

{cat_block}

## Output Format

Respond with ONLY a JSON object (no markdown fences, no preamble):

{{
  "grades": {{
    "completeness": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "correctness": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "specificity": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "ordering_and_dependencies": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "error_handling": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "testability": {{"score": <1-5>, "reasoning": "<brief explanation>"}},
    "clarity": {{"score": <1-5>, "reasoning": "<brief explanation>"}}
  }},
  "overall_score": <float, average of all scores>,
  "summary": "<2-3 sentence overall assessment>"
}}
"""


async def grade_plan_with_opus(
    case: CaseSpec,
    reference_plan_text: str,
    candidate_plan_path: Path,
    candidate_meta: dict[str, str],
    results_dir: Path,
    judge_model: str = "claude-opus-4-6",
) -> GradeResult:
    """
    Use Opus (via Claude Agent SDK in non-planning mode) to grade a plan.

    We use query() with NO tools — just a pure LLM call for judgement.
    """
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        query,
    )

    candidate_text = candidate_plan_path.read_text()
    fw_name = candidate_meta.get("framework", "unknown")
    model_name = candidate_meta.get("model", "unknown")

    grade_result = GradeResult(
        case_name=case.name,
        framework_name=fw_name,
        model_name=model_name,
    )

    prompt = build_grading_prompt(
        objective=case.prompt,
        reference_plan=reference_plan_text,
        candidate_plan=candidate_text,
        categories=GRADING_CATEGORIES,
    )

    options = ClaudeAgentOptions(
        model=judge_model,
        # No tools, no planning mode — just judgement
        permission_mode="plan",  # safe: won't execute anything
        cwd=str(case.working_dir),
    )

    response_text = ""
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

    except Exception as e:
        grade_result.error = f"{type(e).__name__}: {e}"
        return grade_result

    # ── Parse JSON from Opus response ──
    try:
        # Strip markdown fences if present
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = "\n".join(clean.split("\n")[:-1])
        clean = clean.strip()

        parsed = json.loads(clean)
        grade_result.grades = parsed.get("grades", {})
        grade_result.overall_score = parsed.get("overall_score")
        grade_result.judge_reasoning = parsed.get("summary", "")
    except json.JSONDecodeError as e:
        grade_result.error = f"Failed to parse Opus JSON: {e}"
        grade_result.judge_reasoning = response_text

    # ── Save grade ──
    grade_dir = results_dir / case.name / "grades"
    grade_dir.mkdir(parents=True, exist_ok=True)
    safe_model = model_name.replace("/", "_").replace(":", "_")
    grade_path = grade_dir / f"{fw_name}__{safe_model}__graded.json"
    grade_path.write_text(json.dumps({
        "case_name": grade_result.case_name,
        "framework_name": grade_result.framework_name,
        "model_name": grade_result.model_name,
        "grades": grade_result.grades,
        "overall_score": grade_result.overall_score,
        "judge_reasoning": grade_result.judge_reasoning,
        "error": grade_result.error,
    }, indent=2))
    log.info(f"  Grade saved → {grade_path}")

    return grade_result


async def phase3_grade_all(
    cases: list[CaseSpec],
    results_dir: Path,
    judge_model: str = "claude-opus-4-6",
) -> list[GradeResult]:
    """
    For each case with a reference_plan.md, grade all other plans.
    """
    all_grades: list[GradeResult] = []

    for case in cases:
        ref_path = results_dir / case.name / "reference_plan.md"
        if not ref_path.exists():
            log.warning(
                f"No reference plan for {case.name} — "
                f"run `set-reference` first. Skipping."
            )
            continue

        reference_text = ref_path.read_text()
        plan_dir = results_dir / case.name / "plans"

        for plan_file in sorted(plan_dir.glob("*.md")):
            # Parse framework__model from filename
            stem = plan_file.stem  # e.g. "claude_code__claude-sonnet-4-6"
            parts = stem.split("__", 1)
            if len(parts) != 2:
                continue
            fw_name, model_name = parts

            # Skip grading the reference against itself
            ref_stem = ref_path.stem
            # (reference_plan.md doesn't match the pattern, so this is fine)

            log.info(f"  Grading {case.name} | {fw_name} | {model_name}...")

            grade = await grade_plan_with_opus(
                case=case,
                reference_plan_text=reference_text,
                candidate_plan_path=plan_file,
                candidate_meta={"framework": fw_name, "model": model_name},
                results_dir=results_dir,
                judge_model=judge_model,
            )
            all_grades.append(grade)

    return all_grades


# ═══════════════════════════════════════════════════════════════════════════
# §10  REPORTING
# ═══════════════════════════════════════════════════════════════════════════

def generate_report(results_dir: Path) -> str:
    """Generate a summary report from all grades."""
    lines = [
        "# Eval1 — Plan Quality Report",
        f"\nGenerated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    for case_dir in sorted(results_dir.iterdir()):
        if not case_dir.is_dir():
            continue

        grade_dir = case_dir / "grades"
        if not grade_dir.exists():
            continue

        lines.append(f"## {case_dir.name}")
        lines.append("")
        lines.append("| Framework | Model | Overall | Compl. | Corr. | Spec. | Order | Err.H | Test | Clarity |")
        lines.append("|-----------|-------|---------|--------|-------|-------|-------|-------|------|---------|")

        for grade_file in sorted(grade_dir.glob("*__graded.json")):
            data = json.loads(grade_file.read_text())
            grades = data.get("grades", {})

            def s(cat: str) -> str:
                g = grades.get(cat, {})
                score = g.get("score", "?")
                return str(score)

            overall = data.get("overall_score", "?")
            if isinstance(overall, float):
                overall = f"{overall:.1f}"

            lines.append(
                f"| {data.get('framework_name', '?')} "
                f"| {data.get('model_name', '?')} "
                f"| {overall} "
                f"| {s('completeness')} "
                f"| {s('correctness')} "
                f"| {s('specificity')} "
                f"| {s('ordering_and_dependencies')} "
                f"| {s('error_handling')} "
                f"| {s('testability')} "
                f"| {s('clarity')} |"
            )

        lines.append("")

        # Show judge reasoning
        for grade_file in sorted(grade_dir.glob("*__graded.json")):
            data = json.loads(grade_file.read_text())
            reasoning = data.get("judge_reasoning", "")
            if reasoning:
                lines.append(
                    f"**{data.get('framework_name')}/{data.get('model_name')}**: "
                    f"{reasoning}"
                )
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# §11  CLI
# ═══════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="eval1.py — Plan Generation & Evaluation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ── generate ──
    gen = sub.add_parser("generate", help="Phase 1: Generate plans")
    gen.add_argument("--cases-dir", type=Path, default=Path("./cases"))
    gen.add_argument("--results-dir", type=Path, default=Path("./results"))
    gen.add_argument("--case", default=None, help="Run only this case")
    gen.add_argument("--include-ollama", action="store_true")
    gen.add_argument("--ollama-url", default="http://localhost:11434")
    gen.add_argument("--include-lm-studio", action="store_true")
    gen.add_argument("--lm-studio-url", default="http://localhost:1234/v1")
    gen.add_argument(
        "--frameworks", nargs="+", default=DEFAULT_FRAMEWORKS,
        help=f"Frameworks to use (available: {list(FRAMEWORK_REGISTRY.keys())})",
    )
    gen.add_argument("--models", nargs="+", default=None,
                     help="Override model list (e.g., claude-sonnet-4-6 glm-4.7-flash)")
    gen.add_argument("--no-skip", action="store_true",
                     help="Regenerate even if plan already exists")
    gen.add_argument("-v", "--verbose", action="store_true")

    # ── set-reference ──
    ref = sub.add_parser("set-reference", help="Phase 2: Mark best plan")
    ref.add_argument("--results-dir", type=Path, default=Path("./results"))
    ref.add_argument("--case", required=True)
    ref.add_argument("--plan", required=True, help="Filename, e.g. claude_code__claude-sonnet-4-6.md")

    # ── list-plans ──
    lp = sub.add_parser("list-plans", help="List available plans for a case")
    lp.add_argument("--results-dir", type=Path, default=Path("./results"))
    lp.add_argument("--case", required=True)

    # ── grade ──
    gr = sub.add_parser("grade", help="Phase 3: Semantic grading via Opus")
    gr.add_argument("--cases-dir", type=Path, default=Path("./cases"))
    gr.add_argument("--results-dir", type=Path, default=Path("./results"))
    gr.add_argument("--judge-model", default="claude-opus-4-6")
    gr.add_argument("--case", default=None, help="Grade only this case")
    gr.add_argument("-v", "--verbose", action="store_true")

    # ── report ──
    rp = sub.add_parser("report", help="Generate summary report")
    rp.add_argument("--results-dir", type=Path, default=Path("./results"))
    rp.add_argument("--output", type=Path, default=None,
                     help="Write report to file (default: stdout)")

    return p.parse_args()


async def async_main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "generate":
        # ── Load cases ──
        cases = load_cases(args.cases_dir, case_filter=args.case)
        if not cases:
            log.error("No cases found.")
            sys.exit(1)

        # ── Resolve frameworks ──
        frameworks = []
        for fw_name in args.frameworks:
            fw = FRAMEWORK_REGISTRY.get(fw_name)
            if fw is None:
                log.error(f"Unknown framework: {fw_name}")
                sys.exit(1)
            frameworks.append(fw)

        # ── Resolve models ──
        if args.models:
            # User-specified model list
            models = []
            for m in args.models:
                # Heuristic: if it looks like an Anthropic model, tag it so
                if m.startswith("claude-"):
                    models.append(ModelSpec(name=m, provider="anthropic"))
                else:
                    models.append(ModelSpec(
                        name=m, provider="ollama",
                        api_base_url=args.ollama_url,
                    ))
        else:
            models = list(ANTHROPIC_MODELS)
            if args.include_ollama:
                for om in OLLAMA_MODELS:
                    om.api_base_url = args.ollama_url
                models.extend(OLLAMA_MODELS)
            if args.include_lm_studio:
                for lm in LM_STUDIO_MODELS:
                    lm.api_base_url = args.lm_studio_url
                models.extend(LM_STUDIO_MODELS)

        # ── Summary ──
        total = len(cases) * len(frameworks) * len(models)
        log.info(
            f"Phase 1: {len(cases)} cases × {len(frameworks)} frameworks "
            f"× {len(models)} models = {total} plans"
        )
        for c in cases:
            log.info(f"  Case: {c.name}")
        for fw in frameworks:
            log.info(f"  Framework: {fw.name}")
        for m in models:
            log.info(f"  Model: {m.name} ({m.provider})")

        # ── Generate ──
        results = await phase1_generate(
            cases=cases,
            frameworks=frameworks,
            models=models,
            results_dir=args.results_dir,
            skip_existing=not args.no_skip,
        )

        log.info(f"\nDone. Generated {len(results)} new plan(s).")

    elif args.command == "set-reference":
        set_reference_plan(args.results_dir, args.case, args.plan)

    elif args.command == "list-plans":
        plans = list_plans_for_case(args.results_dir, args.case)
        if not plans:
            print(f"No plans found for {args.case}")
        else:
            print(f"Plans for {args.case}:")
            for p in plans:
                print(f"  {p}")

    elif args.command == "grade":
        cases = load_cases(args.cases_dir, case_filter=args.case)
        if not cases:
            log.error("No cases found.")
            sys.exit(1)

        grades = await phase3_grade_all(
            cases=cases,
            results_dir=args.results_dir,
            judge_model=args.judge_model,
        )
        log.info(f"\nGraded {len(grades)} plan(s).")

        for g in grades:
            score = f"{g.overall_score:.1f}" if g.overall_score else "ERR"
            log.info(f"  {g.case_name} | {g.framework_name} | {g.model_name} → {score}")

    elif args.command == "report":
        report = generate_report(args.results_dir)
        if args.output:
            args.output.write_text(report)
            log.info(f"Report written to {args.output}")
        else:
            print(report)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
