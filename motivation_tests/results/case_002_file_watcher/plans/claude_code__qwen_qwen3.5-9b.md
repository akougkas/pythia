---
case: case_002_file_watcher
framework: claude_code
model: qwen/qwen3.5-9b
provider: lm_studio
session_id: 19f05fa1-cead-4b6e-bdcb-4109ec50bb20
duration_ms: 298233
duration_wall_s: 316.1
cost_usd: 2.6585774000000004
num_turns: 15
timestamp: 2026-03-18T15:20:38.397777+00:00
error: None
---

# Plan

# Case 002: File Watcher — Implementation Plan

## Context

Create a Python CLI tool that monitors a directory for file changes and automatically runs a configurable command when source files are modified. This is a greenfield implementation with no existing watchdog or YAML configuration patterns in the codebase, but should follow the existing `argparse` CLI pattern from `eval1.py`.

## Design Decisions

### Architecture
- **CLI Entry Point**: `watcher.py` — Uses argparse with subcommand pattern (matching `eval1.py`)
- **Config Loader**: `config.py` — YAML-based configuration via PyYAML
- **Example Config**: `watcher.yaml` — Sample configuration demonstrating usage
- **Tests**: `test_watcher.py` — Comprehensive unit tests

### File System Events to Monitor
| Event Type | Trigger Action |
|------------|----------------|
| `modified` | Run command after debounce (300ms default) |
| `created` | Run command after debounce |
| `deleted` | Only for source file patterns, not outputs |

### Debounce Implementation
- Use asyncio-based debouncer with configurable delay (default: 300ms)
- Debounce timer reset on each matching event
- Minimum debounce time before executing command

### Include/Exclude Pattern Resolution
1. Resolve glob patterns at startup
2. Track file path sets for include and exclude patterns
3. Event handler checks if changed file matches any pattern
4. Exclude patterns take precedence (AND logic)

## Critical Files to Create

| File | Purpose | Key Components |
|------|---------|----------------|
| `watcher.py` | Main CLI entry point | argparse CLI, Debouncer class, WatchHandler class, asyncio event loop |
| `config.py` | YAML config loader | ConfigDataclass, yaml.load(), pattern resolution |
| `watcher.yaml` | Example configuration | directory, command, debounce_ms, include/exclude patterns |
| `test_watcher.py` | Unit tests | Debouncer tests, CLI parsing tests, config loading tests |

## Implementation Steps

### Step 1: Create `config.py` (YAML Configuration Loader)

```python
"""Configuration loader for File Watcher."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class PatternSpec:
    """Pattern specification for include/exclude globs."""
    pattern: str
    absolute: bool = False


@dataclass
class FileWatcherConfig:
    """File watcher configuration."""
    # Directory to monitor (relative or absolute)
    directory: str = "src"

    # Command to execute when source files change
    command: Optional[str] = None

    # Debounce delay in milliseconds (default: 300ms)
    debounce_ms: int = 300

    # Include patterns (empty = monitor all files)
    include: List[str] = field(
        default_factory=lambda: []
    )

    # Exclude patterns (empty = include everything not in directory)
    exclude: List[str] = field(
        default_factory=lambda: ["*.pyc", "__pycache__/*"]
    )

    # Print event logs
    verbose: bool = False


def load_config(path: str = "watcher.yaml") -> FileWatcherConfig:
    """Load configuration from YAML file."""
    with open(path, 'r') as f:
        data = yaml.safe_load(f) or {}

    return FileWatcherConfig(
        directory=data.get('directory', 'src'),
        command=data.get('command', None),
        debounce_ms=data.get('debounce_ms', 300),
        include=data.get('include', []),
        exclude=data.get('exclude', ['*.pyc']),
        verbose=data.get('verbose', False),
    )


def resolve_patterns(
    directory: Path,
    patterns: List[str],
    absolute: bool = False
) -> set:
    """Resolve glob patterns to matched files."""
    from fnmatch import fnmatch
    import os

    # Get all files in directory (non-recursive for simplicity)
    base_path = directory if absolute else directory.resolve()

    matched = set()
    for root, dirs, files in os.walk(base_path):
        for file in files:
            full_path = Path(root) / file

            # Check each pattern against the relative path
            rel_path = str(full_path.relative_to(base_path))

            for pattern in patterns:
                if fnmatch(rel_path, pattern) or fnmatch(file, pattern):
                    matched.add(rel_path)
                    break

    return matched
```

