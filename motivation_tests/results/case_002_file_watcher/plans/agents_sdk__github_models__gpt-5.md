---
case: case_002_file_watcher
framework: agents_sdk
model: gpt-5
provider: github_models
session_id: None
duration_ms: 94174
duration_wall_s: 94.2
cost_usd: None
num_turns: 1
timestamp: 2026-03-21T03:10:53.924981+00:00
error: None
---

# Plan

Plan: Python CLI File Watcher with debounce, include/exclude patterns, YAML config

Assumptions
- Python 3.9+ is available.
- Dependencies allowed: watchdog (filesystem events), PyYAML (YAML parsing), pytest (tests).
- Default debounce interval is 300 ms when not specified in config.
- Include/exclude patterns are shell-style globs applied to file paths relative to the watch root, using forward slashes regardless of OS.
- Exclude takes precedence over include when both match a path.
- The configured command executes as a subprocess. If the command is provided as a string, it will be split into argv with shlex.split and executed without a shell by default for safety; an optional config flag shell: true allows shell execution.
- The tool should not run multiple instances of the command in parallel. If changes occur while a command is running, the tool will schedule exactly one re-run after the current run completes (coalescing multiple events).
- Directory-only events are ignored; only file events trigger the command.

Project structure
- watcher.py — CLI entry point and runtime orchestration
- config.py — YAML config loader and defaults
- watcher.yaml — example configuration
- test_watcher.py — unit tests
- Optional: requirements.txt with watchdog>=x, PyYAML>=x for convenience

Configuration format (watcher.yaml)
- Fields:
  - watch_path: string, path to directory to watch (default: current working directory)
  - command: string or list of strings; the command to run on changes (required)
  - include: list of glob patterns (default: ["**/*.py"])
  - exclude: list of glob patterns (default: [".git/**", ".venv/**", "venv/**", "__pycache__/**", "*.pyc", ".idea/**", ".mypy_cache/**"])
  - debounce_ms: integer (default: 300)
  - shell: boolean (default: false)
  - verbose: boolean (default: false)
- Semantics:
  - include patterns are ORed; a path matches if it matches any include.
  - exclude patterns are ORed; a path is excluded if it matches any exclude.
  - Exclude wins if both include and exclude match.

Implementation details by file

1) config.py
- Responsibilities:
  - Define a Config data structure to hold configuration with defaults.
  - Load a YAML file and merge with defaults.
  - Validate and normalize fields.
  - Expose a load_config(config_path: str) -> Config function.

- Steps:
  - Define a dataclass Config with fields:
    - watch_path: pathlib.Path
    - command: list[str]
    - include: list[str]
    - exclude: list[str]
    - debounce_ms: int
    - shell: bool
    - verbose: bool
  - Implement function read_yaml_file(path) that:
    - Expands user (~) and env vars.
    - If file does not exist, raise a clear error (or return defaults if desired; assume we error if missing unless overridden by CLI).
    - Loads YAML using yaml.safe_load; if None, treat as empty dict.
  - Implement function normalize_patterns(patterns: list[str]) -> list[str]:
    - Ensure each is a string.
    - Strip whitespace.
    - Remove empty entries.
    - Convert backslashes to forward slashes to normalize.
  - Implement function normalize_command(cmd, shell: bool) -> list[str] or error:
    - If cmd is a list of strings, return as-is.
    - If cmd is a string:
      - If shell == true, keep single string form for subprocess with shell True.
      - Else split to argv with shlex.split and return list.
    - Otherwise raise ValueError.
    - In Config, store both raw and shell flag; for simplicity store command_argv (list[str]) and a shell flag; if shell True and command given as list, join into string or pass first element with shell True; decide: if shell is True, store command_str (string) created by joining list with spaces for logging and running; else store argv. Provide properties to access appropriate.
  - Implement load_config(config_path: str) -> Config:
    - Create default values as described above.
    - Merge YAML values with defaults:
      - watch_path: default Path.cwd() if not provided; else Path(value).expanduser().resolve()
      - command: required; if missing, raise ValueError.
      - include/exclude: normalize patterns.
      - debounce_ms: int; minimum 50 ms safeguard; default 300.
      - shell: bool; default False.
      - verbose: bool; default False.
    - Normalize command based on shell flag:
      - If shell False: store command_argv: list[str], shell=False
      - If shell True: store command_str: string, shell=True
    - Return Config instance with normalized fields.
  - Provide helper function path_to_rel_posix(path: pathlib.Path, root: pathlib.Path) -> str:
    - Return path.relative_to(root).as_posix() if possible, else fallback to path.as_posix().

- Validation:
  - Ensure watch_path exists and is a directory; otherwise raise a clear error.
  - Ensure command is set; else error.
  - Ensure debounce_ms is positive.

