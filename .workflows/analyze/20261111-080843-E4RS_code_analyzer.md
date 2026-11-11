# Code Analysis: EARS acceptance criteria for /analyze plan sets

**Type:** Feature Implementation
**Date:** 2026-11-11 08:08 (WIB)
**Session ID:** 20261111-080843-E4RS
**Plan:** `.workflows/plan/EARS_ACCEPTANCE_CRITERIA_PLAN.md` (5 phases)
**Worktree:** `/home/miftah/.worktrees/claude-commands/ears-acceptance-criteria` on `feature/ears-acceptance-criteria` (base `origin/main` @ `7ab5aca`)

---

## User Input

### Original User Request

```
feature --permission-mode bypassPermissions
Implement candidate 1 from note Z-PYZ (also docs/session-swarm.md, "Borrowed, and worth borrowing next", item 1): EARS acceptance criteria, borrowed from Kiro specs (https://kiro.dev/docs/specs/concepts).

What I want:
1. /analyze writes each requirement R1..Rn in the plan index Requirements table in EARS form: "WHEN <trigger> THE SYSTEM SHALL <behavior>" (plus the other EARS patterns where they fit: ubiquitous "THE SYSTEM SHALL", "WHILE <state>", "IF <unwanted condition> THEN", "WHERE <feature>"). Keep the user raw asks verbatim beside them, since the rationale is the spec.
2. Every phase plan Proof journey traces to one or more EARS criteria by id (e.g. R2.1), so a requirement with no journey is a visible gap.
3. plan-reconciler checks the trace: every criterion has at least one owning phase and at least one Proof journey; an untraced criterion is fixed by editing the plans, or lands in Open Questions only if unowned (rule 6 / /analyze Step 8 must stay in step).
4. The verifier agent checks the list of criteria, reporting a verdict per criterion id, instead of reading prose.
5. Keep consumers working: swarm.py parse_index reads the phase table by header name, create-task maps cards from the R table, skills/task. Old plan sets without EARS must still execute (executors take the path they are handed).

Why: the verifier and reconciler currently read prose requirements; EARS makes R rows machine-checkable and traceable. Read docs/architecture-notes.md sections for /analyze, the swarm, and the board skills before planning. Run ./sync.sh as part of the work.
```

### User-Provided Context
- Source idea: `docs/session-swarm.md:341-344` ("Borrowed, and worth borrowing next", item 1).
- `--permission-mode bypassPermissions` for the launched sessions.

### User-Provided Files
none (`@` files). Named: `docs/architecture-notes.md`, `docs/session-swarm.md`, `skills/swarm/swarm.py`, `skills/create-task`, `skills/task`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | /analyze writes each requirement R1..Rn in the plan index Requirements table in EARS form (WHEN/ubiquitous/WHILE/IF…THEN/WHERE), with the user's raw ask verbatim beside it |
| R2 | Every phase plan Proof journey traces to one or more EARS criteria by id (e.g. R2.1), so a requirement with no journey is a visible gap |
| R3 | plan-reconciler checks the trace (every criterion has an owning phase and a Proof journey); untraced → fix the plans; Open Questions only if unowned; rule 6 and /analyze Step 8 stay in step |
| R4 | The verifier checks the list of criteria and reports a verdict per criterion id instead of reading prose |
| R5 | Consumers keep working (swarm.py parse_index, create-task, skills/task); old plan sets without EARS still execute; ./sync.sh is run |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**: The plan index's Requirements table today holds a one-line
paraphrase per `R`, and each phase plan's Proof section lists journeys with no link back to any
requirement. The reconciler checks requirement *ownership* (phase ↔ R via **Satisfies**) but has
no notion of *proof coverage*; the verifier reports per phase, by reading Proof prose and exit
criteria. The ask is to introduce numbered, EARS-shaped acceptance criteria (`R{n}.{m}`) under
each `R`, trace journeys to them, make the reconciler enforce the trace, and make the verifier
return a verdict per criterion — without breaking the consumers that read the index today or the
plan sets already on disk.

**Success Criteria**:
- A new `/analyze` run produces an index whose Requirements section carries the verbatim ask per
  `R` plus a criteria table, one EARS row per `R{n}.{m}`, each mapped to phases and journeys.
- Every phase plan journey carries `traces R{n}.{m}[, …]`.
- The reconciler finds an untraced/unowned criterion and fixes it (or parks an unowned one) — and
  there is a mechanical check (a script) that reports the same thing, so "machine-checkable" is
  literal.
- The verifier's return value has a `criteria:` list with one verdict per id.
- `swarm.py selftest`, `tests/test_plan_graph.py`, and an old-format index (no criteria) still
  parse and execute; create-task still shapes cards from the R table.

**Key Considerations**:
- `swarm.py _ids` (`swarm.py:258`) is `re.findall(r"R\d+", …)`. A Satisfies cell is R-level today;
  if a criterion id ever reaches it, `R2.1` → `R2`, and `R2.1, R2.2` → `["R2","R2"]` (duplicate).
  Must dedupe and stay R-level.
