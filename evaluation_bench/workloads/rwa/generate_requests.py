"""Generate natural language dispatch requests from PaperBench tasks.

Converts PaperBench's paper replication tasks into natural language
requests suitable for Pythia's intent detector.

PaperBench tasks involve: literature understanding, experimental design,
code generation, experiment execution, and result analysis — full
research workflow automation.

Traceability: §6.1 RWA workload
"""

import json
import os
import sys
from pathlib import Path

PAPERBENCH_DIR = Path(__file__).parent / "../../benchmarks/preparedness/project/paperbench/data/papers"
OUTPUT_FILE = Path(__file__).parent / "rwa_requests.json"


def count_subtasks(task: dict) -> int:
    """Recursively count all subtasks in a rubric tree."""
    count = 0
    for st in task.get("sub_tasks", []):
        count += 1
        count += count_subtasks(st)
    return count


def extract_top_level_steps(task: dict) -> list[str]:
    """Extract top-level subtask requirements as pipeline steps."""
    steps = []
    for st in task.get("sub_tasks", []):
        req = st.get("requirements", "")
        if req:
            steps.append(req[:200])
    return steps


def determine_rwa_pipeline(steps: list[str]) -> list[str]:
    """Determine which agents are needed for a research workflow.

    RWA pipelines:
    - literature_reviewer: understand paper, extract key contributions
    - experiment_designer: design replication experiments
    - code_generator: implement the method
    - experiment_runner: execute experiments, collect results
    - result_analyzer: compare results, write report
    """
    all_text = " ".join(s.lower() for s in steps)
    agents = []

    # Literature understanding
    if any(kw in all_text for kw in ["paper", "model", "dataset", "pre-trained",
                                      "understand", "reproduced", "available"]):
        agents.append("literature_reviewer")

    # Experiment design
    if any(kw in all_text for kw in ["experiment", "setup", "config", "hyperparameter",
                                      "design", "baseline", "architecture"]):
        agents.append("experiment_designer")

    # Code generation
    if any(kw in all_text for kw in ["implement", "code", "train", "script",
                                      "function", "class", "model"]):
        agents.append("code_generator")

    # Experiment execution
    if any(kw in all_text for kw in ["run", "execute", "train", "evaluat",
                                      "test", "benchmark"]):
        agents.append("experiment_runner")

    # Result analysis
    if any(kw in all_text for kw in ["result", "compar", "report", "analyz",
                                      "accuracy", "metric", "table", "figure"]):
        agents.append("result_analyzer")

    # Minimum 3 agents for RWA
    if len(agents) < 3:
        defaults = ["literature_reviewer", "code_generator", "result_analyzer"]
        for d in defaults:
            if d not in agents:
                agents.append(d)
            if len(agents) >= 3:
                break

    return agents


def generate_request(paper_name: str, rubric: dict) -> dict:
    """Generate a Pythia dispatch request from a PaperBench rubric."""
    requirements = rubric.get("requirements", "")
    top_steps = extract_top_level_steps(rubric)
    total_subtasks = count_subtasks(rubric)
    agents = determine_rwa_pipeline(top_steps)

    # Clean paper name for display
    display_name = paper_name.replace("-", " ").title()

    # Build natural language request
    request = (
        f"Replicate the research paper '{display_name}': {requirements} "
        f"This involves {len(top_steps)} major phases and "
        f"{total_subtasks} total subtasks. "
        f"The workflow includes: {'; '.join(top_steps[:3])}."
    )

    # Determine complexity from subtask count
    if total_subtasks <= 20:
        complexity = "moderate"
    elif total_subtasks <= 50:
        complexity = "complex"
    else:
        complexity = "very_complex"

    return {
        "id": f"rwa_{paper_name}",
        "request": request,
        "metadata": {
            "source": "PaperBench",
            "paper_name": paper_name,
            "display_name": display_name,
            "n_top_steps": len(top_steps),
            "n_total_subtasks": total_subtasks,
            "complexity": complexity,
            "category": rubric.get("task_category"),
            "fine_category": rubric.get("finegrained_task_category"),
        },
        "expected": {
            "task_type": "research_workflow",
            "domain_tags_should_include": ["research", "ml"],
            "min_agents": len(agents),
            "pipeline": agents,
        },
        "ground_truth": {
            "top_level_steps": top_steps,
            "total_subtasks": total_subtasks,
        },
    }


def main():
    if not PAPERBENCH_DIR.exists():
        print(f"Error: PaperBench not found at {PAPERBENCH_DIR}")
        print("Clone preparedness repo first")
        sys.exit(1)

    papers = sorted([
        d for d in os.listdir(PAPERBENCH_DIR)
        if os.path.isdir(PAPERBENCH_DIR / d) and not d.startswith(".")
    ])

    print(f"Found {len(papers)} PaperBench papers")

    requests = []
    for paper in papers:
        rubric_path = PAPERBENCH_DIR / paper / "rubric.json"
        if not rubric_path.exists():
            print(f"  Skipping {paper} (no rubric.json)")
            continue

        with open(rubric_path) as f:
            rubric = json.load(f)

        req = generate_request(paper, rubric)
        requests.append(req)

        subtasks = req["metadata"]["n_total_subtasks"]
        pipeline = req["expected"]["pipeline"]
        print(f"  {paper}: {subtasks} subtasks → {len(pipeline)} agents")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"\nGenerated {len(requests)} RWA requests → {OUTPUT_FILE}")

    # Stats
    from collections import Counter
    complexities = Counter(r["metadata"]["complexity"] for r in requests)
    pipelines = Counter(len(r["expected"]["pipeline"]) for r in requests)

    print(f"\nBy complexity: {dict(complexities)}")
    print(f"By pipeline size: {dict(pipelines)}")

    # Samples
    print("\n--- Sample requests ---")
    for r in requests[:2]:
        print(f"\nID: {r['id']}")
        print(f"Request: {r['request'][:200]}...")
        print(f"Pipeline: {r['expected']['pipeline']}")


if __name__ == "__main__":
    main()
