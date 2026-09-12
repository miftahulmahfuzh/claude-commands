---
description: Start a deliberately high-token-consumption ("token-maxxing") work session — auto-generate a menu of real-value ideas, pick the best one yourself, branch, roll, and merge to main when done. Pass a number to fan out N of these as parallel tmux sessions instead of one.
argument-hint: "[N] [optional theme, e.g. tests | docs | refactor | audit]"
---

# /token-maxxing

You are kicking off a **token-maxxing session**. Context: leadership wants higher
overall Claude token consumption, and the team wants a defensible record of real
engineering value to justify upgrading the company Claude subscription. So: burn tokens
generously, but bias hard toward **genuinely useful work** so every session is defensible.

**This command is fully automatic, end to end, in every mode below.** There is no menu
presented for the user to pick from, no "surprise me / reroll" prompt, and no
scope-confirmation checkpoint — you generate the candidate ideas, judge them, pick the
winner(s) yourself, and go. The only legitimate stop is the same bar `/do` and
`/implement` use: an undecidable fork where every branch is irreversible. Never stop to
ask "which idea do you want?", "does this scope look right?", or "should I merge this?" —
decide, record the decision, and proceed. This holds for the solo session below exactly
as it holds for a coordinator running five of them at once.

## Step 0: Mode Selection

Parse **$ARGUMENTS**:

- **Starts with `--worker`** → this is an internal invocation from a Coordinator Mode
  session, not a human. Skip straight to **Worker Mode** below; ignore everything else on
  this page until then.
- **First token is an integer > 1** (e.g. `5`) → that integer is `N`, the rest of
  `$ARGUMENTS` is the optional theme. Go to **Coordinator Mode**.
- **Anything else** (empty, a bare theme word, or `1`) → `N = 1`, the whole string is the
  optional theme. Continue with **Solo Mode** below — this is today's behavior, byte-for-byte
  unchanged.

(If a theme is present — e.g. `tests`, `docs`, `refactor`, `audit`, `teach` — bias idea
selection toward it, in every mode.)

---

## Solo Mode (default — N = 1)

One session, one idea, one branch. Do this, in order.

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

Bias candidates toward the theme if provided, and keep the fresh ones varied across
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
human to sort out.

**Immediately flip the session doc's `Merge status` line.** Step 7 wrote
`docs/token_maxxing/<DATE>-<title>.md` with `Merge status: on branch` — true when it was
written, false the instant the merge above lands. The version of that file now sitting on
`main` still says `on branch`. Edit it there to `merged (commit <merge-sha>)`, `git add`
that one file, `git commit -m "docs: mark <IDEA-SLUG> merged"`, `git push`. Do this before
the branch-deletion step below: Step 2 of this same command reads past session docs as
ground truth, and a doc that claims `on branch` after its branch is gone is exactly the
drift this fixes.

Once merged and pushed, delete the day's branch only if it is now an
ancestor of `origin/main` (`git merge-base --is-ancestor "token-maxxing-<DATE>" origin/main`) —
never delete it on a failed or partial merge. Prefer the `pusher` agent for the final
commit/push mechanics if any uncommitted work remains from Step 6.

---

## Coordinator Mode (N > 1)

`/token-maxxing 5` runs five token-maxxing sessions at once instead of one, each in its
own tmux window, each on its own branch, each writing its own session doc — and this
session becomes the coordinator that picks their ideas, watches them, and lands each one
to `main` the moment it finishes. It borrows the shape of `/analyze-orchestrator` —
generate/decompose centrally, dispatch in parallel, never wait on a human — but not its
machinery: there is no plan index, no phase DAG, and deliberately **no ledger**. The N
ideas are mutually independent (unlike phases of one plan, nothing here `depends_on`
anything else), so there is nothing to resume across a crash except "the branch is still
there, look at it" — a durable ledger would be real new infrastructure bought for a
problem this command doesn't have. If this coordinator dies mid-run, each worker's branch
and worktree survive independently and a human (or a fresh `/token-maxxing N`) can pick
up from `git branch --list 'token-maxxing-<DATE>-*'`.

**No tmux, no fan-out.** `swarm.py launch` needs a live tmux server to open a detached
window in. If `$TMUX` is unset, print one line saying parallel mode needs tmux and fall
back to running **Solo Mode** for a single winning idea instead of refusing outright — a
worse session that does real work beats no session.

### C1. Get the real date, recall, survey — once, centrally
Run Solo Mode Steps 1–3 exactly as written, but **once**, for the whole coordinator run —
not once per worker. This is the whole reason idea generation is centralized: a shared
`completed` / `continuation-candidates` picture is what lets Step C2 hand out N ideas that
don't collide, instead of N workers independently reading the same five docs and quite
possibly picking the same one.

### C2. Generate a menu, then pick N winners with disjoint scope
Run Solo Mode Step 4's process, but generate **at least N + 2** candidates instead of 3–5,
and select **N winners** instead of one. Two rules beyond Step 4's:

