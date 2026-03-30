# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Analyze the following scientific data pipeline task: Find the year with the highest suppression cost per acre of human-caused fire. What was the cost per acre, rounded to the nearest cent? This requires working with 2 data source(s) and involves approximately 6 processing steps. Domain: environmenta
> ... (310 chars total)

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.382
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 23187ms (23.2s)

## Reasoning
This is a moderate data pipeline task requiring two data sources to be located, joined, and analyzed. The low decomposability (0.30) means stages are mostly sequential — data must be found before it can be wrangled, and wrangled before it can be analyzed. The task is straightforward once data is in hand: compute cost-per-acre by year for human-caused fires, then find the maximum.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate the two data sources: wildfire suppression costs and human-caused fire acreage by year
- **Prompt**: Find two data sources needed to answer: 'Which year had the highest suppression cost per acre for human-caused fires?' You need: (1) annual wildfire suppression cost data (likely from USFS, NIFC, or similar federal agency), and (2) annual acreage burned by human-caused fires (from NIFC, USFS Wildfire Statistics, or equivalent). For each source, provide: the dataset name, URL or access path, relevant columns/fields (year, cost, cause classification, acreage), and any known caveats (e.g., inflation adjustments, reporting gaps). Domain: environmental science.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Ingest, clean, and join suppression cost and human-caused acreage datasets by year
- **Prompt**: Given the two data sources identified (wildfire suppression costs by year, and human-caused fire acreage by year), perform the following steps: (1) Load both datasets. (2) Standardize the year column as an integer key in both. (3) Filter the acreage dataset to human-caused fires only (exclude lightning-caused or unknown). (4) Aggregate total suppression cost per year and total human-caused acreage per year if not already annual totals. (5) Inner-join the two datasets on year. (6) Output a clean table with columns: [year, total_suppression_cost_usd, human_caused_acres]. Flag any years with missing or null values.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute cost-per-acre by year and identify the year with the maximum value
- **Prompt**: Using the cleaned joined table with columns [year, total_suppression_cost_usd, human_caused_acres]: (1) Compute cost_per_acre = total_suppression_cost_usd / human_caused_acres for each year. (2) Round each value to the nearest cent (2 decimal places). (3) Identify the year with the highest cost_per_acre. (4) Report that year and its cost_per_acre value. (5) Provide the top-5 years ranked by cost_per_acre as supporting context. Show all intermediate calculations clearly.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the final answer with supporting context and data provenance
- **Prompt**: Produce a concise final answer to the question: 'What year had the highest wildfire suppression cost per acre for human-caused fires, and what was that cost per acre (rounded to the nearest cent)?' Structure your response as: (1) Direct answer: year and cost-per-acre value. (2) Data sources used (names, URLs, years covered). (3) Brief methodology note (how cost-per-acre was computed, any filters applied). (4) One-sentence caveat if applicable (e.g., inflation, data completeness). Keep the total response under 300 words.
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
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | medium |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | light |
| **Total** | | | **7000** | |
