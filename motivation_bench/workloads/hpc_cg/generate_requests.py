"""Generate HPC code-generation dispatch requests from ParEval prompts.

Reads ParEval's generation-prompts and translation-prompts, filters to
HPC-relevant parallelism models (OpenMP, MPI, MPI+OpenMP), and produces
natural-language requests for Pythia's motivation benchmarks.

Two modes:
  --mode verify   Select 5 safe tasks (no iteration/convergence risk)
  --mode full     All HPC tasks (default)

Optionally limit output with --limit N.

Traceability: motivation_bench workload generation for dispatch latency profiling.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

PAREVAL_DIR = Path(__file__).parents[3] / ".scratch_src" / "ParEval" / "prompts"
GENERATION_PROMPTS = PAREVAL_DIR / "generation-prompts.json"
TRANSLATION_PROMPTS = PAREVAL_DIR / "translation-prompts.json"
OUTPUT_FILE = Path(__file__).parent / "hpc_cg_requests.json"

# ── Parallelism models to include (no serial, no accelerator) ─────────

HPC_MODELS = {"omp", "mpi", "mpi+omp"}

# ── Problem type metadata ─────────────────────────────────────────────

PROBLEM_TYPE_NAMES = {
    "dense_la": "dense linear algebra",
    "sparse_la": "sparse linear algebra",
    "fft": "Fast Fourier Transform",
    "geometry": "computational geometry",
    "graph": "graph algorithm",
    "histogram": "histogram computation",
    "reduce": "parallel reduction",
    "scan": "prefix scan",
    "search": "parallel search",
    "sort": "parallel sorting",
    "stencil": "stencil computation",
    "transform": "element-wise transformation",
}

PARALLELISM_NAMES = {
    "omp": "OpenMP",
    "mpi": "MPI",
    "mpi+omp": "MPI with OpenMP",
}

# ── Verification subset: safe tasks unlikely to cause infinite loops ──
# Strategy: pick from problem types with clear termination (no iteration,
# no convergence criteria). One per parallelism model spread.

VERIFY_SELECTION = [
    # (problem_type, parallelism_model) — pick first matching task
    ("reduce", "omp"),
    ("transform", "mpi"),
    ("sort", "mpi+omp"),
    ("search", "omp"),
    ("histogram", "mpi"),
]


def extract_task_description(prompt_text: str) -> str:
    """Extract the task description from C++ block comments."""
    comments = re.findall(r"/\*(.+?)\*/", prompt_text, re.DOTALL)
    if not comments:
        return ""

    desc = comments[0].strip()
    # Remove parallelism instructions — we add our own
    desc = re.sub(
        r"\s*Use (OpenMP|MPI|AMD HIP|CUDA|Kokkos|MPI and OpenMP).*?(?=\.|$)",
        "",
        desc,
        flags=re.DOTALL,
    )
    desc = re.sub(r"\s*Example:.*", "", desc, flags=re.DOTALL)
    desc = re.sub(r"\s*Assume \w+ has already been.*", "", desc, flags=re.DOTALL)
    desc = re.sub(r"\s+", " ", desc).strip().rstrip(".")
    return desc


def generate_nl_request(
    task_desc: str,
    problem_type: str,
    parallelism_model: str,
    prompt_type: str,
) -> str:
    """Build a natural-language request from ParEval metadata."""
    ptype = PROBLEM_TYPE_NAMES.get(problem_type, problem_type)
    pmodel = PARALLELISM_NAMES.get(parallelism_model, parallelism_model)

    if prompt_type == "translation":
        if task_desc:
            return (
                f"Translate the following serial C++ {ptype} code to a parallel "
                f"{pmodel} implementation: {task_desc}. "
                f"The code should be correct, efficient, and handle edge cases."
            )
        return (
            f"Translate the provided serial C++ code to a parallel {pmodel} "
            f"implementation ({ptype}). The code should be correct and efficient."
        )

    # generation
    if task_desc:
        return (
            f"Write a parallel {pmodel} implementation for the following "
            f"{ptype} task: {task_desc}. "
            f"The code should be correct, efficient, and handle edge cases."
        )
    return (
        f"Write a parallel {pmodel} implementation for a {ptype} task. "
        f"The code should be correct, efficient, and handle edge cases."
    )


def build_request(prompt: dict, prompt_type: str) -> dict:
    """Convert a single ParEval prompt into a dispatch request."""
    task_desc = extract_task_description(prompt["prompt"])
    nl_request = generate_nl_request(
        task_desc,
        prompt["problem_type"],
        prompt["parallelism_model"],
        prompt_type,
    )

    prefix = "gen" if prompt_type == "generation" else "trans"
    request_id = f"{prefix}_{prompt['parallelism_model']}_{prompt['name']}"

    domain_tags = ["hpc"]
    if "mpi" in prompt["parallelism_model"]:
        domain_tags.append("mpi")
    if "omp" in prompt["parallelism_model"]:
        domain_tags.append("openmp")

    return {
        "id": request_id,
        "request": nl_request,
        "original_prompt": prompt["prompt"],
        "metadata": {
            "source": "ParEval",
            "prompt_type": prompt_type,
            "problem_type": prompt["problem_type"],
            "parallelism_model": prompt["parallelism_model"],
            "name": prompt["name"],
            "original_prompt_length": len(prompt["prompt"]),
        },
        "expected": {
            "task_type": "hpc_code_gen",
            "domain_tags_should_include": domain_tags,
            "min_agents": 2,  # At minimum: coder + reviewer
        },
    }


def load_hpc_prompts() -> tuple[list[dict], list[dict]]:
    """Load and filter ParEval prompts to HPC-relevant models."""
    gen_prompts: list[dict] = []
    trans_prompts: list[dict] = []

    if GENERATION_PROMPTS.exists():
        with open(GENERATION_PROMPTS) as f:
            raw = json.load(f)
        gen_prompts = [p for p in raw if p["parallelism_model"] in HPC_MODELS]
        print(f"Generation prompts: {len(raw)} total → {len(gen_prompts)} HPC")
    else:
        print(f"Warning: {GENERATION_PROMPTS} not found, skipping generation prompts")

    if TRANSLATION_PROMPTS.exists():
        with open(TRANSLATION_PROMPTS) as f:
            raw = json.load(f)
        trans_prompts = [p for p in raw if p["parallelism_model"] in HPC_MODELS]
        print(f"Translation prompts: {len(raw)} total → {len(trans_prompts)} HPC")
    else:
        print(f"Warning: {TRANSLATION_PROMPTS} not found, skipping translation prompts")

    return gen_prompts, trans_prompts


def select_verify_subset(gen_prompts: list[dict]) -> list[dict]:
    """Pick 5 safe tasks for verification (generation only)."""
    selected = []
    for ptype, pmodel in VERIFY_SELECTION:
        match = next(
            (p for p in gen_prompts
             if p["problem_type"] == ptype and p["parallelism_model"] == pmodel),
            None,
        )
        if match:
            selected.append(build_request(match, "generation"))
        else:
            print(f"  Warning: no match for ({ptype}, {pmodel})")
    return selected


def select_full(
    gen_prompts: list[dict],
    trans_prompts: list[dict],
    limit: int | None = None,
    seed: int = 42,
) -> list[dict]:
    """Build full request set from both generation and translation prompts."""
    requests = []
    for p in gen_prompts:
        requests.append(build_request(p, "generation"))
    for p in trans_prompts:
        requests.append(build_request(p, "translation"))

    if limit and limit < len(requests):
        rng = random.Random(seed)
        requests = rng.sample(requests, limit)

    return requests


def print_summary(requests: list[dict]) -> None:
    """Print distribution stats."""
    prompt_types = Counter(r["metadata"]["prompt_type"] for r in requests)
    problem_types = Counter(r["metadata"]["problem_type"] for r in requests)
    par_models = Counter(r["metadata"]["parallelism_model"] for r in requests)

    print(f"\nBy prompt type: {dict(prompt_types)}")
    print(f"By parallelism model: {dict(par_models)}")
    print(f"By problem type:")
    for t, c in problem_types.most_common():
        print(f"  {t}: {c}")

    print("\n--- Sample requests ---")
    for r in requests[:3]:
        print(f"\n  ID: {r['id']}")
        print(f"  Request: {r['request'][:150]}...")
        print(f"  Type: {r['metadata']['prompt_type']}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate HPC-CG requests from ParEval for motivation benchmarks"
    )
    parser.add_argument(
        "--mode",
        choices=["verify", "full"],
        default="full",
        help="verify: 5 safe tasks for quick testing; full: all HPC tasks (default)",
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

    gen_prompts, trans_prompts = load_hpc_prompts()

    if not gen_prompts and not trans_prompts:
        print("Error: No ParEval prompts found. Clone ParEval into .scratch_src/ first.")
        sys.exit(1)

    if args.mode == "verify":
        requests = select_verify_subset(gen_prompts)
        print(f"\nVerification mode: selected {len(requests)} safe tasks")
    else:
        requests = select_full(gen_prompts, trans_prompts, args.limit, args.seed)
        print(f"\nFull mode: {len(requests)} tasks")

    with open(args.output, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"Output → {args.output}")
    print_summary(requests)


if __name__ == "__main__":
    main()
