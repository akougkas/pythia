#!/usr/bin/env python3
"""
bench_plan_execute.py — Plan-and-Execute pattern dispatch latency benchmark.

Measures three-way latency split:
  1. Planner LLM time   — single LLM call to decompose query into steps
  2. Routing time        — code-only dispatch (no LLM), should be near-zero
  3. Agent execution time — per-agent LLM calls

Usage:
    python bench_plan_execute.py --model qwen3.5:9b --repeats 3
    python bench_plan_execute.py --model qwen3.5:9b --queries Q01,Q03,Q06
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

import requests as _requests

from agents import AGENTS, get_agent_descriptions
from queries import QUERIES

OLLAMA_URL = "http://localhost:11434"

# Models known to break with thinking enabled
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


# Tools available to agents in SDK tools mode
AGENT_TOOL_MAP = {
    "hpc_planner": ["Read", "Glob", "Grep"],
    "hpc_reviewer": ["Read", "Glob", "Grep"],
    "sdp_discovery": ["Read", "Glob", "Grep", "Bash"],
    "sdp_reporter": ["Read"],
    "rwa_literature": ["Read", "Glob", "Grep", "Bash"],
    "rwa_designer": ["Read"],
    "rwa_analyzer": ["Read"],
    "critic": ["Read"],
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


# ── Timing infrastructure ──────────────────────────────────────────


class TimingCollector:
    """Records per-node timing with category labels, responses, and dependencies."""

    def __init__(self):
        self.records: list[dict] = []
        self.steps: list[dict] = []

    def record(self, node: str, category: str, elapsed_s: float,
               response: str = "", step_num: int = 0,
               depends_on: list[int] | None = None,
               phases: dict | None = None):
        self.records.append(
            {"node": node, "category": category, "elapsed_s": round(elapsed_s, 6)}
        )
        step_entry = {
            "node": node,
            "category": category,
            "elapsed_s": round(elapsed_s, 6),
            "response": response,
            "step_num": step_num,
            "depends_on": depends_on or [],
            "chars": len(response),
        }
        if phases:
            step_entry["phases"] = phases
        self.steps.append(step_entry)

    def reset(self):
        self.records = []
        self.steps = []

    def _critical_path_execution(self) -> float:
        """Compute parallel execution time via critical path on dependency graph.

        Each step's earliest finish = max(finish of dependencies) + own duration.
        The critical path is the maximum finish time across all steps.
        """
        exec_steps = [s for s in self.steps if s["category"] == "execution"]
        if not exec_steps:
            return 0.0

        # Map step_num → duration
        duration = {s["step_num"]: s["elapsed_s"] for s in exec_steps}
        deps = {s["step_num"]: s["depends_on"] for s in exec_steps}

        # Compute earliest finish time for each step
        finish: dict[int, float] = {}

        def get_finish(step: int) -> float:
            if step in finish:
                return finish[step]
            dep_finish = max((get_finish(d) for d in deps.get(step, [])
                              if d in duration), default=0.0)
            finish[step] = dep_finish + duration.get(step, 0.0)
            return finish[step]

        for s in exec_steps:
            get_finish(s["step_num"])

        return max(finish.values()) if finish else 0.0

    def summary(self) -> dict:
        planning = sum(
            r["elapsed_s"] for r in self.records if r["category"] == "planning"
        )
        execution_seq = sum(
            r["elapsed_s"] for r in self.records if r["category"] == "execution"
        )
        execution_par = self._critical_path_execution()
        total_seq = planning + execution_seq
        total_par = planning + execution_par
        result = {
            "planning_s": round(planning, 4),
            "execution_seq_s": round(execution_seq, 4),
            "execution_par_s": round(execution_par, 4),
            "total_seq_s": round(total_seq, 4),
            "total_par_s": round(total_par, 4),
            "dispatch_fraction_seq": round(planning / total_seq, 4)
            if total_seq > 0
            else 0,
            "dispatch_fraction_par": round(planning / total_par, 4)
            if total_par > 0
            else 0,
            "num_agent_calls": sum(
                1 for r in self.records if r["category"] == "execution"
            ),
        }

        # Build clean per-agent array (matches debug_plan_execute.py format)
        exec_steps = [s for s in self.steps if s["category"] == "execution"]
        agents = []
        for s in exec_steps:
            agent_entry = {
                "step": s["step_num"],
                "agent": s["node"],
                "depends_on": s["depends_on"],
                "elapsed_s": s["elapsed_s"],
                "chars": s["chars"],
            }
            if "phases" in s:
                agent_entry["phases"] = s["phases"]
            agents.append(agent_entry)
        result["agents"] = agents

        # Phase totals (SDK backends only — zero when phases not recorded)
        total_init = sum(s.get("phases", {}).get("init_s", 0) for s in exec_steps)
        total_warmup = sum(s.get("phases", {}).get("warmup_s", 0) for s in exec_steps)
        total_exec = sum(s.get("phases", {}).get("exec_s", 0) for s in exec_steps)
        if total_init or total_warmup or total_exec:
            result["total_init_s"] = round(total_init, 4)
            result["total_warmup_s"] = round(total_warmup, 4)
            result["total_exec_s"] = round(total_exec, 4)
            result["speculation_window_s"] = round(planning + total_init, 4)

        return result


timing = TimingCollector()


# ── Phase timer (SDK backends) ────────────────────────────────────


class PhaseTimer:
    """Records timestamps at each dispatch phase for a single agent call.

    Three phases (tools mode):
        agent_start → prompt_submitted → first_tool_use → agent_end

    Durations:
        init_s:    agent_start → prompt_submitted  (SDK startup overhead)
        warmup_s:  prompt_submitted → first_tool_use  (LLM deliberation)
        exec_s:    first_tool_use → agent_end  (tool execution)
    """

    def __init__(self):
        self.agent_start: float = 0.0
        self.prompt_submitted: float = 0.0
        self.first_tool_use: float = 0.0
        self.agent_end: float = 0.0
        self.tool_calls: list[dict] = []
        self._current_tool_start: float = 0.0

    def phases(self) -> dict:
        if not self.agent_start or not self.agent_end:
            return {}

        result = {}
        if self.prompt_submitted:
            result["init_s"] = round(self.prompt_submitted - self.agent_start, 4)
            if self.first_tool_use:
                result["warmup_s"] = round(self.first_tool_use - self.prompt_submitted, 4)
                result["exec_s"] = round(self.agent_end - self.first_tool_use, 4)
            else:
                result["warmup_s"] = round(self.agent_end - self.prompt_submitted, 4)
                result["exec_s"] = 0.0
        else:
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


# ── SDK backend functions ─────────────────────────────────────────


def ollama_preload(model: str) -> float:
    """Force Ollama to load the model into memory. Returns load time in seconds."""
    t0 = time.perf_counter()
    _requests.post(f"{OLLAMA_URL}/api/generate", json={
        "model": model,
        "prompt": "hi",
        "options": {"num_predict": 1},
        "stream": False,
    })
    return time.perf_counter() - t0


async def sdk_plan(model: str, user_content: str,
                   env: dict[str, str] | None = None) -> tuple[list[dict], bool]:
    """Plan via Claude Agent SDK — plain chat call, parse JSON from response.

    Returns (plan, planner_failed) to match bench parse_plan signature.
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

    return parse_plan(text)


