# Pythia

Speculative Dispatch for Autonomous Agent Orchestration in Scientific Computing.

SC26 paper + implementation. Deadline: April 8, 2026.

The oracle at Delphi didn't wait for the question to finish before she started seeing the answer. A cheap prediction running in parallel with an expensive optimization amortizes dispatch latency when alignment is high, and a learning system makes alignment increase over time.

## Quickstart

```bash
curl -fsSL https://raw.githubusercontent.com/akougkas/pythia/main/onboard.sh | bash
```

Checks your tools, clones the repo, verifies project state, launches Claude Code in mentor mode. Already cloned? Just `./onboard.sh`.

See `CLAUDE.md` for project rules and development doctrine.

## Structure

```
├── CLAUDE.md           # Project rules for Claude Code (read this first)
├── sections/           # Paper source (8 markdown files)
├── paper/              # LaTeX compilation (main.tex → pdflatex)
├── src/                # Implementation (TDD, co-developed with paper)
├── references.bib      # Shared bibliography
└── .planning/          # WTF-P state, sprint plan, project docs
    ├── PROJECT.md      # Requirements, scope, team
    ├── SPRINT.md       # 5-week timeline and assignments
    ├── config.json     # WTF-P configuration
    └── structure/      # Outline, argument map, narrative arc
```

## Compile Paper

```bash
cd paper && pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```
