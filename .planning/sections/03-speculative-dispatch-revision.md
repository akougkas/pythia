# §3 Speculative Dispatch — Revision Plan

**Status**: Draft-1 | **Words**: 1,597 / 1,500 budget (+97 over) | **Priority**: Medium

## PLACEHOLDERs (0)
None — this section is fully written with formal content. Well done.

## Missing Citations
- [ ] `[CITE:feitelson2004]` (line 173) — needs proper bib key. Likely: Feitelson, Rudolph, Schwiegelshohn "Theory and Practice of Parallel Job Scheduling" or Feitelson's scheduling surveys.

## Figure Placeholders (2)
- [ ] Figure 1: Five-layer architecture diagram (line 33-36)
- [ ] Figure 2: Three speculation modes diagram (line 92-96)
- These are descriptive placeholders (the text says what to draw), not data-dependent. Can be created any time.

## Revision Tasks
1. **Trim ~100 words** to hit budget. Candidates:
   - §3.1 component descriptions are thorough but could tighten (each is ~50 words; reduce to ~35)
   - §3.3 partial commit explanation is slightly verbose
2. **Cost model notation consistency** — verify $C_{prep}^{waste}$, $C_{init}$, $C_{draft}$, $C_{flush}^{M3}$ notation is used consistently when referenced in §6
3. **§3.5 Resource-Aware Dispatch** — the capability vector formulation is clean. Add a sentence connecting to IOWarp's YAML-based fleet configuration (§5) for concreteness.
4. **Create Figures 1 and 2** — these are the paper's most important visual aids. Architecture diagram should be TikZ or similar for IEEE style.

## Prose Quality
- Strongest section in the paper. Formal but readable.
- Mode descriptions with analogies are excellent for SC audience.
- Cost model derivations are clean and well-motivated.
- §3.3 reconciliation protocol is precise — the salvage ratio formalization is a nice touch.
