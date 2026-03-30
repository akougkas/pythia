# Baseline Comparison Report

**Date**: 2026-03-30 07:00
**Baselines**: No Speculation, Static Heuristic, Spec. w/o Learning, Pythia, Oracle

## Summary Table

| Metric | No Speculation | Static Heuristic | Spec. w/o Learning | Pythia | Oracle |
|--------|--------|--------|--------|--------|--------|
| Solver Latency (ms) | 41717 | 0 | 38292 | 37292 | 40341 |
| Speculator Latency (ms) | 0.0 | 0.0 | 21781.3 | 23669.5 | 63596.4 |
| Hit Rate | 0% | 0% | 80% | 80% | 100% |
| Net Benefit | 0.0 | 0.0 | 2.5 | 1.7 | 5.0 |
| Wasted Compute (W) | 0.000 | 0.000 | 0.250 | 0.000 | 0.000 |
| Convergence (N_conv) | 5 | 5 | 3 | 5 | 3 |
| Total Tokens | 20,404 | 22,512 | 18,172 | 17,569 | 18,331 |
| Total Cost (E) | 375.0000 | 350.0000 | 360.0000 | 0.0000 | 342.5000 |
| Mean Salvage (σ) | 0.00 | 0.00 | 0.64 | 0.80 | 1.00 |
| Pipeline Time (s) | 317 | 319 | 273 | 395 | 272 |

## Verdict Distribution

- **No Speculation**: {'NONE': 5}
- **Static Heuristic**: {'NONE': 5}
- **Spec. w/o Learning**: {'PARTIAL': 3, 'FLUSH': 1, 'COMMIT': 1}
- **Pythia**: {'PARTIAL': 4, 'FLUSH': 1}
- **Oracle**: {'COMMIT': 5}

## Key Findings

- Pythia reduces dispatch latency from 41717ms (NS) — speculation hides solver latency
- Hit rate: 80% — 80% of predictions are usable
- Net benefit: 1.7 (system is profitable)
- Wasted compute: 0.0%
- Static Heuristic solver time: 0ms (fast but no LLM reasoning)
- Learning adds 0 percentage points to hit rate