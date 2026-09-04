# Code Analyzer Command

Investigate, then plan. `/analyze` traces dataflow, documents structure, and **always ends with
a complete implementation plan** — one phase for small work, several reconciled phases for
large. It is the only command that writes implementation plans.

**`/analyze` never edits source code.** It reads code and writes markdown.

## Usage

```bash
/analyze [target] [bug|feature|update|refactor] [--phases N] [--no-worktree]
         [--orchestrate [--permission-mode MODE]]
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
- `--orchestrate` — when the plan is finished, **launch the orchestrator yourself** in a new tmux
  window instead of printing a command for the user to paste (Step 11). The point is unattended
  progress: a plan that lands at 22:30 starts implementing at 22:30, not whenever someone next
  looks at the terminal.
- `--permission-mode MODE` — the mode to launch that orchestrator on. Only meaningful with
  `--orchestrate`, and it is the difference between running all night and stopping at the first
  prompt.

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

The only thing that varies is **N**, the number of phases (1 to 20). A one-phase plan set has a
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
- **Requirement IDs** — split the raw input into the distinct things the user asked for and
  number them `R1`, `R2`, … in the order they were written. One R per deliverable the user
  would recognise as separate — a numbered list in the prompt is already that split, so use
  its numbering. One paragraph asking for one thing is `R1` alone.

  This is a *restatement*, not a decomposition: an R is what the user wants, a phase is how
  it gets built, and the mapping between them is what Step 6 decides. Every downstream
  consumer — the phase table, `/implement`, and `create-task` when it shapes the cards —
  reads that mapping instead of re-deriving it from the prose.

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

**Then name the session after the slug, in the same breath:**

```bash
python3 ~/.claude/skills/task/session.py rename "analyze-$SLUG"
```

Five terminals open on one repo all carry the same derived name — `agentic-8f`, `agentic-d4` —
which says which repo and not which piece of work, so the right window is found by reading
scrollback and `/resume` a week later offers a row of near-identical titles. The slug is the one
label that separates them, and it is known here. This is the same rename `/rename` performs: it
reaches the running process over the session's own socket, so the tab title, the `/resume` row
and the name peers address all follow together — **and the tmux window too**, which under tmux is
the only one of those the user can actually see, because the status line covers the terminal's
tab title. `--no-tmux` skips that half.

Two rules. **The rename is not part of the worktree:** do it even when `git worktree add` was
skipped by `--no-worktree` or failed, because the name is about finding the window, not about the
branch. And **never let it stop anything** — it cannot fail by design (no socket, no tmux, a
session started some other way → `renamed: false` with a reason, exit 0), and an analysis is not
worth losing over the name of a window. Keep the slug to three or four words; the name is capped
at 60 characters and a tmux window is narrow.

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

Cap at **20 phases**. If the work needs more, group related ones and say what you grouped.
`--phases N` overrides the decision.

**Then map the phases onto the requirement IDs from Step 0.** Every phase declares the R (or
Rs) it serves, and every R is served by at least one phase. Two properties matter, and both are
checkable rather than felt:

- **No R is unowned.** An R that no phase satisfies is work you decomposed away — fix the
  decomposition, do not drop the R.
- **Prefer phases that serve exactly one R.** A phase spanning two Rs couples two things the
  user asked for separately, so it cannot be tracked, reviewed, or shipped against either one
  alone. Split it if the split leaves both halves building green; if it genuinely cannot be
  split — one schema migration both features need — keep it and say so, because that coupling is
  a real fact about the work and downstream consumers act on it.

State it in one line before proceeding:
`Plan: 4 phases — 23 files across 5 packages, deletion order matters. R1 -> 3,4 · R2 -> 1,2.`

**`Depends on` is load-bearing beyond ordering.** `/analyze-orchestrator` reads that column as a
DAG and runs every phase that shares no edge concurrently, in its own session. A dependency
declared out of caution — "phase 3 probably wants phase 1 first" — costs real parallelism, and a
dependency omitted for tidiness produces two sessions editing the same file at once. State the
edges that are true, and only those.

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
satisfies: [{requirement ids this phase serves, e.g. R1}]
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
complete, every impact point in the analysis is owned by some phase, and **every requirement ID
from Step 0 is satisfied by at least one phase**. Nothing downstream will fill a gap you leave.

### Step 10: Terminate

Output only the block in **Termination** below.

### Step 11: Hand Off — Automatically, with `--orchestrate`

Without the flag, stop at Step 10; the user pastes the command when they are ready.

With `--orchestrate`, launch the orchestrator here, so the plan starts being implemented the
moment it exists:

```bash
python3 ~/.claude/skills/swarm/swarm.py launch \
    --name "orch-<slug>" --cwd "<worktree>" \
    --permission-mode <the mode this session was given> \
    --prompt "/analyze-orchestrator -f <SLUG>_PLAN.md --permission-mode <same mode>"
