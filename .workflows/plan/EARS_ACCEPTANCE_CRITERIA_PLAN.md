# Plan: EARS acceptance criteria for /analyze plan sets

**Slug:** ears-acceptance-criteria
**Date:** 2026-11-11 08:08 (WIB)
**Analysis:** `.workflows/analyze/20261111-080843-E4RS_code_analyzer.md`
**Worktree:** `/home/miftah/.worktrees/claude-commands/ears-acceptance-criteria`
**Branch:** `feature/ears-acceptance-criteria` (base: `origin/main` @ `7ab5aca`)
**Phases:** 5
**Status:** reconciled
**Coordinator:** —

---

## Why

Implement candidate 1 from note Z-PYZ (also docs/session-swarm.md, "Borrowed, and worth borrowing next", item 1): EARS acceptance criteria, borrowed from Kiro specs (https://kiro.dev/docs/specs/concepts).

Why: the verifier and reconciler currently read prose requirements; EARS makes R rows machine-checkable and traceable. Read docs/architecture-notes.md sections for /analyze, the swarm, and the board skills before planning. Run ./sync.sh as part of the work.

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | /analyze writes each requirement R1..Rn in the plan index Requirements table in EARS form: "WHEN <trigger> THE SYSTEM SHALL <behavior>" (plus the other EARS patterns where they fit: ubiquitous "THE SYSTEM SHALL", "WHILE <state>", "IF <unwanted condition> THEN", "WHERE <feature>"). Keep the user raw asks verbatim beside them, since the rationale is the spec. | 1 |
| R2 | Every phase plan Proof journey traces to one or more EARS criteria by id (e.g. R2.1), so a requirement with no journey is a visible gap. | 2 |
| R3 | plan-reconciler checks the trace: every criterion has at least one owning phase and at least one Proof journey; an untraced criterion is fixed by editing the plans, or lands in Open Questions only if unowned (rule 6 / /analyze Step 8 must stay in step). | 3 |
| R4 | The verifier agent checks the list of criteria, reporting a verdict per criterion id, instead of reading prose. | 4 |
| R5 | Keep consumers working: swarm.py parse_index reads the phase table by header name, create-task maps cards from the R table, skills/task. Old plan sets without EARS must still execute (executors take the path they are handed). (+ "Run ./sync.sh as part of the work.") | 5 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | event | WHEN /analyze writes a plan index THE SYSTEM SHALL put under `## Requirements` the R table with each ask verbatim and, beneath it, an `### Acceptance Criteria` table with one row per criterion id `R{n}.{m}`. | 1 | P1.J1, P1.J4, P1.J5 |
| R1.2 | ubiquitous | THE SYSTEM SHALL phrase every criterion in one EARS pattern (ubiquitous, event `WHEN`, state `WHILE`, unwanted `IF … THEN`, optional `WHERE`, or complex) and name that pattern in the row's Pattern column. | 1 | P1.J2 |
| R1.3 | event | WHEN /analyze dispatches a phase-planner THE SYSTEM SHALL pass it the id and text of every criterion that phase owns. | 1 | P1.J3, P1.J5 |
| R2.1 | event | WHEN a phase-planner writes a Proof journey THE SYSTEM SHALL label it with a journey id `J{k}` and the criterion ids it traces. | 2 | P2.J1, P2.J2, P2.J4, P2.J5 |
| R2.2 | unwanted | IF a criterion handed to a phase-planner has no journey tracing it THEN THE SYSTEM SHALL add one, or name the criterion as untraced in the planner's return value. | 2 | P2.J3, P2.J4 |
| R3.1 | event | WHEN plan-reconciler runs THE SYSTEM SHALL report every criterion with no owning phase or no tracing journey, mechanically, from the index and the phase plans. | 3 | P3.J1, P3.J2, P3.J3 |
| R3.2 | unwanted | IF a criterion is owned but untraced THEN THE SYSTEM SHALL edit the owning phase plan to add a journey; IF it is unowned THEN THE SYSTEM SHALL assign it to a phase, and only a criterion no phase can own SHALL land in Open Questions. | 3 | P3.J3, P3.J4 |
| R3.3 | ubiquitous | THE SYSTEM SHALL state the trace rule identically in /analyze Step 8 and plan-reconciler rules 6–7. | 3 | P3.J5 |
| R4.1 | event | WHEN the verifier is handed a plan set whose index has an Acceptance Criteria table THE SYSTEM SHALL return one verdict per criterion id, with evidence. | 4 | P4.J1, P4.J2, P4.J4 |
| R4.2 | optional | WHERE an index has no Acceptance Criteria table THE SYSTEM SHALL verify per phase from Proof prose as before and mark the report `legacy`. | 4 | P4.J3, P4.J4 |
| R5.1 | event | WHEN swarm.py parses an index that carries an Acceptance Criteria table THE SYSTEM SHALL return the same phases as without it, with Satisfies R-level and deduplicated. | 5 | P5.J1, P5.J2 |
| R5.2 | event | WHEN create-task shapes cards from a plan index THE SYSTEM SHALL shape them from the R table and list each R's criteria in the parent card body. | 5 | P5.J3 |
| R5.3 | unwanted | IF an executor or checker is handed a plan set without EARS criteria THEN THE SYSTEM SHALL execute or check it as before, without error. | 5 | P5.J4 |
| R5.4 | event | WHEN the last phase completes THE SYSTEM SHALL have deployed the set with `./sync.sh` and the repo↔`~/.claude` drift check SHALL be clean. | 5 | P5.J5 |

## Scope

**In scope:** EARS criteria in the plan index (format + `/analyze` steps that write it); traced
journeys in phase plans; a trace check in the reconciler backed by a new read-only script
`skills/swarm/ears_trace.py`; per-criterion verifier verdicts and the two dispatch sites that hand
the verifier the index; consumer compatibility (`swarm.py`, create-task, skills/task, implement's
todos line); docs (README, CLAUDE.md, architecture-notes, session-swarm, swarm SKILL.md);
`./sync.sh`.

**Out of scope:** rewriting old plan sets on disk; `/do`'s brief path and `plan-generator` (no
plan index there); candidates 2–7 of the Borrowed list; `CHANGELOG.md` (left to `/up-version`).

