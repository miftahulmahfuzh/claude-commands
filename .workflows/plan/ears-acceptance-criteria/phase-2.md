# Phase 2: Phase plans trace journeys to criteria

**Plan set:** `EARS_ACCEPTANCE_CRITERIA_PLAN.md`
**Analysis:** `.workflows/analyze/20261111-080843-E4RS_code_analyzer.md`
**Satisfies:** R2 — every phase plan Proof journey traces to one or more EARS criteria by id, so a requirement with no journey is a visible gap
**Criteria:** R2.1, R2.2
**Depends on:** none
**Difficulty:** NORMAL
**Package:** `agents`

---

## Goal

After this phase, `agents/phase-planner.md` takes the EARS criteria a phase owns as input, and
tells the planner to label every Proof journey `J{k}` and trace it to criterion ids in the exact
bullet form of the plan index's Invariant 1. A criterion with no journey becomes either a new
journey or an explicit `untraced` entry in the planner's return value. A legacy set (no criteria)
still plans exactly as before, except that journeys carry a `J{k}` label.

## Interface Contract

**Deletes:** the free-prose journey line in the planner's output format (`agents/phase-planner.md:130-131`, "Journeys: one per claim, each with the exact commands or steps file, …"), replaced by the traced bullet form
**Renames:** none
**Creates:**
- planner input key `criteria: [{id, text}]` (`agents/phase-planner.md`, Input block, after `satisfies`)
- phase plan header line `**Criteria:** R1.1, R1.2`, directly after `**Satisfies:**` (left out on a legacy set)
- journey bullet form, quoted verbatim from Invariant 1 and fixed: `  - **J{k}** · traces R1.1, R1.2 — <commands or steps> → passes when <observable end state>` (two leading spaces, nested under `- Journeys:`; separator ` · traces `; criterion ids joined by `, `; then ` — `, then ` → passes when `). The neighbor check stays its own `- Neighbor check:` bullet with no `J{k}` and no trace.
- planner return keys `criteria: [ids]`, `trace: {id: [J…]}`, `untraced: [ids]`
**Signature changes:** planner Input gains optional `criteria`; return value gains `criteria`, `trace`, `untraced` (all present; empty on a legacy set)
**Requires (from earlier phases):** none (no `depends_on`). At run time, phase 1 makes `/analyze` Step 7 pass `criteria:`; until it does, step 6's fallback reads the index's `### Acceptance Criteria` table.
**Leaves alone (owned by others):** `commands/analyze.md` (phases 1 and 3), `agents/plan-reconciler.md` + `skills/swarm/ears_trace.py` + its test (phase 3), `agents/verifier.md` and its dispatch sites (phase 4), `skills/swarm/swarm.py`, skills docs, README, CLAUDE.md, `docs/*`, `./sync.sh` (phase 5)

## Files

| File | Action | What changes |
|---|---|---|
| `agents/phase-planner.md` | modify | Input `criteria` (`:23`); step 6 trace rules (`:48-51`); new hard requirement (`:62-65`); `**Criteria:**` header (`:76`); journey bullet form (`:130-132`); return keys (`:162-164`) |

One file. Line numbers are from `origin/main` @ `7ab5aca`; this phase depends on nothing, so the
file is the same today and when this phase runs. Apply the steps top to bottom; each step's
**old** text occurs exactly once in the file, so match on the text, not the line number.

## Implementation Steps

### Step 1: Input takes the criteria this phase owns
**File:** `agents/phase-planner.md:23`
**Change:** add a `criteria:` line after the `satisfies:` line in the Input YAML.
**Old:**
```yaml
satisfies: [{requirement ids this phase serves, e.g. R1 — from the index's Requirements table}]
```
**New:**
```yaml
satisfies: [{requirement ids this phase serves, e.g. R1 — from the index's Requirements table}]
criteria: [{id: "R1.1", text: "WHEN <trigger> THE SYSTEM SHALL <behavior>"}]  # the EARS criteria this phase owns, from the index's Acceptance Criteria table; absent on a legacy set
```
**Impact:** none for a caller that does not pass it: step 6 falls back to the index, then to legacy.

