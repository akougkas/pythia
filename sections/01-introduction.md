# 1. Introduction

Driven by rapid advances in large language models (LLMs), AI agents are increasingly deployed in scientific computing, such as generating and optimizing parallel HPC code [hayashi2025vibecodehpc,karanjai2025hpcagenttester], automating data-driven discovery [majumder2024datadrivendiscovery], integrating expert tools for computational chemistry [bran2024chemcrow], and orchestrating autonomous experimentation across self-driving laboratories [hartung2025scaince].
Recent efforts such as SWARM [balaprakash2025swarm], which decentralizes workflow management across distributed HPC infrastructure via coordinating multiple agents, and Academy [souza2025provenance], which federates agents across Edge-Cloud-HPC environments, show that multi-agent coordination is gaining traction. Yet orchestrating these heterogeneous agents efficiently remains an open problem, as existing workflow management systems lack the ability to adapt dispatch decisions in real time as workloads and infrastructure change [shin2025revolution].

<!-- This coordination — the *orchestration layer* — has become a critical performance bottleneck. -->
This coordination, *the orchestration layer*, introduces significant overhead before any agent can begin productive work.
When a request arrives, the orchestrator must 1) classify the intent of the request; 2) decompose the request into subtasks; 3) select appropriate agents for each subtask; 4) map agents to available resources; and 5) produce a dispatch plan, which is a pipeline well-established in the centralized multi-agent systems literature [shen2023hugginggpt,qiao2024tdag,li2025masrouter,balaprakash2025swarm]. 
These stages form a data dependency chain. Each step requires its previous step's output, forcing strictly serial execution.
Agent selection is nontrivial especially under heterogeneous constraints (e.g., API rate limits, token budgets, GPU memory, cost ceilings across multiple AI providers, and compute tiers), which is an optimization problem rather than a simple lookup problem.
Only after the dispatch plan is produced can downstream tasks start executing, which includes context assembly from domain-specific data, agent initialization, and finally task execution.
We profile representative scientific computing workloads and observe that dispatch planning constitutes [PLACEHOLDER: X]\% of end-to-end latency for typical scientific computing requests.
However, this overhead is reducible: scientific computing users repeatedly submit similar workloads [luo2021inferring], making dispatch decisions predictable.
[OPTIONAL] Specifically, for the top-K intent classes (accounting for Z% of requests), the dispatch plan has low conditional entropy given the classified intent, making prediction tractable.

This pattern of a serial bottleneck with predictable outcomes is structurally analogous to latency problems solved by *speculative execution* in microprocessors [hennessy2017computer] and *speculative decoding* for LLM inference [leviathan2023fast,chen2023accelerating], where predicted work runs in parallel with the authoritative decision and commits if the prediction is correct.
Both paradigms share a principle that generalizes: *when verification is cheaper than stalling, and prediction accuracy improves with observation, speculative execution amortizes latency*.
Recent work has gradually begun applying speculative execution to agentic systems at different granularities, such as planning-step [hua2024isp,guan2025dsp], tool or API calls [ye2025specactions,paste2026], and workflow-node level [sherlock2025].
However, these approaches share three limitations.
First, all of them speculate within a single agent's execution trace after the dispatch decision is already made, and use binary accept/reject with no mechanism to salvage partially correct speculation.
Second, their learning mechanism targets either depth [guan2025dsp], tool-call patterns [paste2026], or verifier placement [sherlock2025], not dispatch-level predictions that refine progressively with accumulated confidence.
Third, they manage resources at the execution level, but none model heterogeneous constraints as inputs to dispatch decisions.
*Multi-agent dispatch* (i.e., the decision of which agents to assign, with what resources, to which subtasks) satisfies the same two conditions (cheap verification and high predictability) for speculation but remains unexplored.

