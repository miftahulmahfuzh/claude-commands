# Code Analyzer Command

Read-only code archaeology. Traces dataflow, documents structure, and — when the work is too
large for one commit — decomposes it into phases and produces a reconciled set of
implementation plans.

**`/analyze` never edits source code.** It only writes markdown.

## Usage

```bash
/analyze [target] [bug|feature|update|refactor] [--worktree|--no-worktree] [--phases N]
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
- `--worktree` / `--no-worktree` — force or forbid worktree creation (see Step 5)
- `--phases N` — force exactly N phases instead of letting Step 4 decide

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

## Two Modes

Step 4 picks one. Everything before Step 4 is identical for both.

| | **SINGLE** | **ROADMAP** |
|---|---|---|
| When | fits in one reviewable change | multi-package, ordered, or too big for one commit |
| Worktree | no (unless `--worktree`) | yes |
| Writes | `<session-id>_code_analyzer.md` | analysis doc **+** `<SLUG>_ROADMAP.md` **+** one plan file per phase |
| Planning | none — analysis only | swarm of phase planners, then a reconciliation pass |
| Next command | `/implement -f <analysis>.md` | `/implement -f <SLUG>_ROADMAP.md` |

---

## Your Role

**During analysis (Steps 0–3)** you are an objective observer. You trace dataflow and document
structure. You do **not** suggest improvements, propose implementations, make value judgments,
or optimize anything. The analysis document records what *is*.

**During roadmap mode (Steps 7–9)** you plan — that is the deliverable. The separation still
holds: the analysis document stays descriptive, the plan files prescribe. Never mix them, and
never touch source code in either.

---

## Analysis Process

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

For a purge/refactor, the exploration goal is a **complete reference list**: every call site,
every implementer of the interface, every config key, every test, every doc mention. Grep for
the type and function names, not just the ones in the `@` files. An incomplete reference list
is the main way a phased purge fails halfway through.

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

### Step 4: Scope Triage — SINGLE or ROADMAP

Decide from the evidence gathered in Step 2, not from the length of the user's prompt.

Choose **ROADMAP** if **any** of these hold:
- The change spans **3+ packages** or **~15+ files**
- There is a **required order** (something must be removed before something else can be)
- Intermediate states need to stay shippable (each step must build and pass tests on its own)
- The work mixes distinct kinds of change — e.g. delete an abstraction *and* migrate its callers *and* clean up config/docs
- The user asked for phases, a roadmap, or a plan-per-phase

Otherwise choose **SINGLE**.

`--phases N` forces ROADMAP with exactly N phases. `--phases 1` forces SINGLE.

State the decision to the user in one line with the reason before proceeding:
`Scope: ROADMAP (4 phases) — 23 files across 5 packages, deletion order matters.`

**SINGLE →** skip Step 5, write the analysis document (Step 6), then stop at Step 10.
**ROADMAP →** set up the worktree first (Step 5), then write everything inside it.

### Step 5: Worktree Setup (ROADMAP only — before writing anything)

Roadmap work lands over several sessions, so the plans and the code they describe belong on
one branch from the start. Create it before writing any artifact. Skip if `--no-worktree`.

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
- If the repo is not a git repo, or `git worktree add` fails, degrade to writing in place and
  say so plainly. Do not stop.
- If already inside a worktree that isn't the default branch, reuse it — do not nest.

### Step 6: Write the Analysis Document

Create `<session-id>_code_analyzer.md` at the repository root — inside the worktree root if
Step 5 created one. Template in **Analysis Document Template** below.

### Step 7: Decompose Into Phases (ROADMAP only)

A phase is a unit that:
1. **Builds and passes tests on its own.** No phase leaves the tree broken for the next one.
2. **Is reviewable in one sitting** — roughly one package, or one kind of change.
3. **Has explicit dependencies** — states which earlier phases it requires.

Order for a removal/purge is usually: retire call sites → collapse the abstraction → delete the
now-dead types/config → clean up tests and docs. Order for a migration is usually the reverse:
introduce the new thing → move callers → delete the old thing.

Cap at **6 phases**. If the work needs more, group related ones and say what you grouped.
If the decomposition comes out as 1 phase, downgrade to SINGLE — say so and continue.

Write a **draft** `<SLUG>_ROADMAP.md` at the worktree root now, with the phase table filled in
and each phase's boundary stated. This draft is the shared contract the planners plan against.

### Step 8: Swarm — One Planner Per Phase (ROADMAP only)

Dispatch **all N phase planners in a single message** so they run concurrently
(`subagent_type: phase-planner`, see `agents/phase-planner.md`). Wait for all of them.

Each planner gets:

```yaml
worktree_root: "{absolute path}"
roadmap_file: "{worktree_root}/{SLUG}_ROADMAP.md"    # the draft
analysis_file: "{worktree_root}/{session-id}_code_analyzer.md"
phase_number: N
phase_title: "{title}"
phase_scope: "{what this phase owns — and what it must NOT touch}"
depends_on: [{earlier phase numbers}]
other_phases:                                         # boundaries only, not full plans
  - number: 1
    title: "..."
    owns: "..."
