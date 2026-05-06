# 2. Background and Motivation

<!-- This section establishes the technical foundations for speculative dispatch by reviewing speculation in CPU architecture and LLM inference, surveying the multi-agent orchestration landscape, analyzing why existing agentic speculation systems leave the dispatch level unaddressed, and presenting empirical evidence that dispatch planning is both a latency bottleneck and a predictable one. -->

## 2.1 Speculative Execution in CPU Architecture

Modern out-of-order processors routinely execute instructions before all dependencies are resolved.
When the processor encounters a conditional branch, rather than stalling the pipeline until the branch condition is evaluated, a branch predictor predicts the likely outcome and the processor speculatively executes along the predicted path [hennessy2017computer].
If the prediction is correct, the speculative results commit — the processor gains the full latency of the branch resolution for free.
If wrong, the speculative work is flushed and execution restarts on the correct path, incurring a pipeline flush penalty of 10–20 cycles on modern microarchitectures.
Branch prediction has evolved from static heuristics through two-level adaptive [yeh1991two] and tournament predictors [mcfarling1993combining] to TAGE designs that achieve accuracy exceeding 95% on realistic workloads [seznec2006tage, seznec2011tage], with neural approaches enabling linear scaling with history length [jimenez2001perceptron].

Critically, speculation in modern processors extends well beyond branch outcomes.
Recent microarchitectural analyses have uncovered speculative predictors for load addresses [kim2025slap], load values [kim2025flop], and data-dependent memory access patterns [chen2024gofetch]. Each independently instantiates the same predict-execute-verify pattern on a different data domain.
This repeated rediscovery suggests the abstraction is fundamental rather than artifact-specific, a premise central to the transfer we formalize in Section 3.

The cost model is fundamental: speculation is net-positive when prediction accuracy exceeds $\frac{C_{flush}}{L_{saved} + C_{flush}}$, where $C_{flush}$ is the misprediction penalty and $L_{saved}$ is the latency avoided by correct speculation [hennessy2017computer].
For typical pipeline depths and flush costs, the break-even accuracy is approximately 70–75% — well below what modern predictors achieve.
<!-- For typical 15–20 stage pipelines where $C_{flush} \approx 15-20$ cycles and $L_{saved} \approx 5–7$ cycles, the break-even accuracy is approximately 68–80% — well below what modern predictors achieve [hennessy2017computer]. -->

<!-- The security implications of speculative execution are equally instructive.
Spectre demonstrated that speculative memory accesses, even when architecturally rolled back, leave observable traces in microarchitectural state (e.g., cache lines) that can be exploited to leak data across security boundaries [kocher2019spectre].
This lesson transfers directly to multi-agent orchestration: speculative resource access at the dispatch layer may similarly leak context across isolation boundaries in multi-tenant deployments (Section 7.2). -->

## 2.2 Speculative Decoding in LLM Inference

Speculative decoding adapts the draft-verify paradigm to autoregressive language model inference.
A small, fast *draft model* generates $\gamma$ candidate tokens autoregressively, then the larger *target model* scores all candidates in a single forward pass, exploiting the asymmetry between generation (sequential, $O(\gamma)$ forward passes) and verification (parallel, $O(1)$ forward pass) [leviathan2023fast, chen2023accelerating].
A modified rejection sampling scheme ensures the output distribution is *identical* to the target model alone: at each position, the draft token is accepted with probability $\min(1, p_{target}/p_{draft})$, and on first rejection a correction token is sampled from the residual distribution [leviathan2023fast].
<!-- In the worst case, one token is produced per target forward pass (no worse than standard decoding); in the best case, $\gamma + 1$ tokens are produced, yielding up to $\gamma + 1$ times throughput. -->