async def claude_chat_async(model: str, system_prompt: str, user_content: str,
                            agent_name: str = "",
                            max_turns: int = 1,
                            workspace: str | Path | None = None,
                            phase_timer: PhaseTimer | None = None,
                            env: dict[str, str] | None = None) -> str:
    """Call Claude (or local model) via Agent SDK in tools mode. Returns response text."""
    from claude_agent_sdk import (
        query, ClaudeAgentOptions, AssistantMessage, ResultMessage,
        TextBlock, ThinkingBlock, HookMatcher,
    )

    hooks = None
    if phase_timer:
        async def on_prompt_submit(event, matcher, context):
            try:
                phase_timer.prompt_submitted = time.perf_counter()
            except Exception:
                pass
            return {}

        async def on_pre_tool(event, matcher, context):
            try:
                now = time.perf_counter()
                if not phase_timer.first_tool_use:
                    phase_timer.first_tool_use = now
                phase_timer._current_tool_start = now
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
            except Exception:
                pass
            return {}

        hooks = {
            "UserPromptSubmit": [HookMatcher(matcher=None, hooks=[on_prompt_submit])],
            "PreToolUse": [HookMatcher(matcher=None, hooks=[on_pre_tool])],
            "PostToolUse": [HookMatcher(matcher=None, hooks=[on_post_tool])],
        }

    common_kwargs: dict = {"model": model}
    if env:
        common_kwargs["env"] = env

    tools = AGENT_TOOL_MAP.get(agent_name, ["Read", "Glob", "Grep"])

    # Augment system prompt with tool-usage hints (provider-agnostic agents.py
    # describes the role; the dispatch layer adds backend-specific instructions)
    agent_spec = AGENTS.get(agent_name, {})
    ws_path = str(workspace) if workspace else "the current directory"
    if agent_spec.get("readonly", True):
        system_prompt = (
            f"WORKSPACE CONSTRAINT: Your working directory is {ws_path}. "
            f"Do NOT create or modify any files.\n\n"
        ) + system_prompt + (
            "\n\nYou have access to file-reading and search tools. "
            f"Use them to read relevant files in {ws_path} "
            "before producing your analysis."
        )
    else:
        system_prompt = (
            f"WORKSPACE CONSTRAINT: Your working directory is {ws_path}. "
            f"You MUST write ALL files to {ws_path}. "
            f"You MUST use absolute paths starting with {ws_path}/ for ALL file operations. "
            f"Do NOT write files anywhere else. "
            f"Before running any shell command, always cd to {ws_path} first.\n\n"
        ) + system_prompt + (
            f"\n\nYou have access to file and shell tools. "
            f"Write ALL files to {ws_path}. "
            f"Do not just output code as text — actually create the files."
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
                if isinstance(block, TextBlock):
                    text += block.text
        elif isinstance(msg, ResultMessage):
            if msg.total_cost_usd is not None:
                sys.stdout.write(f"  [cost: ${msg.total_cost_usd:.4f}]")
                sys.stdout.flush()

    if phase_timer:
        phase_timer.agent_end = time.perf_counter()

    return text


# ── Graph state ────────────────────────────────────────────────────


class PlanExecuteState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: list  # [{step, task, agent, depends_on}, ...]
    step_index: int
    step_outputs: dict  # step_number → agent output text
    planner_failed: bool


# ── Planner prompt ─────────────────────────────────────────────────

AGENT_LIST = get_agent_descriptions()

PLANNER_SYSTEM = f"""You are a task planner for a scientific computing orchestration system. Given a query, decompose it into ordered steps and assign each step to exactly one specialist agent from the pool.

Available agents:
{AGENT_LIST}

You MUST respond with ONLY a JSON array. No explanation, no markdown fences.
Each step must include "depends_on" — a list of step numbers that must complete before this step can start. Use an empty list [] if the step has no dependencies.
Example format:
[{{"step": 1, "task": "Analyze the algorithm", "agent": "hpc_planner", "depends_on": []}}, {{"step": 2, "task": "Write the code", "agent": "hpc_coder", "depends_on": [1]}}]
"""


# ── Graph construction ─────────────────────────────────────────────


def parse_plan(text: str) -> tuple[list[dict], bool]:
    """Extract JSON plan from LLM response, handling markdown fences.

    Returns (plan, planner_failed). If planner_failed is True, the plan
    is a fallback and should be flagged in the results.
    """
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.strip()
    # Find the JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return [], True
    try:
        plan = json.loads(match.group())
        # Validate agent names
        valid = []
        for step in plan:
            agent = step.get("agent", "")
            if agent not in AGENTS:
                # Try case-insensitive match
                for name in AGENTS:
                    if name.lower() == agent.lower():
                        step["agent"] = name
                        break
                else:
                    step["agent"] = "general_assistant"  # fallback
            valid.append(step)
        if not valid:
            return [], True
        return valid, False
    except json.JSONDecodeError:
        return [], True


def build_plan_execute_graph(llm: ChatOllama):
    """Build a plan-and-execute LangGraph with timing instrumentation."""

    def planner_node(state: PlanExecuteState) -> dict:
        """Single LLM call to generate the full plan."""
        t0 = time.perf_counter()
        messages = [
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=state["messages"][0].content),
        ]
        response = llm.invoke(messages)
        elapsed = time.perf_counter() - t0

        plan, failed = parse_plan(response.content)
        timing.record("planner", "planning", elapsed, response=response.content,
                       step_num=0, depends_on=[])

        return {
            "messages": [AIMessage(content=f"[Planner] Generated {len(plan)}-step plan")],
            "plan": plan,
            "step_index": 0,
            "planner_failed": failed,
        }

    def dispatch_node(state: PlanExecuteState) -> dict:
        """Code-only routing — reads current step, no LLM call."""
        # Routing is near-zero (no LLM); skip timing to reduce noise
        return {}

    def route_to_agent(state: PlanExecuteState) -> str:
        """Conditional edge: route to agent or END based on plan progress."""
        if state.get("planner_failed", False):
            return "DONE"
        idx = state.get("step_index", 0)
        plan = state.get("plan", [])
        if idx >= len(plan):
            return "DONE"
        agent = plan[idx].get("agent", "")
        return agent if agent in AGENTS else "DONE"

    def make_agent_node(name: str, system_prompt: str):
        """Agent node: receives its task + outputs from dependency steps only."""

        def node(state: PlanExecuteState) -> dict:
            idx = state["step_index"]
            step = state["plan"][idx]
            task = step["task"]
            step_num = step.get("step", idx + 1)
            depends_on = step.get("depends_on", [])
            original_query = state["messages"][0].content
            step_outputs = state.get("step_outputs", {})

            # Build context with ONLY outputs from dependency steps
            context = f"Original query: {original_query}\n\nYour specific task: {task}"
            dep_outputs = []
            for dep in depends_on:
                if dep in step_outputs:
                    dep_outputs.append(step_outputs[dep])
            if dep_outputs:
                context += "\n\nPrior agent results (from dependencies):\n" + "\n".join(dep_outputs)

            t0 = time.perf_counter()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context),
            ]
            response = llm.invoke(messages)
            elapsed = time.perf_counter() - t0
            timing.record(name, "execution", elapsed, response=response.content,
                          step_num=step_num, depends_on=depends_on)

            # Store output indexed by step number
            new_outputs = dict(step_outputs)
            new_outputs[step_num] = f"[{name}] {response.content}"

            return {
                "messages": [AIMessage(content=f"[{name}] {response.content}")],
                "step_index": idx + 1,
                "step_outputs": new_outputs,
            }

        return node

    # ── Build graph ────────────────────────────────────────────────
    #
    #  START → planner → dispatch ─┬→ Agent1 ─→ dispatch ─┬→ ...
    #                               ├→ Agent2 ─→ dispatch  │
    #                               └→ DONE ───→ END       │

    builder = StateGraph(PlanExecuteState)
    builder.add_node("planner", planner_node)
    builder.add_node("dispatch", dispatch_node)

    routing_map: dict[str, str] = {"DONE": END}
    for name, info in AGENTS.items():
        builder.add_node(name, make_agent_node(name, info["system_prompt"]))
        builder.add_edge(name, "dispatch")  # after agent → back to dispatch
        routing_map[name] = name

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "dispatch")
    builder.add_conditional_edges("dispatch", route_to_agent, routing_map)

    return builder.compile()


