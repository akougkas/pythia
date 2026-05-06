"""Intent detector comparison harness (plan §F.2).

Runs the three user-facing detectors (rule / semantic / llm) over a prompt
corpus and produces:

  - Per-row CSV: one row per (detector, prompt) with task_type, complexity,
    decomposability, domain_tags, latency_ms, confidence_self.
  - Aggregate JSON: p50/p95/p99 latency per detector, self-confidence
    distribution, pairwise agreement matrix (task_type match, domain Jaccard,
    complexity/decomposability correlation + mean |Δ|).

No ground-truth judge is available (plan "Comparison constraint" section).
The harness therefore reports proxy-accuracy signals only:

  - Per-detector self-confidence (each detector's own uncertainty estimate).
  - Inter-detector agreement (pairwise, with the LLM output treated as a
    soft reference — not ground truth).
  - Latency distribution.

Usage
-----
    uv run python examples/bench_intent_detectors.py \\
        --detectors rule semantic llm \\
        --corpus motivation_bench/prompts.jsonl \\
        --out pred_results/intent_comparison_2026-04-24.csv

Scaffold state
--------------
This file is a Phase 6 scaffold per the approved plan. The structural pieces
below are complete enough to run end-to-end once:

  1. ``make_intent_detector`` lands (Phase 3).
  2. ``SemanticIntentDetector`` lands (Phase 4).
  3. A real benchmark corpus is committed (open question #3 — user is
     wrapping HPC-CG into multi-agent-suitable variants).

The TODO markers below flag places where Jie should fill in concrete logic.
The fallback corpus (the few-shot exemplars from intent.py) lets the harness
produce smoke-test output today without a real corpus.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pythia.contracts import Intent


# --- Data shapes ---


@dataclass
class RunRecord:
    """One (detector, prompt) measurement row."""

    detector: str
    prompt_id: str
    prompt: str
    task_type: str
    complexity: float
    decomposability: float
    domain_tags: str  # comma-joined for CSV-friendliness
    latency_ms: float
    confidence_self: float


# --- Corpus loading ---


def load_corpus(path: Path | None) -> list[tuple[str, str]]:
    """Load prompts as ``(prompt_id, prompt_text)`` pairs.

    Supported formats:
      - JSONL: one ``{"id": "...", "prompt": "..."}`` per line.
      - Plain .txt: one prompt per line; ids auto-assigned as ``"p{i:03d}"``.

    If ``path`` is None, returns the built-in fallback corpus (the four
    few-shot exemplars from intent.py:440-474) — useful for smoke-testing
    the harness before the real corpus is assembled.

    TODO(jie): once motivation_bench/ has a canonical prompts.jsonl with the
    wrapped HPC-CG variants, point the default at it and drop the fallback.
    """
    if path is None:
        # Fallback: the 4 ScienceAgentBench-style few-shot exemplars. Keeps
        # the harness runnable before the real corpus lands.
        return [
            ("fb_01", "Show me the variables in this NetCDF file"),
            (
                "fb_02",
                "Draft the abstract and literature review section for my "
                "paper on distributed computing",
            ),
            (
                "fb_03",
                "Train a graph convolutional network on the aquatic toxicity "
                "dataset to predict compound toxicity. Use the resulting "
                "model to compute and visualize the atomic contributions to "
                "molecular activity of the test compound. Save the figure "
                "as pred_results/aquatic_toxicity_qsar_vis.png.",
            ),
            ("fb_04", "Use Claude to summarize the dataset, limit to 500 tokens, under $2"),
        ]

    if path.suffix == ".jsonl":
        rows: list[tuple[str, str]] = []
        for i, line in enumerate(path.read_text().splitlines()):
            if not line.strip():
                continue
            obj = json.loads(line)
            rows.append((str(obj.get("id", f"p{i:03d}")), str(obj["prompt"])))
        return rows

    if path.suffix == ".txt":
        return [
            (f"p{i:03d}", line.strip())
            for i, line in enumerate(path.read_text().splitlines())
            if line.strip()
        ]

    raise ValueError(f"Unsupported corpus format: {path.suffix}")


# --- Per-detector measurement ---


def extract_confidence(intent: Intent, detector_name: str) -> float:
    """Pull the detector-specific self-confidence out of Intent.constraints.

    Convention (plan §F.2):
      - rule     → ``_confidence_margin``
      - semantic → ``_confidence_task_type``
      - llm      → ``_confidence_llm``
    """
    key = {
        "rule": "_confidence_margin",
        "semantic": "_confidence_task_type",
        "llm": "_confidence_llm",
    }.get(detector_name, "")
    value = intent.constraints.get(key) if key else None
    return float(value) if isinstance(value, (int, float)) else 0.0


def run_detector(
    detector: Any,
    detector_name: str,
    corpus: list[tuple[str, str]],
    warmup: int = 0,
    repeats: int = 1,
) -> list[RunRecord]:
    """Run ``detector`` over the corpus and record one measurement per prompt.

    Default ``warmup=0, repeats=1`` — each prompt is measured on its first
    (uncached) call. This is the realistic "new request" scenario that the
    comparison harness should reflect. A per-detector one-shot warmup call
    outside the measurement loop covers model-load / JIT costs.

    If ``repeats > 1`` is passed, reports the median latency but the first
    measurement still has cache-miss cost; subsequent ones hit the cache.
    """
    # One global warmup per detector to cover model load / JIT / thread-pool
    # startup without contaminating per-prompt cache state.
    if corpus:
        try:
            detector.detect("warmup prompt for model load")
        except Exception:
            pass

    records: list[RunRecord] = []
    for prompt_id, prompt in corpus:
        for _ in range(warmup):
            detector.detect(prompt)

        timings: list[float] = []
        last_intent: Intent | None = None
        for _ in range(repeats):
            t0 = time.perf_counter()
            last_intent = detector.detect(prompt)
            timings.append((time.perf_counter() - t0) * 1000.0)

        assert last_intent is not None
        records.append(
            RunRecord(
                detector=detector_name,
                prompt_id=prompt_id,
                prompt=prompt,
                task_type=last_intent.task_type,
                complexity=last_intent.complexity,
                decomposability=last_intent.decomposability,
                domain_tags=",".join(sorted(last_intent.domain_tags)),
                latency_ms=statistics.median(timings),
                confidence_self=extract_confidence(last_intent, detector_name),
            )
        )
    return records


# --- Aggregation ---


def latency_percentiles(records: list[RunRecord]) -> dict[str, float]:
    latencies = sorted(r.latency_ms for r in records)
    n = len(latencies)
    if n == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "p50": latencies[int(0.50 * (n - 1))],
        "p95": latencies[int(0.95 * (n - 1))],
        "p99": latencies[int(0.99 * (n - 1))],
    }


def _index_by_prompt(records: list[RunRecord]) -> dict[str, RunRecord]:
    return {r.prompt_id: r for r in records}


def pairwise_agreement(
    a: list[RunRecord], b: list[RunRecord]
) -> dict[str, float]:
    """Compute agreement metrics between two detectors over the same corpus.

    Returns:
      - ``task_type_match``: exact-match rate on task_type.
      - ``domain_jaccard_mean``: mean Jaccard similarity on domain_tags.
      - ``complexity_mae``: mean absolute Δ on complexity.
      - ``decomposability_mae``: mean absolute Δ on decomposability.
      - ``complexity_pearson``: Pearson correlation on complexity.

    Skips prompts present in only one detector's record list.

    TODO(jie): add Pearson for decomposability too; consider Cohen's κ or
    similar chance-corrected agreement for task_type if the class
    distribution is skewed.
    """
    idx_a, idx_b = _index_by_prompt(a), _index_by_prompt(b)
    common = sorted(set(idx_a) & set(idx_b))
    if not common:
        return {}

    tt_match = sum(
        1 for pid in common if idx_a[pid].task_type == idx_b[pid].task_type
    ) / len(common)

    def _jaccard(x: str, y: str) -> float:
        xs, ys = set(x.split(",")) - {""}, set(y.split(",")) - {""}
        if not xs and not ys:
            return 1.0
        if not (xs or ys):
            return 0.0
        return len(xs & ys) / max(len(xs | ys), 1)

    jacc_mean = statistics.mean(
        _jaccard(idx_a[pid].domain_tags, idx_b[pid].domain_tags) for pid in common
    )

    comp_mae = statistics.mean(
        abs(idx_a[pid].complexity - idx_b[pid].complexity) for pid in common
    )
    decomp_mae = statistics.mean(
        abs(idx_a[pid].decomposability - idx_b[pid].decomposability)
        for pid in common
    )

    # Pearson correlation on complexity — NaN-safe for constant inputs.
    xs = [idx_a[pid].complexity for pid in common]
    ys = [idx_b[pid].complexity for pid in common]
    try:
        comp_r = statistics.correlation(xs, ys) if len(xs) >= 2 else float("nan")
    except (statistics.StatisticsError, ValueError):
        comp_r = float("nan")

    return {
        "task_type_match": tt_match,
        "domain_jaccard_mean": jacc_mean,
        "complexity_mae": comp_mae,
        "decomposability_mae": decomp_mae,
        "complexity_pearson": comp_r,
    }


# --- Output ---


def write_csv(records: list[RunRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        if not records:
            return
        writer = csv.DictWriter(f, fieldnames=list(asdict(records[0]).keys()))
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))


def summarize(
    per_detector: dict[str, list[RunRecord]]
) -> dict[str, Any]:
    """Build the aggregate JSON summary."""
    out: dict[str, Any] = {"per_detector": {}, "pairwise_agreement": {}}

    for name, recs in per_detector.items():
        confs = [r.confidence_self for r in recs]
        out["per_detector"][name] = {
            "n_prompts": len(recs),
            "latency_ms": latency_percentiles(recs),
            "confidence": {
                "mean": statistics.mean(confs) if confs else 0.0,
                "stdev": statistics.stdev(confs) if len(confs) >= 2 else 0.0,
                "min": min(confs) if confs else 0.0,
                "max": max(confs) if confs else 0.0,
            },
        }

    names = sorted(per_detector)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            key = f"{a}__vs__{b}"
            out["pairwise_agreement"][key] = pairwise_agreement(
                per_detector[a], per_detector[b]
            )

    return out


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, default=str))


# --- Console rendering ---


def _fmt_tags(tags: str, width: int = 25) -> str:
    """Truncate comma-joined tag string for table display."""
    if not tags:
        return "-"
    return tags if len(tags) <= width else tags[: width - 1] + "…"


def print_per_prompt_table(
    per_detector: dict[str, list[RunRecord]],
    corpus: list[tuple[str, str]],
    max_prompts: int = 30,
) -> None:
    """Per-prompt side-by-side comparison across detectors.

    One line per (prompt × detector), grouped by prompt id. Shows task_type,
    complexity, decomposability, a compact domain_tags preview, latency, and
    the detector's self-confidence.
    """
    names = list(per_detector.keys())
    by_id = {name: {r.prompt_id: r for r in per_detector[name]} for name in names}

    print("\n" + "=" * 120)
    print("PER-PROMPT COMPARISON")
    print("=" * 120)
    header = (
        f"{'id':<32} {'detector':<9} {'task_type':<26} "
        f"{'cmplx':>5} {'decmp':>5}  {'tags':<25} {'ms':>8} {'conf':>6}"
    )
    print(header)
    print("-" * 120)

    for prompt_id, prompt in corpus[:max_prompts]:
        print()
        print(f"  prompt: {prompt[:110]}{'…' if len(prompt) > 110 else ''}")
        for name in names:
            r = by_id[name].get(prompt_id)
            if r is None:
                continue
            print(
                f"{prompt_id[:30]:<32} {name:<9} {r.task_type:<26} "
                f"{r.complexity:>5.2f} {r.decomposability:>5.2f}  "
                f"{_fmt_tags(r.domain_tags):<25} "
                f"{r.latency_ms:>8.2f} {r.confidence_self:>6.3f}"
            )
    print("=" * 120)


def print_aggregate_summary(summary: dict[str, Any]) -> None:
    """Readable aggregate: latency percentiles + confidence stats per detector."""
    print("\n" + "=" * 80)
    print("AGGREGATE")
    print("=" * 80)
    print(
        f"{'detector':<10} {'n':>4}  "
        f"{'lat_p50':>9} {'lat_p95':>9} {'lat_p99':>9}  "
        f"{'conf_mean':>10} {'conf_std':>9}"
    )
    print("-" * 80)
    for name, stats in summary["per_detector"].items():
        lat = stats["latency_ms"]
        conf = stats["confidence"]
        print(
            f"{name:<10} {stats['n_prompts']:>4}  "
            f"{lat['p50']:>8.2f}ms {lat['p95']:>8.2f}ms {lat['p99']:>8.2f}ms  "
            f"{conf['mean']:>10.3f} {conf['stdev']:>9.3f}"
        )
    print("=" * 80)


def print_agreement(summary: dict[str, Any]) -> None:
    """Pairwise inter-detector agreement (task_type match, domain Jaccard, ...)."""
    pairs = summary["pairwise_agreement"]
    if not pairs:
        return
    print("\n" + "=" * 80)
    print("PAIRWISE AGREEMENT")
    print("=" * 80)
    print(
        f"{'pair':<28} "
        f"{'tt_match':>10} {'dom_jacc':>10} "
        f"{'cmplx_mae':>10} {'decmp_mae':>10} {'cmplx_r':>9}"
    )
    print("-" * 80)
    for pair_name, m in pairs.items():
        if not m:
            continue
        pretty = pair_name.replace("__vs__", " vs ")
        print(
            f"{pretty:<28} "
            f"{m.get('task_type_match', float('nan')):>10.3f} "
            f"{m.get('domain_jaccard_mean', float('nan')):>10.3f} "
            f"{m.get('complexity_mae', float('nan')):>10.3f} "
            f"{m.get('decomposability_mae', float('nan')):>10.3f} "
            f"{m.get('complexity_pearson', float('nan')):>9.3f}"
        )
    print("=" * 80)


def print_disagreements(
    per_detector: dict[str, list[RunRecord]],
    max_shown: int = 10,
) -> None:
    """Prompts where the three detectors disagreed on task_type."""
    names = list(per_detector.keys())
    if len(names) < 2:
        return
    by_id: dict[str, dict[str, RunRecord]] = {}
    for name in names:
        for r in per_detector[name]:
            by_id.setdefault(r.prompt_id, {})[name] = r

    disagreements: list[tuple[str, dict[str, str]]] = []
    for pid, per_name in by_id.items():
        if len(per_name) < 2:
            continue
        types = {name: rec.task_type for name, rec in per_name.items()}
        if len(set(types.values())) > 1:
            disagreements.append((pid, types))

    if not disagreements:
        print("\nAll detectors agree on task_type for every prompt.")
        return

    print("\n" + "=" * 80)
    print(f"TASK_TYPE DISAGREEMENTS  ({len(disagreements)} / {len(by_id)} prompts)")
    print("=" * 80)
    for pid, types in disagreements[:max_shown]:
        parts = "  ".join(f"{name}={t}" for name, t in types.items())
        print(f"  {pid:<35}  {parts}")
    if len(disagreements) > max_shown:
        print(f"  ... and {len(disagreements) - max_shown} more")
    print("=" * 80)


# --- CLI ---


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--detectors",
        nargs="+",
        default=["rule", "semantic", "llm"],
        choices=["rule", "semantic", "llm"],
        help="Detectors to benchmark (default: all three).",
    )
    p.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Path to prompt corpus (JSONL or .txt). Default: built-in fallback.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("pred_results/intent_comparison.csv"),
        help="Output CSV path. Summary JSON is written alongside with .json suffix.",
    )
    p.add_argument(
        "--warmup", type=int, default=0,
        help="Warmup calls per prompt (default: 0 — first call is the measurement).",
    )
    p.add_argument(
        "--repeats", type=int, default=1,
        help="Measurement calls per prompt (default: 1 — one fresh call, no cache hits).",
    )
    p.add_argument(
        "--show-prompts", type=int, default=30,
        help="Max prompts to show in the per-prompt comparison table (default: 30).",
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress console tables; write CSV/JSON only.",
    )
    p.add_argument(
        "--llm-sla", type=float, default=30.0,
        help=(
            "SLA timeout (s) for LLM calls IN THIS BENCHMARK. "
            "Default 30s so we measure real end-to-end LLM behavior. "
            "Production LLMIntentDetector still defaults to 0.45s — this flag "
            "only affects the harness."
        ),
    )
    p.add_argument(
        "--llm-model", type=str, default=None,
        help="Override LLM model name (default: LLMIntentDetector's default).",
    )
    p.add_argument(
        "--llm-provider", type=str, default=None,
        choices=["ollama", "lmstudio", "vllm"],
        help="Override LLM provider (default: resolved by factory).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        from pythia.intent import make_intent_detector
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    corpus = load_corpus(args.corpus)
    print(f"Loaded {len(corpus)} prompts from {args.corpus or '<fallback>'}")

    per_detector: dict[str, list[RunRecord]] = {}
    for name in args.detectors:
        # LLM detector uses relaxed SLA so the benchmark measures actual
        # provider behavior. Production callers of make_intent_detector still
        # get the 450ms default.
        factory_kwargs: dict[str, Any] = {}
        if name == "llm":
            factory_kwargs["sla_timeout"] = args.llm_sla
            factory_kwargs["timeout"] = args.llm_sla
            if args.llm_model:
                factory_kwargs["model"] = args.llm_model
            if args.llm_provider:
                factory_kwargs["provider"] = args.llm_provider

        try:
            detector = make_intent_detector(name, **factory_kwargs)
        except NotImplementedError:
            print(f"SKIP {name}: factory not implemented yet (Phase 3 scaffold)")
            continue
        except ImportError as exc:
            print(f"SKIP {name}: {exc}")
            continue

        print(f"Running {name} over {len(corpus)} prompts...")
        try:
            per_detector[name] = run_detector(
                detector, name, corpus, warmup=args.warmup, repeats=args.repeats
            )
        except NotImplementedError:
            print(f"SKIP {name}: detector body not implemented yet")

    all_records: list[RunRecord] = [r for recs in per_detector.values() for r in recs]
    if not all_records:
        print("No detectors produced output — nothing to write.", file=sys.stderr)
        return 2

    write_csv(all_records, args.out)
    summary = summarize(per_detector)
    summary_path = args.out.with_suffix(".json")
    write_summary(summary, summary_path)

    if not args.quiet:
        print_per_prompt_table(per_detector, corpus, max_prompts=args.show_prompts)
        print_aggregate_summary(summary)
        print_agreement(summary)
        print_disagreements(per_detector)

    print(f"\nWrote {len(all_records)} rows to {args.out}")
    print(f"Wrote summary JSON to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