<!-- The speedup is governed by three parameters: the mean acceptance rate $\alpha$, the speculation depth $\gamma$, and the cost ratio $c$ between draft and target forward passes.
The theoretical upper bound on speedup is $1/(1-\alpha)$; practical systems achieve 2–3$\times$ throughput improvement with $\alpha$ in the range 0.6–0.85 [xia2024survey]. -->
The speedup is governed by three parameters: the mean acceptance rate $\alpha$, the speculation depth $\gamma$ (i.e., the number of draft tokens), and the cost ratio $c$ between draft and target forward passes. Leviathan et al. [leviathan2023fast] derived the closed-form expected walltime speedup (Theorem 3.8): $E(\text{Speedup}) = \frac{1 - \alpha^{\gamma+1}}{(1-\alpha)(\gamma c + 1)}$. In practice, systems achieve 2–3× walltime improvement with acceptance rates in the range 0.6–0.85 [xia2024survey].

Subsequent work has expanded along three axes, including the tree-based drafting for obtaining higher acceptance rates [miao2024specinfer, chen2024sequoia], draft-free or target-conditioned drafting methods that reduce the gap between draft and target models~[cai2024medusa, li2024eagle, li2025eagle3], and online adaptation that updates the draft model from observed query distributions [liu2024online].
<!-- SpecInfer and Sequoia employ tree-based speculation with hardware-aware optimal tree construction, generating candidate trees from multiple drafts and verifying them in a single pass [miao2024specinfer, chen2024sequoia].
Medusa eliminates the separate draft model entirely, adding lightweight MLP heads to the target model for multi-position prediction [cai2024medusa].
The EAGLE family conditions drafting on the target model's hidden states, with EAGLE-3 simulating inference conditions during training to close the train-inference gap and achieve up to 6.5× speedup [li2024eagle, li2025eagle3].
Online speculative decoding continuously updates the draft model from observed query distributions, improving acceptance rates without offline retraining [liu2024online]. -->
Recent analysis reveals that verification, not drafting, dominates speculative decoding cost [liu2025verification], while TurboSpec formalizes goodput as a unifying metric for adaptive tuning [liu2024turbospec].
These developments and insights directly inform our Learner design (§4).


## 2.3 Multi-Agent Orchestration

Multi-agent LLM systems assign specialized roles to distinct agents that collaborate through structured communication. 
Frameworks such as AutoGen [wu2023autogen], MetaGPT [hong2024metagpt], and ChatDev [qian2024chatdev] differ in coordination topology but all follow the same sequential pipeline: intent recognition → task decomposition → agent assignment → execution. 
Similarly, CrewAI [crewai2024], LangGraph [langgraph2024], and OpenAI's Agents SDK [openai2025agentssdk] organize workflows around sequential or parallel dispatch with explicit handoff primitives. 
A controlled evaluation across 180 configurations found that centralized designs outperform decentralized alternatives on decomposition-heavy tasks while incurring $O(k)$ LLM calls [qian2025scaling].

Recent works have made this pipeline increasingly dynamic along two axes.
In task allocation, TDAG [qiao2024tdag] generates task-specific subagents on the fly rather than relying on pre-defined roles;
COLA [zhang2025cola] combines coarse planning with scenario-aware scheduling for fine-grained refinement;
MasRouter [li2025masrouter] jointly optimizes collaboration mode, role allocation, and LLM backbone selection, reducing orchestration overhead by up to 52\%. 
On the routing side, systems have progressed from simple model cascading [chen2023frugalgpt] through binary strong/weak selection [ong2024routellm] and difficulty-aware heterogeneous routing [huang2024diffrouting] to confidence-aware routing that dynamically selects agent roles and model scales as reasoning unfolds [wang2026oimas].
Yet even the most adaptive of these systems triggers a fresh planning cycle for every request; none predict or pre-execute future dispatch decisions, and infrastructure-level constraints such as GPU availability, API rate limits, and memory pressure remain external to the dispatch decision.

