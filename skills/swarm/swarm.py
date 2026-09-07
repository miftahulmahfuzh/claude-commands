#!/usr/bin/env python3
"""Mechanics for orchestrating a plan set across many Claude Code sessions.

/analyze decomposes work into phases and records each phase's `depends_on`. That is a
DAG, so the phases that share no edge can run at the same time, in their own sessions,
in their own tmux windows. This script is the mechanical half of doing that: it reads
the plan index, computes which phases are runnable right now, launches a session per
phase, and records what happened. The judgement half -- reading reports, deciding a
phase failed, resolving a merge conflict, deciding a migration is safe to apply --
belongs to the orchestrator session, which is a model.

TWO LEDGERS, BECAUSE THEY HAVE DIFFERENT LIFETIMES. Half of what an orchestrator knows
is about the work and outlives any machine: which phases exist, what they depend on,
which ones landed and at which commit. The other half is tmux window ids, pane ids and
session names, which mean nothing on a different laptop and would conflict on every
write if two machines committed them. So:

    <repo>/.workflows/orchestration/<slug>/ledger.json   durable, COMMITTED
    <repo>/.workflows/orchestration/<slug>/.runtime.json  local, gitignored

Resume on another machine reads the durable half and rebuilds the runtime half empty.

THE DURABLE LEDGER IS A HINT, NOT AN ORACLE. A machine that dies mid-phase leaves it
saying `running` forever, so `verify` re-derives every phase's real status from the
things that cannot lie -- the commits on the branch and the task's state in todos.md --
and reports where the ledger disagrees. The orchestrator trusts the derivation.

THE WINDOW IS NOT THE RECORD. A phase that finished leaves an idle claude sitting in
its tmux window forever, and a set of twenty leaves a tab bar nobody can read -- so the
next wave's windows arrive somewhere the user has stopped looking. `reap` closes the
finished ones permanently. That is safe only because it is not destructive: the pane's
scrollback -- the whole reason the window was held open after claude exited -- is
written to logs/phase-N.log first, and any phase can be reopened with `spawn --force`
when a bug or a discrepancy needs a session again. Reaping is the coordinator's job and
never the phase's own: a session cannot close the window it is reporting from.

LANDING IS MECHANICAL EXCEPT WHERE IT IS NOT. `land` merges the set into a throwaway
worktree cut from the base, pushes it, and deletes the worktrees and the branch -- but
in four separate steps, because the two things needing a model sit BETWEEN them:
resolving a merge conflict, and applying the production migrations before the push
(production deploys from the base branch, so code arriving ahead of its schema is a
runtime error on the first request). `cleanup` deletes nothing until `merge-base
--is-ancestor` proves the branch is already in the base, so every earlier stop leaves
the branch standing by construction rather than by remembering to.

NEVER FAILS THE CALLER. Most /do runs have no ledger at all, and a task must not break
because a swarm file is absent. Every read prints `{"swarm": false, "reason": ...}` and
exits 0 rather than raising. Only a malformed invocation is an error.

    swarm.py init   --plan PATH [--coordinator NAME]
    swarm.py waves  --slug SLUG
    swarm.py spawn  --slug SLUG --phase N [--dry-run]
    swarm.py reap   --slug SLUG [--phase N] [--include-failed] [--dry-run]
    swarm.py report --slug SLUG --phase N --status done --commit SHA
    swarm.py verify --slug SLUG
    swarm.py status --slug SLUG
    swarm.py land   --slug SLUG --step check|merge|push|cleanup
    swarm.py find   --plan PATH | --task TASKID
    swarm.py track  [--dry-run]
    swarm.py launch --name NAME --prompt TEXT [--cwd DIR] [--permission-mode MODE]
    swarm.py selftest
"""

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MAX_NAME = 60                      # session.py's cap; a tab title renders this
ORCH_DIR = ".workflows/orchestration"

# A phase moves pending -> spawned -> running -> done, or stops at failed/blocked.
# `blocked` is the orchestrator's word for "a dependency failed", never a phase's own.
LIVE = ("pending", "spawned", "running")
TERMINAL = ("done", "failed", "blocked")

# What a pane is running when claude is no longer running in it. Anything not on this
# list reads as busy, because the conservative direction when reaping is to keep a
# window: a window kept is noise, a window killed mid-write is lost work.
SHELLS = ("sh", "bash", "zsh", "fish", "dash", "ksh", "ksh93", "tcsh", "csh")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(name):
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name).strip()).strip("-.")
    return out[:MAX_NAME] or "swarm"


def soft(reason, **extra):
    """A read that found nothing is a report, never an exception."""
    print(json.dumps(dict({"swarm": False, "reason": reason}, **extra), indent=2))
    return 0


# --------------------------------------------------------------------- git plumbing

def git(*args, cwd=None):
    try:
        out = subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                             text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_run(*args, cwd=None, timeout=180):
    """git() collapses every failure to None. Landing needs to tell them apart.

    A merge that conflicts, a push rejected because `main` moved and a push rejected by
    a protection rule are three different situations with three different next steps,
    and the difference lives in the exit code and stderr. The longer default timeout is
    for the two that talk to the network.
    """
    try:
        out = subprocess.run(("git",) + args, cwd=cwd, capture_output=True,
                             text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"
    return out.returncode, out.stdout.strip(), out.stderr.strip()


def inside(child, parent):
    """Is `child` at or under `parent`? -- the guard against deleting your own cwd."""
    if not child or not parent:
        return False
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def main_worktree(start):
    """The repo the ledger lives in -- the MAIN checkout, not the worktree.

    A plan set's worktree is deleted when the set lands, and a ledger inside it would
    go with it. `--git-common-dir` resolves to the main .git for every linked worktree,
    so its parent is the one directory that outlives them all.
    """
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=start)
    if not common:                                   # git < 2.31 has no --path-format
        rel = git("rev-parse", "--git-common-dir", cwd=start)
        if not rel:
            return None
        common = os.path.abspath(os.path.join(start or ".", rel))
    return str(Path(common).parent)


# ------------------------------------------------------------------- the plan index

# | # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID |
# Parsed by HEADER NAME, never by column position: the index template has grown a
# column twice already, and a positional parse would silently read the wrong cell.
def parse_index(text):
    """(meta, phases) from a <SLUG>_PLAN.md, or (meta, []) if it has no phase table."""
    meta = {}
    for key in ("Slug", "Worktree", "Branch", "Phases", "Status", "Coordinator"):
        hit = re.search(rf"^\*\*{key}:\*\*\s*(.+?)\s*$", text, re.M)
        if hit:
            meta[key.lower()] = _ref(hit.group(1))

    rows, header = [], None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            # A table ended. Forget its header, or the NEXT table inherits it: a plan's
            # Reconciliation Log is also `#`-headed with numeric rows, and was being read
            # as six extra phases whose "title" was a conflict description and whose
            # "plan" cell was empty -- six phantom windows an orchestrator would spawn.
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            # `#` alone is not enough to identify the phase table -- the Reconciliation
            # Log starts with `#` too. Match on the columns only the phase table has.
            lowered = [c.lower() for c in cells]
            if lowered and lowered[0] == "#" and "title" in lowered and "plan" in lowered:
                header = lowered
            continue
        if all(set(c) <= set("-: ") for c in cells):     # the |---|---| separator
            continue
        if not re.fullmatch(r"\d+", cells[0]):           # left the phase table
            continue
        row = dict(zip(header, cells))
        rows.append(row)

    phases = []
    for row in rows:
        phases.append({
            "n": int(row["#"]),
            "title": row.get("title", "").strip("`"),
            "satisfies": _ids(row.get("satisfies", "")),
            "package": row.get("package", "").strip("`"),
            "depends_on": [int(d) for d in re.findall(r"\d+", row.get("depends on", ""))],
            "difficulty": row.get("difficulty", "").upper(),
            "plan": row.get("plan", "").strip("`"),
            "task_id": _cell(row.get("taskid")),
            "card": _cell(row.get("card")),
            "status": "pending", "commit": None, "note": None, "reported_at": None,
        })
    return meta, sorted(phases, key=lambda p: p["n"])


def _ref(value):
    """The one identifier on a metadata line, without its decoration.

    `**Branch:** `feature/x` (base: `main` @ `abc1234`)` names three things and only the
    first is the branch. Splitting on whitespace and stripping backticks afterwards
    leaves a trailing one, so the backticked span is taken whole when there is one.
    """
    value = (value or "").strip()
    quoted = re.match(r"`([^`]+)`", value)
    if quoted:
        return quoted.group(1)
    return value.split()[0].strip("`") if value.split() else ""


def _cell(value):
    """A table cell that means "nothing yet"."""
    value = (value or "").strip().strip("`")
    return None if value in ("", "-", "--", "—", "TBD", "n/a") else value


def _ids(value):
    return re.findall(r"R\d+", value or "")


# ------------------------------------------------------------------------ the ledger

def orch_dir(repo, slug):
    return Path(repo) / ORCH_DIR / slug


def durable_path(repo, slug):
    return orch_dir(repo, slug) / "ledger.json"


