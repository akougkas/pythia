---
case: case_002_file_watcher
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: 8a0c0de1-71f4-47bd-a13d-ec148d8dc342
duration_ms: 159253
duration_wall_s: 167.7
cost_usd: 0.21143884999999996
num_turns: 11
timestamp: 2026-03-18T00:47:24.861575+00:00
error: None
---

# Plan

# File Watcher CLI Tool - Implementation Plan

## Context

This plan describes the implementation of a Python CLI tool that monitors filesystem changes and automatically executes configurable commands. The tool is designed to address the need for automated task triggering (e.g., running tests) when source files are modified, enabling faster development feedback loops.

## Requirements Summary

- Monitor directories for file system changes using `watchdog`
- Load configuration from YAML (`watcher.yaml`)
- Support include/exclude glob patterns for selective file monitoring
- Implement debouncing with 300ms default to handle rapid change events
- Provide a clean CLI interface with logging and signal handling
- Comprehensive test coverage with pytest

## Architecture Overview

```
┌─────────────────────────────────────────┐
│           CLI Layer (watcher.py)        │
│  - argparse integration                 │
│  - Signal handling (SIGINT/SIGTERM)     │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│      Application Layer (FileWatcher)    │
│  - Event handling orchestration         │
│  - Debouncing coordination              │
│  - Pattern matching logic               │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┬────────────┐
        │                     │            │
┌───────▼────────┐ ┌──────────▼──────┐ ┌──▼──────────────┐
│  Config Module │ │ Watchdog Adapter│ │ Debounce Engine │
│  (config.py)   │ │                 │ │ (debouncer.py)  │
│                │ │ - EventHandler  │ │                 │
│ - YAML parsing │ │ - Watchdog obs. │ │ - Timer-based   │
│ - Validation   │ │ - Event filter  │ │ - Thread-safe   │
└────────────────┘ └─────────────────┘ └─────────────────┘
```

## Module Structure

### 1. `config.py` - Configuration Loader and Validator

**Responsibilities:**
- Parse YAML configuration files
- Validate configuration schema
- Provide runtime config objects as dataclasses
- Handle configuration errors gracefully

**Key Classes:**
- `WatcherConfig` - Main configuration dataclass with fields:
  - `watch_paths: List[str]` - Directories to monitor
  - `exclude_patterns: List[str]` - Glob patterns to exclude
  - `include_patterns: List[str]` - Glob patterns to include (positive filter)
  - `debounce_ms: int = 300` - Debounce delay in milliseconds
  - `events: List[str]` - Event types to monitor (created, modified, deleted, moved)
  - `actions: Dict[str, Any]` - Action configuration keyed by event type

- `ActionConfig` - Configuration for individual actions
  - `type: str` - Action type (exec, log, webhook)
  - `params: Dict[str, Any]` - Action-specific parameters

**Key Functions:**
- `load_config(path: str) -> WatcherConfig` - Load and validate config from YAML
- `validate_config(config: dict) -> WatcherConfig` - Validate structure and values

**YAML Schema:**
```yaml
version: "1.0"

watch_paths:
  - ./src
  - ./tests

exclude_patterns:
  - "**/__pycache__/**"
  - "**/*.tmp"
  - "**/.*"

include_patterns:
  - "**/*.py"
  - "**/*.yaml"

debounce_ms: 300

events:
  - created
  - modified
  - deleted

actions:
  on_any:
    - type: log
      level: info
  on_modified:
    - type: exec
      command: "pytest {file}"
```

### 2. `debouncer.py` - Debouncing Engine

**Responsibilities:**
- Debounce rapid filesystem events using timer-based approach
- Maintain thread-safe state across multiple concurrent events
- Cancel previous timers when new events arrive for same path
- Execute callbacks after configured delay if no new events arrive

**Key Classes:**
- `Debouncer` - Main debouncing engine
  - `__init__(delay_ms: int = 300)` - Initialize with delay
  - `debounce(key: str, callback: Callable, *args, **kwargs)` - Schedule debounced callback
  - `cancel(key: str)` - Cancel pending callback
  - `_execute_pending(key: str)` - Internal timer callback

**Implementation Details:**
- Uses `threading.Timer` for each debounced event
- Stores timers in thread-safe dict with `threading.RLock()`
- Each file path gets independent debounce timer
- Callback execution happens outside lock to avoid blocking

