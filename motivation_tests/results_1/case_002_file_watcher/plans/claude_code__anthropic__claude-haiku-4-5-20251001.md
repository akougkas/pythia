---
case: case_002_file_watcher
framework: claude_code
model: claude-haiku-4-5-20251001
provider: anthropic
session_id: df75335d-ea51-4dd3-a955-3f59b1ee8128
duration_ms: 87872
duration_wall_s: 90.6
cost_usd: 0.10533195
num_turns: 5
timestamp: 2026-03-19T14:05:06.742466+00:00
error: None
---

# Plan

# File Watcher CLI Tool - Implementation Plan

## Context

This plan addresses the need for a Python CLI tool that monitors directories for file changes and automatically executes configurable commands. This is useful for development workflows where developers want tests, linting, formatting, or other commands to run automatically whenever source files change.

The tool will be built with:
- **watchdog** library for cross-platform filesystem monitoring
- **YAML configuration** for flexible command and pattern configuration
- **Debouncing** to prevent command spam from rapid file changes
- **Comprehensive testing** to ensure reliability

---

## Architecture Overview

The implementation follows a modular, single-responsibility architecture:

```
┌─────────────────────────────────────────────────────────┐
│                   watcher.py (CLI)                      │
│  - Argument parsing                                     │
│  - Config loading                                       │
│  - Observer initialization                             │
│  - Signal handling & graceful shutdown                 │
└────────────┬──────────────────────────────────┬─────────┘
             │                                  │
    ┌────────▼─────────┐            ┌──────────▼────────┐
    │  config.py       │            │ FileSystemEvent   │
    │  - ConfigLoader  │            │ Handler           │
    │  - PatternMatch  │            │ - Event filtering │
    │  - Validation    │            │ - Debouncing      │
    └──────────────────┘            │ - Command exec    │
                                    └───────────────────┘
             │
    ┌────────▼──────────────┐
    │  watcher.yaml         │
    │  - Watch paths        │
    │  - Glob patterns      │
    │  - Commands           │
    │  - Debounce config    │
    └───────────────────────┘
```

---

## Implementation Approach

### Phase 1: Configuration Foundation (config.py)

**File**: `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/config.py`

**Components**:
- **ConfigLoader** class: Loads and validates YAML configuration
  - `load(config_path: str) -> WatchConfig`: Parse config file
  - `validate() -> bool`: Validate required fields and paths
  - `_parse_yaml() -> dict`: Handle YAML parsing with error reporting

- **WatchConfig** dataclass: Type-safe configuration representation
  - `watch_path`: Root directory to monitor
  - `debounce_ms`: Debounce delay (default: 300ms)
  - `include_patterns`: Glob patterns to include (empty = all files)
  - `exclude_patterns`: Glob patterns to exclude
  - `commands`: List of command configurations
  - `log_level`: Logging verbosity

- **PatternMatcher** class: Efficient glob pattern matching
  - `should_watch(file_path: str) -> bool`: Combined include/exclude check
  - `matches_include(file_path: str) -> bool`: Check inclusion
  - `matches_exclude(file_path: str) -> bool`: Check exclusion
  - Use `fnmatch` module for glob matching

**Key Decision**: Patterns compiled at config load time for performance, especially important for large directories.

---

### Phase 2: YAML Configuration Schema (watcher.yaml)

**File**: `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/watcher.yaml`

**Structure**:
```yaml
watch:
  path: ./src                    # Directory to monitor (required)
  debounce_ms: 300              # Debounce delay in ms (default: 300)

patterns:
  include:                       # Patterns to include (empty = all)
    - "**/*.py"
    - "**/*.yaml"
  exclude:                       # Patterns to exclude
    - "**/*.pyc"
    - "**/__pycache__/**"
    - "**/.git/**"

commands:                        # Commands to execute on changes
  - name: "format"
    cmd: "black {file_path}"
    description: "Format Python files"
    enabled: true
  - name: "test"
    cmd: "pytest"
    description: "Run test suite"
    enabled: true

logging:
  level: "INFO"
  format: "%(asctime)s - %(levelname)s - %(message)s"
```

