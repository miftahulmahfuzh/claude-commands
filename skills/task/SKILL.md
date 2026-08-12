---
name: task
description: Use when the user names a task card to work on — "/task 14", "fetch task 14", "task daily-words#14", "/task 7" in a GitLab repo, a pasted issue URL, "what's open?", "pick up that card again" — or when work finishes and a card needs moving. Drives task cards on GitHub Projects (personal repos) or GitLab Issues (work repos): claims the card by moving it to In Progress as soon as it is fetched, reads it and every comment, brainstorms it, writes or mints the implementation plan, links it back onto the card, and moves it to Completed only once the work is verified. Handles the reopen loop, where a card comes back with a bug report in a new comment.
---

# Task

## Overview

One loop, two backends. A card is captured in a browser (or on a phone), fetched
here by id, brainstormed, planned, built, and moved through **Open → In Progress
→ Completed** — then possibly back to Open when a bug turns up months later.

| | Personal repos | Work repos |
|---|---|---|
| Cards live in | GitHub Issues + a Projects board named `Tasks` | GitLab Issues on the self-hosted instance |
| Stage carried by | the board's **Status** field | labels for Open/In Progress; **Completed = the issue is closed** |
| Kanban view | one user-level Projects board, spanning repos | one board **per project**: 2 label columns + built-in Closed |
| Cross-project view | the same board | the **group issue list**, filtered by label |
| Helper | `task_gh.py` | `task_gl.py` |
| Development loop | this skill runs it | this skill mints a TaskID and hands off to **`/do`** |

**Core principle: the board records what happened, and it is never ahead of
reality.** A card sits in `In Progress` only while it is genuinely being worked,
and reaches `Completed` only after verification has actually passed and the user
has said the work is done. Never move a card on the strength of "the code is
written".

## Picking the backend

Read `git remote get-url origin` in the current directory:

- host is `github.com` → `task_gh.py`
- anything else → `task_gl.py` (it reads `GITLAB_HOST` from
  `~/.config/task-skill/gitlab`)

If the current directory is not a repo, ask which project the card belongs to
rather than guessing. Both helpers take the project explicitly —
`--repo owner/repo` and `--project group/project` — on **either side** of the
subcommand.

```bash
S=~/.claude/skills/task
python3 $S/task_gh.py doctor          # GitHub: gh, auth, scopes, board, Status options
python3 $S/task_gl.py doctor          # GitLab: token, host, tier, project, stage labels
```

`doctor` names the fix for whatever is missing. Run it first whenever anything
behaves oddly, and quote its output rather than diagnosing from a stack trace.

## The loop

### 1. Resolve, read the whole card, and claim it

```bash
python3 $S/task_gh.py resolve <ref>        # or task_gl.py
python3 $S/task_gl.py status <ref> "In Progress"
```

**Move the card to In Progress immediately, as part of fetching it** — not later.
Running `/task <id>` *is* picking the card up, and the board's job is to say what
is being worked on right now; a card that stays in Open while a session is
actively brainstorming it makes the board lie to anyone else looking.

Two consequences to honour rather than ignore:

- **If the session ends without proceeding** — the plan is rejected, the idea
  turns out to be wrong, the user changes direction — **move it back to Open
  before finishing.** Leaving it In Progress is the failure mode this timing
  introduces, and it is yours to prevent.
- It is idempotent, so a card already In Progress reports `changed: false`. Bare
  `/task` with no id is a listing and claims nothing.

`<ref>` is `14`, `owner/repo#14`, `group/project#7`, an issue URL, and on GitHub
also a `PVTI_…` item id or `draft:<part of the title>`.

**Read the body *and* every comment, in order.** On a card that has been round
the loop, the body is the original idea and the newest comment is the current bug
report. Reading only the body is the main way this workflow fails quietly.
`resolve` returns `comments` chronologically, plus `plans` and `round`.

GitLab also returns `systemNotes` separately — GitLab's own audit lines ("added
label …"). They are history, never a bug report; the human `comments` are what
the loop reads.

On GitHub, if the card is still a **draft item** it has no number, no comments
and no reopen, so promote it first:

```bash
python3 $S/task_gh.py promote <ref> --repo <owner/repo>
```

### 2. Check the card belongs here

If the card's repo/project is not the one in the current directory, **stop** and
say which it is. Writing a plan file into the wrong project is worse than an
error message.

### 3. Work out which round this is

`plans` empty → round 1. Otherwise this is a **return visit**: read the existing
plan first, then treat the comments newer than it as the new requirement.
Brainstorm only the delta — do not re-derive the original design.

### 4. Brainstorm

