# Analyze Orchestrator Command

Drive a plan set written by `/analyze` across many sessions at once — one per phase, in parallel
where the DAG allows — and **resume that same set on any machine, at any time.**

```
/analyze-orchestrator -f <SLUG>_PLAN.md          # start driving a fresh plan set
/analyze-orchestrator --resume <slug>            # pick up a set already under way
/analyze-orchestrator --resume                   # pick up the only unfinished set here
/analyze-orchestrator --status <slug>            # report, change nothing

/analyze-orchestrator -f <PLAN> --permission-mode acceptEdits         # narrow the children
```

`/implement` walks a plan set one phase at a time in one session. This command runs the same set
as a swarm: it computes which phases share no dependency edge, opens a session per phase, watches
them, verifies what they claim, and lands the result. Everything mechanical lives in
`skills/swarm/swarm.py`; this command supplies the judgement.

It **writes no plans**. `/analyze` is the only command that writes plans — see the repo's
`CLAUDE.md`. Handed an analysis document instead of a plan index, refuse and name `/analyze`.

---

## Four iron rules

**1. The plan set is committed and pushed before a single phase is spawned.** A set that lives
only in a worktree dies with that worktree — which has already happened here once, and cost a
reconciliation nobody could read back. Durability is not a step at the end; it is the
precondition for starting.

**2. The ledger is pushed after every phase, not at the end of the set.** Resume can only recover
what reached the remote. Pushing per phase bounds the loss to one phase; pushing at the end means
"resume anywhere" quietly means "lose up to N phases".

**3. A finished phase's window is closed, permanently, by this session.** claude does not exit
when it runs out of work — it idles — so nothing closes these windows unless the coordinator
does. Two waves in, the tab bar is a wall of finished sessions and the running ones are off the
end of it; the windows are how the user watches a swarm, and a swarm nobody can watch is a swarm
running unsupervised. Closing them costs nothing to undo: `spawn --force` opens a fresh session
on the current code whenever a bug, a discrepancy or a re-run needs one, which is better than the
stale one you would have kept. The scrollback is captured to a file first, so nothing is lost —
see Step 4.7.

**4. Nobody in this swarm waits for a human — least of all this session.** A coordinator's
question is the most expensive question in the system: a phase that asks stalls one phase, while a
coordinator that asks stalls every phase in the wave, every wave behind it, and every window it
would have reaped. Multiply by fan-out. This session **decides and records**; it does not survey
options, ask which one, or end a turn on a question it needs answered to keep driving.

MEASURED on `nina-character-tuning`: phase 2 found its plan's invariant contradicting its own
prose, asked with `AskUserQuestion`, and held the prompt for **eight hours**. Phases 3 and 4 both
depended on 2, so a six-phase set built nothing overnight and this coordinator sat idle beside it
reporting "a genuine serial stretch, not idle time I can fill" — which was true of the DAG and
false of the reason. The answer was the plan's own invariant, on the first rung of the ladder
`/do` and `/implement` now carry.

Three consequences, each of them load-bearing:

- **Resolve the set's contradictions once, here, before spawning anything** (Step 1). A
  contradiction left in the plan is asked again by every phase that touches it; resolved in the
  ledger, it is inherited by all of them.
- **Answer a child that asks** (Step 4.4b) instead of relaying its question to the user. This
  session holds the plan index, the Requirements table and every sibling's report — it is the
  best-informed decider in the swarm, and the only one awake.
- **A stop is allowed; a block is not — and there is no legitimate wait left, not even the merge.**
  Step 5 lands the set itself: it merges to `main`, applies the production migrations, pushes, and
  deletes the worktree and the branch. A night that ends with every phase committed to a branch
  nobody merged is a night that still needs a human before it is worth anything. A stop is a
  failure with a reason — a conflict no rung resolves, a migration that will not apply, a push the
  remote refuses — reported and ended, never a prompt someone has to come back to.

---

## Step 1: Locate the Set

