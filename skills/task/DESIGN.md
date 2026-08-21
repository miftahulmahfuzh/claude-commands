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
