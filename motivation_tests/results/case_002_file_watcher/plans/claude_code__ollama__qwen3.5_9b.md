---
case: case_002_file_watcher
framework: claude_code
model: qwen3.5:9b
provider: ollama
session_id: 7e95d7c3-c933-4167-b56e-5a5b8b14d3f9
duration_ms: 75646
duration_wall_s: 79.0
cost_usd: 1.17961
num_turns: 5
timestamp: 2026-03-19T14:06:35.138089+00:00
error: None
---

# Plan

# File Watcher CLI Implementation Plan

## Context

This plan addresses the need to create a Python CLI tool that monitors a directory for file changes and automatically executes configurable commands when source files are modified. The tool will leverage the `watchdog` library for filesystem event detection, support YAML-based configuration with include/exclude patterns, and implement debouncing to handle rapid file changes efficiently.

## Deliverables

- `watcher.py` — Main CLI entry point with argument parsing and event handling
- `config.py` — YAML configuration loader with validation
- `watcher.yaml` — Example configuration file demonstrating usage
- `test_watcher.py` — Unit tests for all components

## Implementation Approach

### Phase 1: Configuration Module (`config.py`)

**Purpose**: Handle YAML configuration loading, validation, and pattern parsing

**Key Components**:
1. **ConfigLoader class**
   - Load and parse `watcher.yaml` using PyYAML
   - Validate required fields: `directory`, `command`, `debounce_ms`
   - Validate optional fields: `include_patterns`, `exclude_patterns`, `initial_delay`
   - Provide typed accessors for configuration values

2. **Pattern Handling**
   - Support glob patterns for include/exclude filtering
   - Convert glob patterns to `watchdog` compatible patterns
   - Default patterns: include `*.py`, exclude `__pycache__`, `.git`, `.pyc`, `*.pyo`

3. **Configuration Structure**
   ```yaml
   directory: /path/to/source
   command: "python -m pytest . --verbose"
   debounce_ms: 300
   initial_delay: 1000  # Optional: delay before first watch
   include_patterns:
     - "*.py"
     - "*.ipynb"
   exclude_patterns:
     - "__pycache__"
     - "*.pyc"
     - ".git"
   ```

### Phase 2: Main Watcher (`watcher.py`)

**Purpose**: Core event handling, file filtering, and command execution

**Key Components**:
1. **FileFilter class**
   - Determine if a path should be watched based on include/exclude patterns
   - Implement pattern matching using `fnmatch`
   - Cache filtered results for performance

2. **FileEventHandler class**
   - Extend `watchdog.observers.FileSystemEventHandler`
   - Handle `on_modified`, `on_created`, `on_moved` events
   - Ignore `on_deleted` events (optional based on requirements)
   - Implement debouncing using a dictionary of `{path: last_change_time}`
   - Debounce implementation: track file modification times, only trigger action if `current_time - last_time > debounce_ms`

3. **DirectoryWatcher class**
   - Initialize `watchdog.Observer` with appropriate observer type (`FSEventsObserver` on macOS, `FSEPoller` on Linux, `ReadDirChanger` on Windows)
   - Configure `FileSystemEventHandler` as the event handler
   - Implement `start()` method to begin watching
   - Implement `stop()` method for graceful shutdown
   - Handle signal interrupts (SIGINT, SIGTERM) for clean shutdown

4. **CLI Entry Point**
   - Use `argparse` for command-line argument parsing
   - Support subcommands or options:
     - `--config`: Path to watcher.yaml (default: `./watcher.yaml`)
     - `--directory`: Directory to watch (overrides config)
     - `--command`: Command to execute (overrides config)
   - Print status messages to console (using `logging` module)
   - Exit codes: 0 (success), 1 (error), 2 (interrupted)

### Phase 3: Example Configuration (`watcher.yaml`)

**Purpose**: Provide a ready-to-use configuration example

**Content**:
- Point to the WorkingDir from the case materials
- Use a sample Python test command
- Set default debounce_ms: 300
- Configure sensible default patterns
- Include comments explaining each field

