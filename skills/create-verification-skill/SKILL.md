---
name: create-verification-skill
description: Generate a repo-local verify-<app> skill that launches a throwaway instance of the app, drives it the way a user does, and saves evidence, plus a feature map of what proves each feature. Use for /create-verification-skill, "make a verify skill for this repo", or when a repo has no scripted way for an agent to prove its own work.
disable-model-invocation: true
---

# Create a verification skill

Adapted from pstack's `create-verification-skill` (`cursor/plugins/pstack`), plus what building
`~/mcp-notes/.claude/skills/verify-notesd` taught us. Read that skill before you start. It is
the worked example: a script with subcommands, isolated runs, numbered evidence, and a feature map.

**Why this exists.** `phase-planner` writes a **Proof** section that names
`.claude/skills/verify-*`, `/implement` and `/do` run it, and the `verifier` agent re-runs it
with fresh context before anything lands. Without a verify skill, all of that degrades to "the
tests pass". The skill you write is read cold, mid-task, by an agent that has never seen the
app. Write it for that reader.

**Run unattended.** Answer everything from the repo. Ask the user only what the code cannot
tell you, and if nobody is there to answer, decide, write the decision into the skill's
Gotchas, and go on.

## 1. Interview the repo

Answer these from code, README, CLAUDE.md, Makefile/package scripts, compose files, CI config:

- **Surface:** what a user actually touches: HTTP API, web UI, CLI/TUI, MCP, a bot, a queue
  consumer. Pick the primary one; note the rest.
- **Existing harnesses first:** e2e suites, smoke scripts, Postman/http files, compose test
  stacks, seed scripts, fixtures. A harness the repo already maintains beats anything you
  invent. Wrap it, don't replace it.
- **Run:** the exact local start command, ports, env vars, config files, seed data, auth.
- **Dependencies:** each database, cache, queue and third-party API, and how each can be
  isolated per run (its own Docker container or database name, a local emulator, a fake). Note
  which are paid or external (LLM APIs, SMS, payment, email): those are never called by default.
- **Observe:** what proves behavior: response bodies, DB rows, files written, logs, exit codes,
  screenshots.
- **Isolate:** can two instances run at once? Port 0 or a free-port picker, per-run data dirs,
  per-run DB names. If something cannot be isolated, say so in the skill, and make the script
  refuse to share it.

If the checkout does not build or start as-is, fix that first, or stop and report it exactly.
A skill written against a broken base teaches wrong steps.

## 2. Build the lever: one script, many subcommands

Write `.claude/skills/verify-<app>/scripts/verify.sh` (or the repo's language, if a shell script
would be awkward). Agents call subcommands; they never hand-write launch sequences. Required:

| Subcommand | Does |
|---|---|
| `up [flags]` | Starts a fresh instance from the CURRENT checkout (works in any worktree). Prints `RUN=`, `URL=` (or the equivalent handle) and `EVIDENCE=`. Returns only when the app is usable, not merely when a process answers. |
| `doctor RUN` | Read-only: process alive, health answers, the port belongs to THIS run, dependencies answer, which commit it serves, and a warning if HEAD moved since `up`. |
| drive commands | One per surface (`api`, `cli`, `ui`, `mcp`, `sql`, ...). Each saves its request and its response as a numbered evidence file and prints it. |
| `note RUN "text"` | Appends a line to `evidence/LOG.md`, the human summary of what was proven. |
| `down RUN` / `down --all` | Kills exactly what `up` started, drops per-run state, keeps evidence. |
| `ls` | Runs, state, evidence count. |

Hard-won rules. Each one is a bug we actually hit in `verify-notesd`:

- **Never let the daemon hold the caller's pipe.** Start it with `setsid`, with stdin from
  `/dev/null` and stdout/stderr to a log file, and NOT as part of a `cd && ... &` list (that
  backgrounds a bash wrapper, records the wrong pid, and hangs every `$(verify.sh up)`).
- **Record the process group, kill the group.** `kill -- -$PGID`. Never `pkill` by name: the
  user's real instance has the same name.
