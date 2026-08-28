---
name: create-task
description: Use when a new task card should be captured rather than worked — "create a task for X", "open a card for that bug", "/create-task …", a follow-up found mid-review that must not derail the current work, an idea worth not losing, or a bug noticed in passing that belongs on the board instead of in the scrollback.
---

# create-task

## Overview

Capture one card, on the board, in the **Open** column, in one command — then stop.
This skill does not brainstorm, plan, or implement. `/task <id>` is the loop that
picks a card up; this is only the front door that puts one there.

**It never asks a question.** Capturing a card is a two-second act next to the
work it describes, and a clarifying question turns it into a round trip that can
outlast the session — the card is meant to hold the idea *until* someone has time
for it, so stalling to perfect it defeats the point. Everything below is decided
from what is already on hand: the title from what the user said, the body from
what this session actually knows, the project from the reference or the working
directory, and a **draft** when there is genuinely no project to name. A card
that turns out slightly wrong is edited on the board in five seconds; a question
asked at 1am is answered at 9.

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

If the current directory is not a repo, work down this ladder rather than asking —
the helpers refuse to *guess* a project, but every rung here is evidence, not a
guess:

1. **The reference or the user's words name it** — `owner/repo`, `group/project`,
   a pasted issue URL, "file this on run-insights". Use it.
2. **A repo sits above the working directory** — `git rev-parse --show-toplevel`
   from a subdirectory still answers. Use that repo.
3. **The card came out of work done in this session** — the files being edited
   belong to a repo. That repo owns the card.
4. **Nothing names a project** → capture it as a **GitHub draft item**
   (`--draft`). This is the designed answer for a project-less idea, not a
   consolation prize: the draft is the note, it sits in Open on the board, and
   `promote <ref> --repo owner/repo` files it properly the day someone picks it
   up. An idea parked on the board beats an idea lost to an unanswered question.

Only a genuinely ambiguous project on the **GitLab** side has no draft to fall
back on. There, name the choice you made and say which other project was possible
— a comment on the card, not a prompt.

```bash
S=~/.claude/skills/task          # the plumbing lives with the task skill, not here
python3 $S/task_gh.py create --repo owner/repo "TITLE" --body-file body.md
python3 $S/task_gl.py create --project group/project --title "TITLE" --body-file body.md
```

## When `/analyze` ran in the same breath

