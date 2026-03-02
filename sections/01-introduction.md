# 1. Introduction

Scientific computing stands at an inflection point.
Autonomous AI agents are no longer peripheral tools but active participants in research workflows — generating MPI code, constructing data processing pipelines, orchestrating experiments across heterogeneous infrastructure, and analyzing results at scales that exceed manual human effort.
National cyberinfrastructure initiatives are integrating these agents into platforms that span GPU-accelerated clusters, multi-tier storage hierarchies, and cloud computing resources, creating distributed multi-agent systems that must coordinate dozens of specialized agents across heterogeneous hardware and multiple AI providers simultaneously.

This coordination — the *orchestration layer* — has become a critical performance bottleneck.
When a researcher issues a natural-language request to a multi-agent scientific computing platform, the orchestrator must classify the intent, decompose the task, select appropriate agents, match them to available resources, assemble context from scientific datasets (HDF5, NetCDF, Zarr, and others), construct prompts, and dispatch execution — all before any productive computation begins.
We observe that this dispatch overhead constitutes [PLACEHOLDER: X]\% of end-to-end response latency for typical scientific computing tasks.
The problem compounds in heterogeneous environments where the dispatch solver must navigate provider-specific constraints: API rate limits, token budgets, GPU memory availability, and cost ceilings across multiple AI providers and compute tiers.
For short-duration tasks — the majority of interactive scientific computing requests — dispatch latency can approach or exceed the execution time itself, inverting the intended ratio of useful computation to scheduling overhead.
The HPC community has decades of experience optimizing scheduling overhead in job schedulers, but multi-agent orchestration introduces new dimensions — AI provider selection, prompt construction, token budget management — that existing scheduling theory does not address.

Yet dispatch decisions are not random.
A computational scientist who spends mornings on code review and afternoons on data analysis exhibits strong temporal regularity.
A materials science pipeline that repeatedly invokes the same sequence of agents for structure optimization, property prediction, and visualization follows a predictable dispatch pattern.
We find that for the top-$K$ intent classes — which cover [PLACEHOLDER: Z]\% of all requests in our evaluation — the dispatch plan has low conditional entropy given the classified intent, making prediction tractable.
This regularity is not coincidental: scientific computing workflows are inherently structured, and researchers develop habitual interaction patterns with their tools.

This combination of bottleneck and predictability is structurally identical to latency problems solved in two domains well known to the HPC community.

In processor microarchitecture, *speculative execution* predicts branch outcomes and executes instructions along the predicted path before the branch is resolved; if correct, results commit at zero additional cost [hennessy2017computer].
Modern TAGE-class predictors achieve accuracy exceeding 95\% [seznec2011tage].
In large language model inference, *speculative decoding* uses a small draft model to generate candidate tokens that a larger target model verifies in a single forward pass, achieving 2--3$\times$ throughput improvements [leviathan2023fast, chen2023accelerating].
Both paradigms share a principle that generalizes: *when verification is cheaper than stalling, and prediction accuracy improves with observation, speculative execution amortizes latency*.
We observe that multi-agent dispatch satisfies both conditions and propose a third domain for this paradigm.

We introduce **Pythia**, a speculative dispatch framework that transfers the draft-target speculation paradigm to multi-agent orchestration for scientific computing.
When a request arrives, Pythia's lightweight speculative dispatcher predicts the likely dispatch plan and immediately begins pre-execution — context assembly, agent warm-up, resource reservation, and even draft task execution — while the full dispatch solver computes the optimal plan in parallel.
The solver's output either *commits* the speculative work (prediction correct), *partially commits* salvageable portions (partial match), or *flushes* the speculation entirely (misprediction).
A reinforcement learning component — the *Learner* — observes dispatch outcomes and continuously refines prediction accuracy, creating an orchestration system whose latency *decreases the more it is used* by a given researcher on a given infrastructure.
The result is a system that converges toward oracle-level dispatch performance for recurring workload patterns while degrading gracefully to conservative speculation for novel or unpredictable tasks.

We formalize speculation as a three-mode progressive hierarchy.
**Mode 1** (Speculative Context Preparation) prefetches context and warms caches — the dispatch analog of hardware cache prefetching — with near-zero misprediction cost.
**Mode 2** (Speculative Agent Pre-dispatch) predicts which agents are needed and begins provisioning — the dispatch analog of speculative execution past a branch — gated by a learned confidence threshold.
**Mode 3** (Speculative Execution with Verification) deploys a fast draft agent that begins producing output verified by the target agent upon arrival — the direct analog of LLM speculative decoding applied to multi-agent task execution.
For each mode, we derive a formal cost model establishing the break-even speculation accuracy — the same cost structure that governs branch prediction profitability, now applied to agent dispatch.

This paper makes the following contributions:

1. **The Speculative Dispatch abstraction.** A formal framework adapting the draft-target speculation paradigm from CPU architecture and LLM inference to multi-agent orchestration, with a three-mode speculation hierarchy (context preparation, agent pre-dispatch, execution with verification) and a commit/partial-commit/flush reconciliation protocol with formally defined salvage semantics.

2. **A learner-augmented speculation model.** A reinforcement learning formulation that treats dispatch prediction as a contextual bandit problem, enabling progressive mode activation from conservative context preparation to aggressive speculative execution as the system learns user-specific dispatch patterns. The Learner includes concept drift detection for graceful degradation under non-stationary workloads.

3. **A resource-aware dispatch solver.** An optimization engine that treats heterogeneous infrastructure constraints — compute capacity, memory, API rate limits, token budgets, and cost ceilings — as first-class scheduling parameters, extending the HPC scheduling formulation to AI-specific resource dimensions that have no analog in traditional job scheduling.

4. **Implementation and evaluation.** A working prototype integrated into the IOWarp scientific computing platform (an NSF Cyberinfrastructure project), evaluated on four HPC-adjacent workload suites across heterogeneous infrastructure, demonstrating [PLACEHOLDER: X]\% dispatch latency reduction under Mode 2 speculation, [PLACEHOLDER: Y]\% under Mode 3, and learner convergence within [PLACEHOLDER: N] interactions.

The remainder of this paper is organized as follows.
Section~2 provides background on speculative execution and characterizes the dispatch bottleneck.
Section~3 presents the Pythia architecture, speculation modes, and formal cost model.
Section~4 describes the Learner's reinforcement learning formulation.
Section~5 details the implementation.
Section~6 presents the evaluation.
Section~7 discusses limitations and future directions.
Section~8 concludes.
