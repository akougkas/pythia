"""Tests for data contracts — derived from §3.1, §5.1 paper claims.

Traceability:
- Intent fields: §5.1 (task classification, complexity, domain tags)
- FleetMember fields: §3.5 (fleet capability vector)
- AgentSpec fields: §3.5 (agent resource requirements)
- DispatchPlan structure: §3.1, §5.1 (agents, execution_order, budget)
"""

import pytest
from dataclasses import asdict
from pythia.contracts import (
    Intent,
    FleetMember,
    AgentSpec,
    AgentAssignment,
    DispatchPlan,
)


# --- Intent ---


class TestIntent:
    def test_construction(self):
        intent = Intent(
            task_type="hpc_code_gen",
            complexity=0.8,
            domain_tags=["hpc", "mpi"],
            decomposability=0.6,
            constraints={"max_tokens": 4096},
        )
        assert intent.task_type == "hpc_code_gen"
        assert intent.complexity == 0.8
        assert intent.domain_tags == ["hpc", "mpi"]

    def test_complexity_must_be_in_unit_interval(self):
        with pytest.raises(ValueError, match="complexity"):
            Intent(
                task_type="test",
                complexity=1.5,
                domain_tags=[],
                decomposability=0.5,
            )

    def test_complexity_lower_bound(self):
        with pytest.raises(ValueError, match="complexity"):
            Intent(
                task_type="test",
                complexity=-0.1,
                domain_tags=[],
                decomposability=0.5,
            )

    def test_decomposability_must_be_in_unit_interval(self):
        with pytest.raises(ValueError, match="decomposability"):
            Intent(
                task_type="test",
                complexity=0.5,
                domain_tags=[],
                decomposability=1.1,
            )

    def test_default_constraints_is_empty(self):
        intent = Intent(
            task_type="test",
            complexity=0.5,
            domain_tags=[],
            decomposability=0.5,
        )
        assert intent.constraints == {}

    def test_serialization_roundtrip(self):
        intent = Intent(
            task_type="hpc_code_gen",
            complexity=0.8,
            domain_tags=["hpc"],
            decomposability=0.6,
            constraints={"max_tokens": 4096},
        )
        d = asdict(intent)
        restored = Intent(**d)
        assert restored == intent


# --- FleetMember ---


class TestFleetMember:
    def test_construction(self):
        fm = FleetMember(
            member_id="gpu-node-1",
            compute=100.0,
            memory=64.0,
            rate_limit=10,
            token_budget=100_000,
            cost_rate=0.05,
            latency=0.1,
            capabilities=["code_gen", "analysis"],
            affinity_tags=["gpu", "local"],
        )
        assert fm.member_id == "gpu-node-1"
        assert fm.compute == 100.0
        assert fm.capabilities == ["code_gen", "analysis"]

    def test_negative_compute_rejected(self):
        with pytest.raises(ValueError, match="compute"):
            FleetMember(
                member_id="bad",
                compute=-1.0,
                memory=64.0,
                rate_limit=10,
                token_budget=100_000,
                cost_rate=0.05,
                latency=0.1,
                capabilities=[],
                affinity_tags=[],
            )

    def test_serialization_roundtrip(self):
        fm = FleetMember(
            member_id="node-1",
            compute=50.0,
            memory=32.0,
            rate_limit=5,
            token_budget=50_000,
            cost_rate=0.02,
            latency=0.2,
            capabilities=["analysis"],
            affinity_tags=["cpu"],
        )
        d = asdict(fm)
        restored = FleetMember(**d)
        assert restored == fm


# --- AgentSpec ---


class TestAgentSpec:
    def test_construction(self):
        agent = AgentSpec(
            agent_type="code_gen",
            required_compute=20.0,
            required_memory=8.0,
            estimated_tokens=2000,
            compatible_fleet=["gpu-node-1", "cloud-1"],
            priority=1,
        )
        assert agent.agent_type == "code_gen"
        assert agent.priority == 1

    def test_empty_compatible_fleet_allowed(self):
        """Agent with no fleet restriction can run anywhere."""
        agent = AgentSpec(
            agent_type="simple",
            required_compute=1.0,
            required_memory=1.0,
            estimated_tokens=100,
            compatible_fleet=[],
            priority=0,
        )
        assert agent.compatible_fleet == []


# --- AgentAssignment ---


class TestAgentAssignment:
    def test_construction(self):
        assignment = AgentAssignment(
            agent_type="code_gen",
            fleet_member_id="gpu-node-1",
            allocated_tokens=2000,
            prompt="Generate MPI code for...",
            order=0,
        )
        assert assignment.agent_type == "code_gen"
        assert assignment.fleet_member_id == "gpu-node-1"
        assert assignment.order == 0


# --- DispatchPlan ---


class TestDispatchPlan:
    def test_construction(self):
        assignments = [
            AgentAssignment("code_gen", "gpu-1", 2000, "prompt1", 0),
            AgentAssignment("reviewer", "cpu-1", 1000, "prompt2", 1),
        ]
        plan = DispatchPlan(
            assignments=assignments,
            execution_order=[["code_gen"], ["reviewer"]],
            total_budget=5000,
            total_estimated_latency=1.5,
        )
        assert len(plan.assignments) == 2
        assert plan.total_budget == 5000

    def test_empty_plan(self):
        plan = DispatchPlan(
            assignments=[],
            execution_order=[],
            total_budget=0,
            total_estimated_latency=0.0,
        )
        assert len(plan.assignments) == 0

    def test_serialization_roundtrip(self):
        assignments = [
            AgentAssignment("code_gen", "gpu-1", 2000, "prompt1", 0),
        ]
        plan = DispatchPlan(
            assignments=assignments,
            execution_order=[["code_gen"]],
            total_budget=2000,
            total_estimated_latency=0.5,
        )
        d = asdict(plan)
        restored = DispatchPlan(
            assignments=[AgentAssignment(**a) for a in d["assignments"]],
            execution_order=d["execution_order"],
            total_budget=d["total_budget"],
            total_estimated_latency=d["total_estimated_latency"],
        )
        assert restored == plan
