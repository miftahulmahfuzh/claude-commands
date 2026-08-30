---
name: task
description: Use when the user names a task card to work on — "/task 14", "fetch task 14", "task daily-words#14", "/task 7" in a GitLab repo, a pasted issue URL, "what's open?", "pick up that card again" — or when work finishes and a card needs moving. Drives task cards on GitHub Projects (personal repos) or GitLab Issues (work repos): claims the card by moving it to In Progress as soon as it is fetched, reads it and every comment, designs it without asking, writes or mints the implementation plan, links it back onto the card, and moves it to Completed only once the work is verified. On GitHub the work happens in a fresh worktree branched off origin/main and the session lands its own pull request — running the repo's CI as the gate, resolving conflicts against parallel sessions, and merging without a human. Handles the reopen loop, where a card comes back with a bug report in a new comment. Runs unattended end to end: it designs and decides for itself, never asks for approval, and stops cleanly rather than waiting on an answer.
---

# Task

## Overview

One loop, two backends. A card is captured in a browser (or on a phone), fetched
here by id, designed, planned, built, and moved through **Open → In Progress
→ Completed** — then possibly back to Open when a bug turns up months later.

| | Personal repos | Work repos |
|---|---|---|
| Cards live in | GitHub Issues + a Projects board named `Tasks` | GitLab Issues on the self-hosted instance |
| Stage carried by | the board's **Status** field | labels for Open/In Progress; **Completed = the issue is closed** |
| Kanban view | one user-level Projects board, spanning repos | one board **per project**: 2 label columns + built-in Closed |
| Cross-project view | the same board | the **group issue list**, filtered by label |
| Helper | `task_gh.py` | `task_gl.py` |
| Development loop | this skill runs it, in a **worktree off `origin/main`**, and every card ends in a **pull request it merges itself** | this skill mints a TaskID and hands off to **`/do`** |
| A card with phases | GitHub **sub-issues**: one card per phase, the parent owning the branch and the PR | no sub-issues below Premium — the phases are flat TaskIDs in `todos.md` |
| `Completed` means | the linked PR is **merged** | the issue is **closed** |
| Who merges | **the session**, gated on the repo's CI (step 6b) | `/do`, on its own branch rules |

**Core principle: the board records what happened, and it is never ahead of
reality.** A card sits in `In Progress` only while it is genuinely being worked,
and reaches `Completed` only after the repo's own gate has actually passed. Never
move a card on the strength of "the code is written".

On GitHub that bar is mechanical rather than remembered, which is what lets the
loop close itself: the session merges its own pull request (step 6b), and
`finish` refuses to complete a card unless GitHub itself reports a **merged**
linked PR. **There is no approval step anywhere in this loop** — no plan sign-off,
no "does this look right?", no menu of options. See **Autonomy** below; it is the
rule the rest of this file is written against.

**This skill works cards; it does not create them.** Capturing a *new* card is
`/create-task`, which opens the issue, adds it to the board and writes the Open
stage in one command — three operations, because `gh issue create` alone leaves an
issue no column ever shows. Its plumbing is `task_gh.py create` / `task_gl.py
create`, and it lives here so board discovery and the board-id cache stay single.

## A card with phases

A card captured from a `/analyze` plan set is a **parent** with one **sub-issue per phase** (see
`create-task`). Sub-issues are real issues with real numbers, so nothing new is needed to address
one: `/task 13` fetches phase 1 exactly like any other card. What *is* different is ownership,
and it is one rule:

> **The parent owns the worktree, the branch and the pull request. A phase owns a commit.**

That is not a convention, it is forced: phase 2's plan quotes the tree as it looks *after* phase
1, and phase 1 is not on `origin/main` yet. A phase card that cut its own branch off the base
would be implementing a plan against code that does not exist. So:

| Run on | What happens |
|---|---|
| **the parent** | drive every phase in order, in one worktree, committing per phase, and open **one** pull request for the plan set. This is `/implement --all` reached from the board. |
| **a phase** | claim it, work in the **parent's** worktree, commit, complete the phase on that commit — and leave the PR to the parent |

