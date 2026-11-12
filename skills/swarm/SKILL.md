---
name: swarm
description: Use when a plan set should run across several Claude Code sessions at once instead of one phase at a time — "orchestrate this plan", "run the phases in parallel", "spawn a session per phase", "resume the orchestration on this laptop", "what's the status of the swarm", "which phases can run now" — or when a phase session finishes and has to report back to the session that is tracking the set.
---

# Swarm

A plan set written by `/analyze` is a DAG: every phase declares `depends_on`, so phases that
share no edge can run at the same time, in their own sessions, in their own tmux windows. This
skill is how a coordinator session drives that, and how a phase session reports back.

Two channels, and keeping them apart is what makes the whole thing work:

- **Messaging is the fast path, and it is local.** `ListAgents` sees sessions on this machine
  (plus cloud ones); `SendMessage` addresses them by name. It is live, cheap, dies with the
  machine, and may not exist in a session at all — so **detection never depends on it**: a
  phase's ledger write is its report, and `swarm.py watch` finds it without any message.
- **Git is the skeleton, and it is global.** The durable ledger is committed, so another laptop
  can pick the set up hours later with nothing but a `git pull`.

Never use one for the other's job. A message is not a record; a commit is not a notification.


## `plan_graph.py` — the write-set gate

`swarm.py waves` schedules from `Depends on`, which says what must *exist* before a phase runs.
It says nothing about what two phases in one wave both *write*. Run this before spawning:

```bash
python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md>     # --json for the machine form
```

Exit codes: **0** clean, **2** a file is written by concurrent phases, **1** the plan could not be
read (no phase table, or a phase plan missing). 1 is deliberately not 0 — a caller that reads 0 as
"nothing collides" would spawn a wave on the strength of an analysis that never ran.

In `--json`, each phase carries `plan_path` and `plan_bytes` (the absolute file it read, `null`
when missing) and each `missing_plans` entry carries `tried`. The `swarm-deck` mod attaches these
to `/analyze-orchestrator` and `/implement` prompts, so take a plan's path from here and never
from a directory listing.

**The exit code is enforced, not advisory.** `/analyze-orchestrator` Step 3b spawns nothing on a
non-zero exit. On **1** it stops outright: there is no collision report to act on, only the
`INCOMPLETE:` line and the `resolved against root:` path the gate prints in that state, and both
belong in the stop. On **2** it remediates by class where it can — per-phase worktrees for ISOLATE
(`git worktree add` plus `swarm.py spawn --cwd`), a dependency edge for ORDER and BLOCK — re-runs
the gate once, and stops only if that did not clear it. A gate that stopped on something the
coordinator could have fixed itself would be the no-waiting rule failing in a new costume.

**A stop here terminates with a report; it never prompts.** No `AskUserQuestion`, no `[y/N]`, no
turn ending on a question — a coordinator that asks stalls the whole set. Nothing is spawned, so
every phase stays `pending` and `--resume <slug>` picks the set up once the cause is fixed.

**`--no-gate` is the escape hatch**, the same flag and meaning `skills/task` uses
(`skills/task/DESIGN.md:159`, `skills/task/task_gh.py:2617`): the gate still runs and still prints,
its exit just stops refusing. It has to be passed on purpose. A session that cannot run the gate at
all does not reach for the flag and does not wait for someone to type it — it derives the write
sets by hand from the phase plans' `## Files` tables, proceeds, and **names what it checked
instead** in the ledger note, which is the ladder at `skills/task/DESIGN.md:238-246` applied to
this gate.

It reads each phase plan's `## Files` table, the same write set `/implement` hands `pusher`, and
classifies every shared path:

| Class | Meaning | Fix |
|---|---|---|
| ISOLATE | ordinary source file, concurrent writers | one worktree per phase; disjoint regions then merge. Check the regions — "same file" is not "same lines" |
| ORDER | regenerated, not merged — a snapshot, a bundle, a committed `resources/_gen/` tree | add an edge so one phase publishes last, and regenerate on the way in rather than merging |
| BLOCK | a binary with no textual form — a database, an image, an archive | serialize, always. A binary merge is a choice of side, and the other side is gone |
| sequential | written in different waves | nothing to do |

Measured against four real plan sets: `journal-versioning` 6 files shared, 1 concurrent
(`commands/lab.py`, phases 2+3+4 in one wave — the collision that was reported by hand);
`sean-gotrade-tracker` 12 shared, 0 concurrent; `strategy-b-ranker` none shared;
`journal-unseen-badges` has no phase table and exits 1.

