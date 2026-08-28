# Implement Command

Execute implementation from `/analyze` output. Creates the task(s), generates or adopts the
plan, and implements.

`-f` accepts either of `/analyze`'s two outputs:

| Input | Mode | What happens |
|---|---|---|
| `<session-id>_code_analyzer.md` | **analysis** | one task + one generated plan, then implement it |
| `<SLUG>_ROADMAP.md` | **roadmap** | one task per phase, plans adopted from the roadmap, then implement one phase |

## Usage

```bash
/implement -f <code_analyzer.md | SLUG_ROADMAP.md> [-p <path>] [-note <note>] [--phase N] [--all]
```

**Arguments:**
- `-f` — analysis or roadmap file (required)
- `-p` — directory containing `.workflows/` (optional; auto-detected)
- `-note` — extra context; supplements the analysis, never replaces it
- `--phase N` — roadmap mode: implement phase N instead of the next unfinished one
- `--all` — roadmap mode: continue through every remaining phase in this session

**Examples:**
```bash
/implement -f 20250108-164512-A3F7_code_analyzer.md -p tools/toolcore
/implement -f PURGE_DIRECT_STREAMING_TOOL_ROADMAP.md
/implement -f PURGE_DIRECT_STREAMING_TOOL_ROADMAP.md --phase 3
```

---

## Step 0: Detect Mode

Read the first ~30 lines of the `-f` file. A file starting `# Roadmap:` (or named
`*_ROADMAP.md`) is **roadmap mode** → go to the Roadmap Mode section. Anything else is
**analysis mode** → continue below.

---

## Analysis Mode

### Step 1: Read the Analysis File

The analysis file is ground truth. Extract:
- **User Input** — original request, context, errors, notes
- **Detailed Requirements Understanding** — the technical interpretation
- **Analysis Type** — Bug | Feature | Update | Refactor

### Step 2: Determine Path

With `-p`: use it. Without: parse the file paths in the analysis and pick the `.workflows/`
location by weight — most-changed files, core package over dependencies, directory depth.

Validate `{path}/.workflows/todos.md` exists. If missing, **STOP**:
`Run /update-todos {path} --init first`

### Step 3: Generate TaskID

`P{Priority}-{PackageCode}-{4CharID}` — package code from the todos.md header, priority from
the analysis, next sequential 4-char ID (A000 → A999 → B000).

### Steps 4 & 5: todos.md + Plan (Subagent — required)

**Do not do this in the main context.** The main context stays clean for code.

Dispatch a subagent with:

````
You are implementing Steps 4 and 5 of the /implement command.

Inputs:
- Analysis file: {path}
- Path: {path}
- TaskID / Priority / Package code: {...}
- Note: {if provided}

Step 4 — add to {path}/.workflows/todos.md, in the right priority section:

- [ ] **{TaskID}** {brief title}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Type**: {Bug|Feature|Update|Refactor}
  - **Context**: {from "Detailed Requirements Understanding"}
  - **Status**: in_progress
  - **Plan**: `.workflows/plan/{TaskID}.md`

Step 5 — create {path}/.workflows/plan/{TaskID}.md:

# Implementation Plan: {TaskID}

**TaskID** / **Type** / **Created** / **Analysis Source**

## User Context
<copy from the analysis "User Input" section>

## Requirements Understanding
<copy from "Detailed Requirements Understanding">

## Summary
{one paragraph}

## Scope
### Files to Modify
- `file.go` — {what changes}
### Dependencies
- {packages or services}

## Implementation Steps
### Step 1: {title}
**File**: `{path/file.go}`
**Change**: {description}
**Code**:
```go
// FULL code block — complete functions/structs, no placeholders
```
**Impact**: {what breaks}

## Testing Plan
## Rollback Plan

Requirements:
- All code blocks COMPLETE and runnable. No `// ... existing code`, no `...`.
- Keep it concise — code changes, not prose.
- Trust the analysis; do not re-analyze.
- If anything is ambiguous, ask with AskUserQuestion and give your own recommendation.
  Never guess and proceed.

Return: TaskID, priority, title, plan path, summary of what you did.
````

Verify the returned values before Step 6.

### Step 6: Execute (Main Context)

1. For each step in the plan: read the file, make the change.
2. When done, dispatch the **`completion-handler`** agent with:
   ```yaml
   completion_report:
     task_id: "{TaskID}"
     package_path: "{path}"
     status: "success"
     modified_files: ["{file}"]
   ```

`completion-handler` flips the task to completed in todos.md, updates `analysis_report.md` if a
documented finding was resolved, then chains **`readme-updater`** (opus) and **`pusher`**
(haiku). The main context performs no documentation updates and no git operations.

---

## Roadmap Mode

### Step R1: Verify the Worktree

The roadmap names the worktree and branch it was planned in. Compare with
`git rev-parse --show-toplevel` and `git branch --show-current`.

- Match → proceed.
- Different tree → **STOP** and print `cd <worktree path>` — plans quote code as it exists on
  that branch, and applying them elsewhere silently produces conflicts.
- Worktree gone (roadmap says `none`, or the path no longer exists) → say so and proceed on the
  current branch.

### Step R2: Read the Roadmap

