#!/usr/bin/env python3
"""Regression tests for the swarm write-set gate.

This repo has no test runner, no lint and no CI (CLAUDE.md), so the harness brings its
own: Python 3 standard library only, no pytest, run it directly.

    python3 skills/swarm/tests/test_plan_graph.py              # the repo copy
    python3 ~/.claude/skills/swarm/tests/test_plan_graph.py    # the INSTALLED copy

Both spellings matter. `sync.sh` COPIES rather than symlinks, so the installed copy is
the one every swarm actually runs and is the one a fix must finally be asserted
against. The harness imports `plan_graph` from its own parent directory and shells out
to the `plan_graph.py` beside it, so whichever tree it is run from is the tree it tests.

THE CASE THAT WAS NEVER COVERED is the linked worktree. `/analyze` always cuts one, and
in a worktree `.git` is a FILE, not a directory -- so the gate's root walk ran to `/`,
found no phase plans, reported every write set as empty, and printed "no file is
written by two phases" over a plan set that collided. Tests 1 and 2 build a real repo,
`git worktree add` a real linked worktree, put a real plan set inside, and assert the
gate finds the write sets and exits 2.

Each test builds its tree under tempfile.mkdtemp() and removes it; nothing is written
anywhere else. The module under test stays read-only (invariant 3).
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SWARM = os.path.dirname(HERE)
sys.path.insert(0, SWARM)

import plan_graph  # noqa: E402

GATE = os.path.join(SWARM, "plan_graph.py")


# ------------------------------------------------------------------------- fixtures

INDEX_HEAD = """# Plan: Demo

**Slug:** demo
**Phases:** {n}
**Status:** planned

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
"""

INDEX_ROW = "| {n} | Phase {n} | R1 | `src` | {k} | {dep} | NORMAL | `{plan}` | — | — |\n"

INDEX_TAIL = "\n## Rollback\n"

PHASE = """# Phase {n}: {title}

## Files

| File | Action | What changes |
|---|---|---|
{rows}

## Verification

**Exit criteria:** it works.
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def phase_plan(n, title, files):
    rows = "\n".join(f"| `{p}` | {a} | something |" for p, a in files)
    return PHASE.format(n=n, title=title, rows=rows)


def plan_set(root, index_rel, *phases, deps=None):
    """Write an N-phase plan set into `root`; return the absolute index path.

    `phases` is one `[(path, action)]` list per phase, in order. `deps` is an optional
    list of `Depends on` cell strings of the same length, defaulting to no dependency
    at all -- i.e. every phase in wave 0, which is what makes a shared path concurrent.
    """
    deps = deps or ["—"] * len(phases)
    rows = ""
    for i, files in enumerate(phases, 1):
        rel = f".workflows/plan/demo/phase-{i}.md"
        write(os.path.join(root, rel), phase_plan(i, f"Phase {i}", files))
        rows += INDEX_ROW.format(n=i, k=len(files), dep=deps[i - 1], plan=rel)
    index = os.path.join(root, index_rel)
    write(index, INDEX_HEAD.format(n=len(phases)) + rows + INDEX_TAIL)
    return index


SHARED = [("src/one.py", "modify"), ("src/shared.py", "modify")]
SHARED2 = [("src/two.py", "modify"), ("src/shared.py", "modify")]


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


def gate_exit(index, cwd=None):
    """The CLI's exit code -- the thing the orchestrator's Step 3b actually reads."""
    out = subprocess.run([sys.executable, GATE, index], cwd=cwd,
                         capture_output=True, text=True, timeout=60)
    return out.returncode


def _real(path):
    """realpath, but None stays None -- so a module with no `root` key reads as None
    in the failure line instead of silently resolving to the process cwd."""
    return os.path.realpath(path) if path else None


def collision(graph, path):
    for c in graph.get("collisions", []):
        if c["path"] == path:
            return c
    return None


# --------------------------------------------------------------------------- 1 and 2
# The linked worktree, both index layouts `/analyze` produces. `.git` is a FILE here.

