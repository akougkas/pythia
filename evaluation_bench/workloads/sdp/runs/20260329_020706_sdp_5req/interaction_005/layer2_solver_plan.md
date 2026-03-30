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
- **Time**: 21629ms (21.6s)

## Reasoning
This is a moderately simple data pipeline task requiring two data sources (NOAA and NIFC fire records) to be fetched, aligned, and differenced. The decomposability is low (0.30), meaning the steps are largely sequential — discover → wrangle → analyze → report. Some parallelism is possible at the data discovery and wrangling stages since the two sources are independent.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NOAA and NIFC annual fire count datasets since 2000
- **Prompt**: Find reliable, accessible data sources for annual wildfire/fire counts from two agencies: (1) NOAA (National Oceanic and Atmospheric Administration) and (2) NIFC (National Interagency Fire Center). Identify dataset URLs, file formats, relevant columns (year, fire count), and coverage years (must include 2000–present). Note any caveats about how each agency defines or counts 'fires' differently. Return source URLs and access instructions for both.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Ingest, clean, and align NOAA and NIFC annual fire count data into a comparable year-indexed table
- **Prompt**: Using the data sources identified by data_discovery, load annual fire count records from both NOAA and NIFC for years 2000 through the most recent available year. Steps: (1) Parse each dataset into a table with columns [year, fire_count]. (2) Normalize column names and data types. (3) Filter to years >= 2000. (4) Align both datasets on the 'year' column via an inner join to ensure only comparable years are included. (5) Output a merged table with columns: [year, noaa_fires, nifc_fires]. Handle missing values explicitly — drop or flag incomplete years.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute the average annual difference in fire counts (NOAA minus NIFC) since 2000
- **Prompt**: Using the merged dataset [year, noaa_fires, nifc_fires] produced by data_wrangler, perform the following computations: (1) For each year, calculate the difference: delta = noaa_fires - nifc_fires. (2) Compute the mean of delta across all available years since 2000. (3) Round the result to the nearest whole number. (4) Also report: the number of years included, the min/max annual difference, and any years where NIFC reported MORE fires than NOAA (negative delta). Return all intermediate values for transparency.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the finding as a clear, cited answer to the original question
- **Prompt**: Using the results from the analyst, produce a concise answer to: 'On average, how many more annual fires are reported by NOAA compared to NIFC since 2000?' Format the response as: (1) A direct one-sentence answer with the rounded integer result. (2) A brief methodology note (data sources used, years covered, how the average was computed). (3) Any important caveats about differences in how NOAA vs. NIFC define or count fire incidents that could affect interpretation. Keep the total response under 200 words.
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
