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
- **Time**: 59267ms (59.3s)
- **Mode**: 1
- **Confidence**: 0.500

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Find the relevant NOAA dataset containing acres burned data for the period since Jan 2000
- **Prompt**: Locate the NOAA dataset with historical acres burned data from January 2000 onwards and assess its quality for analysis.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Clean, transform, and join the NOAA dataset to extract relevant information on acres burned
- **Prompt**: Clean and preprocess the extracted data from the NOAA dataset to extract the total acres burned for each month since January 2000.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Analyze the data to find the 3-month period with the highest total acres burned and calculate the total acres burned in that period
- **Prompt**: Perform statistical analysis on the preprocessed data to identify the three-month period with the highest total acres burned since January 2000, along with the total acres burned during this period.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize findings and produce a report on the identified period and its total acres burned
- **Prompt**: Compile the results from the analysis into a clear, concise report detailing the three-month period with the highest total acres burned since January 2000 and the corresponding total acres burned.
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