## Invariants

1. **The format contract below is fixed.** Every phase writes and reads exactly this shape; a
   planner that wants a different shape records it in Handoffs instead of diverging.

   Plan index, inside `## Requirements`:

   ```markdown
   | ID | What the user asked for (verbatim) | Phases |
   |---|---|---|
   | R1 | <the user's words for this ask, verbatim> | 1, 2 |

   ### Acceptance Criteria

   | ID | Pattern | Criterion | Phases | Journeys |
   |---|---|---|---|---|
   | R1.1 | event | WHEN <trigger> THE SYSTEM SHALL <behavior> | 1 | P1.J1, P2.J3 |
   | R1.2 | unwanted | IF <unwanted condition> THEN THE SYSTEM SHALL <behavior> | 2 | P2.J1 |
   ```

   - Criterion id: `R{n}.{m}`, `m` from 1 within each R. Every R has ≥1 criterion.
   - Pattern vocabulary (lower case): `ubiquitous` (THE SYSTEM SHALL), `event` (WHEN … THE SYSTEM
     SHALL), `state` (WHILE … THE SYSTEM SHALL), `unwanted` (IF … THEN THE SYSTEM SHALL),
     `optional` (WHERE … THE SYSTEM SHALL), `complex` (a combination, e.g. WHILE … WHEN …).
   - EARS keywords upper case. `/analyze` fills Phases; Journeys is `—` in the draft and is filled
     by the reconciler (N>1) or by `/analyze` Step 9 (N=1) from the phase plans.
   - Journey global id: `P{phase}.J{k}`.

   Phase plan:
   - Header line after **Satisfies**: `**Criteria:** R1.1, R1.2` — the criteria this phase owns.
   - In `## Verification`, each journey is one bullet under `- Journeys:` of the form
     `  - **J{k}** · traces R1.1, R1.2 — <commands or steps> → passes when <observable end state>`.
     The neighbor check stays a separate bullet and traces nothing.

   Legacy: an index with no `### Acceptance Criteria` heading is a legacy set. Everything that
   reads criteria (checker, reconciler, verifier) treats it as "no criteria" and falls back to the
   pre-EARS behavior; nothing that executes plans (`/implement`, `/do`, swarm.py) depends on
   criteria at all.
