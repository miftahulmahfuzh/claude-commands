---
name: analyze-and-fix-slow-tmux-pane-creation
description: Use when opening a new tmux pane, window, split or shell is slow — "creating a new pane takes forever", "my terminal hangs for 20 seconds", "tmux is slow to open", "is there a memory leak in WSL/tmux/claude?", "new shells take ages", "why is my prompt slow to appear". Measures where the time actually goes instead of guessing, and fixes it. Also the right skill when a machine feels generally sluggish and a runaway filesystem scan is suspected.
---

# Slow tmux pane creation

A new pane runs one thing: your login shell's startup files. So "tmux is slow" is almost never
tmux, and almost never a memory leak — it is something in the rc files, or something elsewhere on
the box making an ordinary command in those rc files take 100x longer than it should.

**Measure first. Every single time.** The instinct is to blame memory, tmux, WSL or Claude, and
MEASURED 2026-10-02 all four were innocent while the machine had 7.2 GiB free and swap completely
untouched. Run `./diagnose.sh` (next to this file) and read it top to bottom before forming a
theory.

## The ladder

Each rung either explains the time or hands you to the next one. Do not skip a rung because you
have a hunch; a hunch is what makes this take an afternoon.

**1. Is the machine actually loaded?** `uptime` against `nproc`, `free -h`, swap.

Load means little until divided by cores. MEASURED: load 7.9 read as alarming and was ~36% of a
22-core box. And read **swap**, not "used" memory — Linux spends free RAM on cache by design, so
`used` is not pressure. Swap in active use is pressure; swap at 4 KiB is not. If RAM and swap are
genuinely exhausted, stop here, that is your answer. Otherwise it is not a memory leak, and saying
so early saves everyone a wasted hour.

**2. Is it the shell or is it tmux?** Time the two ends:

```bash
time zsh -i -c exit     # interactive: reads your rc files
time zsh -f -c exit     # no rc at all: the floor
```

MEASURED: 22.9 s versus 0.00 s. That gap *is* the pane delay, and it rules tmux out completely.
If both are fast, the problem is tmux itself or its config — check `tmux show-options -g` for
hooks and `default-command`, and whether the tmux server is swapping.

**3. Where in the rc files?** This rung has a trap worth knowing before you fall in it.

`zprof` measures **shell functions only**. It will happily report a 400 ms total on a shell that
takes 22 seconds, because the time went to an *external command* and zprof cannot see those.
MEASURED: zprof's whole table summed to 0.4 s and pointed at `cd` and `compaudit`, both red
herrings.

The instrument that works is xtrace with a timestamped `PS4`, then look for the gap:

```bash
PS4='+%D{%s.%6.}|%N:%i> ' zsh -i -x -c exit 2>/tmp/trace.log
```

Each line is stamped, so the time spent *after* a command is the next stamp minus this one. Sort
those deltas and the culprit is line one, usually by two orders of magnitude. `diagnose.sh` does
this parse for you. (For bash: `PS4='+$EPOCHREALTIME|$BASH_SOURCE:$LINENO> ' bash -i -x -c exit`.)

**4. Why is that command slow?** A command in an rc file is normally milliseconds. If one takes
seconds, it is usually a symptom of something else on the box — go to the fd check below before
blaming the command.

## The two faults found 2026-10-02, both of which will recur

### A runaway filesystem scan, eating the system's file descriptors

```
PID 608608   bfs -S dfs / -iname 'Poppins*' -not -path '*/proc/*'
2h 05m old, 43% CPU, 65,438 open fds of the system's 69,044 — 95%
```

A font search, launched by a Claude Code Bash call, walking the **whole filesystem from `/`** —
including `/mnt/c` over 9p, where every stat is a cross-VM round trip to Windows. It will never
finish in a useful time and it grows fds at ~2.5/sec.

This is what made the rc file slow: the rc ran `lsof`, and `lsof` must `readlink` every fd of every
process. At 65k fds, many on 9p, that took **18 seconds**. With the scan killed, the same `lsof`
took **0.03 seconds**.

