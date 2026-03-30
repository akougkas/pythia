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
- **Time**: 54081ms (54.1s)
- **Mode**: 1
- **Confidence**: 0.300

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Find and assess NOAA data sources relevant to total acres burned since Jan 2000
- **Prompt**: Locate the NOAA dataset containing historical fire data from 2000 onwards. Verify that it includes information on total acres burned for each period.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Clean, transform, and join data to extract relevant periods and acres burned values
- **Prompt**: Extract the period with the highest total acres burned from the NOAA dataset. Calculate the total acres burned for that period.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Perform statistical analysis to confirm the identified period has the highest total acres burned
- **Prompt**: Verify that the extracted period indeed holds the record for highest total acres burned. Provide a summary of the analysis.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize findings, including the period and total acres burned, in a clear report
- **Prompt**: Compile the results into a concise report. Include the identified period with the highest total acres burned and the corresponding value.
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