A prompt like *"/create-task 2 cards and /analyze …"* asks for both, and the order is not
negotiable: **`/analyze` runs first, and the cards are created from its finished plan index.**
Cards minted before the plan exists commit the board to a shape nothing downstream agrees with —
which is exactly what happened on `JMTarot`, where two cards (#11, #12) and a four-phase plan set
were produced in one session and never referred to each other.

The two counts are not rivals, they are different altitudes:

| | Unit | Who decides it |
|---|---|---|
| "2 cards" | the deliverables the user would name | the user |
| "4 phases" | independently-shippable units of execution | `/analyze`, which read the code |

So neither count is overridden. `/analyze` now numbers the user's asks `R1…Rn` and every phase
declares which `R` it serves, in the plan index's **Requirements** table. That table is the whole
input to the decision below — read it, do not re-derive it from the prose or from the code.

```bash
python3 $S/task_gh.py create --repo owner/repo "TITLE" --body-file parent.md
python3 $S/task_gh.py create --repo owner/repo "TITLE" --body-file phase-1.md --parent 12
```

### The shape follows the mapping

- **Every phase serves exactly one `R`** → one **parent card per `R`**, with that `R`'s phases as
  its **sub-issues**, in phase order. Nothing is lost: the user's count is the parent count, and
  `/analyze`'s count is the sub-issue count.
- **Some phase serves two or more `R`s** → **one parent card** for the whole plan set, with every
  phase beneath it, and the user's asks listed as bullets in its body. A phase spanning two `R`s
  cannot be attached to either one, and that coupling is a real fact about the work — do not
  pretend it away by picking a parent.
- **One phase, one `R`** → one card, no sub-issues. Do not create a parent for a single phase.

Sub-issues are created in phase order, because that order *is* GitHub's sub-issue order and
`resolve` reads position 1 as phase 1. Create them one at a time, in order, and never sort them.

### What goes in the bodies

**Parent** — everything a session needs before it touches anything:

- the plan index path, and the **branch and base sha**, which are the durable identifiers
- the worktree path, marked as what it is: *cut on this machine on this date; recreate with
  `task_gh.py worktree`*. A `~/.worktrees/...` path means nothing on the other laptop.
- the `R` (or Rs) it covers, in the user's own words
- the phase table: number, title, and plan path — **plus the branch**, because `/analyze` writes
  the plan files *inside the worktree*, so `.workflows/plan/<slug>/phase-1.md` does not exist on
  `main` and a bare path reads as a dead link until the pull request merges

**Each phase** — the plan path (with the branch), `Depends on`, and the ownership line. Spell a
`Depends on` that crosses parents out in full — *phase 1 (#13, under #12)* — because `resolve`'s
`blockedBy` only sees siblings and will not report it:

> Work this in **#12's** worktree, on `feature/history-retry-and-soft-delete`. Do not cut a
> branch off `origin/main` — phase 2 builds on phase 1, which is not there yet. #12 owns the
> pull request; this card completes on its commit
> (`finish <n> --child-of 12 --commit <sha>`).

Then write each card's number back into the plan index's **Card** column, so the mapping reads in
both directions.

### Limits worth stating out loud

- **GitHub only.** GitLab has no sub-issues below Premium — `task_gl.py` has no `--parent` and
  none is coming. On a work repo the phases are already flat TaskIDs in `todos.md` and `/do`
  walks them, so create **one** card there, carry the plan index and the phase list in its body,
  and let `/do` own the order.
- **Cards are captured, not claimed.** Everything lands in `Open`, parent included. `/task <n>`
  claims what it picks up; `--stage "In Progress"` is only for a card being worked right now.
- **Draft items cannot be phases.** Sub-issues are issues; `--draft` and `--parent` are refused
  together. A draft that turns out to be a phase gets `promote`d and then `subissue`d.

## Writing the body: scale to context, never invent

The card's reader is a session months from now with **none** of today's context.

- **Rich context in this session** (you just found the bug, ran the numbers, read the
  code) → write it down: the mechanism, the measured evidence, the file and symbol,
  the suggested fix, and whether it is urgent. This is the whole value of capturing a
  card from inside a session rather than from memory later.
- **A one-line idea from the user** → a faithful one-liner. Do not pad it into a
  fake spec, and do not ask questions to fill it out. `/task` opens with a design
  pass precisely because rough cards are expected; inventing detail the user never
  said is worse than a short card, because the design pass will believe it.

Never fabricate repro steps, error messages, or measurements. If you have not seen
it, say what you actually know and mark the rest as unverified.

## Quick reference

| Need | Flag |
|---|---|
| Body from a file (preferred — no shell escaping) | `--body-file path` or `-` for stdin |
| Picking it up right now, not later | `--stage "In Progress"` (GitHub) / `--status` (GitLab) |
| An idea with no repo yet | `--draft` (GitHub only; `promote` it later) |
| An issue that already exists but is off the board | `--issue N --repo owner/repo` |
| One phase of a plan set, under its parent card | `--parent <ref>` (GitHub only) |
| A phase card that exists but hangs off nothing | `subissue <parent> <child>`, or `--remove` |

`Completed` is refused on both backends. A card cannot be born done — on GitHub
`finish` writes it and requires a merged PR; on GitLab it also means *closed*.

## Common mistakes

| Mistake | What happens |
|---|---|
| `gh issue create` on its own | The issue exists and the board never shows it. |
| Inventing a repo that nothing pointed at | The card lands in the wrong project. Work the ladder above; `--draft` is the floor, not a question. |
| Asking the user to clarify the idea before filing it | The card is the *place* rough ideas wait. Capture what was said, flag what is unverified, move on. |
| Creating the card, then working it in the same breath | Use `/task <id>`, which claims the card as it fetches. |
| Minting cards from the user's sentence when `/analyze` also ran | The board commits to a decomposition the plan set does not share. Read the **Requirements** table; the plan index is the input. |
| Collapsing the user's two asks into one card because the plan has four phases | The counts live at different altitudes and both survive — one parent per `R`, phases as sub-issues. |
| Creating sub-issues out of phase order | GitHub's sub-issue order *is* the order; `resolve` reads position 1 as phase 1 and `blockedBy` follows it. |
| Trusting `created: true` | It only means the issue exists. Read `verdict`. |
| `onBoard: false` right after creating | Projects is eventually consistent; the helper already retries for ~12 s. If it still fails, re-run with `--issue N`. |

## After it exists

Print the number and the URL, say which column it landed in, and **stop**. Do not
start work, and do not offer to — an offer is a question wearing a coat, and it
holds the session open for an answer. If the user wants it worked now, that is
`/task <number>`, which they can run themselves or say in the same breath.

## Layout

Nothing executable lives here. The plumbing is `task_gh.py create` / `task_gl.py
create` in the **task** skill — plus `create --parent` and `subissue` for the phase
shape above — so board discovery, the machine-local board-id cache, the stage aliases,
reference parsing and the sub-issue mutations have exactly one implementation. Run those
scripts' `selftest` after touching either.
