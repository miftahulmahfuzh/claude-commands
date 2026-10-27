# Todos: claude-commands

**Package Path**: `.` (root)

**Package Code**: CL

**Last Updated**: 2026-10-27

**Total Active Tasks**: 1

## Quick Stats
- P0 Critical: 0
- P1 High: 1
- P2 Medium: 0
- P3 Low: 0
- P4 Backlog: 0
- Blocked: 0
- Completed Today: 16
- Completed This Week: 16
- Completed This Month: 17

---

## Active Tasks

- [ ] **P1-CL-A022** Phase 2: Per-repo artifact classes and test commands
  - **Difficulty**: HARD
  - **Type**: Refactor
  - **Context**: Owns `plan_graph.py`'s docstring, `GENERATED`/`REGENERATED_TEXT`/`classify()` (replaced by `CONFIG_PATH`, `BASELINE_BINARY`, `load_config`, `_norm`, `_match`, `gitattributes_classes`, a four-arg `classify`) plus three phase-1 regions (`build()`'s file loop, its `return` — which must keep the `"root"` key — and `render()`'s `out = [...]`); `agents/integrator.md` steps 2 and 4; `skills/swarm/SKILL.md` at line >= 39 only; `README.md`; and 12 appended `@case` functions in phase 1's harness. Exit: no seer-specific path or command remains; an unconfigured repo still classifies from a project-agnostic baseline and Hugo `resources/_gen/` classifies ORDER once declared; the seer values reproduce as a worked example of the mechanism; `integrator.md` derives its suite from the repo via the `DESIGN.md:239-242` ladder; phase 1's work survives (`"root"` intact, 1 all-clear, 2 `INCOMPLETE:`, 25 cases); no new merge class; `README.md` names `.workflows/swarm.json` twice and `tests/`; verified against the installed copy after `./sync.sh`.
  - **Status**: open
  - **Plan Set**: `SWARM_WRITE_SET_GATE_PLAN.md` (phase 2 of 3)
  - **Satisfies**: R3, R1 (one README line) — R3: Make the generated/binary artifact list and the integrator's test commands per-repo; design and argue the mechanism; keep the seer values working as data. R1 (one line): the `README.md` Project Structure entry for the `skills/swarm/tests/` harness phase 1 ships.
  - **Depends on**: P1-CL-A021
  - **Plan**: `.workflows/plan/P1-CL-A022.md`

---

## Completed Tasks

