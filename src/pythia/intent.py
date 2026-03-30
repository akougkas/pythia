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

import functools
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pythia.contracts import Intent

_log = logging.getLogger(__name__)


# --- Default Vocabularies ---

_DEFAULT_TASK_TYPE_VOCAB: dict[str, list[str]] = {
    "hpc_code_gen": [
        "mpi", "openmp", "slurm", "parallel", "cuda", "gpu", "hpc",
        "fortran", "compile", "profil", "optimize", "performance",
        "supercomputer", "cluster", "mpirun", "rank", "nvidia",
        "opencl", "thread", "vectoriz", "simd", "fft",
    ],
    "scientific_data_pipeline": [
        "hdf5", "netcdf", "fits", "zarr", "root", "pipeline", "data",
        "dataset", "convert", "ingest", "etl", "h5py", "xarray",
        "parquet", "csv", "process", "transform", "extract",
        "analyz", "wrangl", "clean", "statistic", "domain",
    ],
    "data_pipeline": [
        "pipeline", "data", "dataset", "analyz", "process", "source",
        "wrangl", "clean", "statistic", "compute", "load",
        "domain", "scientific", "environmental", "biomedical",
        "wildfire", "astronomy", "legal", "archeology",
    ],
    "research_workflow": [
        "replicat", "reproduc", "paper", "research", "experiment",
        "workflow", "subtask", "phase", "implement", "train",
        "evaluat", "model", "benchmark", "result",
    ],
    "research_writing": [
        "paper", "draft", "section", "abstract", "review", "literature",
        "citation", "manuscript", "latex", "write", "edit", "revision",
        "conference", "journal", "submission",
    ],
}

