# Analyze Orchestrator Command

Drive a plan set written by `/analyze` across many sessions at once — one per phase, in parallel
where the DAG allows — and **resume that same set on any machine, at any time.**

```
/analyze-orchestrator -f <path>/<SLUG>_PLAN.md   # start driving a fresh plan set
/analyze-orchestrator --resume <slug>            # pick up a set already under way
/analyze-orchestrator --resume                   # pick up the only unfinished set here
/analyze-orchestrator --status <slug>            # report, change nothing

/analyze-orchestrator -f <PLAN> --permission-mode acceptEdits         # narrow the children
/analyze-orchestrator -f <PLAN> --no-gate                             # spawn without the write-set gate
```

`--no-gate` is the only escape hatch in this command, and it is the same flag `skills/task` uses
for the same reason (`skills/task/DESIGN.md:159`, `skills/task/task_gh.py:2617`). The write-set
gate still runs and still prints; its exit code just stops refusing the spawn. It has to be passed
on purpose, and a wave spawned under it is spawned on somebody's judgement rather than on an
analysis. Step 3b says what to do when the gate cannot run *at all* — that case needs a ladder,
not this flag.

`/implement` walks a plan set one phase at a time in one session. This command runs the same set
as a swarm: it computes which phases share no dependency edge, opens a session per phase, watches
them, verifies what they claim, and lands the result. Everything mechanical lives in
`skills/swarm/swarm.py`; this command supplies the judgement.

**This command exists for N > 1.** Everything about it — waves, a ledger, per-phase sessions,
verifying before landing — is machinery for coordinating *several* phases at once. A one-phase
plan set has no DAG to schedule and nothing to land except a single commit, so `/analyze` never
routes one here: Step 11 there launches `/implement -f <PLAN> --phase 1` directly in a new tmux
window instead, and this command is never invoked for it. Refuse and say so if handed one anyway
(Step 1).

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
- **`Phases: 1`** — a single-phase plan has nothing for this command to coordinate. Say that
  `/analyze` should have launched `/implement -f <PLAN> --phase 1` directly for it (Step 11), and
  point the user at that line instead of proceeding.

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

## Step 3b: The write-set gate — before anything is spawned

`swarm.py waves` schedules from the `Depends on` column, which records what must *exist* before a
phase starts. It says nothing about what two phases in one wave will both *write*. Those are
different questions, and the second is where the collisions come from:

```bash
python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md>           # 0 clean · 1 unreadable · 2 collision
python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md> --json    # the per-collision class, for deciding
```

It reads each phase plan's `## Files` table — the write set the planner declared, the same list
`/implement` hands `pusher` as its allowlist — and reports every file two phases write, split by
whether their waves are concurrent or sequential.

MEASURED on `journal-versioning` (6 phases, the set that ran as four waves): six files are
written by more than one phase, and **exactly one of them concurrently** —
`engine/src/seer_engine/commands/lab.py`, written by phases 2, 3 and 4, all three in one wave.
That is the file whose collision was reported by hand afterwards. The other five —
`lab/store.py`, `test_lab_snapshot.py`, `lab/lab.sqlite`, `view.test.ts`, `web/data/lab.json` —
are written in different waves and were never at risk.

**This gate is enforcing, not advisory.** Nothing is spawned on a non-zero exit until that exit
has been dealt with — and dealing with it is this session's job, not a human's:

| exit | meaning | what this session does |
|---|---|---|
| `0` | no file is written by two concurrent phases | go to Step 4 |
| `1` | the plan could not be read — no phase table, or a phase plan missing | **stop.** There is nothing to remediate |
| `2` | a real concurrent collision | **remediate by class, re-run the gate once, and stop only if that did not clear it** |

Reading `1` or `2` as "proceed and watch" is the failure this gate exists to prevent. The exit
codes were always correct and deliberate (`plan_graph.py` `main()`); what was missing was a caller
that honoured them.

### Exit 1 — stop, and say why

Exit 1 means the analysis never ran. There is no collision report to act on, because there is no
report: the gate could not read the index's phase table, or a phase's **Plan** column points at a
file it could not open. The output lists them under `phase plans not found`, and — since phase 1 —
names the directory it resolved them against:

