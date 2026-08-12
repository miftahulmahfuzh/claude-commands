#!/usr/bin/env python3
"""Plumbing for the /task skill against GitLab Issues. Stdlib only, no pip.

The GitHub counterpart is `task_gh.py` and the two present the same subcommands
and the same JSON, so `SKILL.md` describes one loop. Shared logic — the plan
block, the stages, reference parsing — lives in `taskcore.py`.

Talks REST with `urllib` and a personal access token, so nothing has to be
installed and a self-hosted instance needs no special handling.

  doctor                       token, host, version, tier, labels
  list [--status NAME] [--project PATH]
  resolve REF                  one issue: description, every note in order, stage
  create --project PATH --title T [--body B]
  status REF NAME              set the stage label
  comment REF TEXT             add a note
  plan REF LABEL PATH          add a line to the plan block in the description
  labels --project PATH [--ensure]     inspect or create the three stage labels
  selftest                     offline assertions; no token, no network

REF forms: 7 | ai/chatbot/agentic#7 | https://host/ai/chatbot/agentic/-/issues/7

Two facts about this instance shape the design, both measured rather than assumed:

  * **It is Community Edition** (16.0.4, `enterprise: false`). Scoped labels are
    an EE feature, so `status::in-progress` does NOT automatically remove
    `status::open` — `set_stage` removes the others explicitly, in one API call
    that rewrites the whole label set. Relying on EE behaviour here would leave
    an issue in two stages at once, and the board would show it in two columns.
  * **Group-level issue boards are EE too.** The cross-project view is the group
    issue list filtered by label, which CE does have. `doctor` prints that URL
    rather than a board URL.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from taskcore import (  # noqa: E402
    STAGES,
    TaskError,
    map_stages,
    missing_stages,
    parse_plan_block,
    parse_ref,
    plan_entry,
    resolve_stage,
    upsert_plan_block,
)

CREDS_PATH = Path(
    os.environ.get("TASK_GITLAB_CREDENTIALS", Path.home() / ".config" / "task-skill" / "gitlab")
)

# The stage labels, and their colours. `::` is deliberate: on CE it is just part
# of the name, but it renders as a scoped label on EE, so the same board keeps
# working if this instance is ever upgraded.
STAGE_LABELS = {
    "Open": ("status::open", "#6699cc"),
    "In Progress": ("status::in-progress", "#e9be3a"),
    "Completed": ("status::completed", "#4e9a51"),
}
STAGE_LABEL_NAMES = [v[0] for v in STAGE_LABELS.values()]


# ------------------------------------------------------------------------ creds


def load_creds():
    if not CREDS_PATH.exists():
        raise TaskError(
            f"No GitLab credentials at {CREDS_PATH}. Create it with 0600 permissions:\n"
            f"  GITLAB_HOST=https://git.example.com\n"
            f"  GITLAB_TOKEN=glpat-…\n"
            f"A personal access token with the `api` scope is enough; it inherits your "
            f"own permissions and needs no admin rights."
        )
    host = os.environ.get("GITLAB_HOST")
    token = os.environ.get("GITLAB_TOKEN")
    for line in CREDS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip("'\"")
        if k.strip() == "GITLAB_HOST" and not host:
            host = v
        elif k.strip() == "GITLAB_TOKEN" and not token:
            token = v
    if not host or not token:
        raise TaskError(f"{CREDS_PATH} must set both GITLAB_HOST and GITLAB_TOKEN.")
    return host.rstrip("/"), token


# -------------------------------------------------------------------------- api


class Api:
    def __init__(self, host, token):
        self.host = host
        self.token = token

    def request(self, method, path, params=None, body=None, want_headers=False) -> Any:
        """Returns parsed JSON, or (json, headers) when want_headers."""
        url = f"{self.host}/api/v4/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = None
        headers = {"PRIVATE-TOKEN": self.token, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                parsed = json.loads(raw) if raw.strip() else None
                return (parsed, dict(resp.headers)) if want_headers else parsed
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:400]
            except Exception:
                pass
            if exc.code == 401:
                raise TaskError(
                    f"GitLab rejected the token (401). It may have expired — check "
                    f"{self.host}/-/user_settings/personal_access_tokens."
                )
            if exc.code == 403:
                raise TaskError(
                    f"GitLab refused the request (403). The token needs the `api` scope, "
                    f"and your account needs at least Reporter on the project. {detail}"
                )
            if exc.code == 404:
                raise TaskError(
                    f"Not found (404): {method} {path}. Either the project path is wrong "
                    f"or your account cannot see it. {detail}"
                )
            raise TaskError(f"GitLab {exc.code} on {method} {path}: {detail}")
        except urllib.error.URLError as exc:
            raise TaskError(f"Cannot reach {self.host}: {exc.reason}")

    def paged(self, path, params=None, limit=2000):
        """Follow pagination. Notes and issues both need it."""
        out = []
        page = 1
        params = dict(params or {})
        while len(out) < limit:
            params.update({"per_page": 100, "page": page})
            batch = self.request("GET", path, params=params)
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out[:limit]


def enc(project_path):
    return urllib.parse.quote(str(project_path), safe="")


# ------------------------------------------------------------------- resolution


def current_stage(labels):
    """The stage a label set represents, and any extras that shouldn't be there."""
    present = [l for l in labels if l in STAGE_LABEL_NAMES]
    stage = None
    for name, (label, _c) in STAGE_LABELS.items():
        if label in present:
            stage = name
            break
    return stage, present