- **No two winners may share a package or file** they'd both touch — that is what makes
  N branches mergeable without every one of them fighting over the same lines. Prefer
  candidates from different rows of the catalog (a refactor and a docs rewrite and a
  test-coverage push touch disjoint trees almost by construction).
- If fewer than N non-colliding candidates exist, generate more rather than picking two
  that overlap — an idea menu is cheap; a guaranteed merge conflict between two workers
  that never needed to happen is not.

For each winner, derive its `SLUG_i` (kebab, three or four words, matching Solo Mode's
idea-slug convention). Post the full menu, the N picks, and why each was chosen, in one
status message — visibility, not a question.

### C3. Cut one worktree + branch per winner, from one shared base
Unlike Solo Mode, workers need real filesystem isolation — N sessions cannot each `git
checkout` a different branch in the same working directory at once. Fetch once, then cut
all N worktrees from that same fetched commit so no worker starts one commit behind
another purely from timing:

```bash
ROOT=$(git rev-parse --show-toplevel)
REPO=$(basename "$ROOT")
WT_ROOT=${TASK_WORKTREES:-$HOME/.worktrees}
git -C "$ROOT" fetch origin main --quiet 2>/dev/null || true
BASE=origin/main   # fall back to main, or the repo's default branch, if origin/main is absent

for SLUG_i in <the N slugs>; do
  git -C "$ROOT" worktree add -b "token-maxxing-<DATE>-$SLUG_i" \
      "$WT_ROOT/$REPO/tokenmax-<DATE>-$SLUG_i" "$BASE"
done
```

A branch-name collision (two coordinators running the same day, same idea) makes
`worktree add` fail loudly — that is a safe, visible failure, not a silent one; skip that
worker and note it rather than inventing a disambiguated name.

### C4. Rename this session
```bash
python3 ~/.claude/skills/task/session.py rename "tokenmax-orch-<DATE>" --no-widen
```
Workers address reports here by name — do this before spawning any of them.

### C5. Spawn all N workers in one round
No ledger means no `swarm.py spawn`/`init`/`waves` — those all key off a phase table that
doesn't exist here. Use `swarm.py launch` instead, which needs none of that: it opens one
named, detached tmux window per call and returns the window/pane id in its JSON output.
Call it once per worker, **all in this one step**, and keep each returned `window` id in
this session's own context, keyed by slug — that in-memory map is the entire "ledger":

```bash
python3 ~/.claude/skills/swarm/swarm.py launch \
    --name "tokenmax-$SLUG_i" \
    --cwd "$WT_ROOT/$REPO/tokenmax-<DATE>-$SLUG_i" \
    --permission-mode <this session's mode, bypassPermissions by default> \
    --prompt "/token-maxxing --worker --coordinator tokenmax-orch-<DATE> --slug $SLUG_i --idea $(printf '%q' "<idea i, one crisp sentence plus its Why>")"
```

`--permission-mode`: pass whatever this session runs under; default `bypassPermissions`
for the same reason `/analyze` and `/analyze-orchestrator` do — an unattended worker on a
mode that stops to ask stalls silently, because a child on a *different* mode than its
coordinator has its reports held for a human to approve, which looks identical to a slow
worker. Never hand a worker a mode broader than this session's own.

### C6. Subscribe, then wait for reports
Re-read `ListAgents` immediately before addressing anyone (a name captured a moment ago
may already belong to someone else), then send each worker one `SendMessage` with
`notify_when_idle: true` and no body — this is how a worker that dies without reporting
is distinguished from one still working.

**Answer a worker that asks, rather than relay it.** There is no plan index or invariant
ladder here, but there is still a ladder: **the idea's own stated Why (from C2) → this
repo's CLAUDE.md conventions → surrounding code convention.** This coordinator is the
only session holding all N ideas and the full menu reasoning, which makes it the
best-placed decider even without a formal plan document. The only real stop is the same
one every command in this repo uses: a fork where every branch is irreversible.

### C7. On each report, land it immediately
Do not wait for the other workers. A report is one line stating a fact — `DONE slug=<s>
branch=<b> commit=<sha> summary=<...> doc=<path>`, or `FAILED slug=<s> reason=<...>`, or
`STOPPED slug=<s> reason=<irreversible fork>`. For a `DONE`:

1. **Verify before believing** — `git -C "$WT_ROOT/$REPO/tokenmax-<DATE>-$SLUG_i" rev-parse HEAD`
   must equal the reported commit.
2. **Merge, same judgment as Solo Mode Step 8:**
   ```bash
   git checkout main && git pull --ff-only
   git merge --no-ff "token-maxxing-<DATE>-$SLUG_i" -m "merge: token-maxxing session $SLUG_i"
   git push
   ```
   Resolve any conflict yourself — idea's stated Why → repo convention — `git add`,
   `git commit`, then continue. Never leave a landed worker's branch unmerged waiting for
   the rest of the round; that is the exact overnight stall `/analyze-orchestrator`'s
   iron rules exist to prevent, and nothing here has a reason to serialize on it.
