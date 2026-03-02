# Pythia Implementation

Source code for the Pythia speculative dispatch framework. Co-developed with the paper in `sections/`.

**Development rules**: See `/CLAUDE.md`. TDD from paper claims. Every module traces to a paper section.

## Structure (to be built)

```
src/
├── pythia/              # Core library
│   ├── contracts.py     # Data contracts: Intent, DispatchPlan, SpeculationResult, etc. (§3.1, §5.1)
│   ├── intent.py        # Intent Detector (§3.1, §5.1)
│   ├── solver.py        # Dispatch Solver — target (§3.5, §5.1)
│   ├── speculator.py    # Speculative Dispatcher — draft (§3.2, §5.1)
│   ├── reconciler.py    # Reconciliation Engine: COMMIT/PARTIAL/FLUSH (§3.3, §5.1)
│   ├── learner.py       # RL Learner: contextual bandit + fingerprint (§4, §5.1)
│   ├── cost_model.py    # Cost model: break-even thresholds (§3.4)
│   └── orchestrator.py  # End-to-end pipeline (§3.1)
├── baselines/           # Comparison systems (§6.1)
│   ├── no_speculation.py
│   ├── static_heuristic.py
│   ├── swol.py          # Speculation without Learning
│   └── oracle.py
├── evaluation/          # Experiment harness (§6)
│   ├── workloads/       # HPC-CG, SDP, RWA, DMB generators
│   ├── metrics.py       # L, H, W, Q, N_conv, E, S
│   └── runner.py        # Experiment orchestration
└── tests/               # TDD test suite
    ├── test_cost_model.py
    ├── test_reconciler.py
    ├── test_speculator.py
    ├── test_learner.py
    └── ...
```

Paper section → code module traceability is enforced. See `CLAUDE.md` for the full co-development doctrine.
