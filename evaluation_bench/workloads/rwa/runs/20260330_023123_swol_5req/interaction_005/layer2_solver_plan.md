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
- **Time**: 31732ms (31.7s)

## Reasoning
This is a research replication workflow for a diffusion model paper with adversarial noise-based transfer learning. The complexity is moderate (0.39) with low decomposability (0.35), suggesting the core components (algorithm, experimental setup, figure replication) are tightly coupled. The three deliverables — Algorithm 1 implementation, Section 5 experimental setup, and Figure 2 replication — can largely be parallelized after an initial literature review stage, with a final analysis and reporting stage to synthesize results.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> experiment_runner

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract Algorithm 1, Section 5 setup, and Figure 2 details from the paper
- **Prompt**: Read and extract the following from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning': (1) Full specification of Algorithm 1 — training DPMs with Adversarial Noise-based Transfer, including all hyperparameters, loss functions, and training loop logic. (2) Section 5 experimental setup — datasets used, model architectures, baselines, evaluation metrics (FID, IS, etc.), and hardware/software environment. (3) Figure 2 — identify what is plotted, what data it derives from, and the visual encoding used. Output a structured JSON with keys: algorithm1, experimental_setup, figure2_spec.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the end-to-end replication experiment plan covering all 8 phases
- **Prompt**: Using the extracted paper details from literature_reviewer, design a replication experiment plan for 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Map out all 8 major phases of the replication (data prep, pretraining, adversarial noise injection, transfer, fine-tuning, evaluation, figure generation, result comparison). For each phase specify: inputs, outputs, dependencies, and success criteria. Flag any ambiguities in the paper that require assumptions. Output as a structured phase-by-phase plan.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement Algorithm 1 — DPM training with Adversarial Noise-based Transfer
- **Prompt**: Implement Algorithm 1 from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning' as clean, reproducible PyTorch code. Use the algorithm specification from literature_reviewer. Include: (1) The adversarial noise generation step (PGD or FGSM variant as specified), (2) The transfer learning objective integrating adversarial perturbations into the DPM training loop, (3) The full training loop with proper loss computation, optimizer steps, and EMA if specified. Follow the Section 5 experimental setup for default hyperparameters. Output: a self-contained Python module `algorithm1_train.py` with inline comments referencing paper equations.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer, experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Regenerate Figure 2 from experimental outputs
- **Prompt**: Using the figure specification extracted by literature_reviewer and the results collected during experiment execution, reproduce Figure 2 from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Write a Python plotting script (matplotlib/seaborn) that: (1) loads the correct data outputs, (2) replicates the axes, labels, color scheme, and layout of the original figure, (3) overlays paper-reported values for visual comparison. Save output as `figure2_replicated.pdf` and `figure2_replicated.png`. Note any visual discrepancies.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: literature_reviewer

### 5. experiment_runner -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Regenerate Figure 2 from experimental outputs
- **Prompt**: Using the figure specification extracted by literature_reviewer and the results collected during experiment execution, reproduce Figure 2 from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Write a Python plotting script (matplotlib/seaborn) that: (1) loads the correct data outputs, (2) replicates the axes, labels, color scheme, and layout of the original figure, (3) overlays paper-reported values for visual comparison. Save output as `figure2_replicated.pdf` and `figure2_replicated.png`. Note any visual discrepancies.
- **Tokens**: 500 | Compute: medium
- **Depends on**: literature_reviewer

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer, experiment_runner] (parallel)
- Stage 2: [code_generator, result_analyzer] (parallel)
- Stage 3: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| experiment_runner | claude-haiku-cloud | claude-haiku-4-5-20251001 | 500 | medium |
| **Total** | | | **10000** | |
