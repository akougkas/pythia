# Speculative Dispatch for Multi-Agent Orchestration Systems

## What This Is

A research paper targeting SC26 (IEEE proceedings, 10-page two-column). Introduces speculative dispatch — adapting the draft-target speculation paradigm from CPU speculative execution and LLM speculative decoding to the orchestration layer of multi-agent AI systems. Part of the IOWarp project (iowarp.ai). Evaluated on a working prototype built on Clio Coder, the multi-agent orchestration component of the Clio monorepo, with HPC-adjacent workloads.

## Core Argument

The draft-target speculation paradigm — proven in CPU branch prediction and LLM speculative decoding — generalizes to multi-agent orchestration, enabling a speculative dispatcher to overlap planning with pre-execution and a reinforcement learning loop to improve dispatch accuracy over time, reducing end-to-end orchestration latency without sacrificing dispatch quality.

## Requirements

### Must Have

- [ ] Formal speculative dispatch abstraction with three-mode hierarchy (context prep, agent pre-dispatch, execution with verification)
- [ ] Commit/partial-commit/flush reconciliation protocol
- [ ] Speculation cost model with break-even accuracy threshold derivation
- [ ] RL formulation for the Learner (state/action/reward)
- [ ] Resource-aware dispatch solver treating heterogeneous infrastructure constraints as first-class parameters
- [ ] Working prototype on Clio Coder (IOWarp/Clio) evaluated on realistic workloads
- [ ] End-to-end dispatch latency measurements across all three modes
- [ ] Speculation hit rate and wasted compute ratio analysis
- [ ] Learner convergence curves
- [ ] Four baselines: no speculation, static heuristic, speculation without learning, oracle
- [ ] Ablation studies: mode combinations, confidence thresholds, history window sizes
- [ ] Double-anonymous compliance
- [ ] Mandatory AD appendix
- [ ] IEEE two-column format, ≤10 pages (excluding bib + appendices)

### Should Have

- [ ] Scalability analysis with fleet size and agent count
- [ ] Cost efficiency analysis (tokens, compute-hours, budget)
- [ ] Multi-user vs. single-user speculation comparison
- [ ] Homogeneous vs. heterogeneous infrastructure comparison
- [ ] Explicit Spectre analogy for multi-tenant security discussion
- [ ] Cold-start strategy analysis (Bayesian priors, transfer learning)
- [ ] Concept drift / non-stationary user behavior discussion

### Out of Scope

- Production-grade multi-tenant deployment — single-user prototype sufficient for SC26, multi-tenant is future work
- Full security threat model for speculative context leakage — discuss the Spectre analogy but defer formal analysis
- Federated learning across users — identified as future direction, not implemented
- Integration with Slurm/PBS job schedulers — discussed as future work, prototype uses custom scheduling
- General-purpose agent framework comparison — not benchmarking CrewAI vs AutoGen; they're related work context only

## Target Audience

SC26 reviewers and attendees: HPC systems researchers with deep expertise in scheduling, resource management, and distributed systems. They know CPU speculative execution intimately and understand cost/benefit tradeoffs of speculation. They may not know LLM speculative decoding details — explain clearly. They care about: rigorous evaluation, scalability, reproducibility, and real-system relevance.

Secondary audience: AI systems researchers interested in multi-agent orchestration performance. Citation audience: anyone building orchestration layers for multi-agent systems or applying HPC scheduling concepts to AI workloads.

## Constraints

- **Deadline**: April 8, 2026 (paper), April 24, 2026 (AD appendix). Hard, no extensions.
- **Length**: 10 pages, two-column, US Letter, IEEE proceedings template. Bib and appendices excluded.
- **Format**: Double-anonymous. Self-cite in third person. IEEE proceedings LaTeX template.
- **Review**: SC26 primary area "System Software & Cloud Computing"; secondary "Data Analytics, Visualization, & Storage"
- **AI Policy**: SC26 permits AI tools with disclosure in acknowledgments + citation
- **Data**: Prototype built on Clio Coder (IOWarp/Clio monorepo). HPC-adjacent workloads (code gen, data pipelines, research workflows, micro-benchmarks).

## Team

| Role | Person | Primary Responsibility |
|------|--------|-----------------------|
| PI | Prof. Kougkas | Architecture, narrative, final review |
| Senior PhD | Jie | Formal methods (§3–§4), implementation architecture (§5), profiling (§2.4) |
| PhD (agents) | Shazzadul | Learner RL (§4), agent integration (§5), evaluation pipeline (§6) |

See `SPRINT.md` for detailed assignments and timeline.

## Co-Development Approach

This repo co-hosts the paper and its implementation. They are developed together:
- Paper claims drive test specifications → tests drive implementation → experiments fill PLACEHOLDERs → data updates the paper
- Source code lives in `src/`, paper in `sections/` + `paper/`
- Test-driven development: every code module traces to a paper section
- If experimental results diverge from paper claims, reposition honestly (see SPRINT.md risk register)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Core contribution = paradigm transfer (not results alone) | SC audience values new abstractions; results support the abstraction's validity | ✓ Confirmed |
| 8-section structure (split Design from Learning, add Discussion) | The three-mode hierarchy + RL learner each deserve dedicated treatment; Discussion needed for limitations/security | ✓ Confirmed |
| IEEE CS venue template adapted | SC26 uses IEEE proceedings format; standard IEEE CS structure expanded for paper's needs | ✓ Confirmed |
| Citation style: IEEE numeric | Required by venue | ✓ Good |
| Paper + code co-development in single repo | Sprint timeline demands tight coupling; paper claims must be testable | ✓ Confirmed |
| TDD from paper claims | Forces precision in paper writing; ensures implementation matches claims | ✓ Confirmed |
| WTF-P scaffold mode with all gates on | Students learn by doing; Claude mentors, doesn't write autonomously | ✓ Confirmed |

---
*Last updated: 2026-03-02 — team handoff preparation*
