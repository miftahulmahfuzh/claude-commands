# Plan: Fix and harden the swarm write-set gate

**Slug:** swarm-write-set-gate
**Date:** 2026-10-27 08:48:29
**Analysis:** `20261027-084829-ROCQ_code_analyzer.md`
**Worktree:** `~/.worktrees/claude-commands/swarm-write-set-gate`
**Branch:** `feature/swarm-write-set-gate` (base: `origin/main` @ `471d34a`)
**Phases:** 3
**Status:** phase 1/3 complete
**Reconciled:** 2026-10-27, round 1 — 11 conflicts, 11 resolved, Open Questions empty
**Coordinator:** —

---

## Why

The user's rationale, verbatim — this is the specification:

> Four findings in this repo (~/claude-commands), found 2026-10-27 by a session running the swarm
> tooling against a real plan set. R1 is load-bearing; the rest range from important to a nit.
> Evidence below is measured, not inferred — but VERIFY EACH YOURSELF rather than trusting this text.
>
> Context that shapes every fix: this repo is the SOURCE for ~/.claude/{commands,agents,skills},
> installed by sync.sh, which COPIES (sync.sh:68,74,81) rather than symlinking. [...] So (a) editing
> here cannot break a running swarm, and (b) no fix takes effect until merge AND a sync.sh run — the
> plan must say so explicitly, and the final verification must assert against the INSTALLED copy, not
> just the repo.
>
> R1 — plan_graph.py cannot find the repo root inside a git worktree, so the write-set gate analyses
> nothing on every plan set /analyze produces. [...] Candidate fix, verified to resolve correctly:
> os.path.isdir -> os.path.exists on that line. Confirm it, then decide whether
> `git rev-parse --show-toplevel` is the better root-finder (it handles worktrees, submodules and
> .git files uniformly) — your call, but justify it. Whatever you pick, REGRESSION-TEST THE WORKTREE
> CASE [...] That is the case that was never covered.
>
> R2 — the gate is advisory, not enforcing. [...] Make the gate a gate: a hard stop on 1 (analysis
> never ran) and on 2 (a real concurrent collision), each with the specific remediation already
> tabulated in skills/swarm/SKILL.md's ISOLATE/ORDER/BLOCK table. Preserve the documented escape
> hatch shape used elsewhere in these commands rather than inventing a new flag spelling; find the
> convention first.
>
> R3 — integrator.md and plan_graph.py are hardcoded to a different project ("seer"). [...] These are
> global tools; pointed at any other repo they run suites that do not exist and misclassify that
> repo's real generated artifacts. [...] Make the generated/binary artifact list and the test command
> PER-REPO rather than baked in. Design the mechanism yourself [...] Keep the seer values working as
> a case of the new mechanism, not as a hardcoded default, and do not regress those plan sets.
>
> R4 — dead code in plan_graph.py. [...] Harmless today (comprehension scope is separate in py3) but
> actively misleading. Delete it, or if it was meant to detect a path classified differently by two
> phases, implement that intent deliberately and test it.
>
> BOOTSTRAP HAZARD worth planning around: if this work is decomposed into several phases and
> orchestrated, the orchestrator will run the BROKEN plan_graph.py as its own write-set gate. Sequence
> so R1 lands (and is synced) before anything depends on the gate being trustworthy, or state plainly
> in the plan that the gate is untrusted for this particular set and why.
>
> OUT OF SCOPE: anything in ~/agentic or its Hugo docs site. The custom-home.html popup refactor
> discussed in the originating session is a different repo and a different piece of work.

## Requirements

Final after reconciliation — this is what `create-task` reads, and it matches the plans.

| ID | What the user asked for | Phases |
|---|---|---|
| R1 | Fix `plan_graph.py`'s repo-root discovery so the gate works inside a git worktree; justify the root-finder; regression-test the worktree case. Includes the false all-clear the user's own text names ("while simultaneously printing the reassuring line 'no file is written by two phases.'") | **1** (all of it), **2** (one line: the `README.md` Project Structure entry for the `skills/swarm/tests/` harness phase 1 ships — phase 1 edits no markdown) |
| R2 | Make the gate enforcing — `/analyze-orchestrator` hard-stops on exit 1 and 2 with class-specific remediation, using the repo's existing escape-hatch convention | 3 |
| R3 | Make the generated/binary artifact list and the integrator's test commands per-repo; design and argue the mechanism; keep the seer values working as data | 2 |
| R4 | Remove the dead `kinds` comprehension, or implement its intent deliberately and test it | 1 |

Every `R` is owned. No requirement is unserved, so **Open Questions is empty.**

## Scope

