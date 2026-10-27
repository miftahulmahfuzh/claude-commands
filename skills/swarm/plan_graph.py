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
from swarm import git, parse_index, waves  # noqa: E402

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


# --------------------------------------------------------------------- the repo root

# How far above the index to look when git cannot answer. `/analyze` files the index at
# `<root>/docs/plans/<SLUG>_PLAN.md` when `docs/` exists and at `<root>/<SLUG>_PLAN.md`
# when it does not, so the root is zero to two levels above the index's own directory.
# Three gives one level of slack without reaching so far that an unrelated ancestor's
# `.workflows/` can answer for this plan set.
ROOT_LOOKUP_DEPTH = 3


def _ancestors(start, depth=ROOT_LOOKUP_DEPTH):
    """`start` and its first `depth` ancestors, nearest first, no duplicates."""
    out, cur = [], start
    for _ in range(depth + 1):
        if cur not in out:
            out.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:                                 # reached "/"
            break
        cur = parent
    return out


def find_root(index_path, plans=()):
    """The directory the index's phase-plan paths are relative to.

    The old walk looked for a `.git` DIRECTORY, and in a linked worktree `.git` is a
    FILE -- a `gitdir:` pointer. `/analyze` always cuts a worktree, so the walk ran to
    `/` on every standard plan set and fell back to `dirname(dirname(index))`, which is
    wrong for both layouts `/analyze` produces. The gate then found no phase plans,
    reported every write set as empty, and still printed "no file is written by two
    phases" -- an all-clear over an analysis that never ran.

    Three answers are collected, in order of authority, and the first that actually
    resolves one of `plans` wins -- so a right-looking root that resolves nothing can
    never shadow one that does:

      1. `git rev-parse --show-toplevel`, run with cwd = the index's DIRECTORY, not the
         process cwd: a coordinator's cwd is often a different repo entirely. This is
         the house style (`swarm.py:161 main_worktree` asks git the same class of
         question) and it handles worktrees, submodules and `.git` files uniformly.
         `swarm.py`'s `git()` maps a missing binary and a non-zero exit alike to None,
         so no-git degrades instead of raising (invariant 4).
      2. an `os.path.exists` walk for `.git`, for a machine with no git on PATH.
      3. the index's own directory and its nearest ancestors, probed against the phase
         plan paths the index actually names -- the replacement for the old fallback,
         which was correct for neither layout and only ever worked by accident.
    """
    index_dir = os.path.dirname(os.path.abspath(index_path)) or os.getcwd()

    candidates = []
    top = git("rev-parse", "--show-toplevel", cwd=index_dir)
    if top and os.path.isdir(top):
        candidates.append(os.path.abspath(top))

    walk = index_dir
    while True:
        if os.path.exists(os.path.join(walk, ".git")):
            candidates.append(walk)
            break
        parent = os.path.dirname(walk)
        if parent == walk:
            break
        walk = parent

    candidates.extend(_ancestors(index_dir))

    ordered, seen = [], set()
    for cand in candidates:
        if cand not in seen:
            seen.add(cand)
            ordered.append(cand)

    relative = [p for p in plans if p and not os.path.isabs(p)]
    for cand in ordered:
        if any(os.path.exists(os.path.join(cand, p)) for p in relative):
            return cand
    return ordered[0] if ordered else index_dir


# ------------------------------------------------------------------------- severity

# Most severe first. When two phases declare one path with different actions the WORST
# class wins, never the first phase in index order (invariant 6: BLOCK > ORDER >
# ISOLATE). The old `kind = next(...)` took whichever phase was numbered lower, so a
# generated or binary path that a lower-numbered phase called `modify` was reported
# ISOLATE -- and a wrong ISOLATE on a database is the one error whose cost is rows that
# no longer exist. A rank table rather than a chain of ifs, so a class added later is
# one row here and one row in `_verdict`.
SEVERITY = {"binary": 40, "generated": 30, "modify": 20, "create": 10}

# A class this table has not heard of -- a later per-repo configuration may mint one --
# outranks `modify` but never reaches `binary`: never silently downgraded to ISOLATE,
# never falsely escalated to BLOCK.
SEVERITY_UNKNOWN = 25


def most_severe(kinds, default="modify"):
    """The worst class among the ways the writing phases declared one path.

    `read` is not a write and never participates: a path is only here because some
    phase writes it, and a third phase that merely reads it cannot soften the verdict.
    """
    ranked = sorted({k for k in kinds if k and k != "read"})
    if not ranked:
        return default
    return max(ranked, key=lambda k: SEVERITY.get(k, SEVERITY_UNKNOWN))


def build(index_path):
    meta, phases = parse_index(open(index_path, encoding="utf-8").read())
    if not phases:
        return {"error": f"{index_path} has no phase table"}

    # The plan paths in the index are repo-relative, so the root has to be found before
    # any of them can be opened -- and it is found FROM them, which is why the index is
    # parsed first now.
    repo = find_root(index_path, [p.get("plan") or "" for p in phases])

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

    by_n = {p["n"]: p for p in phases}
    collisions = []
    for path, owners in sorted(writes.items()):
        if len(owners) < 2:
            continue
        # Every way the WRITING phases declared this path, worst one wins -- never the
        # first phase in index order. `owners` holds writers only, so no `read` is here.
        kind = most_severe([by_n[owner]["files"].get(path) for owner in owners])
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
        "root": repo,
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
        out.append(f"  resolved against root: {g.get('root')}")
    out.append("")
    # "no collision was FOUND" and "no collision EXISTS" are different statements, and
    # only the first is true when a write set is unknown. The old text asserted the
    # second unconditionally, so the gate printed an all-clear over an analysis that
    # never ran -- the reassuring sentence that let the worktree bug survive four real
    # plan sets. The clean sentence is kept byte-identical; the incomplete one shares
    # no prefix with it, so neither a reader nor a grep can mistake one for the other.
    unknown = len(g["missing_plans"])
    known = len(g["phases"]) - unknown
    if not g["collisions"]:
        if unknown:
            out.append(f"INCOMPLETE: no collision among the {known} of {len(g['phases'])} "
                       f"phases whose plan could be read. {unknown} write set"
                       f"{' is' if unknown == 1 else 's are'} unknown, so this is not "
                       f"an all-clear.")
        else:
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
    if unknown:
        # The same partiality, on the other branch: this count was computed over the
        # phases that could be read, and a phase whose plan is unknown may collide with
        # any of them.
        out.append(f"INCOMPLETE: computed over {known} of {len(g['phases'])} phases. "
                   f"{unknown} write set{' is' if unknown == 1 else 's are'} unknown, "
                   f"so there may be collisions this does not list.")
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