2) watcher.py
- Responsibilities:
  - Parse CLI arguments, load config, set up watchdog Observer, filter events with include/exclude, debounce and run command.
  - Handle graceful shutdown on Ctrl+C.
  - Provide useful logging when verbose.

- CLI design (argparse):
  - --config/-c: path to YAML (default: "watcher.yaml" in current working directory)
  - --path/-p: override watch_path
  - --debounce-ms/-d: override debounce_ms
  - --verbose/-v: flag to enable verbose
  - --shell: flag to force shell execution override
  - If command is provided via CLI operands (optional), e.g., watcher.py -- pytest -q
    - To keep scope simpler, assume command comes from YAML only. State in help that command must be in watcher.yaml. We will still add potential future support in code structure but not implement parsing positional args now.

- Components:
  - EventFilter:
    - Initialized with root: Path, include_patterns: list[str], exclude_patterns: list[str]
    - Method matches(path: Path, is_directory: bool) -> bool:
      - Ignore directories (return False) to avoid triggering on directory-only events.
      - Convert to relative posix string relative to root.
      - Use fnmatch.fnmatchcase for each pattern.
      - included = any(fnmatch(path_rel, patt) for patt in include_patterns)
      - excluded = any(fnmatch(path_rel, patt) for patt in exclude_patterns)
      - Return included and not excluded.
  - DebouncedCommandRunner:
    - Initialized with command (argv list or string + shell flag), debounce_ms: int, verbose: bool, cwd: Path
    - Internal state:
      - timer: threading.Timer or None
      - lock: threading.Lock
      - running: bool
      - pending: bool (indicates there were triggers while running)
      - last_trigger_path: str (for logging)
      - shutdown: bool
    - Methods:
      - trigger(cause_path: str):
        - Acquire lock.
        - Store last_trigger_path = cause_path.
        - If shutdown: return.
        - If timer exists: cancel it.
        - Create new timer to fire after debounce_ms that calls _on_timer_fired().
        - Start timer.
        - If verbose: print "Change detected in X; scheduling run in N ms"
      - _on_timer_fired():
        - Acquire lock.
        - If running:
          - Set pending = True
          - Return
        - Else:
          - running = True
        - Release lock.
        - Start a background thread to execute _run_command().
      - _run_command():
        - Print "Running: ..." when verbose.
        - Use subprocess.run:
          - If shell flag is True: run(command_str, shell=True, cwd=cwd)
          - Else: run(command_argv, shell=False, cwd=cwd)
        - Capture and stream output to console (leave default stdout/stderr).
        - After subprocess finishes, get return code.
        - If verbose: print "Command exited with code X"
        - Acquire lock:
          - running = False
          - If pending:
            - pending = False
            - If shutdown: return
            - Option 1: Immediately schedule another run by invoking _on_timer_fired() or creating a new timer with debounce_ms (choose to debounce again to give editor time to finish). Implement: create fresh timer with debounce_ms and start.
          - Else: do nothing
      - stop():
        - Set shutdown = True.
        - Cancel any timer if present.
    - Behavior summary:
      - Coalesces multiple events within debounce interval into a single run.
      - If events occur while command is running, exactly one additional run will occur after the process completes and after an additional debounce interval.
  - WatchEventHandler (subclass watchdog.events.FileSystemEventHandler):
    - Initialized with root Path, EventFilter, DebouncedCommandRunner, verbose
    - For on_created, on_modified, on_moved, on_deleted:
      - Determine target path:
        - For moved events, consider dest_path.
        - For other events, event.src_path.
      - Convert to Path object and resolve relative to root if possible.
      - If event.is_directory: ignore
      - If filter.matches(path, is_directory=False):
        - runner.trigger(path relative posix)
        - If verbose, print event type and path.

- Main function flow:
  - Parse arguments.
  - Determine config path (default "watcher.yaml" in current working directory).
  - Load config via config.load_config.
  - Apply CLI overrides: path, debounce_ms, verbose, shell (if provided).
  - Initialize EventFilter with config.include/exclude patterns and root path.
  - Initialize DebouncedCommandRunner with command, debounce, verbose, cwd=root.
  - Set up watchdog.observers.Observer:
    - Create observer = Observer()
    - Create handler = WatchEventHandler(...)
    - observer.schedule(handler, str(root), recursive=True)
    - observer.start()
  - Print "Watching <root> ..." and an initial "Patterns include: ..., exclude: ..." when verbose.
  - Use try/except KeyboardInterrupt:
    - On KeyboardInterrupt: print "Stopping..." if verbose; call runner.stop(); observer.stop(); observer.join()
  - Exit with code 0 (do not propagate last command's code; this is a watcher).

- Notes:
  - Use logging to stdout via print. Keep output minimal unless verbose is set.
  - Ensure threads are daemons or well-joined to avoid hanging on exit.

3) watcher.yaml (example)
- Provide a realistic example that monitors the WorkingDir project:
  - watch_path: "."
  - command: "pytest -q"
  - include: ["**/*.py"]
  - exclude: [".git/**", ".venv/**", "venv/**", "__pycache__/**", "*.pyc", ".idea/**", ".mypy_cache/**"]
  - debounce_ms: 300
  - shell: false
  - verbose: true

