#!/usr/bin/env bash
#
# dlv_core.sh — Post-mortem analysis of a crashed server from a core dump.
#
# This is the killer workflow for "it broke in the running server": instead of
# pasting logs, you capture the FROZEN state at the moment of failure and
# inspect every variable in every goroutine — offline, non-interactively.
#
# ── How to capture a core dump ──────────────────────────────────────────────
# Option A: let a panic dump core
#   ulimit -c unlimited
#   go build -o /tmp/agentic .            # need a NAMED binary (not `go run`)
#   GOTRACEBACK=crash /tmp/agentic        # on panic -> writes ./core or /tmp/core.*
#
# Option B: dump a live (possibly hung) server on demand
#   dlv attach $(lsof -t -i:8082)
#   (dlv) dump /tmp/server.core
#   (dlv) quit
#
# ── Analyze it ──────────────────────────────────────────────────────────────
#   scripts/dlv/dlv_core.sh <binary> <corefile> [cmdfile]
#
# Example:
#   scripts/dlv/dlv_core.sh /tmp/agentic /tmp/server.core /tmp/inspect.dlv
#
# If no cmdfile is given, a sensible default dump is run: all goroutines + the
# current stack. Provide a cmdfile to drill in (same Delve commands as
# dlv_test.sh: goroutine <id>, bt, print, locals, frame N, etc.).
#
set -euo pipefail

BIN="${1:?usage: dlv_core.sh <binary> <corefile> [cmdfile]}"
CORE="${2:?missing corefile}"
CMDFILE="${3:-}"

[[ -f "$BIN" ]]  || { echo "[dlv_core] binary not found: $BIN" >&2; exit 1; }
[[ -f "$CORE" ]] || { echo "[dlv_core] core not found: $CORE" >&2; exit 1; }

RUNFILE="$(mktemp /tmp/dlv_core.XXXXXX.dlv)"
trap 'rm -f "$RUNFILE"' EXIT

if [[ -n "$CMDFILE" ]]; then
  [[ -f "$CMDFILE" ]] || { echo "[dlv_core] cmdfile not found: $CMDFILE" >&2; exit 1; }
  cat "$CMDFILE" > "$RUNFILE"
else
  # Default post-mortem: where are all the goroutines and what was on top?
  cat > "$RUNFILE" <<'EOF'
goroutines -t
stack
locals
args
EOF
fi
printf '\nquit\n' >> "$RUNFILE"

echo "[dlv_core] post-mortem of $CORE (binary $BIN)"
echo "---------------------------------------------------------------"
dlv --allow-non-terminal-interactive=true core "$BIN" "$CORE" < "$RUNFILE"
