"""Generate complex Ares-targeted HPC dispatch requests.

Wraps the existing hpc_cg/ ParEval-derived tasks in a multi-stage
deployment-planning template designed to stretch planning latency on
strong models (Opus, GPT-5) and expose the planning-quality vs
planning-latency gap against weaker models.

Sources from ../hpc_cg/hpc_cg_requests*.json so the two workloads stay
paired 1:1: same task set, two prompt complexities. This pairing is the
controlled comparison that drives the motivation figure.

Usage:
    python generate_requests.py --mode verify   # 5 safe tasks
    python generate_requests.py --mode full     # all 288 tasks
    python generate_requests.py --mode full --limit 50 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SIMPLE_DIR = HERE.parent / "hpc_cg"
SIMPLE_FULL = SIMPLE_DIR / "hpc_cg_requests.json"
SIMPLE_VERIFY = SIMPLE_DIR / "hpc_cg_requests_verify.json"

TEMPLATE_FILE = HERE / "prompt_template.md"
CLUSTER_FILE = HERE / "cluster_ares.yaml"

OUTPUT_FULL = HERE / "hpc_cg_complex_requests.json"
OUTPUT_VERIFY = HERE / "hpc_cg_complex_requests_verify.json"

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
    "mpi+omp": "MPI + OpenMP (hybrid)",
}

# Problem sizes per problem type, chosen so the smallest fits in single-rank
# memory, the medium roughly fills one Ares node, and the largest forces
# multi-node decomposition + NVMe staging.
PROBLEM_SIZES = {
    "reduce":    "N ∈ {10^6 doubles (≈8 MB), 10^8 (≈800 MB), 10^10 (≈80 GB)}",
    "transform": "N ∈ {10^6 elements, 10^8, 10^10}",
    "scan":      "N ∈ {10^6 elements, 10^8, 10^10}",
    "sort":      "N ∈ {10^6 elements, 10^8, 5×10^9} (sort needs ~2× working memory)",
    "search":    "N ∈ {10^6 elements, 10^8, 10^10}",
    "histogram": "N ∈ {10^7 pixels, 10^9, 5×10^10}",
    "stencil":   "Grid ∈ {1024^3 (≈8 GB FP64), 2048^3 (≈64 GB), 4096^3 (≈512 GB, out-of-core)}",
    "fft":       "N ∈ {2^24 complex (≈256 MB), 2^28 (≈4 GB), 2^32 (≈64 GB)}",
    "dense_la":  "Matrix N×N ∈ {N=10000 (≈800 MB), N=30000 (≈7.2 GB), N=80000 (≈51 GB)}",
    "sparse_la": "Non-zeros ∈ {nnz=10^7, nnz=10^9, nnz=10^10}",
    "graph":     "Vertices ∈ {V=10^6, V=10^8, V=10^9}",
    "geometry":  "Points ∈ {N=10^6, N=10^8, N=10^9}",
}


def extract_task_description(simple_request: str) -> str:
    """Pull the human-readable task description out of the simple request.

    The simple request looks like:
      "Write a parallel OpenMP implementation for the following <type> task:
       <description>. The code should be correct, efficient, and handle
       edge cases."
    We isolate <description>.
    """
    text = simple_request
    # Strip the framing prefix and suffix.
    for marker in ("task: ", "computation task: ", "implementation ("):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    text = text.replace(
        "The code should be correct, efficient, and handle edge cases.", ""
    ).replace(
        "The code should be correct and efficient.", ""
    )
    return text.strip().rstrip(".")


def load_template() -> tuple[str, str]:
    if not TEMPLATE_FILE.exists():
        sys.exit(f"Missing template: {TEMPLATE_FILE}")
    if not CLUSTER_FILE.exists():
        sys.exit(f"Missing cluster block: {CLUSTER_FILE}")
    return TEMPLATE_FILE.read_text(), CLUSTER_FILE.read_text().strip()


def render_request(simple: dict, template: str, cluster_block: str) -> str:
    meta = simple["metadata"]
    ptype = meta["problem_type"]
    pmodel = meta["parallelism_model"]

    task_desc = extract_task_description(simple["request"]) or "(no task description provided)"
    sizes = PROBLEM_SIZES.get(
        ptype,
        "small / medium / large (define yourself based on the kernel's working-set scaling)",
    )

    rendered = template
    rendered = rendered.replace("{{CLUSTER_BLOCK}}", cluster_block)
    rendered = rendered.replace("{{KERNEL_NAME}}", meta["name"])
    rendered = rendered.replace(
        "{{PROBLEM_TYPE_NAME}}", PROBLEM_TYPE_NAMES.get(ptype, ptype)
    )
    rendered = rendered.replace(
        "{{PARALLELISM_MODEL_NAME}}", PARALLELISM_NAMES.get(pmodel, pmodel)
    )
    rendered = rendered.replace("{{PROMPT_TYPE}}", meta["prompt_type"])
    rendered = rendered.replace("{{TASK_DESCRIPTION}}", task_desc)
    rendered = rendered.replace("{{PROBLEM_SIZES}}", sizes)
    rendered = rendered.replace(
        "{{ORIGINAL_PROMPT}}", simple["original_prompt"].strip()
    )
    return rendered


def build_request(simple: dict, template: str, cluster_block: str) -> dict:
    meta = simple["metadata"]
    nl_request = render_request(simple, template, cluster_block)

    domain_tags = ["hpc", "ares", "deployment_plan"]
    if "mpi" in meta["parallelism_model"]:
        domain_tags.append("mpi")
    if "omp" in meta["parallelism_model"]:
        domain_tags.append("openmp")

    return {
        "id": f"complex_{simple['id']}",
        "request": nl_request,
        "original_prompt": simple["original_prompt"],
        "simple_request": simple["request"],
        "metadata": {
            "source": "ParEval+Ares",
            "paired_simple_id": simple["id"],
            "prompt_type": meta["prompt_type"],
            "problem_type": meta["problem_type"],
            "parallelism_model": meta["parallelism_model"],
            "name": meta["name"],
            "original_prompt_length": meta["original_prompt_length"],
            "complex_prompt_length": len(nl_request),
            "cluster_target": "Ares",
            "problem_sizes": PROBLEM_SIZES.get(meta["problem_type"]),
        },
        "expected": {
            "task_type": "hpc_deployment_plan",
            "domain_tags_should_include": domain_tags,
            "min_agents": 5,
            "min_stages": 5,
            "must_address": [
                "ares_node_subset_choice",
                "rank_thread_decomposition",
                "memory_arithmetic_per_problem_size",
                "nvme_tier_vs_raid_routing",
                "roce_vs_tcp_justification",
                "strong_and_weak_scaling",
            ],
        },
    }


def load_simple(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(
            f"Missing source workload: {path}\n"
            f"Run hpc_cg/generate_requests.py first."
        )
    with open(path) as f:
        return json.load(f)


def print_summary(requests: list[dict], simple: list[dict]) -> None:
    pt = Counter(r["metadata"]["prompt_type"] for r in requests)
    pm = Counter(r["metadata"]["parallelism_model"] for r in requests)
    types = Counter(r["metadata"]["problem_type"] for r in requests)

    complex_lens = [r["metadata"]["complex_prompt_length"] for r in requests]
    simple_lens = [len(r["request"]) for r in simple]

    avg_complex = sum(complex_lens) // max(len(complex_lens), 1)
    avg_simple = sum(simple_lens) // max(len(simple_lens), 1)
    expansion = avg_complex / max(avg_simple, 1)

    print(f"\nBy prompt type: {dict(pt)}")
    print(f"By parallelism model: {dict(pm)}")
    print(f"By problem type:")
    for t, c in types.most_common():
        print(f"  {t}: {c}")
    print(
        f"\nPrompt length — simple avg: {avg_simple} chars, "
        f"complex avg: {avg_complex} chars (×{expansion:.1f})"
    )

    if requests:
        sample = requests[0]
        print(f"\n--- Sample (first 600 chars of first complex request) ---")
        print(f"ID: {sample['id']}")
        print(f"Paired simple ID: {sample['metadata']['paired_simple_id']}")
        print()
        print(sample["request"][:600] + "...")


def main():
    parser = argparse.ArgumentParser(
        description="Generate complex Ares-targeted HPC dispatch requests "
        "by wrapping the existing hpc_cg/ tasks in a multi-stage planning template."
    )
    parser.add_argument(
        "--mode",
        choices=["verify", "full"],
        default="full",
        help="verify: 5 safe tasks; full: all paired tasks (default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of requests (random sample, full mode only)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output path (default: hpc_cg_complex_requests[_verify].json)",
    )
    args = parser.parse_args()

    template, cluster_block = load_template()

    if args.mode == "verify":
        simple = load_simple(SIMPLE_VERIFY)
        out_path = args.output or OUTPUT_VERIFY
    else:
        simple = load_simple(SIMPLE_FULL)
        out_path = args.output or OUTPUT_FULL

    requests = [build_request(s, template, cluster_block) for s in simple]

    if args.mode == "full" and args.limit and args.limit < len(requests):
        rng = random.Random(args.seed)
        requests = rng.sample(requests, args.limit)

    print(f"\n{args.mode.capitalize()} mode: {len(requests)} tasks "
          f"(sourced from {len(simple)} simple requests)")

    with open(out_path, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"Output → {out_path}")
    print_summary(requests, simple)


if __name__ == "__main__":
    main()