<!-- Multi-agent LLM systems assign specialized roles to distinct agents that collaborate through structured communication.
AutoGen organizes agents into conversable groups with human-in-the-loop capabilities [wu2023autogen].
MetaGPT encodes standardized operating procedures into an assembly-line paradigm with verification at each stage [hong2024metagpt].
ChatDev decomposes software development into chat chains across design, coding, and testing phases [qian2024chatdev].
Agentic patterns such as ReAct interleave reasoning with tool use [yao2023react], while Reflexion adds post-hoc verbal reflection for self-improvement [shinn2023reflexion].
Beyond these centralized designs, AgentNet enables agents to self-organize into dynamic DAGs without a central controller, using retrieval-augmented memory for continual specialization [yang2025agentnet].
A controlled evaluation across 180 configurations and five canonical architectures found that centralized designs outperform independent and decentralized alternatives on decomposition-heavy tasks while incurring $O(k)$ LLM calls [qian2025scaling].

All existing frameworks follow the same sequential pipeline: intent recognition → task decomposition → agent assignment → execution.
CrewAI organizes agents into role-based "crews" with sequential or parallel execution.
LangGraph models workflows as directed state machines.
OpenAI's Swarm (and its successor Agents SDK) introduced lightweight handoff primitives.

Task allocation within this pipeline has grown increasingly dynamic.
TDAG dynamically generates task-specific subagents on the fly rather than relying on pre-defined roles [qiao2024tdag].
COLA combines a planner for coarse decomposition with a scenario-aware task scheduler and decision agents for fine-grained refinement [zhang2025cola].
MasRouter jointly optimizes collaboration mode, role allocation, and LLM backbone selection, reducing orchestration overhead by up to 52\% [li2025masrouter].
Yet even the most dynamic allocation systems trigger a fresh planning cycle for every request, regardless of how similar it is to prior requests; none predict or pre-execute.

Routing efficiency has evolved through four generations.
FrugalGPT introduced simple cascading across models to minimize cost [chen2023frugalgpt].
RouteLLM advanced to binary strong/weak model selection using preference data [ong2024routellm].
Difficulty-aware orchestration routes across heterogeneous LLMs, achieving 11\% accuracy improvement at 64\% cost [huang2024diffrouting].
Most recently, OI-MAS introduced confidence-aware routing that dynamically selects agent roles and model scales as reasoning unfolds [wang2026oimas].
Yet even OI-MAS — the most adaptive router to date — reroutes based on observed state; it never predicts or pre-executes future dispatch decisions. -->

## 2.4 Speculative Execution in Agentic Systems

Recently, a nascent line of work has begun applying speculative execution to agentic planning and action execution.
However, all existing systems speculate *within a single agent's execution trace; none target the dispatch decision itself*.

Several systems speculate at the **planning-step** granularity. Interactive Speculative Planning (ISP) [hua2024isp] first transferred the draft-verify pattern from speculative decoding to agent workflows. Dynamic Speculative Planning (DSP) [guan2025dsp] extended ISP with online reinforcement learning to adaptively adjust speculation depth per episode, balancing latency gains against misprediction cost. SPAgent pushed further by selectively omitting verification when reasoning demand is low via a two-phase adaptive mechanism, crossing from lossless into lossy speculation and achieving up to 1.65× speedup on search-agent workloads [spagent2025]. 
Others speculate at the **tool or API** level. Speculative Actions [ye2025specactions] generalized the paradigm from LLM planning steps to arbitrary agentic environments with formal losslessness guarantees via semantic guards and rollback paths. PASTE [paste2026] specifically targets the LLM--tool serial loop, predicting application-level control flows and pre-executing tool calls (e.g., next tool call) while the LLM is still reasoning. 
Sherlock [sherlock2025] speculates at the **workflow-node** level. It learns which workflow nodes require verification and speculatively executes downstream nodes in the background, reducing latency by up to 48.7%.