4) test_watcher.py
- Overall testing approach:
  - Avoid reliance on live filesystem events to keep tests fast and deterministic.
  - Test configuration loading and normalization.
  - Test pattern matching logic in EventFilter.
  - Test DebouncedCommandRunner debounce and pending behavior using short intervals and mocking subprocess.run.
  - Test WatchEventHandler by constructing event objects and asserting that runner.trigger is called appropriately (mock runner).

- Fixtures and helpers:
  - Use pytest and tmp_path for temporary directories.
  - Use monkeypatch to mock subprocess.run.
  - Use time.sleep with small margins for timers; set debounce_ms in tests to small value (e.g., 50 ms) for speed.
  - Create fake events:
    - from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileDeletedEvent.

- Test cases:
  - test_load_config_defaults:
    - Create a temporary watcher.yaml with only command.
    - Load via load_config.
    - Assert defaults: include default patterns, exclude default patterns, debounce_ms = 300, shell False, watch_path cwd unless overridden by file's path; for testing set watch_path in config to tmp_path.
  - test_load_config_command_parsing_string_and_list:
    - YAML with command as string and shell False: ensure command_argv parsed correctly.
    - YAML with shell True and command as string: ensure shell flag is True and stored string preserved for logging.
  - test_event_filter_matching:
    - Create root temp dir structure with files a.py, b.txt, __pycache__/c.pyc.
    - Initialize EventFilter with include ["**/*.py", "tests/**"] and exclude ["__pycache__/**", "*.pyc"].
    - Assert matches for a.py True, b.txt False, __pycache__/c.pyc False.
  - test_debounce_single_run:
    - Mock subprocess.run to capture invocations and simulate quick success.
    - Create runner with debounce_ms=50.
    - Trigger runner.trigger("file1.py"), wait 20 ms, trigger again "file2.py", wait 100 ms to allow timer to fire and command to run.
    - Assert subprocess.run called exactly once.
  - test_pending_rerun_after_completion:
    - Mock subprocess.run to block for e.g., 100 ms (simulate long-running).
    - Create runner with debounce_ms=30.
    - Trigger initial event, wait 40 ms for timer to queue and process begins, then while running, trigger multiple more events.
    - After the first run completes, ensure that exactly one additional run occurs (call count 2). Allow enough time for second debounce.
  - test_watch_event_handler_calls_trigger_on_file_events_only:
    - Create mock runner with trigger method recording calls.
    - Create EventFilter that returns True only for "*.py" files.
    - Create handler; call on_created with directory event (event.is_directory True) and file event (False).
    - Assert trigger not called for directory but called once for file.
  - Optional integration test with real Observer (may be brittle). If included:
    - Start observer on tmp_path, write a .py file, verify runner.trigger called. Mark as slower test.

- Teardown:
  - Ensure runner.stop() is called in tests using timers to avoid background threads leaking between tests.

Development steps and milestones
1) Set up environment and dependencies:
  - Add requirements: watchdog, PyYAML, pytest.
2) Implement config.py:
  - Dataclass, YAML loader, normalization, validation, command parsing logic.
  - Unit tests for config first (TDD).
3) Implement EventFilter (in watcher.py or separate utility in same file):
  - Include/exclude semantics, case sensitive matching.
  - Tests for matching behavior.
4) Implement DebouncedCommandRunner:
  - Threading.Timer-based debounce, running flag, pending flag, shell vs argv execution, logging.
  - Tests for debounce behaviors and pending reruns with mocked subprocess.
5) Implement WatchEventHandler:
  - File events mapping to runner.trigger with filter.
  - Tests for calling trigger appropriately.
6) Implement CLI in watcher.py:
  - argparse parsing, config loading and CLI overrides, observer setup, graceful shutdown.
  - Manual smoke test locally if possible (not executed here; plan for it).
7) Create example watcher.yaml:
  - Include recommended defaults and comments (if desired).
8) Final polish:
  - Add help text and usage examples in watcher.py.
  - Ensure Windows path separator normalization in filter.
  - Handle moved events by examining destination path.
  - Ensure the observer stops cleanly on exit.
