# Implement Command

Execute the plan `/analyze` wrote. **`/implement` does not plan** — it creates the task
bookkeeping, applies the code, and hands off. Every implementation plan in this workflow has
exactly one author, and it is `/analyze`.

## Autonomy: this command never waits for a human

A plan is handed to `/implement` to be **applied**, not to be discussed. From `-f` to a pushed
commit the session decides everything itself: what an ambiguous step meant, which of two
contradicting sentences in the plan wins, what to do when a verification fails in a way the
rollback section never anticipated. It is written to run at 1am inside a swarm with nobody awake,
because that is when it runs.

The rule that makes that true:

> **Never end a turn with a question this command needs answered to continue.**

Not "ask sparingly" — never. The arithmetic is one-sided:

| | What it costs |
|---|---|
| A decision that turns out wrong | one follow-up commit, or one `/analyze` re-plan — both of which this workflow already handles by design |
| A question asked into an empty room | every hour until someone wakes up, and no code at all |

MEASURED on `nina-character-tuning`: phase 2 found the plan's invariant 2 and its ladder prose
contradicting each other, asked with `AskUserQuestion`, and held the prompt for **eight hours**.
Phases 3 and 4 both depend on 2, so a six-phase set built nothing overnight — and the answer that
finally arrived was `invariant 2 wins`, which is the first rung of the ladder below and was
derivable from the plan in under a minute.

So, concretely:

- **Do not use `AskUserQuestion`**, and do not end a message with "which should I do?",
  "shall I proceed?", `Continue anyway? [y/N]`, or a list of options for someone to pick from.
- **Do not ask permission for what this command already says to do** — creating the tasks,
  applying the phase, running verification, dispatching `completion-handler`, `readme-updater`
  and `pusher`. Running `/implement` *is* the authorisation for all of it.
- **Keep the shell unattended too.** No interactive git (`GIT_EDITOR=true`, `--no-edit`, never
  `-i`), no pager (`--no-pager`), and pass the yes-flag to anything that would otherwise prompt.
  A command blocked on stdin is the same outage with no question attached.
