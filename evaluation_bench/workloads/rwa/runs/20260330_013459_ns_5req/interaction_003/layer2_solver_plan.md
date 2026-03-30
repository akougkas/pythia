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
- **Time**: 50521ms (50.5s)

## Reasoning
This is a research replication workflow for a variational inference paper ('BAM'), already partially decomposed into 4 phases. The task spans literature understanding, algorithm implementation, and experiment replication across two result sections (5.1, 5.2 with Figures 5.3 and E.6). Phases 1 (literature review + experiment design) can run in parallel since they are independent planning stages; code generation depends on both; experiment runners for Section 5.1 and Section 5.2 can run in parallel after implementation; result analysis and reporting are terminal stages.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> tester -> experiment_runner

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract BAM algorithm details, score-based divergence formulation, and experimental setup from the paper
- **Prompt**: Read and analyze the paper 'Batch and Match: Black-Box Variational Inference with a Score-Based Divergence' (BAM). Extract: (1) The core variational inference objective and how the score-based divergence (e.g., Fisher divergence or kernel Stein discrepancy) replaces the standard ELBO. (2) The BAM algorithm pseudocode — batch construction, matching step, and gradient estimator. (3) The specific experimental configurations for Section 5.1 (likely benchmark VI tasks) and Section 5.2 (Figures 5.3 and E.6 — likely posterior approximation quality or convergence plots). (4) Baselines compared against (e.g., ADVI, BBVI, SVGD). (5) Hyperparameters: learning rates, batch sizes, number of iterations, kernel choices. Output a structured summary covering each of these five areas with direct quotes or equations from the paper where possible.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the replication experiment plan covering all four phases and mapping subtasks to code modules
- **Prompt**: Design a complete replication experiment plan for the BAM paper ('Batch and Match: Black-Box Variational Inference with a Score-Based Divergence'). Structure the plan into 4 phases: Phase 1 — Core VI algorithm implementation (BAM optimizer, score-based divergence estimator, variational family). Phase 2 — Section 5.1 replication (identify the benchmark tasks, metrics reported, table/figure targets). Phase 3 — Section 5.2 replication for Figure 5.3 (identify what is plotted: convergence curves, KL divergence, or sample quality vs. iteration). Phase 4 — Section 5.2 replication for Figure E.6 (appendix figure — identify if this is an ablation, sensitivity analysis, or extended benchmark). For each phase specify: input data or distributions needed, expected outputs, success criteria (numeric match within tolerance), and any known implementation pitfalls for score-based VI methods. Output a phased experiment blueprint.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the BAM variational inference algorithm and all supporting experimental infrastructure
- **Prompt**: Implement the complete BAM ('Batch and Match') variational inference system based on the literature review and experiment design. Required modules: (1) `bam_core.py` — The BAM optimizer implementing the score-based divergence objective. Include the batch construction loop, the matching/coupling step between particles or samples, and the gradient estimator. Support both Gaussian and more flexible variational families. (2) `score_estimator.py` — Estimate the score function (gradient of log density) for the target distribution, supporting both analytic and automatic differentiation paths. (3) `vi_baselines.py` — Implement ADVI and standard BBVI baselines for comparison in Section 5.1. (4) `experiment_5_1.py` — Experiment runner for Section 5.1 benchmarks (e.g., log-normal, Student-t, or hierarchical model posteriors as used in the paper). (5) `experiment_5_2.py` — Experiment runner for Figures 5.3 and E.6 from Section 5.2. (6) `plotting.py` — Reproduce exact figure layouts matching the paper. Use PyTorch or JAX. Include docstrings, inline comments explaining correspondence to paper equations, and parameter defaults matching the paper.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer, experiment_designer

### 4. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Validate BAM implementation correctness with unit and integration tests before running full experiments
- **Prompt**: Write and run a test suite for the BAM variational inference implementation. Tests must cover: (1) Unit test for score estimator — verify score function output matches analytic gradients for a standard Gaussian target (tolerance 1e-4). (2) Unit test for BAM batch construction — verify batches are correctly sampled and the matching step produces valid couplings. (3) Integration test — run BAM for 100 iterations on a 2D Gaussian target and verify the variational approximation converges (KL divergence decreasing). (4) Regression test for baselines — verify ADVI and BBVI produce results within known ranges on the same 2D Gaussian. (5) Smoke test for experiment runners — run `experiment_5_1.py` and `experiment_5_2.py` for 10 iterations each without errors. Report pass/fail status per test with error messages for any failures.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_generator

### 5. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute Section 5.2 experiments to replicate Figures 5.3 and E.6
- **Prompt**: Run the full Section 5.2 experiments from the BAM paper replication targeting Figures 5.3 and E.6. Using `experiment_5_2.py`: (1) For Figure 5.3 — execute the experiment series that produces the plotted quantity (e.g., approximation quality vs. number of iterations, or comparison across model dimensions). Use identical axis ranges, method labels, and color conventions as the paper figure. (2) For Figure E.6 (appendix) — execute the ablation or extended experiment shown, which may vary a hyperparameter (kernel bandwidth, batch size, or matching distance). (3) Run with paper-specified seeds and hyperparameters. (4) Save figures to `figures/fig_5_3_replicated.pdf` and `figures/fig_E6_replicated.pdf`. (5) Save raw data to `results/section_5_2.json`. Report any qualitative or quantitative differences from the paper figures.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: tester

## Execution DAG
- Stage 0: [experiment_designer, literature_reviewer] (parallel)
- Stage 1: [code_generator]
- Stage 2: [tester]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]
- Stage 5: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 2000 | medium |
| **Total** | | | **10000** | |
