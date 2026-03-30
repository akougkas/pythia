# Dispatch Plan — SOLVER (RULE-BASED)

## Request
> Replicate the research paper 'All In One': The paper "All-in-one simulation-based inference" has been reproduced. This involves 5 major phases and 233 total subtasks. The workflow includes: Variance Exploding SDE (VESDE) is implemented, as described in A2.1; The Simformer model, training process and
> ... (479 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.434
- **Domain**: ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (rule-based)
- **Time**: 0ms (0.0s)

## Pipeline: literature_reviewer -> experiment_designer -> code_generator -> experiment_runner -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute literature_reviewer task
- **Tokens**: 1000 | Compute: medium
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute experiment_designer task
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Prompt**: [stub] Execute code_generator task
- **Tokens**: 4000 | Compute: medium
- **Depends on**: (none)

### 4. experiment_runner -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute experiment_runner task
- **Tokens**: 3000 | Compute: medium
- **Depends on**: (none)

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute result_analyzer task
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]
- Stage 3: [experiment_runner]
- Stage 4: [result_analyzer]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | medium |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | medium |
| experiment_runner | llama3.1-8b-gpu | llama3.1:8b | 3000 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| **Total** | | | **10000** | |
