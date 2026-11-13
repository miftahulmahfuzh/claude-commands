#!/bin/bash
# capture.sh — the facts an aoi-bug report needs, read mechanically, in one call.
#
# Prints WHERE / VERSIONS / LEDGER lines for the note body. It reads; it never writes, never
# runs swarm.py verify, and never fails: a fact it cannot read is printed as "unknown", because
# a report with a hole in it is worth more than no report.
#
# usage: capture.sh [slug]      (slug defaults to $SWARM_SLUG, then the only set under cwd)

u() { [ -n "$1" ] && printf '%s' "$1" || printf 'unknown'; }

ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
MAIN=$(git worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')
BRANCH=$(git branch --show-current 2>/dev/null)

SLUG="${1:-$SWARM_SLUG}"
LEDGER=""
for base in "$ROOT" "$MAIN"; do
    [ -n "$base" ] || continue
    if [ -n "$SLUG" ]; then
        [ -f "$base/.workflows/orchestration/$SLUG/ledger.json" ] &&
            LEDGER="$base/.workflows/orchestration/$SLUG/ledger.json" && break
    else
        # No slug named: adopt a set only when there is exactly one, never guess between several.
        mapfile -t found < <(ls "$base"/.workflows/orchestration/*/ledger.json 2>/dev/null)
        if [ "${#found[@]}" -eq 1 ]; then
            LEDGER="${found[0]}"; SLUG=$(basename "$(dirname "$LEDGER")"); break
        elif [ "${#found[@]}" -gt 1 ]; then
            SETS=$(for f in "${found[@]}"; do basename "$(dirname "$f")"; done | tr '\n' ' ')
            break
        fi
    fi
done

if [ -n "$SWARM_PHASE" ]; then ROLE="phase $SWARM_PHASE"
elif [ -n "$LEDGER" ] && grep -q "\"coordinator_session_id\": *\"$CLAUDE_CODE_SESSION_ID\"" "$LEDGER" 2>/dev/null; then ROLE="coordinator"
else ROLE="not a swarm session"; fi

echo "WHERE: repo $(u "${MAIN:-$ROOT}"), branch $(u "$BRANCH"), set $(u "$SLUG"), role $ROLE, session $(u "$CLAUDE_CODE_SESSION_ID")"
[ -n "$SETS" ] && echo "SETS HERE (none adopted, name one): $SETS"

# The repo the deployed prompts came from: the swarm-deck mod is loaded straight from it.
CC=""
IFS=':' read -ra dirs <<< "$CLAUDE_CODE_PLUGIN_DIRS"
for d in "${dirs[@]}"; do
    case "$d" in */mods/swarm-deck) CC="${d%/mods/swarm-deck}";; esac
done
[ -d "$CC/.git" ] || CC="$HOME/claude-commands"
if [ -d "$CC/.git" ]; then
    SHA=$(git -C "$CC" rev-parse --short HEAD 2>/dev/null)
    [ -n "$(git -C "$CC" status --porcelain 2>/dev/null | head -1)" ] && SHA="$SHA+uncommitted"
    DRIFT="in sync"
    for d in skills agents commands; do
        diff -rq --exclude=__pycache__ --exclude='.*' "$CC/$d" "$HOME/.claude/$d" 2>/dev/null |
            grep -q "^Files .* differ$" && DRIFT="DEPLOYED COPY DIFFERS FROM REPO ($d)" && break
    done
fi
echo "VERSIONS: claude-commands $(u "$SHA") ($(u "$DRIFT")), Claude Code $(u "$(claude --version 2>/dev/null | head -1)")"

if [ -n "$LEDGER" ]; then
    python3 - "$LEDGER" <<'PY' 2>/dev/null || echo "LEDGER: $LEDGER (unreadable)"
import json, sys
d = json.load(open(sys.argv[1]))
print(f"LEDGER: {sys.argv[1]} (updated {d.get('updated', 'unknown')}, landed {'yes' if d.get('landed') else 'no'})")
for p in d.get("phases", []):
    print(f"  phase {p.get('n')}: {p.get('status', 'unknown')}"
          f" commit {p.get('commit') or '-'} reported {p.get('reported_at') or '-'}")
PY
else
    echo "LEDGER: none found"
fi
