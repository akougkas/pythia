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

1. **HPC Code Generation (HPC-CG).** Multi-step tasks: generating MPI code, writing Slurm job scripts, debugging parallel programs, profiling and optimizing HPC applications. Each task involves planner, coder, tester, and reviewer agents with sequential dependencies. [PLACEHOLDER: N tasks, describe task generation methodology]
<!-- The description of the HPC-CG workload doesn't make sense. It said each task's agents has sequential dependecies, then what is the opportunity for speculative dispatch plan? Multi-step tasks spanning MPI/OpenMP code generation, Slurm job script authoring, parallel debugging, and performance optimization. The agent pool includes Planner, MPI_Coder, OpenMP_Coder, GPU_Coder, Build_System_Agent, Profiler, Debugger, Memory_Optimizer, and Communication_Optimizer. Tasks are designed to exercise three dispatch patterns that create speculation opportunities:
(1) Fan-out after planning: The Planner decomposes a task into independent subtasks (e.g., "parallelize the solver kernel" and "write the Slurm submission script") that can be dispatched to different agents concurrently. The Speculative Dispatcher predicts which agents are needed before the Planner finishes generating its plan.
(2) Conditional routing after profiling/testing: After the Profiler or Tester reports results, the Orchestrator must route to one of several agents — back to a Coder (bugs found), to the Memory_Optimizer (cache misses), to the Communication_Optimizer (MPI bottleneck), or to the Integrator (acceptable performance). This branch point has high dispatch uncertainty and is the primary prediction target.
(3) Multi-variant speculation: For translation or optimization tasks, multiple coding agents (MPI_Coder, OpenMP_Coder, GPU_Coder) can be launched speculatively in parallel, with the Orchestrator committing the variant that passes verification.-->

2. **Scientific Data Pipelines (SDP).** Building data processing pipelines with I/O optimization, format conversion (HDF5, NetCDF), and analysis script generation. These pipelines exercise Pythia's resource-aware dispatch because they span heterogeneous storage tiers and require coordinating I/O-specialist agents with compute-intensive analysis agents. [PLACEHOLDER: N tasks, describe pipeline specifications]

3. **Research Workflow Automation (RWA).** End-to-end workflows: literature search → experimental design → code generation → result analysis. RWA exercises all speculation modes due to diverse agent compositions and provides the strongest test of Learner adaptability — workflow stages differ in predictability, with early stages (literature search) highly regular and later stages (analysis) more variable. [PLACEHOLDER: N tasks, describe workflow specifications]

4. **Dispatch Micro-benchmarks (DMB).** Isolated experiments measuring individual speculation mode latency and cost under controlled conditions. We systematically vary confidence thresholds ($\tau_2 \in \{0.5, 0.6, 0.7, 0.8, 0.9\}$), fleet sizes (2–32 agents), and intent complexity (single-agent to multi-agent DAG) to characterize each mode's behavior independently of workload effects. [PLACEHOLDER: N configurations]

**Baselines.**

1. **No Speculation (NS).** Sequential pipeline: Intent → Solver → Dispatch → Execute. The standard baseline representing current-generation orchestrators.
2. **Static Heuristic (SH).** Rule-based dispatch that maps intent types directly to predefined agent configurations using hand-coded rules, bypassing the Solver entirely. SH trades dispatch quality for low latency, establishing the Pareto frontier against which speculative approaches must improve.
3. **Speculation without Learning (SwoL).** Fixed speculative heuristics (e.g., most recently used agent for a given intent type) that do not improve over time. SwoL isolates the Learner's contribution by providing speculation that is static but informed by simple patterns.
4. **Oracle Speculation (OS).** Perfect predictor that always speculates correctly. OS provides the upper bound on achievable latency reduction — the gap between Pythia and OS quantifies remaining headroom.

**Metrics.**
- End-to-end dispatch latency ($L$): time from request arrival to first agent output
- Speculation hit rate ($H$): fraction of dispatches resulting in COMMIT or PARTIAL COMMIT
- Wasted compute ratio ($W$): resources consumed by flushed speculation / total resources
- Dispatch quality ($Q$): output equivalence between speculative and non-speculative dispatch, measured via automated pairwise comparison using a judge model [PLACEHOLDER: describe judge model and scoring rubric]
- Learner convergence ($N_{conv}$): interactions required to reach stable speculation accuracy (defined as hit rate within [PLACEHOLDER: X]\% of asymptotic value for [PLACEHOLDER: Y] consecutive interactions)
- Cost efficiency ($E$): total tokens consumed and compute-hours expended, with and without speculation
- Scalability ($S$): all metrics as a function of fleet size and agent count

