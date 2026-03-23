#!/usr/bin/env python3
"""
eval_execution.py — Plan Execution Experiments
================================================

Measures execution quality: given the same plan, how much working code
does each model produce within a time budget?

Test 1: Opus executes a gpt-oss plan with a 3-minute hard cutoff.
Test 2: Opus and gpt-oss both execute the same plan in parallel;
        gpt-oss is cancelled when Opus finishes naturally.

Instrumentation:
  - Full event timeline (tool calls, subagent lifecycle, task progress)
  - Per-step token tracking via TaskProgressMessage
  - Subagent start/stop hooks with agent_id attribution
  - Pre/PostToolUse hooks to trace every tool invocation

Usage:
    # Test 1 — Opus with 3-min cutoff
    python eval_execution.py test1 --case case_002_file_watcher [--timeout 180]

    # Test 2 — Opus vs gpt-oss parallel
    python eval_execution.py test2 --case case_002_file_watcher

    # Snapshot a run directory (files, LOC, pytest)
    python eval_execution.py snapshot --dir runs/test1_opus_3min
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("eval_execution")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results"
CASES_DIR = SCRIPT_DIR / "cases"

# Runs directory is OUTSIDE the Pythia project tree to avoid CLAUDE.md
# contamination.  Claude Code walks up the directory tree looking for
# project config — if the working directory is inside Pythia, it picks
# up CLAUDE.md rules (mentor role, TDD, WTF-P gates) that distort the
# experiment.
RUNS_DIR = Path("/home/jye/publications/pythia_eval_runs")

# Default plan to execute (gpt-oss plan for case_002)
DEFAULT_PLAN = "claude_code__ollama__gpt-oss_20b.md"

# Ollama endpoint
OLLAMA_BASE_URL = "http://localhost:11434/v1"


# ═══════════════════════════════════════════════════════════════════════════
# §1  EVENT TIMELINE — records every observable action during execution
# ═══════════════════════════════════════════════════════════════════════════

class EventTimeline:
    """Timestamped event log for a single session.

    Design: Hooks fire in real-time and are the source of truth for timing.
    AssistantMessages arrive in batches (often all at once at session end),
    so we correlate them to hook events via tool_use_id rather than relying
    on message timestamps.

    After the session ends, call `correlate_turns()` to link each tool
    event to the LLM turn that produced it.
    """

    def __init__(self) -> None:
        self._t0 = time.monotonic()
        self._events: list[dict[str, Any]] = []
        self._tool_use_count: int = 0
        self._subagent_count: int = 0
        self._active_subagents: dict[str, dict[str, Any]] = {}
        # Populated from ResultMessage.usage at session end
        self._usage: dict[str, Any] = {}
        # Maps tool_use_id → turn number (populated by correlate_turns)
        self._tool_to_turn: dict[str, int] = {}

    @property
    def elapsed_s(self) -> float:
        return time.monotonic() - self._t0

    def record(self, event_type: str, **data: Any) -> None:
        """Append an event with wall-clock timestamp."""
        entry: dict[str, Any] = {
            "t": round(self.elapsed_s, 3),
            "type": event_type,
        }
        entry.update(data)
        self._events.append(entry)

    # -- Hook-driven recorders (real-time timestamps) --

    def record_tool_start(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        self._tool_use_count += 1
        summary = _summarise_tool_input(tool_name, tool_input)
        self.record(
            "tool_start",
            tool=tool_name,
            tool_use_id=tool_use_id,
            agent_id=agent_id,
            input_summary=summary,
        )

    def record_tool_end(
        self,
        tool_name: str,
        tool_use_id: str | None = None,
        agent_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.record(
            "tool_end",
            tool=tool_name,
            tool_use_id=tool_use_id,
            agent_id=agent_id,
            error=error,
        )

    def record_subagent_start(
        self, agent_id: str, agent_type: str
    ) -> None:
        self._subagent_count += 1
        self._active_subagents[agent_id] = {
            "agent_type": agent_type,
            "start_t": self.elapsed_s,
        }
        self.record(
            "subagent_start",
            agent_id=agent_id,
            agent_type=agent_type,
        )

    def record_subagent_stop(
        self,
        agent_id: str,
        agent_type: str,
        transcript_path: str = "",
    ) -> None:
        start_info = self._active_subagents.pop(agent_id, {})
        duration = self.elapsed_s - start_info.get("start_t", 0.0)
        self.record(
            "subagent_stop",
            agent_id=agent_id,
            agent_type=agent_type,
            duration_s=round(duration, 3),
            transcript_path=transcript_path,
        )

    def record_task_progress(
        self,
        task_id: str,
        total_tokens: int,
        tool_uses: int,
        duration_ms: int,
        last_tool: str | None = None,
    ) -> None:
        self.record(
            "task_progress",
            task_id=task_id,
            total_tokens=total_tokens,
            tool_uses=tool_uses,
            duration_ms=duration_ms,
            last_tool=last_tool,
        )

    def record_task_notification(
        self,
        task_id: str,
        status: str,
        summary: str,
        total_tokens: int | None = None,
    ) -> None:
        self.record(
            "task_notification",
            task_id=task_id,
            status=status,
            summary=summary[:200],
            total_tokens=total_tokens,
        )

    # -- Post-session correlation --

    def correlate_turns(
        self,
        turns: list[dict[str, Any]],
    ) -> None:
        """Link tool events to LLM turns using tool_use_id matching.

        `turns` is a list of dicts, each representing one AssistantMessage:
          {
            "turn": 1,
            "text_chars": 34,
            "thinking_chars": 0,
            "tool_use_ids": ["toolu_01ABC...", ...],
          }

        For each tool_use_id in a turn, we find the matching tool_start
        and tool_end events and add a `turn` field.
        """
        # Build tool_use_id → turn mapping
        for t in turns:
            for tid in t.get("tool_use_ids", []):
                self._tool_to_turn[tid] = t["turn"]

        # Annotate existing events
        for ev in self._events:
            tid = ev.get("tool_use_id")
            if tid and tid in self._tool_to_turn:
                ev["turn"] = self._tool_to_turn[tid]

        # Now insert turn_summary events at the correct timestamps.
        # Each turn's timestamp = earliest tool_start in that turn,
        # or session_start if the turn has no tools (pure text).
        turn_first_t: dict[int, float] = {}
        for ev in self._events:
            if ev.get("turn") and ev["type"] == "tool_start":
                turn_num = ev["turn"]
                if turn_num not in turn_first_t:
                    turn_first_t[turn_num] = ev["t"]

        for t in turns:
            turn_num = t["turn"]
            ts = turn_first_t.get(turn_num)
            # For turns with no tools, use 0.0 as placeholder
            if ts is None:
                ts = 0.0
            self._events.append({
                "t": ts,
                "type": "turn_summary",
                "turn": turn_num,
                "text_chars": t.get("text_chars", 0),
                "thinking_chars": t.get("thinking_chars", 0),
                "tool_count": len(t.get("tool_use_ids", [])),
                "tool_use_ids": t.get("tool_use_ids", []),
            })

        # Re-sort all events by timestamp for clean output
        self._events.sort(key=lambda e: (e["t"], _event_sort_key(e)))

    def set_usage(self, usage: dict[str, Any]) -> None:
        """Store the final token usage breakdown from ResultMessage."""
        self._usage = usage

    # -- Serialisation --

    @property
    def total_tokens(self) -> int:
        """Compute total tokens from usage breakdown."""
        if not self._usage:
            return 0
        return (
            self._usage.get("input_tokens", 0)
            + self._usage.get("cache_creation_input_tokens", 0)
            + self._usage.get("cache_read_input_tokens", 0)
            + self._usage.get("output_tokens", 0)
        )

    def summary(self) -> dict[str, Any]:
        return {
            "total_events": len(self._events),
            "total_tokens": self.total_tokens,
            "input_tokens": self._usage.get("input_tokens", 0),
            "cache_creation_tokens": self._usage.get(
                "cache_creation_input_tokens", 0
            ),
            "cache_read_tokens": self._usage.get(
                "cache_read_input_tokens", 0
            ),
            "output_tokens": self._usage.get("output_tokens", 0),
            "total_tool_uses": self._tool_use_count,
            "total_subagents_spawned": self._subagent_count,
            "duration_s": round(self.elapsed_s, 3),
        }

    def to_list(self) -> list[dict[str, Any]]:
        return list(self._events)


def _event_sort_key(ev: dict[str, Any]) -> int:
    """Secondary sort: turn_summary before tool_start before tool_end."""
    order = {
        "turn_summary": 0,
        "subagent_start": 1,
        "tool_start": 2,
        "tool_end": 3,
        "subagent_stop": 4,
        "task_progress": 5,
        "task_notification": 6,
    }
    return order.get(ev["type"], 10)


def _summarise_tool_input(tool_name: str, tool_input: dict[str, Any]) -> str:
    """One-line summary of a tool invocation for the timeline."""
    if tool_name == "Write":
        fp = tool_input.get("file_path", "?")
        content = tool_input.get("content", "")
        return f"write {fp} ({len(content)} chars)"
    if tool_name == "Edit":
        fp = tool_input.get("file_path", "?")
        return f"edit {fp}"
    if tool_name == "Read":
        return f"read {tool_input.get('file_path', '?')}"
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return f"$ {cmd[:120]}"
    if tool_name == "Glob":
        return f"glob {tool_input.get('pattern', '?')}"
    if tool_name == "Grep":
        return f"grep {tool_input.get('pattern', '?')}"
    if tool_name == "Agent":
        desc = tool_input.get("description", "")
        stype = tool_input.get("subagent_type", "general")
        return f"agent({stype}): {desc[:80]}"
    # Fallback: first 120 chars of JSON
    raw = json.dumps(tool_input, default=str)
    return raw[:120]


# ═══════════════════════════════════════════════════════════════════════════
# §2  HOOK FACTORY — builds SDK hooks wired to an EventTimeline
# ═══════════════════════════════════════════════════════════════════════════

def build_hooks(timeline: EventTimeline) -> dict[str, list[Any]]:
    """Return a hooks dict suitable for ClaudeAgentOptions.hooks.

    Registers callbacks for:
      - PreToolUse   → log tool start
      - PostToolUse  → log tool end
      - PostToolUseFailure → log tool error
      - SubagentStart → log subagent spawn
      - SubagentStop  → log subagent finish
    """
    # Lazy import to keep module importable without the SDK
    from claude_agent_sdk import HookMatcher

    async def on_pre_tool_use(
        hook_input: Any, tool_use_id: str | None, _ctx: Any
    ) -> dict[str, Any]:
        tool_name = hook_input.get("tool_name", "?")
        tool_inp = hook_input.get("tool_input", {})
        agent_id = hook_input.get("agent_id")
        timeline.record_tool_start(
            tool_name, tool_inp, tool_use_id, agent_id
        )
        log.info(
            f"    [hook] PreToolUse: {tool_name}"
            + (f" (agent={agent_id[:8]})" if agent_id else "")
        )
        return {}  # allow the tool to proceed

    async def on_post_tool_use(
        hook_input: Any, tool_use_id: str | None, _ctx: Any
    ) -> dict[str, Any]:
        tool_name = hook_input.get("tool_name", "?")
        agent_id = hook_input.get("agent_id")
        timeline.record_tool_end(tool_name, tool_use_id, agent_id)
        return {}

    async def on_post_tool_failure(
        hook_input: Any, tool_use_id: str | None, _ctx: Any
    ) -> dict[str, Any]:
        tool_name = hook_input.get("tool_name", "?")
        error = hook_input.get("error", "unknown")
        agent_id = hook_input.get("agent_id")
        timeline.record_tool_end(
            tool_name, tool_use_id, agent_id, error=str(error)[:200]
        )
        log.warning(f"    [hook] ToolFailure: {tool_name} — {error}")
        return {}

    async def on_subagent_start(
        hook_input: Any, _tool_use_id: str | None, _ctx: Any
    ) -> dict[str, Any]:
        agent_id = hook_input.get("agent_id", "?")
        agent_type = hook_input.get("agent_type", "?")
        timeline.record_subagent_start(agent_id, agent_type)
        log.info(f"    [hook] SubagentStart: {agent_type} ({agent_id[:8]})")
        return {}

    async def on_subagent_stop(
        hook_input: Any, _tool_use_id: str | None, _ctx: Any
    ) -> dict[str, Any]:
        agent_id = hook_input.get("agent_id", "?")
        agent_type = hook_input.get("agent_type", "?")
        transcript = hook_input.get("agent_transcript_path", "")
        timeline.record_subagent_stop(agent_id, agent_type, transcript)
        log.info(f"    [hook] SubagentStop: {agent_type} ({agent_id[:8]})")
        return {}

    return {
        "PreToolUse": [
            HookMatcher(matcher=None, hooks=[on_pre_tool_use]),
        ],
        "PostToolUse": [
            HookMatcher(matcher=None, hooks=[on_post_tool_use]),
        ],
        "PostToolUseFailure": [
            HookMatcher(matcher=None, hooks=[on_post_tool_failure]),
        ],
        "SubagentStart": [
            HookMatcher(matcher=None, hooks=[on_subagent_start]),
        ],
        "SubagentStop": [
            HookMatcher(matcher=None, hooks=[on_subagent_stop]),
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# §3  DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionResult:
    """Result of a single execution run."""

    case_name: str
    model_name: str
    provider: str
    run_label: str  # e.g. "test1_opus_3min", "test2_opus"
    working_dir: str = ""
    session_id: str | None = None
    duration_ms: int = 0
    duration_api_ms: int = 0
    duration_wall_s: float = 0.0
    total_cost_usd: float | None = None
    num_turns: int = 0
    total_tokens: int = 0
    usage: dict[str, Any] | None = None
    timed_out: bool = False
    cancelled: bool = False
    error: str | None = None
    timestamp: str = ""
    timeline_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_name": self.case_name,
            "model_name": self.model_name,
            "provider": self.provider,
            "run_label": self.run_label,
            "working_dir": self.working_dir,
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "duration_api_ms": self.duration_api_ms,
            "duration_wall_s": self.duration_wall_s,
            "total_cost_usd": self.total_cost_usd,
            "num_turns": self.num_turns,
            "total_tokens": self.total_tokens,
            "usage": self.usage,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "error": self.error,
            "timestamp": self.timestamp,
            "timeline_summary": self.timeline_summary,
        }


@dataclass
class Snapshot:
    """Snapshot of a working directory after execution."""

    working_dir: str
    files: list[dict[str, Any]] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    pytest_exit_code: int | None = None
    pytest_passed: int = 0
    pytest_failed: int = 0
    pytest_errors: int = 0
    pytest_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "working_dir": self.working_dir,
            "files": self.files,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "total_bytes": self.total_bytes,
            "pytest_exit_code": self.pytest_exit_code,
            "pytest_passed": self.pytest_passed,
            "pytest_failed": self.pytest_failed,
            "pytest_errors": self.pytest_errors,
            "pytest_output": self.pytest_output,
        }


# ═══════════════════════════════════════════════════════════════════════════
# §4  WORKING DIRECTORY SETUP
# ═══════════════════════════════════════════════════════════════════════════

def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (---...---) from the plan text.

    The plan files from eval1.py have metadata frontmatter (case, framework,
    model, duration, cost, etc.) that is irrelevant to execution and could
    confuse the executing model.
    """
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def prepare_workdir(
    run_label: str,
    case_name: str,
    plan_path: Path,
) -> Path:
    """Create a fresh, isolated working directory and copy the plan into it.

    The directory is placed OUTSIDE the Pythia project tree (in /tmp/) to
    avoid CLAUDE.md contamination — otherwise Claude Code picks up project
    rules (mentor role, TDD, WTF-P) that distort the experiment.
    """
    workdir = RUNS_DIR / run_label
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # Copy case WorkingDir contents if any exist
    case_workdir = CASES_DIR / case_name / "WorkingDir"
    if case_workdir.exists():
        for item in case_workdir.iterdir():
            if item.name.startswith("."):
                continue
            dest = workdir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    # Copy the plan, stripping eval1 metadata frontmatter
    plan_text = plan_path.read_text()
    clean_plan = _strip_frontmatter(plan_text)
    (workdir / "PLAN.md").write_text(clean_plan)

    log.info(f"Prepared working directory: {workdir}")
    return workdir


