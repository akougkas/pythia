"""Generate natural language dispatch requests from KramaBench tasks.

Converts KramaBench's 104 data pipeline tasks into natural language
requests suitable for Pythia's intent detector.

KramaBench tasks involve: data discovery, wrangling, cleaning,
statistical reasoning, and orchestration of multi-step data pipelines.

Traceability: §6.1 SDP workload
"""

import json
import sys
from pathlib import Path

KRAMA_DIR = Path(__file__).parent / "../../benchmarks/KramaBench/workload"
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

    # Build natural language request
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


def main():
    if not KRAMA_DIR.exists():
        print(f"Error: KramaBench workloads not found at {KRAMA_DIR}")
        print("Clone KramaBench first")
        sys.exit(1)

    requests = []
    for filename in WORKLOAD_FILES:
        filepath = KRAMA_DIR / filename
        if not filepath.exists():
            print(f"  Skipping {filename} (not found)")
            continue

        domain = filename.replace(".json", "")
        domain = DOMAIN_MAP.get(domain, domain)

        with open(filepath) as f:
            tasks = json.load(f)

        print(f"  {filename}: {len(tasks)} tasks → domain={domain}")

        for task in tasks:
            req = generate_request(task, domain)
            requests.append(req)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"\nGenerated {len(requests)} SDP requests → {OUTPUT_FILE}")

    # Stats
    from collections import Counter
    domains = Counter(r["metadata"]["domain"] for r in requests)
    complexities = Counter(r["metadata"]["complexity"] for r in requests)
    pipelines = Counter(len(r["expected"]["pipeline"]) for r in requests)

    print(f"\nBy domain: {dict(domains)}")
    print(f"By complexity: {dict(complexities)}")
    print(f"By pipeline size: {dict(pipelines)}")

    # Samples
    print("\n--- Sample requests ---")
    for r in requests[:3]:
        print(f"\nID: {r['id']}")
        print(f"Request: {r['request'][:150]}...")
        print(f"Pipeline: {r['expected']['pipeline']}")


if __name__ == "__main__":
    main()
