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
