"""Generate SDP dispatch requests from KramaBench tasks for motivation benchmarks.

Reads KramaBench workload JSONs from .scratch_src/KramaBench/workload/,
copies them into a local data/ folder, and generates natural-language
requests for Pythia's dispatch latency profiling.

Two modes:
  --mode verify   Select a small safe subset for quick testing
  --mode full     All SDP tasks (default)

Optionally limit output with --limit N.

Source: KramaBench (already cloned to .scratch_src/KramaBench/)
Traceability: motivation_bench workload generation for dispatch latency profiling.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

KRAMA_DIR = Path(__file__).parents[3] / ".scratch_src" / "KramaBench" / "workload"
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = Path(__file__).parent / "sdp_requests.json"

# Map KramaBench domains to Pythia-relevant categories
DOMAIN_MAP = {
    "wildfire": "environmental_science",
    "astronomy": "astronomy",
    "biomedical": "biomedical",
    "legal": "legal_analytics",
    "environment": "environmental_science",
    "archeology": "archeology",
}

# Workload files to process (skip tiny/quickstart variants)
WORKLOAD_FILES = [
    "wildfire.json",
    "astronomy.json",
    "biomedical.json",
    "legal.json",
    "environment.json",
    "archeology.json",
]

# ── Verification subset: safe tasks with clear answers ──────────────
# Pick one from each domain for a quick sanity check.
VERIFY_SELECTION = [
    ("wildfire", "easy"),
    ("environment", "easy"),
    ("legal", "easy"),
    ("biomedical", "easy"),
    ("astronomy", "easy"),
]


def copy_workload_files() -> None:
    """Copy KramaBench workload JSONs into local data/ folder."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename in WORKLOAD_FILES:
        src = KRAMA_DIR / filename
        dst = DATA_DIR / filename
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {filename} → data/")
        elif not src.exists():
            print(f"  Warning: {src} not found, skipping")


def estimate_pipeline_complexity(task: dict) -> str:
    """Estimate pipeline complexity from subtask count and data sources."""
    n_subtasks = len(task.get("subtasks", []))
    n_sources = len(task.get("data_sources", []))

    if n_subtasks <= 3 and n_sources <= 1:
        return "simple"
    elif n_subtasks <= 6 and n_sources <= 3:
        return "moderate"
    else:
        return "complex"


def determine_agent_pipeline(task: dict) -> list[str]:
    """Determine which agents are needed based on task structure.

    SDP pipelines use different agents than HPC-CG:
    - data_discovery: find and load relevant datasets
    - data_wrangler: clean, transform, join data
    - analyst: statistical analysis and computation
    - reporter: summarize findings, produce answer
    """
    subtasks = task.get("subtasks", [])
    n_sources = len(task.get("data_sources", []))
    steps = [st.get("step", "").lower() for st in subtasks]

    agents = []

    # Always need discovery if multiple sources
    if n_sources > 1 or any("load" in s or "read" in s or "find" in s for s in steps):
        agents.append("data_discovery")

    # Wrangling if cleaning/transforming
    if any(kw in " ".join(steps) for kw in ["clean", "transform", "convert", "merge",
                                              "join", "filter", "dissolve", "parse", "wrangle"]):
        agents.append("data_wrangler")

    # Analysis if computation
    if any(kw in " ".join(steps) for kw in ["compute", "calculate", "sum", "average",
                                              "count", "correlat", "regress", "statistic",
                                              "sort", "rank", "compare"]):
        agents.append("analyst")

    # Always need reporter for final answer
    agents.append("reporter")

    # Minimum 2 agents
    if len(agents) < 2:
        agents.insert(0, "data_discovery")

    return agents


def generate_request(task: dict, domain: str) -> dict:
    """Generate a Pythia dispatch request from a KramaBench task."""
    complexity = estimate_pipeline_complexity(task)
    agents = determine_agent_pipeline(task)

    query = task["query"]
    n_sources = len(task.get("data_sources", []))
    n_subtasks = len(task.get("subtasks", []))

    request = (
        f"Analyze the following scientific data pipeline task: {query} "
        f"This requires working with {n_sources} data source(s) "
        f"and involves approximately {n_subtasks} processing steps. "
        f"Domain: {domain.replace('_', ' ')}."
    )

    return {
        "id": task["id"],
        "request": request,
        "metadata": {
            "source": "KramaBench",
            "domain": domain,
            "answer_type": task.get("answer_type", "unknown"),
            "n_subtasks": n_subtasks,
            "n_data_sources": n_sources,
            "complexity": complexity,
            "data_sources": task.get("data_sources", []),
        },
        "expected": {
            "task_type": "data_pipeline",
            "domain_tags_should_include": ["data", domain],
            "min_agents": len(agents),
            "pipeline": agents,
        },
        "ground_truth": {
            "answer": str(task.get("answer", "")),
            "answer_type": task.get("answer_type", "unknown"),
            "subtasks": [st.get("step", "") for st in task.get("subtasks", [])],
        },
    }