### Per-repo artifact classes — `.workflows/swarm.json`

Which paths are generated and which are binary is a fact about the REPO, and for two of the
three tiers the repo has already stated it. The gate reads three sources, most specific first:

| Tier | Source | What it can say | Who writes it |
|---|---|---|---|
| 1 | `<repo>/.workflows/swarm.json` | anything, including "this JSON is a snapshot of that database, rebuilt by this command" | you, once per repo |
| 2 | `.gitattributes`, via `git check-attr` | `binary` or `-diff` → BLOCK; `-merge` → ORDER | already there, in any repo that merges carefully |
| 3 | a built-in suffix list | `.sqlite`, `.db`, images, archives, fonts, office documents → BLOCK | nobody; it is the same in every repo |

**Tier 3 holds no project's paths.** It used to: two literal filenames from one project were
shipped to every repo on the machine, so a Hugo site's committed `resources/_gen/` classified as
an ordinary source file (ISOLATE, when it is ORDER) and another project's hand-written file of
the same name classified as generated. Tiers 1 and 2 are where a project's paths belong.
`.svg` is deliberately not in tier 3 — SVG is text and merges.

**Tier 2 is free.** A repo that already marks a generated file `-merge` — because it learned the
hard way that git will happily line-merge 11 MB of generated JSON into a file matching neither
source database — has already told the gate everything it needs, and the gate reads the same
declaration the merge itself will honour. Nothing to write.

#### The file

`<repo>/.workflows/swarm.json`. JSON, because every Python 3 reads it with no dependency
(`tomllib` is 3.11+) and the ledger beside it is JSON too. It sits in `.workflows/` because that
is this ecosystem's persistence layer, next to `orchestration/<slug>/ledger.json`.

```json
{
  "generated": ["resources/_gen/", "web/data/lab.json", "lab.xlsx"],
  "binary":    ["fixtures/*.golden.bin"],
  "regenerate": {
    "web/data/lab.json": {
      "from": "lab/lab.sqlite",
      "run":  "python -m seer_engine lab stage"
    }
  },
  "suite": {
    "setup": [
      "python3 -m venv engine/.venv && engine/.venv/bin/pip install -e engine",
      "cp -al ../../web/node_modules web/node_modules"
    ],
    "steps": [
      "PYTHONPATH=engine/src engine/.venv/bin/python -m pytest engine/tests",
      "cd web && npx tsc --noEmit && npm test"
    ],
    "notes": "node_modules must be HARDLINKED (cp -al), never symlinked: a symlink passes vitest and tsc and then fails `next build` with a misleading \"filesystem root\" error. pytest without PYTHONPATH=engine/src silently tests the MAIN checkout instead of the branch — green, and about the wrong code."
  }
}
```

That example is the real configuration for the project whose two filenames used to be compiled
into the tool. It reproduces that project's classifications exactly — as data.

- **`generated`** → ORDER. **`binary`** → BLOCK. Patterns match three ways: a leading dot with no
  slash is a **suffix** (`.xlsx`); a trailing `/` or `/**` is a **directory** and everything under
  it at any depth, anchored at the root or found anywhere in the tree (`resources/_gen/` matches
  `hugo_docs/resources/_gen/style.css`); anything else is a **path** — exact, matched at a
  directory boundary anywhere in the tree, or an `fnmatch` glob when it carries `*`, `?` or `[`.
- **`regenerate`** is read by the `integrator` agent when a merge conflicts on that path: it takes
  the `from` side and runs `run` instead of resolving the conflict. Its keys also count as
  `generated`, so a path with a recipe is never declared twice — the half you forget is the half
  that silently downgrades ORDER to ISOLATE.
- **`suite`** is read by the `integrator` agent, not by the gate. See below.
- A missing, unreadable or malformed file means "no declaration", never an error. A pre-spawn
  check that refused to run over a stray comma would turn a missing declaration into a stopped
  swarm.
- Inside tier 1, `binary` is checked before `generated`: a path listed in both has been described
  twice, and BLOCK is the side whose cost is unrecoverable rows.
- **Tier 1 beats tier 3, and that is the one place a declaration may lower a severity.** Where two
  *phases* classify one path differently the most severe still wins — there no source has
  authority. Here one does: the repo.
