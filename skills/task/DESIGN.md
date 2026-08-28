# Task tracking integrated with Claude Code — design

**Date:** 2026-08-12
**Status:** built; awaiting the one-time `gh` install and board creation.

Filed here rather than in `daily-words/docs/plans/` on purpose: the skill is
cross-project, and a note about a global tool sitting inside one product repo is
exactly the kind of misfiling that confuses a later session reading that repo's
authority order.

## The problem

Ideas, bugs and feature changes were being written into Google Keep, where Claude
Code cannot see them and where they have no stage, no history and no link to the
plan file or the commits that resolved them. The wanted loop:

1. Describe a feature in a card in the browser (or on a phone) — get a task id.
2. New session: fetch that id, brainstorm it, write the plan, record the plan's
   path on the card, move the card to In Progress, build it.
3. Move the card to Completed when done.
4. Months later, hit a bug in the app: comment on the card, move it back to Open,
   fetch it again, repeat.

## Decision: GitHub Issues + a Projects v2 board, not a new tool

Surveyed: Linear's free tier with its official hosted MCP server
(`mcp.linear.app/mcp`, works on the free plan, best mobile capture, but the notes
live on Linear's servers); [Backlog.md](https://github.com/MrLesk/Backlog.md)
(MIT, markdown tasks committed to the repo, real MCP server — genuinely the most
agent-native option, but its web UI binds `127.0.0.1` and it is per-repo, so it
fails both the phone-capture and cross-project tests); and several small
`kanban-mcp` projects, which are aimed at *watching agents work* rather than at
being the place a 2am idea goes.

**Writing a new tracker was rejected.** Nothing in the requirement is unmet by
GitHub Issues, and the only genuinely custom part — the workflow — is one skill
file. That also makes the backend choice reversible: the loop in `SKILL.md` would
survive a swap to Linear with only `task_gh.py` replaced.

The deciding criterion was **where capture happens**. Since the ideas currently go
into Keep, capture is often on a phone, away from the laptop — which eliminates
any board that only listens on localhost.

## Shape

- Issues live in **the project repo they belong to**, so the card, the plan file
  and the commits that close it are in one place.
- One **user-level Projects board `Tasks`** aggregates every repo into a single
  Open / In Progress / Completed view via the built-in **Status** field.
- Capture happens **on the board**, not in a repo: `+` in the Open column makes
  either a real issue or a **draft item** with no repo at all. The draft is the
  Keep note — a title and a body, written and forgotten, promoted to an issue in
  the right repo when work starts.
- **No labels.** Status carries the stage; the repo column says which project.

Rejected: one central `tasks` repo for everything. Simpler capture, but the card
is then never in the same repo as the plan or the commits, and the trail is by
reference only.

## Transitions

`In Progress` is automatic the moment the plan is approved, because approving the
plan *is* the decision to start; a confirmation there would become reflexive.
`Completed` is never automatic — it needs the user to say the work is done *and*
verification to have actually passed. Rejected: confirming every transition (two
extra round trips per task), and automating both ends (a card lands in Completed
while the user still considers the work unfinished).
*Revised — see the 2026-08-22 amendment: there is no plan approval any more, and
`Completed` is automatic once the repo's gate passes and GitHub reports a merged
PR. The bar moved from a human's word to the repo's own, which is stricter.*

## Two things that would have failed quietly

**Completed must not close the issue.** GitHub Projects ships an auto-archive
workflow on closed items, so a closed issue drops off the board — and the reopen
loop would then be fighting the board's own automation on every bug. `task_gh.py`
has no `close` subcommand, so this is structural rather than remembered.
*Revised — see the 2026-08-21 amendment: a merged pull request does close the
issue, so the rule became never* left *closed.*

**The plan link goes in the issue body, not a comment.** A comment gets buried
under bug reports; the body is what the next session reads first. It is a
marker-delimited, append-only block (`<!-- task:plans -->`), so round two adds a
line rather than overwriting round one's.

## Failures made loud

Read `body` **and every comment in order** — on a returning card the body is the
original idea and the newest comment is the bug report. Beyond that, `task_gh.py`
stops with one actionable sentence on: `gh` absent, missing `project` scope, no
board or two boards with one title, no Status field, Status options that do not
cover the three stages, a bare issue number ambiguous across repos, and a card
whose repo is not the current directory.

Stage names are resolved against the board's **real** Status options with aliases
for GitHub's shipped defaults, never assumed.

## Amendment, 2026-08-21: worktree, pull request, linked column

Three changes to the GitHub half, all driven by one requirement — the `Tasks`
board's **Linked pull requests** column should show the work.

1. **Every card is built in a worktree off `origin/main`**, at
   `~/.worktrees/<repo>/task-<n>-<slug>`. Outside the repo on purpose: nothing to
   add to a `.gitignore`, no way to commit a worktree by accident, one place to
   prune. It is cut *before* the plan file is written, so the plan travels in the
   pull request rather than landing on `main` alone.
2. **Every card ends in a pull request**, opened by `task_gh.py pr`.
3. **The PR body must carry a closing keyword.** GitHub only creates the
   issue↔PR link the board column reads from a keyword (`Closes #14`) or the
   Development sidebar; a bare `#14` is a mention and leaves the column empty.
   `pr` therefore writes the keyword itself and reads the link back afterwards
   instead of assuming it took.

**This forces a revision of "Completed must not close the issue" above.** The
keyword means merging closes the issue, and that cannot be avoided while keeping
the column populated — the alternative (`Refs #14`) is not a link at all. So the
rule becomes **never *left* closed**: `status` and `finish` reopen the issue as
part of writing a stage, in one function, so auto-archive never sees a closed
item and the reopen loop keeps working. Reopening does not unlink the PR, so the
column survives it.

`finish` also makes Completed evidence-based rather than trusted: it asks GitHub
for a **merged** linked PR and exits non-zero if there is none.

Rejected: adding the same to `task_gl.py`. GitLab work goes through `/do`, which
already owns branching there, and merge requests are not what the GitLab board is
being asked to show.

## Out of scope

No cron, no polling for new cards, no scraping TODOs out of code, no Google Keep
import. The handful of live Keep notes move over by hand.

## Known gap

`~/.claude/skills/` is not version controlled, so this directory does not reach
the second laptop by itself. It needs a dotfiles repo or a manual clone.
`~/.config/task-skill/config.json` is a machine-local cache and must not be
synced.

## Amendment, 2026-08-21: autonomous landing

Driven by a real collision: two sessions in two worktrees, tasks 6 and 8 of
`run-insights`, both branched off the same `origin/main`. Whichever opened its
pull request second was guaranteed to conflict, and the loop's last line —
*"Give the user the PR URL: merging is theirs"* — made that a human's problem
twice over: once to merge, once to resolve.

So the loop lands its own work. `task_gh.py land` is the new step 6b, and the
merge click is gone.

**What replaces the click is the repo's own gate, not trust.** `land` reads
`.github/workflows/*.yml` and emits every `run:` step of every job triggered by
push or pull_request, in order, with the job's `env:`. On `run-insights` that is
`npm ci`, four bespoke guards, `typecheck`, `test`, `build` — a hardcoded
`npm test` would have waved three of those through. A repo with no CI reports
`gate: none` and `land` **refuses**: no gate means no autonomous landing, and
`--no-gate` has to be typed on purpose.

**The gate runs on the resolved tree, before the push.** A conflict resolution
that was never verified is a guess, and this is the one place a guess reaches
`main` unseen.

**Conflicts are resolved by the session, under a rule with a floor.** The rule is
in SKILL.md as a table (append-only regions keep both sides; lockfiles are
regenerated, not hand-merged; same-function edits get both behaviours composed).
The floor is the only thing a verification pass cannot enforce for itself:

> A resolution that removes the other card's behaviour is not a resolution.

Because verification catches a resolution that *breaks* and is blind to one that
*drops*. Task 8's session, meeting task 6's fix in the same handler, can take its
own side and watch every test pass while task 6 is silently un-fixed with its card
reading Completed. `land --abort-conflict` exists for exactly that: it comments on
**both** cards, naming the other, and leaves the branch merged-but-unpushed so the
resolution work survives being handed back.

`land` splits at the gate — sync-and-resolve, then `--after-gate` for push, merge
and `finish` — because resolving a conflict and judging a test failure are model
work, and pushing and merging are not. Same division as `pr`.

**Rejected: a lock to serialise the two sessions.** Traced: both merge the same
base, both verify, both push, first one wins; the loser must merge the *new* main
and re-run its gate. A lock only decides who loses, and the loser does identical
work — so it buys nothing and adds a stale-lock failure mode. Instead
`--after-gate` re-checks `HEAD..origin/main` and sends the caller back to the gate
whenever main moved, **even when the merge was textually clean** — that is where
semantic conflicts live, and it is the only round that ever sees both changes
together.

Rejected: `--squash`. `run-insights` lands merge commits (`Merge pull request #5
from …`), one feature commit per card, and the tool should match the repo rather
than reformat its history.

Rejected, again, for `task_gl.py`: GitLab work goes through `/do`.

## Amendment, 2026-08-22: no human in the loop

The autonomous-landing amendment removed the merge click. It left one prompt
standing, and that prompt turned out to be the expensive one: **plan approval**.

The failure is not hypothetical and it is not about correctness. A session starts
at 1am, reads the card, designs the change, and at 1:05 asks *"does this look
right?"* — then holds the worktree open and builds nothing until someone wakes up
eight hours later and presses `y`, which is what they press essentially every
time. The approval was buying almost no information and costing a whole night's
work. The same shape appeared inside `brainstorming`, which this loop invoked at
step 4: one question at a time, plus a check-in after every design section.

So the loop now designs and decides for itself. `SKILL.md` gained an **Autonomy**
section stating one rule — *never end a turn with a question the loop needs
answered to continue* — and step 4 became a written design pass that does not
invoke `brainstorming` at all.

**The design work is not what was cut.** Approaches, trade-offs, the reasoning:
all still required, and now written into the plan file (the losing approaches with
one line each on why they lost) instead of spoken into a chat. That record is
strictly more durable than the conversation it replaces — it survives into the
pull request, and it is what makes a wrong call reviewable after the fact.

**Ambiguity resolves to the narrowest reading that satisfies the card's words,**
and the alternative reading is named in a card comment. The arithmetic behind
that: a wrong call costs one comment and one reopen — machinery this loop already
has — while a question into an empty room costs every hour until morning. A
decision that is 70% right and recorded beats one that is 100% right and
unanswered.

**Stopping is kept; blocking is not.** The distinction is the whole design. A stop
ends the session with the card in a truthful stage, the reason commented on the
card, and the work on disk intact. A block is a live session with an unanswered
question in it. Five stops are enumerated in `SKILL.md` and everything else is
decided: an unplaceable card, the conflict floor (`--abort-conflict`), a gate
failing outside this card's diff after three attempts, `--after-gate` above
attempt 3, and missing tooling. Each one already existed; what changed is that
they are now the *only* ways out.

**A repo with no CI no longer dead-ends.** `land` still refuses without a gate,
correctly — but `--no-gate` was written to be typed by a human who is, by
construction, asleep. The skill now documents a ladder the session walks instead:
derive a gate from the repo (`package.json` scripts, `Makefile`, `pytest`,
`cargo test`, `go test`), run it, and land with `--no-gate` **naming what passed**
in the card comment. If literally nothing exists to run, it still lands and the
comment says plainly that the change went in unverified. Landing with the reason
for its confidence written down is recoverable; a card parked until morning is a
night thrown away.

This supersedes *"`Completed` is never automatic — it needs the user to say the
work is done"* in **Transitions** above. Completed is now automatic and
evidence-gated: `finish` demands a merged linked PR from GitHub itself, so the
condition it waits on is mechanical rather than conversational. Nothing about the
board-never-leads-reality rule changes — the bar moved from *a human's word* to
*the repo's gate*, which was always the stricter of the two.

`create-task` got the same treatment, one size smaller: a project it cannot name
from the reference, the working directory, or the session's own edits becomes a
**draft item** rather than a question. That fallback was already in the tool
(`--draft`, then `promote`); it simply was not written down as the answer to
"which project?".

**Rejected: a `--yes`/`--interactive` flag to keep both modes.** Two modes means
the model choosing between them, and it would choose to ask — the interactive path
always looks safer from inside a single turn, which is exactly the bias that
produced the 1am prompt. One mode, with five enumerated stops, is the only version
that behaves the same whether or not anyone is watching.

**Rejected: editing the `brainstorming` skill itself.** It lives in a plugin cache
(`~/.claude/plugins/cache/…`), is overwritten on every plugin update, and is right
for its own use case — a human at the keyboard exploring an idea. The override
belongs in the skill that knows it is running unattended.

## Amendment, 2026-08-28: a plan set on the board

**The measured failure.** One prompt read `/create-task 2 cards and /analyze …`.
The session produced exactly what both halves promised and no relationship
between them: cards #11 and #12 on the board, and a four-phase plan set in
`~/.worktrees/jmtarot/history-retry-and-soft-delete` with 20 inconsistencies
reconciled. Neither artifact referenced the other. Nothing was wrong with either
one; they were simply produced blind, because `create-task` is written to fire in
two seconds and never ask, and it fired before the only thing that knew the
decomposition had run.

**The fix is ordering and data flow, not new prose.** `/analyze` runs first and
the cards are shaped from the finished plan index. To make that mechanical rather
than a re-reading of the prose, `/analyze` now numbers the user's asks `R1…Rn` and
every phase declares which `R` it serves. This is the same move the **Interface
Contract** made for reconciliation: publish the one fact the next stage needs so
it does not have to re-derive everything.

**The two counts are not rivals.** "2 cards" is deliverables; "4 phases" is
execution units. Both are correct at different altitudes, so both survive: one
parent card per `R`, its phases as sub-issues, in phase order. When a phase serves
two `R`s it can be attached to neither, and that coupling is a real fact about the
work — one parent for the whole set, with the user's asks as bullets.

**Ownership is forced, not chosen.** This skill's per-card model is a fresh
worktree off `origin/main` and one merged PR per card. A plan set is one worktree,
one branch, phases in a required order, where phase 2's plan quotes the tree *as
it will look after phase 1*. A phase card cutting its own branch off the base
would implement against code that does not exist. So: **the parent owns the
worktree, the branch and the pull request; a phase owns a commit.**
`finish --child-of` swaps the merged-PR requirement for four checks — is it a
sub-issue of that parent, does the commit exist, is it on the branch you are
standing on, is it absent from the base — rather than dropping the requirement.
`--allow-unmerged` would have asserted nothing, for every card in the system.

**Rejected: `/task 11 --subtask 1`.** The original ask. Sub-issues are real issues
with real numbers, so `/task 13` already addresses a phase; a second addressing
scheme would have to be kept in sync with the first for nothing. Also rejected:
`11.2` as sugar, because `parse_ref` deliberately refuses `1.5` and that strictness
is worth more than the shorthand.

**Rejected: one PR per phase.** Either stacked (phase 2's PR targeting phase 1's
branch) or all targeting a long-lived integration branch. Both give finer review
granularity; both add a second merge order to get wrong, and neither is reviewable
by the one person who reviews nothing. One PR per plan set, one commit per phase.

**Rejected: cascading completion.** When the parent's PR merges, every phase's code
is in `main`, so completing the open ones looks free. It is not: a merge is not
evidence that a phase nobody completed was actually built, and writing Completed on
that guess is the exact failure this board cannot absorb. `complete_card` reports
them as `openChildren` instead.

**Rejected: refusing a phase whose predecessors are not done.** A refusal at 1am is
a night thrown away, and the phases share one branch and one gate — the requested
phase cannot be verified without its prerequisites in the tree anyway. So
`blockedBy` is reported and the loop works the prefix in order, saying which extra
phases it picked up.

**GitLab is out of scope, on evidence.** Sub-issues below Premium do not exist
(child issues are an Epic feature). There the phases are already flat TaskIDs in
`todos.md` and `/do` walks them, so the board gets one card carrying the plan index
and the phase list. `task_gl.py` gains no `--parent`.