2. The R table stays R-level with the header `| ID | What the user asked for (verbatim) | Phases |`;
   create-task reads it and `parse_index` must never take it, or the criteria table, for the phase
   table.
3. The phase table's columns do not change.
4. `python3 skills/swarm/swarm.py selftest` and `python3 skills/swarm/tests/test_plan_graph.py`
   pass at the end of every phase.
5. Rule 6/7 of `agents/plan-reconciler.md` and `/analyze` Step 8 say the same thing about
   untraced criteria (CLAUDE.md requirement).
6. Don't run `./sync.sh` before phase 5: the deployed tree must never hold a partial set.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | /analyze writes EARS criteria | R1 | `commands` | 1 | — | NORMAL | `.workflows/plan/ears-acceptance-criteria/phase-1.md` | P1-CL-A024 | — |
| 2 | Phase plans trace journeys to criteria | R2 | `agents` | 1 | — | NORMAL | `.workflows/plan/ears-acceptance-criteria/phase-2.md` | P1-CL-A025 | — |
| 3 | Reconciler enforces the trace (+ ears_trace.py) | R3 | `skills/swarm` | 4 | 1, 2 | HARD | `.workflows/plan/ears-acceptance-criteria/phase-3.md` | P1-CL-A026 | — |
| 4 | Verifier reports per criterion | R4 | `agents` | 3 | 1, 2 | NORMAL | `.workflows/plan/ears-acceptance-criteria/phase-4.md` | P1-CL-A027 | — |
| 5 | Consumers, docs and deploy | R5 | `skills` | 10 | 1, 2, 3, 4 | NORMAL | `.workflows/plan/ears-acceptance-criteria/phase-5.md` | P1-CL-A028 | — |

### Phase 1 — /analyze writes EARS criteria
**Satisfies:** R1
**Owns:** `commands/analyze.md` Step 0 (criteria derived per R), Step 3, Step 6 (criteria → phases), Step 7 planner input (`criteria:`), Step 9's N=1 Journeys fill paragraph (sole owner of the fill rule and its `ears_trace.py --fill` pointer, with a by-hand fallback), the analysis-document template's Requirement IDs, the plan index template's `## Requirements` section, the termination block's Requirements lines.
**Does not touch:** Step 8, Step 9's two verification paragraphs, the contract bullet on Open Questions, Step 11, the template's `## Open Questions` comment and the termination block's Open Questions comment (all phase 3); any agent file; any script.
**Exit criteria:** the index template carries the R table + Acceptance Criteria table exactly as Invariant 1; Step 0/6/7 instruct writing and passing criteria; grep finds `R{n}.{m}` and all six pattern names in `commands/analyze.md`.
**Done:** ✅ phase 1/5 complete (`P1-CL-A024`, 2026-11-11 08:32) — Proof J1–J5 pass; `swarm.py selftest` and `test_plan_graph.py` (27 cases) green. `**Status:**` above is left to the coordinator (swarm-tracked set); the authoritative phase status is the swarm ledger.

### Phase 2 — Phase plans trace journeys to criteria
**Satisfies:** R2
**Owns:** `agents/phase-planner.md`: input `criteria`, step 6 (one journey per criterion, traced; index fallback skips fenced examples), hard requirement on traced journeys, output format (`**Criteria:**` header, journey bullet form), return value (`criteria`, `trace`, `untraced`).
**Does not touch:** `commands/analyze.md`, reconciler, verifier.
**Exit criteria:** the planner spec's output format shows `**Criteria:**` and `**J{k}** · traces R…` journeys; the hard requirements forbid an untraced journey (other than the neighbor check) and an owned criterion with no journey.
**Done:** ✅ phase 2/5 complete (`P1-CL-A025`, 2026-11-11) — Proof J1–J5 + neighbor check pass; `swarm.py selftest` and `test_plan_graph.py` green. `**Status:**` above is left to the coordinator (swarm-tracked set); the authoritative phase status is the swarm ledger.