`resolve` answers which one you are holding without a second call: `parent` (with its plan block,
so the branch and the plan index are right there), `children`, `position`, `blockedBy`, and
`ownsPullRequest`. Read them before anything else — a phase session that skips this is the one
failure mode this shape introduces.

**`blockedBy` sees siblings only.** It is computed from the parent's sub-issue order, so it
cannot know that phase 3 under one parent depends on phase 1 under another — which is exactly
what happens when a plan set is split across two parent cards, one per `R`. The plan index's
**Depends on** column is the authority for order across parents; read it, and treat a
cross-parent prerequisite the same way as a sibling one.

**An earlier phase that is not done is not a stop.** `blockedBy` names it; work those phases
first, in order, then the one that was asked for. That is not scope creep — the phases share one
branch and one gate, and the requested phase cannot even be verified until its prerequisites are
in the tree. Say in the terminal which extra phases you picked up and why, then keep going.

Two consequences that are easy to get wrong:

- **A completed phase closes its own issue**, and nothing else would: `Closes #N` sits on the
  *parent's* pull request and closes the parent alone. `finish --child-of` therefore writes
  Completed and then closes, because GitHub's own sub-issue progress counts **closed**
  sub-issues — leave a phase open and the parent card reads `0 of 2` with both phases green on
  the board. The board's Status still leads when the two disagree (`child_done` reads Status
  first, issue state second): a card dragged back to Open is open work whatever its state says.
- **The parent completes last, on the merge.** If its PR merges while a phase still reads In
  Progress, the board is lying about code that is in `main`; `complete_card` reports those under
  `openChildren` so they can be swept. Complete each phase as it lands and the list stays empty.

## Autonomy: the loop never waits for a human

A card is handed to this loop to be **finished**, not to be discussed. From
`/task 14` to a merged pull request the session decides everything itself: which
approach, which trade-off, what the ambiguous sentence on the card meant, how to
resolve the conflict, whether the gate passed. It is written to run at 1am with
nobody awake, because that is when it runs.

The rule that makes that true:

> **Never end a turn with a question the loop needs answered to continue.**

Not "ask sparingly" — never. A question at 1:05 does not cost a round trip, it
costs the whole night: the session sits idle until morning, the worktree stays
open, the card still reads In Progress, and nothing got built. The arithmetic is
one-sided, and it is the whole reason this section exists:

| | What it costs |
|---|---|
| A decision that turns out wrong | one comment on the card, one reopen, one more round — which this loop already handles by design |
| A question asked into an empty room | every hour until someone answers, and no work at all |

So a call that is 70% right and **written down** beats a question that would have
been 100% right and goes unanswered. Decide, record why, keep going. The plan
file and the card's comments are where the reasoning goes: they are the record
that replaces the conversation, and they are what makes a wrong call cheap to
correct later.

Concretely, inside this loop:

- **Do not invoke the `brainstorming` skill.** Its protocol — one question at a
  time, a check-in after every design section — is right when a human is sitting
  there and fatal here. Step 4 reaches the same place alone. This overrides any
  general instruction to brainstorm before creative work; that instruction is
  about *not skipping the design*, and step 4 does not skip it.
- **Do not use `AskUserQuestion`,** and do not end a message with "does this look
  right?", "shall I proceed?", or a list of options for someone to pick from.
- **Do not ask permission for what the loop already says to do** — claiming the
  card, cutting the worktree, writing the plan, committing, opening the PR,
  running the gate, merging it. Running `/task` *is* the authorisation for all of
  it.

The user can interrupt at any moment, and that is their steering: always
available, always obeyed. What is removed is the loop's *requirement* for it.

### Stopping is allowed; blocking is not

The two are different and only one is permitted. A **stop** ends the session
cleanly: the card is left in a truthful stage, the reason is posted as a comment
on the card and printed in the terminal, and the work on disk survives. A
**block** is a live session holding an unanswered question, building nothing.

There are exactly five stops. Everything not on this list gets decided:

1. **The card cannot be placed** — a bare id with no repo to read it against, or
   a card whose repo is not this directory (step 2). A plan file written into the
   wrong project is worse than an error message, and `worktree`/`pr` refuse it
   anyway.