- **Decide with the ladder in [Deciding Without Asking](#deciding-without-asking), then write the
  decision down.** A recorded decision is reviewable over breakfast and costs one commit to
  overturn; a waiting prompt is reviewable never.

The user can interrupt at any moment, and that is their steering: always available, always
obeyed. What is removed is this command's *requirement* for it.

**Stopping is allowed; blocking is not.** A stop ends the session cleanly — the task left in a
truthful state, the reason printed in a Next block, the swarm told (Step 4b), the work on disk
surviving. A block is a live session holding an unanswered question and building nothing. Every
terminating branch in this file is a stop; there are no blocks.

## Usage

```bash
/implement -f <path>/<SLUG>_PLAN.md [--phase N] [--all] [-note <note>]
```

**Arguments:**
- `-f` — the plan index written by `/analyze` (required). Pass the **path**, not a bare
  filename: `/analyze` files the index under `.workflows/plan/` (older sets: `docs/plans/` or
  the repo root), and every path you report downstream must be the one you were handed here.
- `--phase N` — implement phase N instead of the next unfinished one
- `--all` — continue through every remaining phase in this session
- `-note` — extra context for implementation; it never overrides the plan

**Examples:**
```bash
/implement -f .workflows/plan/PURGE_DIRECT_STREAMING_TOOL_PLAN.md
/implement -f .workflows/plan/FIX_CITATION_AGGREGATION_PLAN.md --phase 2
/implement -f docs/plans/FIX_CITATION_AGGREGATION_PLAN.md --phase 2   # a set planned before 2026-11-04
```

### Wrong input

Given a `*_code_analyzer.md`, or anything else that is not a plan index, **stop**:

```
✗ Not a plan: {file}
  /implement executes plans; it does not write them.
  Run /analyze to produce <SLUG>_PLAN.md, then re-run with the path it reports.
```

An analysis document describes the code. It is not a plan, and filling the gap here is what
this command deliberately no longer does.

---

## Step 1: Verify the Worktree

The plan index names the worktree and branch it was written against. Compare with
`git rev-parse --show-toplevel` and `git branch --show-current`.

- Match → proceed.
- Different tree → **STOP** and print `cd <worktree path>`. Plans quote code as it exists on
  that branch; applying them elsewhere silently produces conflicts.
- The index says `none` (planned with `--no-worktree`) → check you are on the branch it names.
  Different branch → stop and say so.

## Step 2: Read the Plan Index

Extract: slug, the **Why** section, the **Requirements** table, the invariants, the phase table
(number, title, satisfies, package, depends-on, difficulty, plan file, TaskID, card), and
**Decisions**, and **Open Questions**.

**`## Decisions` is inherited, not re-litigated.** Each row is a fork `/analyze` already settled
with the rung that settled it. Read them, apply them, and do not reopen one because the losing
side reads better in the phase plan — that is the reconciliation talking, and it saw all N phases
at once.

**If Open Questions is non-empty, resolve every item yourself before implementing** — with the
precedence ladder in **Deciding Without Asking**, one printed line per item, before the first
edit. After a current `/analyze` run that section holds only forks where every branch is
irreversible, which is the **Undecidable** stop rather than a question; an older plan set may have
ordinary contradictions parked there, and those get decided. Either way this session is the only
decider awake: implementing over an item silently would be guessing, while deciding it on a stated
rung and recording the choice is not.

Read only the index here. Phase plans are read in Step 4, one at a time, so the main context
never holds plans for phases it is not implementing.

**Then name the session**, from the slug the index just gave you — and from the phase, if the
command line already names one:

```bash
# --phase N was passed: the phase is known now, so say it now
python3 ~/.claude/skills/task/session.py rename "impl-<slug>-p<N>" --no-widen
# no --phase, or --all: the slug is all that is known here
python3 ~/.claude/skills/task/session.py rename "impl-<slug>" --no-widen
```

**`--no-widen` is not optional, and neither is naming the phase when `--phase` gave you one.**
A phase session in a swarm is launched as `claude -n impl-<slug>-p<N>`, so it already answers on
the address its coordinator recorded, *before* this command's first line runs. Renaming it to
`impl-<slug>` here throws the phase number away and hands every phase of the set one address:
between this step and Step 4 they are indistinguishable, a report arrives as
`from="impl-<slug>"` with nothing to say which phase sent it, and a coordinator that writes to
the name it recorded finds nothing there. MEASURED on a seven-phase set: four sessions passed
through the bare `impl-admin-album-file-manager`, and phase 2's — whose Step 4 sharpening never
landed — stayed on it, while `.runtime.json` still addressed phase 2 as
`impl-admin-album-file-manager-p2`. `--no-widen` refuses a rename that is the current name minus
a suffix, so the launch name survives this step even when the branch above picks the bare one.

Five terminals open on one repo all carry the same derived name — `agentic-8f`, `agentic-d4` —
which says which repo and not which plan, so the right window is found by reading scrollback and
`/resume` a week later offers a row of near-identical titles. The slug is the one label that
separates them. It is the same rename `/rename` performs: it reaches the running process over the
session's own socket, so the tab title, the `/resume` row and the name peers address all follow
together — **and the tmux window too**, which under tmux is the only one of those the user can
actually see, because the status line covers the terminal's tab title. `--no-tmux` skips that
half.

**Never let it stop anything.** It cannot fail by design (no socket, no tmux, a session started
some other way → `renamed: false` with a reason, exit 0), and a plan is not worth losing over the
name of a window.

**Shorten the slug only if you named yourself.** Three or four words is right when this session
picked its own name — the cap is 60 characters and a tmux window is narrow. But a session launched
by `swarm.py spawn` was given its name by `claude -n` before it booted, and that name is **two
records, not a preference**: the address the coordinator wrote into `.runtime.json`, and the tmux
window name `reap` matches against before closing anything. Shortening it breaks both.

MEASURED 2026-09-05: a phase launched as `impl-tabbar-new-tab-composer-seam-p2` renamed itself to
`impl-tabbar-seam-p2` on boot, following this very instruction. `--no-widen` allowed it — the new
name still carries `-p2`, so it is not the current name minus a suffix — but `reap` then refused
that window permanently, because its identity check is "does the window's name still equal the
name we spawned it under", and **`--force` does not override it**: `--force` short-circuits the
ledger-status gate, while the name check runs afterwards, on purpose, since a tmux server that
restarted hands `@7` to a stranger's window. The set's coordinator had to verify the pane's
identity by hand and rename the window back before its scrollback could be captured.

So: if the session already has a name when this step runs, **pass it back verbatim**. The rename
is then a no-op that reports `renamed: false`, which is the correct outcome — the launch name was
already right.

## Step 3: Create the Tasks (Subagent — required)

Only on the first run against this plan. Detect a re-run from the index's TaskID column, or by
searching the slug across `todos.md` files; if the tasks exist, skip to Step 4.

Dispatch one subagent to create every phase's task. For each phase:

- Package path = the phase's **Package** column. If `{pkg}/.workflows/todos.md` is missing,
  run `/update-todos {pkg} --init` rather than stopping — a plan can span packages that were
  never tracked.
- Mint a TaskID from that package's own counter: `P{Priority}-{PackageCode}-{4CharID}`.
- Task entry:
  ```markdown
  - [ ] **{TaskID}** Phase {N}: {title}
    - **Difficulty**: {from the plan index}
    - **Type**: {Bug|Feature|Update|Refactor}
    - **Context**: {phase Owns + Exit criteria}
    - **Status**: {in_progress for the first phase, blocked for the rest}
    - **Plan Set**: `{the -f path}` (phase {N} of {total})
    - **Satisfies**: {R id(s)} — {that requirement's text from the index's R table}{ · criteria: the phase plan's **Criteria:** ids, e.g. `R2.1, R2.2` — leave this part out when the plan has no **Criteria:** line, as in a set planned before EARS criteria}
    - **Depends on**: {TaskIDs of the phases this one requires}
    - **Plan**: `.workflows/plan/{TaskID}.md`
    - **Card**: {the index's Card column, e.g. `owner/repo#13`} — omit the line if it is `—`
  ```
- **Adopt the plan file — never rewrite it.** Copy `.workflows/plan/{slug}/phase-{N}.md` to
  `{pkg}/.workflows/plan/{TaskID}.md`, prepending:
  ```markdown
  > Adopted from `{the -f path}` phase {N}. Source: `.workflows/plan/{slug}/phase-{N}.md`.
  > Written and reconciled by /analyze — edit the source, not this copy.
  ```
- Write the TaskID back into the index's **TaskID** column so a later session can map phases
  to tasks.

Return the phase → TaskID → plan path → package mapping. This subagent writes bookkeeping only;
it must not alter the plan content it copies.

## Step 4: Implement One Phase (Main Context)

Pick the phase: `--phase N` if given, else the lowest-numbered phase whose task is not complete.
Refuse a phase whose `Depends on` tasks are incomplete — name the blocker.

**Refuse an explicit `--phase N` whose task is already complete**, and name the phase that is
actually next. `/analyze` hands the user `--phase 1` to paste, so that flag will be re-pasted;
applying a landed phase's plan to a tree that already contains it produces conflicts that look
like drift.

Then sharpen the session's name with the phase you just picked, so two terminals on the same plan
set are still distinguishable:

```bash
python3 ~/.claude/skills/task/session.py rename "impl-<slug>-p<N>" --no-widen
```

A second rename costs nothing — it is idempotent, and reports `renamed: false` when the name is
already right, which is exactly what it reports when `--phase N` let Step 2 name the phase
already. This step is what names the phase when the phase was *derived* here rather than
passed on the command line — where `--phase N` gave one, Step 2 has already used it, and waiting
until here would leave the session sharing a bare address for the whole of Step 3. **With
`--all` skip it:** that session works every remaining phase, so a phase number in its name would
be stale for most of its life; `impl-<slug>` from Step 2 stays — unless the session was launched
with a phase in its name, in which case `--no-widen` kept that, and a slightly stale unique
address beats an accurate shared one.

Read that phase's plan file and apply its steps in order. The code blocks are complete by
construction; use them. If a context block beginning `swarm-deck: the plan set for /implement`
is attached to the prompt, it names that file by absolute path (resolved by `plan_graph.py`
before the turn): read it there, and do not list or search for it. A phase it reports
`MISSING` is missing; say so with the path it tried rather than hunting.

`/do` reaches the same plan the same way — its **adopted path** (Step 1b) routes a task carrying
a `**Plan**:` line straight to its own main context, with no subagent between the plan and the
code. Keep the two
aligned: this command hands off with `/do {TaskID of phase N+1}`, so a phase planned here and
executed there has to be read identically in both.

**If the code has drifted from what the plan quotes:**
- Small drift (a moved line, a renamed local, an added field the plan doesn't touch) → follow
  the plan's intent, note the drift, carry it into the completion report.
- Large drift (the function is gone, the signature changed, the file was restructured) →
  **stop**. Report what drifted and say `Re-run /analyze to re-plan against the current tree.`
  Improvising a replacement plan here is exactly the thing this command doesn't do.
- Genuinely balanced between the two → **treat it as large and stop**. Re-planning costs one
  `/analyze`; applying a plan to a tree it no longer describes costs a wrong change with the
  plan's authority behind it.

Run the plan's **Verification** commands before reporting success. A failing build or test is a
failure, not a caveat.

**Then run the plan's Proof journeys.** Tests are the cheap check. Proof is the real artifact
doing the thing: follow the harness the Proof names (`.claude/skills/verify-*/SKILL.md`: launch,
doctor, drive, cleanup) and run every journey it lists. Keep the evidence paths. A journey that
fails is a failure exactly like a red test: fix the code, never the journey. A journey you
cannot run (missing prerequisite, no harness, billed path the plan forbids) is `inconclusive`
with its reason. Never report it as passed. A plan written before Proof existed (it has a
`Manual check` line instead) gets the same treatment: if the repo has a harness, turn the manual
check into a journey and run it; if not, report it `inconclusive`.

**Quota economy:** if the swarm-deck context block says `Weekly quota N% used ... ECONOMY MODE`,
run the Proof once, on the cheapest journeys that cover the exit criteria; record paid or live
journeys (real model calls, `test:live*`) as `inconclusive (quota economy)`, re-run only a journey
that failed, and dispatch no extra review or research agents. No block means the normal rules;
never measure usage yourself.

This is your own check of your own work, and it is the weaker witness. In a swarm, the
coordinator sends a separate `verifier` agent after the wave. Solo, `completion-handler` sends
one before it lands the set. Your evidence makes their pass cheaper, and replaces it only under
the small-set rule, so report honestly whether your Proof passed in one go.

Then dispatch **`completion-handler`**.

**`modified_files` must be complete and must be yours.** It becomes the `paths` allowlist that
`pusher` commits, so a file missing from it is left out of the commit, and a file wrongly in it is
a peer's work committed under your name. When this phase belongs to a plan set, other phases may
be running **in this same worktree right now** — `git status` shows their half-written files
alongside yours, and the plan index's **File ownership** table is what tells the two apart. List
what you changed, not what is dirty. A file you changed that the table gives to another phase
too goes in `shared_paths` as well, and `pusher` commits it through a private index. If that
happens twice in one set, say so to the coordinator: the split is wrong.

**This session runs no commit, reset, stash or checkout.** `pusher` makes the commit and holds
every shared-worktree git rule (`agents/pusher.md`). If you find your work committed under a
peer's message, **it is not lost and you must not re-implement it** — find it on the branch
(`git log --format=%h <branch> | while read c; do git show --stat --format="" $c | grep -q <your
path> && echo $c; done`), report it, and move on; nobody rewrites pushed history over a wrong
message. If a tree-wide command (`git reset --hard` and its kin) has already been run in a shared
worktree, **stop and tell the coordinator immediately** — orphaned commits are recoverable from
`git reflog` only until garbage collection, and the coordinator tags them.

**Three checks before the report, because the wave moved while you worked.** Everything above
protects peers from this phase; these protect this phase from them. All three run *before* the
`completion_report` — `pusher` commits and pushes straight from it, so a stale green in that
report is on the branch before anyone reads it.

1. **Catch up to what landed.** `git fetch origin`, then bring your branch onto it:
   `git rebase origin/<branch>` for ordinary files. **Never `--autostash`** — it rewrites the
   working tree under peers who are mid-write. And never rebase a branch carrying a **shared
   binary** (a committed database, a generated snapshot): the replay puts your stale copy back
   over the live one peers are still writing. For those, `git merge --ff-only origin/<branch>`,
   which leaves dirty files alone and refuses instead of rewriting.
2. **Then re-run the test files your change touches** — the files, not the suite. A green
   measured before a peer phase landed is not a green. The plan's own "breaks N tests and nothing
   else" was measured at the base commit, and a peer landing first adds breakages the plan never
   saw. If the re-run is red because of what landed, that is drift: report it. Do not patch a
   peer's file to get your green back.
3. **A failure a peer reports is unverified until you reproduce it.** Re-run the named file
   alone, in this session, before believing it or acting on it — a peer's concurrent run can
   redden tests that read exactly like your own regression, and a report written mid-wave
   describes a tree that no longer exists. Reproduce first, then fix. Never fix from someone
   else's transcript. A test suite that shares a service with peers is queued for you: the
   swarm-deck mod runs a command that matches a resource in `.workflows/swarm.json` under
   `swarm.py lease`, and the wait is a line in its output saying who holds it. **Never write
   your own wait for a peer's run** (`until ! pgrep -f vitest ...`). `pgrep -f` matches the
   command line of your own shell, so the loop never ends, and the mod refuses it.

```yaml
completion_report:
  task_id: "{TaskID}"
  package_path: "{pkg}"
  method: "/implement"
  status: "success"
  modified_files: ["{file}"]
  shared_paths: ["{file}"]          # only files the File ownership table also gives a peer
  proof: {result: "verified-first-pass | verified-after-fix | inconclusive", journeys: N, evidence: "{dir}"}
  drift_notes: ["{if any}"]
  decisions: ["{question} → {choice} ({the rung that decided it})"]
plan_set:
  file: "{the -f path, verbatim — completion-handler reopens the index by it}"
  phase: N
  next_task_id: "{TaskID of phase N+1, or empty}"
```

It flips the task to completed, ticks the phase in the index, unblocks the next phase's task,
chains `readme-updater` and `pusher`, and on the set's last phase lands it (Step 5a). The main
context performs no documentation updates, and its only git is check 1's catch-up above.

## Step 4b: Report to the Swarm (only if there is one)

A phase run by an orchestrator has a session waiting on it. The ledger write is the report; a
message, where one can be sent, only makes it arrive sooner.

```bash
python3 ~/.claude/skills/swarm/swarm.py find --plan <the phase plan just implemented> --task <its TaskID>
```

Either path works — the adopted copy `{pkg}/.workflows/plan/{TaskID}.md` leads `find` back to
its phase body through the `Source:` header — but pass both: the ledger is built before TaskIDs
are minted, so `--task` alone can miss, and a miss here is a phase that never reports.

`{"swarm": false, ...}` means this task belongs to no swarm — say nothing, do nothing, done. Every
`swarm.py` read exits 0 when there is no ledger, so an ordinary task is never affected by any of
this.

Otherwise `find` returns the `slug`, the `phase`, the `coordinator` to address and the `peers`:

```bash
python3 ~/.claude/skills/swarm/swarm.py report --slug <slug> --phase <N> \
    --status done --commit <sha from pusher> --task <TaskID> --note "<one line>; proof: <verified-first-pass | verified-after-fix | inconclusive> <evidence dir>"
```

**If the ladder produced any decision, the `--note` is where it goes** — a later phase planned
against the sentence you overruled, and the ledger is the only place it will look. One clause is
enough: `anger ceiling off 0→4 per invariant 2`. A phase that failed reports `--status failed`
with the reason the same way.

Then, **only where this session has a `SendMessage` tool and the coordinator's name is still in
`ListAgents`** (names are reused, so a stale one can reach an unrelated session), message it:
`DONE` or `FAILED`, the TaskID, the commit, one line on what changed. Otherwise say in one line
that the outcome is in the ledger and stop — **never ask the user to relay it**. The coordinator
detects a finished phase from the ledger (`swarm.py watch`) and the `swarm-deck` mod wakes it.
Peer messages follow the mesh rules in `skills/swarm/SKILL.md`: a message states a fact
(`READY`, `NEED`, `WARN`) and never delegates work.

This step runs **after** `pusher`, because the commit sha is part of the report and an unpushed
commit is not something another machine can resume from.

---

## Step 5: Stop or Continue

**Default: stop after one phase.** Print the hand-off block and let the user start a fresh
session — a phase is exactly the unit that fits in one clean context, and phase N+1's plan was
written assuming phase N had landed and been reviewed.

Every terminating branch below ends with a Next block, including the failures: a session that
stops without saying what to run next has handed the user a puzzle. The command sits alone on its
own line so it can be selected and pasted, and nothing follows it on that line — a trailing
`# comment` is read as arguments to the slash command. `/do` and `/analyze` print the same shape.

**With `--all`:** loop back to Step 4 for the next phase in the same session. Say once, up
front, that context grows across phases. When the loop ends, print the **All phases done** block
— the same terminal hand-off a one-phase-at-a-time run reaches.

A single-phase plan finishes in one run either way, and it is the common case Step 5a exists for:
`/analyze` Step 11 launches exactly this session for it, and nobody else is coming to merge.

## Step 5a: Landing (only when there is no next phase)

When this was the plan set's last phase — the only one, or `--all` just finished the loop —
`completion-handler` lands it in the same dispatch: it checks for a swarm coordinator, runs the
set's independent verification (the `verifier`, or a recorded skip under the small-set rule or
quota economy), merges in a throwaway worktree, pushes and cleans up. **This session never
merges.** Landing lives in one place so it cannot happen twice. Act on its `landing.status`:

