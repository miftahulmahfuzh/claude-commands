# claude-commands

Slash commands, subagents, and skills for [Claude Code](https://claude.ai/code). Each file is a
prompt, not a program — there is nothing to build or run.

## Install

```bash
git clone https://github.com/miftahulmahfuzh/claude-commands.git
cd claude-commands
./sync.sh
```

`sync.sh` copies `commands/*` → `~/.claude/commands/`, `agents/*` → `~/.claude/agents/`,
`skills/*` → `~/.claude/skills/`. Re-run it after any edit.

**Legacy installs:** earlier versions were cloned directly into `~/.claude/commands/`, leaving
repo files that show up as bogus commands, plus `.subagents/` and `.workflows/` that Claude Code
loads as skills shadowing the real agents. `./remove_non_commands.sh` clears them; it only ever
deletes inside `~/.claude/commands/` and is safe to re-run.

---

## Commands

| Command | What it does |
|---|---|
| `/analyze` | Traces the code, then writes the implementation plan — the only command that plans |
| `/implement` | Executes a plan: creates the tasks, applies the code |
| `/do` | Executes one existing task by TaskID |
| `/dbg` | Drives Delve to get runtime truth instead of inferring from logs |
| `/analyze-package` | Generates a package's code-quality analysis |
| `/update-readme` | Creates or refreshes `package_readme.md` |
| `/update-todos` | Creates or refreshes `todos.md` |
| `/reorganize-todos` | Re-sorts todos by priority |
| `/postmortem` | Documents what went wrong in a session |
| `/up-version` | Semver bump + CHANGELOG from commits since the last tag |
| `/token-maxxing` | Starts a high-consumption session on deliberately useful work |
| `/token-maxxing-update-docs` | Records that session |

### `/analyze`

Traces dataflow, documents structure, and **writes the implementation plan**. It is the only
command that plans; `/implement` and `/do` execute what it wrote. It never edits source code.

```bash
/analyze [target] [bug|feature|update|refactor] [--phases N] [--no-worktree]
<free-form description>
```

Everything is optional; `/analyze` followed by prose works, and the target and type are inferred.

Every run produces the same three things, in a worktree it cuts off `origin/main`:

| Artifact | What it is |
|---|---|
| `<session-id>_code_analyzer.md` | the analysis — descriptive, what exists today |
| `<SLUG>_PLAN.md` | the plan index — phases, order, invariants, open questions |
| `.workflows/plan/<slug>/phase-{N}.md` | one implementation plan per phase, with complete code |

The only thing that varies is **N**, the number of phases (1–20). A bug fix gets N=1 — same
artifacts, one phase, not a lesser mode. N grows when the change spans 3+ packages, has a
required order, or must stay shippable at every step.

The user's asks are numbered `R1…Rn` and every phase declares which `R` it serves, so the plan
index says what the user wanted *and* how it decomposes. That mapping is what reconciles "make me
2 cards" with a 4-phase plan set — see `create-task`.

For N > 1 the phases are planned **in parallel** — one `phase-planner` each — and then
reconciled. Parallel planners can't see each other's plans, so each declares an **Interface
Contract** (what it deletes, renames, creates, and requires from earlier phases), and
`plan-reconciler` uses those to find deleted-then-used symbols, unmet assumptions, duplicate
work, file collisions, and gaps — then **edits the plan files** to fix them. What it can't
resolve without guessing goes to **Open Questions**, and `/implement` stops and asks about
anything left there.

Every phase must build and pass tests on its own, so the branch is reviewable at any point.

```bash
# terse, classic form
/analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: <logs>

Files:
@tools/toolcore/caller.go

# free-form — no target, no type
/analyze
i want to purge direct tool streaming capability from this codebase. reasons:
1. tencent rag had a streaming api, so i built an abstraction for future streaming tools
2. two years later there are still no other streaming tools
3. cs_manager's three personas can't pass a tool's stream straight through anyway
YAGNI. let the feature go.
```

The rationale is copied into the plan index verbatim — on a purge, the reasons are the spec for
what may be deleted and what may not.

### `/implement`

```bash
/implement -f <SLUG>_PLAN.md [--phase N] [--all] [-note <note>]
```

Executes the plan. It creates one task per phase across the packages the plan names, copies each
phase plan to `{pkg}/.workflows/plan/{TaskID}.md` **unchanged**, applies one phase, runs the
plan's verification commands, and hands off to `completion-handler`.

It stops after one phase by default so the next starts in a fresh context; `--all` continues in
one session. Phases stay blocked until their dependencies complete.

**It writes no plans.** Handed a `*_code_analyzer.md` it refuses and names `/analyze` — an
analysis describes the code, and filling the gap here is what this command deliberately doesn't
do. Same rule when the code has drifted from what a plan quotes: small drift is followed and
noted, large drift stops with `Re-run /analyze`.

### `/do`

```bash
/do P2-CL-A001                                    # EASY — brief from the task text
/do P1-DB-A236 --note="also handle the bulk path"
/do P1-TC-A002                                    # a plan-set phase — adopts its plan
```

Five subagents around one main-context step: `task-locator` finds the TaskID, `context-loader`
condenses the docs, `plan-generator` emits a routing brief, **the main context writes the code**,
and `completion-handler` updates `todos.md` before chaining `readme-updater` and `pusher`.

The main context never reads `todos.md`, `package_readme.md`, `analysis_report.md`, or plan
files, and never runs git — that isolation is the point of the design.

`plan-generator` adopts the task's plan file when there is one and builds a brief from the task
text when there isn't. A **HARD task with no plan file is refused**, pointing at `/analyze`:
that's exactly the case where a real plan matters.

### `/dbg`

Drives **Delve** in batch mode for runtime values — real call sequences, argument values,
goroutine stacks, post-mortem state — instead of guessing which `log.Debug` fired.

```bash
/dbg <what you want to debug>
Context: <symptom>
Error: <optional logs>
```

| Script | Purpose |
|---|---|
| `dlv_trace.sh` | print every call to matching funcs, with args and return values |
| `dlv_test.sh` | batch breakpoint-debug one test, scripted |
| `dlv_core.sh` | post-mortem a crashed or hung server from a core dump |

**This command is different from the others:** the scripts live in the *target Go project*, not
in `~/.claude/`. Reference copies are in [`cmd/dlv/`](cmd/dlv) — see [setup](#go-debugging-with-dbg).

### `/token-maxxing`

Kicks off a deliberately high-consumption session that still lands real work. It reads the 5
most recent `docs/token_maxxing/` docs so it doesn't re-propose finished work, surveys the repo,
and offers 3–5 ranked ideas tagged fresh or continuation. Work lands on
`token-maxxing-YYYY-MM-DD`, never auto-merged. Big ideas get handed to `/analyze --no-worktree`
rather than freehanded.

```bash
/token-maxxing            # anything
/token-maxxing tests      # bias the menu
```

`/token-maxxing-update-docs` writes the session log (achievement first) and maintains a
newest-first index.

### `/up-version`

Finds the latest tag on main, analyzes commits since, picks the bump, updates `CHANGELOG.md`
(Keep-a-Changelog), merges, tags, pushes, and returns you to your branch.

---

## Agents

Dispatched by `subagent_type`. `haiku` for mechanical work, `opus` where judgment matters.

| Agent | Model | Purpose |
|---|---|---|
| `task-locator` | haiku | find a TaskID across every `todos.md`, return metadata |
| `context-loader` | opus | read package docs, return a condensed packet |
| `plan-generator` | opus | routing brief — adopts a plan file, never writes one |
| `phase-planner` | opus | plan one phase, in parallel with the others |
| `plan-reconciler` | opus | resolve cross-phase conflicts by editing the plans |
| `completion-handler` | opus | update `todos.md`, then chain readme-updater and pusher |
| `readme-updater` | opus | update the most-impacted `package_readme.md`, creating it if absent |
| `pusher` | haiku | stage, commit with a conventional message, push |

`pusher` owns **all** git side effects for command-driven work. Invoke it directly by saying
`run pusher`.

---

## Skills

Skills live in `skills/<name>/SKILL.md` and are auto-discovered from their `description`
triggers. Most fire on their own; the task ones are also invocable by name.

### `confluence-writer`
Getting a document into Confluence with formatting intact, on Server/DC and Cloud. The trick is
to render the doc as HTML, copy the *rendered* page from a browser, and paste rich text —
bypassing every markdown and wiki-markup converter. Also fixes literal `##`/`|` from pasted
markdown and the `conf_wikimarkup_conversion_errors` HTTP 500. Ships `template.html`.

### `confluence-reader`
The read counterpart. Hits `/rest/api/content` with your credentials and saves the body as text
plus every inline image as a local file — PDF export and copy-paste both lose the images. Body
text carries `[IMG: images/<file>]` markers so you only open the ones that matter. Resolves
`/display/`, `viewpage.action?pageId=`, tiny `/x/…`, Cloud, or a bare id.

Credentials come from `CONFLUENCE_PAT`, `CONFLUENCE_USER`/`CONFLUENCE_PASS`, or a git-ignored
`~/.config/confluence-reader/credentials`. `confluence_fetch.py` is stdlib-only.

### `issue-ticket-reader`
The Jira counterpart. Pulls the description **and every comment in thread order** — on a
returning ticket the bug report is usually in the comments — plus linked issues, subtasks, and
every attachment. Videos are sampled into timestamped JPEG frames via ffmpeg (`--frames N`).
Extras: `--changelog`, `--all-fields`, `--no-attachments`.

Reuses the `confluence-reader` credentials, so it usually needs zero setup. Stdlib-only.

**Limits:** video audio is never transcribed, so a verbally-explained bug isn't readable from
frames; sparse sampling can miss a transient error toast; pdf/xlsx are downloaded, not converted.

### `task`
Task cards on GitHub Projects (personal repos) or GitLab Issues (work repos), chosen from the
`origin` remote. `/task 14` claims the card by moving it to In Progress, reads every comment,
designs the change without asking, writes the plan, and links it onto the card.

**It runs unattended.** No approval step and no questions — a question at 1am costs the night
and gets a reflexive `y` at 9. It decides, records the losing approaches in the plan, and keeps
going. Five enumerated conditions end the session cleanly with the card in a truthful stage and
the reason commented on it; everything else gets decided.

|  | Personal repos | Work repos |
|---|---|---|
| Cards | GitHub Issues + a `Tasks` Projects board | GitLab Issues |
| Stage | the board's Status field | `status::*` labels |
| Development | worktree off `origin/main`, ending in a PR the session merges | mints a TaskID, hands off to `/do` |
| Completed | linked PR merged; the issue is closed either way | issue closed |
| Phases of a plan set | sub-issues; the parent owns the branch and the PR | flat TaskIDs in `todos.md` |

On GitHub the gate is the repo's **own** `.github/workflows` — every `run:` step of every
push/PR job, in order (on one real repo, 14 commands including seven bespoke guards a hardcoded
`npm test` would have waved through). No CI at all means `land` derives a gate from
`package.json` / `Makefile` / `pytest` / `cargo` / `go test` and names what passed on the card.

A card carrying `/analyze` phases is a **parent with one sub-issue per phase**, and the rule there
is forced rather than chosen: **the parent owns the worktree, the branch and the pull request; a
phase owns a commit.** Phase 2's plan quotes the tree as it looks after phase 1, which is not on
`origin/main` yet, so a phase that branched off the base would implement against code that does
not exist. `/task 13` addresses a phase directly (sub-issues are real issues), `resolve` answers
`parent` / `position` / `blockedBy` / `ownsPullRequest` in one call, and
`finish 13 --child-of 12 --commit <sha>` completes a phase on four checks instead of a merge.
Running `/task` on the *parent* drives every phase in order and opens one PR — `/implement --all`
reached from the board.

Parallel sessions off the same `origin/main` will conflict; `land` exits 2 with the conflicting
files and the other card's number. The session resolves it by a stated rule and re-runs the
gate — but a resolution that removes the other card's behavior is not a resolution, and
`--abort-conflict` comments on both cards instead.

Three things measured rather than assumed: GitLab CE doesn't enforce scoped-label exclusivity,
so transitions rewrite the whole label set and verify; in `todos.md` the checkbox is the stage
only under `## Active Tasks`; and package codes aren't unique, so uniqueness is checked on the
whole TaskID. **Completed means closed on both backends** — on GitLab that took a shared repo
showing 55 open issues, 44 of them finished (now 11); on GitHub it took a parent card reading
`0 of 2` while both its phases were green, because sub-issue progress counts *closed* children
and only the parent's PR carried a closing keyword.

Claiming a card also renames the terminal to `task-<n>`: five sessions in one repo otherwise
all carry the same derived name, and the card number is the only thing that separates them.
It goes over the session's own messaging socket, the way `/rename` does, so the tab title,
the `/resume` row and the peer address change together — plus the tmux window, which under
tmux is the only one of those actually on screen. It can never fail the loop.

**Layout:** `taskcore.py` (shared codec and stages) · `task_gh.py` (gh CLI) · `task_gl.py`
(GitLab REST over urllib) · `todos.py` (the TaskID corpus) · `session.py` (the rename).
Every module has an offline `selftest`.

**Setup:** GitHub needs `gh auth refresh -s project,read:project` and the **Linked pull
requests** field as a board column. GitLab needs a PAT with `api` scope in
`~/.config/task-skill/gitlab`, then `labels --ensure` and `board --ensure` per project.
`doctor` reports what's missing on either backend.

### `create-task`
The front door to the same board. `/create-task "…"` opens the issue, adds it to the board, and
sets the Open stage — three operations, because `gh issue create` alone produces an issue no
column shows. It never asks a question: the project comes from the reference, the repo, or the
files being edited, and otherwise the card is captured as a GitHub draft item. Then it stops —
working the card is `/task <number>`.

**When `/analyze` ran in the same prompt, `/analyze` goes first and the cards come from its plan
index.** The two counts are different altitudes, not rivals: the user names *deliverables*
(`R1…Rn`), `/analyze` decides *phases*. So one parent card per `R` with its phases as GitHub
**sub-issues**, in phase order — or a single parent for the whole set when a phase straddles two
`R`s and can be attached to neither. The parent carries the branch, the base sha and the plan
index; each phase carries its own plan path and `finish --child-of`. GitHub only: GitLab has no
sub-issues below Premium, and there the phases are already flat TaskIDs that `/do` walks.

### `sync-todos-into-gitlab-board`
`/sync-todos-into-gitlab-board .workflows/todos.md` — one GitLab issue per live task, in the
column its stage says. `todos.md` stays the source of truth.

Identity is read from two channels (the title prefix and the `- TaskID:` line), because a title
edited in the browser would otherwise hide the card and the next run would duplicate it.
`apply` refuses to write while any duplicate exists, and refuses to create more than
`--max-create` (default 10) at once — widening what counts as a task once took a file from 26
entries to 55 and created 28 permanent cards in a shared repo. `plan` is the default and writes
nothing. Only entries under `## Active Tasks` become issues; the root file has 27 live entries
and 28 echoes in its summary and activity log.

**Cost, documented rather than discovered:** a closed GitLab issue leaves `status::completed`
for the Closed column, so finished work sits as an open issue carrying the completed label.

### `update-ats-cv`
`/update-ats-cv <input.pdf> <what to change>` — parses the CV for content *and* visual style,
then redraws it from a `*.cv.yaml` model. The input PDF is never patched, which is what makes
"shave 4pt off that gap" answerable.

The page count is an invariant: `--autofit` walks a ladder of (gap, leading, font) triples and
takes the first that fits, or **exits non-zero** saying how many lines are over. Every gap is a
named token, so "those two lines are too far apart" maps to one number. `cv_extract.py`
identifies the typeface by advance-width matching, because CV builders ship flattened PDFs with
font names stripped and bold faked by overprinting — it found Lora at 0.65% error where the
metadata said nothing. Text is emitted in document order; an earlier version batched glyphs by
color, which rendered identically but made parsers read every heading before any body text.

**Limits:** letter-spacing applies to headings only; the layout engine covers a standard
one-column CV, not a sidebar or two-column body. Needs `pymupdf` + `pyyaml`.

### `reap-orphaned-blobs`
Deletes Vercel Blob objects under `shots/` that no database row references, for Run Insights.

---

## Workflows

### Bug → fix

```bash
# Session 1 — investigate and plan
/analyze aggregation_mode bug
Context: Citations missing in aggregated responses
Files:
@tools/toolcore/caller.go
# → worktree feature/fix-citation-aggregation, the analysis doc,
#   FIX_CITATION_AGGREGATION_PLAN.md, and one phase plan

# Session 2 — execute
cd ~/.worktrees/<repo>/fix-citation-aggregation
/implement -f FIX_CITATION_AGGREGATION_PLAN.md
```

Session 1's exploration tokens are thrown away; session 2 pays only for implementation, since
the plan already says exactly what to change. Pass `--no-worktree` to plan against the branch
you're on.

### Large refactor or purge

```bash
# Session 1 — planning
/analyze
<what you want changed, and why it's worth doing>
# → worktree feature/<slug>, an analysis doc, PURGE_..._PLAN.md, and
#   .workflows/plan/<slug>/phase-N.md for each phase, reconciled against each other

# Session 2..N — one phase each
cd ~/.worktrees/<repo>/<slug>
/implement -f PURGE_..._PLAN.md         # phase 1, creates a task per phase
/do P1-TC-A002                          # phase 2, in a fresh session
```

Read the plan index's **Open Questions** before starting — reconciliation puts anything it
couldn't resolve without guessing there. Merge the branch once as a whole.

### Go debugging with `/dbg`

```
Need the code paths?          → /analyze   (static)
Need what ACTUALLY happens?   → /dbg       (runtime, via Delve)
Ready to fix it?              → /implement or /do
```

One-time setup per Go project — the scripts are committed alongside the code so the team shares
the same entry points:

```bash
cp -r ~/claude-commands/cmd/dlv cmd/dlv
chmod +x cmd/dlv/*.sh

# dlv must be built with the project's Go major version — Go 1.25 emits DWARFv5,
# which a dlv built with Go <1.25 cannot read
GOTOOLCHAIN=go1.25.7 go install github.com/go-delve/delve/cmd/dlv@latest

# optional, in .claude/settings.local.json:
#   "Bash(dlv:*)", "Bash(cmd/dlv/dlv_trace.sh:*)",
#   "Bash(cmd/dlv/dlv_test.sh:*)", "Bash(cmd/dlv/dlv_core.sh:*)"
```

For a live crash, capture a core dump the way you'd capture logs:

```bash
ulimit -c unlimited; go build -o /tmp/agentic .
GOTRACEBACK=crash /tmp/agentic
/dbg analyze this core dump   # then hand over the binary + core file
```

### Task tracking

An idea arrives away from the keyboard and goes into a notes app Claude Code can't see. `/task`
makes the browser the front door: file the card anywhere, then `/task 14` picks it up. Going the
other way, `/sync-todos-into-gitlab-board` populates the board from work already tracked.

A card sits in In Progress only while genuinely being worked, and reaches Completed only when
the repo's gate passed and the host reports the PR merged — a mechanical bar, which is what
lets the loop close with nobody watching.

### Cards and `/analyze` in one prompt

The case this shape was built for, from `JMTarot`:

```bash
/create-task 2 cards and /analyze
1. pull data from neon prod. there are 3 "Bacaan ini tidak selesai" — we should add a
   "Coba ulang" button so this empty reading can be refilled.
2. in history item list, make it so user can swipe left to show a trash icon. clicking
   it soft-deletes the reading. sometimes users asked embarrassing questions.
```

**What that produced before:** two cards (#11, #12) *and* a four-phase plan set with 20
inconsistencies reconciled — with no relationship between them. Both halves did exactly what
they promise; they were produced blind, because `create-task` fires in two seconds and never
asks, so it committed the board to a shape before the only thing that had read the code existed.

**What it produces now.** `/analyze` runs first and numbers the asks `R1` (retry) and `R2`
(delete); each of the four phases declares the one `R` it serves, so the mapping is a table
lookup and neither count is overridden — the user's 2 is the parent count, `/analyze`'s 4 is the
sub-issue count:

```
#11  Coba ulang: refill a reading that never finished          [R1]  Open
 ├─ #15  Phase 3 — the predicate, the writer, the endpoint
 └─ #16  Phase 4 — the Coba ulang control, copy, docs
#12  Swipe left to delete a reading from history (soft delete) [R2]  Open
 ├─ #13  Phase 1 — schema, read filters, delete route
 └─ #14  Phase 2 — the swipe gesture and the row
```

Each parent body carries the plan index, the branch and base sha, and the worktree path marked
as machine-local. Each phase body carries its own plan path *with the branch* — `/analyze` writes
plans inside the worktree, so the path is a dead link on `main` until the PR merges.

Then the phases are worked, in one worktree, by whichever session picks a card up:

```bash
/task 12            # the parent: drives phases 1 and 2 in order, opens one PR
/task 15            # one phase: works in #11's worktree, completes on its commit
```

```bash
python3 ~/.claude/skills/task/task_gh.py finish 13 --child-of 12 --commit <sha>
```

Had one phase served *both* asks — a migration both features need — it could be attached to
neither, and the answer is one parent for the whole set with the asks as bullets. That coupling
is a fact about the work, not a labelling problem.

**The order across two parents comes from the plan index, not the board.** `blockedBy` only sees
siblings, so it says phase 4 waits on phase 3; it cannot know that phase 3 waits on phase 1 under
a different card. The plan index's **Depends on** column is the authority there — read it before
picking up a phase whose parent is not the first one.

---

## `/implement` vs `/do`

Neither writes plans. `/analyze` does, and both of these execute what it wrote.

| | `/implement` | `/do` |
|---|---|---|
| Input | `<SLUG>_PLAN.md` | TaskID from `todos.md` |
| Creates the tasks | yes — one per phase | no, it already exists |
| Where the plan comes from | the plan set, copied unchanged | the task's plan file, or a brief from its text |
| Use when | starting the work `/analyze` planned | picking up a task that's already tracked |

`/do` is also the way to run phase 2 onward of a plan set, one per session.

---

## Layout

```
claude-commands/
├── commands/                 # slash commands
│   ├── analyze.md            # archaeology + the implementation plan
│   ├── analyze-package.md    # package quality analysis
│   ├── dbg.md                # Delve batch workflows
│   ├── do.md                 # execute one task by TaskID
│   ├── implement.md          # plan → tasks → code (no planning of its own)
│   ├── postmortem.md
│   ├── reorganize-todos.md
│   ├── token-maxxing.md
│   ├── token-maxxing-update-docs.md
│   ├── update-readme.md
│   ├── update-todos.md
│   └── up-version.md
├── agents/                   # subagents, dispatched by subagent_type
│   ├── task-locator.md       ├── phase-planner.md
│   ├── context-loader.md     ├── plan-reconciler.md
│   ├── plan-generator.md     ├── readme-updater.md
│   ├── completion-handler.md └── pusher.md
├── skills/                   # each a directory with SKILL.md + assets
│   ├── confluence-writer/    # SKILL.md, template.html
│   ├── confluence-reader/    # + confluence_fetch.py, credentials.example
│   ├── issue-ticket-reader/  # + issue_fetch.py, credentials.example
│   ├── create-task/
│   ├── task/                 # + DESIGN.md, taskcore/task_gh/task_gl/todos/session.py
│   ├── sync-todos-into-gitlab-board/  # + sync_todos.py
│   ├── reap-orphaned-blobs/
│   └── update-ats-cv/        # + SCHEMA.md, cv_render/cv_extract/cv_preview.py, fonts
├── cmd/dlv/                  # Delve helpers — copy into your Go project
├── sync.sh
├── remove_non_commands.sh
└── README.md
```

A project using these commands ends up with:

```
your-project/
├── chatbot/bowl/.workflows/
│   ├── todos.md              # tasks, with TaskIDs
│   ├── package_readme.md     # technical docs
│   ├── analysis_report.md    # quality analysis
│   ├── plan/{TaskID}.md
│   └── postmortem/{TaskID}.md
├── .workflows/plan/<slug>/phase-N.md      # repo root, one per phase
├── 20250108-164512-A3F7_code_analyzer.md  # repo root
└── PURGE_..._PLAN.md                      # repo root, the plan index
```

TaskIDs are `P{0-3}-{SCOPE}-{ID}` (e.g. `P0-DB-A236`), unique across every `todos.md` in the
repo. Tasks are tagged EASY / NORMAL / HARD; EASY and NORMAL can run from the task description
alone, HARD requires a plan file.

---

## Contributing

Fork, branch, test against a real `.workflows/` directory, open a PR. Run `./sync.sh` to try a
change locally before committing it.

## License

[MIT](https://mit-license.org).
