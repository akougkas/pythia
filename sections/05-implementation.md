# 5. Implementation

## 5.1 Prototype

We implement Speculative Dispatch within Clio Coder, the multi-agent orchestration component of the IOWarp platform.
IOWarp is an open-source scientific data management platform that deploys autonomous AI agents across heterogeneous computing infrastructure — from GPU HBM to cloud object stores — to enable natural-language interaction with scientific datasets and HPC workflows.
Clio Coder is the subsystem responsible for orchestrating coding and analysis agents: it decomposes user requests into tasks, selects appropriate agents, manages context across a 16+ Model Context Protocol (MCP) server ecosystem, and dispatches work across local workstations, cloud instances, and HPC cluster nodes using multiple AI providers.

[PLACEHOLDER: Describe the current (non-speculative) Clio Coder dispatch pipeline — how a request flows from user input through intent parsing, planning, agent selection, context assembly, and execution today. This establishes the baseline that speculation improves upon.]

The prototype adds four components to the existing Clio Coder architecture:

<!-- **Intent Detector.** [ORIGINAL PLACEHOLDER: Describe the intent classification model — is it a fine-tuned classifier, a prompted LLM, a rule-based system? Input: natural-language request + session context. Output: structured intent (task type, complexity estimate, domain tags, decomposability score). Latency target: sub-second, must be faster than the Solver by an order of magnitude.] -->

**Intent Detector.**
The intent classification is defined by an abstract `IntentDetector` interface that accepts a raw user request with optional session context and outputs a structured `Intent` object comprising task type, complexity estimate, domain tags, decomposability score, and constraints (§3.1). This interface serves as an extensibility point for alternative implementations such as LLM-based detectors. Currently, we implemented it via a rule-based approach to remain lightweight and incur negligible latency. We use a `RuleBasedIntentDetector` to classify task type and domain tags via keyword vocabulary lookup, extract constraints such as model preference or budget limits via regex, and estimate complexity as a weighted sum of five normalized signals (action verb count, technical density, sentence count, sequential markers, and request length) with heuristic weights tuned on the workloads described in §6. For decomposability, a `SpacyIntentDetector` uses dependency parsing to identify how many distinct actions a request contains. For example, it recognizes that "analyze and visualize" describes two separable tasks, while "build X to convert Y" implies a sequential dependency. This captures subtask structure that shallow keyword matching cannot detect. When spaCy fails on domain-specific imperative sentences, the detector falls back to a regex-based score, returning the maximum of the two signals.


**Speculative Dispatcher.** [PLACEHOLDER: Describe the draft dispatch model. This could be: (a) a lookup table of recent (intent → dispatch plan) mappings indexed by intent class, (b) a small neural network trained on the user's dispatch history, or (c) a prompted small LLM (e.g., a local model via Ollama) that predicts dispatch plans. Include the confidence scoring mechanism that gates Mode 2 and Mode 3 activation. The Speculative Dispatcher must produce predictions faster than the Solver — its entire value proposition depends on this latency gap.]

**Reconciliation Engine.** [PLACEHOLDER: Describe the COMMIT/PARTIAL COMMIT/FLUSH logic. How does partial commit work in practice within Clio Coder — when an agent was speculatively started with an incorrect prompt, can its MCP connections and loaded context be reused with a new prompt (cheap redirect), or must the agent be fully re-initialized (expensive redirect)? What state is salvageable?]

**Learner.** [PLACEHOLDER: Describe the RL implementation. Framework (e.g., stable-baselines3, custom lightweight implementation). Policy network architecture. Training: online updates after each dispatch event or batch updates every K events? Dispatch fingerprint: sliding window size, encoding method (recurrent network? attention over recent history?). Storage: where does the learned model persist between sessions?]

The components communicate through structured data contracts:
- `Intent`: `{task_type, complexity, domain_tags, decomposability, constraints}`
- `DispatchPlan`: `{agents[], resources[], prompts[], execution_order, budget}`
- `SpeculationResult`: `{draft_plan, pre_executed_work, confidence, mode}`
- `ReconciliationOutcome`: `{verdict: COMMIT|PARTIAL|FLUSH, salvage_ratio, redirect_list}`
- `DispatchOutcome`: `{intent, solver_plan, speculation_result, reconciliation, execution_metrics}`

[PLACEHOLDER: Implementation language, key libraries, lines of code, development effort. Clio is likely Python/TypeScript — confirm.]

## 5.2 Deployment

The prototype operates across the IOWarp heterogeneous fleet:

[PLACEHOLDER: Describe the actual infrastructure:
- Local workstations: specs (CPU, GPU, RAM) — likely the homelab nodes or lab machines
- Cloud instances: provider, instance types, regions
- HPC cluster nodes: which cluster, node specs, interconnect (InfiniBand? Ethernet?)
- AI providers integrated via MCP: Anthropic (Claude), OpenAI (GPT-4), local models (Ollama/LM Studio on GPU nodes)
- Rate limits and token budgets configured per provider — these become fleet capability vector dimensions]

Provider constraints are encoded as fleet member capability vectors (Section 3.5) and loaded from a YAML configuration at startup, consistent with IOWarp's declarative infrastructure model.
The Dispatch Solver reads fleet state in real time via health check endpoints exposed by each Clio component, ensuring resource availability data is current within [PLACEHOLDER: X] seconds.

The system supports 14+ scientific data formats (HDF5, NetCDF, FITS, Zarr, ROOT, among others) through IOWarp's ingestion and exploration engines, which agents access via MCP servers.
This data-format awareness enables the Intent Detector to incorporate domain-specific signals — a request involving HDF5 datasets triggers different dispatch patterns than one involving source code analysis — improving speculation accuracy for scientific workflows.
