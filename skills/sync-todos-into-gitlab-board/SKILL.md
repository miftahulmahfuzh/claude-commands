---
name: sync-todos-into-gitlab-board
description: Use when asked to sync, push or mirror the tasks in a `.workflows/todos.md` onto a GitLab issue board — "/sync-todos-into-gitlab-board .workflows/todos.md", "put my todos on the GitLab board", "mirror db/.workflows/todos.md into GitLab", "why isn't task X on the board". Creates one GitLab issue per live task, in the board column its stage says, and repairs non-canonical TaskIDs first — mechanically where `todos.py rename` can, with one subagent per case that needs judgement.
---

# Sync todos.md into a GitLab board

## Overview

One `.workflows/todos.md` in, one GitLab issue per live task out, each landing in
the board column its stage says. The **TaskID is the identity**, carried in the
issue title, so re-running updates rather than duplicates.

`todos.md` stays the source of truth for execution — the board is a window onto
it, and each card says so and names `/do <TaskID>`.

```bash
S=~/.claude/skills/sync-todos-into-gitlab-board

python3 $S/sync_todos.py plan   .workflows/todos.md            # what would happen
python3 $S/sync_todos.py apply  .workflows/todos.md            # active tasks only
python3 $S/sync_todos.py apply  .workflows/todos.md --include-completed
python3 $S/sync_todos.py repair .workflows/todos.md            # non-canonical ids
python3 $S/sync_todos.py selftest                              # offline
```

`--project` defaults to the origin remote and is accepted on either side of the
subcommand. `--limit N` takes the first N. `plan` writes nothing and is the
default for a reason — see the warning below.

## Read this before the first `apply` on a repo

**Creating a GitLab issue is close to irreversible.** Deleting one needs the
**Owner** role; a Maintainer can only *close* it, and a closed issue still sits
in the project's issue list forever. On `ai/chatbot/agentic` the user is
Maintainer (access_level 40).

So: run `plan` first, show the user the counts and the stage split, and get
agreement on scope before `apply`. Prefer a small `--limit` pilot so the user can
judge the card format against a handful of permanent issues rather than dozens.
That is not ceremony — the first real run surfaced two format problems
(a finished card carrying neither its `Completed` date nor its `Method`).

## The flow

### 1. Repair non-canonical TaskIDs first

A card whose id does not match `P<0-4>-<PKG>-<L><NNN>` should not be created —
the id is the sync's identity, and syncing a malformed one makes it permanent.

```bash
python3 $S/sync_todos.py repair <file>
```

It splits the problem two ways, and the split is the point:

- **`mechanical`** — ids that have an entry. `todos.py rename --apply` fixes
  these deterministically: it keeps the old suffix's first letter, reserves
  numbers per package across all priorities, stamps `**Former ID**`, writes a
  ledger, and renames plan files in lockstep. **Use it. Do not hand these to a
  subagent** — it is a tested engine with ~60 assertions, and an agent doing
  string surgery across 33 shared files is strictly worse at the same job.
- **`judgement`** — ids appearing only as a bare `- **ID**: text` reference in a
  `## Completed` or `## Recent Activity` log. `rename` cannot reach them: there
  is no entry to rename, and no single right answer. **One subagent per case.**

Dispatch one `Explore`-style agent per judgement case, in parallel, each with:

> In `<repo>`, the file `<file>` line `<line>` (section `## <section>`) carries
> the non-canonical TaskID `<id>` with the description "`<text>`". It has no
> entry in any `.workflows/todos.md`. Decide which of these it is, and report
> back — **do not edit any file**:
> (a) the same work as an existing entry under a different id — name that entry's
> current TaskID and quote its title as evidence;
> (b) real work never entered — say so, and propose a canonical id from
> `todos.py mint <PKG>`;
> (c) a stale log line describing nothing current — say so.
> Give your confidence and the evidence you used. If you cannot tell, say that
> rather than guessing.

Then act on the reports yourself, in the main thread: the agents gather evidence,
you make the edit. Anything below high confidence stays as written, with a note
in the block saying its ids are unreliable — a historical log rewritten on a
guess is worse than one that admits it is wrong.

### 2. Plan, and show the user

```bash
python3 $S/sync_todos.py plan <file> [--include-completed]
```

Report `liveEntries`, `echoesIgnored`, `stageCounts`, and the create/update/
unchanged split. If `nonCanonical` is non-empty, go back to step 1.

### 3. Apply

```bash
python3 $S/sync_todos.py apply <file> [--include-completed] [--limit N]
```

Then verify against the API rather than trusting the exit code: per-column issue
counts, and that no card carries two stage labels.

## Stages

The column comes from the checkbox first, then `Status:`:

| todos.md | Column |
|---|---|
| `- [ ]`, `Status: active` / `pending` / absent | **Open** |
| `- [ ]`, `Status: in_progress` (or wip/started/doing/partial) | **In Progress** |
| `- [x]` | **Completed** |

The checkbox wins on done-ness — it is what the corpus is consistent about,
while `Status:` is missing from 28 live entries. But `Status: in_progress` on an
unticked entry is information the checkbox cannot carry, and three real tasks
have it; mapping those to Open would file started work as untouched. A ticked box
with a contradicting status is still Completed, and the disagreement is reported
in `stageFrom` rather than silently resolved.

## Three things that would go wrong quietly

- **Echoes are not tasks.** A todos.md carries a rolling summary (`### Today` /
  `This Week` / `This Month`) and an append-only `## Recent Activity` log in
  which the same id appears repeatedly. Only entries under `## Active Tasks`
  become issues. The root file has **27 live entries and 28 echoes** — ignoring
  this roughly doubles the issue count with permanent duplicates.
- **Bodies are not rewritten by default.** A human may add notes to a card, and
  clobbering them every run would make the sync hostile. The body is only
  written when the source marker is absent — or with `--refresh-bodies`, which
  *does* discard card notes and is therefore opt-in. That flag needs the real
  source path in the comparison: with an empty one, every card differs from
  itself and every run rewrites everything.
- **Completed cards stay open.** A closed GitLab issue moves to the board's
  Closed column, out of `status::completed`. So finished work sits as an open
  issue carrying the completed label, which inflates the project's open-issue
  count. That is the cost of using a label board; tell the user rather than
  letting them discover it.

## Verified state

First real run, `ai/chatbot/agentic`, `.workflows/todos.md`: 27 cards — 12 Open,
15 Completed — from 27 live entries with 28 echoes ignored; re-run reports 27
unchanged; every card carries exactly one stage label.

Board: `https://git.tuntun.co.id/ai/chatbot/agentic/-/boards/10`

## Setup

Needs the `/task` skill's GitLab half: `~/.config/task-skill/gitlab` with
`GITLAB_HOST` and a `GITLAB_TOKEN` holding the `api` scope, plus the three stage
labels and the board on the target project:

```bash
python3 ~/.claude/skills/task/task_gl.py labels --project <path> --ensure
python3 ~/.claude/skills/task/task_gl.py board  --project <path> --ensure
```

`sync_todos.py` imports `taskcore.py`, `task_gl.py` and `todos.py` from
`~/.claude/skills/task/` rather than re-implementing any of them, so a change to
the stage labels or the plan-block format moves both skills at once. Run **all
five** selftests after touching any of them.
