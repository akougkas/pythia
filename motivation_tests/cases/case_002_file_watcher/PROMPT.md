# Case 002: File Watcher

## Objective

Create a Python CLI tool that monitors a directory for file changes and
automatically runs a configurable command (e.g., test suite) when source
files are modified.

## Constraints

- Must use `watchdog` for filesystem events
- Configuration via a `watcher.yaml` file
- Support include/exclude glob patterns
- Debounce rapid changes (300ms default)

## Expected Deliverables

- `watcher.py` — main CLI entry point
- `config.py` — YAML config loader
- `watcher.yaml` — example configuration
- `test_watcher.py` — unit tests

## Materials

See `WorkingDir/` for an example project structure to monitor.
