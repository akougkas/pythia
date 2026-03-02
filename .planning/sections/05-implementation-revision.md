# §5 Implementation — Revision Plan

**Status**: Draft-1 | **Words**: 647 / 600 budget (+47 over) | **Priority**: **CRITICAL**

## PLACEHOLDERs (8) — Most of any section
- [ ] Clio Coder non-speculative dispatch pipeline description (line 9) — establishes the baseline
- [ ] Intent Detector implementation details (line 13) — classifier type, latency
- [ ] Speculative Dispatcher implementation (line 15) — lookup table vs. neural network vs. small LLM
- [ ] Reconciliation Engine implementation (line 17) — COMMIT/PARTIAL/FLUSH mechanics in practice
- [ ] Learner RL implementation (line 19) — framework, architecture, training regime
- [ ] Implementation language, libraries, LOC (line 28)
- [ ] Deployment infrastructure description (lines 34-39) — actual hardware specs
- [ ] Fleet state polling interval (line 42)

## Missing Citations
None — but the section would benefit from citing IOWarp/Clio if a project reference exists.

## Revision Tasks
1. **This section is almost entirely PLACEHOLDERs.** The framing prose exists but the substance does not. Every PLACEHOLDER requires implementation decisions that affect the rest of the paper.
2. **Priority decision**: Is the prototype built? If yes, fill PLACEHOLDERs from actual implementation. If not, this section must be written to reflect the planned implementation with enough specificity to be credible.
3. **Data contracts** (lines 22-26) are well-specified and complete. These should remain.
4. **Deployment section** needs actual infrastructure specs. If using the homelab cluster + cloud, specify node counts, GPU types, network topology, AI providers.
5. **Trim if needed** after PLACEHOLDERs are filled — current word count includes PLACEHOLDER text that won't remain. Actual section may end up under budget.

## Prose Quality
- Framing is solid: the IOWarp/Clio Coder context is well-established.
- Data contract specification is a strength — reviewers appreciate precise interface definitions.
- The section reads as a blueprint, not a report. Needs implementation reality.

## Blocking Dependencies
- Implementation decisions block this section
- This section blocks §6 (evaluation needs to know what was implemented)
- This section blocks §8 conclusion's contribution 4 claim