- `landed` → print the **landed** block, with its `verification` line and every
  `inconclusive` item.
- `swarm` → print the **swarm-tracked** block. The coordinator verifies and lands the set.
- `nothing` → a `--no-worktree` plan on `main`; print the **landed** block without a merge line.
- `verifier_failed` → **fix it here.** Its `failed_criteria` say which requirement broke and its
  `repro` lines reproduce it. Fix the code (never the journey), re-run the failing journeys
  yourself, then dispatch `completion-handler` again with the fix's `modified_files`, the same
  `plan_set` and `reverify: true`. It commits the fix and verifies once more.
- `failed` → print the **Landing failed** block with its `reason` or both verdicts. Nothing
  destructive has happened: `main` is unmodified and the branch and worktree stand.

A merge conflict where every resolution is irreversible comes back as `failed` with the fork
named; print the **Undecidable** block for it instead.

---

## Termination

**Phase done, more remaining:**
```
✓ Phase {N}/{total} complete: {TaskID} — {title}

Files modified: {count}
Plan: {pkg}/.workflows/plan/{TaskID}.md
Branch: {branch}
Session: impl-{slug}-p{N}
Verification: {command} — passed
Proof: {verified-first-pass | verified-after-fix | failed | inconclusive} — {n} journeys, evidence {dir}
  {one line per claim: claim → evidence file, or the inconclusive reason}

Remaining: phase {N+1} ({TaskID}), phase {N+2} ({TaskID})

Next — phase {N+1} of {total}, in a new session:

  cd {worktree}
  /do {TaskID of phase N+1}
```