def project_hint():
    """The project path of the current directory's origin remote, if any."""
    import subprocess

    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for sep in ("://", "@"):
        if sep in url:
            url = url.split(sep, 1)[1]
    if ":" in url and "/" in url:
        url = url.split(":", 1)[1] if url.index(":") < url.index("/") else url
    if "/" in url:
        url = url.split("/", 1)[1] if "." in url.split("/", 1)[0] else url
    return url.removesuffix(".git").strip("/") or None


def resolve_issue(api, ref, project_override=None):
    path, number = parse_ref(ref, project_override or project_hint())
    if not path:
        raise TaskError(
            f"Reference {ref!r} is a bare number and the current directory has no GitLab "
            f"origin remote to resolve it against. Pass group/project#{number} or --project."
        )
    issue = api.request("GET", f"projects/{enc(path)}/issues/{number}")
    return path, issue


def issue_view(api, path, issue, with_notes=True):
    labels = list(issue.get("labels") or [])
    stage, present = current_stage(labels)
    notes = []
    if with_notes:
        raw = api.paged(
            f"projects/{enc(path)}/issues/{issue['iid']}/notes",
            params={"sort": "asc", "order_by": "created_at"},
        )
        notes = [
            {
                "author": (n.get("author") or {}).get("username"),
                "createdAt": n.get("created_at"),
                "system": bool(n.get("system")),
                "body": n.get("body") or "",
            }
            for n in raw
        ]
    body = issue.get("description") or ""
    plans = parse_plan_block(body)
    return {
        "project": path,
        "number": issue.get("iid"),
        "id": issue.get("id"),
        "title": issue.get("title"),
        "body": body,
        "url": issue.get("web_url"),
        "state": issue.get("state"),
        "labels": labels,
        "stage": stage,
        "stageLabelsPresent": present,
        "createdAt": issue.get("created_at"),
        "updatedAt": issue.get("updated_at"),
        # System notes are GitLab's own audit lines ("added label ..."), useful
        # for history but never a bug report -- kept, flagged, never filtered
        # silently, because the human notes are what the loop reads.
        "comments": [n for n in notes if not n["system"]],
        "systemNotes": [n for n in notes if n["system"]],
        "plans": plans,
        "round": len(plans) + 1 if plans else 1,
    }


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

    creds = {}

    def read_creds():
        host, token = load_creds()
        creds["host"], creds["token"] = host, token
        return f"{CREDS_PATH} readable, host {host}"

    if not check("credentials present", read_creds):
        print(json.dumps(report, indent=2))
        return 1

    api = Api(creds["host"], creds["token"])
    state = {}

    def whoami():
        me = api.request("GET", "user")
        state["user"] = me.get("username")
        return f"{me.get('username')} (id {me.get('id')}, admin={me.get('is_admin', False)})"

    if not check("token authenticates", whoami):
        print(json.dumps(report, indent=2))
        return 1

    def tier():
        v = api.request("GET", "version")
        state["enterprise"] = bool(v.get("enterprise"))
        ee = "Enterprise" if state["enterprise"] else "Community"
        return (
            f"GitLab {v.get('version')} {ee} Edition — "
            + ("scoped labels enforce exclusivity" if state["enterprise"]
               else "no scoped labels or group boards; stage exclusivity is enforced here")
        )

    check("instance tier", tier)

    def token_scopes():
        t = api.request("GET", "personal_access_tokens/self")
        scopes = t.get("scopes") or []
        if "api" not in scopes:
            raise TaskError(f"Token scopes are {scopes} with no `api` scope; writes will 403.")
        return f"scopes {scopes}, expires {t.get('expires_at')}"

    check("token scope and expiry", token_scopes)

    target = args.project or project_hint()
    if target:
        def project():
            p = api.request("GET", f"projects/{enc(target)}")
            state["project"] = p.get("path_with_namespace")
            if not p.get("issues_enabled", True):
                raise TaskError(f"Issues are disabled on {target}.")
            lvl = ((p.get("permissions") or {}).get("project_access")
                   or (p.get("permissions") or {}).get("group_access") or {})
            return (f"{p.get('path_with_namespace')} (id {p.get('id')}), issues enabled, "
                    f"access_level {lvl.get('access_level')}")

        if check(f"project {target}", project):
            def labels():
                have = [l["name"] for l in api.paged(f"projects/{enc(target)}/labels")]
                missing = [n for n in STAGE_LABEL_NAMES if n not in have]
                if missing:
                    raise TaskError(
                        f"Missing stage label(s): {', '.join(missing)}. Create them with: "
                        f"task_gl.py labels --project {target} --ensure"
                    )
                return f"all three stage labels present"

            check("stage labels", labels)

            def board():
                boards = api.paged(f"projects/{enc(target)}/boards")
                if not boards:
                    raise TaskError(
                        f"No kanban board yet. Create it with: "
                        f"task_gl.py board --project {target} --ensure"
                    )
                b = next((x for x in boards if x.get("name") == BOARD_NAME), boards[0])
                lists = api.paged(f"projects/{enc(target)}/boards/{b['id']}/lists")
                cols = [(l.get("label") or {}).get("name") for l in
                        sorted(lists, key=lambda x: x.get("position") or 0)]
                missing = [n for n in STAGE_LABEL_NAMES if n not in cols]
                report["boardUrl"] = f"{creds['host']}/{target}/-/boards/{b['id']}"
                if missing:
                    raise TaskError(
                        f"Board {b.get('name')!r} is missing column(s) {', '.join(missing)}. "
                        f"Fix with: task_gl.py board --project {target} --ensure"
                    )
                return f"{b.get('name')!r} (id {b['id']}), columns {cols}"

            check("kanban board", board)
    else:
        report["checks"].append({
            "name": "project", "ok": False,
            "detail": "No --project and no GitLab origin remote in the current directory.",
        })

    group = (state.get("project") or target or "").split("/")[0] or None
    if group:
        # A distinct key: the project board URL is set by the board check above,
        # and one name for both meant whichever ran last won.
        report["groupIssuesUrl"] = (
            f"{creds['host']}/groups/{group}/-/issues"
            f"?label_name[]={urllib.parse.quote(STAGE_LABELS['In Progress'][0])}"
        )
        report["note"] = (
            "Community Edition has no group boards — verified, POST /groups/:id/boards "
            "404s on this instance. boardUrl is one project's kanban; groupIssuesUrl is "
            "the cross-project view, a filtered list rather than a board."
        )
    report["ok"] = all(c["ok"] for c in report["checks"])
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def cmd_labels(args):
    api = Api(*load_creds())
    have = {l["name"]: l for l in api.paged(f"projects/{enc(args.project)}/labels")}
    created = []
    if args.ensure:
        for stage, (name, colour) in STAGE_LABELS.items():
            if name in have:
                continue
            api.request(
                "POST", f"projects/{enc(args.project)}/labels",
                body={"name": name, "color": colour,
                      "description": f"/task stage: {stage}"},
            )
            created.append(name)
    present = [l["name"] for l in api.paged(f"projects/{enc(args.project)}/labels")]
    print(json.dumps(
        {
            "project": args.project,
            "created": created,
            "stageLabels": {s: (n in present) for s, (n, _c) in STAGE_LABELS.items()},
            "allLabels": present,
        },
        indent=2,
    ))
    return 0


