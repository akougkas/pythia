# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Analyze the following scientific data pipeline task: Find the 3-month period with the highest total acres burned since Jan 2000, according to NOAA. What was the total acres burned in that period? This requires working with 1 data source(s) and involves approximately 5 processing steps. Domain: envir
> ... (317 chars total)

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.388
- **Domain**: data, environmental_science
- **Decomposability**: 0.30

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 18923ms (18.9s)

## Reasoning
This is a moderately simple data pipeline task with a single data source (NOAA) and ~5 processing steps. The workflow is largely sequential: discover the data, wrangle/process it, then analyze and report. There is minimal parallelism given the linear dependency chain, though data discovery and a lightweight planning step could run concurrently at the start.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess the NOAA wildfire/acres-burned dataset available since January 2000
- **Prompt**: Search for and identify the correct NOAA data source that tracks acres burned by wildfires or fires in the United States from January 2000 to present. Identify the dataset name, URL or access method, file format (CSV, API, NetCDF, etc.), temporal resolution (monthly, weekly, daily), and any known caveats or coverage gaps. Return the dataset metadata and recommended access method.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Retrieve, clean, and reshape the NOAA acres-burned data into a monthly time series from Jan 2000 onward
- **Prompt**: Using the NOAA data source identified by data_discovery, retrieve the acres-burned records spanning January 2000 through the most recent available month. Perform the following steps: (1) parse and load the raw data, (2) standardize date fields to a consistent monthly format (YYYY-MM), (3) handle missing or null values using forward-fill or interpolation where appropriate, (4) aggregate to monthly totals if the source is sub-monthly, (5) output a clean time-series table with columns [year_month, acres_burned]. Flag any anomalies or suspicious values.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute rolling 3-month totals and identify the single 3-month window with the highest total acres burned
- **Prompt**: Using the cleaned monthly acres-burned time series (Jan 2000–present) from data_wrangler, perform the following analysis: (1) compute a rolling 3-month sum across all consecutive month windows (e.g., Jan-Mar 2000, Feb-Apr 2000, …), (2) identify the 3-month window with the maximum total acres burned, (3) report the exact start and end months of that window, (4) report the total acres burned in that window, (5) provide the top-5 windows for context. Use precise arithmetic and clearly state your methodology.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize findings: the peak 3-month period and total acres burned, with brief environmental context
- **Prompt**: Using the results from the analyst agent, produce a concise, well-structured answer to the question: 'What is the 3-month period with the highest total acres burned since January 2000 according to NOAA, and what was the total?' Include: (1) the identified 3-month window (month names and year), (2) the total acres burned figure, (3) a one-paragraph environmental context note about why this period may have seen elevated fire activity (e.g., drought conditions, notable fire events). Keep the response factual and cite the NOAA data source.
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