**All phases done — landed (completion-handler landed it):**
```
✓ Plan complete — {SLUG}_PLAN.md ({total} phase(s))
  Verification: {verified | inconclusive: {ids and reasons} | self-verified (small-set rule) | self-verified (quota economy, N%) | skipped (nothing observable changed)}
  Merged {branch} into {base} @ {merged commit sha}, pushed.
  Worktree and branch {branch} deleted.

Next — nothing: the plan set is on {base}, merged, and cleaned up.
```

**All phases done — swarm-tracked (coordinator lands it):**
```
✓ Phase {N}/{total} complete: {TaskID} — {title} (last phase of this set)
  Reported done to swarm coordinator {coordinator} in Step 4b.
  Landing the set is the coordinator's job (analyze-orchestrator Step 5) — this session
  does not merge, push, or delete anything.

Next — nothing for this session.
```

**Landing failed (verifier failed twice, push rejected after retry):**
```
✗ Phase {N}/{total} implemented, but not landed: {verifier failed R2.1, R2.3 twice | what git said}
  main/{base} is unmodified. {branch} and its worktree are intact.
  Evidence: {dir}   Land worktree left at: {land worktree path}

Next — {fix the failing criteria | resolve the push rejection} and finish landing, in a new
session:

  cd {land worktree path, or the set's worktree}
  {git command that still needs to run, or /do {TaskID of the last phase}}
```