2. **A conflict whose only resolution drops the other card's behaviour** — the
   floor in step 6b. `land --abort-conflict` comments on both cards.
3. **The gate fails on something outside this card's diff**, and three attempts
   at fixing it have not moved it. A failure *inside* the diff is not a stop, it
   is the work.
4. **`land --after-gate` above attempt 3** — the tool refuses on purpose rather
   than loop, and that refusal is respected.
5. **Missing tooling or credentials** — `doctor` reports no `gh`, no token, no
   board. No decision changes that.

Every stop ends with the card correct: back to `Open` if nothing was built, left
`In Progress` with a comment if work is parked mid-flight, and never `Completed`.

## Picking the backend

Read `git remote get-url origin` in the current directory:

- host is `github.com` → `task_gh.py`
- anything else → `task_gl.py` (it reads `GITLAB_HOST` from
  `~/.config/task-skill/gitlab`)

If the current directory is not a repo, take the project **from the reference
itself** — `owner/repo#14`, `group/project#7` and issue URLs all carry it, and a
reference that names its project is not a guess. Only a bare number outside any
repo is genuinely unplaceable, and that is stop 1: say so and end the session.
Both helpers take the project explicitly —
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
python3 $S/session.py rename task-<number>   # this window is now task-17
```

**Move the card to In Progress immediately, as part of fetching it** — not later.
Running `/task <id>` *is* picking the card up, and the board's job is to say what
is being worked on right now; a card that stays in Open while a session is
actively designing it makes the board lie to anyone else looking.

Two consequences to honour rather than ignore:

- **If the session ends without proceeding** — the plan is rejected, the idea
  turns out to be wrong, the user changes direction — **move it back to Open
  before finishing.** Leaving it In Progress is the failure mode this timing
  introduces, and it is yours to prevent.
- It is idempotent, so a card already In Progress reports `changed: false`. Bare
  `/task` with no id is a listing and claims nothing.

**Rename the session in the same breath**, to `task-<the number that was asked for>`.
Five open terminals all called `jmtarot-8f`, `jmtarot-d4` say which repo and not which
card, so the right window is found by reading scrollback and `/resume` a week later
offers a row of near-identical titles. The number is the one label that separates them,
and it is known the moment the card resolves. `session.py rename` is the same rename
`/rename` performs — it reaches the running process over the session's own socket, so
the tab title, the `/resume` row and the name peers address all follow together.

Two rules: use **the card that was asked for**, even when `blockedBy` sends you through
earlier phases first — the session is named for its errand, not its current file — and
**never let it stop anything.** It cannot fail by design (no socket, no token, a session
started some other way → `renamed: false` and a reason), and a card is not worth losing
over the name of a window.

`<ref>` is `14`, `owner/repo#14`, `group/project#7`, an issue URL, and on GitHub
also a `PVTI_…` item id or `draft:<part of the title>`.

**On GitHub, read the plan-set fields in the same breath as the body.** `resolve` returns
`parent`, `children`, `position`, `blockedBy` and `ownsPullRequest`; a non-null `parent` means
this card is one phase of a plan set and steps 5a and 7 change shape. See **A card with phases**
above — do not reach step 5 before knowing which one you are holding.

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
Design only the delta — do not re-derive the original design.

### 4. Design it alone

**Do not invoke the brainstorming skill here** — see Autonomy. Its interactive
protocol is the single largest source of overnight stalls in this loop. What it
*produces* is still wanted in full; what changes is that the session produces it
by itself and writes it down instead of asking for it.

The card's body and comments are starting context, not a spec — the user wrote it
in a hurry. Filling the gaps is the job, not a reason to stop.

**a. Buy the decision with evidence instead of with a question.** Nearly every
question worth asking is already answered somewhere in the repo: read the code
the card touches, the tests around it, the neighbouring feature that solved the
same shape of problem, the last few commits in that area. A choice made from what
the repo already does is not a guess. Spend real effort here — this is the effort
that the round trip to a human used to buy.

**b. Write 2–3 approaches down and score them**, against criteria that come from
the repo rather than from taste:

