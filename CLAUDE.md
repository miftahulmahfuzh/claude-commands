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
├── todos.md             # task list with TaskIDs (P{0-3}-{SCOPE}-{ID})
├── plan/{TaskID}.md     # implementation plan for a task
├── analysis_report.md   # code quality analysis
├── package_readme.md    # technical docs (created/updated by /update-readme)
├── postmortem/{TaskID}.md
└── roadmap/{slug}/phase-{N}.md   # repo-root .workflows/ only — /analyze roadmap mode
```

`<session-id>_code_analyzer.md` and `<SLUG>_ROADMAP.md` live at the *repo root* (output of `/analyze`), not inside `.workflows/`.

### Command relationships
- `/analyze` → read-only investigation. Triages scope itself and produces either
  `<session-id>_code_analyzer.md` (SINGLE) or that plus `<SLUG>_ROADMAP.md` and one reconciled
  plan per phase, in a dedicated worktree (ROADMAP).
- `/implement -f <analyzer.md>` → reads that file, creates a **new** task in `todos.md` + plan, then implements.
- `/implement -f <SLUG>_ROADMAP.md` → creates one task per phase, adopts the phase plans as-is, implements one phase.
- `/do <TaskID>` → executes an **existing** task already in `todos.md`.
- `/update-readme`, `/update-todos`, `/reorganize-todos`, `/postmortem`, `/analyze-package` → maintenance commands on `.workflows/` contents.
- `/up-version` → semver bump + CHANGELOG generation for *this* repo (or any repo with tags).

If you edit one of `/do` or `/implement`, check whether the other needs a parallel change — they share the subagent pipeline pattern below.

### Subagent pipeline pattern (`/do`, `/implement`)
These commands enforce **main-context-is-code-only**. All file reading, doc updates, and git ops are delegated to subagents so the main context stays small during code edits. The pipeline for `/do`:

1. **Task Locator** subagent — finds the TaskID across all `todos.md` files, returns metadata.
2. **Context Loader** subagent — reads relevant docs, returns a condensed packet.
3. **Plan Generator** subagent — emits a YAML execution brief.
4. **Main context** — applies the code changes only.
5. **Completion Handler** subagent — updates `todos.md` (mark complete, move to Completed Tasks section).
6. **README Updater** subagent (opus) — refreshes the most-impacted `package_readme.md`; auto-runs `/update-readme` if none exists.
7. **`pusher` agent** (haiku) — stages, writes a conventional-commit message, commits, pushes.

When modifying these flows, preserve the isolation: don't add doc-reading or git operations to the main-context step, and don't have subagents implement code.

### Swarm planning pattern (`/analyze` roadmap mode)
`/analyze` decomposes large work into phases, then dispatches **all `phase-planner` agents in one
message** so they plan concurrently, and follows them with a single **`plan-reconciler`** that
edits the plan files in place to remove cross-phase conflicts. The planners cannot see each
other, so each declares an **Interface Contract** (deletes / renames / creates / requires) —
that section is what makes reconciliation mechanical rather than a re-read of every plan. If
you change the contract's shape in `agents/phase-planner.md`, change the reconciler's ledger in
`agents/plan-reconciler.md` to match.

Downstream, plans produced this way are **adopted, never regenerated**: `plan-generator` and
`/implement` read an existing `.workflows/plan/{TaskID}.md` rather than writing a new one, or
the reconciliation is silently discarded.

### Pusher agent (`agents/pusher.md`)
Owns *all* git side effects for command-driven work. `/do` and `/implement` no longer perform direct git operations — they delegate to `pusher`. If you add a new command that mutates files, end it by spawning `pusher` rather than running `git` inline. Users can also invoke it directly by saying "run pusher".

## Conventions

### TaskID format
`P{0-3}-{SCOPE}-{ID}` (e.g. `P0-DB-A236`, `P1-CB-B789`). Priority `P0` is highest. Scope is a short package abbreviation. IDs must be unique across all `todos.md` files in a repo.

### Difficulty classification
Tasks are tagged EASY / NORMAL / HARD. HARD tasks trigger automatic branch creation in `/do` for isolation; the command surfaces merge instructions at the end.

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
