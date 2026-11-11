# Phase 3: Reconciler enforces the trace (+ ears_trace.py)

**Plan set:** `EARS_ACCEPTANCE_CRITERIA_PLAN.md`
**Analysis:** `.workflows/analyze/20261111-080843-E4RS_code_analyzer.md`
**Satisfies:** R3 — plan-reconciler checks that every criterion has an owning phase and a Proof journey, fixes an untraced one by editing the plans, and parks only an unownable one
**Criteria:** R3.1, R3.2, R3.3
**Depends on:** Phase 1, 2
**Difficulty:** HARD
**Package:** `skills/swarm`

---

## Goal

After this phase the EARS trace is mechanical. A new read-only script, `skills/swarm/ears_trace.py`,
reads the index's `### Acceptance Criteria` table, the phase table and every phase plan's
`**Criteria:**` line and `**J{k}** · traces …` journeys, and reports each criterion that is unowned,
untraced, misassigned, unclaimed or names an unknown id (exit 0 clean or legacy, 1 unreadable,
2 gaps). `--fill` prints the Journeys column. `agents/plan-reconciler.md` builds its criterion
ledger from the script, fixes gaps under one written **trace rule**, fills the Journeys column, and
requires exit 0 to finish. `/analyze` Step 8 states the same trace rule word for word, and the
Step 9 verification runs the script for N = 1 as well.

## Assumptions (from phases 1 and 2, which land first)

- **Phase 1** has rewritten `commands/analyze.md` Steps 0/3/6/7, the N = 1 paragraph of Step 9
  (it now fills the Journeys column by hand from `phase-1.md` and keeps `—` for an untraced
  criterion, "for the verification below"), the templates and the termination block. Phase 1
  left **Step 8** and Step 9's two verification paragraphs ("Before terminating, verify …" and
  "**And verify the two decision sections.**") byte-identical to `7ab5aca`. Phase 1 shifts line
  numbers by about +54 at Step 8 (`:370` → `~:424`) and +61 at "Before terminating" (`:414` →
  `~:475`). **Every edit below to `commands/analyze.md` anchors on text, not line numbers.**
- **Phase 2** has made `agents/phase-planner.md` write `**Criteria:** R1.1, R1.2` directly after
  `**Satisfies:**`, and journeys as `  - **J{k}** · traces R1.1, R1.2 — <commands> → passes when
  <end state>` under `- Journeys:` in `## Verification`; the neighbor check traces nothing. The
  script parses exactly that (Invariant 1).
- `skills/swarm/swarm.py` is unchanged by this phase. `parse_index` already identifies the phase
  table by a header whose first cell is `#` and that contains `title` and `plan`, so the criteria
  table (first cell `ID`) is never read as phases — `test_clean` asserts it.

## Interface Contract

**Deletes:** none
**Renames:** none
**Creates:**
- `skills/swarm/ears_trace.py` — CLI `python3 ears_trace.py <PLAN.md> [--json] [--fill]`; exit
  `0` clean or legacy · `1` unreadable (no index, no phase table, a criteria heading with no table,
  a phase plan the index names is missing) · `2` at least one gap. Module functions: `build(index_path) -> dict`,
  `parse_criteria(text) -> list | None`, `parse_plan(text) -> (claims | None, journeys)`,
  `render(g)`, `render_fill(g)`, `exit_code(g)`, `main()`.
  `build()` keys: `index`, `slug`, `legacy`, `root`, `phase_count`, `criteria[]` (`id`, `pattern`,
  `criterion`, `phases`, `journeys_cell`, `index_phases`, `claimed_by`, `owners`, `journeys`,
  `fill`), `gaps[]` (`kind` ∈ `unowned|untraced|unknown_id|misassigned|unclaimed`, `id`,
  `detail`, optional `phase`, `phases`, `journey`), `missing_plans[]`, `fill` (`{id: "P1.J1, P2.J3" | "—"}`).
  On a legacy index: `{index, slug, legacy: true}` only. On error: `{error}` only.
  `--fill` stdout: one line per criterion, `R1.1 -> P1.J1, P2.J3` (`—` when untraced); legacy prints
  the `legacy: …` line; `--fill --json` prints the `fill` map.
- `skills/swarm/tests/test_ears_trace.py` — 9 stdlib cases.
- A named paragraph, **The trace rule.**, present byte-identical (modulo line wrapping and
  indentation) in `agents/plan-reconciler.md` rule 7 and `commands/analyze.md` Step 8.
- `plan-reconciler` return value gains `criteria_map` and `trace`.
**Signature changes:** none
**Requires (from earlier phases):** the index's `### Acceptance Criteria` table and the phase-plan
`**Criteria:**` / `**J{k}** · traces` formats exactly as Invariant 1 (phases 1, 2); `commands/analyze.md`
Step 8 and Step 9's two verification paragraphs untouched by phase 1 (phase 1's J5 proves it).
Imports `swarm.parse_index` and `plan_graph.find_root` unchanged.
**Leaves alone (owned by others):** `skills/swarm/swarm.py` and `skills/swarm/SKILL.md` (phase 5 —
SKILL.md documents this script there); `agents/phase-planner.md` (phase 2); `agents/verifier.md`
and its dispatch sites (phase 4); `commands/analyze.md` Steps 0/3/6/7, the N = 1 paragraph of
Step 9 (including its `--fill` sentence), the analysis template, the index template's
`## Requirements` section and the termination block's `Requirements:` lines (phase 1); `README.md`, `CLAUDE.md`, `docs/*`
(phase 5). No `./sync.sh` (Invariant 6).

## Files

| File | Action | What changes |
|---|---|---|
| `skills/swarm/ears_trace.py` | create | the read-only trace checker (whole file, Step 1) |
| `skills/swarm/tests/test_ears_trace.py` | create | its stdlib regression tests (whole file, Step 2) |
| `agents/plan-reconciler.md` | modify | Step 1 ledger `:27-34`; conflict rows after `:49`; rule 6 `:73-75`; rule 7 `:79-84`; finalize `:94-95`, `:101-102`; verify `:107-109`; return `:113-122` |
| `commands/analyze.md` | modify | Step 8 "It checks" list, "Then it rewrites" line and item 3 (`:385-402` before phase 1, `~:439-456` after); Step 9 verification paragraphs (`:414-422` before phase 1, `~:475-483` after); the four other statements of the Open Questions residue — contract bullet `:161`, Step 11 refusal bullet `~:533`, index template `## Open Questions` comment `~:786`, termination comment `~:885` (Step 11) — all anchored by text |

## Implementation Steps

