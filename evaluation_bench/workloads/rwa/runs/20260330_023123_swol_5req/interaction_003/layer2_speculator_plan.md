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
- **Confidence**: 0.500

## Reasoning
This is a research replication workflow for 'All-in-One SBI' with clearly defined phases (VESDE, Simformer model/training/inference, and three baseline methods NPE/NRE/NLE). Given the intent classification shows moderate complexity (0.43) but low decomposability (0.30), the phases have tight interdependencies — baselines and Simformer share the same SBI framework and must be validated against common benchmarks. The workflow is best structured as: literature extraction → experiment design → parallel code generation tracks (Simformer vs. baselines) → integrated testing → result analysis and reporting.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> code_gen

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract all mathematical specifications, hyperparameters, and algorithmic details from the All-in-One SBI paper
- **Prompt**: Review the paper 'All-in-One Simulation-Based Inference' and extract: (1) Full VESDE formulation from Appendix A2.1 — SDE coefficients, noise schedules, drift/diffusion terms; (2) Simformer architecture details — transformer blocks, attention mechanisms, embedding dims, conditioning strategy; (3) Training procedure — loss functions, optimizer settings, batch sizes, learning rate schedules, number of epochs; (4) Inference procedure — posterior sampling steps, MCMC or score-based sampling details; (5) Baseline method configurations for NPE, NRE, and NLE — network architectures, training setups, and any shared components; (6) Benchmark tasks used for evaluation and the metrics reported (e.g., C2ST, log-probability, coverage). Output a structured specification document.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering all 5 phases and integration of Simformer vs. baselines
- **Prompt**: Using the extracted paper specifications, design a complete replication experiment plan for All-in-One SBI. Define: (1) The 5 major experimental phases and their subtask breakdown (targeting ~233 subtasks); (2) The benchmark tasks (e.g., SLCP, Lotka-Volterra, Gaussian mixture) with simulator configs; (3) A shared data/simulator interface so Simformer, NPE, NRE, and NLE all run on identical draws; (4) Evaluation protocol — number of posterior samples, reference posterior generation, metric computation (C2ST, MMD, or log-prob); (5) Directory and file structure for reproducibility (configs, checkpoints, results); (6) Which phases can run in parallel and which are sequential. Output a phased experiment plan with dependency graph.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement VESDE and the full Simformer model, training loop, and score-based inference pipeline
- **Prompt**: Implement the following components from the All-in-One SBI paper: (1) VESDE (Variance Exploding SDE) as specified in Appendix A2.1 — implement the forward SDE, reverse SDE, and score network target; (2) Simformer architecture — transformer-based amortized score network that conditions on observed data x_o, implement multi-head attention, positional encodings, and the joint embedding of (theta, x, t); (3) Training loop — denoising score matching loss over simulated (theta, x) pairs with time-conditional noise injection following the VESDE schedule; (4) Inference — implement posterior sampling via reverse SDE or predictor-corrector sampler conditioned on x_o; Use PyTorch. Follow the exact hyperparameters from the experiment design spec. Include docstrings and config-driven hyperparameters.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the three baseline SBI methods: NPE, NRE, and NLE using sbi library or from-scratch as specified
- **Prompt**: Implement the three baseline methods for the All-in-One SBI replication: (1) Neural Posterior Estimation (NPE) — normalizing flow (e.g., MAF or NSF) trained on (theta, x) pairs to directly approximate p(theta | x); (2) Neural Ratio Estimation (NRE) — binary classifier trained to estimate the likelihood-to-evidence ratio; (3) Neural Likelihood Estimation (NLE) — normalizing flow trained to approximate p(x | theta), combined with MCMC for posterior; For each: implement training, posterior evaluation, and a common interface `sample_posterior(x_obs, n_samples)`. Use the same benchmark simulators as Simformer. Ensure all three share the same train/test data splits defined in the experiment design. Use PyTorch; sbi library wrappers are acceptable if they match paper configs.
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
