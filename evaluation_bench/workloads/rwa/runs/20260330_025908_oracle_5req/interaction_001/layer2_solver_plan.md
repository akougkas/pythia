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
- **Time**: 46568ms (46.6s)

## Reasoning
The APT paper replication is a research workflow with foundational work already complete (models, datasets, metrics, LoRA, baselines). Given the pre-work is done and complexity is moderate (0.34) with low decomposability (0.30), the remaining phases center on: understanding the paper's core method, designing the replication experiments, implementing APT-specific logic, running experiments, and analyzing/reporting results. Literature review and experiment design can run in parallel since baselines are already available. Code generation depends on both, and experiment running depends on code. Analysis and reporting are sequential at the end.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract APT's adaptive pruning and tuning methodology from the paper
- **Prompt**: You are replicating the paper 'APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference'. The baselines, LoRA setup, datasets, and metrics are already in place. Your task: (1) Extract the exact adaptive pruning criteria used in APT (structured vs unstructured, importance scoring method, threshold adaptation schedule). (2) Identify how APT integrates pruning with LoRA tuning — specifically the joint optimization objective. (3) Document the training/inference efficiency claims and the experimental configurations (model sizes, sparsity targets, benchmark tasks: GLUE, SQuAD, etc.). (4) List any non-obvious implementation details — e.g., warmup steps before pruning begins, mask update frequency, gradient flow through pruned weights. Output a structured methodology document with sections: Pruning Strategy, Tuning Integration, Hyperparameters, Evaluation Protocol.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the replication experiment grid against established baselines
- **Prompt**: You are designing experiments to replicate APT (Adaptive Pruning and Tuning) results. The baselines (full fine-tuning, LoRA-only, magnitude pruning + fine-tuning) are already implemented. Design: (1) A comparison matrix: APT vs each baseline across sparsity levels (e.g., 30%, 50%, 70%) and tasks (GLUE subtasks, SQuAD v1/v2). (2) Ablation experiments: pruning-only vs tuning-only vs joint APT, to isolate each component's contribution. (3) Efficiency benchmarks: training FLOPs, inference latency, memory footprint — specify measurement methodology. (4) Identify which experiments are highest priority for reproducing the paper's key claims (Table 2 and Figure 3 in most APT-style papers). Output an experiment schedule with priority tiers (P0=must replicate, P1=important, P2=nice-to-have) and estimated compute budget per experiment.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement APT adaptive pruning scheduler and joint optimization loop
- **Prompt**: Implement the core APT components on top of the existing LoRA and baseline codebase. Required modules: (1) `AdaptivePruningMask` — computes importance scores (use gradient magnitude × weight magnitude as per APT), maintains a dynamic binary mask per layer, updates mask on a configurable schedule (e.g., every K steps). (2) `APTTrainer` — extends the existing LoRA trainer to jointly optimize: (a) task loss on active (unmasked) weights + LoRA adapters, (b) sparsity regularization term λ·||mask||₀ with adaptive λ scheduling. (3) `PruningScheduler` — implements gradual sparsity increase from 0% to target sparsity over warmup_pruning_steps, using cubic sparsity schedule. (4) Inference-time model export: apply final mask permanently, remove LoRA adapters by merging into base weights, verify parameter count. Integrate cleanly with existing training loop. Include docstrings and inline comments referencing the APT paper sections.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer, experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute APT replication experiments and collect metrics against baselines
- **Prompt**: Run the APT replication experiments per the experiment design. Execution plan: (1) Run P0 experiments first: APT on BERT-base / RoBERTa-base across GLUE (SST-2, MNLI, QNLI) at 50% sparsity — these reproduce the paper's headline numbers. (2) For each run, log: eval accuracy/F1 per checkpoint, training loss curve, sparsity achieved vs target, wall-clock time per epoch, peak GPU memory. (3) Run corresponding baseline experiments (already implemented) with identical seeds and hyperparameters for fair comparison. (4) Run P1 ablations: pruning-only and tuning-only variants. (5) Collect all results into a structured CSV: columns = [model, task, method, sparsity, metric_value, train_time_hrs, inference_ms, params_M]. Flag any runs where APT underperforms baseline by >2% — these need investigation.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare APT replication results against paper's reported numbers and baselines
- **Prompt**: Analyze the experiment results from the APT replication. Tasks: (1) Build a comparison table: replicated APT results vs paper's reported results vs our baselines. Compute relative error (%) for each metric — flag if >5% deviation from paper. (2) Efficiency analysis: plot accuracy vs sparsity Pareto curves for APT vs baselines. Compute efficiency ratio: (accuracy_drop%) / (parameter_reduction%). (3) Diagnose any discrepancies: check if deviations are within variance (run std dev), or systematic (e.g., consistent underperformance at high sparsity). Likely causes: different pruning schedule, missing regularization term, seed sensitivity. (4) Ablation analysis: quantify contribution of adaptive pruning vs LoRA tuning independently. (5) Output a replication scorecard: Overall Fidelity Score (0-100), per-experiment match status (PASS/PARTIAL/FAIL), and root cause notes for any FAILs.
- **Tokens**: 500 | Compute: medium
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
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| **Total** | | | **10000** | |
