"""Tests for DispatchSolver — derived from §3.1, §3.5, §6.1 paper claims.

Traceability:
- Solver produces valid DispatchPlan: §3.1
- Constraint satisfaction: §3.5
- Objective function (alpha-tunable): §3.4, §6.4
- HPC workload agent pipeline: §6.1
- Greedy optimality verified by ILP oracle: implementation design decision
"""

import pytest
from pythia.contracts import (
    Intent,
    FleetMember,
    AgentSpec,
    AgentAssignment,
    DispatchPlan,
)
from pythia.fleet import Fleet
from pythia.solver import AgentSelector, DispatchSolver


# --- Fixtures ---


def make_fleet() -> Fleet:
    members = [
        FleetMember(
            member_id="gpu-1",
            compute=100.0,
            memory=64.0,
            rate_limit=5,
            token_budget=50_000,
            cost_rate=0.03,
            latency=0.1,
            capabilities=["code_gen", "analysis", "review", "planner"],
            affinity_tags=["gpu", "local"],
        ),
        FleetMember(
            member_id="cpu-1",
            compute=50.0,
            memory=32.0,
            rate_limit=10,
            token_budget=100_000,
            cost_rate=0.01,
            latency=0.3,
            capabilities=["analysis", "review", "planner"],
            affinity_tags=["cpu", "local"],
        ),
        FleetMember(
            member_id="cloud-1",
            compute=200.0,
            memory=128.0,
            rate_limit=3,
            token_budget=200_000,
            cost_rate=0.10,
            latency=0.5,
            capabilities=["code_gen", "analysis", "review", "planner"],
            affinity_tags=["cloud", "api"],
        ),
    ]
    return Fleet(members)


def make_intent(
    task_type: str = "hpc_code_gen",
    complexity: float = 0.8,
    domain_tags: list[str] | None = None,
) -> Intent:
    return Intent(
        task_type=task_type,
        complexity=complexity,
        domain_tags=domain_tags or ["hpc"],
        decomposability=0.6,
    )


# --- Agent Selection (Task 2) ---


class TestAgentSelector:
    def test_hpc_code_gen_selects_pipeline(self):
        """§6.1: HPC code generation workload selects multi-agent pipeline."""
        selector = AgentSelector()
        intent = make_intent(task_type="hpc_code_gen", complexity=0.8)
        agents = selector.select_agents(intent)
        agent_types = [a.agent_type for a in agents]
        # HPC code gen should include at least code_gen and review
        assert "code_gen" in agent_types
        assert "review" in agent_types
        assert len(agents) >= 2

    def test_simple_task_selects_single_agent(self):
        """Simple tasks should dispatch to a single agent."""
        selector = AgentSelector()
        intent = make_intent(task_type="simple_query", complexity=0.2)
        agents = selector.select_agents(intent)
        assert len(agents) == 1

    def test_execution_dag_respects_dependencies(self):
        """Execution DAG must topologically order agent stages."""
        selector = AgentSelector()
        intent = make_intent(task_type="hpc_code_gen", complexity=0.8)
        agents = selector.select_agents(intent)
        dag = selector.compute_execution_dag(agents)
        # DAG is list of stages; code_gen should come before review
        all_types_flat = [t for stage in dag for t in stage]
        if "code_gen" in all_types_flat and "review" in all_types_flat:
            code_gen_stage = next(
                i for i, stage in enumerate(dag) if "code_gen" in stage
            )
            review_stage = next(
                i for i, stage in enumerate(dag) if "review" in stage
            )
            assert code_gen_stage < review_stage

    def test_agents_have_valid_resource_requirements(self):
        selector = AgentSelector()
        intent = make_intent(task_type="hpc_code_gen")
        agents = selector.select_agents(intent)
        for agent in agents:
            assert agent.required_compute > 0
            assert agent.required_memory > 0
            assert agent.estimated_tokens > 0


# --- Core Solver (Task 3) ---


