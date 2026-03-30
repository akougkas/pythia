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
- **Time**: 56092ms (56.1s)

## Reasoning
This is a research replication workflow for 'All-in-One SBI' with clearly defined components (VESDE, Simformer, NPE/NRE/NLE baselines) already partially scoped into 5 phases. Given the moderate complexity (0.43) and low decomposability (0.30), the pipeline should be mostly sequential — literature extraction feeds experiment design, which feeds implementation, which feeds execution and analysis. Parallel execution is possible between the three baseline methods (NPE, NRE, NLE) and between Simformer training vs. baseline training, since they share no direct data dependencies once the experiment design is fixed.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> code_gen

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract and formalize all algorithmic specifications from the All-in-One SBI paper
- **Prompt**: You are replicating 'All-in-One Simulation-Based Inference'. Extract and document the following from the paper: (1) Full VESDE (Variance Exploding SDE) formulation from Appendix A2.1 — drift/diffusion coefficients, noise schedule σ(t), score function parameterization; (2) Simformer architecture — transformer backbone, conditioning mechanism, embedding of simulation parameters θ and data x; (3) Training objective — score matching loss, any regularization terms; (4) Inference procedure — reverse SDE/ODE solver, posterior sampling algorithm; (5) Baseline method specs for NPE (normalizing flows), NRE (ratio estimator network), and NLE (likelihood network); (6) Benchmark tasks used for evaluation and reported metrics (C2ST, MMD, or log-prob). Output a structured specification document with equations, hyperparameters, and architectural details for each component.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experimental protocol covering all 5 phases and benchmark tasks
- **Prompt**: Using the extracted specifications from the literature reviewer, design a complete replication protocol for All-in-One SBI. Define: (1) The 5 replication phases with clear entry/exit criteria and subtask groupings (target ~233 subtasks total); (2) Benchmark tasks to run (e.g., two-moons, SLCP, Lotka-Volterra, or paper-specified tasks) with simulation budgets per task; (3) Shared data contracts — what each component (VESDE, Simformer, NPE, NRE, NLE) receives as input and produces as output; (4) Evaluation protocol — metrics, number of posterior samples, number of independent runs for statistical validity; (5) Hardware/compute assumptions (CPU vs GPU, estimated wall time per component); (6) Dependency graph showing which phases block which. Output a structured experiment plan in JSON-compatible format.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement VESDE and the Simformer model with training and inference pipelines
- **Prompt**: Implement the core All-in-One SBI system in Python (PyTorch). Required components: (1) VESDE implementation per Appendix A2.1 — implement σ(t) noise schedule, forward SDE, reverse SDE via Euler-Maruyama and probability flow ODE; (2) Score network — implement the Simformer transformer architecture with: positional embeddings for (θ, x) pairs, cross-attention conditioning, output head for ∇_θ log p(θ|x); (3) Training loop — score matching objective, gradient clipping, learning rate schedule, checkpoint saving; (4) Inference pipeline — posterior sampler using reverse SDE, batch inference for multiple observations. Use clean, modular code with type hints. Each component should be independently testable. Target compatibility: Python 3.10+, PyTorch 2.x, sbi library if applicable. Output complete, runnable source files.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the three baseline methods NPE, NRE, and NLE using consistent interfaces
- **Prompt**: Implement the three SBI baseline methods for comparison against Simformer in the All-in-One SBI replication. Use a consistent interface across all three: (1) NPE (Neural Posterior Estimation) — implement using masked autoregressive flow or NSF as the density estimator, conditioned on observed data x; (2) NRE (Neural Ratio Estimation) — implement binary classifier to estimate log p(θ|x)/p(θ), train with contrastive pairs; (3) NLE (Neural Likelihood Estimation) — implement flow-based likelihood model p(x|θ), combine with prior for posterior via MCMC. All three should: accept the same simulator interface, expose a .train(θ_samples, x_samples) method and a .sample_posterior(x_obs, n_samples) method, log training metrics to the same schema. Leverage the `sbi` library where appropriate but implement custom variants if paper deviates. Output complete Python source with docstrings.
- **Tokens**: 3500 | Compute: heavy
- **Depends on**: experiment_designer

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer]
- Stage 2: [code_gen, code_generator] (parallel)
- Stage 3: [tester]
- Stage 4: [experiment_runner]
- Stage 5: [result_analyzer]
- Stage 6: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 3500 | heavy |
| **Total** | | | **10000** | |