### Step 2: Step 6 traces journeys to criteria
**File:** `agents/phase-planner.md:50-52` (end of step 6, before step 7)
**Change:** append the trace rules to step 6, after its last sentence.
**Old:**
```markdown
   anyway (run the CLI, read the row back, hit the endpoint) and say `no harness`.
7. Write `output_file`.
```
**New:**
```markdown
   anyway (run the CLI, read the row back, hit the endpoint) and say `no harness`.
   Then trace the journeys to `criteria`. If `criteria` is absent, take the rows of the index's
   `### Acceptance Criteria` table whose Phases cell names your phase number, ignoring any copy
   of the table inside a fenced code block (an index may quote the format as an example); if the
   index has no such table outside a fence, the set is **legacy** (see the end of this step).
   - Give every criterion at least one journey whose end state would be false if the criterion
     were not met. Label each journey `J{k}` (k counts from 1, in order, unique in this plan) and
     name the criterion ids it traces. One journey may trace several criteria.
   - Trace only ids you own. A journey that would prove another phase's criterion goes in
     **Handoffs**, naming that criterion, like a step that serves another phase's requirement.
   - If a criterion you own cannot be observed through anything this phase builds (it is only
     visible once a later phase lands), do not invent a journey for it. List it in `untraced` in
     your return value and say in **Handoffs** which phase can prove it.
   - Legacy set: label journeys `J{k}` but write them without `· traces …`, leave the
     `**Criteria:**` header line out, and return `criteria: []`, `trace: {}`, `untraced: []`.
7. Write `output_file`.
```
**Impact:** the planner now has a rule for R2.2 ("add one, or name the criterion as untraced"):
it adds a journey by default and reports `untraced` only for a criterion this phase cannot observe.

### Step 3: Hard requirement on the trace
**File:** `agents/phase-planner.md:65` (after the "Proof an agent can run" bullet, before "A user-facing change updates the feature map")
**Change:** insert one bullet.
**Old:**
```markdown
  stranger. For a bug fix, the first journey reproduces the bug and must fail before the fix.
```
**New:**
```markdown
  stranger. For a bug fix, the first journey reproduces the bug and must fail before the fix.
- **Every journey traces, every criterion is traced.** Each journey except the neighbor check
  traces at least one criterion you own, by id, in the journey bullet form of the output format.
  Every criterion you own is traced by at least one journey, or is listed in `untraced` with its
  reason in **Handoffs**. The plan-reconciler and the verifier read that bullet form
  mechanically, so do not reword it. A legacy set (no criteria) is the only exception: its
  journeys are labelled but trace nothing.
```
**Impact:** none on other files.

### Step 4: `**Criteria:**` header line in the output format
**File:** `agents/phase-planner.md:76`
**Change:** add the header line directly after `**Satisfies:**` in the output-format template (Invariant 1: "Header line after **Satisfies**").
**Old:**
```markdown
**Satisfies:** {requirement ids, e.g. R1} — the user-facing thing this phase serves
```
**New:**
```markdown
**Satisfies:** {requirement ids, e.g. R1} — the user-facing thing this phase serves
**Criteria:** {criterion ids this phase owns, e.g. R1.1, R1.2 — leave this line out on a legacy set}
```
**Impact:** phase 3's `ears_trace.py` reads this line; phase 4's verifier may read it.

### Step 5: Journey bullet form in the Verification template
**File:** `agents/phase-planner.md:130-132`
**Change:** replace the free-prose Journeys and Neighbor check lines with the traced form. The
backticked line is Invariant 1's journey form verbatim, including its two leading spaces. Keep
the separators exactly: middle dot `·` (U+00B7), em dash `—` (U+2014), arrow `→` (U+2192).
**Old:**
```markdown
- Journeys: one per claim, each with the exact commands or steps file, and the end state that
  passes it ("`GET /api/notes/<id>` returns tags `["beta"]`", not "it works")
- Neighbor check: the existing feature most likely to break, and its journey
```
**New:**
```markdown
- Journeys: one per claim and at least one per criterion in **Criteria**, one bullet per journey,
  written in exactly this form (the reconciler and the verifier parse it):
  `  - **J{k}** · traces R1.1, R1.2 — <commands or steps> → passes when <observable end state>`
  - **J1** · traces R1.1 — `curl -s localhost:3000/api/notes/42 | jq -c .tags` → passes when it prints `["beta"]` (an observable end state, not "it works")
  - **J2** · traces R1.1, R1.2 — `{exact commands or steps file}` → passes when {the observable end state}
- Neighbor check: the existing feature most likely to break, and its journey. A separate bullet,
  never labelled `J{k}`; it traces nothing
