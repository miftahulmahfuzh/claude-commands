# swarm-deck

A [Claude Code mod](https://code.claude.com/docs/en/plugins/mods/overview) that makes an
unattended swarm's central invariant mechanical: **a phase session cannot block on a human.**

Requires Claude Code **v2.1.287+** (developed and tested on 2.1.311).

## The problem it removes

This repo drives plan sets across many Claude Code sessions at once — one session per phase,
a DAG of waves, a coordinator that lands the set. Every one of those sessions runs overnight
with nobody watching. The orchestration docs state the rule plainly:

> a phase that asks stalls its dependents, a coordinator that asks stalls the whole set

And then, MEASURED: *a phase-2 session held an `AskUserQuestion` for eight hours and stalled
a six-phase set whose answer was rung 1 of the precedence ladder.*

The rule was already written down. It was written down **in a prompt** — which is advice, and
advice is something a model can decline to take at 3am. A mod's hooks run inside Claude Code's
own process and can *answer* an event instead of letting it happen, so the dialog never
renders. The question stops being a thing the model is asked not to do and starts being a
thing it cannot do.

## What it does

`tool.call` on `AskUserQuestion`, in a session that `swarm.py spawn` launched as a phase:

- refuses the call, so no dialog renders and nothing waits
- hands back the **precedence ladder** (invariant → exit criteria → code blocks →
  Why/Requirements → task text → surrounding convention) as the tool result, so the phase
  decides on the highest rung that settles it
- requires the decision be recorded in `completion_report.decisions`, which already flows into
  `todos.md`, the commit body and the swarm ledger

Outside a swarm it is **dormant**: an ordinary interactive session is untouched.

## Two design points worth the words

**It fails closed.** A mod hook that throws or times out is *skipped* — which would let the
dialog render and stall the night, i.e. the hook's failure mode would be the exact bug it
exists to prevent. So the guard carries a `.catch` handler that re-issues the same refusal.
`claude plugin validate` reports `gating hook with .catch` to confirm it is wired, and a test
forces the throw and asserts the refusal survives it.

**Identity travels in the environment, not the filesystem.** A session learns which phase of
which set it is from `SWARM_SLUG` / `SWARM_PHASE` / `SWARM_COORDINATOR`, set by
`swarm.py spawn` through tmux's `-e`. Deriving it from the working directory instead would
disarm the guard in precisely the session that needs it: lookup keys on a plan path or TaskID,
and a child that has wandered out of its worktree answers "no swarm owns that".

## Install

It loads straight from this repo — no install step, no second copy:

```jsonc
// ~/.claude/settings.json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "/path/to/claude-commands/mods/swarm-deck" } }
```

Deliberately *not* via `sync.sh`. Installed plugins are cached by version and edits do not
reach the installed copy without a version bump — which is the same "the deployed tree
silently diverges from the repo" failure this repo has a whole section of `CLAUDE.md` about.
One source of truth instead.

## Develop

```bash
claude plugin validate .   # events, calls and env reads the engine will actually see
claude plugin test         # offline: no session, no sign-in, no network
claude --plugin-dir .      # load it live, hot-reloads on save
```

## Status

Slices 1 and 2 of 4 — the guard, and the heartbeat behind it. 8 tests, 0 fail.

Each phase publishes its own row into `$.store`, which is shared by every session on the
machine, on a 15-second timer that runs *outside any turn* — so a coordinator watching ten
phases spends no tokens to do it. One key per phase rather than one per set, because the
phases of a set run concurrently by construction and a shared document would have them
losing each other's writes exactly when the set is busiest.

Refused forks are written down as they happen, under their own per-phase key. The
coordinator's "Decided without asking" review is reconstructed at the end of a run today,
which means a coordinator that dies takes the record with it; this makes it durable.

`/fleet` draws those rows as a docked pane, registered with `immediate: true` so it opens
**while Claude is working** — a deck you can only open between turns is a deck you cannot open
at the moment you need it. Staleness overrides reported status: a row that says `working` and
stopped heartbeating reads `QUIET`, and so does a row with no timestamp at all, because "I
cannot tell when this last reported" is not evidence of health.

`Box` and `Text` only, verified mounting in terminal, desktop and vscode — which is why the
deck refuses `Raster` and `Image`, both terminal-only and both a minefield inside tmux.

Verified end to end in a live tmux session: a forced `AskUserQuestion` came back refused with
the ladder, and the fork appeared on the deck as `Decided without asking: 1` seconds later.

Next: a band above the prompt that lights only when something genuinely needs a human, plus
the interactive-command guard and the undelivered-report detector.

MIT.
