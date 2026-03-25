---
case: case_003_data_pipeline
framework: agents_sdk
model: qwen3.5:4b
provider: ollama
session_id: None
duration_ms: 15571
duration_wall_s: 15.6
cost_usd: None
num_turns: 1
timestamp: 2026-03-20T23:09:19.247823+00:00
error: None
---

# Plan

# Implementation Plan: Case 003 CSV Data Pipeline

## Overview

This plan outlines the step-by-step development process for building a flexible CSV data pipeline system using pandas. The solution will be modular, supporting dynamic transform composition, and include all required deliverables (`pipeline.py`, `transforms.py`, `pipeline.yaml`, `test_pipeline.py`).

---

## Execution Plan

### Phase 1: Working Directory Inspection & Context Gathering
**Step 1.1**: Inspect the provided sample CSV files for structure:
- Identify column names across different CSVs
- Check row counts and data types
- Note naming conventions and potential missing values

**Step 1.2**: Review the reference `pipeline.yaml` (if available):
- Understand the expected configuration format
- Extract transform chain patterns
- Identify output structure expectations

**Step 1.3**: Define working directory structure:
```
Case 003/
├── pipeline.py
├── transforms.py
├── pipeline.yaml
├── test_pipeline.py
├── WorkingDir/
│   ├── sample_input.csv
│   └── sample_output.csv (for reference)
```

---

### Phase 2: Module Design & Implementation

### Phase 2.1: Transform Functions (`transforms.py`)
**Step 2.1.1**: Design transform interface:
- Create base `Transform` class with `apply()` method
- Define each transform as a concrete subclass

**Step 2.1.2**: Implement required base transforms:
- `FilterRows`: accepts lambda or list of columns to drop, boolean expression
- `RenameColumnsMapping`: accepts dict {old: new}
- `AddColumnComputation`: accepts lambda or computed expression

**Step 2.1.3**: Add optional enhancements:
- `FillMissingValues`: configurable strategies (mean, mode, None)
- `DropColumns`: simple list of column names

**Step 2.1.4**: Return interface:
- Each transform must return a pandas DataFrame
- Each transform must return metadata for logging (if applicable)

---

### Phase 2.2: Pipeline Configuration (`pipeline.yaml`)
**Step 2.2.1**: Define YAML structure:
```yaml
pipeline:
  name: "Case 003 CSV Pipeline"
  verbosity: 2  # 0-3 for DEBUG, INFO, WARNING, ERROR
  
  dry_run: false
  
  input_dir: "./WorkingDir/input/"
  output_dir: "./WorkingDir/output/"
  
transforms:
  - name: "load_csv"
    type: "load"
  
  - name: "drop_nulls"
    type: "filter"
    column: "status"
    threshold: 90
    
  - name: "rename_columns"
    type: "rename"
    mapping:
      old_name1: new_name1
      old_name2: new_name2
      
  - name: "add_derived_col"
    type: "computation"
    column: "total"
    expression: "col_a + col_b"
```

**Step 2.2.2**: Generate sample pipeline configuration file based on Phase 1.2 findings.

---

### Phase 2.3: Main Orchestrator (`pipeline.py`)
**Step 2.3.1**: Implement pipeline orchestration class:
- `Pipeline` class accepts configuration
- `DryRun` flag support
- `configure_transforms()` method
- `initialize_directories()` for read/write paths

**Step 2.3.2**: Implement file I/O logic:
- `read_csv_file(file_path)`: read one CSV
- `load_all_csvs(input_dir, transform)`: loop through input files, apply transforms, and process

**Step 2.3.3**: Implement execution flow:
- Initialize directories (read/write)
- Load input data
- Apply transforms sequentially
- Write output DataFrame

**Step 2.3.4**: Implement logging:
- Use `logging` module with configurable level
- Log metadata, transform results, row counts
- Add `log` method for consistent logging

---

### Phase 2.4: Unit Tests (`test_pipeline.py`)
**Step 2.4.1**: Create test infrastructure:
- `TestCase` base class with `setUp()` and `tearDown()`
- Mock `logging` module for dry-run testing

