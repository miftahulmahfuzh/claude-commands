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

## Nobody in a swarm waits for a human

A swarm exists to turn a night into N phases of progress. A question suspends that, and the cost
scales with the fan-out:

| Who asks | What stalls |
|---|---|
| one phase session | that phase — plus every phase that depends on it, transitively |
| the coordinator | the whole set: the wave it was spawning, every wave behind it, every window it would have reaped |

MEASURED on `nina-character-tuning`: phase 2 found its plan's invariant contradicting its own
prose, asked with `AskUserQuestion`, and held that prompt for **eight hours**. Phases 3 and 4 both
declared `depends_on: [1, 2]`, so a six-phase set produced nothing overnight while the coordinator
idled beside it — correctly reporting a serial stretch in the DAG, and wrongly concluding the
serialization was the DAG's fault. The answer was the plan's own invariant.

So the rule, for every session in the mesh:

> **Never end a turn with a question the swarm needs answered to continue.**

Which role decides what:

- **A phase session decides its own forks** — ambiguity in its plan, a self-contradiction, a
  failing check the plan did not anticipate. `/do` and `/implement` each carry the precedence
  ladder (**stated invariant → exit criteria → the plan's code blocks → the index's Why and
  Requirements → task text/note → surrounding convention**) and forbid `AskUserQuestion`
  outright. It reports the decision in the ledger `--note`, never as a question.
- **The coordinator decides the set's forks** — the plan index's Open Questions before spawning
  anything, which phase to resume when several sets are unfinished, what a straggler's silence
  means. And it **answers a child that asks anyway** rather than relaying the question: it holds
  the plan index, the Requirements table and every sibling's report, making it the best-informed
  decider present and the only one awake.
- **Nobody asks the user mid-set.** The one legitimate wait is the **merge**, which is terminal
  and comes after every phase has landed and been pushed.

**Stopping is allowed; blocking is not.** A stop ends a session cleanly — the ledger truthful, the
reason printed, the coordinator told, the work on disk surviving. A block is a live session
holding an unanswered question and building nothing. The stops in this workflow are few and all
terminal: a fork where every branch is irreversible, missing tooling, a permission a session does
not have. Everything else gets decided and written down.

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

**A name is not an identity.** Names are mutable and reused, and the window between reading
`ListAgents` and calling `SendMessage` is enough to invalidate one. MEASURED here: a session
listed as `agentic-golang-30` renamed itself to `analyze-carry-similarity-branch` about a minute
later, when `/analyze` ran in it — and a message addressed to the old name still arrived, at a
session by then doing unrelated work. Nothing was broadcast; the target simply moved.

Three consequences the swarm depends on:

- **Set the child's name at launch.** `claude -n impl-<slug>-p<N>` means the coordinator never
  reads a name it did not choose, and no other session will adopt that shape.
- **A session never renames itself to something less specific.** The child runs `/implement`,
  which renames itself too — and `impl-<slug>` is the launch name minus the one part that says
  which phase, so adopting it gives every phase of the set one address and leaves the recorded
  one answering nowhere. MEASURED: four of seven phases passed through the bare
  `impl-admin-album-file-manager`, and the one whose re-sharpening never landed stayed there.
  Every rename in this workflow passes `session.py rename … --no-widen`, which refuses that.
- **Re-read `ListAgents` immediately before sending.** Never send to a name captured earlier in
  the session; a cached name is a guess about the present.
- **The ledger records `coordinator_session_id` alongside the name.** Before reporting, confirm
  the name still resolves; if it is gone, tell the user rather than sending a phase report to
  whichever session now happens to hold that name.

## The ledger, in two halves

```
<main repo>/.workflows/orchestration/<slug>/
├── ledger.json      DURABLE  — committed. Phases, depends_on, status, landed commit, TaskIDs.
├── .runtime.json    LOCAL    — gitignored. tmux window/pane ids, session names, this machine.
├── logs/phase-N.log LOCAL    — gitignored. The scrollback of a window `reap` closed.
└── .gitignore       .runtime.json and logs/
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

## Launching a session that nobody typed a command into

`launch` opens one named session in a new tmux window, with no ledger required — the same
mechanics as `spawn`, minus the phase. It exists so a session can hand off without a human in the
middle: `/analyze --orchestrate` uses it to start the orchestrator the moment the plan exists,
rather than leaving a pasteable command on screen until somebody wakes up.

```bash
python3 ~/.claude/skills/swarm/swarm.py launch \
    --name orch-<slug> --cwd <worktree> --permission-mode <this session's mode> \
    --prompt "/analyze-orchestrator -f <SLUG>_PLAN.md --permission-mode <same>"
