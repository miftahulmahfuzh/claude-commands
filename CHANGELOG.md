# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-09-04

### Breaking Changes
- **`/analyze` orchestrates by default**: a plan set now launches its own orchestrator session at the end of every run, instead of printing a command and waiting to be told
  - `--orchestrate` is gone as an opt-in; `--no-orchestrate` is the only opt-out — plan, print the command, stop
  - `--permission-mode` now defaults to `bypassPermissions` rather than requiring an explicit value. `acceptEdits`/`auto`/`manual` still narrow it, and `/analyze` never passes a mode broader than the session it runs in
  - `/analyze-orchestrator` likewise defaults its phase spawns to `bypassPermissions` when nothing is passed to it
  - The trade-off is deliberate and documented: the isolation is the worktree and branch `/analyze` cuts, so an unattended run's blast radius is a feature branch, not the working tree
  - One refusal was removed as now impossible ("no `--permission-mode` given"); two remain — a non-empty **Open Questions** section (N parallel sessions would each answer it differently) and a missing phase plan file

- **`/do` executes an adopted plan instead of summarizing it**: a task carrying a plan file no longer passes through `plan-generator`
  - The brief schema has nowhere to put code, so a phase plan's complete code blocks were compressed into a 2–3 sentence approach before the main context — the thing that writes the code — ever saw them, silently discarding `plan-reconciler`'s cross-phase work
  - `do.md` Step 1b forks on the plan file: present takes the adopted path (`context-loader` and `plan-generator` both skipped), absent keeps the brief pipeline unchanged. `/implement` Step 4 has always worked this way; `/do` now agrees with its sibling
  - `plan-generator` **refuses** a task that has a plan rather than adopting it, so the lossy route cannot return through a later edit to the fork

### Added
- **Swarm orchestration — a whole plan set at once** (`/analyze-orchestrator`, `skills/swarm/`)
  - Reads the plan index's **Depends on** column as a DAG and opens one session per phase for every phase in a wave, via tmux + `claude -n`, then collects their reports. It writes no plans — the same invariant `/implement` and `/do` hold
  - `swarm.py`: wave scheduling, `spawn`/`launch`, a JSON session ledger, git-based phase verification, and `.gitignore`-aware artifact tracking
  - The ledger is **split by lifetime**, which is what makes cross-machine resume work: `ledger.json` is committed (phases, `depends_on`, status, landed commit, TaskIDs), `.runtime.json` is local and gitignored (tmux ids, session names) — committing tmux ids would conflict on every write and mean nothing on another laptop. `swarm.py track` re-includes that one path without disturbing the deliberate `.workflows/plan/` ignore
  - `swarm.py verify` re-derives status from the branch and `todos.md` instead of trusting the ledger, and **never downgrades a `done` phase on absent evidence** — "not on the branch" and "not fetched here" are indistinguishable to local git, and confusing them re-runs shipped work
  - Folder trust propagates from the already-trusted repo, never invented fresh; a child on a mismatched permission mode holds its report for approval and stalls the swarm silently, so the mismatch is detected at hand-off
  - An unattended run deliberately stops at the merge: phases landing on the branch overnight are the value, while merging the set is a thirty-second morning decision not worth doing unsupervised

- **Sub-issues, so a plan set's phases are addressable cards** (`skills/task`, `skills/create-task`)
  - `create --parent REF`, `subissue P C` (`--remove`), `finish REF --child-of P --commit SHA`, and a `resolve REF` that answers *whose phase am I and which phase* — parent with its plan block, children, position, `blockedBy`, `ownsPullRequest`
  - The rule the code enforces: **the parent owns the worktree, the branch and the pull request; a phase owns a commit**, because a phase branched off `origin/main` would be planning against code that has not landed. The PR requirement is swapped, never dropped — `verify_phase` refuses a card that is not a sub-issue of the parent it names
  - GitHub only; GitLab has no sub-issues below Premium
  - A parent completing with phases still live reports `openChildren` rather than cascading — a merge is not evidence that a phase nobody completed was built