**In scope**
- `skills/swarm/plan_graph.py` — root discovery, fallback, severity selection, per-repo config
- `skills/swarm/tests/` (new) — a dependency-free regression harness, worktree case included
- `commands/analyze-orchestrator.md` — Step 3b enforcement + escape hatch in the flag block
- `agents/integrator.md` — remove seer-specific paths and test commands
- `skills/swarm/SKILL.md` — exit-code/enforcement prose; per-repo configuration section
- `README.md` — only if a new indexed asset is introduced

**Out of scope** (user stated explicitly)
- `~/agentic` and its Hugo docs site; the `custom-home.html` popup refactor — a different repo.
- `swarm.py` behaviour changes. `plan_graph.py` may *import* more from it; it must not alter it.
  `parse_index` and `waves` are consumed by the orchestrator and the ledger, and a change there
  reaches far more than this gate.
- The `.workflows/` schema and the ledger split. Untouched.

## Invariants

Every phase must hold all of these:

1. **The repo is the source; `~/.claude/` is a copy.** Never edit anything under `~/.claude/`
   directly (CLAUDE.md). Edit the repo file, then `./sync.sh`.
2. **No fix is live until merge *and* a `sync.sh` run.** Every phase's exit criteria must include
   a verification run against the **installed** `~/.claude/skills/swarm/plan_graph.py`, not only
   the repo copy. The two trees must agree at the end:
   `for d in skills agents commands; do diff -rq --exclude=__pycache__ --exclude='.*' "$d" ~/.claude/"$d"; done`
3. **`plan_graph.py` stays read-only** — "It spawns nothing and writes nothing" (module docstring).
   The tests may create throwaway trees; the module may not.
4. **Python 3 standard library only.** No third-party dependency, no new runtime requirement.
   `git` absence must degrade (return `None`), never raise — the `git()` helper at `swarm.py:107`
   already has this shape.
5. **The exit-code contract is load-bearing and does not change meaning:** `0` clean, `1` the plan
   could not be read, `2` a concurrent collision. Phase 3 makes callers *honour* it; no phase
   redefines it.
6. **Never downgrade a severity.** BLOCK > ORDER > ISOLATE. Where a path is classifiable two ways,
   the most severe wins — a wrong ISOLATE on a database is the one error whose cost is unrecoverable
   rows (SKILL.md's BLOCK row).
7. The tree builds and the test harness passes at the end of each phase.

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Gate correctness: worktree root discovery + severity selection | R1, R4 | `skills/swarm` | 2 | — | NORMAL | `.workflows/plan/swarm-write-set-gate/phase-1.md` | P1-CL-A021 | — |
| 2 | Per-repo artifact classes and test commands | R3, R1 (one README line) | `skills/swarm`, `agents` | 5 | 1 | HARD | `.workflows/plan/swarm-write-set-gate/phase-2.md` | P1-CL-A022 | — |
| 3 | Make the gate a gate: enforce exits 1 and 2 | R2 | `commands`, `skills/swarm` | 2 | 1 | NORMAL | `.workflows/plan/swarm-write-set-gate/phase-3.md` | P1-CL-A023 | — |

**Progress:** phase 1 ✅ complete (`P1-CL-A021`, 2026-10-27) — `skills/swarm/plan_graph.py`
root discovery and severity selection fixed, `skills/swarm/tests/test_plan_graph.py` added
(13 cases). Phases 2 and 3 are unblocked and are wave 1. The per-phase tick lives here rather
than in the table above because `swarm.py parse_index` reads every phase-table cell by name and
requires the `#` cell to be a bare integer — a status column would diverge this index from the
one `/analyze` generates. The authoritative phase status is the swarm ledger.

**Bootstrap hazard: closed by phase 1.** The installed gate, run against this set's own index
after phase 1's `./sync.sh`, now exits `2` and names `skills/swarm/SKILL.md` as CONCURRENT /
ISOLATE between phases 2 and 3, with the other two shared files sequential — agreeing exactly
with the hand-declared write-set table below. The coordinator may now trust the gate's output
for this set instead of the hand-declared table.

### Phase 1 — Gate correctness: worktree root discovery + severity selection
**Satisfies:** R1, R4
**Owns:**
- `skills/swarm/plan_graph.py`, four regions: the import line (`:27`, adding `git`); `build()`'s
  root discovery (`:78-85`), replaced by a new `find_root()`/`_ancestors()`/`ROOT_LOOKUP_DEPTH`
  block and a `parse_index`-first reordering that adds a `"root"` key to the returned dict; the
  collision loop's dead `kinds` comprehension and first-wins `kind` (`:114-116`), replaced by
  `SEVERITY`/`SEVERITY_UNKNOWN`/`most_severe()`; and `render()` (`:154-184`), whose all-clear
  becomes conditional with two `INCOMPLETE:` forms plus a `resolved against root:` diagnostic.
- `skills/swarm/tests/` (new directory) — the regression harness, and the worktree case in
  particular. The repo has no test runner (CLAUDE.md: "no lint, no test runner, no CI"), so the
  harness must be self-contained and runnable as `python3 skills/swarm/tests/test_plan_graph.py`.
  13 cases; phase 2 appends 12 more.
**Does not touch:** `classify()`, `GENERATED`, `REGENERATED_TEXT` (phase 2 owns those);
`commands/analyze-orchestrator.md`, `SKILL.md` (phase 3 owns the exit-code prose, phase 2 the
class table and config section); **`README.md` — no markdown at all is in this phase's diff**,
including the Project Structure line for the `tests/` directory it creates, which is phase 2's;
`swarm.py` (out of scope — one more name is imported from it, not a byte changed in it).
**Exit criteria:**
- A plan set inside a **linked worktree** resolves its phase plans; the gate reports real write
  sets and exits `0` or `2`, never `1` for that reason. This is the case that was never covered.
- The main-checkout case and the outside-a-repo case still behave.
- Both `/analyze` index layouts resolve — `<wt>/docs/plans/X_PLAN.md` **and** `<wt>/X_PLAN.md`.
  The current `dirname(dirname(...))` fallback is wrong for both (see the analysis's table); the
  replacement fallback must be correct, not merely correct-by-accident.
- Two phases declaring one path with different actions yield the **most severe** class, not the
  first phase's, with a test that fails against today's code.
- **The all-clear is conditional.** `no file is written by two phases.` is printed only when every
  phase plan was read (`grep -c` returns exactly 1 in the module); otherwise the gate prints
  `INCOMPLETE: no collision among the K of N phases whose plan could be read. …`, and the
  concurrency tally gains `INCOMPLETE: computed over K of N phases. …`. The missing-plans block
  names `resolved against root: <path>`. These are the exact strings phase 3 quotes.
- `python3 skills/swarm/tests/test_plan_graph.py` passes with **13 cases**, and the same harness
  **fails** against `git show HEAD:skills/swarm/plan_graph.py`.
- Verified against the installed copy after `./sync.sh`.

### Phase 2 — Per-repo artifact classes and test commands
**Satisfies:** R3; plus **one line of R1** — the `README.md` Project Structure entry for the
`skills/swarm/tests/` harness phase 1 ships, assigned here because `README.md` is this phase's
file and phase 1 edits no markdown.
**Owns:**
- `skills/swarm/plan_graph.py` — the module docstring, `GENERATED`/`REGENERATED_TEXT`/`classify()`
  (replaced by `CONFIG_PATH`, `BASELINE_BINARY`, `load_config`, `_norm`, `_match`,
  `gitattributes_classes` and a four-argument `classify`), and exactly three regions of phase 1's
  code: `build()`'s **file loop** (from `writes, missing = {}, []` to the
  `writes.setdefault(...)` line), `build()`'s **`return` statement** (which must keep phase 1's
  `"root"` key), and `render()`'s opening `out = [...]` statement (one `artifact classes:` line).