**So do not blame `lsof`.** The honest causal chain is scan → fd explosion → lsof slow → rc slow →
pane slow, and fixing the wrong link leaves the real one in place. MEASURED: killing the scan alone
took shell startup from 22.9 s to 0.55 s, before any rc edit at all.

Find it:

```bash
cut -f1 /proc/sys/fs/file-nr                       # system-wide open fds
for d in /proc/[0-9]*; do n=$(ls $d/fd 2>/dev/null | wc -l);
  [ "$n" -gt 200 ] && echo "$n ${d#/proc/} $(tr -d '\0' <$d/comm)"; done | sort -rn | head
ps -eo pid,etimes,pcpu,args | awk '$2>600' | grep -E '\b(bfs|find|fd|fdfind|rg|ag|grep|locate|updatedb)\b'
```

A few thousand system-wide fds is normal. Tens of thousands in **one** process is the signal.

**Read `/proc/<pid>/cmdline`, never `comm`.** MEASURED: `ps -o comm` reported this process as
`claude.exe`, which sent the first pass hunting a Windows-interop memory leak that did not exist.
`cmdline` said `bfs … -iname Poppins*`. `comm` lies; the cmdline is the truth.

Killing it needs escalation — a process blocked in 9p I/O ignores `SIGTERM`:

```bash
kill -TERM <pid>; sleep 3; kill -0 <pid> 2>/dev/null && kill -KILL <pid>
```

It then shows as `Z` (zombie) until its parent reaps it. A zombie holds **no** fds — check
`/proc/sys/fs/file-nr` rather than the process list to confirm you actually won. If the parent is a
stuck `zsh -c` wrapper from a tool call, kill that too; **never** kill the `claude` session process
itself, which is a live session with a human attached.

### An alias whose `$(...)` runs at every shell startup

```zsh
alias d="kill $(lsof -t -i:8082) 2>/dev/null; docker compose up --build"
#          ^^ DOUBLE quotes: the $(...) is expanded when the alias is DEFINED
```

Double quotes expand command substitutions immediately, so this ran `lsof` **in every new pane**,
and baked that moment's pid into the alias — meaning it had also never killed the right process in
its life. Two bugs, one pair of quote marks.

Single quotes defer it to invocation. And prefer a tool that reads `/proc/net` over one that walks
every fd:

```zsh
alias d='fuser -k 8082/tcp 2>/dev/null; docker compose up --build'
```

`fuser -k 8082/tcp` is 0.01 s. `ss -ltnpH "sport = :8082" | grep -oP 'pid=\K\d+'` also works, but
note that both `ss -p` and `lsof` hide pids for processes owned by **other** users — so neither
sees a docker-published port (owned by root) without `sudo`. If the alias is meant to free a port
docker holds, `docker compose down` is what actually does it.

**Sweep the rc for the whole class, not just the one line you found:**

```bash
grep -nE '^\s*(alias|export)[^=]*="[^"]*\$\(' ~/.zshrc ~/.bashrc ~/.zprofile 2>/dev/null
```

## Fixing

1. Kill the runaway scan first and **re-measure**. It frequently turns out to be the whole problem,
   and an rc you "fixed" on top of it gets undeserved credit.
2. Back up the rc (`cp ~/.zshrc ~/.zshrc.bak-$(date +%Y%m%d-%H%M%S)`) before editing.
3. Apply the fix, then prove it: re-time `zsh -i -c exit`, and re-run the xtrace to confirm the
   command is **gone from startup** rather than merely faster. Grep the trace for its name — hits
   inside `_comps=(...)` arrays and `.zcompdump` are completion *data*, not executions, so read the
   matching lines rather than counting them.
4. Leave a comment in the rc saying why the quoting is the way it is. The next person to tidy that
   line will otherwise re-introduce it.

## Report honestly

State the causal chain in order, and correct any earlier theory you floated out loud — "it is a
memory leak", "lsof is slow on WSL" — because a plausible wrong diagnosis is what gets cargo-culted
into the next machine's setup. Give the before/after numbers for each fix separately, so it is
clear which one actually bought the time.
