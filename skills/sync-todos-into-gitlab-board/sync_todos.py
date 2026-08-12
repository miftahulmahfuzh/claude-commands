#!/usr/bin/env python3
"""Push the tasks in one `.workflows/todos.md` onto a GitLab issue board.

Stdlib only. Reuses the /task skill's modules rather than re-parsing anything:
`todos.py` for the corpus and `task_gl.py` for the API and the stage labels.

  plan   FILE            what would happen; writes nothing (the default)
  apply  FILE            create and update issues
  repair FILE            report non-canonical ids, split by whether `rename` can fix them
  selftest               offline assertions

Three properties this has to hold, each of which is a way it could go wrong
quietly:

  * **Echoes are not tasks.** A todos.md carries a rolling summary and an
    append-only activity log in which the same id appears repeatedly. Only
    entries under `## Active Tasks` become issues; the root file has 27 live
    entries and 28 echoes, so ignoring this roughly doubles the issue count with
    duplicates.
  * **Re-running must not duplicate.** The TaskID is the identity, carried in the
    issue title and matched on the way back in. A second run updates or skips.
  * **It is close to irreversible.** Deleting a GitLab issue needs Owner; a
    Maintainer can only close. So `plan` is the default and `apply` is explicit.
"""

import argparse
import json
import re
import sys
from pathlib import Path

TASK_SKILL = Path.home() / ".claude" / "skills" / "task"
sys.path.insert(0, str(TASK_SKILL))

from taskcore import TaskError, plan_entry, upsert_plan_block  # noqa: E402
from task_gl import (  # noqa: E402
    STAGE_LABELS,
    STAGE_LABEL_NAMES,
    Api,
    current_stage,
    enc,
    load_creds,
    project_hint,
)
from todos import ID_RE, TodoFile, Corpus  # noqa: E402

SOURCE_OPEN = "<!-- task:source -->"
SOURCE_CLOSE = "<!-- /task:source -->"
TITLE_ID_RE = re.compile(r"^\s*(P[0-4]-[A-Z]{1,4}-[A-Z0-9]+)\b")

# Entry fields worth carrying onto the card, in the order a reader wants them.
# `Plan` is handled separately -- it goes in the plan block, not the prose.
#
# `Completed` and `Method` are here because the pilot run showed a finished card
# with neither: they are the two fields that say what actually happened, and a
# Completed-column card without them is just a title. `Files Modified` is left
# out on purpose -- its value in todos.md is empty, the file list being nested
# sub-bullets the field parser does not own.
CARRIED = ("Difficulty", "Type", "Context", "Current Problem", "Impact",
           "Solution", "Location", "Method", "Completed", "Identified", "Former ID")


def issue_title(entry):
    return f"{entry.task_id} — {entry.title}".strip()


def issue_body(entry, todos_rel):
    lines = []
    for name in CARRIED:
        value = entry.fields.get(name)
        if value:
            lines.append(f"- **{name}**: {value}")
    if lines:
        lines.append("")
    lines += [
        SOURCE_OPEN,
        f"- TaskID: `{entry.task_id}`",
        f"- Source: `{todos_rel}`",
        f"- Section: `{entry.section}`",
        SOURCE_CLOSE,
        "",
        "_Card synced from todos.md. `todos.md` stays the source of truth for "
        "execution; run `/do " + entry.task_id + "` to work it._",
    ]
    body = "\n".join(lines)
    plan = (entry.fields.get("Plan") or "").strip().strip("`")
    if plan:
        body, _ = upsert_plan_block(body, plan_entry(entry.task_id, plan))
    return body


# Status values that mean work has started. Measured from the corpus: the live
# entries carry `active` (65), `completed` (20), `in_progress` (3), `pending` (1)
# and nothing at all (28). Only the in-progress family maps to a third column.
IN_PROGRESS_STATUS = ("in_progress", "in progress", "in-progress", "wip",
                      "started", "doing", "partial")


def stage_for(entry):
    """The board column an entry belongs in, and why.

    The checkbox is the primary signal and wins outright for done-ness: it is
    what the corpus is consistent about, while `Status:` is absent on 28 live
    entries. But `Status: in_progress` on an unticked entry is real information
    that the checkbox alone cannot carry -- three tasks have it -- and dropping
    it would file started work under Open.
    """
    status = (entry.fields.get("Status") or "").strip().lower()
    if entry.done:
        # A ticked box with a contradicting status is reported, not silently
        # resolved, so the disagreement is visible on the card.
        disagree = bool(status) and status not in ("completed", "complete", "done")
        return "Completed", ("checkbox" if not disagree
                             else f"checkbox (Status says {status!r})")
    if any(k in status for k in IN_PROGRESS_STATUS):
        return "In Progress", f"Status: {status}"
    return "Open", (f"Status: {status}" if status else "checkbox, no Status field")


