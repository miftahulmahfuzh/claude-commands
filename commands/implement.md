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

Read that phase's plan file and apply its steps in order. The code blocks are complete by
construction; use them.

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

## Step 5: Stop or Continue

**Default: stop after one phase.** Print the next command and let the user start a fresh
session — a phase is exactly the unit that fits in one clean context, and phase N+1's plan was
written assuming phase N had landed and been reviewed.

**With `--all`:** loop back to Step 4 for the next phase in the same session. Say once, up
front, that context grows across phases.

A single-phase plan finishes in one run either way.

---

## Termination

**Phase done, more remaining:**
```
✓ Phase {N}/{total} complete: {TaskID} — {title}

Files modified: {count}
Plan: {pkg}/.workflows/plan/{TaskID}.md
Branch: {branch}
Verification: {command} — passed

Remaining: phase {N+1} ({TaskID}), phase {N+2} ({TaskID})

Next, in a fresh session from this worktree:
/do {TaskID of phase N+1}
```

**All phases done:**
```
✓ Plan complete — {SLUG}_PLAN.md ({total} phase(s))

Branch: {branch}
Review and merge:
  git checkout main && git merge {branch}
```

**Blocked:**
```
✗ Phase {N} ({TaskID}) depends on {TaskID}, which is not complete.
```

**Drifted:**
```
✗ Phase {N} plan does not match the current tree.
  {what drifted}
  Re-run /analyze to re-plan against the current tree.
```

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
    → read the plan index only
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
