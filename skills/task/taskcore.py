#!/usr/bin/env python3
"""Backend-agnostic pieces of the /task skill. Stdlib only, no network.

`task_gh.py` (GitHub Issues + Projects v2) and `task_gl.py` (GitLab Issues)
both drive the same loop, so everything that is not an API call lives here:
the plan-block codec, the three stages and their aliases, and reference
parsing. One implementation means one selftest and no drift between backends.
"""

import re

# The marker-delimited block that carries plan paths in an issue body. It lives
# in the body rather than a comment because comments get buried under bug
# reports, and the body is what the next session reads first.
PLAN_OPEN = "<!-- task:plans -->"
PLAN_CLOSE = "<!-- /task:plans -->"

# The stages the skill reasons about, in order. Each backend maps these onto
# whatever its own board actually calls them -- never assumed.
STAGES = ("Open", "In Progress", "Completed")

STAGE_ALIASES = {
    "Open": ("open", "todo", "to do", "backlog", "not started", "status::open"),
    "In Progress": ("in progress", "in-progress", "doing", "started", "status::in-progress"),
    "Completed": ("completed", "done", "complete", "shipped", "status::completed"),
}


class TaskError(Exception):
    """A failure with a message meant for the user, not a traceback."""


# ------------------------------------------------------------------ plan block


def parse_plan_block(body):
    if not body or PLAN_OPEN not in body:
        return []
    after = body.split(PLAN_OPEN, 1)[1]
    inner = after.split(PLAN_CLOSE, 1)[0]
    return [
        line.strip()[2:].strip()
        for line in inner.splitlines()
        if line.strip().startswith("- ")
    ]


def render_plan_block(entries):
    lines = [PLAN_OPEN, "### Plans"]
    lines += [f"- {e}" for e in entries]
    lines.append(PLAN_CLOSE)
    return "\n".join(lines)


def upsert_plan_block(body, entry):
    """Append one entry, rewriting only between the markers. Idempotent."""
    body = body or ""
    entries = parse_plan_block(body)
    if entry in entries:
        return body, entries  # already recorded: a re-run, not a new plan
    entries.append(entry)
    block = render_plan_block(entries)
    if PLAN_OPEN in body and PLAN_CLOSE in body:
        head, rest = body.split(PLAN_OPEN, 1)
        tail = rest.split(PLAN_CLOSE, 1)[1]
        return head + block + tail, entries
    sep = "" if body.endswith("\n\n") or not body else ("\n" if body.endswith("\n") else "\n\n")
    return body + sep + block + "\n", entries


def plan_entry(label, path, date=None):
    return f"{label} — `{path}` ({date})" if date else f"{label} — `{path}`"


# ----------------------------------------------------------------------- stages


def map_stages(option_names):
    """Map each of STAGES onto a real option name, or None if absent.

    Accepts a backend's shipped defaults (GitHub's Todo/Done, GitLab's
    status:: labels) so the skill works before any renaming, while still
    reporting what it matched so a caller can say so out loud.
    """
    present = {str(n).strip().lower(): n for n in option_names}
    out = {}
    for stage in STAGES:
        found = None
        for alias in STAGE_ALIASES[stage]:
            if alias in present:
                found = present[alias]
                break
        out[stage] = found
    return out


def resolve_stage(option_names, name):
    """Turn a stage name (ours or the backend's) into a real option name."""
    for opt in option_names:
        if str(opt).strip().lower() == str(name).strip().lower():
            return opt
    mapped = map_stages(option_names).get(name)
    if mapped:
        return mapped
    raise TaskError(
        f"Stage {name!r} is not available. Options: {', '.join(sorted(map(str, option_names)))}."
    )


def missing_stages(option_names):
    return [s for s, v in map_stages(option_names).items() if v is None]


# -------------------------------------------------------------- reference forms

# Host-agnostic on purpose: a self-hosted GitLab is reached at a name with
# neither "gitlab" nor "github" in it (git.tuntun.co.id), so matching on the
# host name rejects exactly the instance this has to work against. The `-/`
# segment is GitLab's; GitHub omits it.
_URL_RE = re.compile(
    r"^https?://[^/]+/(?P<path>.+?)/(?:-/)?issues/(?P<num>\d+)(?:[/?#].*)?$"
)
_PATH_RE = re.compile(r"^(?P<path>[^\s#]+/[^\s#]+)#(?P<num>\d+)$")
_NUM_RE = re.compile(r"^#?(?P<num>\d+)$")


