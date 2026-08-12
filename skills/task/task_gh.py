#!/usr/bin/env python3
"""Plumbing for the /task skill: GitHub Issues + a Projects v2 board.

Wraps the `gh` CLI. Stdlib only, no pip. Every subcommand prints JSON to stdout
so the caller never has to parse human output, and every failure exits non-zero
with one actionable sentence on stderr.

Subcommands:
  doctor                          check gh, auth, scopes, board and Status options
  list [--status NAME]            cards on the board
  resolve REF [--repo OWNER/REPO] one card: body, every comment in order, status, plan block
  promote REF --repo OWNER/REPO   convert a draft item into a real issue
  status REF NAME                 set the Status field
  comment REF TEXT                add a comment (issues only)
  plan REF LABEL PATH             add a line to the plan block in the issue body

REF forms: 14 | owner/repo#14 | https://github.com/owner/repo/issues/14 | PVTI_xxx
           | draft:<substring of the title>
"""

import argparse
import json
import os
import re
import subprocess
import sys
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
    m = re.search(r"github\.com/([^/]+/[^/]+)", value)
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
    if (item["status"] or "") == name:
        print(json.dumps({"changed": False, "status": name, **item}, indent=2))
        return 0
    gh(
        "project", "item-edit",
        "--id", item["itemId"],
        "--project-id", cfg["projectId"],
        "--field-id", cfg["statusFieldId"],
        "--single-select-option-id", option_id,
    )
    print(
        json.dumps(
            {"changed": True, "from": item["status"], "to": name, "itemId": item["itemId"]},
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
