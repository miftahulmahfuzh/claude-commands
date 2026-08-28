# Code Analyzer Command

Investigate, then plan. `/analyze` traces dataflow, documents structure, and **always ends with
a complete implementation plan** — one phase for small work, several reconciled phases for
large. It is the only command that writes implementation plans.

**`/analyze` never edits source code.** It reads code and writes markdown.

## Usage

```bash
/analyze [target] [bug|feature|update|refactor] [--phases N] [--no-worktree]
<free-form description of what you want, in your own words>
```

Everything is optional. `/analyze` followed by prose is a valid invocation — infer the target
and the type from what the user wrote.

**Arguments:**
- `[target]` — component, endpoint, or feature (e.g. `aggregation_mode`, `/chat/submit`). Infer it if absent.
- `[bug|feature|update|refactor]` — analysis type. Infer it if absent:
  - `bug` — errors, wrong behavior
  - `feature` — new module, architecture, capability
  - `update` — struct/API changes to something that exists
  - `refactor` — restructuring, purging, consolidating, renaming
- `--phases N` — force exactly N phases instead of letting Step 6 decide
- `--no-worktree` — plan against the current branch instead of cutting a worktree

**Example — terse, classic form:**
```bash
/analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: <paste logs here>
Note: Only happens when mode=parallel

Files:
@tools/toolcore/caller.go
```

**Example — free-form, no target and no type:**
```bash
/analyze
i want to purge direct tool streaming capability from this codebase. reasons:
1. ...
2. ...
final note: YAGNI. let the feature go.
```
Here the target is `direct tool streaming`, the type is `refactor`, and the rationale
paragraphs are requirements input — preserve them verbatim (Step 0).

---

## What You Produce

Every run, without exception:

| Artifact | Location | What it is |
|---|---|---|
| `<session-id>_code_analyzer.md` | repo/worktree root | the analysis — **descriptive**, what exists today |
| `<SLUG>_PLAN.md` | repo/worktree root | the plan index — phases, order, invariants, open questions |
| `.workflows/plan/<slug>/phase-{N}.md` | repo/worktree root | one implementation plan per phase, with complete code |

The only thing that varies is **N**, the number of phases (1 to 6). A one-phase plan set has a
short index and a single plan file; nothing else about the shape changes.

`/implement -f <SLUG>_PLAN.md` executes what you wrote. **It does no planning of its own**, and
neither does `/do` — a plan you leave vague is a plan nobody will fill in later.

---

## Your Role

Two jobs, kept separate in the artifacts:

**Analysis (Steps 0–3)** — you are an objective observer. You trace dataflow and document
structure. No improvements, no proposals, no value judgments. The analysis document records
what *is*.

**Planning (Steps 5–9)** — you prescribe. Complete code, ordered phases, verification commands.

Never mix them in one file: the analysis document stays descriptive, the plan files prescribe.
Neither touches source code.

---

## Process

### Step 0: Capture User Context

**Before any code exploration**, record the user's input exactly as written:

- **User's Raw Input** — the entire prompt after `/analyze`, verbatim. Do not summarize,
  do not clean up, do not drop the numbered rationale. On a refactor or purge, the *reasons*
  are the specification — they say what may be deleted and what may not.
- **User-Provided Files** — everything marked with `@`.

### Step 1: Read Explicitly Mentioned Files

Start with all `@` files.

### Step 2: Recursive Exploration

**RECURSIVELY explore** related files:
- Follow function calls to their definitions
- Trace struct definitions to where they're used
- Follow imports to understand relationships
- Document dependency chains

For a purge or refactor, the exploration goal is a **complete reference list**: every call site,
every implementer of the interface, every config key, every test, every doc mention. Grep for
the type and function names, not just the ones in the `@` files. An incomplete reference list is
the main way a phased change fails halfway through.

For each file you encounter, document:

**Entry Points** — what triggers this code? HTTP endpoint, function call, event? Input parameters?