def runtime_path(repo, slug):
    return orch_dir(repo, slug) / ".runtime.json"


@contextmanager
def locked(path):
    """Read-modify-write under flock: phase sessions report concurrently by design."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            raw = handle.read()
            data = json.loads(raw) if raw.strip() else {}
            yield data
            handle.seek(0)
            handle.truncate()
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def find_repo_and_slug(slug=None, start=None):
    repo = main_worktree(start or os.getcwd())
    if not repo:
        return None, None
    if slug:
        return repo, slug
    return repo, None


def phase_of(ledger, n):
    for phase in ledger.get("phases", []):
        if phase["n"] == n:
            return phase
    return None


# ------------------------------------------------------------------ wave scheduling

def waves(ledger):
    """Phases grouped into the rounds they can run in, from `depends_on` alone.

    Wave 0 is everything with no dependency; wave K is everything whose dependencies
    all sit in waves below K. A cycle -- which reconciliation should have caught -- is
    reported rather than looped on.
    """
    phases = {p["n"]: p for p in ledger.get("phases", [])}
    placed, out = {}, []
    remaining = set(phases)
    while remaining:
        ready = [n for n in sorted(remaining)
                 if all(d in placed for d in phases[n]["depends_on"])]
        if not ready:
            out.append({"wave": len(out), "cycle": sorted(remaining)})
            break
        for n in ready:
            placed[n] = len(out)
        out.append({"wave": len(out), "phases": ready})
        remaining -= set(ready)
    return out


def runnable(ledger):
    """Pending phases whose every dependency is `done` -- what to spawn right now."""
    phases = {p["n"]: p for p in ledger.get("phases", [])}
    out = []
    for n in sorted(phases):
        phase = phases[n]
        if phase["status"] != "pending":
            continue
        deps = [phases[d] for d in phase["depends_on"] if d in phases]
        if all(d["status"] == "done" for d in deps):
            out.append(n)
    return out


def stalled(ledger):
    """Pending phases that can never run because a dependency failed."""
    phases = {p["n"]: p for p in ledger.get("phases", [])}
    dead = {n for n, p in phases.items() if p["status"] in ("failed", "blocked")}
    grew = True
    while grew:
        grew = False
        for n, phase in phases.items():
            if n not in dead and set(phase["depends_on"]) & dead:
                dead.add(n)
                grew = True
    return sorted(n for n in dead if phases[n]["status"] not in ("failed", "blocked"))


# --------------------------------------------------------------------- verification

def resolve(repo, ref):
    """The sha a ref names here, trying the remote-tracking copy before giving up."""
    for candidate in (ref, f"origin/{ref}", f"refs/remotes/origin/{ref}"):
        if not candidate:
            continue
        sha = git("rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", cwd=repo)
        if sha:
            return candidate, sha
    return None, None


def commit_state(repo, sha, branch):
    """Whether a recorded commit actually landed -- or whether this box cannot tell.

    Three outcomes, and the third is the one that matters. A commit missing from the
    object store is not evidence of anything: it was authored on another machine and
    never pushed, or pushed to a branch this clone has not fetched. Calling that
    `pending` would send the orchestrator to re-run a phase that already shipped.
    """
    # `cat-file -e` prints NOTHING on success, and git() returns "" for that -- falsy.
    # Testing truthiness reported every commit that DOES exist as unfetched, which made
    # reap refuse to close the window of a phase that had verifiably landed. Compare
    # against None, exactly as the `merge-base --is-ancestor` call below already does.
    if git("cat-file", "-e", f"{sha}^{{commit}}", cwd=repo) is None:
        return "unknown", f"commit {sha[:8]} is not in this clone (unfetched?)"
    name, _ = resolve(repo, branch)
    if not name:
        return "unknown", f"branch {branch} does not resolve here"
    if git("merge-base", "--is-ancestor", sha, name, cwd=repo) is not None:
        return "done", f"commit {sha[:8]} is on {name}"
    return "pending", f"commit {sha[:8]} exists but is not on {name}"


def verify(repo, ledger):
    """Re-derive each phase's status from what cannot lie, and report disagreements.

    The durable ledger is written by whichever machine ran the phase, and a machine
    that died mid-phase left it reading `running` forever. Two things outlive that:
    the commit is on the branch or it is not, and todos.md says complete or it does
    not. Where they disagree with the ledger, the derivation wins.
    """
    branch = ledger.get("branch")
    findings = []
    for phase in ledger.get("phases", []):
        derived, evidence = "pending", []

        sha = phase.get("commit")
        if sha:
            derived, note = commit_state(repo, sha, branch)
            evidence.append(note)

        task = phase.get("task_id")
        if task:
            state = task_state(repo, task)
            if state:
                evidence.append(f"todos.md: {task} {state}")
                if state == "complete" and derived != "done":
                    derived = "done"
                elif state == "in_progress" and derived == "pending":
                    derived = "running"

        # NEVER downgrade a landed phase on missing evidence. "I cannot see the
        # branch" and "the commit is not on the branch" look identical to git, and
        # confusing them on a laptop that has not fetched yet would re-run a phase
        # that already shipped -- duplicating work and conflicting with itself.
        if derived == "unknown":
            derived = phase["status"]
            evidence.append("kept the ledger's word: no local evidence either way")

        if derived != phase["status"]:
            findings.append({"phase": phase["n"], "ledger": phase["status"],
                             "derived": derived, "evidence": evidence})
        phase["derived"] = derived
        phase["evidence"] = evidence
    return findings


def task_state(repo, task_id):
    """What every todos.md in the repo says about a TaskID, or None if unmentioned."""
    hits = git("grep", "-hn", "--", task_id, "--", "*todos.md", cwd=repo)
    if not hits:
        found = subprocess.run(
            ["grep", "-rhn", "--include=todos.md", task_id, "."],
            cwd=repo, capture_output=True, text=True)
        hits = found.stdout.strip()
    if not hits:
        return None
    text = hits.lower()
    if "[x]" in text or "completed" in text:
        return "complete"
    if "in progress" in text or "in_progress" in text:
        return "in_progress"
    return "open"


# -------------------------------------------------------------------- spawning tmux

CLAUDE_JSON = Path.home() / ".claude.json"


def trust_state(path):
    """Whether Claude Code will open `path` without stopping to ask about it."""
    try:
        config = json.loads(CLAUDE_JSON.read_text())
    except (OSError, ValueError):
        return None, {}
    projects = config.get("projects", {})
    entry = projects.get(str(path), {})
    return bool(entry.get("hasTrustDialogAccepted")), config


def ensure_trusted(cwd, repo, enabled=True):
    """Carry the repo's existing trust across to a worktree of that repo.

    MEASURED, and it is the failure that makes an unattended swarm impossible without
    a fix: a session spawned into a path Claude Code has not seen stops on the folder
    trust prompt before it boots. It never registers as a peer, so the coordinator
    waits on a session that is not running -- and every worktree /analyze cuts is a
    new path, so this fires on the normal case rather than an edge one.

    Trust is PROPAGATED, never invented. The only thing that authorises marking the
    worktree trusted is that the user already trusted the repository it was cut from;
    the code is the same code. If the repo itself is not trusted, this refuses and the
    caller tells the user to open it once by hand.
    """
    cwd, repo = str(Path(cwd).resolve()), str(Path(repo).resolve())
    trusted, config = trust_state(cwd)
    if trusted:
        return {"trusted": True, "action": "already trusted"}
    if trusted is None:
        return {"trusted": None, "action": "no ~/.claude.json to read"}
    if not enabled:
        return {"trusted": False, "action": "left alone (--no-trust)"}
    if cwd != repo and not trust_state(repo)[0]:
        return {"trusted": False, "action": "refused",
                "reason": f"{repo} is not trusted either -- open it once by hand first"}

    config.setdefault("projects", {}).setdefault(cwd, {})["hasTrustDialogAccepted"] = True
    # Atomic replace into the same directory: this file is live, and a partial write
    # would take out every session on the machine, not just this swarm.
    tmp = CLAUDE_JSON.with_suffix(".json.swarm-tmp")
    try:
        tmp.write_text(json.dumps(config, indent=2))
        os.replace(tmp, CLAUDE_JSON)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return {"trusted": False, "action": "failed", "reason": str(exc)}
    return {"trusted": True, "action": "propagated from " + repo}


def tmux(*args):
    if not os.environ.get("TMUX"):
        return None
    try:
        out = subprocess.run(("tmux",) + args, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def child_name(prefix, slug, n):
    """The address a phase session answers on -- known BEFORE it boots.

    `claude -n` sets the session name at launch, so the orchestrator does not race the
    child's own rename to learn where to send it a message. The slug is truncated
    rather than the phase number: `impl-a-very-long-slug-p2` losing its `-p2` would
    give two phases the same address.
    """
    tail = f"-p{n}"
    head = f"{prefix}-{slugify(slug)}"
    return head[:MAX_NAME - len(tail)] + tail


def spawn_argv(name, cwd, prompt, permission_mode=None, model=None, keep_open=True):
    inner = ["claude", "-n", name]
    if permission_mode:
        inner += ["--permission-mode", permission_mode]
    if model:
        inner += ["--model", model]
    inner.append(prompt)
    command = " ".join(shlex.quote(a) for a in inner)
    if keep_open:
        # Without this the window closes the instant claude exits and the scrollback
        # -- which is the only record of a phase that failed -- goes with it.
        command += "; exec ${SHELL:-/bin/sh}"
    return ["tmux", "new-window", "-d", "-n", name, "-c", cwd,
            "-P", "-F", "#{window_id} #{pane_id}", command]


# -------------------------------------------------------------------- reaping tmux

def logs_dir(repo, slug):
    """Where a reaped window's scrollback goes. Local, like .runtime.json."""
    return orch_dir(repo, slug) / "logs"