- **Noted discrepancy.** `lab.xlsx` is carried in `generated` (→ ORDER) above, though an xlsx is a
  zip of XML and `.xlsx` is in tier 3's BLOCK list for every other repo. BLOCK is arguably the
  truer class even there. It stays ORDER because that is what the tool did before this file
  existed, and a severity *upgrade* is still a behaviour change to plan sets already written
  against the old classification. Changing it should be a deliberate act, not a side effect of
  moving the value into configuration.
- If a repo's `.gitignore` excludes `.workflows/` broadly, the file still works — the gate reads
  it from disk, not from git — it simply does not travel to another machine. Add
  `!.workflows/swarm.json` to re-include it. (Measured across seven repos on one machine: none of
  them ignored it.)

See what a plan set resolved to:

```bash
python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md> --json \
  | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["config"], indent=2))'
```

The human form prints one line for it too: `artifact classes: declared in
.workflows/swarm.json`, or `baseline + .gitattributes (no .workflows/swarm.json)`.

#### The suite is the repo's, not the tool's

`integrator` runs the FULL suite after merging a wave, and which suite that is cannot be baked
into a global agent: a hardcoded `npm test` waves through a repo whose CI is four bespoke guards
plus a typecheck and a build. It walks a ladder from `.workflows/swarm.json` → `suite.steps` (the
repo saying it outright) down to `suite: none`; **`agents/integrator.md` step 4 owns that ladder**,
so read it there rather than from a copy.

`suite.setup` and `suite.notes` are where a repo's hard-won worktree knowledge goes, because an
integration worktree is not the main checkout and a suite that silently tests the wrong tree is
the worst possible green. The two that bite most often are per-checkout build artifacts a fresh
worktree lacks (hardlink them; a symlinked `node_modules` passes vitest and tsc and then fails
the build) and a runner that resolves imports outside this tree. The example above carries both.

#### Shared test services: one database per checkout

Separate worktrees isolate files, not the services a suite talks to. A repo whose integration
suite runs against one fixed database (a Docker Postgres on a fixed port and name) still shares
it between every checkout that runs the suite at once: the phases of a wave, the integrator's
throwaway worktree, parallel `/task` sessions, the main checkout. Suites truncate tables and
rebuild databases between files, so a concurrent run fails tests that read exactly like the
phase's own regression. A phase that adds a migration also changes the schema under its siblings.

MEASURED 2026-11-11 on mcp-notes `session-fork-awareness`: phases 2 and 5 ran `npm run test:int`
in the same minute against `mcp_notes_test`. Every integration file truncates every table, and
the connector setup runs `DROP DATABASE … WITH (FORCE)`, which kills the other run's connections.

**The rule: the repo's test script keys its databases on the checkout, not on the swarm.**
Keying on the checkout also covers the integrator, `/task` and a person's terminal, which a
`SWARM_PHASE` key would miss. The reference is mcp-notes `scripts/test-int.sh`:

- the main checkout keeps the plain database names, so nothing changes outside worktrees
- a linked worktree uses `<db>_wt_<first 10 hex of sha1(worktree path)>`, created on first run
  and migrated by the suite's own setup. One container serves them all, so nothing is added
  for memory or ports
- the worktree's path is stored as the database comment, and each run drops any `_wt_` database
  whose path no longer exists. Worktrees deleted by `land --step cleanup` clean up after
  themselves on the next run anywhere
- the suffix is exported (`TEST_DB_SUFFIX`) so every helper that names a database appends it,
  and an explicit `TEST_DB_SUFFIX` overrides the derivation

Isolation removes the collision, not the load. Three suites on one disk still took ~30
minutes where one takes ~5, because every truncate waits on a disk sync. Test containers run
with durability off (`fsync=off`, `synchronous_commit=off`, `full_page_writes=off`): they hold
nothing worth a sync, and the same suite runs several times faster.

#### Declaring them: `resources` in `.workflows/swarm.json`

```json
{
  "resources": {
    "pg-test": {
      "match": ["npm run test:int", "scripts/test-int\\.sh"],
      "isolate": "per-checkout",
      "max_concurrent": 2,
      "probe": "docker exec mcp-notes-pg-test psql -U postgres -tAc \"select ...\"",
      "notes": "one database per worktree; capped at 2 to bound disk load"
    }
  }
}
```

- **`match`**: regexes (a pattern that does not compile is taken literally) for the command
  lines that use it.
- **`isolate`**: `per-checkout` when the repo gives each checkout its own copy, as above.
  `none` (the default) when it is genuinely one thing.
