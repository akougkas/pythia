#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Pythia — Speculative Dispatch for Multi-Agent Orchestration
# Onboarding script for team members
# ──────────────────────────────────────────────────────────────
#
#   curl -fsSL https://raw.githubusercontent.com/akougkas/pythia/main/onboard.sh | bash
#
# Or if you already cloned:
#
#   ./onboard.sh
#
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────
R='\033[0;31m' G='\033[0;32m' Y='\033[0;33m' B='\033[0;34m'
M='\033[0;35m' C='\033[0;36m' W='\033[1;37m' D='\033[0;90m'
RST='\033[0m'

ok()   { printf "  ${G}✓${RST} %s\n" "$1"; }
warn() { printf "  ${Y}⚠${RST} %s\n" "$1"; }
fail() { printf "  ${R}✗${RST} %s\n" "$1"; }
info() { printf "  ${D}→${RST} %s\n" "$1"; }

# ── Banner ────────────────────────────────────────────────────
printf "\n${M}"
cat << 'ORACLE'
         ╔═══════════════════════════════════════╗
         ║                                       ║
         ║   ⏣  P Y T H I A                     ║
         ║                                       ║
         ║   The oracle doesn't wait for the     ║
         ║   question to finish before she        ║
         ║   starts seeing the answer.            ║
         ║                                       ║
         ╚═══════════════════════════════════════╝
ORACLE
printf "${RST}\n"
printf "  ${W}Speculative Dispatch for Multi-Agent Orchestration${RST}\n"
printf "  ${D}SC26 · Deadline: April 8, 2026${RST}\n\n"

# ── Track pass/fail ───────────────────────────────────────────
ERRORS=0
WARNINGS=0

# ── 1. Prerequisites ─────────────────────────────────────────
printf "${C}▸ Checking prerequisites${RST}\n"

# git
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    fail "git not found — install git first"
    ((ERRORS++))
fi

# gh (GitHub CLI)
if command -v gh &>/dev/null; then
    if gh auth status &>/dev/null 2>&1; then
        GH_USER=$(gh api user -q .login 2>/dev/null || echo "unknown")
        ok "gh CLI authenticated as ${W}${GH_USER}${RST}"
    else
        fail "gh CLI installed but not authenticated — run: gh auth login"
        ((ERRORS++))
    fi
else
    fail "gh CLI not found — install: https://cli.github.com"
    ((ERRORS++))
fi

# claude (Claude Code CLI)
if command -v claude &>/dev/null; then
    ok "claude CLI found"
else
    fail "claude CLI not found — install: npm install -g @anthropic-ai/claude-code"
    ((ERRORS++))
fi

# python3
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "python ${PY_VER}"
    else
        warn "python ${PY_VER} (3.11+ recommended)"
        ((WARNINGS++))
    fi
else
    warn "python3 not found — needed for implementation"
    ((WARNINGS++))
fi

# pytest
if python3 -m pytest --version &>/dev/null 2>&1; then
    ok "pytest available"
else
    warn "pytest not found — install: pip install pytest"
    ((WARNINGS++))
fi

# pdflatex
if command -v pdflatex &>/dev/null; then
    ok "pdflatex available"
else
    warn "pdflatex not found — needed to compile paper"
    ((WARNINGS++))
fi

echo ""

# ── 2. Repository ────────────────────────────────────────────
printf "${C}▸ Setting up repository${RST}\n"

REPO_URL="https://github.com/akougkas/pythia.git"
REPO_DIR=""

# Detect if we're already inside the repo
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    REPO_ROOT=$(git rev-parse --show-toplevel)
    REPO_NAME=$(basename "$REPO_ROOT")
    if [ "$REPO_NAME" = "pythia" ]; then
        ok "already inside pythia repo at ${D}${REPO_ROOT}${RST}"
        REPO_DIR="$REPO_ROOT"
    fi
fi

# Clone if needed
if [ -z "$REPO_DIR" ]; then
    TARGET="${HOME}/publications/pythia"
    if [ -d "$TARGET/.git" ]; then
        ok "repo exists at ${D}${TARGET}${RST}"
        REPO_DIR="$TARGET"
    else
        info "cloning to ${TARGET} ..."
        if gh repo clone akougkas/pythia "$TARGET" 2>/dev/null; then
            ok "cloned to ${D}${TARGET}${RST}"
            REPO_DIR="$TARGET"
        else
            # fallback to git clone
            if git clone "$REPO_URL" "$TARGET" 2>/dev/null; then
                ok "cloned to ${D}${TARGET}${RST}"
                REPO_DIR="$TARGET"
            else
                fail "could not clone — check your GitHub access"
                ((ERRORS++))
            fi
        fi
    fi