```
phase plans not found (write set unknown, treated as empty):
  phase 2: .workflows/plan/<slug>/phase-2.md
  resolved against root: /home/<you>/.worktrees/<repo>/<slug>

INCOMPLETE: no collision among the 2 of 3 phases whose plan could be read. 1 write set is
unknown, so this is not an all-clear.
```

Quote both of those lines in the stop. `resolved against root:` is the one that distinguishes a
plan file that is genuinely absent from a root the gate resolved wrongly, and it is the line that
was missing while the worktree bug survived four real plan sets.

No remediation applies, and that is the point of distinguishing 1 from 2: a missing phase plan is
not a scheduling problem to route around, it is a plan set that is not there. Spawning anyway
would run a wave on the strength of an analysis that never happened.

**Do not expect the all-clear sentence here, and do not quote it.** Before phase 1 the gate
printed `no file is written by two phases.` on this branch — affirmatively false, not merely
unknown; MEASURED: a two-phase set with a genuine concurrent ISOLATE collision printed exactly
that sentence and exited 1. Phase 1 made that sentence conditional on every phase plan having been
read, and gave the partial branch the `INCOMPLETE:` forms above, which deliberately share no
prefix with it. So on exit 1 the gate now says what it means; this phase's job is only to stop on
it. If that sentence ever appears alongside exit 1, phase 1's render guard has regressed — report
that, do not work around it.

So **stop**: print the gate's output verbatim, name each plan it could not read and the root it
resolved against, and end the session with the termination block below. Do not retry, do not route
around it, do not ask.

Two causes are worth naming, because they are the common ones and they are fixed differently:

- **A phase plan genuinely is not there.** Step 2 copied the set into
  `.workflows/orchestration/<slug>/` and one `phase-N.md` did not come with it, or the index's
  **Plan** column is stale. Fix the set, then `/analyze-orchestrator -f <PLAN>` again.
- **The index has no phase table at all** — it is an analysis document, not a plan index. Step 1
  should have caught that; say so and name `/analyze`.

An exit 1 that is neither of those means the gate could not resolve the repo root from the index's
location: the `resolved against root:` line names a directory the phase plans are not under. That
is a bug in the gate rather than in the set — report it as one, and quote that line, the index
path and the phase-plan paths it tried.

### Exit 2 — remediate what you can, stop only where you cannot

A gate that stops on something it could have fixed itself is iron rule 4 failing in a new costume:
the wave is not spawned, nobody is asked, and the night is gone anyway. So run `--json`, read each
collision's `verdict`, `concurrent`, `written_by` and `waves` fields, and act by class. These are
the same three classes `skills/swarm/SKILL.md` tabulates; what is added here is which of them this
session fixes for itself.

- **ISOLATE** (ordinary source file, concurrent writers) — **remediate and proceed.** Give each
  colliding phase its own worktree, cut from the integration branch at the start of the wave, and
  spawn into it:

  ```bash
  git worktree add <path> <integration-branch>
  python3 ~/.claude/skills/swarm/swarm.py spawn --slug <slug> --phase N --cwd <path>
  ```

  Use that form, not `spawn --isolate`. **`swarm.py spawn` has no `--isolate` argument and never
  had one** — VERIFIED: `grep -c isolate skills/swarm/swarm.py` is `0`; `git log --all -S'isolate'
  -- skills/swarm/swarm.py` is empty across the whole history, so the flag was only ever written
  into prose; and its argparse (`skills/swarm/swarm.py:2113-2124`) defines only `--slug --phase
  --prefix --prompt --cwd --permission-mode --model --force --no-trust --dry-run`. `--cwd` does
  exist and is the mechanism. Separate worktrees turn concurrent writes into separate branches,
  and disjoint regions of one file then merge cleanly at Step 4c.

  On `journal-versioning` the three phases' edit anchors in `commands/lab.py` were 29 lines apart
  at their closest (`3@101` / `2@130`; phase 4's single anchor at 843 sits 82 from its nearest
  neighbour) — well outside git's 3-line merge context, so isolation would have cost nothing.
  **Serializing that wave would have made it four waves into six.** Check the regions before
  trusting the verdict; "same file" is not "same lines". Where the two plans' anchors for that
  path sit within three lines of each other, isolation only defers the conflict to integration —
  treat that pair as ORDER and add the edge instead, and say that you did.