### Step 1: Create the trace checker
**File:** `skills/swarm/ears_trace.py` (new, mode 0755 like `plan_graph.py`)
**Change:** Write the whole file below. It imports `parse_index` from `swarm` and `find_root` from
`plan_graph` — reuse, not copies, so a linked worktree resolves the way the write-set gate resolves
it. Every reader of a plan skips fenced code blocks (CommonMark: a fence closes only on the same
character with at least the opening length), because the very index of this feature quotes the
criteria table in a fenced example under Invariants; read naively, that example added two phantom
criteria and a phantom owner (measured while planning: `criteria: 16` instead of 14).
**Code:**
````python
#!/usr/bin/env python3
"""The EARS trace of a plan set: is every acceptance criterion owned by a phase and proved by a journey?

`/analyze` writes, under the plan index's `## Requirements`, an `### Acceptance Criteria`
table -- one EARS row per criterion id `R{n}.{m}`, naming the phases that own it. Each
phase plan names the criteria it owns on a `**Criteria:**` header line and labels every
Proof journey `**J{k}** · traces R{n}.{m}, ...`. A criterion no phase owns, or one no
journey traces, is a requirement nobody will prove -- and until this script the only
thing that would notice was a model reading prose. This reads the same three sources
mechanically:

  * the index's criteria table, found by HEADER NAME (first cell `ID`, plus `Criterion`
    and `Journeys`), never by position -- the R table above it also starts with `ID`
  * the phase table, through `swarm.parse_index`, the one parser every swarm tool shares
  * each phase plan's `**Criteria:**` line and the journey bullets in its
    `## Verification` section, skipping fenced code blocks, so a plan that QUOTES the
    format (the phase that defines it does) is not read as using it

Phase plans are located the way `plan_graph.py` locates them -- its `find_root` is
imported, not copied, so a linked worktree resolves here exactly as it does there.

It reports five kinds of gap:

  unowned      a criterion with no phase in its Phases cell and no plan claiming it
  untraced     a criterion some phase owns that no journey in any plan traces
  unknown_id   a journey, or a `**Criteria:**` line, naming an id the table lacks
  misassigned  a plan claiming a criterion the index's Phases cell does not give it
  unclaimed    the index giving a criterion to a phase whose `**Criteria:**` line omits it

`--fill` prints the value of each row's Journeys cell (`R1.1 -> P1.J1, P2.J3`), which the
reconciler (N > 1) or `/analyze` Step 9 (N = 1) writes into the index. This script never
writes it: read-only, it spawns nothing and writes nothing.

A LEGACY index -- no `### Acceptance Criteria` heading, i.e. every plan set written
before EARS -- has nothing to trace. That is exit 0 with a `legacy` line, never an
error: the sets already on disk must keep executing.

Exit codes, the same contract as `plan_graph.py`:
  0  clean, or legacy
  1  unreadable: no index, no phase table, a criteria heading with no table, or a phase
     plan the index names is missing (the trace is then incomplete, never an all-clear)
  2  at least one gap
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swarm import parse_index  # noqa: E402
from plan_graph import find_root  # noqa: E402

CRITERIA_HEADING = re.compile(r"^###\s+Acceptance Criteria\s*$")
CRITERION_ID = re.compile(r"R\d+\.\d+")
CRITERIA_LINE = re.compile(r"^\*\*Criteria:\*\*\s*(.*?)\s*$")
# `  - **J2** · traces R1.1, R1.2 — <commands> → passes when <end state>`. Only the run
# of ids straight after `traces` counts: the commands that follow may mention ids too.
JOURNEY = re.compile(
    r"^\s*[-*]\s+\*\*J(\d+)\*\*.*?\btraces\s+"
    r"(R\d+\.\d+(?:(?:\s*,\s*|\s+and\s+)R\d+\.\d+)*)"
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
H2 = re.compile(r"^##\s+(.+?)\s*$")
NONE = "—"


def _key(cid):
    """Sort key for `R{n}.{m}`: numeric, so R10.1 follows R9.2 and R1.10 follows R1.9."""
    n, m = cid[1:].split(".")
    return int(n), int(m)


def _ids(text):
    return sorted(set(CRITERION_ID.findall(text or "")), key=_key)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _separator(cells):
    return all(set(c) <= set("-: ") for c in cells)


def _unfenced(text):
    """The lines of `text` outside fenced code blocks.

    A plan index QUOTES the format it is written in: this very feature's index carries
    the criteria table as a fenced example under its Invariants, and read naively that
    example added two phantom criteria and a phantom owner to the real table. A fence
    closes only on the same character, at least as long as the one that opened it
    (CommonMark), so a ```` block quoting a ``` block, or a ~~~ block quoting one, does
    not end early.
    """
    fence = None
    for line in text.splitlines():
        hit = FENCE.match(line)
        if hit:
            mark = hit.group(1)
            if fence is None:
                fence = mark
                continue
            closes = (mark[0] == fence[0] and len(mark) >= len(fence)
                      and not line.strip()[len(mark):].strip())
            if closes:
                fence = None
                continue
        if fence is None:
            yield line


def parse_criteria(text):
    """[{id, pattern, criterion, phases, journeys_cell}] from the Acceptance Criteria table.

    None when the index has no `### Acceptance Criteria` heading outside a code fence -- a
    legacy set. An empty list when the heading is there but no table under it parses,
    which the caller treats as unreadable rather than as legacy: a half-written index is
    not an old one. A criterion id that appears twice keeps its first row.
    """
    lines = list(_unfenced(text))
    if not any(CRITERIA_HEADING.match(line) for line in lines):
        return None
    rows, seen, header = [], set(), None
    for line in lines:
        if not line.strip().startswith("|"):
            header = None                            # a table ended; forget its header
            continue
        cells = _cells(line)
        if header is None:
            lowered = [c.lower() for c in cells]
            if (lowered and lowered[0] == "id" and "criterion" in lowered
                    and "journeys" in lowered):
                header = lowered
            continue
        if _separator(cells):
            continue
        cid = cells[0].strip("`").strip()
        if not CRITERION_ID.fullmatch(cid) or cid in seen:
            continue
        seen.add(cid)
        row = dict(zip(header, cells))
        rows.append({
            "id": cid,
            "pattern": row.get("pattern", "").strip("`").strip().lower(),
            "criterion": row.get("criterion", ""),
            "phases": sorted({int(d) for d in re.findall(r"\d+", row.get("phases", ""))}),
            "journeys_cell": row.get("journeys", ""),
        })
    return rows


def parse_plan(text):
    """(claims, journeys) from one phase plan.

    `claims` is the sorted id list on the first `**Criteria:**` line outside a code fence,
    or None when the plan has no such line. `journeys` is [{"j": k, "traces": [ids]}] from
    the `**J{k}** · traces ...` bullets in `## Verification`, outside code fences.
    """
    claims, journeys, section = None, [], None
    for line in _unfenced(text):
        h2 = H2.match(line)
        if h2:
            section = h2.group(1).strip().lower()
            continue
        if claims is None:
            hit = CRITERIA_LINE.match(line)
            if hit:
                claims = _ids(hit.group(1))
                continue
        if section == "verification":
            hit = JOURNEY.match(line)
            if hit:
                journeys.append({"j": int(hit.group(1)), "traces": _ids(hit.group(2))})
    return claims, journeys


def build(index_path):
    try:
        with open(index_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {"error": f"cannot read {index_path}: {exc}"}

    meta, phases = parse_index(text)
    criteria = parse_criteria(text)
    if criteria is None:
        return {"index": index_path, "slug": meta.get("slug"), "legacy": True}
    if not criteria:
        return {"error": f"{index_path} has an '### Acceptance Criteria' heading but no "
                         f"| ID | Pattern | Criterion | Phases | Journeys | table under it"}
    if not phases:
        return {"error": f"{index_path} has no phase table"}

    root = find_root(index_path, [p.get("plan") or "" for p in phases])
    numbers = {p["n"] for p in phases}

    plans, missing = {}, []
    for p in phases:
        plan = p.get("plan") or ""
        full = os.path.abspath(plan if os.path.isabs(plan) else os.path.join(root, plan))
        if not plan or not os.path.exists(full):
            missing.append({"phase": p["n"], "plan": plan or "(none)",
                            "tried": full if plan else None})
            continue
        with open(full, encoding="utf-8") as fh:
            claims, journeys = parse_plan(fh.read())
        plans[p["n"]] = {"path": full, "claims": claims, "journeys": journeys}

    known = {c["id"] for c in criteria}
    gaps, rows, fill = [], [], {}
    for c in criteria:
        cid = c["id"]
        index_phases = [n for n in c["phases"] if n in numbers]
        claimed_by = sorted(n for n, pl in plans.items() if cid in (pl["claims"] or []))
        owners = sorted(set(index_phases) | set(claimed_by))
        traced = list(dict.fromkeys(
            f"P{n}.J{j['j']}" for n in sorted(plans) for j in plans[n]["journeys"]
            if cid in j["traces"]
        ))
        fill[cid] = ", ".join(traced) or NONE
        rows.append(dict(c, index_phases=index_phases, claimed_by=claimed_by,
                         owners=owners, journeys=traced, fill=fill[cid]))

        if not owners:
            # Unowned is reported alone: an untraced report on top would ask for a
            # journey in a phase nobody has chosen yet.
            gaps.append({"kind": "unowned", "id": cid,
                         "detail": "no phase owns it: its Phases cell is empty and no "
                                   "phase plan's **Criteria:** line names it"})
        elif not traced:
            gaps.append({"kind": "untraced", "id": cid, "phases": owners,
                         "detail": f"owned by phase {', '.join(map(str, owners))}, but no "
                                   f"Proof journey traces it"})
        for n in claimed_by:
            if n not in index_phases:
                gaps.append({"kind": "misassigned", "id": cid, "phase": n,
                             "detail": f"phase {n}'s **Criteria:** line claims it; the "
                                       f"index gives it to "
                                       f"{', '.join(map(str, index_phases)) or NONE}"})
        for n in index_phases:
            if n in plans and n not in claimed_by:
                state = "omits it" if plans[n]["claims"] is not None else "is missing"
                gaps.append({"kind": "unclaimed", "id": cid, "phase": n,
                             "detail": f"the index gives it to phase {n}, whose "
                                       f"**Criteria:** line {state}"})

    for n in sorted(plans):
        for cid in plans[n]["claims"] or []:
            if cid not in known:
                gaps.append({"kind": "unknown_id", "id": cid, "phase": n,
                             "detail": f"phase {n}'s **Criteria:** line names it; the "
                                       f"Acceptance Criteria table has no such id"})
        for j in plans[n]["journeys"]:
            for cid in j["traces"]:
                if cid not in known:
                    gaps.append({"kind": "unknown_id", "id": cid, "phase": n,
                                 "journey": f"P{n}.J{j['j']}",
                                 "detail": f"P{n}.J{j['j']} traces it; the Acceptance "
                                           f"Criteria table has no such id"})

    gaps.sort(key=lambda g: (_key(g["id"]), g["kind"], g.get("phase") or 0))
    return {
        "index": index_path,
        "slug": meta.get("slug"),
        "legacy": False,
        "root": root,
        "phase_count": len(phases),
        "criteria": rows,
        "gaps": gaps,
        "missing_plans": missing,
        "fill": fill,
    }


def _legacy_line(g):
    return (f"legacy: {g['index']} has no ### Acceptance Criteria table; "
            f"nothing to trace (a pre-EARS plan set)")


def _incomplete_line(g):
    unknown = len(g["missing_plans"])
    return (f"INCOMPLETE: {unknown} of {g['phase_count']} phase plans could not be read, "
            f"so their claims and journeys are unknown. This is not an all-clear.")


def render(g):
    if g.get("error"):
        return g["error"]
    if g.get("legacy"):
        return _legacy_line(g)
    out = [f"plan set: {g['slug']}   criteria: {len(g['criteria'])}   "
           f"phases: {g['phase_count']}", ""]
    for c in g["criteria"]:
        owners = ", ".join(map(str, c["owners"])) or NONE
        out.append(f"  {c['id']:<7} owned by {owners:<8} traced by {c['fill']}")
    if g["missing_plans"]:
        out.append("")
        out.append("phase plans not found:")
        for m in g["missing_plans"]:
            out.append(f"  phase {m['phase']}: {m['plan']}")
        out.append(f"  resolved against root: {g['root']}")
    out.append("")
    if g["gaps"]:
        out.append(f"gaps: {len(g['gaps'])}")
        for x in g["gaps"]:
            out.append(f"  {x['kind'].upper():<12} {x['id']:<7} {x['detail']}")
    elif not g["missing_plans"]:
        out.append("every criterion is owned by a phase and traced by a journey.")
    if g["missing_plans"]:
        out.append(_incomplete_line(g))
    return "\n".join(out)


def render_fill(g):
    """One line per criterion, `R1.1 -> P1.J1, P2.J3`, and nothing else on stdout."""
    if g.get("error"):
        return g["error"]
    if g.get("legacy"):
        return _legacy_line(g)
    return "\n".join(f"{cid} -> {value}" for cid, value in g["fill"].items())


def exit_code(g):
    if g.get("error"):
        return 1
    if g.get("legacy"):
        return 0
    if g.get("missing_plans"):
        return 1
    return 2 if g.get("gaps") else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("index", help="path to <SLUG>_PLAN.md")
    ap.add_argument("--json", action="store_true", help="the machine form")
    ap.add_argument("--fill", action="store_true",
                    help="print each criterion's Journeys cell value, one per line")
    a = ap.parse_args()
    g = build(a.index)
    if a.json:
        payload = g["fill"] if a.fill and "fill" in g else g
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif a.fill:
        print(render_fill(g))
        if g.get("missing_plans"):
            print(_incomplete_line(g), file=sys.stderr)
    else:
        print(render(g))
    return exit_code(g)


if __name__ == "__main__":
    sys.exit(main())
````
**Impact:** new file; nothing imports it. `chmod +x skills/swarm/ears_trace.py`.

### Step 2: Create its tests
**File:** `skills/swarm/tests/test_ears_trace.py` (new, mode 0755)
**Change:** Write the whole file below, in the style of `tests/test_plan_graph.py` (stdlib harness,
`@case`, `eq`/`ok`, temp trees, a real `git worktree add`). Cases: `clean`, `untraced`, `unowned`,
`unknown_id`, `misassigned`, `unclaimed`, `legacy`, `unreadable` (missing index, missing phase
plan, heading without a table), `linked_worktree`. Every fixture also quotes the format inside
fences, so a parser that reads quoted format fails every case. Verified while planning against a
copy of `skills/swarm/` at `7ab5aca`: all 9 cases pass, and replacing the fence-length check with
`True` fails 12 assertions. The block below is fenced with five backticks because the file
itself contains a four-backtick fence; copy only what is between the fences.
**Code:**
`````python
#!/usr/bin/env python3
"""Regression tests for the EARS trace checker, `ears_trace.py`.

