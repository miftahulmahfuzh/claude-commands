# Code Analysis: swarm write-set gate (plan_graph.py) + per-repo tooling

**Type:** Bug Investigation (R1, R4) + Feature Update (R2, R3)
**Date:** 2026-10-27 08:48:29
**Session ID:** 20261027-084829-ROCQ
**Plan:** `SWARM_WRITE_SET_GATE_PLAN.md` (3 phases)
**Worktree:** `~/.worktrees/claude-commands/swarm-write-set-gate` — branch `feature/swarm-write-set-gate`, base `origin/main` @ `471d34a`

---

## User Input

### Original User Request

```
swarm-write-set-gate bug

Four findings in this repo (~/claude-commands), found 2026-10-27 by a session running the swarm
tooling against a real plan set. R1 is load-bearing; the rest range from important to a nit.
Evidence below is measured, not inferred — but VERIFY EACH YOURSELF rather than trusting this text.

Context that shapes every fix: this repo is the SOURCE for ~/.claude/{commands,agents,skills},
installed by sync.sh, which COPIES (sync.sh:68,74,81) rather than symlinking. Verified: the
installed plan_graph.py is byte-identical to the repo's today. So (a) editing here cannot break a
running swarm, and (b) no fix takes effect until merge AND a sync.sh run — the plan must say so
explicitly, and the final verification must assert against the INSTALLED copy, not just the repo.

R1 — plan_graph.py cannot find the repo root inside a git worktree, so the write-set gate analyses
nothing on every plan set /analyze produces.

  skills/swarm/plan_graph.py build() walks up for the repo root with:
      while repo != "/" and not os.path.isdir(os.path.join(repo, ".git")):
  In a LINKED WORKTREE .git is a FILE (a ~72-byte "gitdir:" pointer), not a directory. Verified
  with `file <worktree>/.git` -> "ASCII text". So isdir() is always False, the walk runs to "/",
  and the fallback `root = dirname(dirname(abspath(index_path)))` resolves to <worktree>/docs —
  one level too deep. Every phase-plan path then resolves under <worktree>/docs/.workflows/... and
  does not exist.

  MEASURED against a valid single-phase set whose phase-1.md exists and HAS a `## Files` table:
      phase 1 (wave 0, depends on -): 0 files
      phase plans not found (write set unknown, treated as empty):
        phase 1: .workflows/plan/home-stock-screener-section/phase-1.md
      no file is written by two phases.
      exit=1

  Why it matters more than the exit code suggests: /analyze ALWAYS cuts a worktree (its Step 4),
  so the gate has been returning "could not read" on every set the standard flow produces, while
  simultaneously printing the reassuring line "no file is written by two phases."

  Candidate fix, verified to resolve correctly: os.path.isdir -> os.path.exists on that line.
  Confirm it, then decide whether `git rev-parse --show-toplevel` is the better root-finder
  (it handles worktrees, submodules and .git files uniformly) — your call, but justify it.
  Whatever you pick, REGRESSION-TEST THE WORKTREE CASE: build a throwaway repo, `git worktree add`
  it, put a plan set inside, and assert the gate finds the write sets and exits 0/2 rather than 1.
  That is the case that was never covered.

