"""Intent Detector — classifies user requests into structured Intents (§3.1, §5.1).

Deliberately shallow: fast classification, not planning.
Must be sub-second, 10x faster than the Solver (§5.1).

Architecture:
- IntentDetector Protocol: extensibility point for future LLM-based detector
- RuleBasedIntentDetector: weighted keyword scoring with configurable vocabularies

Traceability:
- §3.1: Intent classification in the dispatch pipeline
- §5.1: Sub-second latency requirement
- §5.2: Domain tag extraction for scientific data formats
- §4.1: Decomposability feeds Learner state vector i_t
- §6.1: Workload categories (hpc_code_gen, scientific_data_pipeline, research_writing)

Questions to think about:
  - Should the "general" fallback path be characterized in §6? Showing that the system degrades gracefully (no speculation, but  
  no errors) is a publishable property.
  - Adaptive vocabulary expansion via the Learner observing what requests fall to "general" and 
  which domain tags co-occur — Discussed in §7                                                                    
  - The vocabularies should be documented as evaluation-specific configurations, not claimed as general-purpose. A deployment
  would need domain-specific vocabulary tuning. 
"""

from __future__ import annotations

import concurrent.futures
import functools
import json
import logging
import os
import re
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pythia.contracts import Intent

_log = logging.getLogger(__name__)


# --- Default Vocabularies ---

# Vocab entries follow the Phase 2 conventions (see _compile_vocab_regex):
#   - plain string "mpi"       → whole-word, case-insensitive
#   - trailing "*"  "profil*"  → stem: matches "profile", "profiling", ...
#   - ALL-CAPS     "FITS"      → whole-word, case-sensitive (acronym)
#   - tuple       ("high", "performance") → multi-word phrase
_DEFAULT_TASK_TYPE_VOCAB: dict[str, list[VocabEntry]] = {
    "hpc_code_gen": [
        "mpi", "openmp", "slurm*", "parallel*", "cuda", "gpu", "hpc",
        "fortran", "compil*", "profil*", "optimiz*", "performance",
        "supercomputer*", "cluster*", "mpirun", "rank*", "nvidia",
        "opencl", "thread*", "vectoriz*", "simd", "fft",
    ],
    "scientific_data_pipeline": [
        "hdf5", "netcdf", "FITS", "zarr", "ROOT", "pipeline*", "data",
        "dataset*", "convert*", "ingest*", "etl", "h5py", "xarray",
        "parquet", "csv", "process*", "transform*", "extract*",
        "analyz*", "wrangl*", "clean*", "statistic*", "domain*",
    ],
    "data_pipeline": [
        "pipeline*", "data", "dataset*", "analyz*", "process*", "source*",
        "wrangl*", "clean*", "statistic*", "comput*", "load*",
        "domain*", "scientific*", "environmental", "biomedical",
        "wildfire*", "astronomy", "legal", "archeology",
    ],
    "research_workflow": [
        "replicat*", "reproduc*", "paper*", "research*", "experiment*",
        "workflow*", "subtask*", "phase*", "implement*", "train*",
        "evaluat*", "model*", "benchmark*", "result*",
    ],
    "research_writing": [
        "paper*", "draft*", "section*", "abstract*", "review*", "literature*",
        "citation*", "manuscript*", "latex", "writ*", "edit*", "revision*",
        "conference*", "journal*", "submission*",
    ],
}

_DEFAULT_DOMAIN_VOCAB: dict[str, list[VocabEntry]] = {
    "hpc": [
        "hpc", "supercomputer*", "cluster*", "slurm*", "pbs", "parallel*",
        ("high", "performance"),  # matches "high-performance" and "high performance"
    ],
    "mpi": ["mpi", "mpirun", "rank*", "scatter*", "gather*"],
    "gpu": ["cuda", "gpu", "nvidia", "opencl"],
    "hdf5": ["hdf5", "h5py", "hdf"],
    "netcdf": ["netcdf", "xarray"],
    "fits": ["FITS", "astropy"],
    "zarr": ["zarr"],
    "root": ["ROOT"],
    "fortran": ["fortran", "f90", "f77"],
    "openmp": ["openmp", "omp"],
    "slurm": ["slurm", "sbatch", "srun"],
    "parquet": ["parquet", "arrow"],
    "docker": ["docker", "container*", "singularity"],
    "python": ["python", "numpy", "scipy", "pandas"],
    "data": ["data", "dataset*", "pipeline*", "csv", "json", "database*"],
    "research": ["research*", "paper*", "experiment*", "replicat*", "reproduc*"],
    "ml": ["model*", "train*", "neural*", "deep*", "learning", "inference*"],
    # "weather" intentionally omitted: too generic ("what's the weather") to
    # signal environmental-science context without hurting precision.
    "environmental_science": ["wildfire*", "climate", "environmental", "noaa"],
    "astronomy": ["astronomy", "stellar", "galaxy", "telescope*"],
    "biomedical": ["biomedical", "protein*", "gene*", "clinical"],
    "legal_analytics": ["legal", "court*", "contract*", "regulation*"],
    "archeology": ["archeology", "excavat*", "artifact*"],
}

_SUBTASK_INDICATORS = re.compile(
    r"\b(?:first|then|next|also|after that|finally|followed by|additionally|subsequently)\b"
    r"|(?:^|\s)\d+\.",
    re.IGNORECASE,
)

# Action verbs that imply distinct task steps in scientific computing.
# Each match suggests a separate dispatchable unit of work.
_ACTION_VERBS = re.compile(
    r"\b(?:writ[e]|build|creat[e]|implement|develop|design"
    r"|convert|transform|ingest|extract|export|load|import|process|pars[e]"
    r"|analyz[e]|visualiz[e]|plot|generat[e]|comput[e]|calculat[e]|estimat[e]"
    r"|train|evaluat[e]|predict|classif[y]|cluster"
    r"|deploy|submit|run|execut[e]|launch|compil[e]|install"
    r"|profil[e]|benchmark|optimiz[e]|debug|test|validat[e]|verif[y]"
    r"|identif[y]|assess|document|save|download|fetch"
    r"|parallelize|refactor|rewrit[e]|fix|migrat[e])\b",
    re.IGNORECASE,
)