Despite spanning different granularities (i.e., from planning steps to tool calls to workflow nodes), these systems share a structural limitation: 
speculation operates within a single agent's execution loop after the dispatch decision is already made. No system speculates at the *dispatch level*, that is predicting which agents, from a heterogeneous pool, should be assigned to which subtasks before the dispatch plan is fully computed.

<!-- The gap is clear: the multi-agent orchestration layer lacks the predictive, speculative, and adaptive capabilities that have proven transformative in CPU architecture and LLM inference. -->

## 2.5 The Dispatch Latency–Quality Gap

<!-- [PLACEHOLDER: Student drafts §2.5 methodology paragraph — describe plan-and-execute benchmark setup, 8 LLM backends, 3 workload domains, 10 queries each, similarity metric (50% normalized LCS of agent sequences + 50% Jaccard of DAG dependency edges)] -->

![Planning latency vs. plan quality across eight LLM backends on three workload domains (HPC Code Gen, Data Pipelines, Research Workflows). Each point represents the mean over 10 queries. Plan similarity is a composite of normalized LCS over agent sequences and Jaccard index over DAG dependency edges, measured against Claude Opus 4.6 as the reference planner (similarity = 1.0 by construction). Five local models form a fast cluster (2–5 s, similarity 0.28–0.78 depending on workload), while the three API models form a slower cluster (7–33 s). The separation between clusters exposes the draft–target asymmetry that speculative dispatch exploits.](../paper/imgs/motivation/fig2_latency_vs_quality.png)
*Figure: Planning latency vs. plan quality. See `\label{fig:dispatch-latency-vs-quality}` in main.tex.*

<!-- [PLACEHOLDER: Student drafts two observation paragraphs — (1) the fast–slow asymmetry exists (quantify clusters); (2) partial overlap enables partial commit (mid-range similarity means draft plans are partially correct, motivating Mode 2 in §3)] -->
We begin with a simple experiment: how much do planning latency and plan quality vary across LLM backends? We benchmark a plan-and-execute orchestration pattern across eight LLM backends (three cloud models: Claude Opus 4.6, Sonnet 4.6, Haiku 4.5; and five locally hosted models served via ollama: Gemma4 26B, Mistral 24B, GPT-OSS 20B, Gemma4 E2B, Nemotron 4B). The planner decomposes a user query into multi-step subtasks, assigning each step to a domain-specific agent and specifying the execution order. The output is a structured plan; agents are then executed according to that order (sequential or parallel). We evaluate the orchestrator across three workloads (HPC Code Generation, Data Pipelines, and Research Workflows) with 10 queries per workload, stratified by difficulty level and sub-domain to ensure coverage across different planning instances. We measure wall-clock planning latency and compute plan similarity against Opus as the reference planner. The similarity metric is a weighted composite of two components: (1) agent-sequence similarity, defined as the normalized longest common subsequence (LCS) length between the ordered agent assignments of two plans ($2 \cdot |LCS| / (|A| + |B|)$), and (2) dependency-structure similarity, defined as the Jaccard index over the sets of directed agent-role edges extracted from each plan's DAG. The final score is an equal-weight average of these two terms, yielding a value in $[0, 1]$ that captures both the ordering and the structural agreement of dispatch decisions.

