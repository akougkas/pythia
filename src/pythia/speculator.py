"""Speculative Dispatcher — the "draft" model in draft-target speculation (§3.2).

Produces a draft DispatchPlan from historical cache, computes confidence,
and performs pre-execution work according to the active speculation mode.
Must be faster than the Solver by construction: cache lookup + lightweight
pre-execution vs. full constraint-based optimization.

Modes (§3.2, progressive activation):
- Mode 1: Context preparation only (always active)
- Mode 2: Agent pre-dispatch (confidence > tau_2)
- Mode 3: Draft execution (confidence > tau_3)

Traceability:
- §3.2: Speculation modes and progressive activation
- §3.4: Cost model thresholds tau_2, tau_3
- §5.1: Implementation architecture
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from pythia.contracts import (
    AgentAssignment,
    DispatchPlan,
    Intent,
    PreExecutionManifest,
    SpeculationResult,
)
from pythia.fleet import Fleet


# --- Intent fingerprinting ---


def _intent_key(intent: Intent) -> str:
    """Extract cache key from Intent. Coarsest useful fingerprint.

    Uses task_type alone; Learner can refine later.
    """
    return intent.task_type


# --- Dispatch Cache (Task 1) ---


class DispatchCache:
    """Per-task_type history buffer of past dispatch plans.

    FIFO eviction at max_history. Lookup returns most recent plan.
    """

    def __init__(self, max_history: int = 64) -> None:
        self._max_history = max_history
        self._store: dict[str, deque[DispatchPlan]] = {}

    def store(self, intent: Intent, plan: DispatchPlan) -> None:
        """Record a dispatch plan for the given intent's task type."""
        key = _intent_key(intent)
        if key not in self._store:
            self._store[key] = deque(maxlen=self._max_history)
        self._store[key].append(plan)

    def lookup(self, intent: Intent) -> DispatchPlan | None:
        """Return most recent plan for this intent's task type, or None."""
        key = _intent_key(intent)
        buf = self._store.get(key)
        if buf and len(buf) > 0:
            return buf[-1]
        return None

    def history_depth(self, intent: Intent) -> int:
        """Number of stored plans for this intent's task type."""
        key = _intent_key(intent)
        buf = self._store.get(key)
        return len(buf) if buf else 0

    def clear(self) -> None:
        """Remove all cached plans."""
        self._store.clear()


# --- Confidence Tracker (Task 2) ---


class ConfidenceTracker:
    """Per-task_type hit-rate tracker: hits / total observations.

    A "hit" means the speculative plan matched the solver plan
    (COMMIT or PARTIAL verdict). Learner will override later.
    """

    def __init__(self) -> None:
        self._hits: dict[str, int] = {}
        self._totals: dict[str, int] = {}

    def record_outcome(self, intent: Intent, hit: bool) -> None:
        """Record a speculation outcome for this intent's task type."""
        key = _intent_key(intent)
        self._totals[key] = self._totals.get(key, 0) + 1
        if hit:
            self._hits[key] = self._hits.get(key, 0) + 1

    def confidence(self, intent: Intent) -> float:
        """Return hit rate for this intent's task type. 0.0 if unseen."""
        key = _intent_key(intent)
        total = self._totals.get(key, 0)
        if total == 0:
            return 0.0
        return self._hits.get(key, 0) / total

    def total_observations(self, intent: Intent) -> int:
        """Return total observations for this intent's task type."""
        key = _intent_key(intent)
        return self._totals.get(key, 0)


# --- Mode Selection (Task 3) ---


def select_mode(confidence: float, tau_2: float, tau_3: float) -> int:
    """Select speculation mode based on confidence and thresholds (§3.4).

    Returns:
        3 if confidence > tau_3 (draft execution)
        2 if confidence > tau_2 (agent pre-dispatch)
        1 otherwise (context preparation only)

    Raises:
        ValueError: if tau_3 < tau_2 (thresholds must be ordered)
    """
    if tau_3 < tau_2:
        raise ValueError(
            f"tau_3 ({tau_3}) must be >= tau_2 ({tau_2})"
        )
    if confidence > tau_3:
        return 3
    if confidence > tau_2:
        return 2
    return 1


# --- Mode Implementations (Tasks 4-6) ---


def _prepare_context(intent: Intent) -> list[str]:
    """Mode 1: Prepare context keys for speculation (§3.2).

    Derives context keys from domain_tags + task_type.
    Agent-agnostic — no fleet or plan information needed.
    """
    keys: list[str] = []
    keys.append(f"task:{intent.task_type}")
    for tag in intent.domain_tags:
        keys.append(f"domain:{tag}")
    return keys