**Step 2.4.2**: Write tests for individual transforms:
- `test_transforms.py` - Test each transform in isolation
- Test filter functionality with boolean expressions
- Test rename functionality with dict mapping
- Test derived column computation

**Step 2.4.3**: Write end-to-end pipeline tests:
- `test_pipeline_end_to_end.py` - Test complete pipeline with sample CSVs
- Test loading from input directory
- Test write to output directory (or dry-run)
- Test error handling for missing columns

**Step 2.4.4**: Dry-run test case:
- Test `dry_run=True` configuration
- Verify logging but no file writes
- Test error cases and warnings

---

### Phase 3: Integration & Documentation

**Step 3.1**: Integrate all modules:
- Ensure `transforms.py` is importable
- Ensure `pipeline.yaml` is valid JSON
- Run the `test_pipeline.py` suite

**Step 3.2**: Test with sample CSV data:
- Run pipeline with real CSVs from `WorkingDir/`
- Verify expected intermediate outputs
- Confirm pipeline produces correct results

**Step 3.3**: Test configuration:
- Change verbosity levels and verify logs
- Change `dry_run` toggle
- Modify transform configuration via YAML

**Step 3.4**: Add documentation:
- README.md with usage examples
- Function docstrings
- Configuration schema documentation

---

### Phase 4: Final Validation

**Step 4.1**: Run full test suite:
- Execute `python test_pipeline.py -v`
- Ensure 100% test coverage
- Fix any bugs found during execution

**Step 4.2**: Verify constraints:
- Pandas is the only data manipulation library
- YAML is the configuration language
- All transforms can be chained
- Logging is configurable
- Dry-run mode works correctly

**Step 4.3**: Final code review:
- Verify modular design
- Ensure clean separation of concerns
- Check for performance considerations
- Confirm error handling adequacy

---

### Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| CSV file format inconsistent | Medium | High | Add schema validation or flexible column handling |
| Transform API too rigid | Low | Medium | Ensure flexible lambda/callback interface |
| YAML parsing errors | Low | Medium | Add exception handling and clear error messages |
| Dry-run mode not working | Low | Medium | Test explicitly before finalizing |

---

### Success Criteria Checklist

- [ ] `pipeline.py` loads and processes CSVs correctly
- [ ] `transforms.py` provides all required transform functions
- [ ] `pipeline.yaml` is valid and demonstrates chaining
- [ ] `test_pipeline.py` covers all key functionality
- [ ] Dry-run mode logs what would happen without errors
- [ ] Logging works with configurable verbosity levels
- [ ] Code passes all unit and integration tests

---

## File Structure Summary

```
Case003/
├── pipeline.py
│   ├── Pipeline class
│   ├── load_csv_file
│   ├── apply_transform
│   └── run_pipeline
├── transforms.py
│   ├── Transform base class
│   ├── DropNulls transform
│   ├── RenameColumns transform
│   └── AddColumnComputation transform
├── pipeline.yaml
│   ├── pipeline config
│   ├── input/output paths
│   └── transform definitions
├── test_pipeline.py
│   ├── Unit tests for transforms
│   └── Pipeline integration tests
└── WorkingDir/
    ├── input/
    └── output/
```

---

## Implementation Priority

1. **Phase 2**: Core module development (highest priority)
2. **Phase 3**: Integration and testing (critical for validation)
3. **Phase 1**: Context gathering (can run in parallel with Phase 2)
4. **Phase 4**: Final validation and documentation (last priority)

---

## Technical Decisions

1. **Data Loading Strategy**: Use `glob.glob` or `os.walk` to recursively find CSV files
2. **Transform Composition**: Implement a `transform_list` in configuration and apply sequentially
3. **Error Handling**: Use try-except with logging for each transform step
4. **Logging Levels**: Map `int` verbosity level to `logging` constants appropriately
5. **Dry Run**: Write to stdout/logs, do not write to filesystem when `dry_run=True`
6. **Dependency**: Only use `pandas`, `logging`, `yaml` for minimal requirements

This plan ensures all deliverables are met while maintaining modularity, flexibility, and robustness. Ready to begin implementation starting with Phase 1 and 2.
