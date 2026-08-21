#!/usr/bin/env python3
"""Plumbing for the /task skill: GitHub Issues + a Projects v2 board.

Wraps the `gh` CLI. Stdlib only, no pip. Every subcommand prints JSON to stdout
so the caller never has to parse human output, and every failure exits non-zero
with one actionable sentence on stderr.

Subcommands:
  doctor                          check gh, auth, scopes, board and Status options
  list [--status NAME]            cards on the board
  resolve REF [--repo OWNER/REPO] one card: body, every comment in order, status, plan block
  create --repo OWNER/REPO TITLE  open an issue, put it on the board, set the stage
  promote REF --repo OWNER/REPO   convert a draft item into a real issue
  status REF NAME                 set the Status field (and reopen a closed issue)
  comment REF TEXT                add a comment (issues only)
  plan REF LABEL PATH             add a line to the plan block in the issue body
  worktree REF [--remove]         a worktree on task/<n>-<slug>, branched from origin/main
  pr REF [--plan PATH]            push the branch and open a PR that closes the issue
  links REF                       which PRs the issue and the board's field are showing
  reopen REF                      reopen an issue a merged PR closed
  finish REF                      Completed: needs a merged linked PR; reopens what it closed

REF forms: 14 | owner/repo#14 | https://github.com/owner/repo/issues/14 | PVTI_xxx
           | draft:<substring of the title>
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(
    os.environ.get("TASK_SKILL_CONFIG", Path.home() / ".config" / "task-skill" / "config.json")
)
DEFAULT_BOARD = os.environ.get("TASK_BOARD", "Tasks")
DEFAULT_OWNER = os.environ.get("TASK_OWNER", "@me")

# The plan-block codec, the stages and their aliases live in taskcore so that
# this backend and task_gl.py cannot drift apart. One implementation, one
# selftest: `python3 taskcore.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from taskcore import (  # noqa: E402
    PLAN_CLOSE,
    PLAN_OPEN,
    TaskError,
    map_stages,
    parse_plan_block,
    plan_entry,
    upsert_plan_block,
)
from taskcore import resolve_stage as _resolve_stage_name  # noqa: E402


# --------------------------------------------------------------------------- gh


def gh(*args, as_json=False, check=True, stdin=None) -> Any:
    """Run gh. Returns parsed JSON when as_json, else raw stdout."""
    try:
        proc = subprocess.run(
            ("gh",) + tuple(args),
            capture_output=True,
            text=True,
            input=stdin,
        )
    except FileNotFoundError:
        raise TaskError(
            "gh is not installed. `sudo apt install gh`, then `gh auth login` "
            "and `gh auth refresh -s project,read:project`."
        )
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        if "your authentication token is missing required scopes" in err or "read:project" in err:
            raise TaskError(
                "gh is missing the Projects scope. Run: "
                "gh auth refresh -s project,read:project"
            )
        raise TaskError(f"gh {' '.join(args)} failed:\n{err}")
    if as_json:
        out = proc.stdout.strip()
        if not out:
            raise TaskError(f"gh {' '.join(args)} returned no JSON.")
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise TaskError(f"gh {' '.join(args)} returned unparseable JSON: {exc}")
    return proc.stdout


# ------------------------------------------------------------------ board config


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            pass  # a corrupt cache is a cache miss, not an error
    return None


def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def discover_board(owner=DEFAULT_OWNER, board=DEFAULT_BOARD):
    """Find the board and its Status field. Loud on every ambiguity."""
    data = gh("project", "list", "--owner", owner, "--format", "json", as_json=True)
    projects = data.get("projects", data if isinstance(data, list) else [])
    if not projects:
        raise TaskError(
            f"No Projects boards found for owner {owner}. Create one with: "
            f'gh project create --owner {owner} --title "{board}"'
        )

    matches = [p for p in projects if str(p.get("title", "")).strip() == board]
    if not matches and board.isdigit():
        matches = [p for p in projects if str(p.get("number")) == board]
    if not matches:
        titles = ", ".join(repr(p.get("title")) for p in projects)
        raise TaskError(
            f"No board titled {board!r} for owner {owner}. Boards found: {titles}. "
            f"Set TASK_BOARD to the right title."
        )
    if len(matches) > 1:
        nums = ", ".join(str(p.get("number")) for p in matches)
        raise TaskError(
            f"{len(matches)} boards are titled {board!r} (numbers {nums}). "
            f"Set TASK_BOARD to the number instead of the title."
        )
    project = matches[0]
    number = str(project["number"])

    fields = gh(
        "project", "field-list", number, "--owner", owner, "--format", "json", as_json=True
    )
    field_list = fields.get("fields", fields if isinstance(fields, list) else [])
    status = next(
        (f for f in field_list if str(f.get("name", "")).strip().lower() == "status"), None
    )
    if status is None:
        names = ", ".join(repr(f.get("name")) for f in field_list)
        raise TaskError(
            f"Board {board!r} has no field named 'Status'. Fields: {names}. "
            f"The skill drives stages through the Status field."
        )
    options = {
        str(o["name"]).strip(): o["id"] for o in (status.get("options") or []) if o.get("name")
    }
    if not options:
        raise TaskError(
            f"The Status field on {board!r} has no options; it must be a single-select."
        )

    cfg = {
        "owner": owner,
        "board": board,
        "projectNumber": number,
        "projectId": project.get("id"),
        "statusFieldId": status.get("id"),
        "statusFieldName": status.get("name"),
        "statusOptions": options,
    }
    save_config(cfg)
    return cfg


def board_config(refresh=False):
    if not refresh:
        cfg = load_config()
        if cfg and cfg.get("board") == DEFAULT_BOARD and cfg.get("statusOptions"):
            return cfg
    return discover_board()


def stage_map(cfg):
    """Map each of STAGES onto a real Status option name, or None if absent.

    Accepts GitHub's shipped defaults (Todo/Done) so the skill works before the
    rename, and reports what it matched so the caller can say so out loud. The
    alias table itself is in taskcore, shared with the GitLab backend.
    """
    return map_stages(cfg["statusOptions"])


def resolve_stage(cfg, name):
    """Turn a stage name (ours or the board's) into a real option name + id.

    GitHub needs the option's id as well as its name, which is the only reason
    this wraps taskcore's version rather than being it.
    """
    options = cfg["statusOptions"]
    try:
        resolved = _resolve_stage_name(list(options), name)
    except TaskError:
        raise TaskError(
            f"Status option {name!r} is not on the board. Options: "
            f"{', '.join(sorted(options))}."
        )
    return resolved, options[resolved]


# ------------------------------------------------------------------- board items


def normalise_repo(value):
    if not value:
        return None
    value = str(value)
    m = re.search(r"github\.com[:/]([^/]+/[^/]+)", value)
    if m:
        return m.group(1).removesuffix(".git")
    return value.strip("/")


def fetch_items(cfg, limit=500):
    data = gh(
        "project", "item-list", cfg["projectNumber"],
        "--owner", cfg["owner"], "--format", "json", "--limit", str(limit),
        as_json=True,
    )
    items = data.get("items", data if isinstance(data, list) else [])
    status_key = str(cfg.get("statusFieldName") or "Status")
    out = []
    for raw in items:
        content = raw.get("content") or {}
        # gh flattens custom fields onto the item, keyed by field name in
        # varying case depending on version -- match case-insensitively.
        status = None
        for key, value in raw.items():
            if key.strip().lower() == status_key.strip().lower() and isinstance(value, str):
                status = value
                break
        kind = str(content.get("type") or raw.get("content_type") or "").lower()
        out.append(
            {
                "itemId": raw.get("id"),
                "kind": "draft" if "draft" in kind else "issue",
                "title": content.get("title") or raw.get("title"),
                "body": content.get("body") or raw.get("body") or "",
                "number": content.get("number"),
                "repo": normalise_repo(content.get("repository")),
                "url": content.get("url"),
                "status": status,
            }
        )
    return out


def match_ref(items, ref, repo_hint=None):
    """Find exactly one item for REF. Ambiguity is an error, never a guess."""
    ref = ref.strip()

    if ref.startswith("PVTI_"):
        found = [i for i in items if i["itemId"] == ref]
        if not found:
            raise TaskError(f"No item on the board with id {ref}.")
        return found[0]

    if ref.lower().startswith("draft:"):
        needle = ref[6:].strip().lower()
        found = [
            i for i in items
            if i["kind"] == "draft" and needle in str(i["title"] or "").lower()
        ]
        if not found:
            raise TaskError(f"No draft item whose title contains {needle!r}.")
        if len(found) > 1:
            titles = "; ".join(str(i["title"]) for i in found)
            raise TaskError(f"{len(found)} draft items match {needle!r}: {titles}")
        return found[0]

    repo, number = None, None
    m = re.search(r"github\.com/([^/]+/[^/]+)/issues/(\d+)", ref)
    if m:
        repo, number = m.group(1), int(m.group(2))
    else:
        m = re.fullmatch(r"([^/\s]+/[^/\s#]+)#(\d+)", ref)
        if m:
            repo, number = m.group(1), int(m.group(2))
        else:
            m = re.fullmatch(r"#?(\d+)", ref)
            if not m:
                raise TaskError(
                    f"Unrecognised reference {ref!r}. Use 14, owner/repo#14, an issue "
                    f"URL, PVTI_..., or draft:<title>."
                )
            number = int(m.group(1))
            repo = repo_hint

    found = [i for i in items if i["number"] == number]
    if repo:
        found = [i for i in found if i["repo"] == repo]
    if not found:
        where = f" in {repo}" if repo else ""
        raise TaskError(
            f"No card on the board for issue #{number}{where}. Either the number is "
            f"wrong or the issue was never added to the {DEFAULT_BOARD!r} board."
        )
    if len(found) > 1:
        repos = ", ".join(sorted({str(i["repo"]) for i in found}))
        raise TaskError(
            f"Issue #{number} is ambiguous across repos ({repos}). "
            f"Pass owner/repo#{number}."
        )
    return found[0]


# The plan block used to be implemented here as well as in task_gl.py. Both now
# import it from taskcore: parse_plan_block, render_plan_block, upsert_plan_block
# and plan_entry.


# ------------------------------------------------------------------ subcommands


def cmd_doctor(args):
    report = {"ok": False, "checks": []}

    def check(name, fn):
        try:
            report["checks"].append({"name": name, "ok": True, "detail": fn()})
            return True
        except TaskError as exc:
            report["checks"].append({"name": name, "ok": False, "detail": str(exc)})
            return False

    if not check("gh installed", lambda: gh("--version").splitlines()[0].strip()):
        print(json.dumps(report, indent=2))
        return 1

    def auth():
        out = gh("auth", "status", check=False)
        if "Logged in" not in out:
            out2 = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True
            ).stderr
            out = out + out2
        if "Logged in" not in out:
            raise TaskError("Not logged in. Run: gh auth login")
        scopes = ""
        for line in out.splitlines():
            if "Token scopes" in line:
                scopes = line.split(":", 1)[1].strip()
        if "project" not in scopes:
            raise TaskError(
                f"Token scopes are [{scopes}] with no project scope. "
                f"Run: gh auth refresh -s project,read:project"
            )
        return f"logged in, scopes: {scopes}"

    if not check("gh authenticated with project scope", auth):
        print(json.dumps(report, indent=2))
        return 1

    cfg_holder = {}

    def board():
        cfg = discover_board()
        cfg_holder["cfg"] = cfg
        return f"{cfg['board']!r} is project #{cfg['projectNumber']}"

    if not check(f"board {DEFAULT_BOARD!r} exists", board):
        print(json.dumps(report, indent=2))
        return 1

    cfg = cfg_holder["cfg"]

    def stages():
        mapping = stage_map(cfg)
        missing = [s for s, v in mapping.items() if v is None]
        if missing:
            raise TaskError(
                f"No Status option matches {', '.join(missing)}. Options are "
                f"{', '.join(sorted(cfg['statusOptions']))} -- rename them in the "
                f"browser to Open / In Progress / Completed."
            )
        renamed = {s: v for s, v in mapping.items() if v != s}
        if renamed:
            pairs = ", ".join(f"{s} -> {v!r}" for s, v in renamed.items())
            return f"mapped via aliases: {pairs}"
        return "Open / In Progress / Completed all present"

    ok = check("Status options cover the three stages", stages)

    # Reported, not failed. The field is built into every Projects v2 board, so
    # an absence here means gh did not list it or the view hides the column --
    # neither is worth a red doctor, and both are worth saying out loud.
    try:
        fields = gh("project", "field-list", cfg["projectNumber"], "--owner", cfg["owner"],
                    "--format", "json", as_json=True)
        names = [
            str(f.get("name", "")).strip()
            for f in fields.get("fields", fields if isinstance(fields, list) else [])
        ]
        hit = next((n for n in names if n.lower() == "linked pull requests"), None)
        report["linkedPullRequestsField"] = hit or (
            "not listed by gh -- add the built-in 'Linked pull requests' column to the "
            f"board view. Fields: {', '.join(names)}"
        )
    except TaskError as exc:
        report["linkedPullRequestsField"] = f"could not be read: {exc}"

    report["worktreeRoot"] = str(WORKTREE_ROOT)
    report["config"] = cfg
    report["ok"] = ok
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


def cmd_list(args):
    cfg = board_config(refresh=args.refresh)
    items = fetch_items(cfg)
    if args.status:
        wanted, _ = resolve_stage(cfg, args.status)
        items = [i for i in items if (i["status"] or "") == wanted]
    if args.repo:
        items = [i for i in items if i["repo"] == args.repo]
    for item in items:
        item["plans"] = parse_plan_block(item["body"])
    print(json.dumps({"board": cfg["board"], "stages": stage_map(cfg), "items": items}, indent=2))
    return 0


def cmd_resolve(args):
    cfg = board_config(refresh=args.refresh)
    items = fetch_items(cfg)
    item = match_ref(items, args.ref, args.repo)

    out = dict(item)
    out["comments"] = []
    out["stages"] = stage_map(cfg)

    if item["kind"] == "issue" and item["repo"] and item["number"]:
        detail = gh(
            "issue", "view", str(item["number"]), "--repo", item["repo"],
            "--json", "number,title,body,url,state,comments,createdAt,updatedAt,labels",
            as_json=True,
        )
        out["body"] = detail.get("body") or ""
        out["title"] = detail.get("title")
        out["url"] = detail.get("url")
        out["state"] = detail.get("state")
        out["createdAt"] = detail.get("createdAt")
        out["labels"] = [l.get("name") for l in (detail.get("labels") or [])]
        out["comments"] = [
            {
                "author": (c.get("author") or {}).get("login"),
                "createdAt": c.get("createdAt"),
                "body": c.get("body") or "",
            }
            for c in (detail.get("comments") or [])
        ]

    out["plans"] = parse_plan_block(out["body"])
    # Round two: a plan is already recorded and something was said after it.
    out["round"] = len(out["plans"]) + 1 if out["plans"] else 1
    out["commentsAfterLastPlan"] = len(out["comments"])
    print(json.dumps(out, indent=2))
    return 0


def board_item_for_issue(cfg, repo, number, attempts=1, delay=1.0):
    """The board item wrapping this issue, or None. Always a fresh fetch.

    MEASURED: `gh project item-add` returns the new item's id, and the very next
    `item-list` does not include it yet -- Projects is eventually consistent. The
    first version of `create` read back once, reported "the board does not show it"
    and exited non-zero for a card that was in fact placed correctly. So a read-back
    that means "did this land?" has to be allowed to wait; `attempts=1` keeps every
    other caller's behaviour unchanged.
    """
    for attempt in range(attempts):
        for item in fetch_items(cfg):
            if item["kind"] == "issue" and item["repo"] == repo and item["number"] == number:
                return item
        if attempt + 1 < attempts:
            time.sleep(delay)
    return None


def cmd_create(args):
    """Open a card and put it ON THE BOARD — the whole reason this exists.

    `gh issue create` alone leaves an issue the board has never heard of: it does not
    appear in any column, `resolve` cannot find it, and the next session that opens
    the kanban sees nothing. MEASURED: issue #6 in run-insights was created with plain
    `gh issue create` and `resolve 6` answered "No card on the board for issue #6."

    So creation is three steps, never one — open, add, stage — and the last thing this
    does is read the board back and say which column the card actually landed in.
    """
    cfg = board_config(refresh=args.refresh)

    # Completed is not a stage a card can be born in. `finish` owns that transition and
    # gates it on a merged pull request; letting `create` write it would route around the
    # one check that keeps the board from running ahead of reality.
    stage = args.stage or "Open"
    name, option_id = resolve_stage(cfg, stage)
    if name == stage_map(cfg)["Completed"]:
        raise TaskError(
            "A new card cannot start Completed. Create it Open (or In Progress if you are "
            "picking it up now); `finish` is what writes Completed, and it requires a merged PR."
        )

    repo = normalise_repo(args.repo)

    # ── DRAFT: an idea with no home yet. No repo, no number, no comments until promoted.
    if args.draft:
        if repo:
            raise TaskError("--draft and --repo are mutually exclusive: a draft item has no repo.")
        result = gh(
            "project", "item-create", str(cfg["projectNumber"]),
            "--owner", cfg["owner"],
            "--title", args.title,
            *(["--body", read_body(args)] if has_body(args) else []),
            "--format", "json",
            as_json=True,
        )
        item_id = result.get("id")
        if not item_id:
            raise TaskError(f"Could not read the new draft item's id from gh: {result!r}")
        gh("project", "item-edit", "--id", item_id, "--project-id", cfg["projectId"],
           "--field-id", cfg["statusFieldId"], "--single-select-option-id", option_id)
        print(json.dumps({
            "created": True, "kind": "draft", "itemId": item_id, "title": args.title,
            "status": name,
            "hint": f"no issue number until: task_gh.py promote 'draft:{args.title[:24]}' --repo OWNER/REPO",
        }, indent=2))
        return 0

    # ── ISSUE: either open a new one, or adopt one that is already off the board.
    if args.issue is not None:
        if not repo:
            raise TaskError("--issue needs --repo OWNER/REPO to say which repo it lives in.")
        existing = gh("issue", "view", str(args.issue), "--repo", repo,
                      "--json", "number,url,title,state", as_json=True)
        number, url, title = existing["number"], existing["url"], existing["title"]
        created = False
    else:
        if not repo:
            raise TaskError(
                "create needs --repo OWNER/REPO (or --draft for an idea with no home yet). "
                "Guessing the repo is how a card lands in the wrong project."
            )
        if not args.title:
            raise TaskError("create needs a TITLE.")
        cmd = ["issue", "create", "--repo", repo, "--title", args.title]
        if has_body(args):
            cmd += ["--body-file", "-"]
        for label in args.label or []:
            cmd += ["--label", label]
        out = gh(*cmd, stdin=read_body(args) if has_body(args) else None)
        url = (out or "").strip().splitlines()[-1].strip()
        m = re.search(r"/issues/(\d+)$", url)
        if not m:
            raise TaskError(f"Issue created but its URL could not be parsed: {url!r}")
        number, title, created = int(m.group(1)), args.title, True

    already = board_item_for_issue(cfg, repo, number)
    if already:
        item_id = already["itemId"]
        added = False
    else:
        result = gh("project", "item-add", str(cfg["projectNumber"]),
                    "--owner", cfg["owner"], "--url", url, "--format", "json", as_json=True)
        item_id = result.get("id")
        if not item_id:
            raise TaskError(f"Issue #{number} exists but could not be added to the board: {result!r}")
        added = True

    gh("project", "item-edit", "--id", item_id, "--project-id", cfg["projectId"],
       "--field-id", cfg["statusFieldId"], "--single-select-option-id", option_id)

    # READ BACK. The point of the command is board membership, so prove it rather than
    # assume the two mutations above took.
    placed = board_item_for_issue(cfg, repo, number, attempts=8, delay=1.5)
    on_board = placed is not None
    landed = placed["status"] if placed else None
    verdict = (
        f"#{number} is on the board in '{landed}'"
        if on_board and landed == name
        else f"#{number} is on the board but Status reads {landed!r}, expected {name!r}"
        if on_board
        else f"#{number} exists at {url} but the board does not show it — re-run with --issue "
             f"{number} --repo {repo}"
    )
    print(json.dumps({
        "created": created, "adopted": args.issue is not None, "addedToBoard": added,
        "kind": "issue", "repo": repo, "number": number, "url": url, "title": title,
        "itemId": item_id, "status": landed, "onBoard": on_board, "verdict": verdict,
    }, indent=2))
    return 0 if on_board else 1


def has_body(args):
    return bool(getattr(args, "body", None) or getattr(args, "body_file", None))


def read_body(args):
    """--body wins over --body-file; `-` means stdin. Returns the text, never None."""
    if getattr(args, "body", None):
        return args.body
    path = getattr(args, "body_file", None)
    if not path:
        return ""
    if path == "-":
        return sys.stdin.read()
    text = Path(path)
    if not text.exists():
        raise TaskError(f"--body-file not found: {path}")
    return text.read_text()


def cmd_promote(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "draft":
        print(json.dumps({"promoted": False, "reason": "already an issue", **item}, indent=2))
        return 0
    if not args.repo:
        raise TaskError("promote needs --repo OWNER/REPO to say where the issue is created.")
    repo = gh("repo", "view", args.repo, "--json", "id,nameWithOwner", as_json=True)
    mutation = (
        "mutation($itemId:ID!,$repoId:ID!){"
        "convertProjectV2DraftIssueItemToIssue("
        "input:{itemId:$itemId,repositoryId:$repoId}){"
        "item{id content{... on Issue{number url title}}}}}"
    )
    result = gh(
        "api", "graphql",
        "-f", f"query={mutation}",
        "-F", f"itemId={item['itemId']}",
        "-F", f"repoId={repo['id']}",
        as_json=True,
    )
    content = (
        result.get("data", {})
        .get("convertProjectV2DraftIssueItemToIssue", {})
        .get("item", {})
        .get("content", {})
    ) or {}
    print(
        json.dumps(
            {
                "promoted": True,
                "itemId": item["itemId"],
                "repo": repo["nameWithOwner"],
                "number": content.get("number"),
                "url": content.get("url"),
                "title": content.get("title") or item["title"],
            },
            indent=2,
        )
    )
    return 0


def cmd_status(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    name, option_id = resolve_stage(cfg, args.name)
    changed = (item["status"] or "") != name
    if changed:
        gh(
            "project", "item-edit",
            "--id", item["itemId"],
            "--project-id", cfg["projectId"],
            "--field-id", cfg["statusFieldId"],
            "--single-select-option-id", option_id,
        )
    # Runs even when the stage did not change: a merged PR closes the issue, and
    # a closed item is what auto-archive removes from the board.
    issue = ensure_issue_open(item)
    print(
        json.dumps(
            {
                "changed": changed,
                "from": item["status"],
                "to": name,
                "itemId": item["itemId"],
                "issue": issue,
            },
            indent=2,
        )
    )
    return 0


def cmd_comment(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError(
            "A draft item cannot take comments. Promote it to an issue first: "
            f"task_gh.py promote {args.ref} --repo OWNER/REPO"
        )
    gh(
        "issue", "comment", str(item["number"]), "--repo", item["repo"], "--body-file", "-",
        stdin=args.text,
    )
    print(json.dumps({"commented": True, "repo": item["repo"], "number": item["number"]}, indent=2))
    return 0


def cmd_plan(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError(
            "A draft item has no durable body to link a plan into. Promote it first: "
            f"task_gh.py promote {args.ref} --repo OWNER/REPO"
        )
    detail = gh(
        "issue", "view", str(item["number"]), "--repo", item["repo"], "--json", "body",
        as_json=True,
    )
    entry = plan_entry(args.label, args.path, args.date)
    new_body, entries = upsert_plan_block(detail.get("body") or "", entry)
    if new_body == (detail.get("body") or ""):
        print(json.dumps({"changed": False, "plans": entries}, indent=2))
        return 0
    gh(
        "issue", "edit", str(item["number"]), "--repo", item["repo"], "--body-file", "-",
        stdin=new_body,
    )
    print(json.dumps({"changed": True, "plans": entries}, indent=2))
    return 0


# ------------------------------------------------------------ git and worktrees

# Worktrees live outside every repo on purpose: nothing to add to a .gitignore,
# no way to commit one by accident, and one directory to list or prune.
WORKTREE_ROOT = Path(os.environ.get("TASK_WORKTREES", Path.home() / ".worktrees"))

# GitHub only creates an issue<->PR *link* -- the thing the board's "Linked pull
# requests" field reads -- from one of these keywords in the PR body. A bare
# "#14" is a mention, and mentions do not populate that field.
CLOSING_KEYWORDS = (
    "close", "closes", "closed",
    "fix", "fixes", "fixed",
    "resolve", "resolves", "resolved",
)


def git_run(*args, cwd=None, check=True):
    try:
        proc = subprocess.run(("git",) + tuple(args), capture_output=True, text=True, cwd=cwd)
    except FileNotFoundError:
        raise TaskError("git is not installed, so there is no worktree to work in.")
    if check and proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        raise TaskError(f"git {' '.join(args)} failed:\n{err}")
    return proc


def git_out(*args, cwd=None):
    return git_run(*args, cwd=cwd).stdout.strip()


def git_ok(*args, cwd=None):
    return git_run(*args, cwd=cwd, check=False).returncode == 0


def repo_root(cwd):
    proc = git_run("rev-parse", "--show-toplevel", cwd=cwd, check=False)
    if proc.returncode != 0:
        raise TaskError(f"{cwd} is not inside a git repository. Pass --dir <repo path>.")
    return proc.stdout.strip()


def origin_repo(root):
    proc = git_run("remote", "get-url", "origin", cwd=root, check=False)
    if proc.returncode != 0:
        raise TaskError(
            f"{root} has no 'origin' remote, so there is nothing to branch from or push to."
        )
    return normalise_repo(proc.stdout.strip())


def assert_same_repo(item, root):
    """The card's repo must be this repo. Branching in the wrong one is worse than an error."""
    origin = origin_repo(root)
    if item.get("repo") and origin and item["repo"].lower() != origin.lower():
        raise TaskError(
            f"Card {item['repo']}#{item['number']} does not belong to {origin} ({root}). "
            f"Run this from that repo, or pass --dir <path>."
        )
    return origin


def resolve_base(root, base=None):
    """The ref new branches start from. origin/main unless the repo says otherwise."""
    if base:
        if not git_ok("rev-parse", "--verify", "--quiet", base, cwd=root):
            raise TaskError(f"{base} does not exist here. Run: git fetch origin")
        return base
    if git_ok("rev-parse", "--verify", "--quiet", "origin/main", cwd=root):
        return "origin/main"
    head = git_run(
        "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", cwd=root, check=False
    ).stdout.strip()
    if head.startswith("origin/") and git_ok("rev-parse", "--verify", "--quiet", head, cwd=root):
        return head
    if git_ok("rev-parse", "--verify", "--quiet", "origin/master", cwd=root):
        return "origin/master"
    raise TaskError(
        "There is no origin/main here and origin's default branch could not be read. "
        "Run `git fetch origin`, or pass --base explicitly."
    )


def slugify(text, limit=40):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    if len(s) > limit:
        s = s[:limit].rsplit("-", 1)[0] if "-" in s[:limit] else s[:limit]
    return s.strip("-") or "task"


def branch_name(number, title, round_no=1, prefix="task"):
    """task/14-add-recurring-cards, and -r2 on a return visit so round one's branch survives."""
    base = f"{prefix}/{number}-{slugify(title)}"
    return base if (round_no or 1) <= 1 else f"{base}-r{int(round_no)}"


def worktree_path(root, branch):
    return WORKTREE_ROOT / Path(root).name / branch.replace("/", "-")


def list_worktrees(root):
    entries, cur = [], {}
    for line in git_out("worktree", "list", "--porcelain", cwd=root).splitlines():
        key, _, val = line.partition(" ")
        if key == "worktree":
            if cur:
                entries.append(cur)
            cur = {"path": val, "branch": None}
        elif key == "branch":
            cur["branch"] = val.removeprefix("refs/heads/")
    if cur:
        entries.append(cur)
    return entries


def ensure_closes(body, number):
    """Guarantee the PR body carries a closing keyword for #number.

    Returns (body, added). Without this the PR is only a mention, the board's
    Linked pull requests column stays empty, and the card looks unworked.
    """
    pattern = re.compile(rf"\b(?:{'|'.join(CLOSING_KEYWORDS)})\b\s*:?\s+#{number}\b", re.I)
    if pattern.search(body or ""):
        return (body or ""), False
    rest = (body or "").strip()
    return (f"Closes #{number}\n" + (f"\n{rest}\n" if rest else "")), True


def default_pr_body(item, plan=None):
    lines = [f"Closes #{item['number']}", ""]
    if plan:
        lines.append(f"Plan: `{plan}`")
    if item.get("url"):
        lines.append(f"Card: {item['url']}")
    return "\n".join(lines).rstrip() + "\n"


# ------------------------------------------------------- linked pull requests


def issue_links(repo, number):
    """PRs GitHub considers linked to this issue -- the board field's own source.

    Tries the documented field first, falls back to the timeline, and says which
    one answered rather than reporting an empty list as fact.
    """
    owner, name = repo.split("/", 1)

    primary = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){issue(number:$number){"
        "closedByPullRequestsReferences(first:10,includeClosedPrs:true){"
        "nodes{number url state isDraft merged mergeCommit{oid}}}}}}"
    )
    fallback = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){issue(number:$number){"
        "timelineItems(first:100,itemTypes:[CONNECTED_EVENT]){nodes{"
        "... on ConnectedEvent{subject{__typename ... on PullRequest{"
        "number url state isDraft merged mergeCommit{oid}}}}}}}}}"
    )

    def ask(query):
        return gh(
            "api", "graphql",
            "-f", f"query={query}",
            "-f", f"owner={owner}",
            "-f", f"name={name}",
            "-F", f"number={number}",
            as_json=True,
        )

    def shape(nodes):
        out = []
        for pr in nodes or []:
            if not pr:
                continue
            out.append(
                {
                    "number": pr.get("number"),
                    "url": pr.get("url"),
                    "state": pr.get("state"),
                    "draft": bool(pr.get("isDraft")),
                    "merged": bool(pr.get("merged")),
                    "mergeCommit": (pr.get("mergeCommit") or {}).get("oid"),
                }
            )
        return out

    try:
        data = ask(primary)
        nodes = data["data"]["repository"]["issue"]["closedByPullRequestsReferences"]["nodes"]
        return {"source": "closedByPullRequestsReferences", "pullRequests": shape(nodes)}
    except (TaskError, KeyError, TypeError):
        pass
    try:
        data = ask(fallback)
        nodes = [
            n.get("subject")
            for n in data["data"]["repository"]["issue"]["timelineItems"]["nodes"] or []
            if (n or {}).get("subject", {}).get("__typename") == "PullRequest"
        ]
        return {"source": "timelineItems(ConnectedEvent)", "pullRequests": shape(nodes)}
    except (TaskError, KeyError, TypeError) as exc:
        return {"source": None, "pullRequests": [], "unknown": str(exc)}


def board_links(item_id):
    """What the board's own 'Linked pull requests' field holds for this card."""
    query = (
        "query($id:ID!){node(id:$id){... on ProjectV2Item{fieldValues(first:50){nodes{"
        "__typename ... on ProjectV2ItemFieldPullRequestValue{"
        "field{... on ProjectV2FieldCommon{name}}"
        "pullRequests(first:10){nodes{number url}}}}}}}}"
    )
    try:
        data = gh("api", "graphql", "-f", f"query={query}", "-f", f"id={item_id}", as_json=True)
        nodes = (data["data"]["node"]["fieldValues"]["nodes"]) or []
        for node in nodes:
            if (node or {}).get("__typename") == "ProjectV2ItemFieldPullRequestValue":
                return {
                    "field": (node.get("field") or {}).get("name") or "Linked pull requests",
                    "pullRequests": (node.get("pullRequests") or {}).get("nodes") or [],
                }
        return {"field": "Linked pull requests", "pullRequests": []}
    except (TaskError, KeyError, TypeError) as exc:
        return {"known": False, "reason": str(exc)}


def link_report(item):
    issue = issue_links(item["repo"], item["number"])
    board = board_links(item["itemId"])
    prs = issue["pullRequests"]
    merged = [p for p in prs if p["merged"]]
    if not prs:
        verdict = (
            f"No pull request is linked to #{item['number']}. The board's column will be "
            f"empty until a PR body says `Closes #{item['number']}`."
        )
    elif merged:
        verdict = "linked and merged: " + ", ".join(f"#{p['number']}" for p in merged)
    else:
        verdict = "linked, not merged yet: " + ", ".join(f"#{p['number']}" for p in prs)
    if isinstance(board.get("pullRequests"), list) and prs and not board["pullRequests"]:
        verdict += " (the board field can lag a few seconds behind the link)"
    return {"issueLinks": issue, "boardField": board, "verdict": verdict}


def ensure_issue_open(item):
    """No card of ours is ever left closed on GitHub.

    A linked PR closes the issue on merge, and a closed item is what Projects'
    auto-archive workflow eats -- which would silently break the reopen loop.
    Every stage write goes through here, so it cannot be forgotten.
    """
    if item.get("kind") != "issue" or not item.get("number"):
        return {"state": None, "reopened": False}
    state = gh(
        "issue", "view", str(item["number"]), "--repo", item["repo"], "--json", "state",
        as_json=True,
    ).get("state") or ""
    if state.upper() != "CLOSED":
        return {"state": state, "reopened": False}
    gh("issue", "reopen", str(item["number"]), "--repo", item["repo"])
    return {"state": "OPEN", "reopened": True}


# --------------------------------------------------- worktree / pr subcommands


def cmd_worktree(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError(
            "A draft item has no number to name a branch after. Promote it first: "
            f"task_gh.py promote {args.ref} --repo OWNER/REPO"
        )
    root = repo_root(args.dir or os.getcwd())
    assert_same_repo(item, root)

    branch = args.branch or branch_name(item["number"], item["title"], args.round)
    path = worktree_path(root, branch)
    existing = list_worktrees(root)
    at_path = next((e for e in existing if e["path"] == str(path)), None)

    if args.remove:
        if at_path is None:
            print(json.dumps(
                {"removed": False, "reason": "no worktree at this path", "path": str(path)},
                indent=2))
            return 0
        git_out(*(["worktree", "remove", str(path)] + (["--force"] if args.force else [])), cwd=root)
        git_out("worktree", "prune", cwd=root)
        print(json.dumps({"removed": True, "path": str(path), "branch": branch}, indent=2))
        return 0

    if not args.no_fetch:
        git_out("fetch", "origin", "--prune", cwd=root)
    base = resolve_base(root, args.base)

    created, branch_created = False, False
    if at_path and at_path["branch"] == branch:
        pass  # idempotent: this is the worktree we would have made
    elif at_path:
        raise TaskError(
            f"{path} already exists as a worktree on branch {at_path['branch']!r}, not "
            f"{branch!r}. Remove it first: git worktree remove {path}"
        )
    else:
        elsewhere = next((e for e in existing if e["branch"] == branch), None)
        if elsewhere:
            print(json.dumps(
                {
                    "created": False, "path": elsewhere["path"], "branch": branch,
                    "note": "that branch is already checked out in this worktree",
                },
                indent=2))
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if git_ok("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=root):
            git_out("worktree", "add", str(path), branch, cwd=root)
        else:
            git_out("worktree", "add", "-b", branch, str(path), base, cwd=root)
            branch_created = True
        created = True

    work = str(path)
    hints = []
    if created:
        if (path / "package.json").exists():
            hints.append("fresh worktree: run `npm install` (node_modules is not shared)")
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            hints.append("fresh worktree: recreate the virtualenv before running anything")
    print(json.dumps(
        {
            "created": created,
            "branchCreated": branch_created,
            "path": work,
            "branch": branch,
            "base": base,
            "baseSha": git_out("rev-parse", base, cwd=root)[:12],
            "head": git_out("rev-parse", "HEAD", cwd=work)[:12],
            "behindBase": int(git_out("rev-list", "--count", f"HEAD..{base}", cwd=work) or 0),
            "repo": item["repo"],
            "number": item["number"],
            "hints": hints,
        },
        indent=2))
    return 0


def cmd_pr(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError(
            "A draft item cannot be linked to a pull request. Promote it first: "
            f"task_gh.py promote {args.ref} --repo OWNER/REPO"
        )
    root = repo_root(args.dir or os.getcwd())
    assert_same_repo(item, root)

    head = args.head or git_out("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if head == "HEAD":
        raise TaskError(f"HEAD is detached in {root}. Check out the task branch first.")
    base = (args.base or resolve_base(root)).removeprefix("origin/")
    if head == base:
        raise TaskError(
            f"Refusing to open a pull request from {head!r} onto itself. The work belongs on a "
            f"task branch in a worktree: task_gh.py worktree {args.ref}"
        )
    if not git_ok("diff", "--quiet", "HEAD", cwd=root):
        raise TaskError(
            f"{root} has uncommitted changes. Commit them before opening the pull request, "
            f"or the PR will not contain the work."
        )

    body = args.body
    if args.body_file:
        body = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text()
    if body is None:
        body = default_pr_body(item, args.plan)
    body, keyword_added = ensure_closes(body, item["number"])

    if not args.no_push:
        git_out("push", "-u", "origin", f"{head}:{head}", cwd=root)

    listed = gh(
        "pr", "list", "--repo", item["repo"], "--head", head, "--state", "all",
        "--json", "number,url,state,isDraft,body", "--limit", "10",
        as_json=True,
    )
    open_prs = [p for p in listed if str(p.get("state", "")).upper() == "OPEN"]

    if open_prs:
        pr = open_prs[0]
        created = False
        fixed_body, added = ensure_closes(pr.get("body") or "", item["number"])
        if added:
            gh("pr", "edit", str(pr["number"]), "--repo", item["repo"], "--body-file", "-",
               stdin=fixed_body)
        keyword_added = added
    else:
        gh(
            *(["pr", "create", "--repo", item["repo"], "--base", base, "--head", head,
               "--title", args.title or item["title"] or f"Task #{item['number']}",
               "--body-file", "-"] + (["--draft"] if args.draft else [])),
            stdin=body,
        )
        pr = gh("pr", "view", head, "--repo", item["repo"],
                "--json", "number,url,state,isDraft", as_json=True)
        created = True

    out = {
        "created": created,
        "pr": {
            "number": pr.get("number"),
            "url": pr.get("url"),
            "state": pr.get("state"),
            "draft": bool(pr.get("isDraft")),
        },
        "head": head,
        "base": base,
        "closingKeywordAdded": keyword_added,
        "previousPrs": [
            {"number": p["number"], "state": p["state"]} for p in listed
            if str(p.get("state", "")).upper() != "OPEN"
        ],
    }
    out.update(link_report(item))
    print(json.dumps(out, indent=2))
    return 0


def cmd_links(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError("A draft item has no pull requests. Promote it first.")
    out = {"repo": item["repo"], "number": item["number"], "status": item["status"]}
    out.update(link_report(item))
    print(json.dumps(out, indent=2))
    return 0


def cmd_reopen(args):
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    result = ensure_issue_open(item)
    print(json.dumps({"repo": item["repo"], "number": item["number"], **result}, indent=2))
    return 0


def cmd_finish(args):
    """Completed, on evidence: a merged linked PR, the Status field, and never closed."""
    cfg = board_config(refresh=args.refresh)
    item = match_ref(fetch_items(cfg), args.ref, args.repo)
    if item["kind"] != "issue":
        raise TaskError("A draft item cannot be completed. Promote it first.")

    report = link_report(item)
    merged = [p for p in report["issueLinks"]["pullRequests"] if p["merged"]]
    if not merged and not args.allow_unmerged:
        raise TaskError(
            f"No merged pull request is linked to #{item['number']}: {report['verdict']}. "
            f"Merge the PR first, or pass --allow-unmerged if this card genuinely has no PR."
        )

    name, option_id = resolve_stage(cfg, "Completed")
    changed = (item["status"] or "") != name
    if changed:
        gh("project", "item-edit", "--id", item["itemId"], "--project-id", cfg["projectId"],
           "--field-id", cfg["statusFieldId"], "--single-select-option-id", option_id)
    reopened = ensure_issue_open(item)

    note = args.note
    if note is None and merged:
        shas = ", ".join(f"#{p['number']} ({(p['mergeCommit'] or '')[:8]})" for p in merged)
        note = f"Completed. Merged in {shas}."
    if note:
        gh("issue", "comment", str(item["number"]), "--repo", item["repo"], "--body-file", "-",
           stdin=note)

    print(json.dumps(
        {
            "status": name,
            "changed": changed,
            "mergedPrs": [p["number"] for p in merged],
            "commented": bool(note),
            "issue": reopened,
            **report,
        },
        indent=2))
    return 0


def cmd_selftest(args):
    """Offline assertions on the pure logic. No gh, no network."""
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    # plan block: created, appended, idempotent, and only the block is touched
    b0 = "Some description.\n"
    b1, e1 = upsert_plan_block(b0, "F23 — `plans/F23-a.md` (2026-08-12)")
    eq("first entry", e1, ["F23 — `plans/F23-a.md` (2026-08-12)"])
    eq("body preserved", b1.startswith("Some description."), True)
    eq("block present", PLAN_OPEN in b1 and PLAN_CLOSE in b1, True)

    b2, e2 = upsert_plan_block(b1, "F23 round 2 — `plans/F23-a.md` (2026-08-20)")
    eq("append", len(e2), 2)
    eq("single block", b2.count(PLAN_OPEN), 1)

    b3, e3 = upsert_plan_block(b2, "F23 round 2 — `plans/F23-a.md` (2026-08-20)")
    eq("idempotent body", b3, b2)
    eq("idempotent entries", e3, e2)

    tail = "Some description.\n"
    eq("prefix intact", b2.startswith(tail), True)

    trailing = b2.split(PLAN_CLOSE, 1)[1]
    b4, _ = upsert_plan_block(b2 + "\nText added after the block.\n", "F24 — `plans/F24.md`")
    eq("text after block survives", "Text added after the block." in b4, True)
    eq("still one block", b4.count(PLAN_OPEN), 1)
    eq("trailing shape", isinstance(trailing, str), True)

    eq("parse empty", parse_plan_block(""), [])
    eq("parse no block", parse_plan_block("nothing here"), [])

    # repo normalisation
    eq("repo url", normalise_repo("https://github.com/miftahulmahfuzh/daily-words"), "miftahulmahfuzh/daily-words")
    eq("repo plain", normalise_repo("miftahulmahfuzh/daily-words"), "miftahulmahfuzh/daily-words")
    eq("repo git suffix", normalise_repo("https://github.com/a/b.git"), "a/b")
    eq("repo none", normalise_repo(None), None)

    # ref matching
    items = [
        {"itemId": "PVTI_1", "kind": "issue", "number": 14, "repo": "me/alpha", "title": "A", "body": "", "status": "Open", "url": None},
        {"itemId": "PVTI_2", "kind": "issue", "number": 14, "repo": "me/beta", "title": "B", "body": "", "status": "Open", "url": None},
        {"itemId": "PVTI_3", "kind": "draft", "number": None, "repo": None, "title": "Idea about search", "body": "", "status": "Open", "url": None},
    ]
    eq("by item id", match_ref(items, "PVTI_3")["itemId"], "PVTI_3")
    eq("by repo#n", match_ref(items, "me/beta#14")["itemId"], "PVTI_2")
    eq("by url", match_ref(items, "https://github.com/me/alpha/issues/14")["itemId"], "PVTI_1")
    eq("by hint", match_ref(items, "14", "me/alpha")["itemId"], "PVTI_1")
    eq("draft substring", match_ref(items, "draft:search")["itemId"], "PVTI_3")

    for bad, why in [
        ("14", "ambiguous bare number across repos"),
        ("me/gamma#14", "wrong repo"),
        ("99", "no such number"),
        ("nonsense", "unparseable"),
        ("draft:absent", "no draft matches"),
    ]:
        try:
            match_ref(items, bad)
            failures.append(f"{bad!r} ({why}) should have raised")
        except TaskError:
            pass

    # stage mapping against GitHub's shipped defaults and against ours
    default_cfg = {"statusOptions": {"Todo": "a", "In Progress": "b", "Done": "c"}, "statusFieldName": "Status"}
    eq("alias Open", stage_map(default_cfg)["Open"], "Todo")
    eq("alias Completed", stage_map(default_cfg)["Completed"], "Done")
    eq("resolve alias", resolve_stage(default_cfg, "Completed"), ("Done", "c"))
    eq("resolve exact", resolve_stage(default_cfg, "In Progress"), ("In Progress", "b"))

    ours = {"statusOptions": {"Open": "x", "In Progress": "y", "Completed": "z"}, "statusFieldName": "Status"}
    eq("exact Open", stage_map(ours)["Open"], "Open")
    try:
        resolve_stage(ours, "Blocked")
        failures.append("unknown stage should have raised")
    except TaskError:
        pass

    partial = {"statusOptions": {"Todo": "a"}, "statusFieldName": "Status"}
    eq("missing stages reported", [s for s, v in stage_map(partial).items() if v is None], ["In Progress", "Completed"])

    # branch naming: slug, length cap on a word boundary, and round two
    eq("slug", slugify("Add recurring cards!"), "add-recurring-cards")
    eq("slug punctuation only", slugify("???"), "task")
    eq("slug none", slugify(None), "task")
    eq("slug capped", len(slugify("a" * 60)) <= 40, True)
    eq("slug cut on boundary", slugify("one two three four five six seven eight nine ten"),
       "one-two-three-four-five-six-seven-eight")
    eq("branch", branch_name(14, "Add recurring cards"), "task/14-add-recurring-cards")
    eq("branch round 1", branch_name(14, "X", 1), "task/14-x")
    eq("branch round 2", branch_name(14, "X", 2), "task/14-x-r2")
    eq("worktree path", str(worktree_path("/home/me/daily-words", "task/14-x")),
       str(WORKTREE_ROOT / "daily-words" / "task-14-x"))

    # the closing keyword is what populates the board's Linked pull requests
    b, added = ensure_closes("Adds the thing.", 14)
    eq("keyword added", added, True)
    eq("keyword first line", b.splitlines()[0], "Closes #14")
    eq("body kept", "Adds the thing." in b, True)
    eq("idempotent keyword", ensure_closes(b, 14)[1], False)
    eq("fixes counts", ensure_closes("Fixes #14 at last", 14)[1], False)
    eq("resolved counts", ensure_closes("resolved: #14", 14)[1], False)
    eq("mention is not a link", ensure_closes("Related to #14", 14)[1], True)
    eq("other issue is not this one", ensure_closes("Closes #140", 14)[1], True)
    eq("no body", ensure_closes("", 7)[0], "Closes #7\n")

    body = default_pr_body(
        {"number": 14, "url": "https://github.com/me/alpha/issues/14"}, "plans/F23-x.md"
    )
    eq("default body closes", body.splitlines()[0], "Closes #14")
    eq("default body plan", "plans/F23-x.md" in body, True)
    eq("default body card", "issues/14" in body, True)

    # worktree porcelain parsing, including a detached one
    import unittest.mock as _mock
    porcelain = (
        "worktree /home/me/repo\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /home/me/.worktrees/repo/task-14-x\nHEAD def\nbranch refs/heads/task/14-x\n\n"
        "worktree /home/me/.worktrees/repo/loose\nHEAD 123\ndetached\n"
    )
    with _mock.patch(__name__ + ".git_out", return_value=porcelain):
        trees = list_worktrees("/home/me/repo")
    eq("worktrees parsed", len(trees), 3)
    eq("worktree branch", trees[1]["branch"], "task/14-x")
    eq("detached branch", trees[2]["branch"], None)

    if failures:
        print("FAIL\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    print("selftest: all assertions passed")
    return 0


# ------------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(prog="task_gh.py", description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="re-discover the board, ignoring the cache")
    parser.add_argument("--repo", help="owner/repo, to disambiguate a bare issue number")

    # --repo and --refresh are accepted on either side of the subcommand.
    # Parent-only meant `task_gh.py resolve 14 --repo o/r` died with
    # "unrecognized arguments", which reads as a broken tool rather than a
    # misplaced flag. Separate dests: a shared one would let the subparser's
    # default clobber the parent's parsed value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", dest="repo_after", help=argparse.SUPPRESS)
    common.add_argument("--refresh", dest="refresh_after", action="store_true",
                        help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name):
        return sub.add_parser(name, parents=[common])

    add("doctor").set_defaults(fn=cmd_doctor)
    add("selftest").set_defaults(fn=cmd_selftest)

    p = add("list")
    p.add_argument("--status")
    p.set_defaults(fn=cmd_list)

    p = add("resolve")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_resolve)

    p = add("create")
    p.add_argument("title", nargs="?", help="the card's title")
    p.add_argument("--body", help="body text")
    p.add_argument("--body-file", dest="body_file", help="path, or - for stdin")
    p.add_argument("--stage", help="Open (default) or In Progress; Completed is refused")
    p.add_argument("--label", action="append", help="repeatable; the label must already exist")
    p.add_argument("--draft", action="store_true",
                   help="a board draft item with no repo yet (promote it later)")
    p.add_argument("--issue", type=int,
                   help="adopt an existing issue onto the board instead of creating one")
    p.set_defaults(fn=cmd_create)

    p = add("promote")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_promote)

    p = add("status")
    p.add_argument("ref")
    p.add_argument("name")
    p.set_defaults(fn=cmd_status)

    p = add("comment")
    p.add_argument("ref")
    p.add_argument("text")
    p.set_defaults(fn=cmd_comment)

    p = add("plan")
    p.add_argument("ref")
    p.add_argument("label")
    p.add_argument("path")
    p.add_argument("--date", help="YYYY-MM-DD, recorded beside the path")
    p.set_defaults(fn=cmd_plan)

    p = add("worktree")
    p.add_argument("ref")
    p.add_argument("--dir", help="the repo to branch in (default: cwd)")
    p.add_argument("--base", help="ref to branch from (default: origin/main)")
    p.add_argument("--branch", help="override the generated branch name")
    p.add_argument("--round", type=int, default=1, help="round N appends -rN to the branch")
    p.add_argument("--no-fetch", action="store_true", help="skip git fetch origin")
    p.add_argument("--remove", action="store_true", help="remove this card's worktree")
    p.add_argument("--force", action="store_true", help="with --remove, discard dirty state")
    p.set_defaults(fn=cmd_worktree)

    p = add("pr")
    p.add_argument("ref")
    p.add_argument("--dir", help="the worktree to open the PR from (default: cwd)")
    p.add_argument("--head", help="branch to open the PR from (default: current)")
    p.add_argument("--base", help="branch to merge into (default: the repo's default)")
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--body-file", dest="body_file", help="path, or - for stdin")
    p.add_argument("--plan", help="plan path, quoted into the default body")
    p.add_argument("--draft", action="store_true")
    p.add_argument("--no-push", dest="no_push", action="store_true")
    p.set_defaults(fn=cmd_pr)

    p = add("links")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_links)

    p = add("reopen")
    p.add_argument("ref")
    p.set_defaults(fn=cmd_reopen)

    p = add("finish")
    p.add_argument("ref")
    p.add_argument("--note", help="comment to post (default: names the merged PR)")
    p.add_argument("--allow-unmerged", dest="allow_unmerged", action="store_true",
                   help="complete a card that has no merged pull request")
    p.set_defaults(fn=cmd_finish)

    args = parser.parse_args(argv)
    args.repo = getattr(args, "repo_after", None) or args.repo
    args.refresh = getattr(args, "refresh_after", False) or args.refresh
    try:
        return args.fn(args)
    except TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
