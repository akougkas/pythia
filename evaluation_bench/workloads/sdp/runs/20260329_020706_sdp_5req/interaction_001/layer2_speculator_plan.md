# Dispatch Plan — SPECULATOR (DRAFT_MODEL)

## Request
> Analyze the following scientific data pipeline task: Find the 3-month period with the highest total acres burned since Jan 2000, according to NOAA. What was the total acres burned in that period? This requires working with 1 data source(s) and involves approximately 5 processing steps. Domain: envir
> ... (317 chars total)

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.388
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Speculator (draft_model)
- **Time**: 61131ms (61.1s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: planner -> data_discovery -> data_wrangler -> analyst

## Agent Assignments

### 1. planner -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Design a strategy to extract the required data from NOAA's dataset for the specified period.
- **Prompt**: Develop a plan to identify the 3-month period with the highest total acres burned since Jan 2000, including relevant data extraction and processing steps. Consider the environmental science domain and the need for accurate results.
- **Tokens**: 500 | Compute: medium
- **Depends on**: (none)

### 2. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Find and assess NOAA's dataset relevant to total acres burned since Jan 2000.
- **Prompt**: Locate the NOAA dataset containing information on total acres burned for each month since January 2000. Evaluate its quality, relevance, and potential issues that may impact analysis.
- **Tokens**: 500 | Compute: light
- **Depends on**: planner

### 3. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Clean, transform, and join data to prepare it for analysis.
- **Prompt**: Extract the required data from NOAA's dataset for the specified period. Clean, transform, and join the data into a suitable format for analysis, considering any potential issues or inconsistencies.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 4. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Perform statistical analysis to identify the 3-month period with the highest total acres burned and calculate the total acres burned in that period.
- **Prompt**: Analyze the prepared data to determine the 3-month period with the highest total acres burned since Jan 2000. Calculate the total acres burned during this period, considering any relevant statistical methods or techniques from environmental science.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: data_wrangler

## Execution DAG
- Stage 0: [planner]
- Stage 1: [data_discovery]
- Stage 2: [data_wrangler]
- Stage 3: [analyst]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| planner | llama3.1-8b-gpu | llama3.1:8b | 500 | medium |
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| data_wrangler | qwen2.5-14b-gpu | qwen2.5:14b | 2000 | medium |
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | heavy |
| **Total** | | | **6000** | |
