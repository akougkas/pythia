# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'Bam': The core contributions of the paper "Batch and match: black-box variational inference with a score-based divergence" have been reproduced. This involves 4 major phases and 1020 total subtasks. The workflow includes: The core variational inference algorithms studie
> ... (469 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.467
- **Domain**: ml, research
- **Decomposability**: 0.45

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 37834ms (37.8s)

## Reasoning
This is a research replication workflow for a variational inference paper ('BAM'), spanning algorithm implementation, experiment execution, and results comparison across multiple figures/sections. The task decomposes into 4 natural phases: literature understanding → algorithm implementation → experiment execution → results analysis/reporting. Phases 1 and 2 have some parallelism (literature review and experiment design can overlap), while phases 3 and 4 are strictly sequential. Complexity is moderate (0.47) with well-scoped targets (Section 5.1, Figure 5.3, Figure E.6), so 6 agents cover all stages without over-engineering.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract core algorithms, divergence formulations, and experimental protocols from the BAM paper
- **Prompt**: Read and analyze the paper 'Batch and Match: Black-Box Variational Inference with a Score-Based Divergence' (BAM). Extract: (1) the score-based divergence formulation and how it differs from ELBO-based VI, (2) the BAM algorithm pseudocode and key hyperparameters (batch size, matching schedule, score estimator), (3) the experimental setup for Section 5.1 (models, baselines, metrics), (4) the experimental setup for Figures 5.3 and E.6 from Section 5.2 (what axes are plotted, what conditions vary), (5) any implementation details buried in appendices. Produce a structured summary with direct quotes for all equations and algorithm steps.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering Section 5.1, Figure 5.3, and Figure E.6
- **Prompt**: Using the extracted paper details, design a concrete replication plan for: (1) Section 5.1 — identify the probabilistic models used, define the baseline VI methods to compare against BAM, specify convergence metrics (ELBO, KL divergence, wall-clock time), and set random seeds/run counts for statistical validity. (2) Figure 5.3 — identify what is being varied (e.g., batch size, number of samples, step schedule) and what is measured on each axis; define the grid of hyperparameter values to sweep. (3) Figure E.6 — identify the appendix experiment conditions and define the data/model setup. Output a structured experiment manifest (JSON or YAML) listing each experiment ID, model, algorithm config, metric, and expected runtime.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the BAM algorithm and all VI baselines needed for replication
- **Prompt**: Implement the full BAM (Batch and Match) variational inference algorithm in Python using JAX or PyTorch (prefer JAX for autodiff consistency with the paper). Your implementation must include: (1) The score-based divergence estimator as defined in the paper (Stein discrepancy or score-matching variant — confirm from literature_reviewer output), (2) The batch-and-match update rule with configurable batch size and matching strategy, (3) Baseline VI methods: standard BBVI with REINFORCE, reparameterized gradient VI, and any other baselines used in Section 5.1, (4) The probabilistic models from Section 5.1 (e.g., Gaussian mixtures, logistic regression posteriors, or as specified), (5) Logging utilities that record per-iteration ELBO, gradient variance, and wall-clock time. Structure code as a reusable library with clear module separation (models/, algorithms/, metrics/). Include inline comments referencing paper equation numbers.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute all replication experiments for Section 5.1, Figure 5.3, and Figure E.6 and collect raw results
- **Prompt**: Using the implemented BAM code and experiment manifest, run all replication experiments: (1) Section 5.1 — run BAM and all baselines on each benchmark model for the specified number of iterations/seeds; save per-run metrics to CSV files in results/section_5_1/. (2) Figure 5.3 — run the hyperparameter sweep (vary batch size, step schedule, or matching frequency as designed); save results to results/figure_5_3/. (3) Figure E.6 — run the appendix experiment conditions; save to results/figure_E6/. For each experiment: log wall-clock time, final metric value, and convergence curve. If any run diverges or crashes, log the failure and continue. Produce a run_summary.json with pass/fail status per experiment ID.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator, experiment_designer

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replicated results against paper figures/tables and score reproduction fidelity
- **Prompt**: Analyze the collected experimental results and compare them to the paper's reported results: (1) Section 5.1 — extract the paper's reported numbers (mean ± std for each method/model) and compare to your replicated values; compute relative error and flag any discrepancies > 5%. (2) Figure 5.3 — overlay your replicated curve/scatter against the paper figure; assess whether trends (monotonicity, crossover points, saturation) are preserved even if absolute values differ slightly. (3) Figure E.6 — same overlay analysis for the appendix figure. Produce a fidelity scorecard: per-experiment reproduction status (✓ exact / ~ approximate / ✗ failed), likely causes for any deviations (seed sensitivity, missing implementation detail, hyperparameter ambiguity), and an overall replication confidence score (0–100).
- **Tokens**: 500 | Compute: light
- **Depends on**: experiment_runner

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [code_generator, experiment_designer] (parallel)
- Stage 2: [experiment_runner]
- Stage 3: [result_analyzer]
- Stage 4: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| **Total** | | | **10000** | |