# ── Benchmark runner ───────────────────────────────────────────────


def warmup(llm: ChatOllama):
    """Warm up the model to avoid cold-start bias on first query."""
    print("  Warming up model...", end=" ", flush=True)
    llm.invoke([HumanMessage(content="Say OK.")])
    print("done.")


def run_benchmark(
    model: str, repeats: int, query_ids: list[str] | None, output_path: Path,
    max_tokens: int = -1,
):
    llm = ChatOllama(model=model, base_url=OLLAMA_URL, temperature=0,
                     num_predict=max_tokens)
    graph = build_plan_execute_graph(llm)
    warmup(llm)

    queries = QUERIES
    if query_ids:
        queries = [q for q in QUERIES if q["id"] in query_ids]

    results = []
    for query in queries:
        for rep in range(1, repeats + 1):
            print(
                f"  [{query['id']}] rep {rep}/{repeats} ...", end=" ", flush=True
            )
            timing.reset()

            t0 = time.perf_counter()
            try:
                final_state = graph.invoke(
                    {
                        "messages": [HumanMessage(content=query["query"])],
                        "plan": [],
                        "step_index": 0,
                        "step_outputs": {},
                        "planner_failed": False,
                    },
                    config={"recursion_limit": 30},
                )
            except Exception as e:
                print(f"ERROR: {e}")
                continue
            wall_s = time.perf_counter() - t0

            planner_failed = final_state.get("planner_failed", False)
            summary = timing.summary()
            result = {
                "query_id": query["id"],
                "domain": query["domain"],
                "complexity": query["complexity"],
                "pattern": "plan_execute",
                "model": model,
                "repetition": rep,
                "wall_s": round(wall_s, 4),
                "planner_failed": planner_failed,
                **summary,
            }
            results.append(result)
            fail_tag = " PLANNER_FAILED" if planner_failed else ""
            print(
                f"plan={summary['planning_s']:.1f}s "
                f"exec_seq={summary['execution_seq_s']:.1f}s "
                f"exec_par={summary['execution_par_s']:.1f}s "
                f"agents={summary['num_agent_calls']} "
                f"dispatch%_seq={summary['dispatch_fraction_seq']:.0%} "
                f"dispatch%_par={summary['dispatch_fraction_par']:.0%}"
                f"{fail_tag}"
            )

            # Write per-query log
            log_dir = output_path.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{query['id']}_rep{rep}.log"
            with open(log_file, "w") as lf:
                lf.write(f"Query ID:    {query['id']}\n")
                lf.write(f"Domain:      {query['domain']}\n")
                lf.write(f"Complexity:  {query['complexity']}\n")
                lf.write(f"Model:       {model}\n")
                lf.write(f"Max tokens:  {max_tokens}\n")
                lf.write(f"Repetition:  {rep}/{repeats}\n")
                lf.write(f"Wall time:   {wall_s:.4f}s\n")
                lf.write(f"\n{'='*72}\n")
                lf.write(f"USER QUERY:\n{query['query']}\n")
                for i, step in enumerate(timing.steps):
                    lf.write(f"\n{'='*72}\n")
                    deps = step.get('depends_on', [])
                    dep_str = f" depends_on={deps}" if deps else ""
                    lf.write(f"STEP {step.get('step_num', i+1)}: [{step['node']}] "
                             f"({step['category']}, {step['elapsed_s']:.4f}s)"
                             f"{dep_str}\n")
                    phases = step.get("phases", {})
                    if phases:
                        lf.write(f"  Phases: init={phases.get('init_s', 0):.2f}s "
                                 f"warmup={phases.get('warmup_s', 0):.2f}s "
                                 f"exec={phases.get('exec_s', 0):.2f}s\n")
                        for tc in phases.get("tool_calls", []):
                            lf.write(f"    tool: {tc['name']} ({tc['duration_s']:.2f}s)\n")
                    lf.write(f"{'-'*72}\n")
                    lf.write(f"{step['response']}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {output_path}")


