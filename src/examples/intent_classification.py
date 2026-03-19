"""Intent classification demo: natural-language prompt → structured Intent.

Shows how RuleBasedIntentDetector classifies user prompts into task types,
extracts domain tags, estimates complexity/decomposability, and detects constraints.

Run:
    cd src && python -m examples.intent_classification
"""

from pythia.intent import RuleBasedIntentDetector


SAMPLE_PROMPTS = [
    # # HPC workloads
    # "Write an MPI program to parallelize matrix multiplication on a GPU cluster using CUDA",
    # "Optimize the OpenMP loop for better vectorization on the Slurm cluster",

    # # Scientific data pipeline workloads
    # "Build a pipeline to convert HDF5 datasets to NetCDF format with validation",
    # "Ingest FITS astronomical data, transform to Zarr, and load into the analysis pipeline",

    # # Research writing workloads
    # "Draft the abstract and literature review section for my paper on distributed computing",
    # "Review citations in the LaTeX manuscript and fix formatting",

    # # Multi-step complex request
    # "1. First, profile the MPI application on the GPU cluster. "
    # "2. Then identify the bottleneck in the CUDA kernel. "
    # "3. After that, rewrite the kernel with shared memory optimization. "
    # "4. Finally, benchmark the new version against the baseline.",

    # # Request with constraints
    # "Use Claude to summarize the dataset, limit to 500 tokens, under $2",

    # # Unknown / general
    # "What is the weather today?",
    # "Tell me a joke about programming",
    
    "Parallelize this CG solver code (cg_solver.cpp) for a 128-node AMD EPYC cluster. Use MPI+OpenMP. Write the Slurm job script. Profile and optimize."
]


def main() -> None:
    detector = RuleBasedIntentDetector()

    print("=" * 80)
    print("Pythia Intent Classifier — Prompt Classification Demo")
    print("=" * 80)

    for i, prompt in enumerate(SAMPLE_PROMPTS, 1):
        intent = detector.detect(prompt)

        # Truncate long prompts for display
        display = prompt if len(prompt) <= 75 else prompt[:72] + "..."

        print(f"\n{'─' * 80}")
        print(f"[{i}] \"{display}\"")
        print(f"{'─' * 80}")
        print(f"  task_type:        {intent.task_type}")
        print(f"  complexity:       {intent.complexity:.3f}  {'(< 0.3 → single agent)' if intent.complexity < 0.3 else '(≥ 0.3 → multi-agent pipeline)'}")
        print(f"  domain_tags:      {intent.domain_tags or '(none)'}")
        print(f"  decomposability:  {intent.decomposability:.3f}")
        print(f"  constraints:      {intent.constraints or '(none)'}")

    # # Show what happens downstream
    # print(f"\n{'=' * 80}")
    # print("Downstream: how AgentSelector uses complexity threshold")
    # print("=" * 80)

    # from pythia.solver import AgentSelector
    # selector = AgentSelector()

    # for label, prompt in [
    #     ("Simple",  "Fix the bug"),
    #     ("Complex", "Write an MPI program with CUDA to parallelize the HDF5 data processing pipeline"),
    # ]:
    #     intent = detector.detect(prompt)
    #     agents = selector.select_agents(intent)
    #     agent_types = [a.agent_type for a in agents]
    #     print(f"\n  {label} (complexity={intent.complexity:.3f}, task_type={intent.task_type}):")
    #     print(f"    → agents selected: {agent_types}")


if __name__ == "__main__":
    main()