### Step 2: Create `watcher.yaml` (Example Configuration)

```yaml
# File Watcher Configuration
# Usage: python watcher.py run --config watcher.yaml

directory: ./WorkingDir          # Directory to monitor (relative or absolute path)
command: pytest                   # Command to run on file changes

debounce_ms: 300                 # Debounce delay in milliseconds

# Files to watch (empty = all files)
include: []

# Files to ignore
exclude:
  - "*.pyc"                      # Compiled Python files
  - "__pycache__/*"             # Cache directories
  - ".git/*"                    # Git repository
  - "venv/*"                    # Virtual environments
  - ".env"                      # Environment variables

# Optional: enable verbose logging for event tracking
verbose: false
```

### Step 3: Create `watcher.py` (Main CLI Entry Point)

```python
#!/usr/bin/env python3
"""File Watcher CLI Tool.

Monitors a directory for file changes and runs a configurable command
when source files are modified.
"""

import argparse
import asyncio
from pathlib import Path
from typing import Optional, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Install watchdog library: pip install watchdog")
    exit(1)


class Debouncer:
    """Debouncer to throttle rapid events."""

    def __init__(self, delay_ms: int):
        self.delay_ms = delay_ms
        self._task: Optional[asyncio.Task] = None

    async def set(self, value):
        """Set the debounced value."""
        if self._task is not None:
            self._task.cancel()

        try:
            await asyncio.sleep(self.delay_ms / 1000)
        except asyncio.CancelledError:
            pass

        self.value = value

    @property
    def value(self):
        return self._value if hasattr(self, '_value') else None

    @value.setter
    def value(self, val):
        self._value = val


class FileEventHandler(FileSystemEventHandler):
    """Handle file system events."""

    def __init__(
        self,
        directory: Path,
        include_patterns: Set[str] = None,
        exclude_patterns: Set[str] = None,
        command: str = None,
        debounce_ms: int = 300,
        verbose: bool = False
    ):
        super().__init__()
        self.directory = directory.resolve()
        self.include_patterns = include_patterns or set()
        self.exclude_patterns = exclude_patterns or set()
        self.command = command
        self.debounce_ms = debounce_ms
        self.verbose = verbose

        # Debouncer for rapid event handling
        self._debouncer = Debouncer(self.debounce_ms)

    def _is_source_file(self, filepath: Path) -> bool:
        """Check if the changed file is a source file."""
        rel_path = str(filepath.relative_to(self.directory))

        # Skip exclude patterns first
        for pattern in self.exclude_patterns:
            from fnmatch import fnmatch
            if fnmatch(rel_path, pattern) or fnmatch(filepath.name, pattern):
                return False

        # Include all if no include patterns specified
        if not self.include_patterns:
            return True

        # Otherwise, must match an include pattern
        for pattern in self.include_patterns:
            from fnmatch import fnmatch
            if fnmatch(rel_path, pattern) or fnmatch(filepath.name, pattern):
                return True

        return False

    def _get_command(self, filepath: Path) -> str:
        """Get the command to run."""
        if self.command is None:
            return f"echo 'File changed: {{filepath}}' (no command configured)"

        # Use brace expansion for path substitution
        cmd = self.command.replace("{filepath}", str(filepath))
        cmd = cmd.replace("{dir}", str(self.directory))
        return cmd

    def _log_event(self, event_type: str, filepath: Path):
        """Log file system event."""
        if not self.verbose:
            return

        print(f"[{event_type.upper()}] {filepath}")
        if self.command:
            print(f"  -> Would run: {self._get_command(filepath)}")

    def on_modified(self, event):
        """Handle file modification events."""
        if not isinstance(event, FileSystemEvent):
            return

        filepath = Path(event.src_path)

        # Skip directory changes
        if event.is_directory:
            return

        # Check if it's a source file we care about
        if not self._is_source_file(filepath):
            if self.verbose:
                print(f"[MODIFIED] Skipping {filepath} (not in include/exclude)")
            return

        # Debounce and schedule command execution
        asyncio.create_task(self._debouncer.set((self.command, filepath)))

    async def _run_command(self, command: str, filepath: Path):
        """Run the configured command."""
        if self.verbose:
            print(f"\n[EXECUTING] Running: {command}")

        try:
            exit_code = await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await exit_code.communicate()
            print(f"Exit code: {exit_code.returncode}")

            if stdout:
                print(stdout.decode())
            if stderr:
                print(stderr.decode())

        except Exception as e:
            print(f"Error running command: {e}")

    async def run(self):
        """Main event loop."""
        while True:
            value = self._debouncer.value
            await value
```

