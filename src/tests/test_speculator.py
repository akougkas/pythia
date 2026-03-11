"""Tests for Speculative Dispatcher — derived from §3.2, §3.4 paper claims.

Traceability:
- Speculation modes (progressive activation): §3.2
- Cost model thresholds tau_2, tau_3: §3.4
- Pre-execution manifest: §3.2
- Cache-based draft plan: §3.2, §5.1
- Mode 2 threshold: p > tau_2 iff E[sigma]*C_s > C_2: §3.4
- Mode 3 threshold: p > tau_3 iff E[sigma]*C_s > C_3: §3.4
"""

import pytest
from dataclasses import FrozenInstanceError

from pythia.contracts import (
    AgentAssignment,
    DispatchPlan,
    FleetMember,
    Intent,
    PreExecutionManifest,
    SpeculationResult,
)
from pythia.fleet import Fleet
from pythia.speculator import (
    ConfidenceTracker,
    DispatchCache,
    SpeculativeDispatcher,
    _draft_execute,
    _prepare_context,
    _provision_agents,
    select_mode,
)
from pythia.comparison import plan_match, plan_overlap


# --- Fixtures ---


def _intent(task_type: str = "hpc_code_gen") -> Intent:
    return Intent(
        task_type=task_type,
        complexity=0.8,
        domain_tags=["hpc", "mpi"],
        decomposability=0.6,
    )


def _plan(
    assignments: list[tuple[str, str]] | None = None,
) -> DispatchPlan:
    if assignments is None:
        assignments = [("code_gen", "gpu-1"), ("review", "cpu-1")]
    return DispatchPlan(
        assignments=[
            AgentAssignment(at, fm, 1000, "stub", i)
            for i, (at, fm) in enumerate(assignments)
        ],
        execution_order=[[at for at, _ in assignments]],
        total_budget=len(assignments) * 1000,
        total_estimated_latency=0.5,
    )


def _fleet() -> Fleet:
    return Fleet([
        FleetMember("gpu-1", 100.0, 64.0, 10, 100_000, 0.05, 0.1,
                     ["code_gen", "analysis"], ["gpu"]),
        FleetMember("cpu-1", 50.0, 32.0, 5, 50_000, 0.02, 0.2,
                     ["review", "planner"], ["cpu"]),
    ])


# ===== Task 0: Contract Tests =====


class TestPreExecutionManifest:
    def test_frozen(self):
        m = PreExecutionManifest(1, ["ctx"], [], [], "", "")
        with pytest.raises(FrozenInstanceError):
            m.mode = 2  # type: ignore[misc]

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            PreExecutionManifest(0, [], [], [], "", "")

    def test_valid_modes(self):
        for mode in (1, 2, 3):
            m = PreExecutionManifest(mode, [], [], [], "", "")
            assert m.mode == mode


class TestSpeculationResult:
    def test_frozen(self):
        r = SpeculationResult(_plan(), PreExecutionManifest(1, [], [], [], "", ""),
                              0.5, 1, False)
        with pytest.raises(FrozenInstanceError):
            r.confidence = 0.9  # type: ignore[misc]

    def test_confidence_range_lower(self):
        with pytest.raises(ValueError, match="confidence"):
            SpeculationResult(_plan(), PreExecutionManifest(1, [], [], [], "", ""),
                              -0.1, 1, False)

    def test_confidence_range_upper(self):
        with pytest.raises(ValueError, match="confidence"):
            SpeculationResult(_plan(), PreExecutionManifest(1, [], [], [], "", ""),
                              1.1, 1, False)

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            SpeculationResult(_plan(), PreExecutionManifest(1, [], [], [], "", ""),
                              0.5, 4, False)


# ===== Task 1: Dispatch Cache =====