3. **Flip the worker's own `Merge status` line before touching its branch.** The
   worker's `doc=<path>` from its report was written under Worker Mode Step W3, before
   this coordinator ever merged it, so it reads `Merge status: on branch, NOT merged —
   this is a worker session; the coordinator owns landing worker branches` — the copy of
   that file that just landed on `main` still says that. Edit it there to `merged
   (commit <merge-sha>, landed by coordinator tokenmax-orch-<DATE>)`, `git add` that one
   file, `git commit -m "docs: mark $SLUG_i merged"`, `git push`. Do this in the same
   breath as step 2's merge, before step 4 below: a worker doc that still claims `NOT
   merged` once its branch is deleted misleads every later Step 2 recall that reads it
   as ground truth, and there is no other point at which anything will ever fix it.
4. **Delete the branch and worktree only once it's a proven ancestor of `main`:**
   `git merge-base --is-ancestor "token-maxxing-<DATE>-$SLUG_i" origin/main && git worktree remove ... && git push origin --delete ...`
5. **Close that worker's window, permanently** — best-effort scrollback capture first,
   since there is no `reap` without a ledger to back it:
   ```bash
   tmux capture-pane -t "$WINDOW_i" -pS -100000 > "/tmp/tokenmax-<DATE>-$SLUG_i.log" 2>/dev/null || true
   tmux kill-window -t "$WINDOW_i"
   ```
   using the window id this session captured in C5. A `FAILED` or `STOPPED` worker keeps
   its window open — that scrollback is what someone reads next — until the coordinator's
   own termination step closes everything that's left.

Each worker already wrote its own session doc before reporting (its own Worker Mode Step
W3), so there is nothing left for the coordinator to write per worker. Concurrent workers
editing `docs/token_maxxing/README.md`'s index table on different branches is expected and
harmless: it surfaces as an ordinary merge conflict on that one file in step 2 above,
resolved by keeping both new rows.

### C8. Stragglers
An idle notification with no report means that worker stopped without finishing. Send it
one message asking what happened, but never hold the round on the reply — keep collecting
from the others. If nothing arrives before you'd otherwise move on, decide from git: a
commit on the worker's branch means it landed and simply failed to report (treat as
`DONE`, land it); no commit means it failed (note it, close its window, move on). Never
auto-respawn a straggler — report it and let a human decide whether to re-run that one
idea.

### C9. Terminate
When every worker has reported (or been resolved as a straggler), print:

```
Token-maxxing fan-out — <N> workers, <DATE>

Landed:
  <slug-1>   <commit sha>   merged <merge sha>   doc docs/token_maxxing/<file>
  <slug-3>   <commit sha>   merged <merge sha>   doc docs/token_maxxing/<file>

Failed / stopped:
  <slug-2>   <reason>   branch token-maxxing-<DATE>-<slug-2> left intact

Windows: <k> closed, <m> left open for review
```

There is no `--resume` to offer — resuming a stuck or failed worker is re-running
`/token-maxxing` with that one idea as its theme, from a clean branch, which is cheap
enough that building resume machinery for it would cost more than it saves.

---

## Worker Mode (internal — invoked only by Coordinator Mode via `--worker`)

A human never types this directly; `swarm.py launch` in Step C5 does. Parse from
`$ARGUMENTS`: `--coordinator <name>`, `--slug <slug>`, `--idea "<one sentence, with its Why>"`.

This session is already checked out on its own worktree and its own branch — the
coordinator cut both in C3 before launching it. **Do not run Solo Mode Steps 1–5**: there
is no date to recall against beyond what the coordinator already used, no menu to
generate, no branch to create. The idea is pre-assigned; jump straight to execution.

### W1. Rename
```bash
python3 ~/.claude/skills/task/session.py rename "tokenmax-<slug>" --no-widen
```
Same convention Solo Mode uses — this is exactly what a solo session would have named
itself for this idea, which is why sibling workers and the coordinator can all address
each other by the same pattern.

### W2. Roll
Run Solo Mode Step 6 verbatim, against the assigned idea instead of a self-picked one —
including the `/analyze --no-worktree` escalation path for an idea that turns out to be
big. `--no-worktree` still keeps things on this worker's own branch, not a nested one.

### W3. Auto-write the session doc
Run Solo Mode Step 7 verbatim: spawn a fresh subagent for `/token-maxxing-update-docs`,
giving it the assigned idea and its Why in place of Step 4's menu.

### W4. Report to the coordinator — never merge, never ask
This is the one place Worker Mode diverges from Solo Mode's Step 8: **do not merge to
`main`.** The coordinator owns every merge (C7) so that N workers are never all pulling
and pushing `main` at once. Instead, commit everything locally, then send one fact-only
message to `--coordinator`:

- Finished clean → `DONE slug=<slug> branch=token-maxxing-<DATE>-<slug> commit=<sha> summary=<one line> doc=<path>`
- Genuinely blocked, every option irreversible → `STOPPED slug=<slug> reason=<the fork, and why every branch is irreversible>`
- Anything else that stopped progress → `FAILED slug=<slug> reason=<...>`

Then go idle. Do not close your own window (the coordinator does that in C7 once it has
verified and merged you), and do not poll or wait for acknowledgment — the report is a
fact stated once, not the start of a conversation.