def load_all_tasks() -> list[tuple[dict, str]]:
    """Load all tasks from workload files. Returns (task, domain) pairs."""
    all_tasks = []
    for filename in WORKLOAD_FILES:
        filepath = KRAMA_DIR / filename
        if not filepath.exists():
            print(f"  Skipping {filename} (not found)")
            continue

        domain = filename.replace(".json", "")
        domain = DOMAIN_MAP.get(domain, domain)

        with open(filepath) as f:
            tasks = json.load(f)

        print(f"  {filename}: {len(tasks)} tasks -> domain={domain}")
        for task in tasks:
            all_tasks.append((task, domain))

    return all_tasks


def select_verify_subset(all_tasks: list[tuple[dict, str]]) -> list[dict]:
    """Pick one easy task per raw domain for verification."""
    selected = []
    seen_ids: set[str] = set()
    for raw_domain, difficulty in VERIFY_SELECTION:
        domain = DOMAIN_MAP.get(raw_domain, raw_domain)
        match = next(
            (t for t, d in all_tasks
             if d == domain and difficulty in t.get("id", "")
             and raw_domain in t.get("id", "")
             and t["id"] not in seen_ids),
            None,
        )
        if match:
            seen_ids.add(match["id"])
            selected.append(generate_request(match, domain))
        else:
            print(f"  Warning: no match for ({raw_domain}, {difficulty})")
    return selected


def select_full(
    all_tasks: list[tuple[dict, str]],
    limit: int | None = None,
    seed: int = 42,
) -> list[dict]:
    """Build full request set from all tasks."""
    requests = [generate_request(task, domain) for task, domain in all_tasks]

    if limit and limit < len(requests):
        rng = random.Random(seed)
        requests = rng.sample(requests, limit)

    return requests


def print_summary(requests: list[dict]) -> None:
    """Print distribution stats."""
    domains = Counter(r["metadata"]["domain"] for r in requests)
    complexities = Counter(r["metadata"]["complexity"] for r in requests)
    pipelines = Counter(len(r["expected"]["pipeline"]) for r in requests)

    print(f"\nBy domain: {dict(domains)}")
    print(f"By complexity: {dict(complexities)}")
    print(f"By pipeline size: {dict(pipelines)}")

    print("\n--- Sample requests ---")
    for r in requests[:3]:
        print(f"\n  ID: {r['id']}")
        print(f"  Request: {r['request'][:150]}...")
        print(f"  Pipeline: {r['expected']['pipeline']}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate SDP requests from KramaBench for motivation benchmarks"
    )
    parser.add_argument(
        "--mode",
        choices=["verify", "full"],
        default="full",
        help="verify: small safe subset; full: all SDP tasks (default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of requests (randomly sampled). Only applies in full mode.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling when --limit is used (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help=f"Output JSON path (default: {OUTPUT_FILE})",
    )
    args = parser.parse_args()

    if not KRAMA_DIR.exists():
        print(f"Error: KramaBench workloads not found at {KRAMA_DIR}")
        print("Ensure KramaBench is cloned to .scratch_src/KramaBench/")
        sys.exit(1)

    # Copy workload JSONs to local data/ folder
    print("Copying KramaBench workload files...")
    copy_workload_files()

    print("\nLoading tasks...")
    all_tasks = load_all_tasks()

    if not all_tasks:
        print("Error: No tasks loaded.")
        sys.exit(1)

    if args.mode == "verify":
        requests = select_verify_subset(all_tasks)
        print(f"\nVerification mode: selected {len(requests)} safe tasks")
    else:
        requests = select_full(all_tasks, args.limit, args.seed)
        print(f"\nFull mode: {len(requests)} tasks")

    with open(args.output, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"Output -> {args.output}")
    print_summary(requests)


if __name__ == "__main__":
    main()
