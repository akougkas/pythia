"""End-to-end Pythia pipeline: Speculate → Solve → Reconcile → Learn.

Demonstrates the full draft-target speculation loop from §3.1–§3.4:
  1. Intent arrives
  2. Speculator produces draft plan P_hat (fast, from cache)
  3. Solver produces optimal plan P* (slow, constraint-aware)
  4. Reconciler compares P* vs P_hat → verdict + reward
  5. Speculator updates cache/confidence for next round

Run:
    cd src && python -m examples.example
"""

from pythia.contracts import (
    FleetMember,
    Intent,
    ReconciliationConfig,
)
from pythia.fleet import Fleet
from pythia.reconciler import ReconciliationEngine
from pythia.solver import AgentSelector, DispatchSolver
from pythia.speculator import SpeculativeDispatcher


def build_fleet() -> Fleet:
    """Build a small heterogeneous fleet — §3.5."""
    return Fleet([
        FleetMember(
            member_id="gpu-1",
            compute=100.0, memory=64.0,
            rate_limit=5, token_budget=50000,
            cost_rate=0.05, latency=0.1,
            capabilities=["code_gen", "analysis", "planner"],
            affinity_tags=["gpu", "local"],
        ),
        FleetMember(
            member_id="cpu-1",
            compute=50.0, memory=32.0,
            rate_limit=10, token_budget=30000,
            cost_rate=0.02, latency=0.3,
            capabilities=["review", "planner", "analysis"],
            affinity_tags=["cpu", "local"],
        ),
        FleetMember(
            member_id="cloud-1",
            compute=200.0, memory=128.0,
            rate_limit=20, token_budget=100000,
            cost_rate=0.08, latency=0.5,
            capabilities=["code_gen", "analysis", "review", "planner"],
            affinity_tags=["cloud"],
        ),
    ])


def main() -> None:
    fleet = build_fleet()
    selector = AgentSelector()
    solver = DispatchSolver(fleet, selector, alpha=0.5)
    speculator = SpeculativeDispatcher(fleet, tau_2=0.3, tau_3=0.7)
    reconciler = ReconciliationEngine(
        ReconciliationConfig(L_saved=1.0, C_redirect=0.3, C_flush=0.5, C_spec_per_assignment=0.1)
    )

    # Two different intents to show cross-intent independence
    intents = [
        Intent(task_type="hpc_code_gen", complexity=0.8, domain_tags=["hpc", "mpi"], decomposability=0.7),
        Intent(task_type="research_writing", complexity=0.6, domain_tags=["nlp"], decomposability=0.5),
    ]

    budget = 20000
    n_rounds = 5

    print("=" * 72)
    print("Pythia: Speculative Dispatch Pipeline")
    print("=" * 72)

    for intent in intents:
        print(f"\n{'─' * 72}")
        print(f"Intent: {intent.task_type}  (complexity={intent.complexity})")
        print(f"{'─' * 72}")

        for round_num in range(1, n_rounds + 1):
            # --- Step 1: Speculate (fast path) ---
            speculation = speculator.speculate(intent)

            # --- Step 2: Solve (slow path) ---
            solver_plan = solver.solve(intent, budget)

            # --- Step 3: Reconcile ---
            outcome = reconciler.reconcile_and_record(
                solver_plan, speculation, intent, speculator
            )

            # --- Report ---
            spec_agents = [a.agent_type for a in speculation.draft_plan.assignments]
            solver_agents = [
                f"{a.agent_type}→{a.fleet_member_id}" for a in solver_plan.assignments
            ]

            print(f"\n  Round {round_num}:")
            print(f"    Speculation  mode={speculation.mode}  confidence={speculation.confidence:.2f}  "
                  f"cache_hit={speculation.cache_hit}")
            print(f"    Draft agents: {spec_agents or '(empty — cold start)'}")
            print(f"    Solver plan:  {solver_agents}")
            print(f"    Verdict:      {outcome.verdict}  σ={outcome.salvage_ratio:.2f}")
            print(f"    Costs:        redirect={outcome.redirect_cost:.3f}  "
                  f"wasted={outcome.wasted_compute:.3f}")
            print(f"    Reward:       {outcome.reward:+.3f}")

    # --- Summary ---
    print(f"\n{'=' * 72}")
    print("Summary: confidence after all rounds")
    print(f"{'=' * 72}")
    for intent in intents:
        conf = speculator.tracker.confidence(intent)
        depth = speculator.cache.history_depth(intent)
        print(f"  {intent.task_type:30s}  confidence={conf:.2f}  cache_depth={depth}")


if __name__ == "__main__":
    main()
