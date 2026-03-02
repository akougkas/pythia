# Pythia Sprint Plan — SC26 Submission

**Start**: March 3, 2026
**Paper deadline**: April 8, 2026 (hard)
**AD appendix deadline**: April 24, 2026
**Team**: Prof. Kougkas (PI), Jie (senior PhD), Shazzadul (PhD, agents)

## Critical Path

```
Week 1: Implementation skeleton + profiling data
    ↓
Week 2: Core implementation (Modes 1–3) + baseline systems
    ↓
Week 3: Evaluation pipeline + run experiments
    ↓
Week 4: Fill all PLACEHOLDERs + figures + paper trim
    ↓
Week 5: Polish, compile, internal review, submit
```

## Week-by-Week

### Week 1 (March 3–9): Foundation

**Goal**: Runnable skeleton with tests; profiling data for §2.4.

| Task | Owner | Delivers | Paper section |
|------|-------|----------|---------------|
| Instrument Clio Coder dispatch pipeline, collect latency breakdown | Jie | Profiling data for §2.4 PLACEHOLDERs | §2.4 |
| Dispatch predictability analysis (intent entropy) | Jie | Conditional entropy numbers for §1, §2.4 | §1, §2.4 |
| Define Intent, DispatchPlan, SpeculationResult data contracts in code | Shazzadul | `src/contracts.py` with types | §3.1, §5.1 |
| Implement Intent Detector (classifier or prompted LLM) | Shazzadul | Working intent classification | §5.1 |
| Write test suite from §3.4 cost model equations | Both | `tests/test_cost_model.py` | §3.4 |
| Fix 4 broken citation keys in references.bib | Either | Clean bibliography | All |
| Create Figures 1 (architecture) and 2 (mode hierarchy) | Either | TikZ or PDF figures | §3.1, §3.2 |

**Checkpoint**: Profiling data fills §2.4 PLACEHOLDERs. Data contracts are implemented and tested.

### Week 2 (March 10–16): Core Implementation

**Goal**: Speculative Dispatcher, Reconciliation Engine, and Learner are implemented and tested.

| Task | Owner | Delivers | Paper section |
|------|-------|----------|---------------|
| Implement Dispatch Solver (target) | Jie | Working solver with constraint optimization | §3.5, §5.1 |
| Implement Speculative Dispatcher (draft) — all 3 modes | Jie | Prediction + pre-execution pipeline | §3.2, §5.1 |
| Implement Reconciliation Engine (COMMIT/PARTIAL/FLUSH) | Jie | Working reconciliation with salvage ratio | §3.3, §5.1 |
| Implement Learner (contextual bandit, policy network) | Shazzadul | Working RL loop with dispatch fingerprint | §4.1, §5.1 |
| Implement progressive activation logic | Shazzadul | Mode gating by confidence threshold | §4.2, §5.1 |
| Build 4 baseline systems (NS, SH, SwoL, OS) | Shazzadul | Runnable baselines for comparison | §6.1 |
| Fill §5 Implementation PLACEHOLDERs from actual code | Both | Complete §5 section | §5 |
| Update paper main.tex with §2.4 data and §5 details | Either | Updated LaTeX | §2, §5 |

**Checkpoint**: End-to-end dispatch works speculatively. All baselines run. §5 PLACEHOLDERs filled.

### Week 3 (March 17–23): Evaluation

**Goal**: All experiments run. Raw data collected.

| Task | Owner | Delivers | Paper section |
|------|-------|----------|---------------|
| Design and implement 4 workload suites (HPC-CG, SDP, RWA, DMB) | Both | Reproducible workload generators | §6.1 |
| Run dispatch latency experiments (all workloads × baselines × modes) | Shazzadul | Latency data for §6.2 | §6.2 |
| Run Learner convergence experiments (hit rate over time) | Shazzadul | Learning curve data for §6.3 | §6.3 |
| Run cost analysis (wasted compute vs. threshold) | Jie | Pareto frontier data for §6.4 | §6.4 |
| Run ablation studies (modes, thresholds, windows, heterogeneity) | Both | Ablation table data for §6.5 | §6.5 |
| Run scalability experiments (fleet size, agent count) | Jie | Scalability data for §6.6 | §6.6 |
| Begin filling §6 PLACEHOLDERs as data arrives | Both | Partial §6 completion | §6 |

