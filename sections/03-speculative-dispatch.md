# 3. Speculative Dispatch

This section presents the Speculative Dispatch framework: the five-layer architecture, the three progressive speculation modes, the reconciliation protocol, the formal cost model, and the resource-aware dispatch formulation.

## 3.1 Architecture Overview

The Speculative Dispatch pipeline consists of five components with well-defined data contracts (Figure 1).

**Intent Detector.**
A lightweight classifier that transforms a natural-language user request into a structured intent representation: task type, estimated complexity, domain tags, decomposability score, and constraint annotations.
The Intent Detector is deliberately shallow — it performs fast classification, not planning.
Its output feeds both the Dispatch Solver and the Speculative Dispatcher simultaneously.

**Dispatch Solver (Target).**
The full optimization engine that computes the optimal dispatch plan given the complete system state: all classified intents, the current agent pool, fleet configuration, resource availability, and cost constraints.
The Solver produces a `DispatchPlan` — a structured specification of which agents to invoke, on which resources, with what prompts, in what execution order, and under what budget constraints.
Solver latency is the bottleneck that speculation aims to hide.

**Speculative Dispatcher (Draft).**
A lightweight prediction model that runs in parallel with the Solver.
It produces a draft dispatch plan using pattern matching on intent classifications, a historical dispatch cache, and a learned user-specific fingerprint maintained by the Learner.
Upon generating its prediction, the Speculative Dispatcher immediately begins pre-execution steps according to the active speculation mode.
<!-- For speculative dispatcher, do we predict the order. 
Option A: Flat set + explicit execution order. The DispatchPlan is a list of (agent, resource, prompt, phase) tuples. Agents in the same phase run in parallel; phases run sequentially. Simple, not a full DAG, but captures the essential structure.                         
                                                                  
  dispatch_plan = [                                                                                                                                                                                                                                                              
      {"agent": "Claude-code-gen",    "phase": 1},  # runs first                                                                                                                                                                                                                 
      {"agent": "Slurm-template",     "phase": 2},  # waits for phase 1                                                                                                                                                                                                          
      {"agent": "HPCToolkit-profiler", "phase": 2},  # also waits for phase 1                                                                                                                                                                                                    
  ] 
If you go with Option A (phased execution), how does reconciliation change? Think about it — the Speculative Dispatcher now needs to predict not just which agents but also which phase each agent belongs to. What does PARTIAL COMMIT look like when you   
  get the agents right but the phases wrong?  -->

**Orchestrator (Reconciliation Engine).**
Receives both the Solver's optimal plan and the Speculative Dispatcher's pre-executed work.
Performs reconciliation: comparing the two plans element-by-element and issuing one of three verdicts — COMMIT, PARTIAL COMMIT, or FLUSH — before executing the final dispatch.

**Learner.**
A reinforcement learning component that observes the full dispatch lifecycle — intent, solver plan, speculation result, reconciliation decision, and execution outcome — and continuously updates the Speculative Dispatcher's prediction model.
The Learner is described in detail in Section 4.

```
[FIGURE 1: Five-layer architecture diagram. Request flows down through
Intent Detector → parallel split to Solver and Speculative Dispatcher →
Orchestrator reconciliation → Agent Execution → Learner feedback loop.
Show data contracts at each interface.]
```

## 3.2 Speculation Modes

We define three progressive speculation modes, each representing a deeper commitment of resources to the predicted dispatch plan.
The modes form a hierarchy: each successive mode subsumes the previous and adds additional speculative work with higher potential reward but greater misprediction cost.

### Mode 1: Speculative Context Preparation

**Analogy:** CPU cache prefetching.

As soon as intents are classified, the Speculative Dispatcher fetches relevant context documents, warms tool configurations (e.g., MCP server connections), pre-loads agent system prompts, and pre-assembles prompt templates.
This work is useful regardless of the final dispatch plan because the same context typically applies no matter which specific agent is selected — a code generation task requires the same codebase context whether handled by Agent A or Agent B.

