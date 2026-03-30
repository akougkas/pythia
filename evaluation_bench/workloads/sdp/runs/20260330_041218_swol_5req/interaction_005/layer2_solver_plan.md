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
- **Time**: 25064ms (25.1s)

## Reasoning
This is a moderately simple data pipeline task requiring two data sources (NOAA and NIFC fire records) to be fetched, aligned, and compared. The complexity is low (0.39) and decomposability is modest (0.30), suggesting a linear pipeline rather than heavy parallelism. The core challenge is sourcing and harmonizing two datasets across matching years (2000–present), then computing a straightforward annual average difference.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NOAA and NIFC annual fire count datasets since 2000
- **Prompt**: Find accessible data sources for annual wildfire/fire counts from two agencies: (1) NOAA — identify which NOAA dataset or product reports annual fire counts (e.g., NOAA's Storm Events Database, NOAA Climate.gov, or affiliated sources), and (2) NIFC (National Interagency Fire Center) — locate their annual wildfire statistics table (nifc.gov/fire-information/statistics). For each source, document: the URL or access method, the years available (filter to 2000–present), the column/field representing total annual fire count, and any caveats (e.g., reporting methodology differences, what counts as a 'fire'). Return a structured summary of both sources ready for ingestion.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Ingest, clean, and align NOAA and NIFC annual fire count data into a comparable year-indexed table
- **Prompt**: Using the data sources identified by data_discovery, ingest and clean both datasets: (1) Parse NOAA annual fire counts for each year from 2000 to the most recent available year. (2) Parse NIFC annual fire counts for the same year range from their published statistics. (3) Align both datasets on a common 'year' key — retain only years present in BOTH datasets. (4) Handle any missing values, formatting issues, or unit inconsistencies (e.g., ensure both are raw fire count integers, not acreage). (5) Output a clean merged table with columns: [year, noaa_fire_count, nifc_fire_count]. Flag any years with data gaps or anomalies.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute the average annual difference in fire counts between NOAA and NIFC since 2000
- **Prompt**: Using the merged dataset from data_wrangler with columns [year, noaa_fire_count, nifc_fire_count]: (1) For each year, compute the difference: diff = noaa_fire_count - nifc_fire_count. (2) Calculate the mean of all annual differences across all available years since 2000. (3) Round the result to the nearest whole number. (4) Also report: the per-year differences table, the min/max difference years, and whether NOAA consistently reports more fires than NIFC or if it varies by year. (5) Note any years where one agency's count is significantly higher and provide a brief methodological explanation if possible (e.g., NOAA may include prescribed burns or different fire size thresholds).
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the final answer and key findings in a clear, concise response
- **Prompt**: Using the analysis from analyst, produce a final answer report for the question: 'On average, how many more annual fires are reported by NOAA compared to NIFC since 2000?' Structure your response as: (1) **Direct Answer**: State the rounded whole-number average difference prominently. (2) **Data Coverage**: Specify which years were included in the analysis and how many data points. (3) **Key Observations**: Note any trends, outliers, or important caveats about how NOAA and NIFC differ in fire reporting methodology. (4) **Confidence Note**: Flag any data sourcing limitations (e.g., if NOAA fire data required indirect sourcing). Keep the report concise and suitable for a scientific computing context.
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
