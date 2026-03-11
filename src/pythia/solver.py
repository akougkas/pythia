"""Dispatch Solver — the "target" in draft-target speculation (§3.1).

Computes optimal dispatch plan P* given complete system state.
Its latency L_s is the bottleneck that speculation hides.

Architecture:
- AgentSelector: maps Intent -> list[AgentSpec] (rule-based)
- DispatchSolver: assigns agents to fleet members under constraints (greedy)

Objective: minimize alpha * latency + (1 - alpha) * cost (§3.4, §6.4)

Traceability:
- §3.1: Solver produces DispatchPlan
- §3.5: Constraint formulation (capacity, budget, rate limit, affinity)
- §6.4: Pareto frontier via alpha tuning
"""

from __future__ import annotations

from pythia.contracts import (
    AgentAssignment,
    AgentSpec,
    DispatchPlan,
    Intent,
)
from pythia.fleet import Fleet


# --- Agent Selection (Task 2) ---

# Rule-based agent pipeline templates by task type.
# Each entry maps task_type -> list of (agent_type, compute, memory, tokens, priority)
_AGENT_PIPELINES: dict[str, list[tuple[str, float, float, int, int]]] = {
    "hpc_code_gen": [
        ("planner", 10.0, 4.0, 500, 0),
        ("code_gen", 30.0, 16.0, 4000, 1),
        ("review", 15.0, 8.0, 2000, 2),
    ],
    "scientific_data_pipeline": [
        ("planner", 10.0, 4.0, 500, 0),
        ("analysis", 20.0, 8.0, 3000, 1),
        ("code_gen", 25.0, 12.0, 3000, 1),
        ("review", 15.0, 8.0, 2000, 2),
    ],
    "research_writing": [
        ("planner", 10.0, 4.0, 500, 0),
        ("analysis", 20.0, 8.0, 3000, 1),
        ("review", 15.0, 8.0, 2000, 2),
    ],
}

# Default single-agent fallback
_DEFAULT_AGENT = ("code_gen", 15.0, 8.0, 2000, 0)


class AgentSelector:
    """Maps intents to required agent sets — rule-based (§5.1, §6.1)."""

    def select_agents(self, intent: Intent) -> list[AgentSpec]:
        """Select agents for an intent based on task_type and complexity."""
        pipeline = _AGENT_PIPELINES.get(intent.task_type)

        if pipeline is None:
            # Simple/unknown task -> single agent
            t, c, m, tok, p = _DEFAULT_AGENT
            return [AgentSpec(t, c, m, tok, [], p)]

        # For low complexity, simplify pipeline to single agent
        if intent.complexity < 0.3:
            t, c, m, tok, p = _DEFAULT_AGENT
            return [AgentSpec(t, c, m, tok, [], p)]

        return [
            AgentSpec(agent_type, compute, memory, tokens, [], priority)
            for agent_type, compute, memory, tokens, priority in pipeline
        ]

    def compute_execution_dag(
        self, agents: list[AgentSpec]
    ) -> list[list[str]]:
        """Compute execution DAG as topologically ordered stages.

        Agents with the same priority execute in parallel (same stage).
        Lower priority number = earlier stage.
        """
        stages: dict[int, list[str]] = {}
        for agent in agents:
            stages.setdefault(agent.priority, []).append(agent.agent_type)
        return [stages[k] for k in sorted(stages.keys())]


# --- Core Solver (Task 3) ---