To address this gap, we introduce **Pythia**, a speculative dispatch framework that lifts the draft-target speculation paradigm to the dispatch decision in multi-agent orchestration for scientific computing.
It runs the Dispatch Solver and a lightweight Speculative Dispatcher in parallel. The Speculative Dispatcher predicts a dispatch plan based on the classified intent first and immediately begins pre-executing the plan (e.g., context assembly, agent warm-up, resource reservation, or even draft task execution) while the Solver is still generating and computing the optimal assignment.
Once the Solver completes, the Reconciliation Engine either *commits* the speculative work (on correct prediction), *partially commits* salvageable portions (on partial match), or *flushes* the speculation entirely (on misprediction).
Pythia employs a *Learner* (Reinforcement Learning component) that observes reconciliation outcomes and continuously refines prediction accuracy. As a result, the system *progressively reduces dispatch latency* over time as it learns recurring workload patterns, while degrading gracefully to conservative speculation for novel or unpredictable tasks.
Specifically, Pythia structures speculation as a three-mode progressive hierarchy, from low-risk context prefetching to aggressive speculative execution, where each mode is gated by the Learner's confidence.
<!-- **Mode 1** (Speculative Context Preparation) prefetches related context and warms tool configurations, the dispatch analog of hardware cache prefetching. It incurs near-zero misprediction cost.
**Mode 2** (Speculative Agent Pre-dispatch) predicts which agents are needed and starts provisioning them, the dispatch analog of CPU speculative execution past a branch.
**Mode 3** (Speculative Execution with Verification) deploys a fast draft agent that begins producing output verified by the target agent upon arrival, the dispatch analog of LLM speculative decoding applied to multi-agent task execution. -->
<!-- Note (To Conffirm): Mode 3 is confused, I also don't understand why does it have a draft agent, what does this agent do? Does it want to say use a draf agent to generate plan at this mode, and immediate execute? Once the Solver finnished, does it ccompare with the Solver's dispatch Plan with Speculative Dispatcher's plan or current progress along with Plan.
1. The verification here is to verify what? the plan or the output?
Pythia Mode 3: a speculatively selected agent from the pool begins executing its predicted subtask, verified when the dispatch solver confirms the agent-task assignment was correct-->

<!-- For each mode, we derive a formal cost model to establish the break-even speculation accuracy, following the same cost structure that governs branch prediction profitability but now applied to agent dispatch. 
Modes 2 and 3 are each gated by learned confidence thresholds derived from this cost model.
Speculation at the dispatch level may incur higher misprediction cost than action-level speculation: a wrong dispatch will waste agent initialization, context assembly, and resource reservation, not just a single LLM call.
The progressive mode hierarchy ensures that this higher risk is taken only when the Learner's confidence justifies it. -->

This paper makes the following contributions:

1. **Speculative Dispatch Abstraction.** We propose a formal framework that lifts speculation from single-agent action traces to multi-agent dispatch decisions, with a three-mode progressive hierarchy and a commit/partial-commit/flush reconciliation protocol with salvage semantics.

2. **A Learner-Augmented Speculation Model.** We employ a reinforcement learning formulation that learns dispatch-level prediction patterns and outputs a calibrated confidence score to gate progressive mode activation as the system learns user-specific dispatch patterns.

3. **A Resource-Aware Dispatch Solver.** We treat the heterogeneous infrastructure constraints (e.g., compute capacity, memory, and API rate limits) as first-class inputs to dispatch decisions when mapping agents to resources in the optimization engine, bridging HPC scheduling with AI-specific resource dimensions.

4. **Implementation and evaluation.** We implement a prototype integrated into the IOWarp scientific computing platform and evaluate on four HPC-adjacent workload suites across heterogeneous infrastructure, demonstrating [PLACEHOLDER: X]\% dispatch latency reduction under Mode 2 speculation, [PLACEHOLDER: Y]\% under Mode 3, and learner convergence within [PLACEHOLDER: N] interactions.

<!-- The remainder of this paper is organized as follows.
Section~2 provides background on speculative execution and characterizes the dispatch bottleneck.
Section~3 presents the Pythia architecture, speculation modes, and formal cost model.
Section~4 describes the Learner's reinforcement learning formulation.
Section~5 details the implementation.
Section~6 presents the evaluation.
Section~7 discusses limitations and future directions.
Section~8 concludes. -->