def window_facts(window):
    """What tmux says about a window id right now, or None if it is gone.

    A WINDOW ID IS NOT AN IDENTITY EITHER, for the same reason a session name is not.
    `@7` is unique for the life of one tmux server, but a server that was restarted
    hands `@7` to somebody else's window -- and killing that is destroying a stranger's
    work, not tidying up. So every reap re-reads the window's name and refuses when it
    no longer matches the name we spawned it under.
    """
    out = tmux("display-message", "-p", "-t", window,
               "#{window_id}\t#{window_name}\t#{pane_current_command}\t#{pane_id}")
    if not out:
        return None
    cells = (out.splitlines()[0] + "\t\t\t").split("\t")
    return {"window": cells[0], "name": cells[1], "command": cells[2], "pane": cells[3]}


def current_window():
    """This session's own window -- the one thing reap must never close.

    MUST be resolved against our own pane. Bare `display-message -p` answers for the
    client's ACTIVE window, not the window the calling process lives in -- so a
    coordinator whose own window is in the background learns some OTHER window's id.
    MEASURED on nina-character-tuning: the orchestrator sat in @107 while a phase
    window it had just spawned held focus, and reap declined to close that phase as
    "this session's own window". It fails safe -- it refuses rather than kills -- but
    the finished windows then never close, which is the entire job of iron rule 3, and
    the tab bar fills with idle sessions exactly as the rule warns.

    $TMUX_PANE is set by tmux in every pane and is the only self-reference that does
    not depend on which window happens to have focus.
    """
    pane = os.environ.get("TMUX_PANE")
    if pane:
        return tmux("display-message", "-p", "-t", pane, "#{window_id}")
    return tmux("display-message", "-p", "#{window_id}")


def capture(pane, dest):
    """Save a pane's whole scrollback before the window holding it goes away.

    This is what makes closing a window a tidy-up rather than a deletion. `spawn` keeps
    the pane alive after claude exits precisely so a failed phase's output survives;
    reap moves that output somewhere it survives even better -- a file that is still
    there tomorrow, and greppable across the whole set.
    """
    text = tmux("capture-pane", "-p", "-J", "-S", "-", "-E", "-", "-t", pane)
    if text is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text + "\n")
    return len(text.splitlines())


def reap_verdict(phase, entry, repo, ledger, include_failed=False, force=False):
    """May this phase's window be closed, and if not, what would have to change.

    The gate is the ledger's status backed by git, NOT what the pane looks like. A
    claude that has finished its phase does not exit -- it sits at an idle prompt --
    so "the pane is running claude" says nothing about whether the work is over. What
    does say so is a commit that is an ancestor of the branch.
    """
    if not entry:
        return False, "no window recorded on this machine"
    if entry.get("reaped_at"):
        return False, f"already reaped at {entry['reaped_at']}"
    machine = entry.get("machine")
    if machine and machine != os.uname().nodename:
        return False, f"spawned on {machine} -- that machine closes its own windows"
    status = phase.get("status")
    if force:
        return True, "forced"
    if status in LIVE:
        return False, (f"status is {status} -- still working; only --force closes a "
                       "window whose session may still be writing")
    if status != "done" and not include_failed:
        return False, (f"status is {status} -- kept on screen so the failure can be "
                       "read; --include-failed closes it (the log is saved either way)")
    sha, branch = phase.get("commit"), ledger.get("branch")
    if status == "done" and sha and branch:
        state, note = commit_state(repo, sha, branch)
        if state != "done":
            return False, f"reports done but {note} -- verify before closing its window"
    return True, f"{status}, verified"


def forget(repo, slug, n, entry, log=None, lines=None, how="closed"):
    """Move a session from `sessions` to `reaped` in the runtime ledger.

    Kept rather than deleted: "phase 3's window was closed at 02:14 and its scrollback
    is in logs/phase-3.log" is the answer to the only question anyone asks about a
    window that is no longer there.
    """
    record = dict(entry or {})
    record.update({"phase": n, "reaped_at": now(), "how": how})
    if log:
        record["log"] = log
    if lines is not None:
        record["lines"] = lines
    with locked(runtime_path(repo, slug)) as data:
        data.setdefault("sessions", {}).pop(str(n), None)
        data.setdefault("reaped", {})[str(n)] = record
    return record


def reapable(repo, ledger, runtime, **kwargs):
    """The phases whose windows could be closed right now -- for `status` to show."""
    sessions = runtime.get("sessions", {})
    return [p["n"] for p in ledger.get("phases", [])
            if reap_verdict(p, sessions.get(str(p["n"])), repo, ledger, **kwargs)[0]]



# ------------------------------------------------------------------------- commands

def cmd_init(args):
    plan = Path(args.plan).expanduser().resolve()
    if not plan.is_file():
        return soft(f"no plan index at {plan}")
    meta, phases = parse_index(plan.read_text())
    if not phases:
        return soft(f"{plan.name} has no phase table", plan=str(plan))

    slug = args.slug or meta.get("slug") or slugify(plan.stem.replace("_PLAN", ""))
    repo = main_worktree(str(plan.parent)) or str(plan.parent)
    directory = orch_dir(repo, slug)
    directory.mkdir(parents=True, exist_ok=True)

    with locked(durable_path(repo, slug)) as data:
        existing = {p["n"]: p for p in data.get("phases", [])}
        for phase in phases:                       # re-init keeps recorded outcomes
            was = existing.get(phase["n"])
            if was:
                for key in ("status", "commit", "note", "reported_at", "task_id"):
                    if was.get(key):
                        phase[key] = was[key]
        data.update({
            "slug": slug,
            "plan": str(plan),
            "branch": meta.get("branch") or None,
            "worktree": meta.get("worktree") or None,
            "coordinator": args.coordinator or data.get("coordinator")
                           or meta.get("coordinator"),
            # A NAME IS NOT AN IDENTITY. Session names are mutable and reused: MEASURED
            # here, a session listed as `agentic-golang-30` renamed itself to
            # `analyze-carry-similarity-branch` a minute later when /analyze ran in it,
            # and a message addressed to the old name still arrived -- at a session now
            # doing unrelated work. If `init` runs in the coordinator, its session id is
            # recorded too, so a child can tell "my coordinator" from "whoever holds
            # that name now" before sending a report to a stranger.
            "coordinator_session_id": (args.coordinator_session_id
                                       or data.get("coordinator_session_id")
                                       or os.environ.get("CLAUDE_CODE_SESSION_ID")),
            "repo": repo,
            "created": data.get("created") or now(),
            "updated": now(),
            "phases": phases,
        })
        out = dict(data)

    runtime_path(repo, slug).write_text(json.dumps(
        {"slug": slug, "machine": os.uname().nodename, "sessions": {}}, indent=2) + "\n")
    # Both of these are local by nature: one is tmux ids that mean nothing on another
    # laptop, the other is megabytes of raw terminal output. Repaired rather than only
    # created, so a set initialised before `reap` existed still ignores its logs.
    ignore = directory / ".gitignore"
    have = ignore.read_text().splitlines() if ignore.exists() else []
    missing = [line for line in (".runtime.json", "logs/") if line not in have]
    if missing:
        ignore.write_text("\n".join([l for l in have if l.strip()] + missing) + "\n")
    print(json.dumps({"swarm": True, "ledger": str(durable_path(repo, slug)),
                      "slug": slug, "phases": len(phases),
                      "waves": waves(out)}, indent=2))
    return 0


def cmd_waves(args):
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    ledger = load(durable_path(repo, slug))
    if not ledger:
        return soft(f"no ledger for {slug}", repo=repo)
    print(json.dumps({"swarm": True, "slug": slug, "waves": waves(ledger),
                      "runnable_now": runnable(ledger), "stalled": stalled(ledger),
                      "coordinator": ledger.get("coordinator")}, indent=2))
    return 0