- `agents/integrator.md` — steps 2 and 4: the seer regeneration recipe and the seer test commands.
- `skills/swarm/SKILL.md` — the ISOLATE/ORDER/BLOCK table (`:39-44`) and a **new** per-repo
  configuration section inserted at `:50`. **Boundary: every edit is at line ≥ 39; do not touch
  the exit-code paragraph at `:32-34`, which phase 3 owns and is editing concurrently.**
- `README.md` — sole writer: the `### swarm` block, the project `.workflows/` tree, and the
  Project Structure `swarm/` line.
- The test harness phase 1 created — **append 12 `@case` functions** (13 → 25) and `import json`.
  Extend it; do not restructure it.
**Does not touch:** phase 1's `find_root`/`_ancestors`/`ROOT_LOOKUP_DEPTH`,
`SEVERITY`/`SEVERITY_UNKNOWN`/`most_severe`, `build()`'s `parse_index`-first ordering and root
discovery, `build()`'s collision loop, or `render()`'s missing-plans block, conditional all-clear
and two `INCOMPLETE:` lines; `commands/analyze-orchestrator.md` (phase 3); `swarm.py`.
**Exit criteria:**
- No `seer`-specific path, filename, or command remains in `plan_graph.py` or `integrator.md`.
  `grep -rn "seer\|lab\.json\|lab\.sqlite\|lab\.xlsx" skills/swarm/plan_graph.py agents/integrator.md`
  returns nothing but documentation-of-the-example.
- A repo with no configuration still classifies sensibly from a project-agnostic baseline, and the
  Hugo `resources/_gen/` case the user named classifies as ORDER once declared.
- The seer values are reproducible **as a case of the mechanism** — a worked example in SKILL.md —
  not as a built-in default. The mechanism is argued in the plan, not merely chosen.