class TestDispatchCache:
    def test_empty_lookup_returns_none(self):
        cache = DispatchCache()
        assert cache.lookup(_intent()) is None

    def test_store_and_retrieve(self):
        cache = DispatchCache()
        intent = _intent()
        plan = _plan()
        cache.store(intent, plan)
        assert cache.lookup(intent) == plan

    def test_most_recent_returned(self):
        cache = DispatchCache()
        intent = _intent()
        plan1 = _plan([("code_gen", "gpu-1")])
        plan2 = _plan([("review", "cpu-1")])
        cache.store(intent, plan1)
        cache.store(intent, plan2)
        assert cache.lookup(intent) == plan2

    def test_eviction_at_max_history(self):
        cache = DispatchCache(max_history=2)
        intent = _intent()
        cache.store(intent, _plan([("a", "m1")]))
        cache.store(intent, _plan([("b", "m2")]))
        cache.store(intent, _plan([("c", "m3")]))
        assert cache.history_depth(intent) == 2
        # Most recent is ("c", "m3")
        result = cache.lookup(intent)
        assert result is not None
        assert result.assignments[0].agent_type == "c"

    def test_isolation_between_task_types(self):
        cache = DispatchCache()
        i1 = _intent("hpc_code_gen")
        i2 = _intent("research_writing")
        p1 = _plan([("code_gen", "gpu-1")])
        p2 = _plan([("analysis", "cpu-1")])
        cache.store(i1, p1)
        cache.store(i2, p2)
        assert cache.lookup(i1) == p1
        assert cache.lookup(i2) == p2

    def test_history_depth(self):
        cache = DispatchCache()
        intent = _intent()
        assert cache.history_depth(intent) == 0
        cache.store(intent, _plan())
        assert cache.history_depth(intent) == 1
        cache.store(intent, _plan())
        assert cache.history_depth(intent) == 2

    def test_clear(self):
        cache = DispatchCache()
        cache.store(_intent(), _plan())
        cache.clear()
        assert cache.lookup(_intent()) is None
        assert cache.history_depth(_intent()) == 0


# ===== Task 2: Confidence Tracker =====


class TestConfidenceTracker:
    def test_unseen_returns_zero(self):
        tracker = ConfidenceTracker()
        assert tracker.confidence(_intent()) == 0.0

    def test_hits_increase_confidence(self):
        tracker = ConfidenceTracker()
        intent = _intent()
        tracker.record_outcome(intent, hit=True)
        assert tracker.confidence(intent) == 1.0
        tracker.record_outcome(intent, hit=True)
        assert tracker.confidence(intent) == 1.0

    def test_misses_decrease_confidence(self):
        tracker = ConfidenceTracker()
        intent = _intent()
        tracker.record_outcome(intent, hit=True)
        tracker.record_outcome(intent, hit=False)
        assert tracker.confidence(intent) == pytest.approx(0.5)

    def test_isolation_between_task_types(self):
        tracker = ConfidenceTracker()
        i1 = _intent("hpc_code_gen")
        i2 = _intent("research_writing")
        tracker.record_outcome(i1, hit=True)
        tracker.record_outcome(i2, hit=False)
        assert tracker.confidence(i1) == 1.0
        assert tracker.confidence(i2) == 0.0

    def test_perfect_hit_rate(self):
        tracker = ConfidenceTracker()
        intent = _intent()
        for _ in range(10):
            tracker.record_outcome(intent, hit=True)
        assert tracker.confidence(intent) == 1.0

    def test_zero_hit_rate(self):
        tracker = ConfidenceTracker()
        intent = _intent()
        for _ in range(10):
            tracker.record_outcome(intent, hit=False)
        assert tracker.confidence(intent) == 0.0


# ===== Task 3: Mode Selection =====


class TestSelectMode:
    def test_low_confidence_mode_1(self):
        assert select_mode(0.1, tau_2=0.3, tau_3=0.7) == 1

    def test_medium_confidence_mode_2(self):
        assert select_mode(0.5, tau_2=0.3, tau_3=0.7) == 2

    def test_high_confidence_mode_3(self):
        assert select_mode(0.9, tau_2=0.3, tau_3=0.7) == 3

    def test_at_tau_2_boundary_mode_1(self):
        """At exactly tau_2, we stay in Mode 1 (strict >)."""
        assert select_mode(0.3, tau_2=0.3, tau_3=0.7) == 1

    def test_above_tau_2_boundary_mode_2(self):
        assert select_mode(0.31, tau_2=0.3, tau_3=0.7) == 2

    def test_at_tau_3_boundary_mode_2(self):
        """At exactly tau_3, we stay in Mode 2 (strict >)."""
        assert select_mode(0.7, tau_2=0.3, tau_3=0.7) == 2

    def test_invalid_tau_order_raises(self):
        with pytest.raises(ValueError, match="tau_3"):
            select_mode(0.5, tau_2=0.7, tau_3=0.3)


