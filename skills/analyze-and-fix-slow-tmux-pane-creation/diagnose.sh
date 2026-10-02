#!/usr/bin/env bash
# Where does new-pane time actually go? Read-only: reports, changes nothing.
#
# Walks the ladder in SKILL.md so a diagnosis is never a hunch:
#   1. is the box loaded?   2. shell or tmux?   3. which rc line?   4. why is it slow?
#
# Usage:  ./diagnose.sh [shell]        # shell defaults to $SHELL
set -u
SH="${1:-${SHELL:-/bin/bash}}"
SH_NAME="$(basename "$SH")"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
hr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

hr "1. load vs cores, memory vs swap"
CORES=$(nproc 2>/dev/null || echo 1)
LOAD=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 0)
printf '  load %s across %s cores = %s%% busy\n' "$LOAD" "$CORES" \
       "$(awk -v l="$LOAD" -v c="$CORES" 'BEGIN{printf "%.0f", l/c*100}')"
free -h 2>/dev/null | awk 'NR<=3{print "  "$0}'
SWAP_USED=$(free -b 2>/dev/null | awk '/^Swap:/{print $3}')
if [ "${SWAP_USED:-0}" -gt $((512*1024*1024)) ]; then
  echo "  >> swap in active use -- real memory pressure, this may be your answer"
else
  echo "  >> swap effectively unused -- NOT a memory leak, keep going"
fi

hr "2. shell startup: rc files vs the floor"
t() { local s=$(date +%s.%N); timeout 180 "$@" >/dev/null 2>&1; local e=$(date +%s.%N)
      awk -v a="$s" -v b="$e" 'BEGIN{printf "%.2f", b-a}'; }
WITH=$(t "$SH" -i -c exit)
case "$SH_NAME" in zsh) WITHOUT=$(t "$SH" -f -c exit);; *) WITHOUT=$(t "$SH" --norc --noprofile -c exit);; esac
printf '  interactive (reads rc): %s s\n  no rc files at all    : %s s\n' "$WITH" "$WITHOUT"
SLOW=$(awk -v w="$WITH" 'BEGIN{print (w>1.0)?1:0}')
if [ "$SLOW" = 1 ]; then
  echo "  >> the rc files own this delay; tmux is NOT the problem"
else
  echo "  >> shell startup is fine. If panes still feel slow, look at tmux itself:"
  echo "     tmux show-options -g | grep -Ei 'default-command|hook|update-env'"
fi

hr "3. which rc line (xtrace, timestamped -- zprof CANNOT see external commands)"
if [ "$SLOW" = 1 ]; then
  case "$SH_NAME" in
    zsh) PS4='+%D{%s.%6.}|%N:%i> ' timeout 180 "$SH" -i -x -c exit 2>"$TMP/trace" ;;
    *)   PS4='+$EPOCHREALTIME|$BASH_SOURCE:$LINENO> ' timeout 180 "$SH" -i -x -c exit 2>"$TMP/trace" ;;
  esac
  python3 - "$TMP/trace" <<'PY'
import re, sys
rows = []
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r'\++(\d+\.\d+)\|([^>]*)> ?(.*)', line)
    if m: rows.append((float(m.group(1)), m.group(2), m.group(3)[:95]))
if len(rows) < 2:
    print("  (no usable trace -- shell may not support this PS4)"); sys.exit()
print("  traced %.1f s over %d steps\n  biggest gaps (time spent AFTER each command):" %
      (rows[-1][0]-rows[0][0], len(rows)))
gaps = sorted(((rows[i+1][0]-rows[i][0], rows[i][1], rows[i][2])
               for i in range(len(rows)-1)), reverse=True)
for g, loc, cmd in gaps[:8]:
    if g > 0.05: print(f"    {g:7.2f}s  [{loc}]  {cmd}")
PY
else
  echo "  (skipped -- startup is fast)"
fi

hr "4. runaway scans and fd exhaustion (why an ordinary command turns slow)"
TOTAL=$(cut -f1 /proc/sys/fs/file-nr 2>/dev/null || echo "?")
echo "  system-wide open fds: $TOTAL   (a few thousand is normal)"
echo "  processes holding >200 fds:"
found=0
for d in /proc/[0-9]*; do
  n=$(ls "$d/fd" 2>/dev/null | wc -l)
  if [ "$n" -gt 200 ]; then
    p=${d#/proc/}
    # cmdline, never comm -- comm lies (MEASURED: a bfs scan reported itself as claude.exe)
    cl=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null | cut -c1-95)
    [ -z "$cl" ] && cl="[$(tr -d '\0' < "$d/comm" 2>/dev/null)]"
    echo "    $n fds  pid $p  $cl"; found=1
  fi
done
[ "$found" = 0 ] && echo "    (none -- good)"
echo "  long-running filesystem scans (>10 min):"
ps -eo pid,etimes,pcpu,args 2>/dev/null \
  | awk '$2>600' \
  | grep -E '\b(bfs|find|fdfind|locate|updatedb)\b|[[:space:]]-iname[[:space:]]|[[:space:]]-name[[:space:]]' \
  | grep -v grep | cut -c1-120 | sed 's/^/    /' || true
ps -eo pid,etimes,args 2>/dev/null | awk '$2>600' \
  | grep -E '\b(bfs|find|fdfind|locate|updatedb)\b' | grep -vq grep || echo "    (none -- good)"
echo "  slow (9p/drvfs/network) mounts a scan can fall into:"
mount 2>/dev/null | grep -E '9p|drvfs|cifs|nfs' | awk '{print "    "$1" -> "$3}' | head -5 || echo "    (none)"

hr "5. rc lines that run a command at every startup (the quoting bug)"
for f in ~/.zshrc ~/.bashrc ~/.profile ~/.zprofile ~/.bash_profile; do
  [ -f "$f" ] || continue
  grep -nE '^[[:space:]]*(alias|export)[^=]*="[^"]*\$\(' "$f" 2>/dev/null \
    | cut -c1-120 | sed "s|^|    $f:|"
done
echo "    ^ any hit above runs at SHELL STARTUP (double quotes expand \$( ) at definition)."
echo "      Single-quote it to defer to invocation. Nothing listed = clean."

printf '\n\033[1mNext:\033[0m kill any runaway scan FIRST, then re-run this -- it is often the whole\n'
printf 'problem, and an rc "fix" applied on top of it gets undeserved credit.\n'
