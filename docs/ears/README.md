# EARS acceptance criteria

Borrowed from [Kiro specs](https://kiro.dev/docs/specs/concepts), which write requirements in
**EARS** (Easy Approach to Requirements Syntax): short, fixed-shape sentences like "WHEN <trigger>
THE SYSTEM SHALL <behavior>". We reshaped the idea to fit the `/analyze` → orchestrator →
`/implement` pipeline.

- [Why](#why)
- [The shape](#the-shape)
- [What each stage does with it](#what-each-stage-does-with-it)
- [`ears_trace.py`](#ears_tracepy)
- [Legacy plan sets](#legacy-plan-sets)
- [Changing the format](#changing-the-format)

## Why

Before this, a plan index's Requirements table held one paraphrased line per ask (`R1`, `R2`,
…), and a phase plan's Proof journeys were prose with no link back to any of them. Two agents
had to work from that prose and use their own judgement:

- **`plan-reconciler`** could check that every `R` had a phase. It could not check that every
  `R` had a *proof*, so a requirement no journey exercised was invisible until review.
- **`verifier`** returned one verdict per phase. "Phase 3 failed" did not say which promise
  broke.

EARS splits each ask into numbered, checkable statements. Those ids then run through every
stage, so each stage can ask a yes/no question about each one.

## The shape

The plan index's `## Requirements` section now holds two tables. The **R table** stays at the
level of what you asked for, word for word, because your reasons are the spec. `create-task`
still builds cards from it. Beneath it, the **Acceptance Criteria** table splits each `R` into
criteria `R{n}.{m}`:

```markdown
## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | add a "Coba ulang" button so an empty reading can be refilled | 3, 4 |

### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | event | WHEN the user taps Coba ulang on an unfinished reading THE SYSTEM SHALL refill it in place | 3 | P3.J1 |
| R1.2 | unwanted | IF the refill request fails THEN THE SYSTEM SHALL keep the reading and show the error | 4 | P4.J2 |
```

Six patterns, named in the Pattern column:

| Pattern | Form |
|---|---|
| `ubiquitous` | THE SYSTEM SHALL … |
| `event` | WHEN <trigger> THE SYSTEM SHALL … |
| `state` | WHILE <state> THE SYSTEM SHALL … |
| `unwanted` | IF <unwanted condition> THEN THE SYSTEM SHALL … |
| `optional` | WHERE <feature> THE SYSTEM SHALL … |
| `complex` | a combination, e.g. WHILE … WHEN … |

Each phase plan names the criteria it owns, and labels every Proof journey with the criteria it
proves:

```markdown
**Satisfies:** R1
**Criteria:** R1.1

- Journeys:
  - **J1** · traces R1.1 — <commands> → passes when <observable end state>
- Neighbor check: <the feature most likely to break, and its journey>
```

The separators are exact (`·` U+00B7, `—` U+2014, `→` U+2192), because a script parses them.
A journey's global id is `P{phase}.J{k}`, which is what fills the table's Journeys column.

## What each stage does with it

| Stage | Before | After |
|---|---|---|
| `/analyze` Step 0 | one paraphrased line per `R` | the verbatim ask, plus EARS criteria `R{n}.{m}` |
| `/analyze` Step 7 | planner told which `R` it serves | planner also handed the id and text of every criterion it owns |
| `phase-planner` | Proof journeys in prose | one `**J{k}** · traces …` journey per criterion; an unprovable one is returned as `untraced` |
| `plan-reconciler` | checked every `R` has a phase | also checks every criterion has an owning phase **and** a tracing journey, with a script |
| `/analyze` Step 9 | — | runs the same trace check, N = 1 included, and fills Journeys |
| `verifier` | one verdict per phase | one verdict per criterion id, with evidence or a repro |
| Morning review | "phase 3 failed" | "R3.2 failed: here's what was observed, here's the repro" |

**The trace rule**, stated identically in `/analyze` Step 8 and `plan-reconciler` rules 6–7:

- owned but untraced → edit the owning phase plan and add a journey;
- owned by a phase that cannot observe it → move it to the later phase that can, and add the
  journey there;
- unowned → assign it to the phase that satisfies its `R`;
- only a criterion that **no** phase can own goes to `## Open Questions`. That stops the
  unattended launch, so it should be rare.

**The verifier's verdict rule:** a criterion is `verified` only if at least one journey traces it
and every tracing journey passed with evidence. `failed` if any failed. Otherwise
`inconclusive`. An untraced criterion is `inconclusive: no journey`, never `verified`. Failed
criterion ids go first in the swarm ledger's `--note` and into `/implement`'s fix loop.

## `ears_trace.py`

```bash
python3 ~/.claude/skills/swarm/ears_trace.py <PLAN.md>          # 0 clean or legacy · 1 unreadable · 2 gaps
python3 ~/.claude/skills/swarm/ears_trace.py <PLAN.md> --json   # machine form
python3 ~/.claude/skills/swarm/ears_trace.py <PLAN.md> --fill   # R1.1 -> P1.J1, P2.J3, for the Journeys column
python3 skills/swarm/tests/test_ears_trace.py                   # 9 cases, stdlib only
```

It sits beside `plan_graph.py` and shares its exit-code contract and `find_root`, so a linked
worktree resolves the same way in both. It is read-only. It reports five kinds of gap:

| Gap | Meaning |
|---|---|
| `unowned` | no phase in the criterion's Phases cell, and no plan claims it |
| `untraced` | some phase owns it, no journey traces it |
| `unknown_id` | a journey or `**Criteria:**` line names an id the table lacks |
| `misassigned` | a plan claims a criterion the table does not give it |
| `unclaimed` | the table gives a criterion to a phase whose `**Criteria:**` line omits it |

Every reader skips fenced code blocks. A plan that *quotes* the format, as this feature's own
plans did, must not be read as using it. Without the skip, its own index read as 16 criteria
instead of 14.

## Legacy plan sets

An index with no `### Acceptance Criteria` heading is **legacy**, which covers every set written
before 2026-11-11. Nothing breaks:

- `ears_trace.py` exits 0 with a `legacy` line;
- the verifier falls back to reading Proof prose per phase and returns `criteria: legacy`;
- `/implement`, `/do` and `swarm.py` never depended on criteria. `parse_index` returns the same
  phases either way, and `_ids` reduces `R2.1` to `R2` and dedupes, so the Satisfies column
  stays at R level.

## Changing the format

The criteria table and the journey bullet form are one contract with five readers. Change
`commands/analyze.md`, `agents/phase-planner.md`, `agents/plan-reconciler.md`,
`agents/verifier.md` and `skills/swarm/ears_trace.py` together, then run `test_ears_trace.py`
and `swarm.py selftest`.

Built by the plan set `feature/ears-acceptance-criteria` (5 phases, landed at `74e7885`), which
was itself written in this format: 14 criteria, every one owned and traced.
