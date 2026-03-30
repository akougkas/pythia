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
- **Time**: 24698ms (24.7s)

## Reasoning
This is a moderate data pipeline task requiring two data sources to be joined and analyzed. The decomposability is low (0.30), meaning steps are mostly sequential — discover data, wrangle/join it, then compute the cost-per-acre metric and report. Minimal parallelism is possible between data discovery and planning, but wrangling depends on discovery, and analysis depends on wrangling.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess the two data sources needed: wildfire suppression costs and human-caused fire acreage by year
- **Prompt**: Find two data sources relevant to this task: (1) annual wildfire suppression costs (ideally broken down by cause or filterable to human-caused fires), and (2) annual acreage burned by human-caused wildfires. Preferred sources include NIFC (National Interagency Fire Center), USDA Forest Service, or equivalent federal/environmental databases. For each source, identify: the URL or dataset name, available year range, key columns (year, suppression cost, acreage, cause), and any data quality concerns. Flag if suppression cost and acreage data must be joined on a common year field.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Ingest, clean, filter to human-caused fires, and join the two datasets on year
- **Prompt**: Using the data sources identified by data_discovery, perform the following steps: (1) Load both datasets (suppression cost by year, acreage by year). (2) Filter both datasets to human-caused fires only — drop lightning-caused or unknown-cause records. (3) Standardize year columns to integer type; normalize cost columns (ensure values are in consistent dollar units, e.g., USD). (4) Join the two datasets on year (inner join to retain only years present in both). (5) Compute a new column: suppression_cost_per_acre = total_suppression_cost / total_acres_burned. (6) Output a clean tabular result with columns: [year, total_suppression_cost, total_acres_burned, cost_per_acre]. Handle missing values and outliers explicitly — document any dropped rows.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Identify the year with the maximum suppression cost per acre and compute the rounded figure
- **Prompt**: Using the joined dataset produced by data_wrangler (columns: year, total_suppression_cost, total_acres_burned, cost_per_acre): (1) Identify the row with the highest value in cost_per_acre. (2) Extract the year and the cost_per_acre value for that row. (3) Round cost_per_acre to the nearest cent (2 decimal places). (4) Perform a basic sanity check — verify the top year is not an artifact of very low acreage (e.g., under 1000 acres) that could skew the ratio. (5) Report: the winning year, the exact rounded cost-per-acre in USD, and a brief note on whether the result is statistically meaningful given the acreage volume.
- **Tokens**: 3000 | Compute: light
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the final answer with supporting context for the environmental science domain
- **Prompt**: Synthesize the output from analyst into a concise, well-structured answer. Include: (1) The direct answer — 'The year with the highest suppression cost per acre for human-caused fires was [YEAR], at $[X.XX] per acre.' (2) A one-paragraph context note explaining what drove costs that year if inferable (e.g., drought conditions, fire severity, policy changes). (3) A small summary table showing the top 3 years by cost-per-acre for reference. (4) Any caveats about data completeness or methodology. Format the output in Markdown.
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
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | light |
| reporter | llama3.1-8b-gpu | llama3.1:8b | 1500 | light |
| **Total** | | | **7000** | |