**Debouncing Flow:**
```
Event 1 (t=0ms)   → Start 300ms timer
Event 2 (t=50ms)  → Cancel timer, restart 300ms timer
Event 3 (t=100ms) → Cancel timer, restart 300ms timer
                     [No events for 300ms]
                  → Timer fires, execute callback
```

### 3. `file_watcher.py` - Core FileWatcher Engine

**Responsibilities:**
- Manage watchdog Observer and filesystem monitoring
- Apply pattern matching (include/exclude filters) to events
- Coordinate with debouncer for delayed action execution
- Execute configured actions on matching events
- Handle errors gracefully

**Key Classes:**
- `FileWatcher` - Main engine
  - `__init__(config: WatcherConfig)` - Initialize with configuration
  - `start() -> None` - Start watching directories
  - `stop() -> None` - Stop watching and cleanup
  - `_process_event(event: FileSystemEvent)` - Process filesystem event
  - `_should_watch_path(path: str) -> bool` - Check if path matches patterns

- `WatcherEventHandler(watchdog.events.FileSystemEventHandler)` - Handles raw filesystem events
  - `on_created(event)` - Handle file creation
  - `on_modified(event)` - Handle file modification
  - `on_deleted(event)` - Handle file deletion
  - `on_moved(event)` - Handle file move/rename

**Pattern Matching Logic:**
Two-stage filtering using fnmatch patterns:
1. **Include Filter**: If include_patterns specified, only accept paths matching ANY pattern
2. **Exclude Filter**: Reject paths matching ANY exclude pattern
3. **Event Type Filter**: Check if event type is in configured events list

### 4. `watcher.py` - CLI Entry Point

**Responsibilities:**
- Parse command-line arguments
- Load configuration and initialize FileWatcher
- Handle graceful shutdown (SIGINT/SIGTERM)
- Manage application lifecycle
- Provide user-friendly output

**Key Functions:**
- `main(args=None) -> int` - CLI entry point, returns exit code
- `create_argument_parser() -> argparse.ArgumentParser` - Setup CLI arguments
- `FileWatcherCLI` class - Orchestrates CLI operations

**CLI Arguments:**
- `--config FILE` - Path to watcher.yaml (default: ./watcher.yaml)
- `--verbose` / `-v` - Enable verbose logging
- `--quiet` / `-q` - Suppress non-error output
- `--dry-run` - Show what would be watched without executing actions
- `--log-level {DEBUG,INFO,WARNING,ERROR}` - Set logging verbosity

**Signal Handling:**
- Register SIGINT and SIGTERM handlers for graceful shutdown
- Allow observer to cleanly stop and cleanup resources
- Exit with code 0 on successful shutdown

## Configuration File (`watcher.yaml`)

**Required Fields:**
- `watch_paths` - List of directories to monitor

**Optional Fields:**
- `exclude_patterns` - Default: empty list
- `include_patterns` - Default: empty list (watch all, then filter by exclude)
- `debounce_ms` - Default: 300
- `events` - Default: [created, modified, deleted, moved]
- `actions` - Default: empty dict (logs all events)

**Example Configuration:**
```yaml
version: "1.0"

watch_paths:
  - ./src
  - ./config

exclude_patterns:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - "**/.git/**"
  - "**/.*"

include_patterns:
  - "**/*.py"
  - "**/*.yaml"

debounce_ms: 300

events:
  - created
  - modified

actions:
  on_any:
    - type: log
      level: info

  on_modified:
    - type: exec
      command: "python -m pytest {file}"
      ignore_errors: true
```

## Testing Strategy

**Test Framework:** pytest with pytest-mock and pytest-timeout

**Test Organization:**

1. **Configuration Tests** (`test_config.py`)
   - Valid configuration loading
   - Missing/invalid YAML handling
   - Schema validation (required fields)
   - Default values application
   - Invalid pattern syntax detection

2. **Pattern Matching Tests** (`test_patterns.py`)
   - Include-only pattern matching
   - Exclude-only pattern matching
   - Combined include/exclude logic
   - Recursive glob patterns (`**`)
   - Hidden file handling
   - Case sensitivity

3. **Debouncer Tests** (`test_debouncer.py`)
   - Single event execution
   - Rapid events trigger debouncing
   - Timer cancellation on new events
   - Multiple independent keys
   - Thread safety under concurrent access
   - Cleanup of completed timers

4. **FileWatcher Integration Tests** (`test_file_watcher.py`)
   - Start/stop lifecycle
   - Event detection (created/modified/deleted/moved)
   - Pattern filtering applied to events
   - Debouncing applied to rapid changes
   - Action execution coordination
   - Error handling and recovery