**Blocked:**
```
✗ Phase {N} ({TaskID}) depends on {TaskID}, which is not complete.

Next — the blocking phase, in a new session:

  cd {worktree}
  /do {blocking TaskID}
```

**Drifted:**
```
✗ Phase {N} plan does not match the current tree.
  {what drifted}

Next — re-plan against the current tree, in a new session:

  cd {worktree}
  /analyze {plan set title} — re-planning {SLUG}_PLAN.md, {what drifted}
```
`/analyze` takes free-form prose, so the drift note travels with the command instead of being
something the user has to remember to retype.

**Undecidable** (rare — every branch irreversible, see *Deciding Without Asking*):
```
✗ Phase {N} stopped at an irreversible fork. Not asking; reporting.
  The fork: {one line}
  Ladder consulted: invariants, exit criteria, code blocks, Why — none of them decide it.
  Every branch is irreversible: {why}
  Landed and pushed: {commit(s), or "nothing"}
  Swarm: reported failed to {coordinator}

Next — decide it and re-plan against the current tree, in a new session:

  cd {worktree}
  /analyze {plan set title} — re-planning {SLUG}_PLAN.md phase {N}: {the fork}
```
This is the only branch that ends without either a commit or a drift note, and it is not a
question: the session is over when it prints, and the swarm has been told.