**Placeholders**:
- `{file_path}`: Replaced with the changed file's path

---

### Phase 3: Event Handler & Debouncing

**Integrated into**: `watcher.py` (as DebounceFileWatcherHandler class)

**Key Implementation Details**:

1. **Class Inheritance**: Extend `watchdog.events.FileSystemEventHandler`

2. **Event Methods** (override):
   - `on_modified(event)`: Triggered on file modification
   - `on_created(event)`: Triggered on file creation
   - `on_deleted(event)`: Triggered on file deletion
   - `on_moved(event)`: Triggered on file move

3. **Debouncing Mechanism**:
   - Use `threading.Timer` for debounce delay
   - Maintain a set of pending file paths
   - On event: Cancel existing timer, restart it with new delay
   - Timer callback: Execute commands once with accumulated changes
   - Thread-safe with locks for timer management

4. **Command Execution**:
   - For each enabled command, substitute `{file_path}` placeholder
   - Execute via `subprocess.run()` with timeout (default: 30s)
   - Capture stdout/stderr and log results
   - Don't stop watching if command fails
   - Log return codes and errors

---

### Phase 4: CLI Entry Point (watcher.py)

**File**: `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/watcher.py`

**Main Function**:
1. Parse arguments using `argparse`
2. Setup logging (file + console)
3. Load configuration from YAML
4. Validate configuration and watch path
5. Create and start `watchdog.observers.Observer`
6. Register `DebounceFileWatcherHandler`
7. Setup signal handlers (SIGINT, SIGTERM) for graceful shutdown
8. Block on observer thread
9. Cleanup and exit

**CLI Arguments**:
```
--config PATH              Path to watcher.yaml (default: ./watcher.yaml)
--log-level {DEBUG,INFO}   Logging verbosity (default: INFO)
--watch-path PATH          Override config watch path (for testing)
--version                  Show version
--help                     Show help
```

**Exit Codes**:
- `0`: Normal exit
- `1`: Configuration error
- `2`: Argument parsing error
- `3`: Observer startup error
- `130`: Interrupted by user (Ctrl+C)

**Error Handling**:
- Missing config file → Log error message, suggest default path, exit 1
- Invalid YAML → Parse error with line number, exit 1
- Missing watch path → Log path doesn't exist, exit 1
- Observer startup fails → Log reason, exit 3
- Command execution fails → Log error, continue watching
- Signals → Gracefully stop observer, cleanup threads

---

### Phase 5: Comprehensive Test Suite (test_watcher.py)

**File**: `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/test_watcher.py`

**Test Strategy**: Use `unittest` framework with `unittest.mock` for mocking filesystem events.

**Test Categories**:

1. **Configuration Tests**:
   - `test_load_valid_config()`: Parse valid YAML correctly
   - `test_missing_config_file()`: FileNotFoundError raised
   - `test_invalid_yaml()`: YAML syntax error handling
   - `test_missing_required_fields()`: Validation catches missing fields
   - `test_invalid_watch_path()`: Path existence validation

2. **Pattern Matching Tests**:
   - `test_include_pattern_matching()`: Files match include patterns
   - `test_exclude_pattern_matching()`: Excluded files ignored
   - `test_combined_patterns()`: Include + exclude logic correct
   - `test_wildcard_patterns()`: Complex glob patterns work
   - `test_empty_patterns()`: Empty patterns match all files

3. **Event Handler Tests**:
   - `test_event_filtering()`: Only matching files trigger handler
   - `test_debounce_single_event()`: Single event executes once
   - `test_debounce_rapid_events()`: Multiple rapid events debounced
   - `test_debounce_timing()`: Timer executes after correct delay
   - `test_command_placeholder_substitution()`: {file_path} replaced correctly
   - `test_command_execution()`: Commands execute and return codes captured
   - `test_failed_command_continues_watching()`: Errors don't stop watcher