class DispatchSolver:
    """Constraint-aware dispatch solver — greedy assignment (§3.1, §3.5).

    Objective: minimize alpha * latency + (1-alpha) * cost - affinity_bonus
    for each agent-to-fleet-member assignment.

    Args:
        fleet: Fleet instance with current state
        agent_selector: AgentSelector for intent-to-agents mapping
        alpha: Latency vs cost tradeoff. 1.0 = pure latency, 0.0 = pure cost.
    """

    def __init__(
        self, fleet: Fleet, agent_selector: AgentSelector, alpha: float = 0.5
    ) -> None:
        self._fleet = fleet
        self._selector = agent_selector
        self._alpha = alpha

    def solve(self, intent: Intent, budget: int) -> DispatchPlan:
        """Produce optimal dispatch plan P* for the given intent (§3.1).

        Greedy: for each agent (by priority), score all available fleet
        members and pick the best that doesn't violate constraints.

        Resets fleet state before solving so the solver is reusable.
        """
        self._fleet.reset()
        agents = self._selector.select_agents(intent)
        dag = self._selector.compute_execution_dag(agents)
        assignments = self._optimize_assignment(agents, budget)

        total_tokens = sum(a.allocated_tokens for a in assignments)
        total_latency = self._estimate_latency(assignments, dag)

        return DispatchPlan(
            assignments=assignments,
            execution_order=dag,
            total_budget=total_tokens,
            total_estimated_latency=total_latency,
        )

    def _optimize_assignment(
        self, agents: list[AgentSpec], budget: int
    ) -> list[AgentAssignment]:
        """Greedy constraint-aware assignment (§3.5).

        For each agent by priority:
        1. Find available fleet members (capability + capacity + rate limit)
        2. Score each candidate
        3. Pick best that doesn't blow budget
        """
        assignments: list[AgentAssignment] = []
        remaining_budget = budget

        # Sort by priority (lower = first)
        sorted_agents = sorted(agents, key=lambda a: a.priority)

        for agent in sorted_agents:
            candidates = self._fleet.available_members_for(agent)
            if not candidates:
                continue

            # Filter by rate limit
            candidates = [
                m for m in candidates
                if self._fleet.check_rate_limit(m.member_id)
            ]
            if not candidates:
                continue

            # Score and rank candidates (normalized)
            scored = self._rank_candidates(agent, candidates)
            scored.sort(key=lambda x: x[1])  # lower score = better

            # Pick best candidate that fits budget
            for member, _score in scored:
                tokens = min(agent.estimated_tokens, remaining_budget)
                if tokens <= 0:
                    break

                assignment = AgentAssignment(
                    agent_type=agent.agent_type,
                    fleet_member_id=member.member_id,
                    allocated_tokens=tokens,
                    prompt=f"[stub] Execute {agent.agent_type} task",
                    order=agent.priority,
                )

                # Verify budget constraint with this addition
                trial = assignments + [assignment]
                if not self._fleet.check_budget(trial, budget):
                    continue

                # Reserve and commit
                self._fleet.reserve(assignment, agent)
                assignments.append(assignment)
                remaining_budget -= tokens
                break

        return assignments

    def _rank_candidates(
        self, agent: AgentSpec, candidates: list
    ) -> list[tuple]:
        """Score and rank candidates with min-max normalization.

        Normalizes latency and cost to [0, 1] across candidates before
        combining with alpha. This ensures the tradeoff is meaningful
        regardless of raw scale differences.

        Score = alpha * norm_latency + (1-alpha) * norm_cost - affinity_bonus
        """
        if len(candidates) == 1:
            affinity = self._fleet.check_affinity(
                candidates[0].member_id, agent
            )
            return [(candidates[0], 0.0 - affinity * 0.1)]

        latencies = [m.latency for m in candidates]
        costs = [m.cost_rate * agent.estimated_tokens for m in candidates]

        lat_min, lat_max = min(latencies), max(latencies)
        cost_min, cost_max = min(costs), max(costs)
        lat_range = lat_max - lat_min if lat_max > lat_min else 1.0
        cost_range = cost_max - cost_min if cost_max > cost_min else 1.0

        scored = []
        for m in candidates:
            norm_lat = (m.latency - lat_min) / lat_range
            norm_cost = (m.cost_rate * agent.estimated_tokens - cost_min) / cost_range
            affinity = self._fleet.check_affinity(m.member_id, agent)
            affinity_bonus = affinity * 0.1
            score = (
                self._alpha * norm_lat
                + (1 - self._alpha) * norm_cost
                - affinity_bonus
            )
            scored.append((m, score))
        return scored

    def _estimate_latency(
        self,
        assignments: list[AgentAssignment],
        dag: list[list[str]],
    ) -> float:
        """Estimate total plan latency from DAG structure.

        Parallel stages: take max latency within stage.
        Sequential stages: sum across stages.
        """
        if not assignments:
            return 0.0

        assignment_map = {a.agent_type: a for a in assignments}
        total = 0.0

        for stage in dag:
            stage_max = 0.0
            for agent_type in stage:
                if agent_type in assignment_map:
                    a = assignment_map[agent_type]
                    member = self._fleet.get_member(a.fleet_member_id)
                    stage_max = max(stage_max, member.latency)
            total += stage_max

        return total
