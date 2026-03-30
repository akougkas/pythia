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
- **Time**: 20607ms (20.6s)

## Reasoning
This is a moderately simple data pipeline task requiring two data sources (NOAA and NIFC fire records) to be fetched, aligned, and compared. The complexity is low (0.39) and decomposability is modest (0.30), suggesting a linear pipeline rather than a heavily parallelized one. The core challenge is harmonizing annual fire counts from two different agencies since 2000 and computing a mean difference — straightforward statistical work once the data is in hand.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess NOAA and NIFC annual fire count datasets since 2000
- **Prompt**: Find accessible data sources for annual wildfire/fire counts from two agencies: (1) NOAA (National Oceanic and Atmospheric Administration) and (2) NIFC (National Interagency Fire Center). Focus on records from year 2000 onward. Identify the specific dataset names, URLs, file formats (CSV, API, HTML table, etc.), relevant column names (year, fire count), and any known caveats about how each agency defines or counts 'fires'. Return a structured summary of both sources including access method.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Retrieve, clean, and align annual fire counts from both NOAA and NIFC into a unified year-indexed table
- **Prompt**: Using the data sources identified by data_discovery, perform the following steps: (1) Fetch annual fire count records from NOAA for years 2000–present. (2) Fetch annual fire count records from NIFC for the same date range. (3) Standardize column names to [year, noaa_fires, nifc_fires]. (4) Align both datasets on the 'year' column using an inner join to retain only years present in both sources. (5) Handle any missing values, duplicate years, or unit mismatches. Output the final merged table as a clean, year-indexed dataset ready for analysis.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute the average annual difference in fire counts (NOAA minus NIFC) since 2000
- **Prompt**: Using the cleaned, merged dataset from data_wrangler (columns: year, noaa_fires, nifc_fires), perform the following analysis: (1) For each year, compute the difference: diff = noaa_fires - nifc_fires. (2) Calculate the mean of these annual differences across all available years since 2000. (3) Round the result to the nearest whole number. (4) Also report: the number of years included, the min and max annual difference, and any years where the sign flips (NIFC reports more than NOAA). Provide all intermediate values for transparency.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the findings and deliver the final rounded answer with context
- **Prompt**: Using the results from analyst, produce a concise final answer to the question: 'On average, how many more annual fires are reported by NOAA compared to NIFC since 2000?' Structure your response as: (1) Direct answer (rounded whole number with sign — positive means NOAA reports more, negative means NIFC reports more). (2) Brief methodology note (years covered, data sources). (3) Any important caveats about how NOAA vs NIFC define or count fires that may affect interpretation of the result.
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