- **`max_concurrent`**: how many may hold it at once. A shared resource defaults to 1. An
  isolated one with no cap needs no lease at all; give it a cap only to bound the load.
- **`probe`**: optional. A command whose first output line, when there is one, is what a long
  shell using the resource is waiting on. `watch` prints it as `waiting on DB: ...`.

`swarm.py doctor` reports a resource declared `isolate: none` (every phase that needs it queues
behind the others) and a repo whose test scripts point at a fixed service but declare nothing.

#### Where isolation is impossible: the lease, enforced by the mod

```bash
python3 ~/.claude/skills/swarm/swarm.py lease pg-test -- npm run test:int   # wait, then run
python3 ~/.claude/skills/swarm/swarm.py lease --status                      # holders and queue
python3 ~/.claude/skills/swarm/swarm.py lease --front 12 pg-test            # coordinator: 12 next
```

A FIFO queue per repo and resource, under the repo's common git dir so every worktree shares
it (`lease.py`). A holder holds a `flock` that its command inherits, so the lease lasts exactly
as long as the work and is released by the kernel however it ends, crash included. A waiter
whose process died is dropped. A waiter prints who holds the resource and its place once, and
again only when either changes. The command's exit status comes back unchanged; waiting past
`--wait-max` exits 75 without running it.

**Nobody is asked to use it.** The swarm-deck mod's Bash guard rewrites any command that
matches a resource needing a lease into `swarm.py lease <name> -- ...`, in every session in
the repo: phases, the coordinator, the integrator, a `/task` session, a person's own terminal
session. When the queue is busy it also moves the call to the background, so a wait can never
run into the Bash tool's foreground timeout. The guard fails open: if it breaks, the command
runs as written.

**Home-made waits are refused.** A loop that polls the process table for another session's run
(`until ! pgrep -f vitest; do sleep 5; done`) names no holder, keeps no order, and starts every
waiter at the same instant when it clears. Worse, `pgrep -f` matches the command line of the
loop's own shell, which carries the pattern, so the loop never ends. MEASURED 2026-11-11:
phase 2 hung on exactly that. The guard denies both forms and points at the lease.

