#!/usr/bin/env python3
"""
bench_supervisor.py — Supervisor pattern dispatch latency benchmark.

Measures two-way latency split:
  1. Supervisor LLM time — one LLM call per routing decision (dispatch)
  2. Agent execution time — per-agent LLM calls

In the supervisor pattern, planning + routing are fused into every supervisor
LLM call.  The supervisor sees full message history, so later calls pay
a compounding context cost.

Usage:
    python bench_supervisor.py --model qwen3.5:9b --repeats 3
    python bench_supervisor.py --model qwen3.5:9b --queries Q01,Q03,Q06
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict

from agents import AGENTS, get_agent_descriptions
from queries import QUERIES

OLLAMA_URL = "http://localhost:11434"


# ── Timing infrastructure ──────────────────────────────────────────


class TimingCollector:
    """Records per-node timing with category labels."""

    def __init__(self):
        self.records: list[dict] = []

    def record(self, node: str, category: str, elapsed_s: float):
        self.records.append(
            {"node": node, "category": category, "elapsed_s": round(elapsed_s, 6)}
        )

    def reset(self):
        self.records = []

    def summary(self) -> dict:
        dispatch = sum(
            r["elapsed_s"] for r in self.records if r["category"] == "dispatch"
        )
        execution = sum(
            r["elapsed_s"] for r in self.records if r["category"] == "execution"
        )
        total = dispatch + execution
        return {
            "dispatch_s": round(dispatch, 4),
            "execution_s": round(execution, 4),
            "total_s": round(total, 4),
            "dispatch_fraction": round(dispatch / total, 4) if total > 0 else 0,
            "num_dispatch_calls": sum(
                1 for r in self.records if r["category"] == "dispatch"
            ),
            "num_agent_calls": sum(
                1 for r in self.records if r["category"] == "execution"
            ),
            "detail": list(self.records),
        }


timing = TimingCollector()


# ── Graph state ────────────────────────────────────────────────────


class State(TypedDict):
    messages: Annotated[list, add_messages]


# ── Supervisor prompt ──────────────────────────────────────────────

AGENT_LIST = get_agent_descriptions()

SUPERVISOR_SYSTEM = f"""You are a task supervisor for a scientific computing orchestration system. Given a user query, decide which specialist agent should handle the NEXT step.

Available agents:
{AGENT_LIST}

Rules:
- Respond with ONLY the agent name (exactly as listed) or FINISH.
- Choose one agent per turn. After each agent reports back, you decide the next.
- Choose FINISH when the task has been adequately addressed.
- Do NOT explain your reasoning. Output ONLY the agent name or FINISH."""


# ── Graph construction ─────────────────────────────────────────────


def build_supervisor_graph(llm: ChatOllama):
    """Build a supervisor LangGraph with timing instrumentation."""

    def supervisor_node(state: State) -> dict:
        """Supervisor LLM call — counts as dispatch overhead."""
        t0 = time.perf_counter()
        messages = [SystemMessage(content=SUPERVISOR_SYSTEM)] + state["messages"]
        response = llm.invoke(messages)
        elapsed = time.perf_counter() - t0
        timing.record("supervisor", "dispatch", elapsed)
        return {"messages": [response]}

    def route_supervisor(state: State) -> str:
        """Parse supervisor output to extract agent name or FINISH."""
        last_msg = state["messages"][-1].content.strip()
        # Check for FINISH
        if "FINISH" in last_msg.upper():
            return "FINISH"
        # Case-insensitive agent name matching
        lower = last_msg.lower()
        for agent_name in AGENTS:
            if agent_name.lower() in lower:
                return agent_name
        # Can't parse → end to avoid infinite loop
        return "FINISH"

    def make_agent_node(name: str, system_prompt: str):
        """Agent node: receives original query + prior agent results (filtered).

        We filter out the supervisor's raw routing messages (e.g. "DataReader")
        so the agent gets a clean prompt comparable to plan-and-execute agents.
        """

        def node(state: State) -> dict:
            # Extract original query (first human message)
            original_query = state["messages"][0].content
            # Collect prior agent results (skip supervisor routing messages)
            prior_results = []
            for msg in state["messages"][1:]:
                if hasattr(msg, "content") and msg.content.startswith("["):
                    prior_results.append(msg.content)

            context = f"Original query: {original_query}"
            if prior_results:
                context += "\n\nPrior agent results:\n" + "\n".join(prior_results)
            context += f"\n\nYou are {name}. Perform your role for this query."

            t0 = time.perf_counter()
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=context),
            ]
            response = llm.invoke(messages)
            elapsed = time.perf_counter() - t0
            timing.record(name, "execution", elapsed)
            return {"messages": [AIMessage(content=f"[{name}] {response.content}")]}

        return node

    # ── Build graph ────────────────────────────────────────────────
    #
    #  START → supervisor ─┬→ Agent1 → supervisor
    #                       ├→ Agent2 → supervisor
    #                       └→ FINISH → END

    builder = StateGraph(State)
    builder.add_node("supervisor", supervisor_node)

    routing_map: dict[str, str] = {"FINISH": END}
    for name, info in AGENTS.items():
        builder.add_node(name, make_agent_node(name, info["system_prompt"]))
        builder.add_edge(name, "supervisor")  # after agent → back to supervisor
        routing_map[name] = name

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", route_supervisor, routing_map)

    return builder.compile()


# ── Benchmark runner ───────────────────────────────────────────────


def warmup(llm: ChatOllama):
    """Warm up the model to avoid cold-start bias on first query."""
    print("  Warming up model...", end=" ", flush=True)
    llm.invoke([HumanMessage(content="Say OK.")])
    print("done.")


def run_benchmark(
    model: str, repeats: int, query_ids: list[str] | None, output_path: Path,
    max_tokens: int = 512,
):
    llm = ChatOllama(model=model, base_url=OLLAMA_URL, temperature=0,
                     num_predict=max_tokens)
    graph = build_supervisor_graph(llm)
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
                graph.invoke(
                    {"messages": [HumanMessage(content=query["query"])]},
                    config={"recursion_limit": 25},
                )
            except Exception as e:
                print(f"ERROR: {e}")
                continue
            wall_s = time.perf_counter() - t0

            summary = timing.summary()
            result = {
                "query_id": query["id"],
                "domain": query["domain"],
                "complexity": query["complexity"],
                "pattern": "supervisor",
                "model": model,
                "repetition": rep,
                "wall_s": round(wall_s, 4),
                **summary,
            }
            results.append(result)
            print(
                f"dispatch={summary['dispatch_s']:.1f}s "
                f"exec={summary['execution_s']:.1f}s "
                f"calls={summary['num_dispatch_calls']}d/{summary['num_agent_calls']}a "
                f"dispatch%={summary['dispatch_fraction']:.0%}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {output_path}")


# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Supervisor pattern dispatch latency benchmark"
    )
    parser.add_argument("--model", default="qwen3.5:9b", help="Ollama model name")
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
        default="results/supervisor_results.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=512,
        help="Max output tokens per LLM call (bounds execution time)",
    )
    args = parser.parse_args()

    qids = args.queries.split(",") if args.queries else None

    print(f"=== Supervisor Pattern Benchmark ===")
    print(f"Model: {args.model} | Repeats: {args.repeats} | Max tokens: {args.max_tokens}")
    print(f"Queries: {qids or 'all'}\n")
    run_benchmark(args.model, args.repeats, qids, Path(args.output),
                  max_tokens=args.max_tokens)
