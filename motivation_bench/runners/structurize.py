"""Markdown-plan → Plan Pydantic via a Haiku one-shot tool call.

Off the critical path. Run AFTER timing is taken; cheap (~$0.001 per
plan with Haiku); independent of the planning latency measurement.

Strategy: one chat completion to claude-haiku with the submit_plan
tool registered. The tool descriptor carries the Pydantic schema; the
model populates it from the markdown.
"""

from __future__ import annotations

import os
from typing import Optional

from .schemas import Plan, submit_plan_tool_descriptor

STRUCTURIZE_MODEL = os.environ.get("STRUCTURIZE_MODEL", "claude-haiku-4-5")

_SYSTEM = (
    "You are a parser. Convert the user's markdown HPC deployment plan "
    "into a structured Plan by calling the submit_plan tool exactly once. "
    "Preserve every subtask's reasoning verbatim inside the description "
    "field. Do not invent fields the markdown does not contain; if a "
    "value is missing, choose a reasonable default and proceed."
)


def structurize(plan_markdown: str, model: str = STRUCTURIZE_MODEL) -> Optional[Plan]:
    """Parse a markdown plan into Plan. Returns None on tool-call failure
    or schema-validation failure."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError(
            "structurize requires the `anthropic` package. "
            "Run: pip install anthropic"
        )

    client = Anthropic()
    tool = submit_plan_tool_descriptor()
    api_tool = {
        "name": tool["name"],
        "description": tool["description"],
        "input_schema": tool["input_schema"],
    }

    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=_SYSTEM,
        tools=[api_tool],
        tool_choice={"type": "tool", "name": "submit_plan"},
        messages=[{"role": "user", "content": plan_markdown}],
    )

    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_plan":
            try:
                return Plan.model_validate(block.input)
            except Exception:
                return None
    return None
