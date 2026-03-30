# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'Adaptive Pruning': The paper "APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference" has been reproduced This involves 5 major phases and 171 total subtasks. The workflow includes: The required pre-trained models, datasets, and
> ... (391 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.337
- **Domain**: data, ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 41452ms (41.5s)

## Reasoning
Given that the foundational setup is already complete (pre-trained models, datasets, metrics, LoRA, and baselines are all in place), the remaining work centers on understanding the paper's methodology, designing and running replication experiments, and analyzing/reporting results. The complexity score (0.34) and decomposability (0.30) indicate a moderately constrained workflow — not highly parallelizable — but the literature review and experiment design phases can run concurrently since both draw from static inputs (the paper and the existing setup), while code generation depends on both. Experiment execution and result analysis form a strict sequential tail.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract APT's core algorithmic contributions, pruning criteria, and tuning schedule from the paper
- **Prompt**: Carefully read and extract the key technical details from 'APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference'. Focus on: (1) the adaptive pruning criterion — how importance scores are computed for attention heads and FFN neurons, (2) the joint pruning-and-tuning schedule (e.g., warmup, sparsity ramp-up), (3) the LoRA integration strategy used during pruning, (4) evaluation benchmarks (GLUE, SQuAD, or similar) and reported efficiency metrics (FLOPs, latency, parameter count), and (5) any ablation configurations described. Output a structured summary with one section per contribution, noting any implementation ambiguities or hyperparameter ranges that must be resolved before coding.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Translate the APT paper's experimental protocol into a concrete replication plan given the existing setup
- **Prompt**: Design a full replication experiment plan for APT given that the following are already in place: pre-trained models (e.g., BERT/RoBERTa), datasets, evaluation metrics, LoRA configuration, and baseline implementations. Your plan must specify: (1) which model–dataset–sparsity-level combinations to replicate (prioritize the main results table), (2) the exact hyperparameter grid to sweep (pruning rate schedule, LoRA rank, learning rate, warmup steps), (3) which baseline comparisons to run in parallel with APT, (4) hardware/compute assumptions and estimated wall-clock time per run, and (5) a phased execution order (e.g., small-scale sanity checks before full runs). Output a structured experiment manifest with named experiment IDs, configurations, and success criteria (target metric ranges from the paper).
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the APT adaptive pruning and joint tuning logic on top of the existing LoRA and baseline codebase
- **Prompt**: Implement the APT (Adaptive Pruning and Tuning) method as described in the literature review summary and experiment design manifest. Build on the existing LoRA setup and baseline code already in place. Required components: (1) Importance score computation module — implement the paper's criterion for scoring attention heads and FFN neurons (e.g., gradient-based or magnitude-based with moving average), (2) Adaptive pruning scheduler — a training callback that ramps sparsity according to the paper's schedule and prunes at specified steps, (3) Joint pruning + LoRA tuning training loop — integrate the pruning scheduler with the LoRA fine-tuning loop so both run simultaneously, (4) Structured sparsity masks — ensure pruned units are properly zeroed/removed for inference speedup measurement, (5) Evaluation harness — hooks to measure FLOPs, parameter count, and task metrics at each checkpoint. Write modular, well-commented code. Include configuration via a YAML/argparse interface matching the experiment manifest's hyperparameter fields.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer, experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the replication experiments across all configurations defined in the experiment manifest
- **Prompt**: Run all experiments defined in the experiment design manifest using the implemented APT code. Execution protocol: (1) First run a fast sanity-check experiment (1–2 epochs, small sparsity) to verify the training loop, pruning scheduler, and metric logging work correctly — fix any runtime errors before full runs, (2) Execute all experiment IDs from the manifest in the specified phased order, logging training loss, sparsity achieved, and validation metrics at each checkpoint, (3) Run baseline comparisons (already implemented) on the same configurations for fair comparison, (4) Save all checkpoints, logs, and metric curves to structured output directories keyed by experiment ID, (5) Flag any runs that fail to converge or produce anomalous metrics. Output a results ledger mapping each experiment ID to its final metrics (accuracy/F1, FLOPs reduction, parameter count, wall-clock time).
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported numbers and score reproduction fidelity
- **Prompt**: Analyze the results ledger from the experiment runner and score the quality of the APT replication. Tasks: (1) Build a comparison table: for each experiment, show the paper's reported metric vs. the replicated metric, compute absolute and relative deviation, and flag results outside a ±2% tolerance as 'divergent', (2) Diagnose divergent results — check if deviations correlate with specific hyperparameter choices, sparsity levels, or dataset splits, and hypothesize causes (e.g., missing warmup, different random seed protocol, dataset preprocessing difference), (3) Assess efficiency claims — verify that the FLOPs and parameter reduction numbers match the paper's reported speedup/compression ratios, (4) Summarize which of the paper's main claims are: fully replicated, partially replicated, or not replicated, with evidence, (5) Recommend any corrective parameter adjustments for a second-pass re-run if needed. Output a structured fidelity report with a top-line replication score (0–100).
- **Tokens**: 500 | Compute: light
- **Depends on**: experiment_runner

## Execution DAG
- Stage 0: [experiment_designer, literature_reviewer] (parallel)
- Stage 1: [code_generator]
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
