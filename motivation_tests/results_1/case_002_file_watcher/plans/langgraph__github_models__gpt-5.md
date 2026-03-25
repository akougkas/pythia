---
case: case_002_file_watcher
framework: langgraph
model: gpt-5
provider: github_models
session_id: None
duration_ms: 152736
duration_wall_s: 152.7
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T03:12:45.055413+00:00
error: None
---

# Plan

Assumptions
- Python 3.9+ is available.
- The CLI will execute a string command via the system shell by default (shell=True). This is common for developer workflows like “pytest -q”.
- Default include pattern will be Python source files ["**/*.py"] to reflect a typical source watch use case.
- If both watcher.yaml and CLI overrides are provided, CLI overrides take precedence.
- Multiple watch roots (paths) are supported; include/exclude patterns are applied relative to each root.
- When a command is running and more changes occur, we queue exactly one subsequent run (no kill/restart of the current run). This simplifies behavior and avoids unintended kills. This can be extended later if needed.

High-level design
- Files:
  - watcher.py: CLI and main Watcher runtime.
  - config.py: Config dataclass, YAML loader, defaults, and merge logic with CLI options.
  - watcher.yaml: Example configuration.
  - test_watcher.py: Unit tests with pytest and temporary directories.
- Libraries:
  - watchdog (required)
  - pyyaml (for config)
  - pytest (for tests)
- Core features:
  - Watch one or more directories for changes using watchdog Observer.
  - Filter events with include and exclude glob patterns.
  - Debounce rapid changes (default 300ms).
  - On changes, run a configured command as a subprocess.
  - Queue at most one additional run if changes arrive while command is running.
  - Graceful shutdown on SIGINT/SIGTERM.

Step-by-step implementation plan

1) Define configuration schema and loader (config.py)
- Responsibilities:
  - Provide a Config dataclass capturing all runtime settings.
  - Load YAML from a specified path (default ./watcher.yaml if present).
  - Apply reasonable defaults.
  - Merge CLI overrides.
  - Resolve relative paths against config file directory.
- Config fields:
  - command: str (required unless provided via CLI)
  - paths: list[str] (default ["."], relative to YAML file directory)
  - include: list[str] (default ["**/*.py"])
  - exclude: list[str] (default ["**/.git/**", "**/__pycache__/**", "**/.venv/**"])
  - debounce_ms: int (default 300)
  - shell: bool (default True)
  - polling: bool (default False) to opt into PollingObserver
  - run_at_start: bool (default False)
  - verbose: bool (default True)
- Functions/classes:
  - Dataclass Config with:
    - method resolve_paths(base_dir: Path) -> None, making paths absolute.
    - method normalize_patterns() -> None ensuring include/exclude are lists and normalized for matching.
  - load_config(config_path: Optional[str], cli_overrides: dict) -> Config
    - If config_path is None and default watcher.yaml exists in CWD, use it; else continue with defaults.
    - Load YAML via yaml.safe_load; if None, treat as empty dict.
    - Validate types and values (e.g., debounce_ms > 0).
    - Override with CLI options if provided.
    - Ensure command is present after merging; if not, raise ValueError.
    - Resolve paths relative to YAML directory or CWD.
- Error handling:
  - If YAML path provided but not found or invalid YAML, raise a descriptive exception.
  - If fields are of incorrect type, raise ValueError indicating the field.

