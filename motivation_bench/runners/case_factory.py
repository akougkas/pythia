"""Build CaseSpec objects from a workload's requests JSON.

The workload directory is derived from the requests file's parent path, so the
factory works for any workload without per-workload conditionals. For each
case, we stage context files into a per-case `working_dir` so the plan-mode
agent can Read / Glob / Grep them during planning. Two staging mechanisms:

1. Workload-level allowlist (`STAGEABLE_FILES`): filenames at the workload
   directory's root, copied into every case_dir. Used by `hpc_cg_multi`
   (cluster_ares.yaml + companions are shared across all cases).

2. Per-case `metadata.stage_dir`: a path relative to the workload directory.
   Every file directly under that subdir is copied into the case_dir. Used by
   `rwa_single` / `rwa_multi`, where each task references a different paper's
   files (papers/<paper_id>/paper.md, addendum.md, blacklist.txt, config.yaml).

Workloads that embed all context inline in the prompt (e.g. `hpc_cg_complex`)
simply set neither and end up with an empty working directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .models import CaseSpec

# Filenames at the workload directory's root that are copied into every case's
# working_dir if present. Add entries here when a workload ships a context
# artifact shared across all its cases.
STAGEABLE_FILES: tuple[str, ...] = (
    "cluster_ares.yaml",
    "storage_decision_guide.md",
    "slurm_usage.md",
)


def load_requests(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def stage_context(
    case_dir: Path,
    workload_dir: Path,
    metadata: dict | None = None,
) -> list[str]:
    """Copy context files into case_dir.

    Sources, in order:
      1. Each filename in STAGEABLE_FILES present at workload_dir root.
      2. Every file directly under `workload_dir / metadata['stage_dir']`,
         when `metadata['stage_dir']` is set.

    Returns the list of filenames actually staged (possibly empty).
    """
    case_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for name in STAGEABLE_FILES:
        src = workload_dir / name
        if not src.exists():
            continue
        dst = case_dir / name
        if not dst.exists():
            shutil.copy2(src, dst)
        staged.append(name)

    stage_dir = (metadata or {}).get("stage_dir")
    if stage_dir:
        src_dir = workload_dir / stage_dir
        if src_dir.is_dir():
            for src in sorted(src_dir.iterdir()):
                if not src.is_file():
                    continue
                dst = case_dir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
                staged.append(src.name)
    return staged


def build_case(request: dict, root_workdir: Path, workload_dir: Path) -> CaseSpec:
    metadata = request.get("metadata", {})
    case_dir = root_workdir / request["id"]
    stage_context(case_dir, workload_dir, metadata)
    return CaseSpec(
        case_id=request["id"],
        prompt=request["request"],
        working_dir=case_dir.resolve(),
        metadata=metadata,
    )


def build_cases(requests_path: Path, root_workdir: Path) -> list[CaseSpec]:
    workload_dir = requests_path.parent
    return [build_case(r, root_workdir, workload_dir) for r in load_requests(requests_path)]
