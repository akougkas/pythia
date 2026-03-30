# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Replicate the research paper 'Bam': The core contributions of the paper "Batch and match: black-box variational inference with a score-based divergence" have been reproduced. This involves 4 major phases and 1020 total subtasks. The workflow includes: The core variational inference algorithms studie
> ... (469 chars total)

## Intent
- **Task type**: research_workflow
- **Complexity**: 0.467
- **Domain**: ml, research
- **Decomposability**: 0.45

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 82512ms (82.5s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: literature_reviewer -> planner -> code_gen -> tester -> result_analyzer

## Agent Assignments

### 1. literature_reviewer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Understand the core contributions of the paper 'Batch and match: black-box variational inference with a score-based divergence' and extract relevant methods for replication.
- **Prompt**: Please review the research paper 'Batch and match: black-box variational inference with a score-based divergence' and identify the key algorithms, results, and methods that need to be replicated. Provide a detailed summary of the core contributions and their implications for our workflow.
- **Tokens**: 1000 | Compute: medium
- **Depends on**: (none)

### 2. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design a replication strategy that breaks down the complex workflow into manageable stages, taking into account the 4 major phases and 1020 total subtasks.
- **Prompt**: Develop a detailed plan for replicating the research paper 'Batch and match: black-box variational inference with a score-based divergence'. Identify potential bottlenecks and areas where tasks can be parallelized. Provide a clear outline of the replication strategy, including specific tasks and timelines.
- **Tokens**: 500 | Compute: medium
- **Depends on**: literature_reviewer

### 3. code_gen -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Implement the core variational inference algorithms studied in the paper, ensuring that they are accurate and efficient.
- **Prompt**: Write high-quality code to implement the variational inference algorithms discussed in the research paper. Ensure that the implementation is accurate, efficient, and well-documented. Provide a clear explanation of any assumptions or simplifications made during implementation.
- **Tokens**: 4000 | Compute: heavy
- **Depends on**: planner

### 4. tester -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Test the implemented algorithms and results, ensuring that they match those reported in the paper.
- **Prompt**: Develop a comprehensive testing plan to validate the accuracy of the implemented variational inference algorithms. Compare the results with those reported in the research paper, identifying any discrepancies or areas for improvement.
- **Tokens**: 1500 | Compute: medium
- **Depends on**: code_gen

### 5. result_analyzer -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Analyze and compare the results of section 5.1, Figure 5.3, and Figure E.6 from Section 5.2 with those reported in the paper.
- **Prompt**: Compare the results obtained from replicating the research paper with those reported in the original paper. Analyze any discrepancies or differences, providing a clear explanation of their implications for our workflow.
- **Tokens**: 2000 | Compute: light
- **Depends on**: tester

## Execution DAG
- Stage 0: [literature_reviewer]
- Stage 1: [planner]
- Stage 2: [code_gen]
- Stage 3: [tester]
- Stage 4: [result_analyzer]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| literature_reviewer | llama3.1-8b-gpu | llama3.1:8b | 1000 | medium |
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| code_gen | qwen2.5-14b-gpu | qwen2.5:14b | 4000 | heavy |
| tester | qwen2.5-14b-gpu | qwen2.5:14b | 1500 | medium |
| result_analyzer | llama3.1-8b-gpu | llama3.1:8b | 2000 | light |
| **Total** | | | **9000** | |
