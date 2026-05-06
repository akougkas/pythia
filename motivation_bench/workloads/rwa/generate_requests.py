"""Generate RWA dispatch requests from PaperBench tasks for motivation benchmarks.

Reads PaperBench rubric.json files from .scratch_src/preparedness/,
copies them into a local data/ folder, and generates natural-language
requests for Pythia's dispatch latency profiling.

Two modes:
  --mode verify   Select a small safe subset for quick testing
  --mode full     All RWA tasks (default)

Optionally limit output with --limit N.

Source: PaperBench (already cloned to .scratch_src/preparedness/)
Traceability: motivation_bench workload generation for dispatch latency profiling.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

PAPERBENCH_DIR = Path(__file__).parents[3] / ".scratch_src" / "preparedness" / "project" / "paperbench" / "data" / "papers"
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = Path(__file__).parent / "rwa_requests.json"

# ── Verification subset: pick a few smaller papers for quick testing ──
VERIFY_SELECTION = [
    "pinn",
    "lbcs",
    "fre",
    "rice",
    "sapg",
]


def copy_rubric_files() -> None:
    """Copy PaperBench rubric.json files into local data/ folder."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    papers = sorted([
        d for d in os.listdir(PAPERBENCH_DIR)
        if os.path.isdir(PAPERBENCH_DIR / d) and not d.startswith(".")
    ])
    for paper in papers:
        src = PAPERBENCH_DIR / paper / "rubric.json"
        dst_dir = DATA_DIR / paper
        dst = dst_dir / "rubric.json"
        if src.exists() and not dst.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  Copied {paper}/rubric.json -> data/")
        elif not src.exists():
            print(f"  Warning: {paper}/rubric.json not found, skipping")


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

    if any(kw in all_text for kw in ["paper", "model", "dataset", "pre-trained",
                                      "understand", "reproduced", "available"]):
        agents.append("literature_reviewer")

    if any(kw in all_text for kw in ["experiment", "setup", "config", "hyperparameter",
                                      "design", "baseline", "architecture"]):
        agents.append("experiment_designer")

    if any(kw in all_text for kw in ["implement", "code", "train", "script",
                                      "function", "class", "model"]):
        agents.append("code_generator")

    if any(kw in all_text for kw in ["run", "execute", "train", "evaluat",
                                      "test", "benchmark"]):
        agents.append("experiment_runner")

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

    display_name = paper_name.replace("-", " ").title()

    request = (
        f"Replicate the research paper '{display_name}': {requirements} "
        f"This involves {len(top_steps)} major phases and "
        f"{total_subtasks} total subtasks. "
        f"The workflow includes: {'; '.join(top_steps[:3])}."
    )

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


def load_all_papers() -> list[tuple[str, dict]]:
    """Load all paper rubrics. Returns (paper_name, rubric) pairs."""
    papers = sorted([
        d for d in os.listdir(PAPERBENCH_DIR)
        if os.path.isdir(PAPERBENCH_DIR / d) and not d.startswith(".")
    ])

    all_papers = []
    for paper in papers:
        rubric_path = PAPERBENCH_DIR / paper / "rubric.json"
        if not rubric_path.exists():
            print(f"  Skipping {paper} (no rubric.json)")
            continue

        with open(rubric_path) as f:
            rubric = json.load(f)

        subtasks = count_subtasks(rubric)
        print(f"  {paper}: {subtasks} subtasks")
        all_papers.append((paper, rubric))

    return all_papers


def select_verify_subset(all_papers: list[tuple[str, dict]]) -> list[dict]:
    """Pick a few smaller papers for verification."""
    selected = []
    for paper_name in VERIFY_SELECTION:
        match = next(
            ((name, rubric) for name, rubric in all_papers if name == paper_name),
            None,
        )
        if match:
            selected.append(generate_request(match[0], match[1]))
        else:
            print(f"  Warning: no match for {paper_name}")
    return selected


def select_full(
    all_papers: list[tuple[str, dict]],
    limit: int | None = None,
    seed: int = 42,
) -> list[dict]:
    """Build full request set from all papers."""
    requests = [generate_request(name, rubric) for name, rubric in all_papers]

    if limit and limit < len(requests):
        rng = random.Random(seed)
        requests = rng.sample(requests, limit)

    return requests


def print_summary(requests: list[dict]) -> None:
    """Print distribution stats."""
    complexities = Counter(r["metadata"]["complexity"] for r in requests)
    pipelines = Counter(len(r["expected"]["pipeline"]) for r in requests)

    print(f"\nBy complexity: {dict(complexities)}")
    print(f"By pipeline size: {dict(pipelines)}")

    print("\n--- Sample requests ---")
    for r in requests[:2]:
        print(f"\n  ID: {r['id']}")
        print(f"  Request: {r['request'][:200]}...")
        print(f"  Pipeline: {r['expected']['pipeline']}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate RWA requests from PaperBench for motivation benchmarks"
    )
    parser.add_argument(
        "--mode",
        choices=["verify", "full"],
        default="full",
        help="verify: small safe subset; full: all RWA tasks (default)",
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

    if not PAPERBENCH_DIR.exists():
        print(f"Error: PaperBench not found at {PAPERBENCH_DIR}")
        print("Ensure preparedness repo is cloned to .scratch_src/preparedness/")
        sys.exit(1)

    # Copy rubric files to local data/ folder
    print("Copying PaperBench rubric files...")
    copy_rubric_files()

    print("\nLoading papers...")
    all_papers = load_all_papers()

    if not all_papers:
        print("Error: No papers loaded.")
        sys.exit(1)

    if args.mode == "verify":
        requests = select_verify_subset(all_papers)
        print(f"\nVerification mode: selected {len(requests)} tasks")
    else:
        requests = select_full(all_papers, args.limit, args.seed)
        print(f"\nFull mode: {len(requests)} tasks")

    with open(args.output, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"Output -> {args.output}")
    print_summary(requests)


if __name__ == "__main__":
    main()