**Then push one notification** where the `PushNotification` tool exists, and only for the outcomes
nobody else will announce: **landed** (`<SLUG> landed: <total> phase(s), <base> @ <sha>`),
**landing failed**, **drifted**, and **undecidable** — each as the block's first line, under 200
characters. Never for a phase with more to come, and never when this phase is swarm-tracked: its
coordinator owns the set's one notification (`analyze-orchestrator.md` Termination). This session
usually runs unwatched in a tmux window `/analyze` opened, so the termination block is read by
whoever looks; the notification is for whoever is away, and a stop nobody hears about is a stall.

---

## Deciding Without Asking

Every case below used to be a question. All of them are now decisions this session makes,
states, and records:

- the plan index has unresolved **Open Questions**
- the plan's intent is ambiguous at a specific step
- **two parts of the plan contradict each other** — the eight-hour case above
- applying a step would touch code outside the phase's stated scope
- verification fails for a reason the plan's rollback section does not cover
- the `-note` and the plan disagree

### The precedence ladder

Read down; **the first rung that speaks to the question decides it.** This is not a tie-breaker
invented here — it is the order in which the plan's parts were written and reconciled, so a
higher rung is the one that survived more scrutiny.

1. **A stated invariant**, in the plan index or the phase plan. Invariants are what
   `plan-reconciler` held constant across every phase; prose is what one `phase-planner` wrote
   alone, blind to the others. When an invariant and a paragraph disagree, **the invariant wins
   and the prose is the stale half.**