```

The mode is passed twice on purpose: once to launch the session on it, once *inside* the prompt
so the orchestrator knows what to hand its own children. A session cannot read its own permission
mode, so an argument is the only way it travels.

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
6. **Reap the windows the wave finished with.** `reap --slug <slug>`, after `verify` and
   never before it — an unverified `done` is a claim, and its window is the evidence.
7. **Re-compute.** `waves` again; a finished phase may have unblocked others. Go to 1.

Stop when `runnable_now` is empty. `stalled` lists phases that can never run because a dependency
failed — report those to the user rather than spawning them, and **keep driving whatever is still
runnable**. A failure in one branch of the DAG never pauses the branches it does not touch, and it
is never a reason to ask whether to continue: halting a set on one failed phase turns a partial
night into an empty one.

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

## Closing the windows

A phase that finished does not close its own window. claude does not exit when it runs out
of work — it sits at an idle prompt — so a wave of eight leaves eight idle sessions behind,
and the next wave's windows arrive at the far end of a tab bar the user stopped reading two
waves ago. Untidiness here is not cosmetic: the windows *are* how a human watches a swarm.

So the coordinator closes them, and closes them **permanently**:

```bash
python3 ~/.claude/skills/swarm/swarm.py reap --slug <slug>            # every finished phase
python3 ~/.claude/skills/swarm/swarm.py reap --slug <slug> --phase 3  # just one
```

Permanent is the cheaper half of the trade. Reopening a phase costs one `spawn --force`,
which is what a bug report or a discrepancy wants anyway — a fresh session on the current
code, not a stale one that has been idling since the phase landed.

### When `reap` refuses on a name mismatch

`reap` closes a window only while its name still equals the name it was spawned under, and
**`--force` does not override that check** — `--force` short-circuits the ledger-status gate, and
the identity check runs after it, deliberately, because a restarted tmux server hands `@7` to
somebody else's window. So a phase that renamed its own window away from its launch name is
unreapable, and stays that way.

Do **not** hand-kill it: `kill-window` loses the scrollback that `reap` exists to capture. Instead
verify the pane really is that phase — its own commit sha in the scrollback, plus
`pane_current_path` pointing at the set's worktree — then `tmux rename-window` back to the spawned
name and let `reap` run normally. MEASURED 2026-09-05 on `tabbar-new-tab-composer-seam` phase 2,
which had shortened its own slug on boot.

The upstream fix is in `commands/implement.md`: a session launched with `claude -n` passes its
launch name back verbatim rather than shortening it, because that name is the coordinator's
recorded address *and* the string `reap` matches on. `--no-widen` does not catch this on its own —
a shortened slug that keeps its `-p{N}` is not a widening.

**The scrollback survives the window.** `reap` runs `capture-pane` over the whole history
into `logs/phase-N.log` before killing anything. That is why `spawn` keeps the pane alive
after claude exits, and it is why closing the window loses nothing: the output ends up
somewhere better than a scrollback buffer — a file that is still there tomorrow, and
greppable across the whole set at once.

**Reaping is the coordinator's job, never the phase's own.** A session cannot close the
window it is reporting from, and a phase that killed itself the moment it said `done` would
take its own `git push` with it.

### What reap refuses to do

Four refusals, each a real way to destroy work rather than tidy it:

| Refusal | Why |
|---|---|
| a phase in `pending`/`spawned`/`running` | it reported nothing; its session may still be mid-write. `--force` overrides |
| a phase claiming `done` whose commit is not on the branch | the claim is unverified — `verify` first, then reap |
| a window whose name no longer matches what we spawned | tmux window ids are reused across server restarts; `@7` may be a stranger's work now. **`--force` does not override this one** |
| this session's own window | self-explanatory, and worth a guard anyway |

A `failed` phase keeps its window by default, because the failure is the thing someone is
about to read. `--include-failed` closes it — the log is captured either way.

Reap never fails a phase that is simply elsewhere: a window opened on another machine is
left for that machine, and a window already closed by hand is just forgotten.

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
| `CLAIM` | **before** taking a step a live peer owns | which step, which set, and that you are doing it now |

Three hard rules. **A message states a fact; it never delegates work** — "I deleted `SortRows`"
is a mesh message, "please delete `SortRows` for me" is not. **`WARN` before destroying shared
ground**: a session removing a worktree tells every peer whose cwd lives inside it, because their
working directory is about to stop existing.

**`CLAIM` goes before the act, and its whole value is the ordering.** The step this exists for is
the **merge**: a set's coordinator owns it (its Step 5), so any other session taking it — because
the coordinator is gone, or because the user authorised unattended merges while away — must say so
*first*. MEASURED 2026-09-05: a session merged a completed set and told the coordinator afterwards.
The coordinator had a merge of the same content built and gated locally at that moment and
discarded it as redundant, which cost nothing — but thirty seconds the other way and `main` would
have carried two merges of one set to reconcile. The ledger records `coordinator` and
`coordinator_session_id` from before phase 1 spawns for exactly this lookup, so "I could not find
the owner" is a claim to check with `ListAgents`, not to assume.

A `CLAIM` is still a fact and still does not block: it announces, it does not ask, and the sender
proceeds. What it buys the recipient is the chance to drop its own copy of the work before both
land.

**A `CLAIM` on a merge also claims the worktree's index until the sender says it is done.** This is
the half `CLAIM` did not originally cover, and it is not theoretical. MEASURED 2026-09-05: while a
merge sat resolved-but-uncommitted in the main worktree, that set's coordinator began its own
Step 5 prune in the same directory — `git rm --cached` on two phase bodies, plus its ledger and
plan index staged — writing straight into the other session's merge index. It noticed, restored
from `HEAD`, and un-staged its own files, and the merge committed clean; but nothing warned either
side, and `git status` in a shared worktree does not say whose index it is.

So: a coordinator whose set is being merged **parks every index-touching step** — prune, `git add`,
`git rm --cached`, ledger commit — until the merger reports the sha, then runs them on top as its
own commit. And the merger, before committing, **re-verifies the tree against what it staged**
rather than trusting the restore: conflict markers, the paths it did not expect to change, and the
files a peer said it put back. The session that contaminated an index is the weaker of the two
witnesses to its repair.

Worktrees are the isolation boundary for phase work, and they hold. The main checkout is the
exception, because it is where ledgers live and where merges land — the one shared surface, and
therefore the one that needs saying out loud.

And **no message asks a peer for a decision, and none blocks on a reply.** Every kind in that
table is a fact in one direction: `NEED` states what this phase requires and which phase owns it
— it is not a request to be answered before work continues. If a session cannot proceed without a
peer's answer, that is a missing `depends_on` edge in the plan, not a conversation: decide from
the ladder above, note it, and report the edge to the coordinator so it lands in the ledger. A
peer waiting on a peer is the same eight-hour stall with the human swapped out for a session that
is also idle.

A **question that arrives anyway** — from a child on an older prompt, or a fork its own ladder
could not reach — is answered by the coordinator, with the choice *and* the rung that decided it,
and recorded in the ledger note so later phases inherit it. It is never forwarded to the user:
that converts one stalled phase into a stalled set.

## Reporting, from a phase session

Both halves, in this order. The file is the record; the message is the notification. Doing only
one leaves either a silent coordinator or an unrecoverable set.

```bash
python3 ~/.claude/skills/swarm/swarm.py find --plan .workflows/plan/<slug>/phase-2.md
# -> {"swarm": true, "slug": "...", "phase": 2, "coordinator": "orch-...", "peers": [...]}

