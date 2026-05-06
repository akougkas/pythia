"""
queries.py — Load dispatch requests from workload JSON files.

Provides the QUERIES list consumed by bench_plan_execute.py,
bench_supervisor.py, debug_plan_execute.py, and test_planner.py.

Each entry has: id, domain, complexity, query (text), and optional
source/metadata fields.

Usage:
    from queries import QUERIES                          # default: hpc_cg
    from queries import load_requests, load_workload, load_by_name

    # Single workload by name
    qs = load_by_name("sdp")

    # Mixed workload (all three, shuffled)
    qs = load_by_name("mixed", limit=20, seed=42)

    # Single workload by path
    qs = load_workload("workloads/hpc_cg/hpc_cg_requests.json")

    # Multiple workloads by path
    qs = load_requests([
        "workloads/hpc_cg/hpc_cg_requests.json",
        "workloads/sdp/sdp_requests.json",
    ])
"""

from __future__ import annotations

import json
import random
from pathlib import Path

_WORKLOADS_DIR = Path(__file__).parent / "workloads"

# Named workloads: name → JSON path relative to workloads/
# WORKLOAD_REGISTRY: dict[str, str] = {
#     "hpc_cg": "hpc_cg/hpc_cg_requests.json",
#     "sdp": "sdp/sdp_requests.json",
#     "rwa": "rwa/rwa_requests.json",
# }
WORKLOAD_REGISTRY: dict[str, str] = {
    "hpc_cg": "hpc_cg/hpc_cg_test.json",
    "sdp": "sdp/sdp_test.json",
    "rwa": "rwa/rwa_test.json",
}

# Default workload files to load
_DEFAULT_WORKLOADS = [
    WORKLOAD_REGISTRY["hpc_cg"],
]

# Map ParEval problem types to a complexity estimate for bench compatibility.
# Generation prompts don't carry explicit complexity, so we infer from
# problem type characteristics.
_COMPLEXITY_MAP = {
    "transform": "simple",
    "reduce": "simple",
    "search": "simple",
    "histogram": "simple",
    "scan": "medium",
    "sort": "medium",
    "graph": "medium",
    "geometry": "medium",
    "dense_la": "complex",
    "sparse_la": "complex",
    "fft": "complex",
    "stencil": "complex",
}


def _normalize(entry: dict) -> dict:
    """Normalize a workload JSON entry to the bench-expected format.

    Bench scripts expect: id, domain, complexity, query.
    Workload JSONs use:   id, request, metadata.{problem_type, ...}.
    """
    meta = entry.get("metadata", {})

    return {
        "id": entry["id"],
        "domain": meta.get("domain", "hpc"),
        "complexity": meta.get("complexity", _COMPLEXITY_MAP.get(
            meta.get("problem_type", ""), "medium"
        )),
        "query": entry.get("original_prompt", entry.get("request", entry.get("query", ""))),
        # Preserve extra fields for analysis
        "source": meta.get("source", ""),
        "prompt_type": meta.get("prompt_type", ""),
        "problem_type": meta.get("problem_type", ""),
        "parallelism_model": meta.get("parallelism_model", ""),
        "original_prompt": entry.get("original_prompt", ""),
        "expected": entry.get("expected", {}),
    }


def load_workload(path: str | Path) -> list[dict]:
    """Load a single workload JSON file and normalize entries."""
    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = _WORKLOADS_DIR / filepath

    if not filepath.exists():
        raise FileNotFoundError(
            f"Workload file not found: {filepath}\n"
            f"Run the corresponding generate_requests.py first."
        )

    with open(filepath) as f:
        raw = json.load(f)

    return [_normalize(entry) for entry in raw]


def load_requests(workload_paths: list[str | Path] | None = None) -> list[dict]:
    """Load and merge multiple workload JSON files.

    Args:
        workload_paths: List of paths relative to workloads/ dir,
                        or absolute paths. Defaults to _DEFAULT_WORKLOADS.
    """
    if workload_paths is None:
        workload_paths = _DEFAULT_WORKLOADS

    queries: list[dict] = []
    for wp in workload_paths:
        queries.extend(load_workload(wp))

    return queries


def load_by_name(
    name: str,
    limit: int | None = None,
    seed: int = 42,
) -> list[dict]:
    """Load workload(s) by name.

    Args:
        name: One of "hpc_cg", "sdp", "rwa", or "mixed" (all three, shuffled).
        limit: Cap the number of requests (randomly sampled after shuffle).
               Only meaningful for "mixed" mode but works with any workload.
        seed: Random seed for shuffle/sampling.

    Returns:
        List of normalized query dicts.
    """
    if name == "mixed":
        paths = list(WORKLOAD_REGISTRY.values())
    elif name in WORKLOAD_REGISTRY:
        paths = [WORKLOAD_REGISTRY[name]]
    else:
        raise ValueError(
            f"Unknown workload '{name}'. "
            f"Choose from: {', '.join(list(WORKLOAD_REGISTRY) + ['mixed'])}"
        )

    queries = load_requests(paths)

    if name == "mixed":
        rng = random.Random(seed)
        rng.shuffle(queries)

    if limit and limit < len(queries):
        rng = random.Random(seed)
        queries = queries[:limit]

    return queries


# Default export: load hpc_cg workload
QUERIES = load_requests()