2. **The phase's exit criteria** — the published definition of this phase being done.
3. **The phase plan's code blocks.** Complete by construction and reconciled; the prose around
   them is commentary on them.
4. **The plan index's Why and Requirements table** — the deliverable the set exists to produce.
   An `R` the phase **Satisfies** outranks an incidental sentence about how.
5. **The task text** in `todos.md`, then `-note`, which never overrides the plan.
6. **The surrounding code's existing convention** — last rung, and only for questions the plan
   genuinely does not reach.

### Tie-break rules, when the ladder runs out

- **Take the reversible option.** Prefer what a later phase or a one-line follow-up can undo over
  what rewrites a migration, drops a column, or rewrites published history.
- **Take the narrower blast radius.** A change inside the phase's **Owns** beats an equivalent
  change outside it, even when the outside one is tidier.
- **Never widen scope to settle an ambiguity.** If the only way to satisfy a step is to edit what
  another phase owns, that is drift, not a decision — Step 4's drift rule applies instead, and it
  is not a question either.
- **A failing verification is never settled by relaxing the check.** Fix the code, or stop. Never
  delete a test, loosen an assertion, or drop a guard to make a phase report success.
- **Between "do less" and "do more", do exactly what the exit criteria demand** — no extra
  refactor bought with the same commit.