### Phase 3 — Reconciler enforces the trace (+ ears_trace.py)
**Satisfies:** R3
**Owns:** new `skills/swarm/ears_trace.py` (read-only checker, exit 0 clean/legacy · 1 unreadable · 2 gaps, `--json`, `--fill` prints the Journeys column values), new `skills/swarm/tests/test_ears_trace.py`, `agents/plan-reconciler.md` (ledger, conflict rows *Unowned criterion* / *Untraced criterion*, rules 6–7, finalize fills Journeys, verify step runs the script), `commands/analyze.md` Step 8 (incl. the `**The trace rule.**` paragraph), Step 9's two verification paragraphs (new "verify the trace — N = 1 too"), and every other statement of the Open Questions residue in that file (contract bullet `:161`, Step 11 refusal bullet, index template `## Open Questions` comment, termination Open Questions comment).
**Does not touch:** `swarm.py` (phase 5), verifier, planner spec, the index template's `## Requirements` section and Step 9's N=1 fill paragraph (phase 1).
**Exit criteria:** `python3 skills/swarm/tests/test_ears_trace.py` passes (clean set → 0, untraced → 2, unowned → 2, legacy → 0, missing plan → 1); `ears_trace.py` over this index prints 14 `--fill` lines; reconciler rule 7 and Step 8 carry the identical `**The trace rule.**` paragraph (J5); no statement in `commands/analyze.md` still says Open Questions holds "one thing" (J4).
**Done:** ✅ phase 3/5 complete (`P1-CL-A026`, 2026-11-11) — Proof J1–J5 + neighbor check pass; `test_ears_trace.py` (9 cases), `test_plan_graph.py` and `swarm.py selftest` green; `--fill` over this index prints 14 lines. `**Status:**` above is left to the coordinator (swarm-tracked set); the authoritative phase status is the swarm ledger.

### Phase 4 — Verifier reports per criterion
**Satisfies:** R4
**Owns:** `agents/verifier.md` (input `plan_index`, steps read the criteria table + journey traces outside fenced code blocks, return `criteria:` list, `legacy` fallback); the verifier dispatch paragraphs in `commands/analyze-orchestrator.md` (:633-645) and `commands/implement.md` (:494-505, from `**Independent verification first**` through `before landing.`) to pass `plan_index` and act on failed criteria.
**Does not touch:** `commands/implement.md` outside the Step 5a verifier paragraph (phase 5 owns `:196`), swarm scripts.
**Exit criteria:** verifier return value has `criteria: [{id, verdict, journeys, evidence}]`; both dispatch sites pass `plan_index`; a legacy index path is documented.
**Done:** ✅ phase 4/5 complete (`P1-CL-A027`, 2026-11-11) — Proof J1–J4 + neighbor check pass; `swarm.py selftest` and `test_plan_graph.py` (27 cases) green. `**Status:**` above is left to the coordinator (swarm-tracked set); the authoritative phase status is the swarm ledger.

### Phase 5 — Consumers, docs and deploy
**Satisfies:** R5
**Owns:** `skills/swarm/swarm.py` (`_ids` dedupe + selftest fixture with an Acceptance Criteria table and a legacy fixture; `parse_index` untouched), `skills/swarm/SKILL.md` (document `ears_trace.py` incl. its five gap kinds; step 6b names per-criterion verdicts), `skills/create-task/SKILL.md` (parent body lists criteria), `skills/task/SKILL.md` + `skills/task/DESIGN.md` (R → criteria mention), `commands/implement.md:196` (todos Satisfies line), `README.md` (EARS paragraph, Open Questions residue, verifier row, Proof paragraph, `ears_trace.py` line, tree), `CLAUDE.md` (rules 6–7, trace rule), `docs/architecture-notes.md` (rules 6–7, Open Questions residue, EARS paragraph), `docs/session-swarm.md` (move item 1 to "already borrowed"), then `./sync.sh` and the drift check.
**Does not touch:** anything phases 1–4 own.
**Exit criteria:** selftest passes including the new fixtures (and fails with the old `_ids`); `test_plan_graph.py` and `test_ears_trace.py` pass from the repo and from `~/.claude`; drift check prints nothing beyond pre-existing deploy-only `Only in ~/.claude/skills` lines.

