# §1 Introduction — Revision Plan

**Status**: Draft-1 revised | **Words**: 1,020 / 1,050 budget | **Priority**: Medium

## PLACEHOLDERs (3)
- [ ] `[PLACEHOLDER: X]%` — dispatch overhead as % of end-to-end latency (line 9). Requires §2.4 profiling data.
- [ ] `[PLACEHOLDER: Z]%` — coverage of top-K intent classes (line 17). Requires dispatch predictability analysis.
- [ ] `[PLACEHOLDER: X/Y/N]` — contribution 4 result numbers (line 48). Fill after §6 experiments complete.

## Missing Citations
None — all citations present and use proper bracket keys.

## Revision Tasks
1. **Fill PLACEHOLDERs** — blocked on experimental data. These are the three most visible numbers in the paper; they must be precise and defensible.
2. **Sharpen the problem statement** — the second paragraph is dense. Consider splitting the long sentence listing orchestrator tasks into a more scannable structure (but avoid bullet points in intro).
3. **Contribution 2 wording** — "contextual bandit" appears here and §4. Verify terminology is consistent; SC reviewers may not know contextual bandits — briefly gloss or save the term for §4 and keep the intro at "reinforcement learning."
4. **Cross-check contribution numbers** — ensure the 4 contributions match §8 conclusion's restatement. Currently aligned.

## Prose Quality
- Opening paragraph is strong.
- "For short-duration tasks" sentence (added in this pass) tightens the motivation well.
- The mode descriptions (Mode 1/2/3) paragraph is clear but long — consider whether this detail belongs here vs. being a forward reference to §3. Currently acceptable for an SC audience that values technical density.