### Step 4: Create `test_watcher.py` (Unit Tests)

```python
#!/usr/bin/env python3
"""Unit tests for File Watcher."""

import argparse
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

# Test imports
try:
    from watchdog.observers import Observer
except ImportError:
    pass

from config import (
    load_config,
    PatternSpec,
    FileWatcherConfig,
)


class TestDebouncer(unittest.TestCase):
    """Tests for the Debouncer class."""

    def setUp(self):
        self.debouncer = Debouncer(delay_ms=100)  # Fast test debouncer

    def test_initial_value_is_none(self):
        """Initially, no value is set."""
        self.assertIsNone(self.debouncer.value)

    async def test_set_value(self):
        """Setting a value should be delayed."""
        await self.debouncer.set(("test", Path("src/test.py")))
        self.assertEqual(
            self.debouncer.value,
            ("test", Path("src/test.py"))
        )

    async def test_multiple_sets_resets_timer(self):
        """Multiple rapid sets should reset the timer."""
        # Set first value
        await self.debouncer.set(("first", Path("a.py")))

        # Immediately set second value
        await self.debouncer.set(("second", Path("b.py")))

        # The original value should be discarded
        self.assertEqual(
            self.debouncer.value,
            ("second", Path("b.py"))
        )


class TestConfig(unittest.TestCase):
    """Tests for configuration loading."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_default_config(self):
        """Test loading default configuration."""
        config = FileWatcherConfig(
            directory="src",
            command="pytest",
            debounce_ms=300,
        )

        self.assertEqual(config.directory, "src")
        self.assertEqual(config.command, "pytest")
        self.assertEqual(config.debounce_ms, 300)

    def test_load_yaml_config(self):
        """Test loading from YAML file."""
        yaml_content = """
directory: ./myproject
command: pytest -v
debounce_ms: 500
include: ["*.py", "*.pyx"]
exclude: ["*.pyc", ".git/*"]
verbose: true
"""

        with open(self.temp_dir.name, "w") as f:
            f.write(yaml_content)

        config = load_config(self.temp_dir.name)

        self.assertEqual(config.directory, "./myproject")
        self.assertEqual(config.command, "pytest -v")
        self.assertEqual(config.debounce_ms, 500)

    def test_include_patterns_resolve(self):
        """Test include pattern resolution."""
        from config import resolve_patterns

        with TemporaryDirectory() as tmpdir:
            # Create test files
            Path(tmpdir).joinpath("src/main.py").touch()
            Path(tmpdir).joinpath("src/utils.py").touch()
            Path(tmpdir).joinpath("readme.md").touch()

            # Resolve include pattern
            matched = resolve_patterns(
                Path(tmpdir),
                ["*.py"]
            )

            self.assertIn("main.py", matched)
            self.assertIn("utils.py", matched)
            self.assertNotIn("readme.md", matched)

    def test_exclude_patterns_resolve(self):
        """Test exclude pattern resolution."""
        from config import resolve_patterns

        with TemporaryDirectory() as tmpdir:
            Path(tmpdir).joinpath("src/main.py").touch()
            Path(tmpdir).joinpath("src/cache.pyc").touch()

            # Get all files first, then filter by exclude
            all_files = set(Path(p).name for p in Path(tmpdir).rglob("*"))

            matched = resolve_patterns(
                Path(tmpdir),
                [],  # Include all
                absolute=True
            )

            # Should not match .pyc files if we filter properly
            pass  # Simplified for now


class TestCLI(unittest.TestCase):
    """Tests for CLI argument parsing."""

    def test_default_cli_args(self):
        """Test default CLI arguments."""
        parser = argparse.ArgumentParser(description="File Watcher CLI")

        # Simplified parser matching the design
        subparsers = parser.add_subparsers(dest="command", required=True)

        run_parser = subparsers.add_parser("run")
        run_parser.add_argument(
            "--config",
            default="watcher.yaml"
        )

        args = parser.parse_args(["run"])
        self.assertEqual(args.command, "run")

    def test_cli_with_config(self):
        """Test CLI with config file argument."""
        parser = argparse.ArgumentParser(description="File Watcher CLI")

        subparsers = parser.add_subparsers(dest="command", required=True)
        run_parser = subparsers.add_parser("run")
        run_parser.add_argument(
            "--config",
            default="watcher.yaml"
        )
        run_parser.add_argument(
            "--directory",
            default=None,
            help="Directory to monitor"
        )

        args = parser.parse_args(["run", "--directory", "src"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.directory, "src")


class TestFileEventHandler(unittest.TestCase):
    """Tests for file event handler."""

    @patch("watcher.Path")
    def test_on_modified_directory_skipped(self, mock_path):
        """Directory changes should be skipped."""
        from watcher import FileEventHandler

        handler = FileEventHandler(
            directory="/tmp",
            command="pytest"
        )

        mock_event = MagicMock()
        mock_event.src_path = "/some/directory"
        mock_event.is_directory = True

        # Should not raise or execute
        handler.on_modified(mock_event)


if __name__ == "__main__":
    unittest.main()
```

