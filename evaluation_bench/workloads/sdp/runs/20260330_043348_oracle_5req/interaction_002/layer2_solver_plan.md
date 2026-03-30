# Dispatch Plan — SOLVER (LLM: CLAUDE-SONNET-4-6)

## Request
> Analyze the following scientific data pipeline task: Which NIFC geographic area intersects with the most US states? Give the abbreviation of the geographic area This requires working with 2 data source(s) and involves approximately 6 processing steps. Domain: environmental science.

## Intent
- **Task type**: data_pipeline
- **Complexity**: 0.331
- **Domain**: data, environmental_science
- **Decomposability**: 0.20

## Metadata
- **Source**: Solver (LLM: claude-sonnet-4-6)
- **Time**: 21982ms (22.0s)

## Reasoning
This is a moderate-complexity geospatial data pipeline task requiring two data sources (NIFC geographic areas and US state boundaries) and a spatial intersection analysis. The decomposability is low (0.20), meaning steps are largely sequential — data must be found and loaded before it can be wrangled, and wrangling must complete before the intersection analysis can run. The pipeline is straightforward enough to resolve in 3 focused agents without heavy parallelism.

## Pipeline: data_discovery -> data_wrangler -> analyst

## Agent Assignments

### 1. data_discovery -> llama3.1-8b-gpu (llama3.1:8b)
- **Role**: Locate and assess the two required data sources: NIFC geographic area boundaries and US state boundaries
- **Prompt**: Find the two data sources needed for a geospatial intersection analysis:
1. NIFC (National Interagency Fire Center) geographic area boundaries — identify the canonical source (e.g., NIFC ArcGIS REST API, NIFC Open Data portal, or a publicly available GeoJSON/Shapefile). Document the field that contains the geographic area abbreviation.
2. US State boundaries — identify a reliable public source (e.g., US Census Bureau TIGER/Line shapefiles, or a GeoJSON from a public CDN).
For each source, provide: the URL or access method, the relevant geometry and attribute fields, the CRS/projection, and any download/API instructions needed for the next stage.
- **Tokens**: 500 | Compute: light
- **Depends on**: (none)

### 2. data_wrangler -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Load, reproject, and prepare both datasets for spatial intersection analysis
- **Prompt**: Using the data sources identified in the previous step, perform the following data preparation steps:
1. Load the NIFC geographic area boundaries (GeoJSON or Shapefile) into a GeoDataFrame using GeoPandas.
2. Load the US state boundaries into a second GeoDataFrame.
3. Ensure both datasets share the same CRS (reproject to EPSG:4326 or a suitable planar CRS like EPSG:5070 Albers Equal Area for accurate intersection).
4. Clean the data: drop null geometries, fix any invalid geometries using `.buffer(0)`, and retain only the relevant attribute columns (NIFC area abbreviation, state name/FIPS).
5. Output two clean, CRS-aligned GeoDataFrames ready for spatial join/intersection.
Provide the Python code (using geopandas, shapely) to accomplish these steps.
- **Tokens**: 2000 | Compute: medium
- **Depends on**: data_discovery

### 3. analyst -> qwen2.5-14b-gpu (qwen2.5:14b)
- **Role**: Perform spatial intersection to count how many US states each NIFC geographic area overlaps, then identify the area with the maximum count
- **Prompt**: Using the two clean GeoDataFrames prepared in the previous step (NIFC geographic areas and US states), perform the following analysis:
1. Run a spatial join (gpd.sjoin) using predicate 'intersects' to find all (NIFC area, US state) pairs that spatially overlap.
2. For each NIFC geographic area, count the number of distinct US states it intersects.
3. Identify the NIFC geographic area with the highest state intersection count.
4. Extract and report the **abbreviation** of that geographic area (e.g., 'SW', 'RM', 'NR', etc.).
5. Provide a summary table showing all NIFC areas and their respective state intersection counts for verification.
Provide the Python code to perform the spatial join and aggregation, and clearly state the final answer: the abbreviation of the NIFC geographic area that intersects the most US states.
- **Tokens**: 3000 | Compute: heavy
- **Depends on**: data_wrangler

## Execution DAG
- Stage 0: [data_discovery]
- Stage 1: [data_wrangler]
- Stage 2: [analyst]

## Resource Summary

| Agent | Fleet Member | Model | Tokens | Compute |
|-------|-------------|-------|--------|---------|
| data_discovery | llama3.1-8b-gpu | llama3.1:8b | 500 | light |
| data_wrangler | qwen2.5-14b-gpu | qwen2.5:14b | 2000 | medium |
| analyst | qwen2.5-14b-gpu | qwen2.5:14b | 3000 | heavy |
| **Total** | | | **5500** | |
