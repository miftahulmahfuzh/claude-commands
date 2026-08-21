---
name: task
description: Use when the user names a task card to work on — "/task 14", "fetch task 14", "task daily-words#14", "/task 7" in a GitLab repo, a pasted issue URL, "what's open?", "pick up that card again" — or when work finishes and a card needs moving. Drives task cards on GitHub Projects (personal repos) or GitLab Issues (work repos): claims the card by moving it to In Progress as soon as it is fetched, reads it and every comment, brainstorms it, writes or mints the implementation plan, links it back onto the card, and moves it to Completed only once the work is verified. On GitHub the work happens in a fresh worktree branched off origin/main and lands as a pull request linked to the card. Handles the reopen loop, where a card comes back with a bug report in a new comment.
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
| Development loop | this skill runs it, in a **worktree off `origin/main`**, and every card ends in a **pull request** | this skill mints a TaskID and hands off to **`/do`** |
| `Completed` means | the linked PR is **merged** | the issue is **closed** |

**Core principle: the board records what happened, and it is never ahead of
reality.** A card sits in `In Progress` only while it is genuinely being worked,
and reaches `Completed` only after verification has actually passed and the user
has said the work is done. Never move a card on the strength of "the code is
written".

On GitHub that bar is mechanical rather than remembered: `finish` refuses to
complete a card unless GitHub itself reports a **merged** linked pull request.

**This skill works cards; it does not create them.** Capturing a *new* card is
`/create-task`, which opens the issue, adds it to the board and writes the Open
stage in one command — three operations, because `gh issue create` alone leaves an
issue no column ever shows. Its plumbing is `task_gh.py create` / `task_gl.py
create`, and it lives here so board discovery and the board-id cache stay single.

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
error message. On GitHub, `worktree` and `pr` refuse outright when the card's
repo is not the repo they are pointed at, so the check is enforced as well as
instructed.

### 3. Work out which round this is

`plans` empty → round 1. Otherwise this is a **return visit**: read the existing
plan first, then treat the comments newer than it as the new requirement.
Brainstorm only the delta — do not re-derive the original design.

### 4. Brainstorm

Invoke the **brainstorming** skill: one question at a time, 2–3 approaches with a
recommendation, the design in sections. The card's body and comments are starting
context, not a spec — the user wrote it in a hurry.

### 5. On plan approval: cut the worktree, then two writes and no prompt

The moment the user approves the plan, do all of this without asking. The stage
was already claimed in step 1, so what remains is the workspace, the plan and its
link.

**a. On GitHub, cut the worktree first — before the plan file is written.**

```bash
python3 $S/task_gh.py worktree 14                 # a return visit: --round 2
cd ~/.worktrees/<repo>/task-14-<slug>
```

It fetches, branches `task/<number>-<slug>` off **`origin/main`**, and puts the
tree under `~/.worktrees/<repo>/`. Doing it before the plan write is the whole
point: the plan file is then written *inside the worktree*, so it travels in the
pull request with the code it describes instead of landing on `main` on its own.

Everything after this line happens in the worktree — every edit, every commit,
every test run. Nothing in this loop ever writes to the main checkout again.

The command is idempotent (same card, same round → same path, `created: false`),
refuses a card whose repo is not this repo, and reports `behindBase` so a stale
branch is visible rather than surprising. On a **round 2** the branch gets an
`-r2` suffix, so round one's branch and its merged PR stay intact. A fresh
worktree shares no `node_modules` and no virtualenv; the JSON says so under
`hints`.

On **GitLab** there is no worktree step — `/do` owns branching there, and creates
one only for HARD tasks.

**b. Write or mint the plan.** Detect the repo's own convention:

| Repo looks like | Plan path | Label |
|---|---|---|
| has `.workflows/todos.md` | `.workflows/plan/<TaskID>.md` | the TaskID |
| `plans/F<N>-*.md` exists | `plans/F<N+1>-<slug>.md` | `F<N+1>` |
| otherwise | `docs/plans/<YYYY-MM-DD>-<slug>.md` | the date |

On a return visit, **append a dated round section to the existing plan file**
rather than starting a new one, and label the entry `<label> round <n>`.

**c. Link it on the card:**

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

### 6. Develop, then open the pull request

On a **GitHub** repo, do the work in the worktree, commit it there, and then open
the PR — every card ends in one, however small:

```bash
python3 $S/task_gh.py pr 14 --plan plans/F23-recurring-cards.md
```

`pr` pushes the branch, opens the PR with `Closes #14` as the first line of its
body, and then **reads back from GitHub what it actually linked**, printing both
the issue's linked PRs and the board field's own contents plus a one-line
`verdict`. Quote that verdict rather than assuming the link took. It refuses to
run from a dirty worktree or from the base branch, and re-running it on an
existing open PR repairs a missing closing keyword instead of opening a second.

The card **stays In Progress** with the PR now visible in the board's *Linked
pull requests* column. Give the user the PR URL: merging is theirs.

On a **work repo with `.workflows/todos.md`**, none of the above applies. That
repo already has a task system — 33 todos.md files and a `/do` command orchestrating five subagents
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
On GitHub there is a third condition, and it is checked for you: the linked PR is
merged.

```bash
# GitHub — after the user merges the PR
python3 $S/task_gh.py finish 14 --note "Verified: <commands that passed>."

# GitLab
python3 $S/task_gl.py comment <ref> "Done in <sha>. Verified: <commands that passed>."
python3 $S/task_gl.py status <ref> Completed
```

`finish` asks GitHub whether a linked PR is merged, and **exits non-zero if none
is** — so a card cannot reach Completed while its code is still in review. It
then sets Status and posts the note naming the merge commit, leaving the issue
closed (see the closing section). `--allow-unmerged` exists for a card
that genuinely has no PR; using it to skip a review is defeating the check.