# Sentence boundaries — periods, semicolons, explicit list items.
_SENTENCE_BOUNDARIES = re.compile(
    r"[.;!](?:\s|$)"  # punctuation followed by space or end
    r"|(?:^|\n)\s*[-•*]"  # bullet points
    r"|(?:^|\n)\s*\d+[.)]\s",  # numbered lists
    re.MULTILINE,
)

_TOKENIZE_PATTERN = re.compile(r"[a-z0-9]+")

# Fallback task type when no vocabulary matches.
_FALLBACK_TASK_TYPE = "general"


@dataclass(frozen=True)
class _RequestSignals:
    """Pre-computed regex signals for a single request, shared across methods."""

    verb_matches: frozenset[str]
    indicator_count: int
    sentence_count: int


def _compute_signals(request: str) -> _RequestSignals:
    """Run all shared regex scans once for a given request."""
    return _RequestSignals(
        verb_matches=frozenset(
            m.group().lower() for m in _ACTION_VERBS.finditer(request)
        ),
        indicator_count=len(_SUBTASK_INDICATORS.findall(request)),
        sentence_count=len(_SENTENCE_BOUNDARIES.findall(request)) + 1,
    )


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric boundaries."""
    return _TOKENIZE_PATTERN.findall(text.lower())


# --- Protocol ---


@runtime_checkable
class IntentDetector(Protocol):
    """Protocol for intent classification (§3.1)."""

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent: ...


# --- Phase 2 helpers: compiled-regex vocabulary with negation windowing ---
#
# Five fixes land together here (plan §B):
#   B.1 — compile vocab into \b-bounded regex; one finditer pass per category.
#   B.2 — multi-word phrases via tuple entries (tolerates hyphen / whitespace).
#   B.3 — deterministic tie-break: dict-insertion order wins (first vocab-entry
#         wins ties, matching the current accidental behavior where
#         scientific_data_pipeline beats data_pipeline on shared keywords).
#   B.4 — emit (best - second) / max(best, 1) as Intent.constraints["_confidence_margin"].
#   B.5 — suppress a domain tag hit when a negation word appears within ~40
#         characters upstream in the raw request text.

VocabEntry = str | tuple[str, ...]


# Negation markers scanned within a small window upstream of a domain-keyword
# hit (plan §B.5). Operates on raw text rather than tokenized words so we can
# detect "don't" (contraction) the same as "do not" — the tokenizer strips
# apostrophes, which makes token-level detection lossy.
_NEGATION_PATTERN = re.compile(
    r"\b(?:"
    r"don'?t|does\s*n'?t|did\s*n'?t|do\s+not|does\s+not|did\s+not"
    r"|cannot|can'?t|won'?t|shouldn'?t|wouldn'?t"
    r"|not|without|avoid(?:s|ed|ing)?|except|excluding"
    r"|no|never|neither|nor"
    r")\b",
    re.IGNORECASE,
)


def _compile_vocab_regex(
    vocab: dict[str, list[VocabEntry]]
) -> dict[str, re.Pattern[str]]:
    """B.1 + B.2: compile each category's entries into one \b-bounded regex.

    Returns ``{category_name: compiled_pattern}``. Callers use
    ``pattern.search(text)`` (hit test) or ``pattern.finditer(text)`` (for
    negation-window checks).

    Vocab entry conventions:
      - ``"mpi"``     → whole-word, case-insensitive match (``\\bmpi\\b``).
      - ``"profil*"`` → stem match: keyword followed by any word-chars up to
        the next word boundary (``\\bprofil\\w*\\b``). Matches ``profile``,
        ``profiled``, ``profiling``.
      - ``"FITS"``    → uppercase-only: same shape as ``"mpi"`` but compiled
        with ``(?-i:...)`` so the lowercase verb ``"fits"`` doesn't trigger a
        tag for the FITS astronomical format. Detection rule: entry equals its
        own ``.upper()`` and contains at least one alphabetic character.
      - ``("high", "performance")`` → multi-word phrase, tolerates one or more
        hyphen/whitespace chars between tokens (``\\bhigh[-\\s]+performance\\b``).
    """
    compiled: dict[str, re.Pattern[str]] = {}
    for category, entries in vocab.items():
        parts: list[str] = []
        for entry in entries:
            if isinstance(entry, tuple):
                joined = r"[-\s]+".join(re.escape(w) for w in entry)
                parts.append(r"\b" + joined + r"\b")
            elif isinstance(entry, str):
                is_stem = entry.endswith("*")
                bare = entry[:-1] if is_stem else entry
                if not bare:
                    raise ValueError(f"Empty vocab entry in {category!r}")
                is_acronym = (
                    bare == bare.upper()
                    and any(c.isalpha() for c in bare)
                )
                if is_stem:
                    pat = r"\b" + re.escape(bare) + r"\w*\b"
                else:
                    pat = r"\b" + re.escape(bare) + r"\b"
                if is_acronym:
                    pat = "(?-i:" + pat + ")"
                parts.append(pat)
            else:
                raise TypeError(
                    f"Unsupported vocab entry type in {category!r}: "
                    f"{type(entry).__name__}"
                )
        if parts:
            compiled[category] = re.compile("|".join(parts), re.IGNORECASE)
    return compiled


def _in_negation_window(text: str, match_start: int, window_chars: int = 40) -> bool:
    """B.5: True if a negation word appears within ``window_chars`` chars
    upstream of position ``match_start`` in the raw request text.

    40 characters roughly corresponds to 6–8 tokens in English — wide enough
    to catch "do not use any MPI" / "implement this without CUDA support",
    narrow enough to not reach over a clause boundary into a different
    proposition.
    """
    prior = text[max(0, match_start - window_chars):match_start]
    return bool(_NEGATION_PATTERN.search(prior))


# --- Rule-Based Implementation ---


class RuleBasedIntentDetector:
    """Weighted keyword scoring classifier (§5.1).

    Configurable vocabularies for task type classification and domain
    tag extraction. Pure Python, no external dependencies, sub-millisecond.

    Phase 2 changes (plan §B):
      - Vocab entries are ``\\b``-anchored via ``_compile_vocab_regex``.
      - Tuple entries enable multi-word phrases.
      - Tie-break on task-type score uses dict insertion order (documented).
      - ``Intent.constraints["_confidence_margin"]`` reports the best/second
        gap per request.
      - Domain-tag matches inside a negation window are suppressed.
    """

    def __init__(
        self,
        task_type_vocab: dict[str, list[VocabEntry]] | None = None,
        domain_vocab: dict[str, list[VocabEntry]] | None = None,
    ) -> None:
        self._task_type_vocab = task_type_vocab or _DEFAULT_TASK_TYPE_VOCAB
        self._domain_vocab = domain_vocab or _DEFAULT_DOMAIN_VOCAB
        # Pre-compile per-category union regexes once (B.1 + B.2).
        self._compiled_task = _compile_vocab_regex(self._task_type_vocab)
        self._compiled_domain = _compile_vocab_regex(self._domain_vocab)
        # All domain + task-type patterns flattened for technical-density scoring.
        self._tech_patterns: tuple[re.Pattern[str], ...] = tuple(
            p for p in (*self._compiled_task.values(), *self._compiled_domain.values())
        )

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify a user request into a structured Intent."""
        tokens = _tokenize(request)
        signals = _compute_signals(request)

        task_type, margin = self._classify_task_type_with_margin(request)
        constraints = self._extract_constraints(request)
        constraints["_confidence_margin"] = margin  # B.4

        return Intent(
            task_type=task_type,
            complexity=self._estimate_complexity(tokens, request, signals),
            domain_tags=self._extract_domain_tags(request),
            decomposability=self._score_decomposability(signals),
            constraints=constraints,
        )

    def _classify_task_type(self, request: str) -> str:
        """Return the best-scoring task type (§3.1, §6.1).

        Thin wrapper over :meth:`_classify_task_type_with_margin` — kept
        separate so callers that don't need the margin stay readable.
        """
        return self._classify_task_type_with_margin(request)[0]

    def _classify_task_type_with_margin(self, request: str) -> tuple[str, float]:
        """Best task_type + confidence margin against the raw request.

        Margin = ``(best_score - second_score) / max(best_score, 1)`` — 1.0
        when the winner is uncontested, 0.0 when it ties with the runner-up
        or no category matches. Tie-break on ``best_score`` is dict insertion
        order: the first task type to reach the top score keeps it.
        """
        best_type = _FALLBACK_TASK_TYPE
        best_score = 0
        second_score = 0

        for task_type, pattern in self._compiled_task.items():
            # Count distinct matches (len of findall) — more matches = stronger signal.
            score = len(pattern.findall(request))
            if score > best_score:
                second_score = best_score
                best_score = score
                best_type = task_type
            elif score > second_score:
                second_score = score

        if best_score == 0:
            return (_FALLBACK_TASK_TYPE, 0.0)
        margin = (best_score - second_score) / max(best_score, 1)
        return (best_type, margin)

    def _estimate_complexity(
        self, tokens: list[str], request: str, signals: _RequestSignals,
    ) -> float:
        """Five-signal weighted heuristic, normalized to [0,1] (§3.1).

        Signals:
        - Action verb count (0.30): distinct verbs imply distinct skills/tools needed
        - Technical density (0.25): ratio of domain-vocab matches to word count
        - Sentence count    (0.20): multiple sentences often mean multiple steps
        - Sequential markers (0.15): explicit "first/then/next" enumeration
        - Length            (0.10): longer requests tend to be more complex
        """
        word_count = len(tokens)

        verb_signal = min(len(signals.verb_matches) / 4.0, 1.0)

        if word_count == 0:
            tech_signal = 0.0
        else:
            # Total keyword hits across all task_type + domain patterns.
            tech_count = sum(len(p.findall(request)) for p in self._tech_patterns)
            tech_signal = min(tech_count / word_count, 1.0)

        sentence_signal = min(signals.sentence_count / 4.0, 1.0)
        sequential_signal = min(signals.indicator_count / 4.0, 1.0)
        length_signal = min(word_count / 80.0, 1.0)

        return (
            0.30 * verb_signal
            + 0.25 * tech_signal
            + 0.20 * sentence_signal
            + 0.15 * sequential_signal
            + 0.10 * length_signal
        )

    def _extract_domain_tags(self, request: str) -> list[str]:
        """Match raw request against domain vocabulary with negation suppression.

        A tag is included iff at least one non-negated match exists. A match
        at position ``m`` is negated when ``_in_negation_window(request, m)``
        finds a negation word within the preceding ~40 characters (B.5).
        """
        tags: list[str] = []
        for tag, pattern in self._compiled_domain.items():
            for match in pattern.finditer(request):
                if not _in_negation_window(request, match.start()):
                    tags.append(tag)
                    break  # one good hit is enough; don't double-count
        return sorted(tags)

    def _score_decomposability(self, signals: _RequestSignals) -> float:
        """Structural analysis for decomposability (§3.1, §4.1).

        Three signals combined:
        - Action verb count: multiple distinct verbs → separable subtasks
        - Sequential markers: explicit "first/then/next" → ordered subtasks
        - Sentence boundaries: multiple sentences → distinct work units

        A request with 1 verb and 1 sentence scores ~0. A request with
        4+ verbs across 4+ sentences scores ~1.0.
        """
        verb_signal = min(max(len(signals.verb_matches) - 1, 0) / 3.0, 1.0)
        marker_signal = min(signals.indicator_count / 4.0, 1.0)
        sentence_signal = min(max(signals.sentence_count - 1, 0) / 3.0, 1.0)

        return 0.50 * verb_signal + 0.20 * marker_signal + 0.30 * sentence_signal

    def _extract_constraints(self, request: str) -> dict[str, object]:
        """Regex-based constraint extraction (§3.1).

        Detects model preference, token limits, budget constraints.
        """
        constraints: dict[str, object] = {}

        # Model preference
        model_match = re.search(
            r"\buse\s+(claude|gpt[- ]?4|gemini|llama|local\s+model)\b",
            request,
            re.IGNORECASE,
        )
        if model_match:
            constraints["model_preference"] = model_match.group(1).strip().lower()

        # Token limit
        token_match = re.search(
            r"\blimit\s+to\s+(\d+)\s+tokens?\b",
            request,
            re.IGNORECASE,
        )
        if token_match:
            constraints["token_limit"] = int(token_match.group(1))

        # Budget
        budget_match = re.search(
            r"\bunder\s+\$(\d+(?:\.\d+)?)\b",
            request,
            re.IGNORECASE,
        )
        if budget_match:
            constraints["budget"] = float(budget_match.group(1))

        return constraints