output_file: "{worktree_root}/.workflows/roadmap/{SLUG}/phase-{N}.md"
```

Planners read files themselves — pass paths, never file contents. They write their plan file
and return a short summary plus their interface contract. They do not edit code.

### Step 9: Reconcile (ROADMAP only)

The planners worked in parallel and could not see each other's output, so their plans will
disagree. Dispatch **one** `plan-reconciler` subagent (see `agents/plan-reconciler.md`) with
the worktree root, the roadmap path, the analysis path, and all N plan file paths.

It checks, and **edits the plan files in place** to fix:
- **Deleted-then-used** — a symbol deleted in phase K still referenced by a later phase
- **Unmet assumption** — phase K assumes something no earlier phase does
- **Duplicate work** — two phases deleting or editing the same thing; assign it to one
- **Collision** — two phases editing the same file without stating the sequence; the later
  phase must quote the file as it will look *after* the earlier one
- **Gap** — an impact point in the analysis that no phase owns
- **Broken-build phase** — a phase that leaves the tree uncompilable

Then it rewrites `<SLUG>_ROADMAP.md` from draft to final and appends a **Reconciliation Log**
recording each inconsistency and its resolution.

If its edits changed any interface contract, run it **once** more to verify. Cap at 2 rounds;
if contradictions survive, record them under **Open Questions** in the roadmap rather than
inventing an answer.

### Step 10: Terminate

Output only the block in **Termination** below.

---

## Analysis Document Template

Create `<session-id>_code_analyzer.md`:

```markdown
# Code Analysis: <Target>

**Type:** [Bug Investigation | Feature Implementation | Feature Update | Refactoring]
**Scope:** [SINGLE | ROADMAP — N phases]
**Date:** <timestamp>
**Session ID:** <id>
**Worktree:** <path + branch, or "none">

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
1. `file1.go` — why

**Analysis complete. No implementation proposed.**
```

---

## Roadmap Template

Create `<SLUG>_ROADMAP.md` at the worktree root (`SLUG` in SCREAMING_SNAKE, e.g.
`PURGE_DIRECT_STREAMING_TOOL_ROADMAP.md`):

```markdown
# Roadmap: <Title>

**Slug:** <kebab-slug>
**Date:** <timestamp>
**Analysis:** `<session-id>_code_analyzer.md`
**Worktree:** `<path>`
**Branch:** `feature/<slug>` (base: `<base ref>` @ `<short sha>`)
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

| # | Title | Package | Files | Depends on | Difficulty | Plan |
|---|-------|---------|-------|-----------|------------|------|
| 1 | ... | `tools/toolcore` | 6 | — | NORMAL | `.workflows/roadmap/<slug>/phase-1.md` |
| 2 | ... | `chatbot/bowl` | 4 | 1 | HARD | `.workflows/roadmap/<slug>/phase-2.md` |

### Phase 1 — <Title>
**Owns:** <what this phase changes>
**Does not touch:** <boundary>
**Exit criteria:** <what is true when it is done>

### Phase 2 — <Title>
...

## Reconciliation Log

| Conflict | Phases | Resolution |
|---|---|---|
| `StreamHandler` deleted in P1 but called in P3 | 1, 3 | deletion moved to P3; P1 only drops call sites |

## Open Questions

<Contradictions reconciliation could not resolve. Empty is the good outcome.>

## Rollback

<How to back out — per phase, and as a whole.>

## Next

    /implement -f <SLUG>_ROADMAP.md
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

**SINGLE mode:**
```bash
Analysis written to <session-id>_code_analyzer.md
Scope: SINGLE
Token count: ~<estimate>

Run in a new session:
/implement -f <session-id>_code_analyzer.md
```

**ROADMAP mode:**
```bash
Analysis written to <worktree>/<session-id>_code_analyzer.md
Roadmap written to <worktree>/<SLUG>_ROADMAP.md
Scope: ROADMAP — <N> phases, <M> inconsistencies reconciled

Worktree: <path>
Branch:   feature/<slug>  (base <ref> @ <sha>)

Phases:
  1. <title>  -> .workflows/roadmap/<slug>/phase-1.md
  2. <title>  -> .workflows/roadmap/<slug>/phase-2.md

Run from the worktree, in a new session:
cd <worktree>
/implement -f <SLUG>_ROADMAP.md
```
