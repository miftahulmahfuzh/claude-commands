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

THE TMUX WINDOW IS RENAMED TOO, because that is the label actually on screen. Claude
Code's rename reaches the terminal's own tab title, which tmux covers up with its status
line -- so in tmux the session rename is invisible and the window keeps whatever
`automatic-rename` derived, which for every one of these is `claude`. `rename-window`
also switches `automatic-rename` off for that window, so the name then stays put.

A RENAME MUST NEVER WIDEN A LAUNCH NAME. `claude -n impl-<slug>-p2` gives a session its
peer address before it boots, which is how a swarm coordinator addresses a phase without
racing the child's own rename. A later rename to `impl-<slug>` -- the same name minus the
part that says which phase -- hands every phase of that set one address. MEASURED: a
seven-phase set had four sessions pass through the bare `impl-admin-album-file-manager`
on their way to their own numbers, and the one whose sharpening did not land stayed
there, so the coordinator's recorded address for phase 2 pointed at nothing while an
ambiguous one answered for everybody. `--no-widen` refuses that half of a rename: a name
that is a prefix of the one already held is strictly less specific, and a duller name is
worth having only when it is still unique.

    python3 session.py rename task-17
    python3 session.py rename task-17 --no-tmux
    python3 session.py rename impl-x-p2 --no-widen   # keeps a launch name that says more
    python3 session.py name                 # what this session is called now
"""

import argparse
import json
import os
import re
import socket
import subprocess
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


def widens(current, wanted):
    """Would renaming `current` -> `wanted` throw away specificity?

    True only when `wanted` is `current` with a trailing part lopped off at a separator:
    `impl-x-p2` -> `impl-x` yes, `impl-x` -> `impl-x-p2` no, `do-P0-AB-1` -> `impl-x` no.
    Prefix alone is not enough -- `task-1` -> `task-17` shares one but says something
    else entirely, and refusing it would be wrong.
    """
    if not current or current == wanted or not current.startswith(wanted):
        return False
    return current[len(wanted)] in "-_."


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


# ----------------------------------------------------------------- the tmux window

TASK_NAME = re.compile(r"^task-(\d+)$")
TMUX_ADDR = re.compile(r"(@\d+)\.(%\d+)")


def tmux(*args):
    """Run a tmux command, or return None if there is no tmux to run it against."""
    if not os.environ.get("TMUX"):
        return None
    try:
        out = subprocess.run(("tmux",) + args, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def window_name(mine, siblings):
    """What to call a window holding `mine` and, possibly, other task sessions.

    A window is one label for however many panes are in it, and MEASURED here, panes get
    shared: window @1 holds a task session and an ordinary one. So the rule is about who
    has a competing claim. An ordinary session (`tarot-app-8f`) has none -- it is a
    window that happens to also hold task 20, and `task-20` is the right name for it.
    Two task sessions both have one, and no single number is honest, so both are shown.
    """
    names = [n for n in siblings if n and n != mine]
    claims = sorted({mine, *[n for n in names if TASK_NAME.match(n)]},
                    key=lambda n: (int(TASK_NAME.match(n).group(1)) if TASK_NAME.match(n)
                                   else 0, n))
    if len(claims) == 1:
        return mine
    if all(TASK_NAME.match(n) for n in claims):
        return "task-" + "+".join(TASK_NAME.match(n).group(1) for n in claims)
    return "+".join(claims)


def panes_in_my_window():
    """(window id, my pane id, every pane id in that window), or None outside tmux."""
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None
    window = tmux("display-message", "-p", "-t", pane, "-F", "#{window_id}")
    if not window:
        return None
    listed = tmux("list-panes", "-t", window, "-F", "#{pane_id}")
    return window, pane, set((listed or "").split())


def sessions_by_pane():
    """The newest session record per tmux pane.

    Newest wins because the records outlive their processes: pane %0 carries two, and
    the stale one names a session that ended hours ago. `updatedAt` is the only thing
    that separates them, and reading the older one would invent a sibling that is not
    there.
    """
    out = {}
    if not SESSIONS_DIR.is_dir():
        return out
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            rec = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        hit = TMUX_ADDR.search(str(rec.get("tmux") or ""))
        if not hit or not rec.get("name"):
            continue
        pane = hit.group(2)
        if rec.get("updatedAt", 0) >= out.get(pane, {}).get("updatedAt", -1):
            out[pane] = rec
    return out


def rename_window(mine):
    """Rename this session's tmux window. Every failure is a report, never a raise."""
    if not os.environ.get("TMUX"):
        return {"renamed": False, "reason": "not inside tmux"}
    found = panes_in_my_window()
    if not found:
        return {"renamed": False, "reason": "tmux did not report this pane's window"}
    window, my_pane, panes = found
    by_pane = sessions_by_pane()
    siblings = [rec["name"] for pane, rec in by_pane.items()
                if pane in panes and pane != my_pane]
    wanted = slug(window_name(mine, siblings))
    before = tmux("display-message", "-p", "-t", window, "-F", "#{window_name}")
    if before == wanted:
        return {"renamed": False, "window": window, "name": wanted,
                "reason": "already named that"}
    if tmux("rename-window", "-t", window, wanted) is None:
        return {"renamed": False, "window": window, "requested": wanted,
                "reason": "tmux rename-window failed"}
    out = {"renamed": True, "window": window, "name": wanted, "from": before}
    if siblings:
        out["sharedWith"] = siblings
    return out


