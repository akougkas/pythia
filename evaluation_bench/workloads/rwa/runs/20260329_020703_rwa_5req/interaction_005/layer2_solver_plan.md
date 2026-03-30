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
- **Time**: 39900ms (39.9s)

## Reasoning
This is a research replication workflow for a diffusion model paper with adversarial noise-based transfer learning. The task is moderately complex (complexity=0.39) but has low decomposability (0.35), meaning the phases are somewhat sequential — literature understanding must precede experiment design, which must precede implementation and running. However, literature review and data discovery can run in parallel as an initial stage, and code review/result analysis can run in parallel as a final stage.

## Pipeline: literature_reviewer -> data_discovery -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer -> reporter

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract and formalize the methods, architecture, and training protocol from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'
- **Prompt**: Review the paper 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Extract the following with precision: (1) The full specification of Algorithm 1 — adversarial noise generation procedure, transfer learning objective, loss functions, and hyperparameters. (2) The experimental setup from Section 5 — datasets used, model architectures (DPM backbone), training schedules, evaluation metrics (FID, IS, etc.), and baseline comparisons. (3) The exact configuration needed to reproduce Figure 2 — what is plotted, which ablation or condition it represents, and the data sources. Output a structured reference document that downstream agents can use directly.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Identify and assess all datasets required by the paper's experimental setup (Section 5)
- **Prompt**: Based on the experimental setup in Section 5 of 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning', identify all datasets needed for replication. For each dataset: (1) Name and canonical source/URL. (2) Size, format, and any preprocessing steps mentioned in the paper. (3) Availability status (public, restricted, requires registration). (4) Any domain-gap pairs referenced (source domain → target domain) that are central to the transfer learning evaluation. Flag any datasets that are unavailable or require substitution and suggest alternatives.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 3. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering all 8 phases: Algorithm 1 training, Section 5 setup, and Figure 2 reproduction
- **Prompt**: Using the outputs from the literature_reviewer and data_discovery agents, design a complete experiment plan for replicating the paper 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. The plan must cover: (1) Algorithm 1 — adversarial noise-based transfer training loop: initialization, adversarial perturbation step, DPM update step, convergence criteria. (2) Section 5 experimental setup — exact model configs, training hyperparameters, dataset splits, evaluation protocol, and baseline runs. (3) Figure 2 reproduction — specify exactly what experiment produces Figure 2's data, what metrics/conditions are swept, and how to format the output plot. Structure the plan as 8 ordered phases with subtask breakdowns, specifying inputs, outputs, and success criteria per phase.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer, data_discovery

### 4. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement Algorithm 1 (adversarial noise-based DPM transfer training) and the full Section 5 experimental pipeline
- **Prompt**: Implement the replication codebase for 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning' following the experiment_designer's plan. Required implementations: (1) Algorithm 1 — a training loop for Diffusion Probabilistic Models (DPMs) with adversarial noise-based transfer learning. Include: adversarial noise generation (PGD or FGSM variant as specified), the transfer loss objective, integration with a standard DPM training schedule (DDPM or score-matching backbone), and checkpoint saving. (2) Section 5 setup — dataset loaders for identified datasets, model instantiation, training script with configurable hyperparameters (learning rate, noise budget epsilon, transfer weight lambda), and evaluation scripts computing FID/IS or paper-specified metrics. (3) Figure 2 reproduction script — runs the required ablation/comparison, collects results, and generates the plot. Use PyTorch. Structure code into modular files: `train_transfer.py`, `evaluate.py`, `reproduce_fig2.py`, `configs/`, `utils/`.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 5. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the training runs, evaluation, and Figure 2 reproduction pipeline; collect all results
- **Prompt**: Execute the full replication pipeline for 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning' using the implemented code. Steps: (1) Run Algorithm 1 training — launch `train_transfer.py` with Section 5 hyperparameters, monitor convergence, save checkpoints at specified intervals. (2) Run baseline comparisons as defined in Section 5 — train or load baseline DPMs without adversarial transfer, record metrics. (3) Run evaluation — compute FID, IS, or paper-specified metrics on all trained models against held-out test sets. (4) Run `reproduce_fig2.py` — execute the ablation/sweep needed for Figure 2 and save raw result data. Log all outputs (loss curves, metric values, wall-clock times) to structured files. Report any training instabilities or metric anomalies.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 6. result_analyzer -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Compare replication results against paper-reported values for Algorithm 1, Section 5, and Figure 2
- **Prompt**: Analyze the replication results from the experiment_runner against the ground-truth values reported in 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. For each component: (1) Algorithm 1 — compare training loss curves and convergence behavior to any figures/tables in the paper. (2) Section 5 — compare all quantitative metrics (FID, IS, transfer accuracy, etc.) to Table results in the paper; compute percentage deviation and flag any metric >10% off. (3) Figure 2 — overlay the reproduced figure against the paper's Figure 2; assess visual and quantitative fidelity. Produce a replication scorecard: per-metric match status (✓ matched / ⚠ partial / ✗ failed), root cause hypotheses for mismatches, and an overall replication confidence score (0–100).
- **Tokens**: 2000 | Compute: light
- **Depends on**: experiment_runner

### 7. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Produce the final replication report summarizing all 8 phases, findings, and replication fidelity
- **Prompt**: Write the final replication report for 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. The report must include: (1) Executive summary — what was replicated, overall success rate across 206 subtasks and 8 phases. (2) Method summary — concise description of Algorithm 1 and the adversarial noise-based transfer learning mechanism as implemented. (3) Results section — tables comparing paper vs. replicated metrics for all Section 5 experiments, with Figure 2 side-by-side comparison. (4) Replication scorecard from result_analyzer — per-component match status and confidence score. (5) Discrepancies and root causes — any deviations, missing details in the paper, dataset substitutions, or implementation choices made. (6) Reproducibility assessment — recommendations for future replicators. Format as a structured Markdown document suitable for a research lab replication log.
- **Tokens**: 1500 | Compute: light
- **Depends on**: result_analyzer

## Execution DAG
- Stage 0: [data_discovery, literature_reviewer] (parallel)
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]
- Stage 5: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | claude-haiku-cloud | claude-haiku-4-5-20251001 | 2000 | light |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | light |
| **Total** | | | **13500** | |