### Recently Completed
- [x] **P1-CL-A023** Phase 3: Make the gate a gate: enforce exits 1 and 2
  - **Difficulty**: NORMAL
  - **Type**: Feature
  - **Plan Set**: `SWARM_WRITE_SET_GATE_PLAN.md` (phase 3 of 3)
  - **Satisfies**: R2 — Make the gate enforcing: `/analyze-orchestrator` hard-stops on exit 1 and 2 with class-specific remediation, using the repo's existing escape-hatch convention.
  - **Plan**: `.workflows/plan/P1-CL-A023.md`
  - **Completed**: 2026-10-27 09:47
  - **Method**: swarm phase session on isolated branch `swarm-wsg-p3` (`/implement -f SWARM_WRITE_SET_GATE_PLAN.md --phase 3`); coordinator `orch-swarm-write-set-gate` integrates the wave and lands the set
  - **Files**: commands/analyze-orchestrator.md, skills/swarm/SKILL.md, .workflows/todos.md, SWARM_WRITE_SET_GATE_PLAN.md
  - **What landed**: R2 — the write-set gate's exit codes were always correct and deliberate (`plan_graph.py` `main()`); what was missing was a caller that honoured them. `/analyze-orchestrator` Step 3b was advisory prose ("act on what it flags, by class") with no instruction to stop, so a coordinator could read exit 1 or 2 and spawn the wave anyway. Step 3b is now enforcing: an exit table (`0` → Step 4; `1` → stop; `2` → remediate, re-run once, stop only if that did not clear it) followed by a section per non-zero exit. **Exit 1** is a stop with no remediation — the analysis never ran — and must quote the two lines phase 1 added, `INCOMPLETE: no collision among the K of N phases …` and `resolved against root: <path>`, the latter being what distinguishes a genuinely absent plan file from a wrongly resolved root; it also forbids quoting the old all-clear sentence there and says to report a regression if it ever appears alongside exit 1. **Exit 2** is remediate-and-proceed by class — ISOLATE → one worktree per phase via `git worktree add` + `swarm.py spawn --cwd` (explicitly *not* `spawn --isolate`, which does not exist: `grep -c isolate skills/swarm/swarm.py` is 0), with the caveat that anchors within three lines of each other are ORDER in disguise; ORDER and BLOCK → a dependency edge, added mechanically in five numbered steps across **both** copies of the index, re-`init`'d, committed through `pusher` before anything spawns. One remediation round, then stop; a `waves` cycle stops too. **The stop is a stop, not a prompt** — a session that terminates with a report rather than ending a turn on a question, with the two termination blocks in Step 5's shape, and the observation that because nothing was spawned every phase is still `pending` and `--resume <slug>` picks the set up. **`--no-gate`** is added to the flag block and reuses `skills/task`'s flag, meaning and refusal-message shape (`skills/task/DESIGN.md:159`, `task_gh.py:2617`, `task_gh.py:1994-1999`): the gate still runs and still prints, only its refusal is lifted, and it must be passed on purpose. Because the flag was written for a human who is by construction asleep, the command never reaches for it and never waits for it — a gate that cannot run *at all* walks the `DESIGN.md:238-246` ladder instead (derive the write sets by hand from the phase plans' `## Files` tables, proceed under the flag, and **name what was checked instead** in the ledger note), falling through to the exit-1 stop only when nothing could be derived either. `skills/swarm/SKILL.md` gains the matching four paragraphs after its exit-code line (enforced not advisory; the stop never prompts; `--no-gate` and the ladder), touching nothing at or after the class table phase 2 owns.
  - **Verified**: all 7 phase checks pass — flag spelling matches `skills/task`; all three exits enforced; no prompt primitive spelled anywhere in Step 3b (grep finds none); `SKILL.md` lines 55-58 byte-identical to `HEAD` with the edit landing as a single insert-only hunk; `skills/swarm/plan_graph.py` absent from the diff; the post-phase-1 quotes present with the old all-clear sentence appearing exactly once, inside the historical note; no `spawn --isolate` instruction. Check 8 — `python3 skills/swarm/plan_graph.py SWARM_WRITE_SET_GATE_PLAN.md` exits **2**, naming `skills/swarm/SKILL.md` as CONCURRENT/ISOLATE between phases 2 and 3, with no `INCOMPLETE:` line. Pre-sync safety check: phase 1's `rev-parse --show-toplevel` root finder still at `plan_graph.py:128`, the old `os.path.isdir(os.path.join(repo` walk gone. After `./sync.sh` both installed copies are byte-identical to the repo copies and the full three-way drift check is clean; phase 1's harness still passes 13/13.
  - **Drift**: `commands/analyze-orchestrator.md` Step 3b's bash block had one line (`# exit 2 = a concurrent collision`) where the plan's carried-across text showed two; the plan replaces Step 3b wholesale, so the replacement text governs. No impact.
  - **Decided**: Step 3b's prompt-disclaimer sentence named the prompt primitives literally in the plan's code block, but the phase's own exit criterion 3 forbids those spellings appearing anywhere in Step 3b and verification check 3 greps for them expecting no match → reworded the sentence to name no prompt primitive literally, with a parenthetical saying why (rung 2: exit criteria outrank a code block's wording; the intent, "no prompt primitive introduced inside Step 3b", is unchanged and now actually checkable).
  - **Decided**: `skills/swarm/SKILL.md` keeps the plan's literal wording for those same primitives → no criterion forbids those tokens in SKILL.md, and deviating for cosmetic consistency with Step 3b would be scope creep (rung 3: the plan's code block governs where nothing outranks it).
  - **Decided**: Skipped `readme-updater` → no `package_readme.md` exists anywhere in this repo, and the repo `README.md` is phase 2's sole-writer file; the phase's Files table and its "Does not touch" list name exactly two files (rung 2/3: exit criteria + the plan's Files table).
  - **Decided**: git rendered the `SKILL.md` edit as an insertion after old line 35 rather than a replacement of 32-34, narrowing the reconciler's measured margin → re-ran the `git merge-file` check against phase 2's real replacement text (its plan Steps 9 and 10): rc=0, zero conflict markers, all three edits present. ISOLATE stands (rung 1: the phase plan's standing instruction to re-run that check if the margin is in question).
  - **Rollback**: the deploy is a copy, so `git revert` of this commit must be followed by `./sync.sh`.

- [x] **P1-CL-A021** Phase 1: Gate correctness: worktree root discovery + severity selection
  - **Difficulty**: NORMAL
  - **Type**: Bug
  - **Plan Set**: `SWARM_WRITE_SET_GATE_PLAN.md` (phase 1 of 3)
  - **Satisfies**: R1, R4 — R1: Fix `plan_graph.py`'s repo-root discovery so the gate works inside a git worktree; justify the root-finder; regression-test the worktree case (includes the false all-clear). R4: Remove the dead `kinds` comprehension, or implement its intent deliberately and test it.
  - **Plan**: `.workflows/plan/P1-CL-A021.md`
  - **Completed**: 2026-10-27 09:32
  - **Method**: `/implement -f SWARM_WRITE_SET_GATE_PLAN.md --phase 1`
  - **Files**: skills/swarm/plan_graph.py, skills/swarm/tests/test_plan_graph.py, .workflows/todos.md, .workflows/plan/P1-CL-A021.md, .workflows/plan/P1-CL-A022.md, .workflows/plan/P1-CL-A023.md, SWARM_WRITE_SET_GATE_PLAN.md
  - **What landed**: R1 — `plan_graph.py`'s root walk looked for a `.git` **directory**, but in a linked worktree `.git` is a **file** (a `gitdir:` pointer), so the walk ran to `/` and fell back to `dirname(dirname(index))`, wrong for both index layouts `/analyze` produces. The gate therefore reported `0 files` for every phase of every standard plan set *and still printed* `no file is written by two phases.` Replaced by `find_root()`, which collects candidate roots in order of authority (`git rev-parse --show-toplevel` with cwd = the index's directory; an `os.path.exists` walk; the index's directory and its first three ancestors via new `_ancestors()`/`ROOT_LOOKUP_DEPTH`) and returns the first that actually resolves a phase-plan path the index names. `build()` now parses the index **before** finding the root, and returns a new `"root"` key. R1 (second half) — the all-clear is conditional: the exact old sentence prints only when every phase plan was read, otherwise `INCOMPLETE: no collision among the K of N phases whose plan could be read. …`, the tally gains `INCOMPLETE: computed over K of N phases. …`, and the missing-plans block names `resolved against root: <path>`. R4 — the dead `kinds` comprehension and the first-in-index-order `kind = next(...)` replaced by `SEVERITY`/`SEVERITY_UNKNOWN`/`most_severe()`; that was a live bug, not dead code, since a generated or binary path declared `modify` by a *lower-numbered* phase was reported ISOLATE instead of ORDER/BLOCK — the verdict was decided by phase numbering. Most-severe-wins now (invariant 6: BLOCK > ORDER > ISOLATE). New `skills/swarm/tests/test_plan_graph.py`: a stdlib-only, self-contained 13-case regression harness, no pytest, building real repos and real `git worktree add` worktrees under `tempfile.mkdtemp()`; it imports `plan_graph` from its own parent directory, so running the installed copy tests the installed copy. `swarm.py` untouched (one more name imported from it, `git`); no markdown outside bookkeeping.
  - **Verified**: harness passes 13 cases, exit 0; the same harness against `git show HEAD:skills/swarm/plan_graph.py` fails with **33 assertions in 13 cases**, including both worktree cases, the severity case and the three false-all-clear cases — the plan's measured baseline reproduced exactly; a variant with the render guard stripped still fails 5, so the guard is independently load-bearing; `grep -c "no file is written by two phases" skills/swarm/plan_graph.py` = 1; `swarm.py selftest` passes with `git diff --stat skills/swarm/swarm.py` empty; after `./sync.sh` the harness passes against the installed `~/.claude/skills/swarm/plan_graph.py` and the three-way `diff -rq` drift check is silent; the installed gate run from `~` against this set's own index exits **2**, naming `skills/swarm/SKILL.md` as CONCURRENT/ISOLATE between phases 2 and 3 and the other two shared files sequential — agreeing exactly with the index's hand-declared Bootstrap-hazard write-set table. **That closes the bootstrap hazard: this set's own gate is now trustworthy.**
  - **Rollback**: the deploy is a copy, so `git revert` of this commit must be followed by `./sync.sh` and `rm -rf ~/.claude/skills/swarm/tests`.

- [x] **P2-CL-A018** Update postmortem.md with clear persistent file output documentation
  - **Completed**: 2025-01-30 13:00:00
  - **Method**: Enhanced postmortem.md with comprehensive documentation about persistent file creation requirements. Added new "Purpose" and "Persistent File Output" sections emphasizing that command MUST create physical markdown files, not just print analysis. Included specific file path examples like chatbot/processing/.workflows/postmortem/P0-PR-A001.md. Updated all success message templates to emphasize file creation and persistent documentation. Added best practices for verifying file creation and understanding persistent nature of postmortem files
  - **Files Modified**: postmortem.md (Purpose section, Persistent File Output section, Success Messages, Best Practices)
  - **Impact**: Postmortem command documentation now clearly specifies requirement to create persistent .md files in .workflows/postmortem/ directories, addressing issue where agents only printed analysis instead of creating files
  - **Key Features**: Explicit file creation requirements, concrete path examples, enhanced success messaging, verification best practices

- [x] **P1-CL-A017** Design and implement /postmortem command for session problem documentation
  - **Completed**: 2025-01-30 12:30:00
  - **Method**: Created comprehensive postmortem.md command specification with session analysis, TaskID detection, Go-inspired documentation structure, and full integration with existing .workflows system. Updated README.md with complete documentation including workflow examples, project structure, and best practices. Command supports automatic session analysis, manual TaskID specification, new task creation with user confirmation, and recurring issue handling
  - **Files Modified**: postmortem.md (complete new command specification), README.md (extensive documentation updates across multiple sections)
  - **Impact**: Users now have robust knowledge management tool for documenting bugs and problems encountered during vibecoding sessions, with automatic TaskID detection, structured postmortem generation, and seamless integration with existing workflow
  - **Key Features**: Session analysis, Go-inspired documentation templates, recurring issue tracking, multi-package support, automatic directory creation, and comprehensive error handling

- [x] **P2-CL-A016** Add API_VERSION update functionality to up-version command
  - **Completed**: 2025-01-16 00:15:00
  - **Method**: Enhanced up-version.md with comprehensive API_VERSION update functionality. Added Step 9 for .env file handling with support for updating existing API_VERSION variables or creating new ones, including edge case handling for file encoding, line endings, and BOM. Updated Step 10 to include .env file changes in git commits, modified error handling section with .env file validation requirements, updated output requirements to report .env file operations, and revised execution flow diagram to reflect new .env file update step
  - **Files Modified**: up-version.md (Step 9, Step 10, Error Handling, Output Requirements, Execution Flow Summary)
  - **Impact**: The up-version command now automatically synchronizes API_VERSION environment variable with release tags, ensuring consistency between git tags and runtime configuration
  - **Key Features**: Automatic .env detection, existing variable preservation, robust error handling, comprehensive documentation

- [x] **P2-CL-A015** Add --ver parameter to up-version command for manual version specification
  - **Completed**: 2025-01-16 00:00:00
  - **Method**: Implemented --ver parameter in up-version.md to allow manual version specification while disabling semantic versioning analysis. Added parameter documentation with validation rules, modified workflow steps to support manual version override, updated error handling for version format validation, and preserved existing semantic versioning when parameter not provided
  - **Files Modified**: up-version.md (Parameters section, Step 2, Step 6, Error Handling, Output Requirements)
  - **Impact**: Users can now manually specify versions like --ver v0.30.1 while maintaining all existing functionality for automatic semantic versioning
  - **Key Features**: Backward compatible, robust validation, clear documentation, error prevention

- [x] **P2-CL-A014** Update README.md to document HARD task plan persistence
  - **Completed**: 2025-01-14 21:30:00
  - **Method**: Enhanced README.md with comprehensive HARD task plan persistence documentation. Added Plan Persistence step to Automatic HARD Task Process, updated workflow examples, enhanced Task Management benefits, and added plan file references to success messages
  - **Files Modified**: README.md (HARD Task Special Workflow, Complete TaskID Workflow Example, Task Management Commands benefits, Key Benefits sections)
  - **Impact**: Users now understand that HARD task implementation plans are automatically saved to .workflows/{TaskID}-plan.md files for permanent documentation, reference, and audit purposes
  - **Documentation Coverage**: Plan persistence mentioned in 5 key sections across the README

- [x] **P1-CL-A013** Enhance do.md for HARD task detailed plan saving functionality
  - **Completed**: 2025-01-14 21:15:00
  - **Method**: Enhanced do.md with mandatory plan saving for HARD tasks. Added Step 4.2 with plan file creation, updated Step 5 execution workflow, modified all output messages to include plan file references, and updated examples to demonstrate plan saving workflow
  - **Files Modified**: do.md (Step 4.2, Step 5, Success Messages, Progress Messages, Warning Messages, Error Messages, Special Cases, Examples)
  - **Impact**: HARD tasks now automatically save detailed implementation plans to .workflows/<TaskID>-plan.md files, providing persistent documentation and reference during implementation
  - **Plan Template**: Created standardized plan structure with Analysis Phase, Implementation Phases, Rollback Strategy, and Success Criteria sections

- [x] **P2-CL-A012** Document Difficulty classification and handling pipeline in README.md
  - **Completed**: 2025-01-14 21:00:00
  - **Method**: Added comprehensive Difficulty classification system documentation to README.md including EASY/NORMAL/HARD difficulty explanation, HARD task automatic branch creation workflow, practical examples for all difficulty levels, integration with TaskID workflow, and updated best practices
  - **Files Modified**: README.md (sections: /do command, Task Execution Commands, Package Documentation Workflow, Best Practices)
  - **Impact**: Users now understand the complete Difficulty field system, including automatic branch creation for HARD tasks and difficulty-based execution workflows

- [x] **P1-CL-A011** Add Difficulty field analysis and branch creation requirements to do.md and update-todos.md
  - **Completed**: 2025-01-14 20:45:00
  - **Method**: Enhanced both commands with comprehensive Difficulty field system. Added EASY/NORMAL/HARD difficulty assessment with detailed criteria, mandatory branch creation and detailed planning for HARD tasks, validation requirements, and practical examples for all difficulty levels
  - **Files Modified**: update-todos.md (Step 6, validation, mandatory requirements), do.md (Step 4, special cases, examples, output messages)
  - **Impact**: Tasks now have difficulty-based workflow with automatic branch creation for complex tasks, improving project management and code safety

- [x] **P2-CL-A010** Update do.md to move completed tasks to Completed Tasks section
  - **Completed**: 2025-01-14 20:15:00
  - **Method**: Enhanced do.md Step 6 with critical requirement to move completed tasks to Completed Tasks section, create section if missing, and verify clean separation
  - **Files Modified**: do.md (Step 6, Success Messages)
  - **Impact**: Users get automatic task organization after /do execution, maintaining clean separation between active and completed work

- [x] **P2-CL-A009** Update README.md to document reorganize-todos command and troubleshooting guidance
  - **Completed**: 2025-01-14 20:00:00
  - **Method**: Added comprehensive reorganize-todos command documentation and troubleshooting section in README.md
  - **Files Modified**: README.md (lines 228-280, reorganize-todos command section and troubleshooting guidance)
  - **Impact**: Users now understand when and how to use reorganize-todos command for TaskID and organization cleanup

- [x] **P2-CL-A007** Fix update-todos command: TaskID generation and completed tasks movement
  - **Completed**: 2025-01-14 19:30:00
  - **Method**: Strengthened update-todos.md instructions with critical TaskID coverage and organization requirements
  - **Files Modified**: update-todos.md (Step 4, Step 8, Validation, Do NOT sections)
  - **Impact**: Enhanced update-todos command with mandatory TaskID enforcement and completed tasks handling

- [x] **P2-CL-A008** Create reorganize-todos command for TaskID and organization cleanup
  - **Completed**: 2025-01-14 19:15:00
  - **Method**: Designed and implemented focused reorganize-todos.md command specification
  - **Files Modified**: reorganize-todos.md (complete new command specification)
  - **Impact**: New focused command for TaskID generation and task organization cleanup

- [x] **P2-CL-A006** Update README.md to reflect current state of /update-todos command
  - **Completed**: 2025-01-14 18:15:00
  - **Method**: Updated README.md to document TaskID coverage enforcement and completed tasks separation features
  - **Files Modified**: README.md (lines 168-169, 213-226, 270-271, 306-309, 431-432, 444-446, 473-474, 521-522)
  - **Impact**: Users now understand the enhanced /update-todos capabilities with complete TaskID coverage and clean task organization

### Today
- [x] **P2-CL-A005** Separate Active and Completed tasks in /update-todos command
  - **Completed**: 2025-01-14 17:45:00
  - **Method**: Updated update-todos.md with new "Completed Tasks" section structure and maintenance procedures
  - **Files Modified**: update-todos.md (lines 321-330, 366-385, 489-514, 582-590, 662-663)
  - **Impact**: Active Tasks now only shows incomplete tasks, completed tasks moved to time-based sections

### Today
- [x] **P2-CL-A004** Ensure all existing tasks have TaskIDs in /update-todos command
  - **Completed**: 2025-01-14 17:30:00
  - **Method**: Added explicit instructions to check ALL existing tasks for TaskIDs in update-todos.md
  - **Files Modified**: update-todos.md (lines 154-160, 545-552, 443-461)
  - **Impact**: update-todos command now ensures complete TaskID coverage across all task sections

---

## Recent Activity

### [2025-01-14 16:30] - Documentation Update Complete

#### Completed ✓
- [x] **P2-CL-A003** Update README.md to reflect --package-code parameter capability
  - **Completed**: 2025-01-14 16:30:00
  - **Method**: Added comprehensive documentation for --package-code parameter in README.md
  - **Files Modified**: README.md (lines 191-208, 168, 240, 291)
  - **Impact**: Users now understand how to use the package code override feature

### [2025-01-14 16:00] - Package Code Override Feature Complete

#### Completed ✓
- [x] **P2-CL-A002** Added --package-code parameter to /update-todos command
  - **Completed**: 2025-01-14 16:00:00
  - **Method**: Implemented complete package code override functionality with TaskID migration
  - **Files Modified**: update-todos.md
  - **Impact**: Users can now manually set package codes and migrate all TaskIDs automatically

### [2025-01-14 15:45] - System Optimization Complete

#### Completed ✓
- [x] **P2-CL-A000** Updated README.md to reflect the new TaskID workflow system
  - **Completed**: 2025-01-14 15:45:00
  - **Method**: Enhanced README with TaskID generation explanation and workflow examples
  - **Files Modified**: README.md
  - **Impact**: Users now understand how TaskIDs are generated and can use /do command effectively

- [x] **P2-CL-A001** Optimized /do command search strategy for better performance
  - **Completed**: 2025-01-14 15:45:00
  - **Method**: Replaced two-step search with direct TaskID search
  - **Files Modified**: do.md
  - **Impact**: Eliminates wasted tokens and improves search performance

---

## Archive

### 2025-01

#### Completed This Month
- [x] **P2-CL-A016** Add API_VERSION update functionality to up-version command - 2025-01-16
- [x] **P2-CL-A015** Add --ver parameter to up-version command for manual version specification - 2025-01-16
- [x] **P2-CL-A014** Update README.md to document HARD task plan persistence - 2025-01-14
- [x] **P1-CL-A013** Enhance do.md for HARD task detailed plan saving functionality - 2025-01-14
- [x] **P2-CL-A012** Document Difficulty classification and handling pipeline in README.md - 2025-01-14
- [x] **P1-CL-A011** Add Difficulty field analysis and branch creation requirements to do.md and update-todos.md - 2025-01-14
- [x] **P2-CL-A010** Update do.md to move completed tasks to Completed Tasks section - 2025-01-14
- [x] **P2-CL-A009** Update README.md to document reorganize-todos command and troubleshooting guidance - 2025-01-14
- [x] **P2-CL-A008** Create reorganize-todos command for TaskID and organization cleanup - 2025-01-14
- [x] **P2-CL-A007** Fix update-todos command: TaskID generation and completed tasks movement - 2025-01-14
- [x] **P2-CL-A006** Update README.md to reflect current state of /update-todos command - 2025-01-14
- [x] **P2-CL-A005** Separate Active and Completed tasks in /update-todos command - 2025-01-14
- [x] **P2-CL-A004** Ensure all existing tasks have TaskIDs in /update-todos command - 2025-01-14
- [x] **P2-CL-A003** Update README.md to reflect --package-code parameter capability - 2025-01-14
- [x] **P2-CL-A002** Added --package-code parameter to /update-todos command - 2025-01-14
- [x] **P1-CL-A017** Design and implement /postmortem command for session problem documentation - 2025-01-30
- [x] **P2-CL-A016** Add API_VERSION update functionality to up-version command - 2025-01-16
- [x] **P2-CL-A015** Add --ver parameter to up-version command for manual version specification - 2025-01-16
- [x] **P2-CL-A014** Update README.md to document HARD task plan persistence - 2025-01-14
- [x] **P1-CL-A013** Enhance do.md for HARD task detailed plan saving functionality - 2025-01-14
- [x] **P2-CL-A012** Document Difficulty classification and handling pipeline in README.md - 2025-01-14
- [x] **P1-CL-A011** Add Difficulty field analysis and branch creation requirements to do.md and update-todos.md - 2025-01-14
- [x] **P2-CL-A010** Update do.md to move completed tasks to Completed Tasks section - 2025-01-14
- [x] **P2-CL-A009** Update README.md to document reorganize-todos command and troubleshooting guidance - 2025-01-14
- [x] **P2-CL-A008** Create reorganize-todos command for TaskID and organization cleanup - 2025-01-14
- [x] **P2-CL-A007** Fix update-todos command: TaskID generation and completed tasks movement - 2025-01-14
- [x] **P2-CL-A006** Update README.md to reflect current state of /update-todos command - 2025-01-14
- [x] **P2-CL-A005** Separate Active and Completed tasks in /update-todos command - 2025-01-14
- [x] **P2-CL-A004** Ensure all existing tasks have TaskIDs in /update-todos command - 2025-01-14
- [x] **P2-CL-A003** Update README.md to reflect --package-code parameter capability - 2025-01-14
- [x] **P2-CL-A002** Added --package-code parameter to /update-todos command - 2025-01-14
- [x] **P2-CL-A000** Updated README.md to reflect the new TaskID workflow system - 2025-01-14
- [x] **P2-CL-A001** Optimized /do command search strategy for better performance - 2025-01-14

---

## Notes

### Documentation Status
- README.md: ✅ Exists (needs update for TaskID workflow)
- update-todos.md: ✅ Updated with TaskID system
- do.md: ✅ New command specification created

### Known Issues
*None documented*

### Future Considerations
- Add batch operations to /do command
- Implement task dependencies
- Add task deadline tracking
