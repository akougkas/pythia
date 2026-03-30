"""Full HPC-CG Evaluation — 5-Layer Architecture, Everything Real.

Follows the Pythia architecture diagram exactly:

  Layer 1: Intent Detector
  Layer 2: Dispatch Solver (LLM, slow) + Speculative Dispatcher (cache, fast)
  Layer 3: Orchestrator (Reconciliation Engine)
  Layer 4: Execution Engine (real LLM agents)
  Layer 5: Learner (Bayesian RL)

NO fake delays. NO simulated overheads. Every timing is real.

Output structure per interaction:
  runs/<timestamp>/
    config.json
    summary.json
    interaction_001/
      layer1_intent.json
      layer2_solver.json
      layer2_speculator.json
      layer3_reconciliation.json
      layer4_execution.json
      layer4_mode3_draft.json  (if Mode 3)
      layer5_learner.json
      timing.json
    interaction_002/
      ...
    all_results.json

Usage:
  python run_full_eval.py --n-requests 20 --prompt-mode original
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "../../../src"))
sys.path.insert(0, str(Path(__file__).parent / "../hpc_cg"))

from pythia.contracts import FleetMember, ReconciliationConfig
from pythia.fleet import Fleet
from pythia.intent import RuleBasedIntentDetector
from pythia.solver import LLMAgentSelector, DispatchSolver
from pythia.speculator import DispatchCache, SpeculativeDispatcher, create_llm_draft_model
from pythia.reconciler import ReconciliationEngine
from pythia.learner import Learner

from agent_runner import (
    AgentPipelineRunner, OllamaClient, ClaudeClient,
    compute_output_similarity, judge_output_acceptance,
)

REQUESTS_FILE = Path(__file__).parent / "sdp_requests.json"


def create_model_fleet(fleet_size: int = 5) -> Fleet:
    """Each fleet member = specific model on specific hardware (§3.5).

    Heterogeneous fleet: local Ollama models + Claude tiers.
    Fleet sizes: 2 (local only), 3 (+haiku), 5 (full, +sonnet+opus)
    """
    all_members = [
        # --- Local Ollama models ---
        FleetMember(
            member_id="qwen2.5-14b-gpu", compute=100.0, memory=64.0,
            rate_limit=10, token_budget=100000, cost_rate=0.01, latency=2.0,
            capabilities=["code_gen", "tester", "analyst", "data_wrangler", "code_generator"],
            affinity_tags=["gpu", "local", "hpc", "code"],
            model="qwen2.5:14b",
        ),
        FleetMember(
            member_id="llama3.1-8b-gpu", compute=80.0, memory=32.0,
            rate_limit=20, token_budget=200000, cost_rate=0.005, latency=0.5,
            capabilities=["planner", "review", "data_discovery", "reporter",
                          "literature_reviewer", "experiment_designer",
                          "experiment_runner", "result_analyzer"],
            affinity_tags=["gpu", "local", "fast"],
            model="llama3.1:8b",
        ),
        # --- Claude Haiku (fast, cheap — planning, review, testing) ---
        FleetMember(
            member_id="claude-haiku-cloud", compute=150.0, memory=64.0,
            rate_limit=10, token_budget=200000, cost_rate=0.02, latency=3.0,
            capabilities=["planner", "review", "tester", "reporter",
                          "data_discovery", "result_analyzer",
                          "experiment_runner", "experiment_designer"],
            affinity_tags=["cloud", "api", "fast"],
            model="claude-haiku-4-5-20251001",
        ),
        # --- Claude Sonnet (balanced — code gen, analysis) ---
        FleetMember(
            member_id="claude-sonnet-cloud", compute=200.0, memory=128.0,
            rate_limit=5, token_budget=200000, cost_rate=0.08, latency=4.0,
            capabilities=["code_gen", "tester", "analyst", "data_wrangler",
                          "code_generator", "planner", "review",
                          "literature_reviewer", "experiment_designer"],
            affinity_tags=["cloud", "api", "balanced"],
            model="claude-sonnet-4-6",
        ),
        # --- Claude Opus (best quality — complex code, critical analysis) ---
        FleetMember(
            member_id="claude-opus-cloud", compute=300.0, memory=256.0,
            rate_limit=3, token_budget=100000, cost_rate=0.15, latency=5.0,
            capabilities=["code_gen", "analyst", "code_generator",
                          "literature_reviewer"],
            affinity_tags=["cloud", "api", "premium"],
            model="claude-opus-4-6",
        ),
    ]
    # Slice by fleet size: 2=local only, 3=+haiku, 5=full
    size_map = {2: 2, 3: 3, 5: 5}
    n = size_map.get(fleet_size, 5)
    return Fleet(all_members[:n])


def get_request_text(req: dict, prompt_mode: str) -> str:
    if prompt_mode == "original" and "original_prompt" in req:
        return req["original_prompt"]
    return req["request"]


def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def generate_plan_md(
    plan,
    fleet,
    source: str,
    intent=None,
    request_text: str = "",
    time_ms: float = 0.0,
    reasoning: str = "",
    mode: int | None = None,
    confidence: float | None = None,
) -> str:
    """Generate human-readable markdown from a DispatchPlan.

    Used for both Solver and Speculator plans so they can be compared
    side by side. Inspired by motivation test plan format.
    """
    lines = []
    label = source.upper()
    lines.append(f"# Dispatch Plan — {label}")
    lines.append("")

    if request_text:
        preview = request_text[:300].replace("\n", "\n> ")
        lines.append("## Request")
        lines.append(f"> {preview}")
        if len(request_text) > 300:
            lines.append(f"> ... ({len(request_text)} chars total)")
        lines.append("")

    if intent:
        lines.append("## Intent")
        lines.append(f"- **Task type**: {intent.task_type}")
        lines.append(f"- **Complexity**: {intent.complexity:.3f}")
        lines.append(f"- **Domain**: {', '.join(intent.domain_tags)}")
        lines.append(f"- **Decomposability**: {intent.decomposability:.2f}")
        lines.append("")

    # Metadata
    lines.append("## Metadata")
    lines.append(f"- **Source**: {source}")
    lines.append(f"- **Time**: {time_ms:.0f}ms ({time_ms/1000:.1f}s)")
    if mode is not None:
        lines.append(f"- **Mode**: {mode}")
    if confidence is not None:
        lines.append(f"- **Confidence**: {confidence:.3f}")
    lines.append("")

    # Reasoning
    plan_reasoning = reasoning or getattr(plan, 'reasoning', '')
    if plan_reasoning:
        lines.append("## Reasoning")
        lines.append(plan_reasoning)
        lines.append("")

    # Pipeline summary
    if plan.assignments:
        agent_flow = " -> ".join(a.agent_type for a in plan.assignments)
        lines.append(f"## Pipeline: {agent_flow}")
        lines.append("")

    # Agent assignments
    if plan.assignments:
        lines.append("## Agent Assignments")
        lines.append("")
        for i, a in enumerate(plan.assignments, 1):
            try:
                member = fleet.get_member(a.fleet_member_id)
                model = member.model
            except (KeyError, AttributeError):
                model = "unknown"

            lines.append(f"### {i}. {a.agent_type} -> {a.fleet_member_id} ({model})")
            if a.role:
                lines.append(f"- **Role**: {a.role}")
            lines.append(f"- **Prompt**: {a.prompt}")
            lines.append(f"- **Tokens**: {a.allocated_tokens} | "
                         f"Compute: {a.compute_weight}")
            if a.depends_on:
                lines.append(f"- **Depends on**: {', '.join(a.depends_on)}")
            else:
                lines.append("- **Depends on**: (none)")
            lines.append("")

    # Execution DAG
    if plan.execution_order:
        lines.append("## Execution DAG")
        for stage_idx, stage in enumerate(plan.execution_order):
            parallel = " (parallel)" if len(stage) > 1 else ""
            lines.append(f"- Stage {stage_idx}: [{', '.join(stage)}]{parallel}")
        lines.append("")

    # Resource summary table
    if plan.assignments:
        lines.append("## Resource Summary")
        lines.append("")
        lines.append("| Agent | Fleet Member | Model | Tokens | Compute |")
        lines.append("|-------|-------------|-------|--------|---------|")
        for a in plan.assignments:
            try:
                model = fleet.get_member(a.fleet_member_id).model
            except (KeyError, AttributeError):
                model = "?"
            lines.append(f"| {a.agent_type} | {a.fleet_member_id} | "
                         f"{model} | {a.allocated_tokens} | {a.compute_weight} |")
        lines.append(f"| **Total** | | | **{plan.total_budget}** | |")
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-mode", choices=["original", "nl"], default="original")
    parser.add_argument("--n-requests", type=int, default=20)
    parser.add_argument("--solver-provider", choices=["ollama", "claude"], default="claude",
                        help="LLM provider for Solver agent selection")
    parser.add_argument("--solver-model", type=str, default=None,
                        help="Model for Solver (default: claude-sonnet-4-6 for claude, llama3.1:8b for ollama)")
    parser.add_argument("--baseline", choices=["pythia", "ns", "sh", "swol", "oracle"], default="pythia",
                        help="Baseline mode: pythia=full system, ns=no speculation, "
                             "sh=static heuristic (rule-based), swol=speculation without learning, "
                             "oracle=perfect predictor")
    parser.add_argument("--fleet-size", type=int, choices=[2, 3, 5], default=5,
                        help="Fleet size for scalability sweep (§6.6)")
    args = parser.parse_args()

    prompt_mode = args.prompt_mode
    baseline = args.baseline
    fleet_size = args.fleet_size
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    fleet_tag = f"_fleet{fleet_size}" if fleet_size != 5 else ""
    run_dir = Path(__file__).parent / f"runs/{timestamp}_{baseline}{fleet_tag}_{args.n_requests}req"
    run_dir.mkdir(parents=True, exist_ok=True)

    with open(REQUESTS_FILE) as f:
        all_requests = json.load(f)
    requests = all_requests[:args.n_requests]

    # --- Setup (varies by baseline) ---
    solver_provider = args.solver_provider
    solver_model = args.solver_model
    if solver_model is None:
        solver_model = "claude-sonnet-4-6" if solver_provider == "claude" else "llama3.1:8b"

    fleet = create_model_fleet(fleet_size)
    detector = RuleBasedIntentDetector()

    # Solver setup — SH baseline uses rule-based, everything else uses LLM
    from pythia.solver import AgentSelector
    if baseline == "sh":
        rule_selector = AgentSelector()
        solver = DispatchSolver(fleet, rule_selector, alpha=0.5)
        llm_selector = rule_selector  # for logging compatibility
        solver_model = "rule-based"
    else:
        llm_selector = LLMAgentSelector(model=solver_model, provider=solver_provider)
        solver = DispatchSolver(fleet, llm_selector, alpha=0.5)

    cache = DispatchCache(max_history=64)
    learner = Learner(window_size=50, n1=2, n2=6)

    # Clients for agent execution
    clients = {
        "qwen2.5:14b": OllamaClient(model="qwen2.5:14b"),
        "llama3.1:8b": OllamaClient(model="llama3.1:8b"),
        "claude-haiku-4-5-20251001": ClaudeClient(model="claude-haiku-4-5-20251001"),
        "claude-sonnet-4-6": ClaudeClient(model="claude-sonnet-4-6"),
        "claude-opus-4-6": ClaudeClient(model="claude-opus-4-6"),
    }

    # Speculator setup — NS and SH baselines have no speculator
    speculator = None
    draft_runner = None
    draft_model = None

    if baseline in ("pythia", "swol", "oracle"):
        draft_runner = AgentPipelineRunner(client=clients["llama3.1:8b"])
        draft_model = create_llm_draft_model(model="llama3.1:8b", provider="ollama")

        if baseline == "swol":
            # Frozen confidence — speculation but no learning
            speculator = SpeculativeDispatcher(
                fleet=fleet, cache=cache, tau_2=0.5, tau_3=0.8,
                confidence_fn=lambda intent: 0.5,  # fixed, never learns
                draft_executor=draft_runner,
                draft_model_fn=draft_model,
            )
        else:
            speculator = SpeculativeDispatcher(
                fleet=fleet, cache=cache, tau_2=0.5, tau_3=0.8,
                confidence_fn=learner.confidence_fn,
                draft_executor=draft_runner,
                draft_model_fn=draft_model,
            )

    reconciler = ReconciliationEngine(
        config=ReconciliationConfig(L_saved=1.0, C_redirect=0.3, C_flush=0.5, C_spec_per_assignment=0.1)
    )

    # Save config
    config = {
        "timestamp": timestamp, "baseline": baseline, "prompt_mode": prompt_mode,
        "n_requests": args.n_requests,
        "fleet": [{"id": m.member_id, "model": m.model, "capabilities": m.capabilities,
                    "cost_rate": m.cost_rate, "latency": m.latency} for m in fleet.members],
        "solver": {"type": "AgentSelector (rule-based)" if baseline == "sh"
                   else "LLMAgentSelector", "model": solver_model, "provider": solver_provider},
        "speculator": {"type": "disabled" if baseline in ("ns", "sh")
                       else "frozen (SwoL)" if baseline == "swol"
                       else "oracle" if baseline == "oracle"
                       else "DispatchCache + BayesianConfidence"},
        "learner": {"type": "disabled" if baseline in ("ns", "sh", "swol")
                    else "Bayesian Contextual Bandit", "window_size": 50, "n1": 2, "n2": 6},
        "thresholds": {"tau_2": 0.5, "tau_3": 0.8},
        "reconciliation": {"L_saved": 1.0, "C_redirect": 0.3, "C_flush": 0.5, "C_spec": 0.1},
    }
    save_json(run_dir / "config.json", config)

    baseline_labels = {
        "pythia": "Pythia (full system)",
        "ns": "No Speculation (NS)",
        "sh": "Static Heuristic (SH)",
        "swol": "Speculation without Learning (SwoL)",
        "oracle": "Oracle Speculation (OS)",
    }
    print(f"Run: {run_dir}")
    print(f"Baseline: {baseline_labels[baseline]}")
    print(f"Fleet: {[f'{m.member_id} ({m.model})' for m in fleet.members]}")
    print(f"Solver: {'rule-based' if baseline == 'sh' else f'LLM ({solver_provider}/{solver_model})'}")
    print(f"Speculator: {'disabled' if baseline in ('ns','sh') else 'frozen' if baseline == 'swol' else 'oracle' if baseline == 'oracle' else 'cache+learner'}")
    print(f"Requests: {len(requests)} | Prompt: {prompt_mode}")

    all_events = []

    for i, req in enumerate(requests):
        interaction = i + 1
        request_text = get_request_text(req, prompt_mode)
        idir = run_dir / f"interaction_{interaction:03d}"
        idir.mkdir(exist_ok=True)

        print(f"\n{'━'*70}")
        print(f"  INTERACTION {interaction}/{len(requests)}: {req['id']}")
        print(f"{'━'*70}")

        # ════════════════════════════════════════════════════
        # LAYER 1: INTENT DETECTOR
        # ════════════════════════════════════════════════════
        t0 = time.perf_counter()
        intent = detector.detect(request_text)
        t_intent = (time.perf_counter() - t0) * 1000

        layer1 = {
            "layer": "1_intent_detector",
            "input": {"request_text": request_text[:500]},
            "output": {
                "task_type": intent.task_type,
                "complexity": intent.complexity,
                "domain_tags": list(intent.domain_tags),
                "decomposability": intent.decomposability,
                "constraints": dict(intent.constraints),
            },
            "time_ms": t_intent,
        }
        save_json(idir / "layer1_intent.json", layer1)
        print(f"  L1 INTENT: {intent.task_type} | c={intent.complexity:.3f} | "
              f"tags={intent.domain_tags} | {t_intent:.2f}ms")

        # ════════════════════════════════════════════════════
        # LAYER 2a: SPECULATIVE DISPATCHER (Draft, Fast)
        # ════════════════════════════════════════════════════
        t_spec = 0.0
        speculation = None
        draft_agents = []

        if speculator is not None:
            t0 = time.perf_counter()
            speculation = speculator.speculate(intent, request_text=request_text)
            t_spec = (time.perf_counter() - t0) * 1000

            layer2_spec = {
                "layer": "2_speculative_dispatcher",
                "input": {"intent_key": f"{intent.task_type}:{intent.complexity:.1f}:{intent.domain_tags}"},
                "output": {
                    "mode": speculation.mode,
                    "confidence": speculation.confidence,
                    "cache_hit": speculation.cache_hit,
                    "draft_plan": [
                        {"agent": a.agent_type, "fleet_member": a.fleet_member_id,
                         "model": fleet.get_member(a.fleet_member_id).model,
                         "tokens": a.allocated_tokens}
                        for a in speculation.draft_plan.assignments
                    ],
                    "manifest": {
                        "context_prepared": speculation.manifest.context_prepared,
                        "agents_provisioned": speculation.manifest.agents_provisioned,
                        "fleet_reservations": speculation.manifest.fleet_reservations,
                    },
                },
                "time_ms": t_spec,
            }
            layer2_spec["output"]["draft_prompts"] = {
                a.agent_type: a.prompt for a in speculation.draft_plan.assignments
                if not a.prompt.startswith("[stub]")
            }
            if speculation.manifest.draft_output:
                layer2_spec["output"]["draft_output"] = speculation.manifest.draft_output[:1000]
                layer2_spec["output"]["draft_agent"] = speculation.manifest.draft_agent_type
                layer2_spec["draft_execution_time_ms"] = speculator.last_draft_time_ms

            save_json(idir / "layer2_speculator.json", layer2_spec)
            spec_source = "draft_model" if speculator.last_draft_model_used else ("cache" if speculation.cache_hit else "empty")
            spec_plan_md = generate_plan_md(
                speculation.draft_plan, fleet, source=f"Speculator ({spec_source})",
                intent=intent, request_text=request_text, time_ms=t_spec,
                mode=speculation.mode, confidence=speculation.confidence,
            )
            with open(idir / "layer2_speculator_plan.md", "w") as f:
                f.write(spec_plan_md)
            draft_agents = [a.agent_type for a in speculation.draft_plan.assignments]
            print(f"  L2 SPECULATOR: Mode {speculation.mode} | conf={speculation.confidence:.3f} | "
                  f"source={spec_source} | {t_spec:.3f}ms")
        else:
            print(f"  L2 SPECULATOR: disabled ({baseline})")

        # ════════════════════════════════════════════════════
        # LAYER 2b: DISPATCH SOLVER (Target, Slow — LLM call)
        # ════════════════════════════════════════════════════
        t0 = time.perf_counter()
        solver_plan = solver.solve(intent, budget=10000, request_text=request_text)
        t_solver = (time.perf_counter() - t0) * 1000

        llm_call_ms = getattr(llm_selector, 'last_call_time_ms', 0.0)
        llm_reasoning = getattr(llm_selector, 'last_reasoning', '')
        layer2_solver = {
            "layer": "2_dispatch_solver",
            "input": {"intent": layer1["output"], "request_text_preview": request_text[:300]},
            "method": f"{'rule-based' if baseline == 'sh' else 'LLM'} agent selection + greedy fleet assignment",
            "output": {
                "plan": [
                    {"agent": a.agent_type, "fleet_member": a.fleet_member_id,
                     "model": fleet.get_member(a.fleet_member_id).model,
                     "tokens": a.allocated_tokens, "order": a.order}
                    for a in solver_plan.assignments
                ],
                "execution_order": solver_plan.execution_order,
                "total_budget": solver_plan.total_budget,
                "estimated_latency": solver_plan.total_estimated_latency,
            },
            "time_ms": t_solver,
            "llm_call_time_ms": llm_call_ms,
            "assignment_time_ms": t_solver - llm_call_ms,
            "llm_reasoning": llm_reasoning,
            "llm_parsed_agents": getattr(llm_selector, 'last_parsed_agents', []),
            "llm_agent_details": getattr(llm_selector, 'last_agent_details', []),
            "llm_agent_prompts": getattr(llm_selector, 'last_agent_prompts', {}),
        }
        if baseline != "sh":
            layer2_solver["llm_raw_response"] = getattr(llm_selector, 'last_raw_response', '')
        save_json(idir / "layer2_solver.json", layer2_solver)
        solver_plan_md = generate_plan_md(
            solver_plan, fleet, source=f"Solver ({'rule-based' if baseline == 'sh' else f'LLM: {solver_model}'})",
            intent=intent, request_text=request_text, time_ms=t_solver,
            reasoning=llm_reasoning,
        )
        with open(idir / "layer2_solver_plan.md", "w") as f:
            f.write(solver_plan_md)
        solver_agents = [a.agent_type for a in solver_plan.assignments]
        print(f"  L2 SOLVER: {t_solver:.0f}ms ({t_solver/1000:.1f}s)")
        for a in solver_plan.assignments:
            m = fleet.get_member(a.fleet_member_id)
            print(f"     {a.agent_type:20s} → {m.member_id:20s} ({m.model})")

        # ════════════════════════════════════════════════════
        # LAYER 3: ORCHESTRATOR (Reconciliation Engine)
        # ════════════════════════════════════════════════════
        if baseline == "oracle":
            # Oracle: fake a perfect speculation that matches solver exactly
            from pythia.contracts import SpeculationResult, PreExecutionManifest
            oracle_manifest = PreExecutionManifest(
                mode=3, context_prepared=[], agents_provisioned=[],
                fleet_reservations=[], draft_output="", draft_agent_type="")
            speculation = SpeculationResult(
                draft_plan=solver_plan, manifest=oracle_manifest,
                confidence=1.0, mode=3, cache_hit=True)

        if speculation is not None:
            outcome = reconciler.reconcile(solver_plan, speculation)
        else:
            # NS/SH: no speculation → no reconciliation
            # Use a simple namespace instead of ReconciliationOutcome to avoid validation
            class _NoSpecOutcome:
                verdict = "NONE"
                salvage_ratio = 0.0
                adopted = []
                discarded = []
                redirect_cost = 0.0
                wasted_compute = 0.0
                reward = 0.0
                speculation_mode = 0
                confidence = 0.0
            outcome = _NoSpecOutcome()

        layer3 = {
            "layer": "3_orchestrator_reconciliation",
            "input": {
                "solver_plan_agents": [a.agent_type for a in solver_plan.assignments],
                "speculator_plan_agents": draft_agents,
                "solver_plan_members": [a.fleet_member_id for a in solver_plan.assignments],
                "speculator_plan_members": [a.fleet_member_id for a in speculation.draft_plan.assignments] if speculation else [],
            },
            "comparison": {
                "matching_assignments": [a.agent_type for a in outcome.adopted],
                "discarded_assignments": [a.agent_type for a in outcome.discarded],
            },
            "output": {
                "verdict": outcome.verdict,
                "salvage_ratio": outcome.salvage_ratio,
                "reward": outcome.reward,
                "redirect_cost": outcome.redirect_cost,
                "wasted_compute": outcome.wasted_compute,
            },
        }
        save_json(idir / "layer3_reconciliation.json", layer3)
        print(f"  L3 RECONCILE: {outcome.verdict} | salvage={outcome.salvage_ratio:.2f} | "
              f"reward={outcome.reward:+.1f} | adopted={[a.agent_type for a in outcome.adopted]}")

        # ════════════════════════════════════════════════════
        # LAYER 4: EXECUTION ENGINE (Real LLM agents)
        # ════════════════════════════════════════════════════
        role_clients = {}
        for a in solver_plan.assignments:
            model = fleet.get_member(a.fleet_member_id).model
            if model in clients:
                role_clients[a.agent_type] = clients[model]

        runner = AgentPipelineRunner(client=clients["qwen2.5:14b"], role_clients=role_clients)

        print(f"  L4 EXECUTING {len(solver_agents)} agents...")
        target_result = runner.execute_pipeline(
            request_text, solver_agents, solver_plan.execution_order)

        layer4 = {
            "layer": "4_execution_engine",
            "agents": {},
            "pipeline_total_time_s": target_result.total_elapsed_seconds,
            "pipeline_total_tokens": target_result.total_tokens,
            "review_score": target_result.review_score,
            "final_code_preview": target_result.final_code[:500] if target_result.final_code else "",
        }
        for a in target_result.agent_outputs:
            m_id = next((x.fleet_member_id for x in solver_plan.assignments
                         if x.agent_type == a.agent_type), "unknown")
            model = fleet.get_member(m_id).model if m_id != "unknown" else "unknown"
            layer4["agents"][a.agent_type] = {
                "fleet_member": m_id,
                "model": model,
                "output": a.output_text,
                "time_s": a.elapsed_seconds,
                "prompt_tokens": a.prompt_tokens,
                "completion_tokens": a.completion_tokens,
                "success": a.success,
                "error": a.error,
            }
            status = "OK" if a.success else f"FAIL: {a.error[:40]}"
            print(f"     {a.agent_type:20s} ({model:15s}) {a.elapsed_seconds:6.1f}s | "
                  f"{a.completion_tokens:4d} tok | {status}")

        save_json(idir / "layer4_execution.json", layer4)
        print(f"  L4 TOTAL: {target_result.total_elapsed_seconds:.0f}s | "
              f"{target_result.total_tokens} tokens")

        # Mode 3 draft comparison
        layer4_draft = None
        draft_output = speculation.manifest.draft_output if speculation else ""
        draft_agent_type = speculation.manifest.draft_agent_type if speculation else ""
        if draft_output and draft_agent_type:
            # Find target agent's output for comparison
            target_first = next((a.output_text for a in target_result.agent_outputs
                                 if a.agent_type == draft_agent_type), "")
            similarity = 0.0
            judge_accepted = False
            judge_score = 0.0
            judge_reason = ""
            if target_first and draft_output:
                similarity = compute_output_similarity(draft_output, target_first)
                judge_accepted, judge_score, judge_reason = judge_output_acceptance(
                    draft_output, target_first, clients["qwen2.5:14b"])

            layer4_draft = {
                "draft_agent": draft_agent_type,
                "draft_output": draft_output,
                "draft_time_ms": speculator.last_draft_time_ms if speculator else 0,
                "target_output_preview": target_first[:1000],
                "similarity": similarity,
                "judge_accepted": judge_accepted,
                "judge_score": judge_score,
                "judge_reason": judge_reason,
                "note": "Draft was executed INSIDE speculator.speculate() using llama3.1:8b, "
                        "not as a separate call. This is the real Mode 3 behavior.",
            }
            save_json(idir / "layer4_mode3_draft.json", layer4_draft)
            print(f"  L4 MODE 3 DRAFT (from Speculator): {draft_agent_type}")
            print(f"     Draft time: {speculator.last_draft_time_ms:.0f}ms | "
                  f"judge={judge_score:.2f} | accepted={judge_accepted}")
            print(f"     Reason: {judge_reason[:80]}")

        # ════════════════════════════════════════════════════
        # LAYER 5: LEARNER (Reinforcement Learning)
        # ════════════════════════════════════════════════════
        if baseline == "pythia":
            learner.record_outcome(intent, solver_plan, outcome)
        if speculator is not None and baseline != "oracle":
            speculator.record_outcome(intent, solver_plan, outcome.verdict)

        stats = learner.get_stats()
        convergence = learner.get_convergence_metrics()

        layer5 = {
            "layer": "5_learner",
            "baseline": baseline,
            "learner_active": baseline == "pythia",
            "input": {
                "verdict": outcome.verdict,
                "reward": outcome.reward,
                "salvage_ratio": outcome.salvage_ratio,
            },
            "state_update": {
                "phase": stats.phase,
                "total_interactions": stats.total_interactions,
                "unique_intent_keys": stats.unique_intent_keys,
                "mean_confidence": stats.mean_confidence,
                "mode_regressions": stats.mode_regressions,
                "active_drift_keys": stats.active_drift_keys,
            },
            "convergence": convergence,
            "fingerprint_summary": learner.fingerprint.summary_vector(),
        }
        save_json(idir / "layer5_learner.json", layer5)
        print(f"  L5 LEARNER: {'active' if baseline == 'pythia' else 'frozen/disabled'} | "
              f"phase={stats.phase} | conf={stats.mean_confidence:.3f}")

        # ════════════════════════════════════════════════════
        # TIMING SUMMARY
        # ════════════════════════════════════════════════════
        speedup = t_solver / t_spec if t_spec > 0 else 0
        timing = {
            "layer1_intent_ms": t_intent,
            "layer2_speculator_ms": t_spec,
            "layer2_solver_ms": t_solver,
            "layer2_solver_llm_ms": llm_call_ms,
            "layer2_solver_assign_ms": t_solver - llm_call_ms,
            "layer4_pipeline_s": target_result.total_elapsed_seconds,
            "layer4_draft_s": layer4_draft.get("draft_time_ms", layer4_draft.get("draft_time_s", 0)) if layer4_draft else 0,
            "speculator_vs_solver_speedup": speedup,
        }
        save_json(idir / "timing.json", timing)
        print(f"\n  ⏱  Speculator: {t_spec:.3f}ms | Solver: {t_solver:.0f}ms "
              f"({t_solver/1000:.1f}s) | Speedup: {speedup:.0f}x | Pipeline: "
              f"{target_result.total_elapsed_seconds:.0f}s")

        # Collect for summary
        all_events.append({
            "interaction": interaction,
            "request_id": req["id"],
            "baseline": baseline,
            "intent_task_type": intent.task_type,
            "intent_complexity": intent.complexity,
            "speculator_mode": speculation.mode if speculation else 0,
            "speculator_confidence": speculation.confidence if speculation else 0.0,
            "speculator_cache_hit": speculation.cache_hit if speculation else False,
            "speculator_time_ms": t_spec,
            "solver_agents": solver_agents,
            "solver_time_ms": t_solver,
            "verdict": outcome.verdict,
            "reward": outcome.reward,
            "salvage_ratio": outcome.salvage_ratio,
            "wasted_compute": outcome.wasted_compute,
            "redirect_cost": outcome.redirect_cost,
            "pipeline_time_s": target_result.total_elapsed_seconds,
            "pipeline_tokens": target_result.total_tokens,
            "draft_time_s": layer4_draft.get("draft_time_ms", 0) if layer4_draft else 0,
            "draft_accepted": layer4_draft["judge_accepted"] if layer4_draft else None,
            "learner_phase": stats.phase,
            "learner_confidence": stats.mean_confidence,
            "speedup": speedup,
            # Per-agent cost for E metric
            "agent_costs": {a.agent_type: a.allocated_tokens * fleet.get_member(a.fleet_member_id).cost_rate
                           for a in solver_plan.assignments},
        })

    # ════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ════════════════════════════════════════════════════
    from collections import Counter
    n = len(all_events)

    # --- Core metrics ---
    verdicts = dict(Counter(e["verdict"] for e in all_events))
    hit_rate = sum(1 for e in all_events if e["verdict"] in ("COMMIT", "PARTIAL")) / n if n > 0 else 0

    # --- W: Wasted Compute Ratio (§6.4) ---
    total_wasted = sum(e.get("wasted_compute", 0) for e in all_events)
    total_spec_compute = sum(
        len(e["solver_agents"]) * config["reconciliation"]["C_spec"]
        for e in all_events
    )
    W = total_wasted / total_spec_compute if total_spec_compute > 0 else 0.0

    # --- N_conv: Convergence point (§6.3) ---
    # First interaction where rolling hit rate stays above tau_2 for 3+ consecutive
    N_conv = n  # default: never converged
    hits = [1 if e["verdict"] in ("COMMIT", "PARTIAL") else 0 for e in all_events]
    window = min(3, n)
    for i in range(window - 1, n):
        rolling = sum(hits[i - window + 1:i + 1]) / window
        if rolling >= 0.5:  # tau_2
            N_conv = i + 1
            break

    # --- E: Cost Efficiency (§6.4) ---
    total_cost = sum(
        sum(costs.values()) for e in all_events
        for costs in [e.get("agent_costs", {})]
    )
    total_tokens = sum(e["pipeline_tokens"] for e in all_events)

    # --- Dispatch latency L (§6.2) ---
    # For NS/SH: dispatch latency = solver time only (no overlap)
    # For Pythia/SwoL/Oracle: dispatch latency = max(solver, speculator) but
    #   speculation runs in parallel, so effective = solver_time (speculator is hidden)
    dispatch_latencies = []
    for e in all_events:
        if baseline in ("ns", "sh"):
            dispatch_latencies.append(e["solver_time_ms"])
        else:
            # Effective dispatch latency = solver time (speculation overlapped)
            dispatch_latencies.append(e["solver_time_ms"])

    summary = {
        "run_dir": str(run_dir),
        "baseline": baseline,
        "config": config,
        "total_interactions": n,
        # §6.2 Dispatch Latency
        "mean_dispatch_latency_ms": sum(dispatch_latencies) / n if n else 0,
        "mean_solver_ms": sum(e["solver_time_ms"] for e in all_events) / n if n else 0,
        "mean_speculator_ms": sum(e["speculator_time_ms"] for e in all_events) / n if n else 0,
        "mean_speedup": sum(e["speedup"] for e in all_events) / n if n else 0,
        "mean_pipeline_s": sum(e["pipeline_time_s"] for e in all_events) / n if n else 0,
        # §6.3 Speculation Accuracy
        "verdicts": verdicts,
        "hit_rate": hit_rate,
        "mode_distribution": dict(Counter(e["speculator_mode"] for e in all_events)),
        "N_conv": N_conv,
        # §6.4 Cost Analysis
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "net_benefit": sum(e["reward"] for e in all_events),
        "wasted_compute_ratio_W": W,
        "mean_salvage_ratio": sum(e.get("salvage_ratio", 0) for e in all_events) / n if n else 0,
        # Learner state
        "phase_at_end": all_events[-1]["learner_phase"],
        "confidence_at_end": all_events[-1]["learner_confidence"],
    }

    save_json(run_dir / "summary.json", summary)
    save_json(run_dir / "all_results.json", {"summary": summary, "events": all_events})

    print(f"\n{'━'*70}")
    print(f"  {baseline_labels[baseline]} — COMPLETE")
    print(f"{'━'*70}")
    print(f"  Directory:  {run_dir}")
    print(f"\n  §6.2 Dispatch Latency:")
    print(f"    Mean Solver:         {summary['mean_solver_ms']:.0f}ms ({summary['mean_solver_ms']/1000:.1f}s)")
    print(f"    Mean Speculator:     {summary['mean_speculator_ms']:.1f}ms")
    print(f"    Mean Dispatch L:     {summary['mean_dispatch_latency_ms']:.0f}ms")
    print(f"    Mean Pipeline:       {summary['mean_pipeline_s']:.0f}s")
    print(f"\n  §6.3 Speculation Accuracy:")
    print(f"    Verdicts:            {verdicts}")
    print(f"    Hit rate (H):        {100*hit_rate:.0f}%")
    print(f"    Modes:               {summary['mode_distribution']}")
    print(f"    N_conv:              {N_conv}")
    print(f"\n  §6.4 Cost Analysis:")
    print(f"    Total tokens:        {total_tokens}")
    print(f"    Total cost (E):      {total_cost:.4f}")
    print(f"    Wasted ratio (W):    {W:.3f}")
    print(f"    Net benefit:         {summary['net_benefit']:.1f}")
    print(f"    Mean salvage (σ):    {summary['mean_salvage_ratio']:.2f}")
    print(f"\n  Learner: {summary['phase_at_end']} (conf={summary['confidence_at_end']:.3f})")


if __name__ == "__main__":
    main()
