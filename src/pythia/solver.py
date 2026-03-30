"""Dispatch Solver — the "target" in draft-target speculation (§3.1).

Computes optimal dispatch plan P* given complete system state.
Its latency L_s is the bottleneck that speculation hides.

Architecture:
- AgentSelector: maps Intent -> list[AgentSpec] (rule-based, fast fallback)
- LLMAgentSelector: uses LLM to analyze request and select agents (slow, realistic)
- DispatchSolver: assigns agents to fleet members under constraints (greedy)

Objective: minimize alpha * latency + (1 - alpha) * cost (§3.4, §6.4)

Traceability:
- §3.1: Solver produces DispatchPlan
- §3.5: Constraint formulation (capacity, budget, rate limit, affinity)
- §6.4: Pareto frontier via alpha tuning
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request

from pythia.contracts import (
    AgentAssignment,
    AgentSpec,
    DispatchPlan,
    Intent,
)
from pythia.fleet import Fleet

_log = logging.getLogger(__name__)


# --- Agent Selection (Task 2) ---

# Rule-based agent pipeline templates by task type.
# Each entry maps task_type -> list of (agent_type, compute, memory, tokens, priority)
_AGENT_PIPELINES: dict[str, list[tuple[str, float, float, int, int]]] = {
    "hpc_code_gen": [
        ("planner", 10.0, 4.0, 500, 0),
        ("code_gen", 30.0, 16.0, 4000, 1),
        ("tester", 20.0, 8.0, 1500, 2),
        ("review", 15.0, 8.0, 2000, 3),
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
    "data_pipeline": [
        ("data_discovery", 10.0, 4.0, 500, 0),
        ("data_wrangler", 20.0, 8.0, 2000, 1),
        ("analyst", 25.0, 12.0, 3000, 2),
        ("reporter", 15.0, 4.0, 1500, 3),
    ],
    "research_workflow": [
        ("literature_reviewer", 10.0, 4.0, 1000, 0),
        ("experiment_designer", 15.0, 8.0, 1500, 1),
        ("code_generator", 30.0, 16.0, 4000, 2),
        ("experiment_runner", 25.0, 12.0, 3000, 3),
        ("result_analyzer", 15.0, 8.0, 2000, 4),
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


# --- LLM-Based Agent Selector (§5.1) ---

# Resource profiles for known agent types
_AGENT_RESOURCES: dict[str, tuple[float, float, int]] = {
    # agent_type: (compute, memory, estimated_tokens)
    "planner": (10.0, 4.0, 500),
    "code_gen": (30.0, 16.0, 4000),
    "tester": (20.0, 8.0, 1500),
    "review": (15.0, 8.0, 2000),
    "data_discovery": (10.0, 4.0, 500),
    "data_wrangler": (20.0, 8.0, 2000),
    "analyst": (25.0, 12.0, 3000),
    "reporter": (15.0, 4.0, 1500),
    "literature_reviewer": (10.0, 4.0, 1000),
    "experiment_designer": (15.0, 8.0, 1500),
    "code_generator": (30.0, 16.0, 4000),
    "experiment_runner": (25.0, 12.0, 3000),
    "result_analyzer": (15.0, 8.0, 2000),
}

_LLM_SELECTOR_PROMPT = """\
You are the Dispatch Solver for Pythia, a multi-agent orchestration system \
for scientific computing. Your job is to analyze a user request and produce \
a dispatch plan — deciding which specialist agents to launch, what each \
should do, and how they depend on each other.

AVAILABLE AGENT ROLES (use ONLY these names):
  planner           — algorithm design, strategy, decomposition (light compute)
  code_gen          — implementation, code writing (heavy compute)
  tester            — test generation, validation (medium compute)
  review            — code review, quality scoring (light compute)
  data_discovery    — find and assess data sources (light compute)
  data_wrangler     — clean, transform, join data (medium compute)
  analyst           — statistical analysis, computation (heavy compute)
  reporter          — summarize findings, produce answer (light compute)
  literature_reviewer  — understand papers, extract methods (light compute)
  experiment_designer  — design replication experiments (medium compute)
  code_generator       — research code implementation (heavy compute)
  experiment_runner    — execute experiments, collect results (medium compute)
  result_analyzer      — compare results, score quality (light compute)

