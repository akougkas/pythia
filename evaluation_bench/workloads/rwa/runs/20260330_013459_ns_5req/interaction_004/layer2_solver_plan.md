# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Replicate the research paper 'Bbox': The BBOX-ADAPTER approach for adapting black-box LLMs has been reproduced completely. This involves 9 major phases and 421 total subtasks. The workflow includes: Algorithm 1 (Online Adaptation) has been implemented correctly.; The evaluation environments and data
> ... (436 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.332
- **Domain**: data, ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 32466ms (32.5s)

## Reasoning
This is a research replication workflow for the BBOX-ADAPTER paper. Given the intent classification shows moderate complexity (0.33) and low decomposability (0.30), the core work is already framed as a structured replication — the key parallel opportunities are literature extraction, experiment design, and baseline configuration happening simultaneously before code generation and execution. The workflow naturally splits into a comprehension/design phase (parallel), an implementation phase, and a validation/reporting phase.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract and formalize the BBOX-ADAPTER methodology, Algorithm 1 (Online Adaptation), and evaluation protocol from the paper
- **Prompt**: Review the BBOX-ADAPTER paper. Your objectives: (1) Precisely extract Algorithm 1 (Online Adaptation) — its inputs, outputs, update rules, and stopping conditions. (2) Identify all evaluation datasets and metrics used for GPT-3.5 Turbo and Mixtral-8x7B. (3) Document the adapter architecture: how it wraps a black-box LLM, what is trainable vs frozen, and how inference-time adaptation is performed. (4) List all baseline models compared in the paper and their configurations. Output a structured markdown spec covering algorithm pseudocode, dataset descriptions, metric definitions, and baseline summaries.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering all 9 phases, evaluation environments, and success criteria
- **Prompt**: Design a complete replication experiment plan for the BBOX-ADAPTER paper. Based on the paper's methodology: (1) Map out all 9 major replication phases and their dependencies. (2) Define evaluation environments for GPT-3.5 Turbo (OpenAI API) and Mixtral-8x7B (local or Together AI). (3) Specify dataset splits, preprocessing steps, and reproducibility seeds. (4) Define quantitative success criteria — what delta from reported numbers constitutes a successful replication? (5) Identify compute requirements per phase and flag any phases that can be parallelized during execution. Output a phased experiment plan in markdown with clear go/no-go checkpoints.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement Algorithm 1 (Online Adaptation) and the full BBOX-ADAPTER pipeline for both GPT-3.5 Turbo and Mixtral-8x7B
- **Prompt**: Implement the BBOX-ADAPTER replication codebase. Using the extracted algorithm spec and experiment design: (1) Implement Algorithm 1 (Online Adaptation) in Python — include the adapter module, online update loop, and black-box LLM query interface. (2) Build LLM backend wrappers for GPT-3.5 Turbo (via OpenAI API) and Mixtral-8x7B (via HuggingFace or Together AI). (3) Implement all baseline models referenced in the paper (e.g., zero-shot, few-shot, fine-tuned variants). (4) Build the evaluation harness: dataset loaders, metric computation (accuracy, F1, or paper-specific metrics), and results logging. (5) Structure the codebase with clear modules: `adapter/`, `baselines/`, `eval/`, `scripts/`. Include a `config.yaml` for reproducibility. All code must match the paper's described behavior exactly.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer, experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute the replication experiments across all 9 phases for both LLM backends and collect raw results
- **Prompt**: Execute the BBOX-ADAPTER replication experiments. (1) Run Algorithm 1 (Online Adaptation) end-to-end for GPT-3.5 Turbo and Mixtral-8x7B on all evaluation datasets. (2) Run all configured baseline models under identical conditions. (3) Execute across all 9 replication phases in dependency order, logging outputs at each phase checkpoint. (4) Collect and persist raw results: per-example predictions, aggregate metrics, wall-clock timing, and API call counts. (5) Flag any runs that deviate from expected behavior or hit errors. Output a structured results directory with per-phase JSON logs and a summary CSV.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported numbers and score fidelity across all 9 phases
- **Prompt**: Analyze the BBOX-ADAPTER replication results against the original paper. (1) For each evaluation dataset and metric, compute the delta between replicated results and paper-reported values for both GPT-3.5 Turbo and Mixtral-8x7B. (2) Score replication fidelity per phase (exact match, within 1%, within 5%, or divergent). (3) Identify any systematic deviations — e.g., consistent underperformance on a specific dataset or baseline. (4) Diagnose likely causes for any significant gaps: API version differences, dataset version mismatches, hyperparameter ambiguities in the paper. (5) Produce a replication scorecard table and a ranked list of discrepancies with hypothesized causes.
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