def _provision_agents(
    draft_plan: DispatchPlan, fleet: Fleet
) -> tuple[list[str], list[tuple[str, str]]]:
    """Mode 2: Read-only feasibility check for agent pre-dispatch (§3.2).

    Checks which assignments in the draft plan are feasible against
    current fleet state. Does NOT mutate fleet state.

    Returns:
        (agents_provisioned, fleet_reservations) where:
        - agents_provisioned: list of agent_type strings that are feasible
        - fleet_reservations: list of (agent_type, member_id) pairs
    """
    agents_provisioned: list[str] = []
    fleet_reservations: list[tuple[str, str]] = []

    for assignment in draft_plan.assignments:
        member_id = assignment.fleet_member_id
        try:
            member = fleet.get_member(member_id)
        except KeyError:
            continue

        # Check capacity and rate limit — read-only
        from pythia.contracts import AgentSpec

        agent_spec = AgentSpec(
            agent_type=assignment.agent_type,
            required_compute=0.0,  # minimal for feasibility check
            required_memory=0.0,
            estimated_tokens=assignment.allocated_tokens,
            compatible_fleet=[],
            priority=assignment.order,
        )
        if fleet.check_capacity(member_id, agent_spec) and fleet.check_rate_limit(
            member_id
        ):
            agents_provisioned.append(assignment.agent_type)
            fleet_reservations.append((assignment.agent_type, member_id))

    return agents_provisioned, fleet_reservations


def _draft_execute(
    draft_plan: DispatchPlan, intent: Intent
) -> tuple[str, str]:
    """Mode 3: Produce draft output from first-stage agent (§3.2).

    Selects the first agent in execution order and produces a stub output.
    The actual execution engine will replace this with real output later.

    Returns:
        (draft_output, draft_agent_type)
    """
    if not draft_plan.assignments:
        return "", ""

    # Select first agent by execution order
    first_assignment = min(draft_plan.assignments, key=lambda a: a.order)
    draft_agent_type = first_assignment.agent_type
    draft_output = (
        f"[draft] {draft_agent_type} output for "
        f"{intent.task_type} task"
    )
    return draft_output, draft_agent_type


# --- Speculative Dispatcher (Task 7) ---


class SpeculativeDispatcher:
    """The draft model in speculation — §3.2, §5.1.

    Ties together cache lookup, confidence tracking, mode selection,
    and progressive pre-execution. Produces SpeculationResult without
    calling the Solver or mutating Fleet state.

    Args:
        fleet: Fleet instance (read-only access for feasibility checks)
        cache: DispatchCache (shared or dedicated)
        tau_2: Mode 2 activation threshold (§3.4)
        tau_3: Mode 3 activation threshold (§3.4)
        confidence_fn: Optional override for confidence computation
                       (Learner injects its own function here)
    """

    def __init__(
        self,
        fleet: Fleet,
        cache: DispatchCache | None = None,
        tau_2: float = 0.3,
        tau_3: float = 0.7,
        confidence_fn: Callable[[Intent], float] | None = None,
    ) -> None:
        self._fleet = fleet
        self._cache = cache or DispatchCache()
        self._tracker = ConfidenceTracker()
        self._tau_2 = tau_2
        self._tau_3 = tau_3
        self._confidence_fn = confidence_fn

    @property
    def cache(self) -> DispatchCache:
        return self._cache

    @property
    def tracker(self) -> ConfidenceTracker:
        return self._tracker

    def speculate(self, intent: Intent) -> SpeculationResult:
        """Produce a speculative dispatch result for the given intent.

        1. Look up draft plan from cache
        2. Compute confidence (tracker or override)
        3. Select mode based on confidence and thresholds
        4. Execute progressive pre-execution (Mode 1 always, 2 and 3 gated)
        5. Return SpeculationResult
        """
        # Cache lookup
        draft_plan = self._cache.lookup(intent)
        cache_hit = draft_plan is not None

        if draft_plan is None:
            # Cold start: empty plan, Mode 1 only
            draft_plan = DispatchPlan(
                assignments=[],
                execution_order=[],
                total_budget=0,
                total_estimated_latency=0.0,
            )

        # Confidence
        if self._confidence_fn is not None:
            confidence = self._confidence_fn(intent)
        else:
            confidence = self._tracker.confidence(intent)

        # Mode selection
        mode = select_mode(confidence, self._tau_2, self._tau_3)

        # Progressive pre-execution
        context_prepared = _prepare_context(intent)

        agents_provisioned: list[str] = []
        fleet_reservations: list[tuple[str, str]] = []
        draft_output = ""
        draft_agent_type = ""

        if mode >= 2 and cache_hit:
            agents_provisioned, fleet_reservations = _provision_agents(
                draft_plan, self._fleet
            )

        if mode >= 3 and cache_hit:
            draft_output, draft_agent_type = _draft_execute(
                draft_plan, intent
            )

        manifest = PreExecutionManifest(
            mode=mode,
            context_prepared=context_prepared,
            agents_provisioned=agents_provisioned,
            fleet_reservations=fleet_reservations,
            draft_output=draft_output,
            draft_agent_type=draft_agent_type,
        )

        return SpeculationResult(
            draft_plan=draft_plan,
            manifest=manifest,
            confidence=confidence,
            mode=mode,
            cache_hit=cache_hit,
        )

    def record_outcome(
        self, intent: Intent, solver_plan: DispatchPlan, verdict: str
    ) -> None:
        """Record a speculation outcome for learning.

        Updates the cache with the solver's plan and records whether
        the speculation was a hit (COMMIT or PARTIAL).

        Args:
            intent: The original intent
            solver_plan: The Solver's optimal plan P*
            verdict: "COMMIT", "PARTIAL", or "FLUSH"
        """
        self._cache.store(intent, solver_plan)
        hit = verdict in ("COMMIT", "PARTIAL")
        self._tracker.record_outcome(intent, hit)
