"""Tests for plan comparison — derived from §3.3 reconciliation logic.

Traceability:
- COMMIT when P* = P_hat: §3.3
- PARTIAL COMMIT when P* ∩ P_hat ≠ ∅, P* ≠ P_hat: §3.3
- FLUSH when P* ∩ P_hat = ∅: §3.3
- Salvage ratio σ = |P* ∩ P_hat| / |P_hat|: §3.3
"""

import pytest
from pythia.contracts import AgentAssignment, DispatchPlan
from pythia.comparison import plan_match, plan_overlap


def make_plan(assignments: list[tuple[str, str]]) -> DispatchPlan:
    """Helper: create plan from (agent_type, fleet_member_id) pairs."""
    return DispatchPlan(
        assignments=[
            AgentAssignment(agent_type=at, fleet_member_id=fm,
                            allocated_tokens=1000, prompt="stub", order=i)
            for i, (at, fm) in enumerate(assignments)
        ],
        execution_order=[[at for at, _ in assignments]],
        total_budget=len(assignments) * 1000,
        total_estimated_latency=0.5,
    )


class TestPlanMatch:
    def test_identical_plans_yield_commit(self):
        """§3.3: P* = P_hat → COMMIT. All pre-executed work accepted."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        assert plan_match(p_star, p_hat) == "COMMIT"

    def test_partial_overlap_yields_partial_commit(self):
        """§3.3: P* ∩ P_hat ≠ ∅, P* ≠ P_hat → PARTIAL COMMIT."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cloud-1")])
        assert plan_match(p_star, p_hat) == "PARTIAL"

    def test_no_overlap_yields_flush(self):
        """§3.3: P* ∩ P_hat = ∅ → FLUSH. All speculative work discarded."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("analysis", "cloud-1"), ("planner", "cloud-2")])
        assert plan_match(p_star, p_hat) == "FLUSH"

    def test_empty_speculative_plan_yields_flush(self):
        """Empty speculation has nothing to salvage."""
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([])
        assert plan_match(p_star, p_hat) == "FLUSH"

    def test_superset_speculation_yields_partial(self):
        """Speculation has extra agents not in optimal → PARTIAL."""
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        assert plan_match(p_star, p_hat) == "PARTIAL"


class TestPlanOverlap:
    def test_salvage_ratio_computed_correctly(self):
        """§3.3: σ = |P* ∩ P_hat| / |P_hat|."""
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cloud-1")])
        # 1 match out of 2 speculative assignments
        assert plan_overlap(p_star, p_hat) == pytest.approx(0.5)

    def test_full_overlap(self):
        p_star = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        p_hat = make_plan([("code_gen", "gpu-1"), ("review", "cpu-1")])
        assert plan_overlap(p_star, p_hat) == pytest.approx(1.0)

    def test_no_overlap(self):
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([("analysis", "cloud-1")])
        assert plan_overlap(p_star, p_hat) == pytest.approx(0.0)

    def test_empty_speculative_plan_overlap_is_zero(self):
        p_star = make_plan([("code_gen", "gpu-1")])
        p_hat = make_plan([])
        assert plan_overlap(p_star, p_hat) == pytest.approx(0.0)

    def test_partial_overlap_ratio(self):
        """3 speculative assignments, 2 match → σ = 2/3."""
        p_star = make_plan([
            ("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-1"),
        ])
        p_hat = make_plan([
            ("code_gen", "gpu-1"), ("review", "cpu-1"), ("analysis", "cloud-2"),
        ])
        assert plan_overlap(p_star, p_hat) == pytest.approx(2.0 / 3.0)
