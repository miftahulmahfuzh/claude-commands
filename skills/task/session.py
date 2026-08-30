#!/usr/bin/env python3
"""Rename the Claude Code session this command is running inside.

A session working card 17 should be called `task-17`. With five terminals open the
derived names -- `jmtarot-8f`, `jmtarot-d4` -- say which repo but not which card, so
finding the right window means reading scrollback, and `/resume` a week later offers a
list of near-identical titles. The name is the only per-session label the user ever
sees, in the tab title, in `/resume`, and in the peer list other sessions address.

WHY THIS IS NOT JUST A FILE WRITE. The name lives in ~/.claude/sessions/<pid>.json, and
writing it there does change what `/resume` lists -- MEASURED, and it is a trap: the
running process keeps its own copy, so the tab title and the name peers address by both
stay stale until it restarts. The rename has to reach the process.

It has a documented way in: every tool this session runs inherits

    CLAUDE_CODE_MESSAGING_SOCKET   the session's own AF_UNIX socket
    CLAUDE_CODE_MESSAGING_TOKEN    the token that authenticates a connection to it
    CLAUDE_CODE_SESSION_ID         the session the message must name

and the socket speaks newline-delimited JSON: an `auth` line, then messages. This sends
the same `{"type":"control","action":"rename"}` that FleetView sends when it renames a
session from another window, so the process performs its own rename and every surface
follows. `nameSource` reads `peer` afterwards, which is exactly what happened.

NEVER FAILS THE CALLER. A name is a convenience and the card is the work, so every way
this can go wrong -- no socket in the environment (an SDK or print session), a stale
socket, a refused connection -- prints `renamed: false` with a reason and exits 0. A
session that could not be renamed is a session with a duller name, not a broken task.

    python3 session.py rename task-17
    python3 session.py name                 # what this session is called now
"""

import argparse
import json
import os
import re
import socket
import sys
from pathlib import Path

SOCKET_ENV = "CLAUDE_CODE_MESSAGING_SOCKET"
TOKEN_ENV = "CLAUDE_CODE_MESSAGING_TOKEN"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"

# The tab title, a `/resume` row and a peer address all render this, so it is kept to
# what all three display cleanly rather than to what the socket would accept.
MAX_NAME = 60


def slug(name):
    """`task-17`, or the nearest safe thing to whatever was passed."""
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name).strip()).strip("-.")
    return out[:MAX_NAME] or "task"


def session_record():
    """This session's row in ~/.claude/sessions, matched on the session id.

    Read-only, and only ever used to report the name -- never to write one. Matching on
    CLAUDE_CODE_SESSION_ID rather than on the pid is deliberate: the pid in the filename
    is the process the record was created for, and a tool subprocess is not it.
    """
    sid = os.environ.get(SESSION_ENV)
    if not sid or not SESSIONS_DIR.is_dir():
        return None
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            rec = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if rec.get("sessionId") == sid:
            return rec
    return None


def send(lines, timeout=3.0):
    """Write newline-delimited JSON to the session socket and close the write side.

    Closing write is what the protocol's own documented client does (`nc -N`); without
    it the server waits for more lines and the connection sits open until it times out.
    Nothing is read back: the rename is applied by the receiving process, and a reply
    this command waited on would be one more thing that could hang a task loop.
    """
    path = os.environ.get(SOCKET_ENV)
    if not path:
        return False, f"{SOCKET_ENV} is not set — this is not an interactive session"
    if not Path(path).exists():
        return False, f"{path} does not exist"
    payload = "".join(json.dumps(line) + "\n" for line in lines).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(path)
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def rename(name):
    token = os.environ.get(TOKEN_ENV)
    if not token:
        return {"renamed": False, "reason": f"{TOKEN_ENV} is not set"}
    wanted = slug(name)
    before = (session_record() or {}).get("name")
    if before == wanted:
        return {"renamed": False, "name": wanted, "reason": "already named that"}
    control = {"type": "control", "action": "rename", "name": wanted}
    sid = os.environ.get(SESSION_ENV)
    if sid:
        control["session_id"] = sid
    ok, err = send([{"type": "auth", "token": token}, control])
    if not ok:
        return {"renamed": False, "name": before, "requested": wanted, "reason": err}
    return {"renamed": True, "name": wanted, "from": before}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rename", help="rename this session, e.g. task-17")
    p.add_argument("name")
    sub.add_parser("name", help="print this session's current name")
    sub.add_parser("selftest", help="offline checks, no socket needed")
    args = parser.parse_args(argv)

    if args.cmd == "rename":
        print(json.dumps(rename(args.name), indent=2))
    elif args.cmd == "name":
        rec = session_record() or {}
        print(json.dumps({"name": rec.get("name"), "source": rec.get("nameSource"),
                          "sessionId": rec.get("sessionId")}, indent=2))
    else:
        return selftest()
    return 0


def selftest():
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    eq("plain", slug("task-17"), "task-17")
    eq("number", slug(17), "17")
    eq("spaces collapse", slug("task 17"), "task-17")
    eq("slashes are not paths", slug("owner/repo#17"), "owner-repo-17")
    eq("trims junk edges", slug("--task-17--"), "task-17")
    eq("never empty", slug("///"), "task")
    eq("length capped", len(slug("t" * 200)), MAX_NAME)

    # No socket in the environment must be a report, never an exception: a task loop
    # that died because it could not rename a window would be an absurd way to lose work.
    saved = {k: os.environ.pop(k, None) for k in (SOCKET_ENV, TOKEN_ENV)}
    try:
        eq("no token is a soft no", rename("task-1")["renamed"], False)
        os.environ[TOKEN_ENV] = "x"
        out = rename("task-1")
        eq("no socket is a soft no", out["renamed"], False)
        eq("and says why", SOCKET_ENV in out["reason"], True)
    finally:
        os.environ.pop(TOKEN_ENV, None)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    if failures:
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        return 1
    print("selftest: all assertions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
