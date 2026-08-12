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

## Out of scope

No cron, no polling for new cards, no scraping TODOs out of code, no Google Keep
import. The handful of live Keep notes move over by hand.

## Known gap

`~/.claude/skills/` is not version controlled, so this directory does not reach
the second laptop by itself. It needs a dotfiles repo or a manual clone.
`~/.config/task-skill/config.json` is a machine-local cache and must not be
synced.