**Done:** ✅ phase 5/5 complete (`P1-CL-A028`, 2026-11-11) — Proof J1–J5 pass; `swarm.py selftest`, `test_plan_graph.py` (27) and `test_ears_trace.py` (9) green from repo and `~/.claude`; `./sync.sh` deployed, drift clean. `**Status:**` above is left to the coordinator (swarm-tracked set); the authoritative phase status is the swarm ledger.

## Reconciliation Log

Round 1. Ledger: no symbol is deleted or renamed across phases (the only rename is phase 1's R
table header text, which no script reads). Files touched by two phases: `commands/analyze.md`
(1 → 3) and `commands/implement.md` (4 → 5). Every phase's Find text was dry-run on a scratch copy
of `7ab5aca` in DAG order (phase 1's 9 edits, then phase 3's 7 on `analyze.md` and 8 on
`plan-reconciler.md`: every Find matched exactly once); phase 1's J1–J4 and phase 3's J4/J5 pass on
the result. Phase 3's draft `ears_trace.py` (run from that scratch copy) passes its 9 test cases and
reports this set clean: 14 criteria, every one owned and traced (exit 0); the Journeys column
above is its `--fill` output.

| # | Conflict | Class | Resolution |
|---|---|---|---|
| 1 | N=1 Journeys fill described in phase 1 (by hand) while phase 3 suggested pointing it at `ears_trace.py --fill` — two possible owners of one sentence | Duplicate work | Phase 1 owns the paragraph and now carries the `--fill` sentence with a by-hand fallback (the script exists only after phase 3, deployed only by phase 5). Phase 3's Step 10 refers to `--fill` only when fixing a gap; its Handoff rewritten. |
| 2 | Index Phase 2 summary named return key `criteria_traced`; phase 2 plan returns `criteria`, `trace`, `untraced` | Contract drift | Index fixed to phase 2's keys. Phases 1 and 3 do not consume the keys (the reconciler and Step 9 re-derive from the plan files via `ears_trace.py`), recorded in phase 2's Handoffs. |
| 3 | Phase 2 lets a planner list a criterion as `untraced` when only a later phase can observe it, but phase 3's trace rule only said "add a journey to the owning plan" | Unmet assumption | Trace rule (both copies, reconciler rule 7 and `/analyze` Step 8, still identical — J5 passes) gains one sentence: such a criterion moves to the later phase named in Handoffs and gets its journey there. |
| 4 | Phase 3 made rule 6, Step 8 and Step 9 admit an unownable requirement/criterion to Open Questions, but `commands/analyze.md`'s contract bullet (`:161`), Step 11 refusal bullet, index template `## Open Questions` comment and termination comment still said Open Questions holds "one thing" | Gap | Assigned to phase 3 (owner of Open Questions semantics) as new Step 11, four Find/Replace edits, outside phase 1's regions (dry-run verified). Phase 3 J4 now asserts no "one thing" wording survives. |
| 5 | Verifier (phase 4) and planner's index fallback (phase 2) read the criteria table / journey bullets with no fence-skipping, while this very index quotes the table in a fenced example (read naively it yields 16 criteria instead of 14 — phase 3 measured it) | Contract drift | Phase 4's checklist gains a **Fences** bullet and the exact bullet form with its U+00B7 / U+2014 / U+2192 separators; phase 2's step 6 fallback ignores fenced copies. All four readers (template, planner, checker, verifier) now agree on form and fence-skipping. |
| 6 | Phase 4 handed `skills/swarm/SKILL.md:384-385` (step 6b verifier summary) to phase 5, which had no step for it | Gap | Added to phase 5 Step 4 as a second edit; phase 5 Files table updated. |
| 7 | Phase 3 asked phase 5 to document the five gap kinds and that `/analyze` Step 9 runs the script; phase 5's SKILL.md text named only two | Gap | Phase 5 Step 4 text now lists all five gap kinds, fence-skipping, and Step 9. |
| 8 | `docs/architecture-notes.md:131-136` still said "rule 6" and "unowned requirement id" only; phase 5 added a paragraph after it but left the sentence | Gap | Phase 5 Step 11 also replaces "rule 6" → "rules 6–7" and adds "or criterion" to the Open Questions residue. |
| 9 | Phase 1's Handoff claimed a +91 line shift at Step 8; phase 3 assumed +54 | Contract drift | Measured by dry run: Step 8 `:370 → :424` (+54), "Before terminating" `:414 → :475` (+61). Phase 1's Handoff corrected; both phases anchor by text anyway. |
| 10 | `commands/implement.md` shared by phase 4 (`:494-505`) and phase 5 (`:196`) | File collision (checked) | No overlap: phase 5's Find (`- **Satisfies**: {R id(s)} — …`) is 300 lines above phase 4's region, and phase 5 depends on 4, so phase 4's neighbor check (hunks only in 494–505, phase 5 not yet landed) is correctly stated. No edit. |
| 11 | Phase 3 asked phase 5 to consider a fence guard in `swarm.parse_index` | Requirement creep (proposed) | Declined: phase 5 leaves `parse_index` untouched (Decisions). |
| 12 | Phase 5 file count in the phase table said 11; its Files table lists 10 | Contract drift | Phase table fixed to 10. |
| 13 | Phase 4 handoff on `ears_trace.py --json` fields left open | Unmet assumption | Settled: the verifier relies on no JSON field beyond the criterion ids; the table is the source. |

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| criteria inside the R table vs a separate table | separate `### Acceptance Criteria` table under `## Requirements`; R table keeps R-level rows | 4: Requirements (R5 — create-task maps cards from the R table) |
| "machine-checkable" by prose instruction vs a script | new read-only `skills/swarm/ears_trace.py`, modelled on `plan_graph.py` | 4: Why ("makes R rows machine-checkable") |
| when to run `./sync.sh` | once, at the end of phase 5 | 6: convention (deploy a coherent tree) |
| who owns the N=1 Journeys-fill sentence and its `--fill` pointer | phase 1 (it owns the paragraph); phase 3 only refers to `--fill` when fixing a gap | 1: invariant ("one owner per file region", Invariant 1 assigns the N=1 fill to `/analyze` Step 9) — plus phase 1's exit criteria and J4 needles |
| does the reconciler consume the planner's `criteria`/`trace`/`untraced` return keys, or re-derive them | re-derive from the plan files with `ears_trace.py`; the keys are a mirror for the summary | 4: Why ("machine-checkable") — the files are what the script reads |
| an owned criterion the owning phase cannot observe (planner's `untraced`) | the trace rule moves it to the later phase named in Handoffs and adds the journey there | 3: code blocks — phase 2's step 6 ("say in Handoffs which phase can prove it") and phase 3's rule 7 ("criterion ids follow the work") |
| Open Questions: "one thing" (Step 11, contract bullet, templates) vs "an all-irreversible fork or a requirement/criterion no phase can own" (rule 6, R3.2) | the latter, everywhere in `commands/analyze.md` | 4: Requirements (R3: "lands in Open Questions only if unowned"; R3.2) |
| keep phase 3's extra gap kinds `misassigned`, `unclaimed`, `unknown_id` beyond the brief's unowned/untraced | keep: they are bookkeeping disagreements between a plan's `**Criteria:**` line, the table and journey ids, fixed by editing plans, never parked | 3: code blocks (phase 3's tested script) — consistent with R3.1/R3.2 |
| fence-skipping when reading criteria tables and journey bullets | every reader (checker, verifier, planner fallback) skips fenced code blocks | 1: invariant (Invariant 1 fixes the format; a quoted example is not the format in use) — measured: this index's fenced example adds 2 phantom criteria |
| add a fence guard to `swarm.parse_index` | no; `parse_index` stays untouched | 1: invariant (Invariants 3–4: phase table unchanged, selftest green) and phase 5's contract ("`parse_index` itself is not changed") |

## Open Questions

## Rollback

Per phase: `git revert <phase commit>` — each phase touches a disjoint file set except
`commands/analyze.md` (1 then 3) and `commands/implement.md` (4 then 5), which revert in reverse
order. Whole set: revert the merge, then `./sync.sh` to redeploy the previous tree.

## Next

Run the whole set as a swarm:

    /analyze-orchestrator -f .workflows/plan/EARS_ACCEPTANCE_CRITERIA_PLAN.md
