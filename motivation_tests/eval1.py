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

    # Phase 2 — set reference plans (one per case)
    python eval1.py set-reference --results-dir ./results --case case_001_xcompact3d_deployment --plan claude_code__anthropic__claude-opus-4-6.md
    python eval1.py set-reference --results-dir ./results --case case_002_file_watcher --plan claude_code__anthropic__claude-opus-4-6.md
    python eval1.py set-reference --results-dir ./results --case case_003_data_pipeline --plan claude_code__anthropic__claude-opus-4-6.md

    # Phase 3 — grade all plans against references
    python eval1.py grade --cases-dir ./cases --results-dir ./results -v

    # Full report
    python eval1.py report --results-dir ./results --output eval_report.md
"""

from __future__ import annotations

import abc
import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
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
    provider: str          # "anthropic" | "ollama" | "lm_studio"
    api_base_url: str = ""  # e.g. Ollama or LM Studio endpoint
    context_length: int = 0  # 0 = use model's max context length
    disable_thinking: bool = False  # True for models that produce thinking blocks without Anthropic signature


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

        is_local = model.provider in ("ollama", "lm_studio")

        # ── Build options ──
        opts_kwargs: dict[str, Any] = {
            "permission_mode": "plan",
            "model": model.name,
            "cwd": str(case.working_dir),
            # Block interactive tools that would stall automated runs
            "disallowed_tools": ["AskUserQuestion"],
        }

        if is_local:
            opts_kwargs["env"] = {
                "ANTHROPIC_BASE_URL": model.api_base_url,
                "ANTHROPIC_AUTH_TOKEN": "local",
                "ANTHROPIC_API_KEY": "local",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": model.name,
                "CLAUDE_CODE_SUBAGENT_MODEL": model.name,
            }

            # Some local models (e.g. nemotron) produce thinking blocks
            # without the Anthropic-proprietary 'signature' field, causing
            # MessageParseError.  Disable thinking only for those models.
            # Models like Qwen3.5 work fine with thinking enabled.
            if model.disable_thinking:
                opts_kwargs["thinking"] = {"type": "disabled"}
            # Enable debug output to see what the CLI sends/receives
            # opts_kwargs["extra_args"] = {"debug-to-stderr": None}
            # opts_kwargs["stderr"] = lambda line: log.debug(f"  CLI: {line}")

        options = ClaudeAgentOptions(**opts_kwargs)

        # ── Compose prompt ──
        prompt = (
            f"You are in planning mode. Read the objective below and produce "
            f"a detailed, step-by-step implementation plan. Do NOT execute "
            f"anything — only plan.\n\n"
            f"IMPORTANT: Do NOT ask clarifying questions. Do NOT use the "
            f"AskUserQuestion tool. If any detail is ambiguous or missing, "
            f"make a reasonable assumption, state it explicitly in your plan, "
            f"and proceed. You must produce a complete plan in a single pass "
            f"without waiting for human input.\n\n"
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
                                exit_plan = block.input.get("plan", "")
                                if exit_plan and (result.plan_text is None or len(exit_plan) > len(result.plan_text)):
                                    result.plan_text = exit_plan
                            elif block.name == "Write" and "/.claude/plans/" in block.input.get("file_path", ""):
                                write_content = block.input.get("content", "")
                                if write_content and (result.plan_text is None or len(write_content) > len(result.plan_text)):
                                    result.plan_text = write_content

                elif isinstance(message, ResultMessage):
                    result.session_id = message.session_id
                    result.duration_ms = message.duration_ms
                    result.total_cost_usd = message.total_cost_usd
                    result.num_turns = message.num_turns

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0

        # Fallback: if ExitPlanMode was never called (common with local
        # models), use the collected text output as the plan.
        if result.plan_text is None and result.reasoning_text.strip():
            log.warning(
                f"  {model.name}: ExitPlanMode not called — "
                f"falling back to text output as plan"
            )
            result.plan_text = result.reasoning_text.strip()

        return result


# ── Direct API (OpenAI-compatible) ────────────────────────────────────────

class DirectAPIFramework(PlanningFramework):
    """
    Calls any OpenAI-compatible endpoint (LM Studio, Ollama, etc.) directly.

    Single-shot chat completion — no tools, no multi-turn, no SDK.
    Measures wall-clock latency and captures the raw text as the plan.
    """

    @property
    def name(self) -> str:
        return "direct_api"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # ── Compose prompt (same as ClaudeCodeFramework) ──
        prompt = (
            f"You are in planning mode. Read the objective below and produce "
            f"a detailed, step-by-step implementation plan. Do NOT execute "
            f"anything — only plan.\n\n"
            f"IMPORTANT: Do NOT ask clarifying questions. If any detail is "
            f"ambiguous or missing, make a reasonable assumption, state it "
            f"explicitly in your plan, and proceed. You must produce a "
            f"complete plan in a single pass without waiting for human input.\n\n"
            f"## Objective\n\n{case.prompt}\n\n"
            f"## Working Directory\n\n"
            f"The working directory is: {case.working_dir}\n"
            f"Inspect it if needed for context materials."
        )

        # ── Determine API endpoint ──
        if model.provider == "anthropic":
            # For Anthropic models, use the Anthropic messages API
            api_url = "https://api.anthropic.com/v1/messages"
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            body = json.dumps({
                "model": model.name,
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": prompt}],
            }).encode()
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        else:
            # OpenAI-compatible endpoint (LM Studio, Ollama, etc.)
            api_url = f"{model.api_base_url.rstrip('/')}/v1/chat/completions"
            body = json.dumps({
                "model": model.name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 8192,
            }).encode()
            headers = {
                "Content-Type": "application/json",
            }

        # ── Call API ──
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(api_url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw = json.loads(resp.read().decode())

            if model.provider == "anthropic":
                # Anthropic response format
                result.plan_text = "".join(
                    block["text"]
                    for block in raw.get("content", [])
                    if block.get("type") == "text"
                )
            else:
                # OpenAI-compatible response format
                result.plan_text = raw["choices"][0]["message"]["content"]

            result.num_turns = 1

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


# ── Gemini ADK (Google free tier) ─────────────────────────────────────────

class GeminiADKFramework(PlanningFramework):
    """
    Uses Google ADK (Agent Development Kit) with BuiltInPlanner.

    Creates an LlmAgent with BuiltInPlanner (ThinkingConfig) and runs it
    via InMemoryRunner.  Captures thinking parts (plan reasoning) and
    final response (the plan text) from the event stream.
    Tracks token usage for cost estimation.
    """

    @property
    def name(self) -> str:
        return "gemini_adk"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        from google.adk import Agent as LlmAgent
        from google.adk.planners import BuiltInPlanner
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        instruction = (
            "You are in planning mode. Read the objective the user gives you "
            "and produce a detailed, step-by-step implementation plan. Do NOT "
            "execute anything — only plan.\n\n"
            "IMPORTANT: Do NOT ask clarifying questions. If any detail is "
            "ambiguous or missing, make a reasonable assumption, state it "
            "explicitly in your plan, and proceed."
        )

        user_message_text = (
            f"## Objective\n\n{case.prompt}\n\n"
            f"## Working Directory\n\n"
            f"The working directory is: {case.working_dir}\n"
            f"Inspect it if needed for context materials."
        )

        t0 = time.monotonic()
        try:
            # Build agent with BuiltInPlanner
            agent = LlmAgent(
                name="plan_generator",
                model=model.name,
                instruction=instruction,
                planner=BuiltInPlanner(
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=True,
                        thinking_budget=1024,
                    ),
                ),
                generate_content_config=types.GenerateContentConfig(
                    temperature=0.2,
                ),
            )

            runner = InMemoryRunner(
                agent=agent,
                app_name="eval1_gemini",
            )

            session = await runner.session_service.create_session(
                app_name="eval1_gemini",
                user_id="eval1",
            )

            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message_text)],
            )

            # Collect events from the agent run
            plan_parts: list[str] = []
            thinking_parts: list[str] = []

            async for event in runner.run_async(
                user_id="eval1",
                session_id=session.id,
                new_message=user_content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if not part.text:
                            continue
                        if part.thought:
                            thinking_parts.append(part.text)
                        elif event.author == "plan_generator":
                            plan_parts.append(part.text)

            result.plan_text = "\n".join(plan_parts)
            result.thinking_text = "\n".join(thinking_parts)
            result.num_turns = 1

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


# ── Aider (Architect Mode — plan only) ────────────────────────────────────

class AiderFramework(PlanningFramework):
    """
    Uses Aider's ArchitectCoder for plan generation.

    ArchitectCoder has a planning-oriented system prompt:
      "Act as an expert architect engineer… Describe how to modify the code…
       make instructions unambiguous and complete."

    Safety: ArchitectCoder.reply_completed() normally spawns an editor Coder
    that applies edits to files.  We neuter this by overriding reply_completed
    to a no-op on the coder instance after creation.

    - Plan text from coder.partial_response_content
    - Tokens/cost tracked via litellm under the hood
    - Models: any litellm-supported model (Anthropic, Ollama, LM Studio)
    """

    @property
    def name(self) -> str:
        return "aider"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        def _run_aider() -> None:
            from aider.coders import Coder
            from aider.models import Model as AiderModel
            from aider.io import InputOutput

            # ── Map ModelSpec → litellm model string ──
            if model.provider == "ollama":
                litellm_name = f"ollama/{model.name}"
                os.environ["OLLAMA_API_BASE"] = model.api_base_url
            elif model.provider == "lm_studio":
                litellm_name = f"openai/{model.name}"
                os.environ["OPENAI_API_BASE"] = (
                    f"{model.api_base_url.rstrip('/')}/v1"
                )
                os.environ["OPENAI_API_KEY"] = "lm-studio"
            else:
                litellm_name = model.name  # anthropic models work directly

            aider_model = AiderModel(litellm_name)
            io = InputOutput(
                yes=True,          # auto-accept all prompts
                pretty=False,      # no colour / formatting
                fancy_input=False,  # no interactive input
            )

            # ── Gather context files from WorkingDir (if any) ──
            fnames = []
            if case.working_dir.exists():
                for f in case.working_dir.iterdir():
                    if f.is_file() and f.stat().st_size < 100_000:
                        fnames.append(str(f))

            # ── Build prompt (same structure as other frameworks) ──
            prompt = (
                "You are in planning mode. Read the objective below and "
                "produce a detailed, step-by-step implementation plan. "
                "Do NOT execute anything — only plan.\n\n"
                "IMPORTANT: Do NOT ask clarifying questions. If any detail "
                "is ambiguous or missing, make a reasonable assumption, "
                "state it explicitly in your plan, and proceed.\n\n"
                f"## Objective\n\n{case.prompt}\n\n"
                f"## Working Directory\n\n"
                f"The working directory is: {case.working_dir}\n"
                "Inspect it if needed for context materials."
            )

            # edit_format="architect" gives us the planning-oriented system
            # prompt ("Act as expert architect engineer…").
            # use_git=False prevents Aider from discovering the parent git
            # repo (Pythia) and indexing the entire project as context.
            # map_tokens=0 disables the repo map entirely — we only want
            # the case's WorkingDir files, not the whole repo tree.
            coder = Coder.create(
                main_model=aider_model,
                edit_format="architect",
                io=io,
                fnames=fnames,
                auto_commits=False,
                suggest_shell_commands=False,
                stream=False,
                use_git=False,
                map_tokens=0,
            )

            # SAFETY: Neuter reply_completed so the editor Coder is never
            # spawned.  The architect produces the plan text; we capture it
            # from partial_response_content and stop there.
            coder.reply_completed = lambda: None

            # preproc=False disables Aider's URL scraping and file-mention
            # detection, which can inject large amounts of garbage HTML
            # into the prompt and cause API errors.
            plan_text = coder.run(with_message=prompt, preproc=False)

            result.plan_text = plan_text or coder.partial_response_content
            # total_cost is 0.0 for local models (no pricing data in
            # litellm), so only set cost if it's actually non-zero.
            if coder.total_cost > 0:
                result.total_cost_usd = coder.total_cost
            # num_reflections counts extra LLM calls from file-mention
            # detection in the response.  Total turns = 1 + reflections.
            result.num_turns = 1 + coder.num_reflections
            log.info(
                f"  Aider tokens: {coder.total_tokens_sent} sent, "
                f"{coder.total_tokens_received} received, "
                f"cost=${coder.total_cost:.4f}, "
                f"reflections={coder.num_reflections}"
            )

        t0 = time.monotonic()
        try:
            await asyncio.to_thread(_run_aider)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


# ── CrewAI (Single-Agent Planning) ────────────────────────────────────────

class CrewAIFramework(PlanningFramework):
    """
    Uses CrewAI with a single planning agent and one task.

    - No tools, no delegation — the agent's only job is to produce a plan
    - Token usage via CrewOutput.token_usage (UsageMetrics)
    - Models: per-agent `llm` param using litellm model strings
    """

    @property
    def name(self) -> str:
        return "crewai"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        def _run_crewai() -> None:
            from crewai import Agent, Task, Crew

            # ── Map ModelSpec → litellm model string ──
            if model.provider == "ollama":
                llm_string = f"ollama/{model.name}"
                os.environ["OLLAMA_API_BASE"] = model.api_base_url
            elif model.provider == "lm_studio":
                llm_string = f"openai/{model.name}"
                os.environ["OPENAI_API_BASE"] = (
                    f"{model.api_base_url.rstrip('/')}/v1"
                )
                os.environ["OPENAI_API_KEY"] = "lm-studio"
            else:
                llm_string = model.name  # anthropic models work directly

            agent = Agent(
                role="Implementation Planner",
                goal=(
                    "Create a detailed, step-by-step implementation plan. "
                    "Do NOT execute anything. Do NOT ask clarifying questions."
                ),
                backstory=(
                    "You are an expert software architect who produces "
                    "thorough, actionable implementation plans. When details "
                    "are ambiguous, you make reasonable assumptions and state "
                    "them explicitly."
                ),
                llm=llm_string,
                allow_delegation=False,
                verbose=False,
            )

            task = Task(
                description=(
                    f"Read the objective below and produce a detailed, "
                    f"step-by-step implementation plan.\n\n"
                    f"## Objective\n\n{case.prompt}\n\n"
                    f"## Working Directory\n\n"
                    f"The working directory is: {case.working_dir}\n"
                ),
                expected_output=(
                    "A detailed step-by-step implementation plan in markdown "
                    "format, with file paths, function signatures, and "
                    "concrete technical decisions."
                ),
                agent=agent,
            )

            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False,
            )

            output = crew.kickoff()

            result.plan_text = output.raw
            result.num_turns = len(output.tasks_output) if output.tasks_output else 1

            # Extract token metrics from UsageMetrics
            if output.token_usage:
                usage = output.token_usage
                # UsageMetrics has: total_tokens, prompt_tokens,
                # completion_tokens, successful_requests
                # We don't get dollar cost directly — estimate if needed
                log.info(
                    f"  CrewAI tokens: {usage.total_tokens} total "
                    f"({usage.prompt_tokens} prompt, "
                    f"{usage.completion_tokens} completion)"
                )

        t0 = time.monotonic()
        try:
            await asyncio.to_thread(_run_crewai)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


# ── LangGraph (Single-Node Planning Graph) ────────────────────────────────

class LangGraphFramework(PlanningFramework):
    """
    Uses LangGraph with a single planning node.

    Creates a minimal StateGraph: START → planner → END.
    The planner node calls an LLM via langchain_openai's ChatOpenAI
    (which supports Ollama, LM Studio, and OpenAI-compatible endpoints).

    - Plan text from the LLM response content
    - Token usage via langchain's usage_metadata on AIMessage
    - Models: any OpenAI-compatible endpoint (Ollama, LM Studio, Anthropic via proxy)
    """

    @property
    def name(self) -> str:
        return "langgraph"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        def _run_langgraph() -> None:
            from langgraph.graph import StateGraph, START, END
            from langchain_openai import ChatOpenAI
            from typing import TypedDict

            class PlanState(TypedDict):
                prompt: str
                plan: str
                usage: dict

            # ── Build LLM client ──
            llm_kwargs: dict[str, Any] = {
                "temperature": 0.2,
                "max_tokens": 8192,
            }

            if model.provider == "ollama":
                llm_kwargs["model"] = model.name
                llm_kwargs["base_url"] = f"{model.api_base_url}/v1"
                llm_kwargs["api_key"] = "ollama"
            elif model.provider == "lm_studio":
                llm_kwargs["model"] = model.name
                llm_kwargs["base_url"] = f"{model.api_base_url.rstrip('/')}/v1"
                llm_kwargs["api_key"] = "lm-studio"
            elif model.provider == "anthropic":
                # Use Anthropic via their OpenAI-compatible endpoint
                llm_kwargs["model"] = model.name
                llm_kwargs["base_url"] = "https://api.anthropic.com/v1"
                llm_kwargs["api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
            elif model.provider == "github_models":
                llm_kwargs["model"] = model.name
                llm_kwargs["base_url"] = model.api_base_url
                llm_kwargs["api_key"] = os.environ.get("GITHUB_TOKEN", "")
            else:
                llm_kwargs["model"] = model.name

            llm = ChatOpenAI(**llm_kwargs)

            # Store usage from the LLM response
            captured_usage: dict[str, Any] = {}

            def plan_node(state: PlanState) -> dict:
                response = llm.invoke(state["prompt"])
                usage_meta = {}
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    usage_meta = dict(response.usage_metadata)
                return {"plan": response.content, "usage": usage_meta}

            builder = StateGraph(PlanState)
            builder.add_node("planner", plan_node)
            builder.add_edge(START, "planner")
            builder.add_edge("planner", END)
            graph = builder.compile()

            # ── Compose prompt ──
            prompt = (
                "You are in planning mode. Read the objective below and "
                "produce a detailed, step-by-step implementation plan. "
                "Do NOT execute anything — only plan.\n\n"
                "IMPORTANT: Do NOT ask clarifying questions. If any detail "
                "is ambiguous or missing, make a reasonable assumption, "
                "state it explicitly in your plan, and proceed.\n\n"
                f"## Objective\n\n{case.prompt}\n\n"
                f"## Working Directory\n\n"
                f"The working directory is: {case.working_dir}\n"
                "Inspect it if needed for context materials."
            )

            output = graph.invoke({"prompt": prompt, "plan": "", "usage": {}})

            result.plan_text = output["plan"]
            result.num_turns = 1

            # Extract token usage
            usage = output.get("usage", {})
            if usage:
                total_tokens = usage.get("total_tokens", 0)
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                log.info(
                    f"  LangGraph tokens: {total_tokens} total "
                    f"({input_tokens} input, {output_tokens} output)"
                )

        t0 = time.monotonic()
        try:
            await asyncio.to_thread(_run_langgraph)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


# ── OpenAI Agents SDK (No-Tool Agent) ─────────────────────────────────────

class AgentsSDKFramework(PlanningFramework):
    """
    Uses the OpenAI Agents SDK with a no-tool, no-handoff agent.

    The agent receives the planning prompt and returns a text response.
    For non-OpenAI models, uses OpenAIChatCompletionsModel with a custom
    AsyncOpenAI client pointed at the appropriate endpoint.

    - Plan text from result.final_output
    - Token usage from result.raw_responses[-1].usage
    - Models: any OpenAI-compatible endpoint (Ollama, LM Studio, etc.)
    """

    @property
    def name(self) -> str:
        return "agents_sdk"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        from agents import Agent, Runner
        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
        from openai import AsyncOpenAI

        result = PlanOutput(
            case_name=case.name,
            framework_name=self.name,
            model_name=model.name,
            provider=model.provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # ── Build model ──
        if model.provider == "ollama":
            client = AsyncOpenAI(
                base_url=f"{model.api_base_url}/v1",
                api_key="ollama",
            )
            sdk_model = OpenAIChatCompletionsModel(
                model=model.name, openai_client=client,
            )
        elif model.provider == "lm_studio":
            client = AsyncOpenAI(
                base_url=f"{model.api_base_url.rstrip('/')}/v1",
                api_key="lm-studio",
            )
            sdk_model = OpenAIChatCompletionsModel(
                model=model.name, openai_client=client,
            )
        elif model.provider == "anthropic":
            # Agents SDK doesn't natively support Anthropic;
            # would need litellm proxy or Anthropic's OpenAI-compat endpoint
            client = AsyncOpenAI(
                base_url="https://api.anthropic.com/v1",
                api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            )
            sdk_model = OpenAIChatCompletionsModel(
                model=model.name, openai_client=client,
            )
        elif model.provider == "github_models":
            client = AsyncOpenAI(
                base_url=model.api_base_url,
                api_key=os.environ.get("GITHUB_TOKEN", ""),
            )
            sdk_model = OpenAIChatCompletionsModel(
                model=model.name, openai_client=client,
            )
        else:
            # Default OpenAI
            sdk_model = model.name

        instruction = (
            "You are in planning mode. Read the objective the user gives you "
            "and produce a detailed, step-by-step implementation plan. Do NOT "
            "execute anything — only plan.\n\n"
            "IMPORTANT: Do NOT ask clarifying questions. If any detail is "
            "ambiguous or missing, make a reasonable assumption, state it "
            "explicitly in your plan, and proceed. You must produce a "
            "complete plan in a single pass without waiting for human input."
        )

        agent = Agent(
            name="Planner",
            instructions=instruction,
            model=sdk_model,
            tools=[],
            handoffs=[],
        )

        prompt = (
            f"## Objective\n\n{case.prompt}\n\n"
            f"## Working Directory\n\n"
            f"The working directory is: {case.working_dir}\n"
            f"Inspect it if needed for context materials."
        )

        t0 = time.monotonic()
        try:
            run_result = await Runner.run(agent, input=prompt, max_turns=1)

            result.plan_text = run_result.final_output
            result.num_turns = len(run_result.raw_responses)

            # Extract token usage from the last response
            if run_result.raw_responses:
                last_usage = run_result.raw_responses[-1].usage
                if last_usage:
                    total = last_usage.total_tokens or 0
                    prompt_t = last_usage.input_tokens or 0
                    completion_t = last_usage.output_tokens or 0
                    log.info(
                        f"  Agents SDK tokens: {total} total "
                        f"({prompt_t} input, {completion_t} output)"
                    )

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.duration_ms = int(result.duration_wall_s * 1000)
        return result


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
    "direct_api": DirectAPIFramework(),
    "gemini_adk": GeminiADKFramework(),
    "aider": AiderFramework(),
    "crewai": CrewAIFramework(),
    "langgraph": LangGraphFramework(),
    "agents_sdk": AgentsSDKFramework(),
    "openhands": OpenHandsFramework(),
}

# Default active frameworks (override with --frameworks)
DEFAULT_FRAMEWORKS = ["claude_code"]


# ═══════════════════════════════════════════════════════════════════════════
# §4  MODEL CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════

ANTHROPIC_MODELS: list[ModelSpec] = [
    # ModelSpec(name="claude-sonnet-4-6", provider="anthropic"),
    # ModelSpec(name="claude-opus-4-6", provider="anthropic"),
    # ModelSpec(name="claude-haiku-4-5-20251001", provider="anthropic"),
]

OLLAMA_MODELS: list[ModelSpec] = [
    ModelSpec(name="qwen3.5:9b", provider="ollama", api_base_url="http://localhost:11434"),
    ModelSpec(name="gpt-oss:20b", provider="ollama", api_base_url="http://localhost:11434"),
    ModelSpec(name="qwen3.5:4b", provider="ollama", api_base_url="http://localhost:11434"),
    ModelSpec(name="granite4:3b", provider="ollama", api_base_url="http://localhost:11434"),
]

LM_STUDIO_MODELS: list[ModelSpec] = [
    ModelSpec(name="qwen/qwen3.5-9b", provider="lm_studio", api_base_url="http://192.168.1.139:1234"),
    # ModelSpec(name="mistralai/ministral-3-14b-reasoning", provider="lm_studio", api_base_url="http://192.168.1.139:1234"),
    # ModelSpec(name="gemma-3-12b-it", provider="lm_studio", api_base_url="http://192.168.1.139:1234"),
    ModelSpec(name="openai/gpt-oss-20b", provider="lm_studio", api_base_url="http://192.168.1.139:1234"),
]

GEMINI_MODELS: list[ModelSpec] = [
    # ModelSpec(name="gemini-2.5-flash", provider="gemini"),
    ModelSpec(name="gemini-3-flash-preview", provider="gemini"),
    ModelSpec(name="gemini-3.1-flash-lite-preview", provider="gemini"),
]

# WARNING: GitHub Models free tier has strict rate limits and aggressive
# abuse detection. Repeated 429 errors may flag your GitHub account.
# Verify your token is authorized for GitHub Models API before use:
#   https://github.com/marketplace/models
# Use --include-github at your own risk.
GITHUB_MODELS: list[ModelSpec] = [
    ModelSpec(name="gpt-4o-mini", provider="github_models",
             api_base_url="https://models.github.ai/inference"),
    ModelSpec(name="gpt-4o", provider="github_models",
             api_base_url="https://models.github.ai/inference"),
    # ModelSpec(name="gpt-5", provider="github_models",
    #          api_base_url="https://models.github.ai/inference"),
]

# ── LM Studio model management ───────────────────────────────────────────

_lm_studio_loaded_model: str | None = None  # track what we loaded last


def _lm_studio_api(base_url: str, path: str, body: dict | None = None) -> dict:
    """Send a request to LM Studio's management API. Returns parsed JSON."""
    url = f"{base_url.rstrip('/')}{path}"
    if body is not None:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url, method="GET")

    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def lm_studio_swap_model(model: ModelSpec) -> None:
    """
    Unload the current LM Studio model and load the requested one.

    Uses LM Studio's /api/v1/models/load and /api/v1/models/unload endpoints.
    context_length=0 means use the model's max context length (omit the param).
    """
    global _lm_studio_loaded_model

    if model.provider != "lm_studio":
        return

    base = model.api_base_url

    # Skip if already loaded
    if _lm_studio_loaded_model == model.name:
        log.info(f"  LM Studio: {model.name} already loaded, skipping swap")
        return

    # Unload whatever is currently loaded
    if _lm_studio_loaded_model is None:
        # First run — try unloading the target model in case it was pre-loaded
        # with wrong settings (e.g. small context). Also unload any other model
        # by trying all known LM Studio model names.
        models_to_try = {model.name} | {m.name for m in LM_STUDIO_MODELS}
        for mid in models_to_try:
            try:
                _lm_studio_api(base, "/api/v1/models/unload", {"instance_id": mid})
                log.info(f"  LM Studio: unloaded pre-loaded model {mid}")
            except (urllib.error.URLError, urllib.error.HTTPError):
                pass  # not loaded, fine
    else:
        log.info(f"  LM Studio: unloading {_lm_studio_loaded_model}...")
        try:
            _lm_studio_api(base, "/api/v1/models/unload", {
                "instance_id": _lm_studio_loaded_model,
            })
        except urllib.error.URLError as e:
            log.warning(f"  LM Studio: unload failed (may already be unloaded): {e}")

    # Load requested model — use explicit context_length or request max (1M cap)
    print(f"model.context_length = {model.context_length}")
    # ctx = model.context_length if model.context_length > 65536 else 65536
    ctx = 40000
    load_body: dict[str, Any] = {
        "model": model.name,
        "context_length": ctx,
        "flash_attention": True,
        "echo_load_config": True, 
    }

    log.info(f"  LM Studio: loading {model.name} (requesting ctx={ctx})...")

    resp = _lm_studio_api(base, "/api/v1/models/load", load_body)
    load_time = resp.get("load_time_seconds", "?")
    log.info(f"  LM Studio: {model.name} loaded in {load_time}s. (requesting ctx={ctx} {resp["load_config"]["context_length"]})")

    _lm_studio_loaded_model = model.name

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