| Criterion | The question it answers |
|---|---|
| Convention | does it look like what this repo already does? |
| Scope | is it the smallest change that fully satisfies the card? |
| Verifiability | can the gate in step 6b actually prove it works? |
| Reversibility | if it is wrong, is it one commit to undo? |

Pick the winner outright. **Keep the losers** — they go into the plan file with
one line each on why they lost. That record is the reviewable artefact the
conversation used to produce, and without it an unattended decision is
indistinguishable from a coin flip.

**c. Resolve ambiguity toward the narrowest reading that fully satisfies the
words on the card.** Do not widen scope to cover an interpretation the user did
not write, and do not invent requirements to make the design tidier. When two
readings genuinely diverge, build the narrow one and **say on the card, in the
step 5c comment, what the other reading was and why it lost** — one sentence. If
the user wanted the other one they comment, and the reopen loop is already built
for exactly that. One extra round is a cheap price against a night spent idle.

**d. State the decision in the terminal in a few lines, then keep moving.** A
statement is not a question: do not follow it with "sound good?" and do not pause
after it.

### 5. Once the design settles: cut the worktree, then two writes and no prompt

There is nothing to approve. The moment step 4 has a winner, do all of this. The
stage was already claimed in step 1, so what remains is the workspace, the plan
and its link.

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

**A phase card does not cut a worktree.** `resolve` gave you `parent`; its plan block names the
plan index, and the plan index names the branch and the worktree. `cd` there and work in it. If
the worktree is gone (another machine, or it was retired), recreate it from the parent:
`task_gh.py worktree <parent> --branch <the plan index's branch>`. Branching a phase off
`origin/main` is the one move that cannot be recovered from by re-running anything.

On **GitLab** there is no worktree step — `/do` owns branching there, and creates
one only for HARD tasks.

**A phase card already has its plan** — `.workflows/plan/<slug>/phase-{N}.md`, written and
reconciled by `/analyze`, linked from the card body. **Adopt it; never write a second one.** Step
4's design work was already done by the planner and the reconciler, and a plan you mint beside it
is the two-provenances problem this whole workflow exists to prevent. If the code has drifted from
what the plan quotes: small drift → follow the intent and note it in the card comment; large drift
→ stop and say the plan set needs re-running through `/analyze`.

**b. Write or mint the plan.** Detect the repo's own convention:

| Repo looks like | Plan path | Label |
|---|---|---|
| has `.workflows/todos.md` | `.workflows/plan/<TaskID>.md` | the TaskID |
| `plans/F<N>-*.md` exists | `plans/F<N+1>-<slug>.md` | `F<N+1>` |
| otherwise | `docs/plans/<YYYY-MM-DD>-<slug>.md` | the date |

The plan file carries step 4's output, not just the steps: the approaches that
lost and why, and the ambiguity call from 4c. It is the audit trail for a design
nobody was asked about, and it is what a reviewer reads instead of a chat log.

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
pull requests* column. Then land it yourself — step 6b.

### 6b. Land it: the session merges its own pull request

No human clicks merge. `land` does the git and the API; you do the two things that
are judgement — resolving a conflict, and reading a failed gate.

```bash
python3 $S/task_gh.py land 14            # sync with origin/main, then print the gate
```

It refuses a dirty tree, refuses to run from the base branch, merges
`origin/main` **into the task branch** (never the reverse — an unverified `main`
is where everyone else branches from), and then prints one of two things:

| Exit | Phase | What it means |
|---|---|---|
| 0 | `gate` | Merged clean. `commands` is the gate — run it. |
| 2 | `conflict` | `conflicts` lists the files, `otherCards` names the card you collided with. Resolve, commit, continue. |

**The gate is the repo's own, read out of `.github/workflows/*.yml`** — every
`run:` step of every push/pull_request job, in order, with the job's `env`. On
`run-insights` that is 14 commands including seven bespoke guards; a hardcoded
`npm test` would have waved all seven through. Run them in the worktree, in
order, and **read the output** — this gate is the only thing standing where the
merge click used to be.

