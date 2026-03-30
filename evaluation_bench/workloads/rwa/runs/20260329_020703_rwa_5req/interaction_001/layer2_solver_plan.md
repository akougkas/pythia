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
- **Time**: 41828ms (41.8s)

## Reasoning
This is a research replication workflow for APT (Adaptive Pruning and Tuning) with infrastructure already in place (models, datasets, LoRA, baselines). Given the low decomposability score (0.30) and moderate complexity (0.34), the remaining work centers on understanding the paper's methods, implementing APT-specific logic, running experiments, and comparing against baselines. Phases 1-2 (literature review + experiment design) can run in parallel since neither depends on the other's output at this stage, while implementation, execution, and analysis must be sequential.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer -> reporter

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract APT's core algorithmic contributions — pruning schedule, tuning strategy, and evaluation protocol
- **Prompt**: You are replicating 'APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference'. Extract and document: (1) The exact adaptive pruning criterion (how sparsity masks are computed and updated dynamically), (2) The joint pruning+LoRA tuning objective and loss formulation, (3) The pruning schedule (warmup steps, target sparsity ramp, final sparsity levels used in experiments), (4) All evaluation benchmarks and metrics reported (GLUE tasks, perplexity, speedup ratios, model sizes), (5) Hyperparameters: learning rate, pruning frequency, LoRA rank, batch size, number of training steps. Cross-reference any ablation studies that isolate pruning vs tuning contributions. Output a structured reference document to guide implementation.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment matrix covering all APT configurations and baseline comparisons
- **Prompt**: Design a complete experiment plan to replicate APT results. Given that pre-trained models (e.g., BERT, RoBERTa), datasets (GLUE benchmark), and baselines are already set up: (1) Define the experiment matrix — which model × dataset × sparsity level combinations to run (match the paper's Table 1/2 configurations), (2) Specify the comparison grid: APT vs magnitude pruning, movement pruning, and LoRA-only baselines, (3) Define success criteria — acceptable deviation from paper's reported scores (e.g., ±0.5% on GLUE metrics), (4) Identify which experiments can run in parallel (different tasks/seeds), (5) Estimate compute requirements per run. Output a structured experiment manifest with run configurations in a format ready for the experiment runner.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the APT adaptive pruning and joint tuning mechanism on top of the existing LoRA setup
- **Prompt**: Implement the APT method as described in the literature review output. Building on the existing LoRA setup: (1) Implement the adaptive pruning mask module — compute importance scores per weight (use the paper's criterion, likely first-order or second-order sensitivity), (2) Implement the dynamic sparsity scheduler that ramps sparsity from 0 to target over training, (3) Integrate pruning masks with the LoRA adapter forward pass so both operate jointly during fine-tuning, (4) Implement the joint training loop: forward pass with masked weights + LoRA, loss backward, mask update step at pruning frequency, (5) Add inference-time weight consolidation (apply final mask and merge LoRA for speedup measurement), (6) Expose config parameters: target_sparsity, pruning_warmup_steps, pruning_frequency, lora_rank. Ensure the implementation is modular and matches the baseline interface for fair comparison. Include inline comments referencing paper sections.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute all APT replication runs per the experiment manifest and collect raw results
- **Prompt**: Execute the full APT replication experiment suite using the implemented APT code and the experiment manifest. For each configuration in the manifest: (1) Load the specified pre-trained model and tokenizer, (2) Apply the APT training loop with the configured sparsity and LoRA settings, (3) Evaluate on the designated GLUE task(s) after training — record accuracy/F1/Matthews correlation as appropriate, (4) Measure and record: final model sparsity, inference latency (or FLOPs reduction), peak GPU memory, training time, (5) Run each configuration with at least 1 seed (3 if compute allows) and record all results, (6) Save all results to a structured CSV/JSON results file keyed by: model, task, method, sparsity, seed. Also run baseline comparisons (magnitude pruning, LoRA-only) using the same evaluation protocol for apples-to-apples comparison.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator, experiment_designer

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper's reported numbers and score reproduction fidelity
- **Prompt**: Analyze the replication results against the APT paper's reported numbers. (1) Load the results CSV/JSON from the experiment runner and the paper's target numbers from the literature review, (2) For each model × task × sparsity configuration, compute: absolute deviation from paper's score, relative deviation (%), and whether it falls within acceptable tolerance (±0.5% GLUE, ±1 perplexity point), (3) Compute an overall reproduction fidelity score (% of configurations within tolerance), (4) Identify any systematic deviations — do specific tasks, sparsity levels, or model sizes replicate poorly?, (5) Compare APT vs baselines in your runs and check if the relative ordering matches the paper (APT should outperform baselines), (6) Flag any results that deviate >2% as requiring investigation. Output a structured analysis report with a per-configuration table, summary statistics, and a final replication verdict (Successful / Partial / Failed) with justification.
- **Tokens**: 2000 | Compute: light
- **Depends on**: experiment_runner

### 6. reporter -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Produce the final replication report summarizing methodology, results, deviations, and conclusions
- **Prompt**: Produce a comprehensive replication report for APT. Structure it as: (1) **Executive Summary** — replication verdict, overall fidelity score, key finding in 3 sentences, (2) **Method Recap** — brief description of APT's adaptive pruning + LoRA tuning approach as implemented, (3) **Results Table** — side-by-side comparison of paper's reported vs replicated scores for all configurations, color-coded by deviation severity, (4) **Deviation Analysis** — for any result outside tolerance, explain likely causes (e.g., hardware differences, missing implementation details, hyperparameter sensitivity), (5) **Baseline Comparison** — confirm or deny that APT outperforms baselines as claimed, (6) **Reproducibility Notes** — document any ambiguities encountered in the paper and how they were resolved, (7) **Conclusion** — overall assessment of paper's reproducibility and confidence in the replication. Format as a clean Markdown document suitable for inclusion in a research reproducibility study.
- **Tokens**: 1500 | Compute: light
- **Depends on**: result_analyzer

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
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| reporter | claude-haiku-cloud | claude-haiku-4-5-20251001 | 1500 | light |
| **Total** | | | **13000** | |
