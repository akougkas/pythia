#!/usr/bin/env python3
"""
export_results_csv.py — Export latency and accuracy data to CSV.

Reads plan metadata JSON (duration_wall_s) and grade JSON (overall_score + sub-scores),
writes a single CSV with all cases, frameworks, and models.

Usage:
    python export_results_csv.py
    python export_results_csv.py --results-dir ./results --output eval_results.csv
"""

import argparse
import csv
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Export eval results to CSV")
    p.add_argument("--results-dir", type=Path, default=Path(__file__).parent / "results")
    p.add_argument("--output", type=Path, default=Path(__file__).parent / "eval_results.csv")
    args = p.parse_args()

    rows = []

    for case_dir in sorted(args.results_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        grade_dir = case_dir / "grades"
        plan_dir = case_dir / "plans"
        if not grade_dir.exists() or not plan_dir.exists():
            continue

        for grade_file in sorted(grade_dir.glob("*__graded.json")):
            grade_data = json.loads(grade_file.read_text())

            stem = grade_file.stem.replace("__graded", "")
            meta_file = plan_dir / f"{stem}.json"
            if not meta_file.exists():
                continue

            meta_data = json.loads(meta_file.read_text())

            framework = grade_data.get("framework_name", "")
            model = grade_data.get("model_name", "")
            grades = grade_data.get("grades", {})

            rows.append({
                "case": case_dir.name,
                "framework": framework,
                "model": model,
                "latency_s": meta_data.get("duration_wall_s"),
                "latency_ms": meta_data.get("duration_ms"),
                "overall_score": grade_data.get("overall_score"),
                "completeness": grades.get("completeness", {}).get("score"),
                "correctness": grades.get("correctness", {}).get("score"),
                "specificity": grades.get("specificity", {}).get("score"),
                "ordering": grades.get("ordering_and_dependencies", {}).get("score"),
                "error_handling": grades.get("error_handling", {}).get("score"),
                "testability": grades.get("testability", {}).get("score"),
                "clarity": grades.get("clarity", {}).get("score"),
                "cost_usd": meta_data.get("total_cost_usd"),
                "num_turns": meta_data.get("num_turns"),
                "provider": meta_data.get("provider"),
                "timestamp": meta_data.get("timestamp"),
            })

    if not rows:
        print("No data found.")
        return

    fieldnames = list(rows[0].keys())
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