fi

echo ""

# ── 3. Verify repo contents ──────────────────────────────────
if [ -n "$REPO_DIR" ]; then
    printf "${C}▸ Verifying project state${RST}\n"

    cd "$REPO_DIR"

    # Pull latest
    if git pull --ff-only origin main &>/dev/null 2>&1; then
        ok "up to date with origin/main"
    else
        warn "could not fast-forward — you may have local changes"
        ((WARNINGS++))
    fi

    # Critical files
    for f in CLAUDE.md .planning/PROJECT.md .planning/SPRINT.md .planning/config.json; do
        if [ -f "$f" ]; then
            ok "$f"
        else
            fail "$f missing"
            ((ERRORS++))
        fi
    done

    # Paper sections
    SECTION_COUNT=$(ls sections/*.md 2>/dev/null | wc -l)
    if [ "$SECTION_COUNT" -eq 8 ]; then
        ok "all 8 paper sections present"
    else
        warn "expected 8 sections, found ${SECTION_COUNT}"
        ((WARNINGS++))
    fi

    # LaTeX
    if [ -f "paper/main.tex" ]; then
        ok "paper/main.tex"
    else
        fail "paper/main.tex missing"
        ((ERRORS++))
    fi

    # src scaffold
    if [ -d "src" ]; then
        ok "src/ directory exists"
    else
        warn "src/ missing — will be created during development"
        ((WARNINGS++))
    fi

    # Bibliography
    if [ -f "references.bib" ]; then
        REF_COUNT=$(grep -c '@' references.bib 2>/dev/null || echo 0)
        ok "references.bib (${REF_COUNT} entries)"
    else
        fail "references.bib missing"
        ((ERRORS++))
    fi

    # PLACEHOLDERs
    PH_COUNT=$(grep -r "PLACEHOLDER" sections/ 2>/dev/null | wc -l || echo 0)
    if [ "$PH_COUNT" -gt 0 ]; then
        info "${PH_COUNT} PLACEHOLDERs remaining across paper sections"
    fi

    # Word count
    TOTAL_WORDS=$(cat sections/*.md 2>/dev/null | wc -w)
    info "${TOTAL_WORDS} words total (budget: 7,500)"

    echo ""
fi

# ── 4. Summary ────────────────────────────────────────────────
printf "${C}▸ Summary${RST}\n"

if [ "$ERRORS" -gt 0 ]; then
    printf "\n  ${R}${ERRORS} error(s)${RST}"
    [ "$WARNINGS" -gt 0 ] && printf ", ${Y}${WARNINGS} warning(s)${RST}"
    printf "\n  Fix errors above before continuing.\n\n"
    exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
    printf "  ${Y}${WARNINGS} warning(s)${RST} — non-blocking, but address when possible\n"
fi

ok "ready to go"
echo ""

# ── 5. Launch ─────────────────────────────────────────────────
printf "${C}▸ Next step${RST}\n\n"

if [ -n "$REPO_DIR" ]; then
    printf "  ${W}cd ${REPO_DIR}${RST}\n"
    printf "  ${W}claude --dangerously-skip-permissions -p \"/wtfp:progress\"${RST}\n\n"

    printf "  ${D}This launches Claude Code in mentor mode. It will read CLAUDE.md,${RST}\n"
    printf "  ${D}scan the project state, and brief you on what to work on next.${RST}\n"
    printf "  ${D}Read CLAUDE.md first if this is your first session.${RST}\n\n"

    read -rp "  Launch Claude now? [Y/n] " LAUNCH
    LAUNCH=${LAUNCH:-Y}
    if [[ "$LAUNCH" =~ ^[Yy]$ ]]; then
        echo ""
        cd "$REPO_DIR"
        exec claude --dangerously-skip-permissions -p "/wtfp:progress"
    else
        printf "\n  ${D}No worries. Run the commands above when ready.${RST}\n\n"
    fi
else
    printf "  Clone the repo first, then re-run this script.\n\n"
fi
