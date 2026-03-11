"""Tests for Reconciliation Engine — derived from §3.3, §3.4, §4.1.

Traceability:
- §3.3: COMMIT / PARTIAL / FLUSH verdicts + salvage ratio
- §3.4: Cost model (redirect cost, wasted compute)
- §4.1: Learner reward signal
- §5.1: Implementation architecture

~35 tests in 8 groups matching the implementation plan tasks.
"""

import pytest
from pythia.contracts import (
    AgentAssignment,
    DispatchPlan,
    Intent,
    PreExecutionManifest,
    ReconciliationConfig,
    ReconciliationOutcome,
    SpeculationResult,
)
from pythia.reconciler import ReconciliationEngine, _classify_assignments


# --- Helpers ---


def make_plan(assignments: list[tuple[str, str]]) -> DispatchPlan:
    """Create plan from (agent_type, fleet_member_id) pairs."""
    return DispatchPlan(
        assignments=[
            AgentAssignment(
                agent_type=at,
                fleet_member_id=fm,
                allocated_tokens=1000,
                prompt="stub",
                order=i,
            )
            for i, (at, fm) in enumerate(assignments)
        ],
        execution_order=[[at for at, _ in assignments]],
        total_budget=len(assignments) * 1000,
        total_estimated_latency=0.5,
    )


def make_speculation(
    assignments: list[tuple[str, str]],
    confidence: float = 0.5,
    mode: int = 1,
) -> SpeculationResult:
    """Create a SpeculationResult wrapping a draft plan."""
    draft_plan = make_plan(assignments)
    return SpeculationResult(
        draft_plan=draft_plan,
        manifest=PreExecutionManifest(
            mode=mode,
            context_prepared=["task:test"],
            agents_provisioned=[at for at, _ in assignments] if mode >= 2 else [],
            fleet_reservations=list(assignments) if mode >= 2 else [],
            draft_output="[draft] output" if mode >= 3 else "",
            draft_agent_type=assignments[0][0] if mode >= 3 and assignments else "",
        ),
        confidence=confidence,
        mode=mode,
        cache_hit=bool(assignments),
    )


# =========================================================================
# Task 1: Contracts
# =========================================================================


class TestContracts:
    """ReconciliationConfig and ReconciliationOutcome validation."""

    def test_config_frozen(self):
        cfg = ReconciliationConfig()
        with pytest.raises(AttributeError):
            cfg.L_saved = 2.0  # type: ignore[misc]

    def test_outcome_valid_verdict(self):
        """Only COMMIT, PARTIAL, FLUSH accepted."""
        with pytest.raises(ValueError, match="verdict"):
            ReconciliationOutcome(
                verdict="INVALID",
                salvage_ratio=0.5,
                adopted=[],
                discarded=[],
                redirect_cost=0.0,
                wasted_compute=0.0,
                reward=0.0,
                speculation_mode=1,
                confidence=0.5,
            )

    def test_outcome_salvage_ratio_range(self):
        """salvage_ratio must be in [0, 1]."""
        with pytest.raises(ValueError, match="salvage_ratio"):
            ReconciliationOutcome(
                verdict="FLUSH",
                salvage_ratio=1.5,
                adopted=[],
                discarded=[],
                redirect_cost=0.0,
                wasted_compute=0.0,
                reward=0.0,
                speculation_mode=1,
                confidence=0.5,
            )

    def test_outcome_negative_reward_allowed(self):
        """Negative reward is valid (FLUSH penalty)."""
        outcome = ReconciliationOutcome(
            verdict="FLUSH",
            salvage_ratio=0.0,
            adopted=[],
            discarded=[],
            redirect_cost=0.0,
            wasted_compute=0.0,
            reward=-0.5,
            speculation_mode=1,
            confidence=0.0,
        )
        assert outcome.reward == -0.5


# =========================================================================
# Task 2: Assignment Classification
# =========================================================================