python3 ~/.claude/skills/swarm/swarm.py report --slug <slug> --phase 2 \
    --status done --commit <sha> --task P2-TP-A012 --note "tests green"
```

**The `--note` is where a decision goes.** A phase that settled a fork instead of asking about it
must say so here in a clause — `anger ceiling off 0→4 per invariant 2` — because the next phase
was planned against the sentence that got overruled, and the ledger is the only place it will
look. A report is also never a question: `failed` with the reason is a report the coordinator can
act on, while "which should I do?" is a phase that has not reported at all.

then `SendMessage` to the `coordinator` that `find` returned — after confirming that name is
still in `ListAgents`. `find` returns `coordinator_session_id` for exactly this check. If the
coordinator is gone, the file half of the report is already durable: say so to the user and stop,
rather than delivering a phase report to a stranger.

**Check `find`'s `slug` against the directory the plan file lives in before acting on it.** It is a
lookup, not an authority, and a wrong answer is silent — a real slug, a real phase, a real
coordinator, nothing about it looking wrong. MEASURED 2026-09-05: a bug made `find --plan` fall
back to the plan file's basename, and because every set has a `phase-N.md` and ledgers are scanned
in sorted order, the alphabetically-first set won every lookup. `tabbar-new-tab-composer-seam`'s
phase 2 resolved to `admin-album-file-manager` — finished hours earlier, coordinator long gone — so
a phase reporting on that answer would have written its outcome into a stranger's finished ledger
and messaged a dead name, with **both halves reporting success**. The bug is fixed; the check
stays, because the deployed copy of `swarm.py` can drift from the repo and this failure mode gives
no other warning.

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
| `reap --slug S [--phase N]` | capture the scrollback, then close the windows of finished phases |
| `report --slug S --phase N --status ...` | record an outcome (then send the message) |
| `verify --slug S [--apply]` | re-derive status from git and todos.md |
| `status --slug S` | durable + runtime, merged, for a human |
| `find --plan P \| --task T` | which swarm owns this, and who to report to |
| `track` | make `.workflows/orchestration/` survive the repo's `.gitignore` |
| `selftest` | offline assertions; no git, tmux or network |
