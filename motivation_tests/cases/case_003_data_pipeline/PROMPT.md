# Case 003: CSV Data Pipeline

## Objective

Design a data pipeline that reads CSV files from an input directory,
applies a series of configurable transformations (filter rows, rename columns,
compute derived columns), and writes the results to an output directory.

## Constraints

- Must use `pandas` for data manipulation
- Pipeline steps defined in a `pipeline.yaml`
- Support chaining arbitrary transforms
- Dry-run mode that shows what would happen without writing
- Logging with configurable verbosity

## Expected Deliverables

- `pipeline.py` — main orchestrator
- `transforms.py` — individual transform functions
- `pipeline.yaml` — example pipeline config
- `test_pipeline.py` — unit tests

## Materials

See `WorkingDir/` for sample CSV files and a reference pipeline config.