Invoke the **brainstorming** skill: one question at a time, 2–3 approaches with a
recommendation, the design in sections. The card's body and comments are starting
context, not a spec — the user wrote it in a hurry.

### 5. On plan approval, two writes and no prompt

The moment the user approves the plan, do both without asking. The stage was
already claimed in step 1, so what remains is the plan and its link.

**a. Write or mint the plan.** Detect the repo's own convention:

| Repo looks like | Plan path | Label |
|---|---|---|
| has `.workflows/todos.md` | `.workflows/plan/<TaskID>.md` | the TaskID |
| `plans/F<N>-*.md` exists | `plans/F<N+1>-<slug>.md` | `F<N+1>` |
| otherwise | `docs/plans/<YYYY-MM-DD>-<slug>.md` | the date |

On a return visit, **append a dated round section to the existing plan file**
rather than starting a new one, and label the entry `<label> round <n>`.

**b. Link it on the card:**

```bash
python3 $S/task_gl.py plan <ref> P1-MN-A007 .workflows/plan/P1-MN-A007.md --date 2026-08-12
```

`plan` rewrites only the block between `<!-- task:plans -->` and
`<!-- /task:plans -->`, appending a line. It is idempotent and append-only, so
round two adds a second line instead of overwriting the first. It lives in the
**body**, not a comment, because comments get buried under bug reports and the
body is what the next session reads first.

Then post one comment recording the transition and the plan path, so the card has
a timeline as well as a current state.

### 6. Develop

On a **GitHub** repo, do the work here.

On a **work repo with `.workflows/todos.md`**, do not. That repo already has a
task system — 33 todos.md files and a `/do` command orchestrating five subagents
— and this skill is its front door, not a replacement. Mint the TaskID into the
right package's todos.md and hand off:

```bash
python3 $S/todos.py mint MN --priority P1 --letter A   # next free canonical id
python3 $S/todos.py validate                           # before and after
```

Then run `/do <TaskID>`. Its completion-handler updates todos.md; you mirror that
onto the GitLab card in step 7.

### 7. Completed — only on both conditions

The user says the work is done **and** verification has actually passed. Use the
**verification-before-completion** skill; do not claim a pass you have not seen.

```bash
python3 $S/task_gl.py comment <ref> "Done in <sha>. Verified: <commands that passed>."
python3 $S/task_gl.py status <ref> Completed
```

On GitLab that second command **closes the issue** as well as labelling it, which
is what moves it into the Closed column and out of the project's issue list.
Reopening later (`status <ref> Open`) reopens the issue too.

If verification fails, say so and leave the card in `In Progress`. A card in the
wrong column is the one failure this system cannot absorb, because the user
trusts the board instead of re-reading the code.

## Closing: the two backends differ, and the reason is measured

**GitHub — never close.** `Completed` is the Status field only, and `task_gh.py`
has no `close` subcommand. Projects ships an **auto-archive** workflow on closed
items: a closed issue disappears off the board, so the reopen loop would fight
the board's own automation every time a bug comes back.

**GitLab — Completed *is* closed.** `task_gl.py status <ref> Completed` sets the
label **and** closes the issue, in one PUT; `Open` and `In Progress` reopen it.
This reverses what this file said earlier, on evidence:

- A GitLab **label list shows open issues only**, and the project's default issue
  list shows open issues only. So a completed card that stayed open sat in a
  shared repo's issue list forever — `ai/chatbot/agentic` was showing **55 open
  issues** to the team, 44 of them finished work.
- Closing fixes that but empties a `status::completed` label column. Measured:
  after closing, `state=opened&labels=status::completed` returns **0**.
- So the third column is GitLab's **built-in Closed list**, not a label list.
  `board --ensure` therefore creates only two label columns and leaves
  `hide_closed_list` **false**.

`effective_stage()` reads a closed issue as Completed **whatever its labels say** —
without that, a closed card reads as Open and every sync tries to "fix" it
forever. The `status::completed` label is still applied, because it survives
closing and stays useful as a filter.

Result on `ai/chatbot/agentic`: the team's issue list went **55 → 11**, and the
board reads `status::open` (11) | `status::in-progress` (0) | Closed (44).

## The reopen loop

The user hits a bug, comments on the card, and moves it back to `Open`. A fresh
session runs `/task <id>` and the loop restarts at step 1 with `plans` non-empty,
which is what makes it round 2. Nothing else changes.

## The TaskID rules

`todos.py` owns the `.workflows/todos.md` corpus. Canonical form is
**`P<0-4>-<PKG>-<L><NNN>`** — one letter, three digits — and `validate` exits
non-zero on anything else. Three measured facts it encodes, each of which broke
something before it was understood:

- **The checkbox is the stage, but only under `## Active Tasks`.** A file also
  carries a rolling summary (`### Today` / `This Week` / `This Month`) and an
  append-only `## Recent Activity` log; in those, the checkbox records what was
  true *then*. One id is `- [x]` in one section and `- [ ]` in another.
- **The same id appears many times per file, legitimately.** Every repeated id in
  the corpus repeats *within* one file, never across files — that is what
  separates a summary echo from a real collision.
- **Package codes are not unique.** `TT` is claimed by two packages, `CMP` by two
  more. Uniqueness is only ever checked on the whole TaskID across every file.

```bash
python3 $S/todos.py scan          # files, live entries, echoes, problems
python3 $S/todos.py validate      # non-zero if any id is non-canonical or duplicated
python3 $S/todos.py rename        # dry run; --apply to perform, writes a ledger
```

`rename` stamps `**Former ID**` on live entries and records everything in
`.workflows/TASKID-RENAMES.md`, because ids appear in commit messages that cannot
be rewritten.

## Setup

**GitHub**, once per laptop: `sudo apt install gh`, `gh auth login`,
`gh auth refresh -s project,read:project`. Once globally:
`gh project create --owner @me --title "Tasks"`, then rename the Status options
to `Open` / `In Progress` / `Completed` in the browser (the CLI cannot) and check
auto-archive is off.

**GitLab**, once per laptop: a personal access token with the `api` scope — no
admin rights needed, it inherits the user's own permissions — in
`~/.config/task-skill/gitlab`, mode 0600:

```
GITLAB_HOST=https://git.example.com
GITLAB_TOKEN=glpat-…
```

Then once per project, in this order — the board needs the labels to exist:

```bash
python3 $S/task_gl.py labels --project <path> --ensure   # the three stage labels
python3 $S/task_gl.py board  --project <path> --ensure   # the kanban board + columns
```

Both are idempotent, and `doctor` prints the board URL plus the cross-project one.

`board --ensure` shapes the board as **`status::open` | `status::in-progress` |
Closed**. It hides the backlog ("Open") column, which duplicates `status::open`,
and keeps the **Closed** column visible because that is where Completed cards
live — see the closing section above for why a `status::completed` label column
cannot do that job.

The remaining cost is that an **open** issue carrying no stage label appears in no
column, so `doctor` reports those under `hiddenFromBoard`. It reports rather than
fails: in a shared repo a teammate's ordinary issue has no stage labels, and a
doctor that goes red for that is a doctor nobody reads.

**Two Community Edition limits, both measured on this instance rather than
inferred from the docs:**

- **Scoped labels do not enforce exclusivity.** `status::in-progress` does not
  remove `status::open`. `status` therefore writes the whole label set in one
  call and verifies the result before reporting success; `add_labels` alone
  leaves a card in two stages, visible as two board columns.
- **There are no group boards.** `POST /groups/:id/boards` returns 404 —
  and note that `GET` returns `200` with `[]`, which reads as "available but
  empty" and is why this needed testing rather than reading. So there is **one
  board per project**, and the cross-project view is the group *issue list*:
  `<host>/groups/<group>/-/issues?label_name[]=status::in-progress`.

On the board, dragging a card between two label lists is GitLab's own swap — it
removes the source label and adds the destination's, which is the same
one-stage-at-a-time rule `status` enforces. The **Backlog** column holds issues
carrying none of the three labels, so anything appearing there is a card that
missed a stage label rather than a real column of work.

## Layout

```
taskcore.py   plan-block codec, stages and aliases, reference parsing — shared
task_gh.py    GitHub Issues + Projects v2, via the gh CLI
task_gl.py    GitLab Issues, via REST and urllib
todos.py      the .workflows/todos.md corpus: scan, validate, mint, rename
```

Every one has a `selftest` (`python3 taskcore.py` for the shared half) that runs
offline with no token and no network. Run all four after touching any of them —
`taskcore` is imported by both backends, so a change there moves both.

## Cross-laptop

Cards live on GitHub and GitLab, so they need no syncing. **This directory
does**: it belongs in `~/claude-commands/skills/task/`, whose `sync.sh` copies
`commands/`, `agents/` and `skills/` into `~/.claude/`. Editing the copy under
`~/.claude/skills/` alone means the second laptop never sees it.

`~/.config/task-skill/config.json` (GitHub board ids) is a machine-local cache
and must **not** be synced. `~/.config/task-skill/gitlab` holds a secret and must
not be committed anywhere.