**Fresh (`-f`).** Read the plan index. Refuse and stop if:
- it is an analysis document rather than a plan index → name `/analyze`
- any phase's **Plan** column points at a file that does not exist

**Read `## Decisions` and treat it as settled.** Each row is a fork `/analyze` resolved with the
rung that resolved it; the children inherit them through the index, and reopening one here would
overrule reconciliation, which saw all N phases at once.

**A non-empty Open Questions section is not a refusal, and not a question to forward.** After a
current `/analyze` run those items are forks where every branch is irreversible; an older plan set
may have ordinary contradictions parked there. Either way a swarm multiplies each of them across
every phase that touches it, which is exactly why this session resolves them **now, once**,
rather than letting N children meet the same fork independently:

1. Decide each item with the precedence ladder `/implement` states — **stated invariant → exit
   criteria → the plan's code blocks → the index's Why and Requirements table → task text →
   surrounding convention.** First rung that speaks decides it.
2. Print each decision: `⚖ Open question {i} → {choice}. Rung {n}: {what decided it}.`
3. **Write the resolutions into the plan index**, replacing the Open Questions item with the
   decision and the rung — the children read the index, so this is how the answer reaches them —
   and carry the same line into the ledger note at `init`. Step 2 pushes both, so a resume on
   another machine inherits the decisions instead of re-deriving them.

An unresolvable item — every branch irreversible, nothing on the ladder speaking — is the one that
stops, per iron rule 4: report it and end the session before spawning, because a swarm launched
over a real fork does the wrong work N times in parallel.

**Resume (`--resume`).** Read `<repo>/.workflows/orchestration/*/ledger.json`. With no slug, if
exactly one set is unfinished, take it. **If several are, pick one and say which** — the set whose
branch is currently checked out, else the most recently updated ledger — list the others under
`Also unfinished:` with the `--resume <slug>` line that would switch to them. Listing three sets
and waiting is a stall with a 1-in-3 chance of being needed; picking the checked-out one is right
almost always and costs one re-run when it is not. Resume never reads the
worktree first — the worktree may be gone, may belong to another machine, or may never have
existed on this one.

## Step 2: Make It Durable

Once per repo, then idempotently every run:

```bash
python3 ~/.claude/skills/swarm/swarm.py track
```

This re-includes `.workflows/orchestration/` and nothing else. It does **not** un-ignore
`.workflows/plan/` — that directory is ignored deliberately in at least one repo here, holding
hundreds of generated plans, and undoing that would be a change nobody asked for.

Then copy the set out of the worktree into the tracked path, because the worktree is the thing
that disappears:

```
<main repo>/.workflows/orchestration/<slug>/
├── PLAN.md            the plan index
├── analysis.md        the <session-id>_code_analyzer.md it came from
├── phase-1.md ...     every phase plan, verbatim — reconciled, never re-derived
└── ledger.json        written by swarm.py init
```

Copy the phase plans **unchanged**. They were reconciled against each other by
`plan-reconciler`; a plan that gets touched on the way through is a plan whose reconciliation no
longer holds.

Commit and push through the `pusher` agent. Nothing is spawned until that push succeeds — if the
remote rejects it, stop and tell the user, because a set that is not on the remote cannot be
resumed anywhere.

## Step 3: Build the Ledger, Then Distrust It

```bash
python3 ~/.claude/skills/swarm/swarm.py init  --plan .workflows/orchestration/<slug>/PLAN.md \
                                              --coordinator orch-<slug>
python3 ~/.claude/skills/swarm/swarm.py verify --slug <slug> --apply
```

`init` is safe to re-run: it re-reads the phase table but keeps every recorded outcome.

`verify` is the heart of resume. The ledger was written by whichever machine ran the phase, and a
laptop that got closed mid-phase left it saying `running` forever. So the real status is derived
from what cannot lie — whether the commit is an ancestor of the branch, and what `todos.md` says
about the TaskID — and any disagreement is resolved in favour of the derivation.

