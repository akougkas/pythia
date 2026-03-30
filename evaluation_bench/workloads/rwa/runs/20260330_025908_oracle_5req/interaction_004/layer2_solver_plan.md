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
- **Time**: 35456ms (35.5s)

## Reasoning
This is a research replication workflow for the BBOX-ADAPTER paper. Given the moderate complexity score (0.33) and decomposability (0.30), the core stages — literature understanding, experiment design, code implementation, execution, and result analysis — form a natural sequential pipeline with limited parallelism. However, literature review and data/environment discovery can run in parallel upfront, and code generation for Algorithm 1 can overlap with baseline configuration since they are independent implementation tracks.

## Pipeline: literature_reviewer -> data_discovery -> experiment_designer -> code_generator -> code_generator

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Extract BBOX-ADAPTER methodology, Algorithm 1 details, and evaluation protocol from the paper
- **Prompt**: Review the BBOX-ADAPTER paper. Extract: (1) the exact formulation of Algorithm 1 (Online Adaptation) — inputs, outputs, update rules, and hyperparameters; (2) the evaluation datasets and metrics used for GPT-3.5 Turbo and Mixtral-8x7B; (3) the baseline models compared against; (4) any implementation details about the adapter architecture and black-box interaction protocol. Produce a structured summary with section headers for each of these four areas.
- **Tokens**: 1000 | Compute: light
- **Depends on**: (none)

### 2. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Identify and assess all datasets and evaluation environments required for GPT-3.5 Turbo and Mixtral-8x7B evaluations
- **Prompt**: Identify all datasets referenced in the BBOX-ADAPTER replication setup for evaluating GPT-3.5 Turbo and Mixtral-8x7B. For each dataset: (1) confirm public availability and access method (HuggingFace, direct download, API, etc.); (2) note required preprocessing or formatting for LLM prompt inputs; (3) flag any licensing or access constraints. Also assess what API credentials or local inference infrastructure are needed for each model.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 3. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design the full replication experiment plan covering all 9 phases and baseline configurations
- **Prompt**: Using the BBOX-ADAPTER paper methodology summary and dataset inventory, design a complete experiment plan for replication. Structure it across the 9 major phases. For each phase specify: (1) what is being implemented or evaluated; (2) which models (GPT-3.5 Turbo, Mixtral-8x7B) are involved; (3) which baselines must be configured or run; (4) expected outputs and success criteria. Ensure Algorithm 1 (Online Adaptation) is correctly positioned within the phase sequence and its dependencies on model API calls are explicit.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: literature_reviewer, data_discovery

### 4. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement and configure all baseline models for comparative evaluation
- **Prompt**: Implement the baseline models required for BBOX-ADAPTER evaluation comparison. For each baseline: (1) implement or wrap the baseline method as a callable with the same interface as the BBOX-ADAPTER pipeline; (2) configure it for both GPT-3.5 Turbo and Mixtral-8x7B backends; (3) ensure it consumes the same dataset format as the main adapter. Baselines should include at minimum: zero-shot prompting, few-shot prompting, and any other baselines cited in the paper. Structure code so baselines and the adapter can be evaluated in the same evaluation harness.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: literature_reviewer

### 5. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement and configure all baseline models for comparative evaluation
- **Prompt**: Implement the baseline models required for BBOX-ADAPTER evaluation comparison. For each baseline: (1) implement or wrap the baseline method as a callable with the same interface as the BBOX-ADAPTER pipeline; (2) configure it for both GPT-3.5 Turbo and Mixtral-8x7B backends; (3) ensure it consumes the same dataset format as the main adapter. Baselines should include at minimum: zero-shot prompting, few-shot prompting, and any other baselines cited in the paper. Structure code so baselines and the adapter can be evaluated in the same evaluation harness.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: literature_reviewer

## Execution DAG
- Stage 0: [data_discovery, literature_reviewer] (parallel)
- Stage 1: [code_generator, experiment_designer] (parallel)
- Stage 2: [experiment_runner]
- Stage 3: [result_analyzer]
- Stage 4: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | light |
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | heavy |
| **Total** | | | **10000** | |