```

**Refuse to launch, and say why in the termination block, when any of these hold.** Each is a
case where an unattended run would spend the night doing nothing useful, or something wrong:

- **Open Questions is non-empty.** The orchestrator refuses these anyway, so launching would
  produce a session that wakes up, refuses, and idles. Worse, the questions are exactly the
  contradictions that N parallel sessions would each resolve differently.
- **No `--permission-mode` was given.** A session on a prompting mode stops at its first
  permission request and waits — all night, silently. Do not guess a mode: a mode the user did
  not choose is a mode they did not consent to, and it would be broader than this session's own.
- **A phase plan file is missing**, or the index still says `Status: planned` with empty phases.

**Never pass a mode broader than this session runs under.** `--orchestrate` is a convenience for
starting a session sooner, never a way to grant one privileges the user withheld here.

The launch is the last thing this command does. Do not wait for the orchestrator, do not poll it,
and do not report its progress — it renames itself, drives its own phases, and owns the set from
that point. This session's job is finished.

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

### Requirement IDs
<The distinct things the user asked for, numbered in the order written. A restatement of the
raw input above, not a decomposition — the phases that serve each one live in the plan index.>

| ID | What the user asked for |
|---|---|
| R1 | ... |
| R2 | ... |

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
**Coordinator:** —

---

<The Coordinator line is the peer address of the session driving this set, filled in by
`/analyze-orchestrator` when it takes the set over. Leave it `—`: a name written here by hand
addresses a session that does not exist, and the reports meant for it go nowhere.>

## Why

<The user's rationale, verbatim. This is the specification for what may be removed and what
may not — do not paraphrase it away.>

## Requirements

<Carried from the analysis document's Requirement IDs — the plan index must stand alone, because
`create-task` shapes the cards from this table and never reads the analysis.>

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Coba ulang: refill a reading that never finished | 3, 4 |
| R2 | Swipe-left to soft-delete a history item | 1, 2 |

## Scope

**In scope:** <what changes>
**Out of scope:** <what explicitly does not change, and why>

## Invariants

Rules every phase must hold — e.g. "the tree builds and tests pass at the end of each phase",
"no user-visible behavior change", "no public API break outside package X".

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | ... | R2 | `tools/toolcore` | 6 | — | NORMAL | `.workflows/plan/<slug>/phase-1.md` | — | — |
| 2 | ... | R2 | `chatbot/bowl` | 4 | 1 | HARD | `.workflows/plan/<slug>/phase-2.md` | — | — |

<The TaskID column is filled in by /implement when it creates the tasks; the Card column by
`create-task --from-plan`, with the sub-issue it minted for that phase (`owner/repo#13`).
Leave both `—` — writing a card ref here yourself invents one.>

### Phase 1 — <Title>
**Satisfies:** R2
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

Execute the phases one at a time, starting at phase 1:

    /implement -f <SLUG>_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f <SLUG>_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan <SLUG>_PLAN.md
```

Note the shape of that section: each command sits alone on its line with its explanation
**above** it. A trailing `#` on a slash-command line is read as arguments, not as a comment, so a
commented command is not a pasteable one.

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

## If the Same Prompt Also Asked for Task Cards

A prompt that says "2 cards and /analyze" is asking for both, and the order is not negotiable:
**`/analyze` runs first, and the cards are created from the finished plan index.** The user's
count of cards is a statement of *deliverables*; the phase set is the decomposition, and only
this command has read the code well enough to produce it. Cards minted before the plan exists
commit the board to a shape nothing downstream agrees with.

So: finish every step above, then hand the plan index to `create-task --from-plan` (see the
`create-task` skill, which owns the parent/sub-issue shape and the GitHub-only limits). Do not
mint cards from this command directly, and do not adjust the phase count to match the number of
cards the user asked for — the **Requirements** table is what reconciles the two counts.

---

## Termination

```bash
Analysis written to <worktree>/<session-id>_code_analyzer.md
Plan written to     <worktree>/<SLUG>_PLAN.md   (<N> phase(s)<, M inconsistencies reconciled>)

Worktree: <path>
Branch:   feature/<slug>  (base <ref> @ <sha>)
Session:  analyze-<slug>  <or the reason it kept its old name>

Requirements:
  R1 <what the user asked for>   -> phases 3, 4
  R2 <what the user asked for>   -> phases 1, 2

Phases:
  1. <title>  [R2]  -> .workflows/plan/<slug>/phase-1.md
  2. <title>  [R2]  -> .workflows/plan/<slug>/phase-2.md

<If Open Questions is non-empty, list them here — /implement will stop and ask.>

Next — phase 1 of <N>, in a new session:

  cd <worktree>
  /implement -f <SLUG>_PLAN.md --phase 1

<Always offer this, whatever N is. Parallelism decides whether a swarm beats /implement;
it does not decide whether the set should run unattended. A strictly sequential four-phase
set is the case that gains MOST — otherwise it is four commands pasted into four sessions,
each waiting on a human to notice the last one finished. Even N = 1 gains a session that
starts now rather than whenever someone next looks.>

  /analyze-orchestrator -f <SLUG>_PLAN.md

<When --orchestrate was passed, this already happened — say which window it opened instead:>

  Orchestrator running in tmux <window> as orch-<slug>  (mode: <mode>)
```

`--phase 1` is explicit on purpose: the plan set has just been written, so phase 1 is what starts
it, and naming it means the line still says what it does when it is read back a week later.
`/implement` refuses a `--phase N` whose task is already complete, so a re-paste is safe.

The command sits alone on its own line so it can be selected and pasted, and nothing follows it
on that line — a trailing `# comment` is read as arguments to the slash command. `/do` and
`/implement` end with the same shape.
