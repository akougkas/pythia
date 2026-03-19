---
case: case_002_file_watcher
framework: claude_code
model: qwen3.5:4b
provider: ollama
session_id: f7b21146-2052-412a-b8b7-6621bc7bdfe2
duration_ms: 89376
duration_wall_s: 92.6
cost_usd: 1.864475
num_turns: 6
timestamp: 2026-03-19T14:08:32.410532+00:00
error: None
---

# Plan

# File Watcher Implementation Plan

## Context
This task requires creating a Python CLI tool that monitors a directory for file changes and automatically runs a configurable command when source files are modified. The tool is an educational case study example demonstrating file system monitoring with watchdog library.

## Key Observations
- The `/home/jye/publications/cases/case_002_file_watcher/WorkingDir` directory is currently empty
- No existing implementations or reference files are available in the WorkingDir
- This is a standalone project requiring:
  - `watcher.py` — main CLI entry point
  - `config.py` — YAML config loader
  - `watcher.yaml` — example configuration
  - `test_watcher.py` — unit tests

## Requirements Analysis
1. **Must use `watchdog` for filesystem events** - The watchdog library will handle file system monitoring
2. **Configuration via `watcher.yaml`** - YAML configuration file for all settings
3. **Support include/exclude glob patterns** - Filter which files to watch based on glob patterns
4. **Debounce rapid changes (300ms default)** - Prevent runaway loops from rapid file modifications
5. **Run configurable command on change** - Execute arbitrary commands when watched files change

## Implementation Approach

### Phase 1: Configuration System (`config.py`)
- YAML config loader with sensible defaults
- Config fields:
  - `target_directory` — directory to monitor
  - `command` — command to execute on change (as list of strings)
  - `include_patterns` — list of glob patterns to include (default: `*.py`)
  - `exclude_patterns` — list of glob patterns to exclude
  - `debounce_delay` — debounce delay in milliseconds (default: 300)
  - `log_level` — logging level (default: `INFO`)

### Phase 2: File Watching Logic
- Use `watchdog.observers.FileSystemObserver` for file system events
- Use `watchdog.observers.PollingObserver` or `FileEventHandler` for file changes
- Track file state (modified vs deleted) to avoid re-running command
- Debounce mechanism: use `asyncio` or threading with timeout checks
- Include/exclude filtering based on file paths and glob patterns

### Phase 3: CLI Entry Point (`watcher.py`)
- argparse-based CLI with options:
  - `--config` — path to watcher.yaml
  - `--dry-run` — show what would happen without actually running commands
- Argument parser for the command to run (can be passed directly or read from config)
- Log progress and events
- Handle graceful shutdown on Ctrl+C

### Phase 4: Testing (`test_watcher.py`)
- Mock file system events for unit tests
- Test include/exclude pattern filtering
- Test debounce timing
- Test command execution
- Test configuration loading

## File Modifications Required
Since WorkingDir is empty, the following files need to be created:
1. `config.py` — configuration loader
2. `watcher.py` — main CLI tool
3. `watcher.yaml` — example configuration
4. `test_watcher.py` — unit tests
5. `requirements.txt` — dependencies (watchdog, pyyaml)

## Verification Plan
1. Run `python watcher.py --help` to verify CLI interface
2. Test with sample source files in the directory
3. Create a test file and verify the command runs
4. Test debounce: create multiple files rapidly and verify command runs only once per debounce period
5. Test exclude patterns: verify files matching exclude patterns don't trigger command
6. Run `pytest test_watcher.py` to verify unit tests pass

## Dependencies
- `watchdog` — file system monitoring library
- `pyyaml` — YAML configuration loading
- `pytest` — testing framework

