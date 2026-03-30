"""Generate natural language dispatch requests from ParEval prompts.

Takes ParEval's 420 C++ code generation prompts and converts them into
natural language HPC requests suitable for Pythia's intent detector.

Traceability: §6.1 HPC-CG workload
"""

import json
import re
import sys
from pathlib import Path

PAREVAL_PROMPTS = Path(__file__).parent / "../../benchmarks/ParEval/prompts/generation-prompts.json"
OUTPUT_FILE = Path(__file__).parent / "hpc_cg_requests.json"

# Map ParEval problem types to human-readable descriptions
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

# Map ParEval parallelism models to natural language
PARALLELISM_NAMES = {
    "serial": "sequential C++",
    "omp": "OpenMP",
    "mpi": "MPI",
    "mpi+omp": "MPI with OpenMP",
    "cuda": "CUDA",
    "hip": "AMD HIP",
    "kokkos": "Kokkos",
}

# HPC-relevant parallelism models (skip serial, cuda, hip, kokkos for now)
HPC_MODELS = {"mpi", "omp", "mpi+omp"}


def extract_task_description(prompt_text: str) -> str:
    """Extract the task description from C++ block comments."""
    comments = re.findall(r"/\*(.+?)\*/", prompt_text, re.DOTALL)
    if not comments:
        return ""

    desc = comments[0].strip()
    # Clean up: remove "Use OpenMP/MPI..." instruction since we'll add our own
    desc = re.sub(
        r"\s*Use (OpenMP|MPI|AMD HIP|CUDA|Kokkos|MPI and OpenMP).*?(?=\.|$)",
        "",
        desc,
        flags=re.DOTALL,
    )
    # Remove example sections
    desc = re.sub(r"\s*Example:.*", "", desc, flags=re.DOTALL)
    # Remove "Assume MPI/Kokkos has already been initialized"
    desc = re.sub(r"\s*Assume \w+ has already been.*", "", desc, flags=re.DOTALL)
    # Clean whitespace
    desc = re.sub(r"\s+", " ", desc).strip()
    # Remove trailing period duplicates
    desc = desc.rstrip(".")
    return desc


def generate_natural_language_request(
    task_desc: str,
    problem_type: str,
    parallelism_model: str,
    name: str,
) -> str:
    """Generate a natural language request from ParEval metadata + description."""
    ptype = PROBLEM_TYPE_NAMES.get(problem_type, problem_type)
    pmodel = PARALLELISM_NAMES.get(parallelism_model, parallelism_model)

    # Clean up the task name for readability
    clean_name = name.split("_", 2)[-1] if "_" in name else name
    clean_name = clean_name.replace("_", " ")

    # Build natural language request
    if task_desc:
        request = (
            f"Write a parallel {pmodel} implementation for the following "
            f"{ptype} task: {task_desc}. "
            f"The code should be correct, efficient, and handle edge cases."
        )
    else:
        request = (
            f"Write a parallel {pmodel} implementation for {clean_name} "
            f"({ptype}). The code should be correct, efficient, and handle edge cases."
        )

    return request


def main():
    if not PAREVAL_PROMPTS.exists():
        print(f"Error: ParEval prompts not found at {PAREVAL_PROMPTS}")
        print("Clone ParEval first: git clone https://github.com/parallelcodefoundry/ParEval.git")
        sys.exit(1)

    with open(PAREVAL_PROMPTS) as f:
        prompts = json.load(f)

    print(f"Loaded {len(prompts)} ParEval prompts")

    # Filter to HPC-relevant models
    hpc_prompts = [p for p in prompts if p["parallelism_model"] in HPC_MODELS]
    print(f"Filtered to {len(hpc_prompts)} HPC-relevant prompts (MPI, OpenMP, MPI+OMP)")

    requests = []
    for p in hpc_prompts:
        task_desc = extract_task_description(p["prompt"])
        nl_request = generate_natural_language_request(
            task_desc,
            p["problem_type"],
            p["parallelism_model"],
            p["name"],
        )

        requests.append({
            "id": f"{p['parallelism_model']}_{p['name']}",
            "request": nl_request,
            "original_prompt": p["prompt"],
            "metadata": {
                "source": "ParEval",
                "problem_type": p["problem_type"],
                "parallelism_model": p["parallelism_model"],
                "name": p["name"],
                "original_prompt_length": len(p["prompt"]),
            },
            # Ground truth for evaluation
            "expected": {
                "task_type": "hpc_code_gen",
                "domain_tags_should_include": _expected_domain_tags(p["parallelism_model"]),
                "min_agents": 2,  # At minimum: coder + reviewer
            },
        })

    with open(OUTPUT_FILE, "w") as f:
        json.dump(requests, f, indent=2)

    print(f"\nGenerated {len(requests)} requests -> {OUTPUT_FILE}")

    # Print summary
    from collections import Counter
    model_counts = Counter(r["metadata"]["parallelism_model"] for r in requests)
    type_counts = Counter(r["metadata"]["problem_type"] for r in requests)

    print("\nBy parallelism model:")
    for m, c in model_counts.most_common():
        print(f"  {m}: {c}")

    print("\nBy problem type:")
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")

    # Show 3 sample requests
    print("\n--- Sample requests ---")
    for r in requests[:3]:
        print(f"\nID: {r['id']}")
        print(f"Request: {r['request']}")
        print(f"Expected: {r['expected']}")


def _expected_domain_tags(parallelism_model: str) -> list[str]:
    """What domain tags should the intent detector find?"""
    tags = ["hpc"]
    if "mpi" in parallelism_model:
        tags.append("mpi")
    if "omp" in parallelism_model:
        tags.append("openmp")
    return tags


if __name__ == "__main__":
    main()