This repo has no test runner, no lint and no CI (CLAUDE.md), so the harness brings its
own: Python 3 standard library only, no pytest, run it directly.

    python3 skills/swarm/tests/test_ears_trace.py              # the repo copy
    python3 ~/.claude/skills/swarm/tests/test_ears_trace.py    # the INSTALLED copy

Both spellings matter for the reason `test_plan_graph.py` gives: `sync.sh` COPIES, so
the installed copy is the one the reconciler and `/analyze` Step 9 actually run. The
harness imports `ears_trace` from its own parent directory and shells out to the
`ears_trace.py` beside it, so whichever tree it is run from is the tree it tests.

Every case builds a small plan set -- an index with the R table, the Acceptance
Criteria table and the phase table, plus one plan per phase with a `**Criteria:**` line
and traced journeys -- under tempfile.mkdtemp(), and removes it. The index QUOTES the
criteria table in a fenced example, and each plan quotes journeys inside a fence (one of
them nested in a longer fence) and a `**Criteria:**` line mid-sentence, so a parser that
reads quoted format as real usage fails every case, not one. The last case puts the set
in a real linked worktree, the layout `/analyze` always produces, where `.git` is a file.

The module under test stays read-only; nothing is written outside the temp trees.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SWARM = os.path.dirname(HERE)
sys.path.insert(0, SWARM)

import ears_trace  # noqa: E402
import swarm  # noqa: E402

CHECK = os.path.join(SWARM, "ears_trace.py")


# ------------------------------------------------------------------------- fixtures

INDEX = """# Plan: Demo

**Slug:** demo
**Phases:** {n}
**Status:** draft

## Requirements

| ID | What the user asked for (verbatim) | Phases |
|---|---|---|
| R1 | make it work | {all} |

{criteria}
## Invariants

The format, quoted -- a fenced example the checker must never read as the real table:

```markdown
### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
| R1.1 | event | WHEN quoted THE SYSTEM SHALL be ignored | 9 | P9.J9 |
| R9.9 | event | WHEN quoted THE SYSTEM SHALL be ignored | 9 | — |
```

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
{rows}
## Reconciliation Log

| # | Conflict | Resolution |
|---|---|---|
| 1 | none | none |
"""

CRITERIA_HEAD = """### Acceptance Criteria

| ID | Pattern | Criterion | Phases | Journeys |
|---|---|---|---|---|
"""

CRITERION_ROW = "| {cid} | event | WHEN the user asks THE SYSTEM SHALL answer | {phases} | — |\n"

INDEX_ROW = "| {n} | Phase {n} | R1 | `src` | 1 | — | NORMAL | `{plan}` | — | — |\n"

PLAN = """# Phase {n}: Phase {n}

**Satisfies:** R1
{criteria_line}**Depends on:** none

---

## Goal

Example. The header `**Criteria:** R9.9` quoted mid-sentence is not a header.

## Verification

**Build:** `true`
**Proof:**
- Harness: `no harness`
- Journeys:
{journeys}
- Neighbor check: `python3 other.py` → passes when it exits 0

```markdown
  - **J7** · traces R9.9 — an example inside a fence → never counted
```

````text
```markdown
  - **J6** · traces R9.9 — a fence quoted inside a longer fence
```
  - **J8** · traces R9.9 — still inside the outer fence → never counted
````

**Exit criteria:** done.
"""

