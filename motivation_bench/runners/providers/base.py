"""Abstract base for planning providers.

A provider takes a (CaseSpec, ModelSpec) pair, runs its planning workflow,
and returns a PlanOutput. Subclasses encapsulate framework-specific
mechanics (Claude Agent SDK plan mode, direct API, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CaseSpec, ModelSpec, PlanOutput


class PlanningProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate_plan(self, case: CaseSpec, model: ModelSpec) -> PlanOutput: ...

    @abstractmethod
    def compose_prompt(self, case: CaseSpec) -> str:
        """Return the exact prompt the provider will send for this case.

        Exposed so the dispatcher can archive prompts to disk for
        reproducibility and for cross-provider manual comparison
        (e.g., pasting into Gemini CLI).
        """
        ...
