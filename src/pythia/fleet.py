"""Fleet model and constraint checking — §3.5.

Separate from Solver to allow reuse by Reconciliation Engine.
Manages mutable fleet state (capacity reservations, rate limit tracking).

Traceability:
- Fleet capability vector: §3.5
- Capacity constraints: §3.5 (assignment_j <= capacity_i)
- Budget constraints: §3.5 (sum tokens <= budget)
- Rate limits: §3.5 (dispatch_rate <= rate_limit_provider)
- Affinity: §3.5 (infrastructure matching)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pythia.contracts import AgentAssignment, AgentSpec, FleetMember


@dataclass
class _MemberState:
    """Mutable tracking of a fleet member's available resources."""

    available_compute: float
    available_memory: float
    active_requests: int


class Fleet:
    """Heterogeneous fleet F = {f_1, ..., f_n} with constraint checking (§3.5)."""

    def __init__(self, members: list[FleetMember]) -> None:
        self._members: dict[str, FleetMember] = {m.member_id: m for m in members}
        self._state: dict[str, _MemberState] = {
            m.member_id: _MemberState(
                available_compute=m.compute,
                available_memory=m.memory,
                active_requests=0,
            )
            for m in members
        }

    def get_member(self, member_id: str) -> FleetMember:
        return self._members[member_id]

    @property
    def members(self) -> list[FleetMember]:
        return list(self._members.values())

    # --- Constraint checks (§3.5) ---

    def check_capacity(self, member_id: str, agent: AgentSpec) -> bool:
        """§3.5 capacity constraint: agent must fit within available compute and memory."""
        state = self._state[member_id]
        return (
            agent.required_compute <= state.available_compute
            and agent.required_memory <= state.available_memory
        )

    def check_budget(
        self, assignments: list[AgentAssignment], budget_limit: int
    ) -> bool:
        """§3.5 budget constraint: total tokens must not exceed budget."""
        total_tokens = sum(a.allocated_tokens for a in assignments)
        return total_tokens <= budget_limit

    def check_rate_limit(
        self, member_id: str, additional_requests: int = 1
    ) -> bool:
        """§3.5 rate limit constraint: active requests must not exceed member limit."""
        member = self._members[member_id]
        state = self._state[member_id]
        return (state.active_requests + additional_requests) <= member.rate_limit

    def check_affinity(self, member_id: str, agent: AgentSpec) -> float:
        """§3.5 affinity scoring: score based on tag overlap between agent and member.

        Returns fraction of member's affinity tags that match agent's type.
        Agents with matching infrastructure tags score higher.
        """
        member = self._members[member_id]
        if not member.affinity_tags:
            return 0.0
        # Score based on whether the agent type appears in affinity tags
        # plus any overlap between agent compatible_fleet hints and member tags
        matches = 0
        for tag in member.affinity_tags:
            if tag in agent.agent_type:
                matches += 1
        return matches / len(member.affinity_tags)

    def available_members_for(self, agent: AgentSpec) -> list[FleetMember]:
        """Filter fleet to members that can run this agent.

        Checks: capability match, compatible_fleet restriction, capacity.
        """
        result = []
        for member_id, member in self._members.items():
            # Compatible fleet restriction
            if agent.compatible_fleet and member_id not in agent.compatible_fleet:
                continue
            # Capability check: agent_type must be in member capabilities
            if agent.agent_type not in member.capabilities:
                continue
            # Capacity check
            if not self.check_capacity(member_id, agent):
                continue
            result.append(member)
        return result

    # --- Mutable state management ---

    def reserve(self, assignment: AgentAssignment, agent: AgentSpec) -> None:
        """Reserve resources on a fleet member for an assignment."""
        state = self._state[assignment.fleet_member_id]
        state.available_compute -= agent.required_compute
        state.available_memory -= agent.required_memory
        state.active_requests += 1

    def release(self, assignment: AgentAssignment, agent: AgentSpec) -> None:
        """Release resources on a fleet member after an assignment completes."""
        state = self._state[assignment.fleet_member_id]
        state.available_compute += agent.required_compute
        state.available_memory += agent.required_memory
        state.active_requests -= 1

    def reset(self) -> None:
        """Reset all fleet state to initial capacity."""
        for member_id, member in self._members.items():
            self._state[member_id] = _MemberState(
                available_compute=member.compute,
                available_memory=member.memory,
                active_requests=0,
            )