JOURNEY_ROW = "  - **J{k}** · traces {traces} — `python3 run.py` → passes when it prints ok"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def ears_set(root, criteria, plans, index_rel=".workflows/plan/DEMO_PLAN.md",
             legacy=False):
    """Write a plan set into `root`; return the absolute index path.

    `criteria` is [(id, phases_cell)]. `plans` is one (criteria_line, journeys) per phase,
    in order: `criteria_line` is the text after `**Criteria:**`, or None for a plan with
    no such line; `journeys` is [(k, traces_text)]. `legacy` drops the criteria table.
    """
    rows = ""
    for i, (claims, journeys) in enumerate(plans, 1):
        rel = f".workflows/plan/demo/phase-{i}.md"
        line = f"**Criteria:** {claims}\n" if claims is not None else ""
        body = "\n".join(JOURNEY_ROW.format(k=k, traces=t) for k, t in journeys)
        write(os.path.join(root, rel),
              PLAN.format(n=i, criteria_line=line, journeys=body or "  - (none)"))
        rows += INDEX_ROW.format(n=i, plan=rel)
    table = "" if legacy else CRITERIA_HEAD + "".join(
        CRITERION_ROW.format(cid=c, phases=p) for c, p in criteria)
    index = os.path.join(root, index_rel)
    write(index, INDEX.format(n=len(plans),
                              all=", ".join(str(i) for i in range(1, len(plans) + 1)),
                              criteria=table, rows=rows))
    return index


# ------------------------------------------------------------------------------ git

GIT_ENV = dict(
    os.environ,
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_SYSTEM=os.devnull,
    GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
)


def git(*args, cwd=None):
    return subprocess.run(("git",) + args, cwd=cwd, env=GIT_ENV,
                          capture_output=True, text=True, timeout=30)


def have_git():
    try:
        return git("--version").returncode == 0
    except OSError:
        return False


def make_repo(root):
    """An initialised repo with one commit, so `git worktree add` has a base."""
    os.makedirs(root, exist_ok=True)
    git("init", "-q", cwd=root)
    write(os.path.join(root, "README.md"), "demo\n")
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "init", cwd=root)
    return root


def add_worktree(repo, path, branch="feat"):
    out = git("worktree", "add", "-q", "-b", branch, path, cwd=repo)
    if out.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {out.stderr}")
    return path


# ----------------------------------------------------------------------- the harness

FAILURES = []
RUN = []


