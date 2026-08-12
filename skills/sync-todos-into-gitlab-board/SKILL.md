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
python3 $S/sync_todos.py audit                                 # one card per TaskID?
python3 $S/sync_todos.py apply .workflows/todos.md --limit 10   # take it in bites
python3 $S/sync_todos.py apply .workflows/todos.md --yes        # allow a big create
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

Report `liveEntries`, `echoesIgnored`, `stageCounts`, `todosSectionConflicts` and
the create/update/unchanged split. If `nonCanonical` is non-empty, go back to
step 1. **Show the user the create count before applying** — that number is how
many permanent issues appear in a repo they may not be able to delete from.

### 3. Apply

```bash
python3 $S/sync_todos.py apply <file> [--include-completed] [--limit N] [--yes]
```

`apply` refuses above `--max-create` (default 10) unless `--yes` is passed, so a
large create is a decision rather than a side effect.

Then verify against the API rather than trusting the exit code: per-column issue
counts, and that no card carries two stage labels. **Run the subcommands too** —
a green `selftest` proved nothing about `audit`, which had a `NameError` on a line
the offline assertions never reach.

## todos.md is primary — and that spans two sections

**`/do` does not just tick the box; it MOVES the entry** out of `## Active Tasks`
into `## Completed Tasks`. So a task's current state lives in one of two places:

| Section | Means | Kind |
|---|---|---|
| `## Active Tasks` | unfinished | `active` |
| `## Completed Tasks` | finished — `/do` moved it here | `completed` |
| `## Recent Activity`, `## Summary`, `## Quick Stats` | what was true *then* | `log` |

`TodoFile.tasks()` returns one entry per TaskID across the first two, preferring
the active section, and drops ids that appear only in a log. **Reading only the
active section is the bug this replaced:** a task completed via `/do` disappeared
from the sync entirely, so nothing ever moved its card to Completed.

A task present in *both* an active and a completed section is reported as
`todosSectionConflicts` — `/do` moves rather than copies, so that is an
inconsistency, not a state. The active copy is preferred and the disagreement is
surfaced.

### The one exception

An unticked entry means "not finished", which is true both of work nobody has
started and of work a `/task` session is doing **right now**. todos.md cannot say
the difference: a `/task` claim writes to the board only.

So **when todos.md wants Open and the card is In Progress, the sync leaves it
alone.** Without that, every sync would drag a live session's card back to Open.
Everything else is corrected:

| todos.md | card | sync does |
|---|---|---|
| `[x]` | open (Open or In Progress) | label Completed **and close** (the `/do` case) |
| `[ ]` | closed | **reopen** and label Open (reopened task) |
| `[ ]` | open, In Progress | **nothing** — a live `/task` claim |
| `[x]` | closed but labelled `status::open` | fix the label |
| `[x]` | open but labelled `status::completed` | **close it** |
| any | two stage labels | → the wanted one (always drift) |

**Completed is carried by the issue state, so state is half the comparison.** A
card open-but-labelled-completed, or closed-but-labelled-open, is drift even
though one half already agrees — a bug the offline assertions caught after I first
compared labels alone.

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

## One TaskID, one card

todos.md TaskIDs are unique, so the board must never hold two cards for one id.
Identity is read from **two channels**:

1. the `P1-MN-A001 —` prefix in the issue **title**, which is what a human reads
   and what the board shows;
2. the `- TaskID:` line inside the `<!-- task:source -->` block in the body.

The second exists because the first is editable. Retitle a card in the browser and
drop the prefix, and a title-only match makes that card invisible to the next
run — which then creates a second one for the same task. **Verified:** a card
retitled to "someone renamed this card by hand" is still recognised by its body
marker, and the sync proposes restoring its title rather than creating a duplicate.

`index_cards` reports two failures of that mapping, and **`apply` refuses to write
while either exists** rather than compounding it:

- `duplicateCards` — one id held by two issues.
- `idConflicts` — one issue claiming two ids, e.g. a hand-edited title over a
  stale body. Identity is ambiguous there and picking one would be a guess.

```bash
python3 $S/sync_todos.py audit          # exit 0 if unique, 1 with the offenders
```

Fixing a duplicate needs a human: **a GitLab issue needs the Owner role to
delete**, so a Maintainer should close the extra card and clear its stage label
(which also takes it off a board with the closed column hidden). The skill will
not choose which of two cards is the real one.

**Verified on `ai/chatbot/agentic`:** 27 issues, 27 distinct TaskIDs, `unique:
true`; two cards deliberately given the same id made `audit` exit 1 and `apply`
refuse, naming both.

## Three more things that would go wrong quietly

- **Widening what counts as a task changes the blast radius — re-plan.** Moving
  from the active section alone to `tasks()` took the root file from 26 entries
  to **55**, because `## Completed Tasks` holds 29 genuinely distinct finished
  tasks rather than echoes of the active ones. The `apply` that followed created
  28 permanent cards in a shared repo with no warning. `apply` now refuses above
  `--max-create` (default 10) unless `--yes` is passed. Always re-run `plan`
  after anything that changes what the parser sees.
- **Bodies are not rewritten by default.** A human may add notes to a card, and
  clobbering them every run would make the sync hostile. The body is only
  written when the source marker is absent — or with `--refresh-bodies`, which
  *does* discard card notes and is therefore opt-in. That flag needs the real
  source path in the comparison: with an empty one, every card differs from
  itself and every run rewrites everything.
- **Completed cards are closed, and that is deliberate.** A GitLab label list
  shows open issues only, so a completed card left open sat in the project's
  issue list forever — the team saw 55 open issues, 44 of them finished. Closing
  drops that to 11 and puts the card in the board's built-in **Closed** column,
  which is why `board --ensure` keeps that column visible and creates only two
  label columns. `POST /issues` cannot set the state, so an already-finished task
  is created open and then closed: two calls, unavoidable.

## Verified state

`ai/chatbot/agentic`, `.workflows/todos.md`: **55 cards — 11 Open, 44
Completed** — from 55 tasks across both sections; re-run reports 55 unchanged;
every card carries exactly one stage label; `audit` reports 55 distinct TaskIDs
and `unique: true`.

The `/do` path is verified directly rather than argued: card #1 was moved back to
Open by hand while its todos.md entry read `[x]` under `## Completed Tasks`, and
the next sync moved it to Completed with
`{"from": "Open", "to": "Completed", "because": "checkbox"}`.

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