- **Requirement IDs, and phases mapped onto them** (`/analyze`)
  - Step 0 splits the raw prompt into `R1..Rn`; Step 6 maps every phase onto the `R`s it serves; the plan index carries a **Requirements** table and a **Satisfies** column, plus a **Card** column for `create-task` to fill
  - This is what lets `create-task` shape a board from a plan set without re-deriving the decomposition — a table lookup, the same way the Interface Contract made reconciliation mechanical
  - `phase-planner` treats `satisfies` as an input, a plan-file header **and a boundary**: a step serving an `R` outside its list is a Handoff, not scope. `plan-reconciler` gains two conflict classes — unowned requirement and requirement creep

- **Every session names its own window** (`skills/task/session.py`)
  - A session renames itself after the card it claims the moment it claims it, over its own messaging socket — the rename cannot fail and does not block the task. Every long-running command does the same
  - `rename` renames the **tmux window** as well: renaming the session alone reaches the terminal tab title, which tmux covers with its status line, so under tmux the rename was invisible. `rename-window` also switches automatic-rename off, so the name sticks
  - A window holding two task sessions reads `task-15+17`; one shared with an ordinary session keeps the plain `task-20`. Adds `--no-tmux` and offline selftests for the naming rule

- **Every session ends with the next session's command** (`agents/completion-handler.md`)
  - `completion-handler` derives `next_command` / `next_label` and returns a hand-off block — it is the shared tail of both pipelines and the only step that has read the plan index. Empty for a standalone task, the merge line on the last phase, never a guessed TaskID
  - The command sits alone on its line throughout: a trailing `# comment` after a slash command is read as arguments, not as a comment, so a commented command is not a pasteable one

### Changed
- **`/analyze` phase cap raised from 6 to 20**, for decompositions that a six-phase ceiling was quietly truncating
- **`/implement`** reads the new **Satisfies** and **Card** columns into each task entry, and refuses a `--phase N` that is already complete — now that `--phase 1` is handed out to be pasted
- **The `depends_on` check moved from `plan-generator` up into `task-locator`**, which is already reading every `todos.md`, so a blocked task is refused after one haiku call instead of two opus ones
- **Every terminating branch of `/implement` says what to run next**, failures included: blocked names the blocking phase, drifted carries the drift note into a pasteable `/analyze`
- **README and CLAUDE.md** document the swarm architecture, the plan-set-on-a-board rules, and a worked end-to-end example

