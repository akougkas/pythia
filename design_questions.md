# Design & Evaluation Questions — Meeting Agenda

**Status 2026-04-20:** §1–§4 drafted; §5/§6 mostly PLACEHOLDERs; code diverged from paper narrative. Each item below needs a ~2-minute decision. Priority: P0 = blocker, P1 = important, P2 = nice-to-have.

---

## A. Architecture (§3.1)

### A1. What is the Speculative Dispatcher? [P0]

- **A1.1** Cache hit (built-in cache): use most-recent plan, or aggregate over recent plans? 
- **A1.2** Cache miss: empty draft (Mode-1 only) or LLM draft model?
- **A1.3** If draft model exists, is it a separate box in Fig 1?
- **A1.4** Intent-key for the built-in cache: `(task_type, complexity_bucket, primary_tag)` (code) or `(task_type, domain_tags, complexity_level)` (paper), which one to use?

### A2. Draft latency target [P0]

- **A2.1** Is the Intent Detector's "sub-ms" claim realistic? Currently, we use rule-based method, model-based classification is long.
- **A2.2** What number do we claim for $L_{spec\_pred}$?

### A3. Mode 1 decomposition [P0]

- **A3.1** Do we need to split Mode 1 into intent-only (agent-agnostic) vs. plan-aware (agent-specific) work?
- **A3.2** If split: does agent-prompt preloading move to Mode 2?
- **A3.3** If not split: acknowledge Mode 1 has non-zero misprediction cost?

### A4. Orchestrator lifecycle [P1]

*Context: the Orchestrator is currently a one-shot `reconcile()` function in code. In practice it must manage a per-request lifecycle because the Solver and Speculative Dispatcher run in parallel with different completion times.*

- **A4.1 Stateful or reactive?** Is the Orchestrator a stateful component with explicit phases (e.g., `IDLE → SPECULATING → RECONCILING → EXECUTING → DONE`) that it advances per request, or a stateless reactive function that the caller drives? (Current code: stateless. Proposal: stateful per-request.)
- **A4.2 In-flight speculation when $P^*$ arrives.** The Solver returns its plan while Mode 2 provisioning (or Mode 3 draft execution) may still be running. Two choices: **(a)** immediately pause/kill in-flight speculation, then reconcile on whatever is done so far; **(b)** let speculation continue in parallel with reconciliation, then commit-or-flush once the verdict is issued. CPU pipelines do (b). Proposal: (b). Confirm.
- **A4.3 Does the A4.2 rule need mode-specific carve-outs?** A4.2 answers "what do we do with speculation that is still running when $P^*$ arrives." But the nature of that running work differs by mode, and the right answer may differ too:
    - *Mode 1* — fetching context docs, warming MCP connections. Cheap, I/O-bound, agent-independent. Letting it finish costs nothing and helps regardless of the verdict. **No special handling needed.**
    - *Mode 2* — provisioning agents (allocating GPU slots, opening API connections, loading configs). Interrupting mid-provisioning can leave resources half-allocated (leaked connections, held GPU memory). **Choice: finish provisioning even if doomed to flush, or actively tear down mid-way.**
    - *Mode 3* — draft agent is actively generating LLM tokens. Interrupting mid-generation wastes the partial output and still bills the tokens consumed. **Choice: stop immediately on $P^*$ arrival, stop at next natural boundary (end of current LLM call), or let the full draft complete.**

    **The question:** Is A4.2 a single uniform rule ("always let speculation finish, then reconcile"), or do we need to describe three separate rules (one per mode) to be honest about the trade-offs? Uniform is simpler to explain; per-mode is more accurate to implementation.

### A5. Plan comparison [P0]

- **A5.1** Match key: `(agent_type, fleet_member_id)` only, or also prompt/order/deps?
- **A5.2** COMMIT = identical plans, or $\hat{P} \subseteq P^*$?
- **A5.3** What if assignments match but DAG differs?
- **A5.4 Prompt equivalence.** If A5.1 includes prompts, exact string match is brittle — the LLM Solver produces semantically equivalent but textually different prompts across runs. Exact match, embedding similarity, or drop prompt from the key?
- **A5.5 Minimum salvage floor.** PARTIAL fires on any non-empty intersection. If only 1 of 5 agents matches, re-initializing 4 may cost more than a full flush. Define $\sigma_{min}$ below which PARTIAL auto-promotes to FLUSH? (Related: B3.)
- **A5.6 Plan canonicalization before caching.** The LLM Solver is non-deterministic for the same intent (different prompts, different orderings). Without normalization, the cache stores the last plan's exact form and the next identical request spuriously misses. Do we normalize (sort assignments, canonical prompt form, stable tiebreaks) before caching and comparison?

