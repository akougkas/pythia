#!/usr/bin/env python3
"""Stream planner output token-by-token so you can see thinking + response."""

import requests
import json
import sys
import time

from agents import get_agent_descriptions
from queries import QUERIES

AGENT_LIST = get_agent_descriptions()

PLANNER_SYSTEM = f"""You are a task planner for a scientific computing orchestration system. Given a query, decompose it into ordered steps and assign each step to exactly one specialist agent from the pool.

Available agents:
{AGENT_LIST}

You MUST respond with ONLY a JSON array. No explanation, no markdown fences.
Each step must include "depends_on" — a list of step numbers that must complete before this step can start. Use an empty list [] if the step has no dependencies.
Example format:
[{{"step": 1, "task": "Analyze the algorithm", "agent": "hpc_planner", "depends_on": []}}, {{"step": 2, "task": "Write the code", "agent": "hpc_coder", "depends_on": [1]}}]
"""

query_id = sys.argv[1] if len(sys.argv) > 1 else "Q01"
query = next((q for q in QUERIES if q["id"] == query_id), None)
if not query:
    print(f"Unknown query: {query_id}")
    sys.exit(1)

print(f"Query: {query_id} — {query['query'][:80]}...")
print(f"Streaming response:\n{'─' * 70}")

t0 = time.perf_counter()
resp = requests.post("http://localhost:11434/api/chat", json={
    "model": "qwen3.5:9b",
    "stream": True,
    "messages": [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": query["query"]},
    ],
}, stream=True)

total_tokens = 0
for line in resp.iter_lines():
    if line:
        chunk = json.loads(line)
        token = chunk.get("message", {}).get("content", "")
        total_tokens += 1
        sys.stdout.write(token)
        sys.stdout.flush()
        if chunk.get("done"):
            break

elapsed = time.perf_counter() - t0
print(f"\n{'─' * 70}")
print(f"Tokens: {total_tokens} | Time: {elapsed:.1f}s | Speed: {total_tokens/elapsed:.0f} tok/s")
