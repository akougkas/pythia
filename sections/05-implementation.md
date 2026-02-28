# 5. Implementation

## 5.1 Prototype

We implement Speculative Dispatch as an extension to Cleo Coder, a distributed multi-agent coding system that orchestrates AI agents across heterogeneous infrastructure.

[PLACEHOLDER: Describe the Cleo Coder base system — what it does, how it orchestrates agents today (the non-speculative baseline), key components]

The prototype adds four components to the existing system:

**Intent Detector.** [PLACEHOLDER: Describe the intent classification model — is it a fine-tuned classifier, a prompted LLM, a rule-based system? Input format, output schema (task type, complexity estimate, domain tags, decomposability score). Latency target: < X ms.]

**Speculative Dispatcher.** [PLACEHOLDER: Describe the draft dispatch model. Options: (a) a lookup table of recent (intent → plan) mappings, (b) a small neural network trained on dispatch history, (c) a prompted small LLM that predicts dispatch plans. Include the confidence scoring mechanism that gates Mode 2/3 activation.]

**Reconciliation Engine.** [PLACEHOLDER: Describe the implementation of COMMIT/PARTIAL COMMIT/FLUSH logic. How does partial commit work in practice — what state can be salvaged from a speculatively started agent? How are redirects issued?]

**Learner.** [PLACEHOLDER: Describe the RL implementation. Framework (e.g., stable-baselines3, custom). Policy network architecture. Training loop — online updates after each dispatch event? Batch updates? Dispatch fingerprint implementation — sliding window size, encoding method.]

The components communicate through structured data contracts:
- `Intent`: `{task_type, complexity, domain_tags, decomposability, constraints}`
- `DispatchPlan`: `{agents[], resources[], prompts[], execution_order, budget}`
- `SpeculationResult`: `{draft_plan, pre_executed_work, confidence, mode}`
- `ReconciliationOutcome`: `{verdict: COMMIT|PARTIAL|FLUSH, salvage_ratio, redirect_list}`
- `DispatchOutcome`: `{intent, solver_plan, speculation_result, reconciliation, execution_metrics}`

[PLACEHOLDER: Implementation language, key libraries, lines of code, development effort]

## 5.2 Deployment

The prototype operates across a heterogeneous fleet:

[PLACEHOLDER: Describe the actual infrastructure used for evaluation:
- Local workstations: specs (CPU, GPU, RAM)
- Cloud instances: provider, instance types
- HPC cluster nodes: specs, interconnect
- AI providers: which APIs (Anthropic, OpenAI, local models via Ollama/LM Studio)
- Rate limits and token budgets configured per provider]

Provider constraints are encoded as fleet member capability vectors (Section 3.5) and loaded from a configuration file at startup.
The Dispatch Solver reads fleet state in real time via health check endpoints, ensuring resource availability data is current within [PLACEHOLDER: X seconds].
