---
name: swarm
description: Use when a plan set should run across several Claude Code sessions at once instead of one phase at a time — "orchestrate this plan", "run the phases in parallel", "spawn a session per phase", "resume the orchestration on this laptop", "what's the status of the swarm", "which phases can run now" — or when a phase session finishes and has to report back to the session that is tracking the set.
---

# Swarm

A plan set written by `/analyze` is a DAG: every phase declares `depends_on`, so phases that
share no edge can run at the same time, in their own sessions, in their own tmux windows. This
skill is how a coordinator session drives that, and how a phase session reports back.

Two channels, and keeping them apart is what makes the whole thing work:

- **Messaging is the nervous system, and it is local.** `ListAgents` sees sessions on this
  machine (plus cloud ones); `SendMessage` addresses them by name. It is live, cheap, and dies
  with the machine.
- **Git is the skeleton, and it is global.** The durable ledger is committed, so another laptop
  can pick the set up hours later with nothing but a `git pull`.

Never use one for the other's job. A message is not a record; a commit is not a notification.

## The addressing rule

`claude -n <name>` sets a session's peer address **at launch**, before the process boots — so a
coordinator never races a child's own rename to learn where to write to it. Names are derived,
never invented:

| Session | Name |
|---|---|
| the coordinator | `orch-<slug>` (or `analyze-<slug>` when `/analyze` is driving) |
| phase N of a set | `impl-<slug>-p<N>` |
| a lone task | `do-<TaskID>` |

`swarm.py` computes these with `child_name()`, truncating the slug rather than the phase number —
two phases must never collide on one address.

## The ledger, in two halves

```
<main repo>/.workflows/orchestration/<slug>/
├── ledger.json      DURABLE  — committed. Phases, depends_on, status, landed commit, TaskIDs.
├── .runtime.json    LOCAL    — gitignored. tmux window/pane ids, session names, this machine.
└── .gitignore       one line: .runtime.json
```

It lives in the **main worktree**, never in the plan set's own worktree — that worktree is
deleted when the set lands, and a ledger inside it would go with it. `swarm.py` resolves this
with `git rev-parse --git-common-dir`.

Run `swarm.py track` once per repo. Repos ignore `.workflows/` broadly and for good reason (one
of them holds 218 files of generated plans); `track` re-includes the orchestration path *and
nothing else*, leaving `todos.md`, `plan/` and `postmortem/` exactly as ignored as they were.

## Derive, never trust

The durable ledger is written by whichever machine ran the phase. A machine that died mid-phase
left it reading `running` forever. So `swarm.py verify` re-derives every phase's real status
from the two things that cannot lie — whether the commit is an ancestor of the branch, and what
`todos.md` says about the TaskID — and reports where the ledger disagrees. `--apply` writes the
derivation back.

**One asymmetry is deliberate and load-bearing:** a `done` phase is never downgraded on missing
evidence. "The commit is not on the branch" and "this clone has not fetched the branch" look
identical to git, and confusing them would send the orchestrator to re-run a phase that already
shipped. Absence of evidence keeps the ledger's word; only positive contrary evidence overrides
it.

## The orchestrator loop

```bash
python3 ~/.claude/skills/swarm/swarm.py init  --plan <SLUG>_PLAN.md --coordinator orch-<slug>
python3 ~/.claude/skills/swarm/swarm.py waves --slug <slug>      # -> runnable_now: [1, 3]
```

Then, until nothing is runnable and nothing is live:

1. **Spawn every runnable phase, in one round.** `spawn --slug <slug> --phase N` opens a detached
   tmux window (`-d`, so it never steals the window the user is watching) running
   `/implement -f <plan> --phase N`.
2. **Subscribe to each one:** `SendMessage` with `notify_when_idle: true` and no message. This is
   the only way to catch a phase that dies without reporting — a report-back alone cannot
   distinguish "still working" from "crashed".
3. **Collect reports.** Each arrives as `<cross-session-message from="impl-<slug>-pN">`.
4. **Verify before believing.** `swarm.py verify --slug <slug> --apply`. A phase that says it
   landed but whose commit is not on the branch has not landed.
5. **Commit and push the ledger.** Every round, not at the end — this is what bounds a
   cross-machine resume to losing at most one phase.