def load_entries(path, include_completed):
    f = TodoFile(path, Path(path).resolve().parents[1])
    live = [e for e in f.entries if e.authoritative]
    echoes = len(f.entries) - len(live)
    chosen = live if include_completed else [e for e in live if not e.done]
    return f, live, echoes, chosen


def existing_by_taskid(api, project):
    """Index the project's issues by the TaskID in their title."""
    out = {}
    for i in api.paged(f"projects/{enc(project)}/issues", params={"state": "all"}):
        m = TITLE_ID_RE.match(i.get("title") or "")
        if m:
            out.setdefault(m.group(1), i)
    return out


def diff_entry(entry, issue, todos_rel, refresh_bodies=False):
    """What would change on an existing issue. Empty dict means nothing."""
    changes = {}
    want_title = issue_title(entry)
    if (issue.get("title") or "").strip() != want_title:
        changes["title"] = want_title
    want_stage, why = stage_for(entry)
    want_label = STAGE_LABELS[want_stage][0]
    have_stage, present = current_stage(list(issue.get("labels") or []))
    if present != [want_label]:
        changes["stage"] = {"from": have_stage, "to": want_stage, "because": why}
    # The body is only rewritten when the source block is absent or stale --
    # never on every run, because a human may have added notes to the card and
    # clobbering those would make the sync hostile to use.
    #
    # `refresh_bodies` is the deliberate exception: without it, improving what a
    # card carries could never reach the cards already created, so the format
    # would be frozen by its first run. It DOES discard notes added on the card,
    # which is why it is opt-in and never the default.
    body = issue.get("description") or ""
    if SOURCE_OPEN not in body or f"`{entry.task_id}`" not in body:
        changes["body"] = "add source block"
    elif refresh_bodies and body.strip() != issue_body(entry, todos_rel).strip():
        changes["body"] = "refresh from todos.md (--refresh-bodies)"
    return changes


def run(path, project, apply=False, include_completed=False, limit=None,
        refresh_bodies=False):
    api = Api(*load_creds())
    f, live, echoes, chosen = load_entries(path, include_completed)
    todos_rel = f.rel

    labels_present = {l["name"] for l in api.paged(f"projects/{enc(project)}/labels")}
    missing = [n for n in STAGE_LABEL_NAMES if n not in labels_present]
    if missing:
        raise TaskError(
            f"Project {project} is missing stage label(s) {', '.join(missing)}. Run: "
            f"python3 {TASK_SKILL}/task_gl.py labels --project {project} --ensure"
        )

    existing = existing_by_taskid(api, project)
    if limit:
        chosen = chosen[:limit]

    result = {
        "apply": bool(apply),
        "source": todos_rel,
        "project": project,
        "packageCode": f.pkg_code,
        "liveEntries": len(live),
        "echoesIgnored": echoes,
        "selected": len(chosen),
        "includeCompleted": bool(include_completed),
        "refreshBodies": bool(refresh_bodies),
        "toCreate": [],
        "toUpdate": [],
        "unchanged": [],
        "nonCanonical": [e.task_id for e in chosen if not e.canonical],
        "stageCounts": {},
    }
    for entry in chosen:
        st, _why = stage_for(entry)
        result["stageCounts"][st] = result["stageCounts"].get(st, 0) + 1

    for entry in chosen:
        issue = existing.get(entry.task_id)
        if issue is None:
            stage, why = stage_for(entry)
            record = {
                "taskId": entry.task_id,
                "title": issue_title(entry),
                "stage": stage,
                "stageFrom": why,
            }
            if apply:
                created = api.request(
                    "POST", f"projects/{enc(project)}/issues",
                    body={
                        "title": issue_title(entry),
                        "description": issue_body(entry, todos_rel),
                        "labels": STAGE_LABELS[stage][0],
                    },
                )
                record["number"] = created.get("iid")
                record["url"] = created.get("web_url")
            result["toCreate"].append(record)
            continue

        changes = diff_entry(entry, issue, todos_rel, refresh_bodies=refresh_bodies)
        if not changes:
            result["unchanged"].append(entry.task_id)
            continue
        record = {"taskId": entry.task_id, "number": issue.get("iid"), "changes": changes}
        if apply:
            body_payload = {}
            if "title" in changes:
                body_payload["title"] = changes["title"]
            if "body" in changes:
                body_payload["description"] = issue_body(entry, todos_rel)
            if "stage" in changes:
                kept = [l for l in (issue.get("labels") or []) if l not in STAGE_LABEL_NAMES]
                body_payload["labels"] = ",".join(
                    kept + [STAGE_LABELS[changes["stage"]["to"]][0]]
                )
            updated = api.request(
                "PUT", f"projects/{enc(project)}/issues/{issue['iid']}", body=body_payload
            )
            record["url"] = updated.get("web_url")
        result["toUpdate"].append(record)

    return result


