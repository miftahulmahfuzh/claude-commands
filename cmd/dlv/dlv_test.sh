#!/usr/bin/env bash
#
# dlv_test.sh — Scripted (batch) Delve breakpoint debugging of a single test.
#
# This is the gold standard for DETERMINISTIC bugs: turn the bug into a focused
# `go test`, then drive Delve with a command script instead of stepping by hand.
# No interactive ping-pong — Delve runs the commands, prints the transcript,
# and exits. The transcript (variables, stacks, goroutines at the breakpoint)
# is what gets analyzed.
#
# Usage:
#   scripts/dlv/dlv_test.sh <package> <TestName> <cmdfile>
#
# Example:
#   scripts/dlv/dlv_test.sh ./chatbot/processing TestResumeLoop /tmp/cmds.dlv
#
# Where /tmp/cmds.dlv is a Delve command script, e.g.:
#   break processing.go:142
#   condition 1 resp.Sources == nil
#   continue
#   print resp
#   args
#   goroutines
#   stack
#   # 'quit' is appended automatically if you forget it
#
# Delve command cheat-sheet:
#   break <file>:<line> | break pkg.(*Type).Method   set breakpoint
#   condition <id> <expr>                             only stop when expr true
#   continue (c) / next (n) / step (s) / stepout      flow control
#   print <expr> (p) / args / locals / vars           inspect values
#   goroutines / goroutine <id> / stack (bt)          concurrency state
#   set <var> = <val>                                 mutate state
#
set -euo pipefail

PKG="${1:?usage: dlv_test.sh <package> <TestName> <cmdfile>}"
TEST="${2:?missing TestName}"
CMDFILE="${3:?missing cmdfile}"

[[ -f "$CMDFILE" ]] || { echo "[dlv_test] cmdfile not found: $CMDFILE" >&2; exit 1; }

# Ensure the script terminates Delve cleanly even if the user forgot 'quit'.
RUNFILE="$(mktemp /tmp/dlv_test.XXXXXX.dlv)"
trap 'rm -f "$RUNFILE"' EXIT
cat "$CMDFILE" > "$RUNFILE"
printf '\nquit\n' >> "$RUNFILE"

echo "[dlv_test] debugging $TEST in $PKG with $CMDFILE"
echo "---------------------------------------------------------------"
# Pipe commands via stdin: Delve reads them line-by-line in batch mode.
# --allow-non-terminal-interactive lets Delve accept commands from a pipe.
# DLV_BUILD_FLAGS is normally empty; set it to pass extra `go build` flags
# (e.g. DLV_BUILD_FLAGS='-tags=integration') if a package needs them.
if [[ -n "${DLV_BUILD_FLAGS:-}" ]]; then
  dlv --allow-non-terminal-interactive=true test "$PKG" \
    --build-flags="$DLV_BUILD_FLAGS" -- -test.run "$TEST" < "$RUNFILE"
else
  dlv --allow-non-terminal-interactive=true test "$PKG" \
    -- -test.run "$TEST" < "$RUNFILE"
fi
