# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Rules only. The incidents behind each rule and the full design detail live in
`docs/architecture-notes.md` — **read the matching section there before changing that part of the
system** (`/do`/`/implement`, `/analyze`, the swarm, `sync.sh`, the board skills).

## What This Repo Is

A collection of **Claude Code slash commands** (`commands/*.md`), **subagents** (`agents/*.md`), and **skills** (`skills/<name>/SKILL.md`) deployed into `~/.claude/`. There is no application to build, run, or test — each file is a prompt/spec loaded at invocation time. "Editing the code" means editing markdown (plus a few helper scripts such as `skills/swarm/swarm.py`).

## Deploying Changes

- `./sync.sh` copies `commands/*`, `agents/*`, `skills/*` into `~/.claude/`. Run it after any change. No lint, no test runner, no CI. Smoke-test by invoking the command against a real `.workflows/` directory.
- **Never edit anything under `~/.claude/` directly.** `sync.sh` is a one-way copy; a deployed-only fix is erased by the next unrelated deploy. A fix you have already had to re-apply once belongs in the repo now.
- Drift check: `for d in skills agents commands; do diff -rq --exclude=__pycache__ --exclude='.*' "$d" ~/.claude/"$d"; done`
- **Deploy targets must be real directories on the Linux filesystem, never symlinks** (a 9p/Windows-drive symlink makes commands silently vanish). Fix: `rm ~/.claude/commands && mkdir ~/.claude/commands && ./sync.sh`.

## Architecture

### Three artifact types
- **`commands/<name>.md`** — user-invoked as `/<name>`; runs in main context.
- **`agents/<name>.md`** — subagent; frontmatter `name`, `description`, `model`, `color`. `haiku` for routine work, `opus` for judgment.
- **`skills/<name>/SKILL.md`** — auto-discovered from the frontmatter `description`; a directory so it can ship assets beside it.

### The `.workflows/` contract
```
<package>/.workflows/
├── todos.md                 # task list with TaskIDs (P{0-3}-{SCOPE}-{ID})
├── plan/
│   ├── {TaskID}.md          # the plan a task executes (copied here by /implement)
│   └── {slug}/phase-{N}.md  # repo-root .workflows/ only — /analyze plan sets
├── analysis_report.md
├── package_readme.md        # created/updated by /update-readme
└── postmortem/{TaskID}.md
```
`<session-id>_code_analyzer.md` and `<SLUG>_PLAN.md` live at the repo root, not in `.workflows/`.

### Who writes implementation plans — **only `/analyze`**
- `/analyze` → investigation + a complete plan every run (analyzer doc, `<SLUG>_PLAN.md` index with a Requirements table `R1..Rn`, `phase-{N}.md` for N ∈ 1..20) in a worktree it cuts. N=1 launches `/implement -f <PLAN> --phase 1` directly; N>1 launches `/analyze-orchestrator`.
- `/implement -f <SLUG>_PLAN.md` → executes; one task per phase, plan copied unchanged. Refuses an analysis document. On a set's last phase with no swarm coordinator it lands the branch itself (merge to `main` in a throwaway worktree, push, delete worktree and branch).
- `/do <TaskID>` → executes an existing task: adopts its plan file if one exists; builds a brief for EASY/NORMAL without one; runs `/analyze` itself for HARD with no plan (`--no-escalate` prints and stops).
- Drift from a plan: small → follow intent and note it; large → stop and re-run `/analyze`. Never improvise a replacement plan.
- Maintenance: `/update-readme`, `/update-todos`, `/reorganize-todos`, `/postmortem`, `/analyze-package`. `/up-version` → semver bump + CHANGELOG.

Edit one of `/do` or `/implement` → check whether the other needs the parallel change.

### Subagent pipeline (`/do`, `/implement`)
**Main context is code-only.** Pipeline: task-locator → (plan exists? adopt it in main context : context-loader → plan-generator brief) → main context edits code → completion-handler → readme-updater → pusher. Don't add doc-reading or git to the main-context step; don't have subagents implement code. `plan-generator` refuses a task that has a plan — plans are executed, never summarized.

