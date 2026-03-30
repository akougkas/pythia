# Dispatch Plan — SPECULATOR (CACHE)

## Request
> Replicate the research paper 'Bridging Data Gaps': The paper "Bridging Data Gaps in Diffusion Models with Adversarial Noise-Based Transfer Learning" has been reproduced. This involves 8 major phases and 206 total subtasks. The workflow includes: Algorithm 1 for training DPMs with Adversarial Noise-b
> ... (440 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.388
- **Domain**: data, ml, research
- **Decomposability**: 0.35

## Metadata
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.500

## Reasoning
This is a research replication workflow for the BBOX-ADAPTER paper, which is moderately complex but has a low decomposability score (0.30), meaning stages are tightly coupled. The work is largely already scaffolded (9 phases, 421 subtasks partially done), so the focus is on literature grounding, experiment execution, and result validation. Three parallel tracks are viable: literature review + experiment design can run concurrently with baseline configuration, while result analysis and reporting are strictly sequential at the end.

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract BBOX-ADAPTER methodology, Algorithm 1 details, and evaluation protocol from the paper
- **Prompt**: Review the BBOX-ADAPTER paper ('Bbox'). Extract: (1) the exact formulation of Algorithm 1 (Online Adaptation) — inputs, outputs, update rules, and convergence criteria; (2) the evaluation datasets and metrics used for GPT-3.5 Turbo and Mixtral-8x7B; (3) the baseline models compared against (names, configurations, hyperparameters); (4) any ablation variants described. Produce a structured reference document that the experiment_designer and result_analyzer can use for faithful replication.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment protocol aligned to paper specs
- **Prompt**: Using the BBOX-ADAPTER paper methodology extracted by literature_reviewer, design a complete replication experiment plan: (1) Confirm that Algorithm 1 (Online Adaptation) implementation matches the paper's pseudocode — list any deviations or ambiguities; (2) Define the exact evaluation suite for GPT-3.5 Turbo and Mixtral-8x7B (datasets, splits, prompt formats, decoding settings); (3) Specify baseline model configurations (hyperparameters, inference settings) to ensure fair comparison; (4) Define success criteria — what delta from reported numbers is acceptable for replication claim. Output a structured experiment spec document.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement or audit Algorithm 1 and evaluation harness for BBOX-ADAPTER replication
- **Prompt**: Given the BBOX-ADAPTER replication setup: (1) Audit the existing Algorithm 1 (Online Adaptation) implementation — verify it matches the paper's update rule, handles the black-box LLM interface correctly (no gradient access), and correctly manages the adapter state across steps; (2) Implement or complete the evaluation harness for running GPT-3.5 Turbo and Mixtral-8x7B through the BBOX-ADAPTER pipeline on the configured datasets; (3) Ensure baseline models (as specified by experiment_designer) are runnable with the same evaluation loop. Produce clean, commented code with configuration files for each model/dataset combination.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Execute BBOX-ADAPTER and baseline evaluations across GPT-3.5 Turbo and Mixtral-8x7B
- **Prompt**: Execute the full evaluation suite using the code and configurations from code_generator and experiment_designer: (1) Run BBOX-ADAPTER (Algorithm 1, Online Adaptation) on all configured datasets for both GPT-3.5 Turbo and Mixtral-8x7B; (2) Run all baseline models on the same datasets under identical conditions; (3) Collect and log all raw outputs, intermediate adapter states, and final metrics (accuracy, latency, token cost where applicable); (4) Flag any runs that fail or produce anomalous results. Output a results manifest with raw numbers and run metadata.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: code_generator

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Compare replication results against paper-reported numbers and score fidelity
- **Prompt**: Analyze the experimental results from experiment_runner against the BBOX-ADAPTER paper's reported numbers (reference from literature_reviewer): (1) Compute per-dataset, per-model deltas between replicated and reported metrics; (2) Assess whether results fall within acceptable replication tolerance (as defined by experiment_designer); (3) Identify any systematic discrepancies — e.g., consistently lower performance on one model or dataset — and hypothesize causes (API version drift, dataset version, prompt format mismatch); (4) Score overall replication fidelity on a structured rubric. Output a quantitative comparison table and fidelity score.
- **Tokens**: 500 | Compute: light
- **Depends on**: experiment_runner, literature_reviewer

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