- `integrator.md` derives its suite from the repo instead of naming one. The ladder at
  `skills/task/DESIGN.md:239-242` (package.json scripts → Makefile → pytest → cargo → go test) is
  existing prior art in this repo for exactly that problem; reuse its shape rather than inventing one.
- **Phase 1's work survives this phase.** `build()`'s returned dict still carries `"root"`;
  `grep -c "no file is written by two phases" skills/swarm/plan_graph.py` is 1 and
  `grep -c "INCOMPLETE:"` is 2; the harness reports **25 cases**, phase 1's 13 included, and none
  of phase 1's assertions regress.
- **No new merge class is minted**, so phase 1's `SEVERITY` needs no row and `_verdict()` no
  branch. `classify()` still returns only `read`/`binary`/`generated`/`create`/`modify`.
- `README.md` names `.workflows/swarm.json` twice **and** `tests/` in the Project Structure tree.
- Verified against the installed copy after `./sync.sh`.

### Phase 3 — Make the gate a gate: enforce exits 1 and 2
**Satisfies:** R2
**Owns:**
- `commands/analyze-orchestrator.md` — Step 3b (lines 181-220) becomes a hard stop; the flag block
  (lines 6-13) gains the escape hatch.
- `skills/swarm/SKILL.md` — the exit-code paragraph at **lines 32-34** (grown in place) and
  enforcement prose. **Boundary: nothing at or after line 35. Do not edit the ISOLATE/ORDER/BLOCK
  table (`:39-44`), the measured-sets paragraph (`:46-49`), or add a configuration section;
  phase 2 owns those.** Four unchanged lines (35-38) separate the two phases' hunks — measured
  clean through `git merge-file` during reconciliation, with a one-line margin.
**Does not touch:** `plan_graph.py` at all. The exit codes are already correct and deliberate; this
phase changes only who honours them. Also does not touch `commands/analyze-orchestrator.md`
Step 4, which keeps its three `--isolate` references (see Decisions).
**Exit criteria:**
- Step 3b refuses to spawn on exit 1 (the analysis never ran) and on exit 2 (a real concurrent
  collision), each naming the class-specific remediation from SKILL.md's ISOLATE/ORDER/BLOCK table.
- The escape hatch uses the repo's **existing** convention — `--no-gate`, established at
  `skills/task/DESIGN.md:159` and `skills/task/task_gh.py:2617`, with the refusal-message shape at
  `task_gh.py:1994-1999` ("…Pass `--no-gate` to land anyway, on purpose"). Do not coin a new spelling.
- The refusal is a **stop, not a block** — iron rule 4. It reports and ends; it never prompts.
  Consistent with the existing "A stop is a failure with a reason […] never a prompt someone has to
  come back to" at `analyze-orchestrator.md`.
- `DESIGN.md:239-242`'s ladder is honoured in spirit: an unattended coordinator that reaches for
  `--no-gate` must **say what it checked instead**, because the flag "was written to be typed by a
  human who is, by construction, asleep."
- **The refusal quotes the gate as phase 1 leaves it.** `INCOMPLETE: no collision among …` and
  `resolved against root:` both appear in Step 3b; `no file is written by two phases` appears at
  most once, and only inside the note explaining that phase 1 fixed it.
- **No instruction to pass `spawn --isolate`.** The ISOLATE remedy is `git worktree add` plus
  `swarm.py spawn --cwd`; any `--isolate` inside Step 3b is the sentence saying the flag does not
  exist.
- Verified against the installed copy after `./sync.sh`.

## Reconciliation Log

Round 1, 2026-10-27. Eleven conflicts found, eleven resolved **by editing the plan files**; none
deferred. Every claim below was verified against the repo rather than taken from the brief.