- **ORDER** (generated artifact) — **remediate and proceed.** It is regenerated, not merged, so
  one phase has to publish last. Add the dependency edge yourself, as below.
  `journal-versioning`'s planner found the `4 → 6` edge this way by hand.

- **BLOCK** (binary) — **serialize, always, and proceed.** Two concurrent phases writing a
  database is unresolvable after the fact. This is not a preference: a sqlite merge is a choice of
  side, and the discarded side's rows are gone. Serializing is the same edge as ORDER; add it.

- **sequential** — nothing to do. These never caused the exit; they are reported for completeness.

**Adding the edge, mechanically.** The later writer depends on the earlier one, so the last write
is the one that survives:

1. **Pick the publisher.** The phase whose `## Files` row for that path says `regenerate`
   publishes last; with no such row, the higher phase number does.
2. **Edit the Depends on cell** of that phase in **both** copies of the index — the tracked
   `.workflows/orchestration/<slug>/PLAN.md` and the worktree's `<SLUG>_PLAN.md`. They are one
   document in two places, and a resume on another machine reads the tracked one.
3. **Re-read the table:**
   ```bash
   python3 ~/.claude/skills/swarm/swarm.py init --plan .workflows/orchestration/<slug>/PLAN.md \
                                                --coordinator orch-<slug>
   ```
   `init` is safe to re-run: it re-reads the phase table and keeps every recorded outcome.
4. **Commit and push both through `pusher`, before spawning anything.** Iron rules 1 and 2: a
   schedule that exists only in this session's memory dies with this session.
5. **Re-run the gate.** It must now exit `0`, or exit `2` with only ISOLATE collisions left —
   which the per-phase worktrees handle.

**One remediation round, then stop.** If the second run still exits non-zero for a reason that
round was meant to clear, the remediation did not work and repeating it will not make it work.
Stop and report what was tried. Stop too if `dependency waves` comes back holding a cycle — `waves`
reports a cycle rather than looping on it, and a cycle means the edge you added is unaddable.

Print every remediation as it is decided, in the Step 1 format, and carry each line into the
ledger note and the termination block's `Decided without asking`:

```
⚖ collision src/shared.py (phases 2, 3, wave 0) → ISOLATE: one worktree per phase.
  Rung 6: SKILL.md's ISOLATE remedy; anchors 2@130 / 3@101 are 29 lines apart.
⚖ collision lab/lab.sqlite (phases 2, 4, wave 1) → BLOCK: serialize, edge 2 → 4.
  Rung 1: "a database merge is a choice of side and the other side's rows are gone".
```

### The stop is a stop, not a prompt

This is the reading that would turn iron rule 4 inside out, so it is written down rather than
assumed. A hard stop here **terminates the session with a report**. It does not put a question to
anyone: not through the ask-the-user tool, not as a yes-or-no confirmation, not as an interactive
shell command, and not as a turn ending on "which would you like?". Nothing is left running and
nothing is waiting on anybody. Stopping is allowed; blocking is not.

(That sentence names no prompt primitive literally, on purpose: exit criterion 3 and its grep
require that none of those spellings appear anywhere in Step 3b, and a ban that quotes the thing
it bans trips its own check.)

Print the termination block with the refusal in the landing position, the same shape Step 5's stop
uses:

```
Spawned: STOPPED — write-set gate exit 1: phase 3's plan
         .workflows/orchestration/<slug>/phase-3.md could not be read.
         Nothing spawned; all 4 phases remain `pending`.
         Re-run: /analyze-orchestrator --resume <slug>
```

```
Spawned: STOPPED — write-set gate exit 2 after remediation: lab/lab.sqlite is still
         written concurrently by phases 2 and 4; the 2 → 4 edge creates a cycle.
         Index and ledger restored; nothing spawned; all 6 phases remain `pending`.
         Re-run: /analyze-orchestrator --resume <slug>
```