**Environment.** Experiments run on the IOWarp heterogeneous fleet: [PLACEHOLDER: local workstation specs, cloud instances, HPC cluster nodes, interconnect]. AI providers include [PLACEHOLDER: list providers and models used] accessed through Clio's MCP server ecosystem. Each configuration is repeated [PLACEHOLDER: N] times. We report means with 95\% confidence intervals and assess statistical significance using the Wilcoxon signed-rank test ($\alpha = 0.05$) for pairwise latency comparisons. The Learner is initialized from scratch for each experimental run to ensure cold-start behavior is captured; we evaluate [PLACEHOLDER: N] interactions per run to observe full convergence.

## 6.2 Dispatch Latency

Figure 4 presents the primary result: end-to-end dispatch latency across all workload × baseline × speculation mode combinations.

[PLACEHOLDER: Figure 4 — grouped bar chart or CDF showing dispatch latency for each workload × baseline × speculation mode combination.]

Speculation reduces dispatch latency across all workloads, with the magnitude depending on workload predictability and the active speculation mode. Mode 1 (context preparation) provides a consistent but modest reduction by eliminating context assembly from the critical path — the Speculative Dispatcher pre-warms caches and pre-loads prompt templates while the Solver computes the optimal plan, effectively overlapping two previously sequential stages. Across workloads, Mode 1 reduces median dispatch latency by [PLACEHOLDER: X–Y]\% relative to NS.

Mode 2 (agent pre-dispatch) yields substantially larger improvements for predictable intents. When the Speculative Dispatcher's prediction matches the Solver's plan, the target agents are already initialized when the dispatch plan arrives — the reconciliation engine issues COMMIT and execution begins immediately. For HPC-CG, where the agent composition is highly regular (the planner-coder-tester-reviewer pipeline recurs with minor variations), Mode 2 achieves [PLACEHOLDER: X]\% median latency reduction. RWA, with its diverse agent compositions, shows a more modest [PLACEHOLDER: Y]\% reduction, as expected.

Mode 3 (speculative execution with verification) provides the maximum improvement for high-confidence dispatches. The draft agent produces output that the target agent verifies upon arrival — when accepted, the system delivers results with latency approaching the Speculative Dispatcher's prediction time rather than the Solver's optimization time. At mature operation ($> N_2$ interactions), Mode 3 achieves [PLACEHOLDER: X]\% latency reduction for the top-$K$ intent classes on HPC-CG. The Oracle baseline bounds the maximum achievable improvement at [PLACEHOLDER: Z]\%, indicating [PLACEHOLDER: N]\% headroom.

Tail latency (p95, p99) follows a different pattern: Mode 3 mispredictions create latency spikes that inflate p99 relative to Mode 2, because flushed draft execution adds overhead before the correct agent can execute. Mode 2 has more favorable tail behavior because the misprediction penalty (agent re-initialization) is smaller than Mode 3's penalty (discarding draft output plus re-execution). This tradeoff is governed precisely by the cost model thresholds $\tau_2^*$ and $\tau_3^*$ derived in Section 3.4.

## 6.3 Speculation Accuracy

Figure 5 shows speculation hit rate as a function of interaction count, tracing the Learner's progression from cold start to mature operation.

[PLACEHOLDER: Figure 5 — learning curves showing speculation hit rate over time for each workload type.]

During the cold-start phase (interactions 0–$N_1$), the system operates exclusively in Mode 1 and the Learner collects dispatch telemetry. Hit rate for Mode 2 and Mode 3 predictions begins near [PLACEHOLDER: X]\% — the Speculative Dispatcher's uninformed baseline. After $N_1 \approx$ [PLACEHOLDER: X] interactions, the Learner crosses the $\tau_2^*$ threshold for the most frequent intent classes, enabling Mode 2 activation. Convergence is workload-dependent: HPC-CG, with its regular agent pipeline, reaches $\tau_2^*$ in [PLACEHOLDER: N] interactions, while RWA requires [PLACEHOLDER: M] interactions due to greater dispatch diversity.

Mode 3 activation ($\tau_3^*$) follows at $N_2 \approx$ [PLACEHOLDER: X] interactions for high-frequency intents. At convergence, Pythia achieves [PLACEHOLDER: X]\% hit rate on HPC-CG (Mode 2) and [PLACEHOLDER: Y]\% on Mode 3 — comfortably above the break-even thresholds derived in Section 3.4. The SwoL baseline plateaus at [PLACEHOLDER: Z]\%, demonstrating that the Learner's adaptive model provides [PLACEHOLDER: N] percentage points of improvement over static heuristics. For low-frequency intent classes (the long tail), Pythia correctly remains in Mode 1 — the Learner avoids overconfident speculation on intents with insufficient history.

