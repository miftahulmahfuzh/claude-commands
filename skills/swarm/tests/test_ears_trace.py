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
