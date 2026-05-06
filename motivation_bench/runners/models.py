"""Shared dataclasses — the contracts between runner modules.

ModelSpec    — declares a model and how to reach it (Anthropic vs local-via-base-url).
CaseSpec     — one task to plan: prompt + working_dir of context files.
PlanOutput   — the result of one planning run; appended to JSONL log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass(frozen=True)
class ModelSpec:
    """Declaration of a model and how the SDK should reach it."""

    name: str
    provider: Literal["anthropic", "ollama", "vllm", "lm_studio"]
    api_base_url: Optional[str] = None    # required for non-anthropic
    disable_thinking: bool = False        # set for models whose thinking blocks lack signature
    label: Optional[str] = None

    @property
    def is_local(self) -> bool:
        return self.provider != "anthropic"

    @property
    def display_name(self) -> str:
        return self.label or self.name


@dataclass
class CaseSpec:
    """One planning task. The working_dir is staged with context files per case."""

    case_id: str
    prompt: str
    working_dir: Path
    metadata: dict = field(default_factory=dict)


@dataclass
class PlanOutput:
    """One run record. Serialized to JSONL after each dispatch."""

    case_id: str
    model_name: str
    provider: str
    repeat: int

    timestamp_utc: str = ""
    duration_wall_s: float = 0.0
    duration_ms_sdk: Optional[float] = None

    plan_markdown: Optional[str] = None
    reasoning_text: str = ""
    thinking_text: str = ""

    num_turns: Optional[int] = None
    num_tool_calls: int = 0
    tool_call_sequence: list[str] = field(default_factory=list)

    total_cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    session_id: Optional[str] = None
    error: Optional[str] = None
    used_fallback: bool = False           # ExitPlanMode never fired; reasoning_text used

    plan_structured: Optional[dict] = None  # filled later by structurize.py