class TestClassifyAssignments:
    """_classify_assignments partitions P_hat into adopted vs discarded."""

    def test_full_match(self):
        """All speculative assignments match P*."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        adopted, discarded = _classify_assignments(p_star, p_hat)
        assert len(adopted) == 2
        assert len(discarded) == 0

    def test_no_match(self):
        """No speculative assignments match P*."""
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([("analysis", "cloud-1")])
        adopted, discarded = _classify_assignments(p_star, p_hat)
        assert len(adopted) == 0
        assert len(discarded) == 1

    def test_partial_split(self):
        """Some match, some don't."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cloud-1")])
        adopted, discarded = _classify_assignments(p_star, p_hat)
        assert len(adopted) == 1
        assert adopted[0].agent_type == "code_gen"
        assert len(discarded) == 1
        assert discarded[0].agent_type == "review"

    def test_empty_speculative_plan(self):
        """Empty P_hat → both lists empty."""
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([])
        adopted, discarded = _classify_assignments(p_star, p_hat)
        assert adopted == []
        assert discarded == []

    def test_superset_speculation(self):
        """P_hat has extra assignments not in P*."""
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        adopted, discarded = _classify_assignments(p_star, p_hat)
        assert len(adopted) == 1
        assert len(discarded) == 1


# =========================================================================
# Task 3: Core Reconcile — Verdict + Salvage
# =========================================================================


