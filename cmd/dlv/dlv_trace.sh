#!/usr/bin/env bash
#
# dlv_trace.sh — Non-interactive Delve call tracing.
#
# Prints every call to functions matching REGEXP, with arguments and return
# values, WITHOUT touching the source (no print statements) and WITHOUT an
# interactive breakpoint loop. This is the direct replacement for the
# "paste logs -> guess which log.Debug fired -> infer dataflow" cycle.
#
# Usage:
#   scripts/dlv/dlv_trace.sh <regexp> [package]
#   scripts/dlv/dlv_trace.sh --test <regexp> <package> [-- -test.run TestName]
#
# Examples:
#   # Trace the live server while you hit it with curl (runs until Ctrl-C / SIGTERM):
#   scripts/dlv/dlv_trace.sh 'processing\.\(\*Streamer\)' .
#
#   # Trace a deterministic test run (preferred — reproducible, no timing noise):
#   scripts/dlv/dlv_trace.sh --test 'finalizeResponse' ./chatbot/processing -- -test.run TestResume
#
# The regexp matches fully-qualified function names, e.g.
#   github.com/.../chatbot/processing.(*Streamer).finalizeResponse
# so anchor loosely. Output goes to BOTH stdout and /tmp/dlv_trace.log.
#
set -euo pipefail

OUT=/tmp/dlv_trace.log

# Normally empty; set DLV_BUILD_FLAGS to pass extra `go build` flags if needed
# (e.g. DLV_BUILD_FLAGS='-tags=integration').
BUILD_FLAGS=()
[[ -n "${DLV_BUILD_FLAGS:-}" ]] && BUILD_FLAGS=(--build-flags="$DLV_BUILD_FLAGS")

if [[ "${1:-}" == "--test" ]]; then
  shift
  REGEXP="${1:?usage: dlv_trace.sh --test <regexp> <package> [-- -test.run X]}"
  PKG="${2:?missing package}"
  shift 2
  echo "[dlv_trace] tracing TEST '$REGEXP' in $PKG (extra args: $*)" | tee "$OUT"
  # `dlv trace --test` builds the test binary and traces matching funcs.
  exec dlv trace "${BUILD_FLAGS[@]}" --test "$PKG" "$REGEXP" "$@" 2>&1 | tee -a "$OUT"
else
  REGEXP="${1:?usage: dlv_trace.sh <regexp> [package]}"
  PKG="${2:-.}"
  echo "[dlv_trace] tracing '$REGEXP' in $PKG (Ctrl-C or kill to stop)" | tee "$OUT"
  exec dlv trace "${BUILD_FLAGS[@]}" "$PKG" "$REGEXP" 2>&1 | tee -a "$OUT"
fi