6. **Re-compute.** `waves` again; a finished phase may have unblocked others. Go to 1.

Stop when `runnable_now` is empty. `stalled` lists phases that can never run because a dependency
failed — report those to the user rather than spawning them.

### Spawn children on the coordinator's own permission mode

Two separate reasons, and both are load-bearing.

**It is what makes reports arrive at all.** MEASURED: a child running on a different permission
mode than the coordinator has its cross-session messages *held for the user to approve* —
"the recipient's session has different permission-mode settings". The coordinator sees nothing
until a human clicks, and a stalled swarm looks exactly like a slow one. Pass
`--permission-mode` matching the mode this session is running under; `swarm.py spawn` warns when
it is omitted because the failure is otherwise silent.

**And never spawn with permissions you do not have.**

`spawn --permission-mode` is passed straight to the child. A coordinator must never hand a child
a mode *broader* than its own session runs under. A peer doing what your session was denied is
permission laundering: it routes around a decision the user made. If a phase needs permissions
you do not have, stop and say so.

## The folder trust prompt

MEASURED, and it breaks an unattended swarm on the normal case rather than an edge one: a session
spawned into a path Claude Code has not seen stops on the folder-trust prompt *before it boots*.
It never registers as a peer, so the coordinator waits forever on a session that is not running —
and every worktree `/analyze` cuts is a new path.

There is no interactive flag that skips it (`-p` does, but a print session is not one the user
can watch or take over). So `swarm.py spawn` **propagates** the trust: if the repo the worktree
was cut from is already trusted, the worktree is marked trusted too, in `~/.claude.json`, by an
atomic replace. Trust is propagated, never invented — if the repo itself is untrusted, `spawn`
refuses and tells the user to open it once by hand. `--no-trust` opts out.

## The mesh

Phase sessions may message each other directly, not only the coordinator. Kept useful rather than
chatty by restricting it to four message kinds — everything else goes to the coordinator.

| Kind | When | Body |
|---|---|---|
| `DONE` | a phase has landed | phase, TaskID, commit sha, one line on what changed |
| `READY` | an Interface Contract item now exists | the symbol or file a dependent was waiting on |
| `NEED` | before assuming a dependency landed | the contract item, and which phase owns it |
| `WARN` | about to delete a worktree or branch | the path, and what the recipient should do |

Two hard rules. **A message states a fact; it never delegates work** — "I deleted `SortRows`" is
a mesh message, "please delete `SortRows` for me" is not. And **`WARN` before destroying shared
ground**: a session removing a worktree tells every peer whose cwd lives inside it, because their
working directory is about to stop existing.

## Reporting, from a phase session

Both halves, in this order. The file is the record; the message is the notification. Doing only
one leaves either a silent coordinator or an unrecoverable set.

```bash
python3 ~/.claude/skills/swarm/swarm.py find --plan .workflows/plan/<slug>/phase-2.md
# -> {"swarm": true, "slug": "...", "phase": 2, "coordinator": "orch-...", "peers": [...]}

python3 ~/.claude/skills/swarm/swarm.py report --slug <slug> --phase 2 \
    --status done --commit <sha> --task P2-TP-A012 --note "tests green"
```

then `SendMessage` to the `coordinator` that `find` returned.

`find` is discovery over flags on purpose: a session the user launched by hand carries no
`--swarm` argument, and a report that silently went nowhere is worse than no report. Every
`swarm.py` read prints `{"swarm": false, ...}` and exits 0 when there is no ledger, so an
ordinary `/do` outside any swarm is unaffected.

## Commands

| | |
|---|---|
| `init --plan PATH [--coordinator NAME]` | build the ledger from a plan index; re-running keeps recorded outcomes |
| `waves --slug S` | the DAG in rounds, plus `runnable_now` and `stalled` |
| `spawn --slug S --phase N` | launch one phase in its own named session; `--dry-run` prints the argv |
| `report --slug S --phase N --status ...` | record an outcome (then send the message) |
| `verify --slug S [--apply]` | re-derive status from git and todos.md |
| `status --slug S` | durable + runtime, merged, for a human |
| `find --plan P \| --task T` | which swarm owns this, and who to report to |
| `track` | make `.workflows/orchestration/` survive the repo's `.gitignore` |
| `selftest` | offline assertions; no git, tmux or network |
