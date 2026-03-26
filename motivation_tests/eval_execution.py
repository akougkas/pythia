#!/usr/bin/env python3
"""
eval_execution.py — Plan Execution Experiments
================================================

Measures execution quality: given the same plan, how much working code
does each model produce within a time budget?

Test 1: gpt-oss generates a plan, starts executing it, and is stopped
        after a timeout (default 30s).  The solver context is saved so a
        follow-up agent can merge the partial work with its own plan.
Test 2: Speculative dispatch — gpt-oss and Opus generate plans in
        parallel; gpt-oss starts executing immediately; when Opus finishes
        planning, gpt-oss execution is stopped and context is saved.
Test 3: Speculative dispatch + merge — same as Test 2, then Opus takes
        over gpt-oss's workdir, evaluates its partial work, and decides
        to reuse / merge / discard before completing the task.

Instrumentation:
  - Full event timeline (tool calls, subagent lifecycle, task progress)
  - Per-step token tracking via TaskProgressMessage
  - Subagent start/stop hooks with agent_id attribution
  - Pre/PostToolUse hooks to trace every tool invocation

Usage:
    # Test 1 — gpt-oss plan + execute + stop after 30s
    python eval_execution.py test1 --case case_002_file_watcher [--timeout 30]

    # Test 2 — Speculative dispatch (plan + execute)
    python eval_execution.py test2 --case case_003_data_pipeline

    # Test 3 — Speculative dispatch + merge
    python eval_execution.py test3 --case case_003_data_pipeline

    # Snapshot a run directory (files, LOC, pytest)
    python eval_execution.py snapshot --dir runs/test1_opus_3min
"""

from __future__ import annotations

import argparse
import ast
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
from typing import Any, Literal

log = logging.getLogger("eval_execution")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results_2"
# CASES_DIR = SCRIPT_DIR / "cases"
CASES_DIR = Path("/home/jye/publications/cases/")
# CASES_DIR = Path("/Users/yejie/publications/cases/")

# Runs directory is OUTSIDE the Pythia project tree to avoid CLAUDE.md
# contamination.  Claude Code walks up the directory tree looking for
# project config — if the working directory is inside Pythia, it picks
# up CLAUDE.md rules (mentor role, TDD, WTF-P gates) that distort the
# experiment.
RUNS_DIR = Path("/home/jye/publications/pythia_eval_runs")
# RUNS_DIR = Path("/Users/yejie/publications/pythia_eval_runs")

# Default plan to execute (gpt-oss plan for case_002)
DEFAULT_PLAN = "claude_code__ollama__gpt-oss_20b.md"

# Ollama endpoint
OLLAMA_BASE_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# SDK patch: tolerate missing 'signature' in thinking blocks from local models
# ---------------------------------------------------------------------------
# Local models (e.g. gpt-oss via Ollama) may emit thinking blocks that lack
# the Anthropic-proprietary 'signature' field.  The SDK's message parser
# raises MessageParseError in this case.  We patch it so missing signatures
# are replaced with an empty string instead of crashing.

def _patch_sdk_thinking_signature() -> None:
    """Monkey-patch claude_agent_sdk message parser to tolerate missing signature."""
    try:
        import claude_agent_sdk._internal.message_parser as mp
        _original_parse = mp.parse_message

        def _patched_parse(data: dict) -> Any:
            # Inject empty signature into thinking blocks that lack it
            if isinstance(data, dict) and data.get("type") == "assistant":
                msg = data.get("message", {})
                for block in msg.get("content", []):
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "thinking"
                        and "signature" not in block
                    ):
                        block["signature"] = ""
            return _original_parse(data)

        mp.parse_message = _patched_parse
        log.debug("Patched SDK message parser for missing thinking signatures")
    except Exception as e:
        log.warning(f"Could not patch SDK message parser: {e}")