**Both executors are unattended and never ask.** No `[y/N]`, no `AskUserQuestion`, no interactive shell commands. Decide on the precedence ladder: invariant → exit criteria → code blocks → Why/Requirements → task text/note → surrounding convention. The only stop is a fork where every branch is irreversible, and it exits with a report, not a prompt. Decisions are recorded (`completion_report.decisions` → `todos.md`, commit body, swarm ledger `--note`).

### Swarm planning (`/analyze`)
All `phase-planner` agents dispatch in one message; for N>1 a single `plan-reconciler` follows. Each planner declares an **Interface Contract** (deletes / renames / creates / requires) — change its shape in `agents/phase-planner.md` and the ledger in `agents/plan-reconciler.md` together. Reconciliation **decides** forks into `## Decisions` (with the rung); `## Open Questions` is only for an unowned requirement or an all-irreversible fork. `/analyze` Step 8 and `plan-reconciler` rule 6 must stay in step.

### Plan sets on the board (`skills/task`, `skills/create-task`)
Cards + `/analyze` → analyze first, cards from the plan index's Requirements table. **The parent owns the worktree, branch and PR; a phase owns a commit** (`finish --child-of`). GitHub only. A completed phase closes its own issue; board Status leads when they disagree.

### Swarm orchestration (`commands/analyze-orchestrator.md`, `skills/swarm`)
- N>1 only; writes no plans; reads the index's **Depends on** column as a DAG and spawns a session per phase per wave (`swarm.py spawn`, named via `claude -n`).
- Mesh rules: a message states a fact and never delegates work; never ask a peer to do what your permissions denied; never ask a peer for a decision or block on a reply.
- **Iron rule 4:** the coordinator resolves Open Questions before spawning and answers a child that asks rather than relaying. Decisions surface in `Decided without asking`.
- Step 5 lands the set itself via `swarm.py land` (`check` → `merge` → `push` → `cleanup`). **Migrations apply and verify before the push**; branch deletion is guarded by `git merge-base --is-ancestor "$BR" origin/main`; `cd "$MAIN"` before removing the worktree. Check migration numbering after merge — regenerate a duplicate, never rename it.
- Landing a set you did not cut → send `CLAIM` to the ledger's `coordinator` **before** merging.
- Ledger: `ledger.json` committed (phases, status, landed commit, TaskIDs); `.runtime.json` local and gitignored (tmux ids, session names).
- `swarm.py verify` never downgrades a `done` phase on absent evidence. Changing the phase-table columns in `commands/analyze.md` → update `parse_index` in `swarm.py`.

### Pusher (`agents/pusher.md`)
Owns all git side effects for command-driven work. A new file-mutating command ends by spawning `pusher`, not inline `git`.

## Conventions

- **TaskID:** `P{0-3}-{SCOPE}-{ID}` (e.g. `P0-DB-A236`), unique across all `todos.md` in a repo. P0 highest.
- **Difficulty:** EASY / NORMAL / HARD. HARD needs a plan file. A `**Difficulty**:` line mentioning HARD at all is HARD; `task-locator` returns it verbatim as `difficulty_line`.
- **New command:** `commands/<name>.md`, first line `# <Name> Command`; end with `pusher` if it mutates files; follow the `.workflows/` schema; add to README "Available Commands"; `./sync.sh`.
- **New agent:** `agents/<name>.md` with frontmatter (`name`, `description`, `model`, `color`).
- **New skill:** `skills/<name>/SKILL.md`, frontmatter only `name` + `description` (third person, starts "Use when…", lists triggers — never summarizes the workflow); assets beside it; add to README "Available Skills" and the Project Structure tree; `./sync.sh`.
- **Versioning:** let `/up-version` write `CHANGELOG.md`; don't hand-edit it.

> [!IMPORTANT]

> when user type in "p" : you must git add . commit push in a new subagent. USE haiku model for this task.
