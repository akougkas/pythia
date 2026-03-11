"""Plan comparison for reconciliation — §3.3.

Standalone functions comparing optimal plan P* with speculative plan P_hat.
Used by both Reconciliation Engine and Learner.

Match definition: same agent_type assigned to same fleet_member_id.

Traceability:
- COMMIT / PARTIAL / FLUSH verdicts: §3.3
- Salvage ratio σ = |P* ∩ P_hat| / |P_hat|: §3.3
"""

from __future__ import annotations

from typing import Literal

from pythia.contracts import DispatchPlan

Verdict = Literal["COMMIT", "PARTIAL", "FLUSH"]


def _matching_assignments(
    p_star: DispatchPlan, p_hat: DispatchPlan
) -> int:
    """Count assignments in P_hat that match P* (same agent_type + fleet_member_id)."""
    optimal_set = {
        (a.agent_type, a.fleet_member_id) for a in p_star.assignments
    }
    return sum(
        1
        for a in p_hat.assignments
        if (a.agent_type, a.fleet_member_id) in optimal_set
    )


def plan_match(p_star: DispatchPlan, p_hat: DispatchPlan) -> Verdict:
    """Compare optimal and speculative plans — §3.3 reconciliation logic.

    Returns:
        "COMMIT": P* = P_hat (all speculative work accepted)
        "PARTIAL": P* ∩ P_hat ≠ ∅, P* ≠ P_hat (some work salvaged)
        "FLUSH": P* ∩ P_hat = ∅ (all speculative work discarded)
    """
    if not p_hat.assignments:
        return "FLUSH"

    matches = _matching_assignments(p_star, p_hat)

    if matches == len(p_hat.assignments) and matches == len(p_star.assignments):
        return "COMMIT"
    elif matches > 0:
        return "PARTIAL"
    else:
        return "FLUSH"


def plan_overlap(p_star: DispatchPlan, p_hat: DispatchPlan) -> float:
    """Compute salvage ratio σ = |P* ∩ P_hat| / |P_hat| — §3.3.

    Returns 0.0 if P_hat is empty.
    """
    if not p_hat.assignments:
        return 0.0

    matches = _matching_assignments(p_star, p_hat)
    return matches / len(p_hat.assignments)
