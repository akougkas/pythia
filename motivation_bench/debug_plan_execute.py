#!/usr/bin/env python3
"""
debug_plan_execute.py — See exactly what the planner and agents generate.

Supports three backends:
  - ollama:     local models via Ollama API (streaming, no hooks)
  - claude:     Claude models via Claude Agent SDK (hooks, tools)
  - ollama-sdk: local Ollama models routed through Claude Agent SDK
                (hooks, tools — same as claude but with local models)

Stage 1 (Planning): generate dispatch plan (JSON) via simple chat call.
Stage 2 (Execution): run agents in tools mode with phase instrumentation.

Usage:
    python debug_plan_execute.py --backend ollama --model nemotron-3-nano:4b
    python debug_plan_execute.py --backend claude --model claude-sonnet-4-20250514
    python debug_plan_execute.py --backend ollama-sdk --model gemma4:e2b
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import requests as _requests

from agents import AGENTS, get_agent_descriptions
from queries import QUERIES

OLLAMA_URL = "http://localhost:11434"

# Models known to break with thinking enabled (produce thinking blocks
# without Anthropic's signature field, causing MessageParseError)
DISABLE_THINKING_MODELS = {
    "nemotron-3-nano:4b",
}


def _ollama_sdk_env(model: str, ollama_url: str = OLLAMA_URL) -> dict[str, str]:
    """Build env vars to route Claude Agent SDK through Ollama."""
    return {
        "ANTHROPIC_BASE_URL": ollama_url,
        "ANTHROPIC_AUTH_TOKEN": "local",
        "ANTHROPIC_API_KEY": "local",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
        "CLAUDE_CODE_SUBAGENT_MODEL": model,
    }

AGENT_LIST = get_agent_descriptions()
AGENT_NAMES = list(AGENTS.keys())

PLANNER_SYSTEM = f"""You are a task planner for a scientific computing orchestration system. Given a query, decompose it into ordered steps and assign each step to exactly one specialist agent from the pool.

Available agents:
{AGENT_LIST}

You MUST respond with ONLY a JSON array. No explanation, no markdown fences.
Each step must include "depends_on" — a list of step numbers that must complete before this step can start. Use an empty list [] if the step has no dependencies.
Example format:
[{{"step": 1, "task": "Analyze the algorithm", "agent": "hpc_planner", "depends_on": []}}, {{"step": 2, "task": "Write the code", "agent": "hpc_coder", "depends_on": [1]}}]
"""

PLANNER_SYSTEM_TOOL = f"""You are a task planner for a scientific computing orchestration system. Given a query, decompose it into ordered steps and assign each step to exactly one specialist agent from the pool.

Available agents:
{AGENT_LIST}

