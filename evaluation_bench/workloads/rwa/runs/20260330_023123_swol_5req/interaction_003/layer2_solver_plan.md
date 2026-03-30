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
- **Time**: 41023ms (41.0s)

## Reasoning
This is a research replication workflow for a variational inference paper ('BAM'), requiring literature understanding, algorithm implementation, and experiment execution across multiple result sections. The workflow decomposes into 4 natural phases: (1) literature extraction runs independently first, (2) algorithm implementation and experiment design can run in parallel once the paper is understood, (3) experiment execution depends on both implementation and design, and (4) result analysis and reporting depend on experiment outputs. Complexity is moderate-to-high due to the specificity of replicating Section 5.1, Figure 5.3, and Figure E.6 results.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract core BAM algorithm details, score-based divergence formulation, and figure/section specs from the paper
- **Prompt**: Read the paper 'Batch and Match: Black-Box Variational Inference with a Score-Based Divergence' (BAM). Extract: (1) The mathematical formulation of the score-based divergence used (likely a Fisher divergence or related), (2) The BAM algorithm pseudocode and key hyperparameters (batch size, step size, matching procedure), (3) Baselines compared against in Section 5.1 (e.g., BBVI variants, ADVI), (4) Experimental setup for Section 5.1 — which models, datasets, and metrics are reported, (5) What Figure 5.3 shows — axes, curves, conditions, (6) What Figure E.6 in Appendix E shows — axes, curves, conditions. Produce a structured specification document that the experiment_designer and code_generator can use directly.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design replication experiment protocols for Section 5.1, Figure 5.3, and Figure E.6
- **Prompt**: Using the structured paper spec from literature_reviewer, design detailed experiment protocols for: (1) Section 5.1 replication — specify each model (e.g., Gaussian, logistic regression, hierarchical models), the variational families used, the number of gradient steps, evaluation metrics (ELBO, KL, etc.), and how to fairly compare BAM vs baselines. (2) Figure 5.3 replication — specify the exact x/y axes, what hyperparameter or condition is varied, and how many runs/seeds are needed. (3) Figure E.6 replication — same level of detail for the appendix figure. For each protocol, specify: random seeds, convergence criteria, compute budget, and expected output format (arrays/dataframes for plotting). Output a structured experiment plan with clear entry points for the code_generator.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the BAM algorithm and all baselines needed for replication
- **Prompt**: Using the paper spec from literature_reviewer, implement the following in Python (NumPy/JAX/PyTorch as appropriate): (1) The BAM BBVI algorithm — including the score-based divergence estimator, the batch construction procedure, and the matching step. Ensure the implementation matches the paper's Algorithm box exactly. (2) Baseline BBVI methods referenced in Section 5.1 (e.g., standard REINFORCE-based BBVI, ADVI, or reparameterization gradient methods as cited). (3) The target model classes used in experiments (log-joint implementations for each model in Section 5.1). (4) A shared training loop that accepts an algorithm, a model, and config dict, and returns a trace of metrics (ELBO, divergence, wall time). (5) Plotting utilities that reproduce Figure 5.3 and Figure E.6 axes/styles. Structure as a reusable module with a `run_experiment(config)` entry point.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute all replication experiments for Section 5.1, Figure 5.3, and Figure E.6
- **Prompt**: Using the experiment protocols from experiment_designer and the implementation from code_generator, execute the full replication suite: (1) Run Section 5.1 experiments — for each model/baseline pair, run with the specified seeds and record final metrics. Store results as structured JSON or CSV. (2) Run Figure 5.3 experiments — sweep the relevant hyperparameter/condition, collect per-step traces, and store raw curves. (3) Run Figure E.6 experiments — execute the appendix experiment variant, collect results. For all runs: log wall-clock time, flag any numerical instabilities or divergences, and save checkpoints. Produce a results manifest listing all output files and their correspondence to paper figures/tables.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: experiment_designer, code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported values and score reproduction fidelity
- **Prompt**: Using the raw results from experiment_runner, perform a quantitative replication assessment: (1) Section 5.1 — extract the paper's reported numbers from the literature_reviewer spec and compute absolute/relative error for each metric and model. Flag any result that deviates by more than 5% relative error. (2) Figure 5.3 — overlay the replicated curves against a digitized version of the paper figure (if available) or describe qualitative agreement (shape, ordering, convergence point). (3) Figure E.6 — same analysis as Figure 5.3. (4) Produce a replication scorecard: per-result pass/fail, overall fidelity score (0–1), and root-cause analysis for any mismatches (hyperparameter sensitivity, implementation difference, stochasticity). Output a structured `replication_report.json`.
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
