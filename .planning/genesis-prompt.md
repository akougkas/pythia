# Research Project: Speculative Dispatch for Multi-Agent Orchestration Systems

## Target Venue & Deadlines

**SC26 — The International Conference for High Performance Computing, Networking, Storage, and Analysis**
November 15–20, 2026 | McCormick Place, Chicago, Illinois

| Milestone | Date |
|-----------|------|
| Submissions Open | March 1, 2026 |
| Abstract Deadline | April 1, 2026 |
| Paper Deadline (hard, no extensions) | April 8, 2026 |
| AD Appendix Due (mandatory) | April 24, 2026 |
| Review/Rebuttal Period | June 8–11, 2026 |
| Notifications | July 1, 2026 |
| Final Paper Due | August 28, 2026 |

**Format**: 10 pages (two-column, US Letter), IEEE proceedings template, excluding bibliography and AD/AE appendices. Double-anonymous review. Artifact Description appendix is mandatory.

**Primary Area**: "System Software & Cloud Computing" — specifically: *Systems that facilitate distributed applications, such as workflow systems, task-oriented systems, functions-as-a-service, and service-oriented computing; Scheduling, load balancing, resource provisioning, resource management, cost efficiency, fault tolerance, and reliability for large-scale systems and clouds.*

**Secondary Area**: "Data Analytics, Visualization, & Storage" — specifically: *Storage innovations using machine learning; Data integration workflows and design and performance of data-centric workflows.*

---

## The Research Idea

### Origin and Inspiration

This work draws from two well-established optimization techniques in computer systems:

**1. CPU Speculative Execution.** Modern out-of-order processors predict branch outcomes and execute instructions speculatively along the predicted path. If the prediction is correct, the results are committed with zero additional latency. If the prediction is wrong, the speculative work is flushed and the correct path is executed from scratch. The net effect is positive as long as the branch predictor accuracy exceeds a threshold (~60-70% for typical workloads). Branch predictors improve over time through hardware learning (e.g., two-level adaptive predictors, TAGE). The critical insight: *verification is cheaper than stalling, and prediction accuracy improves with observation.*

**2. LLM Speculative Decoding.** In large language model inference, a small, fast "draft" model generates candidate token sequences, and a larger, more capable "target" model verifies them in a single forward pass. Because verification (scoring multiple tokens simultaneously) is far cheaper than autoregressive generation (producing one token at a time), the system achieves significant speedups when the draft model's predictions align with what the target model would have produced. Key papers: Leviathan et al. (2023) "Fast Inference from Transformers via Speculative Decoding," Chen et al. (2023) "Accelerating Large Language Model Decoding with Speculative Sampling." Production implementations exist in vLLM, TensorRT-LLM, llama.cpp, and Medusa/EAGLE variants. The critical insight: *a cheap approximation running in parallel with an expensive exact computation amortizes latency when alignment is high.*

**3. Our Contribution: Speculative Dispatch for Multi-Agent Orchestration.** We propose adapting the draft-target speculation paradigm to the orchestration layer of multi-agent AI systems. When a user request arrives at a multi-agent system, the orchestrator must decide which agents to dispatch, on what resources, with what prompts, in what order — a combinatorial optimization problem that introduces latency before any useful work begins. We introduce a **Speculative Dispatcher** that runs a lightweight "draft dispatch" model in parallel with the full dispatch solver. The speculative dispatcher predicts the likely dispatch plan based on classified intent patterns and begins pre-execution steps (context assembly, agent warm-up, resource reservation, prompt pre-computation, and even draft task execution) while the full solver computes the optimal plan. The solver's output either **commits** the speculative work (zero wasted dispatch latency), **partially commits** (redirect some agents, keep others), or **flushes** (discard and execute from scratch). A reinforcement learning loop — the **Learner** — observes dispatch outcomes over time and continuously improves the speculative model's prediction accuracy, creating a system that gets faster the more it is used by a specific user on a specific infrastructure.

### Why This Matters for HPC

Multi-agent AI systems are rapidly entering scientific computing workflows. Researchers increasingly use AI agents for code generation, data analysis, experiment orchestration, and workflow management across HPC resources. Current orchestration approaches are naive: sequential intent parsing → planning → dispatch → execution, with no speculation, no learning, and no resource-awareness. This work brings HPC-grade scheduling intelligence to AI agent orchestration, directly connecting to the SC community's expertise in job scheduling, resource management, and performance optimization.

