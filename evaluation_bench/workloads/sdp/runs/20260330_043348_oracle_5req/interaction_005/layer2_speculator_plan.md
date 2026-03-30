# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Analyze the following scientific data pipeline task: On average, how many more annual fires are reported by NOAA compared to NIFC since 2000? Round to the nearest whole number. This requires working with 2 data source(s) and involves approximately 7 processing steps. Domain: environmental science.

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.387
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 56946ms (56.9s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Find and assess the NOAA and NIFC data sources for annual fire reports since 2000
- **Prompt**: Identify the relevant datasets from NOAA and NIFC that contain annual fire reports, and evaluate their quality and relevance to the task at hand.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Clean, transform, and join the NOAA and NIFC data sources for annual fire reports since 2000
- **Prompt**: Merge the two datasets into a single table, handling any discrepancies or inconsistencies in formatting or structure.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Calculate the average annual fire reports for NOAA and NIFC since 2000, and compute the difference between them
- **Prompt**: Perform statistical analysis to calculate the mean number of fires reported by each agency, and then find the difference between these two means.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Round the result to the nearest whole number and produce a final answer
- **Prompt**: Take the calculated difference between NOAA and NIFC fire reports, round it to the nearest whole number, and present this as the final answer.
- **Tokens**: 1500 | Compute: light
- **Depends on**: analyst

## Execution DAG
- Stage 0: [data_discovery]
- Stage 1: [data_wrangler]
- Stage 2: [analyst]
- Stage 3: [reporter]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| data_wrangler | qwen2.5-14b-gpu | qwen2.5:14b | 2000 | medium |
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | heavy |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | light |
| **Total** | | | **7000** | |