Figure \ref{fig:dispatch-latency-vs-quality} depicts the results. The five local models form a consistent fast cluster: mean latency ranges from 2–3 s on HPC Code Gen and Data Pipelines to 4–5 s on Research Workflows. Plan similarity against Opus varies by workload, reaching 0.65–0.78 on HPC Code Gen (Gemma4 E2B highest at 0.78, GPT-OSS 20B lowest at 0.65), 0.50–0.70 on Data Pipelines (Gemma4 26B highest at 0.70, Nemotron 4B lowest at 0.50), and 0.28–0.36 on Research Workflows (Gemma4 26B highest at 0.36, GPT-OSS 20B and Nemotron 4B lowest at 0.28). Opus and Sonnet form the slow, high-quality cluster. Opus, the reference planner, requires ~13 s (HPC), ~20 s (Data Pipelines), and ~33 s (Research Workflows). Sonnet achieves high similarity (0.60–0.78) but at comparable or greater latency (~15–33 s). Haiku falls between the two clusters: its latency (~7–15 s) is slower than the local models yet faster than Opus and Sonnet, while its similarity (0.33–0.72) is neither consistently high nor consistently low, making it a poor fit for either the draft or the target role in a speculative pipeline. Per-query latency and pairwise similarity distributions exhibit moderate variance within each model; full per-query breakdowns and pairwise similarity matrices are provided in the artifact appendix. The fast cluster produces plans at 4–10× lower wall-clock cost than Opus. Because mid-range similarity represents actionable partial correctness, a system that identifies high-confidence subtask assignments can commit them early and begin agent execution before the authoritative planner finishes. We note that similarity is measured against Opus rather than human-curated ground truth; consequently, the metric captures agreement with a strong planner, not absolute plan correctness. The consistent separation between fast and slow clusters across all three workloads indicates a robust latency–quality gap, independent of whether Opus plans are globally optimal.

The results reveal two findings. First, a clear fast–slow asymmetry exists in dispatch planning: local models produce plans in 2–5 s while the strongest planner (Opus) requires 13–33 s depending on workload. This gap is the structural precondition for speculation. Second, fast models recover a non-trivial fraction of the reference plan. On HPC Code Gen, all five local models achieve similarity scores of 0.65–0.78, indicating that draft plans are partially correct rather than random; this is the operational precondition for partial commit. Similarity degrades on more complex workloads (0.28–0.36 on Research Workflows), which suggests that speculation depth and commit thresholds must be workload-adaptive. Together, these two preconditions motivate the multi-mode framework formalized in §3, where Mode 2 commits high-confidence partial plans while the full planner completes the remainder.

## 2.6 Positioning: Dispatch as a Speculation Target

The preceding subsections have established that the draft-verify-commit/flush abstraction has proven effective across disparate domains from CPU pipelines (§2.1) to LLM inference (§2.2), and an exploitable latency-quality gap exists at the dispatch level in multi-agent orchestration (§2.5). Table 1 maps the structural parallel across these domains and identifies multi-agent dispatch as the transfer target.

| | CPU Speculation | LLM Spec. Decoding | Speculative Dispatch (Ours) |
|---|---|---|---|
| **Draft** | Branch predictor | Small/fast draft model | Lightweight dispatch predictor |
| **Target** | Branch resolution | Large target model | Full dispatch solver |
| **Unit** | Instructions | Tokens | Agent dispatch plans |
| **Commit** | Prediction correct | Token accepted | Plan matches solver |
| **Flush** | Misprediction | Token rejected | Plan mismatch |
| **Cost metric** | Pipeline flush cycles | Wasted draft computation | Wasted agent initialization |
| **Learning** | Adaptive predictors (TAGE) | Online spec. decoding | RL-based Learner |
| **Break-even** | ~70–75% accuracy | ~50–60% acceptance | Derived per mode (§3.4) |
| **Security risk** | Spectre [kocher2019spectre] | N/A | Context leakage (§7.2) |

The key observation is that the draft-target-verify-commit/flush pattern is *domain-independent*.
It applies wherever (a) an expensive optimization can be approximated cheaply, (b) verification of the approximation is cheaper than computing the exact solution, and (c) prediction accuracy improves with observation.
Multi-agent dispatch satisfies all three conditions. First, the §2.5 benchmark shows that lightweight models approximate the target planner's dispatch decisions in 2–5 seconds (cheap approximation). Second, verification can be done by comparing two structured plans (i.e., a set intersection over agent-task assignments), which completes in negligible time relative to plan generation (cheap verification). Third, scientific computing users repeatedly submit similar workloads [luo2021inferring], providing the recurrence that allows a learner to improve prediction accuracy over time (learning from observation).