The system is designed to operate across heterogeneous infrastructure: local workstations, cloud instances, and HPC cluster nodes — respecting provider-specific constraints (API rate limits, token budgets, subscription tiers) as first-class optimization parameters rather than afterthoughts.

---

## Architecture

The full dispatch pipeline consists of five layers with well-defined data contracts:

```
User Request (natural language query to a multi-agent coding/research system)
    │
    ▼
┌─────────────────────────────────────────────────┐
│              INTENT DETECTOR                     │
│  Lightweight classification of the request into  │
│  structured intents: task type, complexity        │
│  estimate, domain, constraints, decomposability.  │
│  Fast, cheap — NOT the planning step.             │
└───────────────┬─────────────────────────────────┘
                │ Intent (structured)
        ┌───────┴───────────────────────┐
        ▼                               ▼
┌───────────────────┐     ┌──────────────────────────────┐
│   DISPATCH SOLVER  │     │   SPECULATIVE DISPATCHER      │
│   (Target Model)   │     │   (Draft Model)                │
│                    │     │                                │
│ Full optimization: │     │ Lightweight prediction:        │
│ • All intents      │     │ • Pattern matching on intents  │
│ • Agent pool state │     │ • Historical dispatch cache    │
│ • Fleet config     │     │ • Learned user fingerprint     │
│ • Resource limits  │     │                                │
│ • Cost constraints │     │ Races ahead with draft plan    │
│ • Produces optimal │     │ and begins pre-execution:      │
│   dispatch plan    │     │ • Context fetching             │
│                    │     │ • Agent warm-up                │
│                    │     │ • Prompt pre-assembly          │
│                    │     │ • Resource reservation         │
│                    │     │ • Draft task execution (Mode 3)│
└────────┬──────────┘     └──────────────┬───────────────┘
         │ DispatchPlan                   │ SpeculationResult
         │ (optimal)                      │ (draft + pre-executed work)
         └───────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│                ORCHESTRATOR                      │
│  Reconciliation engine:                          │
│  • Receives Solver's optimal plan                │
│  • Compares against Speculative pre-execution    │
│  • COMMIT: speculation matches → zero latency    │
│  • PARTIAL COMMIT: keep useful work, redirect    │
│  • FLUSH: discard speculation, execute fresh     │
│  • Executes final dispatch                       │
│  • Monitors, coordinates, handles failures       │
└───────────────────┬─────────────────────────────┘
                    ▼
            [Agent Execution]
                    │
                    ▼  DispatchOutcome (telemetry)
┌─────────────────────────────────────────────────┐
│                  LEARNER                          │
│  Reinforcement learning loop:                    │
│  • Collects: intent → solver plan → speculation  │
│    result → reconciliation decision → outcome    │
│  • Tracks speculation accuracy per intent class  │
│  • Learns user-specific patterns over time       │
│  • Updates speculation confidence thresholds     │
│  • Optimizes for: latency, cost, correctness,    │
│    resource utilization                          │
│  • Feeds improved heuristics back to the         │
│    Speculative Dispatcher                        │
└─────────────────────────────────────────────────┘
```

### Three Speculation Modes (Progressive)

**Mode 1 — Speculative Context Preparation.**
Analogous to CPU cache prefetching. As soon as intents are classified, the speculative dispatcher fetches relevant context, warms caches, pre-loads tool configurations (e.g., MCP servers), and pre-assembles prompt templates. This work is useful regardless of the final dispatch plan — context preparation is rarely wasted because most of the same context applies no matter which agent is selected. Low risk, consistent reward. This is the baseline speculation mode.

**Mode 2 — Speculative Agent Pre-dispatch.**
Analogous to CPU speculative execution past a branch. A draft dispatch model (which could be a smaller LLM, a learned lookup table of recent patterns, or a heuristic model trained by the Learner) predicts which agents will be needed and begins spinning them up with provisional prompts and resource allocations. The full Solver's plan either confirms (commit) or redirects (partial flush). This mode is gated by a confidence threshold — only speculate when draft model confidence exceeds a tunable parameter. The cost of misprediction is wasted agent initialization, so the threshold must be calibrated against infrastructure costs.

**Mode 3 — Speculative Execution with Verification.**
The full LLM speculative decoding analogy applied to agent outputs. A fast, cheap "draft agent" (e.g., a smaller model or cached prior response) actually begins producing task output while the target agent is being set up with the Solver's optimal plan. If the target agent's plan aligns with the draft agent's work, the draft output is accepted (exactly like accepting speculated tokens in LLM inference). If not, the draft output is discarded and the target agent runs fresh. This is the most aggressive mode and the most paper-worthy contribution — it's the first application of the draft-target verification pattern to multi-agent task execution.

