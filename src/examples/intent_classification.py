"""Intent classification demo: natural-language prompt → structured Intent.

Compares RuleBasedIntentDetector vs SpacyIntentDetector vs LLMIntentDetector.

Run (rule-based only):
    cd src && python -m examples.intent_classification

Run (rule-based vs spaCy):
    cd src && python -m examples.intent_classification --spacy

Run (all three):
    cd src && python -m examples.intent_classification --spacy --llm

Run (rule-based vs LLM):
    cd src && python -m examples.intent_classification --llm --model qwen3.5:4b
"""

import argparse
import time

from pythia.intent import LLMIntentDetector, RuleBasedIntentDetector, SpacyIntentDetector


# # --- Previous prompt set (general coverage) ---
# SAMPLE_PROMPTS = [
#     # Simple, single-agent tasks
#     "Show me the variables in this NetCDF file",
#
#     # HPC workloads
#     "Write an MPI program to parallelize matrix multiplication on a GPU cluster using CUDA",
#     "Optimize the OpenMP loop for better vectorization on the Slurm cluster",
#
#     # Scientific data pipeline workloads
#     "Build a pipeline to convert HDF5 datasets to NetCDF format with validation",
#     "Ingest FITS astronomical data, transform to Zarr, and load into the analysis pipeline",
#
#     # Research writing workloads
#     "Review citations in the LaTeX manuscript and fix formatting",
#
#     # Complex scientific workflows (from ScienceAgentBench — no step markers)
#     (
#         "Analyze and visualize Elk movements in the GeoJSON dataset. Estimate home "
#         "ranges and assess habitat preferences using spatial analysis. Identify "
#         "spatial clusters and document findings with maps."
#     ),
#
#     # Request with constraints
#     "Use Claude to summarize the dataset, limit to 500 tokens, under $2",
#
#     # Ambiguous / general
#     "Help me understand why the simulation diverged at timestep 1000",
# ]

# --- §6.1 Workload-aligned prompt set ---
# Prompts derived from the four evaluation workload suites in §6.1.
# Tests whether intent classification behaves consistently across
# the actual workloads we will evaluate in the paper.

SAMPLE_PROMPTS = [
    # ── HPC Code Generation (HPC-CG) ──
    # Simple: single agent, one task
    "Write an OpenMP parallel loop for matrix multiply",
    # Medium: planner + coder, some decomposition
    "Generate MPI code to scatter a dataset across ranks and gather reduced results",
    # Complex: full pipeline — plan, code, test, review (fan-out after planning)
    (
        "Parallelize this CFD solver using MPI+OpenMP for a 64-node Slurm cluster. "
        "Write the job script, profile with HPCToolkit, and optimize the hotspot."
    ),
    # Conditional routing: profiling result drives next agent
    (
        "Profile the MPI application, identify whether the bottleneck is in "
        "communication or computation, and apply the appropriate optimization."
    ),

    # ── Scientific Data Pipelines (SDP) ──
    # Simple: single format read
    "Load this HDF5 file and list the dataset variables",
    # Medium: format conversion with validation
    "Convert the NetCDF climate dataset to Zarr format and validate checksums",
    # Complex: multi-stage pipeline across storage tiers
    (
        "Ingest the raw FITS observations, transform to HDF5, run quality-control "
        "checks, generate summary statistics, and archive to the object store."
    ),
    # I/O + compute coordination
    (
        "Read the ROOT event data from the distributed filesystem, filter by energy "
        "threshold, compute histograms on the GPU node, and save results as Parquet."
    ),

    # ── Research Workflow Automation (RWA) ──
    # Simple: single stage
    "Search for recent papers on speculative execution in multi-agent systems",
    # Medium: two loosely-coupled stages
    "Review the literature on LLM-based task planning and draft a related work section",
    # Complex: end-to-end workflow — literature → design → code → analysis
    (
        "Survey distributed scheduling algorithms, design an experiment comparing "
        "three heuristics, implement the simulator in Python, run the experiments "
        "on the cluster, and generate publication-quality figures."
    ),
    # High diversity: each stage needs different agent type
    (
        "Collect benchmark datasets from three repositories, preprocess and normalize "
        "them, train a baseline model, evaluate against published results, and write "
        "the experimental methodology section."
    ),

    # ── Dispatch Micro-benchmarks (DMB) ──
    # Trivial: single agent, minimal context
    "What is 2 + 2",
    # Single intent, explicit constraint
    "Use the local Llama model to summarize this log file, limit to 200 tokens",
    # Multi-agent DAG: tests decomposition detection at maximum complexity
    (
        "Deploy a three-stage pipeline: agent A preprocesses input, agent B runs "
        "inference on the GPU, agent C post-processes and validates output. "
        "Use under $5 total budget."
    ),
]


