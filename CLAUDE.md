# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A collection of **Claude Code slash commands** (`commands/*.md`), **subagents** (`agents/*.md`), and **skills** (`skills/<name>/SKILL.md`) that are deployed into a user's `~/.claude/` directory. There is no application to build, run, or test — each file is a prompt/spec that Claude Code loads at invocation time. "Editing the code" here means editing markdown.

## Deploying Changes

`./sync.sh` copies `commands/*` → `~/.claude/commands/`, `agents/*` → `~/.claude/agents/`, and `skills/*` → `~/.claude/skills/`. Run it after any change to make the change live in Claude Code. There is no lint, no test runner, no CI.

To smoke-test a command after editing, run `./sync.sh` then invoke the command (e.g. `/do P0-XX-A123`) in a Claude Code session against a real `.workflows/` directory.

## Architecture

### Three artifact types
- **`commands/<name>.md`** — invoked by the user as `/<name>`. Top-level prompt; main context executes it.
- **`agents/<name>.md`** — invoked as a subagent via the Task/Agent tool. Frontmatter (`name`, `description`, `model`, `color`) controls dispatch; `model: haiku` is used to keep cost/latency low for routine work (see `agents/pusher.md`).
- **`skills/<name>/SKILL.md`** — auto-discovered by Claude Code from its frontmatter `description` (a "Use when…" trigger); not user-invoked. Each skill is a **directory** so it can ship supporting assets (templates, scripts) beside the `SKILL.md` — e.g. `skills/confluence-writer/template.html`.

### The `.workflows/` contract
Most commands operate on a target package directory that contains a `.workflows/` folder. This is the persistence layer that ties commands together:

```
<package>/.workflows/
├── todos.md                 # task list with TaskIDs (P{0-3}-{SCOPE}-{ID})
├── plan/
│   ├── {TaskID}.md          # the plan a task executes (copied here by /implement)
│   └── {slug}/phase-{N}.md  # repo-root .workflows/ only — /analyze plan sets
├── analysis_report.md       # code quality analysis
├── package_readme.md        # technical docs (created/updated by /update-readme)
└── postmortem/{TaskID}.md
```

`<session-id>_code_analyzer.md` and `<SLUG>_PLAN.md` live at the *repo root* (output of `/analyze`), not inside `.workflows/`.

### Who writes implementation plans
**Only `/analyze`.** This is the single most important invariant in the repo — it was previously split between `/analyze` and `/implement`, which produced plans of two different provenances and no way to tell which was authoritative.

- `/analyze` → read-only investigation **plus a complete plan, every run**: `<session-id>_code_analyzer.md` (descriptive) + `<SLUG>_PLAN.md` (index) + `.workflows/plan/<slug>/phase-{N}.md` for N ∈ 1..20, in a worktree it cuts. N=1 is not a different mode — same artifacts, one phase. It also numbers the user's asks `R1..Rn` and maps every phase onto the `R`s it serves — the plan index's **Requirements** table, which is what lets `create-task` shape the board without re-deriving the decomposition.
- `/implement -f <SLUG>_PLAN.md` → **executes**. Creates one task per phase, copies each phase plan to `{pkg}/.workflows/plan/{TaskID}.md` unchanged, applies one phase, hands to `completion-handler`. It writes no plans; handed an analysis document it refuses and names `/analyze`.
- `/do <TaskID>` → executes an **existing** task. Executes its plan file directly in the main context if there is one (the adopted path); builds a routing brief from the task text for EASY/NORMAL without one; **escalates a HARD task with no plan file by running `/analyze` itself** (Step 1c, before any subagent), which plans and — orchestration being its default — runs the set. `--no-escalate` prints the command and stops instead.
- When code has drifted from what a plan quotes: small drift → follow intent and note it; large drift → stop and re-run `/analyze`. Neither executor improvises a replacement plan.
- `/update-readme`, `/update-todos`, `/reorganize-todos`, `/postmortem`, `/analyze-package` → maintenance commands on `.workflows/` contents.
- `/up-version` → semver bump + CHANGELOG generation for *this* repo (or any repo with tags).

If you edit one of `/do` or `/implement`, check whether the other needs a parallel change — they share the subagent pipeline pattern below.

### Subagent pipeline pattern (`/do`, `/implement`)
These commands enforce **main-context-is-code-only**. All file reading, doc updates, and git ops are delegated to subagents so the main context stays small during code edits. The pipeline for `/do`:

1. **Task Locator** subagent — finds the TaskID across all `todos.md` files, returns metadata — including the `**Plan**:` path and which of `depends_on` is still incomplete.
2. **The fork** (`do.md` Step 1b) — a task whose plan file exists takes the **adopted path**: steps 3 and 4 are skipped and the main context reads that plan itself. Only a task with no plan continues into the brief pipeline. `/implement` Step 4 has always worked this way; the fork is what makes `/do` agree with it.
3. **Context Loader** subagent — reads relevant docs, returns a condensed packet. *(brief path)*
4. **Plan Generator** subagent — emits a YAML execution brief, and refuses a task that has a plan rather than summarizing it. *(brief path)*
5. **Main context** — applies the code changes only, reading the adopted plan file when there is one and no other `.workflows` file.
6. **Completion Handler** subagent — updates `todos.md` (mark complete, move to Completed Tasks section).
7. **README Updater** subagent (opus) — refreshes the most-impacted `package_readme.md`; auto-runs `/update-readme` if none exists.
8. **`pusher` agent** (haiku) — stages, writes a conventional-commit message, commits, pushes.

When modifying these flows, preserve the isolation: don't add doc-reading or git operations to the main-context step, and don't have subagents implement code.