- **Doctor checks port ownership** by comparing the listener's process group with the run's,
  not with a pid regex.
- **Binary responses go to a file** with their size and sha256, never to the terminal. Raw bytes
  corrupt the agent's output and every `grep` after them. Use one `curl -w` (a second `-w`
  silently replaces the first).
- **Real env beats config files.** Pin every path and endpoint the app reads (DB URL, data
  dir, home dirs, ports) to per-run values, and blank out paid API keys unless a flag opts in.
  Check how the app's config loader merges env and files before trusting this.
- **Evidence lives outside the repo and outside the worktree**
  (`~/.local/state/<app>-verify/<run>/evidence/`), so it survives `down` and worktree deletion,
  and is never committed by accident.
- **Number evidence files by drive order** (`01-api-...txt`), counting only the primary files.

Make scripts executable, `bash -n` clean, and print usage when called with no arguments.

## 3. Write the SKILL.md

`.claude/skills/verify-<app>/SKILL.md`, with frontmatter (`name: verify-<app>` and a
`description` saying what it proves, when to use it, and what it never touches). Sections, each
with real commands from this repo and no placeholders:

- **Launch:** `up` and its flags (rebuild frontend, seed fixtures, enable a paid dependency).
- **Doctor:** when to run it (before the first drive and after any surprise) and what its
  warnings mean.
- **Drive:** a table of the drive commands, plus one complete example per surface (a UI steps
  file, a CLI invocation, an API call). Prefer stable handles: routes, ARIA labels, test ids,
  prompt strings.
- **Evidence:** where it lands, and the proof standards:
  - Use the real user path, never a test-only endpoint.
  - Capture the action AND the resulting state, and read side effects back.
  - For a bug fix, show the failure first.
  - A step that could not be driven is `inconclusive` with its reason. Never weaken a journey
    to make it pass.
- **Cleanup:** `down`. Evidence survives it.
- **Feature map:** points at `features/README.md`, and says that a user-facing change updates its
  entry in the same change.
- **Gotchas:** what must never be driven (paid APIs, anything that messages real people,
  anything outside the sandbox), what cannot be produced locally, flaky timings.

## 4. Seed the feature map

`features/README.md` (an index table: feature, file, surfaces) plus one file per user-facing
feature. Start with the 5 to 8 most important, taken from routes, commands, menus and docs. Every
file has exactly these four H2s:

- `## Sub-features`
- `## How to get to it (user POV)`
- `## Driving it with verify.sh` (real commands, and the end state that proves each one)
- `## Gotchas`

If seed data lacks a precondition a journey needs, the journey reports failure, and the reason
goes in Gotchas.

## 5. Prove every recipe before handing over

A skill that was never executed is a draft. Run, for real:

1. `up`, then `doctor` on the run.
2. **Every journey in every feature file, once.** Fix the recipe when the recipe was wrong
   (wrong arg name, wrong column, wrong route). When the APP is wrong, record it as a product
   bug in the final report and do not paper over it in the map.
3. `down`, then confirm the evidence still exists and no process or per-run DB is left behind.

Run `down` after every failed attempt too. Expect this pass to find bugs in your own script:
it is the point of the pass.

## 6. Wire it into the repo

- `.claude/skills/verify-<app>/` must be tracked by git. If `.gitignore` hides `.claude/`,
  un-ignore that path; keep `.claude/settings.local.json` ignored.
- Add one line to the repo's `CLAUDE.md` (Conventions, or wherever commands live) pointing at
  the skill and the feature map.
- Any dev dependency the drives need (Playwright, an HTTP client) goes into the repo's own
  manifest at a pinned version. Prefer browsers and tools already installed on this machine.
- Commit with the repo's conventions (its CHANGELOG under Unreleased if it keeps one) and push
  to the default branch, unless the repo's CLAUDE.md says otherwise.

## Report

End with:
- the skill path and its subcommands;
- the feature-map entries, and which journeys were proven, failed, or inconclusive, each with
  its evidence path;
- product bugs found (app wrong, not recipe wrong);
- what the skill deliberately never drives;
- the commit sha.
