# 4. Learner-Augmented Speculation

The Learner transforms Speculative Dispatch from a static prediction system into an adaptive one.
This section formalizes the learning problem, describes the progressive activation strategy, and analyzes convergence behavior.

## 4.1 Reinforcement Learning Formulation

We formulate the speculation policy as a contextual bandit problem, where each dispatch event is an independent decision with immediate reward.

**State space.** The state $s_t$ at time $t$ is a tuple:

$$s_t = (\mathbf{i}_t, \mathbf{f}_t, \mathbf{h}_t)$$

where $\mathbf{i}_t$ is the intent feature vector (task type, complexity estimate, domain tags, decomposability), $\mathbf{f}_t$ is the fleet state vector (resource availability, active agents, queue depths, rate limit headroom), and $\mathbf{h}_t$ is a compressed representation of the user's recent dispatch history (the *dispatch fingerprint*).

**Action space.** The action $a_t$ is the speculative dispatch plan $\hat{P}_t$ — specifically, the set of agents to speculatively activate, the mode to operate in (1, 2, or 3), and the resource allocations to reserve.

**Reward signal.** The reward $r_t$ directly encodes the reconciliation outcome:

$$r_t = \begin{cases}
+L_{saved} & \text{if COMMIT} \\
+\sigma_t \cdot L_{saved} - (1 - \sigma_t) \cdot C_{redirect} & \text{if PARTIAL COMMIT} \\
-C_{flush} & \text{if FLUSH}
\end{cases}$$

where $L_{saved}$ is the dispatch latency avoided by correct speculation, $\sigma_t$ is the salvage ratio, $C_{redirect}$ is the redirection cost, and $C_{flush}$ is the total cost of wasted speculative work.
This reward structure directly penalizes misprediction proportional to wasted resources, creating a natural pressure toward conservative speculation when the model is uncertain and aggressive speculation when confidence is high.

**Policy.** The Learner maintains a parameterized policy $\pi_\theta(a | s)$ that maps states to speculative dispatch plans.
We use a policy gradient approach where the objective is to maximize expected cumulative reward:

$$J(\theta) = \mathbb{E}_{s \sim \mathcal{D}, a \sim \pi_\theta} [r(s, a)]$$

The policy network takes the state tuple as input and outputs: (1) a probability distribution over candidate dispatch plans, (2) a confidence score determining the active speculation mode, and (3) resource allocation parameters.
The confidence score directly maps to the mode selection: if confidence exceeds $\tau_3^*$, activate Mode 3; if it exceeds $\tau_2^*$, activate Mode 2; otherwise, default to Mode 1.

**Dispatch fingerprint.** The history component $\mathbf{h}_t$ is critical.
We maintain a sliding window of the $k$ most recent dispatch events for each user, encoded as (intent class, solver plan, reconciliation outcome) triples.
This captures recurring patterns: a researcher who spends mornings on code review and afternoons on data analysis will exhibit strong temporal regularities in dispatch patterns.
The fingerprint is encoded via a small recurrent network that compresses the history window into a fixed-dimensional vector.

## 4.2 Progressive Activation

The Learner governs a staged activation strategy that mirrors the evolution of CPU branch predictors from static heuristics to adaptive algorithms to neural predictors.

**Cold start (interactions 0–$N_1$).**
The system has no user-specific history.
The Speculative Dispatcher operates exclusively in Mode 1 (context preparation), which requires no prediction accuracy.
During this phase, the Learner is in pure observation mode: it collects (intent, solver plan, outcome) tuples to bootstrap the dispatch fingerprint.
If aggregate dispatch statistics are available from other users (in a multi-tenant deployment), the Learner initializes with Bayesian priors derived from these aggregate patterns — analogous to how static branch predictors use heuristics like "backward branches are usually taken" before adaptive prediction is available.

**Early learning ($N_1$–$N_2$ interactions).**
The Learner has accumulated enough history to identify high-frequency intent classes — the task types that recur most often.
For these intent classes, speculation accuracy typically exceeds $\tau_2^*$ first, enabling Mode 2 activation.
The system begins speculatively pre-dispatching agents for predictable requests while remaining conservative for novel or rare intents.
This mirrors two-level adaptive branch prediction, where per-branch history tables enable pattern-specific prediction.

**Mature operation ($> N_2$ interactions).**
The dispatch fingerprint is well-populated.
For high-confidence intent classes (the top $k$ by frequency and prediction accuracy), the Learner activates Mode 3 — speculative execution with verification.
The system effectively "knows" the dispatch plan before the Solver finishes, and draft agents begin producing output that is verified against the optimal plan.
This corresponds to TAGE-class neural branch predictors that achieve 95%+ accuracy on regular patterns.

The activation thresholds $N_1$ and $N_2$ are not fixed hyperparameters but emergent properties of the learning dynamics.
They depend on the predictability of the user's workload: a user with highly regular patterns (e.g., a daily pipeline of code-review → test → deploy) will reach Mode 3 activation faster than a user with diverse, unpredictable requests.

## 4.3 Convergence and Adaptation

**Convergence.** For the contextual bandit formulation with a finite intent class space, the Learner's speculation accuracy converges to the Bayes-optimal policy at a rate bounded by $O(\sqrt{T \log |\mathcal{A}| / T})$, where $T$ is the number of interactions and $|\mathcal{A}|$ is the action space cardinality [CITE:agarwal2014].
In practice, convergence is faster because the effective action space is small — most users invoke a handful of intent patterns repeatedly, and the dispatch plan for a given intent class has low entropy.

We define the *speculation regret* as the cumulative difference between the oracle speculation policy (which always predicts correctly) and the Learner's policy:

$$R_T = \sum_{t=1}^{T} [r^*(s_t) - r(s_t, \pi_\theta(s_t))]$$

The Learner minimizes this regret over time.
We expect $R_T$ to grow sublinearly (formally $R_T = o(T)$), meaning the average per-interaction regret vanishes — the system asymptotically approaches oracle performance for recurring intent patterns.

**Non-stationary behavior.** Users change their patterns over time: new projects, new tools, evolving workflows.
This introduces distribution shift (concept drift) in the intent-to-dispatch mapping.
We handle non-stationarity through two mechanisms:

1. **Windowed history.** The dispatch fingerprint uses a sliding window of size $k$, ensuring that stale patterns decay naturally. Old dispatch patterns that no longer reflect current behavior are gradually evicted.

2. **Drift detection.** We monitor the Learner's recent prediction accuracy using an exponentially weighted moving average. A sustained drop in accuracy below $\tau_2^*$ triggers a *mode regression* — the system falls back from Mode 3 to Mode 2 or from Mode 2 to Mode 1 — and increases the learning rate to accelerate adaptation to the new distribution.

This adaptive mechanism ensures that the system degrades gracefully under distribution shift rather than persisting with a stale model.
The parallel to CPU branch prediction is direct: modern predictors use tagged geometric history lengths (TAGE) that naturally weight recent history more heavily, and misprediction recovery mechanisms flush stale branch history entries [CITE:seznec2011].
Recent hardware research has validated RL-based adaptive strategy selection in a closely related setting: Janus dynamically switches between speculation defense policies per execution phase using a reinforcement learning agent, outperforming any single static policy by 2–5\% [aimoniotis2024janus].
Our Learner's mode regression mechanism is structurally analogous — adapting the speculation strategy to the observed workload phase rather than committing to a fixed policy.