**Checkpoint**: All experiments complete. Raw data available. §6 PLACEHOLDERs being filled.

**RISK GATE**: If results diverge from paper claims, STOP here. Discuss with PI. See Risk Register below.

### Week 4 (March 24–30): Integration

**Goal**: Paper is complete — all PLACEHOLDERs filled, all figures created, word budget met.

| Task | Owner | Delivers | Paper section |
|------|-------|----------|---------------|
| Fill remaining §6 PLACEHOLDERs (30+) | Both | Complete evaluation section | §6 |
| Fill §1, §7, §8 result PLACEHOLDERs (~10) | Either | Complete intro/discussion/conclusion | §1, §7, §8 |
| Create Figures 4–8 and Table 7 from experimental data | Both | Publication-quality figures | §6 |
| Trim all sections to word budget (currently ~10% over) | Both | ≤ 7,500 words | All |
| Run `/wtfp:review-section` on all 8 sections | Both | Clean review reports | All |
| Run `/wtfp:audit-milestone` for full status | Either | Milestone audit report | — |
| Compile final LaTeX, verify formatting | Either | Clean PDF | paper/ |

**Checkpoint**: Paper is submission-ready pending final review.

### Week 5 (March 31–April 7): Polish & Submit

**Goal**: Internal review, final polish, submission.

| Task | Owner | Delivers |
|------|-------|----------|
| PI review of full paper | Prof. Kougkas | Feedback |
| Address PI feedback | Both | Revised paper |
| Cross-reference check (all §X references resolve) | Either | Clean cross-refs |
| Final bibliography audit (`/wtfp:check-refs`) | Either | Clean bib |
| Double-anonymous compliance check | Both | No author identification |
| Final LaTeX compilation + PDF review | Either | Submission PDF |
| **SUBMIT** (April 8) | Prof. Kougkas | Submitted paper |

### Post-Submission (April 9–24)

- Write Artifact Description (AD) appendix
- Clean and package code for reproducibility
- Submit AD by April 24

## Student Assignments

### Jie (Senior PhD)
**Primary**: Formal methods and systems architecture.
- Cost model implementation and validation (§3.4)
- Dispatch Solver and Reconciliation Engine (§3.3, §3.5)
- Speculative Dispatcher core logic (§3.2)
- Profiling and instrumentation of Clio Coder (§2.4)
- Cost analysis and scalability experiments (§6.4, §6.6)

### Shazzadul (PhD, Agents)
**Primary**: RL/agent systems and evaluation.
- Learner implementation (contextual bandit, policy network, fingerprint) (§4)
- Intent Detector and agent integration (§5.1)
- Baseline systems (NS, SH, SwoL, OS) (§6.1)
- Workload suite design (§6.1)
- Dispatch latency and accuracy experiments (§6.2, §6.3)

### Shared
- Data contracts and interfaces
- Workload design (collaborate on realistic scenarios)
- Ablation studies
- Paper sections §1, §2, §7, §8
- Figures and tables
- Bibliography maintenance

## Co-Development Cycles

Every 2–3 days, run this cycle:

1. **Code check**: Does the implementation match what the paper describes?
2. **Paper check**: Does the paper accurately describe what the code does?
3. **Data check**: Are new experimental results reflected in the paper?
4. **Test check**: Do all tests pass? Is coverage adequate?
5. **PLACEHOLDER check**: Run `/wtfp:check-todos` — how many remain?

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Speculation doesn't reduce latency | Low | Fatal | Check implementation correctness first. If correct, reframe contribution around cost model and abstraction (formal contribution vs. empirical). |
| Learner doesn't converge | Medium | High | Simplify RL to lookup-table or nearest-neighbor. Progressive activation story still holds with simpler learning. Reduce claim scope. |
| Mode 3 is never profitable | Medium | Medium | Drop Mode 3 from primary contribution. Two-mode (1+2) speculation is still novel and publishable. Mode 3 becomes future work. |
| Profiling shows dispatch isn't a bottleneck | Low | Fatal | Redefine "bottleneck" — even 20% of latency is worth optimizing. Or shift to a different workload where it is. |
| Can't finish implementation in time | Medium | High | Prioritize Modes 1+2 only. Simulation-based evaluation for Mode 3. Reduce evaluation scope to 2 workloads. |
| Word budget blown | Low | Low | Trim §2 (catalog-heavy), §4 (analogy-heavy), §7 (future work). These compress easily. |
