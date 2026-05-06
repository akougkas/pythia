"""Hybrid plan schema for HPC-CG-complex dispatch experiments.

This is the contract for the agent's terminal `submit_plan` tool, shared
across all model arms (Claude Haiku/Sonnet/Opus via the Claude Agent SDK,
plus local models via vLLM/Ollama). The schema is enforced by the
runtime; reasoning lives inside the markdown-allowed string fields
(`description`, `hardware_footprint`, `mitigation`, `executive_summary`).

Design notes:
- Typed fields are what we diff/merge across plans (DAG, agent
  assignments, resource budgets).
- Markdown-allowed string fields preserve per-step reasoning. This is
  what makes the strong-vs-weak quality gap measurable.
- Soft minimums (`min_length`) enforce coverage: ≥5 subtasks (≥1 per
  stage), ≥5 resource-budget rows, ≥3 risks. Per-stage coverage is
  checked post-hoc by the harness.

Usage:
    from motivation_bench.runners.schemas import Plan
    schema = Plan.model_json_schema()           # JSON Schema for tool registration
    plan = Plan.model_validate(payload)         # parse + validate
    plan.model_dump_json(indent=2)              # serialize for archive
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ── Constrained primitives ────────────────────────────────────────────

StageInt = Annotated[int, Field(ge=1, le=5, description="Stage number, 1..5.")]

SpecialistAgent = Literal[
    "coder",      # writes code, build scripts, batch scripts
    "sysadmin",   # cluster discovery, module loads, environment
    "profiler",   # performance measurement, scaling study
    "validator",  # correctness oracle, regression checks
    "reviewer",   # plan/code/result review against requirements
    "tuner",      # hyperparameter / rank-thread / placement tuning
]


# ── Subtask ───────────────────────────────────────────────────────────


class Subtask(BaseModel):
    """A single planned subtask within one of the five stages."""

    id: str = Field(
        ...,
        description=(
            "Plan-unique identifier, e.g. 'S3.2'. Used as the key for "
            "depends_on and parallel_with edges."
        ),
    )
    stage: StageInt
    title: str = Field(..., description="Short imperative title.")
    specialist_agent: SpecialistAgent
    hardware_footprint: str = Field(
        ...,
        description=(
            "Which Ares nodes (master / compute-001..024 / compute-025..032), "
            "which storage tier, RAM and core budget, expected I/O footprint "
            "in GB. Markdown allowed."
        ),
    )
    token_budget_estimate: int = Field(
        ...,
        gt=0,
        description=(
            "Estimated LLM token cost (input + output) to execute this "
            "subtask. Strictly positive."
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Subtask ids that must complete before this one starts.",
    )
    parallel_with: list[str] = Field(
        default_factory=list,
        description=(
            "Subtask ids with no mutual dependency that can run "
            "concurrently with this subtask."
        ),
    )
    description: str = Field(
        ...,
        description=(
            "Reasoning, commands, configurations, justifications, and any "
            "nuance for this subtask. Markdown is allowed and encouraged "
            "here — this is where reasoning depth lives."
        ),
    )


# ── Resource budget row (per stage) ───────────────────────────────────


class ResourceBudgetRow(BaseModel):
    """Per-stage resource budget summary."""

    stage: StageInt
    nodes_used: int = Field(..., ge=0, description="Number of Ares nodes engaged in this stage.")
    peak_memory_gb: float = Field(..., ge=0, description="Peak aggregate memory (GB).")
    peak_io_gb: float = Field(..., ge=0, description="Peak intermediate I/O footprint (GB).")
    token_estimate: int = Field(..., ge=0, description="Sum of subtask token budgets in this stage.")


# ── Risk register entry ───────────────────────────────────────────────


class Risk(BaseModel):
    """One Ares-specific risk and its mitigation."""

    id: str = Field(..., description="Short stable id, e.g. 'roce_fallback'.")
    description: str = Field(..., description="What the risk is. Markdown allowed.")
    mitigation: str = Field(..., description="How the plan mitigates it. Markdown allowed.")


# ── The plan ──────────────────────────────────────────────────────────


class Plan(BaseModel):
    """Terminal output of the planning agent."""

    executive_summary: str = Field(
        ...,
        description=(
            "≤5 sentences summarising the chosen node subset, rank/thread "
            "split per problem size, and total walltime budget."
        ),
    )
    subtasks: list[Subtask] = Field(
        ...,
        min_length=5,
        description="At least one subtask per stage, covering all five stages.",
    )
    resource_budget: list[ResourceBudgetRow] = Field(
        ...,
        min_length=5,
        description="One row per stage.",
    )
    risk_register: list[Risk] = Field(
        ...,
        min_length=3,
        description="At least three Ares-specific risks with mitigations.",
    )


# ── Convenience: tool descriptor ──────────────────────────────────────


def submit_plan_tool_descriptor() -> dict:
    """Return the tool descriptor for terminal submit_plan registration.

    Use with the Claude Agent SDK and OpenAI-compatible function-calling
    endpoints (vLLM, Ollama). The schema travels via this descriptor —
    do NOT paste it into the user prompt.
    """
    return {
        "name": "submit_plan",
        "description": (
            "Submit the final structured deployment plan and end the "
            "planning session. After this is called, no further tool "
            "calls or text outputs are accepted."
        ),
        "input_schema": Plan.model_json_schema(),
    }
