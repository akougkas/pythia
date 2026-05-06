"""Wrap hpc_cg simple tasks into orchestration-heavy multi-agent briefs.

Reads `hpc_cg/hpc_cg_requests*.json` and produces a paired dataset where each
`request` is a realistic engineering brief — multiple deliverables, deployment
context, quality gates — that any sensible orchestrator would naturally split
across specialists. The dataset itself does not prescribe roles, stages, or a
dependency graph; that scaffolding belongs to the planner system prompt and
the evaluator, not to the task description.

Three modes mirror the source workload:
  --mode verify   wrap hpc_cg_requests_verify.json (5 safe tasks)
  --mode test     wrap hpc_cg_test.json (10-task smoke set)
  --mode full     wrap hpc_cg_requests.json (~288 tasks; default)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "hpc_cg"
OUT_DIR = Path(__file__).parent

INPUTS = {
    "verify": "hpc_cg_requests_verify.json",
    "test":   "hpc_cg_test.json",
    "full":   "hpc_cg_requests.json",
}
OUTPUTS = {
    "verify": "hpc_cg_multi_requests_verify.json",
    "test":   "hpc_cg_multi_test.json",
    "full":   "hpc_cg_multi_requests.json",
}

WRAP_VERSION = "v1"

CONTEXT_VARIANTS = [
    {"problem_scale": "small",  "n_elements": "1e6", "latency_budget_s":   5.0},
    {"problem_scale": "medium", "n_elements": "1e8", "latency_budget_s":  30.0},
    {"problem_scale": "large",  "n_elements": "1e9", "latency_budget_s": 120.0},
]

TEMPLATE = """\
We need a verified parallel implementation of the function stubbed below.

Target: a subset of the **Ares** cluster (see `cluster_ares.yaml` and the
companion files `storage_decision_guide.md` and `slurm_usage.md` staged in
the working directory) sized to fit a **{problem_scale}** workload (problem
size N ≈ {n_elements} elements) within a **{latency_budget_s} s** end-to-end
budget. You must derive the node count, rank/thread layout, fabric (10 GbE
vs RoCE -40g), and storage tier from the cluster files; do not invent
cluster facts that are not present in those files.

# What the team needs to deliver

- The implemented C++ function, compile-clean against the stub.
- A reference oracle and a test harness with small / medium / large inputs and
  edge cases (empty, singleton, degenerate, overflow / NaN where applicable),
  with tolerance assertions and deterministic seeding.
- A build recipe that justifies the compiler / MPI / OpenMP toolchain choice
  against the cluster files, and pins the exact module loads, flags, and
  dependencies. Treat unsnapshotted module versions as load-time-verified.
- A Slurm submission script with rank/thread layout and NUMA pinning, plus
  the env exports needed to reproduce the run. Use the correct hostname
  variant for the chosen fabric (see `slurm_usage.md`).
- A short performance writeup: expected bottleneck, strong-scaling or
  weak-scaling study design, profiling commands, and whether the latency
  budget is met under {problem_scale} scale. If the budget is not met,
  propose a tuning plan rather than declaring done.
- A review note that flags any inconsistency between the I/O contract, the
  algorithm choice, the implementation, the tests, and the perf numbers.{translation_bullet}

# Underlying coding task (verbatim)

{simple_request}

# Function stub (C++)

{original_prompt}

# Constraints

- All cluster-facing decisions (node count, hostnames, fabric, storage,
  toolchain, rank/thread layout, walltime estimate, memory budget) must be
  grounded in the staged files. Do not invent cluster facts.
- Tolerance and edge-case coverage must be explicit, not implied.
- Performance claims must be backed by a reproducible measurement plan,
  not assertions.
- The deliverables above are interdependent; inconsistency between them is
  a failure even if each in isolation looks correct.

## Output format

Begin the plan with an explicit **subtask decomposition table** before any
other content. Each row has these columns:

| id | title | role | depends_on | deliverable |
|----|-------|------|------------|-------------|

- **id** — `S1`, `S2`, ... (plan-unique).
- **title** — one-line imperative summary of the subtask.
- **role** — the specialist who would own this subtask end-to-end. Pick
  role names that fit the objective; two subtasks may share a role.
- **depends_on** — comma-separated subtask ids, or `—` if none. Two
  subtasks with the same predecessors and no edge between them may run in
  parallel.