### Record it, or it did not happen

Recording is what makes deciding cheap, and it costs no waiting:

1. **Print it when you make it**, one line:
   `⚖ Decided: {the fork} → {choice}. Rung {n}: {the invariant/criterion that decided it}.`
2. **Carry it in the completion report's `decisions:` list**, so `completion-handler` writes it
   into `todos.md` and `pusher` puts it in the commit body — the artefacts that outlive this
   window.
3. **Leave it where the choice is not self-evident** — one comment in the code or a line in the
   doc, naming the rung that forced it, so the next reader does not re-litigate it.
4. **If it is a swarm phase, put it in the ledger note** (Step 4b), where the coordinator and
   every later phase can see it.

### The one thing that still stops — and it is a stop, not a question

If a fork is genuinely undecidable *and* every branch is irreversible — destroying data,
rewriting published history, an unrepeatable migration — do not ask and do not wait. Land and
push whatever already verified, report `failed` to the swarm with the fork in one line (Step 4b),
and print the **Undecidable** block. A session that exits with a report lets its coordinator
strand the dependents deliberately or re-plan; a session holding a prompt strands them silently
and indefinitely, which is the failure this whole section exists to prevent.

Reach for it only when the ladder above has genuinely nothing to say. Rung 1 usually does.

---

## Context Management

```
Main context (Steps 1–2)
    → read the plan index only, then name the session impl-<slug>-p<N> (impl-<slug>
      only when no --phase was passed; never widening a launch name)
    ↓
Subagent (Step 3)
    → todos.md entries + adopted plan copies
    → returns: phase → TaskID → plan path → package
    ↓
Main context (Step 4)
    → read one phase plan, apply it, verify
    ↓
completion-handler (opus)
    → todos.md, plan index, next phase unblocked
    → readme-updater (opus) → package_readme.md
    → pusher (haiku) → commit + push code and docs together
    → last phase, no coordinator: verifier (sonnet) → merge, push, clean up
```