**Watching it.** `swarm.py watch` prints `CONTENTION <resource>: p2, p5 (2 of 2 unleased)` when
two or more sessions use one resource and any of them bypassed the lease, and
`QUEUE <resource>` when someone is waiting. Every `SHELL` line carries a label:
`progressing` (the shell's process tree gained CPU or started a real process),
`waiting on DB: ...` (from the resource's `probe`), or `idle-hung` (neither, for
`SWARM_IDLE_AFTER`, default 3m). `sleep`, `pgrep` and `grep` children are not counted as
progress, so a polling loop reads as hung, which is what it is.

## `ears_trace.py` — the criteria trace check

A plan index written since 2026-11-11 carries, under `## Requirements`, an `### Acceptance
Criteria` table: one EARS row per criterion `R{n}.{m}` with its owning phases. Each phase plan
names the criteria it owns on a `**Criteria:**` line and labels every Proof journey
`**J{k}** · traces R…`. This script reads both and reports every criterion with **no owning
phase** or **no tracing journey**:

```bash
python3 ~/.claude/skills/swarm/ears_trace.py <PLAN.md>          # --json for the machine form
python3 ~/.claude/skills/swarm/ears_trace.py <PLAN.md> --fill   # the Journeys column values
```

Exit codes mirror `plan_graph.py`: **0** every criterion owned and traced — or a **legacy** index
with no `### Acceptance Criteria` heading, which has nothing to check; **2** at least one gap;
**1** the index or a phase plan could not be read. Read-only, stdlib only, and it imports nothing
the executors need: `/implement`, `/do` and `swarm.py` never read criteria, so a legacy set runs
exactly as before.

It names five gap kinds: `unowned` (no phase owns the criterion), `untraced` (owned, but no
journey traces it), `unknown_id` (a journey or `**Criteria:**` line names an id the table lacks),
`misassigned` (a plan claims a criterion the index gives to another phase) and `unclaimed` (the
index gives a phase a criterion its `**Criteria:**` line omits). Every reader skips fenced code
blocks, so an index or plan that quotes the format in an example is not read as using it.

`plan-reconciler` runs it and acts on the gaps by the trace rule (its rules 6–7, `/analyze`
Step 8): an owned but untraced criterion is fixed by editing that phase's plan to add a journey;
an unowned one is assigned to a phase; only a criterion no phase can own lands in Open Questions.
`/analyze` Step 9 runs it too, so a one-phase set gets the same check. `--fill` gives the
`P{phase}.J{k}` lists the reconciler (or `/analyze` Step 9 for a one-phase set) writes into the
index's Journeys column. The verifier then reports one verdict per criterion.

`swarm.py` stays criteria-blind on purpose: `parse_index` reads only the `#`-headed phase table,
and a Satisfies cell is R-level — `_ids` folds a stray `R2.1` into `R2` and drops duplicates.
`swarm.py selftest` asserts both against an index carrying the criteria table and a legacy one.

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
- **Nobody asks the user, and nothing waits for one — the merge included.** The coordinator's
  Step 5 lands the set on its own: merge to `main`, apply and verify the production migrations,
  push, delete the worktree and the branch. A set that ends on a branch nobody merged still needs
  a human, which is the wait this workflow removed rather than relocated.

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
  the name still resolves; if it is gone, the ledger write already holds the report — say so
  and stop, rather than sending it to whichever session now holds that name or asking the user
  to relay it.

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
middle: `/analyze` uses it (its Step 11) to start the orchestrator the moment the plan exists,
rather than leaving a pasteable command on screen until somebody wakes up.

```bash
python3 ~/.claude/skills/swarm/swarm.py launch \
    --name orch-<slug> --cwd <worktree> --permission-mode <this session's mode> \
    --prompt "/analyze-orchestrator -f .workflows/plan/<SLUG>_PLAN.md --permission-mode <same>"
```

The mode is passed twice on purpose: once to launch the session on it, once *inside* the prompt
so the orchestrator knows what to hand its own children. A session cannot read its own permission
mode, so an argument is the only way it travels.

### Quota economy: the model

`swarm.py spawn` and `launch` read `~/.claude/swarm-deck/quota.json`, which the swarm-deck mod writes on a
15s clock and on every prompt. A reading under 30 minutes old with `economy: true` makes an unnamed spawn or
launch run `--model sonnet`, and the JSON reports `"model": "sonnet (quota economy N%)"`. An explicit
`--model opus` or `--model fable` is refused with a soft error in that state; `--force-model` overrides it.
A missing, stale or unreadable file means the normal rules. `swarm.py selftest` covers the decision.

### Never launch the same name twice

**The launch's own JSON is the only evidence of whether it worked.** `launch` returns as soon as
the session is spawned and trusted; tmux registers the window *a beat later*. So
`tmux list-windows` run in the same breath — or in the same tool-call block — shows **nothing**,
and reading that as "the launch failed" is wrong.

MEASURED 2026-10-20, on the fold-selector plan set: a launch returned
`{"swarm": true, "launched": ..., "trust": {"trusted": true}}`, an immediate `list-windows`
showed no window, the launch was repeated, and **two Claude sessions ran the same plan in the
same repo** — creating tasks against one `todos.md` and heading for the same files. Each was a
full agent session, so the cost was two complete model budgets, not two shell commands. The owner
caught it; the tooling did not.

`launch` now **refuses** a name that already has a window and tells you this, so the mistake
costs one soft error instead of a session. Rules:

- Got a JSON with `"launched"` and a `window`? **It worked.** Do not verify by window list, and
  do not re-launch.
- Need to confirm by window anyway? Do it in a **separate, later** tool call — never in the block
  that launched.
- A peer reporting a name collision (*"X has become two sessions both named Y"*) is a
  **duplication report**, not a naming note. Act on it immediately.
- `--allow-duplicate` exists for the rare case where two sessions on one name is genuinely
  intended. Reaching for it to get past the refusal is the bug.

If two are already running, recovery is cheap **only while both are still in setup**: compare
panes, keep the one further along, `tmux kill-window` the other, then check for duplicated task
ids in `todos.md` and duplicated `.workflows/plan/*.md` files before continuing.

## The orchestrator loop

```bash
python3 ~/.claude/skills/swarm/swarm.py init  --plan .workflows/plan/<SLUG>_PLAN.md --coordinator orch-<slug>
python3 ~/.claude/skills/swarm/swarm.py waves --slug <slug>      # -> runnable_now: [1, 3]
```

Then, until nothing is runnable and nothing is live:

1. **Spawn every runnable phase, in one round.** `spawn --slug <slug> --phase N` opens a detached
   tmux window (`-d`, so it never steals the window the user is watching) running
   `/implement -f <plan> --phase N`. By default each phase of a wave gets its own worktree, cut
   from the integration branch at the start of the wave, and passed with `--cwd`; without
   `--cwd` it falls back to the set's one shared worktree. `analyze-orchestrator.md` step 4 owns
   that choice and how the worktrees are cut. See **Worktrees and commits**.
2. **Arm the watch before the turn ends:** `swarm.py watch --slug <slug>` under `Monitor`
   (re-armed on expiry until the set lands). It prints a line for each phase whose ledger or git
   derivation moved, each window that closed on unfinished work, and each shell running past
   `MAX_SHELL_SCRIPT_DURATION` (default `5m`). Nothing else starts a coordinator's next turn: a
   finished phase idles rather than exits, so window counts and HEAD do not move when it is done.
   Where `SendMessage` exists, also subscribe to each phase with `notify_when_idle: true` and no
   message — faster, but a session without the tool must not be left with nothing armed.
3. **Collect reports** (`<cross-session-message from="impl-<slug>-pN">`) and act on each `ACT`
   line from the watch **per phase, the moment it lands** — verify, reap, spawn what it
   unblocked — never waiting for the rest of its wave.
4. **Verify before believing.** `swarm.py verify --slug <slug> --apply`. A phase that says it
   landed but whose commit is not on the branch has not landed. Then read the commit's file list
   (`git show --stat --format="" <sha>`) against the plan index's **File ownership** table —
   `verify` proves a commit is on the branch, not that it contains only what its phase owned.
5. **Commit and push the ledger.** Every round, not at the end — this is what bounds a
   cross-machine resume to losing at most one phase.
6. **Reap each finished phase's window as soon as it verifies.** `reap --slug <slug>`, after
   `verify` and never before it — an unverified `done` is a claim, and its window is the
   evidence. It closes every verified `done` phase regardless of its wave-mates.
6b. **Prove the wave, with an agent that did not write it.** `swarm.py verify` proves the
   commits landed, not that the feature works. Dispatch one `verifier` agent per wave with the
   plan index (`agents/verifier.md`; the details are in step 6b of `analyze-orchestrator.md`). It
   returns one verdict per acceptance criterion (`criteria:`), or `criteria: legacy` for an index
   with no criteria table, beside the per-phase verdicts. A `failed` verdict marks that phase
   failed in the ledger, with the repro and its failed criterion ids, and its dependents stall.
   Sets of at most 2 phases may skip it under the small-set rule (step 6b of
   `analyze-orchestrator.md`), recorded as `self-verified (small-set rule)`.
7. **Re-compute.** `waves` again; a finished phase may have unblocked others. Go to 1.

8. **When every phase is `done`, land the set** — `land`, below. The loop does not end with a
   branch somebody has to merge in the morning.

Stop when `runnable_now` is empty. `stalled` lists phases that can never run because a dependency
failed — report those to the user rather than spawning them, and **keep driving whatever is still
runnable**. A failure in one branch of the DAG never pauses the branches it does not touch, and it
is never a reason to ask whether to continue: halting a set on one failed phase turns a partial
night into an empty one.

### Worktrees and commits

Isolation is the default: `analyze-orchestrator.md` step 4 cuts one worktree per phase from the
integration branch, and the `integrator` merges each wave before the next is cut. Phases in one
wave are independent by construction, and the write-set gate proves it. A set run without
`--cwd` shares one worktree instead, and then `git status` there shows other phases'
half-written files beside the running phase's own.

Either way, **committing safely is `pusher`'s job, and its rules live in `agents/pusher.md`**:
an explicit path allowlist, a commit bounded by pathspec (or a private index for a file two
phases share), and no tree-wide git command (`reset --hard`, `clean`, `checkout .`,
`restore .`, bare `stash`, `checkout <branch>`), ever. `/implement` and `/do` report
`modified_files`; `completion-handler` turns that into the allowlist.

What is the coordinator's own:

- **Read each commit's file list against the plan index's File ownership table** before believing
  a phase's report (`git show --stat --format="" <sha>`). In a shared worktree it tells you a
  phase's work landed *somewhere*, not that it landed in its own commit: when a file is missing
  from the phase that owns it, search the whole branch
  (`git log --format=%h <branch> | while read c; do git show --stat --format="" $c | grep -q <path> && echo $c; done`)
  **before** concluding it was lost. A phase told "your work vanished" re-implements work that is
  already on the branch. A wrong commit message is cosmetic; never rewrite pushed history to fix
  one.
- **If a tree-wide command has already been run, preserve before you repair.** `git reflog` names
  every commit the reset orphaned; tag each one at once —
  `git tag -f rescue/reset-casualty-<sha> <sha>` — because orphaned commits are gc-able and tags
  make them permanent. Then diff each tag against the branch, and tell the owning phase what to
  recover. Do not restore a peer's files yourself. MEASURED 2026-10-08 on `gotrade-fee-rebuild`:
  one phase's `git reset --hard` destroyed another's twelve finished, uncommitted files, and the
  tags were how the rest was recovered.

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

## Landing the set

**Land only verified work.** Every phase needs a wave verdict of `verified`, `inconclusive`
(with its reason carried into the landing report), `self-verified (small-set rule)`, or
`self-verified (quota economy, N%)`. A phase whose wave verdict is `failed`, and
not re-verified after a fix, keeps the set off `main`. Green tests do not mean the feature works.

The loop above ends with N phases on a branch, which is worth nothing until it is on `main`.
`land` is the mechanical half of getting it there — and it is **four steps rather than one**,
because the two things that need a model sit *between* them:

```bash
S=~/.claude/skills/swarm/swarm.py
python3 $S land --slug <slug> --step check     # is this landable? -- derived from git
python3 $S land --slug <slug> --step merge     # --no-ff, into a throwaway worktree of origin/main
#   -> resolve any conflicts yourself, then apply and VERIFY the production migrations
python3 $S land --slug <slug> --step push      # push it, re-merging a base that moved
python3 $S land --slug <slug> --step cleanup   # delete both worktrees and the branch
```

**`check` derives, it does not read the ledger.** A phase recorded `done` whose commit is not on
the branch blocks the landing, which is the same distrust `verify` exists for, applied to the one
irreversible step.

**`merge` never touches the shared main checkout.** It cuts `land-<slug>` from `origin/main` —
the remote-tracking ref, deliberately, because the local `main` in a repo whose work happens in
worktrees is usually behind — merges `--no-ff`, and on conflict leaves the merge in place with the
conflicted paths listed. Resolve them on the precedence ladder, `git add`, `git commit --no-edit`,
and re-run `--step push`; or `git merge --abort`, which leaves the branch exactly as it was.
`merge` also reports the branch's **migration collisions**: two branches cut from one base can
each mint a `0004`, which is not a file conflict and which a migrator that only applies entries
newer than the last applied row will silently skip. Regenerate from the merged schema — never
rename the file.

**Migrations run between `merge` and `push`, and that order is the whole point.** Production
deploys from `main`, so code that arrives ahead of its schema is a runtime error on the first
request. Apply from the land worktree, verify the objects exist by querying for them rather than
trusting the migrator's exit code, and only then push. A migration that will not apply stops the
landing with `main` untouched and the branch intact — which is why nothing was pushed yet.

**`push` also catches the main checkout's own `main` up, and that is not cosmetic.** The push goes
out from the throwaway land worktree as `HEAD:main`, so the shared checkout's `main` ref does not
move with it — and the coordinator's close-out commit is made *there*, on the stale tip. MEASURED
2026-10-02 on `media-parity-compact-pager`: that close-out was rejected non-fast-forward, correctly,
and the obvious reflex (`--force`) would have reverted the whole merge. A `git fetch` first does
not save you either: by then the commit's PARENT is already wrong. `push` now reports what it did
under `local_base`, fast-forward only — it moves the ref when nothing is checked out on it, lets
git's own guard refuse a dirty tree, and leaves the branch alone when another worktree holds it or
when it carries local commits of its own. If `local_base` says it changed nothing, rebase the
close-out onto `origin/main` rather than forcing it.

**`cleanup` is the destructive step and it is guarded twice.** It refuses unless `git merge-base
--is-ancestor <branch> <base>` proves the work is already in the base, so every earlier stop
leaves the branch standing *by construction* rather than by someone remembering to check. And it
refuses when the caller's cwd is inside a worktree it would delete — the coordinator's own cwd is
usually the set's worktree, so `cd` to the main checkout first. `--keep-remote` leaves
`origin/<branch>` alone when an open pull request still needs it.

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
chatty by restricting it to five message kinds — everything else goes to the coordinator.

| Kind | When | Body |
|---|---|---|
| `DONE` | a phase has landed | phase, TaskID, commit sha, one line on what changed |
| `READY` | an Interface Contract item now exists | the symbol or file a dependent was waiting on |
| `NEED` | before assuming a dependency landed | the contract item, and which phase owns it |
| `WARN` | about to delete a worktree or branch | the path, and what the recipient should do |
| `CLAIM` | **before** taking a step a live peer owns | which step, which set, and that you are doing it now |

Three hard rules. **A message states a fact; it never delegates work** — "I deleted `SortRows`"
is a mesh message, "please delete `SortRows` for me" is not, and asking a peer to do what your own
permissions denied is permission laundering. **Never ask a peer for a decision or block on a
reply** — decide on the ladder, or report. **`WARN` before destroying shared ground**: a session
removing a worktree tells every peer whose cwd lives inside it, because their working directory
is about to stop existing.

**`CLAIM` goes before the act, and its whole value is the ordering.** The step this exists for is
the **merge**: a set's coordinator owns it (its Step 5), so any other session taking it — because
the coordinator is gone, or because a peer resumed the set on another machine — must say so
*first*. Every coordinator merges its own set unattended now, so this is a live collision rather
than a courtesy. MEASURED 2026-09-05: a session merged a completed set and told the coordinator afterwards.
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

The ledger write is the report; a message, where one can be sent, only makes it arrive sooner.

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

then, where the session has a `SendMessage` tool, message the `coordinator` that `find`
returned — after confirming that name is still in `ListAgents`. `find` returns
`coordinator_session_id` for exactly this check. The ledger write is the report: the coordinator's
`swarm.py watch` and the `swarm-deck` wake both detect it without any message, so a session with no
`SendMessage` tool, or whose coordinator is gone, says the outcome is in the ledger and stops. It
never asks the user to relay it, and never delivers a phase report to a stranger.

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

**The index answers too, and it has to.** `--plan` accepts either a phase body or the set's
own index — the `PLAN.md` that `spawn` writes onto every child's command line
(`/implement -f <...>/orchestration/<slug>/PLAN.md --phase 3`). FIXED 2026-09-25, having been
the mirror image of the basename bug above: too *tight* a match, answering `swarm: false` for
the one path every child is guaranteed to hold. Since a set's last phase auto-lands
(`completion-handler` step 5a) when no coordinator owns it, that answer sent the final phase to merge a set its live
coordinator was already landing — two merges of one set on `main`, caught only because the
coordinator warned the child by hand. An index hit names the set but not which phase you are,
so it returns `"phase": null` with a `phase_note`; pass `--phase N` — your own number, from
your `/implement` invocation — to get the same answer a phase body gives. Either way
`swarm: true` is the load-bearing half: **it means this set has a coordinator, so do not land
it yourself.**

## Commands

| | |
|---|---|
| `init --plan PATH [--coordinator NAME]` | build the ledger from a plan index; re-running keeps recorded outcomes |
| `waves --slug S` | the DAG in rounds, plus `runnable_now` and `stalled` |
| `spawn --slug S --phase N` | launch one phase in its own named session; `--dry-run` prints the argv |
| `reap --slug S [--phase N]` | capture the scrollback, then close the windows of finished phases |
| `report --slug S --phase N --status ...` | record an outcome -- this is the report; a message, where `SendMessage` exists, only speeds it up |
| `verify --slug S [--apply]` | re-derive status from git and todos.md; never resets a phase whose window is live |
| `doctor` | before a set: the swarm-deck mod is configured, no deny list hides `SendMessage`/`Monitor`/`PushNotification`/notes tools, a Claude Code shell is quiet on `cd` (rebuilt snapshot); exit 2 lists each problem with its fix |
| `watch --slug S [--max-shell 5m] [--once]` | for the coordinator's `Monitor`: one line per phase that finished, window that closed on unfinished work, or shell past `MAX_SHELL_SCRIPT_DURATION`; exits when the set is terminal |
| `land --slug S --step check\|merge\|push\|cleanup` | merge the set into `main`, push it, delete the worktrees and the branch |
| `status --slug S` | durable + runtime, merged, for a human |
| `find --plan P \| --task T [--phase N]` | which swarm owns this, and who to report to. `P` may be a phase body, the set's index, OR /implement's adopted copy `{TaskID}.md` (followed through its `Source:` header) |
| `track` | make `.workflows/orchestration/` survive the repo's `.gitignore` |
| `selftest` | offline assertions; no git, tmux or network |