- `parse_index` (`swarm.py:189`) identifies the phase table by a header row whose first cell is `#`
  and that contains `title` and `plan`. A new criteria table must not start with `#` + contain
  `plan`, or it is read as phases. Criteria table header begins with `ID`, so it is safe — but the
  selftest must assert it.
- `plan_graph.py` imports `parse_index` from `swarm`; any change to its return shape ripples there.
- The Requirements R table (`| ID | What the user asked for | Phases |`) is what create-task reads
  (`skills/create-task/SKILL.md:82-104`). Its columns and R-level rows must survive, so criteria go
  in a separate table, not as extra rows in it.
- Old plan sets: no criteria table, journeys untraced. Executors (`/implement`, `/do`) never parse
  criteria; verifier and the trace checker must degrade to today's behavior with a `legacy` note,
  never fail.

**Assumptions** (inferred, planned against):
- "In the plan index Requirements table in EARS form … verbatim beside them" is satisfied by a
  `## Requirements` section holding the R table (verbatim ask, phases) and directly beneath it an
  `### Acceptance Criteria` table (one EARS row per criterion). Separate tables keep create-task's
  R-level mapping intact (R5) while giving each criterion its own machine-readable row (R1, R4).
- The mechanical check is a new read-only script, `skills/swarm/ears_trace.py`, beside
  `plan_graph.py` and modelled on it (stdlib, exit codes 0/1/2, `--json`). It is not asked for by
  name; it is the literal reading of "machine-checkable" and lets the reconciler and Step 9 verify
  the trace instead of eyeballing it.
- `./sync.sh` runs once, at the end of the last phase, so the deployed tree never holds a partial
  set.

---

## Analysis Scope

### Explicitly Mentioned Files
- `docs/architecture-notes.md`, `docs/session-swarm.md`, `skills/swarm/swarm.py`, `skills/create-task/SKILL.md`, `skills/task/SKILL.md`

### Discovered Related Files
- `commands/analyze.md` — Steps 0, 6, 7, 8, 9; plan index template (`:640-655`); termination (`:780`)
- `agents/phase-planner.md` — input YAML (`:17-27`), step 6 Proof (`:46-49`), Proof format (`:118-128`), return (`:137-155`)
- `agents/plan-reconciler.md` — ledger (`:26-33`), conflicts table (`:35-48`), rules 6–7 (`:72-95`), finalize (`:99-113`), return (`:120-126`)
- `agents/verifier.md` — input (`:22-29`), steps (`:31-75`), return (`:77-98`)
- `commands/analyze-orchestrator.md:630-645` — verifier dispatch per wave and handling of its verdict
- `commands/implement.md:103-104` (reads Requirements), `:196` (Satisfies line text), `:494-507` (solo verifier dispatch)
- `commands/do.md:295-305` — Proof; no verifier on this path (unchanged)
- `skills/swarm/plan_graph.py` — imports `parse_index`; CLI conventions to mirror
- `skills/swarm/tests/test_plan_graph.py` — stdlib test harness convention
- `skills/swarm/SKILL.md:23-30` — documents `plan_graph.py`
- `skills/task/DESIGN.md:284-290` — describes R numbering
- `README.md:136-150, 330, 448, 486-489, 618-630` — /analyze description, verifier, board
- `CLAUDE.md` — Swarm planning section (rule 6 / Step 8 in step)

---

## Current Dataflow

### Entry Point: `/analyze` (commands/analyze.md)
**Trigger:** user slash command. **Input:** free prose.
1. Step 0 records raw input and splits it into `R1..Rn` (`analyze.md:183-192`).
2. Step 6 maps phases → R (`:318-331`), writes the draft index with Requirements table `| ID | What the user asked for | Phases |` (`:642-650`).
3. Step 7 dispatches `phase-planner`s with `satisfies: [R…]` (`:349-366`).
4. Step 8 dispatches `plan-reconciler` (N>1), then resolves forks into `## Decisions` (`:375-405`).
5. Step 9 verifies every R is satisfied by ≥1 phase (`:411-421`).
6. Step 11 launches `/implement` (N=1) or `/analyze-orchestrator` (N>1).

### phase-planner (agents/phase-planner.md)
Input `satisfies`; writes `**Satisfies:** R1` header and a Proof with `- Journeys: one per claim…` (free prose, no ids). Returns `proof: "<harness>; <n> journeys"`.

### plan-reconciler (agents/plan-reconciler.md)
Ledger includes `requirement id → phases`. Conflicts *Unowned requirement* and *Requirement creep*. Rule 7: an unowned R is an Open Question. Finalize writes the Requirements table's Phases column. No proof-coverage check.

### verifier (agents/verifier.md)
Input: worktree, base, `phases: [{number, plan_file}]`. Reads each phase's Proof and Exit criteria, runs every journey + one neighbor. Return: per-phase verdict with `proved/failed/inconclusive` lists of free-text `claim`s.
Dispatched by `analyze-orchestrator.md:635` (per wave) and `implement.md:494` (solo last phase).

### swarm.py parse_index (`swarm.py:189-238`)
Reads `**Key:**` meta lines, then any table whose header's first cell is `#` and contains `title`+`plan`; each numeric row → phase dict; `satisfies` via `_ids` (`:258`). Selftest fixture `INDEX` (`:1909`) and assertions (`:1934-1960`). Run: `python3 skills/swarm/swarm.py selftest`.

