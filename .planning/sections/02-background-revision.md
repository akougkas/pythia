# §2 Background & Motivation — Revision Plan

**Status**: Draft-1 | **Words**: 1,243 / 1,125 budget (+118 over) | **Priority**: High

## PLACEHOLDERs (3)
- [ ] §2.4 profiling methodology (line 63) — describe how Clio Coder was instrumented, N requests, M days
- [ ] §2.4 dispatch latency breakdown figure/table (lines 65-71) — the quantitative anchor for the entire paper's motivation
- [ ] §2.4 dispatch predictability analysis (line 73) — conditional entropy of dispatch plans given intent class

## Missing Citations
None explicit, but §2.3 could benefit from:
- [ ] A Clio/IOWarp citation or project reference (currently described but not cited)
- [ ] Consider citing the MCP specification if published

## Revision Tasks
1. **§2.4 is the critical gap.** The profiling data and predictability analysis are the empirical foundation for the entire paper. Without these, reviewers will question whether dispatch is actually a bottleneck. This blocks nearly everything.
2. **Trim §2.2** — at ~300 words covering LLM speculative decoding, it's thorough but could lose 50-75 words. The SpecInfer/Medusa/EAGLE/Online SD catalog is comprehensive for a survey but SC reviewers need only the key insight. Consider cutting one or two system descriptions.
3. **Trim §2.3** — the AutoGen/MetaGPT/ChatDev/CrewAI/LangGraph/Swarm catalog similarly over-enumerates. 2-3 representative systems + the gap observation suffices.
4. **Table 1 (§2.5)** — excellent. Keep as-is. This table is the argumentative linchpin.
5. **Tighten §2.1** — solid but the "four generations" narrative could compress. SC audience already knows branch prediction evolution. Focus on the cost model equation and Spectre parallel.

## Prose Quality
- §2.1 and §2.2 are well-written.
- §2.3 reads slightly as a literature dump — restructure around the "none speculate" argument.
- §2.5 closing paragraph is strong and quotable.

## Word Budget Strategy
Trim §2.1-§2.3 by ~100 words total to bring section under budget while making room for §2.4 data.
