# Pythia — Draft-1 Revision Summary

**Date**: 2026-03-02 | **Deadline**: April 8, 2026 (37 days)

## Word Budget Status

| § | Section | Budget | Actual | Delta | Status |
|---|---------|--------|--------|-------|--------|
| 1 | Introduction | 1,050 | 1,020 | -30 | Revised this session |
| 2 | Background | 1,125 | 1,243 | +118 | Needs trimming |
| 3 | Speculative Dispatch | 1,500 | 1,597 | +97 | Needs trimming |
| 4 | Learner | 900 | 1,058 | +158 | Needs trimming |
| 5 | Implementation | 600 | 647 | +47 | Mostly PLACEHOLDERs |
| 6 | Evaluation | 1,500 | 1,827 | +327 | Revised this session; will compress with data |
| 7 | Discussion | 450 | 558 | +108 | Needs trimming |
| 8 | Conclusion | 375 | 361 | -14 | Near target |
| — | **Total** | **7,500** | **8,311** | **+811** | **~10% over; trim in revision** |

## PLACEHOLDER Census

| § | Count | Blocking? |
|---|-------|-----------|
| 1 | 3 | Blocked on §6 results |
| 2 | 3 | Blocked on profiling data |
| 3 | 0 | — |
| 4 | 0 | — |
| 5 | 8 | Blocked on implementation decisions |
| 6 | 30+ | Blocked on experiments |
| 7 | 3 | Blocked on §6 results |
| 8 | 4 | Blocked on §6 results |
| — | **~51** | |

## Missing/Broken Citations

| Key | Section | Issue |
|-----|---------|-------|
| `[CITE:feitelson2004]` | §3 | Needs proper bib entry |
| `[CITE:agarwal2014]` | §4 | Needs proper bib entry |
| `[CITE:seznec2011]` | §4 | May duplicate `seznec2011tage` from §2 — verify |
| `[CITE:kocher2019]` | §7 | May duplicate `kocher2019spectre` from §2 — verify |

## Figures & Tables Not Yet Created

| # | Type | Section | Data-dependent? |
|---|------|---------|-----------------|
| 1 | Figure | §3.1 | No — architecture diagram |
| 2 | Figure | §3.2 | No — mode hierarchy diagram |
| 3 | Table | §2.5 | No — already written in markdown |
| 4 | Figure | §6.2 | Yes — latency results |
| 5 | Figure | §6.3 | Yes — learning curves |
| 6 | Figure | §6.4 | Yes — Pareto frontier |
| 7 | Table | §6.5 | Yes — ablation matrix |
| 8 | Figure | §6.6 | Yes — scalability |

## Critical Path

```
Implementation decisions (§5)
    → Build prototype
        → Run experiments
            → Fill §6 PLACEHOLDERs (30+)
                → Fill §1, §7, §8 PLACEHOLDERs (~10)
                    → Final trim to word budget
                        → Create figures
                            → Compile LaTeX
                                → Submit
```

### Parallelizable now (no data dependency):
- [ ] Trim §2, §3, §4, §7 to word budgets
- [ ] Fix 4 broken citation keys
- [ ] Create Figures 1 and 2 (architecture + modes)
- [ ] Convert Table 1 (§2.5) to LaTeX

### Blocked on implementation:
- [ ] Fill §5 PLACEHOLDERs (8)
- [ ] Fill §2.4 profiling data (3)

### Blocked on experiments:
- [ ] Fill §6 PLACEHOLDERs (30+)
- [ ] Fill §1, §7, §8 result PLACEHOLDERs (10)
- [ ] Create Figures 4-8 and Table 7
