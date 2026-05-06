"""Generate RWA-multi dispatch requests by wrapping PaperBench papers.

Three real wrap dimensions, all grounded in PaperBench artifacts (no
fabricated companion files):

1. Budget tier: a wall-clock and GPU-minute pair the planner has to
   reason over. Tighter tiers force the planner to skip ablations and
   only reproduce the central claim; looser tiers open room for one or
   two ablations. The gradient is the planning surface.

2. Deliverable structure (`code/`, `runs/`, `REPORT.md`, `crosscheck/`)
   that mirrors PaperBench's own three rubric categories — Code
   Development, Code Execution, Result Analysis — without leaking the
   rubric. The planner derives the dependency graph from the
   deliverables.

3. Real per-paper constraints from already-shipped files: blacklist.txt
   (forbidden web sources), addendum.md (author clarifications). Both
   staged into the case_dir.

N = 23 papers x 3 budget tiers = 69 plan-instances. Per-task staging
(metadata.stage_dir = "papers/<paper_id>") — same staging mechanism as
hpc_cg_multi, just per-task instead of workload-wide.

Source: PaperBench (preparedness/project/paperbench/data/papers/).
The rubric is the evaluator's possession; the brief never references
rubric content, mirroring how real PaperBench evaluates agents.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
PAPERBENCH_DIR = (
    Path(__file__).parents[3]
    / ".scratch_src" / "preparedness"
    / "project" / "paperbench" / "data" / "papers"
)
PAPERS_DIR = HERE / "papers"

OUTPUT_FULL = HERE / "rwa_multi_requests.json"
OUTPUT_TEST = HERE / "rwa_multi_test.json"
OUTPUT_VERIFY = HERE / "rwa_multi_requests_verify.json"

PAPER_FILES = ("paper.md", "addendum.md", "blacklist.txt", "config.yaml")

WRAP_VERSION = "v1"

BUDGET_VARIANTS = [
    {"tier": "fast",     "wall_clock_min":  5},
    {"tier": "standard", "wall_clock_min": 15},
    {"tier": "thorough", "wall_clock_min": 60},
]

VERIFY_PAPERS = ("sapg", "fre", "mechanistic-understanding")
TEST_PAPERS = (
    "sapg", "fre", "mechanistic-understanding",
    "stochastic-interpolants", "bridging-data-gaps",
)
# Verify/test always use the tightest tier — one task per paper, fastest
# turnaround on smoke runs.
VERIFY_TIER = "fast"

TEMPLATE = """\
Replicate the paper "{title}" within a {wall_clock_min}-minute wall-clock
budget.

Inputs (staged in your working directory):
  - paper.md       the paper text
  - addendum.md    author clarifications (read before scheduling)
  - blacklist.txt  forbidden web sources
  - config.yaml    paper id and title

Deliver, in this order, a self-consistent set of artifacts:
  - code/          working code that loads the datasets and pretrained models
                   named in the paper, plus the baselines and the main method.
  - runs/          logs and outputs from executing the experiments needed to
                   test the paper's central numerical claims.
  - REPORT.md      mapping each reproduced number to the corresponding paper
                   claim, with explanation of any divergence.
  - crosscheck/    one ablation or sanity run that would catch a silent
                   pipeline bug (chosen by you, justified in REPORT.md).

Constraints:
- Stay within the wall-clock budget above.
- Do not fetch from URLs listed in blacklist.txt.
- When an artifact depends on an external service unavailable in this
  environment, mark it "skipped: <rationale>" rather than failing silently.
- Inconsistency between code, run logs, and REPORT.md is a failure even if
  each in isolation looks correct.