2) Implement event filtering and debounce logic (watcher.py core classes)
- Classes:
  - DebouncedRunner:
    - Purpose: manage debounced scheduling and execution of the command, with queuing if a run is in progress.
    - Fields:
      - debounce_ms: int
      - run_callable: callable with no args, returns exit code (int) or None
      - lock: threading.Lock
      - timer: Optional[threading.Timer]
      - run_in_progress: bool
      - pending: bool (true if a run should be triggered after current finishes)
      - stopped: bool
    - Methods:
      - schedule(): called when a relevant file change event occurs. Creates or resets a Timer to fire after debounce_ms. Thread-safe.
      - _on_timer(): timer callback. If run_in_progress then set pending=True; otherwise start run in a thread.
      - _start_run(): sets run_in_progress True, runs run_callable synchronously in a worker thread, logs start/finish, then upon completion sets run_in_progress False; if pending then pending=False and schedule() to re-debounce a subsequent run.
      - stop(): cancel timer and set stopped; prevent new schedules from scheduling runs.
  - FileChangeHandler (inherits watchdog.events.FileSystemEventHandler):
    - Purpose: filter relevant file events and trigger DebouncedRunner.schedule() when a change is detected.
    - Constructor args: roots: list[Path], include: list[str], exclude: list[str], debounced_runner: DebouncedRunner, verbose: bool
    - Implementation details:
      - Maintain a list of (root_path, root_str) so we can compute relative paths and match patterns per root.
      - Use fnmatch.fnmatch on POSIX-style relative paths. Convert relpath to rel.as_posix() for consistent matching.
      - Ignore directories (event.is_directory).
      - Events to consider: on_created, on_modified, on_moved, on_deleted. For moved: consider both src and dest; if either matches, schedule.
      - include semantics: if include is empty, treat as ["**/*"] (match all files). Default is ["**/*.py"].
      - exclude semantics: if any exclude matches, ignore.
      - When a change matches, optionally log which path and event type, then call debounced_runner.schedule().
- Matching algorithm:
  - For each candidate path from the event (src_path and possibly dest_path):
    - Determine which root it belongs to by picking the first root where path is under that root (path.resolve().is_relative_to(root.resolve()) on Python 3.9+ implement with try/except using Path.relative_to).
    - Compute rel = resolved_path.relative_to(root).
    - Convert rel to posix: rel_posix = rel.as_posix().
    - included = (include empty) or any(fnmatch(rel_posix, pat) for pat in include)
    - excluded = any(fnmatch(rel_posix, pat) for pat in exclude)
    - if included and not excluded: schedule and break.
- Observer:
  - Choose watchdog.observers.Observer by default; if config.polling True, use watchdog.observers.polling.PollingObserver.

3) Implement command execution (watcher.py)
- CommandRunner:
  - Constructor args: command: str, shell: bool, cwd: Path, verbose: bool
  - run(): executes the command, streaming output to the console.
    - Use subprocess.Popen with:
      - args = command (string)
      - shell = shell
      - cwd = cwd
      - stdout, stderr = None (inherit parent streams)
      - env = os.environ (inherit)
    - Print starting message with timestamp and the command.
    - Wait for process to complete (proc.wait()) and log exit code.
    - Return exit code (int).
  - Edge cases:
    - If stop requested, we do not forcibly terminate; we rely on graceful shutdown.
    - If shell is False, we could split with shlex.split(command). For this plan, we keep shell=True default; still add support if shell=False (split using shlex.split).
- Integration with DebouncedRunner:
  - DebouncedRunner.run_callable calls CommandRunner.run().

4) CLI and program lifecycle (watcher.py main)
- Parse arguments with argparse:
  - -c/--config: path to watcher.yaml (default: if ./watcher.yaml exists, use it; else None)
  - -p/--path: repeatable; additional paths to watch (merge with config paths)
  - --command: override command string
  - --debounce-ms: int
  - --include: repeatable glob
  - --exclude: repeatable glob
  - --shell / --no-shell: boolean flag to set shell
  - --polling: boolean
  - --run-at-start: boolean
  - --quiet: sets verbose=False
  - --verbose: sets verbose=True (default True unless quiet is specified)
- Load config via config.load_config(config_path, overrides_dict) where overrides_dict includes only provided CLI args.
- Build observer and handlers:
  - Instantiate DebouncedRunner with config.debounce_ms and a run_callable that wraps CommandRunner.run().
  - Instantiate FileChangeHandler with roots=config.paths, include=config.include, exclude=config.exclude, debounced_runner, verbose=config.verbose.
  - Instantiate Observer or PollingObserver based on config.polling.
  - For each root in config.paths, call observer.schedule(handler, str(root), recursive=True).