BOARD_NAME = os.environ.get("TASK_GITLAB_BOARD", "Tasks")


def cmd_board(args):
    """Inspect, or with --ensure create, the project's kanban board.

    Community Edition allows one board per project and no group boards, so this
    is the only actual kanban view available; the cross-project view is the
    group issue list. The three columns are label lists in stage order, and
    GitLab swaps the labels itself when a card is dragged between them.
    """
    api = Api(*load_creds())
    path = args.project or project_hint()
    if not path:
        raise TaskError("board needs --project, or a GitLab origin remote in this directory.")

    boards = api.paged(f"projects/{enc(path)}/boards")
    board = next((b for b in boards if b.get("name") == BOARD_NAME), None) or (
        boards[0] if boards else None
    )
    created_board = False
    if board is None:
        if not args.ensure:
            print(json.dumps(
                {"project": path, "board": None,
                 "hint": f"No board yet. Create it with: task_gl.py board "
                         f"--project {path} --ensure"},
                indent=2))
            return 0
        board = api.request("POST", f"projects/{enc(path)}/boards",
                            body={"name": BOARD_NAME})
        created_board = True

    labels = {l["name"]: l["id"] for l in api.paged(f"projects/{enc(path)}/labels")}
    missing_labels = [n for n in STAGE_LABEL_NAMES if n not in labels]
    if missing_labels:
        raise TaskError(
            f"Missing stage label(s) {', '.join(missing_labels)}. Run first: "
            f"task_gl.py labels --project {path} --ensure"
        )

    have = {
        (l.get("label") or {}).get("name")
        for l in api.paged(f"projects/{enc(path)}/boards/{board['id']}/lists")
    }
    added = []
    if args.ensure:
        # Created in STAGES order so the columns read left to right the way the
        # loop moves through them.
        for name in STAGE_LABEL_NAMES:
            if name in have:
                continue
            api.request("POST", f"projects/{enc(path)}/boards/{board['id']}/lists",
                        body={"label_id": labels[name]})
            added.append(name)

    lists = api.paged(f"projects/{enc(path)}/boards/{board['id']}/lists")
    columns = [
        (l.get("label") or {}).get("name")
        for l in sorted(lists, key=lambda x: x.get("position") or 0)
    ]
    host = api.host
    print(json.dumps(
        {
            "project": path,
            "boardId": board["id"],
            "boardName": board.get("name"),
            "createdBoard": created_board,
            "addedColumns": added,
            "columns": columns,
            "boardUrl": f"{host}/{path}/-/boards/{board['id']}",
            "projectIssuesUrl": f"{host}/{path}/-/issues",
            "groupIssuesUrl": f"{host}/groups/{path.split('/')[0]}/-/issues",
        },
        indent=2,
    ))
    return 0


