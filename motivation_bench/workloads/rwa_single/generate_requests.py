"""Generate RWA-single dispatch requests from PaperBench papers.

Raw, unwrapped framing: the brief just names the paper and the staged
inputs. The planner has to read paper.md / addendum.md to plan a
replication. No budget tier, no deliverables list, no operational
constraints — that's `rwa_multi`'s job.

Per-task staging (mirrors hpc_cg_multi pattern, but per-paper instead of
workload-wide). Each request's metadata declares `stage_dir =
"papers/<paper_id>"`; the dispatch runner copies every file under that
subdir into the case's working_dir, so the planner can Read them during
planning.

Source: PaperBench (preparedness/project/paperbench/data/papers/).
LFS pull required first; see the project README for the override flags
that defeat the repo's `fetchexclude = project/paperbench/data/**`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
PAPERBENCH_DIR = (
    Path(__file__).parents[3]
    / ".scratch_src" / "preparedness"
    / "project" / "paperbench" / "data" / "papers"
)
PAPERS_DIR = HERE / "papers"

OUTPUT_FULL = HERE / "rwa_single_requests.json"
OUTPUT_TEST = HERE / "rwa_single_test.json"
OUTPUT_VERIFY = HERE / "rwa_single_requests_verify.json"

# Files to copy from each PaperBench paper into the workload's papers/<id>/
# subdir. The runner stages every file under that subdir into the case_dir.
PAPER_FILES = ("paper.md", "addendum.md", "blacklist.txt", "config.yaml")

# Smallest papers by paper.md size — quick to iterate on.
VERIFY_PAPERS = ("sapg", "fre", "mechanistic-understanding")
TEST_PAPERS = (
    "sapg", "fre", "mechanistic-understanding",
    "stochastic-interpolants", "bridging-data-gaps",
)

TEMPLATE = """\
Reproduce the experiments in the paper "{title}".

Inputs (staged in your working directory):
  - paper.md       the paper text
  - addendum.md    author clarifications (read before scheduling)
  - blacklist.txt  forbidden web sources
  - config.yaml    paper id and title
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
    """Pick the `title:` line out of config.yaml without a YAML dep."""
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
    """Copy PaperBench paper artifacts into papers/<paper_id>/.

    Returns (dst_dir, byte sizes per filename). Skips files that don't
    exist upstream; refuses to copy an unresolved LFS pointer.
    Re-runnable.
    """
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


def build_request(paper_id: str) -> dict:
    dst_dir, sizes = stage_paper(paper_id)
    title = read_title(dst_dir / "config.yaml")
    request = TEMPLATE.format(title=title)
    return {
        "id": f"rwa_single_{paper_id}",
        "request": request,
        "metadata": {
            "source": "PaperBench",
            "paper_id": paper_id,
            "paper_title": title,
            "stage_dir": f"papers/{paper_id}",
            "staged_files": sorted(sizes),
            "paper_md_bytes": sizes.get("paper.md", 0),
            "addendum_md_bytes": sizes.get("addendum.md", 0),
        },
    }


def print_summary(requests: list[dict]) -> None:
    paper_md_bytes = [r["metadata"]["paper_md_bytes"] for r in requests]
    avg_paper = sum(paper_md_bytes) // max(len(paper_md_bytes), 1)
    avg_request = sum(len(r["request"]) for r in requests) // max(len(requests), 1)
    print(f"\nTasks: {len(requests)}")
    print(f"Avg request length: {avg_request} chars (frame only)")
    print(f"Avg paper.md size : {avg_paper} bytes (staged, planner reads)")
    if requests:
        sample = requests[0]
        print(f"\n--- Sample ({sample['id']}) ---")
        print(f"stage_dir: {sample['metadata']['stage_dir']}")
        print(f"staged: {sample['metadata']['staged_files']}")
        print()
        print(sample["request"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode", choices=("verify", "test", "full"), default="full",
        help="verify: 3 small papers; test: 5 small papers; full: all 23",
    )
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path (default derived from --mode)")
    args = p.parse_args()

    all_papers = list_papers()
    if args.mode == "verify":
        selected = [p for p in VERIFY_PAPERS if p in all_papers]
        out_path = args.output or OUTPUT_VERIFY
    elif args.mode == "test":
        selected = [p for p in TEST_PAPERS if p in all_papers]
        out_path = args.output or OUTPUT_TEST
    else:
        selected = all_papers
        out_path = args.output or OUTPUT_FULL

    requests = [build_request(p) for p in selected]
    out_path.write_text(json.dumps(requests, indent=2))

    print(f"{args.mode}: {len(requests)} tasks")
    print(f"Source -> {PAPERBENCH_DIR}")
    print(f"Output -> {out_path}")
    print_summary(requests)


if __name__ == "__main__":
    main()
