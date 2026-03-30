# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'Bridging Data Gaps': The paper "Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning" has been reproduced. This involves 8 major phases and 206 total subtasks. The workflow includes: Algorithm 1 for training DPMs with Adversarial Noise-b
> ... (440 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.388
- **Domain**: data, ml, research
- **Decomposability**: 0.35

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 35916ms (35.9s)

## Reasoning
This is a research replication workflow for a diffusion model paper with adversarial noise-based transfer learning. The core components — algorithm implementation, experimental setup, and figure replication — are largely independent and can be parallelized after an initial literature review. Given the stated complexity (0.39) and decomposability (0.35), a focused 5-agent pipeline covering understanding, implementation, execution, analysis, and reporting is appropriate without over-engineering.

## Pipeline: literature_reviewer -> code_generator -> experiment_designer -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract the core methodology, Algorithm 1 details, and Section 5 experimental config from the paper
- **Prompt**: Review the paper 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Extract: (1) the exact formulation of Algorithm 1 — adversarial noise generation procedure, training loop, loss functions, and hyperparameters; (2) Section 5 experimental setup — datasets used, model architectures, evaluation metrics (FID, IS, etc.), training schedules, and baselines; (3) the data required to reproduce Figure 2 — what axes represent, which models/conditions are compared, and how results are aggregated. Output a structured summary that downstream agents can directly use.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement Algorithm 1 — the DPM training loop with adversarial noise-based transfer learning
- **Prompt**: Using the methodology extracted by the literature_reviewer, implement Algorithm 1 from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Your implementation must include: (1) the adversarial noise generation module (PGD or FGSM-style perturbation applied to source domain data); (2) the diffusion model training loop with transfer learning objective — correctly combining the denoising score matching loss with the adversarial transfer term; (3) configurable hyperparameters (epsilon for noise budget, number of adversarial steps, noise schedule beta_t, learning rate); (4) compatibility with standard DPM backbones (e.g., UNet). Use PyTorch. Include inline comments referencing Algorithm 1 steps. Output clean, modular code with a train() entry point.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer

### 3. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Define the full experimental setup replicating Section 5 and the Figure 2 conditions
- **Prompt**: Using the experimental details extracted by the literature_reviewer from Section 5, design the replication experiment configuration. Specify: (1) dataset pairs for source→target transfer (e.g., CIFAR-10→STL-10 or as described); (2) baseline conditions to run — standard DPM fine-tuning, no-transfer, and the proposed adversarial noise-based transfer; (3) evaluation protocol — FID and IS computation method, number of generated samples, number of seeds for variance estimation; (4) training budget — epochs, batch size, GPU requirements; (5) the exact conditions needed to reproduce each curve/bar in Figure 2. Output a structured experiment config (YAML or JSON format) and a run matrix table.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the implemented algorithm under the designed experimental conditions and collect results
- **Prompt**: Using the Algorithm 1 implementation from code_generator and the experiment config from experiment_designer, execute the full replication pipeline: (1) run all baseline and proposed-method conditions defined in the Figure 2 run matrix; (2) for each condition, collect FID and IS scores across all seeds; (3) log training curves (loss vs. epoch) for the adversarial noise transfer training runs; (4) save generated image samples for qualitative inspection; (5) organize all outputs into a structured results directory with one JSON summary file per condition. Flag any training instabilities or divergences. Output a consolidated results table.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator, experiment_designer

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported values and score fidelity for Figure 2
- **Prompt**: Analyze the results collected by experiment_runner against the values reported in the original paper 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. For each condition in Figure 2: (1) compute the absolute and relative difference between replicated FID/IS and paper-reported FID/IS; (2) assess whether replication is within acceptable tolerance (±5% FID is typical); (3) identify any conditions where replication failed or diverged significantly and hypothesize causes (data preprocessing mismatch, hyperparameter sensitivity, stochasticity); (4) produce a replication fidelity score (0–100) for the overall Figure 2 reproduction. Output a structured comparison table and a written assessment.
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
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| **Total** | | | **10000** | |