5. **CLI Tests** (`test_cli.py`)
   - Argument parsing
   - Config file loading
   - Signal handling (SIGINT/SIGTERM)
   - Dry-run mode
   - Exit codes

**Test Fixtures:**
- `temp_directory` - Temporary directory for file operations
- `sample_config` - Valid test configuration
- `mock_observer` - Mocked watchdog Observer for isolation
- `watch_dir` - Pre-configured temporary watch directory

**Key Test Patterns:**
- Use `pytest.mark.timeout` for tests with threads/timers
- Mock external dependencies (watchdog Observer)
- Use fixtures for common setup/teardown
- Test both happy paths and error conditions
- Verify thread safety with concurrent operations

## Implementation Sequence

### Phase 1: Core Foundation
1. Create `config.py` with WatcherConfig and validation
2. Create exception hierarchy and logging setup
3. Create `debouncer.py` with thread-safe Timer-based debouncing
4. Write comprehensive tests for config and debouncer

### Phase 2: Integration
1. Create `file_watcher.py` with FileWatcher and EventHandler
2. Integrate pattern matching using fnmatch
3. Integrate debouncer for delayed event processing
4. Implement action execution framework (at minimum: logging)
5. Write integration tests

### Phase 3: CLI and Polish
1. Create `watcher.py` as CLI entry point
2. Implement signal handling for graceful shutdown
3. Create example `watcher.yaml`
4. Write CLI tests
5. Add comprehensive error messages

### Phase 4: Testing and Documentation
1. Achieve >90% code coverage
2. Add docstrings to all modules
3. Write usage README with examples
4. Test on multiple Python versions

## Critical Files to Implement

| File | Purpose | Dependencies |
|------|---------|--------------|
| `config.py` | Configuration loading and validation | PyYAML |
| `debouncer.py` | Thread-safe event debouncing | threading, typing |
| `file_watcher.py` | Watchdog integration and orchestration | config.py, debouncer.py, watchdog |
| `watcher.py` | CLI interface and lifecycle | config.py, file_watcher.py |
| `test_watcher.py` | Comprehensive test suite | pytest, pytest-mock, pytest-timeout |
| `watcher.yaml` | Example configuration | (documentation) |

## Dependencies

**Required:**
```
watchdog>=3.0.0
PyYAML>=6.0
python>=3.8
```

**Testing (optional):**
```
pytest>=7.0
pytest-mock>=3.10
pytest-timeout>=2.1
pytest-cov>=4.0
```

## Error Handling

**Configuration Errors** (fail at startup):
- Missing config file → Exit code 1
- Invalid YAML syntax → Exit code 2
- Missing required fields → Exit code 3
- Invalid pattern syntax → Exit code 4

**Runtime Errors** (log and continue):
- File permission denied → Warning log
- Disk I/O error → Error log
- Action execution failure → Log based on ignore_errors setting

**Shutdown Errors** (force shutdown):
- Observer timeout → Warning log, exit code 5
- Resource cleanup failure → Error log, exit code 5

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Timer-based debouncing | Simpler than batching, predictable latency, scalable |
| Two-stage pattern matching | Include (positive) then exclude (safety), efficient |
| Separate debouncer module | Testable in isolation, reusable |
| Dataclass for config | Type hints, validation, IDE support |
| YAML configuration | Human-readable, supports comments, nested structures |
| RLock for thread safety | Allows same thread to reacquire, prevents deadlocks |
| Callback execution outside lock | Prevents long operations from blocking other events |

## Verification and Testing

**End-to-End Testing:**
1. Create sample `watcher.yaml` with test directory
2. Run `python watcher.py --config watcher.yaml --verbose`
3. Create/modify/delete files in watched directory
4. Verify:
   - Events are detected correctly
   - Include/exclude patterns filter properly
   - Debouncing prevents duplicate action execution
   - Actions execute as configured
   - Graceful shutdown on SIGINT

**Test Coverage Target:** >90% with pytest-cov

**Manual Testing Scenarios:**
- Rapid file modifications (debouncing validation)
- Pattern matching edge cases (hidden files, recursive patterns)
- Large directory trees (performance)
- Signal handling during action execution
- Configuration error recovery

## Notes

- The working directory at `/home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/WorkingDir` is empty and ready for implementation
- All code should follow PEP 8 style guidelines
- Comprehensive docstrings required for all public APIs
- Test fixtures should use pytest's tmp_path for isolation

