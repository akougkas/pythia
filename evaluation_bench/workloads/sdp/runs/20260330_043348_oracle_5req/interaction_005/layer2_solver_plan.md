# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Analyze the following scientific data pipeline task: On average, how many more annual fires are reported by NOAA compared to NIFC since 2000? Round to the nearest whole number. This requires working with 2 data source(s) and involves approximately 7 processing steps. Domain: environmental science.

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.387
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 21767ms (21.8s)

## Reasoning
This is a moderately simple data pipeline task requiring two data sources (NOAA and NIFC fire records since 2000) and roughly 7 processing steps. The discovery of both sources can happen in parallel, but wrangling and analysis must follow. A single reporter can synthesize the numeric answer at the end. Low decomposability (0.30) means stages are mostly sequential after the parallel discovery phase.

## Pipeline: data_discovery -> data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NIFC annual fire report data since 2000
- **Prompt**: Find the NIFC (National Interagency Fire Center) data source that reports annual wildfire/fire counts in the United States from 2000 onward. Identify the dataset name, URL or access method, time coverage, and the specific field/column that represents annual fire count. Note any caveats about how NIFC defines or counts fires compared to other agencies.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NIFC annual fire report data since 2000
- **Prompt**: Find the NIFC (National Interagency Fire Center) data source that reports annual wildfire/fire counts in the United States from 2000 onward. Identify the dataset name, URL or access method, time coverage, and the specific field/column that represents annual fire count. Note any caveats about how NIFC defines or counts fires compared to other agencies.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 3. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Ingest, clean, and align NOAA and NIFC annual fire count data into a comparable format
- **Prompt**: Using the sources identified by both data_discovery agents, retrieve and clean the NOAA and NIFC annual fire count datasets for years 2000 through the most recent available year. Steps: (1) Extract the year and annual fire count columns from each source. (2) Standardize column names (year, noaa_fires, nifc_fires). (3) Filter to years >= 2000. (4) Align both datasets on the 'year' column via an inner join to ensure only overlapping years are compared. (5) Handle any missing values or anomalies. Output a clean merged table with columns: year, noaa_fires, nifc_fires.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 4. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute the average annual difference in fire counts (NOAA minus NIFC) since 2000
- **Prompt**: Using the merged dataset (year, noaa_fires, nifc_fires) produced by the data_wrangler: (1) Compute the per-year difference: diff = noaa_fires - nifc_fires for each year. (2) Compute the mean of all per-year differences. (3) Round the result to the nearest whole number. (4) Report the mean difference, the range of years used, the number of data points, and a brief note on whether NOAA consistently reports more fires than NIFC or if there is variance.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 5. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the final answer and provide environmental science context
- **Prompt**: Using the analyst's computed mean annual difference between NOAA and NIFC fire counts since 2000, produce a concise final answer in this format: (1) State the rounded whole-number answer clearly (e.g., 'On average, NOAA reports X more annual fires than NIFC since 2000.'). (2) Briefly explain any methodological reasons why NOAA and NIFC fire counts might differ (e.g., reporting scope, fire size thresholds, data collection methods). (3) Note any caveats or limitations in the comparison (e.g., partial year coverage, differing definitions of 'fire').
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
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| data_wrangler | qwen2.5-14b-gpu | qwen2.5:14b | 2000 | medium |
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | medium |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | light |
| **Total** | | | **7500** | |
