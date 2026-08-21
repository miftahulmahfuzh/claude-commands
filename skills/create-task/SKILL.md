---
name: create-task
description: Use when a new task card should be captured rather than worked — "create a task for X", "open a card for that bug", "/create-task …", a follow-up found mid-review that must not derail the current work, an idea worth not losing, or a bug noticed in passing that belongs on the board instead of in the scrollback.
---

# create-task

## Overview

Capture one card, on the board, in the **Open** column, in one command — then stop.
This skill does not brainstorm, plan, or implement. `/task <id>` is the loop that
picks a card up; this is only the front door that puts one there.

**The measured fact this exists for:** `gh issue create` alone produces an issue the
board has never heard of. It sits in no column, `resolve` cannot find it, and the
next person to open the kanban sees nothing. Verified on `run-insights`: issue #6
was created with plain `gh issue create`, and `task_gh.py resolve 6` answered
*"No card on the board for issue #6."*

So creating a card is **three** operations, never one — open the issue, add it to
the board, write the stage — and the helper does all three and then reads the board
back to say which column it actually landed in. Quote that verdict; do not assume.

## Picking the backend

Same rule as the `task` skill — read `git remote get-url origin`:

- host is `github.com` → `task_gh.py create`
- anything else → `task_gl.py create`

If the current directory is not a repo, **ask which project the card belongs to.**
Both helpers refuse to guess, because a card in the wrong project is worse than an
error message.

```bash
S=~/.claude/skills/task          # the plumbing lives with the task skill, not here
python3 $S/task_gh.py create --repo owner/repo "TITLE" --body-file body.md
python3 $S/task_gl.py create --project group/project --title "TITLE" --body-file body.md
```

## Writing the body: scale to context, never invent

The card's reader is a session months from now with **none** of today's context.

- **Rich context in this session** (you just found the bug, ran the numbers, read the
  code) → write it down: the mechanism, the measured evidence, the file and symbol,
  the suggested fix, and whether it is urgent. This is the whole value of capturing a
  card from inside a session rather than from memory later.
- **A one-line idea from the user** → a faithful one-liner. Do not pad it into a
  fake spec. `/task` opens with brainstorming precisely because rough cards are
  expected; inventing detail the user never said is worse than a short card.

Never fabricate repro steps, error messages, or measurements. If you have not seen
it, say what you actually know and mark the rest as unverified.

## Quick reference

| Need | Flag |
|---|---|
| Body from a file (preferred — no shell escaping) | `--body-file path` or `-` for stdin |
| Picking it up right now, not later | `--stage "In Progress"` (GitHub) / `--status` (GitLab) |
| An idea with no repo yet | `--draft` (GitHub only; `promote` it later) |
| An issue that already exists but is off the board | `--issue N --repo owner/repo` |

`Completed` is refused on both backends. A card cannot be born done — on GitHub
`finish` writes it and requires a merged PR; on GitLab it also means *closed*.

## Common mistakes

| Mistake | What happens |
|---|---|
| `gh issue create` on its own | The issue exists and the board never shows it. |
| Guessing the repo from context | The card lands in the wrong project. Ask. |
| Creating the card, then working it in the same breath | Use `/task <id>`, which claims the card as it fetches. |
| Trusting `created: true` | It only means the issue exists. Read `verdict`. |
| `onBoard: false` right after creating | Projects is eventually consistent; the helper already retries for ~12 s. If it still fails, re-run with `--issue N`. |

## After it exists

Print the number and the URL, say which column it landed in, and **stop**. Do not
start work. If the user wants it worked now, that is `/task <number>`.

## Layout

Nothing executable lives here. The plumbing is `task_gh.py create` / `task_gl.py
create` in the **task** skill, so board discovery, the machine-local board-id cache,
the stage aliases and reference parsing have exactly one implementation. Run those
scripts' `selftest` after touching either.