- Startup behavior:
  - Start observer.start().
  - If config.run_at_start: call debounced_runner.schedule() immediately (or run immediately by calling schedule() then sleeping <debounce_ms>?). Simpler: directly schedule so it debounces together with any immediate changes; or provide an immediate run by invoking _start_run() directly. For predictability, schedule() is fine.
- Signal handling:
  - Trap SIGINT/SIGTERM to call debounced_runner.stop(), observer.stop().
- Loop:
  - Wait in a try/except KeyboardInterrupt loop; on exit, stop observer, join observer thread, stop DebouncedRunner, and exit with code 0.
- Exit codes:
  - The CLI exit code is 0 unless there’s a fatal error during initialization (like invalid config). Command exit codes do not affect the watcher’s exit code since the watcher continues running.

5) Pattern handling details
- Patterns use POSIX style and fnmatch.fnmatch.
- Users can supply patterns like:
  - include: ["**/*.py", "**/*.yaml"]
  - exclude: ["**/.git/**", "**/build/**", "**/__pycache__/**"]
- Documentation comments will clarify that patterns are matched against the relative path to each watched root.

6) Debounce details
- Default 300ms; configurable via debounce_ms.
- schedule():
  - If stopped: no-op.
  - Acquire lock, cancel an existing timer if present, and create a new Timer(debounce_ms/1000, _on_timer).
  - Start the timer.
- _on_timer():
  - Acquire lock. If run_in_progress: set pending=True and return.
  - Else: set run_in_progress=True, release lock, run command in a worker thread to avoid blocking timer thread.
- After run completes:
  - Acquire lock, set run_in_progress=False.
  - If pending: set pending=False and schedule() again to debounce any accumulated changes.

7) Example configuration file (watcher.yaml)
- Contents:
  - command: "pytest -q"
  - paths:
    - "."
  - include:
    - "**/*.py"
  - exclude:
    - "**/.git/**"
    - "**/__pycache__/**"
    - "**/.venv/**"
  - debounce_ms: 300
  - shell: true
  - polling: false
  - run_at_start: false
- Notes:
  - The command executes in the first path listed (or current working directory) as cwd.

8) Implement unit tests (test_watcher.py)
- Use pytest and temporary directories.
- Utilities for tests:
  - create_temp_project(tmp_path) helper to make files and directories.
  - A FakeRunner callable that records invocation count and last invocation timestamp; can simulate a long-running process by sleeping.
- Tests:
  - test_config_defaults_and_overrides:
    - Create a temp watcher.yaml with partial settings (e.g., just command).
    - Load config and assert defaults are applied (debounce, include/exclude).
    - Override via CLI dict and assert values override YAML.
  - test_include_exclude_matching:
    - Setup temp project with files that match include and exclude patterns.
    - Instantiate FileChangeHandler with FakeRunner via DebouncedRunner.
    - Instead of starting Observer, call handler methods directly with a Fake event object (build simple object with src_path, is_directory=False). Ensure schedule() called only for included and not excluded.
  - test_debounce_coalesces_multiple_events:
    - Use a very small debounce_ms (e.g., 100).
    - Start DebouncedRunner with FakeRunner that increments a counter.
    - Call schedule() multiple times within less than debounce window; sleep slightly longer than debounce; assert FakeRunner ran exactly once.
  - test_queue_when_running:
    - FakeRunner that sleeps longer than debounce (e.g., 0.3s).
    - Trigger schedule() to start a run, then while run_in_progress is True, trigger schedule() again.
    - After runner completes, await time for subsequent scheduled run and assert it ran twice total (one queued).
  - test_observer_integration_basic:
    - Mark as integration-like test.
    - Create tmpPath with a simple file. Start full Watcher with PollingObserver (more reliable in CI) and FakeRunner with short debounce.
    - Touch file multiple times; assert FakeRunner was called at least once, and not more than expected due to debounce.
    - Teardown: stop watcher cleanly to avoid dangling threads.
  - test_run_at_start:
    - Configure run_at_start=True, debounce small.
    - Start DebouncedRunner schedule at start or directly run; assert one run occurs even without file changes.