### Swarm planning pattern (`/analyze`)
`/analyze` decomposes the work into phases, then dispatches **all `phase-planner` agents in one
message** so they plan concurrently. With N > 1 it follows them with a single
**`plan-reconciler`** that edits the plan files in place to remove cross-phase conflicts. The
planners cannot see each other, so each declares an **Interface Contract** (deletes / renames /
creates / requires) — that section is what makes reconciliation mechanical rather than a re-read
of every plan. If you change the contract's shape in `agents/phase-planner.md`, change the
reconciler's ledger in `agents/plan-reconciler.md` to match.

Downstream, plans are **adopted, never regenerated** — and adopted means *executed*, not
summarized. `/implement` and `/do` both read the plan file in their own main context; a plan
routed through `plan-generator` instead would have its complete code compressed into a 2–3
sentence brief, silently discarding the reconciliation. That is why `plan-generator` refuses a
task that has a plan rather than adopting one.

### Plan sets on the board (`skills/task`, `skills/create-task`)
When a prompt asks for cards *and* `/analyze`, the order is fixed: **analyze first, cards from the
plan index.** The user's count is deliverables (`R1..Rn`), `/analyze`'s count is phases, and the
Requirements table reconciles them — one parent card per `R` with its phases as GitHub sub-issues,
or one parent for the whole set when a phase serves two `R`s. The invariant the code enforces:
**the parent owns the worktree, the branch and the pull request; a phase owns a commit**
(`finish --child-of`), because a phase branched off `origin/main` would be planning against code
that has not landed. GitHub only — GitLab has no sub-issues below Premium. A completed phase closes its own issue
(`Closes #N` sits on the *parent's* PR, and GitHub's sub-issue progress counts closed children),
but the board's Status still leads when the two disagree.

### Swarm orchestration (`commands/analyze-orchestrator.md`, `skills/swarm`)
`/analyze-orchestrator` runs a whole plan set at once: it reads the plan index's **Depends on**
column as a DAG, opens one session per phase for every phase in a wave, and collects their
reports. It **writes no plans** — same invariant as `/implement` and `/do`.

Sessions address each other by name (`ListAgents` → `SendMessage`), which works because every
long-running command already renames itself via `skills/task/session.py`; `swarm.py spawn` goes
further and sets the child's name at launch with `claude -n`, so the coordinator never races the
child's own rename. Two rules keep the mesh from becoming a chat room: **a message states a fact
and never delegates work**, and a session must **never ask a peer to do what its own permissions
denied** — that is permission laundering.

The ledger is split by lifetime, and the split is the whole reason cross-machine resume works:
`.workflows/orchestration/<slug>/ledger.json` is **committed** (phases, depends_on, status,
landed commit, TaskIDs), `.runtime.json` is **local and gitignored** (tmux ids, session names) —
committing tmux ids would conflict on every write and mean nothing on another laptop. `swarm.py
track` re-includes that one path without disturbing the deliberate `.workflows/plan/` ignore.

`swarm.py verify` re-derives status from the branch and `todos.md` instead of trusting the
ledger, and **never downgrades a `done` phase on absent evidence** — "not on the branch" and "not
fetched here" look identical to git, and confusing them re-runs shipped work. If you change the
phase table's columns in `commands/analyze.md`, check `parse_index` in `swarm.py`, which reads
that table by header name.

### Pusher agent (`agents/pusher.md`)
Owns *all* git side effects for command-driven work. `/do` and `/implement` no longer perform direct git operations — they delegate to `pusher`. If you add a new command that mutates files, end it by spawning `pusher` rather than running `git` inline. Users can also invoke it directly by saying "run pusher".

## Conventions

### TaskID format
`P{0-3}-{SCOPE}-{ID}` (e.g. `P0-DB-A236`, `P1-CB-B789`). Priority `P0` is highest. Scope is a short package abbreviation. IDs must be unique across all `todos.md` files in a repo.

### Difficulty classification
Tasks are tagged EASY / NORMAL / HARD. EASY and NORMAL can run from the task description alone; **HARD requires a plan file** — `/do` escalates a HARD task without one by invoking `/analyze` itself instead of printing the command (`--no-escalate` restores the print-and-stop). A `**Difficulty**:` line that mentions HARD at all resolves to HARD, and `task-locator` returns that line verbatim as `difficulty_line` so nobody has to ask it twice. Branch isolation comes from the worktree `/analyze` cuts, not from `/do`.

### Adding a new command
1. Create `commands/<name>.md`. The first line should be `# <Name> Command` (matches existing style).
2. If it mutates files, end with a `pusher` invocation rather than direct git.
3. If it touches `.workflows/`, follow the existing schema above.
4. Update `README.md` (the "Available Commands" section is the user-facing index).
5. Run `./sync.sh` to deploy.

### Adding a new agent
Create `agents/<name>.md` with frontmatter (`name`, `description`, `model`, `color`). Use `model: haiku` for fast/cheap routine work, `opus` for tasks needing judgment (e.g. README updater).

### Adding a new skill
1. Create `skills/<name>/SKILL.md` with YAML frontmatter — only `name` and `description`. The `description` must be third-person and start with "Use when…", listing concrete triggers/symptoms (Claude reads it to decide whether to load the skill); do NOT summarize the skill's workflow there.
2. Put supporting assets (templates, scripts) in the same directory and reference them by relative name.
3. Update `README.md` (the "Available Skills" section is the user-facing index) and the Project Structure tree.
4. Run `./sync.sh` to deploy.

### Versioning
`/up-version` analyzes commits since the last tag and updates `CHANGELOG.md` following Keep-a-Changelog + SemVer. Don't hand-edit `CHANGELOG.md` for routine changes — let `/up-version` generate the entry on release.

> [!IMPORTANT]

> when user type in "p" : you must git add . commit push in a new subagent. USE haiku model for this task.