def repair_report(path):
    """Non-canonical ids, split by whether `todos.py rename` can reach them.

    `rename` rewrites ids that have an entry. An id that appears only as a bare
    `- **ID**: text` reference in a log section has no entry to rename and no
    single right answer -- that is the judgement case, and the one worth handing
    to a subagent.
    """
    root = Path(path).resolve().parents[1]
    corpus = Corpus(root)
    mechanical, judgement = [], []
    entry_ids = {e.task_id for e in corpus.entries}
    for e in corpus.outliers:
        mechanical.append({
            "taskId": e.task_id, "file": e.file, "line": e.start + 1,
            "authoritative": e.authoritative, "done": e.done,
        })
    for f in corpus.files:
        for ref in f.refs:
            m = ID_RE.match(ref["taskId"])
            from todos import CANON_SUFFIX_RE
            if m and CANON_SUFFIX_RE.match(m.group(3)):
                continue
            if ref["taskId"] in entry_ids:
                continue
            judgement.append({
                "taskId": ref["taskId"], "file": f.rel, "line": ref["line"],
                "section": ref["section"], "text": ref["text"],
            })
    return {
        "root": str(root),
        "mechanical": mechanical,
        "judgement": judgement,
        "mechanicalFix": "python3 %s/todos.py rename --apply" % TASK_SKILL,
    }