**Report every disagreement, then act on it in the same turn.** A ledger that said `running` and
derives to `pending` means a phase was abandoned half-done, and the user may well know why — but
the report is a line in the output, not a question, and the derivation is what you act on either
way. `verify` already resolves disagreement in favour of what git can prove; printing the
disagreement lets a human correct it later without holding the set until they do.

Then name this session, so the phases have somewhere to report:

```bash
python3 ~/.claude/skills/task/session.py rename "orch-<slug>" --no-widen
```

## Step 4: Drive

Loop until `runnable_now` is empty:

1. `swarm.py waves --slug <slug>` → the phases whose dependencies have all landed.
2. **Spawn them all in this round**, not one at a time — the whole point is that a wave runs
   concurrently:
   ```bash
   python3 ~/.claude/skills/swarm/swarm.py spawn --slug <slug> --phase N
   ```
   Each opens a detached tmux window running `/implement -f <PLAN.md> --phase N` in a session
   already named `impl-<slug>-p<N>`. Detached on purpose: it must never steal the window the user
   is reading.
3. **Re-read `ListAgents` before addressing anyone.** A name captured a minute ago may now
   belong to a different session — names are mutable and reused. Then **subscribe to each**,
   in one message, with `SendMessage` carrying `notify_when_idle: true`
   and no body. This is the only way to notice a phase that dies without reporting — silence
   from a working session and silence from a crashed one are otherwise identical. Never poll
   `ListAgents` in a loop, and never send "are you done?".
4. **Collect reports** as they arrive (`<cross-session-message from="impl-<slug>-p2">`).
4b. **Answer a child that asks — never relay it.** `/do` and `/implement` forbid the question, so
   a child asking one is a session on an older prompt, a genuine plan contradiction, or a fork
   its own ladder could not reach. All three are yours: you hold the plan index, the Requirements
   table, the resolved Open Questions and every sibling's report, which makes this the
   best-informed decider in the swarm and the only one awake. Decide on the same ladder
   (**invariant → exit criteria → code blocks → Why/Requirements → task text → convention**),
   reply with the choice *and the rung*, and record it in the ledger note so the phases after it
   inherit the answer. Forwarding it to the user converts one stalled phase into a stalled set.
   The only exception is iron rule 4's stop: a fork where every branch is irreversible, which is
   reported, not asked.
5. **Verify, then believe.** `swarm.py verify --slug <slug> --apply`. A phase that reports `done`
   whose commit is not on the branch has not landed, whatever it said.
6. **Push the ledger** via `pusher`. Every round. This is iron rule 2.
7. **Reap the finished windows.**
   ```bash
   python3 ~/.claude/skills/swarm/swarm.py reap --slug <slug>
   ```
   After the verify in step 5, never before it — an unverified `done` is a claim, and its
   scrollback is the evidence. `reap` captures each pane's whole history to
   `.workflows/orchestration/<slug>/logs/phase-N.log` and then closes the window, so the tab bar
   holds only what is still running. It refuses on its own to touch a phase that is still
   working, a `done` whose commit is not on the branch, a window whose id now belongs to some
   other window, or this session's own window — so it is safe to run every round without
   reading the list first.

   A **failed** phase keeps its window: that failure is what someone is about to read. Close it
   with `--include-failed` once the user has seen it, or when landing the set.
8. Recompute and go to 1.

**Stragglers.** An idle notice with no report means the phase stopped without finishing. Send that
session one message asking what happened — a peer is not a human, and `SendMessage` to a live
session is cheap — but **do not hold the round on its reply.** Carry on with the rest of the wave;
if no answer has arrived by the next `verify`, decide from what git can prove: a commit on the
branch means it landed and forgot to report, and no commit means it failed. Mark it, note it, and
let `stalled` show what it took down with it.

**A failure never pauses the branches of the DAG it does not touch.** Report the failed phase and
its `stalled` dependents, then keep spawning everything still in `runnable_now`. Halting the whole
set on one failure turns a partial night into an empty one.

