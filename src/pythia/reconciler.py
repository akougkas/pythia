"""Reconciliation Engine — compares P* against P_hat and produces outcomes (§3.3).

Delegates verdict and salvage ratio to comparison.py (stateless functions).
Adds cost computation (§3.4) and Learner reward signal (§4.1).

Traceability:
- §3.3: Reconciliation protocol (COMMIT / PARTIAL / FLUSH)
- §3.4: Cost model (redirect cost, wasted compute, reward formula)
- §4.1: Learner reward signal
- §5.1: Implementation architecture
"""

from __future__ import annotations

from pythia.comparison import plan_match, plan_overlap
from pythia.contracts import (
    AgentAssignment,
    DispatchPlan,
    Intent,
    ReconciliationConfig,
    ReconciliationOutcome,
    SpeculationResult,
)


def _classify_assignments(
    solver_plan: DispatchPlan, speculative_plan: DispatchPlan
) -> tuple[list[AgentAssignment], list[AgentAssignment]]:
    """Partition speculative assignments into adopted vs discarded.

    An assignment is adopted if (agent_type, fleet_member_id) appears in P*.

    Returns:
        (adopted, discarded)
    """
    optimal_set = {
        (a.agent_type, a.fleet_member_id) for a in solver_plan.assignments
    }
    adopted: list[AgentAssignment] = []
    discarded: list[AgentAssignment] = []
    for a in speculative_plan.assignments:
        if (a.agent_type, a.fleet_member_id) in optimal_set:
            adopted.append(a)
        else:
            discarded.append(a)
    return adopted, discarded


class ReconciliationEngine:
    """Reconciliation Engine — §3.3, §5.1.

    Compares the Solver's optimal plan P* against the Speculator's draft
    plan P_hat. Produces a ReconciliationOutcome with verdict, costs,
    and Learner reward signal.
    """

    def __init__(self, config: ReconciliationConfig | None = None) -> None:
        self._config = config or ReconciliationConfig()

    @property
    def config(self) -> ReconciliationConfig:
        return self._config

    def reconcile(
        self,
        solver_plan: DispatchPlan,
        speculation: SpeculationResult,
    ) -> ReconciliationOutcome:
        """Compare P* against speculative result and produce outcome.

        Steps:
        1. Verdict via plan_match(P*, P_hat)
        2. Salvage ratio via plan_overlap(P*, P_hat)
        3. Classify assignments into adopted / discarded
        4. Compute redirect cost and wasted compute
        5. Compute §4.1 reward signal
        """
        draft_plan = speculation.draft_plan
        cfg = self._config

        # 1. Verdict
        verdict = plan_match(solver_plan, draft_plan)

        # 2. Salvage ratio
        salvage_ratio = plan_overlap(solver_plan, draft_plan)

        # 3. Classify
        adopted, discarded = _classify_assignments(solver_plan, draft_plan)

        # 4. Costs
        n_discarded = len(discarded)
        redirect_cost = n_discarded * cfg.C_redirect
        wasted_compute = n_discarded * cfg.C_spec_per_assignment

        # 5. Reward — §4.1
        if verdict == "COMMIT":
            reward = cfg.L_saved
        elif verdict == "FLUSH":
            reward = -cfg.C_flush
        else:  # PARTIAL
            sigma = salvage_ratio
            reward = sigma * cfg.L_saved - (1 - sigma) * cfg.C_redirect

        return ReconciliationOutcome(
            verdict=verdict,
            salvage_ratio=salvage_ratio,
            adopted=adopted,
            discarded=discarded,
            redirect_cost=redirect_cost,
            wasted_compute=wasted_compute,
            reward=reward,
            speculation_mode=speculation.mode,
            confidence=speculation.confidence,
        )

    def reconcile_and_record(
        self,
        solver_plan: DispatchPlan,
        speculation: SpeculationResult,
        intent: Intent,
        speculator: object,
    ) -> ReconciliationOutcome:
        """Reconcile and update speculator cache + confidence.

        Convenience method: calls reconcile() then speculator.record_outcome().
        """
        outcome = self.reconcile(solver_plan, speculation)
        # Type-narrow: speculator must have record_outcome method
        speculator.record_outcome(intent, solver_plan, outcome.verdict)  # type: ignore[attr-defined]
        return outcome