def _worktree_case(label, index_rel):
    tmp = tempfile.mkdtemp(prefix="pg-wt-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        ok(f"{label}: .git is a file, not a directory",
           os.path.isfile(os.path.join(wt, ".git")))

        index = plan_set(wt, index_rel, SHARED, SHARED2)
        g = plan_graph.build(index)

        eq(f"{label}: root is the worktree", _real(g.get("root")),
           os.path.realpath(wt))
        eq(f"{label}: no plan went missing", g["missing_plans"], [])
        eq(f"{label}: phase 1 write set", g["phases"][0]["writes"],
           ["src/one.py", "src/shared.py"])
        eq(f"{label}: phase 2 write set", g["phases"][1]["writes"],
           ["src/shared.py", "src/two.py"])

        hit = collision(g, "src/shared.py")
        ok(f"{label}: the shared file is reported", hit is not None)
        if hit:
            eq(f"{label}: both phases own it", hit["written_by"], [1, 2])
            eq(f"{label}: they are concurrent", hit["concurrent"], [[1, 2]])
            ok(f"{label}: verdict is ISOLATE", hit["verdict"].startswith("ISOLATE"))

        eq(f"{label}: exits 2, not 1", gate_exit(index), 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_worktree_docs_plans_index():
    _worktree_case("worktree + docs/plans index", "docs/plans/DEMO_PLAN.md")


@case
def test_worktree_root_index():
    _worktree_case("worktree + root index", "DEMO_PLAN.md")


# --------------------------------------------------------------------------------- 3
# The main checkout still works -- `.git` is a directory there.

@case
def test_main_checkout():
    tmp = tempfile.mkdtemp(prefix="pg-main-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        ok("main checkout: .git is a directory",
           os.path.isdir(os.path.join(repo, ".git")))
        index = plan_set(repo, "docs/plans/DEMO_PLAN.md", SHARED, SHARED2)
        g = plan_graph.build(index)
        eq("main checkout: root is the repo", _real(g.get("root")),
           os.path.realpath(repo))
        eq("main checkout: no plan went missing", g["missing_plans"], [])
        eq("main checkout: exits 2", gate_exit(index), 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------------- 4
# Outside any git repo: degrade, never crash. The probe answers where git cannot.

@case
def test_outside_any_repo():
    tmp = tempfile.mkdtemp(prefix="pg-bare-")
    try:
        root = os.path.join(tmp, "tree")
        index = plan_set(root, "docs/plans/DEMO_PLAN.md", SHARED, SHARED2)
        ok("outside a repo: there is no .git", not os.path.exists(os.path.join(root, ".git")))
        g = plan_graph.build(index)
        eq("outside a repo: the probe finds the root", _real(g.get("root")),
           os.path.realpath(root))
        eq("outside a repo: no plan went missing", g["missing_plans"], [])
        eq("outside a repo: exits 2, does not crash", gate_exit(index), 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------------- 5
# Most severe wins. The MODIFY phase is numbered FIRST on purpose: under the old
# first-in-index-order rule this reported `modify`/ISOLATE on a regenerated artifact.

@case
def test_severity_most_severe_wins():
    tmp = tempfile.mkdtemp(prefix="pg-sev-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(
            wt, "DEMO_PLAN.md",
            [("web/data/x.json", "modify")],          # phase 1 -- the LOWER number
            [("web/data/x.json", "regenerate")],      # phase 2
        )
        g = plan_graph.build(index)
        hit = collision(g, "web/data/x.json")
        ok("severity: the shared path is reported", hit is not None)
        if hit:
            eq("severity: generated beats modify regardless of phase order",
               hit["kind"], "generated")
            ok("severity: verdict is ORDER, not ISOLATE",
               hit["verdict"].startswith("ORDER"))
        eq("severity: exits 2", gate_exit(index), 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_severity_table():
    eq("binary outranks generated", plan_graph.most_severe(["generated", "binary"]), "binary")
    eq("order does not matter", plan_graph.most_severe(["binary", "generated"]), "binary")
    eq("generated outranks modify", plan_graph.most_severe(["modify", "generated"]), "generated")
    eq("modify outranks create", plan_graph.most_severe(["create", "modify"]), "modify")
    eq("a read never softens a verdict", plan_graph.most_severe(["read", "binary"]), "binary")
    eq("reads alone fall back to the default", plan_graph.most_severe(["read"]), "modify")
    eq("nothing at all falls back", plan_graph.most_severe([]), "modify")
    eq("an unknown class outranks modify",
       plan_graph.most_severe(["modify", "frobnicated"]), "frobnicated")
    eq("an unknown class never reaches binary",
       plan_graph.most_severe(["binary", "frobnicated"]), "binary")


# --------------------------------------------------------------------------------- 6
# A genuinely clean set exits 0 -- and a shared file in different waves is not a
# collision to act on.

@case
def test_clean_set():
    tmp = tempfile.mkdtemp(prefix="pg-clean-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md",
                         [("src/one.py", "modify")],
                         [("src/two.py", "create")])
        g = plan_graph.build(index)
        eq("clean: nothing collides", g["collisions"], [])
        eq("clean: no plan went missing", g["missing_plans"], [])
        eq("clean: exits 0", gate_exit(index), 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_sequential_is_not_concurrent():
    tmp = tempfile.mkdtemp(prefix="pg-seq-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md", SHARED, SHARED2, deps=["—", "1"])
        g = plan_graph.build(index)
        hit = collision(g, "src/shared.py")
        ok("sequential: the shared file is still reported", hit is not None)
        if hit:
            eq("sequential: not concurrent", hit["concurrent"], [])
            ok("sequential: verdict says so", hit["verdict"].startswith("sequential"))
        eq("sequential: exits 0", gate_exit(index), 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------------- 7
# A plan set whose phase plans really are absent must still exit 1. The fix must not
# turn "could not read" into a false all-clear by probing until something resolves.

@case
def test_missing_plans_still_exit_1():
    tmp = tempfile.mkdtemp(prefix="pg-miss-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md", SHARED, SHARED2)
        os.remove(os.path.join(wt, ".workflows/plan/demo/phase-1.md"))
        os.remove(os.path.join(wt, ".workflows/plan/demo/phase-2.md"))
        g = plan_graph.build(index)
        eq("missing: both plans reported missing", len(g["missing_plans"]), 2)
        eq("missing: exits 1", gate_exit(index), 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------ 10 and 11
# THE FALSE ALL-CLEAR. Fixing the root removes the dominant CAUSE of a missing plan,
# not the reassuring sentence printed over one. A plan file genuinely absent, a typo'd
# `Plan` cell, a phase planned but not yet written -- each still leaves a write set
# unknown, and the old render said "no file is written by two phases." anyway. That
# exact sentence is what R1 names: the gate returned "could not read" while
# simultaneously printing an all-clear.

@case
def test_missing_plan_suppresses_the_all_clear():
    tmp = tempfile.mkdtemp(prefix="pg-false-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md",
                         [("src/one.py", "modify")],
                         [("src/two.py", "modify")])
        os.remove(os.path.join(wt, ".workflows/plan/demo/phase-2.md"))

        g = plan_graph.build(index)
        text = plan_graph.render(g)
        eq("false all-clear: one plan is missing", len(g["missing_plans"]), 1)
        eq("false all-clear: nothing collides among what could be read",
           g["collisions"], [])
        ok("false all-clear: the all-clear sentence is NOT printed",
           "no file is written by two phases." not in text)
        ok("false all-clear: the output says so plainly", "INCOMPLETE" in text)
        ok("false all-clear: it counts the unknown write sets",
           "1 write set is unknown" in text)
        ok("false all-clear: it still names the root it looked under",
           "resolved against root:" in text)
        eq("false all-clear: still exits 1", gate_exit(index), 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_missing_plan_caveats_the_collision_summary():
    """The symmetric case: the `N of M shared files` tally is also partial."""
    tmp = tempfile.mkdtemp(prefix="pg-partial-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md", SHARED, SHARED2,
                         [("src/three.py", "modify")])
        os.remove(os.path.join(wt, ".workflows/plan/demo/phase-3.md"))

        g = plan_graph.build(index)
        text = plan_graph.render(g)
        eq("partial tally: one plan is missing", len(g["missing_plans"]), 1)
        ok("partial tally: the real collision is still found",
           collision(g, "src/shared.py") is not None)
        ok("partial tally: the summary line is still printed",
           "1 of 1 shared files are written concurrently." in text)
        ok("partial tally: and it is marked partial",
           "computed over 2 of 3 phases" in text)
        ok("partial tally: it says collisions may be unlisted",
           "may be collisions this does not list" in text)
        eq("partial tally: a missing plan outranks a collision -- exits 1, not 2",
           gate_exit(index), 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@case
def test_clean_set_keeps_the_exact_old_sentence():
    """The happy path must stay byte-identical: Phase 3 and SKILL.md quote it."""
    tmp = tempfile.mkdtemp(prefix="pg-exact-")
    try:
        repo = make_repo(os.path.join(tmp, "repo"))
        wt = add_worktree(repo, os.path.join(tmp, "wt"))
        index = plan_set(wt, "DEMO_PLAN.md",
                         [("src/one.py", "modify")],
                         [("src/two.py", "create")])
        text = plan_graph.render(plan_graph.build(index))
        ok("clean: the exact sentence survives",
           text.endswith("no file is written by two phases."))
        ok("clean: nothing is marked incomplete", "INCOMPLETE" not in text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------------- 8
# An index with no phase table is an error, not an empty clean set.

@case
def test_no_phase_table_exits_1():
    tmp = tempfile.mkdtemp(prefix="pg-nt-")
    try:
        index = os.path.join(tmp, "DEMO_PLAN.md")
        write(index, "# Plan: Demo\n\n**Slug:** demo\n\n## Why\n\nnothing here.\n")
        g = plan_graph.build(index)
        ok("no phase table: an error", bool(g.get("error")))
        eq("no phase table: exits 1", gate_exit(index), 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------- driver

def main():
    if not have_git():
        print("test_plan_graph: git is not on PATH; the worktree cases cannot run",
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
    print(f"test_plan_graph: all assertions passed ({len(RUN)} cases) "
          f"against {GATE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