```
**Impact:** every phase plan written after deploy carries traced journeys. The two example
bullets are themselves in the parseable form, so a planner that copies them gets it right.

### Step 6: Return value reports the trace
**File:** `agents/phase-planner.md:162-164`
**Change:** add three keys after `proof:` and one paragraph after the YAML block.
**Old:**
````markdown
proof: "{harness name or 'no harness'}; {number of journeys}"
risks: ["..."]
```
````
**New:**
````markdown
proof: "{harness name or 'no harness'}; {number of journeys}"
criteria: ["R1.1", "R1.2"]                    # the criterion ids you own; [] on a legacy set
trace: {"R1.1": ["J1"], "R1.2": ["J1", "J2"]}  # each traced criterion -> the journeys that trace it
untraced: []                                  # owned criteria with no journey; each has its reason in Handoffs
risks: ["..."]
```

`trace` keys and `untraced` together are exactly `criteria`. `untraced` is empty unless step 6
sent a criterion to a later phase; the reconciler treats every id in it as a gap to close.
````
**Impact:** `/analyze` Step 7/8 and the reconciler receive the trace in the summary. Consuming
it is phase 1/3 work (see Handoffs). Nothing breaks if a consumer ignores the new keys.

## Principles applied

- Laziness protocol: one file, six anchored text insertions, no rewrite of the planner spec. The legacy path is "omit the traces", not a second output template.
- Make illegal states unrepresentable: the return value says `trace` keys plus `untraced` are exactly `criteria`, so a criterion cannot be silently dropped. It is either traced or named, which is what R2.2 asks for.
- Boundary discipline: criteria enter through one place, the `criteria` input, with one fallback (the index table rows for this phase). Step 6 decides legacy once, and the rest of the spec reads that decision.
- Build the lever: Proof J1 and J4 run the Invariant 1 regex over the template examples and over this plan, rather than trusting the format by eye. That is the same parse phase 3's `ears_trace.py` will run.

## Verification

**Build:** `cd /home/miftah/.worktrees/claude-commands/ears-acceptance-criteria && python3 skills/swarm/swarm.py selftest` (expects `selftest: all assertions passed`)
**Tests:** `cd /home/miftah/.worktrees/claude-commands/ears-acceptance-criteria && python3 skills/swarm/tests/test_plan_graph.py` (expects `test_plan_graph: all assertions passed`)
**Proof:** The edited planner spec is the artifact. Each journey greps or parses `agents/phase-planner.md` for the contract a planner will follow.
- Harness: `no harness` (`.claude/skills/verify-*` does not exist in this repo). Shell and Python 3 run against the edited file instead. Set `W=/home/miftah/.worktrees/claude-commands/ears-acceptance-criteria` first.
- Feature-map entries: none (no `features/` directory in this repo)
- Journeys:
  - **J1** · traces R2.1 — `grep -cF '**J{k}** · traces R1.1, R1.2 — <commands or steps> → passes when <observable end state>' $W/agents/phase-planner.md && python3 -c "import re,sys; t=open(sys.argv[1]).read(); rx=re.compile(r'^  - \*\*J(\d+)\*\* · traces (R\d+\.\d+(?:, R\d+\.\d+)*) — (.+) → passes when (.+)$', re.M); m=rx.findall(t); print(len(m), [x[0] for x in m]); sys.exit(0 if [x[0] for x in m]==['1','2'] else 1)" $W/agents/phase-planner.md` → passes when grep prints `1`, then python prints `2 ['1', '2']` and exits 0. That means Invariant 1's form is quoted verbatim, and the two template example bullets parse with the Invariant 1 regex.
  - **J2** · traces R2.1 — `grep -n '^criteria: \[{id: "R1.1"' $W/agents/phase-planner.md; grep -n -A1 '^\*\*Satisfies:\*\* {requirement ids' $W/agents/phase-planner.md | grep -F '**Criteria:** {criterion ids this phase owns'` → passes when the first grep prints one line inside the Input YAML (line 24), and the second prints the `**Criteria:**` template line immediately after the `**Satisfies:**` line.
  - **J3** · traces R2.2 — `grep -cE '^untraced: \[\]|List it in .untraced. in|or is listed in .untraced. with its|^trace: \{"R1.1": \["J1"\]|^criteria: \["R1.1", "R1.2"\]|.trace. keys and .untraced. together are exactly .criteria.' $W/agents/phase-planner.md` → passes when it prints `6`: the return keys `criteria`/`trace`/`untraced`, the step 6 rule, the hard requirement and the completeness sentence are all present.
  - **J4** · traces R2.1, R2.2 — `python3 -c "import re,sys; t=open(sys.argv[1]).read(); v=t.split('\n## Verification\n')[1].split('\n## Handoffs\n')[0]; rx=re.compile(r'^  - \*\*J(\d+)\*\* · traces (R\d+\.\d+(?:, R\d+\.\d+)*) — (.+) → passes when (.+)$', re.M); crit=re.search(r'^\*\*Criteria:\*\* (.+)$', t, re.M).group(1).split(', '); tr={}; [tr.setdefault(c,[]).append('J'+j) for j,ids,_,_ in rx.findall(v) for c in ids.split(', ')]; miss=[c for c in crit if c not in tr]; extra=[c for c in tr if c not in crit]; print(crit, tr, miss, extra); sys.exit(1 if miss or extra else 0)" $W/.workflows/plan/ears-acceptance-criteria/phase-2.md` → passes when it prints `['R2.1', 'R2.2'] {'R2.1': ['J1', 'J2', 'J4', 'J5'], 'R2.2': ['J3', 'J4']} [] []` and exits 0. It parses only the `## Verification` section, because the Step 5 code block above holds template example bullets. This plan, written in the new format, traces every owned criterion and nothing else.
  - **J5** · traces R2.1 — `grep -c 'Legacy set: label journeys .J{k}. but write them without' $W/agents/phase-planner.md; grep -c 'never labelled .J{k}.; it traces nothing' $W/agents/phase-planner.md` → passes when both print `1`: the legacy fallback and the untraced neighbor check are both specified.