- Flakiness mitigation:
  - Use timeouts and waits slightly larger than debounce_ms to ensure timers fire.
  - Prefer PollingObserver in integration test to reduce platform-specific issues.

9) Implementation skeletons

- config.py (outline):
  - import dataclasses, typing, yaml, pathlib, os
  - @dataclass class Config:
    - fields as above
    - resolve_paths(self, base_dir: Path)
    - normalize_patterns(self)
  - def load_config(config_path: Optional[str], overrides: dict) -> Config:
    - locate YAML, load dict, merge overrides, validate, instantiate Config, resolve paths, return.

- watcher.py (outline):
  - import argparse, threading, time, signal, subprocess, os, sys, fnmatch, pathlib
  - from watchdog.observers import Observer
  - from watchdog.observers.polling import PollingObserver
  - from watchdog.events import FileSystemEventHandler
  - from config import load_config
  - class DebouncedRunner: as above
  - class CommandRunner: as above
  - class FileChangeHandler(FileSystemEventHandler): as above
  - def main():
    - parse args
    - build overrides dict
    - cfg = load_config(args.config, overrides)
    - build CommandRunner and DebouncedRunner
    - build handler and observer(s)
    - register signal handlers
    - start observer, optionally schedule run_at_start
    - loop waiting for KeyboardInterrupt; on exit, stop observer and runner
  - if __name__ == "__main__": main()

10) Logging and UX considerations
- Print concise messages when:
  - Starting watcher with paths and patterns.
  - Change detected: show event type and relative path.
  - Debounce notice: “Change detected; running in X ms...”
  - Running command: show timestamp and command.
  - Command finished with exit code.
  - Queued run while running: “Change detected during run; queuing another run.”
- Respect verbose flag; if quiet, limit to errors and command start/finish.

11) Cross-platform and path handling
- Convert all rel paths to POSIX for pattern matching.
- Resolve watch roots to absolute Paths.
- Use shell=True default; be mindful that Windows CMD vs Unix shell differ; this is acceptable given assumption. Support shell=False via CLI if needed.

12) Performance considerations
- Use a single DebouncedRunner for all watched paths, so bursts across the repo coalesce into a single run.
- Pattern filtering in Python is cheap; watchdog handles event coalescing efficiently.

13) Error handling
- Fail fast on missing command with a clear error message and exit code 2.
- If a path in config does not exist, print a warning and skip scheduling it; if no valid paths remain, exit with error.
- Catch exceptions in runner to prevent crashing the watcher; log and continue.

14) Documentation in code and comments
- Document pattern semantics (relative to roots, POSIX-style).
- Explain debounce and queue semantics.
- Clarify that restart/kill-on-change is not implemented but could be added.

15) Example usage
- In WorkingDir or any project:
  - Create watcher.yaml as shown.
  - Run: python watcher.py
  - Or override: python watcher.py --command "pytest -q" --include "**/*.py" --exclude "**/build/**" --debounce-ms 200

16) Integration with the provided WorkingDir
- The tool can be run from /home/jye/publications/cases/case_002_file_watcher/WorkingDir or pointed at it via --path.
- Default include pattern will cover Python files in that directory.

17) Future enhancements (out of scope now)
- Option to restart running command on new changes (kill and rerun).
- Colored output and timestamps.
- Notify only on test failure or change summary.
- JSON logging for integration with other tools.

Deliverables content details

- watcher.py:
  - Full implementation of CLI, DebouncedRunner, CommandRunner, FileChangeHandler, and main loop per steps 2–4, 9.
- config.py:
  - Config dataclass, defaults, YAML loader, overrides, path resolution per step 1.
- watcher.yaml:
  - Example config per step 7.
- test_watcher.py:
  - Pytest tests per step 8.

Validation checklist before delivery
- Run unit tests locally (not part of this plan execution).
- Verify that touching a .py file triggers a single run after debounce and that multiple quick touches coalesce.
- Verify include/exclude filters work as expected.
- Verify graceful shutdown on Ctrl+C and that subprocess outputs are forwarded.