Extract: slug, the **Why** section, the invariants, the phase table (number, title, package,
depends-on, difficulty, plan file), and any **Open Questions**.

**If Open Questions is non-empty, resolve them before implementing.** Ask with
`AskUserQuestion`, one question per unresolved item, each with your own recommendation.
Reconciliation deliberately left these for a human — implementing over them guesses.

### Step R3: Create One Task Per Phase (Subagent — required)

Only on the first `/implement` run against this roadmap. Detect a re-run by searching the
roadmap slug in the todos.md files; if the tasks exist, skip to R4.

Dispatch one subagent to create all phase tasks. For each phase:

- Package path = the phase's **Package** column. Validate `{pkg}/.workflows/todos.md` exists;
  if missing, run `/update-todos {pkg} --init` rather than stopping — a roadmap can span
  packages that were never tracked.
- Mint a TaskID per phase from that package's own counter.
- Task entry:
  ```markdown
  - [ ] **{TaskID}** Phase {N}: {title}
    - **Difficulty**: {from the roadmap}
    - **Type**: {Bug|Feature|Update|Refactor}
    - **Context**: {phase Owns + Exit criteria}
    - **Status**: {in_progress for the first phase, blocked for the rest}
    - **Roadmap**: `{SLUG}_ROADMAP.md` (phase {N} of {total})
    - **Depends on**: {TaskIDs of the phases this one requires}
    - **Plan**: `.workflows/plan/{TaskID}.md`
  ```
- **Adopt, do not regenerate, the plan.** Copy `.workflows/roadmap/{slug}/phase-{N}.md` to
  `{pkg}/.workflows/plan/{TaskID}.md`, prepending:
  ```markdown
  > Adopted from `{SLUG}_ROADMAP.md` phase {N}. Source: `.workflows/roadmap/{slug}/phase-{N}.md`.
  > Reconciled against the other phases — edit the source, not this copy, if the plan changes.
  ```
  Regenerating would discard the reconciliation that made the phases consistent.
- Write the TaskID back into the roadmap's phase table (add a **TaskID** column) so a later
  session can map phases to tasks.

Return: the phase → TaskID → plan path → package mapping.

### Step R4: Implement One Phase (Main Context)

Pick the phase: `--phase N` if given, else the lowest-numbered phase whose task is not
complete. Refuse a phase whose `Depends on` tasks are not all complete — name the blocker.

Apply that phase's plan step by step. The plan's code blocks are complete by construction;
where the real code has drifted from the plan, follow the plan's *intent*, note the drift, and
carry it into the completion report.

Then dispatch **`completion-handler`** with the phase's `completion_report`, plus:
```yaml
roadmap:
  file: "{SLUG}_ROADMAP.md"
  phase: N
  next_task_id: "{TaskID of phase N+1, or empty}"
```
It marks the phase task complete and flips the next phase's task from `blocked` to `open`.

### Step R5: Stop or Continue

**Default: stop after one phase.** Print the next command and let the user start a fresh
session — a roadmap phase is exactly the unit that fits in one clean context, and phase N+1's
plan was written assuming phase N had landed and been reviewed.

**With `--all`:** loop back to R4 for the next phase, in the same session. Say once, up front,
that context will grow across phases.

---

## Termination

**Analysis mode:**
```
✓ Implementation complete: {TaskID}

Files modified: {count}
Plan: .workflows/plan/{TaskID}.md
```

**Roadmap mode:**
```
✓ Phase {N}/{total} complete: {TaskID} — {title}

Files modified: {count}
Plan: {pkg}/.workflows/plan/{TaskID}.md
Branch: {branch}

Remaining: phase {N+1} ({TaskID}), phase {N+2} ({TaskID})

Next, in a fresh session from this worktree:
/do {TaskID of phase N+1}
```

**Roadmap complete:**
```
✓ All {total} phases complete — {SLUG}_ROADMAP.md

Branch: {branch}
Review and merge:
  git checkout main && git merge {branch}
```

**todos.md missing (analysis mode):**
```
✗ Error: todos.md not found in {path}/.workflows/
Run: /update-todos {path} --init
```

---

## Handling Confusion

**During plan creation (Step 5) and phase implementation (R4):** stop, ask with
`AskUserQuestion`, and give your own recommendation with rationale for each option. Wait for
the answer.

Cases that warrant a question:
- Multiple valid implementations, or a performance-vs-simplicity trade-off
- Ambiguous error-handling requirements
- Conflicting signals in the analysis
- Breaking changes reaching code outside the stated scope
- The real code structure differs from the analysis in a way that changes the approach
- Roadmap **Open Questions** left unresolved

**When in doubt, ask — never guess and proceed.**

---

## Context Management

Documentation work is delegated so the main context holds only code:

```
Main context (Steps 1–3 / R1–R2)
    → read input, resolve path, mint TaskID(s)
    ↓
Subagent (Steps 4–5 / R3)
    → todos.md + plan files
    → returns: TaskID, priority, title, plan path
    ↓
Main context (Step 6 / R4)
    → implement, in a clean context
    ↓
completion-handler (opus)
    → todos.md, analysis_report.md
    → readme-updater (opus) → package_readme.md
    → pusher (haiku) → commit + push code and docs together
```
