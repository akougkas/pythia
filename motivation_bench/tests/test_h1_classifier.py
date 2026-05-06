"""H1 Intent Classifier Benchmark — real corpus, multi-detector, no follow-up.

Runs every query in the motivation_bench corpus through every available
IntentDetector, captures per-call latency and the structured Intent output,
and emits three artifacts in a timestamped run directory:

    runs.jsonl     one row per (query, detector, repetition)
    summary.json   per-detector latency stats + N-way pairwise agreement
    manifest.json  CLI args + git sha + library versions + host info

Optional --export-prompts / --export-only / --ingest workflow lets external
hosted models (Gemini, GPT, Claude API, ...) participate in the comparison
without bolting cloud SDKs into this script. Export step writes:

    corpus.jsonl        raw queries selected for this run
    prompts.jsonl       prebuilt system + user prompts (identical templates
                        to LLMIntentDetector — output is directly comparable)
    intent_schema.json  JSON Schema for an Intent (drop into response_format)

The user runs their own client against each external API, then re-feeds the
results back via `--ingest PATH --as-detector NAME` (repeatable).

Usage:

    # local detectors, mixed workload, 50 queries
    uv run python motivation_bench/tests/test_h1_classifier.py \\
        --workload mixed --limit 50

    # export-only, no detectors run
    uv run python motivation_bench/tests/test_h1_classifier.py \\
        --export-only --workload mixed --limit 10 \\
        --output-dir /tmp/h1-export

    # rule + ingested external results
    uv run python motivation_bench/tests/test_h1_classifier.py \\
        --workload mixed --limit 10 --seed 42 --detectors rule \\
        --ingest /tmp/h1-export/external/gpt-4.jsonl --as-detector gpt-4
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import logging
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# motivation_bench/ on sys.path so `from queries import ...` works regardless of cwd.
_BENCH_DIR = Path(__file__).resolve().parent.parent
if str(_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_BENCH_DIR))

from queries import load_by_name  # noqa: E402
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
# sentence-transformers uses its own tqdm bars ("Loading weights:", "Batches:")
# that ignore HF_HUB_DISABLE_PROGRESS_BARS — TQDM_DISABLE silences them globally.
os.environ.setdefault("TQDM_DISABLE", "1")

from pythia.contracts import Intent, bucket  # noqa: E402
from pythia.intent import (  # noqa: E402
    _DEFAULT_DOMAIN_VOCAB,
    _DEFAULT_TASK_TYPE_VOCAB,
    _FALLBACK_TASK_TYPE,
    _LLM_JSON_SCHEMA,
    _LLM_SYSTEM_PROMPT,
    _LLM_USER_TEMPLATE,
    make_intent_detector,
)

_log = logging.getLogger("h1_classifier")
_LOCAL_DETECTORS = ("rule", "semantic", "llm")


@dataclass
class RunRecord:
    """One (query, detector, repetition) measurement."""
    query_id: str
    workload: str
    domain: str
    complexity_label: str
    request: str
    detector: str
    repetition: int
    latency_ms: float | None  # None when ingested without timing
    task_type: str
    complexity: float
    decomposability: float
    domain_tags: list[str]
    constraints: dict[str, Any]


# --- corpus / detectors ---------------------------------------------------


def load_corpus(workload: str, limit: int | None, seed: int) -> list[dict]:
    queries = load_by_name(workload, limit=limit, seed=seed)
    if not queries:
        raise SystemExit(f"Corpus empty for workload={workload!r}, limit={limit}")
    return queries


def build_detectors(
    names: list[str],
    per_detector_kwargs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, tuple[Any, float]]:
    """Construct each named detector. Skip and warn on missing deps / bad provider.

    ``per_detector_kwargs`` is keyed by detector name, e.g.::

        {"llm":      {"provider": "ollama", "model": "...", "sla_timeout": 5.0},
         "semantic": {"model_name": "BAAI/bge-base-en-v1.5",
                      "domain_sim_threshold": 0.40}}

    Each dict is forwarded verbatim to ``make_intent_detector(name, **kwargs)``.
    """
    out: dict[str, tuple[Any, float]] = {}
    per_detector_kwargs = per_detector_kwargs or {}
    for name in names:
        kwargs: dict[str, Any] = dict(per_detector_kwargs.get(name, {}))
        t0 = time.perf_counter()
        try:
            det = make_intent_detector(name, **kwargs)
        except (ImportError, ValueError, OSError) as exc:
            _log.warning("Skipping detector %r: %s", name, exc)
            continue
        init_s = time.perf_counter() - t0
        out[name] = (det, init_s)
        # Surface the underlying implementation so the log says *what* was built.
        # LLM exposes provider + model; rule auto-selects spaCy vs RuleBased; the
        # class name disambiguates either case.
        if name == "llm":
            extra = (
                f" ({type(det).__name__}, provider={getattr(det, '_provider', '?')}, "
                f"model={getattr(det, '_model', '?')})"
            )
        else:
            extra = f" ({type(det).__name__})"
        _log.info("Built detector %r in %.3fs%s", name, init_s, extra)
    return out


def llm_preflight(det: Any, sample_request: str, max_wait: float = 30.0) -> tuple[bool, str]:
    """One direct call against the LLM provider with a generous timeout.

    Bypasses the SLA timeout race so the actual exception (or non-JSON response)
    bubbles up — the in-loop fallback path swallows everything at DEBUG level,
    leaving the user wondering why fallback_rate=100%.

    Returns ``(ok, message)``. On success, ``message`` shows what the provider
    returned. On failure, ``message`` is the actual exception type + text.
    """
    orig_timeout = getattr(det, "_timeout", None)
    orig_sla = getattr(det, "_sla_timeout", None)
    try:
        det._timeout = max_wait
        det._sla_timeout = max_wait
        try:
            raw = det._call_provider(sample_request)
        except Exception as exc:  # noqa: BLE001
            return (False, f"{type(exc).__name__}: {exc}")
        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            return (False, f"non-JSON response: {raw[:200]!r} ({exc})")
        return (True, f"OK; response keys: {sorted(parsed.keys())}")
    finally:
        if orig_timeout is not None:
            det._timeout = orig_timeout
        if orig_sla is not None:
            det._sla_timeout = orig_sla


def warmup(detectors: dict[str, tuple[Any, float]]) -> None:
    """One probe per detector to absorb threadpool / first-parse overhead."""
    for name, (det, _) in detectors.items():
        try:
            det.detect("warmup probe for benchmark setup")
        except Exception as exc:  # noqa: BLE001
            _log.debug("Warmup failed for %s: %s", name, exc)


# --- measurement ----------------------------------------------------------


def _record_for(
    query: dict, detector_name: str, repetition: int,
    intent: Intent, latency_ms: float | None, workload_label: str,
) -> RunRecord:
    return RunRecord(
        query_id=query["id"],
        workload=workload_label,
        domain=query.get("domain", ""),
        complexity_label=query.get("complexity", ""),
        request=query["query"],
        detector=detector_name,
        repetition=repetition,
        latency_ms=latency_ms,
        task_type=intent.task_type,
        complexity=intent.complexity,
        decomposability=intent.decomposability,
        domain_tags=list(intent.domain_tags),
        constraints=dict(intent.constraints),
    )


def run_local(
    detectors: dict[str, tuple[Any, float]],
    queries: list[dict],
    workload_label: str,
    repeats: int,
    progress: bool,
) -> list[RunRecord]:
    """Time each detector against each query. One row per (query, detector, repeat)."""
    records: list[RunRecord] = []
    if "llm" in detectors and repeats > 1:
        _log.warning(
            "repeats=%d with LLM detector active — will clear LLMIntentDetector._cache "
            "between repeats so all calls measure cold latency, not LRU hits.", repeats,
        )

    for q_idx, query in enumerate(queries):
        if progress:
            preview = query["query"][:70].replace("\n", " ")
            print(f"[{q_idx + 1}/{len(queries)}] {query['id']}: {preview}...")
        request = query["query"]
        for name, (det, _) in detectors.items():
            for rep in range(repeats):
                if rep > 0 and name == "llm" and hasattr(det, "_cache"):
                    det._cache.clear()
                t0 = time.perf_counter()
                intent = det.detect(request)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                records.append(_record_for(
                    query, name, rep, intent, latency_ms, workload_label,
                ))
    return records


# --- export (for external API clients) ------------------------------------


def export_prompts(queries: list[dict], out_dir: Path, workload_label: str) -> None:
    """Dump corpus.jsonl + prompts.jsonl + intent_schema.json.

    Uses the SAME templates LLMIntentDetector uses internally, so external API
    outputs are directly comparable to local LLM detector outputs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    known_task_types = sorted(list(_DEFAULT_TASK_TYPE_VOCAB.keys()) + [_FALLBACK_TASK_TYPE])
    domain_tag_list = sorted(_DEFAULT_DOMAIN_VOCAB.keys())
    system_prompt = _LLM_SYSTEM_PROMPT.format(
        task_types=known_task_types, domain_tags=domain_tag_list,
    )

    corpus_path = out_dir / "corpus.jsonl"
    prompts_path = out_dir / "prompts.jsonl"
    schema_path = out_dir / "intent_schema.json"

    with corpus_path.open("w") as cf, prompts_path.open("w") as pf:
        for q in queries:
            cf.write(json.dumps({
                "query_id": q["id"],
                "workload": workload_label,
                "domain": q.get("domain", ""),
                "complexity_label": q.get("complexity", ""),
                "request": q["query"],
            }) + "\n")
            pf.write(json.dumps({
                "query_id": q["id"],
                "system_prompt": system_prompt,
                "user_prompt": _LLM_USER_TEMPLATE.format(request=q["query"]),
            }) + "\n")

    schema_path.write_text(json.dumps(_LLM_JSON_SCHEMA, indent=2))
    print(f"  wrote {corpus_path}")
    print(f"  wrote {prompts_path}")
    print(f"  wrote {schema_path}")