_DEFAULT_DOMAIN_VOCAB: dict[str, list[str]] = {
    "hpc": ["hpc", "supercomputer", "cluster", "slurm", "pbs", "parallel", "high-performance"],
    "mpi": ["mpi", "mpirun", "rank", "scatter", "gather"],
    "gpu": ["cuda", "gpu", "nvidia", "opencl"],
    "hdf5": ["hdf5", "h5py", "hdf"],
    "netcdf": ["netcdf", "xarray"],
    "fits": ["fits", "astropy"],
    "zarr": ["zarr"],
    "root": ["root"],
    "fortran": ["fortran", "f90", "f77"],
    "openmp": ["openmp", "omp"],
    "slurm": ["slurm", "sbatch", "srun"],
    "parquet": ["parquet", "arrow"],
    "docker": ["docker", "container", "singularity"],
    "python": ["python", "numpy", "scipy", "pandas"],
    "data": ["data", "dataset", "pipeline", "csv", "json", "database"],
    "research": ["research", "paper", "experiment", "replicat", "reproduc"],
    "ml": ["model", "train", "neural", "deep", "learning", "inference"],
    "environmental_science": ["wildfire", "climate", "weather", "environmental", "noaa"],
    "astronomy": ["astronomy", "stellar", "galaxy", "telescope"],
    "biomedical": ["biomedical", "protein", "gene", "clinical"],
    "legal_analytics": ["legal", "court", "contract", "regulation"],
    "archeology": ["archeology", "excavat", "artifact"],
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


# --- Rule-Based Implementation ---


class RuleBasedIntentDetector:
    """Weighted keyword scoring classifier (§5.1).

    Configurable vocabularies for task type classification and domain
    tag extraction. Pure Python, no external dependencies, sub-millisecond.
    """

    def __init__(
        self,
        task_type_vocab: dict[str, list[str]] | None = None,
        domain_vocab: dict[str, list[str]] | None = None,
    ) -> None:
        self._task_type_vocab = task_type_vocab or _DEFAULT_TASK_TYPE_VOCAB
        self._domain_vocab = domain_vocab or _DEFAULT_DOMAIN_VOCAB
        # Pre-compute merged keyword set for technical density scoring.
        self._all_domain_keywords: frozenset[str] = frozenset(
            kw
            for keywords in (*self._domain_vocab.values(), *self._task_type_vocab.values())
            for kw in keywords
        )

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify a user request into a structured Intent."""
        tokens = _tokenize(request)
        token_set = set(tokens)
        signals = _compute_signals(request)

        return Intent(
            task_type=self._classify_task_type(token_set),
            complexity=self._estimate_complexity(tokens, token_set, signals),
            domain_tags=self._extract_domain_tags(token_set),
            decomposability=self._score_decomposability(signals),
            constraints=self._extract_constraints(request),
        )

    def _classify_task_type(self, token_set: set[str]) -> str:
        """Score each task type by keyword hits; highest wins (§3.1, §6.1).

        Uses prefix matching: token "profiling" matches vocab entry "profil".
        Only tok.startswith(kw) — not the reverse, which causes false positives
        when short tokens like "a" or "for" match long keywords.
        Below minimum threshold of 1 hit -> "general".
        """
        best_type = _FALLBACK_TASK_TYPE
        best_score = 0

        for task_type, keywords in self._task_type_vocab.items():
            score = sum(
                1 for kw in keywords
                if any(tok.startswith(kw) for tok in token_set)
            )
            if score > best_score:
                best_score = score
                best_type = task_type

        return best_type

    def _estimate_complexity(
        self, tokens: list[str], token_set: set[str], signals: _RequestSignals,
    ) -> float:
        """Five-signal weighted heuristic, normalized to [0,1] (§3.1).

        Signals:
        - Action verb count (0.30): distinct verbs imply distinct skills/tools needed
        - Technical density (0.25): ratio of domain-vocab tokens to total
        - Sentence count    (0.20): multiple sentences often mean multiple steps
        - Sequential markers (0.15): explicit "first/then/next" enumeration
        - Length            (0.10): longer requests tend to be more complex
        """
        word_count = len(tokens)

        verb_signal = min(len(signals.verb_matches) / 4.0, 1.0)

        if word_count == 0:
            tech_signal = 0.0
        else:
            tech_count = sum(
                1 for tok in tokens
                if any(tok.startswith(kw) for kw in self._all_domain_keywords)
            )
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

    def _extract_domain_tags(self, token_set: set[str]) -> list[str]:
        """Match tokens against domain vocabulary (§3.1, §5.2).

        Returns deduplicated, sorted list of domain tags.
        """
        tags: list[str] = []
        for tag, keywords in self._domain_vocab.items():
            if any(
                any(tok.startswith(kw) for tok in token_set)
                for kw in keywords
            ):
                tags.append(tag)
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
        task_type_vocab: dict[str, list[str]] | None = None,
        domain_vocab: dict[str, list[str]] | None = None,
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
        token_set = set(tokens)
        signals = _compute_signals(request)

        return Intent(
            task_type=self._classify_task_type(token_set),
            complexity=self._estimate_complexity(tokens, token_set, signals),
            domain_tags=self._extract_domain_tags(token_set),
            decomposability=self._spacy_decomposability(request, signals),
            constraints=self._extract_constraints(request),
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


# --- LLM-Based Implementation ---

# Few-shot examples for the LLM prompt.  Each is a (request, gold-label) pair.
# Gold labels are hand-annotated by domain experts — the ground truth that
# the rule-based heuristics fail to capture.
_FEW_SHOT_EXAMPLES: list[tuple[str, dict]] = [
    # --- Simple, single-agent tasks ---
    (
        "Show me the variables in this NetCDF file",
        {
            "task_type": "scientific_data_pipeline",
            "complexity": 0.10,
            "domain_tags": ["netcdf"],
            "decomposability": 0.05,
            "constraints": {},
        },
    ),
    # --- Medium complexity ---
    (
        "Draft the abstract and literature review section for my paper on distributed computing",
        {
            "task_type": "research_writing",
            "complexity": 0.45,
            "domain_tags": ["hpc"],
            "decomposability": 0.50,
            "constraints": {},
        },
    ),
    # --- High complexity, multi-step (from ScienceAgentBench) ---
    (
        "Train a graph convolutional network on the aquatic toxicity dataset to predict "
        "compound toxicity. Use the resulting model to compute and visualize the atomic "
        "contributions to molecular activity of the test compound. Save the figure as "
        "pred_results/aquatic_toxicity_qsar_vis.png.",
        {
            "task_type": "scientific_data_pipeline",
            "complexity": 0.85,
            "domain_tags": ["python"],
            "decomposability": 0.75,
            "constraints": {},
        },
    ),
    # --- With constraints ---
    (
        "Use Claude to summarize the dataset, limit to 500 tokens, under $2",
        {
            "task_type": "scientific_data_pipeline",
            "complexity": 0.20,
            "domain_tags": [],
            "decomposability": 0.10,
            "constraints": {"model_preference": "claude", "token_limit": 500, "budget": 2.0},
        },
    ),
]

_SYSTEM_PROMPT = """\
You are an intent classifier in multi-agent orchestration frameworks for scientific computing.

Given a user request, classify it into a structured intent representation with these fields:
- task_type: one of {task_types}
- complexity: float in [0, 1]. How much domain expertise, reasoning depth,
  and technical precision is required to correctly execute this task?
  0.0 = no expertise needed, single well-defined operation with obvious solution 
        (e.g., "sort this list").
  0.3 = basic domain knowledge, standard procedure, solution is well-known
        (e.g., "write a Python HTTP server").
  0.6 = significant domain expertise, multiple interacting constraints, 
        non-obvious solution path (e.g., "optimize this CUDA kernel for A100").
  1.0 = deep specialist knowledge across multiple domains, ambiguous or open-ended 
        problem, no standard solution exists
- domain_tags: list of relevant domain tags from {domain_tags}. Only include tags \
that are clearly relevant. Empty list if none apply.
- decomposability: float in [0, 1]. How naturally does this task split into 
  independent or loosely-coupled subtasks that could be dispatched to different agents?
  0.1 = monolithic, cannot be meaningfully split (e.g., "what is 2+2").
  0.3 = sequential steps but tightly coupled, splitting adds little value.
  0.7 = clear subtask boundaries with distinct output artifacts per subtask.
  0.9 = fully parallel fan-out, subtasks are independent and could run simultaneously
independent parallel subtasks.
- constraints: dict of explicit constraints mentioned in the request. Keys: \
"model_preference" (str), "token_limit" (int), "budget" (float). Empty dict if none.

Respond with ONLY valid JSON. No markdown, no code fences, no extra text.\
"""

# /no_think disables Qwen3/3.5 chain-of-thought reasoning.
# Intent classification is pattern matching, not reasoning —
# thinking tokens waste latency without improving accuracy.
_USER_TEMPLATE = "Request: {request}\n/no_think"


def _build_messages(
    request: str,
    task_types: frozenset[str],
    domain_tags: list[str],
) -> list[dict[str, str]]:
    """Build the chat messages list with few-shot examples."""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT.format(
                task_types=sorted(task_types),
                domain_tags=sorted(domain_tags),
            ),
        },
    ]

    for req_text, gold in _FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": _USER_TEMPLATE.format(request=req_text)})
        messages.append({"role": "assistant", "content": json.dumps(gold)})

    messages.append({"role": "user", "content": _USER_TEMPLATE.format(request=request)})
    return messages


class LLMIntentDetector:
    """LLM-based intent classifier via Ollama local models (§5.1).

    Uses few-shot prompting with hand-labeled examples to produce
    complexity and decomposability scores that capture semantic structure,
    not just surface-level keyword patterns.

    Falls back to RuleBasedIntentDetector on LLM failure.
    """

    def __init__(
        self,
        model: str = "qwen3:4b",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
        task_type_vocab: dict[str, list[str]] | None = None,
        domain_vocab: dict[str, list[str]] | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
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
        
        # Pre-build the static portion of the message list (system + few-shot).
        self._message_prefix = _build_messages(
            request="",  # placeholder — will be replaced per call
            task_types=self._known_task_types,
            domain_tags=self._domain_tag_list,
        )[:-1]  # drop the placeholder user message

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify a user request via LLM, with rule-based fallback."""
        try:
            return self._detect_llm(request)
        except Exception as exc:
            _log.warning("LLM intent detection failed (%s), falling back to rule-based", exc)
            return self._fallback.detect(request, session_context)

    def _detect_llm(self, request: str) -> Intent:
        """Call Ollama chat API and parse the structured JSON response."""
        messages = list(self._message_prefix)
        messages.append({"role": "user", "content": _USER_TEMPLATE.format(request=request)})

        payload = json.dumps({
            "model": self._model,
            "messages": messages,
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read())

        raw_text = body["message"]["content"]
        parsed = self._extract_json(raw_text)
        return self._parse_intent(parsed)

    def _parse_intent(self, data: dict) -> Intent:
        """Validate and convert raw LLM JSON output into an Intent."""
        task_type = str(data.get("task_type", _FALLBACK_TASK_TYPE))
        if task_type not in self._known_task_types:
            _log.warning("LLM returned unknown task_type %r, using %r", task_type, _FALLBACK_TASK_TYPE)
            task_type = _FALLBACK_TASK_TYPE

        complexity = self._clamp(float(data.get("complexity", 0.5)))
        decomposability = self._clamp(float(data.get("decomposability", 0.5)))

        raw_tags = data.get("domain_tags", [])
        if isinstance(raw_tags, list):
            domain_tags = sorted(
                t for t in raw_tags if isinstance(t, str) and t in self._domain_vocab
            )
        else:
            domain_tags = []

        raw_constraints = data.get("constraints", {})
        constraints: dict[str, object] = {}
        if isinstance(raw_constraints, dict):
            if "model_preference" in raw_constraints:
                constraints["model_preference"] = str(raw_constraints["model_preference"])
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
        """Extract JSON from LLM output that may contain think tags, code fences, or prose."""
        # Strip <think>...</think> blocks (Qwen3/3.5)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip()
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find the first { ... } block
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON object found in LLM response: {text[:200]!r}")

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))