**Data Transformations** — what happens to the data? Fields added/removed/modified? Validation?

**Exit Points** — where does the data go next? What is returned? Side effects (logs, events, cache)?

**State Changes** — what is persisted, where? DB operations, cache updates, external calls.

**Implicit Dependencies** — config values, env vars, DB schema, external services.

### Step 3: Write the Requirements Understanding

**After** the dataflow work, write your own technical reading of the request:

- What is the actual issue or requirement, in your own words?
- What specific behavior must change?
- What are the success criteria?
- What edge cases or constraints matter?
- What are you assuming?

This bridges raw input and implementation.

### Step 4: Worktree Setup

Cut the branch before writing anything. Plans quote code as it exists on a specific tree; if the
tree moves under them they go stale, and `/implement` applies them as written.

```bash
ROOT=$(git rev-parse --show-toplevel)
REPO=$(basename "$ROOT")
SLUG=<kebab-slug-of-the-work>            # e.g. purge-direct-streaming-tool
WT_ROOT=${TASK_WORKTREES:-$HOME/.worktrees}
git -C "$ROOT" fetch origin main --quiet 2>/dev/null || true
git -C "$ROOT" worktree add -b "feature/$SLUG" "$WT_ROOT/$REPO/$SLUG" <BASE>
```

Choosing `<BASE>`:
- `origin/main` normally (fall back to `main`, or the default branch from
  `git symbolic-ref refs/remotes/origin/HEAD`, if `origin/main` is absent)
- **`HEAD` instead** if the current checkout is dirty or ahead of `origin/main` — the analysis
  described the code you just read, and plans written against a different tree are wrong.
  Say which base you picked and why, in one line.

Then:
- All artifacts are written under the worktree root, by absolute path. The session's own cwd
  does not change — every subagent must be told the worktree root explicitly.
- **Skip on `--no-worktree`**, or if this is not a git repo, or if `git worktree add` fails.
  Write in place, and say plainly which branch the plans are pinned to.
- If already inside a worktree that isn't the default branch, reuse it — do not nest.

### Step 5: Write the Analysis Document

Create `<session-id>_code_analyzer.md` at the worktree root. Template below.

### Step 6: Decompose Into Phases

Decide N from the evidence in Step 2, not from the length of the user's prompt.

A phase is a unit that:
1. **Builds and passes tests on its own.** No phase leaves the tree broken for the next one.
2. **Is reviewable in one sitting** — roughly one package, or one kind of change.
3. **Has explicit dependencies** — states which earlier phases it requires.

**N = 1** when the work fits in one reviewable change. This is the common case for a bug fix,
and it is not a lesser mode — it still gets a plan index and a full plan file.

**N > 1** when any of these hold:
- The change spans 3+ packages or ~15+ files
- There is a required order (something must be removed before something else can be)
- Intermediate states need to stay shippable
- The work mixes distinct kinds of change — delete an abstraction *and* migrate its callers
  *and* clean up config and docs

Order for a removal is usually: retire call sites → collapse the abstraction → delete the
now-dead types and config → clean up tests and docs. For a migration it is the reverse:
introduce the new thing → move callers → delete the old thing.

Cap at **6 phases**. If the work needs more, group related ones and say what you grouped.
`--phases N` overrides the decision.

State it in one line before proceeding:
`Plan: 4 phases — 23 files across 5 packages, deletion order matters.`

Then write a **draft** `<SLUG>_PLAN.md` at the worktree root with the phase table filled in and
each phase's boundary stated. This draft is the contract the planners plan against.

### Step 7: Write the Phase Plans

Dispatch **all N phase planners in a single message** so they run concurrently
(`subagent_type: phase-planner`, see `agents/phase-planner.md`). Wait for all of them.

Each planner gets:

```yaml
worktree_root: "{absolute path}"
plan_index: "{worktree_root}/{SLUG}_PLAN.md"          # the draft
analysis_file: "{worktree_root}/{session-id}_code_analyzer.md"
phase_number: N
phase_title: "{title}"
phase_scope: "{what this phase owns — and what it must NOT touch}"
depends_on: [{earlier phase numbers}]
other_phases:                                          # boundaries only, not full plans
  - number: 1
    title: "..."
    owns: "..."
output_file: "{worktree_root}/.workflows/plan/{slug}/phase-{N}.md"
```

Planners read files themselves — pass paths, never file contents. They write their plan file and
return a short summary plus their interface contract. They do not edit code.

With N = 1 this is one planner. Dispatch it the same way.

### Step 8: Reconcile (N > 1 only)

With one phase there is nothing to reconcile — skip to Step 9.

The planners worked in parallel and could not see each other's output, so their plans will
disagree. Dispatch **one** `plan-reconciler` subagent (see `agents/plan-reconciler.md`) with the
worktree root, the plan index path, the analysis path, and all N plan file paths.

It checks, and **edits the plan files in place** to fix:
- **Deleted-then-used** — a symbol deleted in phase K still referenced by a later phase
- **Unmet assumption** — phase K assumes something no earlier phase does
- **Duplicate work** — two phases deleting or editing the same thing; assign it to one
- **Collision** — two phases editing the same file without stating the sequence; the later
  phase must quote the file as it will look *after* the earlier one
- **Gap** — an impact point in the analysis that no phase owns
- **Broken-build phase** — a phase that leaves the tree uncompilable

Then it rewrites `<SLUG>_PLAN.md` from draft to final and appends a **Reconciliation Log**.

If its edits changed any interface contract, run it **once** more to verify. Cap at 2 rounds; if
contradictions survive, record them under **Open Questions** rather than inventing an answer.

### Step 9: Finalize the Plan Index

For N = 1, promote the draft yourself: fill the phase row from the planner's return value, set
`**Status:** planned`, and leave the Reconciliation Log with the note
`single phase — nothing to reconcile`.

Before terminating, verify: every phase has a plan file, every plan file's code blocks are
complete, and every impact point in the analysis is owned by some phase. Nothing downstream
will fill a gap you leave.

### Step 10: Terminate

Output only the block in **Termination** below.

---

## Analysis Document Template

Create `<session-id>_code_analyzer.md`:

```markdown
# Code Analysis: <Target>

**Type:** [Bug Investigation | Feature Implementation | Feature Update | Refactoring]
**Date:** <timestamp>
**Session ID:** <id>
**Plan:** `<SLUG>_PLAN.md` (<N> phase(s))
**Worktree:** <path + branch, or "none — planned against <branch>">

---

## User Input

### Original User Request
<Exact copy of the user's prompt after "/analyze" — verbatim, including rationale>

### User-Provided Context
<Error messages, notes, constraints>

### User-Provided Files
- file1.go

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**: <clear technical description>

**Success Criteria**: <what "done" looks like>

**Key Considerations**: <edge cases, constraints, assumptions>

---

## Analysis Scope

### Explicitly Mentioned Files
- file1.go

### Discovered Related Files
- file3.go (called by file1.go:123)

---

## Current Dataflow

### Entry Point: <endpoint or function>

**Location:** `path/to/file.go:LineNumber`
**Trigger:** HTTP POST / function call / event
**Input Schema:** { "field": "type" }
**Validation:** <checks performed>
**Next Step:** calls `FunctionName()` at `file.go:456`

### Processing Chain

1. **Function:** `FunctionName()`
   - **Location:** `file.go:456`
   - **Input / Transform / Output**
   - **Calls:** next function in chain

### Data Persistence

**Database:** collection, operation, fields, location
**Cache:** key pattern, TTL, location

### Exit Points
- HTTP response / side effects / error conditions

---

## Key Data Structures

### Struct: `StructName`
**Location:** `path/to/file.go:123`
**Fields:** <definition>
**Used In:** `function1()` — file.go:456

---

## Dependencies

### Configuration / Environment / External Services

---

## Reference List
<Required for refactor and update types. Every site that touches the thing being changed —
this is what the phase decomposition is built from.>

| Symbol / key | File:line | Kind (def · call · impl · config · test · doc) | Package |
|---|---|---|---|

---

## Impact Points (files that WILL need changes)
1. `file1.go` — why, and which phase owns it

**This document describes. The plan files prescribe.**
```

