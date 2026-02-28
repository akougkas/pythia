# 6. Evaluation

We evaluate Speculative Dispatch across four workload types, four baselines, and seven metrics.
Our experiments answer five questions:
(1) Does speculation reduce dispatch latency? (§6.2)
(2) Does the Learner improve speculation accuracy over time? (§6.3)
(3) What is the cost of misprediction? (§6.4)
(4) How sensitive are results to design parameters? (§6.5)
(5) Does the system scale? (§6.6)

## 6.1 Experimental Setup

**Workloads.** We design four workload suites representative of HPC-adjacent multi-agent tasks:

1. **HPC Code Generation (HPC-CG).** Multi-step tasks: generating MPI code, writing Slurm job scripts, debugging parallel programs, profiling and optimizing HPC applications. Involves planner, coder, tester, and reviewer agents with sequential dependencies. [PLACEHOLDER: N tasks, describe task generation methodology]

2. **Scientific Data Pipelines (SDP).** Building data processing pipelines with I/O optimization, format conversion (HDF5, NetCDF), and analysis script generation. [PLACEHOLDER: N tasks, describe pipeline specifications]

3. **Research Workflow Automation (RWA).** End-to-end workflows: literature search → experimental design → code generation → result analysis. Exercises all speculation modes due to diverse agent compositions. [PLACEHOLDER: N tasks, describe workflow specifications]

4. **Dispatch Micro-benchmarks (DMB).** Isolated experiments measuring individual speculation mode latency and cost under controlled conditions. [PLACEHOLDER: Describe micro-benchmark design — vary confidence thresholds, fleet sizes, intent complexity]

**Baselines.**

1. **No Speculation (NS).** Sequential pipeline: Intent → Solver → Dispatch → Execute. The standard baseline representing current-generation orchestrators.
2. **Static Heuristic (SH).** Rule-based dispatch without solver optimization. Maps intent types directly to predefined agent configurations using hand-coded rules.
3. **Speculation without Learning (SwoL).** Fixed speculative heuristics (e.g., "most recently used agent for this intent type") that do not improve over time. Isolates the Learner's contribution.
4. **Oracle Speculation (OS).** Perfect predictor that always speculates correctly. Upper bound on achievable latency reduction.

**Metrics.**
- End-to-end dispatch latency ($L$): time from request arrival to first agent output
- Speculation hit rate ($H$): fraction of dispatches resulting in COMMIT or PARTIAL COMMIT
- Wasted compute ratio ($W$): resources consumed by flushed speculation / total resources
- Dispatch quality ($Q$): output equivalence between speculative and non-speculative dispatch [PLACEHOLDER: describe quality metric — automated code quality, human evaluation, or both]
- Learner convergence ($N_{conv}$): interactions to reach stable speculation accuracy
- Cost efficiency ($E$): total tokens + compute-hours consumed, with and without speculation
- Scalability ($S$): metrics vs. fleet size and agent count

**Environment.** [PLACEHOLDER: Full hardware/software specification. Repeat count per experiment. Statistical methodology (mean, CI, significance tests).]

## 6.2 Dispatch Latency

[PLACEHOLDER: Primary result. Figure 4 — bar chart or CDF showing dispatch latency for each workload × baseline × speculation mode combination.

Expected narrative:
- Mode 1 provides modest but consistent latency reduction (context is pre-warmed)
- Mode 2 provides substantial reduction for predictable intents (agents are pre-dispatched)
- Mode 3 provides maximum reduction when draft agent output is accepted
- Improvement grows with workload predictability (HPC-CG > RWA for regular patterns)
- Oracle bounds show how much headroom remains

Key numbers to report:
- Mean/median latency reduction per mode per workload
- Tail latency (p95, p99) impact
- Comparison to NS baseline as percentage]

## 6.3 Speculation Accuracy

[PLACEHOLDER: Figure 5 — learning curves showing speculation hit rate over time (number of interactions) for each workload type.

Expected narrative:
- Cold start: hit rate near 0 for Modes 2/3 (system in Mode 1 only)
- Rapid learning for high-frequency intent classes (first N1 interactions)
- Gradual improvement for less common patterns
- SwoL baseline shows static heuristic ceiling
- Mode 2 threshold reached before Mode 3 threshold (progressive activation)
- Workload-dependent convergence: regular patterns (HPC-CG) converge faster than diverse patterns (RWA)

Key numbers to report:
- Hit rate at convergence per workload per mode
- N1 (Mode 2 activation) and N2 (Mode 3 activation) per workload
- Comparison of learned vs. static (SwoL) hit rates]

## 6.4 Cost Analysis

[PLACEHOLDER: Figure 6 — Pareto frontier: wasted compute ratio vs. confidence threshold for each speculation mode.

Expected narrative:
- Mode 1: near-zero waste regardless of threshold (context prep is rarely wasted)
- Mode 2: waste increases as threshold decreases (more aggressive = more misses)
- Mode 3: highest waste potential but also highest savings
- Optimal threshold gives best latency/waste tradeoff
- Net cost efficiency: despite waste, speculation reduces total cost because latency reduction avoids unnecessary polling, timeouts, and redundant work

Key numbers to report:
- Wasted compute ratio at optimal thresholds per mode
- Net cost efficiency (total tokens/compute-hours) compared to NS baseline
- Break-even analysis: observed hit rates vs. theoretical thresholds from §3.4]

## 6.5 Ablation Studies

[PLACEHOLDER: Table 7 — ablation results matrix.

Ablations:
(a) Mode 1 only vs. Mode 1+2 vs. Mode 1+2+3
(b) Confidence threshold sensitivity: τ2 ∈ {0.5, 0.6, 0.7, 0.8, 0.9}
(c) Learner history window: k ∈ {10, 50, 100, 500}
(d) Single-user vs. multi-user speculation models
(e) Homogeneous vs. heterogeneous infrastructure

Key findings to report per ablation:
- Which modes contribute most to latency reduction
- Optimal threshold values
- Sufficient history window size
- Impact of fleet heterogeneity on speculation accuracy]

## 6.6 Scalability

[PLACEHOLDER: Figure 8 — scalability analysis.

Dimensions:
(a) Fleet size: 2, 4, 8, 16, 32 agents
(b) Agent diversity: 2, 4, 8 agent types
(c) Dispatch search space complexity: simple (single agent) to complex (multi-agent DAG)

Expected narrative:
- Solver latency increases with fleet size (more options to evaluate)
- Speculation benefit increases proportionally (more latency to hide)
- Speculative Dispatcher overhead is constant or sublinear in fleet size
- Learner convergence slightly slower with larger action space but still practical]