def cmd_spawn(args):
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    ledger = load(durable_path(repo, slug))
    phase = phase_of(ledger, args.phase)
    if not phase:
        return soft(f"{slug} has no phase {args.phase}")
    if phase["status"] != "pending" and not args.force:
        return soft(f"phase {args.phase} is {phase['status']}, not pending",
                    hint="pass --force to relaunch it anyway")

    name = child_name(args.prefix, slug, args.phase)
    cwd = args.cwd or ledger.get("worktree") or repo
    if not Path(cwd).is_dir():
        return soft(f"cwd {cwd} does not exist", hint="the worktree may have been removed")
    prompt = args.prompt or f"/implement -f {ledger['plan']} --phase {args.phase}"
    argv = spawn_argv(name, cwd, prompt, args.permission_mode, args.model)
    trust = ensure_trusted(cwd, ledger.get("repo") or repo, enabled=not args.no_trust)

    if args.dry_run:
        print(json.dumps({"swarm": True, "dry_run": True, "name": name, "cwd": cwd,
                          "prompt": prompt, "trust": trust, "argv": argv}, indent=2))
        return 0
    if trust.get("action") == "refused":
        return soft("would hang on the folder trust prompt", trust=trust,
                    hint=f"open it once by hand: cd {cwd} && claude")
    if not os.environ.get("TMUX"):
        return soft("not inside tmux -- cannot open a window",
                    hint=f"run this by hand in a new terminal: cd {cwd} && "
                         f"claude -n {name} {shlex.quote(prompt)}")
    handle = tmux(*argv[1:])
    if handle is None:
        return soft("tmux new-window failed", argv=argv)
    window, _, pane = handle.partition(" ")

    # The phase was checked before the window opened, but `locked` re-reads the ledger
    # from disk -- and a concurrent `init` re-reading a plan index whose phase table
    # changed can leave a number that no longer exists. The window is already running
    # by now, so a missing row is reported rather than raised: `verify` derives this
    # phase from git either way, which is the whole reason it exists.
    recorded = False
    with locked(durable_path(repo, slug)) as data:
        target = phase_of(data, args.phase)
        if target:
            target["status"] = "spawned"
            data["updated"] = now()
            recorded = True
    with locked(runtime_path(repo, slug)) as data:
        data.setdefault("sessions", {})[str(args.phase)] = {
            "name": name, "window": window, "pane": pane.strip(),
            "cwd": cwd, "spawned_at": now(), "machine": os.uname().nodename,
            "permission_mode": args.permission_mode}
    out = {"swarm": True, "spawned": args.phase, "name": name, "window": window,
           "pane": pane.strip(), "cwd": cwd, "trust": trust, "prompt": prompt,
           "recorded_in_ledger": recorded}
    if not recorded:
        out["ledger_note"] = (f"phase {args.phase} was not in the ledger by the time "
                              "the window opened -- the session IS running; recover it "
                              "with init then verify --apply")
    if not args.permission_mode:
        # MEASURED: a child on a different permission mode than the coordinator has its
        # reports "held for approval" -- the coordinator never sees them until a human
        # clicks, which is the one thing an unattended swarm cannot survive. Silent, so
        # it is worth saying out loud every time.
        out["warning"] = ("no --permission-mode given: if this child's mode differs "
                          "from the coordinator's, its reports are held for the user "
                          "to approve and the swarm stalls silently")
    print(json.dumps(out, indent=2))
    return 0


def cmd_reap(args):
    """Close the tmux windows of phases that are over, keeping their scrollback.

    Tidiness is not cosmetic when the windows are how a human watches the swarm: a wave
    of eight leaves eight idle sessions, and the next wave's windows arrive at the far
    end of a tab bar nobody is reading any more. Closing a finished phase's window is
    PERMANENT and meant to be -- a phase that needs looking at again gets a fresh
    session from `spawn --force`, which is cheap, rather than a stale one kept alive on
    the chance it might be, which is not.

    Three refusals are worth knowing about, because each is a real way to destroy work:
    a phase still running, a window whose id now belongs to someone else, and this
    session's own window.
    """
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    ledger = load(durable_path(repo, slug))
    if not ledger:
        return soft(f"no ledger for {slug}", repo=repo)
    if not os.environ.get("TMUX"):
        return soft("not inside tmux -- no windows to reap from here", slug=slug)

    runtime = load(runtime_path(repo, slug))
    sessions = runtime.get("sessions", {})
    wanted = args.phase or [p["n"] for p in ledger.get("phases", [])]
    here = current_window()

    reaped, kept = [], []
    for n in wanted:
        phase = phase_of(ledger, n)
        if not phase:
            kept.append({"phase": n, "reason": f"{slug} has no phase {n}"})
            continue
        entry = sessions.get(str(n)) or {}
        ok, why = reap_verdict(phase, entry or None, repo, ledger,
                               include_failed=args.include_failed, force=args.force)
        if not ok:
            kept.append({"phase": n, "window": entry.get("window"), "reason": why})
            continue

        window, name = entry.get("window"), entry.get("name")
        facts = window_facts(window) if window else None
        if facts is None:
            # Already gone -- closed by hand, or the tmux server was restarted. There
            # is nothing to kill; stop tracking it so `status` stops implying a window.
            reaped.append(forget(repo, slug, n, entry, how="window was already gone"))
            continue
        if name and facts["name"] != name:
            kept.append({"phase": n, "window": window,
                         "reason": f"{window} is now {facts['name']!r}, not {name!r} -- "
                                   "another window took that id; refusing to kill it"})
            continue
        if here and facts["window"] == here:
            kept.append({"phase": n, "window": window,
                         "reason": "that is this session's own window"})
            continue

        dest = logs_dir(repo, slug) / f"phase-{n}.log"
        if args.dry_run:
            kept.append({"phase": n, "window": window, "name": name, "reason": "dry run",
                         "would": f"capture {facts['pane']} to {dest}, then kill {window}",
                         "verdict": why, "pane_running": facts["command"]})
            continue
        lines = None if args.no_log else capture(entry.get("pane") or facts["pane"], dest)
        if tmux("kill-window", "-t", window) is None and window_facts(window):
            kept.append({"phase": n, "window": window, "reason": "kill-window failed",
                         "log": str(dest) if lines is not None else None})
            continue
        reaped.append(forget(repo, slug, n, entry, lines=lines,
                             log=str(dest) if lines is not None else None,
                             how=f"closed ({why})"))

    still_open = sorted(int(k) for k in load(runtime_path(repo, slug))
                        .get("sessions", {}) if k.isdigit())
    print(json.dumps({"swarm": True, "slug": slug, "dry_run": bool(args.dry_run),
                      "reaped": reaped, "kept": kept, "windows_still_open": still_open,
                      "logs": str(logs_dir(repo, slug))}, indent=2))
    return 0


def cmd_report(args):
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    path = durable_path(repo, slug)
    if not path.exists():
        return soft(f"no ledger for {slug}", hint="this task is not part of a swarm")
    with locked(path) as data:
        phase = phase_of(data, args.phase)
        if not phase:
            return soft(f"{slug} has no phase {args.phase}")
        phase["status"] = args.status
        phase["reported_at"] = now()
        if args.commit:
            phase["commit"] = args.commit
        if args.note:
            phase["note"] = args.note
        if args.task:
            phase["task_id"] = args.task
        data["updated"] = now()
        coordinator = data.get("coordinator")
        snapshot = dict(phase)
    print(json.dumps({"swarm": True, "recorded": snapshot,
                      "coordinator": coordinator,
                      "next": "now SendMessage the coordinator -- the file is only "
                              "half of a report"}, indent=2))
    return 0


def cmd_verify(args):
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    path = durable_path(repo, slug)
    ledger = load(path)
    if not ledger:
        return soft(f"no ledger for {slug}", repo=repo)
    findings = verify(repo, ledger)
    if args.apply and findings:
        with locked(path) as data:
            # Re-looked-up under the lock, not carried in from the findings: `verify`
            # read an unlocked copy, and a phase session reporting concurrently may
            # have rewritten the table since. A row that is gone is left alone.
            for finding in findings:
                target = phase_of(data, finding["phase"])
                if target:
                    target["status"] = finding["derived"]
            data["updated"] = now()
            data["verified_at"] = now()
        ledger = load(path)
    print(json.dumps({"swarm": True, "slug": slug, "disagreements": findings,
                      "applied": bool(args.apply and findings),
                      "runnable_now": runnable(ledger), "stalled": stalled(ledger),
                      "phases": [{k: p.get(k) for k in
                                  ("n", "title", "status", "derived", "commit", "task_id")}
                                 for p in ledger.get("phases", [])]}, indent=2))
    return 0


def cmd_status(args):
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    ledger = load(durable_path(repo, slug))
    if not ledger:
        return soft(f"no ledger for {slug}", repo=repo)
    runtime = load(runtime_path(repo, slug))
    sessions, gone = runtime.get("sessions", {}), runtime.get("reaped", {})
    rows = []
    for phase in ledger.get("phases", []):
        live = sessions.get(str(phase["n"]), {})
        past = gone.get(str(phase["n"]), {})
        rows.append({"n": phase["n"], "title": phase["title"],
                     "status": phase["status"], "depends_on": phase["depends_on"],
                     "task_id": phase.get("task_id"), "commit": phase.get("commit"),
                     "session": live.get("name") or past.get("name"),
                     "window": live.get("window") if live else None,
                     "machine": (live or past).get("machine"),
                     "reaped_at": past.get("reaped_at") or None,
                     "log": past.get("log")})
    done = sum(1 for p in ledger.get("phases", []) if p["status"] == "done")
    print(json.dumps({"swarm": True, "slug": slug,
                      "coordinator": ledger.get("coordinator"),
                      "branch": ledger.get("branch"), "worktree": ledger.get("worktree"),
                      "progress": f"{done}/{len(ledger.get('phases', []))}",
                      "runnable_now": runnable(ledger), "stalled": stalled(ledger),
                      "this_machine": runtime.get("machine"),
                      "windows_open": sorted(int(k) for k in sessions if k.isdigit()),
                      "reapable_now": reapable(repo, ledger, runtime),
                      "phases": rows}, indent=2))
    return 0


