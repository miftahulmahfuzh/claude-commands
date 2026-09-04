# Implement Command

Execute the plan `/analyze` wrote. **`/implement` does not plan** — it creates the task
bookkeeping, applies the code, and hands off. Every implementation plan in this workflow has
exactly one author, and it is `/analyze`.

## Usage

```bash
/implement -f <SLUG>_PLAN.md [--phase N] [--all] [-note <note>]
```

**Arguments:**
- `-f` — the plan index written by `/analyze` (required)
- `--phase N` — implement phase N instead of the next unfinished one
- `--all` — continue through every remaining phase in this session
- `-note` — extra context for implementation; it never overrides the plan

**Examples:**
```bash
/implement -f PURGE_DIRECT_STREAMING_TOOL_PLAN.md
/implement -f FIX_CITATION_AGGREGATION_PLAN.md --phase 2
```

### Wrong input

Given a `*_code_analyzer.md`, or anything else that is not a plan index, **stop**:

```
✗ Not a plan: {file}
  /implement executes plans; it does not write them.
  Run /analyze to produce <SLUG>_PLAN.md, then re-run.
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
**Open Questions**.

**If Open Questions is non-empty, resolve it before implementing.** Ask with
`AskUserQuestion` — one question per item, each with your own recommendation. `/analyze`'s
reconciliation deliberately left these for a human; implementing over them guesses.

Read only the index here. Phase plans are read in Step 4, one at a time, so the main context
never holds plans for phases it is not implementing.

**Then name the session after the slug**, which the index just gave you:

```bash
python3 ~/.claude/skills/task/session.py rename "impl-<slug>"
```

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
name of a window. Keep the slug to three or four words if the index's is long — the name is
capped at 60 characters and a tmux window is narrow.

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
    - **Plan Set**: `{SLUG}_PLAN.md` (phase {N} of {total})
    - **Satisfies**: {R id(s)} — {that requirement's one-line text from the index}
    - **Depends on**: {TaskIDs of the phases this one requires}
    - **Plan**: `.workflows/plan/{TaskID}.md`
    - **Card**: {the index's Card column, e.g. `owner/repo#13`} — omit the line if it is `—`
  ```
- **Adopt the plan file — never rewrite it.** Copy `.workflows/plan/{slug}/phase-{N}.md` to
  `{pkg}/.workflows/plan/{TaskID}.md`, prepending:
  ```markdown
  > Adopted from `{SLUG}_PLAN.md` phase {N}. Source: `.workflows/plan/{slug}/phase-{N}.md`.
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
python3 ~/.claude/skills/task/session.py rename "impl-<slug>-p<N>"
```

A second rename costs nothing — it is idempotent, and reports `renamed: false` when the name is
already right. **With `--all` skip it:** that session works every remaining phase, so a phase
number in its name would be stale for most of its life; `impl-<slug>` from Step 2 stays.

Read that phase's plan file and apply its steps in order. The code blocks are complete by
construction; use them.

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

Run the plan's **Verification** commands before reporting success. A failing build or test is a
failure, not a caveat.

Then dispatch **`completion-handler`**:
```yaml
completion_report:
  task_id: "{TaskID}"
  package_path: "{pkg}"
  status: "success"
  modified_files: ["{file}"]
  drift_notes: ["{if any}"]
plan_set:
  file: "{SLUG}_PLAN.md"
  phase: N
  next_task_id: "{TaskID of phase N+1, or empty}"
```

It flips the task to completed, ticks the phase in the index, unblocks the next phase's task,
then chains `readme-updater` and `pusher`. The main context performs no documentation updates
and no git operations.

## Step 4b: Report to the Swarm (only if there is one)

A phase run by an orchestrator has a session waiting on it. Report in **both** halves, in this
order — the file is the record, the message is the notification, and doing only one leaves either
a silent coordinator or a set nobody can resume:

```bash
python3 ~/.claude/skills/swarm/swarm.py find --plan <the phase plan just implemented>
```

`{"swarm": false, ...}` means this task belongs to no swarm — say nothing, do nothing, done. Every
`swarm.py` read exits 0 when there is no ledger, so an ordinary task is never affected by any of
this.

Otherwise `find` returns the `slug`, the `phase`, the `coordinator` to address and the `peers`:

```bash
python3 ~/.claude/skills/swarm/swarm.py report --slug <slug> --phase <N> \
    --status done --commit <sha from pusher> --task <TaskID> --note "<one line>"
```

then `SendMessage` the coordinator — `DONE`, the TaskID, the commit, and one line on what
actually changed. Report `failed` the same way, with the reason: a coordinator that is told a
phase failed can strand its dependents deliberately, while one left guessing stalls the whole set.

**Mesh messages** go to peers directly, and only these: `READY` when an Interface Contract item
a dependent is waiting on now exists, `NEED` before assuming a dependency landed, `WARN` before
deleting a worktree or branch a peer is sitting in. A message states a fact and never delegates
work — "I deleted `SortRows`" is a mesh message; "please delete `SortRows` for me" is not, and
asking a peer to do what this session could not is permission laundering.

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

A single-phase plan finishes in one run either way.

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

Remaining: phase {N+1} ({TaskID}), phase {N+2} ({TaskID})

Next — phase {N+1} of {total}, in a new session:

  cd {worktree}
  /do {TaskID of phase N+1}
```

**All phases done:**
```
✓ Plan complete — {SLUG}_PLAN.md ({total} phase(s))

Branch: {branch}

Next — review and merge:

  cd {worktree}
  git checkout main && git merge {branch}
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

---

## Handling Confusion

Stop and ask with `AskUserQuestion`, giving your own recommendation with rationale, when:
- The plan index has unresolved **Open Questions**
- The plan's intent is ambiguous at a specific step
- Applying a step would break code outside the phase's stated scope
- Verification fails for a reason the plan's rollback section does not cover

**When in doubt, ask — never guess and proceed.** What you must not do is quietly invent the
missing part of a plan.

---

## Context Management

```
Main context (Steps 1–2)
    → read the plan index only, then name the session impl-<slug>
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
```