**Spawn every child on this session's own permission mode.** When `--permission-mode` was passed
to *this* command — which is what `/analyze` does when it launches you — that is the mode: hand it
to every `spawn`. With nothing passed, use `bypassPermissions`, matching `/analyze`'s default,
because an orchestrator exists to run unattended and a child that stops to ask stalls the wave it
is in until someone notices. A session cannot read its own mode, so this argument is the only way
it travels.
A child on a different mode has its reports *held for the user to approve* — the coordinator
never sees them, and a stalled swarm is indistinguishable from a slow one. `spawn` warns when the
flag is missing, because nothing else about the failure is visible.

The same flag is a boundary in the other direction: **never hand a child a mode broader than this
session runs under.** That routes around a decision the user made. If a phase needs permissions
you lack, stop and say so.

**The folder trust prompt is handled, and you should know why.** A session spawned into a path
Claude Code has not seen stops to ask whether the folder is trusted, before it boots — so it
never becomes a peer and this session waits on it forever. Every worktree `/analyze` cuts is such
a path. `spawn` propagates the repo's existing trust to the worktree; if the repo itself is not
trusted it refuses rather than inventing trust, and the user has to open it once by hand.

## Step 5: Land the Set

**The merge belongs to this set's coordinator.** Every coordinator now merges its own set
unattended, so a second session reaching Step 5 for a set it did not cut is the collision this
rule exists for. If you are landing a set you did not cut — the coordinator died, or a peer
resumed the set on another machine — check `ListAgents` for the
ledger's `coordinator` first and send it a **`CLAIM`** *before* you merge, not after. MEASURED
2026-09-05: a peer merged a completed set and reported afterwards; the coordinator had the same
merge built and gated locally and discarded it, which cost nothing — but the other ordering puts
two merges of one set on `main`. `coordinator` and `coordinator_session_id` are in the ledger from
before phase 1 spawned, so the owner is always findable. A `CLAIM` announces and proceeds; it does
not ask, and it does not wait for a reply.

**It also claims the main worktree's index until you report the sha.** A coordinator whose set is
being merged parks its own prune, ledger commit and any `git add`/`git rm --cached` in that
directory until then, and runs them on top afterwards as a separate commit. MEASURED 2026-09-05: a
Step 5 prune ran into a resolved-but-uncommitted merge index in the shared main checkout and
removed two phase bodies from it; it was caught and restored, and the merge committed clean, but
`git status` in a shared worktree never says whose index it is. Re-verify the tree against what you
staged before committing — including anything a peer reports it put back, since the session that
contaminated an index is the weaker witness to its repair.

**Check the answer `swarm.py find` gives you against the ledger's own `slug` before you address
anyone.** `find` is a lookup, not an authority, and a wrong answer from it is silent: it names a
real slug, a real phase and a real coordinator, so nothing about the reply looks wrong. MEASURED
2026-09-05: a matching bug made `find --plan` fall back to the plan file's BASENAME, and since
every set has a `phase-N.md` and ledgers are scanned in sorted order, the alphabetically-first set
won every lookup — `tabbar-new-tab-composer-seam/phase-2.md` resolved to
`admin-album-file-manager`, a set finished hours earlier, naming a coordinator that no longer
existed. A `CLAIM` sent on that answer goes to the wrong session about the wrong set, which is the
exact failure `CLAIM` exists to prevent. One comparison — does the returned `slug` match the
directory the plan file lives in? — costs nothing and catches it.

**The merge is not put to the user, and neither is anything after it.** This step runs to
completion on its own: merge, migrate, push, delete the worktree, delete the branch. The old
shape stopped here and reported — every phase landed on a branch, waiting on a thirty-second
decision in the morning — which is the same dead night iron rule 4 exists to prevent, moved to the
end of the run where it is least visible. The isolation that makes it safe is the same isolation
that justified `bypassPermissions` upstream: `/analyze` cut the branch, every phase built green on
it, and Step 5 verifies from git before it touches `main`. A merge that turns out wrong costs one
`git revert`; a set that never merged costs the whole night it took to build.

