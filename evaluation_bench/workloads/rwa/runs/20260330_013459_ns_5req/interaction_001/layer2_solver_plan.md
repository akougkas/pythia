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
- **Time**: 33591ms (33.6s)

## Reasoning
The request involves replicating a research paper (APT: Adaptive Pruning and Tuning) with significant prior setup already completed — models, datasets, metrics, LoRA, and baselines are all in place. Given the decomposability score of 0.30 and complexity of 0.34, the remaining work is moderate: understanding the paper's methodology, designing/running the replication experiments, and analyzing/reporting results. The pipeline is largely sequential (understand → design → implement → run → analyze → report), though literature review and experiment design can partially overlap.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract APT's core adaptive pruning and tuning methodology from the paper
- **Prompt**: Review the paper 'APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference'. Extract and document: (1) the adaptive pruning criterion and schedule (how heads/neurons are scored and removed), (2) the joint tuning mechanism (how LoRA interacts with pruning), (3) the training objective and loss formulation, (4) key hyperparameters reported (pruning ratio, LoRA rank, learning rate schedules), (5) evaluation benchmarks and metrics used (GLUE, SQuAD, perplexity, latency, etc.), and (6) the baseline comparisons made. Output a structured methodology summary that can directly guide experiment design. Note: LoRA is already configured and baselines are implemented.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the replication experiment plan for APT's 5 major phases
- **Prompt**: Using the APT methodology summary provided, design a concrete replication experiment plan covering the paper's 5 major phases. For each phase specify: (1) exact configuration (model checkpoint, dataset split, pruning ratio schedule, LoRA rank), (2) the expected output artifact (checkpoint, metric table, latency profile), (3) which baselines to compare against (already implemented), and (4) success criteria aligned with the paper's reported numbers. Ensure the plan maps onto the 171 subtasks already identified. Pre-trained models, datasets, LoRA setup, and baselines are confirmed available — focus on experiment sequencing, ablation variants, and any edge cases that could cause deviation from reported results.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement APT adaptive pruning logic integrated with the existing LoRA setup
- **Prompt**: Implement the APT adaptive pruning and tuning code on top of the existing LoRA configuration. Required components: (1) importance scoring function for attention heads and FFN neurons (use the paper's criterion — typically first-order Taylor expansion or gradient-magnitude based), (2) adaptive pruning scheduler that incrementally removes units across training steps according to the target sparsity schedule, (3) joint training loop that alternates or combines LoRA gradient updates with pruning mask updates, (4) checkpoint saving at each pruning stage for ablation, (5) inference-time pruning application (structural removal for latency gains). Code must be compatible with the pre-configured LoRA setup and available model/dataset infrastructure. Output clean, modular code with inline comments referencing paper sections.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the APT replication experiments across all 5 phases and collect results
- **Prompt**: Execute the full APT replication pipeline according to the experiment design plan. Run all 5 major phases: (1) baseline fine-tuning runs for reference metrics, (2) APT training with adaptive pruning at configured sparsity targets, (3) evaluation on all designated benchmarks (GLUE subtasks, SQuAD, or domain-specific metrics as per paper), (4) latency/throughput profiling on pruned vs. unpruned models, (5) ablation runs (e.g., pruning without LoRA tuning, static vs. adaptive schedule). Log all metrics, training curves, and intermediate checkpoints. Flag any runs where results deviate >5% from paper-reported numbers for later analysis. Output a raw results table covering all conditions.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported numbers and diagnose gaps
- **Prompt**: Analyze the collected experimental results against the APT paper's reported numbers. For each benchmark and condition: (1) compute delta between replicated and reported metrics (accuracy, F1, perplexity, latency speedup), (2) classify deviations as within noise (<1%), minor gap (1-5%), or significant gap (>5%), (3) for significant gaps, hypothesize root causes (hyperparameter sensitivity, dataset preprocessing differences, hardware-dependent latency, LoRA rank mismatch), (4) verify ablation results are internally consistent with the paper's claims about adaptive vs. static pruning and LoRA contribution, (5) produce a fidelity score per experimental condition. Output a structured comparison table and gap analysis.
- **Tokens**: 500 | Compute: light
- **Depends on**: experiment_runner

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]
- Stage 5: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| **Total** | | | **10000** | |