### The Learner's Role in Speculation

The Learner creates a reinforcement learning feedback loop that makes the system increasingly aggressive in its speculation over time:

- **Early usage** (cold start): The system operates conservatively, primarily Mode 1 (context prep). The Learner is collecting telemetry — observing which intents lead to which dispatch plans, which agents get selected, what resources are used.
- **After N interactions**: The Learner has built a user-specific dispatch fingerprint. For recurring intent patterns (which dominate real usage — most users have a handful of common task types), speculation accuracy is high enough to activate Mode 2.
- **Mature system**: With sufficient telemetry, the Learner activates Mode 3 for high-confidence intent classes, achieving maximum latency reduction. The system effectively "knows" what the user is going to need before the Solver finishes computing it.

This progression mirrors how CPU branch predictors improve from static heuristics to learned patterns. The paper should explicitly draw this parallel.

---

## Contributions

The paper should present the following contributions:

1. **The Speculative Dispatch abstraction.** A formal framework that adapts the draft-target speculation paradigm (from both CPU architecture and LLM inference) to multi-agent orchestration. This includes the three-mode speculation hierarchy and the commit/partial-commit/flush reconciliation protocol.

2. **A learner-augmented speculation model.** An RL-based system that improves speculation accuracy over time by learning user-specific dispatch patterns, creating a system where orchestration latency decreases with usage. We formalize this as an online learning problem with well-defined regret bounds.

3. **A resource-aware dispatch solver.** A dispatch optimization engine that treats heterogeneous infrastructure constraints (compute, memory, API rate limits, token budgets, subscription tiers, cost budgets) as first-class parameters. This connects directly to HPC scheduling literature and extends it to the multi-agent AI context.

4. **Implementation and evaluation.** A working prototype built on top of Cleo Coder (a distributed agentic coding harness) evaluated on realistic HPC-adjacent workloads. We demonstrate measurable latency reduction, quantify the cost of misprediction, and show the Learner's convergence behavior.

---

## Experimental Design

### System Under Test

The prototype is implemented within Cleo Coder, a multi-vendor, multi-platform distributed agentic coding system. The system orchestrates coding agents across heterogeneous infrastructure (local machines, cloud instances, and HPC cluster nodes) using multiple AI providers (Anthropic, OpenAI, open-source local models via Ollama/LM Studio).

### Workloads

Design experiments using workloads relevant to the SC audience:

1. **HPC Code Generation Workflows.** Multi-step tasks representative of scientific computing: generating MPI code, writing Slurm job scripts, debugging parallel programs, profiling and optimizing HPC applications. These involve multiple agents (planner, coder, tester, reviewer) with complex dependencies.

2. **Scientific Data Pipeline Construction.** Building data processing pipelines involving I/O optimization, data format conversion (HDF5, NetCDF), and analysis script generation. Relevant to the IOWarp and ChronoLog project contexts.

3. **Research Workflow Automation.** Literature search → experimental design → code generation → result analysis → paper drafting. This represents a realistic end-to-end research workflow that exercises all speculation modes.

4. **Micro-benchmarks for Speculation Modes.** Isolated experiments that measure the latency and cost characteristics of each speculation mode independently, varying confidence thresholds and infrastructure configurations.

### Metrics

- **End-to-end dispatch latency**: Time from request arrival to first agent output. The primary metric. Measure with and without speculation across all three modes.
- **Speculation hit rate**: Fraction of speculative dispatch plans that are committed (fully or partially) vs. flushed. Analogous to branch prediction accuracy in CPU literature and acceptance rate in LLM speculative decoding.
- **Wasted compute ratio**: Resources consumed by flushed speculative work as a fraction of total resources consumed. The "misprediction cost."
- **Dispatch quality**: Does the speculated plan produce equivalent output quality to the non-speculative optimal plan? Measure via automated code quality metrics and human evaluation.
- **Learner convergence**: How many interactions before the Learner achieves stable speculation accuracy for a given user? Plot learning curves.
- **Cost efficiency**: Total API tokens consumed, compute-hours used, subscription budget consumed — with and without speculation. The system should be net-positive on cost despite occasional mispredictions.
- **Scalability**: How does speculation overhead scale with the number of available agents, the size of the fleet, and the complexity of the dispatch search space?

### Baselines