Use the submit_plan tool to submit your plan. Each step must include depends_on — a list of step numbers that must complete before this step can start. Use an empty list [] if the step has no dependencies.
"""

# ── Plan tool schema (shared across backends) ──────────────────────

PLAN_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "integer", "description": "Step number (1-indexed)"},
                    "task": {"type": "string", "description": "Task description for the agent"},
                    "agent": {
                        "type": "string",
                        "description": "Agent name from the available pool",
                        "enum": AGENT_NAMES,
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Step numbers that must complete before this step",
                    },
                },
                "required": ["step", "task", "agent", "depends_on"],
            },
        },
    },
    "required": ["steps"],
}

PLAN_TOOL_DESC = "Submit the final dispatch plan with all steps, agent assignments, and dependencies."

# Ollama format
PLAN_TOOL_OLLAMA = {
    "type": "function",
    "function": {
        "name": "submit_plan",
        "description": PLAN_TOOL_DESC,
        "parameters": PLAN_INPUT_SCHEMA,
    },
}


def parse_plan(text: str) -> list[dict]:
    """Extract JSON plan from LLM response."""
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        print("  ⚠ Could not find JSON array in planner output")
        return []
    try:
        plan = json.loads(match.group())
        return plan
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parse error: {e}")
        return []


# ── Backend: Ollama (local models) ───────────────────────────────────


def ollama_preload(model: str) -> float:
    """Force Ollama to load the model into memory. Returns load time in seconds."""
    t0 = time.perf_counter()
    _requests.post(f"{OLLAMA_URL}/api/generate", json={
        "model": model,
        "prompt": "hi",
        "options": {"num_predict": 1},
        "stream": False,
    })
    elapsed = time.perf_counter() - t0
    return elapsed


def ollama_chat(model: str, system_prompt: str, user_content: str,
                stream: bool = True) -> str:
    """Call Ollama API with streaming output. Returns full response text."""
    resp = _requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": model,
        "stream": stream,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }, stream=stream)

    content = ""
    if stream:
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                content += token
                sys.stdout.write(token)
                sys.stdout.flush()
                if chunk.get("done"):
                    break
    else:
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        print(content)

    return content


def ollama_plan_with_tool(model: str, user_content: str) -> list[dict]:
    """Call Ollama with submit_plan tool. Returns parsed plan steps."""
    resp = _requests.post(f"{OLLAMA_URL}/api/chat", json={
        "model": model,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM_TOOL},
            {"role": "user", "content": user_content},
        ],
        "tools": [PLAN_TOOL_OLLAMA],
    })

    data = resp.json()
    msg = data.get("message", {})

    # Check for tool calls
    tool_calls = msg.get("tool_calls", [])
    for tc in tool_calls:
        if tc.get("function", {}).get("name") == "submit_plan":
            args = tc["function"].get("arguments", {})
            steps = args.get("steps", [])
            print(f"  [submit_plan tool called with {len(steps)} steps]")
            print(json.dumps(steps, indent=2))
            return steps

    # Fallback: model returned text instead of tool call
    content = msg.get("content", "")
    if content:
        print(f"  ⚠ Model returned text instead of tool call, falling back to regex parse")
        print(content)
        return parse_plan(content)

    print("  ⚠ No tool call and no content in response")
    return []


# ── Backend: Claude (via Agent SDK) ──────────────────────────────────



# Tools available to agents in tool mode
AGENT_TOOL_MAP = {
    # Readonly agents get read-only tools
    "hpc_planner": ["Read", "Glob", "Grep"],
    "hpc_reviewer": ["Read", "Glob", "Grep"],
    "sdp_discovery": ["Read", "Glob", "Grep", "Bash"],
    "sdp_reporter": ["Read"],
    "rwa_literature": ["Read", "Glob", "Grep", "Bash"],
    "rwa_designer": ["Read"],
    "rwa_analyzer": ["Read"],
    "critic": ["Read"],
    # Code-writing agents get full tools
    "hpc_coder": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    "hpc_tester": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    "sdp_wrangler": ["Read", "Write", "Edit", "Bash"],
    "sdp_analyst": ["Read", "Write", "Edit", "Bash"],
    "rwa_coder": ["Read", "Write", "Edit", "Bash"],
    "rwa_runner": ["Read", "Write", "Edit", "Bash"],
    "deployer": ["Read", "Write", "Edit", "Bash"],
    "documenter": ["Read", "Write", "Edit"],
    "general_assistant": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
}


class PhaseTimer:
    """Records timestamps at each dispatch phase for a single agent call.

    Three phases (tools mode):
        agent_start → prompt_submitted → first_tool_use → agent_end

    Durations:
        init_s:    agent_start → prompt_submitted
                   (SDK startup + prompt assembly — dispatch overhead)
        warmup_s:  prompt_submitted → first_tool_use
                   (LLM processing context + deliberation before first action
                    — counted as agent execution time)
        exec_s:    first_tool_use → agent_end
                   (tool execution + response assembly)

    init_s = dispatch overhead per agent.
    warmup_s + exec_s = agent execution time.
    """

    def __init__(self):
        self.agent_start: float = 0.0
        self.prompt_submitted: float = 0.0
        self.first_tool_use: float = 0.0
        self.agent_end: float = 0.0
        self.tool_calls: list[dict] = []  # [{name, duration_s}]
        self._current_tool_start: float = 0.0

    def phases(self) -> dict:
        """Return phase durations. Gaps between stages are the durations."""
        if not self.agent_start or not self.agent_end:
            return {}

        result = {}

        if self.prompt_submitted:
            result["init_s"] = round(self.prompt_submitted - self.agent_start, 4)
            if self.first_tool_use:
                result["warmup_s"] = round(self.first_tool_use - self.prompt_submitted, 4)
                result["exec_s"] = round(self.agent_end - self.first_tool_use, 4)
            else:
                # No tool calls — all time after prompt is warmup
                result["warmup_s"] = round(self.agent_end - self.prompt_submitted, 4)
                result["exec_s"] = 0.0
        else:
            # No prompt hook fired — can't split init from warmup
            if self.first_tool_use:
                result["init_s"] = 0.0
                result["warmup_s"] = round(self.first_tool_use - self.agent_start, 4)
                result["exec_s"] = round(self.agent_end - self.first_tool_use, 4)
            else:
                result["init_s"] = 0.0
                result["warmup_s"] = round(self.agent_end - self.agent_start, 4)
                result["exec_s"] = 0.0

        result["tool_calls"] = self.tool_calls
        result["total_s"] = round(self.agent_end - self.agent_start, 4)
        return result


async def claude_chat_async(model: str, system_prompt: str, user_content: str,
                            agent_name: str = "",
                            max_turns: int = 1,
                            workspace: str | Path | None = None,
                            phase_timer: PhaseTimer | None = None,
                            env: dict[str, str] | None = None) -> str:
    """Call Claude (or local model) via Agent SDK in tools mode. Returns full response text.

    Args:
        agent_name: Used to look up which tools to grant.
        max_turns: Max agentic turns per agent call.
        workspace: Working directory for agents.
        phase_timer: If provided, records per-phase timestamps.
        env: Extra environment variables (used to route SDK to Ollama).
    """
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, AssistantMessage, ResultMessage,
        TextBlock, ThinkingBlock, HookMatcher,
    )

    # ── Phase instrumentation hooks ─────────────────────────────
    hooks = None
    if phase_timer:
        async def on_prompt_submit(event, matcher, context):
            try:
                phase_timer.prompt_submitted = time.perf_counter()
                sys.stdout.write("  [hook: prompt_submitted]\n")
                sys.stdout.flush()
            except Exception:
                pass
            return {}

        async def on_pre_tool(event, matcher, context):
            try:
                now = time.perf_counter()
                if not phase_timer.first_tool_use:
                    phase_timer.first_tool_use = now
                phase_timer._current_tool_start = now
                tool_name = event.get("tool_name", "unknown") if isinstance(event, dict) else "unknown"
                sys.stdout.write(f"  [hook: pre_tool_use → {tool_name}]\n")
                sys.stdout.flush()
            except Exception:
                pass
            return {}

        async def on_post_tool(event, matcher, context):
            try:
                now = time.perf_counter()
                tool_name = event.get("tool_name", "unknown") if isinstance(event, dict) else "unknown"
                phase_timer.tool_calls.append({
                    "name": tool_name,
                    "duration_s": round(now - phase_timer._current_tool_start, 4),
                })
                sys.stdout.write(f"  [hook: post_tool_use ← {tool_name}]\n")
                sys.stdout.flush()
            except Exception:
                pass
            return {}

        hooks = {
            "UserPromptSubmit": [HookMatcher(matcher=None, hooks=[on_prompt_submit])],
            "PreToolUse": [HookMatcher(matcher=None, hooks=[on_pre_tool])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[on_post_tool])],
        }

    # Common kwargs shared across all modes
    common_kwargs: dict = {"model": model}
    if env:
        common_kwargs["env"] = env

    tools = AGENT_TOOL_MAP.get(agent_name, ["Read", "Glob", "Grep"])

    # Augment system prompt with tool-usage hints (provider-agnostic agents.py
    # describes the role; the dispatch layer adds backend-specific instructions)
    agent_spec = AGENTS.get(agent_name, {})
    if agent_spec.get("readonly", True):
        system_prompt += (
            "\n\nYou have access to file-reading and search tools. "
            "Use them to read relevant files in the current directory "
            "before producing your analysis."
        )
    else:
        system_prompt += (
            "\n\nYou have access to file and shell tools. "
            "Write your code to files in the current directory, "
            "then compile and test it using the shell. "
            "Do not just output code as text — actually create the files."
        )

    options = ClaudeAgentOptions(
        **common_kwargs,
        system_prompt=system_prompt,
        allowed_tools=tools,
        max_turns=max_turns,
        permission_mode="bypassPermissions",
        cwd=str(workspace) if workspace else None,
        hooks=hooks,
    )

    if phase_timer:
        phase_timer.agent_start = time.perf_counter()

    text = ""
    async for msg in query(prompt=user_content, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ThinkingBlock):
                    preview = block.thinking[:100] if block.thinking else ""
                    sys.stdout.write(f"\n  [thinking: {preview}...]\n")
                    sys.stdout.flush()
                elif isinstance(block, TextBlock):
                    text += block.text
                    sys.stdout.write(block.text)
                    sys.stdout.flush()
        elif isinstance(msg, ResultMessage):
            if msg.total_cost_usd is not None:
                print(f"\n  [cost: ${msg.total_cost_usd:.4f}]", end="")

    if phase_timer:
        phase_timer.agent_end = time.perf_counter()

    return text


async def sdk_plan(model: str, user_content: str,
                   env: dict[str, str] | None = None) -> list[dict]:
    """Plan via Claude Agent SDK — plain chat call, parse JSON from response.

    Same pattern as ClaudeClient in evaluation_bench/agent_runner.py.
    Works for both claude and ollama-sdk backends.
    """
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, AssistantMessage, TextBlock,
    )

    common_kwargs: dict = {"model": model}
    if env:
        common_kwargs["env"] = env

    options = ClaudeAgentOptions(
        **common_kwargs,
        system_prompt=PLANNER_SYSTEM,
    )

    text = ""
    async for msg in query(prompt=user_content, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text += block.text
                    sys.stdout.write(block.text)
                    sys.stdout.flush()

    return parse_plan(text)


# ── Unified agent chat dispatcher ──────────────────────────────────


async def chat(backend: str, model: str, system_prompt: str, user_content: str,
               agent_name: str = "",
               max_turns: int = 1, workspace: str | Path | None = None,
               phase_timer: PhaseTimer | None = None) -> str:
    """Dispatch agent execution to the appropriate backend."""
    if backend == "ollama":
        return ollama_chat(model, system_prompt, user_content)
    elif backend in ("claude", "ollama-sdk"):
        env = _ollama_sdk_env(model) if backend == "ollama-sdk" else None
        return await claude_chat_async(model, system_prompt, user_content,
                                       agent_name=agent_name,
                                       max_turns=max_turns,
                                       workspace=workspace,
                                       phase_timer=phase_timer,
                                       env=env)
    else:
        raise ValueError(f"Unknown backend: {backend}")


# ── Main debug runner ─────────────────────────────────────────────────


async def run_debug(query_id: str, model: str, backend: str,
                    max_turns: int = 5, use_tool_plan: bool = False):
    query = next((q for q in QUERIES if q["id"] == query_id), None)
    if not query:
        print(f"Query {query_id} not found. Available: {[q['id'] for q in QUERIES]}")
        return

    sdk_backend = backend in ("claude", "ollama-sdk")

    # Create isolated workspace for SDK backends (agents use tools)
    workspace = None
    if sdk_backend:
        import shutil
        model_tag = model.replace(":", "_").replace("/", "_")
        workspace = Path(f"results/workspace/{model_tag}_{query_id}").resolve()
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)

    print(f"{'=' * 70}")
    print(f"  Query:    {query_id} ({query['domain']}, {query['complexity']})")
    print(f"  Model:    {model}")
    print(f"  Backend:  {backend}")
    if sdk_backend:
        print(f"  Planner:  plain chat (SDK)")
        print(f"  Agents:   tools mode (SDK)")
    else:
        print(f"  Mode:     chat (direct Ollama API)")
    if workspace:
        print(f"  Workspace: {workspace}")
    print(f"{'=' * 70}")
    print(f"\n📥 USER QUERY:\n{query['query']}")

    # ── Preload model for Ollama backends ─────────────────────────
    if backend in ("ollama", "ollama-sdk"):
        print(f"\n⏳ Preloading model {model}...", end="", flush=True)
        load_time = ollama_preload(model)
        print(f" done ({load_time:.1f}s)")

    # ── Step 1: Planner ────────────────────────────────────────────
    print(f"\n{'─' * 70}")
    print("📋 PLANNER OUTPUT:")
    print(f"{'─' * 70}")

    t0 = time.perf_counter()
    if backend == "ollama":
        if use_tool_plan:
            plan = ollama_plan_with_tool(model, query["query"])
            planner_content = json.dumps(plan, indent=2)
        else:
            planner_content = ollama_chat(model, PLANNER_SYSTEM, query["query"])
            plan = parse_plan(planner_content)
    else:
        # claude and ollama-sdk: always use sdk_plan (simple chat + JSON parse)
        env = _ollama_sdk_env(model) if backend == "ollama-sdk" else None
        plan = await sdk_plan(model, query["query"], env=env)
        planner_content = json.dumps(plan, indent=2)
    planner_time = time.perf_counter() - t0
    print(f"\n  [{planner_time:.1f}s] (tool={use_tool_plan})")

    if not plan:
        print("\nFailed to parse plan. Stopping.")
        return

    print(f"\nParsed plan ({len(plan)} steps):")
    for step in plan:
        agent = step.get("agent", "???")
        task = step.get("task", "???")
        deps = step.get("depends_on", [])
        valid = "✓" if agent in AGENTS else "✗ UNKNOWN"
        print(f"  Step {step.get('step', '?')}: [{agent}] {valid} → {task} (depends_on: {deps})")

    # ── Step 2: Execute each agent ─────────────────────────────────
    step_outputs: dict[int, str] = {}
    agent_full_outputs = []
    agent_phase_data = []  # per-agent phase breakdown
    total_exec = 0.0

    for i, step in enumerate(plan):
        agent_name = step.get("agent", "general_assistant")
        task = step.get("task", "")
        step_num = step.get("step", i + 1)
        depends_on = step.get("depends_on", [])

        if agent_name not in AGENTS:
            print(f"\n  Skipping unknown agent: {agent_name}")
            agent_full_outputs.append(f"[SKIPPED] {agent_name}")
            agent_phase_data.append({"agent": agent_name, "skipped": True})
            continue

        agent_spec = AGENTS[agent_name]

        print(f"\n{'─' * 70}")
        print(f"  AGENT: {agent_name} (step {step_num}/{len(plan)})")
        print(f"  Task: {task}")
        print(f"  Depends on: {depends_on}")
        print(f"{'─' * 70}")

        # Build context with ONLY outputs from dependency steps
        context = f"Original query: {query['query']}\n\nYour specific task: {task}"
        dep_outputs = []
        for dep in depends_on:
            if dep in step_outputs:
                dep_outputs.append(step_outputs[dep])
        if dep_outputs:
            context += "\n\nPrior agent results (from dependencies):\n" + "\n".join(dep_outputs)

        # Create phase timer for SDK backends (agents always use tools mode)
        timer = PhaseTimer() if sdk_backend else None

        t0 = time.perf_counter()
        content = await chat(backend, model, agent_spec["system_prompt"], context,
                             agent_name=agent_name, max_turns=max_turns,
                             workspace=workspace, phase_timer=timer)
        agent_time = time.perf_counter() - t0
        total_exec += agent_time

        # Record phase data
        phases = timer.phases() if timer else {}
        agent_phase_data.append({
            "step": step_num,
            "agent": agent_name,
            "depends_on": depends_on,
            "elapsed_s": round(agent_time, 4),
            "chars": len(content),
            "phases": phases,
        })

        # Print phase breakdown if available
        if phases:
            print(f"\n  [{agent_time:.1f}s, {len(content)} chars]")
            print(f"    init={phases.get('init_s', 0):.2f}s "
                  f"warmup={phases.get('warmup_s', 0):.2f}s "
                  f"exec={phases.get('exec_s', 0):.2f}s")
        else:
            print(f"\n  [{agent_time:.1f}s, {len(content)} chars]")

        step_outputs[step_num] = f"[{agent_name}] {content}"
        agent_full_outputs.append(content)

    # ── Summary ────────────────────────────────────────────────────
    total = planner_time + total_exec
    summary_text = (
        f"\n{'=' * 70}\n"
        f"  TIMING SUMMARY\n"
        f"{'=' * 70}\n"
        f"  Backend:             {backend}\n"
        f"  Model:               {model}\n"
        f"  Planner (dispatch):  {planner_time:.1f}s\n"
        f"  Agents (execution):  {total_exec:.1f}s\n"
        f"  Total:               {total:.1f}s\n"
        f"  Dispatch fraction:   {planner_time / total:.0%}\n"
        f"  Agent calls:         {len(plan)}\n"
    )
    print(summary_text)

    # ── Write full log to file ─────────────────────────────────────
    model_tag = model.replace(":", "_").replace("/", "_")
    plan_tag = "toolplan" if use_tool_plan else "chatplan"
    log_dir = Path(f"results/debug_{backend}_{model_tag}_{plan_tag}")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / f"{query_id}.log"
    with open(log_path, "w") as f:
        f.write(f"Query: {query_id} ({query['domain']}, {query['complexity']})\n")
        f.write(f"Backend: {backend}\n")
        f.write(f"Model: {model}\n")
        f.write(f"{'=' * 70}\n\n")
        f.write(f"USER QUERY:\n{query['query']}\n\n")
        f.write(f"{'=' * 70}\n")
        f.write(f"PLANNER OUTPUT ({planner_time:.1f}s):\n")
        f.write(f"{planner_content}\n\n")
        f.write(f"Parsed plan ({len(plan)} steps):\n")
        for step in plan:
            deps = step.get("depends_on", [])
            f.write(f"  Step {step.get('step', '?')}: [{step.get('agent')}] "
                    f"{step.get('task')} (depends_on: {deps})\n")
        f.write(f"\n{'=' * 70}\n")
        for i, (step, full_output) in enumerate(zip(plan, agent_full_outputs)):
            f.write(f"\nAGENT: {step.get('agent')} (step {i+1}/{len(plan)})\n")
            f.write(f"Task: {step.get('task')}\n")
            f.write(f"Depends on: {step.get('depends_on', [])}\n")
            # Write phase breakdown if available
            pd = agent_phase_data[i] if i < len(agent_phase_data) else {}
            phases = pd.get("phases", {})
            if phases:
                f.write(f"Phases: init={phases.get('init_s', 0):.2f}s "
                        f"warmup={phases.get('warmup_s', 0):.2f}s "
                        f"exec={phases.get('exec_s', 0):.2f}s\n")
                if phases.get("tool_calls"):
                    for tc in phases["tool_calls"]:
                        f.write(f"  tool: {tc['name']} ({tc['duration_s']:.2f}s)\n")
            f.write(f"{'─' * 70}\n")
            f.write(f"{full_output}\n\n")
        f.write(summary_text)
    print(f"Full log → {log_path}")

    # ── Write JSON results with phase data ────────────────────────
    # Compute global phase totals across all agents
    total_init = sum(a.get("phases", {}).get("init_s", 0) for a in agent_phase_data)
    total_warmup = sum(a.get("phases", {}).get("warmup_s", 0) for a in agent_phase_data)
    total_agent_exec = sum(a.get("phases", {}).get("exec_s", 0) for a in agent_phase_data)

    json_path = log_dir / f"{query_id}.json"
    result_data = {
        "query_id": query_id,
        "domain": query["domain"],
        "complexity": query["complexity"],
        "backend": backend,
        "model": model,
        "planning_s": round(planner_time, 4),
        "total_init_s": round(total_init, 4),
        "total_warmup_s": round(total_warmup, 4),
        "total_exec_s": round(total_agent_exec, 4),
        "execution_s": round(total_exec, 4),
        "total_s": round(planner_time + total_exec, 4),
        "speculation_window_s": round(planner_time + total_init, 4),
        "dispatch_fraction": round(planner_time / (planner_time + total_exec), 4)
        if (planner_time + total_exec) > 0 else 0,
        "num_agents": len(plan),
        "agents": agent_phase_data,
    }
    with open(json_path, "w") as f:
        json.dump(result_data, f, indent=2)
    print(f"JSON    → {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Debug plan-and-execute output")
    parser.add_argument("--query", default=None, help="Query ID (e.g. gen_omp_26_reduce_product_of_inverses)")
    parser.add_argument("--model", default=None, help="Model name (auto-set per backend if omitted)")
    parser.add_argument(
        "--backend", choices=["ollama", "claude", "ollama-sdk"], default="ollama",
        help="LLM backend: ollama (direct local API), claude (Agent SDK), "
             "or ollama-sdk (local model via Agent SDK — hooks + tools)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=5,
        help="Max agentic turns per agent (SDK backends only, default: 5)",
    )
    parser.add_argument(
        "--tool-plan", action="store_true",
        help="Use submit_plan tool for structured planning (ollama backend only)",
    )
    args = parser.parse_args()

    # Default model per backend
    if args.model is None:
        args.model = {
            "ollama": "nemotron-3-nano:4b",
            "claude": "claude-sonnet-4-20250514",
            "ollama-sdk": "gemma4:e2b",
        }[args.backend]

    # Default query: first available
    if args.query is None:
        args.query = QUERIES[0]["id"] if QUERIES else "Q01"

    asyncio.run(run_debug(args.query, args.model, args.backend,
                          max_turns=args.max_turns,
                          use_tool_plan=args.tool_plan))
