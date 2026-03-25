# 2. Background and Motivation

This section establishes the technical foundations for speculative dispatch by reviewing speculation in CPU architecture and LLM inference, surveying the multi-agent orchestration landscape, and presenting empirical evidence that dispatch planning is both a latency bottleneck and a predictable one.

## 2.1 Speculative Execution in CPU Architecture

Modern out-of-order processors routinely execute instructions before all dependencies are resolved.
When the processor encounters a conditional branch, rather than stalling the pipeline until the branch condition is evaluated, a branch predictor predicts the likely outcome and the processor speculatively executes along the predicted path [hennessy2017computer].
If the prediction is correct, the speculative results commit — the processor gains the full latency of the branch resolution for free.
If wrong, the speculative work is flushed and execution restarts on the correct path, incurring a pipeline flush penalty of 10–20 cycles on modern microarchitectures.

Branch prediction has evolved through four generations.
Static heuristics (e.g., "backward branches taken") gave way to two-level adaptive predictors that correlate branch outcomes with recent history [yeh1991two], then to tournament predictors combining multiple strategies [mcfarling1993combining], and finally to TAGE predictors using tagged geometric history lengths that achieve accuracy exceeding 95% on realistic workloads [seznec2006tage, seznec2011tage].
Neural branch prediction introduced perceptrons as an alternative to table-based predictors, enabling linear scaling with history length [jimenez2001perceptron].
<!-- Branch prediction has evolved from static heuristics through two-level adaptive [yeh1991two] and tournament predictors [mcfarling1993combining] to TAGE designs that achieve accuracy exceeding 95% on realistic workloads [seznec2006tage, seznec2011tage], with neural approaches enabling linear scaling with history length [jimenez2001perceptron]. -->

Critically, speculation in modern processors extends well beyond branch outcomes.
Recent microarchitectural analyses have uncovered speculative predictors for load addresses [kim2025slap], load values [kim2025flop], and data-dependent memory access patterns [chen2024gofetch]. Each independently instantiates the same predict-execute-verify pattern on a different data domain.
This repeated rediscovery suggests the abstraction is fundamental rather than artifact-specific, a premise central to the transfer we formalize in Section 3.

The cost model is fundamental: speculation is net-positive when prediction accuracy exceeds $\frac{C_{flush}}{L_{saved} + C_{flush}}$, where $C_{flush}$ is the misprediction penalty and $L_{saved}$ is the latency avoided by correct speculation [hennessy2017computer].
For typical pipeline depths and flush costs, the break-even accuracy is approximately 70–75% — well below what modern predictors achieve.
<!-- For typical 15–20 stage pipelines where $C_{flush} \approx 15-20$ cycles and $L_{saved} \approx 5–7$ cycles, the break-even accuracy is approximately 68–80% — well below what modern predictors achieve [hennessy2017computer]. -->

The security implications of speculative execution are equally instructive.
Spectre demonstrated that speculative memory accesses, even when architecturally rolled back, leave observable traces in microarchitectural state (e.g., cache lines) that can be exploited to leak data across security boundaries [kocher2019spectre].
This lesson transfers directly to multi-agent orchestration: speculative resource access at the dispatch layer may similarly leak context across isolation boundaries in multi-tenant deployments (Section 7.2).

## 2.2 Speculative Decoding in LLM Inference

Speculative decoding adapts the draft-verify paradigm to autoregressive language model inference.
A small, fast *draft model* generates $\gamma$ candidate tokens autoregressively, then the larger *target model* scores all candidates in a single forward pass — exploiting the asymmetry between generation (sequential, $O(\gamma)$ forward passes) and verification (parallel, $O(1)$ forward pass) [leviathan2023fast, chen2023accelerating].

A modified rejection sampling scheme ensures the output distribution is *identical* to the target model alone: at each position, the draft token is accepted with probability $\min(1, p_{target}/p_{draft})$, and on first rejection a correction token is sampled from the residual distribution [leviathan2023fast].
In the worst case, one token is produced per target forward pass (no worse than standard decoding); in the best case, $\gamma + 1$ tokens are produced, yielding up to $\gamma + 1$ times throughput.

The field has diversified rapidly.
SpecInfer and Sequoia employ tree-based speculation with hardware-aware optimal tree construction, generating candidate trees from multiple drafts and verifying them in a single pass [miao2024specinfer, chen2024sequoia].
Medusa eliminates the separate draft model entirely, adding lightweight MLP heads to the target model for multi-position prediction [cai2024medusa].
The EAGLE family conditions drafting on the target model's hidden states, with EAGLE-3 simulating inference conditions during training to close the train-inference gap and achieve up to 6.5× speedup [li2024eagle, li2025eagle3].
Online speculative decoding continuously updates the draft model from observed query distributions, improving acceptance rates without offline retraining [liu2024online].
Recent analysis reveals that verification — not drafting — dominates speculative decoding cost [liu2025verification], while TurboSpec formalizes "goodput" as a unifying metric for adaptive runtime tuning [liu2024turbospec].
These three developments — online adaptation, verification-centric cost analysis, and adaptive parameter control — directly inform our Learner design (§4).