Because nothing was spawned, every phase is still `pending` in the ledger and the set resumes
cleanly the moment the cause is fixed. That is what makes stopping cheap enough to be the right
answer here — unlike a stop mid-wave, this one costs nothing but the time to fix the plan.

### `--no-gate` — the escape hatch, and the ladder before it

`--no-gate` is the same flag and the same meaning `skills/task` gives it
(`skills/task/DESIGN.md:159`, `skills/task/task_gh.py:2617`): the gate still runs and still prints,
but its exit no longer refuses the spawn. It restores the advisory behaviour deliberately, for one
run. State the refusal in the shape `task_gh.py:1994-1999` established — what is missing, why it
matters, and the flag plus the words *on purpose*:

> The write-set gate could not read this plan set (exit 1), so nothing has checked whether two
> phases in one wave write the same file, and a collision found after the fact is a commit
> carrying work its author never finished. Fix the plan set, or pass `--no-gate` to spawn anyway,
> on purpose.

> The write-set gate found `lab/lab.sqlite` written concurrently by phases 2 and 4 (exit 2) and
> the serializing edge could not be added, so a wave spawned now would merge a binary by choosing
> a side. Serialize the two phases by hand, or pass `--no-gate` to spawn anyway, on purpose.

**But `--no-gate` was written to be typed by a human who is, by construction, asleep.** So this
session never reaches for it and never ends a turn hoping somebody types it. Where the gate cannot
run *at all* — `plan_graph.py` missing from the install, a crash, no `python3` — walk the ladder
instead, the same one `skills/task/DESIGN.md:238-246` documents for a repo with no CI:

1. **Derive the write sets by hand.** Read each phase plan's `## Files` table yourself, map every
   path to the phases that write it, and intersect that against `swarm.py waves`. This is the same
   analysis the gate performs — read rather than computed.
2. **Something was checked** → proceed under `--no-gate`, applying the class rules above to what
   you derived, and **name what you derived** — the paths, the phases, the waves — in the ledger
   note and under `Decided without asking`. "The gate did not run" is not the same as "nothing was
   checked", and the report must not blur them.
3. **Nothing could be derived either** — the phase plans are unreadable too — then this is exit 1
   by another route, and the answer is the stop above.

A plan index that already declares its own write-set table by hand, because the gate is
known-untrusted for that particular set, is rung 1 already done: act on that table and say so.

