# Leave-behinds — swarm-write-set-gate

Raised by phase 1 after it landed; decided by the coordinator, not forwarded to the user.
None is in the plan's Scope list, so none is this set's to fix. Each wants its own card.

| # | Item | Decision | Rung |
|---|---|---|---|
| L1 | `README.md:171-175` lists the orchestrator's refusal conditions; phase 3 adds exits 1 and 2 plus `--no-gate`, and no phase owns those lines. Phase 1 offered phase 2 (sole `README.md` writer) as a cheap absorber. | **Do not absorb — card it.** Phase 2 and phase 3 are CONCURRENT in wave 1, so phase 2 would be documenting text phase 3 has not written yet. That is exactly reconciliation conflict class 1 (stale quote), which cost this set a whole round to eliminate; re-creating it to save a card is a bad trade. | 4 — the index's Requirements table (R2 is phase 3's alone) and Scope ("`README.md` — only if a new indexed asset is introduced") |
| L2 | `CLAUDE.md:11` reads "There is no lint, no test runner, no CI." Phase 1 made a test harness load-bearing (invariant 7), so the line is now false. | **Card it.** `CLAUDE.md` is not in Scope and no phase owns it. A second writer in a file no phase declared would break the hand-declared write-set table's single-writer rows. | 4 — the index's Scope section is explicit about what is in and out |
| L3 | `CLAUDE.md`'s swarm section never mentions `plan_graph.py` at all, including the phase-plan-structure coupling that mirrors the `parse_index` warning already documented there. | **Card it, with L2** — same file, same reason. Worth one card covering both. | 4 — as L2 |
| L4 | `SKILL.md:46-49`'s "measured against four real plan sets" counts may have moved under most-severe-wins. Phase 1 flagged it as LOW CONFIDENCE and unverified: those measurements are against repos not reachable from this worktree. | **Card it, do not guess.** The lines sit in the unowned four-line gap between phase 2's region (>= 39) and phase 3's (32-34), so no phase can touch them without breaking the ISOLATE margin that reconciliation measured at ONE line. Re-measuring needs the other repos. | 6 — surrounding convention: this set does not edit what it cannot verify |

**Not a leave-behind, already decided in the plan:** `spawn --isolate` at
`analyze-orchestrator.md:237,255,383` instructs a flag that does not exist. The index's Decisions
table recorded it as a leave-behind wanting its own card; the coordinator re-verified it this run
(`grep -c isolate ~/.claude/skills/swarm/swarm.py` = 0) and used `git worktree add` + `spawn --cwd`
for wave 1 instead, which worked.

## L5 — reported by a peer coordinator, 2026-10-27

**The write-set gate cannot see an index-base collision, and should say so.**

`orch-planner-malformed-json-no-answer` MEASURED this in
`~/.worktrees/agentic_golang/planner-malformed-json-no-answer`, phases 3 and 4 concurrent in one
SHARED worktree: phase 3 committed through a private `GIT_INDEX_FILE` — the recipe the swarm skill
recommends — and it worked, its commit held exactly its own six files. But committing from a
private index leaves the **shared** index still built against the OLD HEAD, so `git diff --cached`
then showed a staged *revert* of all six files plus a delete. A peer running a bare `git commit` in
that window would have shipped a revert of phase 3 under its own message. Repaired index-only with
`git read-tree HEAD` (no `-u`); peers' dirty files verified intact.

Why it matters to THIS set: the collision is not over a path, it is over the index's **base
commit**, so path-ownership analysis is structurally blind to it. That peer's own `plan_graph` run
reported `0 of 2 shared files written concurrently` and was *correct*. This is a boundary of what
the gate can promise, and the gate's prose does not currently state it.

**Decision: card it, do not absorb.** Rung 4 — the index's Scope section. Two reasons, either
sufficient: (a) the mitigation lives in `swarm.py`/SKILL.md commit-hygiene prose, and "`swarm.py`
behaviour changes" is explicitly Out of scope; (b) `SKILL.md`'s regions are fully owned by phases 2
and 3 right now with a measured **one-line** margin, so inserting a limitations section mid-wave
would break the exact ISOLATE verdict this set exists to make trustworthy.

**This set is not exposed.** Verified 2026-10-27: wave 1 runs ISOLATED, one worktree per phase, and
each worktree carries its own index file
(`.git/worktrees/swarm-write-set-gate{,-p2,-p3}/index`) — all four indexes clean at the time of
checking. Phase 1 ran alone in the shared worktree with no concurrent peer. The hazard needs a
shared index, which this set does not have. Wave 1 was deliberately NOT warned about it: it does not
apply to them, and interrupting two running phases with an inapplicable hazard is pure cost.

The card should carry the mitigation verbatim: after any private-index commit in a shared worktree,
run `git read-tree HEAD`; before any commit, check `git diff --cached --stat` and repair
**index-only** if it lists files you do not own. Never `reset --hard` / `checkout .` / `restore .`
for this — that is the separate measured failure already documented in the skill.

## L6 — peer design note on the clean verdict, 2026-10-27

`orch-planner-malformed-json-no-answer` independently corroborated phase 1's fix against a
different repo (`agentic_golang`, 4-phase set): with the fixed copy installed, the gate resolves
natively from inside a worktree and reproduces byte for byte the result they had previously only
obtained via a symlink workaround — phases 3/4/6/5 files, two shared paths, both sequential,
0 of 2 concurrent. Three of their four phases have since landed with each commit's file list matching
its declared write set exactly. That is external validation of R1 on a repo this set cannot reach.

**Their suggestion:** make the verdict state its own coverage — `clean (4/4 plans read)` rather
than a bare `no file is written by two phases.` "A verdict that states its own coverage is hard to
misread; an exit code is not."

**Decision: card it — but note it is most of the way delivered already.** Rung 2, phase exit
criteria. Phase 1 already made the INCOMPLETE case state coverage verbatim:
`INCOMPLETE: no collision among the 0 of 2 phases whose plan could be read. 2 write sets are
unknown, so this is not an all-clear.` The only gap is the CLEAN case, which still prints the bare
sentence — and that string is pinned byte-for-byte by phase 1's own contract and by phase 3's exit
criterion 7b, both of which quote it. Changing it mid-wave would break a measured, reconciled
contract between all three phases while two of them are running. The card is: add a coverage count
to the clean verdict in a later set, updating all three quoting sites together.

**CORRECTION to the peer's report, measured here rather than accepted.** They recalled "the exit
code was 0 and the headline verdict read clean". The exit code was **1**, not 0. Measured on the
old gate (`55e51ae`) against a set whose phase plans cannot be resolved:

    no file is written by two phases.
    OLD EXIT=1

So the old gate's exit code was *correct all along*; it was the VERDICT TEXT that lied. This makes
their point stronger, not weaker, and it relocates the fix: a caller honouring exit 1 would have
refused their blind run even before phase 1 existed. **That is exactly R2, and exactly what phase 3
is shipping.** The information was present in the exit code and nobody acted on it — which is the
one-sentence case for making the gate a gate.

Post-phase-1, the same blind case prints the INCOMPLETE form and still exits 1, so text and exit
code now agree.

**Observed in passing:** the installed gate already carries phase 2's in-progress work
(`artifact classes: baseline + .gitattributes (no .workflows/swarm.json)` appears in
`~/.claude/`), confirming phase 2 has run `./sync.sh` from its isolated worktree. This is the
transient sync collision the coordinator predicted and recorded in the phase 2/3 ledger notes. It
means any measurement taken against `~/.claude/` during wave 1 must be attributed carefully; the
measurements above were re-run against the set worktree at 2773a34 (phase 1 only) to keep the
attribution honest.

## L7 — `swarm.py cmd_track` does not re-include `.workflows/swarm.json`

Reported by phase 2. `cmd_track` re-includes only `.workflows/orchestration/`, so in a repo that
gitignores `.workflows/` broadly, phase 2's new per-repo config file works locally but does not
travel to other machines or other clones. **Card it.** `swarm.py` behaviour changes are explicitly
Out of scope for this set; phase 2 documented the manual `!.workflows/swarm.json` remedy in
SKILL.md, and it measured that no repo on this machine needs it today. Rung 4 — the index's Scope.

## L8 — ledger keeps the Package cell's backticks

Reported by phase 3: its phase was recorded with package ``commands`, `skills/swarm`` because
`parse_index` keeps the backticks from the Package cell. Cosmetic, lives in `swarm.py`, out of
scope. **Card it** alongside L7 — same file, same follow-up.

---

# Wave 1 — decisions the phases made without asking

Collected from both phases' completion reports. These are the morning's review queue.

**Phase 2 (`P1-CL-A022`, 2b8b95e)**
1. `_match`'s docstring shipped `web/data/lab.json` as a path example, contradicting the phase's own
   exit criterion that the seer grep over `plan_graph.py` return nothing. Replaced with
   `data/snapshot.json` — identical length, no test asserts on the docstring. **Rung 2** (exit
   criteria) over **rung 3** (the plan's code block).
2. `readme-updater` not dispatched. The hand-declared write-set table lists exactly 5 files and no
   `package_readme.md`; creating one would add a sixth, unowned file to a live wave. **Rung 4**,
   plus "never widen scope to settle an ambiguity."

**Phase 3 (`P1-CL-A023`, 0a54f90)**
1. Step 3b's prompt disclaimer named `AskUserQuestion` and `[y/N]` literally in the plan's code
   block, but the phase's exit criterion 3 forbids those spellings anywhere in Step 3b and its
   verification check greps for them expecting no match — **the plan contradicted itself.**
   Reworded to name no prompt primitive literally. **Rung 2**: exit criteria outrank a code block's
   wording.
2. SKILL.md keeps the plan's literal `AskUserQuestion` / `[y/N]` wording — no criterion forbids them
   there, and changing it for symmetry would be scope creep. **Rung 3**.
3. `readme-updater` skipped — no `package_readme.md` exists and `README.md` is phase 2's sole-writer
   file. **Rung 2/3**. (Both phases reached this independently.)
4. **Re-measured the ISOLATE margin rather than trusting it.** git rendered phase 3's SKILL.md edit
   as an insertion after old line 35 (`@@ -35,0 +36,20 @@`), not as a replacement of 32-34 — a
   different shape from the one the reconciler measured, narrowing the one-line margin. Phase 3
   rebuilt phase 2's side from its plan and re-ran `git merge-file`: rc=0, zero conflict markers,
   all three edits present, old 35-38 byte-identical. **Rung 1**: the phase plan's standing
   instruction to re-run the check if the margin is in question.
   *Coordinator note:* that measurement used phase 2's PLAN, not its commit. The `integrator` is
   the first to merge the two real commits, and is instructed to report whether 35-38 survived.

**Coordinator**
- `**Status:**` on index line 9 reads `phase 1/3 complete`. Phase 3 deliberately left it alone:
  phases 1 and 3 were done but 2 was not, any ordinal would mislead, and it is the one line phase 2
  would also rewrite — two writers on a field the index itself calls non-authoritative ("the
  authoritative phase status is the swarm ledger"). **Correct call.** The coordinator sets it once
  after integration, when the ordinal is finally true.

## L9 — the documented invocation must not discard the exit status

`orch-planner-malformed-json-no-answer` traced its own misreport to this command:

    python3 plan_graph.py <PLAN> 2>&1 | grep -v 'command not found'; echo "EXIT=$?"

`$?` after a pipeline is **grep's** status, not `plan_graph`'s. The caller destroyed the signal on
its way to being read and then fell back on the prose — which was the half that lied. So the blind
run lost its exit code twice over: once to the pipe, once to a verdict text that read clean.

*(This coordinator hit the same trap earlier in this session and caught it, re-running with
`>/dev/null 2>&1; echo $?` to get the true code. It is an easy mistake and a shell on this machine
prints noise into stderr that invites exactly the offending `| grep`.)*

**VERIFIED: the defect is NOT in what phase 3 shipped.** Both invocations in its Step 3b are bare,
with no trailing pipe:

    python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md>           # 0 clean · 1 unreadable · 2 collision
    python3 ~/.claude/skills/swarm/plan_graph.py <PLAN.md> --json    # the per-collision class, for deciding

`grep -n 'plan_graph.*|'` over the file returns nothing. R2's exit criteria are satisfied as built.

**Decision: card it, do not amend mid-integration.** Rung 2 — R2's exit criteria are met and the
shipped commands are correct; adding a prophylactic "never pipe this, `$?` becomes grep's" note is a
docs improvement, not a correctness fix, and it would put a second writer into
`commands/analyze-orchestrator.md` while the `integrator` is merging that very file. Card it with
L6: both are the same idea — **the verdict must be hard to misread, and so must the status.**

## L5 update — the index hazard is deterministic, not a race

Same peer, after it hit the hazard a SECOND time in a different session on an unrelated file set
(its phase 3's completion-handler reproduced it exactly: a staged revert of precisely its own two
doc files). Mechanism, now firm: committing from a private `GIT_INDEX_FILE` moves HEAD while the
shared index still points at the old tree, so the shared index **necessarily** reads as "revert
everything that commit contained" until refreshed. Two occurrences, two sessions, same shape.

That upgrades the card from "a measured race" to "a deterministic consequence of the recommended
recipe", which is a much stronger reason to document `git read-tree HEAD` as a required follow-up
step rather than a tip. Still out of scope here (`swarm.py` / shared-worktree prose), still carded.
