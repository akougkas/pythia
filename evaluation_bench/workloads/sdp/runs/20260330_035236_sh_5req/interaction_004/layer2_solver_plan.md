# Dispatch Plan — SOLVER (RULE-BASED)

## Request
> Analyze the following scientific data pipeline task: Find the year with the highest suppression cost per acre of human-caused fire. What was the cost per acre, rounded to the nearest cent? This requires working with 2 data source(s) and involves approximately 6 processing steps. Domain: environmenta
> ... (310 chars total)

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.382
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (rule-based)
- **Time**: 0ms (0.0s)

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute data_discovery task
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Prompt**: [stub] Execute data_wrangler task
- **Tokens**: 2000 | Compute: medium
- **Depends on**: (none)

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Prompt**: [stub] Execute analyst task
- **Tokens**: 3000 | Compute: medium
- **Depends on**: (none)

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Prompt**: [stub] Execute reporter task
- **Tokens**: 1500 | Compute: medium
- **Depends on**: (none)

## Execution DAG
- Stage 0: [data_discovery]
- Stage 1: [data_wrangler]
- Stage 2: [analyst]
- Stage 3: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| data_wrangler | qwen2.5-14b-gpu | qwen2.5:14b | 2000 | medium |
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | medium |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | medium |
| **Total** | | | **7000** | |