4. **Integration Tests**:
   - `test_full_workflow()`: Config load → Observer start → Event → Command → Stop
   - `test_multiple_file_events()`: Create/modify multiple files, verify debounce
   - `test_excluded_files_ignored()`: Changes to excluded files don't trigger commands
   - `test_signal_handling()`: SIGINT gracefully stops observer
   - `test_cleanup_on_exit()`: All threads and timers properly cleaned up

**Mock Strategy**:
- Mock `watchdog.events.FileModifiedEvent` for filesystem events
- Mock `subprocess.run()` to avoid executing real commands
- Use `tempfile.TemporaryDirectory()` for test directories
- Use `threading.Event()` to synchronize test assertions with async operations

---

## Critical Files & Reuse Opportunities

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `config.py` | Config loading & validation | `ConfigLoader`, `WatchConfig`, `PatternMatcher` |
| `watcher.py` | CLI entry point & orchestration | `main()`, `DebounceFileWatcherHandler`, argument parsing |
| `watcher.yaml` | Configuration schema & example | YAML structure with all config options |
| `test_watcher.py` | Comprehensive test suite | 15+ test methods covering all components |

**Dependencies Used**:
- `watchdog>=3.0.0` - FileSystemEventHandler, Observer
- `pyyaml>=6.0` - YAML parsing
- `threading` - Debounce Timer, signal handling
- `subprocess` - Command execution
- `logging` - Structured logging
- `argparse` - CLI argument parsing
- `pathlib` - Cross-platform path handling
- `fnmatch` - Glob pattern matching
- `signal` - Signal handling (SIGINT, SIGTERM)

---

## Implementation Sequence

1. **Create config.py**: ConfigLoader, WatchConfig, PatternMatcher (foundation)
2. **Create watcher.yaml**: Example configuration file
3. **Create watcher.py**: Main CLI with DebounceFileWatcherHandler
4. **Create test_watcher.py**: Comprehensive unit + integration tests
5. **Manual testing**: Test with real files in WorkingDir

---

## Verification & Testing Strategy

### Manual Testing
1. **Create test files** in `/home/jye/publications/cases/case_002_file_watcher/WorkingDir/`
2. **Configure watcher.yaml** to watch that directory
3. **Run watcher.py** with various options
4. **Modify files** and verify commands execute
5. **Test debouncing** by rapid file modifications
6. **Test exclusions** by modifying excluded file types
7. **Test signal handling** with Ctrl+C

### Automated Testing
```bash
cd /home/jye/publications/cases/case_002_file_watcher/WorkingDir/
python -m pytest test_watcher.py -v
```

### Key Verification Checks
- [ ] Config loads from YAML without errors
- [ ] Pattern matching correctly includes/excludes files
- [ ] Debounce delay observed (300ms default)
- [ ] Commands execute with correct file path substitution
- [ ] Multiple rapid changes result in single command execution
- [ ] Excluded files don't trigger commands
- [ ] Ctrl+C stops watcher gracefully
- [ ] All threads cleaned up on exit
- [ ] Error messages are helpful and logged

---

## Key Design Decisions

1. **Debouncing with threading.Timer**: Simple, reliable, but slight latency (acceptable trade-off for fewer command executions)
2. **Command execution in threads**: Prevents blocking the observer
3. **Pattern compilation at load time**: Performance optimization for large directories
4. **Graceful error handling**: Failed commands don't stop watching; user informed via logs
5. **YAML for config**: Familiar, human-readable, supports complex structures
6. **Comprehensive logging**: Users can debug via --log-level flag

---

## Assumptions

1. Python 3.8+ available in environment
2. watchdog and pyyaml can be installed via pip
3. Commands to execute are shell-compatible (tests, formatters, etc.)
4. Debounce delay of 300ms acceptable for most workflows
5. Sequential command execution (not parallel) acceptable