# --- spaCy-Enhanced Implementation ---


@functools.lru_cache(maxsize=1)
def _load_spacy():
    """Lazily load spaCy and the English model. Returns None if unavailable.

    Cached so the model is loaded once and shared across all instances.
    """
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        return None


class SpacyIntentDetector(RuleBasedIntentDetector):
    """Rule-based detector enhanced with spaCy dependency parsing for decomposability.

    Inherits all methods from RuleBasedIntentDetector. Only overrides
    _score_decomposability to use syntactic parse trees — identifying
    coordinated verbs (conj), purpose clauses (advcl/xcomp), and
    independent clauses (ROOT) that regex cannot detect.

    Falls back to regex-based decomposability if spaCy is not installed.

    Latency: ~5-10ms per request (spaCy parse) vs ~0ms (pure regex).
    """

    def __init__(
        self,
        task_type_vocab: dict[str, list[VocabEntry]] | None = None,
        domain_vocab: dict[str, list[VocabEntry]] | None = None,
    ) -> None:
        super().__init__(task_type_vocab=task_type_vocab, domain_vocab=domain_vocab)
        self._nlp = _load_spacy()
        if self._nlp is None:
            _log.warning(
                "spaCy or en_core_web_sm not available; "
                "SpacyIntentDetector will use regex-based decomposability"
            )

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify with spaCy-enhanced decomposability.

        Overrides detect() rather than _score_decomposability() because
        spaCy needs the raw request string, while the parent's refactored
        _score_decomposability() now takes pre-computed _RequestSignals.
        """
        tokens = _tokenize(request)
        signals = _compute_signals(request)

        task_type, margin = self._classify_task_type_with_margin(request)
        constraints = self._extract_constraints(request)
        constraints["_confidence_margin"] = margin  # B.4 (same contract as parent)

        return Intent(
            task_type=task_type,
            complexity=self._estimate_complexity(tokens, request, signals),
            domain_tags=self._extract_domain_tags(request),
            decomposability=self._spacy_decomposability(request, signals),
            constraints=constraints,
        )

    def _spacy_decomposability(self, request: str, signals: _RequestSignals) -> float:
        """Dependency-parse-based decomposability scoring.

        Uses spaCy's dependency parser to count separable verb phrases:
        - ROOT verbs: independent clause heads
        - conj verbs: coordinated verbs ("analyze and visualize")
        - advcl/xcomp/relcl verbs: purpose/relative clauses ("build X to convert Y")

        When spaCy's small model fails to detect verbs (common with
        domain-specific imperative sentences), falls back to the regex
        verb count from the parent class. The final score is the max
        of spaCy-based and regex-based signals.
        """
        if self._nlp is None:
            return super()._score_decomposability(signals)

        doc = self._nlp(request)

        roots = [t for t in doc if t.dep_ == "ROOT" and t.pos_ == "VERB"]
        conjs = [t for t in doc if t.dep_ == "conj" and t.pos_ == "VERB"]
        subclauses = [
            t for t in doc
            if t.dep_ in ("advcl", "xcomp", "relcl") and t.pos_ == "VERB"
        ]

        separable = len(roots) + len(conjs) + len(subclauses)
        spacy_signal = min(max(separable - 1, 0) / 3.0, 1.0)

        regex_score = super()._score_decomposability(signals)
        return max(spacy_signal, regex_score)


# --- LLM-Based Implementation (Phase 3) ---
#
# Design targets a 500ms p95 ceiling on CPU. The combination that gets us
# there (plan §C):
#   - qwen2.5:0.5b-instruct-q4_K_M default (~350MB, ~80-150 tok/s on CPU).
#   - Zero-shot prompt + provider JSON-schema mode (eliminates few-shot tokens
#     and <think>/fence cleanup).
#   - num_predict=128, temperature=0, top_p=1.0 (fully deterministic).
#   - Per-instance OrderedDict LRU cache (warm hits → microseconds).
#   - ThreadPoolExecutor timeout race at sla_timeout: LLM and rule-based
#     compute in parallel; whichever finishes first wins, subject to the SLA.
#   - provider kwarg dispatches to ollama | lmstudio | vllm with the right
#     JSON-schema flavor for each.


# JSON schema passed to the provider's structured-output mode. Once enforced,
# we don't need `_extract_json` to scrub <think> tags or ```json fences.
# The _extract_json helper is kept as a safety net in case a provider's
# JSON mode is incomplete (e.g. older Ollama builds).
_LLM_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string"},
        "complexity": {"type": "number", "minimum": 0, "maximum": 1},
        "domain_tags": {"type": "array", "items": {"type": "string"}},
        "decomposability": {"type": "number", "minimum": 0, "maximum": 1},
        "constraints": {"type": "object"},
    },
    "required": [
        "task_type", "complexity", "domain_tags", "decomposability",
    ],
}


# Zero-shot system prompt. Replaces the 4-exemplar few-shot block; schema
# enforcement + this description is enough to pin output shape for a 0.5B
# model, and halving input tokens visibly cuts prefill latency.
_LLM_SYSTEM_PROMPT = """\
You are an intent classifier for a scientific-computing agent orchestrator.