def parse_ref(ref, host_hint=None):
    """Parse `14`, `group/proj#14` or an issue URL into (path_or_None, number).

    Deliberately strict: anything else raises rather than being coerced, so a
    typo cannot silently address a different issue. GitLab paths may nest
    (`ai/chatbot/agentic`), which is why the path half is not restricted to a
    single slash.
    """
    ref = (ref or "").strip()
    if not ref:
        raise TaskError("Empty reference.")

    m = _URL_RE.match(ref)
    if m:
        return m.group("path").strip("/"), int(m.group("num"))

    m = _PATH_RE.match(ref)
    if m:
        return m.group("path"), int(m.group("num"))

    m = _NUM_RE.match(ref)
    if m:
        return host_hint, int(m.group("num"))

    raise TaskError(
        f"Unrecognised reference {ref!r}. Use 14, group/project#14, or an issue URL."
    )


# --------------------------------------------------------------------- selftest


def _selftest():
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    # plan block
    b0 = "Some description.\n"
    b1, e1 = upsert_plan_block(b0, plan_entry("F23", "plans/F23-a.md", "2026-08-12"))
    eq("first entry", e1, ["F23 — `plans/F23-a.md` (2026-08-12)"])
    eq("body preserved", b1.startswith("Some description."), True)
    b2, e2 = upsert_plan_block(b1, plan_entry("F23 round 2", "plans/F23-a.md", "2026-08-20"))
    eq("append", len(e2), 2)
    eq("single block", b2.count(PLAN_OPEN), 1)
    b3, e3 = upsert_plan_block(b2, plan_entry("F23 round 2", "plans/F23-a.md", "2026-08-20"))
    eq("idempotent", (b3, e3), (b2, e2))
    b4, _ = upsert_plan_block(b2 + "\nTrailing text.\n", plan_entry("F24", "plans/F24.md"))
    eq("trailing text survives", "Trailing text." in b4, True)
    eq("still one block", b4.count(PLAN_OPEN), 1)
    eq("no date", plan_entry("F9", "p.md"), "F9 — `p.md`")
    eq("parse empty", parse_plan_block(""), [])
    eq("parse no block", parse_plan_block("nothing"), [])

    # stages: GitHub defaults, GitLab labels, ours
    gh = ["Todo", "In Progress", "Done"]
    eq("gh Open", map_stages(gh)["Open"], "Todo")
    eq("gh Completed", map_stages(gh)["Completed"], "Done")
    eq("gh resolve", resolve_stage(gh, "Completed"), "Done")
    gl = ["status::open", "status::in-progress", "status::completed"]
    eq("gl Open", map_stages(gl)["Open"], "status::open")
    eq("gl In Progress", map_stages(gl)["In Progress"], "status::in-progress")
    eq("gl resolve exact", resolve_stage(gl, "status::completed"), "status::completed")
    eq("gl resolve by stage", resolve_stage(gl, "Completed"), "status::completed")
    ours = list(STAGES)
    eq("exact", map_stages(ours)["Open"], "Open")
    eq("missing none", missing_stages(ours), [])
    eq("missing some", missing_stages(["Todo"]), ["In Progress", "Completed"])
    try:
        resolve_stage(ours, "Blocked")
        failures.append("unknown stage should raise")
    except TaskError:
        pass

    # references
    eq("bare", parse_ref("14"), (None, 14))
    eq("bare hash", parse_ref("#14"), (None, 14))
    eq("bare with hint", parse_ref("14", "ai/chatbot/agentic"), ("ai/chatbot/agentic", 14))
    eq("path", parse_ref("me/repo#14"), ("me/repo", 14))
    eq("nested path", parse_ref("ai/chatbot/agentic#7"), ("ai/chatbot/agentic", 7))
    eq("github url", parse_ref("https://github.com/me/repo/issues/14"), ("me/repo", 14))
    eq("gitlab url",
       parse_ref("https://git.tuntun.co.id/ai/chatbot/agentic/-/issues/7"),
       ("ai/chatbot/agentic", 7))
    eq("gitlab url with note anchor",
       parse_ref("https://git.tuntun.co.id/ai/chatbot/agentic/-/issues/7#note_912"),
       ("ai/chatbot/agentic", 7))
    eq("github url with trailing slash",
       parse_ref("https://github.com/me/repo/issues/14/"), ("me/repo", 14))
    # a project literally named "issues" must not confuse the path split
    eq("repo named issues", parse_ref("https://x.dev/me/issues/issues/3"), ("me/issues", 3))
    for bad in ("", "nonsense", "me/repo#", "#", "1.5", "abc#1x", "me/repo#0x1"):
        try:
            parse_ref(bad)
            failures.append(f"{bad!r} should raise")
        except TaskError:
            pass

    if failures:
        return failures
    return []


if __name__ == "__main__":
    import sys
    fails = _selftest()
    if fails:
        print("FAIL\n  " + "\n  ".join(fails), file=sys.stderr)
        sys.exit(1)
    print("taskcore selftest: all assertions passed")