### A6. Data contracts [P1]

- **A6.1** Dispatcher outputs `DispatchPlan` or `SpeculationResult`? Does both 'Solver' and 'Dispatch Solver' return `DispatchPlan`? 
- **A6.2** Who owns fleet-reservation side effects?

---

## B. Speculation & Cost Model (§3.2)

### B1. Mode 3 scope [P0]

- **B1.1** Separate draft LLM, or reuse first cached agent?
- **B1.2** Verify plan identity or draft output?
- **B1.3** Evaluate Mode 3 end-to-end or cut to Modes 1–2?

### B2. Cost-model parameters [P0]

- **B2.1** $C_{penalty}$ measured offline or estimated online?
- **B2.2** $L_{init}$ parallel vs. sequential definition?
- **B2.3** $\tau_2^*, \tau_3^*$ per-intent-class or global?
- **B2.4** Are `ReconciliationConfig` defaults principled or hand-tuned?

### B3. Salvage ratio [P1]

- **B3.1** $\sigma$ formula: $|P^* \cap \hat{P}|/|\hat{P}|$ (paper) or $/\min(|P^*|,|\hat{P}|)$ (code)?
- **B3.2** Weighted by agent cost, or uniform?

### B4. Resource-contention assumption [P1]

*Reference: §3.2.3, right after the PARTIAL-commit latency equation. The paper currently states:*
> *"We assume that cleaning up and re-provisioning mismatched agents contends for shared resources (e.g., GPU memory, rate limits), preventing correctly retained agents from beginning execution until all re-provisioning completes."*

*This is what "cleanup blocks correct agents" refers to: on a PARTIAL commit, the correctly-predicted agents (the $\bar{\sigma}$ fraction) cannot start executing until the mispredicted $(1-\bar{\sigma})$ fraction has been torn down and re-provisioned, because both share the same finite pool of resources. This assumption is what makes the PARTIAL-commit latency $L_{partial} = L_s + (1-\bar{\sigma})(C_{penalty} + L_{init}) + L_{exec}$ — it treats the correct fraction as gated by the worst-case cleanup of the wrong fraction.*

- **B4.1** Is this assumption empirically true in our deployment, or an analytical worst case? In practice: GPU cleanup can be async, API rate limits only bind for same-provider agents, and correctly-provisioned agents on *different* fleet members (e.g., Claude Haiku for `review`) should not be blocked by a cleanup on `qwen2.5-14b-gpu`. Do we need a microbenchmark measuring whether correct agents actually wait for cleanup, or do we relax the model (treat $C_{penalty}$ as average, not blocking)?

### B5. Wasted-compute denominator [P2]

- **B5.1** Define $R_{total}$ precisely — on COMMIT there is no separate non-speculative execution.

---

## C. Resource-Aware Dispatch (§3.3)

### C1. ILP vs. greedy [P1]

- **C1.1** Keep ILP as spec + greedy as impl, or rewrite §3.3 to describe greedy?
- **C1.2** Do we need a small-instance ILP comparison to validate greedy quality?

### C2. Live fleet state [P2]

- **C2.1** How does the Solver read rate_limit and token_budget at dispatch time?
- **C2.2** Do Solver and Dispatcher share fleet state?

### C3. Affinity [P2]

- **C3.1** State `compatible(a, f)` definition (set membership over capabilities).

---

## D. Learner (§3.4 / §4)

### D1. Paper ↔ code mismatch [P0]

- **D1.1** Rewrite §4 as Bayesian + drift (what we built), or build the policy-gradient model before deadline?
- **D1.2** Dispatch fingerprint: neural encoder (paper) or window summary (code)?
- **D1.3** Convergence citation for the Bayesian formulation?

### D2. Reward parameters [P1]

- **D2.1** Are $L_{saved}, C_{redirect}, C_{flush}$ the same as §3.2.3, or reparameterized?
- **D2.2** Is $L_{saved}$ in seconds, ratio, or dimensionless?

### D3. Update cadence [P1]

- **D3.1** Synchronous (current code) or asynchronous? Document.

### D4. Progressive activation [P1]

- **D4.1** $N_1, N_2$: emergent or hyperparameter?
- **D4.2** Do phase caps (0.3, 0.75) replace or layer on top of $\tau_2^*, \tau_3^*$?

### D5. Drift regression [P1]

- **D5.1** Per-intent-key or global?
- **D5.2** Recovery path: 1→2→3 on consecutive hits?
- **D5.3** Default `drift_threshold` = 0.3 — justify or tune.

### D6. Cold-start priors [P2]