| # | Class | Conflict | Resolution (edits made) |
|---|---|---|---|
| 1 | **Stale quote** | Phase 3 was drafted before phase 1's render amendment and built its exit-1 refusal around the gate printing `no file is written by two phases` — which phase 1 makes impossible on that branch. Also in phase 3's `SKILL.md` replacement ("the all-clear line the gate prints in that state is affirmatively false"). | Phase 3's **Exit 1** section rewritten to quote the real post-phase-1 output: the `phase plans not found` block with `resolved against root: <path>`, and `INCOMPLETE: no collision among the K of N phases whose plan could be read. …`. The old sentence survives only as a historical note naming it as the bug phase 1 fixed, with "if it ever appears alongside exit 1, phase 1's render guard has regressed". `SKILL.md` replacement reworded the same way. New **Requires** bullet binds phase 3 to phase 1's render changes; new exit criterion **7b** and verification check **6** grep for it. |
| 2 | **Deleted-then-used** (silent) | Phase 2's Step 5 gives a complete replacement for `build()`'s `return` statement that **omits phase 1's `"root"` key**. `render()` prints `g.get('root')`, so the key's loss does not raise — it prints `resolved against root: None` and fails four of phase 1's assertions. The set's most dangerous conflict after #1, because nothing errors. | `"root": repo` restored to phase 2's return block with an inline comment and a callout box above it. Phase 2's **Requires** and the index's phase-2 **Owns** both name it. Phase 2's `test_end_to_end_config_flips_the_verdict` now asserts `g["root"]` is the worktree, so the regression is caught by the harness and not only by review. Phase 1's handoff names it too. |
| 3 | **File collision / stale anchors** | Phase 2's Step 4 anchors on `plan_graph.py:90-102` of `origin/main`, but phase 1 replaces the whole of `build()`. Its promise to "leave `build()`'s root discovery and the collision loop alone" was stated only as prose, so an executor working from line numbers could revert phase 1's work inside the same function. | Step 4 rewritten to reproduce **`build()` as phase 1 leaves it**, every line marked `PHASE 1 — leave` or inside the owned block, with the boundary stated explicitly: "begins at `writes, missing = {}, []`, ends at `writes.setdefault(path, []).append(p["n"])`". Added the ordering constraint that `load_config(repo)` must follow `repo = find_root(...)`. |
| 4 | **File collision / contract drift** | Phase 2's Step 5 also replaces "the first statement of `render()` (lines 157-159)" — a function phase 1 rewrote end to end. Separately, phase 1's contract claims its clean output is "byte-for-byte unchanged", which phase 2's new header line makes false. | Phase 2's render edit restated as a **find/replace on the `out = [...]` statement**, with the three phase-1 regions it must not touch listed by name. Phase 1's contract amended: the guarantee is scoped to the **final sentence and the collision tally**, with a note that phase 2 prepends a header line and that `test_clean_set_keeps_the_exact_old_sentence` (`endswith` + `"INCOMPLETE" not in text`) survives it by construction. |
| 5 | **Duplicate work / unrunnable code** | Phase 2's Step 12 appended plain `def test_…()` functions using bare `assert`, plus its own `_git_repo`, `_index` and `_phase_plan` fixtures. Phase 1's harness runs **only** functions registered with `@case`, so **every one of phase 2's twelve cases would have silently never run** — a green harness proving nothing. Phase 1 also already ships `make_repo`, `add_worktree`, `write`, `plan_set`, `phase_plan`, `git`, `gate_exit`, `collision`, `_real`. | Step 12 rewritten in full against phase 1's real conventions: `@case` on every function, `eq`/`ok` instead of `assert`, the three duplicate fixtures deleted in favour of phase 1's, `_cfg` and a new `_write_cfg` kept, `tempfile`/`shutil` cleanup in phase 1's try/finally style, and the end-to-end case moved into a real linked worktree. The adaptation note is gone — phase 2 now names each helper's signature in a table. `import json` specified as the one import to add. |
| 6 | **Count drift** | Phase 2 said "eleven new cases" and listed twelve. | Corrected to **12**; harness total stated as **25** (phase 1's 13 + 12), added to both plans' exit criteria and the index, with the failure signatures spelled out (a run reporting 13 means the decorators were dropped). |
| 7 | **Gap** | `skills/swarm/tests/` is a new shipped skill asset that CLAUDE.md's "Adding a new skill" rule says must be named in `README.md`'s Project Structure tree. Phase 1 edits no markdown; phase 2 explicitly assumed "no new shipped asset". **No phase owned the line.** | Assigned to **phase 2**, which already owns `README.md` (rule: one owner per file region; a second README writer would cost the hand-declared write-set table its single-writer row). Step 11 gained a find/replace for `README.md:841`. The `R` followed the work: phase 2's **Satisfies** line, the index phase table and the Requirements table all now show **R1 → phases 1, 2**. |
| 8 | **Phantom mechanism** | `spawn --isolate` does not exist — `grep -c isolate skills/swarm/swarm.py` is **0**; `spawn`'s argparse (`swarm.py:2113-2124`) defines `--slug --phase --prefix --prompt --cwd --permission-mode --model --force --no-trust --dry-run`. Phase 3's ISOLATE branch still framed `git worktree add` + `--cwd` as a fallback "where that flag is not available on this install". (Checked: phase 2 contains **no** `--isolate` claim — the brief's item 2 does not apply to it.) | Phase 3's ISOLATE branch now states `git worktree add <path> <branch>` + `swarm.py spawn --cwd <path>` as **the** mechanism, in a code block, with the grep result and the argparse line range as evidence, and names `:237`, `:255`, `:383` as wrong-but-out-of-scope. Handoff rewritten as a recorded leave-behind. New exit criterion **7c** and verification check **7**. No fix is planned for the three stale lines — they serve none of R1-R4. |
| 9 | **Unverified ISOLATE** (the set's one real collision) | Phases 2 and 3 both write `skills/swarm/SKILL.md` concurrently in wave 1, and the ISOLATE classification rested on a 4-line gap nobody had tested — while the gate that would catch a bad call is the broken thing being fixed. | **Verified against the real file.** Exit-code paragraph is `:32-34` (the index said `~31-33`); class table `:39-44`; measurement `:46-49`; phase 2 inserts at `:50`. Both sides' actual replacement texts were applied and merged with `git merge-file`: **rc=0, zero conflict markers, both edits present**. ISOLATE stands. The measurement and a "re-run this if either side grows to touch line 35 or 38 — the margin is one line" warning were added to phase 3; the index's phase-3 block now says `:32-34`, as does phase 2's boundary note. |
| 10 | **Contract drift (resolved as a no-op)** | Phase 1's handoff requires that any class phase 2 mints get both a `SEVERITY` row and a `_verdict()` branch; phase 2 never said whether it mints one. | Checked every `return` in phase 2's new `classify()`: `read`, `binary`, `generated`, `create`, `modify` — **no new class**. Both plans now state it explicitly, phase 2 in Step 4's Impact and phase 1 in its handoff, each keeping the conditional as the standing rule for a later change. Index exit criteria record it. |
| 11 | **Dangling scope question** | Phase 2 left `commands/analyze-orchestrator.md`'s seer paths "to Phase 3, or to a follow-up if Phase 3's rewrite does not reach those lines" — and phase 3's rewrite deliberately carries them across verbatim. An unowned residue either way. | **Decided, not parked** (see Decisions): the lines are a *measurement* of `journal-versioning`, not a hardcoded tool value, and R3's exit-criterion grep is scoped to `plan_graph.py` and `integrator.md` where the behaviour lives. Phase 2's handoff rewritten from "left to… or a follow-up" to a closed decision. |

**Unchanged and re-verified:** the dependency edges (1 → 2, 1 → 3; both backward-pointing, no
cycle); all six Impact Points in the analysis are owned; every Reference List entry maps to a
phase; file counts 2 / 5 / 3 → **2 / 5 / 2** as the phase table says; and each phase still builds
green alone — phase 1 because `render()`/`build()` land together, phase 2 because its harness
additions run against its own new code, phase 3 because it ships only prose.

**Contract moved between phases:** yes — one README line (conflict 7) moved from nobody to
phase 2, and phase 2's `return`-statement edit was corrected to preserve a phase-1 creation
(conflict 2). Neither moves a deletion or a rename, and no plan was written against the old
arrangement, so no further round is required.

## Decisions

| Fork | Chosen | Rung |
|---|---|---|
| Root-finder: `os.path.exists` walk vs `git rev-parse --show-toplevel` | **`git rev-parse --show-toplevel` via `swarm.py`'s existing `git()` helper, with the `exists()` walk retained as the no-git fallback.** Measured: both resolve worktree, main checkout and submodule identically, but `rev-parse` returns `None` cleanly outside a repo where the walk runs to `/` and needs a fallback that is currently wrong. `plan_graph.py` already imports from `swarm.py` (line 27), and `swarm.py:161 main_worktree()` is the same tool answering the same class of question — so this is reuse of house style, not a new dependency. `git()` already maps `OSError` to `None`, satisfying invariant 4. | 6: surrounding convention (`swarm.py` shells to git for root discovery), on measured evidence |
| Phase 2 and phase 3 both edit `skills/swarm/SKILL.md` | **Keep them concurrent with disjoint section ownership**, stated in each phase's Owns/Does-not-touch. Phase 2 owns the ISOLATE/ORDER/BLOCK table and the new configuration section; phase 3 owns the exit-code paragraph. This is exactly the ISOLATE class — separate worktrees merge cleanly when the line regions are disjoint — and SKILL.md's own guidance is that "same file" is not "same lines". A dependency edge declared here would be the "dependency declared out of caution" that `/analyze` Step 6 warns costs real parallelism. **Isolate wave 1 by cutting a worktree per phase and passing `spawn --cwd`.** NOTE: `spawn --isolate` does NOT exist — `swarm.py` has zero occurrences of `isolate`, though `analyze-orchestrator.md:237,255,383` instruct it. `spawn` accepts `--slug --phase --prefix --prompt --cwd --permission-mode --model --force --no-trust --dry-run`. Use `git worktree add` + `spawn --cwd <wt>`. | 4: the index's Why/Requirements + SKILL.md's own ISOLATE remedy, on a mechanism verified to exist |
| Phase 2 depends on phase 1 although they touch different functions | **Keep the edge.** Both write `plan_graph.py`; phase 1 is the bootstrap-critical fix that must land and sync first, and serialising a two-region edit to one 205-line file costs one wave against a real risk. | 6: surrounding convention — the set's own BLOCK/ISOLATE reasoning applied to itself |
| `lab.xlsx` currently sits in `REGENERATED_TEXT` (→ ORDER) though an xlsx is a binary (→ BLOCK) | **Preserve the existing classification when migrating it to configuration.** The user said "do not regress those plan sets". Phase 2 must carry it across as-is and note the discrepancy in SKILL.md rather than silently re-classifying it; a severity *upgrade* is still a behaviour change to a shipped set. | 5: the user's raw input ("do not regress those plan sets") |
| R4: delete the dead comprehension, or implement its intent | **Implement the intent.** Measured: it is not merely misleading — `kind` at line 116 takes the first phase in index order, so a `generated`/`binary` path that a lower-numbered phase declared `modify` is reported ISOLATE instead of ORDER/BLOCK. Deleting the comprehension would leave that live downgrade in place. Most-severe-wins, with a test. | 2: phase exit criteria + invariant 6 |
| Does this set's own orchestration trust the write-set gate? | **No — the gate is untrusted for this set, by construction.** See "Bootstrap hazard" below. | 5: the user's raw input (the stated hazard) |

Added by the reconciler, 2026-10-27:

| Fork | Chosen | Rung |
|---|---|---|
| Is phase 1's "the all-clear must be conditional" work inside R1, or creep? | **Inside R1.** The user's own R1 text names the sentence: *"while simultaneously printing the reassuring line 'no file is written by two phases.'"* (analysis `:48`). The root fix removes the dominant *cause* of a missing plan, never the sentence printed over one — phase 1 measured five assertions still failing with the root fixed and the render guard out. No `Satisfies` line was widened; R1 already covered it. | 5: the user's raw input, quoted verbatim |
| Who owns the `README.md` Project Structure line for `skills/swarm/tests/`, which phase 1 creates and no plan claimed? | **Phase 2**, and `R1` follows the work into phase 2's `Satisfies` and the Requirements table. Phase 1 edits no markdown — its exit criterion 6 asserts that, and it is what keeps `README.md` and `SKILL.md` single-writer in wave 0. A second `README.md` writer would cost the hand-declared write-set table its single-writer row for no benefit; the alternative, leaving the line unwritten, breaks CLAUDE.md's "Adding a new skill" rule. | 4: the index's Scope line ("`README.md` — only if a new indexed asset is introduced") plus one-owner-per-file |
| Does R3's de-seering extend to `commands/analyze-orchestrator.md:197,199,396`? Phase 2 left it "to Phase 3, or to a follow-up"; phase 3 carries those lines across verbatim. | **No — they stay.** They are a *measurement* of a real plan set (`journal-versioning`: six files shared, one concurrent, `engine/src/seer_engine/commands/lab.py` by phases 2+3+4), not a value the tool behaves on. R3 is about a global tool running one project's filenames and one project's suite against every repo; prose evidence does not. R3's exit-criterion grep is therefore scoped to `skills/swarm/plan_graph.py` and `agents/integrator.md`. Phase 2's handoff was rewritten from a dangling "or a follow-up" to this decision. | 4: the index's Requirements table — R3's wording is "the artifact list and the test command", both of which are behaviour |
| `spawn --isolate` is instructed at `analyze-orchestrator.md:237,255,383` but does not exist. Fix it here, or leave it? | **Leave it, and say so.** VERIFIED: `grep -c isolate skills/swarm/swarm.py` = 0; `spawn` accepts `--slug --phase --prefix --prompt --cwd --permission-mode --model --force --no-trust --dry-run` (`swarm.py:2113-2124`). It serves none of R1-R4, and the two fixes available — implementing the flag, or rewriting Step 4 — are respectively a `swarm.py` behaviour change (explicitly Out of scope) and a second writer in phase 3's file for no requirement. Phase 3 states the working form (`git worktree add` + `spawn --cwd`) wherever Step 3b needs it; the three stale lines are a **recorded leave-behind wanting its own card**, not an oversight. | 3: the plans' code blocks — `--cwd` exists and does the job — bounded by the index's Out-of-scope line |
| `**Status:**` after reconciliation — `planned` or `reconciled`? `agents/plan-reconciler.md:103` says to write `reconciled`; `commands/analyze.md:410` and `swarm.py:1802`'s own index template both say `planned`. | **`planned`**, with a separate `**Reconciled:**` line carrying the fact. Nothing machine-parses the value (`parse_index` reads `Slug`, the phase table and `Depends on`), and `planned` is what every other artifact in this ecosystem writes and reads; inventing a second vocabulary in the one index an orchestrator is about to drive is a risk with no payoff. **This is a genuine inconsistency in the repo's own prompts** — `agents/plan-reconciler.md` against `commands/analyze.md` — and it wants its own card; it is not this set's to fix (no `R` covers it). | 6: surrounding convention, two sources to one |
| Phases 2 and 3 both write `SKILL.md` in wave 1 on a 4-line gap. Is ISOLATE actually safe, when the gate that would check it is the broken thing? | **ISOLATE stands — measured, not assumed.** Both sides' real replacement texts applied to the current `SKILL.md` and merged: `git merge-file -p <p3> <base> <p2>` → rc=0, zero conflict markers, both edits present. The exit-code paragraph is `:32-34` (not `~31-33`), the class table `:39-44`, and lines 35-38 stay byte-identical. The margin is **one line**: phase 3 now carries the measurement plus "re-run this check if either side grows to touch line 35 or 38". | 3: the plans' code blocks, settled by running the merge rather than reasoning about it |

## Bootstrap hazard — the gate cannot police this plan set

`/analyze-orchestrator` Step 3b runs the **installed** `~/.claude/skills/swarm/plan_graph.py`,
which today is byte-identical to the repo's broken copy (verified this session: `diff -rq` across
`skills`, `agents`, `commands` is clean). This plan set lives in a **linked worktree**, which is
precisely the case R1 fixes. So the gate run against this set will:

- fail to resolve `.workflows/plan/swarm-write-set-gate/phase-N.md`,
- report `0 files` for every phase,
- print **"no file is written by two phases"** — which is false; phases 2 and 3 both write
  `skills/swarm/SKILL.md` —
- and exit `1`.

Today that is advisory, so the orchestrator proceeds. **The write sets are therefore declared here
by hand**, and the coordinator must act on this table rather than on the gate's output:

| Path | Phases | Waves | Class | Action |
|---|---|---|---|---|
| `skills/swarm/plan_graph.py` | 1, 2 | 0, 1 | modify | sequential — phase 2 depends on 1, no isolation needed |
| `skills/swarm/SKILL.md` | 2, 3 | 1, 1 | modify | **ISOLATE** — concurrent; disjoint sections, per-phase worktrees (`git worktree add` + `spawn --cwd`; `--isolate` does not exist) |
| `skills/swarm/tests/test_plan_graph.py` | 1, 2 | 0, 1 | create / modify | sequential |
| `agents/integrator.md` | 2 | 1 | modify | single writer |
| `commands/analyze-orchestrator.md` | 3 | 1 | modify | single writer |
| `README.md` | 2 | 1 | modify | single writer — **no longer conditional**: phase 1 ships `skills/swarm/tests/`, so the Project Structure line must be written, and reconciliation assigned it to phase 2 so this row stays single-writer |

**Reconciled 2026-10-27 and unchanged in shape.** Re-derived from the three final plans: the six
rows above are still the complete write set, the only concurrent row is still
`skills/swarm/SKILL.md`, and its ISOLATE verdict has now been **measured** rather than assumed
(`git merge-file`, rc=0, no conflict markers — see Decisions). The row that moved is `README.md`,
from conditional to certain, with no change of owner. If a phase's write set changes again, this
table changes with it: it is the only write-set analysis this set gets.

Note the ordering consequence for phase 3, which is the reason it depends on phase 1 and not merely
on tidiness: **enforcing the gate before fixing it would refuse every swarm this machine runs.** A
hard stop on exit 1, shipped while the gate exits 1 on every worktree-based plan set, is a total
outage of the orchestrator. Phase 1 must land *and* be synced first.

## Open Questions

**Empty.** Reconciliation round 1 found eleven conflicts and resolved all eleven by editing the
plan files; the five behavioural forks among them are recorded under **Decisions** with the rung
that settled each. Every requirement id is owned (R1 → 1, 2; R2 → 3; R3 → 2; R4 → 1), so there is
no unowned `R`, and no fork in this set has every branch irreversible — the whole set is prose and
Python in a throwaway worktree, revertible by `git revert` plus `./sync.sh`.

Nothing here refuses `/analyze` Step 11's launch.

## Rollback

**Per phase:** each phase is one commit on `feature/swarm-write-set-gate`; `git revert <sha>`.
Phase 1 and 2 both touch `plan_graph.py`, so reverting 1 without 2 requires reverting 2 first.

**As a whole:** `git branch -D feature/swarm-write-set-gate` and delete the worktree — nothing has
reached `main`. After a merge, revert the merge commit and re-run `./sync.sh`; because the deploy is
a copy, the installed tree is only restored by that second step. A revert that skips `sync.sh`
leaves the fixed code in `~/.claude/` and the reverted code in the repo — the exact drift CLAUDE.md
warns about.

## Next

Execute the phases one at a time, starting at phase 1:

    /implement -f SWARM_WRITE_SET_GATE_PLAN.md --phase 1

Or run the whole set as a swarm — a session per phase, concurrent wherever `Depends on` allows,
resumable on any machine:

    /analyze-orchestrator -f SWARM_WRITE_SET_GATE_PLAN.md

Or put them on the board first (GitHub repos only):

    /create-task --from-plan SWARM_WRITE_SET_GATE_PLAN.md
