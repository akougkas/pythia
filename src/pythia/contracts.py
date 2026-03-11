"""Data contracts for the Pythia dispatch framework.

Traceability:
- Intent: §5.1 (intent classification)
- FleetMember: §3.5 (fleet capability vector f_i)
- AgentSpec: §3.5 (agent resource requirements)
- AgentAssignment: §5.1 (dispatch plan element)
- DispatchPlan: §3.1, §5.1 (optimal dispatch plan P*)
- PreExecutionManifest: §3.2 (speculative pre-execution record)
- SpeculationResult: §3.2 (speculator output)
- ReconciliationConfig: §3.4 (cost model parameters)
- ReconciliationOutcome: §3.3, §5.1 (reconciliation engine output)
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _validate_unit_interval(value: float, name: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be in [0, 1], got {value}")


def _validate_non_negative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")


@dataclass(frozen=True, eq=True)
class Intent:
    """Classified user request — output of Intent Detector (§5.1)."""

    task_type: str
    complexity: float  # in [0, 1]
    domain_tags: list[str]
    decomposability: float  # in [0, 1]
    constraints: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_unit_interval(self.complexity, "complexity")
        _validate_unit_interval(self.decomposability, "decomposability")


@dataclass(frozen=True, eq=True)
class FleetMember:
    """Single member of the heterogeneous fleet — §3.5 capability vector.

    f_i = (compute_i, memory_i, rate_limit_i, token_budget_i, cost_rate_i, latency_i)
    """

    member_id: str
    compute: float
    memory: float
    rate_limit: int  # max concurrent requests
    token_budget: int
    cost_rate: float  # $/token
    latency: float  # seconds, expected response latency
    capabilities: list[str]
    affinity_tags: list[str]

    def __post_init__(self) -> None:
        _validate_non_negative(self.compute, "compute")
        _validate_non_negative(self.memory, "memory")
        _validate_non_negative(self.cost_rate, "cost_rate")
        _validate_non_negative(self.latency, "latency")


@dataclass(frozen=True, eq=True)
class AgentSpec:
    """Specification for a single agent to be dispatched — §3.5."""

    agent_type: str
    required_compute: float
    required_memory: float
    estimated_tokens: int
    compatible_fleet: list[str]  # member_ids; empty = any
    priority: int  # lower = higher priority (dispatched first)


@dataclass(frozen=True, eq=True)
class AgentAssignment:
    """One agent assigned to one fleet member — element of DispatchPlan."""

    agent_type: str
    fleet_member_id: str
    allocated_tokens: int
    prompt: str
    order: int  # execution order index


@dataclass(frozen=True, eq=True)
class DispatchPlan:
    """Optimal dispatch plan P* produced by the Solver (§3.1, §5.1).

    Contains agent assignments, execution DAG, and resource totals.
    """

    assignments: list[AgentAssignment]
    execution_order: list[list[str]]  # DAG as list of parallel stages
    total_budget: int  # total tokens allocated
    total_estimated_latency: float


@dataclass(frozen=True, eq=True)
class PreExecutionManifest:
    """Record of speculative pre-execution work — §3.2.

    Captures what *would* be done, without mutating Fleet state.
    The active mode determines which fields are populated.
    """

    mode: int  # 1, 2, or 3
    context_prepared: list[str]  # Mode 1+: context keys prepared
    agents_provisioned: list[str]  # Mode 2+: agent types provisioned
    fleet_reservations: list[tuple[str, str]]  # Mode 2+: (agent_type, member_id)
    draft_output: str  # Mode 3: stub output from first-stage agent
    draft_agent_type: str  # Mode 3: agent type that produced draft_output

    def __post_init__(self) -> None:
        if self.mode not in (1, 2, 3):
            raise ValueError(f"mode must be 1, 2, or 3, got {self.mode}")


@dataclass(frozen=True, eq=True)
class SpeculationResult:
    """Output of the Speculative Dispatcher — §3.2.

    Contains the draft plan, pre-execution manifest, confidence score,
    active mode, and whether the cache was hit.
    """

    draft_plan: DispatchPlan
    manifest: PreExecutionManifest
    confidence: float  # in [0, 1]
    mode: int  # 1, 2, or 3
    cache_hit: bool

    def __post_init__(self) -> None:
        _validate_unit_interval(self.confidence, "confidence")
        if self.mode not in (1, 2, 3):
            raise ValueError(f"mode must be 1, 2, or 3, got {self.mode}")


_VALID_VERDICTS = frozenset({"COMMIT", "PARTIAL", "FLUSH"})


@dataclass(frozen=True, eq=True)
class ReconciliationConfig:
    """Cost parameters for reconciliation — §3.4.

    L_saved: latency benefit on full COMMIT (normalized)
    C_redirect: cost per redirected (discarded) assignment
    C_flush: penalty for full flush
    C_spec_per_assignment: speculative compute cost per assignment
    """

    L_saved: float = 1.0
    C_redirect: float = 0.3
    C_flush: float = 0.5
    C_spec_per_assignment: float = 0.1

    def __post_init__(self) -> None:
        _validate_non_negative(self.L_saved, "L_saved")
        _validate_non_negative(self.C_redirect, "C_redirect")
        _validate_non_negative(self.C_flush, "C_flush")
        _validate_non_negative(self.C_spec_per_assignment, "C_spec_per_assignment")


@dataclass(frozen=True, eq=True)
class ReconciliationOutcome:
    """Output of the Reconciliation Engine — §3.3, §5.1.

    verdict: COMMIT | PARTIAL | FLUSH
    salvage_ratio: σ ∈ [0, 1]
    adopted: speculative assignments matching P*
    discarded: speculative assignments NOT in P*
    redirect_cost: (1-σ) redirect penalty
    wasted_compute: speculative compute on discarded assignments
    reward: §4.1 Learner signal
    speculation_mode: mode active at speculation time
    confidence: confidence at speculation time
    """

    verdict: str
    salvage_ratio: float
    adopted: list[AgentAssignment]
    discarded: list[AgentAssignment]
    redirect_cost: float
    wasted_compute: float
    reward: float
    speculation_mode: int
    confidence: float

    def __post_init__(self) -> None:
        if self.verdict not in _VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {_VALID_VERDICTS}, got {self.verdict!r}"
            )
        _validate_unit_interval(self.salvage_ratio, "salvage_ratio")
        if self.speculation_mode not in (1, 2, 3):
            raise ValueError(
                f"speculation_mode must be 1, 2, or 3, got {self.speculation_mode}"
            )
        _validate_unit_interval(self.confidence, "confidence")