# ═══════════════════════════════════════════════════════════════════════════
# §5  SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════

def snapshot_workdir(working_dir: Path) -> Snapshot:
    """Capture file list, line counts, and pytest results."""
    snap = Snapshot(working_dir=str(working_dir))

    for f in sorted(working_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(working_dir)
        # Skip hidden files and result metadata
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.name.startswith("_"):
            continue

        info: dict[str, Any] = {
            "path": str(rel),
            "size_bytes": f.stat().st_size,
        }

        # Count lines for text files
        try:
            lines = f.read_text(errors="replace").count("\n")
            info["lines"] = lines
            snap.total_lines += lines
        except Exception:
            info["lines"] = None

        snap.files.append(info)
        snap.total_files += 1
        snap.total_bytes += info["size_bytes"]

    # Run pytest if test files exist
    test_files = list(working_dir.glob("test_*.py")) + list(
        working_dir.glob("*_test.py")
    )
    if test_files:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "--tb=short", "-q"],
                cwd=str(working_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            snap.pytest_exit_code = proc.returncode
            snap.pytest_output = proc.stdout + proc.stderr

            # Parse pytest summary line
            for line in (proc.stdout + proc.stderr).splitlines():
                line_lower = line.lower()
                if "passed" in line_lower or "failed" in line_lower:
                    m_passed = re.search(r"(\d+)\s+passed", line_lower)
                    m_failed = re.search(r"(\d+)\s+failed", line_lower)
                    m_errors = re.search(r"(\d+)\s+error", line_lower)
                    if m_passed:
                        snap.pytest_passed = int(m_passed.group(1))
                    if m_failed:
                        snap.pytest_failed = int(m_failed.group(1))
                    if m_errors:
                        snap.pytest_errors = int(m_errors.group(1))
        except subprocess.TimeoutExpired:
            snap.pytest_output = "pytest timed out after 60s"
            snap.pytest_exit_code = -1
        except FileNotFoundError:
            snap.pytest_output = "pytest not found"
            snap.pytest_exit_code = -1

    return snap


# ═══════════════════════════════════════════════════════════════════════════
# §6  SESSION RUNNER — the core execution loop with full instrumentation
# ═══════════════════════════════════════════════════════════════════════════

async def run_session(
    model_name: str,
    provider: str,
    working_dir: Path,
    prompt: str,
    api_base_url: str = "",
    timeout_s: float | None = None,
    run_label: str = "",
    case_name: str = "",
) -> ExecutionResult:
    """
    Start a Claude Code session via the Agent SDK with full instrumentation.

    Tracks:
      - Every tool call (via PreToolUse / PostToolUse hooks)
      - Subagent lifecycle (via SubagentStart / SubagentStop hooks)
      - Token usage (via TaskProgressMessage / TaskNotificationMessage)
      - LLM turns (via AssistantMessage counting)

    Returns an ExecutionResult.  Saves _timeline.json to working_dir.
    """
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        query,
    )
    # Import system message types for token tracking
    from claude_agent_sdk import (
        TaskProgressMessage,
        TaskNotificationMessage,
        TaskStartedMessage,
    )

    timeline = EventTimeline()
    timeline.record("session_start", model=model_name, provider=provider)

    result = ExecutionResult(
        case_name=case_name,
        model_name=model_name,
        provider=provider,
        run_label=run_label,
        working_dir=str(working_dir),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    is_local = provider in ("ollama", "lm_studio")

    # -- Build options with hooks --
    hooks = build_hooks(timeline)

    # The bundled CLI can close its stream before final hook responses
    # are delivered, producing "Stream closed" + minified JS stack traces.
    # This is a CLI-side shutdown race condition — harmless but noisy.
    # We filter those out while keeping real errors visible.
    stderr_lines: list[str] = []

    def _stderr_handler(line: str) -> None:
        stderr_lines.append(line)
        # Suppress known shutdown noise
        if "Stream closed" in line or "Error in hook callback" in line:
            return
        # Show real errors
        log.debug(f"  [{model_name}] stderr: {line.rstrip()}")

    opts_kwargs: dict[str, Any] = {
        "permission_mode": "bypassPermissions",
        "model": model_name,
        "cwd": str(working_dir),
        "disallowed_tools": ["AskUserQuestion"],
        "hooks": hooks,
        "stderr": _stderr_handler,
    }

    if is_local:
        opts_kwargs["env"] = {
            "ANTHROPIC_BASE_URL": api_base_url or OLLAMA_BASE_URL,
            "ANTHROPIC_AUTH_TOKEN": "local",
            "ANTHROPIC_API_KEY": "local",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
            "CLAUDE_CODE_SUBAGENT_MODEL": model_name,
        }

    options = ClaudeAgentOptions(**opts_kwargs)

    # Collect turn data from AssistantMessages for post-session correlation
    turn_counter = 0
    turn_data: list[dict[str, Any]] = []

    async def _run() -> None:
        nonlocal turn_counter
        try:
            async for message in query(prompt=prompt, options=options):
                # ── AssistantMessage: one LLM turn ──
                # NOTE: These arrive batched (often all at session end).
                # We collect turn metadata and correlate with hook events
                # after the session using tool_use_id matching.
                if isinstance(message, AssistantMessage):
                    turn_counter += 1
                    text_len = 0
                    thinking_len = 0
                    tool_use_ids: list[str] = []

                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_len += len(block.text)
                        elif isinstance(block, ThinkingBlock):
                            thinking_len += len(block.thinking)
                        elif isinstance(block, ToolUseBlock):
                            tool_use_ids.append(block.id)

                    turn_data.append({
                        "turn": turn_counter,
                        "text_chars": text_len,
                        "thinking_chars": thinking_len,
                        "tool_use_ids": tool_use_ids,
                    })

                # ── TaskProgressMessage: cumulative token usage ──
                elif isinstance(message, TaskProgressMessage):
                    usage = message.usage
                    total_tok = (
                        usage.get("total_tokens", 0)
                        if isinstance(usage, dict)
                        else getattr(usage, "total_tokens", 0)
                    )
                    tool_uses = (
                        usage.get("tool_uses", 0)
                        if isinstance(usage, dict)
                        else getattr(usage, "tool_uses", 0)
                    )
                    dur_ms = (
                        usage.get("duration_ms", 0)
                        if isinstance(usage, dict)
                        else getattr(usage, "duration_ms", 0)
                    )
                    timeline.record_task_progress(
                        task_id=message.task_id,
                        total_tokens=total_tok,
                        tool_uses=tool_uses,
                        duration_ms=dur_ms,
                        last_tool=getattr(message, "last_tool_name", None),
                    )
                    log.info(
                        f"  [{model_name}] progress: "
                        f"{total_tok:,} tokens, {tool_uses} tools"
                    )

                # ── TaskNotificationMessage: task completed/failed ──
                elif isinstance(message, TaskNotificationMessage):
                    usage = message.usage
                    tok = None
                    if usage is not None:
                        tok = (
                            usage.get("total_tokens")
                            if isinstance(usage, dict)
                            else getattr(usage, "total_tokens", None)
                        )
                    timeline.record_task_notification(
                        task_id=message.task_id,
                        status=(
                            message.status
                            if isinstance(message.status, str)
                            else str(message.status)
                        ),
                        summary=message.summary,
                        total_tokens=tok,
                    )
                    log.info(
                        f"  [{model_name}] task {message.task_id[:8]}: "
                        f"{message.status} — {message.summary[:80]}"
                    )

                # ── TaskStartedMessage: subagent task started ──
                elif isinstance(message, TaskStartedMessage):
                    timeline.record(
                        "task_started",
                        task_id=message.task_id,
                        description=getattr(message, "description", ""),
                    )

                # ── ResultMessage: session finished ──
                elif isinstance(message, ResultMessage):
                    result.session_id = message.session_id
                    result.duration_ms = message.duration_ms
                    result.duration_api_ms = getattr(
                        message, "duration_api_ms", 0
                    )
                    result.total_cost_usd = message.total_cost_usd
                    result.num_turns = message.num_turns
                    result.usage = message.usage

                    # Store usage for token breakdown
                    if isinstance(message.usage, dict):
                        timeline.set_usage(message.usage)

                    timeline.record(
                        "session_end",
                        session_id=message.session_id,
                        num_turns=message.num_turns,
                        cost_usd=message.total_cost_usd,
                        duration_ms=message.duration_ms,
                        usage=message.usage,
                        stop_reason=getattr(message, "stop_reason", None),
                    )

        except asyncio.CancelledError:
            result.cancelled = True
            timeline.record("session_cancelled")
            raise
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            timeline.record("session_error", error=result.error)

    t0 = time.monotonic()

    if timeout_s is not None:
        try:
            await asyncio.wait_for(_run(), timeout=timeout_s)
        except asyncio.TimeoutError:
            result.timed_out = True
            timeline.record("session_timeout", timeout_s=timeout_s)
            log.info(
                f"  [{model_name}] timed out after {timeout_s:.0f}s"
            )
    else:
        await _run()

    # -- Post-session: correlate turns with hook events --
    timeline.correlate_turns(turn_data)

    result.duration_wall_s = time.monotonic() - t0
    result.total_tokens = timeline.total_tokens
    result.timeline_summary = timeline.summary()

    # Save timeline
    timeline_path = Path(working_dir) / "_timeline.json"
    timeline_data = {
        "model": model_name,
        "provider": provider,
        "summary": timeline.summary(),
        "events": timeline.to_list(),
    }
    timeline_path.write_text(json.dumps(timeline_data, indent=2))
    log.info(
        f"  [{model_name}] timeline saved: {len(timeline.to_list())} events, "
        f"{timeline.total_tokens:,} tokens"
    )

    # Save full stderr for debugging (including filtered shutdown noise)
    stderr_log = Path(working_dir) / "_stderr.log"
    stderr_log.write_text("\n".join(stderr_lines))

    return result


# ═══════════════════════════════════════════════════════════════════════════
# §7  TEST 1 — Opus with timeout
# ═══════════════════════════════════════════════════════════════════════════

async def test1_baseline(
    case_name: str,
    plan_path: Path,
    timeout_s: float = 180.0,
) -> None:
    """Test 1: Opus executes the plan with a hard time cutoff."""
    run_label = f"{case_name}/test1_opus_3min"
    workdir = prepare_workdir(run_label, case_name, plan_path)

    prompt = (
        f"Read the implementation plan in {workdir}/PLAN.md and execute it. "
        "Implement all files described in the plan in this directory. Use subagents for independent implementation tasks."
    )

    log.info(f"=== Test 1: Opus executing plan (timeout={timeout_s}s) ===")
    log.info(f"  Plan: {plan_path}")
    log.info(f"  Working dir: {workdir}")

    result = await run_session(
        model_name="claude-opus-4-6",
        provider="anthropic",
        working_dir=workdir,
        prompt=prompt,
        timeout_s=timeout_s,
        run_label=run_label,
        case_name=case_name,
    )

    # Save result metadata
    result_path = workdir / "_result.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2))

    # Take snapshot
    snap = snapshot_workdir(workdir)
    snap_path = workdir / "_snapshot.json"
    snap_path.write_text(json.dumps(snap.to_dict(), indent=2))

    _print_single_result("Test 1: Opus", timeout_s, result, snap, workdir)


# ═══════════════════════════════════════════════════════════════════════════
# §8  TEST 2 — Opus vs gpt-oss parallel
# ═══════════════════════════════════════════════════════════════════════════

async def test2_parallel(
    case_name: str,
    plan_path: Path,
) -> None:
    """Test 2: Opus and gpt-oss execute the same plan in parallel."""
    opus_label = f"{case_name}/test2_opus"
    gptoss_label = f"{case_name}/test2_gptoss"

    opus_workdir = prepare_workdir(opus_label, case_name, plan_path)
    gptoss_workdir = prepare_workdir(gptoss_label, case_name, plan_path)

    prompt = (
        "Read the implementation plan in ./PLAN.md and execute it. "
        "Implement all files described in the plan in this directory."
    )

    log.info("=== Test 2: Opus vs gpt-oss parallel execution ===")
    log.info(f"  Plan: {plan_path}")
    log.info(f"  Opus dir:   {opus_workdir}")
    log.info(f"  gpt-oss dir: {gptoss_workdir}")

    # Start both sessions
    opus_task = asyncio.create_task(
        run_session(
            model_name="claude-opus-4-6",
            provider="anthropic",
            working_dir=opus_workdir,
            prompt=prompt,
            run_label=opus_label,
            case_name=case_name,
        )
    )

    gptoss_task = asyncio.create_task(
        run_session(
            model_name="gpt-oss:20b",
            provider="ollama",
            working_dir=gptoss_workdir,
            prompt=prompt,
            api_base_url=OLLAMA_BASE_URL,
            run_label=gptoss_label,
            case_name=case_name,
        )
    )

    # Wait for Opus to finish, then cancel gpt-oss
    opus_result = await opus_task
    log.info(
        f"  Opus finished in {opus_result.duration_wall_s:.1f}s — "
        f"cancelling gpt-oss"
    )

    gptoss_task.cancel()
    try:
        gptoss_result = await gptoss_task
    except asyncio.CancelledError:
        gptoss_result = ExecutionResult(
            case_name=case_name,
            model_name="gpt-oss:20b",
            provider="ollama",
            run_label=gptoss_label,
            working_dir=str(gptoss_workdir),
            cancelled=True,
            duration_wall_s=opus_result.duration_wall_s,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Save results
    for res, wdir in [
        (opus_result, opus_workdir),
        (gptoss_result, gptoss_workdir),
    ]:
        result_path = wdir / "_result.json"
        result_path.write_text(json.dumps(res.to_dict(), indent=2))

    # Take snapshots
    opus_snap = snapshot_workdir(opus_workdir)
    gptoss_snap = snapshot_workdir(gptoss_workdir)

    for snap, wdir in [
        (opus_snap, opus_workdir),
        (gptoss_snap, gptoss_workdir),
    ]:
        snap_path = wdir / "_snapshot.json"
        snap_path.write_text(json.dumps(snap.to_dict(), indent=2))

    # Print comparison
    _print_comparison(opus_result, gptoss_result, opus_snap, gptoss_snap,
                      opus_workdir, gptoss_workdir)


# ═══════════════════════════════════════════════════════════════════════════
# §9  OUTPUT FORMATTING
# ═══════════════════════════════════════════════════════════════════════════

def _print_single_result(
    title: str,
    timeout_s: float,
    result: ExecutionResult,
    snap: Snapshot,
    workdir: Path,
) -> None:
    ts = result.timeline_summary
    print(f"\n{'='*60}")
    print(f"{title} ({timeout_s}s cutoff)")
    print(f"{'='*60}")
    print(f"  Wall time:        {result.duration_wall_s:.1f}s")
    print(f"  API time:         {result.duration_ms}ms")
    print(f"  Timed out:        {result.timed_out}")
    print(f"  Cost:             ${result.total_cost_usd or 0:.4f}")
    print(f"  Turns:            {result.num_turns}")
    print(f"  --- Tokens ---")
    print(f"  Total:            {result.total_tokens:,}")
    print(f"    Input:          {ts.get('input_tokens', 0):,}")
    print(f"    Cache create:   {ts.get('cache_creation_tokens', 0):,}")
    print(f"    Cache read:     {ts.get('cache_read_tokens', 0):,}")
    print(f"    Output:         {ts.get('output_tokens', 0):,}")
    print(f"  --- Pipeline ---")
    print(f"  Tool uses:        {ts.get('total_tool_uses', 0)}")
    print(f"  Subagents:        {ts.get('total_subagents_spawned', 0)}")
    print(f"  Timeline events:  {ts.get('total_events', 0)}")
    print(f"  --- Output ---")
    print(f"  Files:            {snap.total_files}")
    print(f"  Lines of code:    {snap.total_lines}")
    print(f"  Tests passed:     {snap.pytest_passed}")
    print(f"  Tests failed:     {snap.pytest_failed}")
    if result.error:
        print(f"  Error:            {result.error}")
    print(f"\n  Results:  {workdir}")
    print(f"  Timeline: {workdir / '_timeline.json'}")


def _print_comparison(
    opus: ExecutionResult,
    gptoss: ExecutionResult,
    opus_snap: Snapshot,
    gptoss_snap: Snapshot,
    opus_dir: Path,
    gptoss_dir: Path,
) -> None:
    ots = opus.timeline_summary
    gts = gptoss.timeline_summary

    print(f"\n{'='*60}")
    print("Test 2 Results: Opus vs gpt-oss (parallel)")
    print(f"{'='*60}")
    print(f"{'Metric':<20} {'Opus':>15} {'gpt-oss':>15}")
    print(f"{'-'*50}")

    rows = [
        ("Wall time (s)", f"{opus.duration_wall_s:.1f}",
         f"{gptoss.duration_wall_s:.1f}"),
        ("Cost ($)", f"{opus.total_cost_usd or 0:.4f}",
         f"{gptoss.total_cost_usd or 0:.4f}"),
        ("Turns", str(opus.num_turns), str(gptoss.num_turns)),
        ("Total tokens", f"{opus.total_tokens:,}",
         f"{gptoss.total_tokens:,}"),
        ("  Input", f"{ots.get('input_tokens', 0):,}",
         f"{gts.get('input_tokens', 0):,}"),
        ("  Cache create", f"{ots.get('cache_creation_tokens', 0):,}",
         f"{gts.get('cache_creation_tokens', 0):,}"),
        ("  Cache read", f"{ots.get('cache_read_tokens', 0):,}",
         f"{gts.get('cache_read_tokens', 0):,}"),
        ("  Output", f"{ots.get('output_tokens', 0):,}",
         f"{gts.get('output_tokens', 0):,}"),
        ("Tool uses", str(ots.get("total_tool_uses", 0)),
         str(gts.get("total_tool_uses", 0))),
        ("Subagents", str(ots.get("total_subagents_spawned", 0)),
         str(gts.get("total_subagents_spawned", 0))),
        ("Files created", str(opus_snap.total_files),
         str(gptoss_snap.total_files)),
        ("Lines of code", str(opus_snap.total_lines),
         str(gptoss_snap.total_lines)),
        ("Tests passed", str(opus_snap.pytest_passed),
         str(gptoss_snap.pytest_passed)),
        ("Tests failed", str(opus_snap.pytest_failed),
         str(gptoss_snap.pytest_failed)),
        ("Cancelled", "yes" if opus.cancelled else "no",
         "yes" if gptoss.cancelled else "no"),
    ]

    for label, v1, v2 in rows:
        print(f"{label:<20} {v1:>15} {v2:>15}")

    print(f"\n  Opus dir:    {opus_dir}")
    print(f"  gpt-oss dir: {gptoss_dir}")
    print(f"  Timelines:   _timeline.json in each directory")


# ═══════════════════════════════════════════════════════════════════════════
# §10  SNAPSHOT COMMAND
# ═══════════════════════════════════════════════════════════════════════════

def cmd_snapshot(args: argparse.Namespace) -> None:
    """Print snapshot of a run directory."""
    workdir = Path(args.dir).resolve()
    if not workdir.exists():
        print(f"Directory not found: {workdir}", file=sys.stderr)
        sys.exit(1)

    snap = snapshot_workdir(workdir)

    print(f"\nSnapshot: {workdir}")
    print(f"  Files:        {snap.total_files}")
    print(f"  Total lines:  {snap.total_lines}")
    print(f"  Total bytes:  {snap.total_bytes}")
    print()

    for f in snap.files:
        lines_str = (
            f"{f['lines']:>5}" if f["lines"] is not None else "  bin"
        )
        print(
            f"  {lines_str} lines  {f['size_bytes']:>8} bytes  {f['path']}"
        )

    if snap.pytest_exit_code is not None:
        print(f"\n  pytest exit code: {snap.pytest_exit_code}")
        print(
            f"  passed: {snap.pytest_passed}  "
            f"failed: {snap.pytest_failed}  "
            f"errors: {snap.pytest_errors}"
        )
        if snap.pytest_output.strip():
            print(f"\n  --- pytest output ---")
            for line in snap.pytest_output.strip().splitlines():
                print(f"  {line}")

    # Also print timeline summary if available
    tl_path = workdir / "_timeline.json"
    if tl_path.exists():
        tl = json.loads(tl_path.read_text())
        s = tl.get("summary", {})
        print(f"\n  --- Timeline Summary ---")
        print(f"  Events:     {s.get('total_events', '?')}")
        print(f"  Tokens:     {s.get('total_tokens', '?'):,}")
        print(f"  Tool uses:  {s.get('total_tool_uses', '?')}")
        print(f"  Subagents:  {s.get('total_subagents_spawned', '?')}")

    # Save snapshot
    snap_path = workdir / "_snapshot.json"
    snap_path.write_text(json.dumps(snap.to_dict(), indent=2))
    print(f"\n  Saved to: {snap_path}")


# ═══════════════════════════════════════════════════════════════════════════
# §11  CLI
# ═══════════════════════════════════════════════════════════════════════════

def resolve_plan_path(case_name: str, plan_file: str = DEFAULT_PLAN) -> Path:
    """Resolve the plan file path from the results directory."""
    plan_path = RESULTS_DIR / case_name / "plans" / plan_file
    if not plan_path.exists():
        print(f"Plan not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
    return plan_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan execution experiments with full instrumentation"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Debug logging"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # test1
    p1 = sub.add_parser("test1", help="Opus executes plan with timeout")
    p1.add_argument("--case", required=True, help="Case name")
    p1.add_argument(
        "--plan", default=DEFAULT_PLAN,
        help="Plan filename in results/plans/",
    )
    p1.add_argument(
        "--timeout", type=float, default=180.0,
        help="Timeout in seconds (default: 180)",
    )

    # test2
    p2 = sub.add_parser("test2", help="Opus vs gpt-oss parallel")
    p2.add_argument("--case", required=True, help="Case name")
    p2.add_argument(
        "--plan", default=DEFAULT_PLAN,
        help="Plan filename in results/plans/",
    )

    # snapshot
    p3 = sub.add_parser("snapshot", help="Snapshot a run directory")
    p3.add_argument("--dir", required=True, help="Path to run directory")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "test1":
        plan_path = resolve_plan_path(args.case, args.plan)
        asyncio.run(test1_baseline(args.case, plan_path, args.timeout))

    elif args.command == "test2":
        plan_path = resolve_plan_path(args.case, args.plan)
        asyncio.run(test2_parallel(args.case, plan_path))

    elif args.command == "snapshot":
        cmd_snapshot(args)


if __name__ == "__main__":
    main()