# ------------------------------------------------------------------------- landing

# A path is a migration if any directory on it is named `migrations` or `migrate`.
# Deliberately broad -- drizzle, alembic, supabase, rails and prisma all satisfy it --
# because a false positive costs one line in a report and a miss costs a table that
# never exists in production.
MIGRATION_DIR = re.compile(r"(?:^|/)(?:migrations?|migrate)/", re.I)
MIGRATION_NUM = re.compile(r"^(\d{2,})[_-]")


def base_ref(repo):
    """The ref this set merges into -- the remote-tracking copy where there is one.

    Merging into a local `main` that is behind the remote produces a merge that cannot
    be fast-forwarded and a push that is rejected, so the remote copy is the base and
    the local branch is never checked out at all.
    """
    head = git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", cwd=repo)
    name = head.split("/", 1)[-1] if head else None
    for candidate in ([name] if name else []) + ["main", "master"]:
        # origin/ FIRST, deliberately -- `resolve` prefers the local ref and the local
        # `main` in a repo whose worktrees do all the work is usually behind. Merging
        # into a stale base builds a merge nobody asked for and a push that is rejected.
        for ref in (f"origin/{candidate}", candidate):
            if git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=repo):
                return ref
    return None


def land_worktree(repo, slug):
    root = os.environ.get("TASK_WORKTREES") or str(Path.home() / ".worktrees")
    return Path(root) / Path(repo).name / f"land-{slug}"


def landable(repo, ledger):
    """What stands between this set and `main`, derived from git, not from the ledger.

    `verify` stamps each phase with what the commits and todos.md actually say, and
    that is the gate -- a ledger reading `done` for a phase whose commit is not on the
    branch is exactly the claim Step 5 exists to distrust.
    """
    verify(repo, ledger)                       # stamps `derived` on every phase
    blockers = []
    phases = ledger.get("phases", [])
    if not phases:
        blockers.append("the ledger has no phases")
    for phase in phases:
        if phase.get("derived") != "done":
            blockers.append(
                f"phase {phase['n']} derives as {phase.get('derived')} "
                f"(ledger says {phase['status']}): " + "; ".join(phase.get("evidence") or
                                                                 ["no evidence"]))
    if not ledger.get("branch"):
        blockers.append("the ledger records no branch to merge")
    return blockers


def migration_survey(repo, base, branch):
    """Migrations this branch adds, and the ones whose number `base` already used.

    Two branches cut from one base can each mint a `0004`, which is NOT a file conflict
    -- the names differ -- and is silently skipped by any migrator that only applies
    journal entries newer than the last applied row. The deploy exits 0 and the table
    is simply never created. Finding it is mechanical; regenerating from the merged
    schema is the orchestrator's job.
    """
    _, out, _ = git_run("diff", "--name-only", "--diff-filter=A", f"{base}...{branch}",
                        cwd=repo)
    added = [p for p in out.splitlines() if MIGRATION_DIR.search(p)]
    _, out, _ = git_run("ls-tree", "-r", "--name-only", base, cwd=repo)
    taken = {}
    for path in out.splitlines():
        if not MIGRATION_DIR.search(path):
            continue
        hit = MIGRATION_NUM.match(Path(path).name)
        if hit:
            taken.setdefault((str(Path(path).parent), hit.group(1)), []).append(path)
    collisions = []
    for path in added:
        hit = MIGRATION_NUM.match(Path(path).name)
        if not hit:
            continue
        number = hit.group(1)
        clash = taken.get((str(Path(path).parent), number))
        if clash:
            collisions.append({"number": number, "branch": path, "base": clash})
    return {"added": added, "collisions": collisions}


def unmerged(land):
    _, out, _ = git_run("diff", "--name-only", "--diff-filter=U", cwd=land)
    return [line for line in out.splitlines() if line]


def cmd_land(args):
    """The mechanical half of Step 5: merge, push, delete. The judgement stays outside.

    Split into steps on purpose, because the two things that need a model sit BETWEEN
    them: resolving a merge conflict (after `merge`) and applying the production
    migrations (before `push`). A single land-it-all command would have to either ask
    or guess at both, and guessing at a migration is how a schema and its code part
    company in production.

        land --step check     is this set landable at all, per git
        land --step merge     merge --no-ff into a throwaway worktree of the base
        land --step push      push it to the base branch, retrying a base that moved
        land --step cleanup   delete the land worktree, the set's worktree, the branch

    `cleanup` is the destructive one and it is guarded twice: it refuses unless the
    branch is already an ancestor of the base -- so every earlier stop leaves the
    branch standing by construction -- and it refuses to delete the directory the
    caller is standing in.
    """
    repo, slug = find_repo_and_slug(args.slug)
    if not repo:
        return soft("not inside a git repository")
    path = durable_path(repo, slug)
    ledger = load(path)
    if not ledger:
        return soft(f"no ledger for {slug}", repo=repo)

    branch = ledger.get("branch")
    base = base_ref(repo)
    land = land_worktree(repo, slug)
    wt = ledger.get("worktree")
    out = {"swarm": True, "slug": slug, "step": args.step, "repo": repo,
           "branch": branch, "base": base, "land_worktree": str(land),
           "worktree": wt, "dry_run": bool(args.dry_run),
           "landed": ledger.get("landed")}

    if not base:
        out.update({"ok": False, "reason": "no main/master branch resolves in this repo"})
        print(json.dumps(out, indent=2))
        return 0

    if args.step == "check":
        blockers = landable(repo, ledger)
        out.update({"ok": not blockers, "blockers": blockers,
                    "migrations": migration_survey(repo, base, branch) if branch else {},
                    "phases": [{k: p.get(k) for k in ("n", "status", "derived", "commit")}
                               for p in ledger.get("phases", [])]})
        print(json.dumps(out, indent=2))
        return 0

    if args.step == "merge":
        blockers = landable(repo, ledger)
        if blockers and not args.force:
            out.update({"ok": False, "blockers": blockers,
                        "hint": "every phase must derive as done -- run verify --apply, "
                                "or --force if you have decided otherwise"})
            print(json.dumps(out, indent=2))
            return 0
        if args.dry_run:
            out.update({"ok": True, "would": f"worktree add -B land-{slug} {land} {base}"
                                             f" && merge --no-ff {branch}"})
            print(json.dumps(out, indent=2))
            return 0

        git_run("fetch", "origin", "--quiet", cwd=repo)
        base = base_ref(repo) or base
        out["base"] = base
        if not land.is_dir():
            land.parent.mkdir(parents=True, exist_ok=True)
            code, _, err = git_run("worktree", "add", "-B", f"land-{slug}",
                                   str(land), base, cwd=repo)
            if code:
                out.update({"ok": False, "reason": f"worktree add failed: {err}"})
                print(json.dumps(out, indent=2))
                return 0
        else:
            out["reused_land_worktree"] = True

        stuck = unmerged(land)
        if stuck:                              # a previous merge is still half-resolved
            out.update({"ok": False, "merged": False, "conflicts": stuck,
                        "hint": "resolve these, git add, git commit --no-edit, then "
                                "land --step push"})
            print(json.dumps(out, indent=2))
            return 0

        title = ledger.get("title") or slug
        message = args.message or (f"merge({slug}): {len(ledger.get('phases', []))} "
                                   f"phases -- {title}")
        code, _, err = git_run("merge", "--no-ff", branch, "-m", message, cwd=land)
        conflicts = unmerged(land)
        head = git("rev-parse", "HEAD", cwd=land)
        out.update({"ok": code == 0, "merged": code == 0, "conflicts": conflicts,
                    "head": head, "message": message,
                    "migrations": migration_survey(repo, base, branch),
                    "stderr": err or None})
        if conflicts:
            out["hint"] = ("decide each on the precedence ladder, git add, "
                           "git commit --no-edit -- or git merge --abort to stop, "
                           "which leaves the branch exactly as it was")
        elif code == 0:
            out["hint"] = ("apply and VERIFY the production migrations now, before "
                           "land --step push: main is what production deploys from")
        print(json.dumps(out, indent=2))
        return 0

    if args.step == "push":
        if not land.is_dir():
            out.update({"ok": False, "reason": f"no land worktree at {land} -- "
                                               "run land --step merge first"})
            print(json.dumps(out, indent=2))
            return 0
        stuck = unmerged(land)
        if stuck:
            out.update({"ok": False, "conflicts": stuck,
                        "reason": "the merge is still unresolved"})
            print(json.dumps(out, indent=2))
            return 0
        target = base.split("/", 1)[-1] if base.startswith("origin/") else base
        if args.dry_run:
            out.update({"ok": True, "would": f"push origin HEAD:{target} from {land}"})
            print(json.dumps(out, indent=2))
            return 0

        attempts = []
        for attempt in range(1, args.retries + 1):
            code, _, err = git_run("push", "origin", f"HEAD:{target}", cwd=land)
            attempts.append({"attempt": attempt, "ok": code == 0, "stderr": err or None})
            if code == 0:
                break
            # A base that moved is the ordinary race and merges forward; anything else
            # -- a protection rule, no permission, a hook -- will not fix itself by
            # being retried, so say so once instead of hammering the remote.
            if "non-fast-forward" not in err and "fetch first" not in err \
                    and "behind" not in err:
                attempts[-1]["fatal"] = True
                break
            git_run("fetch", "origin", target, "--quiet", cwd=land)
            code, _, err = git_run("merge", "--no-edit", f"origin/{target}", cwd=land)
            if code:
                attempts[-1]["remerge_conflicts"] = unmerged(land)
                attempts[-1]["fatal"] = True
                break

        pushed = attempts[-1]["ok"]
        sha = git("rev-parse", "HEAD", cwd=land) if pushed else None
        if pushed:
            with locked(path) as data:
                data["landed"] = {"commit": sha, "base": target, "at": now(),
                                  "machine": os.uname().nodename}
                data["updated"] = now()
            out["landed"] = {"commit": sha, "base": target}
        out.update({"ok": pushed, "pushed": pushed, "attempts": attempts,
                    "hint": None if pushed else
                            "nothing landed: main is untouched and the branch is intact"})
        print(json.dumps(out, indent=2))
        return 0

    # ------------------------------------------------------------------- cleanup
    here = os.getcwd()
    if inside(here, land) or (wt and inside(here, wt)):
        out.update({"ok": False, "reason": f"cwd {here} is inside a worktree this step "
                                           "deletes",
                    "hint": f"cd {repo} first -- a session cannot outlive its own cwd"})
        print(json.dumps(out, indent=2))
        return 0

    git_run("fetch", "origin", "--quiet", cwd=repo)
    base = base_ref(repo) or base
    merged = branch and git_run("merge-base", "--is-ancestor", branch, base,
                                cwd=repo)[0] == 0
    if not merged and not args.force:
        out.update({"ok": False, "merged_into_base": False, "base": base,
                    "reason": f"{branch} is not an ancestor of {base} -- nothing is "
                              "deleted until the set has actually landed"})
        print(json.dumps(out, indent=2))
        return 0

    plan = []
    if land.is_dir():
        plan.append(("remove the land worktree", ("worktree", "remove", "--force",
                                                  str(land))))
        plan.append(("delete the land branch", ("branch", "-D", f"land-{slug}")))
    if wt and Path(wt).is_dir():
        plan.append(("remove the set's worktree", ("worktree", "remove", "--force", wt)))
    if branch:
        plan.append(("delete the local branch", ("branch", "-D", branch)))
        if not args.keep_remote:
            plan.append(("delete the remote branch",
                         ("push", "origin", "--delete", branch)))

    if args.dry_run:
        out.update({"ok": True, "merged_into_base": merged,
                    "would": [f"git {' '.join(a)}" for _, a in plan]})
        print(json.dumps(out, indent=2))
        return 0

    # `worktree remove --force` is right here and only here: the ancestor check above
    # already proved every commit is on the base, so what remains in that directory is
    # residue rather than work. Keep a record of it anyway -- a dirty worktree at this
    # point is worth knowing about even when it is safe to delete.
    if wt and Path(wt).is_dir():
        _, dirt, _ = git_run("status", "--porcelain", cwd=wt)
        if dirt:
            logs_dir(repo, slug).mkdir(parents=True, exist_ok=True)
            (logs_dir(repo, slug) / "worktree-dirt.txt").write_text(dirt + "\n")
            out["uncommitted_at_removal"] = str(logs_dir(repo, slug) /
                                                "worktree-dirt.txt")

    done, failed = [], []
    for what, argv in plan:
        code, _, err = git_run(*argv, cwd=repo)
        (done if code == 0 else failed).append(
            {"did": what, "git": " ".join(argv), "stderr": err or None})
    git_run("worktree", "prune", cwd=repo)
    out.update({"ok": not failed, "merged_into_base": merged,
                "cleaned": done, "failed": failed})
    print(json.dumps(out, indent=2))
    return 0