def _print_intent(intent, latency_ms: float | None = None) -> None:
    lat_str = f"  [{latency_ms:.0f}ms]" if latency_ms is not None else ""
    print(f"  task_type:        {intent.task_type}{lat_str}")
    thresh_note = "(< 0.3 → single agent)" if intent.complexity < 0.3 else "(≥ 0.3 → multi-agent)"
    print(f"  complexity:       {intent.complexity:.3f}  {thresh_note}")
    print(f"  domain_tags:      {intent.domain_tags or '(none)'}")
    print(f"  decomposability:  {intent.decomposability:.3f}")
    print(f"  constraints:      {intent.constraints or '(none)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pythia Intent Classification Demo")
    parser.add_argument("--spacy", action="store_true", help="Also run spaCy-enhanced detector")
    parser.add_argument("--llm", action="store_true", help="Also run LLM-based detector (requires Ollama)")
    parser.add_argument("--model", default="qwen3.5:4b", help="Ollama model name (default: qwen3.5:4b)")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    args = parser.parse_args()

    rule_detector = RuleBasedIntentDetector()
    spacy_detector = None
    llm_detector = None
    if args.spacy:
        spacy_detector = SpacyIntentDetector()
    if args.llm:
        llm_detector = LLMIntentDetector(model=args.model, base_url=args.base_url)
        print(f"LLM detector: model={args.model}, url={args.base_url}")

    modes = ["Rule-Based"]
    if spacy_detector:
        modes.append("spaCy")
    if llm_detector:
        modes.append("LLM")
    print("=" * 80)
    print(f"Pythia Intent Classifier — {' vs '.join(modes)}")
    print("=" * 80)

    for i, prompt in enumerate(SAMPLE_PROMPTS, 1):
        display = prompt if len(prompt) <= 75 else prompt[:72] + "..."

        print(f"\n{'─' * 80}")
        print(f"[{i}] \"{display}\"")
        print(f"{'─' * 80}")

        # Rule-based
        print()
        print("  [Rule-Based]")
        t0 = time.perf_counter()
        rule_intent = rule_detector.detect(prompt)
        rule_ms = (time.perf_counter() - t0) * 1000
        _print_intent(rule_intent, rule_ms)

        # spaCy-enhanced (if enabled)
        if spacy_detector:
            print()
            print("  [spaCy-Enhanced]")
            t0 = time.perf_counter()
            spacy_intent = spacy_detector.detect(prompt)
            spacy_ms = (time.perf_counter() - t0) * 1000
            _print_intent(spacy_intent, spacy_ms)

            # Only decomposability differs — show the delta
            dd = spacy_intent.decomposability - rule_intent.decomposability
            print(f"  Δ decomp (vs rule): {dd:+.3f}")

        # LLM-based (if enabled)
        if llm_detector:
            print()
            print("  [LLM-Based]")
            t0 = time.perf_counter()
            llm_intent = llm_detector.detect(prompt)
            llm_ms = (time.perf_counter() - t0) * 1000
            _print_intent(llm_intent, llm_ms)

            dc = llm_intent.complexity - rule_intent.complexity
            dd = llm_intent.decomposability - rule_intent.decomposability
            print()
            print(f"  Δ complexity:     {dc:+.3f}")
            print(f"  Δ decomposability:{dd:+.3f}")

    print(f"\n{'=' * 80}")
    print("Done.")


if __name__ == "__main__":
    main()