# ── SDK benchmark runner (claude / ollama-sdk) ────────────────────


async def run_benchmark_sdk(
    model: str, backend: str, repeats: int, query_ids: list[str] | None,
    output_path: Path, results_base: Path, max_turns: int = 5,
):
    """Benchmark runner for claude and ollama-sdk backends via Agent SDK."""
    env = _ollama_sdk_env(model) if backend == "ollama-sdk" else None

    # Preload model for Ollama-backed backends
    if backend == "ollama-sdk":
        print(f"  Preloading model {model}...", end="", flush=True)
        load_time = ollama_preload(model)
        print(f" done ({load_time:.1f}s)")

    queries = QUERIES
    if query_ids:
        queries = [q for q in QUERIES if q["id"] in query_ids]

    results = []
    for q in queries:
        for rep in range(1, repeats + 1):
            print(
                f"  [{q['id']}] rep {rep}/{repeats} ...", end=" ", flush=True
            )
            timing.reset()

            # Create isolated workspace for agents
            model_tag = model.replace(":", "_").replace("/", "_")
            workspace = results_base / "workspace" / f"{model_tag}_{q['id']}_rep{rep}"
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True)

            t0 = time.perf_counter()

            # ── Planning ──────────────────────────────────────────
            plan_t0 = time.perf_counter()
            try:
                plan, planner_failed = await sdk_plan(model, q["query"], env=env)
            except Exception as e:
                print(f"PLAN ERROR: {e}")
                continue
            plan_elapsed = time.perf_counter() - plan_t0

            plan_text = json.dumps(plan, indent=2)
            timing.record("planner", "planning", plan_elapsed,
                          response=plan_text, step_num=0, depends_on=[])

            if planner_failed:
                wall_s = time.perf_counter() - t0
                summary = timing.summary()
                result = {
                    "query_id": q["id"],
                    "domain": q["domain"],
                    "complexity": q["complexity"],
                    "pattern": "plan_execute",
                    "backend": backend,
                    "model": model,
                    "repetition": rep,
                    "wall_s": round(wall_s, 4),
                    "planner_failed": True,
                    **summary,
                }
                results.append(result)
                print(f"plan={plan_elapsed:.1f}s PLANNER_FAILED")
                continue

            # ── Execute agents sequentially ───────────────────────
            step_outputs: dict[int, str] = {}

            for i, step in enumerate(plan):
                agent_name = step.get("agent", "general_assistant")
                task = step.get("task", "")
                step_num = step.get("step", i + 1)
                depends_on = step.get("depends_on", [])

                if agent_name not in AGENTS:
                    timing.record(agent_name, "execution", 0.0,
                                  response=f"[SKIPPED] unknown agent: {agent_name}",
                                  step_num=step_num, depends_on=depends_on)
                    continue

                agent_spec = AGENTS[agent_name]

                # Build context with dependency outputs
                context = f"Original query: {q['query']}\n\nYour specific task: {task}"
                dep_outputs = [step_outputs[d] for d in depends_on if d in step_outputs]
                if dep_outputs:
                    context += "\n\nPrior agent results (from dependencies):\n" + "\n".join(dep_outputs)

                timer = PhaseTimer()
                agent_t0 = time.perf_counter()
                try:
                    content = await claude_chat_async(
                        model, agent_spec["system_prompt"], context,
                        agent_name=agent_name, max_turns=max_turns,
                        workspace=workspace, phase_timer=timer, env=env,
                    )
                except Exception as e:
                    content = f"[ERROR] {e}"
                    print(f"\n    agent {agent_name} error: {e}", end="")
                agent_elapsed = time.perf_counter() - agent_t0

                phases = timer.phases()
                timing.record(agent_name, "execution", agent_elapsed,
                              response=content, step_num=step_num,
                              depends_on=depends_on, phases=phases)

                step_outputs[step_num] = f"[{agent_name}] {content}"

            wall_s = time.perf_counter() - t0
            summary = timing.summary()
            result = {
                "query_id": q["id"],
                "domain": q["domain"],
                "complexity": q["complexity"],
                "pattern": "plan_execute",
                "backend": backend,
                "model": model,
                "repetition": rep,
                "wall_s": round(wall_s, 4),
                "planner_failed": False,
                **summary,
            }
            results.append(result)

            # Print summary line
            phase_str = ""
            if "total_init_s" in summary:
                phase_str = (f" init={summary['total_init_s']:.1f}s"
                             f" warmup={summary['total_warmup_s']:.1f}s"
                             f" tool_exec={summary['total_exec_s']:.1f}s")
            print(
                f"plan={summary['planning_s']:.1f}s "
                f"exec_seq={summary['execution_seq_s']:.1f}s "
                f"exec_par={summary['execution_par_s']:.1f}s "
                f"agents={summary['num_agent_calls']} "
                f"dispatch%_seq={summary['dispatch_fraction_seq']:.0%} "
                f"dispatch%_par={summary['dispatch_fraction_par']:.0%}"
                f"{phase_str}"
            )

            # Write per-query log
            log_dir = output_path.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{q['id']}_rep{rep}.log"
            with open(log_file, "w") as lf:
                lf.write(f"Query ID:    {q['id']}\n")
                lf.write(f"Domain:      {q['domain']}\n")
                lf.write(f"Complexity:  {q['complexity']}\n")
                lf.write(f"Backend:     {backend}\n")
                lf.write(f"Model:       {model}\n")
                lf.write(f"Repetition:  {rep}/{repeats}\n")
                lf.write(f"Wall time:   {wall_s:.4f}s\n")
                lf.write(f"\n{'='*72}\n")
                lf.write(f"USER QUERY:\n{q['query']}\n")
                for j, step_data in enumerate(timing.steps):
                    lf.write(f"\n{'='*72}\n")
                    deps = step_data.get('depends_on', [])
                    dep_str = f" depends_on={deps}" if deps else ""
                    lf.write(f"STEP {step_data.get('step_num', j+1)}: [{step_data['node']}] "
                             f"({step_data['category']}, {step_data['elapsed_s']:.4f}s)"
                             f"{dep_str}\n")
                    phases = step_data.get("phases", {})
                    if phases:
                        lf.write(f"  Phases: init={phases.get('init_s', 0):.2f}s "
                                 f"warmup={phases.get('warmup_s', 0):.2f}s "
                                 f"exec={phases.get('exec_s', 0):.2f}s\n")
                        for tc in phases.get("tool_calls", []):
                            lf.write(f"    tool: {tc['name']} ({tc['duration_s']:.2f}s)\n")
                    lf.write(f"{'-'*72}\n")
                    lf.write(f"{step_data['response']}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {output_path}")


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plan-and-Execute pattern dispatch latency benchmark"
    )
    parser.add_argument("--model", default=None,
                        help="Model name (auto-set per backend if omitted)")
    parser.add_argument(
        "--backend", choices=["ollama", "claude", "ollama-sdk"], default="ollama",
        help="LLM backend: ollama (LangGraph + Ollama), claude (Agent SDK), "
             "or ollama-sdk (local model via Agent SDK)",
    )
    parser.add_argument(
        "--repeats", type=int, default=3, help="Repetitions per query"
    )
    parser.add_argument(
        "--queries",
        default=None,
        help="Comma-separated query IDs to run (e.g. Q01,Q03). Default: all.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (default: auto-generated from model/tokens)",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=-1,
        help="Max output tokens per LLM call (-1 = unlimited, default; ollama only)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=5,
        help="Max agentic turns per agent (SDK backends only, default: 5)",
    )
    parser.add_argument(
        "--results-dir", default=None,
        help="Base directory for results and workspaces (default: <script_dir>/results)",
    )
    args = parser.parse_args()

    # Default model per backend
    if args.model is None:
        args.model = {
            "ollama": "qwen3.5:9b",
            "claude": "claude-sonnet-4-20250514",
            "ollama-sdk": "gemma4:e2b",
        }[args.backend]

    qids = args.queries.split(",") if args.queries else None

    # Resolve results base directory to absolute path
    script_dir = Path(__file__).resolve().parent
    results_base = Path(args.results_dir).resolve() if args.results_dir else script_dir / "results"

    # Auto-generate output path from backend + model + max_tokens
    model_tag = args.model.replace(":", "_").replace("/", "_")
    tok_tag = f"tok{args.max_tokens}" if args.max_tokens > 0 else "tokunlim"
    run_dir = results_base / f"{args.backend}_{model_tag}_{tok_tag}"
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = run_dir / "plan_execute.json"

    print(f"=== Plan-and-Execute Pattern Benchmark ===")
    print(f"Backend: {args.backend} | Model: {args.model} | Repeats: {args.repeats}")
    print(f"Results: {results_base}")
    print(f"Queries: {qids or 'all'}\n")

    if args.backend == "ollama":
        run_benchmark(args.model, args.repeats, qids, output_path,
                      max_tokens=args.max_tokens)
    else:
        asyncio.run(run_benchmark_sdk(
            args.model, args.backend, args.repeats, qids, output_path,
            results_base=results_base, max_turns=args.max_turns,
        ))