def cmd_list(args):
    api = Api(*load_creds())
    params = {"state": "all", "scope": "all"}
    if args.status:
        params["labels"] = resolve_stage(STAGE_LABEL_NAMES, args.status)
    target = args.project or project_hint()
    path = f"projects/{enc(target)}/issues" if target else "issues"
    issues = api.paged(path, params=params, limit=args.limit)
    out = []
    for i in issues:
        stage, present = current_stage(list(i.get("labels") or []))
        plans = parse_plan_block(i.get("description") or "")
        out.append({
            "project": (i.get("references") or {}).get("full", "").split("#")[0] or target,
            "number": i.get("iid"),
            "title": i.get("title"),
            "state": i.get("state"),
            "stage": stage,
            "stageLabelsPresent": present,
            "labels": list(i.get("labels") or []),
            "url": i.get("web_url"),
            "plans": plans,
        })
    print(json.dumps({"scope": target or "all visible", "count": len(out), "items": out}, indent=2))
    return 0


def cmd_resolve(args):
    api = Api(*load_creds())
    path, issue = resolve_issue(api, args.ref, args.project)
    view = issue_view(api, path, issue)
    view["stages"] = map_stages(STAGE_LABEL_NAMES)
    print(json.dumps(view, indent=2))
    return 0


def cmd_create(args):
    api = Api(*load_creds())
    target = args.project or project_hint()
    if not target:
        raise TaskError("create needs --project, or a GitLab origin remote in this directory.")
    body = {"title": args.title, "description": args.body or ""}
    label = resolve_stage(STAGE_LABEL_NAMES, args.status or "Open")
    body["labels"] = label
    issue = api.request("POST", f"projects/{enc(target)}/issues", body=body)
    print(json.dumps(
        {"created": True, "project": target, "number": issue.get("iid"),
         "url": issue.get("web_url"), "stage": args.status or "Open"},
        indent=2,
    ))
    return 0