### Fixed
- **Cross-session messaging no longer trusts a stale peer name** (`swarm`, `/do`, `/implement`, `/analyze-orchestrator`): session names are mutable and reused, so a name read from a days-old committed ledger can deliver a phase's DONE report to an unrelated session that has since adopted it — measured, with a message reaching a session doing entirely different work. `swarm.py` now records `coordinator_session_id` alongside the name, and every site that addresses a peer re-reads `ListAgents` immediately before sending and reports to the user rather than sending to a stranger when the name is gone
- **`task`: Completed means closed** — a completed card now closes its own issue instead of leaving it to a merged PR's `Closes #N`, which silently assumed every completed card had one. Two paths don't: a phase card (the keyword sits on the *parent's* PR) and `finish --allow-unmerged`, both of which stranded cards Done-on-board but open-on-GitHub. Because GitHub counts *closed* sub-issues, an open phase held the parent's own progress bar at `0 of 2` with both phases green; it now reads `2 of 2`
- **`/do`'s main-context isolation restated precisely** rather than weakened: never `todos.md`, `package_readme.md` or `analysis_report.md`; exactly one plan file, the adopted one, and no other `.workflows` file
- **`/analyze`'s orchestrator hand-off is offered for every N**, correcting a gating error that offered it only when N > 1 with two independent phases. Parallelism decides whether a swarm beats `/implement`; it does not decide whether a set should run unattended — a strictly sequential set gains the most, and even N=1 gains a session that starts immediately

## [2.0.0] - 2026-08-28

### Breaking Changes
- **Implementation planning is consolidated under `/analyze`**: previously both `/analyze` and `/implement` could write plans, producing plans of two provenances with no way to tell which was authoritative
  - `/analyze` is now the only plan author. Every run produces a complete plan set: `<session-id>_code_analyzer.md`, `<SLUG>_PLAN.md`, and `.workflows/plan/<slug>/phase-{N}.md`, in a worktree it cuts
  - `/implement -f <SLUG>_PLAN.md` executes only. Handed an analysis document it refuses and names `/analyze`
  - `/do <TaskID>` adopts an existing plan file, builds a routing brief from the task text for EASY/NORMAL without one, and **refuses a HARD task with no plan file**
  - Plans are adopted, never regenerated — otherwise reconciliation is silently discarded

### Added
- **Skills: a third artifact type**: `skills/<name>/SKILL.md` directories, auto-discovered by Claude Code from their `description` trigger and deployed by `sync.sh` alongside commands and agents
  - Each skill is a directory so it can ship supporting assets (templates, Python helpers, fonts) beside its `SKILL.md`

- **New Skills**:
  - `task`: drives task cards on GitHub Projects (personal repos) or GitLab Issues (work repos) — claims the card on fetch, designs and plans autonomously, and runs unattended end to end. On GitHub it works in a fresh worktree off `origin/main`, opens a linked PR, gates on the repo's CI, resolves conflicts against parallel sessions, and merges itself. Handles the reopen loop when a card comes back with a bug report.
  - `create-task`: a front door for the board, capturing a card without derailing the current work — `gh issue create` alone misses the project board
  - `sync-todos-into-gitlab-board`: mirrors `.workflows/todos.md` onto a GitLab issue board, one issue per live task in the column its stage names, repairing non-canonical TaskIDs first
  - `confluence-writer`: publishes correctly-formatted documents to Confluence Server/DC and Cloud
  - `confluence-reader`: reads login-walled Confluence pages as text plus inline images
  - `issue-ticket-reader`: reads Jira tickets — description, comments, links, subtasks, and every attachment downloaded locally
  - `update-ats-cv`: rebuilds an ATS resume PDF from a YAML content model with millimetre-level layout control and a guaranteed page count
  - `reap-orphaned-blobs`: garbage-collects unreferenced Vercel Blob objects for Run Insights

- **`/dbg` Command**: batch Go debugging with Delve
  - Vendored helper scripts `cmd/dlv/dlv_core.sh`, `dlv_test.sh`, `dlv_trace.sh`
  - Postmortem on Delve setup and DWARFv5 compatibility

- **`/token-maxxing` and `/token-maxxing-update-docs` Commands**: deliberately high-token work sessions with an achievement-first session doc and index

- **Roadmap Mode for `/analyze`**: decomposes work into phases and dispatches every `phase-planner` in a single message so they plan concurrently
  - Each planner declares an **Interface Contract** (deletes / renames / creates / requires) so conflicts can be reconciled mechanically
  - A single `plan-reconciler` then edits the plan files in place to remove cross-phase conflicts

- **Real Agent Files**: the five in-spec `/do` subagents were promoted to `agents/*.md` — `task-locator`, `context-loader`, `plan-generator`, `completion-handler`, `readme-updater` — joined by `phase-planner` and `plan-reconciler`

- **CLAUDE.md**: repository guidance covering the three artifact types, the `.workflows/` contract, and the subagent pipeline invariants

- **remove_non_commands.sh**: cleanup script that strips clutter from `~/.claude/commands`

- **`/up-version` step 8a**: the changelog link reference definition check, the step that silently gets missed

### Changed
- **`/implement` reuses the shared `/do` agents** for the completion workflow instead of carrying its own copies

- **GitLab boards treat Completed as closed**: moving a card to Completed closes the issue, so the team stops seeing it

- **README**: rewritten around the three artifact types, with user-facing indexes for Commands, Agents, and Skills

### Fixed
- **remove-non-commands**: eliminated shadow `.subagents/` and `.workflows/` files and added safety guards
- **`task`**: a merge now closes the card instead of the session fighting GitHub over its state
- **`sync-todos-into-gitlab-board`**: enforces one TaskID to one card, adds an `audit` subcommand, treats `todos.md` as primary across both sections, and guards against a large blast radius
- **`update-ats-cv`**: autofit no longer inflates gaps, and negative gaps are rejected

## [1.1.0] - 2026-02-25

### Added
- **Subagent-based Architecture for /do and /implement**: Complete redesign with context isolation
  - Task Locator, Context Loader, Plan Generator, and Completion Handler subagents
  - Improved task execution with dedicated context management
  - Better error handling and task tracking

- **New Commands**:
  - `/postmortem`: Session problem documentation with TaskID integration
  - `/reorganize-todos`: Task organization with automatic completed tasks management
  - `/analyze-package`: Package analysis command
  - `/analyze`: Code archaeology and analysis command
  - `/update-readme`: Automated README updates
  - `/update-todos`: Task list management command

- **Difficulty Classification System**: Automatic HARD task branch management
  - P1/P2/P3 priority system with difficulty indicators
  - Automatic branch creation for complex tasks

- **TaskID System**: Comprehensive task tracking with unique identifiers
  - Enforced uniqueness and 4-section structure
  - Completed tasks separation and archive management

- **Pusher Agent**: Specialized git commit and push operations

- **Sync Script**: Repository synchronization utility with portability fixes

### Changed
- **Repository Reorganization**: Improved directory structure
  - Moved plan files to dedicated plan directory
  - Moved push.md to agents/pusher.md
  - Added .workflows/todos.md for workflow tracking

- **Enhanced Documentation**:
  - Comprehensive README updates with 487 new lines
  - Detailed command documentation for all new commands
  - Interactive clarification guidance for confusion handling

### Fixed
- **sync.sh**: Fixed dirname command syntax for portability across shell implementations

### Removed
- **install.sh**: Replaced with sync.sh for improved workflow

## [1.0.0] - 2025-09-14

### Added
- **Installation script (install.sh)**: Automated setup script for easy installation with symlink management
  - Creates symlink from `~/.claude/commands` to repository directory
  - Handles backup of existing commands directory with timestamp
  - Validates Claude CLI installation and provides setup guidance
  - Lists available commands after successful installation
  - Includes comprehensive error handling and user feedback

- **Comprehensive README.md**: Complete project documentation and usage guide
  - Detailed installation instructions with both automated and manual options
  - Complete command descriptions with usage examples and use cases
  - Project benefits and feature highlights
  - Contributing guidelines and development workflow
  - Professional formatting with clear sections and visual elements

- **Custom Claude Commands**: Two powerful workflow automation commands
  - `/push`: Intelligent git workflow automation with AI-powered commit messages
  - `/up-version`: Automated semantic versioning and changelog maintenance

### Technical Details
- Total additions: 186 lines of code across 2 new files
- Repository structure established for command management
- Symlink-based installation system for seamless updates
- Keep a Changelog format compliance for version tracking

### Project Milestone
This represents the initial release of the Claude Commands Collection, providing a complete foundation for custom Claude Code command management with professional documentation and automated installation.

[3.0.0]: https://github.com/miftahulmahfuzh/claude-commands/releases/tag/v3.0.0
[2.0.0]: https://github.com/miftahulmahfuzh/claude-commands/releases/tag/v2.0.0
[1.1.0]: https://github.com/miftahulmahfuzh/claude-commands/releases/tag/v1.1.0
[1.0.0]: https://github.com/miftahulmahfuzh/claude-commands/releases/tag/v1.0.0
