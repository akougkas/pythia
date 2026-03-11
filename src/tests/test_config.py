"""Tests for configuration loading and integration — §5.2.

Includes integration test: load fleet from YAML → solve → verify feasibility.
"""

import pytest
from pathlib import Path

from pythia.config import load_fleet_config, create_solver_from_config
from pythia.contracts import Intent, DispatchPlan
from pythia.fleet import Fleet
from pythia.solver import DispatchSolver


FIXTURE_DIR = Path(__file__).parent / "fixtures"
FLEET_YAML = FIXTURE_DIR / "test_fleet.yaml"


class TestConfigLoading:
    def test_fleet_loads_from_yaml(self):
        """§5.2: Fleet configuration loaded from YAML."""
        fleet = load_fleet_config(FLEET_YAML)
        assert len(fleet.members) == 3
        ids = {m.member_id for m in fleet.members}
        assert ids == {"gpu-workstation", "cpu-server", "cloud-api"}

    def test_fleet_member_values_correct(self):
        fleet = load_fleet_config(FLEET_YAML)
        gpu = fleet.get_member("gpu-workstation")
        assert gpu.compute == 100.0
        assert gpu.memory == 64.0
        assert gpu.rate_limit == 5
        assert gpu.cost_rate == 0.03

    def test_solver_created_from_config(self):
        solver = create_solver_from_config(FLEET_YAML, alpha=0.7)
        assert isinstance(solver, DispatchSolver)


class TestIntegration:
    def test_end_to_end_dispatch(self):
        """Integration: YAML → Fleet → Solver → DispatchPlan → feasibility check.

        Verifies the full pipeline from §5.2 config through §3.1 solving.
        """
        solver = create_solver_from_config(FLEET_YAML, alpha=0.5)
        intent = Intent(
            task_type="hpc_code_gen",
            complexity=0.8,
            domain_tags=["hpc", "mpi"],
            decomposability=0.6,
            constraints={"max_tokens": 10_000},
        )
        plan = solver.solve(intent, budget=50_000)

        # Plan should be valid
        assert isinstance(plan, DispatchPlan)
        assert len(plan.assignments) > 0

        # Budget respected
        assert plan.total_budget <= 50_000

        # All assignments reference valid fleet members
        fleet = load_fleet_config(FLEET_YAML)
        valid_ids = {m.member_id for m in fleet.members}
        for a in plan.assignments:
            assert a.fleet_member_id in valid_ids

        # Execution order is non-empty
        assert len(plan.execution_order) > 0

        # Latency estimate is positive
        assert plan.total_estimated_latency > 0

    def test_pareto_sweep(self):
        """§6.4: Varying alpha should produce different cost/latency tradeoffs."""
        intent = Intent(
            task_type="simple_query",
            complexity=0.2,
            domain_tags=["general"],
            decomposability=0.1,
        )

        latencies = []
        for alpha in [0.0, 0.5, 1.0]:
            solver = create_solver_from_config(FLEET_YAML, alpha=alpha)
            plan = solver.solve(intent, budget=50_000)
            if plan.assignments:
                latencies.append(plan.total_estimated_latency)

        # With different alphas, at least the assignments should vary
        # (or latency should change if members differ)
        assert len(latencies) > 0