**Formal characterization.** Let $C_{prep}$ be the cost of context preparation and $C_{prep}^{waste}$ be the fraction of preparation wasted on a misprediction. For Mode 1, $C_{prep}^{waste} \approx 0$ because context is agent-agnostic. Mode 1 is therefore activated unconditionally — there is no confidence threshold because the downside is negligible.

### Mode 2: Speculative Agent Pre-dispatch

**Analogy:** CPU speculative execution past a branch.

The Speculative Dispatcher predicts which agents will be needed and begins provisioning them: allocating compute resources, initializing agent runtimes, establishing API connections, and loading agent-specific configurations.
This mode is gated by a confidence threshold $\tau_2$ — the Speculative Dispatcher only activates Mode 2 when its prediction confidence for the intent class exceeds $\tau_2$.

**Formal characterization.** Let $C_{init}$ be the cost of agent initialization and $p$ be the speculation accuracy (probability that the predicted agent set matches the Solver's optimal set). The expected cost of Mode 2 speculation is:

$$E[C_{M2}] = p \cdot 0 + (1 - p) \cdot C_{init} = (1 - p) \cdot C_{init}$$

The expected benefit is $p \cdot L_{init}$, where $L_{init}$ is the agent initialization latency saved on a correct prediction. Mode 2 is profitable when:

$$p \cdot L_{init} > (1 - p) \cdot C_{init}$$

$$p > \frac{C_{init}}{L_{init} + C_{init}} = \tau_2^*$$

This is the break-even accuracy threshold for Mode 2 — structurally identical to the break-even condition in CPU branch prediction.

### Mode 3: Speculative Execution with Verification

**Analogy:** LLM speculative decoding.

A fast, cheap *draft agent* (e.g., a smaller model, a cached prior response template, or a heuristic generator) begins producing actual task output while the Solver computes the optimal plan and the target agent is being provisioned.
When the target agent's plan arrives, the Orchestrator compares the draft output against what the target agent would produce.
If aligned, the draft output is accepted — exactly as speculated tokens are accepted in LLM inference.
If not, the draft output is discarded and the target agent executes fresh.

**Formal characterization.** Let $C_{draft}$ be the cost of running the draft agent, $L_{target}$ be the target agent's execution latency, and $q$ be the output acceptance probability (fraction of draft work that the target agent validates). The expected net benefit is:

$$\Delta = q \cdot L_{target} - C_{draft} - (1 - q) \cdot C_{flush}^{M3}$$

where $C_{flush}^{M3}$ includes the overhead of discarding draft output and any state cleanup. Mode 3 is profitable when:

$$q > \frac{C_{draft} + C_{flush}^{M3}}{L_{target} + C_{flush}^{M3}} = \tau_3^*$$

This mirrors the acceptance rate threshold in speculative decoding, where the draft model must align with the target model above a minimum rate for net speedup.

```
[FIGURE 2: Three speculation modes shown as progressive layers.
Mode 1 (always on) → Mode 2 (confidence-gated) → Mode 3 (high-confidence only).
Show risk/reward tradeoff increasing with each mode.
Annotate with CPU/LLM analogy labels.]
```

## 3.3 Reconciliation Protocol

The Orchestrator performs reconciliation when the Solver's optimal plan $P^*$ arrives and speculative pre-execution based on predicted plan $\hat{P}$ is in progress.
We define three reconciliation outcomes:

**COMMIT ($P^* = \hat{P}$).**
The speculative plan matches the optimal plan exactly.
All pre-executed work is accepted.
Effective dispatch latency is reduced to zero — the system has been executing the correct plan since the Speculative Dispatcher's prediction.

**PARTIAL COMMIT ($P^* \cap \hat{P} \neq \emptyset$, $P^* \neq \hat{P}$).**
Some speculated agents and context match the optimal plan; others do not.
The Orchestrator retains the correctly speculated work and issues *redirect* commands for the mismatched components.
Partial commit requires careful state management: agents that were speculatively started with incorrect prompts or context must be either re-initialized with corrected inputs (if cheaper than starting fresh) or terminated and replaced.

We define the *salvage ratio* $\sigma$ as the fraction of speculative work retained under partial commit:

$$\sigma = \frac{|P^* \cap \hat{P}|}{|\hat{P}|}$$

The cost of partial commit is $(1 - \sigma) \cdot C_{redirect}$, where $C_{redirect}$ is the average cost of redirecting a mismatched agent.
Partial commit is the most operationally complex case and the most common in practice — full matches and full misses are edge cases for mature systems.

**FLUSH ($P^* \cap \hat{P} = \emptyset$).**
The speculative plan is entirely wrong.
All pre-executed work is discarded.
The Solver's plan executes from scratch.
Effective latency equals the non-speculative baseline plus the wasted resources consumed by the flushed speculation.

## 3.4 Cost Model

We now derive the unified cost model for Speculative Dispatch.
Let $L_s$ be the Solver's latency, $L_{spec}$ be the Speculative Dispatcher's latency (where $L_{spec} \ll L_s$ by construction), and $p_c$, $p_{pc}$, $p_f$ be the probabilities of COMMIT, PARTIAL COMMIT, and FLUSH respectively ($p_c + p_{pc} + p_f = 1$).

**Non-speculative baseline latency:**

$$L_{baseline} = L_s + L_{exec}$$

where $L_{exec}$ is the agent execution latency after dispatch.

**Speculative dispatch latency:**

$$L_{spec\_dispatch} = L_s + p_c \cdot 0 + p_{pc} \cdot (1 - \bar{\sigma}) \cdot L_{redirect} + p_f \cdot L_{exec}$$

The expected latency reduction is:

$$\Delta L = L_{exec} - [p_c \cdot 0 + p_{pc} \cdot (1 - \bar{\sigma}) \cdot L_{redirect} + p_f \cdot L_{exec}]$$

Speculation is net-positive when $\Delta L > 0$, which simplifies to:

$$p_c + p_{pc} \cdot \bar{\sigma} > \frac{L_{exec} - L_{redirect}}{L_{exec}} \cdot p_{pc} + 0$$

More intuitively: speculation pays off when the weighted probability of usable pre-execution exceeds the relative cost of wasted work.
The break-even accuracy — the minimum COMMIT + weighted PARTIAL COMMIT rate — depends on the ratio of flush cost to saved latency, exactly as in CPU speculation.

**Wasted compute ratio:**

$$W = \frac{p_f \cdot C_{spec} + p_{pc} \cdot (1 - \bar{\sigma}) \cdot C_{spec}}{C_{total}}$$

where $C_{spec}$ is the total resource cost of speculative pre-execution and $C_{total}$ is the total system resource consumption.
$W$ is the primary cost metric — it quantifies the price of misprediction and is directly comparable to the wasted instruction ratio in CPU speculation.

## 3.5 Resource-Aware Dispatch

The Dispatch Solver operates over a heterogeneous resource landscape.
We model the available infrastructure as a *fleet* $\mathcal{F} = \{f_1, \ldots, f_n\}$ where each fleet member $f_i$ has a capability vector:

$$f_i = (\text{compute}_i, \text{memory}_i, \text{rate\_limit}_i, \text{token\_budget}_i, \text{cost\_rate}_i, \text{latency}_i)$$

The Solver optimizes dispatch subject to:

- **Capacity constraints:** Agent assignments must not exceed any fleet member's compute, memory, or concurrent request limits.
- **Budget constraints:** Total token consumption and API costs must stay within per-request and per-session budgets.
- **Rate limit constraints:** Dispatch rates to external API providers must respect per-minute and per-day rate limits.
- **Affinity constraints:** Some agents perform better on specific infrastructure (e.g., local models on GPU nodes, API models through low-latency network paths).

This formulation connects directly to the HPC scheduling literature [CITE:feitelson2004], where job schedulers solve analogous constraint satisfaction problems over heterogeneous compute resources.
The key extension is that our constraints include AI-specific dimensions — token budgets and API rate limits — that have no direct analog in traditional HPC scheduling.
