# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Replicate the research paper 'Bbox': The BBOX-ADAPTER approach for adapting black-box LLMs has been reproduced completely. This involves 9 major phases and 421 total subtasks. The workflow includes: Algorithm 1 (Online Adaptation) has been implemented correctly.; The evaluation environments and data
> ... (436 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.332
- **Domain**: data, ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 54123ms (54.1s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: planner -> experiment_designer -> code_generator

## Agent Assignments

### 1. planner -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Design a detailed strategy for replicating the BBOX-ADAPTER approach, including task decomposition and resource allocation.
- **Prompt**: Develop a step-by-step plan for reproducing 'Bbox': The BBOX-ADAPTER approach, considering its 9 major phases and 421 subtasks. Ensure that each phase is well-defined and feasible to execute.
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. experiment_designer -> claude-haiku-cloud (claude-haiku-4-5-20251001)
- **Role**: Design replication experiments for the BBOX-ADAPTER approach, including setup of evaluation environments and datasets.
- **Prompt**: Create a detailed design for replicating the experiments in 'Bbox': The BBOX-ADAPTER approach, focusing on setting up evaluation environments and datasets for GPT-3.5 Turbo and Mixtral-8x7B.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: planner

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the necessary code for replicating the BBOX-ADAPTER approach, including algorithm implementation and model configuration.
- **Prompt**: Write the required code to implement Algorithm 1 (Online Adaptation) and configure baseline models for evaluations in 'Bbox': The BBOX-ADAPTER approach.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

## Execution DAG
- Stage 0: [planner]
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | claude-haiku-cloud | claude-haiku-4-5-20251001 | 500 | medium |
| experiment_designer | claude-haiku-cloud | claude-haiku-4-5-20251001 | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| **Total** | | | **6000** | |