def plan_filename(framework: str, provider: str, model: str) -> str:
    """Deterministic filename for a plan: framework__provider__model.md"""
    safe_model = model.replace("/", "_").replace(":", "_")
    return f"{framework}__{provider}__{safe_model}.md"


def save_plan(results_dir: Path, output: PlanOutput) -> Path:
    """Write a plan to disk as Markdown with YAML-ish front matter."""
    plan_dir = results_dir / output.case_name / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)

    fname = plan_filename(output.framework_name, output.provider, output.model_name)
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
    fname = f"{output.framework_name}__{output.provider}__{safe_model}.json"
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
                    / plan_filename(fw.name, model.provider, model.name)
                )
                if skip_existing and existing.exists():
                    log.info(f"  {tag} — SKIP (exists)")
                    continue

                log.info(f"  {tag} — generating...")

                # Swap model if needed (provider-specific)
                lm_studio_swap_model(model)

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

                # Rate-limit free tier APIs
                if model.provider == "gemini":
                    log.info("  Gemini rate limit: sleeping 7s...")
                    await asyncio.sleep(7)
                elif model.provider == "github_models":
                    log.info("  GitHub Models rate limit: sleeping 60s...")
                    await asyncio.sleep(60)

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
    gen.add_argument("--lm-studio-url", default="http://192.168.1.139:1234")
    gen.add_argument("--include-gemini", action="store_true")
    gen.add_argument("--include-github", action="store_true",
                     help="Include GitHub Models (GPT-4o, GPT-4o-mini) — set GITHUB_TOKEN env var")
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
            if args.include_gemini:
                models.extend(GEMINI_MODELS)
            if args.include_github:
                models.extend(GITHUB_MODELS)

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