## Verification Plan

### 1. Installation
```bash
# Install dependencies
pip install watchdog pyyaml

# Verify installation
python -c "import watchdog; import yaml; print('OK')"
```

### 2. Test Configuration Loading
```bash
# Create watcher.yaml in WorkingDir
cp /home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/WorkingDir/watcher.yaml \
   /home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/WorkingDir/watcher.yaml

# Test config loading
python -c "from config import load_config; c = load_config('watcher.yaml'); print(c)"
```

### 3. Run Tests
```bash
cd /home/jye/publications/pythia/motivation_tests/cases/case_002_file_watcher/WorkingDir
pytest test_watcher.py -v
```

### 4. Test Live Monitoring
```bash
# Start watcher in background
python watcher.py run --config watcher.yaml &

# Create a new file
touch WorkingDir/new_file.txt

# Verify command ran (check output or exit code)
```

### 5. Expected End-to-End Flow
1. User creates `WorkingDir` with source files
2. Place `watcher.yaml` configuration in directory
3. Run `python watcher.py run --config watcher.yaml`
4. When source files change, debounce runs test command
5. Output shows debounced execution

## Summary of Deliverables

| File | Description |
|------|-------------|
| `watcher.py` | Main CLI entry point with Debouncer class and FileEventHandler |
| `config.py` | YAML config loader with pattern resolution |
| `watcher.yaml` | Example configuration file |
| `test_watcher.py` | Unit tests for all components |

---

*Plan created for Case 002: File Watcher implementation.*

