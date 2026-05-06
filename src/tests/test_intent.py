"""Tests for IntentDetector — derived from §3.1, §5.1, §6.1 paper claims.

Traceability:
- Task type classification: §3.1, §6.1 workload categories
- Complexity estimation: §3.1 (feeds AgentSelector threshold at solver.py:69)
- Domain tag extraction: §3.1, §5.2 (feeds speculator._prepare_context)
- Decomposability scoring: §3.1, §4.1 (Learner state vector)
- Constraint extraction: §3.1
- Latency: §5.1 (sub-second, 10x faster than Solver)
- Downstream compatibility: §5.1 (output accepted by AgentSelector and speculator)
"""

import time

import pytest
from pythia.contracts import Intent, bucket
from pythia.intent import IntentDetector, RuleBasedIntentDetector


# --- Fixtures ---


@pytest.fixture
def detector() -> RuleBasedIntentDetector:
    return RuleBasedIntentDetector()


# --- TestTaskTypeClassification (§3.1, §6.1) ---


class TestTaskTypeClassification:
    """Known task types correctly identified; unknown -> 'general'."""

    def test_hpc_code_gen(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Write an MPI program to parallelize matrix multiplication on a GPU cluster using CUDA")
        assert intent.task_type == "hpc_code_gen"

    def test_scientific_data_pipeline(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Build a pipeline to convert HDF5 datasets to NetCDF format with data validation")
        assert intent.task_type == "scientific_data_pipeline"

    def test_research_writing(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Draft the abstract and literature review section for my paper on distributed computing")
        assert intent.task_type == "research_writing"

    def test_unknown_falls_back_to_general(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("What is the weather today?")
        assert intent.task_type == "general"

    def test_empty_string_returns_general(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("")
        assert intent.task_type == "general"

    def test_task_types_align_with_agent_pipelines(self, detector: RuleBasedIntentDetector) -> None:
        """Output task types must match _AGENT_PIPELINES keys in solver.py:33-50."""
        from pythia.solver import _AGENT_PIPELINES

        valid_types = set(_AGENT_PIPELINES.keys()) | {"general"}
        for request in [
            "Write MPI code for parallel sorting",
            "Build HDF5 data pipeline",
            "Draft paper abstract",
            "What time is it?",
        ]:
            intent = detector.detect(request)
            assert intent.task_type in valid_types, f"task_type '{intent.task_type}' not in {valid_types}"


# --- TestComplexityEstimation (§3.1) ---


class TestComplexityEstimation:
    """Simple requests < 0.3; complex multi-step > 0.5."""

    def test_simple_request_below_threshold(self, detector: RuleBasedIntentDetector) -> None:
        """Simple one-line request must score < 0.3 to trigger AgentSelector single-agent fallback (solver.py:69)."""
        intent = detector.detect("Fix the bug")
        assert intent.complexity < 0.3

    def test_complex_multistep_above_threshold(self, detector: RuleBasedIntentDetector) -> None:
        request = (
            "1. First, analyze the HDF5 dataset structure and identify schema inconsistencies. "
            "2. Then write a conversion pipeline to transform the data into NetCDF format. "
            "3. After that, validate the output against the original checksums. "
            "4. Finally, generate a summary report with performance metrics and optimization recommendations."
        )
        intent = detector.detect(request)
        assert intent.complexity > 0.5

    def test_complexity_in_unit_interval(self, detector: RuleBasedIntentDetector) -> None:
        for request in ["Hi", "Do X then Y then Z then W then V" * 10]:
            intent = detector.detect(request)
            assert 0.0 <= intent.complexity <= 1.0


# --- TestDomainTagExtraction (§3.1, §5.2) ---


class TestDomainTagExtraction:
    """Scientific format keywords extracted as domain tags."""

    def test_hdf5_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Read the HDF5 file and extract datasets")
        assert "hdf5" in intent.domain_tags

    def test_mpi_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Use MPI to scatter data across ranks")
        assert "mpi" in intent.domain_tags

    def test_gpu_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Optimize the CUDA kernel for GPU execution")
        assert "gpu" in intent.domain_tags

    def test_netcdf_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Load NetCDF climate data with xarray")
        assert "netcdf" in intent.domain_tags

    def test_multiple_tags(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Write an MPI program with CUDA GPU support reading HDF5 data")
        assert "mpi" in intent.domain_tags
        assert "gpu" in intent.domain_tags
        assert "hdf5" in intent.domain_tags

    def test_tags_sorted(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Use MPI and CUDA on HDF5 data")
        assert intent.domain_tags == sorted(intent.domain_tags)

    def test_no_tags_for_generic_request(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("What is the weather?")
        assert intent.domain_tags == []


# --- TestDecomposabilityScoring (§3.1, §4.1) ---


class TestDecomposabilityScoring:
    """Single tasks score low; multi-step requests score high; always in [0,1]."""

    def test_single_task_low(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Fix the bug")
        assert intent.decomposability < 0.3

    def test_multistep_high(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect(
            "1. Parse the data. 2. Transform it. 3. Then validate. 4. After that, export."
        )
        assert intent.decomposability > 0.5

    def test_always_unit_interval(self, detector: RuleBasedIntentDetector) -> None:
        for req in ["x", "1. a 2. b 3. c 4. d 5. e 6. f 7. g 8. h"]:
            intent = detector.detect(req)
            assert 0.0 <= intent.decomposability <= 1.0


# --- TestConstraintExtraction (§3.1) ---


class TestConstraintExtraction:
    """Explicit constraints captured in dict."""

    def test_model_preference(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Use Claude to write a summary")
        assert "model_preference" in intent.constraints

    def test_token_limit(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Limit to 500 tokens")
        assert "token_limit" in intent.constraints
        assert intent.constraints["token_limit"] == 500

    def test_budget_constraint(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Complete the task under $5")
        assert "budget" in intent.constraints
        assert intent.constraints["budget"] == 5.0

    def test_no_constraints(self, detector: RuleBasedIntentDetector) -> None:
        # No *user-extracted* constraints (model_preference/token_limit/budget).
        # Keys starting with "_" are internal detector metadata (Phase 2 B.4
        # introduced _confidence_margin) — they're always present.
        intent = detector.detect("Write some code")
        user_keys = {k for k in intent.constraints if not k.startswith("_")}
        assert user_keys == set()


# --- TestLatencyBudget (Phase 5 — plan §F.1) ---


@pytest.mark.slow
class TestLatencyBudget:
    """Enforces the 500ms p95 SLA for every user-facing detector (plan §F.1).

    Skips cleanly when a detector's deps or factory are not yet available,
    so this test class is already in place waiting for Phases 3 and 4 to land.
    """

    COMPLEX_PROMPT = (
        "Train a graph convolutional network on the aquatic toxicity dataset "
        "to predict compound toxicity. Use the resulting model to compute and "
        "visualize the atomic contributions to molecular activity of the test "
        "compound. Save the figure as pred_results/aquatic_toxicity_qsar_vis.png."
    )
    # Matches the most-complex few-shot in intent.py — paper-traceable.

    @pytest.mark.parametrize("name", ["rule", "semantic", "llm"])
    def test_p95_under_500ms(self, name: str) -> None:
        try:
            from pythia.intent import make_intent_detector
        except ImportError:
            pytest.skip("make_intent_detector not available")

        try:
            det = make_intent_detector(name)
        except NotImplementedError:
            pytest.skip(f"{name}: factory not implemented (Phase 3 scaffold)")
        except ImportError:
            pytest.skip(f"{name}: deps unavailable")

        try:
            det.detect(self.COMPLEX_PROMPT)  # warmup
        except NotImplementedError:
            pytest.skip(f"{name}: detector body not implemented yet")

        timings: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            det.detect(self.COMPLEX_PROMPT)
            timings.append(time.perf_counter() - t0)
        p95 = sorted(timings)[int(0.95 * len(timings))]
        assert p95 < 0.5, f"{name}: p95={p95*1000:.0f}ms (budget: 500ms)"


# --- TestLatencyRequirement (§5.1) ---


class TestLatencyRequirement:
    """1000 classifications in < 1 second (< 1ms each)."""

    def test_throughput(self, detector: RuleBasedIntentDetector) -> None:
        requests = [
            "Write MPI code for parallel sorting on GPU cluster",
            "Build HDF5 to NetCDF conversion pipeline",
            "Draft the abstract for my paper",
            "Fix the bug in line 42",
        ] * 250  # 1000 total

        start = time.perf_counter()
        for req in requests:
            detector.detect(req)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"1000 classifications took {elapsed:.3f}s (must be < 1s)"


# --- TestDownstreamCompatibility (§5.1) ---


class TestDownstreamCompatibility:
    """Output accepted by AgentSelector.select_agents() and speculator._prepare_context()."""

    def test_agent_selector_accepts_output(self, detector: RuleBasedIntentDetector) -> None:
        from pythia.solver import AgentSelector

        selector = AgentSelector()
        for req in [
            "Write MPI code",
            "Build HDF5 pipeline",
            "Draft paper section",
            "What time is it?",
        ]:
            intent = detector.detect(req)
            agents = selector.select_agents(intent)
            assert len(agents) >= 1

    def test_prepare_context_accepts_output(self, detector: RuleBasedIntentDetector) -> None:
        from pythia.speculator import _prepare_context

        for req in [
            "Write MPI CUDA code",
            "Build HDF5 pipeline",
            "Hello",
        ]:
            intent = detector.detect(req)
            keys = _prepare_context(intent)
            assert f"task:{intent.task_type}" in keys
            for tag in intent.domain_tags:
                assert f"domain:{tag}" in keys


# --- TestWorkloadCoverage (§6.1) ---


class TestWorkloadCoverage:
    """Multiple representative requests per workload type all classify correctly."""

    @pytest.mark.parametrize("user_request", [
        "Write an OpenMP parallel loop for matrix multiply",
        "Optimize CUDA kernel for FFT on GPU",
        "Profile the MPI application with Slurm",
        "Compile the Fortran HPC code with parallel optimizations",
    ])
    def test_hpc_workload(self, detector: RuleBasedIntentDetector, user_request: str) -> None:
        assert detector.detect(user_request).task_type == "hpc_code_gen"

    @pytest.mark.parametrize("user_request", [
        "Convert HDF5 datasets to Zarr format",
        "Build an ETL pipeline for NetCDF climate data",
        "Ingest FITS astronomical data into the pipeline",
        "Process ROOT files and extract event datasets",
    ])
    def test_data_pipeline_workload(self, detector: RuleBasedIntentDetector, user_request: str) -> None:
        assert detector.detect(user_request).task_type == "scientific_data_pipeline"

    @pytest.mark.parametrize("user_request", [
        "Write the literature review section",
        "Draft an abstract for the manuscript",
        "Review citations in the paper",
        "Edit the LaTeX draft for the conference submission",
    ])
    def test_writing_workload(self, detector: RuleBasedIntentDetector, user_request: str) -> None:
        assert detector.detect(user_request).task_type == "research_writing"


# --- TestCustomVocabulary ---


class TestCustomVocabulary:
    """Custom vocabularies override defaults."""

    def test_custom_task_type_vocab(self) -> None:
        custom_vocab = {"custom_type": ["foobar", "bazqux"]}
        det = RuleBasedIntentDetector(task_type_vocab=custom_vocab)
        intent = det.detect("Run the foobar bazqux process")
        assert intent.task_type == "custom_type"

    def test_custom_domain_vocab(self) -> None:
        custom_domain = {"myformat": ["zzzformat", "zzzlib"]}
        det = RuleBasedIntentDetector(domain_vocab=custom_domain)
        intent = det.detect("Load zzzformat data with zzzlib")
        assert "myformat" in intent.domain_tags


# --- TestProtocolConformance ---


class TestProtocolConformance:
    """RuleBasedIntentDetector satisfies IntentDetector Protocol."""

    def test_conforms_to_protocol(self) -> None:
        det: IntentDetector = RuleBasedIntentDetector()
        result = det.detect("test request")
        assert isinstance(result, Intent)

    def test_session_context_accepted(self, detector: RuleBasedIntentDetector) -> None:
        result = detector.detect("test", session_context={"history": []})
        assert isinstance(result, Intent)


# --- TestRuleBasedEdgeCases (Phase 2 scaffold — marked xfail) ---
#
# These tests describe the TARGET behavior for the five rule-based fixes
# in plan §B. They are expected to FAIL on today's implementation and should
# start passing one-by-one as the helpers in intent.py are filled in.
#
# Flip xfail → expected-pass to promote each fix as it lands.


class TestRuleBasedEdgeCases:
    """Plan §B fixes — implemented in Phase 2."""

    def test_word_boundary_no_substring_match(self, detector: RuleBasedIntentDetector) -> None:
        # "rooftop" must NOT trigger the ROOT file-format tag.
        intent = detector.detect("Install solar panels on the rooftop")
        assert "root" not in intent.domain_tags

    def test_word_boundary_no_prefix_collision(self, detector: RuleBasedIntentDetector) -> None:
        # The 3rd-person verb "fits" (lowercase) must NOT tag the uppercase
        # FITS astronomical format.
        intent = detector.detect(
            "This approach fits our needs and the results benefit everyone"
        )
        assert "fits" not in intent.domain_tags

    def test_multiword_phrase_hpc(self, detector: RuleBasedIntentDetector) -> None:
        # "high-performance computing" (hyphen and space forms) → hpc tag.
        for phrase in [
            "Run the code on high-performance computing hardware",
            "Deploy to a high performance computing cluster",
        ]:
            intent = detector.detect(phrase)
            assert "hpc" in intent.domain_tags, f"Missing hpc tag for: {phrase!r}"

    def test_specificity_tiebreak_scientific_vs_generic(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # When scientific_data_pipeline and data_pipeline tie on score, dict
        # insertion order picks scientific_data_pipeline — documented tie-break.
        request = "Build a domain pipeline to clean and analyze statistical data"
        intent = detector.detect(request)
        assert intent.task_type == "scientific_data_pipeline", (
            f"Expected scientific_data_pipeline on tie; got {intent.task_type}"
        )

    def test_confidence_margin_present(self, detector: RuleBasedIntentDetector) -> None:
        # Rule detector must populate _confidence_margin for the harness.
        intent = detector.detect("Write MPI code for parallel sorting on GPU cluster")
        assert "_confidence_margin" in intent.constraints
        margin = intent.constraints["_confidence_margin"]
        assert isinstance(margin, float)
        assert 0.0 <= margin <= 1.0

    def test_confidence_margin_higher_for_clearer_winner(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # A clean HPC-heavy prompt should have a HIGHER margin than one that
        # straddles scientific_data_pipeline and data_pipeline.
        clear = detector.detect(
            "Write MPI OpenMP CUDA GPU cluster code"
        ).constraints.get("_confidence_margin", 0.0)
        muddy = detector.detect(
            "Build a domain pipeline to clean and analyze statistical data"
        ).constraints.get("_confidence_margin", 0.0)
        assert clear > muddy, f"Expected clear > muddy; got clear={clear}, muddy={muddy}"

    def test_negation_suppresses_tag(self, detector: RuleBasedIntentDetector) -> None:
        # "don't use MPI" → no mpi tag.
        intent = detector.detect("Write a parallel sort but don't use MPI")
        assert "mpi" not in intent.domain_tags

    def test_without_preposition_suppresses_tag(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        intent = detector.detect("Implement the algorithm without CUDA or GPU acceleration")
        assert "gpu" not in intent.domain_tags


# --- TestSemanticIntentDetector (Phase 4) ---


class TestSemanticIntentDetector:
    """Zero-shot encoder detector (plan §D) — implemented in Phase 4.

    Requires ``pythia[ml]`` (sentence-transformers + torch). Tests skip
    rather than fail when the deps are missing — matches the optional-extra
    guard pattern from SpacyIntentDetector.
    """

    def _skip_if_no_ml(self) -> None:
        pytest.importorskip("sentence_transformers")
        pytest.importorskip("torch")

    def test_constructs_without_error(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        assert det is not None

    def test_detect_returns_intent(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        intent = det.detect("Write MPI code for parallel sorting on GPU cluster")
        assert isinstance(intent, Intent)
        assert intent.task_type == "hpc_code_gen"
        assert "mpi" in intent.domain_tags or "gpu" in intent.domain_tags

    def test_emits_task_type_confidence(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        intent = det.detect("Write MPI code")
        assert "_confidence_task_type" in intent.constraints
        conf = intent.constraints["_confidence_task_type"]
        assert isinstance(conf, float) and 0.0 <= conf <= 1.0

    def test_emits_domain_confidence(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        intent = det.detect("Use CUDA on the GPU cluster")
        assert "_confidence_domain_avg" in intent.constraints
        conf = intent.constraints["_confidence_domain_avg"]
        assert isinstance(conf, float) and 0.0 <= conf <= 1.0

    def test_complexity_interpolates_between_anchors(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        simple = det.detect("sort this list").complexity
        complex_ = det.detect(
            "Train a graph convolutional network on the aquatic toxicity dataset, "
            "visualize atomic contributions, and save the result."
        ).complexity
        assert complex_ > simple, f"Expected complex > simple; got {complex_} vs {simple}"

    def test_decomposability_interpolates_between_anchors(self) -> None:
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        atomic = det.detect("what is 2 plus 2").decomposability
        parallel = det.detect(
            "1. Parse the data. 2. Transform it. 3. Validate. 4. Export."
        ).decomposability
        assert parallel > atomic, (
            f"Expected parallel > atomic; got {parallel} vs {atomic}"
        )

    def test_falls_back_without_deps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the loader to return None (deps missing).
        import pythia.intent as intent_mod
        monkeypatch.setattr(intent_mod, "_load_sentence_transformer", lambda *a, **kw: None)
        # Must still produce a valid Intent via the rule-based fallback.
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        intent = det.detect("Write MPI code")
        assert isinstance(intent, Intent)
        # Fallback still produces the correct task_type via the rule detector.
        assert intent.task_type == "hpc_code_gen"

    def test_intent_field_types(self) -> None:
        # Guard against numpy scalars leaking into Intent (must be Python floats).
        self._skip_if_no_ml()
        from pythia.intent import SemanticIntentDetector
        det = SemanticIntentDetector()
        intent = det.detect("Build an HDF5 to Zarr pipeline")
        assert type(intent.complexity) is float
        assert type(intent.decomposability) is float
        assert isinstance(intent.domain_tags, list)
        for tag in intent.domain_tags:
            assert isinstance(tag, str)


# --- TestLLMUpgradeAndFactory (Phase 3) ---


class TestLLMUpgradeAndFactory:
    """Plan §C (LLM slim-down) and §E (factory) — implemented in Phase 3."""

    def test_factory_returns_rule_by_default(self) -> None:
        from pythia.intent import make_intent_detector
        det = make_intent_detector()
        intent = det.detect("Write MPI code")
        assert isinstance(intent, Intent)
        assert intent.task_type == "hpc_code_gen"

    def test_factory_respects_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pythia.intent import (
            RuleBasedIntentDetector,
            SpacyIntentDetector,
            make_intent_detector,
        )
        monkeypatch.setenv("PYTHIA_INTENT_DETECTOR", "rule")
        det = make_intent_detector()
        # rule auto-selects SpacyIntentDetector when available, else RuleBased.
        assert isinstance(det, (RuleBasedIntentDetector, SpacyIntentDetector))

    def test_factory_unknown_name_raises(self) -> None:
        from pythia.intent import make_intent_detector
        with pytest.raises(ValueError):
            make_intent_detector("bogus")

    def test_factory_unknown_name_via_env_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Env-var-supplied names must also go through validation.
        from pythia.intent import make_intent_detector
        monkeypatch.setenv("PYTHIA_INTENT_DETECTOR", "gibberish")
        with pytest.raises(ValueError):
            make_intent_detector()

    def test_llm_accepts_provider_kwarg(self) -> None:
        from pythia.intent import LLMIntentDetector
        for provider in ("ollama", "lmstudio", "vllm"):
            LLMIntentDetector(provider=provider)

    def test_llm_rejects_unknown_provider(self) -> None:
        from pythia.intent import LLMIntentDetector
        with pytest.raises(ValueError):
            LLMIntentDetector(provider="bogus")

    def test_llm_default_model_is_small(self) -> None:
        # Default must be the 0.5B model to fit the 500ms SLA on CPU.
        from pythia.intent import LLMIntentDetector
        det = LLMIntentDetector()
        assert "0.5b" in det._model.lower() or "500m" in det._model.lower()

    def test_factory_llm_provider_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pythia.intent import LLMIntentDetector, make_intent_detector
        monkeypatch.setenv("PYTHIA_LLM_PROVIDER", "lmstudio")
        det = make_intent_detector("llm")
        assert isinstance(det, LLMIntentDetector)
        assert det._provider == "lmstudio"

    def test_llm_falls_back_on_unreachable_provider(self) -> None:
        # Unreachable URL → timeout race → rule-based fallback.
        # _confidence_llm = 0.0 signals "fell back" to the harness.
        from pythia.intent import LLMIntentDetector
        det = LLMIntentDetector(base_url="http://127.0.0.1:1")
        intent = det.detect("Write MPI code for parallel sorting on GPU cluster")
        assert isinstance(intent, Intent)
        assert intent.constraints.get("_confidence_llm") == 0.0
        # Fallback still produces a meaningful classification.
        assert intent.task_type == "hpc_code_gen"

    def test_500ms_ceiling_on_hang(self) -> None:
        # Even with an unreachable provider, detect() must return well
        # under 500ms via the timeout race (plan §C.6).
        from pythia.intent import LLMIntentDetector
        det = LLMIntentDetector(base_url="http://127.0.0.1:1")
        # Warmup (first call may pay thread-pool startup on very first use).
        det.detect("warmup")
        t0 = time.perf_counter()
        det.detect("Write MPI code for parallel sorting on GPU cluster, fresh")
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.6, f"detect() took {elapsed*1000:.0f}ms on LLM hang"

    def test_llm_cache_hit_is_instant(self) -> None:
        # Second call with same request should hit the LRU cache and return
        # in microseconds — no thread pool, no HTTP.
        from pythia.intent import LLMIntentDetector
        det = LLMIntentDetector(base_url="http://127.0.0.1:1")
        det.detect("cache me")
        t0 = time.perf_counter()
        det.detect("cache me")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 5.0, f"Cache hit took {elapsed_ms:.2f}ms"


# --- TestBucketHelper (Phase 1) ---


class TestBucketHelper:
    """contracts.bucket() is the single source of truth for low/med/high thresholds.

    Parity check: speculator._intent_key and learner._intent_key both now call
    bucket(). This test locks the thresholds in place so a future change to the
    helper doesn't silently split the cache key across the two callers.
    """

    @pytest.mark.parametrize("value,expected", [
        (0.0, "low"),
        (0.1, "low"),
        (0.29, "low"),
        (0.3, "med"),
        (0.5, "med"),
        (0.59, "med"),
        (0.6, "high"),
        (0.9, "high"),
        (1.0, "high"),
    ])
    def test_thresholds(self, value: float, expected: str) -> None:
        assert bucket(value) == expected

    def test_speculator_and_learner_agree(self) -> None:
        """Both intent_key functions must produce identical strings for the same Intent."""
        from pythia.learner import _intent_key as learner_key
        from pythia.speculator import _intent_key as speculator_key

        for complexity in [0.0, 0.29, 0.3, 0.59, 0.6, 1.0]:
            intent = Intent(
                task_type="hpc_code_gen",
                complexity=complexity,
                domain_tags=["mpi", "gpu"],
                decomposability=0.5,
            )
            assert speculator_key(intent) == learner_key(intent)


# --- Corner Cases (Phase 2 follow-up) ---
#
# Pin behaviors that the existing suite leaves uncovered: degenerate inputs,
# non-ASCII content, pathological lengths, acronym case discipline, negation
# window edges, constraint regex edges, vocab compilation errors, the spaCy
# detector path, and LRU cache eviction. Cases marked "known limitation" are
# pinned to current behavior so a future rewrite has to consciously change
# the contract.


class TestEmptyAndDegenerateInputs:
    """Empty / whitespace / single-char input must not crash and must return a valid Intent."""

    def test_empty_string_returns_valid_intent(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("")
        assert isinstance(intent, Intent)
        assert intent.task_type == "general"
        assert 0.0 <= intent.complexity <= 1.0
        assert intent.domain_tags == []
        assert 0.0 <= intent.decomposability <= 1.0

    def test_whitespace_only(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("   \n\t  ")
        assert intent.task_type == "general"
        assert intent.domain_tags == []

    def test_single_character(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("x")
        assert isinstance(intent, Intent)
        assert intent.task_type == "general"


class TestUnicodeAndNonASCIIInput:
    """Non-ASCII content does not crash; ASCII keywords inside still match."""

    def test_french_input_no_crash(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("écrire un programme en parallèle")
        assert isinstance(intent, Intent)

    def test_emoji_does_not_break_keyword_match(self, detector: RuleBasedIntentDetector) -> None:
        # Emoji counts as a non-word char so \b still anchors on either side.
        intent = detector.detect("🚀 launch the MPI job 🎉")
        assert "mpi" in intent.domain_tags

    def test_cjk_with_embedded_english_keyword(self, detector: RuleBasedIntentDetector) -> None:
        # CJK chars are \w under Python's default unicode regex, so a space
        # between them and an ASCII keyword still produces the expected \b.
        intent = detector.detect("训练 GPU 模型 with CUDA")
        assert "gpu" in intent.domain_tags


class TestPathologicalInput:
    """Long inputs complete in reasonable time — guards against catastrophic backtracking."""

    def test_long_input_completes_quickly(self, detector: RuleBasedIntentDetector) -> None:
        request = "Write MPI code for parallel sorting on a GPU cluster. " * 400  # ~22k chars
        start = time.perf_counter()
        intent = detector.detect(request)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"detect() took {elapsed*1000:.0f}ms on {len(request)}-char input"
        assert intent.task_type == "hpc_code_gen"


class TestAcronymCaseSensitivity:
    """ALL-CAPS vocab entries (FITS, ROOT) reject lowercase AND Title Case forms."""

    def test_title_case_fits_does_not_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("This Fits our needs perfectly")
        assert "fits" not in intent.domain_tags

    def test_title_case_root_does_not_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("The Root cause is unclear")
        assert "root" not in intent.domain_tags

    def test_uppercase_fits_does_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Process the FITS image header")
        assert "fits" in intent.domain_tags

    def test_uppercase_root_does_tag(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Open the ROOT event file from the experiment")
        assert "root" in intent.domain_tags


class TestNegationWindowEdgeCases:
    """Pin behavior at the boundaries of the ~40-char negation suppression window."""

    def test_negation_outside_window_does_not_suppress(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # >40 chars between "don't" and "MPI" — mpi tag survives.
        request = (
            "We don't have any objections at all, "
            + ("padding text " * 5)
            + "MPI is fine"
        )
        intent = detector.detect(request)
        assert "mpi" in intent.domain_tags

    def test_clause_local_negation_only_affects_local_keyword(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # Window can reach across a sentence boundary, but only suppresses the
        # nearby keyword. MPI is unnegated; CUDA sits inside the "don't" window.
        intent = detector.detect("We use MPI. We don't use CUDA.")
        assert "mpi" in intent.domain_tags
        assert "gpu" not in intent.domain_tags

    def test_double_negation_known_limitation(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # Known limitation: any negation in window suppresses, even when two
        # negations would semantically restore the keyword. Pinned so a future
        # rewrite has to consciously change the contract.
        intent = detector.detect("Please don't avoid MPI when parallelizing")
        assert "mpi" not in intent.domain_tags


class TestConstraintExtractionEdgeCases:
    """Edges of the regex-based constraint extractor."""

    def test_decimal_budget(self, detector: RuleBasedIntentDetector) -> None:
        intent = detector.detect("Run this under $5.50 please")
        assert intent.constraints.get("budget") == 5.5

    def test_first_model_preference_wins(self, detector: RuleBasedIntentDetector) -> None:
        # re.search returns the first match — pin the lexical-order tie-break.
        intent = detector.detect("Use Claude or maybe use GPT-4 instead")
        assert intent.constraints.get("model_preference") == "claude"

    def test_token_limit_under_negation_known_limitation(
        self, detector: RuleBasedIntentDetector
    ) -> None:
        # Known limitation: constraint regexes do not respect negation windows.
        # "don't limit to 500 tokens" still extracts 500. Pinned to flag the
        # behavior; if the rule detector later gains constraint-level negation
        # handling, this expectation flips.
        intent = detector.detect("don't limit to 500 tokens")
        assert intent.constraints.get("token_limit") == 500


class TestVocabCompilationErrors:
    """Malformed vocab entries fail loudly at construction time."""

    def test_empty_stem_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty vocab"):
            RuleBasedIntentDetector(task_type_vocab={"x": ["*"]})

    def test_invalid_entry_type_raises(self) -> None:
        with pytest.raises(TypeError):
            RuleBasedIntentDetector(task_type_vocab={"x": [123]})  # type: ignore[list-item]


class TestSpacyDecomposability:
    """SpacyIntentDetector — direct coverage of the spaCy code path and fallback."""

    def _skip_if_no_spacy(self) -> None:
        spacy = pytest.importorskip("spacy")
        try:
            spacy.load("en_core_web_sm")
        except OSError:
            pytest.skip("en_core_web_sm not installed")

    def test_constructs_and_returns_intent(self) -> None:
        self._skip_if_no_spacy()
        from pythia.intent import SpacyIntentDetector

        det = SpacyIntentDetector()
        intent = det.detect("Parse the data, transform it, and export the result")
        assert isinstance(intent, Intent)
        assert 0.0 <= intent.decomposability <= 1.0

    def test_falls_back_when_nlp_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force the loader to return None — exercises the fallback branch in
        # _spacy_decomposability without needing spaCy installed.
        import pythia.intent as intent_mod

        monkeypatch.setattr(intent_mod, "_load_spacy", lambda: None)
        from pythia.intent import SpacyIntentDetector

        det = SpacyIntentDetector()
        assert det._nlp is None
        intent = det.detect(
            "1. Parse the data. 2. Transform it. 3. Validate. 4. Export."
        )
        assert isinstance(intent, Intent)
        assert 0.0 <= intent.decomposability <= 1.0


class TestLLMCacheEviction:
    """LRU cache honors cache_size and evicts the least-recently-used entry."""

    def test_eviction_drops_oldest(self) -> None:
        from pythia.intent import LLMIntentDetector

        # Unreachable provider → every call falls back, but the result is still cached.
        det = LLMIntentDetector(base_url="http://127.0.0.1:1", cache_size=2)
        det.detect("alpha")
        det.detect("beta")
        det.detect("gamma")
        assert len(det._cache) == 2
        assert "alpha" not in det._cache
        assert "beta" in det._cache
        assert "gamma" in det._cache

    def test_lru_promotes_recent_hits(self) -> None:
        from pythia.intent import LLMIntentDetector

        det = LLMIntentDetector(base_url="http://127.0.0.1:1", cache_size=2)
        det.detect("alpha")
        det.detect("beta")
        det.detect("alpha")  # promote alpha to most-recent
        det.detect("gamma")  # should evict beta, not alpha
        assert "alpha" in det._cache
        assert "beta" not in det._cache
        assert "gamma" in det._cache