def rename_session(wanted):
    token = os.environ.get(TOKEN_ENV)
    if not token:
        return {"renamed": False, "reason": f"{TOKEN_ENV} is not set"}
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


def rename(name, tmux_too=True, no_widen=False):
    """Both names, independently. The two can disagree and neither blocks the other.

    A window already called `task-17` says nothing about whether the session is, and a
    session rename that no-ops because it was already right must not leave a window
    still reading `claude`. So the tmux half runs whatever the session half returned.

    The one exception is a refused widening, where BOTH halves stand down: the point of
    the refusal is that the name already held is the specific one, and renaming only the
    window to the vaguer name would put the two surfaces of one session out of step for
    no gain.
    """
    wanted = slug(name)
    if no_widen:
        current = (session_record() or {}).get("name")
        if widens(current, wanted):
            return {"renamed": False, "name": current, "requested": wanted,
                    "reason": f"{current} is more specific than {wanted}; "
                              "refused to widen"}
    out = dict(rename_session(wanted), requested=wanted)
    if tmux_too:
        out["tmux"] = rename_window(wanted)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rename", help="rename this session, e.g. task-17")
    p.add_argument("name")
    p.add_argument("--no-tmux", dest="tmux", action="store_false",
                   help="leave the tmux window name alone")
    p.add_argument("--no-widen", action="store_true",
                   help="keep the current name if it is this one plus a suffix, e.g. "
                        "a launch name impl-x-p2 asked to become impl-x")
    sub.add_parser("name", help="print this session's current name")
    sub.add_parser("selftest", help="offline checks, no socket needed")
    args = parser.parse_args(argv)

    if args.cmd == "rename":
        print(json.dumps(rename(args.name, tmux_too=args.tmux,
                                no_widen=args.no_widen), indent=2))
    elif args.cmd == "name":
        rec = session_record() or {}
        # -t is not optional: without it tmux answers for the ACTIVE window, which is
        # whichever one the user is looking at, not the one this command is running in.
        pane = os.environ.get("TMUX_PANE")
        print(json.dumps({"name": rec.get("name"), "source": rec.get("nameSource"),
                          "sessionId": rec.get("sessionId"),
                          "tmuxWindow": tmux("display-message", "-p", "-t", pane, "-F",
                                             "#{window_id} #{window_name}")
                          if pane else None}, indent=2))
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

    # A window alone keeps the plain name; an ordinary session sharing it has no
    # competing claim, and a second TASK session does.
    eq("alone", window_name("task-17", []), "task-17")
    eq("an ordinary session is not a claim",
       window_name("task-20", ["tarot-app-8f"]), "task-20")
    eq("two tasks share the label", window_name("task-17", ["task-15"]), "task-15+17")
    eq("numeric order, not string order",
       window_name("task-9", ["task-17"]), "task-9+17")
    eq("three", window_name("task-9", ["task-17", "task-2"]), "task-2+9+17")
    eq("a duplicate is not a sibling", window_name("task-17", ["task-17"]), "task-17")
    eq("an ordinary sibling drops out of a shared label",
       window_name("task-17", ["hotfix", "task-2"]), "task-2+17")
    # the only way a non-task name survives is being the one asked for
    eq("mixed shapes fall back to whole names",
       window_name("hotfix", ["task-2"]), "hotfix+task-2")

    # Widening: the phase number is the part that makes a swarm address unique, so a
    # rename that drops it is refused rather than performed.
    eq("dropping the phase widens", widens("impl-x-p2", "impl-x"), True)
    eq("adding one does not", widens("impl-x", "impl-x-p2"), False)
    eq("same name is not widening", widens("impl-x", "impl-x"), False)
    eq("unrelated name is not widening", widens("do-P0-AB-1", "impl-x"), False)
    eq("a shared prefix mid-token is not widening", widens("task-17", "task-1"), False)
    eq("an unnamed session cannot widen", widens(None, "impl-x"), False)
    eq("other separators count too", widens("impl_x.p2", "impl_x"), True)

    # No socket in the environment must be a report, never an exception: a task loop
    # that died because it could not rename a window would be an absurd way to lose work.
    saved = {k: os.environ.pop(k, None) for k in (SOCKET_ENV, TOKEN_ENV, "TMUX")}
    try:
        eq("no token is a soft no", rename("task-1")["renamed"], False)
        eq("no tmux is a soft no", rename("task-1")["tmux"]["renamed"], False)
        os.environ[TOKEN_ENV] = "x"
        out = rename("task-1")
        eq("no socket is a soft no", out["renamed"], False)
        eq("and says why", SOCKET_ENV in out["reason"], True)
        eq("--no-tmux omits the half", "tmux" in rename("task-1", tmux_too=False), False)
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
