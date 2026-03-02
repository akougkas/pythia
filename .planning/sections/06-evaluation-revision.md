# §6 Evaluation — Revision Plan

**Status**: Draft-1 revised (this session) | **Words**: 1,827 / 1,500 budget (+327 over) | **Priority**: **CRITICAL**

## PLACEHOLDERs (~30+)
All result numbers are PLACEHOLDERs. The narrative structure is complete but every quantitative claim needs experimental data. Major categories:
- [ ] Workload task counts and generation methodology (§6.1)
- [ ] Judge model for dispatch quality metric (§6.1)
- [ ] Convergence definition parameters (§6.1)
- [ ] Hardware/software environment specification (§6.1)
- [ ] Repeat count and statistical methodology details (§6.1)
- [ ] All latency reduction percentages — Modes 1, 2, 3 per workload (§6.2)
- [ ] Oracle upper bound numbers (§6.2)
- [ ] All hit rate numbers and convergence interaction counts (§6.3)
- [ ] SwoL baseline hit rate ceiling (§6.3)
- [ ] All wasted compute ratios at various thresholds (§6.4)
- [ ] Net token efficiency numbers (§6.4)
- [ ] Break-even validation: observed vs. theoretical thresholds (§6.4)
- [ ] Mode combination ablation percentages (§6.5)
- [ ] Optimal threshold value (§6.5)
- [ ] Optimal history window size (§6.5)
- [ ] Heterogeneity impact on accuracy (§6.5)
- [ ] Solver latency scaling behavior (§6.6)
- [ ] Fleet size convergence multiplier (§6.6)
- [ ] Figures 4, 5, 6, 8 and Table 7

## Missing Citations
None needed — evaluation sections typically don't cite external work.

## Revision Tasks
1. **Run experiments and fill PLACEHOLDERs** — this is the paper's make-or-break section. SC reviewers weight evaluation heavily.
2. **Trim ~300 words** after PLACEHOLDERs are replaced with concise numbers. The narrative prose is intentionally expansive to guide result interpretation; it will compress when actual data replaces speculative descriptions.
3. **Figures and tables** — 4 figures + 1 table specified. These must be publication-quality. Budget ~1.5 columns total for figures.
4. **Statistical rigor** — Wilcoxon signed-rank test is specified. Ensure sufficient repeats (≥30 for parametric claims, ≥10 for non-parametric).
5. **Dispatch quality metric** — the judge model approach needs specification. Consider: (a) automated LLM judge scoring output equivalence 1-5, (b) BLEU/ROUGE-like metrics for code output, or (c) functional equivalence via test suite pass rates.

## Prose Quality
- Section structure is strong: setup → primary result → learning → cost → ablation → scale.
- Each subsection has a clear expected narrative that will survive data insertion.
- Good use of cross-references to §3.4 cost model thresholds.
- Tail latency discussion in §6.2 anticipates reviewer concern about p99.

## Blocking Dependencies
- §5 implementation decisions block experimental setup
- Actual prototype execution blocks all result numbers
- §3.4 cost model thresholds needed for break-even validation in §6.4