**What this gate cannot buy you is width.** The schedule's parallelism is a property of the
plan's DAG, not of the worktree model: `journal-versioning`'s widest wave holds three phases, so
no amount of isolation runs it eight ways. If you want eight-way waves, that is a demand on
`/analyze` to cut more independent phases — and `plan_graph.py` is also how you check it did.

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

   **Isolation: one worktree per phase, cut fresh from the integration branch at the start of
   each wave.** Cut it yourself, then spawn into it — `spawn` has no `--isolate` flag, and `--cwd`
   is the mechanism:

   ```bash
   WT=~/.worktrees/<repo>/<slug>-p<N>
   git worktree add -b "phase-<N>-<slug>" "$WT" "<integration branch>"
   # provision $WT here — see below
   python3 ~/.claude/skills/swarm/swarm.py spawn --slug <slug> --phase <N> --cwd "$WT"
   ```

   The phase's session then never sees a peer's uncommitted state, and its commits land on its
   own branch.

   **The provisioning is yours too, and three things must be right or the isolation is worse than
   sharing**: the worktree needs its **own `engine/.venv`** (Seer's CLAUDE.md),
   `web/node_modules` must be **hardlinked and not symlinked** (a symlink passes vitest and tsc,
   then fails `next build` with a misleading "filesystem root" error), and `pytest` needs
   `PYTHONPATH=engine/src` or it silently tests the main checkout instead of the branch. The
   research store is not copied into worktrees — point `--store` at the main checkout. Where the
   repo declares `.workflows/swarm.json`, its `suite.setup` is that list in the repo's own words;
   `agents/integrator.md` step 4 carries the same ladder for the integration worktree, and is the
   one place this knowledge is maintained.

   **Why the shared worktree was the old default, and what replaces the reason.** Phase N+1 needs
   phase N's code on disk to build against, so per-phase worktrees would once have meant each
   phase planning against a tree the others' work had not reached. What makes isolation safe now
   is that **a wave does not start until the previous wave has integrated** (Step 4c): each
   worktree is cut from an integration branch that already carries every landed predecessor. The
   guarantee moved from "we all share a tree" to "the tree we are each cut from is complete".
   Within a wave, phases are independent by construction — that is what the wave means — and the
   write-set gate above is what proves it rather than assuming it.

   The old shared-worktree default, for reference, and still what `spawn` does when it is given
   no `--cwd` — it falls back to the ledger's set-wide worktree (`swarm.py:852`):

   **Every phase in the wave runs in the SAME worktree — the one `/analyze` cut for the set — and
   that is deliberate.** Phase N+1 needs phase N's code on disk to build against, so one worktree
   per phase would mean each phase planning against a tree the others' work had not reached. The
   cost is that concurrent phases see each other's uncommitted files, and a phase that stages the
   tree as a whole commits its siblings' half-written work under its own name.

   The flow handles this — `completion-handler` passes `pusher` a `paths` allowlist built from
   `modified_files`, and `pusher` refuses `git add .` — but **verify it held rather than assuming
   it**: when a phase reports, check its commit's file list against the plan index's
   **File ownership** table before you believe the report (Step 4.5). A commit carrying a file
   another phase owns is a contaminated commit even when the tests passed, because the tests
   passed against a tree that included work its author never finished.

   MEASURED 2026-10-06 on `build-promotion-path`: phases 1, 2 and 3 ran concurrently in one
   worktree. Phase 1 committed while phase 3's partly-written `lab/prereg.py`, `commands/lab.py`
   and tests were dirty beside it. Both sessions chose explicit path allowlists unprompted and
   nothing was contaminated — but at the time nothing in the flow required it, so the clean
   result was two correct guesses rather than a guarantee. `pusher` and `completion-handler` were
   changed to require the allowlist; this check is the belt to that braces.

   **The allowlist does not stop the commit either, because the INDEX is shared as well as the
   tree.** A phase can stage exactly its own files by name, verify `git diff --cached`, and still
   ship a commit carrying a peer's whole phase — because a peer stages into the same index between
   the `add` and the `commit`, and a bare `git commit` takes all of it. MEASURED 2026-10-08 on
   `gotrade-fee-rebuild`, from two phases independently: `86ae23f` went out under phase 4's
   message carrying 17 files **none of which were `sim/`**, and `836d1a5` went out under phase 3's
   message carrying phase 4's entire bracket path. Both sessions had staged correctly.

   Two consequences for a coordinator, and the second is the one that bites:

   - **Reading a commit's file list against the ownership table no longer tells you whose work it
     is.** It tells you the work landed *somewhere*. Before concluding a phase's work is missing,
     search the whole branch for the file:
     `git log --format=%h <branch> | while read c; do git show --stat --format="" $c | grep -q <path> && echo $c; done`
   - **Never tell a phase its work vanished without running that search first.** MEASURED in the
     same run: phase 4's entire bracket path was on the branch inside phase 3's commit while
     phase 4 believed it had been destroyed. Had it re-implemented on that belief, a cosmetic
     mis-attribution would have become a real conflict. The correct instruction to the phase is
     "your work is at `<sha>`; diff against it and report", never "re-run your plan".

   **Do not fix a mis-attributed commit by rewriting it.** Every file is on the branch, only the
   message lies, and the set merges as one branch where the message is cosmetic. Rewriting a
   pushed commit in a worktree five sessions are pushing to is strictly worse. Record it in the
   ledger note and in `Decided without asking`, and move on.

   **The allowlist stops contamination; it does not stop a tree-wide command, and that is the
   failure that actually destroys work.** `git reset --hard` names no path, so "stay inside your
   allowlist" never catches it — and it reverts every tracked file of every peer, leaving no
   recoverable object behind for anything unstaged. Same for `git clean -fd`, `git checkout .`,
   `git restore .`, bare `git stash` and `git checkout <branch>`.

   MEASURED 2026-10-08 on `gotrade-fee-rebuild`: phase 1 committed, correctly noticed its commit
   had swept in phase 3's `benchmark.py` and `test_paper_benchmark.py` under its own message, and
   reached for `git reset --hard origin/<branch>` to undo it. The contamination guard worked
   perfectly — neither bad commit reached the branch. The *cleanup* destroyed phase 4's twelve
   files of finished, verified, uncommitted work in the same instant and cost phase 3 ~86 lines
   of tests. One session's correct instinct, executed tree-wide, took out two uninvolved peers.

   So when a wave spawns into a shared worktree, **say the ban once to every child in the wave**,
   with the safe alternative beside it — the reach for `reset --hard` is almost always a correct
   instinct aimed at the wrong tool:

   - to undo your own commit: `git reset --soft HEAD~1` (moves HEAD, touches nothing in the tree)
   - to revert your own edits: `git checkout -- <each path you own>`
   - to set work aside: `git stash push -u -m "p<N>-<unique-tag>"`, recover with `apply <sha>`

   **Say the between-wave protocol in the same breath**, because every phase in every wave but
   the first inherits a tree that moved under it, and three of the four items cost nothing until
   the one time they are missing:

   - commit explicit paths, and a **private `GIT_INDEX_FILE`** when a file is genuinely shared —
     a pathspec commit reads the working tree, so it takes a peer's uncommitted edit to any file
     it names
   - `git fetch` and rebase before reporting, never `--autostash`, and `merge --ff-only` instead
     of rebase for a branch carrying a shared binary
   - re-run the touched test files *after* catching up: a green from before a peer landed is not
     a green, and the plan's impact counts were measured at the base commit
   - a peer's failure report is unverified until this session reproduces it — a concurrent run
     reddens tests that read exactly like your own regression

   `/implement` carries all four in full; the wave message only has to make the child expect them.

   **If one has already run, preserve before you repair, and do it first.** `git reflog` names
   every commit the reset orphaned, and orphaned commits are gc-able — so tag each one *before*
   investigating: `git tag -f rescue/reset-casualty-<sha> <sha>`. Then diff each tag against the
   branch to learn what is actually missing, and tell the owning phase what to recover. Do not
   restore a peer's files yourself: the phase owns them and knows which version it wanted. A
   phase whose work is gone re-runs from its plan — which is exactly why `/analyze` builds phases
   that stand alone.
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

   `verify` answers *did it land*, not *did it land only what it owned* — and in a shared worktree
   those are different questions. So also read the commit's own file list:

   ```bash
   git show --stat --format="" <sha>
   ```

   Check it against the plan index's **File ownership** table. A file another phase owns, or one
   no phase claims, means the stage was not scoped — stop and look before spawning anything that
   depends on it, because a dependent phase built on a contaminated commit inherits the problem
   and buries it one layer deeper. `verify` cannot catch this: the commit is a perfectly good
   ancestor of the branch either way.

   Where a phase's exit criteria name a guardrail that a bad stage could silently break — a
   pinned constant, a test that must not be edited, a fingerprint that must not move — re-run
   that check yourself here rather than quoting the phase's report of it. A phase verifying its
   own guardrail is the weaker witness, and these are cheap: one `grep`, one `git diff --numstat`.
6. **Integrate the wave before the next one is cut** — only where the wave ran isolated, each
   phase in its own worktree and landing on its own branch. Dispatch the **`integrator`** agent with the wave's branches and the
   integration branch. It merges them in dependency order in a throwaway worktree, regenerates
   derived artifacts rather than merging them, runs the **full** suite, and only then moves the
   integration branch. It never pushes `main`.

   This step is what makes per-phase isolation safe: the next wave's worktrees are cut from an
   integration branch that already carries every landed predecessor, which is the guarantee the
   shared worktree used to provide by sharing a disk. **A red integration stops the wave loop** —
   the integration branch does not move, every phase branch stands untouched, and the report names
   the merge on which the suite started failing. Do not spawn the next wave over a red integration;
   that is how a one-phase regression becomes a six-phase bisect.

   `lab/lab.sqlite` changed on both sides is the one thing it escalates instead of deciding. There
   is no merge for a database — only a choice of side, and the other side's rows are then gone.
   The write-set gate is where that is prevented, by never putting two database writers in one
   wave.

7. **Push the ledger** via `pusher`. Every round. This is iron rule 2.
8. **Reap the finished windows.**
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

### Watching the wave while it runs

A wave is only as fast as its slowest member, and a *stalled* member is not slow — it is stopped,
and it blocks everything behind it. Watch rather than poll by hand: a `Monitor` on the wave's log
directory and each worktree's test output surfaces three states worth acting on.

- **Working** — the pane is producing output and the ledger moves. Leave it alone.
- **Stalled** — no output for materially longer than its peers took to reach the same step. Check
  `swarm.py status --slug <slug>`, then read the pane before acting; a HARD phase writing 20 tests
  is quiet for a long time on purpose.
- **Looping** — the same command repeating with the same result. This is the one to kill: it will
  not recover on its own, and it burns a slot plus tokens. `reap --force` the window, then
  `spawn` the phase again from the integration branch. A phase respawned from a clean cut of an
  integrated branch starts from a better place than the one that got stuck.

Kill-and-respawn is cheap **because** of isolation: the phase's branch holds whatever it committed
and its worktree holds the rest, so nothing a peer did is at risk either way. In a shared worktree
the same action risked a peer's uncommitted files, which is why it was never the default before.

**A note on width, measured.** Isolation removes the collision ceiling, not the machine's. Five
concurrent *lab* phases — each loading the research store, ~1 GB resident — took this laptop's WSL
down twice at 15 GB. Implementation phases are lighter (no store), but each still carries a Claude
session, its own `engine/.venv` and a hardlinked `node_modules`, so treat eight-way as something to
measure on the first set that wants it rather than as a setting to turn on. The honest cap today
is: lab waves 4, implementation waves unmeasured above 4.

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

1b. **Know what the migration-numbering check is for before you read step 4.** A set cut from one
   base and merged
   into a `main` that moved can carry a migration whose number another set already used — two
   different `0004`s, one per branch. This does not present as a conflict on the `.sql` files,
   because their names differ, and it is the more dangerous half of the failure: a migrator that
   applies journal entries newer than the most recently applied row will **silently skip** a
   migration whose timestamp predates one already applied. The deploy looks clean and the table
   is simply never created. MEASURED on `nina-character-tuning`: the branch's `0004` was stamped
   14:49 and `main`'s applied `0004` at 20:18, so `nina_tuning` would never have existed.

   `land --step merge` finds these mechanically — it lists every migration the branch adds and
   every one whose number the base already used — so the detection is not yours to remember. The
   resolution is: keep the base's migration and **regenerate** the set's from the merged schema,
   never rename the file. A rename keeps the stale timestamp and the stale snapshot chain; a
   regeneration re-derives both from what the schema now says, and the new entry is stamped after
   everything already applied. Step 4 does this, before applying anything.
2. **Leave the worktree before you touch anything.** This session's cwd is the worktree
   `/analyze` cut, and step 6 deletes it — a session standing in a directory that stops existing
   cannot run the rest of its own landing sequence. `land --step cleanup` refuses outright when it
   is asked to delete the caller's cwd, so this is a guard rather than a hope, but the `cd` is
   still yours to do:
   ```bash
   S=~/.claude/skills/swarm/swarm.py
   MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
   cd "$MAIN"
   python3 $S land --slug <slug> --step check
   ```
   `check` re-derives every phase from git rather than reading the ledger, and lists what stands
   in the way. A phase recorded `done` whose commit is not on the branch is a blocker, not a
   detail — that is the same distrust step 1 applies, aimed at the one irreversible step.

3. **Merge.** `land --step merge` cuts `land-<slug>` from `origin/main` and merges `--no-ff` into
   it. The throwaway worktree is the point: the shared main checkout may be dirty, on another
   branch, or holding a peer's half-staged index — the MEASURED contamination two paragraphs up
   happened in exactly that directory — and a worktree deleted after the merge has no neighbours.
   It merges into the *remote-tracking* ref deliberately, because the local `main` in a repo whose
   work happens in worktrees is usually behind.
   ```bash
   python3 $S land --slug <slug> --step merge
   ```
   **Conflicts are decided, not asked.** `merge` leaves a conflict in place and lists the paths;
   it does not resolve them, because a conflict here is between two phases of one set, or between
   the set and what landed on `main` while it ran — and this session holds the plan index, the
   invariants, the Requirements table and every phase's report. Resolve on the same ladder
   (**invariant → exit criteria → the plan's code blocks → Why/Requirements → task text →
   convention**), `git add`, `git commit --no-edit`, and record the rung. The only stop is a
   conflict no rung reaches: `git merge --abort` in the land worktree, and report — the branch is
   exactly as safe as it was before this step started.

4. **Apply the production migrations before the push, and verify them against the database.**
   Production deploys from `main`, so code that arrives ahead of its schema is a runtime error on
   the first request. Applying first, from the merge commit, is the order that cannot produce one
   — and it is why `land` is four steps rather than one.

   `merge` already reports what the branch adds under any `migrations/` or `migrate/` directory,
   and which of those numbers `origin/main` has already used — the `0004`-versus-`0004` collision
   step 1b describes. **Regenerate a colliding migration here, from the merged schema**, before
   applying and never by renaming the file.

   Find the migrator from the repo rather than guessing it: the phase plans' exit criteria name it
   first (they were written against this tree), then `package.json` scripts matching `migrate`/`db:`,
   `drizzle.config.*`, `alembic.ini`, `prisma/`, `supabase/migrations/`, a `Makefile` target, the
   README's deploy section. Use the credentials the repo already carries — a `.env.production`, a
   deploy env var, whatever the migrate script itself reads. **Never invent a connection string,
   and never point a migrator at a database nothing in the repo names:** that is a stop, reported
   with what you looked for.

   - **Verify the objects, not the exit code.** Query the database for the tables, columns,
     indexes and enum values the migration claims to have created, and quote the answer in the
     termination block. A migrator that skips an entry silently exits 0.
   - **A destructive migration the plan prescribes is executed, not parked.** Dropping a column
     the plan says to drop is planned work, not an undecidable fork — but take what dump the
     tooling offers first (`pg_dump -t` of the affected tables into
     `.workflows/orchestration/<slug>/logs/`), and list it in `Decided without asking`. What
     *does* stop is a destructive step no phase plan asked for.
   - **A migration that will not apply stops the landing, and nothing is pushed.** That is the
     whole reason it runs before the push: `main` is untouched, the branch still holds the work,
     and the morning's job is one migration rather than a broken production.

5. **Push, then tell the peers.**
   ```bash
   python3 $S land --slug <slug> --step push
   ```
   A base that moved while you merged is re-merged and retried automatically, three rounds by
   default. Anything else — a protection rule, a missing permission, a rejecting hook — is
   reported once rather than hammered at; open the pull request and merge it with the tooling the
   repo already uses (`gh pr create --base main --head "$BR"` then `gh pr merge --merge`), and
   only if that is unavailable stop with the branch pushed and the reason named. `push` writes the
   merge sha into the ledger's `landed`, and **if a live coordinator handed you this set, tell it
   what landed** — it holds the record for the set and outlives your session's knowledge of it.

6. **`WARN` every peer whose cwd is inside the worktree, then delete the worktrees and the
   branch.** Their working directory is about to stop existing, and one of them may still be
   mid-write. Close the remaining windows first — a session inside a worktree that vanished is
   worse than a session closed:
   ```bash
   python3 $S reap --slug <slug> --include-failed
   python3 $S land --slug <slug> --step cleanup
   ```
   `cleanup` removes the land worktree and its branch, removes the set's worktree, and deletes the
   branch local and remote. **It refuses unless `git merge-base --is-ancestor` proves the branch
   is already in the base** — which is what makes it safe to run unattended: a stop at step 3, 4
   or 5 leaves the branch standing by construction rather than by remembering to. Pass
   `--keep-remote` when an open pull request still needs `origin/<branch>`. A worktree with
   uncommitted residue is force-removed and its `git status --porcelain` kept in `logs/`, since
   the ancestor check already proved the phases' work is on `main`.

   The set is over, so the failed phases' windows go too — their scrollback is in `logs/` and will
   outlive the tmux server. Anything `reap` refuses is a session that is genuinely busy; name it
   in the termination block rather than forcing it.

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