---

## Plan Index Template

Create `<SLUG>_PLAN.md` at the worktree root (`SLUG` in SCREAMING_SNAKE, e.g.
`PURGE_DIRECT_STREAMING_TOOL_PLAN.md`):

```markdown
# Plan: <Title>

**Slug:** <kebab-slug>
**Date:** <timestamp>
**Analysis:** `<session-id>_code_analyzer.md`
**Worktree:** `<path>`
**Branch:** `feature/<slug>` (base: `<base ref>` @ `<short sha>`)
**Phases:** <N>
**Status:** planned

---

## Why

<The user's rationale, verbatim. This is the specification for what may be removed and what
may not — do not paraphrase it away.>

## Scope

**In scope:** <what changes>
**Out of scope:** <what explicitly does not change, and why>

## Invariants

Rules every phase must hold — e.g. "the tree builds and tests pass at the end of each phase",
"no user-visible behavior change", "no public API break outside package X".

## Phases

| # | Title | Package | Files | Depends on | Difficulty | Plan | TaskID |
|---|-------|---------|-------|-----------|------------|------|--------|
| 1 | ... | `tools/toolcore` | 6 | — | NORMAL | `.workflows/plan/<slug>/phase-1.md` | — |
| 2 | ... | `chatbot/bowl` | 4 | 1 | HARD | `.workflows/plan/<slug>/phase-2.md` | — |

<The TaskID column is filled in by /implement when it creates the tasks.>

### Phase 1 — <Title>
**Owns:** <what this phase changes>
**Does not touch:** <boundary>
**Exit criteria:** <what is true when it is done>

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| `StreamHandler` deleted in P1 but called in P3 | 1, 3 | deletion moved to P3; P1 only drops call sites |

<For a single-phase plan: "single phase — nothing to reconcile">

## Open Questions

<Contradictions reconciliation could not resolve. Empty is the good outcome —
/implement stops and asks about anything left here.>

## Rollback

<How to back out — per phase, and as a whole.>

## Next

    /implement -f <SLUG>_PLAN.md
```

---

## Focus by Analysis Type

**Bug Investigation** — where does it manifest? What input leads to it? What transformation
produces it? Where should validation have caught it?

**Feature Implementation** — gap analysis, touch points, dependencies, testing strategy.

**Feature Update** — which fields/structs change, which signatures, which callers, what breaks.

**Refactor / Purge** — the complete reference list (Step 2), what is safe to delete versus what
still has live callers, the removal order, and what must keep working throughout.

---

## Session ID Generation

`YYYYMMDD-HHMMSS` + 4-char alphanumeric suffix, e.g. `20250108-164512-A3F7`.
Get the date from `date +%Y%m%d-%H%M%S` — never guess it.

---

## Termination

```bash
Analysis written to <worktree>/<session-id>_code_analyzer.md
Plan written to     <worktree>/<SLUG>_PLAN.md   (<N> phase(s)<, M inconsistencies reconciled>)

Worktree: <path>
Branch:   feature/<slug>  (base <ref> @ <sha>)

Phases:
  1. <title>  -> .workflows/plan/<slug>/phase-1.md
  2. <title>  -> .workflows/plan/<slug>/phase-2.md

<If Open Questions is non-empty, list them here — /implement will stop and ask.>

Run from the worktree, in a new session:
cd <worktree>
/implement -f <SLUG>_PLAN.md
```