# ===== Task 4: Mode 1 — Context Preparation =====


class TestPrepareContext:
    def test_always_produces_keys(self):
        keys = _prepare_context(_intent())
        assert len(keys) > 0

    def test_includes_domain_tags(self):
        keys = _prepare_context(_intent())
        assert "domain:hpc" in keys
        assert "domain:mpi" in keys

    def test_includes_task_type(self):
        keys = _prepare_context(_intent())
        assert "task:hpc_code_gen" in keys

    def test_agent_agnostic(self):
        """Context keys must not reference specific fleet members or agents."""
        keys = _prepare_context(_intent())
        for key in keys:
            assert "gpu-1" not in key
            assert "code_gen" not in key.split(":")[-1] or key.startswith("task:")

    def test_no_duplicate_keys(self):
        intent = Intent("test", 0.5, ["a", "b", "c"], 0.5)
        keys = _prepare_context(intent)
        assert len(keys) == len(set(keys))


# ===== Task 5: Mode 2 — Agent Pre-dispatch =====


class TestProvisionAgents:
    def test_provisions_feasible_agents(self):
        fleet = _fleet()
        plan = _plan([("code_gen", "gpu-1")])
        agents, reservations = _provision_agents(plan, fleet)
        assert "code_gen" in agents
        assert ("code_gen", "gpu-1") in reservations

    def test_records_all_feasible_assignments(self):
        fleet = _fleet()
        plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        agents, reservations = _provision_agents(plan, fleet)
        assert len(agents) == 2
        assert len(reservations) == 2

    def test_skips_unavailable_member(self):
        fleet = _fleet()
        plan = _plan([("code_gen", "nonexistent-member")])
        agents, reservations = _provision_agents(plan, fleet)
        assert len(agents) == 0

    def test_mode_2_gated_by_threshold(self):
        """Mode 2 only activates when confidence > tau_2 (§3.4)."""
        assert select_mode(0.1, tau_2=0.3, tau_3=0.7) == 1  # below -> no provisioning
        assert select_mode(0.5, tau_2=0.3, tau_3=0.7) == 2  # above -> provisioning

    def test_no_fleet_mutation(self):
        """Pre-dispatch must be read-only — Fleet state unchanged."""
        fleet = _fleet()
        members_before = [(m.member_id, m.compute) for m in fleet.members]
        plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        _provision_agents(plan, fleet)
        members_after = [(m.member_id, m.compute) for m in fleet.members]
        assert members_before == members_after

    def test_threshold_formula(self):
        """§3.4: Mode 2 profitable when p > tau_2 iff E[sigma]*C_s > C_2."""
        # This is a structural test: verify the threshold gates Mode 2
        tau_2 = 0.4
        assert select_mode(0.39, tau_2=tau_2, tau_3=0.9) == 1
        assert select_mode(0.41, tau_2=tau_2, tau_3=0.9) == 2


# ===== Task 6: Mode 3 — Draft Execution =====


class TestDraftExecute:
    def test_produces_output(self):
        plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        output, agent_type = _draft_execute(plan, _intent())
        assert len(output) > 0
        assert len(agent_type) > 0

    def test_selects_first_stage_agent(self):
        plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        # code_gen has order=0, review has order=1
        _, agent_type = _draft_execute(plan, _intent())
        assert agent_type == "code_gen"

    def test_mode_3_gated_by_threshold(self):
        """Mode 3 only activates when confidence > tau_3 (§3.4)."""
        assert select_mode(0.5, tau_2=0.3, tau_3=0.7) == 2  # below tau_3
        assert select_mode(0.9, tau_2=0.3, tau_3=0.7) == 3  # above tau_3

    def test_subsumes_mode_2(self):
        """Mode 3 includes all Mode 2 work (progressive activation)."""
        # If mode >= 3, mode >= 2 is also true
        assert select_mode(0.9, tau_2=0.3, tau_3=0.7) >= 2

    def test_threshold_formula(self):
        """§3.4: Mode 3 profitable when p > tau_3 iff E[sigma]*C_s > C_3."""
        tau_3 = 0.8
        assert select_mode(0.79, tau_2=0.3, tau_3=tau_3) < 3
        assert select_mode(0.81, tau_2=0.3, tau_3=tau_3) == 3


