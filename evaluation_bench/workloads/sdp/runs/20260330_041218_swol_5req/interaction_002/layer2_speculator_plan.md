# Dispatch Plan — SPECULATOR (CACHE)

## Request
> Analyze the following scientific data pipeline task: Which NIFC geographic area intersects with the most US states? Give the abbreviation of the geographic area This requires working with 2 data source(s) and involves approximately 6 processing steps. Domain: environmental science.

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.331
- **Domain**: data, environmental_science
- **Decomposability**: 0.20

## Metadata
- **Source**: Speculator (cache)
- **Time**: 0ms (0.0s)
- **Mode**: 1
- **Confidence**: 0.500

## Reasoning
This is a moderately simple data pipeline task with a single data source (NOAA wildfire/acres burned data) and ~5 processing steps. The workflow is largely sequential: first discover and retrieve the data, then wrangle/aggregate it, then analyze for the rolling 3-month maximum, then report. There is limited parallelism given the linear dependency chain, though data discovery and a light planning step can run concurrently at the start.

## Pipeline: data_discovery -> data_wrangler -> analyst -> reporter

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate the correct NOAA dataset for acres burned (wildfire statistics) since January 2000
- **Prompt**: Search for and identify the specific NOAA data source(s) that contain monthly or annual wildfire acres burned statistics for the United States since January 2000. Identify the dataset name, URL or access method, file format (CSV, API, etc.), temporal resolution (monthly preferred), and any relevant field names (e.g., 'acres_burned', 'date', 'state'). Note any data gaps or caveats. Return a structured summary of the data source including how to programmatically retrieve it.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Retrieve, clean, and reshape the NOAA acres-burned dataset into a monthly time series from Jan 2000 onward
- **Prompt**: Using the data source identified by data_discovery, retrieve the NOAA wildfire acres burned dataset. Steps: (1) Download or access the raw data. (2) Parse and normalize dates to monthly granularity (YYYY-MM). (3) Ensure the series spans January 2000 to the most recent available month. (4) Handle missing values (document any gaps). (5) Produce a clean, sorted monthly time series with columns: [year_month, acres_burned]. Output the cleaned dataset as a table or structured list ready for rolling analysis.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Compute all rolling 3-month window totals and identify the window with the maximum total acres burned
- **Prompt**: Given the cleaned monthly acres-burned time series (from data_wrangler), perform the following analysis: (1) Compute a rolling 3-month sum across the entire series from January 2000 onward (e.g., Jan+Feb+Mar 2000, Feb+Mar+Apr 2000, ...). (2) Identify the 3-month window (by start and end month/year) that yields the highest total acres burned. (3) Report the exact start month, end month, and total acres burned for that peak window. (4) Provide the top 5 windows for context. Include any relevant notes about data quality or anomalies that may affect the result.
- **Tokens**: 3000 | Compute: medium
- **Depends on**: data_wrangler

### 4. reporter -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Summarize the findings into a clear, concise answer with supporting context
- **Prompt**: Using the analysis results from the analyst agent, produce a clear final answer to the question: 'What is the 3-month period with the highest total acres burned since January 2000 according to NOAA, and what was the total acres burned?' Structure the response as: (1) Direct answer stating the 3-month period and total acres burned. (2) Brief context (e.g., was this during a known severe fire season? which region/states contributed?). (3) Data provenance: cite the specific NOAA dataset used, its URL, and the date range covered. (4) Any caveats about data completeness or methodology.
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
