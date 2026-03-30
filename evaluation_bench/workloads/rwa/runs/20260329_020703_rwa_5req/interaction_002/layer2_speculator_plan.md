# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Replicate the research paper 'All In One': The paper "All-in-one simulation-based inference" has been reproduced. This involves 5 major phases and 233 total subtasks. The workflow includes: Variance Exploding SDE (VESDE) is implemented, as described in A2.1; The Simformer model, training process and
> ... (479 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.434
- **Domain**: ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 57854ms (57.9s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: planner -> code_gen -> tester

## Agent Assignments

### 1. planner -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Decompose the research paper's 5 major phases and 233 total subtasks into a manageable workflow for replication.
- **Prompt**: Break down the 'All-in-one simulation-based inference' paper into its constituent parts, identifying key tasks and dependencies. Consider the implementation of VESDE, Simformer model, training process, inference process, NPE, NRE, and NLE methods.
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the VESDE algorithm, Simformer model, training process, inference process, NPE, NRE, and NLE methods in code.
- **Prompt**: Write the necessary Python code to implement each of the mentioned models and methods. Ensure that the code is well-documented and follows best practices for readability and maintainability.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 3. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Test the implemented models and methods to ensure correctness and accuracy.
- **Prompt**: Develop a testing framework to validate the performance of each model and method. This includes generating test data, running experiments, and analyzing results to identify any issues or areas for improvement.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

## Execution DAG
- Stage 0: [planner]
- Stage 1: [code_gen]
- Stage 2: [tester]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | claude-haiku-cloud | claude-haiku-4-5-20251001 | 500 | medium |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| **Total** | | | **6000** | |