A repo with **no CI** reports `gate: none` and `land` refuses: no gate means
nothing would check an auto-resolved conflict. `--no-gate` exists and has to be
typed on purpose — and since nobody is awake to type it, the session earns it
instead, down a ladder whose rungs are not skipped:

1. **Derive a gate from the repo itself** — `package.json` scripts (`test`,
   `typecheck`, `lint`, `build`), a `Makefile` target, `pytest`, `cargo test`,
   `go test ./...`. Run every one that exists, in that order, and read the
   output. That is the same standard CI would have applied; it is just discovered
   by hand instead of parsed out of a workflow file.
2. **Something ran and passed** → land with `--no-gate` on both halves
   (`land 14 --no-gate`, then `land 14 --after-gate --no-gate`, since the check
   sits before the split), and **name the commands that passed** in the card
   comment. "No CI" is not the same as "unverified", and the card should not blur
   them.
3. **Nothing exists to run at all** → still land, and make the card comment say
   plainly that the repo has no gate and the change went in unverified. Do not
   let it read like a pass.

A merge whose confidence is written down is recoverable. A card sitting In
Progress until morning because `land` said no is a night thrown away.

Then, and only then:

```bash
python3 $S/task_gh.py land 14 --after-gate
```

which pushes, merges the PR (`--merge`, one commit per card), sets Completed and
posts the note naming the merge commit, then deletes the remote branch. It refuses
a draft PR.

The order there is deliberate: the merge is the only step allowed to fail the
command. The card is completed next, and the branch is tidied **last and
best-effort** (`remoteBranchDeleted` says whether it went), because a leftover
branch is not worth a landing that merged the code and left the card saying
In Progress. `gh pr merge --delete-branch` is not used at all — it checks out the
default branch first, which fails inside a worktree where `main` is checked out
elsewhere, and it would fail *after* merging.

**It can send you back to the gate, and that is not a failure.** If `origin/main`
moved while the gate was running — the other session landed first — `--after-gate`
merges the new base in and reprints the gate with `regate: true`, *even when the
merge was textually clean*. That round is the only one that ever sees both changes
together, and a clean merge of two unrelated edits is exactly where a semantic
break hides. Re-run the gate, then `--after-gate --attempt 2`. Above attempt 3 it
refuses and tells you to stop rather than loop.

The same applies if GitHub calls the PR conflicting, **or if `gh` refuses the
merge outright** — losing the race is the expected half of racing, so it is
reported as `regate`, not as an error. (GitHub computes `mergeable` lazily and
often answers `UNKNOWN`, so `gh` is the authority and its refusal is read rather
than trusted in advance.)

There is no lock and no queue. Two sessions landing at once is fine: the first
wins, the second is sent round again, and going round is work that had to happen
anyway.

#### The conflict rule

On exit 2, classify the region first — the classification picks the resolution,
not taste:

| Conflict region | Resolution |
|---|---|
| Append-only list (todos, CHANGELOG, plan block, README index, a catalog) | **Keep both sides**, theirs then ours |
| Disjoint edits git flagged for adjacency | Keep both hunks |
| Same function, both sides changed behaviour | **Compose both behaviours** |
| Lockfile (`package-lock.json`) | Discard both, regenerate: `npm install --package-lock-only` |
| Generated or derived file | Discard both, re-run the generator |

Then the floor, which is the one thing the gate cannot enforce for itself:

> **A resolution that removes the other card's behaviour is not a resolution.**
> If the only way to make the tree build is to delete what the other session
> added, stop. Do not simplify your way past it.

```bash
python3 $S/task_gh.py land 14 --abort-conflict \
  --reason "Task 6 debounces onPick; task 8 splits the same handler. Composing them
            needs a decision about which fires on a zoom tap."
```

That comments on **both** cards, naming the other, leaves the card In Progress and
leaves the merge resolved-but-unpushed so the work survives.

This is stop 2, and it is a stop rather than a question: print what happened, say
which decision a human owes, and **end the turn**. Do not sit waiting for an
answer that is not coming until morning.