_patch_sdk_thinking_signature()


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
        extra: dict[str, Any] = {}
        # For Agent calls, capture the full prompt so context docs can
        # tell a follow-up agent exactly what each subagent was tasked with.
        if tool_name == "Agent":
            extra["agent_prompt"] = tool_input.get("prompt", "")
        self.record(
            "tool_start",
            tool=tool_name,
            tool_use_id=tool_use_id,
            agent_id=agent_id,
            input_summary=summary,
            **extra,
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
        transcript_stats: dict[str, Any] | None = None,
    ) -> None:
        start_info = self._active_subagents.pop(agent_id, {})
        duration = self.elapsed_s - start_info.get("start_t", 0.0)
        extra: dict[str, Any] = {}
        if transcript_stats:
            extra.update(transcript_stats)
        self.record(
            "subagent_stop",
            agent_id=agent_id,
            agent_type=agent_type,
            duration_s=round(duration, 3),
            transcript_path=transcript_path,
            **extra,
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

    # -- Context generation for portable handoff --

    SessionRole = Literal["solver", "speculative_dispatcher"]

    def build_context(
        self,
        role: SessionRole,
        model_name: str,
        working_dir: Path,
        timeout_s: float | None,
        session_id: str | None,
    ) -> str:
        """Build a portable markdown context document from the timeline.

        Args:
            role: "solver" — single agent executing a plan.
                  "speculative_dispatcher" — orchestrator that spawns workers.
            model_name: Model that ran this session.
            working_dir: Where files were written.
            timeout_s: Timeout budget (None if completed naturally).
            session_id: Claude Code session ID (for reference only).

        Returns:
            Markdown string suitable for writing to *_context.md.
        """
        if role == "solver":
            return self._build_solver_context(
                model_name, working_dir, timeout_s, session_id
            )
        else:
            return self._build_dispatcher_context(
                model_name, working_dir, timeout_s, session_id
            )

    # ── solver context ───────────────────────────────────────────────

    def _build_solver_context(
        self,
        model_name: str,
        working_dir: Path,
        timeout_s: float | None,
        session_id: str | None,
    ) -> str:
        """Context for a solver: per-subagent detail with prompts, files, status."""
        lines: list[str] = []
        elapsed = round(self.elapsed_s, 1)
        timed_out = any(e["type"] == "session_timeout" for e in self._events)

        lines.append("# Solver Execution Context")
        lines.append("")
        status = "INTERRUPTED (timeout)" if timed_out else "completed"
        lines.append(f"- **Status**: {status}")
        lines.append(f"- **Model**: {model_name}")
        lines.append(f"- **Wall time**: {elapsed}s"
                      + (f" / {timeout_s}s budget" if timeout_s else ""))
        lines.append(f"- **Tokens**: {self.total_tokens:,}")
        lines.append(f"- **Tool uses**: {self._tool_use_count}")
        if session_id:
            lines.append(f"- **Session ID**: {session_id}")
        lines.append("")

        # ── Build per-subagent records ──
        # Collect: agent_id → {description, prompt, status, files_written,
        #                      files_read, tokens, duration, errors}
        agent_descs: dict[str, str] = {}   # task_id → description
        agent_prompts: dict[str, str] = {} # tool_use_id → prompt
        # Map tool_use_id (of Agent tool call) → agent_id
        agent_tool_to_id: dict[str, str] = {}

        for ev in self._events:
            if ev["type"] == "task_started":
                agent_descs[ev["task_id"]] = ev.get("description", "")
            elif (ev["type"] == "tool_start" and ev["tool"] == "Agent"
                  and ev.get("agent_prompt")):
                agent_prompts[ev.get("tool_use_id", "")] = ev["agent_prompt"]

        # Match Agent tool_use_id → agent_id via subagent_start events
        # (subagent_start fires right after the Agent tool_start)
        agent_tool_events = [
            ev for ev in self._events
            if ev["type"] == "tool_start" and ev["tool"] == "Agent"
        ]
        subagent_starts = [
            ev for ev in self._events if ev["type"] == "subagent_start"
        ]
        # Pair them by order (Agent tool_start N → subagent_start N)
        for atev, ssev in zip(agent_tool_events, subagent_starts):
            tuid = atev.get("tool_use_id", "")
            aid = ssev["agent_id"]
            agent_tool_to_id[tuid] = aid

        # Resolve prompt per agent_id
        agent_id_prompts: dict[str, str] = {}
        for tuid, aid in agent_tool_to_id.items():
            if tuid in agent_prompts:
                agent_id_prompts[aid] = agent_prompts[tuid]

        # Collect files written/read per agent_id (None = main orchestrator)
        files_by_agent: dict[str | None, list[str]] = {}   # agent_id → [rel_paths]
        reads_by_agent: dict[str | None, list[str]] = {}

        for ev in self._events:
            if ev["type"] != "tool_start":
                continue
            summary = ev.get("input_summary", "")
            aid = ev.get("agent_id")

            if ev["tool"] == "Write":
                parts = summary.split(" ", 1)
                if len(parts) > 1:
                    fp = parts[1].split(" (")[0]
                    try:
                        rel = str(Path(fp).relative_to(working_dir))
                    except ValueError:
                        rel = fp
                    files_by_agent.setdefault(aid, [])
                    if rel not in files_by_agent[aid]:
                        files_by_agent[aid].append(rel)

            elif ev["tool"] == "Read":
                fp = summary.replace("read ", "", 1).strip()
                try:
                    rel = str(Path(fp).relative_to(working_dir))
                except ValueError:
                    rel = fp
                reads_by_agent.setdefault(aid, [])
                if rel not in reads_by_agent[aid]:
                    reads_by_agent[aid].append(rel)

        # Collect completed / in-progress subagents
        completed_ids: set[str] = set()
        completed_tokens: dict[str, int] = {}
        for ev in self._events:
            if ev["type"] == "task_notification" and ev.get("status") == "completed":
                tid = ev["task_id"]
                completed_ids.add(tid)
                completed_tokens[tid] = ev.get("total_tokens", 0)

        stopped_agents: dict[str, dict[str, Any]] = {}
        for ev in self._events:
            if ev["type"] == "subagent_stop":
                stopped_agents[ev["agent_id"]] = ev

        # All known agent_ids (from subagent_start events)
        all_agent_ids: list[str] = [
            ev["agent_id"] for ev in self._events
            if ev["type"] == "subagent_start"
        ]

        # ── Render per-subagent sections ──
        lines.append("## Subagents")
        lines.append("")

        for aid in all_agent_ids:
            desc = agent_descs.get(aid, "unknown task")
            is_done = aid in completed_ids
            is_killed = aid in self._active_subagents
            short_id = aid[:8]

            if is_done:
                checkbox = "[x]"
                status_label = "COMPLETED"
            elif is_killed:
                checkbox = "[ ]"
                status_label = "KILLED (timeout)"
            else:
                checkbox = "[?]"
                status_label = "unknown"

            lines.append(f"### {checkbox} {desc} (`{short_id}`)")
            lines.append("")
            lines.append(f"- **Status**: {status_label}")

            if aid in stopped_agents:
                sa = stopped_agents[aid]
                lines.append(f"- **Duration**: {sa.get('duration_s', 0):.1f}s")
                lines.append(f"- **Model**: {sa.get('model', '?')}")
                tok_in = sa.get("input_tokens", 0)
                tok_out = sa.get("output_tokens", 0)
                lines.append(f"- **Tokens**: {tok_in}in / {tok_out}out")
            elif is_killed:
                started_at = self._active_subagents[aid].get("start_t", 0)
                lines.append(
                    f"- **Ran for**: {elapsed - started_at:.1f}s before kill"
                )

            # Prompt (the instructions the orchestrator gave this subagent)
            prompt = agent_id_prompts.get(aid, "")
            if prompt:
                lines.append(f"- **Prompt**:")
                # Indent the prompt as a blockquote for readability
                for pline in prompt.strip().splitlines():
                    lines.append(f"  > {pline}")

            # Files this subagent wrote
            written = files_by_agent.get(aid, [])
            if written:
                lines.append(f"- **Files written**: {', '.join(f'`{f}`' for f in written)}")

            # Files this subagent read
            read = reads_by_agent.get(aid, [])
            if read:
                lines.append(f"- **Files read**: {', '.join(f'`{f}`' for f in read)}")

            lines.append("")

        # ── Orchestrator (main agent) direct actions ──
        main_written = files_by_agent.get(None, [])
        main_read = reads_by_agent.get(None, [])
        if main_written or main_read:
            lines.append("## Orchestrator Direct Actions")
            lines.append("")
            if main_written:
                lines.append(
                    f"- **Files written**: "
                    f"{', '.join(f'`{f}`' for f in main_written)}"
                )
            if main_read:
                lines.append(
                    f"- **Files read**: "
                    f"{', '.join(f'`{f}`' for f in main_read)}"
                )
            lines.append("")

        # ── Aggregate file inventory ──
        all_written: list[str] = []
        for flist in files_by_agent.values():
            for f in flist:
                if f not in all_written:
                    all_written.append(f)

        lines.append("## Files Present After Execution")
        if all_written:
            for f in all_written:
                exists = (working_dir / f).exists()
                marker = "exists" if exists else "MISSING"
                lines.append(f"- `{f}` ({marker})")
        else:
            lines.append("- (none)")
        lines.append("")

        # ── Errors encountered ──
        errors: list[dict[str, Any]] = [
            ev for ev in self._events
            if ev["type"] == "tool_end" and ev.get("error")
        ]
        if errors:
            lines.append("## Errors Encountered")
            for err in errors:
                agent = err.get("agent_id")
                prefix = f"[{agent[:8]}] " if agent else "[main] "
                lines.append(f"- {prefix}`{err['tool']}`: {err['error']}")
            lines.append("")

        return "\n".join(lines)

    # ── speculative dispatcher context ───────────────────────────────

    def _build_dispatcher_context(
        self,
        model_name: str,
        working_dir: Path,
        timeout_s: float | None,
        session_id: str | None,
    ) -> str:
        """Context for a speculative dispatcher: dispatch decisions, worker
        outcomes, resource usage, and speculation results."""
        lines: list[str] = []
        elapsed = round(self.elapsed_s, 1)
        timed_out = any(e["type"] == "session_timeout" for e in self._events)

        lines.append("# Speculative Dispatcher Context")
        lines.append("")
        status = "INTERRUPTED (timeout)" if timed_out else "completed"
        lines.append(f"- **Status**: {status}")
        lines.append(f"- **Model**: {model_name}")
        lines.append(f"- **Wall time**: {elapsed}s"
                      + (f" / {timeout_s}s budget" if timeout_s else ""))
        lines.append(f"- **Total tokens**: {self.total_tokens:,}")
        lines.append(f"- **Workers spawned**: {self._subagent_count}")
        if session_id:
            lines.append(f"- **Session ID**: {session_id}")
        lines.append("")

        # ── Worker dispatch log ──
        # Gather all subagent start/stop pairs with their stats
        worker_starts: dict[str, dict[str, Any]] = {}
        worker_stops: dict[str, dict[str, Any]] = {}
        worker_descs: dict[str, str] = {}

        for ev in self._events:
            if ev["type"] == "subagent_start":
                worker_starts[ev["agent_id"]] = ev
            elif ev["type"] == "subagent_stop":
                worker_stops[ev["agent_id"]] = ev
            elif ev["type"] == "task_started":
                worker_descs[ev["task_id"]] = ev.get("description", "")

        lines.append("## Worker Dispatch Log")
        lines.append("")
        lines.append("| Worker | Task | Status | Duration | Tokens | Model |")
        lines.append("|--------|------|--------|----------|--------|-------|")

        for agent_id, start_ev in worker_starts.items():
            desc = worker_descs.get(agent_id, "?")
            short_id = agent_id[:8]
            if agent_id in worker_stops:
                stop_ev = worker_stops[agent_id]
                dur = f"{stop_ev.get('duration_s', 0):.1f}s"
                tok_in = stop_ev.get("input_tokens", 0)
                tok_out = stop_ev.get("output_tokens", 0)
                model = stop_ev.get("model", "?")
                status_str = "done"
            elif agent_id in self._active_subagents:
                started_at = self._active_subagents[agent_id].get("start_t", 0)
                dur = f"{elapsed - started_at:.1f}s (killed)"
                tok_in = 0
                tok_out = 0
                model = "?"
                status_str = "**KILLED**"
            else:
                dur = "?"
                tok_in = 0
                tok_out = 0
                model = "?"
                status_str = "unknown"
            lines.append(
                f"| {short_id} | {desc} | {status_str} | {dur} "
                f"| {tok_in}in/{tok_out}out | {model} |"
            )
        lines.append("")

        # ── Parallelism timeline ──
        # Show which workers overlapped (useful for speculation analysis)
        lines.append("## Parallelism Timeline")
        lines.append("```")
        if worker_starts:
            # Find the time range
            t_min = min(
                ev.get("t", 0) for ev in worker_starts.values()
            )
            t_max = elapsed
            for agent_id, start_ev in worker_starts.items():
                desc = worker_descs.get(agent_id, agent_id[:8])[:30]
                t_start = start_ev.get("t", 0)
                if agent_id in worker_stops:
                    t_end = worker_stops[agent_id].get("t", t_max)
                else:
                    t_end = t_max  # killed at timeout
                lines.append(
                    f"  {desc:<30s}  "
                    f"[{t_start:6.1f}s — {t_end:6.1f}s]  "
                    f"({t_end - t_start:.1f}s)"
                )
        lines.append("```")
        lines.append("")

        # ── Files produced with structural fingerprints ──
        # Collect file paths, write times, and sizes from Write events.
        # A file may be written multiple times (overwrite); keep last write.
        file_meta: dict[str, dict[str, Any]] = {}  # rel_path -> {abs, t, chars}
        for ev in self._events:
            if ev["type"] == "tool_start" and ev["tool"] == "Write":
                summary = ev.get("input_summary", "")
                parts = summary.split(" ", 1)
                if len(parts) > 1:
                    fp = parts[1].split(" (")[0]
                    # Extract char count from summary like "write /path (4223 chars)"
                    chars = 0
                    m = re.search(r"\((\d+)\s+chars?\)", summary)
                    if m:
                        chars = int(m.group(1))
                    try:
                        rel = str(Path(fp).relative_to(working_dir))
                    except ValueError:
                        rel = fp
                    file_meta[rel] = {
                        "abs": Path(fp),
                        "t": ev.get("t"),
                        "chars": chars,
                    }

        # Also detect files created via Bash (mkdir, cp, echo >, etc.)
        # by scanning the working directory for files not in file_meta.
        try:
            for p in sorted(working_dir.rglob("*")):
                if not p.is_file():
                    continue
                # Skip hidden files, __pycache__, and timeline/context artifacts
                if any(
                    part.startswith(".") or part == "__pycache__"
                    for part in p.relative_to(working_dir).parts
                ):
                    continue
                if p.name.startswith("_") or p.name.endswith("_context.md"):
                    continue
                if p.name.endswith("_PLAN.md"):
                    continue
                try:
                    rel = str(p.relative_to(working_dir))
                except ValueError:
                    continue
                if rel not in file_meta:
                    file_meta[rel] = {
                        "abs": p,
                        "t": None,  # unknown — not from a Write event
                        "chars": 0,
                    }
        except OSError:
            pass

        lines.append("## File Inventory")
        lines.append("")

        if not file_meta:
            lines.append("No files produced.")
            lines.append("")
        else:
            # Summary table first for quick scanning
            lines.append("| File | Size | Lines | Written at | Status |")
            lines.append("|------|------|-------|------------|--------|")
            for rel in sorted(file_meta.keys()):
                meta = file_meta[rel]
                absp = meta["abs"]
                exists = absp.exists()
                if exists:
                    sz = absp.stat().st_size
                    try:
                        lc = absp.read_text(
                            encoding="utf-8", errors="replace"
                        ).count("\n") + 1
                    except Exception:
                        lc = "?"
                else:
                    sz = meta["chars"]
                    lc = "?"
                t_str = f"T={meta['t']:.1f}s" if meta["t"] is not None else "—"
                status = "on disk" if exists else "MISSING"
                lines.append(
                    f"| `{rel}` | {sz:,}B | {lc} | {t_str} | {status} |"
                )
            lines.append("")

            # Detailed fingerprint per file
            lines.append("## File Details")
            lines.append("")
            for rel in sorted(file_meta.keys()):
                meta = file_meta[rel]
                absp = meta["abs"]
                if absp.exists():
                    fp = _extract_file_fingerprint(absp)
                    fp_lines = _format_fingerprint_md(
                        rel, fp, write_time=meta["t"]
                    )
                    lines.extend(fp_lines)
                else:
                    lines.append(f"### `{rel}` (MISSING)")
                    t_str = (f"Written at T={meta['t']:.1f}s"
                             if meta["t"] is not None else "")
                    if t_str:
                        lines.append(f"- {t_str}, but file no longer on disk")
                    lines.append("")

        # ── Commands executed (Bash tool calls) ──
        bash_events: list[dict[str, Any]] = []
        for ev in self._events:
            if ev["type"] == "tool_start" and ev["tool"] == "Bash":
                cmd = ev.get("input_summary", "")
                # Find matching tool_end for error/success
                end_ev = next(
                    (e for e in self._events
                     if e["type"] == "tool_end"
                     and e.get("tool_use_id") == ev.get("tool_use_id")),
                    None,
                )
                bash_events.append({
                    "t": ev.get("t"),
                    "cmd": cmd,
                    "error": end_ev.get("error") if end_ev else None,
                })

        if bash_events:
            lines.append("## Commands Executed")
            lines.append("")
            lines.append("| Time | Command | Result |")
            lines.append("|------|---------|--------|")
            for be in bash_events:
                t_str = f"T={be['t']:.1f}s" if be["t"] is not None else "—"
                result = "ERROR" if be["error"] else "OK"
                cmd = be["cmd"][:100]
                lines.append(f"| {t_str} | `{cmd}` | {result} |")
            lines.append("")

        # ── Execution summary ──
        lines.append("## Execution Summary")
        total_files = len(file_meta)
        existing = sum(1 for m in file_meta.values() if m["abs"].exists())
        missing = total_files - existing
        lines.append(f"- **Files produced**: {total_files}")
        lines.append(f"- **On disk**: {existing}")
        if missing:
            lines.append(f"- **Missing/deleted**: {missing}")
        tests_ran = any("pytest" in be.get("cmd", "") for be in bash_events)
        lines.append(f"- **Tests executed**: {'yes' if tests_ran else 'no'}")
        lines.append("")

        # ── Errors ──
        errors = [
            ev for ev in self._events
            if ev["type"] == "tool_end" and ev.get("error")
        ]
        if errors:
            lines.append("## Errors")
            for err in errors:
                agent = err.get("agent_id", "main")
                if agent:
                    agent = agent[:8]
                lines.append(f"- [{agent}] `{err['tool']}`: {err['error']}")
            lines.append("")

        return "\n".join(lines)


def _extract_file_fingerprint(filepath: Path) -> dict[str, Any]:
    """Extract structural fingerprint from a file on disk.

    For Python files: uses ast to get imports, functions, classes, and
    top-level variable assignments.
    For YAML files: uses yaml.safe_load to get top-level keys and structure.
    For CSV files: reads header row for column names and counts rows.
    For other files: returns basic size info only.

    Returns a dict with 'type' and type-specific fields.  Never raises;
    returns a minimal dict on any parse error.
    """
    info: dict[str, Any] = {
        "exists": filepath.exists(),
        "size_bytes": 0,
    }
    if not filepath.exists():
        return info
    try:
        info["size_bytes"] = filepath.stat().st_size
    except OSError:
        pass

    suffix = filepath.suffix.lower()

    # ── Python files ──
    if suffix == ".py":
        info["lang"] = "python"
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            info["lines"] = source.count("\n") + 1
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError as exc:
            info["parse_error"] = str(exc)
            return info
        except Exception:
            return info

        imports: list[str] = []
        functions: list[str] = []
        classes: list[str] = []
        top_vars: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                sig_parts = [node.name + "("]
                args = node.args
                params: list[str] = []
                for a in args.args:
                    params.append(a.arg)
                sig_parts.append(", ".join(params))
                sig_parts.append(")")
                functions.append("".join(sig_parts))
            elif isinstance(node, ast.ClassDef):
                bases = [
                    (getattr(b, "id", None) or getattr(b, "attr", "?"))
                    for b in node.bases
                ]
                base_str = f"({', '.join(bases)})" if bases else ""
                methods = [
                    n.name for n in ast.iter_child_nodes(node)
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
                classes.append({
                    "name": f"{node.name}{base_str}",
                    "methods": methods,
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        top_vars.append(target.id)

        if imports:
            info["imports"] = imports
        if functions:
            info["functions"] = functions
        if classes:
            info["classes"] = classes
        if top_vars:
            info["top_level_vars"] = top_vars

        # Detect CLI entry point
        for node in ast.walk(tree):
            if (isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"):
                info["has_main_guard"] = True
                break

        # Detect fixtures and test functions (for test files)
        if filepath.name.startswith("test_") or filepath.name.endswith("_test.py"):
            fixtures: list[str] = []
            test_funcs: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith("test_"):
                        test_funcs.append(node.name)
                    for dec in node.decorator_list:
                        dec_name = ""
                        if isinstance(dec, ast.Attribute):
                            dec_name = dec.attr
                        elif isinstance(dec, ast.Name):
                            dec_name = dec.id
                        elif isinstance(dec, ast.Call):
                            func = dec.func
                            if isinstance(func, ast.Attribute):
                                dec_name = func.attr
                            elif isinstance(func, ast.Name):
                                dec_name = func.id
                        if dec_name == "fixture":
                            fixtures.append(node.name)
            if test_funcs:
                info["test_functions"] = test_funcs
            if fixtures:
                info["fixtures"] = fixtures

        return info

    # ── YAML files ──
    if suffix in (".yaml", ".yml"):
        info["lang"] = "yaml"
        try:
            import yaml
            source = filepath.read_text(encoding="utf-8", errors="replace")
            info["lines"] = source.count("\n") + 1
            data = yaml.safe_load(source)
            if isinstance(data, dict):
                info["top_level_keys"] = list(data.keys())
                # For pipeline configs, show transform step types
                if "transforms" in data and isinstance(data["transforms"], list):
                    step_types = []
                    for step in data["transforms"]:
                        if isinstance(step, dict) and "type" in step:
                            step_types.append(step["type"])
                    if step_types:
                        info["transform_steps"] = step_types
            elif isinstance(data, list):
                info["top_level_type"] = "list"
                info["num_items"] = len(data)
        except Exception:
            pass
        return info

    # ── CSV files ──
    if suffix == ".csv":
        info["lang"] = "csv"
        try:
            import csv as csv_mod
            with open(filepath, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv_mod.reader(f)
                header = next(reader, None)
                if header:
                    info["columns"] = header
                row_count = sum(1 for _ in reader)
                info["num_rows"] = row_count
        except Exception:
            pass
        return info

    # ── JSON files ──
    if suffix == ".json":
        info["lang"] = "json"
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            info["lines"] = source.count("\n") + 1
            data = json.loads(source)
            if isinstance(data, dict):
                info["top_level_keys"] = list(data.keys())
            elif isinstance(data, list):
                info["top_level_type"] = "list"
                info["num_items"] = len(data)
        except Exception:
            pass
        return info

    # ── Markdown / text files ──
    if suffix in (".md", ".txt", ".rst"):
        info["lang"] = "text"
        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            info["lines"] = source.count("\n") + 1
            # Extract headings for markdown
            if suffix == ".md":
                headings = [
                    line.strip()
                    for line in source.splitlines()
                    if line.strip().startswith("#")
                ]
                if headings:
                    info["headings"] = headings[:20]
        except Exception:
            pass
        return info

    # ── Fallback ──
    info["lang"] = suffix.lstrip(".") or "unknown"
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        info["lines"] = source.count("\n") + 1
    except Exception:
        pass
    return info


def _format_fingerprint_md(relpath: str, fp: dict[str, Any],
                           write_time: float | None = None) -> list[str]:
    """Format a file fingerprint as markdown lines for the context doc."""
    lines: list[str] = []
    size = fp.get("size_bytes", 0)
    line_count = fp.get("lines", "?")
    time_str = f", written at T={write_time:.1f}s" if write_time is not None else ""

    lines.append(f"### `{relpath}` ({size:,} bytes, {line_count} lines{time_str})")

    if fp.get("parse_error"):
        lines.append(f"- **Parse error**: {fp['parse_error']}")
        return lines

    lang = fp.get("lang", "")

    if lang == "python":
        if fp.get("imports"):
            lines.append(f"- **Imports**: {', '.join(fp['imports'])}")
        if fp.get("functions"):
            lines.append(f"- **Functions**: {', '.join(fp['functions'])}")
        if fp.get("classes"):
            for cls in fp["classes"]:
                methods_str = ", ".join(cls["methods"]) if cls["methods"] else "(none)"
                lines.append(f"- **Class** `{cls['name']}`: {methods_str}")
        if fp.get("top_level_vars"):
            lines.append(f"- **Top-level vars**: {', '.join(fp['top_level_vars'])}")
        if fp.get("has_main_guard"):
            lines.append("- **CLI entry**: `if __name__ == '__main__'`")
        if fp.get("test_functions"):
            lines.append(f"- **Test functions** ({len(fp['test_functions'])}): "
                         f"{', '.join(fp['test_functions'])}")
        if fp.get("fixtures"):
            lines.append(f"- **Fixtures**: {', '.join(fp['fixtures'])}")

    elif lang == "yaml":
        if fp.get("top_level_keys"):
            lines.append(f"- **Top-level keys**: {', '.join(fp['top_level_keys'])}")
        if fp.get("transform_steps"):
            lines.append(f"- **Transform steps**: {', '.join(fp['transform_steps'])}")

    elif lang == "csv":
        if fp.get("columns"):
            lines.append(f"- **Columns**: {', '.join(fp['columns'])}")
        if "num_rows" in fp:
            lines.append(f"- **Rows**: {fp['num_rows']}")

    elif lang == "json":
        if fp.get("top_level_keys"):
            lines.append(f"- **Top-level keys**: {', '.join(fp['top_level_keys'])}")
        elif fp.get("top_level_type") == "list":
            lines.append(f"- **Type**: list ({fp.get('num_items', '?')} items)")

    elif lang == "text":
        if fp.get("headings"):
            lines.append("- **Headings**: " + " / ".join(fp["headings"][:10]))

    lines.append("")
    return lines


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


def _parse_subagent_transcript(path: str) -> dict[str, Any]:
    """Extract token usage, model, and first-token latency from a subagent transcript JSONL.

    The transcript is a sequence of JSON lines. We look for:
    - 'user' lines  → timestamps (the first is the prompt sent to the subagent)
    - 'assistant' lines → message.model, message.usage (per-turn token counts),
                          and timestamp (first assistant timestamp gives TTFT)

    Returns a dict with:
        model:               str   – model used by the subagent
        input_tokens:        int   – total input tokens across all turns
        output_tokens:       int   – total output tokens across all turns
        cache_creation_tokens: int
        cache_read_tokens:   int
        num_turns:           int   – number of assistant turns
        first_token_latency_s: float – time from first user message to first assistant response
    """
    stats: dict[str, Any] = {}
    if not path:
        return stats

    transcript = Path(path)
    if not transcript.exists():
        return stats

    model: str | None = None
    total_input = 0
    total_output = 0
    total_cache_create = 0
    total_cache_read = 0
    num_turns = 0
    first_user_ts: str | None = None
    first_assistant_ts: str | None = None

    try:
        for line in transcript.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            msg_type = obj.get("type")

            if msg_type == "user" and first_user_ts is None:
                first_user_ts = obj.get("timestamp")

            elif msg_type == "assistant":
                msg = obj.get("message", {})
                if model is None:
                    model = msg.get("model")
                if first_assistant_ts is None:
                    first_assistant_ts = obj.get("timestamp")

                usage = msg.get("usage", {})
                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)
                total_cache_create += usage.get("cache_creation_input_tokens", 0)
                total_cache_read += usage.get("cache_read_input_tokens", 0)
                num_turns += 1
    except Exception as exc:
        log.warning(f"Failed to parse subagent transcript {path}: {exc}")
        return stats

    stats["model"] = model
    stats["input_tokens"] = total_input
    stats["output_tokens"] = total_output
    stats["cache_creation_tokens"] = total_cache_create
    stats["cache_read_tokens"] = total_cache_read
    stats["num_turns"] = num_turns

    # First-token latency: time between first user message and first assistant response
    if first_user_ts and first_assistant_ts:
        try:
            t_user = datetime.fromisoformat(first_user_ts.replace("Z", "+00:00"))
            t_asst = datetime.fromisoformat(first_assistant_ts.replace("Z", "+00:00"))
            stats["first_token_latency_s"] = round(
                (t_asst - t_user).total_seconds(), 3
            )
        except (ValueError, TypeError):
            pass

    return stats


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
        stats = _parse_subagent_transcript(transcript)
        timeline.record_subagent_stop(
            agent_id, agent_type, transcript, transcript_stats=stats
        )
        log.info(
            f"    [hook] SubagentStop: {agent_type} ({agent_id[:8]}) "
            f"model={stats.get('model', '?')} "
            f"tokens={stats.get('input_tokens', 0)}in/{stats.get('output_tokens', 0)}out "
            f"ttft={stats.get('first_token_latency_s', '?')}s"
        )
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
class TestConfig:
    """Model role assignments for a test run.

    Each test (test1, test2, test3) can be run with different model
    combinations.  The config_id is used as the directory name under
    the test folder, and configs.json provides the manifest.
    """

    config_id: str                          # e.g. "cfg_001"
    solver: str = "claude-opus-4-6"         # model for planning (high-quality)
    solver_provider: str = "anthropic"
    dispatcher: str = "gpt-oss:20b"         # model for speculative planning + execution
    dispatcher_provider: str = "ollama"
    executor: str = "gpt-oss:20b"           # model for executing the dispatcher plan
    executor_provider: str = "ollama"

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "solver": self.solver,
            "solver_provider": self.solver_provider,
            "dispatcher": self.dispatcher,
            "dispatcher_provider": self.dispatcher_provider,
            "executor": self.executor,
            "executor_provider": self.executor_provider,
        }


# Default config: Opus + gpt-oss (current test setup)
DEFAULT_CONFIG = TestConfig(config_id="cfg_001")


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
# §5b  DATA TYPES — plan generation result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PlanGenResult:
    """Result of a plan generation session."""

    model_name: str
    provider: str
    plan_text: str | None = None
    reasoning_text: str = ""
    thinking_text: str = ""
    plan_path: Path | None = None
    session_id: str | None = None
    duration_wall_s: float = 0.0
    duration_ms: int = 0
    total_cost_usd: float | None = None
    num_turns: int = 0
    usage: dict[str, Any] | None = None
    error: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "provider": self.provider,
            "plan_text": self.plan_text,
            "reasoning_text": self.reasoning_text,
            "thinking_text": self.thinking_text,
            "plan_path": str(self.plan_path) if self.plan_path else None,
            "session_id": self.session_id,
            "duration_wall_s": self.duration_wall_s,
            "duration_ms": self.duration_ms,
            "total_cost_usd": self.total_cost_usd,
            "num_turns": self.num_turns,
            "usage": self.usage,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════════
# §6  ClaudeCodeFramework — Agent SDK wrapper for plan generation & execution
# ═══════════════════════════════════════════════════════════════════════════

class ClaudeCodeFramework:
    """Wraps the Claude Agent SDK for plan generation and instrumented execution.

    Centralises option building, provider handling (Anthropic vs Ollama/LM Studio),
    and session lifecycle so that test functions only express orchestration logic.

    Usage::

        fw = ClaudeCodeFramework(ollama_base_url="http://localhost:11434")

        plan = await fw.generate_plan(
            model_name="gpt-oss:20b", provider="ollama",
            case_name="case_002", working_dir=workdir,
        )

        result = await fw.run_session(
            model_name="gpt-oss:20b", provider="ollama",
            working_dir=workdir, prompt="Execute the plan...",
            timeout_s=30, stop_event=some_event,
        )
    """

    def __init__(
        self,
        ollama_base_url: str = OLLAMA_BASE_URL,
        cases_dir: Path = CASES_DIR,
        disable_thinking: bool = True,
        temperature: float | None = None,
    ) -> None:
        self.ollama_base_url = ollama_base_url
        self.cases_dir = cases_dir
        self.disable_thinking = disable_thinking
        self.temperature = temperature

    # ── warmup ─────────────────────────────────────────────────────────

    async def warmup_model(
        self,
        model_name: str,
        provider: str,
        keep_alive: str = "10m",
    ) -> None:
        """Pre-load a local model into GPU/RAM so the first real call is warm.

        Uses Ollama's /api/generate with an empty prompt, which loads the
        model weights without producing any output.  No-op for cloud providers.
        """
        if not self._is_local(provider):
            return

        import urllib.request

        url = f"{self.ollama_base_url}/api/generate"
        payload = json.dumps({
            "model": model_name,
            "prompt": "",
            "keep_alive": keep_alive,
        }).encode()

        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        log.info(f"  Warming up {model_name} on Ollama (keep_alive={keep_alive})...")
        t0 = time.monotonic()

        # Run the blocking HTTP call in a thread so we don't stall the loop
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=120).read(),
            )
            dt = time.monotonic() - t0
            log.info(f"  {model_name} warm ({dt:.1f}s)")
        except Exception as e:
            dt = time.monotonic() - t0
            log.warning(f"  Warmup failed for {model_name} after {dt:.1f}s: {e}")

    # ── shared helpers ──────────────────────────────────────────────────

    def _is_local(self, provider: str) -> bool:
        return provider in ("ollama", "lm_studio")

    def _build_env(
        self,
        provider: str,
        model_name: str,
        api_base_url: str = "",
    ) -> dict[str, str]:
        """Build environment dict for the child CLI process.

        Unsets CLAUDECODE so the child doesn't think it's nested inside a
        parent Claude Code session (which would cause it to refuse to start).
        """
        base: dict[str, str] = {"CLAUDECODE": ""}
        if self._is_local(provider):
            base.update({
                "ANTHROPIC_BASE_URL": api_base_url or self.ollama_base_url,
                "ANTHROPIC_AUTH_TOKEN": "local",
                "ANTHROPIC_API_KEY": "local",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_name,
                "CLAUDE_CODE_SUBAGENT_MODEL": model_name,
            })
            if self.temperature is not None:
                base["OLLAMA_TEMPERATURE"] = str(self.temperature)
        return base

    def _build_options(
        self,
        model_name: str,
        provider: str,
        working_dir: Path,
        api_base_url: str = "",
        *,
        permission_mode: str = "bypassPermissions",
        hooks: dict[str, list[Any]] | None = None,
        stderr: Any | None = None,
    ) -> Any:
        """Build ClaudeAgentOptions with provider-appropriate config."""
        from claude_agent_sdk import ClaudeAgentOptions

        env = self._build_env(provider, model_name, api_base_url)

        opts_kwargs: dict[str, Any] = {
            "permission_mode": permission_mode,
            "model": model_name,
            "cwd": str(working_dir),
            "disallowed_tools": ["AskUserQuestion"],
            "env": env,
        }
        # Local models (e.g. gpt-oss via Ollama) produce thinking blocks
        # without the Anthropic-proprietary 'signature' field, causing
        # MessageParseError.  Disable thinking for local providers.
        # if self._is_local(provider) and self.disable_thinking:
        #     opts_kwargs["thinking"] = {"type": "disabled"}
        #     log.info(
        #         f"  [{model_name}] thinking disabled for local provider "
        #         f"({provider})"
        #     )

        if hooks is not None:
            opts_kwargs["hooks"] = hooks
        if stderr is not None:
            opts_kwargs["stderr"] = stderr

        return ClaudeAgentOptions(**opts_kwargs)

    # ── plan generation ─────────────────────────────────────────────────

    async def generate_plan(
        self,
        model_name: str,
        provider: str,
        case_name: str,
        working_dir: Path,
        plan_filename: str = "PLAN.md",
        api_base_url: str = "",
    ) -> PlanGenResult:
        """Generate a plan using the Agent SDK in planning mode.

        Runs the model with ``permission_mode="plan"`` so it cannot write
        files; the plan is extracted from the ``ExitPlanMode`` tool call
        (or a Write to ``/.claude/plans/``), then saved to
        *working_dir/plan_filename*.
        """
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
            query,
        )

        result = PlanGenResult(
            model_name=model_name,
            provider=provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # ── Load case prompt ──
        case_prompt = (self.cases_dir / case_name / "PROMPT.md").read_text()

        # ── Compose prompt ──
        prompt = (
            "You are in planning mode. Read the objective below and produce "
            "a detailed, step-by-step implementation plan. Do NOT execute "
            "anything — only plan.\n\n"
            "IMPORTANT: Do NOT ask clarifying questions. Do NOT use the "
            "AskUserQuestion tool. If any detail is ambiguous or missing, "
            "make a reasonable assumption, state it explicitly in your plan, "
            "and proceed. You must produce a complete plan in a single pass "
            "without waiting for human input.\n\n"
            f"## Objective\n\n{case_prompt}\n\n"
            f"## Working Directory\n\n"
            f"The working directory is: {working_dir}\n"
            f"Inspect it if needed for context materials."
        )

        options = self._build_options(
            model_name, provider, working_dir, api_base_url,
            permission_mode="plan",
        )

        # ── Run ──
        reasoning_text = ""
        thinking_text = ""
        plan_text: str | None = None

        t0 = time.monotonic()
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            reasoning_text += block.text + "\n"
                        elif isinstance(block, ThinkingBlock):
                            thinking_text += block.thinking + "\n"
                        elif isinstance(block, ToolUseBlock):
                            if block.name == "ExitPlanMode":
                                exit_plan = block.input.get("plan", "")
                                if exit_plan and (
                                    plan_text is None
                                    or len(exit_plan) > len(plan_text)
                                ):
                                    plan_text = exit_plan
                            elif (
                                block.name == "Write"
                                and "/.claude/plans/" in block.input.get(
                                    "file_path", ""
                                )
                            ):
                                write_content = block.input.get("content", "")
                                if write_content and (
                                    plan_text is None
                                    or len(write_content) > len(plan_text)
                                ):
                                    plan_text = write_content

                elif isinstance(message, ResultMessage):
                    result.session_id = message.session_id
                    result.duration_ms = message.duration_ms
                    result.total_cost_usd = message.total_cost_usd
                    result.num_turns = message.num_turns
                    result.usage = message.usage

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"

        result.duration_wall_s = time.monotonic() - t0
        result.reasoning_text = reasoning_text
        result.thinking_text = thinking_text

        # Fallback: use text output if ExitPlanMode was never called
        if plan_text is None and reasoning_text.strip():
            log.warning(
                f"  [{model_name}] ExitPlanMode not called — "
                f"falling back to text output as plan"
            )
            plan_text = reasoning_text.strip()

        result.plan_text = plan_text

        # Write plan to disk
        if plan_text:
            plan_path = working_dir / plan_filename
            plan_path.write_text(plan_text)
            result.plan_path = plan_path
            log.info(
                f"  [{model_name}] plan saved: {plan_path} "
                f"({len(plan_text)} chars, {result.duration_wall_s:.1f}s)"
            )
        else:
            log.warning(f"  [{model_name}] no plan text produced")

        return result

    # ── instrumented execution session ──────────────────────────────────

    async def run_session(
        self,
        model_name: str,
        provider: str,
        working_dir: Path,
        prompt: str,
        api_base_url: str = "",
        timeout_s: float | None = None,
        stop_event: asyncio.Event | None = None,
        run_label: str = "",
        case_name: str = "",
        role: Literal["solver", "speculative_dispatcher"] = "solver",
        artifact_prefix: str = "",
        save_context: bool = True,
        artifacts_dir: Path | None = None,
    ) -> ExecutionResult:
        """Start an instrumented Claude Code session via the Agent SDK.

        Uses ``ClaudeSDKClient`` for graceful session control:
          - ``interrupt()`` signals the CLI to stop the current response
          - ``disconnect()`` tears down the session and subprocess

        Args:
            stop_event: If provided, the session will be interrupted when
                the event is set (used by test2/test3 to stop speculative
                execution when the solver plan is ready).
            timeout_s: Hard timeout — session is interrupted then disconnected.

        Tracks:
          - Every tool call (via PreToolUse / PostToolUse hooks)
          - Subagent lifecycle (via SubagentStart / SubagentStop hooks)
          - Token usage (via TaskProgressMessage / TaskNotificationMessage)
          - LLM turns (via AssistantMessage counting)

        Returns an ExecutionResult.  Saves ``_timeline.json`` to *working_dir*.
        """
        from claude_agent_sdk import (
            ClaudeSDKClient,
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            ToolUseBlock,
        )
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

        # -- Build options with hooks --
        hooks = build_hooks(timeline)

        # The bundled CLI can close its stream before final hook responses
        # are delivered, producing "Stream closed" + minified JS stack traces.
        # This is a CLI-side shutdown race condition — harmless but noisy.
        # We filter those out while keeping real errors visible.
        stderr_lines: list[str] = []

        def _stderr_handler(line: str) -> None:
            stderr_lines.append(line)
            if "Stream closed" in line or "Error in hook callback" in line:
                return
            log.debug(f"  [{model_name}] stderr: {line.rstrip()}")

        options = self._build_options(
            model_name, provider, working_dir, api_base_url,
            hooks=hooks, stderr=_stderr_handler,
        )

        # Collect turn data from AssistantMessages for post-session correlation
        turn_counter = 0
        turn_data: list[dict[str, Any]] = []

        client = ClaudeSDKClient(options=options)
        timed_out = False

        async def _timeout_watchdog(timeout: float) -> None:
            """Wait for timeout, then interrupt → grace period → disconnect."""
            nonlocal timed_out
            await asyncio.sleep(timeout)
            timed_out = True
            log.info(
                f"  [{model_name}] timeout reached ({timeout:.0f}s) "
                f"— interrupting session"
            )
            try:
                await client.interrupt()
            except Exception:
                pass
            await asyncio.sleep(5)
            log.info(f"  [{model_name}] grace period elapsed — disconnecting")
            try:
                await client.disconnect()
            except Exception:
                pass

        # ── Stop-event watchdog (external signal to stop the session) ──
        externally_stopped = False

        async def _stop_event_watchdog() -> None:
            """Wait for the external stop event, then interrupt → disconnect."""
            nonlocal externally_stopped
            assert stop_event is not None
            await stop_event.wait()
            externally_stopped = True
            log.info(
                f"  [{model_name}] stop_event set — interrupting session"
            )
            try:
                await client.interrupt()
            except Exception:
                pass
            await asyncio.sleep(5)
            log.info(f"  [{model_name}] grace period elapsed — disconnecting")
            try:
                await client.disconnect()
            except Exception:
                pass

        t0 = time.monotonic()
        watchdog_task: asyncio.Task[None] | None = None
        stop_task: asyncio.Task[None] | None = None

        try:
            await client.connect()
            await client.query(prompt)

            if timeout_s is not None:
                watchdog_task = asyncio.create_task(
                    _timeout_watchdog(timeout_s)
                )
            if stop_event is not None:
                stop_task = asyncio.create_task(_stop_event_watchdog())

            async for message in client.receive_messages():
                # ── AssistantMessage: one LLM turn ──
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
                    break

        except (Exception, asyncio.CancelledError) as e:
            if not timed_out and not externally_stopped:
                result.error = f"{type(e).__name__}: {e}"
                timeline.record("session_error", error=result.error)
        finally:
            for task in (watchdog_task, stop_task):
                if task is not None and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            try:
                await client.disconnect()
            except Exception:
                pass

        if timed_out:
            result.timed_out = True
            timeline.record("session_timeout", timeout_s=timeout_s)
            log.info(f"  [{model_name}] timed out after {timeout_s:.0f}s")

        if externally_stopped:
            result.cancelled = True
            timeline.record("session_stopped", reason="stop_event")
            log.info(
                f"  [{model_name}] externally stopped via stop_event"
            )

        # -- Post-session: correlate turns with hook events --
        timeline.correlate_turns(turn_data)

        result.duration_wall_s = time.monotonic() - t0
        result.total_tokens = timeline.total_tokens
        result.timeline_summary = timeline.summary()

        # Save timeline
        _adir = Path(artifacts_dir) if artifacts_dir else Path(working_dir)
        timeline_path = _adir / f"{artifact_prefix}timeline.json"
        timeline_data = {
            "model": model_name,
            "provider": provider,
            "summary": timeline.summary(),
            "events": timeline.to_list(),
        }
        timeline_path.write_text(json.dumps(timeline_data, indent=2))
        log.info(
            f"  [{model_name}] timeline saved: "
            f"{len(timeline.to_list())} events, "
            f"{timeline.total_tokens:,} tokens"
        )

        # Save portable context document (skip for terminal phases like merge)
        if save_context:
            context_filename = (
                f"{artifact_prefix}solver_context.md"
                if role == "solver"
                else f"{artifact_prefix}spec_dsp_context.md"
            )
            ctx_t0 = time.monotonic()
            context_md = timeline.build_context(
                role=role,
                model_name=model_name,
                working_dir=Path(working_dir),
                timeout_s=timeout_s,
                session_id=result.session_id,
            )
            context_path = _adir / context_filename
            context_path.write_text(context_md)
            ctx_ms = (time.monotonic() - ctx_t0) * 1000
            log.info(
                f"  [{model_name}] context saved: "
                f"{context_path.name} ({ctx_ms:.1f}ms)"
            )

        # Save full stderr for debugging (including filtered shutdown noise)
        stderr_log = _adir / f"{artifact_prefix}stderr.log"
        stderr_log.write_text("\n".join(stderr_lines))

        return result


# ═══════════════════════════════════════════════════════════════════════════
# §7  TEST 1 — gpt-oss plan + execute + stop
# ═══════════════════════════════════════════════════════════════════════════

async def test1_baseline(
    case_name: str,
    plan_path: Path | None = None,
    timeout_s: float = 30.0,
    config: TestConfig | None = None,
) -> None:
    """Test 1: gpt-oss generates a plan then executes it; execution is
    stopped after *timeout_s* seconds.  The solver context is saved so
    that a follow-up agent can merge the partial work with its own plan.

    Flow:
      Phase 1: gpt-oss generates an implementation plan.
      Phase 2: gpt-oss starts executing its plan.
      Phase 3: After timeout_s seconds, execution is interrupted.
      Phase 4: Solver context + timeline + snapshot are saved.
    """
    if config is None:
        config = DEFAULT_CONFIG

    fw = ClaudeCodeFramework()
    dirs = prepare_test_dirs(
        case_name, "test1", config,
        ["phase1_planning", "phase2_execution"],
    )
    workdir = dirs["workdir"]
    run_label = f"{case_name}/test1/{config.config_id}"

    log.info(f"=== Test 1: gpt-oss plan -> execute -> stop after {timeout_s}s ===")
    log.info(f"  Case: {case_name}")
    log.info(f"  Config: {config.config_id}")
    log.info(f"  Working dir: {workdir}")

    # ── Phase 1: Generate plan with dispatcher ──
    log.info("  Phase 1: generating plan with dispatcher...")

    plan_result = await fw.generate_plan(
        model_name=config.dispatcher,
        provider=config.dispatcher_provider,
        case_name=case_name,
        working_dir=workdir,
        plan_filename="PLAN.md",
    )

    if plan_result.error:
        log.error(f"  Plan generation failed: {plan_result.error}")
        print(f"\nTest 1 FAILED: plan generation error -- {plan_result.error}")
        return

    log.info(
        f"  Plan ready ({plan_result.duration_wall_s:.1f}s, "
        f"{len(plan_result.plan_text or '')} chars)"
    )

    # Save plan and metadata to phase1_planning/
    phase1 = dirs["phase1_planning"]
    shutil.copy2(workdir / "PLAN.md", phase1 / "PLAN.md")
    plan_gen_path = phase1 / "plan_gen.json"
    plan_gen_path.write_text(json.dumps(plan_result.to_dict(), indent=2))

    # ── Phase 2: Execute the plan (time-boxed) ──
    log.info(f"  Phase 2: executing plan (will stop after {timeout_s}s)...")

    exec_prompt = (
        f"Read the implementation plan in {workdir}/PLAN.md and execute it. "
        "Implement all files described in the plan in this directory. "
        "Use subagents for independent implementation tasks."
    )

    result = await fw.run_session(
        model_name=config.executor,
        provider=config.executor_provider,
        working_dir=workdir,
        prompt=exec_prompt,
        timeout_s=timeout_s,
        run_label=run_label,
        case_name=case_name,
        role="solver",
        artifacts_dir=dirs["phase2_execution"],
    )

    # ── Save execution artifacts to phase2_execution/ ──
    phase2 = dirs["phase2_execution"]
    result_path = phase2 / "result.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2))

    snap = snapshot_workdir(workdir)
    snap_path = phase2 / "snapshot.json"
    snap_path.write_text(json.dumps(snap.to_dict(), indent=2))

    _print_test1_stop_results(plan_result, result, snap, dirs["root"], timeout_s)


def _print_test1_stop_results(
    plan_result: PlanGenResult,
    exec_result: ExecutionResult,
    snap: Snapshot,
    workdir: Path,
    timeout_s: float,
) -> None:
    """Print results of the test1 gpt-oss plan+execute+stop test."""
    ts = exec_result.timeline_summary

    print(f"\n{'='*60}")
    print(f"Test 1: gpt-oss plan -> execute -> stop ({timeout_s}s cutoff)")
    print(f"{'='*60}")

    print(f"\n  --- Plan Generation (gpt-oss) ---")
    print(f"  Planning time:    {plan_result.duration_wall_s:.1f}s")
    print(f"  Plan size:        {len(plan_result.plan_text or '')} chars")
    print(f"  Cost:             ${plan_result.total_cost_usd or 0:.4f}")

    print(f"\n  --- Execution (gpt-oss, stopped) ---")
    print(f"  Wall time:        {exec_result.duration_wall_s:.1f}s")
    print(f"  Timed out:        {exec_result.timed_out}")
    print(f"  Cost:             ${exec_result.total_cost_usd or 0:.4f}")
    print(f"  Turns:            {exec_result.num_turns}")
    print(f"  Total tokens:     {exec_result.total_tokens:,}")
    print(f"  Tool uses:        {ts.get('total_tool_uses', 0)}")
    print(f"  Subagents:        {ts.get('total_subagents_spawned', 0)}")

    print(f"\n  --- Output ---")
    print(f"  Files created:    {snap.total_files}")
    print(f"  Lines of code:    {snap.total_lines}")
    print(f"  Tests passed:     {snap.pytest_passed}")
    print(f"  Tests failed:     {snap.pytest_failed}")

    if exec_result.error:
        print(f"  Exec error:       {exec_result.error}")

    print(f"\n  --- Artifacts ---")
    print(f"  Run dir:          {workdir}")
    print(f"    workdir/                 (generated code)")
    print(f"    phase1_planning/         (PLAN.md, plan_gen.json)")
    print(f"    phase2_execution/        (result.json, timeline.json, snapshot.json)")


# ═══════════════════════════════════════════════════════════════════════════
# §8  TEST 2 — Speculative Dispatch (plan generation + execution)
# ═══════════════════════════════════════════════════════════════════════════

def prepare_bare_workdir(run_label: str, case_name: str) -> Path:
    """Create a fresh working directory without a pre-existing plan.

    Copies case WorkingDir contents (if any) but no plan — the plan will
    be generated by the agent during the test.
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

    # Initialise a git repo so Claude Code can use worktree isolation
    # for subagents (Agent tool with isolation="worktree" requires git).
    subprocess.run(
        ["git", "init", "-q"],
        cwd=str(workdir),
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(workdir), "add", "-A"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(workdir), "commit", "-q",
         "--allow-empty", "-m", "init workdir"],
        check=True,
    )

    log.info(f"Prepared bare working directory (git init): {workdir}")
    return workdir


def prepare_test_dirs(
    case_name: str,
    test_name: str,
    config: TestConfig,
    phases: list[str],
) -> dict[str, Path]:
    """Create the directory structure for a test run.

    Layout::

        RUNS_DIR / case_name / test_name / config.config_id /
            workdir/            ← agents execute here (generated code)
            phase1_planning/    ← plans + plan-gen metadata
            phase2_execution/   ← execution metadata
            phase3_merge/       ← merge metadata (test3 only)

    Also creates/updates ``configs.json`` at the test level so that all
    config→model mappings are discoverable.

    Returns a dict with keys: "root", "workdir", and one key per phase name.
    """
    test_dir = RUNS_DIR / case_name / test_name
    test_dir.mkdir(parents=True, exist_ok=True)

    config_dir = test_dir / config.config_id
    if config_dir.exists():
        shutil.rmtree(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create workdir (populated from case WorkingDir + git init)
    workdir = config_dir / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)

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

    subprocess.run(["git", "init", "-q"], cwd=str(workdir), check=True)
    subprocess.run(["git", "-C", str(workdir), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(workdir), "commit", "-q",
         "--allow-empty", "-m", "init workdir"],
        check=True,
    )

    # Create phase directories
    dirs: dict[str, Path] = {"root": config_dir, "workdir": workdir}
    for phase in phases:
        phase_dir = config_dir / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        dirs[phase] = phase_dir

    # Update configs.json manifest
    configs_path = test_dir / "configs.json"
    if configs_path.exists():
        existing = json.loads(configs_path.read_text())
    else:
        existing = {}
    existing[config.config_id] = config.to_dict()
    configs_path.write_text(json.dumps(existing, indent=2))

    log.info(
        f"Prepared test dirs: {config_dir} "
        f"(phases: {', '.join(phases)})"
    )
    return dirs


async def test2_parallel(
    case_name: str,
    config: TestConfig | None = None,
) -> None:
    """Test 2: Speculative dispatch — dispatcher generates plan + executes
    while solver generates plan.  When solver finishes planning, dispatcher
    execution is stopped and its context is saved.

    Flow:
      Phase 1: Both agents generate plans concurrently.
      Phase 2: Dispatcher finishes first → starts executing its plan.
      Phase 3: Solver finishes planning → stop dispatcher execution.
      Phase 4: Save all artifacts.
    """
    if config is None:
        config = DEFAULT_CONFIG

    fw = ClaudeCodeFramework()
    dirs = prepare_test_dirs(
        case_name, "test2", config,
        ["phase1_planning", "phase2_execution"],
    )
    workdir = dirs["workdir"]
    run_label = f"{case_name}/test2/{config.config_id}"

    log.info("=== Test 2: Speculative Dispatch (plan + execute) ===")
    log.info(f"  Case: {case_name}")
    log.info(f"  Config: {config.config_id}")
    log.info(f"  Working dir: {workdir}")

    # ── Phase 1: Parallel plan generation ──
    log.info("  Phase 1: generating plans concurrently...")

    dispatcher_plan_task = asyncio.create_task(
        fw.generate_plan(
            model_name=config.dispatcher,
            provider=config.dispatcher_provider,
            case_name=case_name,
            working_dir=workdir,
            plan_filename="spec_dsp_PLAN.md",
        )
    )

    solver_plan_task = asyncio.create_task(
        fw.generate_plan(
            model_name=config.solver,
            provider=config.solver_provider,
            case_name=case_name,
            working_dir=workdir,
            plan_filename="solver_PLAN.md",
        )
    )

    # Wait for dispatcher to finish planning first (it's faster)
    done, pending = await asyncio.wait(
        [dispatcher_plan_task, solver_plan_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Identify which finished first
    if dispatcher_plan_task in done:
        dispatcher_plan_result = dispatcher_plan_task.result()
        log.info(
            f"  Dispatcher plan ready "
            f"({dispatcher_plan_result.duration_wall_s:.1f}s)"
            f" — solver still planning"
        )
    else:
        log.info("  Solver finished planning first (unexpected) — waiting for dispatcher")
        dispatcher_plan_result = await dispatcher_plan_task

    if dispatcher_plan_result.error:
        log.error(f"  Dispatcher plan generation failed: {dispatcher_plan_result.error}")
        solver_plan_result = await solver_plan_task
        _print_plan_gen_summary(dispatcher_plan_result, solver_plan_result,
                                dirs["root"], dirs["root"],
                                test_name="Test 2")
        return

    # ── Phase 2: Dispatcher starts executing while solver still plans ──
    log.info("  Phase 2: dispatcher starting speculative execution...")

    stop_event = asyncio.Event()

    exec_prompt = (
        f"Read the implementation plan in {workdir}/spec_dsp_PLAN.md "
        f"and execute it. Implement all files described in the plan in this "
        f"directory. Use subagents for independent implementation tasks."
    )

    dispatcher_exec_task = asyncio.create_task(
        fw.run_session(
            model_name=config.executor,
            provider=config.executor_provider,
            working_dir=workdir,
            prompt=exec_prompt,
            stop_event=stop_event,
            run_label=run_label,
            case_name=case_name,
            role="speculative_dispatcher",
            artifacts_dir=dirs["phase2_execution"],
        )
    )

    # ── Phase 3: Wait for solver to finish planning, then stop dispatcher ──
    solver_plan_result = await solver_plan_task
    log.info(
        f"  Solver plan ready ({solver_plan_result.duration_wall_s:.1f}s)"
        f" — stopping speculative dispatcher"
    )

    stop_event.set()
    dispatcher_exec_result = await dispatcher_exec_task

    log.info(
        f"  Dispatcher execution stopped after "
        f"{dispatcher_exec_result.duration_wall_s:.1f}s"
    )

    # ── Phase 4: Save artifacts ──
    phase1 = dirs["phase1_planning"]
    phase2 = dirs["phase2_execution"]

    # Save execution result
    result_path = phase2 / "result.json"
    result_path.write_text(json.dumps(dispatcher_exec_result.to_dict(), indent=2))

    # Take snapshot of execution output
    snap = snapshot_workdir(workdir)
    snap_path = phase2 / "snapshot.json"
    snap_path.write_text(json.dumps(snap.to_dict(), indent=2))

    # Save plan generation metadata to phase1_planning/
    shutil.copy2(workdir / "spec_dsp_PLAN.md", phase1 / "spec_dsp_PLAN.md")
    shutil.copy2(workdir / "solver_PLAN.md", phase1 / "solver_PLAN.md")

    dsp_plan_json = phase1 / "spec_dsp_plan_gen.json"
    dsp_plan_json.write_text(json.dumps(dispatcher_plan_result.to_dict(), indent=2))
    log.info(f"  Dispatcher plan metadata saved: {dsp_plan_json}")

    solver_plan_json = phase1 / "solver_plan_gen.json"
    solver_plan_json.write_text(json.dumps(solver_plan_result.to_dict(), indent=2))
    log.info(f"  Solver plan metadata saved: {solver_plan_json}")

    # Print results
    _print_speculative_results(
        dispatcher_plan_result, solver_plan_result,
        dispatcher_exec_result, snap,
        dirs["root"], dirs["root"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# §8b  TEST 3 — Speculative dispatch + merge phase
# ═══════════════════════════════════════════════════════════════════════════

async def test3_merge(
    case_name: str,
    config: TestConfig | None = None,
) -> None:
    """Test 3: Speculative dispatch with merge phase.

    Phases 1–3 are identical to test2:
      Phase 1: Both agents generate plans concurrently.
      Phase 2: Dispatcher finishes first → starts executing its plan.
      Phase 3: Solver finishes planning → stop dispatcher execution.

    Then the merge phase:
      Phase 4: Save pre-merge artifacts (dispatcher execution state).
      Phase 5: Solver takes over workdir, evaluates dispatcher's
               partial work, and decides to reuse / merge / discard.
      Phase 6: Save merge artifacts and print results.
    """
    if config is None:
        config = DEFAULT_CONFIG

    fw = ClaudeCodeFramework()
    dirs = prepare_test_dirs(
        case_name, "test3", config,
        ["phase1_planning", "phase2_execution", "phase3_merge"],
    )
    workdir = dirs["workdir"]
    run_label = f"{case_name}/test3/{config.config_id}"

    log.info("=== Test 3: Speculative Dispatch + Merge ===")
    log.info(f"  Case: {case_name}")
    log.info(f"  Config: {config.config_id}")
    log.info(f"  Working dir: {workdir}")

    # ── Warmup: pre-load local models so timing reflects pure inference ──
    # Warmup dispatcher (used in Phase 1 planning) first, then kick off
    # executor warmup concurrently with Phase 1 so it's ready for Phase 2.
    await fw.warmup_model(config.dispatcher, config.dispatcher_provider)

    # ── Phase 1: Parallel plan generation (same as test2) ──
    log.info("  Phase 1: generating plans concurrently...")

    dispatcher_plan_task = asyncio.create_task(
        fw.generate_plan(
            model_name=config.dispatcher,
            provider=config.dispatcher_provider,
            case_name=case_name,
            working_dir=workdir,
            plan_filename="spec_dsp_PLAN.md",
        )
    )

    solver_plan_task = asyncio.create_task(
        fw.generate_plan(
            model_name=config.solver,
            provider=config.solver_provider,
            case_name=case_name,
            working_dir=workdir,
            plan_filename="solver_PLAN.md",
        )
    )

    done, pending = await asyncio.wait(
        [dispatcher_plan_task, solver_plan_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if dispatcher_plan_task in done:
        dispatcher_plan_result = dispatcher_plan_task.result()
        log.info(
            f"  Dispatcher plan ready "
            f"({dispatcher_plan_result.duration_wall_s:.1f}s)"
            f" — solver still planning"
        )
    else:
        log.info("  Solver finished planning first (unexpected) — waiting for dispatcher")
        dispatcher_plan_result = await dispatcher_plan_task

    if dispatcher_plan_result.error:
        log.error(f"  Dispatcher plan generation failed: {dispatcher_plan_result.error}")
        solver_plan_result = await solver_plan_task
        _print_plan_gen_summary(dispatcher_plan_result, solver_plan_result,
                                dirs["root"], dirs["root"],
                                test_name="Test 3")
        return

    # Warmup executor model before Phase 2 if it differs from dispatcher.
    # Done AFTER Phase 1 planning completes — not concurrently — because
    # Ollama evicts the running model when GPU memory is insufficient for
    # two models, which would slow down Phase 1 inference.
    if (config.executor != config.dispatcher
            or config.executor_provider != config.dispatcher_provider):
        await fw.warmup_model(config.executor, config.executor_provider)

    # ── Phase 2: Dispatcher starts executing (same as test2) ──
    log.info("  Phase 2: dispatcher starting speculative execution...")

    stop_event = asyncio.Event()

    exec_prompt = (
        f"Read the implementation plan in {workdir}/spec_dsp_PLAN.md "
        f"and execute it. Implement all files described in the plan in this "
        f"directory. Use subagents for independent implementation tasks."
    )

    dispatcher_exec_task = asyncio.create_task(
        fw.run_session(
            model_name=config.executor,
            provider=config.executor_provider,
            working_dir=workdir,
            prompt=exec_prompt,
            stop_event=stop_event,
            run_label=run_label,
            case_name=case_name,
            role="speculative_dispatcher",
            artifacts_dir=dirs["phase2_execution"],
        )
    )

    # ── Phase 3: Wait for solver plan, then stop dispatcher (same as test2) ──
    solver_plan_result = await solver_plan_task
    log.info(
        f"  Solver plan ready ({solver_plan_result.duration_wall_s:.1f}s)"
        f" — stopping speculative dispatcher"
    )

    stop_event.set()
    dispatcher_exec_result = await dispatcher_exec_task

    log.info(
        f"  Dispatcher execution stopped after "
        f"{dispatcher_exec_result.duration_wall_s:.1f}s"
    )

    # ── Phase 4: Save pre-merge artifacts ──
    log.info("  Phase 4: saving pre-merge artifacts...")

    phase1 = dirs["phase1_planning"]
    phase2 = dirs["phase2_execution"]
    phase3 = dirs["phase3_merge"]

    # Save execution result to phase2
    result_path = phase2 / "result.json"
    result_path.write_text(json.dumps(dispatcher_exec_result.to_dict(), indent=2))

    # NOTE: snapshot commented out to measure pipeline without pytest overhead.
    # pre_merge_snap = snapshot_workdir(workdir)
    # snap_path = phase2 / "snapshot.json"
    # snap_path.write_text(json.dumps(pre_merge_snap.to_dict(), indent=2))
    pre_merge_snap = None

    # Save plans and plan metadata to phase1_planning/
    for plan_file in ("spec_dsp_PLAN.md", "solver_PLAN.md"):
        src = workdir / plan_file
        if src.exists():
            shutil.copy2(src, phase1 / plan_file)

    dsp_plan_json = phase1 / "spec_dsp_plan_gen.json"
    dsp_plan_json.write_text(json.dumps(dispatcher_plan_result.to_dict(), indent=2))

    solver_plan_json = phase1 / "solver_plan_gen.json"
    solver_plan_json.write_text(json.dumps(solver_plan_result.to_dict(), indent=2))

    # ── Phase 5: Merge — Solver takes over workdir ──
    log.info("  Phase 5: Solver merge phase — evaluating dispatcher work...")

    merge_prompt = (
        f"You are a solver using Claude Opus that generated the {workdir}/solver_PLAN.md "
        "for a task. Besides that, another agent the gpt-oss "
        "(speculative_dispatcher) has already executed some work "
        "during the period you were planning. You can find its progress "
        f"and what it accomplished in {workdir}/spec_dsp_context.md.\n\n"
        "IMPORTANT — efficiency rules:\n"
        "- Read solver_PLAN.md and spec_dsp_context.md first.\n"
        "- To inspect gpt-oss source files, use a SINGLE Bash call to cat "
        "all files at once (e.g. `cat file1.py file2.py ...`). Do NOT read "
        "files one at a time with the Read tool.\n"
        "- Do NOT execute, test, or modify any code. Only produce a plan.\n\n"
        "With all of this knowledge:\n"
        "1. Read solver_PLAN.md and spec_dsp_context.md\n"
        "2. Inspect the gpt-oss source files in a single Bash call\n"
        "3. Evaluate the quality and correctness of the work gpt-oss has done\n"
        "4. Decide:\n"
        "   - If all gpt-oss work is correct and complete: output 'ALL DONE', "
        "no further work needed.\n"
        "   - If gpt-oss work is partially correct: merge the reusable parts "
        "with your plan to produce a final merged plan.\n"
        "   - If all gpt-oss work is wrong: the final plan is your "
        "solver_PLAN.md as-is. Discard everything the gpt-oss generated.\n\n"
        "Write your final merged plan to MERGED_PLAN.md."
    )

    merge_result = await fw.run_session(
        model_name=config.solver,
        provider=config.solver_provider,
        working_dir=workdir,
        prompt=merge_prompt,
        run_label=f"{case_name}/test3/{config.config_id}/merge",
        case_name=case_name,
        role="solver",
        save_context=False,
        artifacts_dir=phase3,
    )

    log.info(
        f"  Merge phase completed in {merge_result.duration_wall_s:.1f}s"
    )

    # ── Phase 6: Save merge artifacts and print results ──
    log.info("  Phase 6: saving merge artifacts...")

    merge_result_path = phase3 / "result.json"
    merge_result_path.write_text(
        json.dumps(merge_result.to_dict(), indent=2)
    )

    # Copy MERGED_PLAN.md from workdir to phase3 if it was created there
    merged_plan_src = workdir / "MERGED_PLAN.md"
    if merged_plan_src.exists():
        shutil.copy2(merged_plan_src, phase3 / "MERGED_PLAN.md")

    # NOTE: snapshot commented out to measure pipeline without pytest overhead.
    # merge_snap = snapshot_workdir(workdir)
    # merge_snap_path = phase3 / "snapshot.json"
    # merge_snap_path.write_text(json.dumps(merge_snap.to_dict(), indent=2))
    merge_snap = None

    _print_merge_results(
        dispatcher_plan_result, solver_plan_result,
        dispatcher_exec_result, pre_merge_snap,
        merge_result, merge_snap,
        dirs["root"], dirs["root"],
    )


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


def _print_plan_gen_summary(
    gptoss_plan: PlanGenResult,
    opus_plan: PlanGenResult,
    spec_dsp_dir: Path,
    solver_dir: Path,
    test_name: str = "Test 2",
) -> None:
    """Print summary when a test ends early (plan generation failure)."""
    print(f"\n{'='*60}")
    print(f"{test_name}: Plan Generation Only (execution skipped)")
    print(f"{'='*60}")
    print(f"  Dispatcher plan:  {'ERROR: ' + (gptoss_plan.error or '?') if gptoss_plan.error else f'{gptoss_plan.duration_wall_s:.1f}s'}")
    print(f"  Solver plan:      {'ERROR: ' + (opus_plan.error or '?') if opus_plan.error else f'{opus_plan.duration_wall_s:.1f}s'}")
    print(f"\n  Run dir: {spec_dsp_dir}")


def _print_speculative_results(
    gptoss_plan: PlanGenResult,
    opus_plan: PlanGenResult,
    gptoss_exec: ExecutionResult,
    spec_dsp_snap: Snapshot,
    spec_dsp_dir: Path,
    solver_dir: Path,
) -> None:
    """Print results of the speculative dispatch test."""
    ts = gptoss_exec.timeline_summary

    print(f"\n{'='*60}")
    print("Test 2: Speculative Dispatch Results")
    print(f"{'='*60}")

    # Helper to extract token counts from usage dict
    def _tok(usage: dict[str, Any] | None, key: str) -> int:
        if not usage or not isinstance(usage, dict):
            return 0
        return usage.get(key, 0)

    gu = gptoss_plan.usage
    ou = opus_plan.usage

    print(f"\n  --- Plan Generation ---")
    print(f"  {'Metric':<30} {'gpt-oss':>15} {'Opus':>15}")
    print(f"  {'-'*60}")
    print(f"  {'Planning time (s)':<30} {gptoss_plan.duration_wall_s:>15.1f} {opus_plan.duration_wall_s:>15.1f}")
    print(f"  {'API time (ms)':<30} {gptoss_plan.duration_ms:>15} {opus_plan.duration_ms:>15}")
    print(f"  {'Cost ($)':<30} {gptoss_plan.total_cost_usd or 0:>15.4f} {opus_plan.total_cost_usd or 0:>15.4f}")
    print(f"  {'Turns':<30} {gptoss_plan.num_turns:>15} {opus_plan.num_turns:>15}")
    print(f"  {'Input tokens':<30} {_tok(gu, 'input_tokens'):>15,} {_tok(ou, 'input_tokens'):>15,}")
    print(f"  {'Output tokens':<30} {_tok(gu, 'output_tokens'):>15,} {_tok(ou, 'output_tokens'):>15,}")
    print(f"  {'Cache create tokens':<30} {_tok(gu, 'cache_creation_input_tokens'):>15,} {_tok(ou, 'cache_creation_input_tokens'):>15,}")
    print(f"  {'Cache read tokens':<30} {_tok(gu, 'cache_read_input_tokens'):>15,} {_tok(ou, 'cache_read_input_tokens'):>15,}")
    print(f"  {'Plan size (chars)':<30} {len(gptoss_plan.plan_text or ''):>15} {len(opus_plan.plan_text or ''):>15}")

    spec_exec_time = gptoss_exec.duration_wall_s
    opus_plan_time = opus_plan.duration_wall_s
    gptoss_plan_time = gptoss_plan.duration_wall_s
    # How much execution time gpt-oss got = Opus plan time - gpt-oss plan time
    exec_window = max(0, opus_plan_time - gptoss_plan_time)

    print(f"\n  --- Speculative Execution (gpt-oss) ---")
    print(f"  Execution window:   {exec_window:.1f}s (Opus plan time - gpt-oss plan time)")
    print(f"  Actual exec time:   {spec_exec_time:.1f}s")
    print(f"  Cost:               ${gptoss_exec.total_cost_usd or 0:.4f}")
    print(f"  Turns:              {gptoss_exec.num_turns}")
    print(f"  Total tokens:       {gptoss_exec.total_tokens:,}")
    print(f"  Tool uses:          {ts.get('total_tool_uses', 0)}")
    print(f"  Subagents:          {ts.get('total_subagents_spawned', 0)}")
    print(f"  Cancelled:          {gptoss_exec.cancelled}")

    print(f"\n  --- Output (speculative execution) ---")
    print(f"  Files created:      {spec_dsp_snap.total_files}")
    print(f"  Lines of code:      {spec_dsp_snap.total_lines}")
    print(f"  Tests passed:       {spec_dsp_snap.pytest_passed}")
    print(f"  Tests failed:       {spec_dsp_snap.pytest_failed}")

    if gptoss_exec.error:
        print(f"  Exec error:         {gptoss_exec.error}")
    if opus_plan.error:
        print(f"  Opus plan error:    {opus_plan.error}")

    print(f"\n  --- Artifacts ---")
    print(f"  Run dir:         {spec_dsp_dir}")
    print(f"    workdir/                 (generated code)")
    print(f"    phase1_planning/         (plans, plan_gen.json)")
    print(f"    phase2_execution/        (result.json, timeline.json, snapshot.json)")


def _print_merge_results(
    gptoss_plan: PlanGenResult,
    opus_plan: PlanGenResult,
    gptoss_exec: ExecutionResult,
    pre_merge_snap: Snapshot | None,
    merge_exec: ExecutionResult,
    merge_snap: Snapshot | None,
    spec_dsp_dir: Path,
    solver_dir: Path,
) -> None:
    """Print results of the speculative dispatch + merge test."""

    def _tok(usage: dict[str, Any] | None, key: str) -> int:
        if not usage or not isinstance(usage, dict):
            return 0
        return usage.get(key, 0)

    gu = gptoss_plan.usage
    ou = opus_plan.usage
    gts = gptoss_exec.timeline_summary
    mts = merge_exec.timeline_summary

    print(f"\n{'='*60}")
    print("Test 3: Speculative Dispatch + Merge Results")
    print(f"{'='*60}")

    # ── Plan generation ──
    print(f"\n  --- Plan Generation ---")
    print(f"  {'Metric':<30} {'gpt-oss':>15} {'Opus':>15}")
    print(f"  {'-'*60}")
    print(f"  {'Planning time (s)':<30} {gptoss_plan.duration_wall_s:>15.1f} {opus_plan.duration_wall_s:>15.1f}")
    print(f"  {'API time (ms)':<30} {gptoss_plan.duration_ms:>15} {opus_plan.duration_ms:>15}")
    print(f"  {'Cost ($)':<30} {gptoss_plan.total_cost_usd or 0:>15.4f} {opus_plan.total_cost_usd or 0:>15.4f}")
    print(f"  {'Turns':<30} {gptoss_plan.num_turns:>15} {opus_plan.num_turns:>15}")
    print(f"  {'Input tokens':<30} {_tok(gu, 'input_tokens'):>15,} {_tok(ou, 'input_tokens'):>15,}")
    print(f"  {'Output tokens':<30} {_tok(gu, 'output_tokens'):>15,} {_tok(ou, 'output_tokens'):>15,}")
    print(f"  {'Plan size (chars)':<30} {len(gptoss_plan.plan_text or ''):>15} {len(opus_plan.plan_text or ''):>15}")

    # ── Speculative execution (pre-merge) ──
    spec_exec_time = gptoss_exec.duration_wall_s
    opus_plan_time = opus_plan.duration_wall_s
    gptoss_plan_time = gptoss_plan.duration_wall_s
    exec_window = max(0, opus_plan_time - gptoss_plan_time)

    print(f"\n  --- Speculative Execution (gpt-oss, pre-merge) ---")
    print(f"  Execution window:   {exec_window:.1f}s")
    print(f"  Actual exec time:   {spec_exec_time:.1f}s")
    print(f"  Cost:               ${gptoss_exec.total_cost_usd or 0:.4f}")
    print(f"  Turns:              {gptoss_exec.num_turns}")
    print(f"  Total tokens:       {gptoss_exec.total_tokens:,}")
    print(f"  Tool uses:          {gts.get('total_tool_uses', 0)}")
    print(f"  Subagents:          {gts.get('total_subagents_spawned', 0)}")
    if pre_merge_snap is not None:
        print(f"  Files created:      {pre_merge_snap.total_files}")
        print(f"  Lines of code:      {pre_merge_snap.total_lines}")
    else:
        print(f"  Files created:      (snapshot skipped)")
        print(f"  Lines of code:      (snapshot skipped)")

    # ── Merge phase ──
    merge_time = merge_exec.duration_wall_s
    print(f"\n  --- Merge Phase (Opus) ---")
    print(f"  Merge time (s):     {merge_time:.1f}")
    print(f"  Cost:               ${merge_exec.total_cost_usd or 0:.4f}")
    print(f"  Turns:              {merge_exec.num_turns}")
    print(f"  Total tokens:       {merge_exec.total_tokens:,}")
    print(f"    Input:            {mts.get('input_tokens', 0):,}")
    print(f"    Output:           {mts.get('output_tokens', 0):,}")
    print(f"  Tool uses:          {mts.get('total_tool_uses', 0)}")
    print(f"  Subagents:          {mts.get('total_subagents_spawned', 0)}")

    # ── Final output (post-merge) ──
    print(f"\n  --- Final Output (post-merge) ---")
    if merge_snap is not None:
        print(f"  Files:              {merge_snap.total_files}")
        print(f"  Lines of code:      {merge_snap.total_lines}")
        print(f"  Tests passed:       {merge_snap.pytest_passed}")
        print(f"  Tests failed:       {merge_snap.pytest_failed}")
    else:
        print(f"  (snapshot skipped — no file/test metrics)")

    # ── Totals ──
    total_wall = opus_plan_time + merge_time
    total_cost = (
        (gptoss_plan.total_cost_usd or 0)
        + (opus_plan.total_cost_usd or 0)
        + (gptoss_exec.total_cost_usd or 0)
        + (merge_exec.total_cost_usd or 0)
    )
    print(f"\n  --- Totals ---")
    print(f"  Total wall time:    {total_wall:.1f}s (Opus plan + merge)")
    print(f"  Total cost:         ${total_cost:.4f}")

    if gptoss_exec.error:
        print(f"  Exec error:         {gptoss_exec.error}")
    if merge_exec.error:
        print(f"  Merge error:        {merge_exec.error}")

    print(f"\n  --- Artifacts ---")
    print(f"  Run dir:            {spec_dsp_dir}")
    print(f"    workdir/                 (generated code)")
    print(f"    phase1_planning/         (plans, plan_gen.json)")
    print(f"    phase2_execution/        (result.json, timeline.json)")
    print(f"    phase3_merge/            (MERGED_PLAN.md, result.json, timeline.json)")


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

def _add_config_args(parser: argparse.ArgumentParser) -> None:
    """Add common --config/--solver/--dispatcher/--executor args to a parser."""
    parser.add_argument(
        "--config", default="cfg_001",
        help="Config ID (default: cfg_001)",
    )
    parser.add_argument(
        "--solver", default="claude-opus-4-6",
        help="Solver model name (default: claude-opus-4-6)",
    )
    parser.add_argument(
        "--solver-provider", default="anthropic",
        help="Solver provider (default: anthropic)",
    )
    parser.add_argument(
        "--dispatcher", default="gpt-oss:20b",
        help="Dispatcher model name (default: gpt-oss:20b)",
    )
    parser.add_argument(
        "--dispatcher-provider", default="ollama",
        help="Dispatcher provider (default: ollama)",
    )
    parser.add_argument(
        "--executor", default=None,
        help="Executor model name (default: same as dispatcher)",
    )
    parser.add_argument(
        "--executor-provider", default=None,
        help="Executor provider (default: same as dispatcher-provider)",
    )


def _build_config(args: argparse.Namespace) -> TestConfig:
    """Build a TestConfig from parsed CLI args."""
    return TestConfig(
        config_id=args.config,
        solver=args.solver,
        solver_provider=args.solver_provider,
        dispatcher=args.dispatcher,
        dispatcher_provider=args.dispatcher_provider,
        executor=args.executor or args.dispatcher,
        executor_provider=args.executor_provider or args.dispatcher_provider,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan execution experiments with full instrumentation"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Debug logging"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # test1
    p1 = sub.add_parser(
        "test1",
        help="Dispatcher generates plan, executes, stops after timeout",
    )
    p1.add_argument("--case", required=True, help="Case name")
    p1.add_argument(
        "--timeout", type=float, default=30.0,
        help="Execution timeout in seconds (default: 30)",
    )
    _add_config_args(p1)

    # test2
    p2 = sub.add_parser(
        "test2",
        help="Speculative dispatch: dispatcher plans+executes while solver plans",
    )
    p2.add_argument("--case", required=True, help="Case name")
    _add_config_args(p2)

    # test3
    p3t = sub.add_parser(
        "test3",
        help="Speculative dispatch + merge: solver evaluates dispatcher work",
    )
    p3t.add_argument("--case", required=True, help="Case name")
    _add_config_args(p3t)

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
        config = _build_config(args)
        asyncio.run(test1_baseline(args.case, timeout_s=args.timeout, config=config))

    elif args.command == "test2":
        config = _build_config(args)
        asyncio.run(test2_parallel(args.case, config=config))

    elif args.command == "test3":
        config = _build_config(args)
        asyncio.run(test3_merge(args.case, config=config))

    elif args.command == "snapshot":
        cmd_snapshot(args)


if __name__ == "__main__":
    main()
