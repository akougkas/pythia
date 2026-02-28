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

The cost model is fundamental: speculation is net-positive when prediction accuracy exceeds $\frac{C_{flush}}{L_{saved} + C_{flush}}$, where $C_{flush}$ is the misprediction penalty and $L_{saved}$ is the latency avoided by correct speculation [hennessy2017computer].
For typical pipeline depths and flush costs, the break-even accuracy is approximately 70–75% — well below what modern predictors achieve.

The security implications of speculative execution are equally instructive.
Spectre demonstrated that speculative memory accesses, even when architecturally rolled back, leave observable traces in microarchitectural state (e.g., cache lines) that can be exploited to leak data across security boundaries [kocher2019spectre].
This lesson transfers directly to multi-agent orchestration: speculative resource access at the dispatch layer may similarly leak context across isolation boundaries in multi-tenant deployments (Section 7.2).

## 2.2 Speculative Decoding in LLM Inference

Speculative decoding adapts the draft-verify paradigm to autoregressive language model inference.
A small, fast *draft model* generates $\gamma$ candidate tokens autoregressively, then the larger *target model* scores all candidates in a single forward pass — exploiting the asymmetry between generation (sequential, $O(\gamma)$ forward passes) and verification (parallel, $O(1)$ forward pass) [leviathan2023fast, chen2023accelerating].

A modified rejection sampling scheme ensures the output distribution is *identical* to the target model alone: at each position, the draft token is accepted with probability $\min(1, p_{target}/p_{draft})$, and on first rejection a correction token is sampled from the residual distribution [leviathan2023fast].
In the worst case, one token is produced per target forward pass (no worse than standard decoding); in the best case, $\gamma + 1$ tokens are produced, yielding up to $\gamma + 1$ times throughput.

The field has diversified rapidly.
SpecInfer uses tree-based speculation with multiple draft models generating a candidate tree verified in one pass [miao2024specinfer].
Medusa eliminates the separate draft model entirely, adding lightweight MLP heads to the target model for multi-position prediction [cai2024medusa].
EAGLE conditions drafting on the target model's hidden states for higher acceptance rates [li2024eagle, li2024eagle2].
Online speculative decoding continuously updates the draft model from observed query distributions, improving acceptance rates over time without offline retraining [liu2024online] — a direct precedent for our Learner's online adaptation.

The speedup is governed by three parameters: the mean acceptance rate $\alpha$, the speculation depth $\gamma$, and the cost ratio $c$ between draft and target forward passes.
The theoretical upper bound on speedup is $1/(1-\alpha)$; practical systems achieve 2–3$\times$ throughput improvement with $\alpha$ in the range 0.6–0.85 [xia2024survey].

## 2.3 Multi-Agent Orchestration

Multi-agent LLM systems assign specialized roles to distinct agents that collaborate through structured communication.
AutoGen organizes agents into conversable groups with human-in-the-loop capabilities [wu2023autogen].
MetaGPT encodes standardized operating procedures into an assembly-line paradigm with verification at each stage [hong2024metagpt].
ChatDev decomposes software development into chat chains across design, coding, and testing phases [qian2024chatdev].
Agentic patterns such as ReAct interleave reasoning with tool use [yao2023react], while Reflexion adds post-hoc verbal reflection for self-improvement [shinn2023reflexion].

All existing frameworks follow the same sequential pipeline: intent recognition → task decomposition → agent assignment → execution.
CrewAI organizes agents into role-based "crews" with sequential or parallel execution.
LangGraph models workflows as directed state machines.
OpenAI's Swarm (and its successor Agents SDK) introduced lightweight handoff primitives.
None of these systems perform predictive dispatch — each request triggers a fresh planning cycle regardless of how similar it is to prior requests.

Recent work has begun to address routing efficiency.
RouteLLM trains routers to select between LLMs using preference data [ong2024routellm], and Mixture-of-Agents constructs layered multi-model architectures [wang2024moa].
However, these operate reactively at query time: they classify *then* route, with no speculation, no pre-execution, and no learning from dispatch history.

The gap is clear: the multi-agent orchestration layer lacks the predictive, speculative, and adaptive capabilities that have proven transformative in CPU architecture and LLM inference.

## 2.4 Empirical Motivation

To quantify the dispatch bottleneck, we profiled Clio Coder — the multi-agent orchestration component of the IOWarp scientific computing platform — handling realistic HPC-adjacent workloads including MPI code generation, scientific data pipeline construction, and research workflow automation.
[PLACEHOLDER: Insert Clio Coder profiling methodology — instrument dispatch pipeline stages, collect timing data across N requests over M days]

[PLACEHOLDER: Figure or table showing dispatch latency breakdown:
- Intent classification: ~X ms (Y% of total)
- Task decomposition/planning: ~X ms (Y% of total)
- Agent selection and resource matching: ~X ms (Y% of total)
- Context assembly and prompt construction: ~X ms (Y% of total)
- Agent initialization and warm-up: ~X ms (Y% of total)
- TOTAL dispatch overhead: ~X ms (Y% of end-to-end)]

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