Why the floor is a rule and not a judgement call: the gate catches a resolution
that **breaks** and is blind to one that **drops**. Task 8's session, meeting task
6's fix in the same handler, can take its own side and watch all 14 gate commands
pass while task 6 is silently un-fixed — with its card reading Completed and its
PR reading merged. Nothing downstream ever catches that.

On a **work repo with `.workflows/todos.md`**, none of the above applies. That
repo already has a task system — 33 todos.md files and a `/do` command orchestrating five subagents
— and this skill is its front door, not a replacement. Mint the TaskID into the
right package's todos.md and hand off:

```bash
python3 $S/todos.py mint MN --priority P1 --letter A   # next free canonical id
python3 $S/todos.py validate                           # before and after
```

Then run `/do <TaskID>` — hand off directly, without pausing to confirm the mint
or the TaskID. Its completion-handler updates todos.md; you mirror that onto the
GitLab card in step 7.

### 7. Completed — on evidence, not on a claim

On **GitHub this already happened**: `land --after-gate` set Completed itself,
because by then all three conditions were mechanically true — the gate passed, the
PR is merged, and GitHub says so. There is nothing left to do but report.

**A phase card completes on its commit, not on a merge** — the parent owns the pull request, so
there is nothing merged to point at until the whole plan set lands:

```bash
python3 $S/task_gh.py finish 13 --child-of 12 --commit <sha>
```

It refuses a card that is not a sub-issue of the parent it names, a commit that does not exist,
a commit that is not on the branch you are standing on, and a commit already on the base. Those
four checks are what replace the merged-PR requirement — do not reach for `--allow-unmerged`
here, which asserts nothing at all. Run it as each phase lands, so the parent's own completion
never has to sweep an `openChildren` list.

It then **closes the phase's issue**, which is the last thing a phase card needs and the only
thing no merge will do for it — see **A card with phases** above. So a finished phase is
Completed *and* closed while the parent is still open and still holds the pull request; that is
the correct shape, not a contradiction.

Once the plan set has landed, `--child-of` no longer applies — it refuses a commit that is
already on the base, on purpose. A phase left unswept until after the merge is completed with
the ordinary `finish 14 --allow-unmerged --note "Landed in #<pr> (<sha>) via parent #<n>."`,
which is the one honest use of that flag: the code is in `main`, it just went in under the
parent's PR rather than a PR of its own.

`finish` remains for the paths that skipped `land`:

```bash
# GitHub — a card landed by hand, or one that genuinely has no PR
python3 $S/task_gh.py finish 14 --note "Verified: <commands that passed>."

# GitLab
python3 $S/task_gl.py comment <ref> "Done in <sha>. Verified: <commands that passed>."
python3 $S/task_gl.py status <ref> Completed
```

`finish` asks GitHub whether a linked PR is merged, and **exits non-zero if none
is** — so a card cannot reach Completed while its code is still in review.
`--allow-unmerged` exists for a card that genuinely has no PR; using it to skip a
review is defeating the check. `land --after-gate` calls the same function, so
the rule is one implementation, not two.

Use the **verification-before-completion** skill: do not claim a pass you have not
seen. The gate's output is that evidence — quote what passed.

On GitLab, `status <ref> Completed` **closes the issue** as well as labelling it,
which is what moves it into the Closed column and out of the project's issue
list. Reopening later (`status <ref> Open`) reopens the issue too.

If the gate fails, that is the work, not a handoff: read the failure, fix it in
the worktree, re-run the gate. Only a failure that is **outside this card's diff**
and unmoved after three attempts is stop 3 — comment on the card with the failing
command and its output, leave the card `In Progress`, and end. Nothing has been
pushed or merged at that point, so there is nothing to undo. A card in the wrong
column is the one failure this system cannot absorb, because the user trusts the
board instead of re-reading the code.

### 8. Retire the worktree (GitHub)

`land --after-gate` already deleted the **remote** branch. What is left is the
local worktree and its branch, which is dead weight:

```bash
python3 $S/task_gh.py worktree 14 --remove       # --force to discard dirty state
```

It refuses to remove a dirty worktree without `--force`, which is the correct
default — unpushed work is easier to lose here than anywhere else in the loop.
Once the PR is merged the branch is dead and the code is in `main`, so retire it
by default; keep the tree only if the user already said in this session that they
want it. Do not ask.

