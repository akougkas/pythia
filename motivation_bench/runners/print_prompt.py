"""Dump the full composed prompt for a given case, for manual inspection
or for pasting into a non-Claude CLI (Gemini, GPT, etc.).

Usage:
    python -m motivation_bench.runners.print_prompt \\
        --requests motivation_bench/workloads/hpc_cg_complex/hpc_cg_complex_requests_verify.json \\
        --case-id complex_gen_omp_26_reduce_product_of_inverses

    # or just take the first case
    python -m motivation_bench.runners.print_prompt --requests <path>

    # objective-only (strip the plan-mode wrapper)
    python -m motivation_bench.runners.print_prompt --requests <path> --objective-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .case_factory import build_case
from .providers.agent_sdk import AgentSDKPlanMode


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests", required=True, type=Path)
    p.add_argument("--case-id", default=None,
                   help="If omitted, prints the first case in the file")
    p.add_argument("--objective-only", action="store_true",
                   help="Strip the plan-mode preamble and working-dir note")
    p.add_argument("--workdir", type=Path,
                   default=Path("/tmp/print_prompt_workdir"),
                   help="Where to stage cluster_ares.yaml (won't be written if --objective-only)")
    args = p.parse_args()

    requests = json.loads(args.requests.read_text())
    if args.case_id:
        match = [r for r in requests if r["id"] == args.case_id]
        if not match:
            raise SystemExit(f"No case matched {args.case_id!r}")
        request = match[0]
    else:
        request = requests[0]

    if args.objective_only:
        print(request["request"])
        return

    case = build_case(request, args.workdir)
    prompt = AgentSDKPlanMode().compose_prompt(case)
    print(prompt)


if __name__ == "__main__":
    main()