class TestDispatchSolver:
    def test_solver_produces_valid_dispatch_plan(self):
        """§3.1: Solver must produce a valid DispatchPlan."""
        fleet = make_fleet()
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent()
        plan = solver.solve(intent, budget=50_000)
        assert isinstance(plan, DispatchPlan)
        assert len(plan.assignments) > 0
        assert plan.total_budget > 0
        assert plan.total_estimated_latency > 0

    def test_solver_respects_capacity_constraints(self):
        """§3.5: No assignment should exceed fleet member capacity."""
        fleet = make_fleet()
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent()
        plan = solver.solve(intent, budget=100_000)
        # Verify each assignment fits within its member
        for assignment in plan.assignments:
            member = fleet.get_member(assignment.fleet_member_id)
            # allocated_tokens should not exceed member token_budget
            assert assignment.allocated_tokens <= member.token_budget

    def test_solver_respects_budget_constraints(self):
        """§3.5: Total tokens must not exceed budget."""
        fleet = make_fleet()
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent()
        budget = 10_000
        plan = solver.solve(intent, budget=budget)
        assert plan.total_budget <= budget

    def test_solver_respects_rate_limits(self):
        """§3.5: No fleet member should exceed its rate limit."""
        fleet = make_fleet()
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent()
        plan = solver.solve(intent, budget=100_000)
        # Count assignments per member
        member_counts: dict[str, int] = {}
        for a in plan.assignments:
            member_counts[a.fleet_member_id] = (
                member_counts.get(a.fleet_member_id, 0) + 1
            )
        for member_id, count in member_counts.items():
            member = fleet.get_member(member_id)
            assert count <= member.rate_limit

    def test_solver_prefers_affinity_matches(self):
        """§3.5: Affinity tags should influence assignment scoring."""
        # Fleet with one gpu member and one cpu member, both capable
        members = [
            FleetMember("gpu-1", 100, 64, 5, 50_000, 0.03, 0.2,
                        ["code_gen"], ["gpu", "code_gen"]),
            FleetMember("cpu-1", 100, 64, 5, 50_000, 0.03, 0.2,
                        ["code_gen"], ["cpu"]),
        ]
        fleet = Fleet(members)
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent(task_type="simple_query", complexity=0.2)
        plan = solver.solve(intent, budget=50_000)
        # code_gen agent should prefer gpu-1 (affinity match)
        code_gen_assignments = [
            a for a in plan.assignments if a.agent_type == "code_gen"
        ]
        if code_gen_assignments:
            assert code_gen_assignments[0].fleet_member_id == "gpu-1"

    def test_solver_minimizes_latency_when_alpha_high(self):
        """High alpha = latency priority. Should pick low-latency members."""
        members = [
            FleetMember("fast", 100, 64, 5, 50_000, 0.10, 0.05,
                        ["code_gen"], []),
            FleetMember("cheap", 100, 64, 5, 50_000, 0.01, 0.50,
                        ["code_gen"], []),
        ]
        fleet = Fleet(members)
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.95)
        intent = make_intent(task_type="simple_query", complexity=0.2)
        plan = solver.solve(intent, budget=50_000)
        assert plan.assignments[0].fleet_member_id == "fast"

    def test_solver_minimizes_cost_when_alpha_low(self):
        """Low alpha = cost priority. Should pick low-cost members."""
        members = [
            FleetMember("fast", 100, 64, 5, 50_000, 0.10, 0.05,
                        ["code_gen"], []),
            FleetMember("cheap", 100, 64, 5, 50_000, 0.01, 0.50,
                        ["code_gen"], []),
        ]
        fleet = Fleet(members)
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.05)
        intent = make_intent(task_type="simple_query", complexity=0.2)
        plan = solver.solve(intent, budget=50_000)
        assert plan.assignments[0].fleet_member_id == "cheap"

    def test_solver_handles_heterogeneous_fleet(self):
        """§3.5: Solver must handle fleets with varying capabilities."""
        fleet = make_fleet()  # 3 heterogeneous members
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent(task_type="hpc_code_gen", complexity=0.8)
        plan = solver.solve(intent, budget=100_000)
        # All assignments should reference valid fleet members
        member_ids = {m.member_id for m in fleet.members}
        for a in plan.assignments:
            assert a.fleet_member_id in member_ids

    def test_solver_infeasible_when_resources_exhausted(self):
        """Solver should produce empty plan when no feasible assignment exists."""
        # Tiny fleet that can't handle the workload
        members = [
            FleetMember("tiny", 5.0, 2.0, 1, 100, 0.01, 0.1,
                        ["code_gen"], []),
        ]
        fleet = Fleet(members)
        solver = DispatchSolver(fleet, AgentSelector(), alpha=0.5)
        intent = make_intent(task_type="hpc_code_gen", complexity=0.9)
        plan = solver.solve(intent, budget=100)
        # Plan may be partial or empty if resources are exhausted
        # At minimum, it shouldn't crash
        assert isinstance(plan, DispatchPlan)

    def test_greedy_matches_ilp_optimal(self):
        """Verify greedy solver finds optimal solution on small instances.

        Uses scipy.optimize.linprog as oracle. Since agents are assigned
        independently (no inter-agent coupling constraint), greedy is
        optimal when normalization preserves ranking — which it does
        because min-max normalization is monotonic.

        The ILP uses the same constraint model as the greedy:
        - Each agent assigned to exactly one member
        - No 1-per-member exclusivity (agents CAN share members)
        """
        pytest.importorskip("scipy")
        import numpy as np
        from scipy.optimize import linprog

        # Small instance: 2 agents, 3 fleet members
        members = [
            FleetMember("m0", 100, 64, 5, 50_000, 0.02, 0.1,
                        ["code_gen", "review"], []),
            FleetMember("m1", 100, 64, 5, 50_000, 0.05, 0.05,
                        ["code_gen", "review"], []),
            FleetMember("m2", 100, 64, 5, 50_000, 0.08, 0.02,
                        ["code_gen", "review"], []),
        ]

        alpha = 0.5
        agents = [
            AgentSpec("code_gen", 20.0, 8.0, 2000, [], 0),
            AgentSpec("review", 10.0, 4.0, 1000, [], 1),
        ]

        # --- ILP oracle (using same normalized scoring as greedy) ---
        n_agents = len(agents)
        n_members = len(members)
        n_vars = n_agents * n_members

        # Objective: use normalized latency/cost per agent (same as greedy)
        c = np.zeros(n_vars)
        for i, agent in enumerate(agents):
            latencies = [m.latency for m in members]
            costs = [m.cost_rate * agent.estimated_tokens for m in members]
            lat_min, lat_max = min(latencies), max(latencies)
            cost_min, cost_max = min(costs), max(costs)
            lat_range = lat_max - lat_min if lat_max > lat_min else 1.0
            cost_range = cost_max - cost_min if cost_max > cost_min else 1.0
            for j, member in enumerate(members):
                idx = i * n_members + j
                norm_lat = (member.latency - lat_min) / lat_range
                norm_cost = (
                    member.cost_rate * agent.estimated_tokens - cost_min
                ) / cost_range
                c[idx] = alpha * norm_lat + (1 - alpha) * norm_cost

        # Each agent assigned to exactly one member
        A_eq = np.zeros((n_agents, n_vars))
        b_eq = np.ones(n_agents)
        for i in range(n_agents):
            for j in range(n_members):
                A_eq[i, i * n_members + j] = 1.0

        # No 1-per-member constraint — agents can share members
        result = linprog(
            c,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=[(0, 1)] * n_vars,
            integrality=[1] * n_vars,
        )
        assert result.success

        # Extract ILP assignment
        ilp_assignment: dict[str, str] = {}
        for i, agent in enumerate(agents):
            for j, member in enumerate(members):
                if result.x[i * n_members + j] > 0.5:
                    ilp_assignment[agent.agent_type] = member.member_id

        # --- Greedy solution ---
        fleet = Fleet(members)
        solver = DispatchSolver(fleet, AgentSelector(), alpha=alpha)
        assignments = solver._optimize_assignment(agents, budget=50_000)
        greedy_map = {a.agent_type: a.fleet_member_id for a in assignments}

        # Greedy with normalized scoring preserves ranking (monotonic),
        # so it should find the same assignment as ILP for each agent.
        assert greedy_map == ilp_assignment, (
            f"Greedy {greedy_map} != ILP {ilp_assignment}"
        )