### Phase 4: Unit Tests (`test_watcher.py`)

**Purpose**: Comprehensive test coverage for all components

**Test Modules**:

1. **test_config.py**
   - Test YAML loading and validation
   - Test missing required fields error handling
   - Test pattern matching (include/exclude)
   - Test with various file paths and patterns
   - Test type coercion (e.g., debounce_ms as string to int)

2. **test_filter.py** (or integrate into test_watcher.py)
   - Test FileFilter with various paths
   - Test include-only behavior
   - Test exclude-only behavior
   - Test combined include/exclude logic
   - Test case sensitivity

3. **test_debounce.py** (or integrate into test_watcher.py)
   - Test that rapid changes within debounce window are ignored
   - Test that changes after debounce window trigger actions
   - Test with varying debounce values (0ms, 300ms, 1000ms)
   - Test edge cases (exact debounce boundary)

4. **test_integration.py** (optional but recommended)
   - Create test directory with sample files
   - Create temp watcher.yaml
   - Modify a file and verify command is executed once after debounce
   - Test with multiple rapid modifications
   - Test stop/start functionality
   - Test signal handling (SIGINT)

**Test Utilities**:
- Use `tempfile` for temporary test directories
- Use `unittest.mock` for mocking command execution
- Use `pytest` or `unittest` framework
- Include fixtures for common test setup

### Phase 5: Documentation

**Content** (as docstrings and/or README):
- Installation requirements (`watchdog`, `pyyaml`)
- Usage examples
- Configuration schema
- Event handling details
- Platform-specific notes (macOS vs Linux vs Windows)

## Technical Decisions

1. **Observer Selection**: Use platform-appropriate observers:
   - macOS: `FSEventsObserver` (efficient, kernel-level events)
   - Linux: `FSEPoller` with 200ms interval (balance of speed and accuracy)
   - Windows: `ReadDirChanger` (polling-based)

2. **Event Types**: Monitor for:
   - `FileCreated` — new source files
   - `FileModified` — existing source files modified
   - `FileMoved` — files moved into watched directory
   - (Optionally monitor `FileDeleted` if needed)

3. **Debouncing Strategy**: Use a simple dictionary tracking `{abs_path: last_timestamp}`:
   - On event, check if `now - last_timestamp > debounce_ms`
   - If yes, execute command and update timestamp
   - If no, update timestamp and suppress event
   - Reset timestamp on `on_created` events

4. **Error Handling**:
   - Catch exceptions in event handlers
   - Log errors but don't crash the watcher
   - Re-raise or handle command execution errors gracefully

5. **Logging**: Use Python's `logging` module with levels:
   - DEBUG: Detailed event tracking
   - INFO: Successful command executions
   - WARNING: Debounced events (suppressed)
   - ERROR: Exceptions and failures

## File Paths

- `watcher.py` — `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/watcher.py`
- `config.py` — `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/config.py`
- `watcher.yaml` — `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/watcher.yaml`
- `test_watcher.py` — `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/test_watcher.py`

## Verification Plan

1. **Unit Tests**: Run `python -m pytest test_watcher.py -v`
2. **Manual Testing**:
   - Create test directory with sample Python files
   - Place `watcher.yaml` config
   - Run `python watcher.py`
   - Modify a file and verify command executes once after 300ms
   - Rapidly modify and verify debouncing works
3. **Integration Test**: Ensure clean shutdown on Ctrl+C

## Assumptions

1. The `watchdog` library is available (install via `pip install watchdog`)
2. PyYAML is available for config parsing
3. WorkingDir is empty and will be populated with test files before actual monitoring
4. The user has appropriate permissions to watch the target directory
5. Commands will be executed in a shell context (using `shlex.split()` for argument handling)

## Next Steps

1. Create `config.py` with ConfigLoader and FileFilter classes
2. Create `watcher.py` with FileEventHandler, DirectoryWatcher, and CLI entry point
3. Create `watcher.yaml` example configuration
4. Create `test_watcher.py` with comprehensive unit tests
5. Run tests and verify functionality
6. Document usage and edge cases