R2 — the gate is advisory, not enforcing.
  commands/analyze-orchestrator.md Step 3b runs plan_graph.py and says "exit 2 = a concurrent
  collision", but nothing REFUSES to spawn on exit 1 or 2 — it reports and the operator decides.
  Exit 1 is deliberately distinguished from 0 (see the module docstring and main()'s comment), and
  that intent is good; the orchestrator just doesn't honour it. Make the gate a gate: a hard stop
  on 1 (analysis never ran) and on 2 (a real concurrent collision), each with the specific
  remediation already tabulated in skills/swarm/SKILL.md's ISOLATE/ORDER/BLOCK table. Preserve the
  documented escape hatch shape used elsewhere in these commands rather than inventing a new flag
  spelling; find the convention first.

R3 — integrator.md and plan_graph.py are hardcoded to a different project ("seer").
  agents/integrator.md step 2 names web/data/lab.json, lab/lab.sqlite and
  `python -m seer_engine lab stage`, and its step 4 runs `pytest engine/tests` plus
  `npx tsc --noEmit && npm test`. skills/swarm/plan_graph.py has
  REGENERATED_TEXT = ("web/data/lab.json", "lab.xlsx") and GENERATED = (".sqlite",".sqlite3",".db").
  These are global tools; pointed at any other repo they run suites that do not exist and misclassify
  that repo's real generated artifacts. Concrete miss: a Hugo site commits resources/_gen/, which is
  regenerated-not-merged (ORDER) but classifies today as plain "modify".
  Make the generated/binary artifact list and the test command PER-REPO rather than baked in.
  Design the mechanism yourself — a repo-local config file, a CLAUDE.md-declared block, or
  convention-based detection are all plausible; pick one and argue it. Keep the seer values working
  as a case of the new mechanism, not as a hardcoded default, and do not regress those plan sets.

R4 — dead code in plan_graph.py.
  In build(), the `kinds = {phases[0]["files"].get(path) for p in phases for phases in [[p]] ...}`
  comprehension shadows the outer `phases` and its result is never read; the next line computes
  `kind` independently and that is what is used. Harmless today (comprehension scope is separate in
  py3) but actively misleading. Delete it, or if it was meant to detect a path classified
  differently by two phases, implement that intent deliberately and test it.

BOOTSTRAP HAZARD worth planning around: if this work is decomposed into several phases and
orchestrated, the orchestrator will run the BROKEN plan_graph.py as its own write-set gate. Sequence
so R1 lands (and is synced) before anything depends on the gate being trustworthy, or state plainly
in the plan that the gate is untrusted for this particular set and why.

OUT OF SCOPE: anything in ~/agentic or its Hugo docs site. The custom-home.html popup refactor
discussed in the originating session is a different repo and a different piece of work.
```

### User-Provided Context

- The repo is the **source** for `~/.claude/{commands,agents,skills}`; `sync.sh` **copies**.
- Every finding was to be re-verified independently rather than taken on trust.
- Explicit out-of-scope: `~/agentic`, its Hugo docs site, the `custom-home.html` popup refactor.

### User-Provided Files

None marked with `@`. The prompt named by path:
`skills/swarm/plan_graph.py`, `commands/analyze-orchestrator.md`, `agents/integrator.md`,
`skills/swarm/SKILL.md`, `sync.sh`.

### Requirement IDs

| ID | What the user asked for |
|---|---|
| R1 | Fix `plan_graph.py`'s repo-root discovery so the write-set gate works inside a git worktree; justify the chosen root-finder; add a regression test that builds a real worktree and asserts the gate finds write sets and exits 0/2 rather than 1 |
| R2 | Make the gate *enforcing* rather than advisory: `/analyze-orchestrator` hard-stops on exit 1 and exit 2, each with the remediation from SKILL.md's ISOLATE/ORDER/BLOCK table, using the repo's existing escape-hatch flag convention rather than a new spelling |
| R3 | Make the generated/binary artifact list and the integrator's test commands **per-repo** instead of hardcoded to "seer"; design and argue the mechanism; keep the seer values working as a case of it |
| R4 | Remove the dead `kinds` comprehension in `build()` — or implement its evident intent (a path two phases classify differently) deliberately, and test it |

---

## Detailed Requirements Understanding

**Problem/Requirement Statement**

`skills/swarm/plan_graph.py` is the write-set gate: the one check that runs before a swarm
coordinator spawns a wave, answering "will two concurrent phases write the same file?". Four
defects were reported against it and its callers. The gate's *purpose* is to be trusted
unattended, which is what makes a silent false negative the severe class of bug here.

**Success Criteria**

- The gate reports true write sets when run on a plan set inside a linked worktree — the layout
  `/analyze` always produces — and exits 0 or 2 accordingly (R1).
- A regression test covers the worktree case specifically, since that is what was never covered (R1).
- `/analyze-orchestrator` refuses to spawn on exit 1 and exit 2, with the class-specific
  remediation, and offers the repo's existing documented escape hatch (R2).
- No `seer`-specific path, filename, or test command remains baked into a global tool; the seer
  values still work, as data rather than as default (R3).
- The misleading comprehension is gone and the classification intent behind it is either
  implemented with a test or deliberately declined in writing (R4).
- Every fix is verified against the **installed** `~/.claude/...` copy after `sync.sh`, not only
  against the repo.

**Key Considerations**

- **The deploy is a copy, not a link.** Nothing takes effect until merge + `./sync.sh`. The
  CLAUDE.md prohibition on editing `~/.claude/` directly applies throughout.
- **Bootstrap hazard.** Any orchestration of *this* plan set runs the *installed*, still-broken
  gate against itself.
- **No test runner exists in this repo** — "no lint, no test runner, no CI" (CLAUDE.md). A
  regression test for R1 must therefore bring its own harness.

**Assumptions**

- `git` is on `PATH` wherever the swarm tooling runs (already assumed: `swarm.py` shells out to
  `git` throughout).
- Python 3 only; no third-party dependencies may be introduced.

---

## Analysis Scope

### Explicitly Mentioned Files
- `skills/swarm/plan_graph.py` (205 lines)
- `commands/analyze-orchestrator.md` (733 lines)
- `agents/integrator.md` (93 lines)
- `skills/swarm/SKILL.md` (645 lines)
- `sync.sh` (116 lines)

### Discovered Related Files
- `skills/swarm/swarm.py` — imported by `plan_graph.py:27` (`parse_index`, `waves`); also holds
  `git()` (:107) and `main_worktree()` (:161), an **already-correct** worktree-aware root finder
- `skills/task/DESIGN.md` — the documented rationale for the `--no-gate` escape-hatch convention (:159, :239)
- `skills/task/task_gh.py:1994` — the canonical refusal-message shape for a gate that will not pass
- `skills/task/SKILL.md:434-444` — `--no-gate` in operational use
- `CLAUDE.md` — the "never edit `~/.claude/` directly" invariant and the sync contract

---

## Current Dataflow

### Entry Point: `plan_graph.py main()`

**Location:** `skills/swarm/plan_graph.py:187`
**Trigger:** `python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md>` from
`commands/analyze-orchestrator.md:188` (Step 3b) and `skills/swarm/SKILL.md:29`
**Input:** one positional `index` path, optional `--json`
**Exit contract (`:194-201`):** `0` clean · `1` could not read the plan · `2` a concurrent collision
**Next step:** `build(index)` → `render(g)` → exit code

### Processing Chain

1. **`build(index_path)`** — `plan_graph.py:77`
   - `:78` `root = dirname(dirname(abspath(index_path)))` — the fallback root
   - `:80-83` walks up from the index looking for a **directory** named `.git`
   - `:84-85` on reaching `/`, falls back to `root`
   - `:86` `parse_index()` (from `swarm.py:182`) → `(meta, phases)`
   - `:91-102` per phase: resolve `plan` relative to `repo`, `parse_files()` its `## Files`
     table, `classify()` each path, accumulate `writes[path] → [phase numbers]`
   - `:104-108` `waves()` (from `swarm.py`) → `wave_of[phase] = wave index`
   - `:110-130` for each path with ≥2 writers: pick `kind`, group owners by wave, derive
     `concurrent`, attach `_verdict()`
   - **Output:** dict with `phases`, `dep_waves`, `collisions`, `missing_plans`

2. **`classify(path, action)`** — `plan_graph.py:37`
   - `read*` → `read`; suffix in `GENERATED` → `binary`; suffix in `REGENERATED_TEXT` **or**
     action `regenerate*` → `generated`; `create*` → `create`; else `modify`

3. **`_verdict(kind, concurrent)`** — `plan_graph.py:144`
   - not concurrent → `sequential`; `binary` → `BLOCK`; `generated` → `ORDER`; else `ISOLATE`

### Data Persistence

None. The module is read-only by contract (`:17` "It spawns nothing and writes nothing").

### Exit Points

stdout (human table or `--json`) + the exit code consumed by Step 3b.

---

## Key Data Structures

### Module constants
**Location:** `skills/swarm/plan_graph.py:33-34`
```python
GENERATED = (".sqlite", ".sqlite3", ".db")
REGENERATED_TEXT = ("web/data/lab.json", "lab.xlsx")
```
**Used in:** `classify()` — `plan_graph.py:41, 43`

### Phase record (from `swarm.py parse_index`)
**Location:** `skills/swarm/swarm.py:216-227`
**Fields:** `n`, `title`, `satisfies`, `package`, `depends_on`, `difficulty`, `plan`, `task_id`,
`card`, `status`, `commit`, `note`, `reported_at`
`build()` adds `files: {path → kind}` at `:92`.

### `main_worktree(start)` — the existing correct root finder
**Location:** `skills/swarm/swarm.py:161`
Uses `git rev-parse --path-format=absolute --git-common-dir` with a pre-2.31 fallback. Returns the
**main checkout**, deliberately — a ledger must outlive the worktree. `plan_graph.py` needs the
opposite (the worktree root, where the phase plans live), so it needs `--show-toplevel`, not this
function — but it demonstrates the house style: shell out to `git`, tolerate `None`.

---

## Dependencies

### Configuration / Environment
- `git` on `PATH` (`swarm.py:107 git()` returns `None` on `OSError`, so absence degrades rather than crashes)
- `TASK_WORKTREES` (optional) — where `/analyze` cuts worktrees
- No env var or config file currently parameterises `plan_graph.py` or `integrator.md`

### External Services
None.

---

## Reference List

Every site that touches the thing being changed.

| Symbol / key | File:line | Kind | Package |
|---|---|---|---|
| `os.path.isdir(... ".git")` root walk | `skills/swarm/plan_graph.py:81` | def (the R1 defect) | swarm |
| `root = dirname(dirname(abspath(index_path)))` | `skills/swarm/plan_graph.py:78` | def (the wrong fallback) | swarm |
| `repo` used to resolve phase plans | `skills/swarm/plan_graph.py:94` | call | swarm |
| `GENERATED` | `skills/swarm/plan_graph.py:33` | def | swarm |
| `GENERATED` | `skills/swarm/plan_graph.py:41` | call | swarm |
| `REGENERATED_TEXT` | `skills/swarm/plan_graph.py:34` | def | swarm |
| `REGENERATED_TEXT` | `skills/swarm/plan_graph.py:43` | call | swarm |
| `classify()` | `skills/swarm/plan_graph.py:37` | def | swarm |
| `classify()` | `skills/swarm/plan_graph.py:99` | call | swarm |
| dead `kinds` comprehension | `skills/swarm/plan_graph.py:114-115` | def (the R4 defect) | swarm |
| `kind = next(...)` first-writer wins | `skills/swarm/plan_graph.py:116` | def (the R4 live bug) | swarm |
| `_verdict()` | `skills/swarm/plan_graph.py:144` | def | swarm |
| exit-code contract | `skills/swarm/plan_graph.py:194-201` | def | swarm |
| `git()` | `skills/swarm/swarm.py:107` | def (reusable) | swarm |
| `main_worktree()` | `skills/swarm/swarm.py:161` | def (prior art) | swarm |
| `parse_index`, `waves` import | `skills/swarm/plan_graph.py:27` | call | swarm |
| Step 3b, runs the gate | `commands/analyze-orchestrator.md:181-220` | doc (the R2 defect) | commands |
| Step 4 spawn loop | `commands/analyze-orchestrator.md:222-250` | doc | commands |
| usage / flag block | `commands/analyze-orchestrator.md:6-13` | doc | commands |
| exit-code documentation | `skills/swarm/SKILL.md:31-33` | doc | swarm |
| ISOLATE/ORDER/BLOCK table | `skills/swarm/SKILL.md:38-45` | doc | swarm |
| `web/data/lab.json`, `lab/lab.sqlite`, `seer_engine lab stage` | `agents/integrator.md:31-42` | doc (R3) | agents |
| `pytest engine/tests`, `npx tsc --noEmit && npm test` | `agents/integrator.md:55-67` | doc (R3) | agents |
| `--no-gate` convention | `skills/task/DESIGN.md:159, 239-242` | doc (prior art for R2) | task |
| `--no-gate` refusal message | `skills/task/task_gh.py:1994-1999` | def (shape to copy) | task |
| `--no-gate` argparse | `skills/task/task_gh.py:2617` | def | task |
| copy-not-symlink deploy | `sync.sh:68, 74, 81` | config | root |

---

## Measured Evidence (this session, independently reproduced)

### R1 — confirmed, and more severe than reported

Built a throwaway repo, added a linked worktree, placed a **two-phase** plan set in it with both
phases declaring `src/shared.py` in their `## Files` tables and **no dependency edge** — i.e. a
genuine concurrent ISOLATE collision in wave 0.

```
$ file <worktree>/.git
<worktree>/.git: ASCII text
$ python3 -c "... os.path.isdir / os.path.exists ..."
isdir: False   exists: True
```

Current code, run from the worktree:

```
phase 1 (wave 0, depends on -): 0 files
phase 2 (wave 0, depends on -): 0 files
phase plans not found (write set unknown, treated as empty):
  phase 1: .workflows/plan/demo/phase-1.md
  phase 2: .workflows/plan/demo/phase-2.md

no file is written by two phases.
exit=1
```

**The last line is the finding.** A real concurrent collision was present and the gate printed
the all-clear sentence. Exit 1 is correct-but-unread; the rendered text is affirmatively wrong,
which matters because Step 3b today shows a human the text and not the code.

With `os.path.isdir` → `os.path.exists`, same tree:

```
phase 1 (wave 0, depends on -): 2 files   src/one.py, src/shared.py
phase 2 (wave 0, depends on -): 2 files   src/shared.py, src/two.py
shared files: 1
  [CONCURRENT] src/shared.py  (modify)
      ISOLATE: separate worktrees merge cleanly IF the line regions are disjoint; ...
1 of 1 shared files are written concurrently.
```

**Additional defect found, not in the report: the fallback `root` is wrong in *both* layouts
`/analyze` produces.** `/analyze` files the index at `docs/plans/<SLUG>_PLAN.md` when `docs/`
exists and at `<root>/<SLUG>_PLAN.md` when it does not.

| index location | `dirname(dirname(abspath(index)))` | correct root | error |
|---|---|---|---|
| `<wt>/docs/plans/X_PLAN.md` | `<wt>/docs` | `<wt>` | one level too deep |
| `<wt>/X_PLAN.md` | parent of `<wt>` | `<wt>` | one level too shallow, outside the tree |

Confirmed by running the fixed build against a root-level index: it only resolves because the
`.git` walk now succeeds, never because the fallback is right. So the fallback cannot be left as
the safety net it pretends to be.

**Root-finder comparison, measured.** Both candidates resolve the worktree and the submodule
identically:

| case | `exists()` walk | `git rev-parse --show-toplevel` |
|---|---|---|
| linked worktree (`.git` = file) | worktree root | worktree root |
| main checkout (`.git` = dir) | repo root | repo root |
| submodule (`.git` = file) | submodule root | submodule root |
| outside any repo | runs to `/`, needs the fallback | `None` (git exits 128, `git()` maps to `None`) |

### R2 — confirmed

`commands/analyze-orchestrator.md:188` runs the gate and annotates `# exit 2 = a concurrent
collision`. Lines 203-216 tabulate ISOLATE / ORDER / BLOCK as advice. Step 4 (`:222` onward)
spawns unconditionally; no line in the file refuses on a non-zero exit, and the flag block
(`:6-13`) has no escape hatch for one.

**The convention to preserve is `--no-gate`**, already established in `skills/task/`:
- `skills/task/DESIGN.md:159` — "no gate means no autonomous landing, and `--no-gate` has to be typed on purpose"
- `skills/task/task_gh.py:1994-1999` — the refusal message shape: state what is missing, why it
  matters, and name the flag plus the words *"on purpose"*
- `skills/task/DESIGN.md:239-242` — the ladder an unattended session walks *before* reaching for
  the flag, and the requirement to **name what it did instead** when it uses it

### R3 — confirmed

`skills/swarm/plan_graph.py:33-34` — `REGENERATED_TEXT = ("web/data/lab.json", "lab.xlsx")` is a
literal seer path. `agents/integrator.md:38-41` runs `python -m seer_engine lab stage`;
`:59-60` runs `engine/.venv/bin/python -m pytest engine/tests` and `npx tsc --noEmit && npm test`.
Both files ship to `~/.claude/` and are loaded for every repo.

### R4 — confirmed, and the intent behind it is a live severity bug

```
$ python3 -c "<the comprehension, on two phases disagreeing about one path>"
kinds = {'binary', 'modify'}
kind  = modify
outer phases intact: 2
```

The comprehension is genuinely dead. But what it was reaching for is real:

```
classify('web/data/x.json', 'regenerate') -> generated
classify('web/data/x.json', 'modify')     -> modify
```

`kind` at `:116` is `next((p["files"][path] for p in phases ...))` — **the first phase in index
order wins**. So when two phases declare the same path with different actions, the verdict depends
on phase numbering, and a `generated` or `binary` path that a lower-numbered phase called `modify`
is reported as **ISOLATE** instead of **ORDER** or **BLOCK**. Against SKILL.md's own table, BLOCK
is the class where "the discarded side's rows are gone" — downgrading it is the most costly
direction to be wrong in.

---

## Impact Points (files that WILL need changes)

1. `skills/swarm/plan_graph.py` — root discovery (R1), fallback (R1), `kinds`/`kind` severity
   (R4), `GENERATED`/`REGENERATED_TEXT` → per-repo config (R3). **Phases 1 and 2.**
2. `skills/swarm/tests/` *(new)* — the worktree regression harness (R1), the severity test (R4),
   the config test (R3). **Phases 1 and 2.**
3. `commands/analyze-orchestrator.md` — Step 3b becomes a hard stop; flag block gains the escape
   hatch (R2). **Phase 3.**
4. `agents/integrator.md` — de-seer steps 2 and 4 (R3). **Phase 2.**
5. `skills/swarm/SKILL.md` — exit-code/enforcement prose (R2, phase 3) and the per-repo config
   section (R3, phase 2). **Both phases, disjoint sections.**
6. `README.md` — only if a new skill asset or config filename needs indexing. **Phase 2.**

**This document describes. The plan files prescribe.**
