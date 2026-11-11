#!/usr/bin/env python3
"""A first-in-first-out lease on a resource that several Claude Code sessions share.

WHY THIS EXISTS. Worktrees isolate files, not the services a suite talks to. MEASURED
2026-11-11 on mcp-notes `session-fork-awareness`: phases 2 and 5 ran `npm run test:int`
against one Postgres database at once, and the coordinator ran a third suite beside them.
Every integration file truncates every table, and each truncate waits on a disk sync, so
a suite that takes ~5 minutes alone took ~30. The phases then wrote their own wait loops
(`until ! pgrep -f vitest`), which matched the coordinator's unrelated run and each
other, and would have started both phases at the same instant the moment it cleared.
A wait that names no holder and keeps no order is not a schedule.

THE MECHANISM. One directory per repo and resource, under the repo's COMMON git dir, so
every worktree of the repo shares it and no clone of it ever sees it:

    <git-common-dir>/swarm-leases/<resource>/
        queue.lock        held for a few milliseconds while the queue is read or changed
        seq               the last ticket number handed out
        tickets/<seq>.json  one per caller: who, where, what, when, its priority
        slot-<i>.lock     `max_concurrent` of them; a holder keeps one flock'd

A holder is whoever holds a slot's flock, not whoever a ticket names. The wrapper opens
the slot, takes the lock, and passes the descriptor to the child (`pass_fds`), so the
lock lives exactly as long as the work: the kernel drops it when the last process
holding the descriptor exits, however it exits. A wrapper killed with -9 while its test
run carries on still holds the resource -- correctly, since the resource is still in
use -- and nothing is ever left locked by a process that is gone.

A waiting ticket whose pid is dead is deleted on the next look at the queue. Order is
(priority, seq): `--front` gives one ticket a priority below everyone else's, which is
the coordinator putting the phase on the critical path first.

NEVER LOSES THE EXIT CODE. `lease NAME -- CMD...` returns CMD's exit status, or 128+N
for a signal. Waiting past `--wait-max` returns 75 (EX_TEMPFAIL) without running CMD.
"""

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

WAIT_EXIT = 75                      # EX_TEMPFAIL: the queue did not reach us in time
POLL = 0.5
NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
CONFIG = os.path.join(".workflows", "swarm.json")


# ------------------------------------------------------------------------- config

def resources(root):
    """The `resources` a repo declares in .workflows/swarm.json, normalised; {} when none.

    Malformed means undeclared, as everywhere else that file is read: a stray comma must
    not turn a missing declaration into a refused command.
    """
    try:
        with open(os.path.join(root, CONFIG), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}
    decl = raw.get("resources") if isinstance(raw, dict) else None
    if not isinstance(decl, dict):
        return {}
    out = {}
    for name, spec in decl.items():
        if not isinstance(name, str) or not NAME_OK.match(name) or not isinstance(spec, dict):
            continue
        match = spec.get("match")
        match = [m for m in match if isinstance(m, str) and m.strip()] \
            if isinstance(match, list) else []
        isolate = spec.get("isolate") if spec.get("isolate") in ("per-checkout", "none") else "none"
        cap = spec.get("max_concurrent")
        cap = cap if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 1 else None
        probe = spec.get("probe") if isinstance(spec.get("probe"), str) else None
        out[name] = {"match": match, "isolate": isolate, "max_concurrent": cap,
                     "probe": probe, "notes": spec.get("notes") or ""}
    return out


def needs_lease(spec):
    """A shared resource always does; an isolated one only when it bounds concurrency."""
    return spec["isolate"] == "none" or spec["max_concurrent"] is not None


def capacity(spec):
    return (spec or {}).get("max_concurrent") or 1


def matches(spec, command):
    """True when a command line uses this resource. A pattern is a regex; a pattern that
    does not compile is taken literally."""
    for pattern in spec["match"]:
        try:
            if re.search(pattern, command):
                return True
        except re.error:
            if pattern in command:
                return True
    return False


def resource_for(decl, command):
    """(name, spec) of the first declared resource this command uses, or (None, None)."""
    for name, spec in decl.items():
        if matches(spec, command):
            return name, spec
    return None, None


# ------------------------------------------------------------------------- the queue

def _git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def toplevel(start):
    return _git("rev-parse", "--show-toplevel", cwd=start)


def lease_dir(start, resource):
    """<git-common-dir>/swarm-leases/<resource>, shared by every worktree of the repo."""
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=start)
    if not common:
        return None
    return Path(common) / "swarm-leases" / resource