def plan_matches(needle, recorded, slug):
    """Does this plan path belong to THIS set's phase?

    A bare basename is NOT enough, and trusting one misroutes an entire phase report.
    MEASURED on nina-character-tuning: `find --plan .../nina-character-tuning/phase-5.md`
    answered with slug `admin-album-file-manager`. Every set has a `phase-5.md`, the old
    fallback compared basenames only, and ledgers are scanned in sorted order -- so the
    alphabetically-first set won. A phase session trusting it would have recorded its
    outcome in a FINISHED set's ledger and messaged a coordinator that had not existed
    for hours, and the report would have looked like it succeeded.

    That is the worst shape a bug can have here, because `find` exists precisely so a
    session carrying no --swarm flag can discover its owner. Discovery that can silently
    answer for the wrong set is worse than no discovery at all.

    So the basename may only stand in when the directory holding it is the set's own
    slug -- true both of `.workflows/plan/<slug>/phase-N.md` in a worktree and of
    `.workflows/orchestration/<slug>/phase-N.md` in the tracked copy.
    """
    if not needle or not recorded:
        return False
    if needle.endswith(recorded):          # the recorded path, in full
        return True
    here = Path(needle)
    return bool(slug) and here.name == Path(recorded).name and here.parent.name == slug


def cmd_find(args):
    """Which swarm, if any, owns this plan file or TaskID -- discovery over flags.

    /do and /implement must not need a --swarm argument: a session launched by hand
    would never carry one, and then the report would silently go nowhere.
    """
    repo = main_worktree(os.getcwd())
    if not repo:
        return soft("not inside a git repository")
    root = Path(repo) / ORCH_DIR
    if not root.is_dir():
        return soft("no orchestration directory", repo=repo)
    needle = str(Path(args.plan).expanduser()) if args.plan else None
    for ledger_file in sorted(root.glob("*/ledger.json")):
        ledger = load(ledger_file)
        for phase in ledger.get("phases", []):
            hit = (args.task and phase.get("task_id") == args.task) or (
                needle and plan_matches(needle, phase.get("plan"),
                                        ledger.get("slug")))
            if hit:
                print(json.dumps({"swarm": True, "slug": ledger["slug"],
                                  "phase": phase["n"],
                                  "coordinator": ledger.get("coordinator"),
                                  "coordinator_session_id":
                                      ledger.get("coordinator_session_id"),
                                  "addressing_note":
                                      "confirm this name is still in ListAgents before "
                                      "sending; names are mutable and reused, and a "
                                      "stale one delivers your report to a stranger. "
                                      "If it is gone, tell the user -- do not guess.",
                                  "ledger": str(ledger_file),
                                  "peers": [child_name("impl", ledger["slug"], p["n"])
                                            for p in ledger.get("phases", [])
                                            if p["n"] != phase["n"]]}, indent=2))
                return 0
    return soft("no swarm owns that", plan=args.plan, task=args.task)


TRACK_BLOCK = """
# --- swarm orchestration (added by skills/swarm/swarm.py track) ---
# An orchestrated plan set must outlive the machine that started it: another laptop
# resumes it by reading these files out of the repo. Generated scratch plans stay
# ignored above; only sets someone is actively driving live here, and the orchestrator
# prunes the phase bodies when the set lands so this stays kilobytes.
{negations}
# The runtime half -- tmux window ids, pane ids, session names -- is meaningless on
# any other machine and would conflict on every write. It never leaves this box.
.workflows/orchestration/**/.runtime.json
"""


