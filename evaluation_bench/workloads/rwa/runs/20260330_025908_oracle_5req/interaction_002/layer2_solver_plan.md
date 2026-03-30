# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'All In One': The paper "All-in-one simulation-based inference" has been reproduced. This involves 5 major phases and 233 total subtasks. The workflow includes: Variance Exploding SDE (VESDE) is implemented, as described in A2.1; The Simformer model, training process and
> ... (479 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.434
- **Domain**: ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 49144ms (49.1s)

## Reasoning
This is a research replication workflow for 'All-in-One SBI' with clearly delineated components (VESDE, Simformer, NPE/NRE/NLE baselines) that have already been partially implemented. The decomposability is low (0.30) indicating tight coupling between components, so parallelism is limited — baseline methods can be implemented in parallel, but result analysis must wait for all experiments to complete. Complexity is moderate (0.43) with 5 phases, so we target a focused 5-6 agent pipeline rather than over-decomposing.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> code_gen

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract algorithmic specs for VESDE, Simformer architecture, and all three baseline methods from the All-in-One SBI paper
- **Prompt**: You are replicating the paper 'All-in-One Simulation-Based Inference'. Your task is to extract precise algorithmic and architectural specifications needed for implementation. Focus on: (1) VESDE formulation from Appendix A2.1 — the SDE coefficients, diffusion schedule, and score network interface; (2) Simformer architecture — transformer depth, attention mechanism, conditioning on summary statistics, training objective (score matching loss); (3) Training hyperparameters — optimizer, learning rate, batch size, number of epochs, any scheduler; (4) Inference procedure — how posterior samples are drawn via reverse SDE; (5) Baseline methods — NPE (normalizing flow type, e.g. NSF or MAF), NRE (classifier architecture), NLE (likelihood estimator); (6) Evaluation protocol — which benchmark tasks (e.g. SLCP, Lotka-Volterra, M/G/1), metrics (C2ST, MMD, SBC), and number of simulations budget. Output a structured specification document with one section per component, including any equations needed for implementation.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering VESDE+Simformer and NPE/NRE/NLE baselines on shared benchmarks
- **Prompt**: Using the extracted specifications from the literature reviewer, design a complete replication experiment plan for 'All-in-One SBI'. Your plan must cover: (1) Benchmark tasks to use — specify exact simulators (SLCP, Lotka-Volterra, M/G/1, or others from the paper), parameter dimensionality, and simulation budgets; (2) Shared data protocol — how to generate and split training/validation/test simulations so all methods see identical data; (3) Simformer experiment configuration — VESDE schedule parameters, score network config, training setup; (4) Baseline experiment configurations — one config block each for NPE, NRE, NLE using sbi library or equivalent; (5) Evaluation metrics — C2ST accuracy, expected coverage, posterior predictive checks; (6) Dependency graph — which experiments can run in parallel (baselines are independent of each other and of Simformer once data is generated); (7) Acceptance criteria — what delta from paper results counts as successful replication. Output a structured experiment plan in markdown with config tables.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement VESDE and Simformer model, training loop, and reverse-SDE inference pipeline
- **Prompt**: Implement the core 'All-in-One SBI' method in Python. Based on the specifications extracted from the paper, write the following modules: (1) `vesde.py` — Variance Exploding SDE class with sigma(t) schedule, marginal probability, and forward noising as per Appendix A2.1; implement `sde_coeff(t)` and `marginal_prob(x, t)`; (2) `score_network.py` — transformer-based score network conditioned on observed data x_o; include multi-head attention, positional encoding for parameter tokens, and cross-attention to summary statistics; (3) `simformer.py` — top-level model class wrapping VESDE + score network with `train_step(theta, x)` and `sample_posterior(x_o, n_samples)` methods; (4) `train_simformer.py` — training loop with Adam optimizer, learning rate schedule, loss logging, and checkpoint saving; (5) `inference_simformer.py` — reverse SDE sampler (Euler-Maruyama or Predictor-Corrector) to draw posterior samples given x_o. Use PyTorch. Include docstrings, shape comments, and a `__main__` block for smoke testing on a 2D Gaussian toy task.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement NPE, NRE, and NLE baseline methods and shared simulator/data generation utilities
- **Prompt**: Implement the three baseline SBI methods and shared infrastructure in Python, based on the experiment plan. (1) `simulators.py` — implement or wrap benchmark simulators: SLCP (simple likelihood complex posterior), Lotka-Volterra, and M/G/1 queue; each should expose `simulate(theta) -> x` and `prior` attributes; (2) `baselines/npe.py` — Neural Posterior Estimation using a Masked Autoregressive Flow (MAF) or Neural Spline Flow conditioned on x; use `sbi` library if available, otherwise implement manually with `nflows`; (3) `baselines/nre.py` — Neural Ratio Estimation using a binary classifier (MLP or ResNet) trained on joint vs marginal samples; (4) `baselines/nle.py` — Neural Likelihood Estimation using a conditional flow modeling p(x|theta); (5) `data_gen.py` — script to pre-generate N simulation pairs (theta, x) and save to disk so all methods use identical data; (6) `run_baseline.py` — unified CLI to train and evaluate any baseline given a simulator name and method name. Use PyTorch. Each baseline must expose `train(dataset)` and `sample_posterior(x_o, n_samples)` with the same interface as Simformer for fair comparison.
- **Tokens**: 3500 | Compute: heavy
- **Depends on**: experiment_designer

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer]
- Stage 2: [code_gen, code_generator] (parallel)
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 3500 | heavy |
| **Total** | | | **10000** | |