## Why the PR must say `Closes #14`

The board's **Linked pull requests** column reads GitHub's issue↔PR *link*, and
GitHub creates one from exactly two things: a closing keyword in the PR body, or
the PR's Development sidebar. A bare `#14` is a **mention**, and mentions leave
the column empty — the card then looks unworked next to a PR nobody can find from
the board. So `pr` writes `Closes #14` itself and repairs the body if the keyword
is missing, rather than trusting whatever text it was handed.

The keyword's other effect is intended: **merging the PR closes the issue**, and
that closure is allowed to stand. `finish` records Completed and leaves it closed —
and closes the issue itself when no merge did, which is every phase card, since the
keyword sits on the parent's PR and closes the parent alone. Only the *live* stages
reopen; see the closing section for why that asymmetry is the whole rule.

`links <ref>` answers "is the board actually showing it?" from two sources — the
issue's links and the board field itself — and names which one answered. The
board field can lag the link by a few seconds, so an empty field beside a live
link is a refresh, not a bug.

## Closing: Completed means closed, and the reason is measured

**One rule on both backends: the live stages open the issue, `Completed` closes
it.** `Open` and `In Progress` reopen a closed card, because "nobody has picked
this up" and "being worked" cannot be true of a finished issue. `Completed` does
the reverse. `ensure_issue_open` and `ensure_issue_closed` hold the two halves.

| Stage written | The issue is… |
|---|---|
| `Open` | reopened — nobody can pick up a finished card |
| `In Progress` | reopened — "being worked" and "closed" cannot both be true |
| `Completed` | **closed** — by the merge if there was one, by the stage write if not |

That took two reversals to reach, both on evidence, and both are worth knowing
because each undid a rule that sounded right:

**First: stop reopening.** The original rule reopened the issue on *every* stage
write, to dodge Projects' **auto-archive** workflow — a closed item disappears off
the board, which would have broken the reopen loop. **Measured on this board: six
closed issues sit in `Done` and every one is still visible.** Auto-archive is not
enabled, so the hazard the rule existed for does not exist, and all the rule
produced was a column of cards that were Done-but-open forever, fighting GitHub's
own semantics on every command.

**Second: close the ones no merge closes.** Leaving that at "don't reopen" quietly
assumed every completed card had a merged PR carrying `Closes #14` to close it for
free. Two do not, and both were stranding cards: a **phase**, whose closing keyword
lives on the *parent's* PR, and `finish --allow-unmerged`, the card that has no PR
at all. **Measured on `jmtarot`: #13 Done and closed on its merge; #14 and #15
built, verified, Completed — both still open, and the parent's sub-issue progress
reading `0 of 2`,** because GitHub counts *closed* sub-issues and nothing on the
board can tell it otherwise. So `complete_card` closes what it completes, last and
best-effort — the Status field is the authority and is already written, so a failed
close is reported (`issue.closed`) and never costs the card its stage.

When a card resurfaces months later, `reopen <ref>` puts it back — that is exactly
what the subcommand is for — and the next `/task <id>` picks it up normally.

If you ever turn auto-archive **on**, the first reversal flips back: completed
cards would start vanishing from the board, and the reopen rule would have to
return. `doctor` reports what it can see; the setting itself is browser-only.

**GitLab reached the same rule first, from a different direction.** `task_gl.py
status <ref> Completed` sets the label **and** closes the issue, in one PUT;
`Open` and `In Progress` reopen it. This reverses what this file said earlier, on
evidence:

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
so reopening it is the first move and the session makes it: `reopen <ref>`, then
`Open`. Nobody needs to be asked whether to reopen a card someone just filed a bug
on. Moving it to `Open` or `In Progress` reopens it anyway, so a card
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
session.py    rename this Claude Code session to `task-<n>`, over its own socket —
              backend-agnostic, and unable to fail the caller
```

Every one has a `selftest` (`python3 taskcore.py` for the shared half) that runs
offline with no token and no network. Run all five after touching any of them —
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
