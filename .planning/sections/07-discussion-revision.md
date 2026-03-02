# §7 Discussion — Revision Plan

**Status**: Draft-1 | **Words**: 558 / 450 budget (+108 over) | **Priority**: Low

## PLACEHOLDERs (3)
- [ ] N1 interactions for Mode 2 activation (line 7) — fill from §6.3 results
- [ ] N2 interactions for Mode 3 activation (line 7) — fill from §6.3 results
- [ ] Solver implementation description (line 18)

## Missing Citations (1)
- [ ] `[CITE:kocher2019]` (line 25) — should match `kocher2019spectre` used in §2.1. Verify bib key consistency.

## Revision Tasks
1. **Trim ~110 words** to hit budget. Candidates:
   - §7.1 "Dispatch solver fidelity" paragraph (lines 18-21): arguably belongs in §5 or §3.5, not Discussion. Could cut entirely and fold the tradeoff into §3.4 cost model or a §5 footnote. Saves ~50 words.
   - §7.3 Future Directions: each direction is ~50 words. Could compress each by 15-20 words without losing content.
2. **§7.2 Security Implications** — strongest part of the section. The three mitigation strategies (speculative isolation, deferred context binding, speculative access auditing) are concrete and well-named. Keep as-is.
3. **§7.3 Federated learning** — good future work item. Consider adding a sentence about privacy guarantees needed (differential privacy, secure aggregation) to show awareness of the challenges.

## Prose Quality
- §7.1 limitations are honest and well-framed — doesn't oversell.
- §7.2 Spectre analogy is the paper's most distinctive discussion point. This will catch SC reviewers' attention (positive).
- §7.3 is standard "future work" — adequate but not inspiring. Consider reframing as "implications for HPC systems" to resonate with SC audience.