**Never reach this step early.** Landing while any phase is still `runnable_now` or `running`
merges a partial set and then deletes the branch the rest of it needed — the failure iron rule 4
describes, wearing Step 5's clothes. Every phase `done` and verified from git, or this step does
not start.

When every phase is `done`:

1. Verify once more, from the branch rather than from the ledger.

1b. **Check the migration numbering before anything else.** A set cut from one base and merged
   into a `main` that moved can carry a migration whose number another set already used — two
   different `0004`s, one per branch. This does not present as a conflict on the `.sql` files,
   because their names differ, and it is the more dangerous half of the failure: a migrator that
   applies journal entries newer than the most recently applied row will **silently skip** a
   migration whose timestamp predates one already applied. The deploy looks clean and the table
   is simply never created. MEASURED on `nina-character-tuning`: the branch's `0004` was stamped
   14:49 and `main`'s applied `0004` at 20:18, so `nina_tuning` would never have existed.

   Resolve by keeping the base's migration and **regenerating** the set's from the merged schema —
   never by renaming the file. A rename keeps the stale timestamp and the stale snapshot chain;
   a regeneration re-derives both from what the schema now says, and the new entry is stamped
   after everything already applied. Then apply it and verify the objects exist in the database
   rather than trusting the migrator's exit code.
2. **Leave the worktree before you touch anything.** This session's cwd is the worktree
   `/analyze` cut, and step 6 deletes it — a session standing in a directory that stops existing
   cannot run the rest of its own landing sequence. Resolve the main checkout once, up front, and
   address every later command at it explicitly:
   ```bash
   MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
   SLUG=<slug>; BR=feature/$SLUG
   WT=$(git -C "$MAIN" worktree list --porcelain | awk -v b="refs/heads/$BR" \
          '/^worktree /{w=$2} $0=="branch "b{print w}')
   cd "$MAIN"
   ```

3. **Merge in a throwaway worktree of `origin/main`, never in the shared main checkout.** The
   main checkout may be dirty, on another branch, or holding a peer's half-staged index — the
   MEASURED contamination two paragraphs up happened in exactly that directory. A worktree cut
   for the merge and deleted after it has no such neighbours:
   ```bash
   LAND=${TASK_WORKTREES:-$HOME/.worktrees}/$(basename "$MAIN")/land-$SLUG
   git -C "$MAIN" fetch origin main --quiet
   git -C "$MAIN" worktree add -B "land-$SLUG" "$LAND" origin/main
   git -C "$LAND" merge --no-ff "$BR" -m "merge($SLUG): <N> phases — <title>"
   ```
   **Conflicts are decided, not asked.** A conflict here is between two phases of one set, or
   between the set and what landed on `main` while it ran — and this session holds the plan index,
   the invariants, the Requirements table and every phase's report. Resolve on the same ladder
   (**invariant → exit criteria → the plan's code blocks → Why/Requirements → task text →
   convention**), `git add`, `git commit --no-edit`, and record the rung. The only stop is a
   conflict no rung reaches: `git -C "$LAND" merge --abort`, remove the land worktree, keep
   `$BR` and its pushed commits intact, and report — the branch is exactly as safe as it was
   before this step started.