1. **No speculation** (sequential pipeline): Intent detection → Solver → Orchestrator → Dispatch. The standard baseline.
2. **Static heuristic dispatch**: Simple rule-based dispatch without solver optimization (represents naive current-generation orchestrators).
3. **Speculation without learning**: Fixed speculative heuristics that don't improve over time. Isolates the Learner's contribution.
4. **Oracle speculation**: A "perfect predictor" that always speculates correctly. Upper bound on achievable latency reduction.

### Ablation Studies

- Mode 1 only vs. Mode 1+2 vs. Mode 1+2+3
- Effect of confidence threshold on hit rate and wasted compute
- Learner with varying history window sizes
- Single-user vs. multi-user speculation models
- Homogeneous vs. heterogeneous infrastructure

---

## Narrative Arc for the Paper

### Story

The paper tells the following story:

**Opening (Section 1 — Introduction):** Multi-agent AI systems are entering scientific computing workflows at scale. The orchestration layer — which decides what agents run where with what context — is becoming a performance bottleneck. Current orchestrators treat every request as a cold-start planning problem, ignoring the fact that (a) many dispatch decisions are predictable from the request's intent, and (b) most pre-execution setup work is useful regardless of the exact dispatch plan. We observe that this is the same problem that CPU architects solved with speculative execution and that LLM inference engineers solved with speculative decoding. We adapt these techniques to multi-agent orchestration.

**Problem (Section 2 — Background & Motivation):** Characterize the dispatch latency problem empirically. Show measurements from a real multi-agent system (Cleo Coder) demonstrating that dispatch planning and setup constitute X% of end-to-end latency. Show that dispatch plans are highly predictable for recurring intent patterns. Motivate the analogy to CPU speculation and LLM speculative decoding with concrete parallels.

**Design (Section 3 — Speculative Dispatch):** Present the architecture. Define the five layers. Formalize the three speculation modes. Define the commit/partial-commit/flush reconciliation protocol. Formalize the cost model: when does speculation pay off? Derive the break-even speculation accuracy threshold (analogous to the minimum branch prediction accuracy for net-positive speculative execution).

**Learning (Section 4 — Learner-Augmented Speculation):** Present the RL formulation. The state space is the intent classification + fleet state. The action space is the speculative dispatch plan. The reward signal is the reconciliation outcome (commit = positive reward, flush = negative reward proportional to wasted resources). Show how the Learner shifts the system from conservative to aggressive speculation over time. Draw explicit parallels to how CPU branch predictors evolve from static to adaptive to neural.

**Implementation (Section 5):** Describe the prototype in sufficient detail for reproducibility. Data contracts, component interfaces, the specific models and agents used. Artifact Description appendix should cover deployment instructions, dependencies, and reproduction steps.

**Evaluation (Section 6):** Present results across all workloads and metrics. Key plots: (a) dispatch latency reduction across speculation modes, (b) speculation hit rate over time (the learning curve), (c) wasted compute ratio vs. confidence threshold (the Pareto frontier), (d) scalability with fleet size and agent count, (e) cost efficiency analysis.

**Discussion (Section 7):** Limitations (cold start, adversarial/unpredictable workloads, security considerations of speculative resource access — the Spectre analogy). Future directions (federated learning across users, transfer learning across projects, integration with HPC job schedulers like Slurm).

**Conclusion (Section 8):** Summarize contributions. The speculative dispatch paradigm, the learner-augmented speculation model, and experimental evidence that the system achieves meaningful latency reduction while maintaining dispatch quality.

---

## Related Work Domains to Cover

The background research must be thorough and precisely positioned. Cover these domains:

### Speculative Decoding in LLM Inference
- Leviathan et al. (2023), Chen et al. (2023) — foundational speculative decoding
- Medusa (Cai et al. 2024) — multiple draft heads
- EAGLE/EAGLE-2 — context-aware draft models
- SpecInfer — tree-based speculation
- Production implementations: vLLM, TensorRT-LLM, llama.cpp speculative decoding
- Acceptance rate analysis and cost models

### CPU Speculative Execution
- Branch prediction fundamentals (two-level adaptive, gshare, TAGE)
- Speculative execution cost models and break-even analysis
- Spectre/Meltdown — security implications of speculation (directly relevant: speculative resource access in agent systems could leak context across users in multi-tenant deployments)

### Multi-Agent Orchestration
- CrewAI, AutoGen/AG2, LangGraph, OpenAI Swarm — current frameworks and their dispatch mechanisms
- Agent routing in production systems (ChatGPT, Claude, Gemini)
- Mixture-of-agents architectures
- ReAct, plan-and-execute, and other agentic patterns