9) Write README usage instructions (optional but recommended).

Algorithmic details and edge cases
- Path normalization:
  - For matching, compute posix-style relative path string from event path to root. If path cannot be relativized (e.g., event outside root; unlikely), match on absolute posix path.
- Pattern semantics:
  - Use fnmatch.fnmatchcase for deterministic case sensitivity; note on Windows NTFS case-insensitivity, but our matching remains case-sensitive by default; document this. Optionally, provide a config option case_insensitive (not required; omit for simplicity).
- Event types:
  - on_created, on_modified, on_deleted, on_moved:
    - For moved, use event.dest_path for matching new location. Optionally also consider src_path. To keep simple, consider dest_path only; note in comments.
- Concurrency:
  - Protect shared state in DebouncedCommandRunner with a Lock.
  - Ensure timer callback rechecks state and uses background thread to run subprocess so the timer thread is not blocked by the subprocess.
  - When stopping, cancel timer and set shutdown flag to prevent scheduling new timers.
- Command execution:
  - When shell=False and command is parsed from string, use shlex.split respecting quotes.
  - If shell=True and command provided as list, join with spaces just for runtime; document that shell mode expects a string in YAML.
  - Use cwd=watch_path for subprocess.run.
  - Do not capture stdout/stderr to allow live output; let subprocess inherit parent's stdout/stderr.
- Exit codes:
  - The watcher process continues regardless of the subprocess's exit status. It prints a message with the code when verbose.
- Debounce default:
  - 300 ms if not specified; enforce minimum 50 ms to avoid pathological settings.

Example content for watcher.yaml
- watch_path: "."
- command: "pytest -q"
- include:
  - "**/*.py"
- exclude:
  - ".git/**"
  - ".venv/**"
  - "venv/**"
  - "__pycache__/**"
  - "*.pyc"
  - ".idea/**"
  - ".mypy_cache/**"
- debounce_ms: 300
- shell: false
- verbose: true

Outline of watcher.py main behavior
- Parse args.
- cfg = load_config(args.config)
- Apply overrides: if args.path: cfg.watch_path = Path(args.path).resolve(); if args.debounce_ms: cfg.debounce_ms = args.debounce_ms; if args.verbose: cfg.verbose = True; if args.shell: cfg.shell = True (and adjust command parsing accordingly).
- filter = EventFilter(root=cfg.watch_path, include=cfg.include, exclude=cfg.exclude)
- runner = DebouncedCommandRunner(command=cfg.command_argv or cfg.command_str, shell=cfg.shell, debounce_ms=cfg.debounce_ms, verbose=cfg.verbose, cwd=cfg.watch_path)
- observer = Observer(); handler = WatchEventHandler(root=cfg.watch_path, filter=filter, runner=runner, verbose=cfg.verbose)
- observer.schedule(handler, str(cfg.watch_path), recursive=True); observer.start()
- try: while True: time.sleep(1)
- except KeyboardInterrupt: runner.stop(); observer.stop(); observer.join()

Testing considerations and stability
- Timers: In tests, use short debounce_ms and sleeps with some buffer (e.g., debounce_ms + 50 ms) to reduce flakiness.
- Mocking subprocess.run: Use monkeypatch to replace it and count calls; optionally simulate delays with time.sleep inside the mock.
- Ensure cleanup: In tests that instantiate DebouncedCommandRunner, call stop() at test end to cancel timers and threads.

Future enhancements (not required but easy to add)
- CLI support to pass the command as positional args to override YAML.
- Option to run the command initially at startup.
- Option to print changed file list to the command via environment variable.
- Case-insensitive matching option on Windows.
- Colored logs.

Deliverables summary
- watcher.py:
  - Argparse CLI.
  - EventFilter, DebouncedCommandRunner, WatchEventHandler as described.
  - Observer setup and graceful shutdown.
- config.py:
  - Config dataclass, YAML loader, defaults, normalization, validation, command parsing.
- watcher.yaml:
  - Example with pytest command and typical Python project patterns.
- test_watcher.py:
  - Unit tests for config loading, filtering logic, debounce behavior, handler triggering.

Estimated implementation order and time
- config.py + tests: 1–2 hours
- DebouncedCommandRunner + tests: 1.5–2 hours
- EventFilter + tests: 0.5 hour
- WatchEventHandler + tests: 0.5–1 hour
- CLI wiring and manual sanity: 0.5 hour
- Example config and polish: 0.25 hour
- Total: ~4–6 hours

Notes about WorkingDir
- The WorkingDir is provided for context. This plan assumes a typical Python project structure and that the default include pattern "**/*.py" will be suitable to monitor it. If WorkingDir contains non-Python files that should trigger runs, include patterns can be adjusted in watcher.yaml.