def check_ignored(repo, path):
    """The .gitignore rule excluding `path`, or None if nothing excludes it."""
    try:
        out = subprocess.run(["git", "check-ignore", "-v", "--no-index", str(path)],
                             cwd=repo, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    rule = out.stdout.strip()
    if not rule:
        return None
    # `check-ignore -v` reports the LAST pattern that matched, and a negation matching
    # last means the path is included, not excluded. Reading any output as "ignored"
    # would make this command believe its own fix had failed.
    pattern = rule.split("\t")[0].rsplit(":", 1)[-1]
    return None if pattern.startswith("!") else rule


def cmd_track(args):
    """Make .workflows/orchestration/ tracked, whatever the repo already ignores.

    Repos ignore .workflows/ broadly and for good reason -- one of them holds 218 files
    of generated plans. Un-ignoring the lot would undo a deliberate decision, so this
    re-includes exactly the orchestration path and nothing else. Git cannot re-include
    a file whose PARENT directory is excluded, so every excluded ancestor needs its own
    negation, deepest last.
    """
    repo = main_worktree(os.getcwd())
    if not repo:
        return soft("not inside a git repository")
    probe = Path(repo) / ORCH_DIR / "probe" / "ledger.json"

    rule = check_ignored(repo, probe)
    if not rule:
        print(json.dumps({"swarm": True, "tracked": True,
                          "reason": "nothing ignores .workflows/orchestration/ already",
                          "gitignore": str(Path(repo) / ".gitignore")}, indent=2))
        return 0

    # Deepest last: git applies the last matching pattern, so `!.workflows/` must come
    # before `!.workflows/orchestration/` or the directory stays excluded.
    # Descend without un-ignoring the siblings. Git cannot re-include a file whose
    # parent directory is excluded, so each ancestor is re-included -- but a bare
    # `!.workflows/` would also start tracking todos.md and analysis_report.md, which
    # this repo ignored on purpose. Re-excluding `<ancestor>/*` right after each
    # negation reopens the door only wide enough to walk through it.
    ancestors, part = [], Path(ORCH_DIR)
    while str(part) not in (".", "/"):
        ancestors.append(str(part))
        part = part.parent
    lines = []
    for ancestor in reversed(ancestors):
        lines.append(f"!{ancestor}/")
        if ancestor != ORCH_DIR:
            lines.append(f"{ancestor}/*")
    lines.append(f"!{ORCH_DIR}/**")
    negations = "\n".join(lines)

    gitignore = Path(repo) / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if "swarm orchestration (added by" in existing:
        print(json.dumps({"swarm": True, "tracked": None,
                          "reason": "the swarm block is already in .gitignore",
                          "blocked_by": rule}, indent=2))
        return 0
    if args.dry_run:
        print(json.dumps({"swarm": True, "dry_run": True, "blocked_by": rule,
                          "would_append": TRACK_BLOCK.format(negations=negations),
                          "gitignore": str(gitignore)}, indent=2))
        return 0

    with open(gitignore, "a") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write(TRACK_BLOCK.format(negations=negations))

    still = check_ignored(repo, probe)
    print(json.dumps({"swarm": True, "tracked": still is None,
                      "was_blocked_by": rule, "still_blocked_by": still,
                      "gitignore": str(gitignore),
                      "appended": TRACK_BLOCK.format(negations=negations)}, indent=2))
    return 0


def cmd_launch(args):
    """Open one named Claude Code session in a new tmux window. No ledger required.

    `spawn` needs a ledger and a phase; this does not. It exists so a session can hand
    its work to a fresh session without a human retyping a command -- /analyze finishing
    at 22:30 and starting the orchestrator itself, rather than the plan sitting untouched
    until someone wakes up and pastes one line.
    """
    cwd = str(Path(args.cwd or os.getcwd()).resolve())
    if not Path(cwd).is_dir():
        return soft(f"cwd {cwd} does not exist")
    repo = args.repo or main_worktree(cwd) or cwd
    name = slugify(args.name)
    argv = spawn_argv(name, cwd, args.prompt, args.permission_mode, args.model)
    trust = ensure_trusted(cwd, repo, enabled=not args.no_trust)

    if args.dry_run:
        print(json.dumps({"swarm": True, "dry_run": True, "name": name, "cwd": cwd,
                          "trust": trust, "prompt": args.prompt, "argv": argv}, indent=2))
        return 0
    if trust.get("action") == "refused":
        return soft("would hang on the folder trust prompt", trust=trust,
                    hint=f"open it once by hand: cd {cwd} && claude")
    if not os.environ.get("TMUX"):
        return soft("not inside tmux -- cannot open a window",
                    hint=f"run this by hand: cd {cwd} && claude -n {name} "
                         f"{shlex.quote(args.prompt)}")
    handle = tmux(*argv[1:])
    if handle is None:
        return soft("tmux new-window failed", argv=argv)
    window, _, pane = handle.partition(" ")
    out = {"swarm": True, "launched": name, "window": window, "pane": pane.strip(),
           "cwd": cwd, "trust": trust, "prompt": args.prompt}
    if not args.permission_mode:
        out["warning"] = ("no --permission-mode given: an unattended session on a mode "
                          "that prompts will stop at the first prompt and wait all night")
    print(json.dumps(out, indent=2))
    return 0


# ------------------------------------------------------------------------- selftest

INDEX = """# Plan: Demo

**Slug:** branch-sort-order
**Worktree:** `/tmp/wt`
**Branch:** `feature/branch-sort-order` (base: `main` @ `abc1234`)
**Phases:** 4
**Status:** planned

## Phases

| # | Title | Satisfies | Package | Files | Depends on | Difficulty | Plan | TaskID | Card |
|---|-------|-----------|---------|-------|-----------|------------|------|--------|------|
| 1 | Serve order | R1 | `serve` | 6 | — | NORMAL | `.workflows/plan/x/phase-1.md` | — | — |
| 2 | Docs | R1 | `docs` | 4 | 1 | EASY | `.workflows/plan/x/phase-2.md` | P2-TP-A012 | — |
| 3 | Harness | R2 | `e2e` | 2 | — | NORMAL | `.workflows/plan/x/phase-3.md` | — | — |
| 4 | Wire up | R1, R2 | `serve` | 3 | 2, 3 | HARD | `.workflows/plan/x/phase-4.md` | — | — |

## Rollback
"""


def selftest():
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    meta, phases = parse_index(INDEX)
    eq("slug", meta["slug"], "branch-sort-order")
    eq("branch keeps only the ref", meta["branch"], "feature/branch-sort-order")
    eq("a bare ref needs no backticks", _ref("main @ abc1234"), "main")
    eq("worktree path survives", meta["worktree"], "/tmp/wt")
    eq("four phases", len(phases), 4)
    eq("em dash is no dependency", phases[0]["depends_on"], [])
    eq("one dependency", phases[1]["depends_on"], [1])
    eq("two dependencies", phases[3]["depends_on"], [2, 3])
    eq("em dash is not a TaskID", phases[0]["task_id"], None)
    eq("a real TaskID survives", phases[1]["task_id"], "P2-TP-A012")
    eq("multi-R", phases[3]["satisfies"], ["R1", "R2"])
    eq("difficulty", phases[3]["difficulty"], "HARD")

    # A column added in the middle must not shift the parse -- this is why the header
    # is read by name. Same table, one extra column before Depends on.
    shifted = INDEX.replace("| Files | Depends on |", "| Files | Risk | Depends on |")
    shifted = re.sub(r"\| (\d) \| ([^|]+)\| (R[^|]*)\| ([^|]+)\| (\d+) \|",
                     r"| \1 | \2| \3| \4| \5 | low |", shifted)
    _, moved = parse_index(shifted)
    eq("a new column does not shift depends_on", [p["depends_on"] for p in moved],
       [[], [1], [], [2, 3]])

    ledger = {"phases": phases}
    eq("waves", [w.get("phases") for w in waves(ledger)], [[1, 3], [2], [4]])
    eq("both roots are runnable at once", runnable(ledger), [1, 3])

    phases[0]["status"] = "done"
    eq("finishing 1 unblocks 2", runnable(ledger), [2, 3])
    phases[2]["status"] = "failed"
    eq("a failure does not block its sibling", runnable(ledger), [2])
    eq("but it strands everything downstream", stalled(ledger), [4])

    cyclic = {"phases": [{"n": 1, "depends_on": [2], "status": "pending"},
                         {"n": 2, "depends_on": [1], "status": "pending"}]}
    eq("a cycle is reported, not looped on", waves(cyclic)[-1].get("cycle"), [1, 2])

    eq("child name", child_name("impl", "branch-sort-order", 2),
       "impl-branch-sort-order-p2")
    long = child_name("impl", "x" * 90, 12)
    eq("a long slug is truncated, never the phase", long.endswith("-p12"), True)
    eq("and stays addressable", len(long) <= MAX_NAME, True)

    argv = spawn_argv("impl-x-p1", "/tmp", "/implement -f P.md --phase 1",
                      permission_mode="acceptEdits")
    eq("detached so it does not steal the coordinator's focus", "-d" in argv, True)
    eq("names the session at launch", "-n" in argv, True)
    eq("the pane outlives claude", "exec ${SHELL:-/bin/sh}" in argv[-1], True)
    eq("the prompt is quoted, not concatenated",
       "'/implement -f P.md --phase 1'" in argv[-1], True)
    eq("permission mode is passed through", "--permission-mode acceptEdits" in argv[-1],
       True)

    # Reaping. The gate is the ledger backed by git, never what the pane looks like:
    # a claude that finished its phase sits at an idle prompt rather than exiting.
    mine = {"name": "impl-x-p2", "window": "@7", "pane": "%9",
            "machine": os.uname().nodename}
    empty = {"branch": None, "phases": []}
    eq("nothing recorded, nothing to close",
       reap_verdict({"n": 2, "status": "done"}, None, "/nonexistent", empty)[0], False)
    eq("a running phase keeps its window",
       reap_verdict({"n": 2, "status": "running"}, mine, "/nonexistent", empty)[0], False)
    eq("--force closes it anyway",
       reap_verdict({"n": 2, "status": "running"}, mine, "/nonexistent", empty,
                    force=True)[0], True)
    eq("a done phase with nothing to check against is closed",
       reap_verdict({"n": 2, "status": "done"}, mine, "/nonexistent", empty)[0], True)
    eq("a failure stays on screen by default",
       reap_verdict({"n": 2, "status": "failed"}, mine, "/nonexistent", empty)[0], False)
    eq("until asked for by name",
       reap_verdict({"n": 2, "status": "failed"}, mine, "/nonexistent", empty,
                    include_failed=True)[0], True)
    eq("another machine closes its own windows",
       reap_verdict({"n": 2, "status": "done"}, dict(mine, machine="somewhere-else"),
                    "/nonexistent", empty)[0], False)
    eq("reaping twice is not an error, it is a no-op",
       reap_verdict({"n": 2, "status": "done"}, dict(mine, reaped_at=now()),
                    "/nonexistent", empty)[0], False)
    # The one that protects shipped work: `done` is a claim until git agrees with it.
    eq("a done phase whose commit is not on the branch keeps its window",
       reap_verdict({"n": 2, "status": "done", "commit": "f" * 40}, mine,
                    "/nonexistent-repo", {"branch": "feature/x"})[0], False)
    eq("no swarm, no reaping -- and still not an error", cmd_reap(argparse.Namespace(
        slug="no-such-slug-selftest", phase=None, all=False, include_failed=False,
        force=False, no_log=False, dry_run=True)), 0)

    eq("launch needs no ledger", cmd_launch(argparse.Namespace(
        name="orch-x", prompt="/analyze-orchestrator -f P.md", cwd="/nonexistent-dir",
        repo=None, permission_mode=None, model=None, no_trust=True, dry_run=True)), 0)

    # The cross-machine hazard, in one assertion: a ledger that says `done` must
    # survive a clone that cannot see the commit yet.
    unknown = {"phases": [{"n": 1, "status": "done", "commit": "deadbeef" * 5,
                           "depends_on": [], "task_id": None}],
               "branch": "feature/nope"}
    eq("an unfetched commit never downgrades a landed phase",
       verify("/nonexistent-repo", unknown), [])
    eq("and the phase keeps its status", unknown["phases"][0]["status"], "done")

    # Trust is propagated, never invented: an untrusted repo must refuse rather than
    # mark itself trusted, because that prompt is the user's decision to make.
    eq("an unknown path under an untrusted repo is refused",
       ensure_trusted("/nonexistent/wt", "/nonexistent/repo")["action"] in
       ("refused", "no ~/.claude.json to read"), True)
    eq("--no-trust never writes",
       ensure_trusted("/nonexistent/wt", "/nonexistent/repo", enabled=False)["action"]
       in ("left alone (--no-trust)", "no ~/.claude.json to read"), True)

    # Landing. The gate is the DERIVED status, not the ledger's word -- a phase whose
    # commit is not on the branch is a claim, and merging on a claim ships nothing.
    claimed = {"branch": "feature/nope", "phases": [
        {"n": 1, "status": "done", "commit": "a" * 40, "depends_on": [], "task_id": None},
        {"n": 2, "status": "running", "commit": None, "depends_on": [1], "task_id": None}]}
    blockers = landable("/nonexistent-repo", claimed)
    eq("a phase that is not done blocks the landing",
       any("phase 2" in b for b in blockers), True)
    eq("an unfetched done is not held against it",
       any("phase 1" in b for b in blockers), False)
    eq("a ledger with no branch cannot be merged",
       any("no branch" in b for b in landable("/nonexistent-repo", {"phases": []})), True)

    # The guard that makes cleanup safe to run unattended: it deletes the directory the
    # session may be standing in, so standing in it is a refusal, not a crash.
    eq("cwd inside the worktree is a refusal", inside("/tmp/wt/pkg/x", "/tmp/wt"), True)
    eq("a sibling path is not inside it", inside("/tmp/wt-other", "/tmp/wt"), False)
    eq("no worktree recorded, nothing to be inside", inside("/tmp/x", None), False)

    # Two branches off one base can each mint a 0004. Different filenames, so git sees
    # no conflict -- and a migrator that only applies entries newer than the last
    # applied row skips it, exits 0, and the table never exists.
    survey = migration_survey("/nonexistent-repo", "origin/main", "feature/x")
    eq("no repo, no migrations, no exception", survey["collisions"], [])
    eq("a numbered migration is recognised",
       bool(MIGRATION_NUM.match("0004_add_nina_tuning.sql")), True)
    eq("drizzle, alembic and supabase all match",
       [bool(MIGRATION_DIR.search(p)) for p in
        ("db/migrations/0004_x.sql", "alembic/migrations/0004_x.py",
         "supabase/migrations/0004_x.sql", "src/migrate/0004_x.go",
         "docs/migrating.md")], [True, True, True, True, False])

    eq("landing a set that has no ledger is a soft no", cmd_land(argparse.Namespace(
        slug="no-such-slug-selftest", step="check", message=None, retries=3,
        keep_remote=False, force=False, dry_run=True)), 0)

    eq("a missing plan is a soft no", cmd_init(argparse.Namespace(
        plan="/nonexistent/NOPE_PLAN.md", slug=None, coordinator=None,
        coordinator_session_id=None)), 0)

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    print(f"selftest: all assertions passed ({len(INDEX.splitlines())} line fixture)")
    return 0


def main(argv=None):
    summary = (__doc__ or "Mechanics for orchestrating a plan set.").splitlines()[0]
    parser = argparse.ArgumentParser(description=summary)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create a ledger from a plan index")
    p.add_argument("--plan", required=True)
    p.add_argument("--slug")
    p.add_argument("--coordinator")
    p.add_argument("--coordinator-session-id",
                   help="defaults to this session's, when init runs in the coordinator")

    for name, help_text in (("waves", "what can run now"), ("status", "the table")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--slug", required=True)

    p = sub.add_parser("spawn", help="launch one phase in its own session")
    p.add_argument("--slug", required=True)
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--prefix", default="impl")
    p.add_argument("--prompt")
    p.add_argument("--cwd")
    p.add_argument("--permission-mode")
    p.add_argument("--model")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-trust", action="store_true",
                   help="do not propagate the repo's trust to the worktree")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("reap", help="close the tmux windows of finished phases")
    p.add_argument("--slug", required=True)
    p.add_argument("--phase", type=int, action="append",
                   help="repeatable; every phase in the set when omitted")
    p.add_argument("--all", action="store_true",
                   help="accepted for clarity -- reaping the whole set is the default")
    p.add_argument("--include-failed", action="store_true",
                   help="also close failed and blocked phases (their log is kept)")
    p.add_argument("--force", action="store_true",
                   help="close a window even while its session may still be working")
    p.add_argument("--no-log", action="store_true",
                   help="skip the scrollback capture -- the window's output is lost")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("report", help="record a phase's outcome")
    p.add_argument("--slug", required=True)
    p.add_argument("--phase", type=int, required=True)
    p.add_argument("--status", required=True, choices=list(LIVE + TERMINAL))
    p.add_argument("--commit")
    p.add_argument("--task")
    p.add_argument("--note")

    p = sub.add_parser("verify", help="re-derive status from git and todos.md")
    p.add_argument("--slug", required=True)
    p.add_argument("--apply", action="store_true", help="write the derivation back")

    p = sub.add_parser("land", help="merge the set to main, push it, delete the branch")
    p.add_argument("--slug", required=True)
    p.add_argument("--step", required=True,
                   choices=("check", "merge", "push", "cleanup"),
                   help="the two steps needing judgement -- resolving a conflict and "
                        "applying the migrations -- sit between merge and push")
    p.add_argument("--message", help="the merge commit subject")
    p.add_argument("--retries", type=int, default=3,
                   help="how many times to merge a base that moved and push again")
    p.add_argument("--keep-remote", action="store_true",
                   help="leave origin/<branch> in place (an open PR still needs it)")
    p.add_argument("--force", action="store_true",
                   help="merge with phases not derived done, or clean up an unmerged "
                        "branch -- both are decisions, not defaults")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("find", help="which swarm owns this plan file or TaskID")
    p.add_argument("--plan")
    p.add_argument("--task")

    p = sub.add_parser("launch", help="open one named session in a new tmux window")
    p.add_argument("--name", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--cwd")
    p.add_argument("--repo")
    p.add_argument("--permission-mode")
    p.add_argument("--model")
    p.add_argument("--no-trust", action="store_true")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("track", help="make .workflows/orchestration/ survive .gitignore")
    p.add_argument("--dry-run", action="store_true")

    sub.add_parser("selftest", help="offline checks, no git or tmux needed")

    args = parser.parse_args(argv)
    return {"init": cmd_init, "waves": cmd_waves, "spawn": cmd_spawn,
            "reap": cmd_reap, "report": cmd_report, "land": cmd_land,
            "verify": cmd_verify, "status": cmd_status,
            "find": cmd_find, "track": cmd_track, "launch": cmd_launch,
            "selftest": lambda _: selftest()}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