- **D6.1** Multi-tenant priors: in scope, or future work?

---

## E. Implementation (§5)

### E1. Clio Coder framing [P0]

- **E1.1** Clio Coder doesn't exist. Drop the framing, or describe the proxy we actually built?

### E2. Component details [P1]

- **E2.1** Intent Detector: document the rule-based + spaCy ensemble.
- **E2.2** Speculative Dispatcher: which A1.x wins?
- **E2.3** Reconciliation: cheap vs. expensive redirect cost.
- **E2.4** Learner: framework, persistence, update path.

### E3. Deployment [P0]

- **E3.1** Hardware: local, cloud, HPC — list specs.
- **E3.2** Providers in evaluation: qwen2.5, llama3.1, haiku, sonnet, opus — all five?
- **E3.3** Rate limits / token budgets per provider.

### E4. Prototype stats [P2]

- **E4.1** LOC count.
- **E4.2** Test coverage (CLAUDE.md target: 80%).

### E5. Solver fidelity [P1]

- **E5.1** Is Claude Sonnet/Opus a realistic Solver stand-in, or a deliberate worst-case?

---

## F. Evaluation (§6)

### F1. Workloads [P0]

- **F1.1** Task count per workload.
- **F1.2** Task source: hand-written, LLM-generated, or real traces?
- **F1.3** HPC-CG description is self-contradictory — rewrite per the inline-comment fix.
- **F1.4** Difficulty stratification definition.

### F2. Baselines [P0]

- **F2.1** NS: same Solver, no speculation?
- **F2.2** SH: rule table = `_AGENT_PIPELINES` in code?
- **F2.3** SwoL = Pythia with Learner disabled?
- **F2.4** Oracle: how is it implemented?

### F3. Metrics [P0]

- **F3.1** $L$: arrival to first agent output — precise definition?
- **F3.2** $Q$: judge model + rubric?
- **F3.3** $H$: does PARTIAL count as hit uniformly?
- **F3.4** $N_{conv}$: define X% and Y consecutive.
- **F3.5** $E$: tokens, dollars, GPU-seconds — pick two.
- **F3.6** $S$: feasible max fleet size?

### F4. Protocol [P0]

- **F4.1** Repetitions per configuration (≥10?).
- **F4.2** Interactions per run (must cover $N_2$).
- **F4.3** Runs independent across workloads?
- **F4.4** Fresh Learner per run — confirm.
- **F4.5** What happens when the Solver LLM fails (retry, exclude, flag)?

### F5. Threshold ablation [P1]

- **F5.1** Is $\tau_2$ grid a global override over the cost-model threshold?

### F6. Heterogeneity experiment [P1]

- **F6.1** Do we actually have a homogeneous deployment, or is it synthetic?

### F7. Scalability [P1]

- **F7.1** Which members added at fleet size 2/4/8/16/32?
- **F7.2** Which agent types at 2/4/6/8?

### F8. Attribution [P1]

- **F8.1** How do we separate Mode 2 gain from Mode 1 context-prefetch gain?

### F9. Negative-result bar [P1]

- **F9.1** Define the threshold below which we drop Mode 3 from the contribution list.
- **F9.2** Define the contingency if Learner doesn't converge.

### F10. Judge validation [P1]

- **F10.1** Human-labeled sanity-check set (N ≥ 30)?

### F11. §2.5 reuse [P2]

- **F11.1** Is §2.5's data reused in §6, or re-collected?

---

## G. Cross-Cutting

### G1. Section numbering [P1]

- **G1.1** Is the Learner §3.4 or §4? Align all cross-refs.
- **G1.2** Consolidate $L_{spec}$, $L_{spec\_pred}$, $L_{spec\_dispatch}$ into one symbol.

### G2. Claim→code traceability [P0]

- **G2.1** Every §3.2.3 equation has a test?
- **G2.2** Every §6.1 metric has a collection path?
- **G2.3** §4.3 convergence tested on a synthetic trace?

### G3. Figure budget [P2]

- **G3.1** 7 figures + 1 table in 10 pages — feasible? Cut candidates?

### G4. Bibliography [P2]

- **G4.1** Resolve `[CITE:foo]` sentinels (feitelson2004, agarwal2014, kocher2019, seznec2011).

---

## H. Go/No-Go Before §5 / §6 Writing

Must be locked: **A1, A2, A3, A5, B1, B2, D1, E1, E3, F1, F2, F3, F4, G1, G2.**

---

## Owners

- **Jie:** A, B, C, D, G
- **Shazzadul:** E, F
- **Shared:** G1, G4

Decisions from the meeting → `.planning/CONTEXT.md` as locked decisions.