@contextmanager
def queue_lock(d):
    d.mkdir(parents=True, exist_ok=True)
    (d / "tickets").mkdir(exist_ok=True)
    with open(d / "queue.lock", "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tickets(d):
    out = []
    for f in sorted((d / "tickets").glob("*.json")):
        try:
            t = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        t["_file"] = str(f)
        out.append(t)
    return out


def slot_free(path):
    """True when nobody holds this slot. Probing takes the lock for an instant."""
    with open(path, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(fh, fcntl.LOCK_UN)
        return True


def prune(d):
    """Drop tickets whose owner is gone: a waiter with a dead pid, or a holder whose
    slot nobody holds any more (the wrapper and its child have both exited)."""
    for t in tickets(d):
        dead = not alive(t.get("pid", -1))
        holding = t.get("state") == "holding"
        orphan = holding and t.get("slot") is not None and \
            slot_free(d / f"slot-{t['slot']}.lock")
        if (dead and not holding) or orphan:
            try:
                os.unlink(t["_file"])
            except OSError:
                pass


def order(ts):
    return sorted((t for t in ts if t.get("state") == "waiting"),
                  key=lambda t: (t.get("priority", 0), t.get("seq", 0)))


def who(t):
    if t.get("phase"):
        return f"p{t['phase']}"
    return t.get("label") or f"pid {t.get('pid')}"


def age(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}m" if seconds >= 60 else f"{seconds}s"


def enqueue(d, command, cwd, environ):
    with queue_lock(d):
        seq_file = d / "seq"
        try:
            seq = int(seq_file.read_text().strip() or 0) + 1
        except (OSError, ValueError):
            seq = 1
        seq_file.write_text(str(seq))
        ticket = {"seq": seq, "pid": os.getpid(), "state": "waiting", "priority": 0,
                  "slug": environ.get("SWARM_SLUG"), "phase": environ.get("SWARM_PHASE"),
                  "label": environ.get("SWARM_LEASE_LABEL"), "cwd": cwd,
                  "command": command[:300], "enqueued": time.time(), "started": None,
                  "slot": None}
        path = d / "tickets" / f"{seq:08d}.json"
        path.write_text(json.dumps(ticket))
    return seq, path


def try_acquire(d, seq, path, cap):
    """Under the queue lock: if this ticket's turn has come and a slot is free, take the
    slot and return its open file. Else (None, the line to show while waiting)."""
    with queue_lock(d):
        prune(d)
        ts = tickets(d)
        waiting = order(ts)
        rank = next((i for i, t in enumerate(waiting) if t["seq"] == seq), None)
        free = []
        for i in range(cap):
            if slot_free(d / f"slot-{i}.lock"):
                free.append(i)
        if rank is not None and rank < len(free):
            fh = open(d / f"slot-{free[rank]}.lock", "a+")
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                fh.close()
            else:
                t = json.loads(path.read_text())
                t.update(state="holding", started=time.time(), slot=free[rank])
                path.write_text(json.dumps(t))
                return fh, None
        holders = [t for t in ts if t.get("state") == "holding"]
        now = time.time()
        held = ", ".join(f"{who(t)} ({age(now - (t.get('started') or now))})" for t in holders) \
            or "a process outside the queue"
        pos = (rank or 0) + 1
        return None, f"held by {held}, you are #{pos}"


def run(resource, cmd, start=None, wait_max=None, cap=None, environ=None, out=sys.stderr):
    """Wait for the lease, run cmd holding it, return cmd's exit status."""
    start = start or os.getcwd()
    environ = os.environ if environ is None else environ
    if not NAME_OK.match(resource):
        print(f"lease: bad resource name {resource!r}", file=out)
        return 2
    d = lease_dir(start, resource)
    if d is None:
        print("lease: not inside a git repository; running without a lease", file=out)
        return subprocess.call(cmd)
    if cap is None:
        root = toplevel(start)
        cap = capacity(resources(root).get(resource)) if root else 1
    seq, path = enqueue(d, " ".join(cmd), start, environ)
    fh, last, began = None, None, time.time()
    try:
        while fh is None:
            fh, line = try_acquire(d, seq, path, cap)
            if fh is None:
                key = re.sub(r" \(\d+[sm]\)", "", line)    # a new line per holder or place, not per tick
                if key != last:
                    print(f"lease: {resource} busy: {line}", file=out, flush=True)
                    last = key
                if wait_max is not None and time.time() - began > wait_max:
                    print(f"lease: gave up on {resource} after {age(wait_max)}; "
                          f"nothing was run", file=out, flush=True)
                    return WAIT_EXIT
                time.sleep(POLL)
        if last is not None or environ.get("SWARM_LEASE_VERBOSE"):
            print(f"lease: {resource} acquired after {age(time.time() - began)}",
                  file=out, flush=True)
        child = subprocess.Popen(cmd, pass_fds=(fh.fileno(),))
        forward = lambda sig, _frame: child.send_signal(sig)   # noqa: E731
        old = {s: signal.signal(s, forward) for s in (signal.SIGINT, signal.SIGTERM,
                                                      signal.SIGHUP)}
        try:
            code = child.wait()
        finally:
            for s, h in old.items():
                signal.signal(s, h)
        return code if code >= 0 else 128 - code
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
        if fh is not None:
            fh.close()


def status(start, resource=None):
    """{resource: {capacity, holding: [...], waiting: [...]}} for the repo at start."""
    common = _git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=start)
    if not common:
        return {}
    base = Path(common) / "swarm-leases"
    root = toplevel(start)
    decl = resources(root) if root else {}
    names = [resource] if resource else sorted(
        {p.name for p in base.iterdir() if p.is_dir()} if base.is_dir() else set())
    now, out = time.time(), {}
    for name in names:
        d = base / name
        if not d.is_dir():
            out[name] = {"capacity": capacity(decl.get(name)), "holding": [], "waiting": []}
            continue
        with queue_lock(d):
            prune(d)
            ts = tickets(d)
        view = lambda t: {"ticket": t["seq"], "who": who(t), "pid": t.get("pid"),   # noqa: E731
                          "cwd": t.get("cwd"), "command": t.get("command"),
                          "for": age(now - (t.get("started") or t.get("enqueued") or now))}
        out[name] = {"capacity": capacity(decl.get(name)),
                     "holding": [view(t) for t in ts if t.get("state") == "holding"],
                     "waiting": [view(t) for t in order(ts)]}
    return out


def front(start, resource, seq):
    """Move one waiting ticket ahead of every other. True when it was found."""
    d = lease_dir(start, resource)
    if d is None or not d.is_dir():
        return False
    with queue_lock(d):
        ts = tickets(d)
        lowest = min((t.get("priority", 0) for t in ts), default=0)
        for t in ts:
            if t["seq"] == seq and t.get("state") == "waiting":
                t["priority"] = lowest - 1
                f = t.pop("_file")
                Path(f).write_text(json.dumps(t))
                return True
    return False
