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

import re
from typing import Protocol, runtime_checkable

from pythia.contracts import Intent


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
    ],
    "research_writing": [
        "paper", "draft", "section", "abstract", "review", "literature",
        "citation", "manuscript", "latex", "write", "edit", "revision",
        "conference", "journal", "submission",
    ],
}

_DEFAULT_DOMAIN_VOCAB: dict[str, list[str]] = {
    "hpc": ["hpc", "supercomputer", "cluster", "slurm", "pbs"],
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
}

_SUBTASK_INDICATORS = re.compile(
    r"\b(?:first|then|next|also|after that|finally|followed by|additionally|subsequently)\b"
    r"|(?:^|\s)\d+\.",
    re.IGNORECASE,
)

_TOKENIZE_PATTERN = re.compile(r"[a-z0-9]+")


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

    def detect(
        self, request: str, session_context: dict[str, object] | None = None
    ) -> Intent:
        """Classify a user request into a structured Intent."""
        tokens = _tokenize(request)
        token_set = set(tokens)

        return Intent(
            task_type=self._classify_task_type(token_set),
            complexity=self._estimate_complexity(request, tokens, token_set),
            domain_tags=self._extract_domain_tags(token_set),
            decomposability=self._score_decomposability(request),
            constraints=self._extract_constraints(request),
        )

    def _classify_task_type(self, token_set: set[str]) -> str:
        """Score each task type by keyword hits; highest wins (§3.1, §6.1).

        Uses prefix matching: token "profiling" matches vocab entry "profil".
        Only tok.startswith(kw) — not the reverse, which causes false positives
        when short tokens like "a" or "for" match long keywords.
        Below minimum threshold of 1 hit -> "general".
        """
        best_type = "general"
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
        self, request: str, tokens: list[str], token_set: set[str]
    ) -> float:
        """Three-signal weighted heuristic, normalized to [0,1] (§3.1).

        - Length (0.3): min(word_count / 100, 1.0)
        - Sub-task indicators (0.3): count of sequential/enumeration markers
        - Technical density (0.4): ratio of domain-vocab tokens to total
        """
        # Length signal
        word_count = len(tokens)
        length_signal = min(word_count / 100.0, 1.0)

        # Sub-task indicators
        indicator_count = len(_SUBTASK_INDICATORS.findall(request))
        subtask_signal = min(indicator_count / 5.0, 1.0)

        # Technical density
        if word_count == 0:
            tech_signal = 0.0
        else:
            all_domain_keywords: set[str] = set()
            for keywords in self._domain_vocab.values():
                all_domain_keywords.update(keywords)
            for keywords in self._task_type_vocab.values():
                all_domain_keywords.update(keywords)

            tech_count = sum(
                1 for tok in tokens
                if any(tok.startswith(kw) for kw in all_domain_keywords)
            )
            tech_signal = min(tech_count / word_count, 1.0)

        return 0.3 * length_signal + 0.3 * subtask_signal + 0.4 * tech_signal

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

    def _score_decomposability(self, request: str) -> float:
        """Structural analysis for decomposability (§3.1, §4.1).

        Counts enumeration markers and sequential/parallel indicators.
        Normalized: min(indicator_count / 5, 1.0).
        """
        indicator_count = len(_SUBTASK_INDICATORS.findall(request))
        return min(indicator_count / 5.0, 1.0)

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
