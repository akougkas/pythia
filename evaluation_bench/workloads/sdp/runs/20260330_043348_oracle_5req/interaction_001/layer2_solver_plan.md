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
- **Time**: 23284ms (23.3s)

## Reasoning
This is a moderately simple data pipeline task with a single data source (NOAA) and ~5 processing steps. The workflow is mostly sequential: discover the data, wrangle/process it, then analyze and report. There is limited parallelism given the linear dependency chain, but data discovery and literature/context review can run in parallel at the start.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NOAA wildfire/acres burned datasets available since January 2000
- **Prompt**: Search for NOAA datasets that track wildfire acres burned in the United States from January 2000 to present. Identify the specific dataset name, URL, file format (CSV, NetCDF, API, etc.), temporal resolution (monthly, annual, etc.), and any access requirements. Confirm the dataset covers the full period since Jan 2000 and contains acres burned as a variable. Return dataset metadata including source URL, column names, and any caveats about data completeness or methodology.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Download, clean, and reshape NOAA acres burned data into a monthly time series from Jan 2000 onward
- **Prompt**: Using the NOAA dataset identified in the previous step, download and ingest the acres burned data. Perform the following processing steps: (1) Filter records to dates >= January 2000; (2) Aggregate to monthly total acres burned if data is at finer granularity; (3) Handle missing values — document any gaps and apply forward-fill or interpolation if appropriate; (4) Produce a clean time series DataFrame with columns [year, month, date, acres_burned]; (5) Validate that all months from Jan 2000 to the latest available date are represented. Output the cleaned dataset and a brief data quality summary.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute all 3-month rolling windows and identify the window with the maximum total acres burned
- **Prompt**: Using the cleaned monthly acres burned time series from the data wrangler, perform the following analysis: (1) Compute a rolling 3-month sum of acres burned across the entire time series (Jan 2000 to latest available month); (2) Identify the 3-month window (start month, end month) with the highest total acres burned; (3) Report the exact months in that window and the total acres burned; (4) Provide the top 5 worst 3-month periods for context; (5) Check whether the peak window aligns with known wildfire seasons or anomalous events (e.g., 2020 California fires). Return results as a structured summary with the winning window clearly labeled.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the findings and produce a concise, cited answer to the original question
- **Prompt**: Based on the analyst's results, produce a clear and concise answer to the question: 'What is the 3-month period with the highest total acres burned since January 2000 according to NOAA, and what was the total acres burned?' Structure your response as: (1) Direct answer — the 3-month period and total acreage; (2) Data source citation — NOAA dataset name, URL, and date accessed; (3) Brief context — why this period was anomalous (e.g., drought, wind events, geography); (4) Runner-up periods table (top 5); (5) Any caveats about data completeness or methodology that affect confidence in the result.
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
