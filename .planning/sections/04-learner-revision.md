# §4 Learner-Augmented Speculation — Revision Plan

**Status**: Draft-1 | **Words**: 1,058 / 900 budget (+158 over) | **Priority**: Medium

## PLACEHOLDERs (0)
None — section is fully written.

## Missing Citations (2)
- [ ] `[CITE:agarwal2014]` (line 69) — needs proper bib key. Likely Agarwal et al. "Taming the Monster: A Fast and Simple Algorithm for Contextual Bandits" (ICML 2014).
- [ ] `[CITE:seznec2011]` (line 88) — needs proper bib key. Should match `seznec2011tage` used in §2.1; verify consistency.

## Revision Tasks
1. **Trim ~160 words** — this section is the most over-budget. Candidates:
   - §4.2 Progressive Activation: the three phases (cold start, early learning, mature) are clear but slightly redundant with the CPU predictor evolution analogy. The analogy adds color but costs ~40 words per phase that could be cut.
   - §4.3 convergence bound explanation: the regret formulation is good but the "we expect $R_T$ to grow sublinearly" paragraph could tighten to 2 sentences.
   - §4.1 dispatch fingerprint paragraph: well-motivated but the researcher example duplicates the §1 introduction's example. Cut the example here, keep the technical description.
2. **Convergence claim rigor** — "converges to the Bayes-optimal policy at a rate bounded by..." is a strong claim. Either prove it or soften to "is bounded by ... under standard assumptions." SC reviewers will check this.
3. **Non-stationarity handling** — §4.3's drift detection is well-described. Ensure the exponentially weighted moving average and mode regression thresholds are referenced in §6 ablation (they are, via threshold sensitivity).

## Prose Quality
- §4.1 RL formulation is clear and well-structured.
- The reward signal definition is elegant — directly encodes the reconciliation economics.
- §4.2 progressive activation is the section's main contribution to readability — the CPU predictor evolution parallel works well.
- §4.3 non-stationarity handling anticipates a key reviewer concern.
