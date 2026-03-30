# Dispatch Plan — SPECULATOR (CACHE)

## Request
> Replicate the research paper 'Bam': The core contributions of the paper "Batch and match: black-box variational inference with a score-based divergence" have been reproduced. This involves 4 major phases and 1020 total subtasks. The workflow includes: The core variational inference algorithms studie
> ... (469 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.467
- **Domain**: ml, research
- **Decomposability**: 0.45

## Metadata
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.300

## Reasoning
This is a research replication workflow for 'All-in-One Simulation-Based Inference' with clearly defined components (VESDE, Simformer, NPE/NRE/NLE baselines). Since the core implementations are already stated as complete, the workflow focuses on validating correctness, running experiments, and comparing against baselines — making this a verification/analysis pipeline rather than a greenfield build. Literature review and experiment design can run in parallel as independent upstream stages, followed by parallel code review and experiment execution, then result analysis and reporting.

## Pipeline: literature_reviewer -> experiment_designer -> review -> experiment_runner -> result_analyzer -> reporter

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract key quantitative benchmarks and evaluation criteria from the All-in-One SBI paper
- **Prompt**: Review the paper 'All-in-One Simulation-Based Inference' (Gloeckler et al.). Extract: (1) the core claims about Simformer vs NPE/NRE/NLE baselines — specific metrics such as C2ST scores, log-posterior accuracy, or calibration values on benchmark tasks (e.g., SLCP, two-moons, Lotka-Volterra); (2) the VESDE score network architecture specs from Appendix A2.1 — noise schedules, sigma_min/max, number of diffusion steps; (3) the Simformer training protocol — batch size, optimizer, learning rate schedule, number of simulations; (4) any ablation results that distinguish the 'all-in-one' capability (amortized over multiple observations, posterior/likelihood/ratio all from one model). Produce a structured checklist of claims to verify during replication.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the replication experiment suite mapping paper benchmarks to runnable configs
- **Prompt**: Design a replication experiment plan for 'All-in-One SBI'. Given that VESDE, Simformer, NPE, NRE, and NLE are already implemented, define: (1) the benchmark task suite to run — at minimum two-moons, SLCP, and one ODE-based task like Lotka-Volterra; (2) evaluation metrics: C2ST (classifier two-sample test), expected log-posterior predictive (ELPP), and marginal coverage; (3) number of simulations per task (e.g., 10k/50k/100k), number of posterior samples, and number of test observations; (4) a comparison matrix: Simformer vs NPE vs NRE vs NLE on each task/metric; (5) the 'all-in-one' test — verify a single trained Simformer can produce posterior, likelihood ratio, and marginal posteriors without retraining. Output as a structured experiment config spec (JSON or YAML schema).
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. review -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Audit the VESDE and Simformer implementations for correctness against paper spec
- **Prompt**: Perform a correctness review of the existing implementations: (1) VESDE (Variance Exploding SDE) — verify the forward SDE is dx = sigma(t)^2 * dW with the correct noise schedule from Song et al. (sigma(t) = sigma_min * (sigma_max/sigma_min)^t), that the score network is conditioned on simulation context, and that the reverse-time SDE sampler (Euler-Maruyama or Predictor-Corrector) matches Appendix A2.1; (2) Simformer — verify the transformer architecture uses cross-attention over (theta, x) pairs, that it supports amortized inference over variable numbers of observations, and that the training loss is the denoising score matching objective; (3) Baselines (NPE/NRE/NLE) — verify they use sbi-library-standard implementations or equivalent normalizing flows. Flag any deviations from the paper spec with severity (critical/minor).
- **Tokens**: 2000 | Compute: light
- **Depends on**: literature_reviewer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the benchmark experiments for Simformer and all three baselines across tasks
- **Prompt**: Execute the replication experiments as specified by the experiment designer. For each benchmark task (two-moons, SLCP, Lotka-Volterra): (1) train the Simformer model using the implemented training loop — log training loss curves and confirm convergence; (2) run NPE, NRE, and NLE baselines with matched simulation budgets; (3) draw posterior samples for 10 held-out observations per task; (4) compute C2ST scores comparing each method's posterior samples to reference posteriors; (5) test the Simformer's 'all-in-one' capability by querying posterior, likelihood ratio, and marginal posteriors from a single trained model without retraining. Save all results as structured outputs (numpy arrays or JSON) with method/task/metric labels for the result analyzer.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: experiment_designer, review

### 5. result_analyzer -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Compare replication results against paper-reported numbers and score fidelity
- **Prompt**: Analyze the experiment results against the paper's reported benchmarks. For each task-method-metric combination: (1) compute the deviation between replicated C2ST/ELPP values and paper-reported values — flag anything >5% relative error as a discrepancy; (2) assess whether Simformer outperforms baselines on the same tasks as claimed in the paper; (3) verify the all-in-one property holds — that a single Simformer model's posterior, likelihood, and ratio estimates are consistent with dedicated single-task models; (4) check calibration: are posterior coverage probabilities within expected error bands? (5) produce a replication fidelity score (0-100) based on: metric match (50%), qualitative trend match (30%), all-in-one capability confirmed (20%). Identify root causes for any major discrepancies.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: experiment_runner

### 6. reporter -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Produce a structured replication report with findings, tables, and fidelity verdict
- **Prompt**: Produce a comprehensive replication report for 'All-in-One Simulation-Based Inference'. Structure it as: (1) **Executive Summary** — overall replication fidelity score and one-paragraph verdict; (2) **Implementation Status** — table of components (VESDE, Simformer, NPE, NRE, NLE) with review findings (correct / minor deviation / critical issue); (3) **Benchmark Results Table** — rows = tasks, columns = methods, cells = C2ST score (replicated vs paper); (4) **All-in-One Capability Verification** — did a single Simformer reproduce posterior/likelihood/ratio without retraining? Yes/No with evidence; (5) **Discrepancies and Hypotheses** — list of deviations with likely causes (hyperparameter mismatch, random seed, dataset split, etc.); (6) **Recommendations** — specific code or config changes to close remaining gaps. Output as a clean Markdown document suitable for a research lab report.
- **Tokens**: 1500 | Compute: light
- **Depends on**: result_analyzer, review

## Execution DAG
- Stage 0: [experiment_designer, literature_reviewer] (parallel)
- Stage 1: [review]
- Stage 2: [experiment_runner]
- Stage 3: [result_analyzer]
- Stage 4: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| review | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | claude-haiku-cloud | claude-haiku-4-5-20251001 | 2000 | medium |
| reporter | claude-haiku-cloud | claude-haiku-4-5-20251001 | 1500 | light |
| **Total** | | | **11000** | |