def cmd_selftest(_args):
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    class E:
        def __init__(self, tid, title, done=False, fields=None, section="Active Tasks"):
            self.task_id, self.title, self.done = tid, title, done
            self.fields = fields or {}
            self.section = section
            self.canonical = True

    e = E("P1-MN-A001", "Do the thing", fields={
        "Difficulty": "NORMAL", "Context": "why", "Plan": "`.workflows/plan/P1-MN-A001.md`"})
    eq("title carries the id", issue_title(e), "P1-MN-A001 — Do the thing")
    body = issue_body(e, ".workflows/todos.md")
    eq("fields carried", "- **Difficulty**: NORMAL" in body, True)
    eq("source block", SOURCE_OPEN in body and SOURCE_CLOSE in body, True)
    eq("taskid in source block", "`P1-MN-A001`" in body, True)
    eq("plan path in plan block", ".workflows/plan/P1-MN-A001.md" in body, True)
    eq("backticks stripped from plan", "``" in body, False)
    eq("do handoff named", "/do P1-MN-A001" in body, True)
    # The three-column mapping. `Status: in_progress` on an unticked entry is the
    # case that has no checkbox representation, and three real tasks carry it.
    eq("unticked + Status active -> Open",
       stage_for(E("A", "t", fields={"Status": "active"}))[0], "Open")
    eq("unticked + no Status -> Open", stage_for(E("A", "t"))[0], "Open")
    eq("unticked + Status pending -> Open",
       stage_for(E("A", "t", fields={"Status": "pending"}))[0], "Open")
    eq("unticked + in_progress -> In Progress",
       stage_for(E("A", "t", fields={"Status": "in_progress"}))[0], "In Progress")
    eq("in progress with a space", stage_for(E("A", "t", fields={"Status": "In Progress"}))[0],
       "In Progress")
    eq("ticked -> Completed", stage_for(E("X", "y", done=True))[0], "Completed")
    eq("ticked + Status completed -> Completed",
       stage_for(E("X", "y", done=True, fields={"Status": "completed"}))[0], "Completed")
    # a ticked box beats a contradicting status, but the disagreement is reported
    ticked_active = stage_for(E("X", "y", done=True, fields={"Status": "active"}))
    eq("ticked beats contradicting status", ticked_active[0], "Completed")
    eq("disagreement surfaced", "Status says" in ticked_active[1], True)
    eq("every stage maps to a real label",
       all(s in STAGE_LABELS for s in ("Open", "In Progress", "Completed")), True)

    # a field the entry does not have must not appear as an empty bullet
    eq("absent field omitted", "- **Impact**" in issue_body(E("P1-MN-A002", "t"), "f"), False)

    # title matching is what makes a re-run idempotent
    def title_id(s):
        m = TITLE_ID_RE.match(s)
        return m.group(1) if m else None

    eq("title parse", title_id("P1-MN-A001 — Do the thing"), "P1-MN-A001")
    eq("title parse no id", title_id("Just a normal issue"), None)
    eq("title parse leading space", title_id("  P2-TC-A062 x"), "P2-TC-A062")
    eq("title parse non-canonical still found", title_id("P1-MN-AUTH001 — x"), "P1-MN-AUTH001")

    # diff: nothing to do when title, stage and source block already agree
    REL = ".workflows/todos.md"
    issue = {"title": "P1-MN-A001 — Do the thing", "labels": ["status::open"],
             "description": issue_body(e, REL)}
    eq("no diff when in sync", diff_entry(e, issue, REL), {})
    eq("stage drift detected",
       "stage" in diff_entry(e, {**issue, "labels": ["status::completed"]}, REL), True)
    eq("title drift detected",
       "title" in diff_entry(e, {**issue, "title": "old title"}, REL), True)
    eq("two stage labels is drift",
       "stage" in diff_entry(e, {**issue, "labels": ["status::open", "status::completed"]}, REL),
       True)
    # a human's added notes must survive: body is only touched if the marker is gone
    noted = {**issue, "description": issue["description"] + "\n\nMy own notes.\n"}
    eq("human notes not clobbered", "body" in diff_entry(e, noted, REL), False)
    eq("missing source block is a diff",
       "body" in diff_entry(e, {**issue, "description": "bare"}, REL), True)
    # the source path must take part in the comparison, or --refresh-bodies
    # rewrites every card on every run
    eq("refresh is a no-op against the SAME source path",
       "body" in diff_entry(e, issue, REL, refresh_bodies=True), False)
    eq("a different source path is a real difference",
       "body" in diff_entry(e, issue, "other/todos.md", refresh_bodies=True), True)

    # a finished entry must carry what happened, not just a title
    done = E("P1-MN-L003", "Web search lang", done=True, fields={
        "Difficulty": "NORMAL", "Type": "Feature", "Status": "completed",
        "Completed": "2026-05-21", "Method": "did the thing"})
    db = issue_body(done, REL)
    eq("completed date carried", "- **Completed**: 2026-05-21" in db, True)
    eq("method carried", "- **Method**: did the thing" in db, True)

    # --refresh-bodies: off by default, so a card with notes is left alone even
    # when the body no longer matches todos.md
    stale = {"title": issue_title(done), "labels": ["status::completed"],
             "description": issue_body(done, REL) + "\n\nA human note.\n"}
    eq("stale body untouched by default", "body" in diff_entry(done, stale, REL), False)
    eq("refresh rewrites it",
       "body" in diff_entry(done, stale, REL, refresh_bodies=True), True)
    fresh = {**stale, "description": issue_body(done, REL)}
    eq("refresh is a no-op when already identical",
       "body" in diff_entry(done, fresh, REL, refresh_bodies=True), False)

    if failures:
        print("FAIL\n  " + "\n  ".join(failures), file=sys.stderr)
        return 1
    print("selftest: all assertions passed")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="sync_todos.py", description=__doc__)
    p.add_argument("--project", help="GitLab group/project; defaults to the origin remote")
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", dest="project_after", help=argparse.SUPPRESS)

    for name in ("plan", "apply"):
        q = sub.add_parser(name, parents=[common])
        q.add_argument("file")
        q.add_argument("--include-completed", action="store_true",
                       help="also create cards for finished tasks")
        q.add_argument("--limit", type=int)
        q.add_argument("--refresh-bodies", action="store_true",
                       help="rewrite existing card bodies from todos.md; discards notes "
                            "added on the card")
        q.set_defaults(mode=name)

    q = sub.add_parser("repair", parents=[common])
    q.add_argument("file")
    q.set_defaults(mode="repair")

    sub.add_parser("selftest").set_defaults(mode="selftest")

    args = p.parse_args(argv)
    args.project = getattr(args, "project_after", None) or args.project

    try:
        if args.mode == "selftest":
            return cmd_selftest(args)
        if args.mode == "repair":
            print(json.dumps(repair_report(args.file), indent=2))
            return 0
        project = args.project or project_hint()
        if not project:
            raise TaskError("Needs --project, or a GitLab origin remote in this directory.")
        out = run(args.file, project, apply=(args.mode == "apply"),
                  include_completed=args.include_completed, limit=args.limit,
                  refresh_bodies=args.refresh_bodies)
        print(json.dumps(out, indent=2))
        if not out["apply"]:
            print("\nplan only -- nothing written. Re-run with `apply`.", file=sys.stderr)
        return 0
    except TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
