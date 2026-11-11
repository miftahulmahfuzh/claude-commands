#!/usr/bin/env python3
"""Tests for the resource lease (lease.py, `swarm.py lease`).

Stdlib only, no pytest, like test_plan_graph.py:

    python3 skills/swarm/tests/test_lease.py              # the repo copy
    python3 ~/.claude/skills/swarm/tests/test_lease.py    # the INSTALLED copy

Every case runs REAL processes against a real git repo under tempfile.mkdtemp(): the lease
is a claim about what several processes do to one flock at once, and a test that mocked
the processes would be testing the mock.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SWARM_DIR = os.path.dirname(HERE)
sys.path.insert(0, SWARM_DIR)

import lease  # noqa: E402

SWARM = os.path.join(SWARM_DIR, "swarm.py")
FAILURES = []
RUN = []


def case(fn):
    RUN.append(fn)
    return fn


def eq(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def ok(label, cond):
    if not cond:
        FAILURES.append(label)


def repo():
    d = tempfile.mkdtemp(prefix="lease-test-")
    subprocess.run(["git", "init", "-q", d], check=True)
    subprocess.run(["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    return d


def leased(d, resource, cmd, *extra, env=None):
    """Start `swarm.py lease` in the background; its stderr is captured."""
    e = dict(os.environ, **(env or {}))
    return subprocess.Popen([sys.executable, SWARM, "lease", *extra, resource, "--", *cmd],
                            cwd=d, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)


def wait_for(cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def holders(d, resource):
    return lease.status(d, resource)[resource]["holding"]


def waiting(d, resource):
    return lease.status(d, resource)[resource]["waiting"]


@case
def exit_code_and_signal():
    d = repo()
    try:
        p = leased(d, "r", ["sh", "-c", "exit 7"])
        eq("the child's exit status comes back", p.wait(timeout=10), 7)
        p = leased(d, "r", ["sh", "-c", "kill -TERM $$"])
        eq("a signal death is 128+N", p.wait(timeout=10), 128 + signal.SIGTERM)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def fifo_order():
    """Three waiters behind one holder run in the order they asked."""
    d = repo()
    log = os.path.join(d, "order.log")
    try:
        first = leased(d, "r", ["sh", "-c", "sleep 1.5"])
        ok("the first caller holds", wait_for(lambda: len(holders(d, "r")) == 1))
        rest = []
        for name in ("a", "b", "c"):
            rest.append(leased(d, "r", ["sh", "-c", f"echo {name} >> {log}"]))
            ok(f"{name} is queued", wait_for(lambda n=len(rest): len(waiting(d, "r")) == n))
        for p in [first, *rest]:
            p.wait(timeout=20)
        eq("FIFO", open(log).read().split(), ["a", "b", "c"])
        err = rest[0].stderr.read()
        ok("a waiter is told who holds it and its place", "busy: held by" in err and "#1" in err)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def capacity_two():
    """max_concurrent 2: two run together, the third waits for one of them."""
    d = repo()
    try:
        os.makedirs(os.path.join(d, ".workflows"))
        with open(os.path.join(d, ".workflows", "swarm.json"), "w") as fh:
            json.dump({"resources": {"db": {"match": ["test:int"], "isolate": "per-checkout",
                                            "max_concurrent": 2}}}, fh)
        a = leased(d, "db", ["sleep", "1.5"])
        b = leased(d, "db", ["sleep", "1.5"])
        ok("two hold at once", wait_for(lambda: len(holders(d, "db")) == 2))
        c = leased(d, "db", ["true"])
        ok("the third waits", wait_for(lambda: len(waiting(d, "db")) == 1))
        eq("status reports the declared capacity", lease.status(d, "db")["db"]["capacity"], 2)
        for p in (a, b, c):
            eq("all three succeed", p.wait(timeout=20), 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def crash_releases():
    """SIGKILL the wrapper: the lease is held while its child runs, and freed after."""
    d = repo()
    try:
        p = leased(d, "r", ["sleep", "1.5"])
        ok("held", wait_for(lambda: len(holders(d, "r")) == 1))
        os.kill(p.pid, signal.SIGKILL)
        p.wait()
        ok("still held while the orphaned child runs", len(holders(d, "r")) == 1)
        q = leased(d, "r", ["true"])
        eq("the next caller gets it once the child is gone", q.wait(timeout=15), 0)
        eq("no ticket left behind", holders(d, "r") + waiting(d, "r"), [])
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def dead_waiter_is_skipped():
    d = repo()
    log = os.path.join(d, "log")
    try:
        h = leased(d, "r", ["sleep", "1.5"])
        ok("held", wait_for(lambda: len(holders(d, "r")) == 1))
        dead = leased(d, "r", ["sh", "-c", f"echo dead >> {log}"])
        ok("queued", wait_for(lambda: len(waiting(d, "r")) == 1))
        os.kill(dead.pid, signal.SIGKILL)
        dead.wait()
        live = leased(d, "r", ["sh", "-c", f"echo live >> {log}"])
        eq("the live waiter runs", live.wait(timeout=15), 0)
        h.wait(timeout=10)
        eq("the killed waiter never ran", open(log).read().split(), ["live"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def wait_max_and_front():
    d = repo()
    log = os.path.join(d, "log")
    try:
        h = leased(d, "r", ["sleep", "2.5"])
        ok("held", wait_for(lambda: len(holders(d, "r")) == 1))
        late = leased(d, "r", ["sh", "-c", f"echo late >> {log}"], "--wait-max", "0.5")
        eq("gave up without running", late.wait(timeout=10), lease.WAIT_EXIT)
        x = leased(d, "r", ["sh", "-c", f"echo x >> {log}"])
        ok("x queued", wait_for(lambda: len(waiting(d, "r")) == 1))
        y = leased(d, "r", ["sh", "-c", f"echo y >> {log}"])
        ok("y queued", wait_for(lambda: len(waiting(d, "r")) == 2))
        ticket_y = waiting(d, "r")[1]["ticket"]
        moved = subprocess.run([sys.executable, SWARM, "lease", "--front", str(ticket_y), "r"],
                               cwd=d, capture_output=True, text=True)
        eq("front moved it", moved.returncode, 0)
        for p in (h, x, y):
            p.wait(timeout=20)
        eq("the coordinator's reorder wins over FIFO", open(log).read().split(), ["y", "x"])
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def worktrees_share_one_queue():
    d = repo()
    wt = d + "-wt"
    try:
        subprocess.run(["git", "-C", d, "worktree", "add", "-q", wt], check=True)
        h = leased(d, "r", ["sleep", "1"])
        ok("held from the main checkout", wait_for(lambda: len(holders(d, "r")) == 1))
        eq("a linked worktree sees the same holder", len(holders(wt, "r")), 1)
        h.wait(timeout=10)
    finally:
        shutil.rmtree(wt, ignore_errors=True)
        shutil.rmtree(d, ignore_errors=True)


@case
def options_on_either_side():
    """MEASURED 2026-11-11: `lease pg --capacity 2 -- npm ...` acquired, then Popen'd
    "--capacity" and crashed. Options go before the --, on either side of the resource."""
    d = repo()
    try:
        for argv in (["lease", "r", "--capacity", "2", "--", "sh", "-c", "exit 4"],
                     ["lease", "--capacity", "2", "r", "--", "sh", "-c", "exit 4"],
                     ["lease", "r", "--repo", d, "--wait-max", "5", "--", "sh", "-c", "exit 4"]):
            r = subprocess.run([sys.executable, SWARM, *argv], cwd=d, capture_output=True,
                               text=True, timeout=20)
            eq(f"parsed and ran: {' '.join(argv[:5])}", (r.returncode, "Traceback" in r.stderr),
               (4, False))
        for argv in (["lease", "r"], ["lease", "r", "--"], ["lease", "r", "--", "--capacity"]):
            r = subprocess.run([sys.executable, SWARM, *argv], cwd=d, capture_output=True,
                               text=True, timeout=20)
            eq(f"refused cleanly: {argv}", (r.returncode, "Traceback" in r.stderr), (2, False))
        # The command the swarm-deck guard writes must parse.
        r = subprocess.run([sys.executable, SWARM, "lease", "r", "--repo", d, "--",
                            os.environ.get("SHELL") or "/bin/sh", "-c", "echo 'it''s'; exit 5"],
                           cwd=d, capture_output=True, text=True, timeout=20)
        eq("the guard's rewrite form runs", (r.returncode, r.stdout.strip()), (5, "its"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def failed_launch_releases():
    d = repo()
    try:
        p = leased(d, "r", ["/nonexistent/binary"])
        eq("a command that cannot start exits 127", p.wait(timeout=10), 127)
        eq("and leaves no ticket or holder", holders(d, "r") + waiting(d, "r"), [])
        eq("the next caller runs at once", leased(d, "r", ["true"]).wait(timeout=10), 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@case
def config_parsing():
    d = repo()
    try:
        eq("no file: no resources", lease.resources(d), {})
        os.makedirs(os.path.join(d, ".workflows"))
        path = os.path.join(d, ".workflows", "swarm.json")
        open(path, "w").write("{not json")
        eq("malformed: no resources", lease.resources(d), {})
        json.dump({"generated": ["x"], "resources": {
            "pg": {"match": ["npm run test:int", "scripts/test-int\\.sh"], "isolate": "per-checkout"},
            "gpu": {"match": ["train.py"], "isolate": "none"},
            "bad name!": {"match": ["x"]}, "capped": {"match": ["y"], "max_concurrent": 0}}},
            open(path, "w"))
        r = lease.resources(d)
        eq("bad names dropped", sorted(r), ["capped", "gpu", "pg"])
        eq("isolated without a cap needs no lease", lease.needs_lease(r["pg"]), False)
        eq("shared needs one", lease.needs_lease(r["gpu"]), True)
        eq("a cap below 1 is no cap; isolate defaults to none", (r["capped"]["max_concurrent"],
                                                                 r["capped"]["isolate"]),
           (None, "none"))
        eq("regex match", lease.resource_for(r, "cd x && bash scripts/test-int.sh a")[0], "pg")
        eq("no match", lease.resource_for(r, "npm test")[0], None)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
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
    print(f"test_lease: all assertions passed ({len(RUN)} cases) against {SWARM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