### HPC Job Scheduling and Resource Management
- Classical HPC scheduling: FCFS, backfill, fair-share
- RL-based scheduling: DeepRM (Mao et al. 2016), Decima (Mao et al. 2019)
- Heterogeneous resource scheduling in HPC
- Slurm, PBS, and modern resource managers
- This literature is critical for SC positioning — the dispatch solver is essentially an HPC-informed scheduler for AI agents

### Reinforcement Learning for System Optimization
- RL for query optimization in databases (learned query optimizers)
- Online learning and contextual bandits for routing decisions
- Transfer learning and personalization in RL systems

---

## Key Technical Challenges to Address

These are the hard problems the paper must confront:

1. **Cold-start problem.** The Learner has no history for new users or new task types. The paper needs a principled cold-start strategy (Mode 1 default, Bayesian priors from aggregate patterns, transfer learning from similar users).

2. **Speculation cost model.** Precisely quantify when speculation pays off. Derive the break-even accuracy threshold as a function of: dispatch solver latency, speculative pre-execution cost, agent initialization cost, and misprediction flush cost. This is the paper's theoretical core.

3. **Partial commit semantics.** Full commit and full flush are straightforward. Partial commit — where some speculated agents are correct but others need redirection — requires careful protocol design. How do you "redirect" an agent that has already started working? What state can be salvaged?

4. **Multi-tenant security.** If the speculative dispatcher pre-fetches context or pre-warms agents, is there a risk of context leakage between users in a shared deployment? This is the Spectre analogy for agent systems and SC reviewers will ask about it.

5. **Non-stationary user behavior.** Users change their patterns over time. The Learner must handle distribution shift (a user starts working on a new project, changes their preferred tools). Discuss concept drift detection and model refresh strategies.

---

## What You (the Writing Agent) Must Do

You are an expert academic research agent. Your job is to independently produce a complete, submission-ready SC26 paper. This means:

1. **Conduct thorough background research.** Search for, read, and synthesize all relevant prior work across the domains listed above. Build a proper bibliography. Identify the precise novelty gap — what has been done before, what hasn't, and where we differentiate.

2. **Formalize the technical contribution.** Define the speculation cost model mathematically. Formalize the RL formulation for the Learner. Derive the break-even speculation accuracy threshold. This paper needs theory, not just system description.

3. **Design and run experiments.** Implement the prototype, design the workloads, run the experiments, collect the data, and produce publication-quality figures. Follow the experimental design above but adapt as needed based on what you learn during implementation.

4. **Write the paper.** 10 pages, IEEE two-column format, double-anonymous. Clear, precise, SC-quality writing. Strong related work section. Honest limitations discussion. Compelling evaluation.

5. **Prepare the AD appendix.** Mandatory for SC26. Describe all artifacts, how to reproduce results, and what dependencies are required.

6. **Self-review.** Before submitting any draft, review it against SC26's criteria: novelty, technical soundness, relevance to HPC, quality of evaluation, reproducibility. Address weaknesses proactively.

### Constraints

- **Double-anonymous.** No author names, affiliations, funding acknowledgments, or self-identifying references in the submission. Self-cite in third person.
- **10-page hard limit** (excluding bibliography and appendices). Every sentence must earn its place. No filler, no padding, no redundant motivation.
- **SC audience.** These are HPC systems people. They know scheduling, they know resource management, they know distributed systems. They may not know LLM speculative decoding details — explain that clearly. They definitely know CPU speculative execution — leverage that familiarity.
- **AI-generated text policy.** SC26 permits AI tools but requires disclosure in acknowledgments and citations to AI systems used. Plan for this.
- **The paper must be original work** not previously published in a peer-reviewed venue. arXiv preprint is fine.

### Timeline Suggestion

| Phase | Target Date | Deliverable |
|-------|------------|-------------|
| Literature survey complete | Week 1 | Annotated bibliography, gap analysis |
| Architecture formalized | Week 2 | Technical design document with cost model derivations |
| Prototype implementation | Weeks 3–6 | Working system with all 3 speculation modes |
| Experimental evaluation | Weeks 7–9 | All experiments run, figures produced |
| Paper draft v1 | Week 10 | Full 10-page draft |
| Internal review & revision | Weeks 11–12 | Revised draft addressing self-identified weaknesses |
| Final submission prep | Week 13 | Camera-ready submission + AD appendix |

Begin with the literature survey. Produce an annotated bibliography and a clear novelty gap analysis before moving to implementation. Show progress at each phase — do not disappear for weeks and deliver a monolithic draft.
