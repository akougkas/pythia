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
- **Time**: 22621ms (22.6s)

## Reasoning
This is a moderately simple data pipeline task with low decomposability (0.30), meaning the steps are mostly sequential rather than parallelizable. The core work is: find the NOAA data source, retrieve and wrangle it, then analyze for the peak 3-month rolling window. A light data_discovery agent can locate the exact NOAA dataset, a data_wrangler can clean and structure it, an analyst can compute the rolling sums and find the peak period, and a reporter can surface the answer. Minimal parallelism is possible — discovery must precede wrangling, which must precede analysis.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate the specific NOAA wildfire/acres-burned dataset covering Jan 2000 to present
- **Prompt**: Search for the official NOAA data source that tracks wildfire acres burned in the United States from January 2000 onward. Identify the exact dataset name, URL, file format (CSV, API, etc.), and relevant column names (e.g., date, acres burned, region). Note any access requirements or pagination. Output a structured summary: source name, URL, format, temporal coverage, and key fields needed for downstream analysis.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Retrieve, clean, and reshape the NOAA acres-burned data into a monthly time series from Jan 2000 onward
- **Prompt**: Using the NOAA data source identified by data_discovery, retrieve all wildfire acres-burned records from January 2000 to the most recent available date. Perform the following steps: (1) Parse and standardize date fields to YYYY-MM format. (2) Aggregate total acres burned per calendar month. (3) Handle missing months by filling with zero or flagging gaps. (4) Output a clean monthly time series as a table with columns [year_month, total_acres_burned]. Ensure no duplicate records and validate that the sum across all months is internally consistent.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute rolling 3-month totals and identify the peak period and its total acres burned
- **Prompt**: Using the clean monthly acres-burned time series from data_wrangler, perform the following analysis: (1) Compute a rolling 3-month sum over the full time series (e.g., Jan+Feb+Mar, Feb+Mar+Apr, …). (2) Identify the 3-month window with the highest total acres burned — record its start month, end month, and total acres burned. (3) Provide the top 5 candidate windows for context. (4) Verify the result is not an artifact of missing data or outliers. Output the winning period (e.g., 'June–August 2020') and the exact total acres burned figure, plus a brief note on runner-up periods.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the findings into a clear, cited answer with the peak 3-month period and total acres burned
- **Prompt**: Using the results from the analyst, produce a concise final answer to the question: 'What is the 3-month period with the highest total acres burned since January 2000, according to NOAA, and what was the total?' Structure the response as: (1) Direct answer — the period and total acres burned. (2) Data provenance — NOAA source name, URL, and date range used. (3) Brief context — how this period compares to the next highest windows. Keep the answer factual, cite the NOAA source, and flag any data caveats (e.g., incomplete months, regional scope).
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