4. **Apply the production migrations before the push, and verify them against the database.**
   Production deploys from `main`, so code that arrives ahead of its schema is a runtime error on
   the first request. Applying first, from the merge commit, is the order that cannot produce one.

   Find the migrator from the repo rather than guessing it: the phase plans' exit criteria name it
   first (they were written against this tree), then `package.json` scripts matching `migrate`/`db:`,
   `drizzle.config.*`, `alembic.ini`, `prisma/`, `supabase/migrations/`, a `Makefile` target, the
   README's deploy section. Use the credentials the repo already carries — a `.env.production`, a
   deploy env var, whatever the migrate script itself reads. **Never invent a connection string,
   and never point a migrator at a database nothing in the repo names:** that is a stop, reported
   with what you looked for.
   ```bash
   git -C "$LAND" log --oneline origin/main..HEAD -- '*migrations*' '*migrate*'
   # then the repo's own command, run from $LAND with the production credentials
   ```
   - **Regenerate a colliding migration here, from the merged schema** (step 1b) — before applying,
     never after, and never by renaming the file.
   - **Verify the objects, not the exit code.** Query the database for the tables, columns,
     indexes and enum values the migration claims to have created, and quote the answer in the
     termination block. A migrator that skips an entry silently exits 0.
   - **A destructive migration the plan prescribes is executed, not parked.** Dropping a column
     the plan says to drop is planned work, not an undecidable fork — but take what dump the
     tooling offers first (`pg_dump -t` of the affected tables into
     `.workflows/orchestration/<slug>/logs/`), and list it in `Decided without asking`. What
     *does* stop is a destructive step no phase plan asked for.
   - **A migration that will not apply stops the landing, and nothing is pushed.** That is the
     whole reason it runs before the push: `main` is untouched, `$BR` still holds the work, and
     the morning's job is one migration rather than a broken production.

5. **Push, then tell the peers.**
   ```bash
   git -C "$LAND" push origin HEAD:main
   ```
   If the remote rejects it because `main` moved while you merged, re-fetch, merge `origin/main`
   into the land worktree, and push again — up to three rounds, then stop and report rather than
   looping. If it is rejected by a branch-protection rule, open the pull request and merge it
   with the tooling the repo already uses (`gh pr create --base main --head "$BR"` then
   `gh pr merge --merge`), and only if that is unavailable stop with the branch pushed and the
   reason named. Then record the merge sha in the ledger, and **if a live coordinator handed you
   this set, tell it what landed** — it holds the record for the set and outlives your session's
   knowledge of it.

6. **`WARN` every peer whose cwd is inside the worktree, then delete the worktree and the
   branch.** Their working directory is about to stop existing, and one of them may still be
   mid-write. Close the remaining windows first — a session inside a worktree that vanished is
   worse than a session closed:
   ```bash
   python3 ~/.claude/skills/swarm/swarm.py reap --slug "$SLUG" --include-failed
   git -C "$MAIN" worktree remove --force "$LAND" && git -C "$MAIN" branch -D "land-$SLUG"
   git -C "$MAIN" worktree remove "$WT"
   git -C "$MAIN" merge-base --is-ancestor "$BR" origin/main \
     && git -C "$MAIN" branch -D "$BR" \
     && git -C "$MAIN" push origin --delete "$BR"
   ```
   The set is over, so the failed phases' windows go too — their scrollback is in `logs/` and will
   outlive the tmux server. Anything `reap` still refuses is a session that is genuinely busy;
   name it in the termination block rather than forcing it, and leave the worktree until it is
   gone. **The `merge-base` guard is what makes the branch deletion safe to run unattended:** it
   deletes only a branch `main` already contains, so a stop at step 3, 4 or 5 leaves the branch
   standing by construction rather than by remembering to. `git worktree remove` refuses a dirty
   worktree — if it does, something in there was never committed; capture `git -C "$WT" status
   --porcelain` into `logs/` and force it, since the phases' work is on `main` and the residue is
   not.

7. Prune: keep `PLAN.md`, `analysis.md` and `ledger.json`; drop the phase bodies. `logs/` and
   `.runtime.json` are gitignored and stay on this machine — captured scrollback is exactly the
   kind of thing that has no business in a repo. That is what keeps the tracked footprint
   kilobytes rather than megabytes, and it is why tracking this directory does not recreate the
   problem `.workflows/plan/` was ignored to solve.
8. Final `pusher`, in `$MAIN` — the ledger's terminal state, the pruned set, the merge sha.

