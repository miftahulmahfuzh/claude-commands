---
description: Start a deliberately high-token-consumption ("token-maxxing") work session — auto-generate a menu of real-value ideas, pick the best one yourself, branch, roll, and merge to main when done.
argument-hint: "[optional theme, e.g. tests | docs | refactor | audit]"
---

# /token-maxxing

You are kicking off a **token-maxxing session**. Context: leadership wants higher
overall Claude token consumption, and the team wants a defensible record of real
engineering value to justify upgrading the company Claude subscription. So: burn tokens
generously, but bias hard toward **genuinely useful work** so every session is defensible.

**This command is fully automatic, end to end.** There is no menu presented for the user
to pick from, no "surprise me / reroll" prompt, and no scope-confirmation checkpoint —
you generate the candidate ideas, judge them, pick the best one, and go. The only
legitimate stop is the same bar `/do` and `/implement` use: an undecidable fork where
every branch is irreversible. Never stop to ask "which idea do you want?", "does this
scope look right?", or "should I merge this?" — decide, record the decision, and proceed.

Optional theme passed by the user: **$ARGUMENTS**
(If empty, ideas may span anything. If present — e.g. `tests`, `docs`, `refactor`,
`audit`, `teach` — bias selection toward that theme.)

## Do this, in order

### 1. Get the real date
Run `date +%F` in bash. Never guess the date. Call the result `<DATE>`.

### 2. Recall recent sessions (spawn a subagent)
Give the workflow memory so today doesn't repeat what we already finished, and so we can
choose to *continue* prior work.

Spawn a **fresh subagent** to read the most recent token-maxxing docs:
- List `docs/token_maxxing/*.md` (excluding `README.md`), sort by ISO filename **descending**,
  take the top **5**. If fewer exist, take what's there. If none exist, skip this step —
  everything is fresh.
- The subagent reads those docs **in full** and returns a compact digest. For each session:
  title, achievement one-liner, **merge status**, and any items under
  "Follow-ups & YAGNI notes".
- From the digest, the subagent produces two buckets:
  - **`completed`** — work that is done and merged; do NOT re-propose these verbatim.
  - **`continuation-candidates`** — open follow-ups, unmerged branches, or ideas explicitly
    deferred; these are ripe to *continue or improve* today.

Hold both buckets for Step 4.

### 3. Survey the repo (read-only, cheap)
Skim for grounding — do NOT do deep work yet:
- Recent commits: `git log --oneline -15`
- Open work: any `.workflows/todos.md` and `**/analysis_report.md` files (`find . -name todos.md` , `find . -name analysis_report.md`)
- Test-coverage gaps: packages with few/no `*_test.go` files
- Stale or thin docs under `docs/` , `**/analysis_report.md` , `**/package_readme.md` and `**/unittest_guide.md`
- Obvious smells: large files, TODO/FIXME markers, dead code

