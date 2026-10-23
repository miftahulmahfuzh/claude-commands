#!/usr/bin/env python3
"""The file-level dependency graph of a plan set, computed before anything is spawned.

`swarm.py waves` schedules from the `Depends on` column alone. That column records what a
phase needs to *exist* before it starts; it says nothing about what two phases in the same
wave will both *write*. Those are different questions, and the second one is what produces
the collisions: on `journal-versioning`, phases 2, 3 and 4 were correctly placed in one wave
by their dependencies and all three wrote `engine/src/seer_engine/commands/lab.py`.

This reads each phase plan's `## Files` table -- the write set the planner declared, which is
also what `/implement` hands `pusher` as its allowlist -- and reports:

  * every file written by more than one phase, and whether those phases are concurrent
  * the fix per collision: isolate (separate worktrees, disjoint regions merge) or serialize
  * generated and binary artifacts separately, because those never textually merge

Read-only. It spawns nothing and writes nothing.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swarm import parse_index, waves  # noqa: E402

# A path whose merge is a regeneration, not a three-way text merge. Two phases writing one of
# these are not in conflict over content -- they are in conflict over WHO REGENERATES LAST,
# which is an ordering edge, not a file split. The `4 -> 6` edge on journal-versioning is
# exactly this, and its planner found it by hand.
GENERATED = (".sqlite", ".sqlite3", ".db")
REGENERATED_TEXT = ("web/data/lab.json", "lab.xlsx")


def classify(path, action):
    a = action.replace("*", "").strip().lower()
    if a.startswith("read"):
        return "read"
    if path.endswith(GENERATED):
        return "binary"
    if any(path.endswith(s) for s in REGENERATED_TEXT) or a.startswith("regenerate"):
        return "generated"
    if a.startswith("create"):
        return "create"
    return "modify"


def parse_files(text):
    """[(path, action)] from a phase plan's `## Files` table."""
    out, inside, header = [], False, False
    for line in text.splitlines():
        if re.match(r"^##\s", line):
            if inside:
                break
            inside = bool(re.match(r"^##\s+Files\s*$", line, re.I))
            header = False
            continue
        if not inside or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not header:
            header = True                                 # the | File | Action | ... row
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if len(cells) < 2:
            continue
        path = cells[0].strip().strip("`").strip()
        if not path or " " in path:                       # prose row, not a path
            continue
        out.append((path, cells[1]))
    return out


def build(index_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(index_path)))
    # the plan paths in the index are repo-relative; find the repo root by walking up
    repo = os.path.abspath(index_path)
    while repo != "/" and not os.path.isdir(os.path.join(repo, ".git")):
        repo = os.path.dirname(repo)
    if repo == "/":
        repo = root

    meta, phases = parse_index(open(index_path, encoding="utf-8").read())
    if not phases:
        return {"error": f"{index_path} has no phase table"}

    writes, missing = {}, []
    for p in phases:
        p["files"] = {}
        plan = p.get("plan") or ""
        full = plan if os.path.isabs(plan) else os.path.join(repo, plan)
        if not plan or not os.path.exists(full):
            missing.append({"phase": p["n"], "plan": plan or "(none)"})
            continue
        for path, action in parse_files(open(full, encoding="utf-8").read()):
            kind = classify(path, action)
            p["files"][path] = kind
            if kind != "read":
                writes.setdefault(path, []).append(p["n"])

    dep_waves = waves({"phases": phases})
    wave_of = {}
    for w in dep_waves:
        for n in w.get("phases", []):
            wave_of[n] = w["wave"]

    collisions = []
    for path, owners in sorted(writes.items()):
        if len(owners) < 2:
            continue
        kinds = {phases[0]["files"].get(path) for p in phases for phases in [[p]]
                 if path in p["files"]}
        kind = next((p["files"][path] for p in phases if path in p["files"]), "modify")
        by_wave = {}
        for n in owners:
            by_wave.setdefault(wave_of.get(n), []).append(n)
        concurrent = sorted(
            [sorted(v) for k, v in by_wave.items() if len(v) > 1], key=lambda g: g[0]
        )
        collisions.append({
            "path": path,
            "kind": kind,
            "written_by": sorted(owners),
            "waves": {str(k): sorted(v) for k, v in sorted(by_wave.items(), key=lambda kv: (kv[0] is None, kv[0]))},
            "concurrent": concurrent,
            "verdict": _verdict(kind, concurrent),
        })
    return {
        "slug": meta.get("slug"),
        "index": index_path,
        "phases": [{"n": p["n"], "title": p["title"], "depends_on": p["depends_on"],
                    "wave": wave_of.get(p["n"]),
                    "writes": sorted(f for f, k in p["files"].items() if k != "read")}
                   for p in phases],
        "dep_waves": [w.get("phases", w.get("cycle", [])) for w in dep_waves],
        "collisions": collisions,
        "missing_plans": missing,
    }


def _verdict(kind, concurrent):
    if not concurrent:
        return "sequential: written in different waves, no isolation needed"
    if kind == "binary":
        return "BLOCK: a binary written by concurrent phases has no merge; serialize them"
    if kind == "generated":
        return "ORDER: regenerated, not merged; add an edge so the last writer is the one that publishes"
    return "ISOLATE: separate worktrees merge cleanly IF the line regions are disjoint; else serialize or split the file"


def render(g):
    if g.get("error"):
        return g["error"]
    out = [f"plan set: {g['slug']}   phases: {len(g['phases'])}",
           f"dependency waves: {' -> '.join('[' + ', '.join(map(str, w)) + ']' for w in g['dep_waves'])}",
           ""]
    out.append("write sets")
    for p in g["phases"]:
        out.append(f"  phase {p['n']} (wave {p['wave']}, depends on {p['depends_on'] or '-'}): "
                   f"{len(p['writes'])} files")
        for f in p["writes"]:
            out.append(f"      {f}")
    if g["missing_plans"]:
        out.append("")
        out.append("phase plans not found (write set unknown, treated as empty):")
        for m in g["missing_plans"]:
            out.append(f"  phase {m['phase']}: {m['plan']}")
    out.append("")
    if not g["collisions"]:
        out.append("no file is written by two phases.")
        return "\n".join(out)
    out.append(f"shared files: {len(g['collisions'])}")
    for c in g["collisions"]:
        flag = "CONCURRENT" if c["concurrent"] else "sequential"
        out.append(f"  [{flag}] {c['path']}  ({c['kind']})")
        out.append(f"      written by phases {c['written_by']}, by wave: {c['waves']}")
        out.append(f"      {c['verdict']}")
    live = [c for c in g["collisions"] if c["concurrent"]]
    out.append("")
    out.append(f"{len(live)} of {len(g['collisions'])} shared files are written concurrently.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("index", help="path to <SLUG>_PLAN.md")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    g = build(a.index)
    print(json.dumps(g, indent=2) if a.json else render(g))
    # 1 = could not read the plan, 2 = a concurrent collision, 0 = clean. An unreadable plan
    # must NOT exit 0: a caller that reads 0 as "nothing collides" would spawn the wave on the
    # strength of an analysis that never ran.
    if g.get("error"):
        return 1
    if g.get("missing_plans"):
        return 1
    return 2 if any(c["concurrent"] for c in g.get("collisions", [])) else 0


if __name__ == "__main__":
    sys.exit(main())