Classify the user request into a JSON object matching this schema:
- task_type: exactly one of {task_types}
- complexity: 0.0 (trivial, well-defined, obvious solution) ... 1.0 (deep
  specialist knowledge, open-ended, ambiguous, no standard solution).
- domain_tags: subset of {domain_tags}, empty list if none clearly apply.
- decomposability: 0.0 (atomic, cannot be meaningfully split) ... 1.0 (fully
  parallel independent subtasks).
- constraints: object with optional keys "model_preference" (str),
  "token_limit" (int), "budget" (float). Empty object if none mentioned.

Respond with ONLY the JSON object. No prose, no code fences, no <think> tags.\
"""


# /no_think disables Qwen3-family chain-of-thought reasoning tokens.
# Intent classification is pattern matching, not reasoning; thinking tokens
# waste latency without improving accuracy at this task.
_LLM_USER_TEMPLATE = "Request: {request}\n/no_think"


# Provider base-URL defaults. User can override via kwarg or per-provider
# env var at construction time (see LLMIntentDetector.__init__).
_PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama":   "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
    "vllm":     "http://localhost:8000",
}


# Shared thread pool for the timeout race (plan §C.6). Module-level so every
# detector instance doesn't spin up its own worker threads.
_LLM_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="intent-llm"
)


# Legacy few-shot exemplars preserved for A/B rollback if the zero-shot
# prompt proves insufficient on the benchmark. Not consumed by any code path.
_LEGACY_FEWSHOTS: list[tuple[str, dict]] = [
    (
        "Show me the variables in this NetCDF file",
        {
            "task_type": "scientific_data_pipeline", "complexity": 0.10,
            "domain_tags": ["netcdf"], "decomposability": 0.05,
            "constraints": {},
        },
    ),
    (
        "Draft the abstract and literature review section for my paper on "
        "distributed computing",
        {
            "task_type": "research_writing", "complexity": 0.45,
            "domain_tags": ["hpc"], "decomposability": 0.50,
            "constraints": {},
        },
    ),
    (
        "Train a graph convolutional network on the aquatic toxicity dataset "
        "to predict compound toxicity. Use the resulting model to compute "
        "and visualize the atomic contributions to molecular activity of the "
        "test compound. Save the figure as pred_results/aquatic_toxicity_qsar_vis.png.",
        {
            "task_type": "scientific_data_pipeline", "complexity": 0.85,
            "domain_tags": ["python"], "decomposability": 0.75,
            "constraints": {},
        },
    ),
    (
        "Use Claude to summarize the dataset, limit to 500 tokens, under $2",
        {
            "task_type": "scientific_data_pipeline", "complexity": 0.20,
            "domain_tags": [], "decomposability": 0.10,
            "constraints": {
                "model_preference": "claude", "token_limit": 500, "budget": 2.0
            },
        },
    ),
]


def _with_llm_confidence(intent: Intent, confidence: float) -> Intent:
    """Return a copy of ``intent`` with ``_confidence_llm`` added to constraints.

    Constructs a new Intent rather than mutating the input so cached results
    stay stable for other callers. Confidence values (plan §C.8):
      - 1.0: first parse of the LLM response succeeded cleanly.
      - 0.5: parse needed _extract_json to strip fences / tags.
      - 0.0: rule-based fallback was returned (timeout or exception).
    """
    new_constraints: dict[str, object] = dict(intent.constraints)
    new_constraints["_confidence_llm"] = float(confidence)
    return Intent(
        task_type=intent.task_type,
        complexity=intent.complexity,
        domain_tags=list(intent.domain_tags),
        decomposability=intent.decomposability,
        constraints=new_constraints,
    )


class LLMIntentDetector:
    """LLM-based intent classifier with 500ms SLA (§5.1, plan §C).

    Keeps the class name stable (no Grace subclass, no Ollama prefix) —
    the ``provider`` kwarg dispatches to the selected backend. The API
    shape matches ``IntentDetector`` exactly so it's a drop-in alongside
    ``RuleBasedIntentDetector`` and ``SemanticIntentDetector``.

    The timeout race guarantees bounded latency even under provider hang:
    an LLM stuck in TCP-connect or slow decode won't block beyond
    ``sla_timeout`` because the rule-based fallback has already completed.
    """

    def __init__(
        self,
        model: str = "qwen2.5:0.5b-instruct-q4_K_M",
        provider: str = "ollama",
        base_url: str | None = None,
        timeout: float = 0.45,
        sla_timeout: float = 0.45,
        cache_size: int = 512,
        num_predict: int = 128,
        temperature: float = 0.0,
        task_type_vocab: dict[str, list[VocabEntry]] | None = None,
        domain_vocab: dict[str, list[VocabEntry]] | None = None,
    ) -> None:
        if provider not in _PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unknown LLM provider {provider!r}. "
                f"Expected one of: {sorted(_PROVIDER_DEFAULTS)}"
            )
        self._provider = provider
        self._model = model
        self._base_url = (base_url or _PROVIDER_DEFAULTS[provider]).rstrip("/")
        # Hard-cap urllib's socket timeout at sla_timeout so a stuck connect
        # can't outlive the race. Reading the old 30s default is a trap.
        self._timeout = min(timeout, sla_timeout)
        self._sla_timeout = sla_timeout
        self._num_predict = num_predict
        self._temperature = temperature

        self._task_type_vocab = task_type_vocab or _DEFAULT_TASK_TYPE_VOCAB
        self._domain_vocab = domain_vocab or _DEFAULT_DOMAIN_VOCAB
        self._known_task_types = frozenset(
            list(self._task_type_vocab.keys()) + [_FALLBACK_TASK_TYPE]
        )
        self._domain_tag_list = sorted(self._domain_vocab.keys())
        self._fallback = RuleBasedIntentDetector(
            task_type_vocab=self._task_type_vocab,
            domain_vocab=self._domain_vocab,
        )

        # Pre-format the system prompt once per instance.
        self._system_prompt = _LLM_SYSTEM_PROMPT.format(
            task_types=sorted(self._known_task_types),
            domain_tags=self._domain_tag_list,
        )

        # Per-instance LRU cache. Keyed on request only — model / provider /
        # base_url are frozen at construction. Instances with different
        # configs have independent caches.
        self._cache: OrderedDict[str, Intent] = OrderedDict()
        self._cache_size = cache_size

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify a user request via LLM + timeout race + rule fallback."""
        cached = self._cache_get(request)
        if cached is not None:
            return cached

        # Submit the LLM call; compute the fallback synchronously. Both run
        # in parallel because submit() returns immediately.
        future = _LLM_EXECUTOR.submit(self._detect_llm_tracked, request)
        fallback_intent = self._fallback.detect(request, session_context)

        try:
            intent, parse_confidence = future.result(timeout=self._sla_timeout)
            intent = _with_llm_confidence(intent, parse_confidence)
        except concurrent.futures.TimeoutError:
            _log.debug(
                "LLM timeout (>%.2fs) for %s; using rule-based fallback",
                self._sla_timeout, self._provider,
            )
            intent = _with_llm_confidence(fallback_intent, 0.0)
        except Exception as exc:
            _log.debug(
                "LLM detect failed (%s) for %s; using rule-based fallback",
                exc, self._provider,
            )
            intent = _with_llm_confidence(fallback_intent, 0.0)

        self._cache_put(request, intent)
        return intent

    def _detect_llm_tracked(self, request: str) -> tuple[Intent, float]:
        """Call the provider and parse. Returns ``(intent, parse_confidence)``.

        Parse confidence distinguishes clean structured-output results (1.0)
        from ones that needed the _extract_json fallback (0.5). A downstream
        harness can aggregate these to gauge how reliable the provider's
        JSON-mode is in practice.
        """
        raw_text = self._call_provider(request)
        try:
            parsed = json.loads(raw_text.strip())
            return (self._parse_intent(parsed), 1.0)
        except json.JSONDecodeError:
            parsed = self._extract_json(raw_text)
            return (self._parse_intent(parsed), 0.5)

    def _call_provider(self, request: str) -> str:
        """Dispatch the chat call to the configured provider.

        Only URL shape, schema-field name, and a couple of option fields
        differ between providers. Returns the raw assistant-message content
        (should be a JSON string under structured-output mode).
        """
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": _LLM_USER_TEMPLATE.format(request=request)},
        ]

        if self._provider == "ollama":
            # think=False disables Qwen3-family thinking blocks at the API level
            # (Ollama ≥0.5). Belt-and-suspenders alongside the /no_think directive
            # in _LLM_USER_TEMPLATE — older Ollama builds ignore the field, newer
            # ones honor it and skip emitting <think>...</think> entirely.
            payload = {
                "model": self._model,
                "messages": messages,
                "stream": False,
                "think": False,
                "format": _LLM_JSON_SCHEMA,
                "options": {
                    "num_predict": self._num_predict,
                    "temperature": self._temperature,
                    "top_p": 1.0,
                },
            }
            body = self._http_post(f"{self._base_url}/api/chat", payload)
            return body["message"]["content"]

        if self._provider == "lmstudio":
            payload = {
                "model": self._model,
                "messages": messages,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "intent", "schema": _LLM_JSON_SCHEMA,
                    },
                },
                "max_tokens": self._num_predict,
                "temperature": self._temperature,
                "top_p": 1.0,
            }
            body = self._http_post(
                f"{self._base_url}/v1/chat/completions", payload
            )
            return body["choices"][0]["message"]["content"]

        if self._provider == "vllm":
            payload = {
                "model": self._model,
                "messages": messages,
                "stream": False,
                "max_tokens": self._num_predict,
                "temperature": self._temperature,
                "top_p": 1.0,
                "extra_body": {"guided_json": _LLM_JSON_SCHEMA},
            }
            body = self._http_post(
                f"{self._base_url}/v1/chat/completions", payload
            )
            return body["choices"][0]["message"]["content"]

        # Guarded by __init__ — defensive raise in case of later provider
        # extensions that forget to wire a branch here.
        raise ValueError(f"Unhandled provider: {self._provider!r}")

    def _http_post(self, url: str, payload: dict) -> dict:
        """POST JSON and return parsed JSON body. Uses ``self._timeout``."""
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def _parse_intent(self, data: dict) -> Intent:
        """Validate and convert raw LLM JSON output into an Intent."""
        task_type = str(data.get("task_type", _FALLBACK_TASK_TYPE))
        if task_type not in self._known_task_types:
            _log.warning(
                "LLM returned unknown task_type %r, using %r",
                task_type, _FALLBACK_TASK_TYPE,
            )
            task_type = _FALLBACK_TASK_TYPE

        complexity = self._clamp(float(data.get("complexity", 0.5)))
        decomposability = self._clamp(float(data.get("decomposability", 0.5)))

        raw_tags = data.get("domain_tags", [])
        if isinstance(raw_tags, list):
            domain_tags = sorted(
                t for t in raw_tags
                if isinstance(t, str) and t in self._domain_vocab
            )
        else:
            domain_tags = []

        raw_constraints = data.get("constraints", {})
        constraints: dict[str, object] = {}
        if isinstance(raw_constraints, dict):
            if "model_preference" in raw_constraints:
                constraints["model_preference"] = str(
                    raw_constraints["model_preference"]
                )
            if "token_limit" in raw_constraints:
                try:
                    constraints["token_limit"] = int(raw_constraints["token_limit"])
                except (ValueError, TypeError):
                    pass
            if "budget" in raw_constraints:
                try:
                    constraints["budget"] = float(raw_constraints["budget"])
                except (ValueError, TypeError):
                    pass

        return Intent(
            task_type=task_type,
            complexity=complexity,
            domain_tags=domain_tags,
            decomposability=decomposability,
            constraints=constraints,
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Safety-net extractor for providers with partial JSON-mode support.

        Under properly-configured structured output the LLM returns bare JSON
        and `json.loads` in `_detect_llm_tracked` succeeds directly. This
        helper handles the degraded path: <think>...</think> blocks, markdown
        code fences, or a JSON object embedded in surrounding prose.
        """
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL
        )
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    # --- LRU cache helpers ---

    def _cache_get(self, key: str) -> Intent | None:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_put(self, key: str, value: Intent) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)


# --- SemanticIntentDetector (Phase 4, plan §D) ---
#
# Zero-shot MasRouter-style classifier using sentence-transformers/all-MiniLM-L6-v2.
# No training — all 5 Intent fields come from cosine similarity against
# pre-computed anchor embeddings. Optional dep: install with `pythia[ml]`.
#
# Design: the encoder is a 22M-parameter model (~90 MB on disk). One forward
# pass per request runs in ~15-25ms on CPU. Anchor embeddings are computed
# once at init and cached across instances. Total p50 latency: ~20-30ms.

# Anchor phrases for complexity / decomposability. These effectively DEFINE
# what those scalars mean under the semantic detector — changing the wording
# changes the score distribution. Kept as module-level constants so Jie can
# tune without touching class code. Worth reviewing with Prof. Kougkas so
# §5.1 prose stays consistent (plan "Open questions" #1).
_COMPLEXITY_ANCHORS: dict[str, str] = {
    "low": "a simple, well-defined task with an obvious solution",
    "high": "a complex multi-step task requiring deep domain expertise",
}

_DECOMPOSABILITY_ANCHORS: dict[str, str] = {
    "low": "a single atomic operation",
    "high": "multiple independent subtasks that can run in parallel",
}

# One descriptive sentence per task_type. Used at init to pre-compute class
# embeddings; at inference we cosine-sim request vs each.
_TASK_TYPE_ANCHORS: dict[str, str] = {
    "hpc_code_gen": (
        "writing parallel MPI, OpenMP, or CUDA code for HPC clusters; "
        "compiling, profiling, or optimizing Fortran or C++ scientific applications"
    ),
    "scientific_data_pipeline": (
        "building a pipeline to convert, ingest, or analyze scientific "
        "data in HDF5, NetCDF, FITS, Zarr, or ROOT formats"
    ),
    "data_pipeline": (
        "a generic ETL or data-processing pipeline to clean, transform, "
        "or load tabular data"
    ),
    "research_workflow": (
        "reproducing a research experiment, training and evaluating a "
        "model, or running a scientific workflow"
    ),
    "research_writing": (
        "drafting, editing, or reviewing academic paper text such as "
        "abstracts, literature reviews, citations, or LaTeX manuscripts"
    ),
    _FALLBACK_TASK_TYPE: (
        "a general-purpose conversational request not specific to any "
        "scientific domain"
    ),
}

# One descriptive sentence per domain tag. Must cover every key in
# _DEFAULT_DOMAIN_VOCAB — init() warns if any are missing.
_DOMAIN_TAG_ANCHORS: dict[str, str] = {
    "hpc": "high-performance computing on a supercomputer, cluster, or HPC facility",
    "mpi": "distributed message-passing parallelism via the MPI library",
    "gpu": "GPU-accelerated computation using CUDA, OpenCL, or NVIDIA hardware",
    "hdf5": "reading or writing HDF5 hierarchical scientific data files",
    "netcdf": "climate or earth-science data stored in the NetCDF format",
    "fits": "astronomical imaging data stored in the FITS file format",
    "zarr": "chunked array storage in the Zarr format for large scientific datasets",
    "root": "high-energy physics event data in the CERN ROOT file format",
    "fortran": "scientific code written in Fortran — F77, F90, or modern Fortran",
    "openmp": "shared-memory parallelism via OpenMP pragmas or directives",
    "slurm": "job submission and batch scheduling on an HPC cluster with Slurm",
    "parquet": "columnar analytical data stored in the Apache Parquet format",
    "docker": "containerized workflow execution using Docker, Singularity, or similar",
    "python": (
        "Python scientific computing with NumPy, SciPy, pandas, "
        "or the standard scientific stack"
    ),
    "data": "generic data processing, ingestion, cleaning, or tabular analysis",
    "research": (
        "scientific research activities including paper writing, "
        "experiments, and reproducibility"
    ),
    "ml": "machine learning model training, neural network inference, or evaluation",
    "environmental_science": (
        "environmental science topics like climate modeling, wildfire "
        "simulation, or NOAA data analysis"
    ),
    "astronomy": (
        "astronomical observation and analysis of stars, galaxies, "
        "or telescope imaging"
    ),
    "biomedical": (
        "biomedical research including protein structures, gene analysis, "
        "or clinical data"
    ),
    "legal_analytics": (
        "legal analytics involving court records, contracts, "
        "regulations, or case law"
    ),
    "archeology": "archeological analysis of excavation sites and artifact catalogs",
}

# Similarity threshold for multi-label domain tagging (plan §D). Tunable on
# motivation_bench/ once the corpus is ready.
_DOMAIN_SIM_THRESHOLD: float = 0.35

# Softmax temperature for task_type classification. Lower = sharper argmax.
_TASK_TYPE_SOFTMAX_TAU: float = 0.15

# Default encoder model. MiniLM-L6-v2: 22M params, 384-d embeddings.
_DEFAULT_ENCODER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@functools.lru_cache(maxsize=1)
def _load_sentence_transformer(model_name: str = _DEFAULT_ENCODER_MODEL):
    """Lazily load the sentence-transformer model, cached across instances.

    Returns ``None`` when sentence-transformers or torch is not installed,
    or when the model cannot be fetched from the HuggingFace cache — caller
    then falls back to :class:`RuleBasedIntentDetector`.

    Mirrors the ``_load_spacy`` pattern so both optional-dep detectors
    behave identically under missing dependencies.
    """
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except (ImportError, OSError) as exc:
        _log.warning(
            "Cannot load sentence-transformer %r (%s); "
            "SemanticIntentDetector will use rule-based fallback",
            model_name, exc,
        )
        return None


class SemanticIntentDetector:
    """Zero-shot semantic intent detector (plan §D).

    Pre-computes anchor embeddings at ``__init__`` time:
      - 6 task_type anchors (5 vocab + ``general``)
      - 21 domain_tag anchors
      - 2 complexity anchors (low / high)
      - 2 decomposability anchors (low / high)

    At ``detect()`` time runs one encoder forward on the request, then:
      - task_type: cosine-sim vs each class anchor → softmax(τ=0.15) → argmax.
        Emits ``_confidence_task_type = max(softmax)``.
      - domain_tags: cosine-sim vs each tag anchor → threshold ≥ 0.35.
        Emits ``_confidence_domain_avg = mean(sim for selected tags)``.
      - complexity: ``sim_high / (sim_low + sim_high)`` clipped to [0, 1].
      - decomposability: same formula with its own anchor pair.
      - constraints: reuses ``RuleBasedIntentDetector._extract_constraints``.

    Fallback: on encoder load failure or any exception during inference,
    delegates to :class:`RuleBasedIntentDetector`.
    """

    def __init__(
        self,
        task_type_vocab: dict[str, list[VocabEntry]] | None = None,
        domain_vocab: dict[str, list[VocabEntry]] | None = None,
        task_type_anchors: dict[str, str] | None = None,
        domain_tag_anchors: dict[str, str] | None = None,
        model_name: str = _DEFAULT_ENCODER_MODEL,
        domain_sim_threshold: float = _DOMAIN_SIM_THRESHOLD,
        task_type_softmax_tau: float = _TASK_TYPE_SOFTMAX_TAU,
    ) -> None:
        self._task_type_vocab = task_type_vocab or _DEFAULT_TASK_TYPE_VOCAB
        self._domain_vocab = domain_vocab or _DEFAULT_DOMAIN_VOCAB
        self._fallback = RuleBasedIntentDetector(
            task_type_vocab=self._task_type_vocab,
            domain_vocab=self._domain_vocab,
        )
        self._domain_sim_threshold = domain_sim_threshold
        self._task_type_softmax_tau = task_type_softmax_tau

        self._model = _load_sentence_transformer(model_name)
        if self._model is None:
            # Degraded mode — detect() will route everything to the fallback.
            return

        # Build task-type anchor list, preserving vocab insertion order + general.
        anchors = task_type_anchors or _TASK_TYPE_ANCHORS
        known = list(self._task_type_vocab.keys()) + [_FALLBACK_TASK_TYPE]
        self._task_names: list[str] = [t for t in known if t in anchors]
        missing_tt = [t for t in known if t not in anchors]
        if missing_tt:
            _log.warning(
                "task_types missing semantic anchors: %s (will be unreachable)",
                missing_tt,
            )

        # Build domain-tag anchor list in vocab order.
        tag_anchors = domain_tag_anchors or _DOMAIN_TAG_ANCHORS
        self._tag_names: list[str] = [
            t for t in self._domain_vocab.keys() if t in tag_anchors
        ]
        missing_tags = [
            t for t in self._domain_vocab.keys() if t not in tag_anchors
        ]
        if missing_tags:
            _log.warning(
                "domain_tags missing semantic anchors: %s (will be unreachable)",
                missing_tags,
            )

        # Pre-compute all anchor embeddings. Normalized so dot product = cosine.
        self._task_embs = self._model.encode(
            [anchors[t] for t in self._task_names],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        self._tag_embs = self._model.encode(
            [tag_anchors[t] for t in self._tag_names],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        self._complexity_embs = self._model.encode(
            [_COMPLEXITY_ANCHORS["low"], _COMPLEXITY_ANCHORS["high"]],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        self._decomposability_embs = self._model.encode(
            [_DECOMPOSABILITY_ANCHORS["low"], _DECOMPOSABILITY_ANCHORS["high"]],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify via encoder + anchor similarity. Fall back on failure."""
        if self._model is None:
            return self._fallback.detect(request, session_context)

        try:
            import numpy as np

            req_emb = self._model.encode(
                request, normalize_embeddings=True, convert_to_numpy=True
            )

            # Task type — softmax over cosine similarities.
            task_sims = self._task_embs @ req_emb
            logits = task_sims / self._task_type_softmax_tau
            logits = logits - logits.max()  # numerical stability
            probs = np.exp(logits)
            probs = probs / probs.sum()
            best_idx = int(probs.argmax())
            task_type = self._task_names[best_idx]
            task_confidence = float(probs[best_idx])

            # Domain tags — threshold-gated multi-label over cosine similarities.
            tag_sims = self._tag_embs @ req_emb
            selected = np.where(tag_sims >= self._domain_sim_threshold)[0]
            domain_tags = sorted(self._tag_names[int(i)] for i in selected)
            if len(selected) > 0:
                domain_conf_avg = float(tag_sims[selected].mean())
            else:
                domain_conf_avg = 0.0

            # Complexity / decomposability via low/high anchor interpolation.
            complexity = self._score_interp(req_emb, self._complexity_embs)
            decomposability = self._score_interp(req_emb, self._decomposability_embs)

            # Constraints: reuse rule-based regex extraction, overlay confidence.
            constraints = self._fallback._extract_constraints(request)
            constraints["_confidence_task_type"] = task_confidence
            constraints["_confidence_domain_avg"] = domain_conf_avg

            return Intent(
                task_type=task_type,
                complexity=complexity,
                domain_tags=domain_tags,
                decomposability=decomposability,
                constraints=constraints,
            )
        except Exception as exc:
            _log.warning("Semantic detect failed (%s); using rule-based fallback", exc)
            return self._fallback.detect(request, session_context)

    @staticmethod
    def _score_interp(req_emb, anchor_embs) -> float:
        """Interpolate the request position between a (low, high) anchor pair.

        Returns ``sim_high / (sim_low + sim_high)``, clamped to [0, 1].
        Negative cosine similarities are clipped to 0 before the ratio so a
        request that's antipodal to both anchors doesn't flip sign.
        """
        sims = anchor_embs @ req_emb
        sim_low = max(0.0, float(sims[0]))
        sim_high = max(0.0, float(sims[1]))
        total = sim_low + sim_high
        if total <= 1e-9:
            return 0.5  # equidistant from both anchors → middle
        return max(0.0, min(1.0, sim_high / total))


# --- Factory (plan §E) ---


_VALID_DETECTOR_NAMES: frozenset[str] = frozenset({"rule", "semantic", "llm"})


def make_intent_detector(
    name: str | None = None, **kwargs: object
) -> IntentDetector:
    """Factory for the three user-facing detectors (plan §E).

    Resolution order for the detector name:
      1. Explicit ``name`` argument
      2. ``PYTHIA_INTENT_DETECTOR`` environment variable
      3. Default ``"rule"``

    Names:
      - ``"rule"``: one logical rule-based detector. Prefers
        :class:`SpacyIntentDetector` when spaCy + the English model are
        loadable; falls back to :class:`RuleBasedIntentDetector` otherwise.
        Users don't pick between the two — the factory picks the best
        available.
      - ``"semantic"``: :class:`SemanticIntentDetector` (zero-shot encoder).
        Requires ``pythia[ml]`` optional extras; raises ``ImportError`` when
        ``sentence-transformers`` / ``torch`` is missing.
      - ``"llm"``: :class:`LLMIntentDetector`. Provider is resolved from
        ``kwargs["provider"]``, then ``PYTHIA_LLM_PROVIDER``, then
        ``"ollama"``.

    Any other ``name`` raises :class:`ValueError`.
    """
    resolved = name or os.getenv("PYTHIA_INTENT_DETECTOR", "rule")
    if resolved not in _VALID_DETECTOR_NAMES:
        raise ValueError(
            f"Unknown intent detector {resolved!r}. "
            f"Expected one of: {sorted(_VALID_DETECTOR_NAMES)}."
        )

    if resolved == "rule":
        # spaCy's English model ships separately — OSError means the model
        # isn't installed even if the package imports cleanly. Either failure
        # mode drops us to the pure-regex detector.
        try:
            return SpacyIntentDetector(**kwargs)  # type: ignore[arg-type]
        except (ImportError, OSError):
            return RuleBasedIntentDetector(**kwargs)  # type: ignore[arg-type]

    if resolved == "semantic":
        # Import-lazy: the class body raises NotImplementedError today (Phase 4
        # scaffold). When implemented, it will itself check sentence-transformers
        # availability and either construct or raise ImportError.
        return SemanticIntentDetector(**kwargs)  # type: ignore[arg-type]

    # "llm" — extract provider from kwargs / env so LLMIntentDetector.__init__
    # doesn't get the kwarg twice.
    provider = kwargs.pop("provider", None) or os.getenv(
        "PYTHIA_LLM_PROVIDER", "ollama"
    )
    return LLMIntentDetector(provider=str(provider), **kwargs)  # type: ignore[arg-type]