### 4. Generate a menu of ideas, then pick the winner yourself
Blend fresh ideas with continuations. Tag each candidate the same way as before, but this
is now internal reasoning and session-doc material — not a prompt for the user:
- **🆕 Fresh** — new work that does NOT collide with anything in the `completed` bucket.
- **🔁 Continue/improve** — drawn from `continuation-candidates` (deepen, finish, or improve
  a prior session's work).

Generate 3–5 candidates. For EACH, work out:
- **Tag** — 🆕 or 🔁 (for 🔁, name the prior session it continues)
- **What** — one crisp sentence
- **Why it's real value** — not busywork
- **Scope** — files/packages touched, rough size
- **🔥 Burn potential** — low / med / high (how many tokens it will credibly consume)

Bias candidates toward `$ARGUMENTS` if provided, and keep the fresh ones varied across
sessions by drawing from this catalog (don't propose the same set every day):

- **Refactor** a subsystem for clarity/quality (e.g. `chatbot/queue`, `chatbot/cancellation`, `tools/toolcore/pipeline`)
- **Test coverage** — raise coverage in one package with real, meaningful tests
- **Audit** — hunt races/leaks/edge cases in a concurrency-heavy package
- **Docs rewrite** — modernize an architecture/overview doc under `docs/`
- **Deep-dive teaching** — explain one feature/function end-to-end for the user
- **gofmt + lint** — sweep formatting/lint issues across a package (`gofmt`, `golangci-lint`)
- **YAGNI hunt** — find and remove dead/speculative code

Then **immediately select the single highest-value candidate yourself** — the same
judgment call "surprise me" used to delegate to you, now made without waiting for that
prompt. Rank by real value first, burn potential second. Post the menu and which one you
picked plus why in one short message so the user has visibility, then proceed — this is a
status update, not a question, and does not block on a reply.

### 5. Create / reuse today's branch
```bash
git checkout main && git pull --ff-only 2>/dev/null; \
git checkout -b "token-maxxing-<DATE>" 2>/dev/null || git checkout "token-maxxing-<DATE>"
```
One branch per day — reuse it if it already exists.

Then name the session after the idea, not after the day:

```bash
python3 ~/.claude/skills/task/session.py rename "tokenmax-<IDEA-SLUG>" --no-widen
```

Five terminals open on one repo all carry the same derived name — `agentic-8f`, `agentic-d4` —
which says which repo and not which work, so the right window is found by reading scrollback and
`/resume` a week later offers a row of near-identical titles. The branch is per *day* and the
sessions under it are not, so the idea is what separates them: `tokenmax-queue-refactor`, not
`tokenmax-2026-08-31`. Keep it to three or four words — the name is capped at 60 characters and a
tmux window is narrow.

It is the same rename `/rename` performs: it reaches the running process over the session's own
socket, so the tab title, the `/resume` row and the name peers address all follow together — **and
the tmux window too**, which under tmux is the only one of those the user can actually see,
because the status line covers the terminal's tab title. `--no-tmux` skips that half. It cannot
fail (no socket, no tmux, a session started some other way → `renamed: false` with a reason, exit
0), and a session is not worth stopping over the name of a window.

If the scope changes because deeper investigation reveals the idea should shift, rename
again — it is idempotent and costs nothing. Do not pause to confirm the scope change; decide
and keep moving.

### 6. Roll
Do the work. Commit real increments with clear messages. Follow the project's skills
(TDD, systematic-debugging, etc.) as normal — quality still matters. Be thorough and
verbose; exhaustive-but-correct is the goal, not terse.

**If the idea is big** — 3+ packages, ~15+ files, or a removal/migration where order matters
(a YAGNI purge and a subsystem refactor usually are) — don't freehand it. Run:

```bash
/analyze --no-worktree <the idea, in prose, with the reasons it's worth doing>
```

It decomposes the work into phases, fans out one planner per phase, and reconciles their plans
against each other before anything is implemented. `--no-worktree` keeps the work on today's
`token-maxxing-<DATE>` branch instead of cutting a second one. Then implement with
`/implement -f <SLUG>_PLAN.md`, one phase at a time.

This is also high burn spent well: N planners in parallel plus a reconciliation pass, on work
that ends in a reviewed plan rather than a half-finished refactor.

`/analyze` renames the session to `analyze-<slug>` as part of its own step 4. Leave it — that name
is *more* specific than the day's idea, and it is the one the plan index and the artifacts carry.
Rename back to `tokenmax-<IDEA-SLUG>` only once planning is done and implementation moves on.

### 7. Auto-write the session doc when done
When you judge the work complete (or at a natural stopping point), **spawn a fresh
subagent** to run the `/token-maxxing-update-docs` workflow so the session is recorded
without you having to be asked. Give the subagent a full summary of what happened this
session, including the menu from Step 4 and why the winning idea was picked.

### 8. Merge to main automatically
Unless the user has explicitly instructed otherwise for this session, land the work on
`main` yourself as soon as Step 7's doc is written — do not stop and wait for review:

```bash
git checkout main && git pull --ff-only
git merge --no-ff "token-maxxing-<DATE>" -m "merge: token-maxxing session <IDEA-SLUG>"
git push
```

If the merge conflicts, resolve it yourself (same judgment `/analyze-orchestrator`'s
`swarm.py land` uses for merge conflicts) rather than leaving the branch unmerged for a
human to sort out. Once merged and pushed, delete the day's branch only if it is now an
ancestor of `origin/main` (`git merge-base --is-ancestor "token-maxxing-<DATE>" origin/main`) —
never delete it on a failed or partial merge. Prefer the `pusher` agent for the final
commit/push mechanics if any uncommitted work remains from Step 6.