### create-task (skills/create-task/SKILL.md:66-130)
Reads the Requirements table's ID → Phases mapping to choose one parent per R vs one parent per set; parent body lists "the `R` (or Rs) it covers, in the user's own words".

### skills/task
`SKILL.md:63-70` and `:344-346` rely on parent cards per R and the plan index's branch/worktree; no parsing of the Requirements table in `task_gh.py`. `DESIGN.md:284-290` documents R numbering.

### Data Persistence
All artifacts are markdown under `<worktree>/.workflows/`. `.workflows/plan/` is gitignored (plans live on the branch locally); deployed copies via `sync.sh` into `~/.claude/`.

---

## Key Data Structures

### Plan index Requirements table (today)
`| ID | What the user asked for | Phases |` — R-level, read by create-task, `/implement` Step 2, reconciler.

### Phase table (today)
`| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |` — read by `parse_index` by header name.

### Verifier return (today)
`phases: [{number, verdict, proved[], failed[], inconclusive[], map_drift[]}]`.

---

## Dependencies
- Python 3 stdlib only for `skills/swarm/*.py`. No test runner; `swarm.py selftest` and `tests/test_plan_graph.py` are the checks.
- `./sync.sh` deploys to `~/.claude/`.

---

## Reference List

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| Requirement IDs (Step 0) | `commands/analyze.md:183` | doc | commands |
| phases → R mapping (Step 6) | `commands/analyze.md:318` | doc | commands |
| planner input `satisfies` | `commands/analyze.md:356` | doc | commands |
| Step 8 ladder / Open Questions | `commands/analyze.md:392-405` | doc | commands |
| Step 9 R check | `commands/analyze.md:415` | doc | commands |
| analysis template Requirement IDs | `commands/analyze.md:524` | doc | commands |
| index template `## Requirements` | `commands/analyze.md:642` | doc | commands |
| termination Requirements block | `commands/analyze.md:780` | doc | commands |
| planner `satisfies` input / Proof / return | `agents/phase-planner.md:24,46,118,137` | doc | agents |
| reconciler ledger / conflicts / rules 6–7 / finalize | `agents/plan-reconciler.md:26,35,72,99` | doc | agents |
| verifier input / return | `agents/verifier.md:22,77` | doc | agents |
| verifier dispatch (wave) | `commands/analyze-orchestrator.md:635` | doc | commands |
| verifier dispatch (solo) | `commands/implement.md:494` | doc | commands |
| Requirements read | `commands/implement.md:103` | doc | commands |
| todos Satisfies line | `commands/implement.md:196` | doc | commands |
| `parse_index` | `skills/swarm/swarm.py:189` | def | swarm |
| `_ids` | `skills/swarm/swarm.py:258` | def | swarm |
| selftest INDEX | `skills/swarm/swarm.py:1909` | test | swarm |
| `from swarm import parse_index` | `skills/swarm/plan_graph.py:30` | call | swarm |
| plan_graph doc | `skills/swarm/SKILL.md:23` | doc | swarm |
| Requirements → cards | `skills/create-task/SKILL.md:82` | doc | create-task |
| R numbering | `skills/task/DESIGN.md:284` | doc | task |
| R per parent | `skills/task/SKILL.md:69` | doc | task |
| /analyze R description | `README.md:136` | doc | root |
| verifier row / Proof | `README.md:330,486` | doc | root |
| swarm planning rule 6 | `CLAUDE.md` Swarm planning | doc | root |
| Swarm planning pattern | `docs/architecture-notes.md` | doc | docs |
| Borrowed item 1 | `docs/session-swarm.md:341` | doc | docs |

---

## Impact Points (files that WILL need changes)
1. `commands/analyze.md` — Step 0/3/6/7/9 + templates + termination emit EARS criteria (phase 1); Step 8 + Step 9 trace check (phase 3)
2. `agents/phase-planner.md` — `criteria` input, traced journeys, return (phase 2)
3. `agents/plan-reconciler.md` — trace ledger, conflicts, rule 6/7, finalize (phase 3)
4. `skills/swarm/ears_trace.py` + `skills/swarm/tests/test_ears_trace.py` — new mechanical checker (phase 3)
5. `agents/verifier.md` — per-criterion verdicts, legacy fallback (phase 4)
6. `commands/analyze-orchestrator.md`, `commands/implement.md` (verifier dispatch) — pass `plan_index` (phase 4)
7. `skills/swarm/swarm.py` — `_ids` dedupe, selftest with criteria table (phase 5)
8. `skills/create-task/SKILL.md`, `skills/task/SKILL.md`, `skills/task/DESIGN.md`, `skills/swarm/SKILL.md` — consumers (phase 5)
9. `commands/implement.md:196` todos Satisfies text (phase 5)
10. `README.md`, `CLAUDE.md`, `docs/architecture-notes.md`, `docs/session-swarm.md` — docs (phase 5), plus `./sync.sh`

**This document describes. The plan files prescribe.**
