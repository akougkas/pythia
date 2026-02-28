# 7. Discussion

## 7.1 Limitations

**Cold start.** The Learner requires interaction history to move beyond Mode 1 speculation.
For new users or novel task types, the system operates conservatively — context preparation only — until sufficient dispatch telemetry accumulates.
Our evaluation (Section 6) shows that Mode 2 activation requires approximately [PLACEHOLDER: N1] interactions for common intent classes, with Mode 3 requiring [PLACEHOLDER: N2].
In multi-tenant deployments, Bayesian priors from aggregate user behavior could reduce this cold-start period, but we have not evaluated this approach.

**Adversarial and unpredictable workloads.** Speculative Dispatch assumes that dispatch decisions exhibit temporal locality — that future requests resemble past requests for a given user.
This assumption holds for routine workflows (code review, data processing pipelines, iterative development) but breaks down for exploratory or one-off tasks.
For workloads with high dispatch entropy, the system correctly regresses to Mode 1 via the drift detection mechanism, but the latency benefit during such periods is limited to context preparation.

**Single-user evaluation.** Our prototype and evaluation focus on single-user scenarios.
Multi-user deployments introduce resource contention for speculative pre-execution — multiple users' speculative dispatches may compete for the same agents or infrastructure.
Extending the framework to multi-tenant environments with fair-share speculative scheduling is future work.

**Dispatch solver fidelity.** The current Solver uses [PLACEHOLDER: description of solver implementation].
A more sophisticated solver might produce substantially different plans from the Speculative Dispatcher's predictions, reducing hit rates.
Conversely, a simpler solver reduces the latency gap that speculation aims to hide.
The cost model's break-even analysis (Section 3.4) accounts for this tradeoff explicitly.

## 7.2 Security Implications

Speculative Dispatch raises security considerations directly analogous to Spectre-class vulnerabilities in CPU speculative execution [CITE:kocher2019].
When the Speculative Dispatcher pre-fetches context or pre-warms agents, it may access resources based on a *predicted* dispatch plan that differs from the *authorized* optimal plan.
In multi-tenant deployments, this creates a potential information channel: speculative context assembly for User A's predicted task might inadvertently load context that should be accessible only under the Solver's verified plan for User B.

We identify three mitigation strategies but defer their full analysis to future work:
(1) *speculative isolation* — confining speculative pre-execution to resources already authorized for the requesting user;
(2) *deferred context binding* — assembling context skeletons speculatively but deferring content retrieval until the Solver's plan is verified;
(3) *speculative access auditing* — logging all speculative resource accesses and flagging cases where the Solver's plan would not have authorized the access.

The Spectre parallel is deliberate: both the HPC community's and the security community's lessons about speculative side channels apply directly.

## 7.3 Future Directions

**HPC scheduler integration.** The Dispatch Solver's constraint formulation maps naturally to Slurm's resource management model.
Integrating speculative dispatch with HPC job schedulers would enable agent orchestration across managed cluster resources, with Slurm handling resource allocation and the Learner optimizing dispatch predictions.

**Federated learning.** In multi-tenant deployments, dispatch patterns from one user can inform speculation for similar users — a researcher in computational chemistry likely has dispatch patterns similar to other computational chemistry researchers.
Federated learning across users (with privacy guarantees) could dramatically reduce cold-start times.

**Transfer learning across projects.** When a user transitions to a new project, the Learner's dispatch fingerprint becomes partially stale.
Transfer learning techniques could preserve generalizable patterns (e.g., "this user prefers thorough code review before commits") while rapidly adapting to project-specific dispatch requirements.