# ===== Task 7: SpeculativeDispatcher Integration =====


class TestSpeculativeDispatcher:
    def test_speculate_returns_speculation_result(self):
        sd = SpeculativeDispatcher(_fleet())
        result = sd.speculate(_intent())
        assert isinstance(result, SpeculationResult)

    def test_cold_start_mode_1(self):
        """No cache → Mode 1, cache_hit=False, empty draft plan."""
        sd = SpeculativeDispatcher(_fleet())
        result = sd.speculate(_intent())
        assert result.mode == 1
        assert result.cache_hit is False
        assert len(result.draft_plan.assignments) == 0

    def test_mode_2_activation(self):
        """With high-enough confidence, Mode 2 activates and provisions agents."""
        sd = SpeculativeDispatcher(_fleet(), tau_2=0.3, tau_3=0.7)
        intent = _intent()
        plan = _plan([("code_gen", "gpu-1")])
        # Seed cache and build confidence
        sd.cache.store(intent, plan)
        for _ in range(5):
            sd.tracker.record_outcome(intent, hit=True)
        result = sd.speculate(intent)
        assert result.mode >= 2
        assert result.cache_hit is True
        assert len(result.manifest.agents_provisioned) > 0

    def test_mode_3_activation(self):
        """With very high confidence, Mode 3 activates and produces draft output."""
        sd = SpeculativeDispatcher(_fleet(), tau_2=0.3, tau_3=0.7)
        intent = _intent()
        plan = _plan([("code_gen", "gpu-1")])
        sd.cache.store(intent, plan)
        for _ in range(10):
            sd.tracker.record_outcome(intent, hit=True)
        result = sd.speculate(intent)
        assert result.mode == 3
        assert len(result.manifest.draft_output) > 0
        assert result.manifest.draft_agent_type == "code_gen"

    def test_mode_hierarchy(self):
        """Higher modes subsume lower modes — context always prepared."""
        sd = SpeculativeDispatcher(_fleet(), tau_2=0.3, tau_3=0.7)
        intent = _intent()
        sd.cache.store(intent, _plan([("code_gen", "gpu-1")]))
        for _ in range(10):
            sd.tracker.record_outcome(intent, hit=True)
        result = sd.speculate(intent)
        # Mode 3 → context_prepared is non-empty (Mode 1 work)
        assert len(result.manifest.context_prepared) > 0
        # Mode 3 → agents_provisioned is non-empty (Mode 2 work)
        assert len(result.manifest.agents_provisioned) > 0
        # Mode 3 → draft_output is non-empty (Mode 3 work)
        assert len(result.manifest.draft_output) > 0

    def test_cache_updated_on_record_outcome(self):
        sd = SpeculativeDispatcher(_fleet())
        intent = _intent()
        solver_plan = _plan([("review", "cpu-1")])
        sd.record_outcome(intent, solver_plan, "COMMIT")
        assert sd.cache.lookup(intent) == solver_plan

    def test_confidence_updated_on_record_outcome(self):
        sd = SpeculativeDispatcher(_fleet())
        intent = _intent()
        sd.record_outcome(intent, _plan(), "COMMIT")
        assert sd.tracker.confidence(intent) == 1.0
        sd.record_outcome(intent, _plan(), "FLUSH")
        assert sd.tracker.confidence(intent) == pytest.approx(0.5)

    def test_independence_from_solver(self):
        """speculate() must never call DispatchSolver.solve()."""
        # Structural: SpeculativeDispatcher has no reference to DispatchSolver
        sd = SpeculativeDispatcher(_fleet())
        assert not hasattr(sd, '_solver')

    def test_confidence_fn_override(self):
        """Learner can inject custom confidence function."""
        sd = SpeculativeDispatcher(
            _fleet(), tau_2=0.3, tau_3=0.7,
            confidence_fn=lambda _: 0.9,
        )
        intent = _intent()
        sd.cache.store(intent, _plan([("code_gen", "gpu-1")]))
        result = sd.speculate(intent)
        assert result.confidence == 0.9
        assert result.mode == 3

    def test_compatible_with_comparison(self):
        """Draft plan from speculator can be compared with solver plan."""
        sd = SpeculativeDispatcher(_fleet())
        intent = _intent()
        solver_plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        sd.cache.store(intent, solver_plan)
        result = sd.speculate(intent)
        # comparison functions accept DispatchPlan
        verdict = plan_match(solver_plan, result.draft_plan)
        assert verdict in ("COMMIT", "PARTIAL", "FLUSH")
        overlap = plan_overlap(solver_plan, result.draft_plan)
        assert 0.0 <= overlap <= 1.0