---

## What Resume Cannot Recover

Say this plainly to the user rather than discovering it together later: **uncommitted or unpushed
work on the other machine is gone.** There is no path from this laptop to a dirty worktree on
that one. A phase that was half-applied when the lid closed restarts from its plan.

That is survivable precisely because `/analyze` builds phases that stand alone — each one builds
and passes tests on its own — so restarting a phase is a re-run, never a repair. It is also the
whole reason for iron rule 2.

Three states resume distinguishes, and it must name which one it found:

| Found | Meaning | Action |
|---|---|---|
| commit on the branch | the phase landed | `done`, move on |
| commit recorded, not in this clone | pushed nowhere, or not fetched | fetch, then re-verify — **never** downgrade on absence alone |
| no commit, task open | never started, or lost with a worktree | re-spawn from the plan |

## Boards: GitHub and GitLab Are Not Symmetric

Both resume; they cannot share one code path.

- **GitHub** — the `/task` skill's shape applies: a parent card owns the worktree, branch and
  pull request, and each phase is a sub-issue closing on the parent's PR. Resume reads the
  sub-issue states as a third witness alongside git and `todos.md`.
- **GitLab** — sub-issues sit behind Premium, so there is no parent/child shape to read. Resume
  leans on `todos.md` plus git, and the board is a mirror to be updated, never a source to be
  believed.

Where a board and the derivation disagree, **the derivation wins and the board gets corrected** —
a card is a claim about the work, the branch is the work.

---

## Termination

```
Orchestrating <slug> — <N> phases, <W> waves

  wave 0   phases 1, 3     <- ran concurrently
  wave 1   phase 2
  wave 2   phase 4

Landed:
  1  <title>   P1-TP-A011  f4d75ca9   window closed, log kept
  3  <title>   P1-TP-A014  9c1e0b22   window closed, log kept

Open:
  2  <title>   spawned as impl-<slug>-p2  (tmux @71)

Merged:   feature/<slug> -> main   <merge sha>   pushed
Migrated: 0007_add_nina_tuning   applied to production
          verified: table nina_tuning, index nina_tuning_user_idx
Cleaned:  worktree ~/.worktrees/<repo>/<slug> removed
          branch feature/<slug> deleted local + origin

Decided without asking:
  OQ1  <the fork>  ->  <choice>   rung 1: plan invariant 2
  p2   <the fork>  ->  <choice>   rung 2: phase exit criterion 3
  merge <conflicted file>  ->  <side kept>   rung 3: phase-2 plan code block

Windows:  1 open, 2 closed -- scrollback in .workflows/orchestration/<slug>/logs/

Ledger:  .workflows/orchestration/<slug>/ledger.json  (pushed @ <sha>)
Branch:  feature/<slug>
Session: orch-<slug>

Resume this anywhere:

  /analyze-orchestrator --resume <slug>
```

**The three landing lines are the report the user reads first**, because they are what happened to
`main` while nobody was watching. State them as facts with shas and object names, never as "should
be" — a `Migrated:` line that names no verified object is a migrator's exit code wearing a
verification's clothes. When the landing stopped instead of finishing, say so in the same place
with the reason and what is still standing: `Merged: STOPPED — conflict in <file>, no rung
resolves it; feature/<slug> intact at <sha>, main untouched.`

**The `Decided without asking` section is the morning's review queue**, and it is omitted only
when it is empty. Every entry is a fork this session or one of its phases settled from the plan
instead of holding a prompt — sourced from the resolved Open Questions, the ledger notes and the
phases' `decisions`. Overturning one costs a commit; not knowing it happened costs trust in the
whole run, so an unattended swarm that decided nothing worth listing is either trivial or lying.

The resume line sits alone so it can be pasted, and nothing follows it on that line — a trailing
`#` is read as arguments to a slash command, not as a comment. Same shape as `/analyze`, `/do`
and `/implement`.
