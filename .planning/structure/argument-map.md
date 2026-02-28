# Argument Map

## Central Thesis

The draft-target speculation paradigm generalizes from CPU architecture and LLM inference to multi-agent orchestration, enabling a speculative dispatcher that reduces end-to-end dispatch latency through predictive pre-execution and a reinforcement learning feedback loop.

## Supporting Claims

### C1: Dispatch planning is a latency bottleneck in multi-agent systems
- **Evidence needed**: Profiling data from Cleo Coder showing dispatch planning + setup as fraction of end-to-end latency
- **Supports**: Motivation for speculation — you can't optimize what isn't a bottleneck
- **Section**: §2 (Background & Motivation)

### C2: Dispatch decisions are predictable for recurring intent patterns
- **Evidence needed**: Empirical analysis of dispatch decision entropy given intent classification; show that most users have a handful of common task types
- **Supports**: Speculation is viable — if dispatch were random, prediction would fail
- **Section**: §2 (Background & Motivation)

### C3: The draft-target pattern maps structurally to orchestration
- **Evidence needed**: Formal parallel between CPU speculation / LLM speculative decoding / speculative dispatch — same cost model structure, same commit/flush semantics
- **Supports**: This is a generalizable abstraction, not an ad-hoc heuristic
- **Section**: §3 (Speculative Dispatch)

### C4: Three speculation modes form a progressive risk/reward hierarchy
- **Evidence needed**: Cost model derivation for each mode; break-even accuracy thresholds; Mode 1 is nearly always beneficial, Mode 3 is highest payoff but highest risk
- **Supports**: Practical deployability — system can be tuned to risk tolerance
- **Section**: §3 (Speculative Dispatch)

### C5: RL-based learning improves speculation accuracy over time
- **Evidence needed**: Learning curves showing hit rate improvement; regret bounds or convergence analysis; comparison of learned vs. static heuristics
- **Supports**: The system gets better with use — differentiator from static approaches
- **Section**: §4 (Learner-Augmented Speculation)

### C6: The cost model correctly predicts when speculation pays off
- **Evidence needed**: Theoretical derivation of break-even threshold; empirical validation that observed hit rates exceed threshold for mature system
- **Supports**: Principled deployment criteria, not just "try it and see"
- **Section**: §3 + §6 (Evaluation)

### C7: Implementation is practical on real heterogeneous infrastructure
- **Evidence needed**: Working prototype details; deployment across local/cloud/HPC nodes; handling of API rate limits, token budgets, cost constraints
- **Supports**: This isn't a simulation study — real system on real infrastructure
- **Section**: §5 (Implementation)

### C8: Measured latency reductions are significant across workload types
- **Evidence needed**: Dispatch latency measurements with/without speculation across 4 workload types, 4 baselines, 3 modes; statistical rigor
- **Supports**: The central claim actually works in practice
- **Section**: §6 (Evaluation)

## Argument Flow

```
C1 (dispatch is bottleneck) + C2 (dispatch is predictable)
    → THEREFORE speculation is viable and worthwhile
    → C3 (paradigm maps structurally)
        → C4 (three modes provide progressive speculation)
        → C6 (cost model predicts break-even)
    → C5 (learner improves accuracy over time)
    → C7 (practical implementation exists)
    → C8 (measured results confirm the thesis)
```

## Potential Weaknesses / Reviewer Objections

| Objection | Pre-emptive Response | Where Addressed |
|-----------|---------------------|-----------------|
| "This is just caching/prefetching, not speculation" | Formally distinguish: caching reuses past results; speculation predicts *future* dispatch and begins execution before verification | §3 (cost model formalism) |
| "Cold-start means system is useless initially" | Mode 1 (context prep) provides immediate value; cold-start strategy using aggregate priors | §4 + §7 |
| "Single-user evaluation isn't convincing" | SC papers often evaluate single-user; multi-tenant is explicit future work; focus is on the paradigm | §6 + §7 |
| "Misprediction waste could be expensive" | Cost model gives precise break-even; wasted compute ratio quantified; confidence thresholds gate aggressive modes | §3 (cost model) + §6 (ablation) |
| "Why not just make the solver faster?" | Orthogonal optimization; speculation provides latency hiding regardless of solver speed; faster solver raises the break-even bar but speculation still adds value | §3 + §7 |
| "Security implications (Spectre analogy)" | Acknowledged directly; speculative context access risks discussed; future work for formal model | §7 (Discussion) |

## Gaps to Investigate

- [ ] What is the actual dispatch latency breakdown in current multi-agent systems? Need empirical characterization.
- [ ] How does the cost model interact with provider-specific constraints (API rate limits, token pricing)?
- [ ] What is the minimum interaction history for the Learner to outperform static heuristics?
- [ ] Partial commit protocol: precise semantics for redirecting an agent mid-execution?
