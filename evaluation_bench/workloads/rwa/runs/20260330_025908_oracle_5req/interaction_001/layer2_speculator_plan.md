# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Replicate the research paper 'Adaptive Pruning': The paper "APT: Adaptive Pruning and Tuning Pretrained Language Models for Efficient Training and Inference" has been reproduced This involves 5 major phases and 171 total subtasks. The workflow includes: The required pre-trained models, datasets, and
> ... (391 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.337
- **Domain**: data, ml, research
- **Decomposability**: 0.30

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 56340ms (56.3s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: planner -> experiment_designer -> code_generator

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design an algorithmic strategy for replicating the Adaptive Pruning workflow, considering the existing baselines and LoRA setup.
- **Prompt**: Develop a detailed plan to replicate the APT research paper, including task decomposition, resource allocation, and potential bottlenecks. Consider the 5 major phases and 171 subtasks outlined in the original paper.
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. experiment_designer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design replication experiments for each phase, ensuring consistency with the original paper and accounting for potential variations.
- **Prompt**: Create a set of experiment designs that replicate the Adaptive Pruning workflow, including parameters, metrics, and expected outcomes. Ensure these designs align with the existing baselines and LoRA setup.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: planner

### 3. code_generator -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Generate research code to implement the Adaptive Pruning workflow, including necessary libraries, functions, and data structures.
- **Prompt**: Write a set of Python scripts that implement the Adaptive Pruning algorithm, incorporating existing baselines and LoRA setup. Ensure these scripts are modular, efficient, and well-documented.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: experiment_designer

## Execution DAG
- Stage 0: [planner]
- Stage 1: [experiment_designer]
- Stage 2: [code_generator]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| experiment_designer | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| code_generator | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| **Total** | | | **6000** | |