GUIDELINES (not rigid rules — adapt to the request):
- Match the number of agents to ACTUAL task complexity:
  * Simple (single function, clear spec) → 1-2 agents
  * Medium (multi-step, needs testing) → 3-4 agents
  * Complex (deployment, multi-stage pipeline, research workflow) → 4-6+ agents
- Identify stages that can run in PARALLEL (no mutual dependency)
- For each agent, write a prompt SPECIFIC to THIS request — not generic
- compute_weight reflects how much LLM compute the agent needs:
  * "light" — short output, planning/review (~500 tokens)
  * "medium" — moderate output, testing/analysis (~1500 tokens)
  * "heavy" — long output, code generation (~4000 tokens)

Respond with ONLY a JSON object:
{
  "reasoning": "2-3 sentences: why this decomposition, what is complex/simple, \
which stages are parallel",
  "agents": [
    {
      "name": "agent_role_from_list_above",
      "role": "one-line description of what this agent does for THIS request",
      "prompt": "Specific, detailed instruction for this agent",
      "depends_on": ["other_agent_name_or_empty"],
      "estimated_tokens": 500,
      "compute_weight": "light"
    }
  ]
}\
"""


class LLMAgentSelector:
    """LLM-based agent selector — uses an LLM to analyze the request (§5.1).

    This is the REALISTIC version of AgentSelector. Instead of a dict lookup,
    it calls an LLM to decide which agents are needed based on the request
    content. This makes the Solver genuinely slow (1-5s per call), which is
    what the Speculator is designed to hide.

    Supports two providers:
    - "ollama": local models via Ollama HTTP API
    - "claude": Claude models via Agent SDK (no API key, uses Claude Code session)

    Falls back to rule-based AgentSelector on LLM failure.
    """

    def __init__(
        self,
        model: str = "llama3.1:8b",
        provider: str = "ollama",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._provider = provider
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._fallback = AgentSelector()
        self.last_call_time_ms: float = 0.0  # observable for metrics
        self.last_raw_response: str = ""  # raw LLM output for inspection
        self.last_parsed_agents: list[str] = []  # parsed agent names
        self.last_reasoning: str = ""  # LLM's reasoning
        self.last_agent_prompts: dict[str, str] = {}
        self.last_agent_details: list[dict] = []
        self.last_agent_depends: dict[str, list[str]] = {}
        self.last_agent_weights: dict[str, str] = {}
        self.last_agent_roles: dict[str, str] = {}

    def select_agents(self, intent: Intent, request_text: str = "") -> list[AgentSpec]:
        """Select agents using LLM analysis of the request.

        Args:
            intent: Classified intent from IntentDetector
            request_text: Original request text for LLM context

        Returns:
            List of AgentSpec with resource requirements
        """
        t0 = time.perf_counter()
        # Try LLM twice before falling back to rule-based
        last_err = None
        for attempt in range(2):
            try:
                agents = self._select_via_llm(intent, request_text)
                self.last_call_time_ms = (time.perf_counter() - t0) * 1000
                return agents
            except Exception as e:
                last_err = e
                _log.warning("LLM agent selection attempt %d failed (%s)", attempt + 1, e)
                if attempt == 0:
                    time.sleep(1)  # brief pause before retry
        _log.warning("LLM agent selection failed after 2 attempts, falling back to rule-based")
        self.last_call_time_ms = (time.perf_counter() - t0) * 1000
        return self._fallback.select_agents(intent)

    def _select_via_llm(self, intent: Intent, request_text: str) -> list[AgentSpec]:
        """Call LLM to decide which agents are needed."""
        user_msg = (
            f"Request: {request_text}\n\n"
            f"Intent classification: task_type={intent.task_type}, "
            f"complexity={intent.complexity:.2f}, "
            f"domain_tags={intent.domain_tags}, "
            f"decomposability={intent.decomposability:.2f}"
        )

        if self._provider == "claude":
            raw_text = self._call_claude(user_msg)
        else:
            raw_text = self._call_ollama(user_msg)

        self.last_raw_response = raw_text
        agents = self._parse_response(raw_text, intent)
        self.last_parsed_agents = [a.agent_type for a in agents]
        return agents

    def _call_ollama(self, user_msg: str) -> str:
        """Call Ollama API."""
        payload = json.dumps({
            "model": self._model,
            "messages": [
                {"role": "system", "content": _LLM_SELECTOR_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read())

        return body["message"]["content"]

    def _call_claude(self, user_msg: str) -> str:
        """Call Claude via Agent SDK (no API key needed)."""
        import anyio
        from claude_agent_sdk import query, AssistantMessage, TextBlock, ClaudeAgentOptions

        full_prompt = f"{_LLM_SELECTOR_PROMPT}\n\n{user_msg}"

        async def _run():
            text = ""
            async for message in query(
                prompt=full_prompt,
                options=ClaudeAgentOptions(model=self._model),
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text += block.text
            return text

        try:
            return anyio.from_thread.run(_run)
        except RuntimeError:
            return anyio.run(_run)

    def _parse_response(self, text: str, intent: Intent) -> list[AgentSpec]:
        """Parse LLM response into AgentSpec list.

        Supports formats:
        - Detailed: {"agents": [{"name": "...", "prompt": "...", "depends_on": [...], ...}]}
        - Simple:   {"agents": ["agent1", "agent2"]}
        """
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip()

        # Find JSON — use greedy match for nested objects
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in LLM response: {text[:200]}")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            # Try finding a simpler JSON block
            match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
            if not match:
                raise ValueError(f"Cannot parse JSON from: {text[:200]}")
            data = json.loads(match.group())

        self.last_reasoning = data.get("reasoning", "")
        agent_list = data.get("agents", [])

        if not agent_list or not isinstance(agent_list, list):
            raise ValueError(f"Invalid agents list: {agent_list}")

        # Store per-agent details from LLM
        self.last_agent_prompts: dict[str, str] = {}
        self.last_agent_details: list[dict] = []
        self.last_agent_depends: dict[str, list[str]] = {}
        self.last_agent_weights: dict[str, str] = {}
        self.last_agent_roles: dict[str, str] = {}

        specs = []
        for i, item in enumerate(agent_list):
            if isinstance(item, dict):
                name = item.get("name", "").strip().lower()
                prompt = item.get("prompt", "")
                est_tokens = item.get("estimated_tokens", 0)
                depends = item.get("depends_on", [])
                weight = item.get("compute_weight", "medium")
                role = item.get("role", "")
                # Clean depends_on — filter empty strings and self-references
                depends = [d.strip().lower() for d in depends if d and d.strip().lower() != name]
                self.last_agent_prompts[name] = prompt
                self.last_agent_depends[name] = depends
                self.last_agent_weights[name] = weight
                self.last_agent_roles[name] = role
                self.last_agent_details.append({
                    "name": name, "prompt": prompt, "role": role,
                    "depends_on": depends, "estimated_tokens": est_tokens,
                    "compute_weight": weight,
                })
            elif isinstance(item, str):
                name = item.strip().lower()
                self.last_agent_details.append({
                    "name": name, "prompt": "", "role": "",
                    "depends_on": [], "estimated_tokens": 0,
                    "compute_weight": "medium",
                })
            else:
                continue

            if name not in _AGENT_RESOURCES:
                _log.warning("Unknown agent type from LLM: %r, skipping", name)
                continue
            compute, memory, tokens = _AGENT_RESOURCES[name]
            specs.append(AgentSpec(name, compute, memory, tokens, [], i))

        if not specs:
            raise ValueError("LLM returned no valid agent types")

        return specs

    def compute_execution_dag(self, agents: list[AgentSpec]) -> list[list[str]]:
        """Build execution DAG from depends_on relationships.

        If depends_on info is available (from LLM), use topological sort.
        Otherwise fall back to priority-based ordering.
        """
        agent_names = [a.agent_type for a in agents]

        # Check if we have depends_on data
        if self.last_agent_depends:
            return self._dag_from_depends(agent_names)

        # Fallback: priority-based (same as rule-based selector)
        return AgentSelector().compute_execution_dag(agents)

    def _dag_from_depends(self, agent_names: list[str]) -> list[list[str]]:
        """Topological sort of agents using depends_on relationships.

        Agents with no dependencies go in stage 0 (can run in parallel).
        Agents depending only on stage-0 agents go in stage 1, etc.
        """
        # Filter depends_on to only reference agents in this plan
        name_set = set(agent_names)
        deps: dict[str, set[str]] = {}
        for name in agent_names:
            raw = self.last_agent_depends.get(name, [])
            deps[name] = {d for d in raw if d in name_set}

        stages: list[list[str]] = []
        placed: set[str] = set()
        remaining = set(agent_names)

        while remaining:
            # Find agents whose dependencies are all placed
            ready = [n for n in remaining if deps[n].issubset(placed)]
            if not ready:
                # Cycle or unresolvable — dump remaining into last stage
                stages.append(sorted(remaining))
                break
            stages.append(sorted(ready))
            placed.update(ready)
            remaining -= set(ready)

        return stages


# --- Core Solver (Task 3) ---


class DispatchSolver:
    """Constraint-aware dispatch solver — greedy assignment (§3.1, §3.5).

    Objective: minimize alpha * latency + (1-alpha) * cost - affinity_bonus
    for each agent-to-fleet-member assignment.

    Args:
        fleet: Fleet instance with current state
        agent_selector: AgentSelector or LLMAgentSelector
        alpha: Latency vs cost tradeoff. 1.0 = pure latency, 0.0 = pure cost.
    """

    def __init__(
        self,
        fleet: Fleet,
        agent_selector: AgentSelector | LLMAgentSelector,
        alpha: float = 0.5,
    ) -> None:
        self._fleet = fleet
        self._selector = agent_selector
        self._alpha = alpha
        self.last_solve_time_ms: float = 0.0  # observable for metrics

    def solve(self, intent: Intent, budget: int, request_text: str = "") -> DispatchPlan:
        """Produce optimal dispatch plan P* for the given intent (§3.1).

        Greedy: for each agent (by priority), score all available fleet
        members and pick the best that doesn't violate constraints.

        Resets fleet state before solving so the solver is reusable.
        """
        t0 = time.perf_counter()
        self._fleet.reset()

        # LLMAgentSelector needs request_text; AgentSelector ignores it
        if isinstance(self._selector, LLMAgentSelector):
            agents = self._selector.select_agents(intent, request_text)
        else:
            agents = self._selector.select_agents(intent)
        dag = self._selector.compute_execution_dag(agents)

        # Get LLM-generated details if available
        agent_prompts: dict[str, str] = {}
        agent_weights: dict[str, str] = {}
        agent_depends: dict[str, list[str]] = {}
        agent_roles: dict[str, str] = {}
        reasoning = ""
        if isinstance(self._selector, LLMAgentSelector):
            agent_prompts = getattr(self._selector, 'last_agent_prompts', {})
            agent_weights = getattr(self._selector, 'last_agent_weights', {})
            agent_depends = getattr(self._selector, 'last_agent_depends', {})
            agent_roles = getattr(self._selector, 'last_agent_roles', {})
            reasoning = getattr(self._selector, 'last_reasoning', '')

        assignments = self._optimize_assignment(
            agents, budget, agent_prompts, agent_weights, agent_depends, agent_roles,
        )

        total_tokens = sum(a.allocated_tokens for a in assignments)
        total_latency = self._estimate_latency(assignments, dag)

        plan = DispatchPlan(
            assignments=assignments,
            execution_order=dag,
            total_budget=total_tokens,
            total_estimated_latency=total_latency,
            reasoning=reasoning,
        )
        self.last_solve_time_ms = (time.perf_counter() - t0) * 1000
        return plan

    def _optimize_assignment(
        self, agents: list[AgentSpec], budget: int,
        agent_prompts: dict[str, str] | None = None,
        agent_weights: dict[str, str] | None = None,
        agent_depends: dict[str, list[str]] | None = None,
        agent_roles: dict[str, str] | None = None,
    ) -> list[AgentAssignment]:
        """Greedy constraint-aware assignment (§3.5).

        For each agent by priority:
        1. Find available fleet members (capability + capacity + rate limit)
        2. Score each candidate
        3. Pick best that doesn't blow budget

        Uses LLM-generated prompts, weights, and roles when available.
        """
        agent_prompts = agent_prompts or {}
        agent_weights = agent_weights or {}
        agent_depends = agent_depends or {}
        agent_roles = agent_roles or {}
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

                prompt = agent_prompts.get(
                    agent.agent_type,
                    f"[stub] Execute {agent.agent_type} task"
                )
                weight = agent_weights.get(agent.agent_type, "medium")
                deps = tuple(agent_depends.get(agent.agent_type, []))
                role = agent_roles.get(agent.agent_type, "")

                assignment = AgentAssignment(
                    agent_type=agent.agent_type,
                    fleet_member_id=member.member_id,
                    allocated_tokens=tokens,
                    prompt=prompt,
                    order=agent.priority,
                    compute_weight=weight,
                    depends_on=deps,
                    role=role,
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
