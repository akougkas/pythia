# Paper Outline — Speculative Dispatch for Multi-Agent Orchestration Systems

**Venue**: SC26 (IEEE proceedings)
**Budget**: ~7,500 words (10 pages, two-column, IEEE template)

## Word Budget

| # | Section | Words | Ratio | Notes |
|---|---------|-------|-------|-------|
| 1 | Introduction | 1,050 | 0.14 | Problem, motivation, contributions list, organization |
| 2 | Background & Motivation | 1,125 | 0.15 | Speculation fundamentals, multi-agent orchestration, empirical motivation |
| 3 | Speculative Dispatch | 1,500 | 0.20 | Architecture, three modes, cost model, reconciliation protocol |
| 4 | Learner-Augmented Speculation | 900 | 0.12 | RL formulation, cold start, convergence |
| 5 | Implementation | 600 | 0.08 | Prototype details, data contracts, deployment |
| 6 | Evaluation | 1,500 | 0.20 | Setup, all experiments, ablations, figures |
| 7 | Discussion | 450 | 0.06 | Limitations, security (Spectre analogy), future work |
| 8 | Conclusion | 375 | 0.05 | Summary of contributions |
| — | **Total** | **7,500** | **1.00** | |

## Section Breakdown

### §1 Introduction (1,050 words)

- **1.1 Problem Statement** — Multi-agent AI systems are entering HPC workflows; orchestration is becoming a latency bottleneck. Current approach: sequential intent → plan → dispatch → execute.
- **1.2 Insight** — The dispatch bottleneck mirrors problems solved by CPU speculative execution and LLM speculative decoding. Dispatch decisions are predictable; verification is cheaper than stalling.
- **1.3 Contributions** — Numbered list:
  1. Speculative dispatch abstraction (three-mode hierarchy + reconciliation protocol)
  2. Learner-augmented speculation model (RL-based, improves with use)
  3. Resource-aware dispatch solver for heterogeneous infrastructure
  4. Implementation and evaluation on realistic HPC-adjacent workloads
- **1.4 Organization** — 1–2 sentences mapping sections.

### §2 Background & Motivation (1,125 words)

- **2.1 Speculative Execution in CPU Architecture** — Brief primer: branch prediction, speculative execution, commit/flush, cost model. Leverage SC audience's familiarity. (~200 words)
- **2.2 Speculative Decoding in LLM Inference** — Draft model generates, target model verifies in one forward pass. Key papers. Acceptance rate. Cost model parallel. (~300 words)
- **2.3 Multi-Agent Orchestration** — Current frameworks (CrewAI, AutoGen, LangGraph). Dispatch problem. No speculation in existing systems. (~250 words)
- **2.4 Empirical Motivation** — Profiling data from Clio Coder: dispatch latency breakdown, predictability of dispatch decisions for recurring intents. (~250 words)
- **2.5 Positioning** — Table showing CPU speculation / LLM speculation / our speculation side-by-side. Novelty gap. (~125 words)

### §3 Speculative Dispatch (1,500 words)

- **3.1 Architecture Overview** — Five-layer pipeline diagram (Intent Detector, Dispatch Solver, Speculative Dispatcher, Orchestrator, Learner). Data contracts. (~250 words + figure)
- **3.2 Speculation Modes** — Mode 1 (context prep / cache prefetch), Mode 2 (agent pre-dispatch / branch speculation), Mode 3 (draft execution with verification / speculative decoding). Progressive risk/reward. (~400 words)
- **3.3 Reconciliation Protocol** — Commit, partial commit, flush semantics. State salvage in partial commits. Agent redirection. (~250 words)
- **3.4 Cost Model** — Formal derivation: break-even speculation accuracy as function of solver latency, pre-execution cost, flush cost. Per-mode analysis. Threshold equation. (~400 words + equations)
- **3.5 Resource-Aware Dispatch** — Heterogeneous infrastructure constraints: compute, memory, API limits, token budgets, cost budgets. Connection to HPC scheduling. (~200 words)

### §4 Learner-Augmented Speculation (900 words)

- **4.1 RL Formulation** — State space (intent + fleet state), action space (speculative dispatch plan), reward signal (commit = positive, flush = negative proportional to waste). (~300 words + equations)
- **4.2 Progressive Activation** — Cold start → Mode 1 default → Mode 2 after N interactions → Mode 3 for high-confidence intents. Parallel to CPU predictor evolution. (~250 words)
- **4.3 Convergence and Adaptation** — Regret bounds or convergence guarantees. Concept drift detection. Model refresh. Non-stationary behavior handling. (~350 words)

### §5 Implementation (600 words)

- **5.1 Prototype** — Built on Clio Coder. Component interfaces. Models and agents used. Languages, libraries, infrastructure. (~350 words)
- **5.2 Deployment** — Heterogeneous setup: local workstations, cloud instances, HPC nodes. Provider constraints as first-class parameters. (~250 words)

### §6 Evaluation (1,500 words)

- **6.1 Experimental Setup** — 4 workloads (HPC code gen, data pipelines, research workflows, micro-benchmarks). 4 baselines. Metrics. (~250 words)
- **6.2 Dispatch Latency** — End-to-end latency reduction across modes. Primary result. (~300 words + figure)
- **6.3 Speculation Accuracy** — Hit rate over time. Learning curves. Comparison to static heuristics. (~250 words + figure)
- **6.4 Cost Analysis** — Wasted compute ratio vs. confidence threshold. Cost efficiency with/without speculation. Pareto frontier. (~250 words + figure)
- **6.5 Ablation Studies** — Mode combinations, threshold sensitivity, history window, infrastructure heterogeneity. (~250 words + table)
- **6.6 Scalability** — Fleet size, agent count, search space complexity. (~200 words + figure)

### §7 Discussion (450 words)

- **7.1 Limitations** — Cold start, adversarial/unpredictable workloads, single-user evaluation scope. (~200 words)
- **7.2 Security Implications** — Spectre analogy: speculative context access in multi-tenant deployments. (~125 words)
- **7.3 Future Directions** — Federated learning, Slurm integration, transfer learning across projects. (~125 words)

### §8 Conclusion (375 words)

- Summary of contributions. Key results. Implications for HPC + AI systems convergence.

## Figures & Tables Budget

| # | Type | Description | Section |
|---|------|-------------|---------|
| 1 | Figure | Architecture diagram (5-layer pipeline) | §3.1 |
| 2 | Table | CPU / LLM / Agent speculation parallel | §2.5 |
| 3 | Figure | Three speculation modes diagram | §3.2 |
| 4 | Figure | Dispatch latency comparison (primary result) | §6.2 |
| 5 | Figure | Speculation hit rate learning curves | §6.3 |
| 6 | Figure | Wasted compute vs. confidence threshold (Pareto) | §6.4 |
| 7 | Table | Ablation results | §6.5 |
| 8 | Figure | Scalability analysis | §6.6 |

~8 figures/tables is typical for a 10-page SC paper.
