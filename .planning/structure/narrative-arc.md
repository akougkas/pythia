# Narrative Arc — Speculative Dispatch

## The Story in One Paragraph

Multi-agent AI systems are becoming essential to scientific computing, but their orchestration layers are naive — every request is a cold-start planning problem. We observe that this bottleneck is structurally identical to problems the HPC community already solved: CPU speculative execution predicts branch outcomes to avoid pipeline stalls; LLM speculative decoding uses cheap draft models to avoid autoregressive bottlenecks. We introduce speculative dispatch, which predicts dispatch plans and begins pre-execution while the full solver computes the optimal plan. A reinforcement learning loop makes the system increasingly accurate over time. The result: orchestration latency that decreases with usage, without sacrificing dispatch quality.

## Three-Act Structure

### Act 1: The Problem (§1–§2)

**Reader state**: "I know scheduling. I know speculation. Show me why agent orchestration needs it."

- **Hook**: Multi-agent systems are entering HPC. The orchestration layer is the new bottleneck.
- **Tension**: Current orchestrators are sequential and cold-start. They waste time re-solving problems they've seen before.
- **Recognition moment**: The SC reader sees the parallel to branch prediction / speculative execution immediately. The LLM speculative decoding parallel adds a second layer — cheap draft, expensive verify.
- **Empirical grounding**: Profiling data showing dispatch is X% of latency. Intent patterns are predictable.

**Transition**: "We adapt these well-understood paradigms to a new domain."

### Act 2: The Solution (§3–§5)

**Reader state**: "This is a clean abstraction. The math checks out."

- **Architecture**: Five layers with clear data contracts. The reader can map each component to something they know.
- **Three modes**: Progressive risk/reward. Mode 1 is cache prefetch (familiar). Mode 2 is branch speculation (familiar). Mode 3 is speculative decoding for agents (novel).
- **Cost model**: The paper's theoretical anchor. Break-even equation. Per-mode thresholds. The reader can reason about when speculation pays off without running experiments.
- **Learner**: RL formulation that makes the system adaptive. Parallels CPU predictor evolution (static → adaptive → neural).
- **Implementation**: Real system, real infrastructure, real constraints.

**Transition**: "Does it work?"

### Act 3: The Evidence (§6–§8)

**Reader state**: "The results support the abstraction."

- **Primary result**: Latency reduction across all modes and workloads.
- **Learning curve**: The system improves. Hit rate climbs. This is the most compelling plot.
- **Cost tradeoff**: Wasted compute is bounded and manageable. Pareto frontier shows the tuning space.
- **Ablations**: Each design choice is justified by data.
- **Honest limitations**: Cold start, adversarial workloads, single-user scope.
- **Future**: Slurm integration, federated learning — connects back to HPC community's roadmap.

**Closing**: This is a new abstraction for a real problem, backed by theory and evidence. The HPC community's scheduling expertise is directly applicable to the next generation of AI system design.

## Reader Experience

| Section | Reader Learns | Reader Feels |
|---------|--------------|--------------|
| §1 Introduction | The problem exists and matters | "This is relevant to my work" |
| §2 Background | The parallel to CPU/LLM speculation is precise | "I already understand the core idea" |
| §3 Speculative Dispatch | How the abstraction works formally | "This is well-designed" |
| §4 Learner | The system improves over time | "That's the differentiator" |
| §5 Implementation | It's a real system on real hardware | "This isn't vapor" |
| §6 Evaluation | Results are strong and rigorous | "The evidence supports the claims" |
| §7 Discussion | Authors are honest about limitations | "They anticipated my objections" |
| §8 Conclusion | Summary + forward look | "This opens a direction" |

## Key Narrative Devices

1. **The triple parallel**: CPU speculation → LLM speculation → Agent speculation. Thread this through the entire paper. Each time a concept is introduced, show the parallel in all three domains.
2. **The learning curve plot**: The single most important figure. Shows the system evolving from conservative to aggressive, mirroring CPU predictor evolution.
3. **The cost model as unifying theory**: Everything connects through the break-even equation. It's the formal backbone that makes this a systems contribution, not just an engineering report.
