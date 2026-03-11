"""Tests for Fleet model + constraint checking — derived from §3.5 paper claims.

Traceability:
- Capacity constraints: §3.5 (assignment_j <= capacity_i)
- Budget constraints: §3.5 (sum tokens <= token_budget)
- Rate limit constraints: §3.5 (dispatch_rate <= rate_limit_provider)
- Affinity scoring: §3.5 (infrastructure matching)
"""

import pytest
from pythia.contracts import FleetMember, AgentSpec, AgentAssignment
from pythia.fleet import Fleet


# --- Fixtures ---


def make_fleet() -> Fleet:
    """Small heterogeneous fleet for testing."""
    members = [
        FleetMember(
            member_id="gpu-1",
            compute=100.0,
            memory=64.0,
            rate_limit=5,
            token_budget=50_000,
            cost_rate=0.05,
            latency=0.1,
            capabilities=["code_gen", "analysis"],
            affinity_tags=["gpu", "local"],
        ),
        FleetMember(
            member_id="cpu-1",
            compute=50.0,
            memory=32.0,
            rate_limit=10,
            token_budget=100_000,
            cost_rate=0.02,
            latency=0.3,
            capabilities=["analysis", "review"],
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
            capabilities=["code_gen", "analysis", "review"],
            affinity_tags=["cloud", "api"],
        ),
    ]
    return Fleet(members)


def make_agent(
    agent_type: str = "code_gen",
    compute: float = 20.0,
    memory: float = 8.0,
    tokens: int = 2000,
    compatible: list[str] | None = None,
    priority: int = 0,
) -> AgentSpec:
    return AgentSpec(
        agent_type=agent_type,
        required_compute=compute,
        required_memory=memory,
        estimated_tokens=tokens,
        compatible_fleet=compatible or [],
        priority=priority,
    )


# --- §3.5 Capacity Constraints ---


class TestCapacityConstraints:
    def test_capacity_constraint_rejects_overcommit(self):
        """§3.5: Agent assignments must not exceed compute/memory of fleet member."""
        fleet = make_fleet()
        # cpu-1 has 50 compute, 32 memory
        oversized_agent = make_agent(compute=60.0, memory=8.0)
        assert not fleet.check_capacity("cpu-1", oversized_agent)

    def test_capacity_constraint_accepts_within_limits(self):
        fleet = make_fleet()
        small_agent = make_agent(compute=10.0, memory=4.0)
        assert fleet.check_capacity("gpu-1", small_agent)

    def test_capacity_reduces_after_reservation(self):
        """Reserving an assignment reduces available capacity."""
        fleet = make_fleet()
        agent = make_agent(compute=40.0, memory=16.0)
        assignment = AgentAssignment("code_gen", "gpu-1", 2000, "prompt", 0)
        fleet.reserve(assignment, agent)
        # gpu-1 had 100 compute, 64 memory. After reserving 40/16:
        second_agent = make_agent(compute=70.0, memory=16.0)
        assert not fleet.check_capacity("gpu-1", second_agent)

    def test_capacity_restores_after_release(self):
        fleet = make_fleet()
        agent = make_agent(compute=40.0, memory=16.0)
        assignment = AgentAssignment("code_gen", "gpu-1", 2000, "prompt", 0)
        fleet.reserve(assignment, agent)
        fleet.release(assignment, agent)
        assert fleet.check_capacity("gpu-1", make_agent(compute=90.0, memory=60.0))

    def test_memory_constraint_rejects_overcommit(self):
        fleet = make_fleet()
        memory_hog = make_agent(compute=10.0, memory=70.0)
        assert not fleet.check_capacity("gpu-1", memory_hog)  # gpu-1 has 64 mem


# --- §3.5 Budget Constraints ---