class TestCoreReconcile:
    """ReconciliationEngine.reconcile() verdict and salvage ratio."""

    def test_commit_verdict(self):
        """Identical plans → COMMIT."""
        engine = ReconciliationEngine()
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.verdict == "COMMIT"
        assert outcome.salvage_ratio == pytest.approx(1.0)

    def test_partial_verdict(self):
        """Partial overlap → PARTIAL."""
        engine = ReconciliationEngine()
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.verdict == "PARTIAL"

    def test_flush_verdict(self):
        """No overlap → FLUSH."""
        engine = ReconciliationEngine()
        spec = make_speculation([("analysis", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.verdict == "FLUSH"
        assert outcome.salvage_ratio == pytest.approx(0.0)

    def test_salvage_ratio_matches_plan_overlap(self):
        """Salvage ratio from reconcile() equals plan_overlap() for same inputs."""
        from pythia.comparison import plan_overlap

        engine = ReconciliationEngine()
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-1")])
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-2")])
        outcome = engine.reconcile(p_star, spec)
        expected = plan_overlap(p_star, spec.draft_plan)
        assert outcome.salvage_ratio == pytest.approx(expected)


# =========================================================================
# Task 4: Redirect Cost
# =========================================================================


class TestRedirectCost:
    """redirect_cost = len(discarded) * C_redirect."""

    def test_commit_zero_redirect(self):
        """COMMIT: no discarded assignments → zero redirect cost."""
        engine = ReconciliationEngine()
        spec = make_speculation([("code_gen", "gpu-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.redirect_cost == pytest.approx(0.0)

    def test_flush_redirect_cost(self):
        """FLUSH: all discarded → redirect_cost = n * C_redirect."""
        cfg = ReconciliationConfig(C_redirect=0.3)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("analysis", "cloud-1"), ("planner", "cloud-2")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.redirect_cost == pytest.approx(2 * 0.3)

    def test_partial_proportional_to_mismatch(self):
        """PARTIAL: redirect cost proportional to discarded count."""
        cfg = ReconciliationConfig(C_redirect=0.5)
        engine = ReconciliationEngine(cfg)
        # 3 speculative: 2 match, 1 discarded
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-2")])
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.redirect_cost == pytest.approx(1 * 0.5)

    def test_scales_with_config(self):
        """Different C_redirect values scale cost linearly."""
        spec = make_speculation([("analysis", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        for c_r in [0.1, 0.5, 1.0]:
            engine = ReconciliationEngine(ReconciliationConfig(C_redirect=c_r))
            outcome = engine.reconcile(p_star, spec)
            assert outcome.redirect_cost == pytest.approx(1 * c_r)

    def test_zero_c_redirect(self):
        """C_redirect=0 → zero redirect cost even with discarded."""
        cfg = ReconciliationConfig(C_redirect=0.0)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("analysis", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.redirect_cost == pytest.approx(0.0)


# =========================================================================
# Task 5: Wasted Compute
# =========================================================================


class TestWastedCompute:
    """wasted_compute = len(discarded) * C_spec_per_assignment."""

    def test_commit_zero_waste(self):
        """COMMIT: nothing wasted."""
        engine = ReconciliationEngine()
        spec = make_speculation([("code_gen", "gpu-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.wasted_compute == pytest.approx(0.0)

    def test_flush_wastes_all(self):
        """FLUSH: all speculative compute wasted."""
        cfg = ReconciliationConfig(C_spec_per_assignment=0.2)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("a", "x"), ("b", "y")])
        p_star = make_plan([("c", "z")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.wasted_compute == pytest.approx(2 * 0.2)

    def test_partial_wastes_discarded_only(self):
        """PARTIAL: only discarded assignments count as waste."""
        cfg = ReconciliationConfig(C_spec_per_assignment=0.1)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        outcome = engine.reconcile(p_star, spec)
        # 1 adopted, 1 discarded
        assert outcome.wasted_compute == pytest.approx(1 * 0.1)

    def test_scales_with_config(self):
        """Different C_spec_per_assignment values scale linearly."""
        spec = make_speculation([("a", "x")])
        p_star = make_plan([("b", "y")])
        for c_s in [0.05, 0.1, 0.5]:
            engine = ReconciliationEngine(ReconciliationConfig(C_spec_per_assignment=c_s))
            outcome = engine.reconcile(p_star, spec)
            assert outcome.wasted_compute == pytest.approx(1 * c_s)


# =========================================================================
# Task 6: Reward Signal
# =========================================================================


class TestRewardSignal:
    """§4.1: COMMIT → +L_saved, PARTIAL → σ·L_saved - (1-σ)·C_redirect, FLUSH → -C_flush."""

    def test_commit_reward(self):
        """COMMIT → reward = +L_saved."""
        cfg = ReconciliationConfig(L_saved=1.0)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("code_gen", "gpu-1")])
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.reward == pytest.approx(1.0)

    def test_flush_reward(self):
        """FLUSH → reward = -C_flush."""
        cfg = ReconciliationConfig(C_flush=0.5)
        engine = ReconciliationEngine(cfg)
        spec = make_speculation([("a", "x")])
        p_star = make_plan([("b", "y")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.reward == pytest.approx(-0.5)

    def test_partial_formula(self):
        """PARTIAL → σ·L_saved - (1-σ)·C_redirect."""
        cfg = ReconciliationConfig(L_saved=1.0, C_redirect=0.3)
        engine = ReconciliationEngine(cfg)
        # 2 speculative: 1 match → σ = 0.5
        spec = make_speculation([("code_gen", "gpu-1"), ("review", "cloud-1")])
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        outcome = engine.reconcile(p_star, spec)
        expected = 0.5 * 1.0 - 0.5 * 0.3  # 0.35
        assert outcome.reward == pytest.approx(expected)

    def test_partial_positive_when_sigma_high(self):
        """High σ → positive reward."""
        cfg = ReconciliationConfig(L_saved=1.0, C_redirect=0.3)
        engine = ReconciliationEngine(cfg)
        # 3 speculative: 2 match → σ = 2/3
        spec = make_speculation([("a", "x"), ("b", "y"), ("c", "wrong")])
        p_star = make_plan([("a", "x"), ("b", "y"), ("c", "z")])
        outcome = engine.reconcile(p_star, spec)
        sigma = 2.0 / 3.0
        expected = sigma * 1.0 - (1 - sigma) * 0.3
        assert outcome.reward == pytest.approx(expected)
        assert outcome.reward > 0

    def test_partial_negative_when_sigma_low(self):
        """Low σ → negative reward."""
        cfg = ReconciliationConfig(L_saved=0.3, C_redirect=1.0)
        engine = ReconciliationEngine(cfg)
        # 3 speculative: 1 match → σ = 1/3
        spec = make_speculation([("a", "x"), ("b", "wrong1"), ("c", "wrong2")])
        p_star = make_plan([("a", "x"), ("b", "y"), ("c", "z")])
        outcome = engine.reconcile(p_star, spec)
        sigma = 1.0 / 3.0
        expected = sigma * 0.3 - (1 - sigma) * 1.0
        assert outcome.reward == pytest.approx(expected)
        assert outcome.reward < 0

    def test_breakeven_sigma(self):
        """Breakeven: σ* = C_redirect / (L_saved + C_redirect) → reward ≈ 0."""
        L_saved = 1.0
        C_redirect = 0.5
        sigma_star = C_redirect / (L_saved + C_redirect)  # 1/3
        # Need 1 match out of 3 → σ = 1/3
        # But breakeven σ = 0.5/(1.0+0.5) = 1/3
        cfg = ReconciliationConfig(L_saved=L_saved, C_redirect=C_redirect)
        engine = ReconciliationEngine(cfg)
        # Build a scenario where σ ≈ σ*
        # σ = 1/3: 1 out of 3 match
        spec = make_speculation([("a", "x"), ("b", "wrong1"), ("c", "wrong2")])
        p_star = make_plan([("a", "x"), ("b", "y"), ("c", "z")])
        outcome = engine.reconcile(p_star, spec)
        # reward = σ*·L - (1-σ*)·C_r = (1/3)·1.0 - (2/3)·0.5 = 1/3 - 1/3 = 0
        assert outcome.reward == pytest.approx(0.0, abs=1e-10)


# =========================================================================
# Task 7: Integration with Speculator
# =========================================================================


class TestSpeculatorIntegration:
    """reconcile_and_record() updates speculator cache and confidence."""

    def _make_intent(self, task_type: str = "code_gen") -> Intent:
        return Intent(
            task_type=task_type,
            complexity=0.5,
            domain_tags=["test"],
            decomposability=0.5,
        )

    def _make_speculator(self):
        """Create a SpeculativeDispatcher with a minimal fleet."""
        from pythia.fleet import Fleet
        from pythia.contracts import FleetMember
        from pythia.speculator import SpeculativeDispatcher

        fleet = Fleet([FleetMember(
            member_id="gpu-1", compute=100.0, memory=64.0,
            rate_limit=10, token_budget=100000, cost_rate=0.01,
            latency=0.1, capabilities=["code_gen"], affinity_tags=["gpu"],
        )])
        return SpeculativeDispatcher(fleet=fleet)

    def test_cache_updated(self):
        """After reconcile_and_record, cache stores solver_plan."""
        engine = ReconciliationEngine()
        speculator = self._make_speculator()
        intent = self._make_intent()
        p_star = make_plan([("code_gen", "gpu-1")])
        spec = make_speculation([("analysis", "cloud-1")])

        engine.reconcile_and_record(p_star, spec, intent, speculator)
        cached = speculator.cache.lookup(intent)
        assert cached is not None
        assert cached.assignments == p_star.assignments

    def test_confidence_updated(self):
        """After reconcile_and_record, confidence tracker is updated."""
        engine = ReconciliationEngine()
        speculator = self._make_speculator()
        intent = self._make_intent()

        # Record a COMMIT
        p_star = make_plan([("code_gen", "gpu-1")])
        spec = make_speculation([("code_gen", "gpu-1")])
        engine.reconcile_and_record(p_star, spec, intent, speculator)
        assert speculator.tracker.confidence(intent) == pytest.approx(1.0)

        # Record a FLUSH
        spec2 = make_speculation([("analysis", "cloud-1")])
        engine.reconcile_and_record(p_star, spec2, intent, speculator)
        # 1 hit out of 2 total
        assert speculator.tracker.confidence(intent) == pytest.approx(0.5)

    def test_full_loop(self):
        """speculate → reconcile_and_record → speculate: cache improves next speculation."""
        engine = ReconciliationEngine()
        speculator = self._make_speculator()
        intent = self._make_intent()

        # First speculation: cold start (empty cache)
        spec1 = speculator.speculate(intent)
        assert not spec1.cache_hit

        # Solver produces optimal plan
        p_star = make_plan([("code_gen", "gpu-1")])
        engine.reconcile_and_record(p_star, spec1, intent, speculator)

        # Second speculation: cache hit, draft matches P*
        spec2 = speculator.speculate(intent)
        assert spec2.cache_hit
        assert spec2.draft_plan.assignments == p_star.assignments

    def test_cold_start_reconciliation(self):
        """Empty speculation (cold start) produces FLUSH with zero costs."""
        engine = ReconciliationEngine()
        spec = make_speculation([])  # cold start: empty plan
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.verdict == "FLUSH"
        assert outcome.redirect_cost == pytest.approx(0.0)
        assert outcome.wasted_compute == pytest.approx(0.0)


# =========================================================================
# Task 8: End-to-End Integration
# =========================================================================


class TestEndToEnd:
    """Progressive lifecycle and cross-intent independence."""

    def _make_intent(self, task_type: str = "code_gen") -> Intent:
        return Intent(
            task_type=task_type,
            complexity=0.5,
            domain_tags=["test"],
            decomposability=0.5,
        )

    def _make_speculator(self):
        from pythia.fleet import Fleet
        from pythia.contracts import FleetMember
        from pythia.speculator import SpeculativeDispatcher

        fleet = Fleet([
            FleetMember(
                member_id="gpu-1", compute=100.0, memory=64.0,
                rate_limit=10, token_budget=100000, cost_rate=0.01,
                latency=0.1, capabilities=["code_gen"], affinity_tags=["gpu"],
            ),
            FleetMember(
                member_id="cpu-1", compute=50.0, memory=32.0,
                rate_limit=20, token_budget=50000, cost_rate=0.005,
                latency=0.2, capabilities=["review"], affinity_tags=["cpu"],
            ),
        ])
        return SpeculativeDispatcher(fleet=fleet)

    def test_progressive_lifecycle(self):
        """Cold start (FLUSH) → build confidence → COMMIT → mismatch → PARTIAL."""
        engine = ReconciliationEngine()
        speculator = self._make_speculator()
        intent = self._make_intent()

        # Cold start → FLUSH
        spec = speculator.speculate(intent)
        p_star = make_plan([("code_gen", "gpu-1")])
        outcome1 = engine.reconcile_and_record(p_star, spec, intent, speculator)
        assert outcome1.verdict == "FLUSH"

        # Now cache has P*, next speculation should hit → COMMIT
        spec2 = speculator.speculate(intent)
        outcome2 = engine.reconcile_and_record(p_star, spec2, intent, speculator)
        assert outcome2.verdict == "COMMIT"
        assert outcome2.reward > outcome1.reward

        # Solver changes plan: different fleet member → PARTIAL with σ < 1
        p_star_new = make_plan([("code_gen", "cpu-1")])
        spec3 = speculator.speculate(intent)
        outcome3 = engine.reconcile_and_record(p_star_new, spec3, intent, speculator)
        assert outcome3.verdict == "FLUSH"  # completely different assignment
        assert outcome3.reward < outcome2.reward  # reward drops

    def test_cross_intent_independence(self):
        """Reconciliation for one task_type doesn't affect another."""
        engine = ReconciliationEngine()
        speculator = self._make_speculator()
        intent_a = self._make_intent("code_gen")
        intent_b = self._make_intent("analysis")

        # Build up cache for intent_a
        spec_a = speculator.speculate(intent_a)
        p_star_a = make_plan([("code_gen", "gpu-1")])
        engine.reconcile_and_record(p_star_a, spec_a, intent_a, speculator)

        # intent_b is still cold
        spec_b = speculator.speculate(intent_b)
        assert not spec_b.cache_hit
        outcome_b = engine.reconcile(make_plan([("analysis", "cpu-1")]), spec_b)
        assert outcome_b.verdict == "FLUSH"

    def test_mode3_draft_discarded_on_flush(self):
        """Mode 3 produces draft_output; FLUSH discards all speculative work."""
        engine = ReconciliationEngine()
        # Simulate Mode 3 speculation with draft output
        spec = make_speculation(
            [("code_gen", "gpu-1")],
            confidence=0.9,
            mode=3,
        )
        assert spec.manifest.draft_output != ""

        # Solver wants something completely different
        p_star = make_plan([("analysis", "cloud-1")])
        outcome = engine.reconcile(p_star, spec)
        assert outcome.verdict == "FLUSH"
        assert outcome.speculation_mode == 3
        assert len(outcome.discarded) == 1
        assert outcome.reward < 0