# ===== Task 8: Integration Tests =====


class TestIntegration:
    def test_progressive_activation_lifecycle(self):
        """Cold start → Mode 1 → Mode 2 → Mode 3 as confidence builds."""
        fleet = _fleet()
        sd = SpeculativeDispatcher(fleet, tau_2=0.3, tau_3=0.7)
        intent = _intent()
        solver_plan = _plan([("code_gen", "gpu-1")])

        # Cold start: Mode 1
        r1 = sd.speculate(intent)
        assert r1.mode == 1
        assert r1.cache_hit is False

        # Record outcomes to build confidence
        sd.record_outcome(intent, solver_plan, "COMMIT")

        # After 1 hit (conf=1.0), cache is seeded → Mode 3
        r2 = sd.speculate(intent)
        assert r2.cache_hit is True
        assert r2.mode == 3  # 1.0 > 0.7

        # Record a miss to lower confidence
        sd.record_outcome(intent, solver_plan, "FLUSH")
        # conf = 1/2 = 0.5 → Mode 2
        r3 = sd.speculate(intent)
        assert r3.mode == 2

        # Record more misses
        sd.record_outcome(intent, solver_plan, "FLUSH")
        # conf = 1/3 ≈ 0.33 → Mode 2 (just above 0.3)
        r4 = sd.speculate(intent)
        assert r4.mode == 2

        sd.record_outcome(intent, solver_plan, "FLUSH")
        # conf = 1/4 = 0.25 → Mode 1
        r5 = sd.speculate(intent)
        assert r5.mode == 1

    def test_cross_intent_independence(self):
        """Different task types have independent caches and confidence."""
        fleet = _fleet()
        sd = SpeculativeDispatcher(fleet, tau_2=0.3, tau_3=0.7)
        i1 = _intent("hpc_code_gen")
        i2 = _intent("research_writing")

        # Build confidence only for i1
        solver_plan = _plan([("code_gen", "gpu-1")])
        for _ in range(5):
            sd.record_outcome(i1, solver_plan, "COMMIT")

        r1 = sd.speculate(i1)
        r2 = sd.speculate(i2)

        assert r1.mode == 3  # high confidence
        assert r2.mode == 1  # no history

    def test_end_to_end_speculation_reconciliation(self):
        """Full loop: speculate → solver produces P* → compare → record."""
        fleet = _fleet()
        sd = SpeculativeDispatcher(fleet, tau_2=0.3, tau_3=0.7)
        intent = _intent()

        # Seed with a known plan
        known_plan = _plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        sd.cache.store(intent, known_plan)
        for _ in range(5):
            sd.tracker.record_outcome(intent, hit=True)

        # Speculate
        spec_result = sd.speculate(intent)
        assert spec_result.cache_hit is True

        # "Solver" produces same plan (simulated)
        solver_plan = known_plan
        verdict = plan_match(solver_plan, spec_result.draft_plan)
        overlap = plan_overlap(solver_plan, spec_result.draft_plan)

        assert verdict == "COMMIT"
        assert overlap == pytest.approx(1.0)

        # Record outcome
        sd.record_outcome(intent, solver_plan, verdict)
        assert sd.tracker.confidence(intent) > 0.8