On GitLab, `status <ref> Completed` **closes the issue** as well as labelling it,
which is what moves it into the Closed column and out of the project's issue
list. Reopening later (`status <ref> Open`) reopens the issue too.

If verification fails, say so and leave the card in `In Progress`. A card in the
wrong column is the one failure this system cannot absorb, because the user
trusts the board instead of re-reading the code.

### 8. Retire the worktree (GitHub)

Once the PR is merged and the card is Completed, the branch is dead weight:

```bash
python3 $S/task_gh.py worktree 14 --remove       # --force to discard dirty state
```

It refuses to remove a dirty worktree without `--force`, which is the correct
default — unpushed work is easier to lose here than anywhere else in the loop.
Skip this step if the user still wants the tree around; it costs nothing but disk.

## Why the PR must say `Closes #14`

The board's **Linked pull requests** column reads GitHub's issue↔PR *link*, and
GitHub creates one from exactly two things: a closing keyword in the PR body, or
the PR's Development sidebar. A bare `#14` is a **mention**, and mentions leave
the column empty — the card then looks unworked next to a PR nobody can find from
the board. So `pr` writes `Closes #14` itself and repairs the body if the keyword
is missing, rather than trusting whatever text it was handed.

The keyword's other effect is intended: **merging the PR closes the issue**, and
that closure is allowed to stand. `finish` records Completed and leaves the issue
closed. Only the *live* stages reopen — see the closing section for why that
asymmetry is the whole rule.

`links <ref>` answers "is the board actually showing it?" from two sources — the
issue's links and the board field itself — and names which one answered. The
board field can lag the link by a few seconds, so an empty field beside a live
link is a refresh, not a bug.

## Closing: the two backends differ, and the reason is measured

**GitHub — a merge closes the card, and that is left alone.** `Completed` is the
Status field, and `task_gh.py` still has no `close` subcommand: it never closes an
issue itself. But a merged PR carrying `Closes #14` does, and that closure is
GitHub reporting the truth, so nothing undoes it.

This reverses what this file said earlier, on evidence. The old rule reopened the
issue on *every* stage write, to dodge Projects' **auto-archive** workflow — a
closed item disappears off the board, which would have broken the reopen loop.
**Measured on this board: six closed issues sit in `Done` and every one is still
visible.** Auto-archive is not enabled, so the hazard the rule existed for does
not exist, and all the rule actually produced was a column of cards that were
Done-but-open forever, fighting GitHub's own semantics on every command.

So the reopen is now scoped to the stages where a closed issue would make the
board *lie*:

| Stage written | Closed issue is… |
|---|---|
| `Open` | reopened — nobody can pick up a finished card |
| `In Progress` | reopened — "being worked" and "closed" cannot both be true |
| `Completed` | **left closed** |

`ensure_issue_open` holds that asymmetry in one place. When a card resurfaces
months later, **reopen it by hand** — or `reopen <ref>`, which is exactly what
that subcommand is for — and the next `/task <id>` picks it up normally.

If you ever turn auto-archive **on**, this flips back: completed cards would start
vanishing from the board, and the reopen rule would have to return. `doctor`
reports what it can see; the setting itself is browser-only.

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

The user hits a bug and comments on the card. On GitHub the card is closed by then,
so reopening it is the first move — by hand, or `reopen <ref>` — and then it goes
back to `Open`. Moving it to `Open` or `In Progress` reopens it anyway, so a card
dragged across the board in the browser is repaired by the next stage write rather
than left contradicting itself.

A fresh session runs `/task <id>` and the loop restarts at step 1 with `plans`
non-empty, which is what makes it round 2.

On GitHub, round 2 gets its **own** worktree, branch (`task/14-<slug>-r2`) and
pull request — pass `--round 2` to `worktree`. Round one's merged PR stays linked
to the card, so the column accumulates the card's whole history rather than
overwriting it. Nothing else changes.

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
`gh project create --owner @me --title "Tasks"`, then in the browser (the CLI
cannot do any of these):

- rename the Status options to `Open` / `In Progress` / `Completed`;
- add the built-in **Linked pull requests** field as a column in the board view,
  which is what makes step 6's PR visible on the card;
- leave auto-archive **off** — with it off, completed cards stay visible in `Done`
  after the merge closes them, which is what the closing rule above relies on.

`doctor` reports the Status options, whether it can see a `Linked pull requests`
field, and the worktree root. Worktrees go under `~/.worktrees/<repo>/` —
set `TASK_WORKTREES` to move them.

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
task_gh.py    GitHub Issues + Projects v2 via the gh CLI, plus the worktree,
              pull-request and linked-PR plumbing (GitHub-only, by design)
task_gl.py    GitLab Issues, via REST and urllib
todos.py      the .workflows/todos.md corpus: scan, validate, mint, rename
```

Every one has a `selftest` (`python3 taskcore.py` for the shared half) that runs
offline with no token and no network. Run all four after touching any of them —
`taskcore` is imported by both backends, so a change there moves both.

The `create-task` skill is a SKILL.md and nothing else; both its backends are the
`create` subcommands here, so it ships no plumbing of its own.

## Cross-laptop

Cards live on GitHub and GitLab, so they need no syncing. **This directory
does**: it belongs in `~/claude-commands/skills/task/`, whose `sync.sh` copies
`commands/`, `agents/` and `skills/` into `~/.claude/`. Editing the copy under
`~/.claude/skills/` alone means the second laptop never sees it.

`~/.config/task-skill/config.json` (GitHub board ids) is a machine-local cache
and must **not** be synced. `~/.config/task-skill/gitlab` holds a secret and must
not be committed anywhere.
