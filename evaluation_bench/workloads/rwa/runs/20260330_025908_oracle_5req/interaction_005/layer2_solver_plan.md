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
- **Time**: 32700ms (32.7s)

## Reasoning
This is a research replication workflow for a diffusion model paper with adversarial noise-based transfer learning. The core components — literature understanding, experiment design, code implementation, and result analysis — have natural sequential dependencies, but literature review and data discovery can run in parallel as an initial stage. Given the stated complexity (0.39) and decomposability (0.35), a focused 5-agent pipeline is appropriate: parallel ingestion first, then sequential implementation, execution, and reporting.

## Pipeline: literature_reviewer -> data_discovery -> experiment_designer -> code_generator -> experiment_runner

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract and formalize the methodology from 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'
- **Prompt**: Read and analyze the paper 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. Extract: (1) the formal definition of Algorithm 1 — Adversarial Noise-Based Transfer training for DPMs, including loss functions, noise schedule, and adversarial perturbation strategy; (2) the experimental setup from Section 5, including datasets, baselines, evaluation metrics (FID, IS, etc.), and hyperparameters; (3) the data and architecture details needed to replicate Figure 2. Produce a structured methods summary in Markdown with clearly labeled sections for Algorithm 1, Experimental Setup, and Figure 2 specification.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess all datasets and pretrained model checkpoints required for the replication
- **Prompt**: Identify and assess the availability of all data sources needed to replicate 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning'. This includes: (1) source and target domain datasets referenced in Section 5 (e.g., CIFAR-10, CelebA, LSUN, or domain-specific splits); (2) any pretrained DPM or GAN checkpoints used for initialization; (3) adversarial perturbation budgets or auxiliary datasets if mentioned. For each resource, report: name, source URL or repository, license, size, and download instructions. Flag any gaps where data is unavailable or requires special access.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 3. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Produce a full replication experiment plan covering Algorithm 1 training, Section 5 setup, and Figure 2 reproduction
- **Prompt**: Using the methods summary from the literature_reviewer and the data availability report from data_discovery, design a complete replication experiment plan. Specify: (1) environment setup — Python version, key libraries (PyTorch, diffusers, etc.), GPU requirements; (2) Algorithm 1 implementation plan — model architecture, adversarial noise injection loop, transfer learning objective, training schedule; (3) Section 5 experiment matrix — which dataset pairs to run, which baselines to include, number of seeds, evaluation protocol; (4) Figure 2 reproduction plan — what is plotted, how to generate the data, and how to render the figure. Output a structured experiment specification in Markdown with numbered steps and clear checkpoints.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer, data_discovery

### 4. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement Algorithm 1, the Section 5 training pipeline, and Figure 2 plotting code
- **Prompt**: Implement the full replication codebase for 'Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning' following the experiment specification provided. Produce: (1) `algorithm1.py` — the Adversarial Noise-Based Transfer training loop for DPMs, including the adversarial perturbation step, KL/score-matching loss, and transfer regularization term; (2) `train.py` — end-to-end training script matching the Section 5 setup, with argument parsing for dataset, model config, and hyperparameters; (3) `evaluate.py` — evaluation script computing FID, IS, or other metrics reported in the paper; (4) `figure2.py` — script to reproduce Figure 2 from saved checkpoints or logged metrics. Use PyTorch. Include inline comments referencing paper equations and section numbers. Each script must be runnable from the command line.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 5. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the replication experiments and collect quantitative results for all Section 5 benchmarks
- **Prompt**: Run the replication experiments using the code from code_generator and the datasets from data_discovery, following the plan from experiment_designer. Steps: (1) validate environment setup and data loading; (2) run Algorithm 1 training for each dataset pair specified in Section 5; (3) evaluate each trained model and record FID/IS/other metrics; (4) generate Figure 2 using `figure2.py`; (5) log all results to a structured CSV and save model checkpoints. Report any training instabilities, OOM errors, or deviations from the paper's described procedure. Output a results log in Markdown with a table comparing your metrics to the paper's reported values.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

## Execution DAG
- Stage 0: [data_discovery, literature_reviewer] (parallel)
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| **Total** | | | **10000** | |