def eq(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def ok(label, cond):
    if not cond:
        FAILURES.append(f"{label}: expected true")


def case(fn):
    RUN.append(fn)
    return fn


def cli(index, *flags, cwd=None):
    """(exit code, stdout) of the CLI -- the thing the reconciler and Step 9 read."""
    out = subprocess.run([sys.executable, CHECK, index, *flags], cwd=cwd,
                         capture_output=True, text=True, timeout=60)
    return out.returncode, out.stdout


def gaps(g):
    return sorted((x["kind"], x["id"]) for x in g.get("gaps", []))


def gap(g, kind, cid):
    for x in g.get("gaps", []):
        if x["kind"] == kind and x["id"] == cid:
            return x
    return None


# ---------------------------------------------------------------------------- cases

@case
def test_clean():
    tmp = tempfile.mkdtemp(prefix="et-clean-")
    try:
        index = ears_set(tmp, [("R1.1", "1"), ("R1.2", "2")], [
            ("R1.1", [(1, "R1.1")]),
            ("R1.2", [(1, "R1.2"), (2, "R1.1, R1.2")]),
        ])
        g = ears_trace.build(index)
        eq("clean: no error", g.get("error"), None)
        eq("clean: not legacy", g.get("legacy"), False)
        eq("clean: no gaps", g.get("gaps"), [])
        eq("clean: no missing plan", g.get("missing_plans"), [])
        eq("clean: the criteria table is not read as phases",
           len(swarm.parse_index(open(index, encoding="utf-8").read())[1]), 2)
        eq("clean: the fenced example table adds no criterion",
           [c["id"] for c in g.get("criteria", [])], ["R1.1", "R1.2"])
        eq("clean: nor an owner", g["criteria"][0]["owners"] if g.get("criteria") else None, [1])
        eq("clean: fill", g.get("fill"),
           {"R1.1": "P1.J1, P2.J2", "R1.2": "P2.J1, P2.J2"})
        eq("clean: the fenced J7 and the mid-sentence R9.9 are never read",
           gap(g, "unknown_id", "R9.9"), None)
        code, out = cli(index)
        eq("clean: exits 0", code, 0)
        ok("clean: says so", "every criterion is owned by a phase and traced" in out)
        code, out = cli(index, "--fill")
        eq("clean: --fill exits 0", code, 0)
        eq("clean: --fill prints one line per criterion", out.strip().splitlines(),
           ["R1.1 -> P1.J1, P2.J2", "R1.2 -> P2.J1, P2.J2"])
        code, out = cli(index, "--fill", "--json")
        eq("clean: --fill --json is the fill map", json.loads(out),
           {"R1.1": "P1.J1, P2.J2", "R1.2": "P2.J1, P2.J2"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_untraced():
    tmp = tempfile.mkdtemp(prefix="et-untraced-")
    try:
        index = ears_set(tmp, [("R1.1", "1"), ("R1.2", "2")], [
            ("R1.1", [(1, "R1.1")]),
            ("R1.2", [(1, "R1.1")]),
        ])
        g = ears_trace.build(index)
        eq("untraced: the one gap", gaps(g), [("untraced", "R1.2")])
        hit = gap(g, "untraced", "R1.2")
        if hit:
            eq("untraced: names the owning phase", hit.get("phases"), [2])
        eq("untraced: the fill shows the hole", g["fill"]["R1.2"], "—")
        code, out = cli(index)
        eq("untraced: exits 2", code, 2)
        ok("untraced: the report names it", "UNTRACED" in out and "R1.2" in out)
        code, out = cli(index, "--fill")
        eq("untraced: --fill still exits 2", code, 2)
        ok("untraced: --fill prints the empty cell", "R1.2 -> —" in out.splitlines())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_unowned():
    tmp = tempfile.mkdtemp(prefix="et-unowned-")
    try:
        index = ears_set(tmp, [("R1.1", "1"), ("R1.2", "—")], [
            ("R1.1", [(1, "R1.1")]),
        ])
        g = ears_trace.build(index)
        eq("unowned: reported alone, not also untraced", gaps(g), [("unowned", "R1.2")])
        code, out = cli(index)
        eq("unowned: exits 2", code, 2)
        ok("unowned: the report names it", "UNOWNED" in out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_unknown_id():
    tmp = tempfile.mkdtemp(prefix="et-unknown-")
    try:
        index = ears_set(tmp, [("R1.1", "1")], [
            ("R1.1, R8.1", [(1, "R1.1"), (2, "R7.1")]),
        ])
        g = ears_trace.build(index)
        eq("unknown: a journey and a Criteria line naming absent ids", gaps(g),
           [("unknown_id", "R7.1"), ("unknown_id", "R8.1")])
        hit = gap(g, "unknown_id", "R7.1")
        if hit:
            eq("unknown: names the journey", hit.get("journey"), "P1.J2")
        eq("unknown: exits 2", cli(index)[0], 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_misassigned():
    tmp = tempfile.mkdtemp(prefix="et-misassigned-")
    try:
        index = ears_set(tmp, [("R1.1", "1"), ("R1.2", "1")], [
            ("R1.1, R1.2", [(1, "R1.1, R1.2")]),
            ("R1.1", [(1, "R1.1")]),
        ])
        g = ears_trace.build(index)
        eq("misassigned: phase 2 claims what the index gives phase 1", gaps(g),
           [("misassigned", "R1.1")])
        hit = gap(g, "misassigned", "R1.1")
        if hit:
            eq("misassigned: names phase 2", hit.get("phase"), 2)
        eq("misassigned: exits 2", cli(index)[0], 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_unclaimed():
    tmp = tempfile.mkdtemp(prefix="et-unclaimed-")
    try:
        index = ears_set(tmp, [("R1.1", "1, 2")], [
            ("R1.1", [(1, "R1.1")]),
            (None, []),
        ])
        g = ears_trace.build(index)
        eq("unclaimed: phase 2 has no Criteria line", gaps(g), [("unclaimed", "R1.1")])
        hit = gap(g, "unclaimed", "R1.1")
        if hit:
            eq("unclaimed: names phase 2", hit.get("phase"), 2)
            ok("unclaimed: says the line is missing", "is missing" in hit["detail"])
        eq("unclaimed: exits 2", cli(index)[0], 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_legacy():
    tmp = tempfile.mkdtemp(prefix="et-legacy-")
    try:
        index = ears_set(tmp, [], [("R1.1", [(1, "R1.1")])], legacy=True)
        g = ears_trace.build(index)
        eq("legacy: flagged, though a fenced example quotes the heading",
           g.get("legacy"), True)
        eq("legacy: no error", g.get("error"), None)
        code, out = cli(index)
        eq("legacy: exits 0", code, 0)
        ok("legacy: says legacy", out.startswith("legacy:"))
        code, out = cli(index, "--json")
        eq("legacy: --json exits 0", code, 0)
        eq("legacy: --json legacy", json.loads(out).get("legacy"), True)
        code, out = cli(index, "--fill")
        eq("legacy: --fill exits 0", code, 0)
        ok("legacy: --fill says legacy", out.startswith("legacy:"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_unreadable():
    tmp = tempfile.mkdtemp(prefix="et-unreadable-")
    try:
        eq("unreadable: no index exits 1", cli(os.path.join(tmp, "NOPE_PLAN.md"))[0], 1)

        index = ears_set(tmp, [("R1.1", "1"), ("R1.2", "2")], [
            ("R1.1", [(1, "R1.1")]),
            ("R1.2", [(1, "R1.2")]),
        ])
        os.remove(os.path.join(tmp, ".workflows/plan/demo/phase-2.md"))
        g = ears_trace.build(index)
        eq("unreadable: the missing plan is listed", [m["phase"] for m in g["missing_plans"]], [2])
        code, out = cli(index)
        eq("unreadable: a missing plan exits 1, not 0 or 2", code, 1)
        ok("unreadable: never an all-clear", "INCOMPLETE" in out
           and "every criterion is owned" not in out)

        legacy = ears_set(os.path.join(tmp, "half"), [], [("R1.1", [(1, "R1.1")])],
                          legacy=True)
        text = open(legacy, encoding="utf-8").read()
        write(legacy, text.replace("## Phases", "### Acceptance Criteria\n\nnone yet\n\n## Phases", 1))
        eq("unreadable: a heading with no table exits 1", cli(legacy)[0], 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_linked_worktree():
    """The layout `/analyze` produces: `.git` is a FILE, the index under `.workflows/plan/`,
    and the caller's cwd somewhere else entirely."""
    tmp = tempfile.mkdtemp(prefix="et-wt-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        ok("worktree: .git is a file", os.path.isfile(os.path.join(wt, ".git")))
        index = ears_set(wt, [("R1.1", "1"), ("R1.2", "2")], [
            ("R1.1", [(1, "R1.1")]),
            ("R1.2", [(1, "R1.2")]),
        ])
        g = ears_trace.build(index)
        eq("worktree: root is the worktree", os.path.realpath(g.get("root") or ""),
           os.path.realpath(wt))
        eq("worktree: no plan went missing", g.get("missing_plans"), [])
        eq("worktree: no gaps", g.get("gaps"), [])
        eq("worktree: exits 0 from another cwd", cli(index, cwd=tmp)[0], 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------- driver

def main():
    if not have_git():
        print("test_ears_trace: git is not on PATH; the worktree case cannot run",
              file=sys.stderr)
        return 1
    for fn in RUN:
        try:
            fn()
        except Exception as exc:                          # one broken case, not a lost run
            FAILURES.append(f"{fn.__name__}: raised {type(exc).__name__}: {exc}")
    if FAILURES:
        for line in FAILURES:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"\n{len(FAILURES)} assertion(s) failed in {len(RUN)} cases", file=sys.stderr)
        return 1
    print(f"test_ears_trace: all assertions passed ({len(RUN)} cases) against {CHECK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
`````
**Impact:** new file.

### Step 3: Reconciler — build the criterion ledger from the script
**File:** `agents/plan-reconciler.md:27-34` (`### 1. Build the ledger`)
**Change:** Replace the two paragraphs of Step 1.
**Find:**
~~~markdown
Read every plan file's **Interface Contract**, **Satisfies** line and **Files** table. Build one
table across all phases: symbol → the phase that deletes it, the phases that reference it, the
phases that create it; file → the phases that touch it, in order; and requirement id → the
phases that serve it.

Read the analysis file's **Reference List** and **Impact Points** — that is the checklist of
what must be covered. Read the plan index's **Requirements** table — that is the checklist of
what the user actually asked for.
~~~
**Replace with:**
~~~markdown
Read every plan file's **Interface Contract**, **Satisfies** and **Criteria** lines and **Files**
table. Build one table across all phases: symbol → the phase that deletes it, the phases that
reference it, the phases that create it; file → the phases that touch it, in order; requirement
id → the phases that serve it; and criterion id → the phases that own it and the journeys
(`P{n}.J{k}`) that trace it.

Build the criterion half mechanically, not by reading:

```bash
python3 ~/.claude/skills/swarm/ears_trace.py <plan_index> --json
```

`criteria[]` is the criterion ledger (`owners`, `index_phases`, `claimed_by`, `journeys`) and
`gaps[]` is every trace conflict in the table below. `"legacy": true` means the index has no
`### Acceptance Criteria` table — a set planned before EARS: skip the criterion rows and the
trace rule, and say `legacy` in the summary. If the script cannot run at all (missing from the
install, no `python3`), build the same ledger by reading the criteria table, each plan's
`**Criteria:**` line and its `**J{k}** · traces …` journey bullets, and say in the summary that
the trace was checked by hand.

Read the analysis file's **Reference List** and **Impact Points** — that is the checklist of
what must be covered. Read the plan index's **Requirements** table — that is the checklist of
what the user actually asked for — and its **Acceptance Criteria** table, the checklist of what
must be proved.
~~~
**Impact:** the reconciler now reads the trace from the script's JSON (Build the lever).

### Step 4: Reconciler — two conflict rows
**File:** `agents/plan-reconciler.md:49` (after the `**Requirement creep**` row of the Step 2 table)
**Change:** Append two rows to the conflicts table.
**Find:**
~~~markdown
| **Requirement creep** | a phase whose steps serve an `R` outside its own **Satisfies** line |
~~~
**Replace with:**
~~~markdown
| **Requirement creep** | a phase whose steps serve an `R` outside its own **Satisfies** line |
| **Unowned criterion** | a criterion `R{n}.{m}` in the index's Acceptance Criteria table that no phase owns — `ears_trace.py` gap `unowned` |
| **Untraced criterion** | a criterion some phase owns that no Proof journey traces — gap `untraced`; and its bookkeeping kin `misassigned`, `unclaimed`, `unknown_id` (a plan's **Criteria:** line or journey ids disagree with the table) |
~~~
**Impact:** none beyond the table.

### Step 5: Reconciler — rule 6 admits the unownable criterion to Open Questions
**File:** `agents/plan-reconciler.md:73-75`
**Change:** Rule 6 says Open Questions is *only* for an all-irreversible fork, while rule 7 has
always parked an unowned `R` there. Make rule 6 name rule 7's exception so the two do not
contradict (the incident quoted in rule 6 was exactly such a contradiction).
**Find:**
~~~markdown
   **Open Questions is only for a fork where every branch is irreversible** (destroying data,
   rewriting published history, an unrepeatable migration), because a parked item costs the plan
   set its unattended launch: `/analyze` Step 11 refuses to start an orchestrator over one.
~~~
**Replace with:**
~~~markdown
   **Open Questions is only for a fork where every branch is irreversible** (destroying data,
   rewriting published history, an unrepeatable migration), or for a requirement or criterion no
   phase can own (rule 7), because a parked item costs the plan set its unattended launch:
   `/analyze` Step 11 refuses to start an orchestrator over one.
~~~
**Impact:** none beyond the rule text.

### Step 6: Reconciler — rule 7 carries the trace rule
**File:** `agents/plan-reconciler.md:79-84`
**Change:** Extend rule 7 with criterion ids and the trace rule paragraph. The paragraph that
starts `**The trace rule.**` must be the same words as Step 9 below puts into `/analyze` Step 8 —
Proof J5 compares them after collapsing whitespace, so wrap lines freely but do not reword one
without the other.
**Find:**
~~~markdown
7. **Requirement ids follow the work.** When a step moves between phases, move its `R` with it:
   update both phases' **Satisfies** lines and the index's Requirements table. Never widen a
   phase's `Satisfies` to legalise creep — move the step instead, or split it. An `R` no phase
   serves is an **Open Question**, never a silent drop: it is the one conflict class where the
   user is guaranteed to notice — and it is a genuine gap in coverage rather than a fork between
   two behaviors, which is why it stays a question instead of being decided.
~~~
**Replace with:**
~~~markdown
7. **Requirement ids follow the work.** When a step moves between phases, move its `R` with it:
   update both phases' **Satisfies** lines and the index's Requirements table. Never widen a
   phase's `Satisfies` to legalise creep — move the step instead, or split it. An `R` no phase
   serves is an **Open Question**, never a silent drop: it is the one conflict class where the
   user is guaranteed to notice — and it is a genuine gap in coverage rather than a fork between
   two behaviors, which is why it stays a question instead of being decided. Criterion ids follow
   the work the same way: a step that moves takes its criteria (the `**Criteria:**` line and the
   criteria table's Phases cell) and the journeys that trace them with it.

   **The trace rule.** Every acceptance criterion `R{n}.{m}` in the index's `### Acceptance Criteria`
   table has at least one owning phase and at least one Proof journey that traces it, and
   `python3 ~/.claude/skills/swarm/ears_trace.py <plan index>` exits 0 over the set. A criterion that
   is owned but untraced is fixed by editing its owning phase plan: add a journey
   `**J{k}** · traces R{n}.{m} — <commands> → passes when <end state>` under that plan's
   `- Journeys:`. If the owning phase cannot observe it — its planner returned it in `untraced` and
   named in Handoffs the later phase that can — move it to that phase instead (its `**Criteria:**`
   line and the table's Phases cell) and add the journey there. A criterion that is unowned is assigned to the phase that satisfies its `R` (the
   one whose steps the behavior lands in; the earliest of them when that does not settle it): add it
   to that plan's `**Criteria:**` line and to the criteria table's Phases cell, and give it a
   journey. A `misassigned`, `unclaimed` or `unknown_id` gap is fixed by making the plan's
   `**Criteria:**` line, the table's Phases cell and the journey ids agree, on whichever side the
   plan's steps support. Only a criterion whose `R` no phase satisfies, and that no phase can take
   on, lands in `## Open Questions` — never an untraced one, which a written journey always fixes.
   An index with no `### Acceptance Criteria` heading is a legacy set: there is nothing to trace, and
   the script exits 0 with a `legacy` line.
~~~
**Impact:** the reconciler now fixes trace gaps by editing plans instead of reporting them.

### Step 7: Reconciler — finalize fills Phases and Journeys of the criteria table
**File:** `agents/plan-reconciler.md:94-95` and `:101-102` (`### 4. Finalize the plan index`)
**Change:** Two edits in the finalize list.
**Find (a):**
~~~markdown
- **Requirements** table maps every `R` to the phases that ended up serving it — this is what
  `create-task` reads to shape the board's cards, so it must match the plans, not the draft
~~~
**Replace with (a):**
~~~markdown
- **Requirements** table maps every `R` to the phases that ended up serving it — this is what
  `create-task` reads to shape the board's cards, so it must match the plans, not the draft
- **Acceptance Criteria** table: each row's Phases cell names the phases that own it after your
  moves, and its Journeys cell is filled from
  `python3 ~/.claude/skills/swarm/ears_trace.py <plan_index> --fill` — it prints one line per
  criterion, `R1.1 -> P1.J1, P2.J3`; write the value right of `->` into that row's Journeys cell
  (`—` stays `—`, and is a gap rule 7 has not closed). A legacy index has no such table; leave it
  as it is
~~~
**Find (b):**
~~~markdown
- Fill **Open Questions** with the residue only: unowned requirement ids, and forks where every
  branch is irreversible. Empty is the normal outcome, not a lucky one
~~~
**Replace with (b):**
~~~markdown
- Fill **Open Questions** with the residue only: unowned requirement ids, criteria no phase can
  own (rule 7), and forks where every branch is irreversible. Empty is the normal outcome, not a
  lucky one
~~~
**Impact:** the Journeys column is written by the reconciler for N > 1 (phase 1 writes it for N = 1).

### Step 8: Reconciler — verify runs the script; return value reports the trace
**File:** `agents/plan-reconciler.md:107-109` (`### 5. Verify`) and `:113-122` (`## Return value`)
**Find (a):**
~~~markdown
Re-read the ledger after your edits. Every phase must still satisfy: dependencies point
backward only, no deleted-then-used, no unowned impact point, no unowned requirement id, builds
green on its own.
~~~
**Replace with (a):**
~~~markdown
Re-read the ledger after your edits. Every phase must still satisfy: dependencies point
backward only, no deleted-then-used, no unowned impact point, no unowned requirement id, builds
green on its own.

Then run `python3 ~/.claude/skills/swarm/ears_trace.py <plan_index>`. It must exit 0 — a clean
trace, or `legacy`. Exit 2 prints each gap: fix it under rule 7 and run the script again. Exit 1
means the index is unreadable or a phase plan it names is missing: return `status: blocked`. The
only exit 2 you may return with is a criterion you parked in Open Questions under rule 7, and the
summary names it.
~~~
**Find (b):**
~~~markdown
requirement_map: {R1: [3, 4], R2: [1, 2]}    # final, after every move
~~~
**Replace with (b):**
~~~markdown
requirement_map: {R1: [3, 4], R2: [1, 2]}    # final, after every move
criteria_map: {R1.1: [3], R2.1: [1, 2]}      # final owners per criterion; {} on a legacy index
trace: clean | legacy | manual | "gaps: R3.4 unowned"   # ears_trace.py's verdict after your edits
~~~
**Impact:** `/analyze` Step 8 can read `trace` from the return; nothing breaks if it ignores it.

### Step 9: `/analyze` Step 8 — the same trace rule
**File:** `commands/analyze.md`, `### Step 8: Reconcile (N > 1 only)` (`:385-402` today, `~:439-456`
after phase 1 — Step 8 is byte-identical to `7ab5aca` after phase 1, so the Find text matches).
**Change:** Three edits, all inside Step 8.
**Find (a):**
~~~markdown
- **Broken-build phase** — a phase that leaves the tree uncompilable

Then it rewrites `<SLUG>_PLAN.md` from draft to final and appends a **Reconciliation Log**.
~~~
**Replace with (a):**
~~~markdown
- **Broken-build phase** — a phase that leaves the tree uncompilable
- **Unowned / untraced criterion** — an acceptance criterion `R{n}.{m}` no phase owns, or one no
  Proof journey traces; `skills/swarm/ears_trace.py` finds both mechanically

Then it rewrites `<SLUG>_PLAN.md` from draft to final — including the Acceptance Criteria table's
Phases and Journeys cells — and appends a **Reconciliation Log**.

**The trace rule.** Every acceptance criterion `R{n}.{m}` in the index's `### Acceptance Criteria`
table has at least one owning phase and at least one Proof journey that traces it, and
`python3 ~/.claude/skills/swarm/ears_trace.py <plan index>` exits 0 over the set. A criterion that
is owned but untraced is fixed by editing its owning phase plan: add a journey
`**J{k}** · traces R{n}.{m} — <commands> → passes when <end state>` under that plan's
`- Journeys:`. If the owning phase cannot observe it — its planner returned it in `untraced` and
named in Handoffs the later phase that can — move it to that phase instead (its `**Criteria:**`
line and the table's Phases cell) and add the journey there. A criterion that is unowned is assigned to the phase that satisfies its `R` (the
one whose steps the behavior lands in; the earliest of them when that does not settle it): add it
to that plan's `**Criteria:**` line and to the criteria table's Phases cell, and give it a
journey. A `misassigned`, `unclaimed` or `unknown_id` gap is fixed by making the plan's
`**Criteria:**` line, the table's Phases cell and the journey ids agree, on whichever side the
plan's steps support. Only a criterion whose `R` no phase satisfies, and that no phase can take
on, lands in `## Open Questions` — never an untraced one, which a written journey always fixes.
An index with no `### Acceptance Criteria` heading is a legacy set: there is nothing to trace, and
the script exits 0 with a `legacy` line.
~~~
**Find (b):**
~~~markdown
3. **Leave `## Open Questions` for the residue only** — a fork where every branch is irreversible
   (destroying data, rewriting published history, an unrepeatable migration). Nothing else
   qualifies, and an item parked there costs the whole set its unattended launch at Step 11.
~~~
**Replace with (b):**
~~~markdown
3. **Leave `## Open Questions` for the residue only** — a fork where every branch is irreversible
   (destroying data, rewriting published history, an unrepeatable migration), or a requirement or
   criterion no phase can own (the trace rule above). Nothing else qualifies, and an item parked
   there costs the whole set its unattended launch at Step 11.
~~~
**Impact:** Step 8 and reconciler rules 6–7 now say the same thing (Invariant 5, CLAUDE.md).

### Step 10: `/analyze` Step 9 — run the trace check, N = 1 too
**File:** `commands/analyze.md`, `### Step 9: Finalize the Plan Index` (`:418-422` today,
`~:479-483` after phase 1). Insert one paragraph immediately **before** the paragraph that starts
`**And verify the two decision sections.**`, and widen that paragraph's first sentence. Do not
touch phase 1's N = 1 paragraph or the "Before terminating, verify" paragraph.
**Find:**
~~~markdown
**And verify the two decision sections.** `## Open Questions` must be empty, or every item in it
must be a fork where *every* branch is irreversible — anything else belongs in `## Decisions` with
its rung, resolved per Step 8.
~~~
**Replace with:**
~~~markdown
**And verify the trace — N = 1 too.** Run `python3 ~/.claude/skills/swarm/ears_trace.py
<plan index>`. It must exit 0: every criterion owned and traced, or `legacy` for an index with no
`### Acceptance Criteria` table. Exit 2 lists each gap: fix it by the trace rule in Step 8 (for
N = 1 there is no reconciler, so you edit the one phase plan yourself), refill the Journeys column
(`--fill` prints the values), and run it again. Exit 1 means a phase plan the index names is
missing. The only exit 2 that may survive this step is a criterion parked in `## Open Questions`
under that rule, and it holds the launch at Step 11 like any other item there.

**And verify the two decision sections.** `## Open Questions` must be empty, or every item in it
must be a fork where *every* branch is irreversible, or a requirement or criterion no phase can
own — anything else belongs in `## Decisions` with its rung, resolved per Step 8.
~~~
**Impact:** an N = 1 set gets the same mechanical check the reconciler runs for N > 1.

### Step 11: `/analyze` — the other four statements of what Open Questions holds
**File:** `commands/analyze.md` — the "contract with everything downstream" bullet (`:161-163`
today, unchanged by phase 1), Step 11's first refusal bullet (`:472-477` today, `~:533-538` after
phase 1), the plan index template's `## Open Questions` comment (`:699-702` today, `~:786-789`
after phase 1) and the termination block's Open Questions comment (`:794-796` today, `~:885-887`
after phase 1). All four are outside phase 1's regions (phase 1 edits only the template's
`## Requirements` section and the termination block's `Requirements:` lines), so these Find
texts match after phase 1. Anchor on text.
**Change:** Added by the reconciler. Rule 6 (Step 5), rule 7 (Step 6), Step 8 item 3 (Step 9) and
Step 9 (Step 10) now all say Open Questions holds an all-irreversible fork *or* a requirement or
criterion no phase can own (R3.2). These four places still say "one thing", which would leave
Step 11 refusing a launch for a reason its own text says cannot exist. Make them say the same.
**Find (a):**
~~~markdown
- **`## Open Questions` is reserved for one thing:** a fork where *every* branch is irreversible.
  That is the only item a plan set may legitimately stop on, and it is why Step 11 still refuses
  to launch over a non-empty section.
~~~
**Replace with (a):**
~~~markdown
- **`## Open Questions` is reserved for two things:** a fork where *every* branch is
  irreversible, and a requirement or acceptance criterion no phase can own (the trace rule,
  Step 8). Those are the only items a plan set may legitimately stop on, and they are why Step 11
  still refuses to launch over a non-empty section.
~~~
**Find (b):**
~~~markdown
- **Open Questions is non-empty** — which after Step 8 means one thing: a fork where every branch
  is irreversible. Launching over it would spend the night doing the wrong work N times in
  parallel, since the contradiction is exactly what N sessions would each resolve differently.
~~~
**Replace with (b):**
~~~markdown
- **Open Questions is non-empty** — which after Step 8 means a fork where every branch is
  irreversible, or a requirement or criterion no phase can own. Launching over the first would
  spend the night doing the wrong work N times in parallel, since the contradiction is exactly
  what N sessions would each resolve differently; launching over the second would land a set that
  leaves part of the ask unbuilt and unproved.
~~~
**Find (c):**
~~~markdown
<Reserved for forks where EVERY branch is irreversible — destroying data, rewriting
published history, an unrepeatable migration. Everything else was decided at Step 8 and
belongs under Decisions.
~~~
**Replace with (c):**
~~~markdown
<Reserved for forks where EVERY branch is irreversible — destroying data, rewriting
published history, an unrepeatable migration — and for a requirement or acceptance criterion
no phase can own (the trace rule, Step 8). Everything else was decided at Step 8 and
belongs under Decisions.
~~~
**Find (d):**
~~~markdown
<If Open Questions is non-empty, list them too. After Step 8 that means an irreversible
fork, so say so plainly
~~~
**Replace with (d):**
~~~markdown
<If Open Questions is non-empty, list them too. After Step 8 that means an irreversible
fork or a requirement or criterion no phase can own, so say so plainly
~~~
**Impact:** wording only; every statement of the Open Questions residue in `commands/analyze.md`
now matches rules 6–7 and R3.2.

## Principles applied

- Build the lever: the trace is checked by a script (`ears_trace.py`) the reconciler and Step 9 both run and must see exit 0, instead of a prose instruction to "check every criterion"; its tests prove the five gap kinds on fixtures.
- Laziness protocol: `parse_index` and `find_root` are imported, not reimplemented; the CLI shape, exit codes and test harness copy `plan_graph.py`'s; the script prints the Journeys values and never writes the index, so it stays read-only and has no second writer to keep in step.
- Encode lessons in structure: the trace rule is one named paragraph (`**The trace rule.**`) that appears in both files, and Proof J5 fails if the two copies drift — the CLAUDE.md "must stay in step" rule becomes a check instead of a sentence.
- Test behavior, not implementation: tests drive `build()` and the real CLI exit codes and stdout on real temp trees (including a real linked worktree), never private helpers; a mutation of the fence check fails 12 assertions.
- Prove it works: Proof J2/J3 run the script against this plan set's own index, not only fixtures.

## Verification

**Build:** `cd "$T" && python3 -m py_compile skills/swarm/ears_trace.py skills/swarm/tests/test_ears_trace.py`
**Tests:** `cd "$T" && python3 skills/swarm/tests/test_ears_trace.py && python3 skills/swarm/tests/test_plan_graph.py && python3 skills/swarm/swarm.py selftest`
**Proof:**
- Harness: `no harness` (this repo has no `.claude/skills/verify-*`; the real artifacts are the
  script's CLI run against a real plan set, and the two prompt files). Variables for every
  journey: `W=/home/miftah/.worktrees/claude-commands/ears-acceptance-criteria` (holds this set's
  `.workflows/plan/`), `T` = the tree where this phase's commit is checked out (`T=$W` when
  implemented in place), `IDX=$W/.workflows/plan/EARS_ACCEPTANCE_CRITERIA_PLAN.md`.
- Feature-map entries: none (the repo has no `features/` map)
- Journeys:
  - **J1** · traces R3.1 — `cd "$T" && python3 skills/swarm/tests/test_ears_trace.py; echo "exit=$?"` → passes when it prints `test_ears_trace: all assertions passed (9 cases)` and `exit=0`.
  - **J2** · traces R3.1 — `cd "$T" && python3 skills/swarm/ears_trace.py "$IDX" --fill > /tmp/et-fill.txt; echo "exit=$?"; grep -c -E '^R[0-9]+\.[0-9]+ -> ' /tmp/et-fill.txt; grep -E '^R3\.[123] -> ' /tmp/et-fill.txt` → passes when exit is `0` (or `2` only if `python3 skills/swarm/ears_trace.py "$IDX" | grep -E '^  [A-Z_]+ +R'` lists no gap on an `R3.` id — another phase's gap is the reconciler's), the count is `14`, and the three lines read `R3.1 -> P3.J1, P3.J2, P3.J3`, `R3.2 -> P3.J3, P3.J4`, `R3.3 -> P3.J5`. Exit `1` fails it.
  - **J3** · traces R3.1, R3.2 — write a probe index beside the real one (so its plan paths resolve) with two extra criteria, run the checker on it, delete it. `cd "$W/.workflows/plan" && python3 - <<'EOF'` with the script below, then `python3 "$T/skills/swarm/ears_trace.py" EARS_TRACE_PROBE_PLAN.md; echo "exit=$?"; rm -f EARS_TRACE_PROBE_PLAN.md` → passes when the output has a line matching `UNTRACED +R3\.9 +owned by phase 3` and one matching `UNOWNED +R3\.8 +no phase owns it`, it ends `exit=2`, and the probe file is gone afterwards:
    ```python
    t = open("EARS_ACCEPTANCE_CRITERIA_PLAN.md", encoding="utf-8").read()
    row = next(l for l in t.splitlines() if l.startswith("| R3.3 |"))
    extra = ("| R3.9 | event | WHEN probed THE SYSTEM SHALL be reported | 3 | — |\n"
             "| R3.8 | event | WHEN probed THE SYSTEM SHALL be reported | — | — |")
    open("EARS_TRACE_PROBE_PLAN.md", "w", encoding="utf-8").write(t.replace(row, row + "\n" + extra, 1))
    ```
  - **J4** · traces R3.2 — `cd "$T" && python3 - <<'EOF'` with the script below → passes when it prints `PASS J4`:
    ```python
    import re
    r = open("agents/plan-reconciler.md", encoding="utf-8").read()
    a = open("commands/analyze.md", encoding="utf-8").read()
    def sec(t, start, end): return t[t.index(start):t.index(end)]
    assert "| **Unowned criterion** |" in r and "| **Untraced criterion** |" in r, "conflict rows"
    s1 = sec(r, "### 1. Build the ledger", "### 2. Find the conflicts")
    assert "ears_trace.py <plan_index> --json" in s1, "ledger from the script"
    s3 = sec(r, "### 3. Resolve", "### 4. Finalize")
    assert "**The trace rule.**" in s3 and "add a journey" in s3, "rule 7 fixes untraced by a journey"
    assert "or for a requirement or criterion no phase can own (rule 7)" in " ".join(s3.split()), "rule 6 names the exception"
    s4 = sec(r, "### 4. Finalize", "### 5. Verify")
    assert "ears_trace.py <plan_index> --fill" in s4 and "Journeys cell" in s4, "finalize fills Journeys"
    s5 = sec(r, "### 5. Verify", "## Return value")
    assert "ears_trace.py <plan_index>" in s5 and "must exit 0" in s5, "verify requires exit 0"
    assert re.search(r"^criteria_map: ", r, re.M) and re.search(r"^trace: ", r, re.M), "return value"
    s9 = sec(a, "### Step 9", "### Step 10")
    assert "**And verify the trace — N = 1 too.**" in s9 and "ears_trace.py" in s9, "Step 9 runs the check"
    flat = " ".join(a.split())
    assert "reserved for one thing" not in flat and "which after Step 8 means one thing" not in flat, "stale Open Questions wording"
    assert flat.count("criterion no phase can own") >= 5, "Step 8, Step 9, contract, Step 11, template all name the unownable criterion"
    print("PASS J4")
    EOF
    ```
  - **J5** · traces R3.3 — `cd "$T" && python3 - <<'EOF'` with the script below → passes when it prints `PASS J5 identical` (exit 0):
    ```python
    import re, sys
    def rule(path):
        t = open(path, encoding="utf-8").read()
        m = re.search(r"\*\*The trace rule\.\*\*(.*?)\n[ \t]*\n", t, re.S)
        return " ".join(m.group(1).split()) if m else None
    a, b = rule("commands/analyze.md"), rule("agents/plan-reconciler.md")
    assert a and b, f"missing: analyze={bool(a)} reconciler={bool(b)}"
    assert a == b, "the trace rule differs between /analyze Step 8 and plan-reconciler rule 7"
    s8 = open("commands/analyze.md", encoding="utf-8").read()
    s8 = s8[s8.index("### Step 8"):s8.index("### Step 9")]
    assert "**The trace rule.**" in s8, "the rule sits in Step 8"
    print("PASS J5 identical")
    EOF
    ```
- Neighbor check: the write-set gate and the index parser share `find_root` / `parse_index` with
  the new script — `cd "$T" && python3 skills/swarm/tests/test_plan_graph.py && python3 skills/swarm/swarm.py selftest`
  → passes when both print their `all assertions passed` line and exit 0 (Invariant 4). And the
  committed pre-EARS set still checks clean: `cd "$T" && python3 skills/swarm/ears_trace.py
  .workflows/plan/SWARM_WRITE_SET_GATE_PLAN.md; echo "exit=$?"` → passes when it prints one line
  starting `legacy:` and `exit=0`.
- Cost: none (no LLM turns; every journey is a local command).
**Exit criteria:** `python3 skills/swarm/tests/test_ears_trace.py` passes (clean → 0, untraced → 2,
unowned → 2, legacy → 0, missing plan → 1); `ears_trace.py` over this set's own index prints 14
`--fill` lines with R3.1–R3.3 traced by `P3.J*`; reconciler rules 6–7 and `/analyze` Step 8 carry
the same `**The trace rule.**` paragraph (J5); `test_plan_graph.py` and `swarm.py selftest` still pass.

## Handoffs

- **Phase 5 (R5)** — `skills/swarm/SKILL.md`: add an `## ears_trace.py — the EARS trace check`
  section beside the `plan_graph.py` one (`SKILL.md:23-30`): the CLI, exit codes `0 clean or legacy
  · 1 unreadable · 2 gaps`, `--json`, `--fill`, the five gap kinds, and that the reconciler and
  `/analyze` Step 9 run it. Also `README.md`/`CLAUDE.md` mention of the script, and the CLAUDE.md
  "Swarm planning" sentence "`/analyze` Step 8 and `plan-reconciler` rule 6 must stay in step"
  should read "rules 6–7", since the trace rule lives in rule 7. Phase 5's deploy must include
  `skills/swarm/tests/test_ears_trace.py`, and its "both test scripts pass from `~/.claude`" exit
  criterion should name this file as one of them.
- **Phase 5 (R5)** — `swarm.parse_index` does not skip fenced code blocks. It is safe today (no
  fenced example of a `#`/`Title`/`Plan`-headed table sits in an index). Reconciler decision:
  phase 5 does **not** add the guard — it leaves `parse_index` untouched (index Decisions).
- **Phase 1 (R1)** — settled by the reconciler: phase 1 owns the N = 1 Journeys-fill paragraph,
  including the sentence that points at `ears_trace.py --fill` (with a by-hand fallback for a
  tree deployed before phase 5's `./sync.sh`). This phase's Step 10 only refers to `--fill` when
  a gap is fixed; it does not restate the fill rule.
- **Phase 2 (R2)** — none needed; the script parses the format phase 2 defines. If the reconciler
  changes the journey bullet shape, change `JOURNEY` in `ears_trace.py` with it.

## Rollback

`git revert <phase-3 commit>`: removes both new files and restores `agents/plan-reconciler.md` and
the Step 8 / Step 9 paragraphs of `commands/analyze.md`. Phase 1's edits to `commands/analyze.md`
sit in other regions and survive the revert; revert phase 3 before phase 1 if both go. Nothing is
deployed by this phase, so there is nothing to undo under `~/.claude/`.