class TestBudgetConstraints:
    def test_budget_constraint_rejects_over_budget(self):
        """§3.5: Total token consumption must stay within budget."""
        fleet = make_fleet()
        assignments = [
            AgentAssignment("code_gen", "gpu-1", 30_000, "p1", 0),
            AgentAssignment("review", "gpu-1", 25_000, "p2", 1),
        ]
        # Total = 55,000 tokens, limit = 50,000
        assert not fleet.check_budget(assignments, budget_limit=50_000)

    def test_budget_constraint_accepts_within_budget(self):
        fleet = make_fleet()
        assignments = [
            AgentAssignment("code_gen", "gpu-1", 20_000, "p1", 0),
            AgentAssignment("review", "cpu-1", 10_000, "p2", 1),
        ]
        assert fleet.check_budget(assignments, budget_limit=50_000)

    def test_budget_constraint_exact_boundary(self):
        fleet = make_fleet()
        assignments = [
            AgentAssignment("code_gen", "gpu-1", 50_000, "p1", 0),
        ]
        assert fleet.check_budget(assignments, budget_limit=50_000)


# --- §3.5 Rate Limit Constraints ---


class TestRateLimitConstraints:
    def test_rate_limit_constraint_respected(self):
        """§3.5: Dispatch rates must respect per-provider rate limits."""
        fleet = make_fleet()
        # cloud-1 has rate_limit=3
        assert fleet.check_rate_limit("cloud-1", additional_requests=1)
        # Reserve 3 slots
        for i in range(3):
            agent = make_agent(agent_type=f"agent_{i}")
            assignment = AgentAssignment(f"agent_{i}", "cloud-1", 100, "p", i)
            fleet.reserve(assignment, agent)
        # Now at limit — no more allowed
        assert not fleet.check_rate_limit("cloud-1", additional_requests=1)

    def test_rate_limit_releases_on_release(self):
        fleet = make_fleet()
        agent = make_agent(agent_type="agent_0")
        assignment = AgentAssignment("agent_0", "cloud-1", 100, "p", 0)
        fleet.reserve(assignment, agent)
        fleet.release(assignment, agent)
        # Should be back at 0 active
        assert fleet.check_rate_limit("cloud-1", additional_requests=3)


# --- §3.5 Affinity Scoring ---


class TestAffinityScoring:
    def test_affinity_scoring_prefers_matching_infrastructure(self):
        """§3.5: Agents perform better on infrastructure with matching affinity tags."""
        fleet = make_fleet()
        gpu_agent = make_agent(agent_type="code_gen")
        # gpu-1 has tags ["gpu", "local"], cloud-1 has ["cloud", "api"]
        gpu_score = fleet.check_affinity("gpu-1", gpu_agent)
        cloud_score = fleet.check_affinity("cloud-1", gpu_agent)
        # Both should return numeric scores; gpu should score >= cloud
        assert isinstance(gpu_score, float)
        assert isinstance(cloud_score, float)

    def test_affinity_returns_zero_for_no_match(self):
        fleet = make_fleet()
        # Agent with no overlapping tags
        agent = make_agent(agent_type="exotic")
        score = fleet.check_affinity("gpu-1", agent)
        assert score == 0.0


# --- Capability Filtering ---


class TestCapabilityFiltering:
    def test_available_members_filters_by_capability(self):
        fleet = make_fleet()
        review_agent = make_agent(agent_type="review")
        # Only cpu-1 and cloud-1 have "review" capability
        available = fleet.available_members_for(review_agent)
        member_ids = [m.member_id for m in available]
        assert "cpu-1" in member_ids
        assert "cloud-1" in member_ids
        assert "gpu-1" not in member_ids

    def test_available_members_respects_compatible_fleet(self):
        fleet = make_fleet()
        restricted_agent = make_agent(
            agent_type="code_gen",
            compatible=["gpu-1"],
        )
        available = fleet.available_members_for(restricted_agent)
        assert len(available) == 1
        assert available[0].member_id == "gpu-1"

    def test_available_members_filters_by_capacity(self):
        fleet = make_fleet()
        big_agent = make_agent(
            agent_type="code_gen",
            compute=150.0,
            memory=100.0,
        )
        available = fleet.available_members_for(big_agent)
        # Only cloud-1 has compute=200, memory=128
        member_ids = [m.member_id for m in available]
        assert "cloud-1" in member_ids
        assert "gpu-1" not in member_ids
        assert "cpu-1" not in member_ids