<!-- The speedup is governed by three parameters: the mean acceptance rate $\alpha$, the speculation depth $\gamma$, and the cost ratio $c$ between draft and target forward passes.
The theoretical upper bound on speedup is $1/(1-\alpha)$; practical systems achieve 2–3$\times$ throughput improvement with $\alpha$ in the range 0.6–0.85 [xia2024survey]. -->
The speedup is governed by three parameters: the mean acceptance rate $\alpha$, the speculation depth $\gamma$ (i.e., the number of draft tokens), and the cost ratio $c$ between draft and target forward passes. Leviathan et al. [leviathan2023fast] derived the closed-form expected walltime speedup (Theorem 3.8): $E(\text{Speedup}) = \frac{1 - \alpha^{\gamma+1}}{(1-\alpha)(\gamma c + 1)}$. Note that as $c \to 0$ (negligible draft cost), it approaches $1/(1-\alpha)$, demonstrating the theoretical upper bound on speedup. Increasing $\gamma$ raises tokens per cycle but increases wasted computation when $\alpha$ is low (early rejection invalidates all subsequent draft tokens). Practical systems achieve 2–3× walltime improvement with acceptance rates in the range 0.6–0.85 [xia2024survey].

## 2.3 Multi-Agent Orchestration

Multi-agent LLM systems assign specialized roles to distinct agents that collaborate through structured communication.
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
Yet even OI-MAS — the most adaptive router to date — reroutes based on observed state; it never predicts or pre-executes future dispatch decisions.

The gap is clear: the multi-agent orchestration layer lacks the predictive, speculative, and adaptive capabilities that have proven transformative in CPU architecture and LLM inference.

## 2.4 Empirical Motivation

To quantify the dispatch bottleneck, we profiled Clio Coder — the multi-agent orchestration component of the IOWarp scientific computing platform — handling realistic HPC-adjacent workloads including MPI code generation, scientific data pipeline construction, and research workflow automation.
<!-- [PLACEHOLDER: Insert Clio Coder profiling methodology — instrument dispatch pipeline stages, collect timing data across N requests over M days] -->

To further characterize the dispatch bottleneck in existing frameworks, we profiled the LangGraph supervisor pattern — the dominant orchestration architecture in current multi-agent systems — on 25 scientific data analysis queries drawn from the KramaBench benchmark across three domains (wildfire science, astronomy, and legal analytics). We configured a supervisor with six specialist agents (DataReader, DataCleaner, GeoProcessor, Calculator, StatModeler, Visualizer) backed by a qwen3.5:9b model served locally via Ollama. For each query, we measured supervisor LLM inference time (dispatch overhead) and agent LLM inference time (execution) separately by collecting per-node timestamps through LangGraph's streaming API. Each query was repeated three times to assess dispatch consistency.

<!-- [PLACEHOLDER: Figure or table showing dispatch latency breakdown:
- Intent classification: ~X ms (Y% of total)
- Task decomposition/planning: ~X ms (Y% of total)
- Agent selection and resource matching: ~X ms (Y% of total)
- Context assembly and prompt construction: ~X ms (Y% of total)
- Agent initialization and warm-up: ~X ms (Y% of total)
- TOTAL dispatch overhead: ~X ms (Y% of end-to-end)] -->

![Dispatch vs. execution latency for six representative KramaBench queries processed by a LangGraph supervisor (qwen3.5:9b). Dark bars show supervisor routing overhead (1.6–3.8 s, 19–37% of total); light bars show agent execution time. Dispatch decisions are made by sequential LLM calls — one per agent handoff — constituting a fixed latency tax on every query.](../paper/imgs/motivation/dispatch_vs_execution_latency.png)
*Figure: Dispatch vs. execution latency breakdown (§2.4). See `\label{fig:dispatch-latency}` in main.tex.*

[PLACEHOLDER: Dispatch predictability analysis — show that for the top-K intent classes (which cover Z% of all requests), the dispatch plan has low conditional entropy given the intent. This is the empirical justification for why speculation can work.]

The profiling reveals two key findings: (1) dispatch overhead constitutes a substantial fraction of end-to-end latency, particularly for shorter tasks where dispatch time approaches or exceeds execution time; and (2) dispatch decisions exhibit strong temporal locality — recurring intent patterns map to consistent dispatch plans, making prediction tractable.

## 2.5 Positioning

Table 1 summarizes the structural parallel across the three speculation domains.

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

The key observation: the draft-target-verify-commit/flush pattern is *domain-independent*.
It applies wherever (a) an expensive optimization can be approximated cheaply, (b) verification of the approximation is cheaper than computing the exact solution, and (c) prediction accuracy improves with observation.
Multi-agent dispatch satisfies all three conditions.
To our knowledge, this is the first work to formalize and evaluate this transfer.
