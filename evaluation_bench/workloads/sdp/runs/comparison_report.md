# Baseline Comparison Report

**Date**: 2026-03-30 07:00
**Baselines**: No Speculation, Static Heuristic, Spec. w/o Learning, Pythia, Oracle

## Summary Table

| Metric | No Speculation | Static Heuristic | Spec. w/o Learning | Pythia | Oracle |
|--------|--------|--------|--------|--------|--------|
| Solver Latency (ms) | 22686 | 0 | 25996 | 21362 | 23626 |
| Speculator Latency (ms) | 0.0 | 0.0 | 11853.4 | 12226.2 | 53783.7 |
| Hit Rate | 0% | 0% | 100% | 100% | 100% |
| Net Benefit | 0.0 | 0.0 | 4.4 | 4.3 | 5.0 |
| Wasted Compute (W) | 0.000 | 0.000 | 0.100 | 0.000 | 0.000 |
| Convergence (N_conv) | 5 | 5 | 3 | 5 | 3 |
| Total Tokens | 15,566 | 14,610 | 14,283 | 14,176 | 14,084 |
| Total Cost (E) | 300.0000 | 300.0000 | 272.5000 | 0.0000 | 292.5000 |
| Mean Salvage (σ) | 0.00 | 0.00 | 0.91 | 1.00 | 1.00 |
| Pipeline Time (s) | 243 | 236 | 220 | 344 | 213 |

## Verdict Distribution

- **No Speculation**: {'NONE': 5}
- **Static Heuristic**: {'NONE': 5}
- **Spec. w/o Learning**: {'COMMIT': 2, 'PARTIAL': 3}
- **Pythia**: {'PARTIAL': 3, 'COMMIT': 2}
- **Oracle**: {'COMMIT': 5}

## Key Findings

- Pythia reduces dispatch latency from 22686ms (NS) — speculation hides solver latency
- Hit rate: 100% — 100% of predictions are usable
- Net benefit: 4.3 (system is profitable)
- Wasted compute: 0.0%
- Static Heuristic solver time: 0ms (fast but no LLM reasoning)
- Learning adds 0 percentage points to hit rate