def cmd_status(args):
    api = Api(*load_creds())
    path, issue = resolve_issue(api, args.ref, args.project)
    want = resolve_stage(STAGE_LABEL_NAMES, args.name)
    labels = list(issue.get("labels") or [])
    stage_now, present = current_stage(labels)

    if present == [want]:
        print(json.dumps({"changed": False, "stage": args.name, "labels": labels}, indent=2))
        return 0

    # Rewrite the whole label set in one PUT. On Community Edition nothing
    # removes the previous status:: label for us, and `add_labels` alone would
    # leave the issue in two stages at once -- visible as two board columns.
    kept = [l for l in labels if l not in STAGE_LABEL_NAMES]
    new_labels = kept + [want]
    updated = api.request(
        "PUT", f"projects/{enc(path)}/issues/{issue['iid']}",
        body={"labels": ",".join(new_labels)},
    )
    after = list(updated.get("labels") or [])
    stage_after, present_after = current_stage(after)
    if present_after != [want]:
        raise TaskError(
            f"Stage label set is {present_after} after the update, expected [{want}]. "
            f"Nothing else changed; re-run or fix the labels by hand."
        )
    print(json.dumps(
        {"changed": True, "from": stage_now, "to": stage_after,
         "removed": [l for l in present if l != want], "labels": after},
        indent=2,
    ))
    return 0


def cmd_comment(args):
    api = Api(*load_creds())
    path, issue = resolve_issue(api, args.ref, args.project)
    note = api.request(
        "POST", f"projects/{enc(path)}/issues/{issue['iid']}/notes",
        body={"body": args.text},
    )
    print(json.dumps({"commented": True, "project": path, "number": issue["iid"],
                      "noteId": note.get("id")}, indent=2))
    return 0


def cmd_plan(args):
    api = Api(*load_creds())
    path, issue = resolve_issue(api, args.ref, args.project)
    entry = plan_entry(args.label, args.path, args.date)
    new_body, entries = upsert_plan_block(issue.get("description") or "", entry)
    if new_body == (issue.get("description") or ""):
        print(json.dumps({"changed": False, "plans": entries}, indent=2))
        return 0
    api.request(
        "PUT", f"projects/{enc(path)}/issues/{issue['iid']}",
        body={"description": new_body},
    )
    print(json.dumps({"changed": True, "plans": entries}, indent=2))
    return 0