"""


def list_papers() -> list[str]:
    if not PAPERBENCH_DIR.is_dir():
        sys.exit(
            f"PaperBench papers not found at {PAPERBENCH_DIR}\n"
            "Pull LFS first:\n"
            "  cd .scratch_src/preparedness && \\\n"
            '    git lfs pull --exclude="" \\\n'
            '      --include="project/paperbench/data/papers/**"'
        )
    return sorted(
        d.name for d in PAPERBENCH_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def read_title(config_yaml: Path) -> str:
    if not config_yaml.exists():
        return "(unknown title)"
    for line in config_yaml.read_text().splitlines():
        line = line.strip()
        if line.startswith("title:"):
            return line[len("title:"):].strip().strip('"').strip("'")
    return "(unknown title)"


LFS_POINTER_SIGNATURE = b"version https://git-lfs.github.com/spec/v1"


def is_lfs_pointer(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(len(LFS_POINTER_SIGNATURE)) == LFS_POINTER_SIGNATURE


def stage_paper(paper_id: str) -> tuple[Path, dict[str, int]]:
    """Copy PaperBench paper artifacts into papers/<paper_id>/."""
    src_dir = PAPERBENCH_DIR / paper_id
    dst_dir = PAPERS_DIR / paper_id
    dst_dir.mkdir(parents=True, exist_ok=True)
    sizes: dict[str, int] = {}
    for fname in PAPER_FILES:
        src = src_dir / fname
        if not src.exists():
            continue
        if is_lfs_pointer(src):
            sys.exit(
                f"{src} is still an LFS pointer.\n"
                "Pull LFS before generating: see module docstring."
            )
        size = src.stat().st_size
        dst = dst_dir / fname
        if not dst.exists() or dst.stat().st_size != size:
            shutil.copy2(src, dst)
        sizes[fname] = size
    return dst_dir, sizes


def build_request(paper_id: str, budget: dict) -> dict:
    dst_dir, sizes = stage_paper(paper_id)
    title = read_title(dst_dir / "config.yaml")
    request = TEMPLATE.format(title=title, **budget)
    return {
        "id": f"rwa_multi_{paper_id}_{budget['tier']}",
        "request": request,
        "metadata": {
            "source": "PaperBench",
            "paper_id": paper_id,
            "paper_title": title,
            "stage_dir": f"papers/{paper_id}",
            "staged_files": sorted(sizes),
            "paper_md_bytes": sizes.get("paper.md", 0),
            "addendum_md_bytes": sizes.get("addendum.md", 0),
            "wrap_version": WRAP_VERSION,
            "budget": budget,
        },
    }


def build_all(papers: list[str], budgets: list[dict]) -> list[dict]:
    return [build_request(p, b) for p in papers for b in budgets]


def print_summary(requests: list[dict]) -> None:
    tiers = Counter(r["metadata"]["budget"]["tier"] for r in requests)
    paper_md_bytes = [r["metadata"]["paper_md_bytes"] for r in requests]
    avg_paper = sum(paper_md_bytes) // max(len(paper_md_bytes), 1)
    avg_request = sum(len(r["request"]) for r in requests) // max(len(requests), 1)
    print(f"\nTasks: {len(requests)}")
    print(f"By tier: {dict(tiers)}")
    print(f"Avg request length: {avg_request} chars (frame only)")
    print(f"Avg paper.md size : {avg_paper} bytes (staged, planner reads)")
    if requests:
        sample = requests[0]
        print(f"\n--- Sample ({sample['id']}) ---")
        print(f"stage_dir: {sample['metadata']['stage_dir']}")
        print(f"budget   : {sample['metadata']['budget']}")
        print()
        print(sample["request"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode", choices=("verify", "test", "full"), default="full",
        help="verify: 3 papers x fast tier (3); test: 5 papers x fast tier (5); "
             "full: all 23 papers x 3 tiers (69)",
    )
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path (default derived from --mode)")
    args = p.parse_args()

    all_papers = list_papers()
    fast_only = [b for b in BUDGET_VARIANTS if b["tier"] == VERIFY_TIER]
    if args.mode == "verify":
        selected = [p for p in VERIFY_PAPERS if p in all_papers]
        budgets = fast_only
        out_path = args.output or OUTPUT_VERIFY
    elif args.mode == "test":
        selected = [p for p in TEST_PAPERS if p in all_papers]
        budgets = fast_only
        out_path = args.output or OUTPUT_TEST
    else:
        selected = all_papers
        budgets = BUDGET_VARIANTS
        out_path = args.output or OUTPUT_FULL

    requests = build_all(selected, budgets)
    out_path.write_text(json.dumps(requests, indent=2))

    print(f"{args.mode}: {len(requests)} tasks "
          f"({len(selected)} papers x {len(budgets)} tier(s))")
    print(f"Source -> {PAPERBENCH_DIR}")
    print(f"Output -> {out_path}")
    print_summary(requests)


if __name__ == "__main__":
    main()