- Neighbor check: the planner spec's existing contract must survive. `cd $W && git diff --name-only origin/main -- agents commands skills && grep -c '^## Interface Contract$\|^\*\*Deletes:\*\*\|^\*\*Requires (from earlier phases):\*\*\|^proof: "' agents/phase-planner.md && python3 skills/swarm/swarm.py selftest && python3 skills/swarm/tests/test_plan_graph.py`. Passes when the diff lists `agents/phase-planner.md` and no other file except ones owned by a phase that has already landed on this branch (e.g. `commands/analyze.md` from phase 1), the grep prints `4`, and both checks print `all assertions passed`.
- Cost: none (no LLM turns; greps and stdlib Python only)

**Exit criteria:** `agents/phase-planner.md` takes `criteria` as input. Its output format shows the `**Criteria:**` header after `**Satisfies:**` and journeys in Invariant 1's `**J{k}** · traces R…` bullet form. Its hard requirements forbid an untraced journey (other than the neighbor check) and an owned criterion with neither a journey nor an `untraced` entry. Its return value carries `criteria`, `trace` and `untraced`. J1–J5 and the neighbor check pass, and this phase's commit changes only `agents/phase-planner.md`.

## Handoffs

- **Phase 1 (R1, criterion R1.3):** `/analyze` Step 7 must pass `criteria: [{id, text}]` in each planner's input, with exactly that key name and shape. Until it does, step 6's fallback reads the index's `### Acceptance Criteria` rows whose Phases cell names the phase.
- **Phase 3 (R3):** `ears_trace.py` must parse the journey bullet form exactly as quoted in the Interface Contract. J1/J4 above use the reference regex: `^  - \*\*J(\d+)\*\* · traces (R\d+\.\d+(?:, R\d+\.\d+)*) — (.+) → passes when (.+)$` (multiline). A journey without `· traces …` (legacy) does not match it, and the parser should treat such a plan as untraced or legacy rather than error. The `**Criteria:**` line is `^\*\*Criteria:\*\* (.+)$`, ids joined by `, `. Phase 3 also decides whether the reconciler consumes the planner's `untraced`/`trace` return keys or re-derives them from the plan files. Either works, because the return keys are a mirror of the file.
- **Phase 3 (R3):** `/analyze` Step 7/8's handling of a non-empty `untraced` return (closing the gap per R3.2) belongs to phase 3, not here.
- **Phase 4 (R4):** the verifier reads journeys by `J{k}` and their traced ids from this form. The global id `P{phase}.J{k}` (Invariant 1) is composed by the reader. Planners write only the local `J{k}`.
- **Phase 5 (R5):** README / CLAUDE.md / architecture-notes wording for "phase plans trace journeys to criteria"; `./sync.sh`.
- **Reconciler note (resolved):** the index's Phase 2 summary now names `criteria`, `trace` and `untraced`, matching this plan; `criteria_traced` is gone. No phase consumes these keys mechanically: the reconciler and `/analyze` Step 9 re-derive the trace from the plan files with `ears_trace.py`, so the keys are a mirror for the summary. A criterion returned in `untraced` (only observable after a later phase) is closed under the trace rule by moving it to the phase named in Handoffs.

## Rollback

`git revert <phase 2 commit>`. It touches only `agents/phase-planner.md`, so it reverts cleanly
on its own. Planners then go back to untraced journeys, and phases 3/4 fall back to their
legacy paths for any plan written afterwards. No deploy happened (`./sync.sh` is phase 5), so
`~/.claude/` needs nothing.
