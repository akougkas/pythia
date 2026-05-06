"""Claude Agent SDK plan-mode provider.

Uses claude_agent_sdk.query() with permission_mode='plan'. The agent has
read-only file access (Read, Glob, Grep) and terminates by emitting an
ExitPlanMode tool call whose `plan` argument is the markdown plan.

Works for:
- Anthropic models via the standard API
- Local models served on an OpenAI-compatible endpoint (Ollama, vLLM,
  LM Studio) by injecting ANTHROPIC_BASE_URL into the SDK env.

If ExitPlanMode is never emitted (common with weak local models that
don't reliably learn the tool), the provider falls back to the
collected text output and flags PlanOutput.used_fallback=True.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import CaseSpec, ModelSpec, PlanOutput
from .base import PlanningProvider

log = logging.getLogger(__name__)


def _patch_sdk_for_ollama_unsigned_thinking() -> None:
    """Tolerate thinking blocks that lack a signature.

    Ollama ≥0.23 emits Anthropic-format thinking blocks with no signature
    field (they cannot produce a real Anthropic signature). The SDK's
    parse_message hard-requires it (claude_agent_sdk/_internal/message_parser.py
    line 108: signature=block["signature"]) and crashes the run with
    MessageParseError. Patch parse_message to inject an empty signature on
    incoming thinking blocks before the original parser runs.
    """
    from claude_agent_sdk._internal import client as _client
    from claude_agent_sdk._internal import message_parser as _mp

    if getattr(_mp, "_pythia_unsigned_thinking_patched", False):
        return
    _orig_parse = _mp.parse_message

    def parse_message(data: Any) -> Any:
        if isinstance(data, dict) and data.get("type") == "assistant":
            for block in (data.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    block.setdefault("signature", "")
        return _orig_parse(data)

    _mp.parse_message = parse_message
    _client.parse_message = parse_message  # client imported it by name
    _mp._pythia_unsigned_thinking_patched = True


_patch_sdk_for_ollama_unsigned_thinking()


# Tools whose input carries a filesystem path that must stay inside the case
# working directory. Maps tool name → input key holding the path.
_PATH_TOOLS: dict[str, str] = {
    "Read": "file_path",
    "Edit": "file_path",
    "Write": "file_path",
    "NotebookEdit": "notebook_path",
    "Glob": "path",
    "Grep": "path",
}


def _make_workdir_path_guard(workdir: Path) -> Any:
    """Return a can_use_tool callback that denies file access outside workdir.

    The plan-mode default already forbids most writes, but weak local models
    (e.g. mistral-small) hallucinate paths into ancestor projects when their
    narrow workdir Glob returns nothing. Constraining tool calls here prevents
    those hallucinations from polluting the captured plan and stops Read/Glob/
    Grep from pulling unrelated files into context.

    Allows: ExitPlanMode and the plan-capture write to ~/.claude/plans/*.
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    workdir_abs = str(workdir.resolve())
    plans_prefix = str((Path.home() / ".claude" / "plans").resolve())

    def _inside(path: str, root: str) -> bool:
        try:
            resolved = str(Path(path).resolve())
        except (ValueError, OSError):
            return False
        return resolved == root or resolved.startswith(root + "/")

    async def can_use_tool(
        tool_name: str, tool_input: dict[str, Any], context: Any
    ) -> Any:
        if tool_name not in _PATH_TOOLS:
            return PermissionResultAllow()
        key = _PATH_TOOLS[tool_name]
        path = tool_input.get(key)
        # Glob/Grep without an explicit path default to cwd (== workdir) → allow.
        if not path:
            return PermissionResultAllow()
        # Plan capture path is how Claude Code surfaces plans in plan mode.
        if tool_name == "Write" and _inside(path, plans_prefix):
            return PermissionResultAllow()
        if _inside(path, workdir_abs):
            return PermissionResultAllow()
        log.warning(
            "    [guard] denying %s outside workdir: %s", tool_name, path
        )
        return PermissionResultDeny(
            message=(
                f"Path {path!r} is outside the case working directory "
                f"({workdir_abs}). All file access must stay within the "
                f"working directory."
            )
        )

    return can_use_tool


class AgentSDKPlanMode(PlanningProvider):
    @property
    def name(self) -> str:
        return "agent_sdk_plan"

    async def generate_plan(
        self,
        case: CaseSpec,
        model: ModelSpec,
    ) -> PlanOutput:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
            query,
        )

        out = PlanOutput(
            case_id=case.case_id,
            model_name=model.name,
            provider=model.provider,
            repeat=0,  # caller fills in after return
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
        )

        options = self._build_options(model, case, ClaudeAgentOptions)
        prompt = self.compose_prompt(case)

        # can_use_tool requires streaming-mode input (AsyncIterable of message
        # dicts). Wrap the single composed prompt in a one-shot async generator.
        async def _prompt_stream() -> Any:
            yield {
                "type": "user",
                "message": {"role": "user", "content": prompt},
                "parent_tool_use_id": None,
                "session_id": "default",
            }

        t0 = time.monotonic()
        last = t0
        try:
            async for message in query(prompt=_prompt_stream(), options=options):
                now = time.monotonic()
                dt = now - last
                last = now
                if isinstance(message, AssistantMessage):
                    self._absorb_assistant(
                        message, out, TextBlock, ThinkingBlock, ToolUseBlock, dt=dt
                    )
                elif isinstance(message, ResultMessage):
                    out.session_id = message.session_id
                    out.duration_ms_sdk = message.duration_ms
                    out.total_cost_usd = message.total_cost_usd
                    out.num_turns = message.num_turns
                    log.info(
                        "    [+%5.1fs] result turns=%d cost=$%.4f sdk_ms=%s",
                        dt, message.num_turns,
                        message.total_cost_usd or 0.0,
                        message.duration_ms,
                    )
        except Exception as e:
            out.error = f"{type(e).__name__}: {e}"
            log.exception("    [error] %s: %s", type(e).__name__, e)

        out.duration_wall_s = time.monotonic() - t0
        self._fallback_if_no_exit_plan(out, model)
        return out

    # ── Internals ────────────────────────────────────────────────────

    def _build_options(self, model: ModelSpec, case: CaseSpec, OptionsCls: Any) -> Any:
        kwargs: dict[str, Any] = {
            "permission_mode": "plan",
            "model": model.name,
            "cwd": str(case.working_dir),
            "disallowed_tools": ["AskUserQuestion"],
            "setting_sources": [],
            "can_use_tool": _make_workdir_path_guard(Path(case.working_dir)),
        }
        if model.is_local:
            if not model.api_base_url:
                raise ValueError(f"Local model {model.name} requires api_base_url")
            # The CLI appends /v1/messages to ANTHROPIC_BASE_URL itself, so
            # strip a trailing /v1 if the registry supplies one (Ollama's
            # OpenAI-compat base is http://host:11434/v1, but the
            # Anthropic-compat endpoint is http://host:11434/v1/messages —
            # passing the URL with /v1 yields /v1/v1/messages → 404).
            base = model.api_base_url.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            kwargs["model"] = model.name
            kwargs["env"] = {
                "ANTHROPIC_BASE_URL": base,
                "ANTHROPIC_AUTH_TOKEN": "local",
                "ANTHROPIC_API_KEY": "local",
                "CLAUDE_CODE_SUBAGENT_MODEL": model.name,
            }
            if model.disable_thinking:
                kwargs["thinking"] = {"type": "disabled"}
        return OptionsCls(**kwargs)

    def compose_prompt(self, case: CaseSpec) -> str:
        staged = sorted(p.name for p in case.working_dir.iterdir()) \
            if case.working_dir.exists() else []
        if staged:
            file_list = ", ".join(f"`{name}`" for name in staged)
            workdir_block = (
                f"## Working directory\n\n"
                f"The working directory is: {case.working_dir}\n"
                f"Inspect it for context — staged files: {file_list}.\n\n"
            )
        else:
            workdir_block = (
                f"## Working directory\n\n"
                f"The working directory is: {case.working_dir} (no context "
                f"files staged; all context is inline in the objective).\n\n"
            )

        # If the objective ships its own `## Output format` contract (e.g.
        # `hpc_cg_complex`'s prompt_template.md, or `hpc_cg_multi`'s template
        # which adds cluster-citation guidance), defer to it. Otherwise inject
        # a workload-neutral subtask-decomposition contract so the resulting
        # plan is something a multi-agent orchestrator can consume — without
        # leaking role names or a dependency graph (those are the planner's
        # job) and without baking workload-specific concerns (cluster facts,
        # paper-replication artifacts, ...) into the runner.
        has_output_format = (
            "## Output format" in case.prompt
            or "## Output Format" in case.prompt
        )
        format_block = "" if has_output_format else (
            "\n## Output format (runner-injected)\n\n"
            "Begin the plan with an explicit **subtask decomposition table** "
            "before any other content. Each row has these columns:\n\n"
            "| id | title | role | depends_on | deliverable |\n"
            "|----|-------|------|------------|-------------|\n\n"
            "- **id** — `S1`, `S2`, ... (plan-unique).\n"
            "- **title** — one-line imperative summary of the subtask.\n"
            "- **role** — the specialist who would own this subtask "
            "end-to-end. Pick role names that fit the objective; you are "
            "not given a fixed enum, and two subtasks may share a role.\n"
            "- **depends_on** — comma-separated subtask ids, or `—` if "
            "none. Two subtasks with the same predecessors and no edge "
            "between them may run in parallel.\n"
            "- **deliverable** — one short noun phrase naming the concrete "
            "artifact this subtask produces.\n\n"
            "Decompose the work into subtasks small enough that one "
            "specialist could own each end-to-end. The number of subtasks, "
            "the role names, and the dependency structure are your choice — "
            "pick what the objective actually demands, no more and no less. "
            "Do not pad with subtasks that have no deliverable.\n\n"
            "After the table, write one detailed section per subtask. Each "
            "section heading MUST reference the subtask id and MUST cite "
            "its predecessors, e.g. `## S3 — Build recipe (consumes: S2)`. "
            "Sections must appear in topological order of the table.\n\n"
            "**Citations.** Every subtask whose decisions depend on staged "
            "context files MUST cite the specific file and section it "
            "relies on. Decisions without a citation are ungrounded; the "
            "verification subtask must flag them.\n\n"
            "End with a short **Verification** section describing how to "
            "check the deliverables end-to-end.\n"
        )

        return (
            "You are in planning mode. Read the objective below and produce "
            "a structured markdown plan that conforms to the Output format "
            "section. Do NOT execute anything — only plan.\n\n"
            "IMPORTANT: Do NOT ask clarifying questions. Do NOT use the "
            "AskUserQuestion tool. If any detail is ambiguous or missing, "
            "make a reasonable assumption, state it explicitly, and proceed.\n\n"
            f"{workdir_block}"
            f"## Objective\n\n{case.prompt}\n"
            f"{format_block}"
        )

    def _absorb_assistant(
        self,
        message: Any,
        out: PlanOutput,
        TextBlock: Any,
        ThinkingBlock: Any,
        ToolUseBlock: Any,
        dt: float = 0.0,
    ) -> None:
        for block in message.content:
            if isinstance(block, TextBlock):
                snippet = block.text[:140].replace("\n", " ")
                log.info("    [+%5.1fs] text     %s", dt, snippet)
                out.reasoning_text += block.text + "\n"
            elif isinstance(block, ThinkingBlock):
                snippet = block.thinking[:140].replace("\n", " ")
                log.info("    [+%5.1fs] thinking %s", dt, snippet)
                out.thinking_text += block.thinking + "\n"
            elif isinstance(block, ToolUseBlock):
                arg_preview = str(block.input)[:140].replace("\n", " ")
                log.info("    [+%5.1fs] tool     %s %s", dt, block.name, arg_preview)
                out.num_tool_calls += 1
                out.tool_call_sequence.append(block.name)
                self._capture_plan_from_tool(block, out)

    def _capture_plan_from_tool(self, block: Any, out: PlanOutput) -> None:
        if block.name == "ExitPlanMode":
            plan = block.input.get("plan", "")
            if plan and (out.plan_markdown is None or len(plan) > len(out.plan_markdown)):
                out.plan_markdown = plan
        elif block.name == "Write" and "/.claude/plans/" in block.input.get("file_path", ""):
            content = block.input.get("content", "")
            if content and (out.plan_markdown is None or len(content) > len(out.plan_markdown)):
                out.plan_markdown = content

    def _fallback_if_no_exit_plan(self, out: PlanOutput, model: ModelSpec) -> None:
        if out.plan_markdown is None and out.reasoning_text.strip():
            log.warning(
                "%s: ExitPlanMode not called — falling back to text output as plan",
                model.name,
            )
            out.plan_markdown = out.reasoning_text.strip()
            out.used_fallback = True