def cmd_selftest(args):
    """Offline assertions on the pure logic. No token, no network."""
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    # stage detection from a label set
    eq("no stage", current_stage(["bug"]), (None, []))
    eq("one stage", current_stage(["bug", "status::open"]), ("Open", ["status::open"]))
    eq("in progress", current_stage(["status::in-progress"]),
       ("In Progress", ["status::in-progress"]))
    # two at once is the CE failure mode: reported, never silently picked over
    two = current_stage(["status::open", "status::completed"])
    eq("two stages detected", two[1], ["status::open", "status::completed"])
    eq("two stages resolve in STAGES order", two[0], "Open")

    # the label set a transition writes: non-stage labels kept, others dropped
    labels = ["bug", "status::open", "priority::high"]
    kept = [l for l in labels if l not in STAGE_LABEL_NAMES]
    eq("kept non-stage labels", kept, ["bug", "priority::high"])
    eq("new set", kept + ["status::in-progress"],
       ["bug", "priority::high", "status::in-progress"])

    # stage names map both ways
    eq("resolve ours", resolve_stage(STAGE_LABEL_NAMES, "Completed"), "status::completed")
    eq("resolve label", resolve_stage(STAGE_LABEL_NAMES, "status::open"), "status::open")
    eq("all stages available", missing_stages(STAGE_LABEL_NAMES), [])
    eq("stage keys match STAGES", tuple(STAGE_LABELS), STAGES)
    try:
        resolve_stage(STAGE_LABEL_NAMES, "Blocked")
        failures.append("unknown stage should raise")
    except TaskError:
        pass

    # path encoding for nested groups
    eq("nested encode", enc("ai/chatbot/agentic"), "ai%2Fchatbot%2Fagentic")

    # refs, including the self-hosted URL form
    eq("nested ref", parse_ref("ai/chatbot/agentic#7"), ("ai/chatbot/agentic", 7))
    eq("self-hosted url",
       parse_ref("https://git.tuntun.co.id/ai/chatbot/agentic/-/issues/7"),
       ("ai/chatbot/agentic", 7))

    # a bare number with no project must fail loudly rather than guess
    class NoApi:
        def request(self, *a, **k):
            raise AssertionError("must not call the API without a project")

    try:
        resolve_issue(NoApi(), "7", None) if project_hint() is None else None
    except TaskError:
        pass
    except AssertionError as exc:
        failures.append(str(exc))

    if failures:
        print("FAIL\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    print("selftest: all assertions passed")
    return 0


# ------------------------------------------------------------------------- main


def main(argv=None):
    p = argparse.ArgumentParser(prog="task_gl.py", description=__doc__)
    p.add_argument("--project", help="group/project path; defaults to the origin remote")

    # --project is accepted on either side of the subcommand. Parent-only meant
    # `task_gl.py labels --project X` died with "unrecognized arguments", which
    # reads as a broken tool rather than a misplaced flag. A separate dest is
    # required: sharing one would let the subparser's None clobber the parent's
    # parsed value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", dest="project_after", help=argparse.SUPPRESS)

    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    add("doctor").set_defaults(fn=cmd_doctor)
    add("selftest").set_defaults(fn=cmd_selftest)

    q = add("list")
    q.add_argument("--status")
    q.add_argument("--limit", type=int, default=200)
    q.set_defaults(fn=cmd_list)

    q = add("resolve"); q.add_argument("ref"); q.set_defaults(fn=cmd_resolve)

    q = add("create")
    q.add_argument("--title", required=True)
    q.add_argument("--body")
    q.add_argument("--status", default="Open")
    q.set_defaults(fn=cmd_create)

    q = add("status"); q.add_argument("ref"); q.add_argument("name")
    q.set_defaults(fn=cmd_status)

    q = add("comment"); q.add_argument("ref"); q.add_argument("text")
    q.set_defaults(fn=cmd_comment)

    q = add("plan")
    q.add_argument("ref"); q.add_argument("label"); q.add_argument("path")
    q.add_argument("--date", help="YYYY-MM-DD, recorded beside the path")
    q.set_defaults(fn=cmd_plan)

    q = add("labels")
    q.add_argument("--ensure", action="store_true", help="create any missing stage label")
    q.set_defaults(fn=cmd_labels)

    q = add("board")
    q.add_argument("--ensure", action="store_true",
                   help="create the board and its three stage columns if absent")
    q.set_defaults(fn=cmd_board)

    args = p.parse_args(argv)
    args.project = getattr(args, "project_after", None) or args.project
    if args.cmd == "labels" and not args.project:
        args.project = project_hint()
        if not args.project:
            print("error: labels needs --project", file=sys.stderr)
            return 1
    try:
        return args.fn(args)
    except TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
