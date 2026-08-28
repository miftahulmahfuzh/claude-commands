# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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