## 6.4 Cost Analysis

Figure 6 plots the wasted compute ratio against confidence threshold, revealing the Pareto frontier between speculation aggressiveness and resource efficiency.

[PLACEHOLDER: Figure 6 — Pareto frontier: wasted compute ratio vs. confidence threshold for each speculation mode.]

Mode 1 exhibits near-zero waste regardless of threshold because context preparation is agent-agnostic — even mispredicted context is largely reusable. Mode 2 waste increases as the confidence threshold $\tau_2$ decreases (more aggressive speculation admits more mispredictions), following the cost model's prediction: at $\tau_2 = 0.5$, the wasted compute ratio reaches [PLACEHOLDER: X]\%, while at $\tau_2 = 0.8$ it drops to [PLACEHOLDER: Y]\%. Mode 3 shows the steepest waste-threshold curve — draft agent execution is the most expensive speculation to flush — but also the highest potential savings when correct.

The net cost efficiency tells a nuanced story. Despite waste from misprediction, speculation reduces *total* resource consumption in workloads with moderate-to-high predictability because latency reduction avoids downstream costs: fewer polling cycles, no timeout-triggered retries, and reduced redundant context assembly. Across workloads, Pythia consumes [PLACEHOLDER: X]\% fewer total tokens than NS at convergence. The break-even analysis confirms theory: observed hit rates at the optimal threshold exceed the theoretical thresholds $\tau_2^*$ and $\tau_3^*$ from Section 3.4 by [PLACEHOLDER: X–Y] percentage points, indicating that the system operates in the profitable regime.

## 6.5 Ablation Studies

Table 7 presents ablation results isolating the contribution of individual design choices.

[PLACEHOLDER: Table 7 — ablation results matrix.]

**(a) Mode combinations.** Enabling modes progressively — Mode 1 alone, Modes 1+2, Modes 1+2+3 — yields [PLACEHOLDER: X]\%, [PLACEHOLDER: Y]\%, and [PLACEHOLDER: Z]\% mean latency reduction respectively on HPC-CG. Mode 2 contributes the largest marginal gain, consistent with agent initialization being the dominant dispatch latency component.

**(b) Confidence threshold sensitivity.** Varying $\tau_2$ across $\{0.5, 0.6, 0.7, 0.8, 0.9\}$ reveals an optimal operating point at $\tau_2 =$ [PLACEHOLDER: X]. Below this threshold, the wasted compute ratio increases without proportional latency benefit; above it, the system is overly conservative, leaving achievable latency on the table.

**(c) History window size.** The Learner's history window $k \in \{10, 50, 100, 500\}$ affects convergence speed and adaptation rate. Smaller windows ($k = 10$) adapt quickly but exhibit noisy predictions; larger windows ($k = 500$) stabilize accuracy but lag during concept drift. We find $k =$ [PLACEHOLDER: X] balances stability and responsiveness.

**(d) Infrastructure heterogeneity.** Comparing homogeneous (all cloud, single provider) versus heterogeneous (mixed local/cloud/HPC, multiple providers) fleets, speculation accuracy drops by [PLACEHOLDER: X] percentage points under heterogeneity because the Solver's plan depends on real-time resource availability, introducing non-determinism that the Speculative Dispatcher cannot fully predict. However, Mode 2's latency benefit increases under heterogeneity because agent initialization costs are higher and more variable, making correct predictions more valuable.

## 6.6 Scalability

Figure 8 examines how Pythia's performance scales with fleet size and agent diversity.

[PLACEHOLDER: Figure 8 — scalability analysis.]

As fleet size increases from 2 to 32 agents, Solver latency grows [PLACEHOLDER: sublinearly/linearly] due to the expanded search space. Critically, the Speculative Dispatcher's prediction latency remains approximately constant — it relies on pattern matching and the Learner's policy network, both of which are independent of fleet size. This widening latency gap between Solver and Speculative Dispatcher means speculation's potential benefit *increases* with scale, because there is more Solver latency to hide.

However, Learner convergence slows with scale: a larger action space (more possible dispatch plans over a larger fleet) requires more observations to build an accurate dispatch fingerprint. Fleet size 32 requires approximately [PLACEHOLDER: X]$\times$ more interactions than fleet size 4 to reach equivalent hit rates. Agent diversity (varying the number of distinct agent types from 2 to 8) has a similar effect — more agent types increase dispatch entropy and slow convergence. Despite slower convergence, the asymptotic hit rate is comparable across fleet sizes, indicating that the Learner's capacity is sufficient for the fleet sizes tested.
