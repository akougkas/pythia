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
from pythia.contracts import Intent
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
        intent = detector.detect("Write some code")
        assert intent.constraints == {}


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