# --- ingest (external API results) ----------------------------------------


_REQUIRED_INGEST_KEYS = {"query_id", "task_type", "complexity", "decomposability"}


def ingest_external(
    path: Path, detector_name: str, queries_by_id: dict[str, dict], workload_label: str,
) -> list[RunRecord]:
    """Read a JSONL produced by an external API client and convert to RunRecords.

    Each row must have query_id, task_type, complexity, decomposability.
    Optional: domain_tags (list), constraints (dict), latency_ms (number).
    Rows referring to query_ids not in the active corpus are skipped with a warning.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    records: list[RunRecord] = []
    skipped = 0
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = _REQUIRED_INGEST_KEYS - row.keys()
        if missing:
            raise ValueError(f"{path}:{line_no} missing required keys {sorted(missing)}")
        qid = row["query_id"]
        if qid not in queries_by_id:
            skipped += 1
            continue
        try:
            intent = Intent(
                task_type=str(row["task_type"]),
                complexity=float(row["complexity"]),
                decomposability=float(row["decomposability"]),
                domain_tags=list(row.get("domain_tags", [])),
                constraints=dict(row.get("constraints", {})),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{line_no} invalid Intent: {exc}") from exc
        latency = row.get("latency_ms")
        records.append(_record_for(
            queries_by_id[qid], detector_name, 0, intent,
            float(latency) if latency is not None else None,
            workload_label,
        ))
    if skipped:
        _log.warning(
            "Ingested %s: skipped %d rows whose query_ids weren't in this corpus",
            path, skipped,
        )
    return records


# --- aggregation ----------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = max(0, min(len(sorted_values) - 1, int(round(p * (len(sorted_values) - 1)))))
    return sorted_values[k]


def _latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"n": 0}
    s = sorted(latencies_ms)
    return {
        "n": len(s),
        "mean_ms": statistics.fmean(s),
        "p50_ms": _percentile(s, 0.50),
        "p95_ms": _percentile(s, 0.95),
        "p99_ms": _percentile(s, 0.99),
        "min_ms": s[0],
        "max_ms": s[-1],
    }


def _agreement_pair(
    a_records: list[RunRecord], b_records: list[RunRecord],
) -> dict[str, float]:
    """Pairwise metrics, restricted to query_ids present in both at rep=0."""
    a_idx = {r.query_id: r for r in a_records if r.repetition == 0}
    b_idx = {r.query_id: r for r in b_records if r.repetition == 0}
    common = sorted(set(a_idx) & set(b_idx))
    if not common:
        return {}

    tt_match = sum(
        1 for q in common if a_idx[q].task_type == b_idx[q].task_type
    ) / len(common)

    def _jaccard(xs: list[str], ys: list[str]) -> float:
        sx, sy = set(xs), set(ys)
        if not sx and not sy:
            return 1.0
        return len(sx & sy) / len(sx | sy)

    dom_jaccard = statistics.fmean(
        _jaccard(a_idx[q].domain_tags, b_idx[q].domain_tags) for q in common
    )
    cmplx_bucket = sum(
        1 for q in common
        if bucket(a_idx[q].complexity) == bucket(b_idx[q].complexity)
    ) / len(common)
    decmp_bucket = sum(
        1 for q in common
        if bucket(a_idx[q].decomposability) == bucket(b_idx[q].decomposability)
    ) / len(common)
    cmplx_mae = statistics.fmean(
        abs(a_idx[q].complexity - b_idx[q].complexity) for q in common
    )
    decmp_mae = statistics.fmean(
        abs(a_idx[q].decomposability - b_idx[q].decomposability) for q in common
    )

    return {
        "n": len(common),
        "task_type_match": tt_match,
        "domain_jaccard_mean": dom_jaccard,
        "complexity_bucket_match": cmplx_bucket,
        "decomposability_bucket_match": decmp_bucket,
        "complexity_mae": cmplx_mae,
        "decomposability_mae": decmp_mae,
    }


def summarize(
    records: list[RunRecord], init_times: dict[str, float],
) -> dict[str, Any]:
    by_detector: dict[str, list[RunRecord]] = {}
    for r in records:
        by_detector.setdefault(r.detector, []).append(r)

    per_detector: dict[str, dict[str, Any]] = {}
    for name, recs in by_detector.items():
        latencies = [r.latency_ms for r in recs if r.latency_ms is not None]
        stats = _latency_stats(latencies)
        if name in init_times:
            stats["init_s"] = init_times[name]
        if name == "llm":
            llm_cold = [r for r in recs if r.repetition == 0]
            if llm_cold:
                fb = sum(
                    1 for r in llm_cold
                    if r.constraints.get("_confidence_llm") == 0.0
                )
                stats["fallback_rate"] = fb / len(llm_cold)
        per_detector[name] = stats

    names = sorted(by_detector.keys())
    agreement = {
        f"{a}_vs_{b}": _agreement_pair(by_detector[a], by_detector[b])
        for a, b in itertools.combinations(names, 2)
    }

    return {
        "n_queries": len({r.query_id for r in records}),
        "n_detectors": len(by_detector),
        "per_detector": per_detector,
        "agreement": agreement,
    }


# --- manifest -------------------------------------------------------------


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
            cwd=str(_BENCH_DIR),
        )
        return out.stdout.strip() or None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _lib_version(name: str) -> str | None:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", None)
    except ImportError:
        return None


def build_manifest(
    args: argparse.Namespace,
    per_detector_kwargs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        # Resolved kwargs that were actually forwarded to make_intent_detector.
        # Captures the merge of (CLI args + script-supplied defaults), so a future
        # reader can reproduce the run without re-reading argparse defaults.
        "detector_config": per_detector_kwargs or {},
        "git_sha": _git_sha(),
        "host": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "hostname": platform.node(),
        },
        "library_versions": {
            "pythia": _lib_version("pythia"),
            "spacy": _lib_version("spacy"),
            "sentence_transformers": _lib_version("sentence_transformers"),
            "torch": _lib_version("torch"),
        },
    }


# --- output ---------------------------------------------------------------


def write_outputs(
    out_dir: Path, records: list[RunRecord], summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / "runs.jsonl"
    summary_path = out_dir / "summary.json"
    manifest_path = out_dir / "manifest.json"

    with runs_path.open("w") as f:
        for r in records:
            f.write(json.dumps(asdict(r)) + "\n")
    summary_path.write_text(json.dumps(summary, indent=2))
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"  wrote {runs_path} ({len(records)} rows)")
    print(f"  wrote {summary_path}")
    print(f"  wrote {manifest_path}")


def print_summary(summary: dict[str, Any]) -> None:
    print()
    print(f"{'detector':<14} {'n':>5} {'init_s':>8} "
          f"{'p50_ms':>9} {'p95_ms':>9} {'p99_ms':>9} {'mean_ms':>9}")
    print("-" * 78)
    for name, stats in summary["per_detector"].items():
        if stats.get("n", 0) == 0:
            print(f"{name:<14} {'0':>5}  (no rows)")
            continue
        init = stats.get("init_s")
        init_s = f"{init:.3f}" if isinstance(init, (int, float)) else "-"
        line = (
            f"{name:<14} {stats['n']:>5} {init_s:>8} "
            f"{stats['p50_ms']:>8.2f} {stats['p95_ms']:>8.2f} "
            f"{stats['p99_ms']:>8.2f} {stats['mean_ms']:>8.2f}"
        )
        if "fallback_rate" in stats:
            line += f"  fallback={stats['fallback_rate']:.0%}"
        print(line)

    if summary["agreement"]:
        print()
        print(f"{'pair':<28} {'n':>5} {'tt_match':>10} {'dom_jacc':>9} "
              f"{'cmplx_bkt':>10} {'decmp_bkt':>10}")
        print("-" * 78)
        for pair, m in summary["agreement"].items():
            if not m:
                continue
            print(
                f"{pair:<28} {m['n']:>5} "
                f"{m['task_type_match']:>10.3f} "
                f"{m['domain_jaccard_mean']:>9.3f} "
                f"{m['complexity_bucket_match']:>10.3f} "
                f"{m['decomposability_bucket_match']:>10.3f}"
            )


# --- CLI ------------------------------------------------------------------


def parse_detectors(spec: str) -> list[str]:
    if not spec or spec.lower() == "none":
        return []
    names = [s.strip() for s in spec.split(",") if s.strip()]
    invalid = [n for n in names if n not in _LOCAL_DETECTORS]
    if invalid:
        raise SystemExit(
            f"Unknown detector(s): {invalid}; expected subset of {list(_LOCAL_DETECTORS)}"
        )
    return names


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="H1 intent classifier benchmark — real corpus, multi-detector.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--workload", default="mixed",
                   choices=["hpc_cg", "sdp", "rwa", "mixed"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--detectors", default=",".join(_LOCAL_DETECTORS),
                   help="Comma-separated subset of {rule,semantic,llm}. Use '' or 'none' to skip locals.")
    # --- LLM detector knobs ---
    p.add_argument("--llm-provider", default="ollama",
                   choices=["ollama", "lmstudio", "vllm"])
    p.add_argument("--llm-model", default=None,
                   help="Model name (default: LLMIntentDetector's qwen2.5:0.5b).")
    p.add_argument("--llm-base-url", default=None,
                   help="Override provider URL (e.g. http://gpu-host:11434 for remote Ollama).")
    p.add_argument("--llm-sla", type=float, default=None,
                   help="Override LLMIntentDetector sla_timeout AND request timeout (seconds). "
                        "Production default is 0.45s; raise to e.g. 30 for honest CPU measurement.")
    p.add_argument("--llm-num-predict", type=int, default=None,
                   help="Max tokens to generate (default: 128).")
    p.add_argument("--llm-temperature", type=float, default=None,
                   help="Sampling temperature (default: 0.0 = deterministic).")
    p.add_argument("--llm-cache-size", type=int, default=None,
                   help="LRU cache size (default: 512). Set to 1 to effectively disable.")

    # --- Semantic detector knobs ---
    p.add_argument("--semantic-model", default=None,
                   help="Sentence-transformer model (default: sentence-transformers/all-MiniLM-L6-v2).")
    p.add_argument("--semantic-domain-threshold", type=float, default=None,
                   help="Cosine-sim threshold for domain-tag inclusion (default: 0.35).")
    p.add_argument("--semantic-tau", type=float, default=None,
                   help="Softmax temperature for task_type classification (default: 0.15). "
                        "Lower = sharper argmax.")

    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-warmup", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--diagnose-llm", action="store_true",
                   help="Skip the benchmark; do one direct LLM call with a 30s timeout "
                        "and print the actual response or exception. Use to debug "
                        "fallback_rate=100% problems.")
    p.add_argument("--no-llm-preflight", action="store_true",
                   help="Skip the automatic LLM preflight check before the timed loop.")

    p.add_argument("--export-prompts", action="store_true",
                   help="Also write corpus.jsonl, prompts.jsonl, intent_schema.json into the output dir.")
    p.add_argument("--export-only", action="store_true",
                   help="Implies --export-prompts; skip running detectors entirely.")
    p.add_argument("--ingest", action="append", default=[], metavar="PATH",
                   help="(repeatable) external JSONL to merge in. Pair each with --as-detector.")
    p.add_argument("--as-detector", action="append", default=[], metavar="NAME",
                   help="(repeatable) detector name for the matching --ingest path.")

    default_dir = Path("motivation_bench/tests/results/h1") / dt.datetime.now(
        dt.timezone.utc
    ).strftime("%Y-%m-%dT%H-%M-%SZ")
    p.add_argument("--output-dir", type=Path, default=default_dir)

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Silence noisy third-party loggers — they emit INFO for every cache lookup
    # / device assignment, which buries the benchmark's own output.
    for noisy in ("httpx", "sentence_transformers", "huggingface_hub", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    args = parse_args(argv)

    if len(args.ingest) != len(args.as_detector):
        raise SystemExit(
            f"--ingest and --as-detector must be paired; got "
            f"{len(args.ingest)} ingests vs {len(args.as_detector)} detector names"
        )

    local_names: list[str] = [] if args.export_only else parse_detectors(args.detectors)

    queries = load_corpus(args.workload, args.limit, args.seed)
    print(f"Loaded {len(queries)} queries from workload={args.workload!r}")

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.export_prompts or args.export_only:
        export_prompts(queries, out_dir, args.workload)
        if args.export_only:
            (out_dir / "manifest.json").write_text(
                json.dumps(build_manifest(args, {}), indent=2)
            )
            print(f"Export-only complete. Output: {out_dir}")
            return 0

    llm_kwargs: dict[str, Any] = {"provider": args.llm_provider}
    if args.llm_model:
        llm_kwargs["model"] = args.llm_model
    if args.llm_base_url:
        llm_kwargs["base_url"] = args.llm_base_url
    if args.llm_sla is not None:
        llm_kwargs["sla_timeout"] = args.llm_sla
        llm_kwargs["timeout"] = args.llm_sla
    if args.llm_num_predict is not None:
        llm_kwargs["num_predict"] = args.llm_num_predict
    if args.llm_temperature is not None:
        llm_kwargs["temperature"] = args.llm_temperature
    if args.llm_cache_size is not None:
        llm_kwargs["cache_size"] = args.llm_cache_size

    semantic_kwargs: dict[str, Any] = {}
    if args.semantic_model:
        semantic_kwargs["model_name"] = args.semantic_model
    if args.semantic_domain_threshold is not None:
        semantic_kwargs["domain_sim_threshold"] = args.semantic_domain_threshold
    if args.semantic_tau is not None:
        semantic_kwargs["task_type_softmax_tau"] = args.semantic_tau

    per_detector_kwargs = {"llm": llm_kwargs, "semantic": semantic_kwargs}

    # --- diagnostic shortcut: build LLM only, run preflight, exit ---
    if args.diagnose_llm:
        diag = build_detectors(["llm"], per_detector_kwargs)
        if "llm" not in diag:
            print("LLM detector failed to construct — see warning above.", file=sys.stderr)
            return 3
        det = diag["llm"][0]
        sample = queries[0]["query"]
        print(f"Preflight call to {getattr(det, '_provider', '?')} "
              f"@ {getattr(det, '_base_url', '?')} model={getattr(det, '_model', '?')} ...")
        ok, msg = llm_preflight(det, sample)
        if ok:
            print(f"  ✓ {msg}")
            return 0
        print(f"  ✗ {msg}", file=sys.stderr)
        print("\nLikely fixes:", file=sys.stderr)
        print("  - Connection refused → start Ollama: `ollama serve &`", file=sys.stderr)
        print("  - 404 / model not found → `ollama pull <model>`", file=sys.stderr)
        print("  - Timeout → CPU may be too slow; try a larger --llm-sla", file=sys.stderr)
        print("  - Wrong URL → pass --llm-base-url http://host:port", file=sys.stderr)
        return 4

    detectors = build_detectors(local_names, per_detector_kwargs)
    init_times = {name: t for name, (_, t) in detectors.items()}

    # Surface LLM connectivity early so fallback_rate=100% isn't a silent surprise.
    if "llm" in detectors and not args.no_llm_preflight:
        ok, msg = llm_preflight(detectors["llm"][0], queries[0]["query"])
        if ok:
            _log.info("LLM preflight: %s", msg)
        else:
            _log.warning(
                "LLM preflight FAILED (%s) — every llm row will fall back to rule-based. "
                "Re-run with `--diagnose-llm` for fix suggestions, or skip with --no-llm-preflight.",
                msg,
            )

    if detectors and not args.no_warmup:
        warmup(detectors)

    records: list[RunRecord] = []
    if detectors:
        records.extend(run_local(
            detectors, queries, args.workload, args.repeats, progress=not args.quiet,
        ))

    queries_by_id = {q["id"]: q for q in queries}
    for path_str, name in zip(args.ingest, args.as_detector):
        ingested = ingest_external(Path(path_str), name, queries_by_id, args.workload)
        print(f"Ingested {len(ingested)} rows from {path_str} as detector {name!r}")
        records.extend(ingested)

    if not records:
        print(
            "No records produced — nothing to write. "
            "(Did you pass --detectors none with no --ingest?)",
            file=sys.stderr,
        )
        return 2

    summary = summarize(records, init_times)
    manifest = build_manifest(args, per_detector_kwargs)
    write_outputs(out_dir, records, summary, manifest)

    if not args.quiet:
        print_summary(summary)

    print(f"\nDone. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