- **deliverable** — one short noun phrase naming the concrete artifact
  this subtask produces.

Decompose the work into subtasks small enough that one specialist could
own each end-to-end. The number of subtasks, the role names, and the
dependency structure are your choice — pick what the objective actually
demands, no more and no less. Do not pad with subtasks that have no
deliverable.

After the table, write one detailed section per subtask. Each section
heading MUST reference the subtask id and MUST cite its predecessors,
e.g. `## S3 — Build recipe (consumes: S2)`. Sections must appear in
topological order of the table.

**Citations.** Every subtask whose decisions depend on cluster facts
(toolchain, hostname selection, fabric choice, storage tier, rank/thread
layout, walltime, memory budget, scheduler policy, ...) MUST cite the
specific file and section it relies on, e.g.
`cluster_ares.yaml:fabric.notes`, `storage_decision_guide.md` § Decision
rules #1, or `slurm_usage.md` § Hostname routing. Decisions without a
citation are ungrounded; the review subtask must flag them.

End with a short **Verification** section describing how to check the
deliverables end-to-end.
"""

TRANSLATION_BULLET = (
    "\n- An equivalence argument between the serial reference (the stub) and the\n"
    "  parallel implementation, plus differential-test inputs that would catch\n"
    "  divergence."
)


def pick_context(task_id: str) -> dict:
    """Deterministic per-task context selection (stable across runs/processes)."""
    digest = hashlib.sha256(task_id.encode()).digest()
    idx = int.from_bytes(digest[:8], "big") % len(CONTEXT_VARIANTS)
    return CONTEXT_VARIANTS[idx]


def render_request(simple_entry: dict, ctx: dict) -> str:
    is_translation = simple_entry["metadata"].get("prompt_type") == "translation"
    return TEMPLATE.format(
        simple_request=simple_entry["request"],
        original_prompt=simple_entry["original_prompt"],
        translation_bullet=TRANSLATION_BULLET if is_translation else "",
        **ctx,
    )


def wrap(simple_entry: dict) -> dict:
    ctx = pick_context(simple_entry["id"])
    return {
        "id": "multi_" + simple_entry["id"],
        "request": render_request(simple_entry, ctx),
        "simple_request": simple_entry["request"],
        "original_prompt": simple_entry["original_prompt"],
        "metadata": {
            **simple_entry["metadata"],
            "wrap_version": WRAP_VERSION,
            "context": ctx,
        },
        "expected": {
            "task_type": "hpc_code_gen_multi_agent",
            "domain_tags_should_include":
                simple_entry["expected"]["domain_tags_should_include"],
        },
    }


def print_summary(wrapped: list[dict]) -> None:
    contexts = Counter(w["metadata"]["context"]["problem_scale"] for w in wrapped)
    pmodels  = Counter(w["metadata"]["parallelism_model"] for w in wrapped)
    ptypes   = Counter(w["metadata"]["prompt_type"] for w in wrapped)

    avg_simple  = sum(len(w["simple_request"]) for w in wrapped) / max(len(wrapped), 1)
    avg_wrapped = sum(len(w["request"])        for w in wrapped) / max(len(wrapped), 1)

    print(f"\nBy context scale: {dict(contexts)}")
    print(f"By parallelism model: {dict(pmodels)}")
    print(f"By prompt type: {dict(ptypes)}")
    print(f"Avg request length: simple={avg_simple:.0f} chars, "
          f"wrapped={avg_wrapped:.0f} chars (x{avg_wrapped / max(avg_simple, 1):.1f})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wrap hpc_cg requests into multi-agent engineering briefs"
    )
    parser.add_argument("--mode", choices=list(INPUTS), default="full")
    parser.add_argument("--output", type=Path, default=None,
                        help="Override output path (default derived from --mode)")
    args = parser.parse_args()

    src_path = SRC_DIR / INPUTS[args.mode]
    if not src_path.exists():
        print(f"Error: source file not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    src = json.loads(src_path.read_text())
    wrapped = [wrap(e) for e in src]

    out_path = args.output or (OUT_DIR / OUTPUTS[args.mode])
    out_path.write_text(json.dumps(wrapped, indent=2))

    print(f"{args.mode}: {len(wrapped)} tasks wrapped")
    print(f"Source -> {src_path}")
    print(f"Output -> {out_path}")
    print_summary(wrapped)


if __name__ == "__main__":
    main()
