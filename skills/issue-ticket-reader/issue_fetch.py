#!/usr/bin/env python3
"""Fetch a Jira issue as readable text + attachments (images, video frames), for an agent.

Works against Jira Server/Data Center (/rest/api/2) and Jira Cloud (/rest/api/3, ADF).
Stdlib only (urllib) — no pip. ffmpeg/ffprobe are used only if a video is attached.

Auth (in priority order):
  1. Env: JIRA_PAT                       -> `Authorization: Bearer <PAT>`
  2. Env: JIRA_USER + JIRA_PASS (or JIRA_API_TOKEN) -> HTTP Basic
  3. Credentials file: $JIRA_CREDENTIALS_FILE, else ~/.config/issue-ticket-reader/credentials
  4. Fallback, same-SSO convenience: ~/.config/confluence-reader/credentials
     (CONFLUENCE_PAT / CONFLUENCE_USER / CONFLUENCE_PASS / CONFLUENCE_API_TOKEN).
     Jira and Confluence usually share one directory, so one credential set covers both.
     CONFLUENCE_BASE_URL is NOT reused as the Jira base URL — the hosts differ.
Credentials are never printed.

Usage:
  issue_fetch.py <url-or-issue-key> [-o OUTDIR] [--base-url URL] [--no-attachments]
                                    [--frames N] [--changelog] [--all-fields]

Examples:
  issue_fetch.py https://project.example.com/browse/UATP-2960 -o ./ticket
  issue_fetch.py UATP-2960 --base-url https://project.example.com
  issue_fetch.py https://example.atlassian.net/browse/ABC-12 --frames 12 --changelog
"""
import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

JIRA_KEYS = ("JIRA_BASE_URL", "JIRA_USER", "JIRA_PAT", "JIRA_PASS", "JIRA_API_TOKEN")
CONF_KEYS = ("CONFLUENCE_USER", "CONFLUENCE_PAT", "CONFLUENCE_PASS",
             "CONFLUENCE_API_TOKEN")
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")


# ---------------------------------------------------------------- credentials

def _parse_env_file(path, wanted):
    creds = {}
    if path and os.path.isfile(path):
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in wanted and v:
                creds[k] = v
    return creds


def load_creds():
    """Merge, in priority order: env -> jira creds file -> confluence creds file."""
    creds = {k: os.environ[k] for k in JIRA_KEYS if os.environ.get(k)}

    jira_file = os.environ.get("JIRA_CREDENTIALS_FILE") or os.path.expanduser(
        "~/.config/issue-ticket-reader/credentials")
    for k, v in _parse_env_file(jira_file, JIRA_KEYS).items():
        creds.setdefault(k, v)

    # Same-SSO fallback: reuse the confluence-reader credentials.
    conf_file = os.environ.get("CONFLUENCE_CREDENTIALS_FILE") or os.path.expanduser(
        "~/.config/confluence-reader/credentials")
    conf = {k: os.environ[k] for k in CONF_KEYS if os.environ.get(k)}
    for k, v in _parse_env_file(conf_file, CONF_KEYS).items():
        conf.setdefault(k, v)
    for src, dst in (("CONFLUENCE_PAT", "JIRA_PAT"),
                     ("CONFLUENCE_USER", "JIRA_USER"),
                     ("CONFLUENCE_PASS", "JIRA_PASS"),
                     ("CONFLUENCE_API_TOKEN", "JIRA_API_TOKEN")):
        if conf.get(src):
            creds.setdefault(dst, conf[src])
    return creds


def auth_header(creds):
    if creds.get("JIRA_PAT"):
        return "Bearer " + creds["JIRA_PAT"]
    user = creds.get("JIRA_USER")
    pw = creds.get("JIRA_PASS") or creds.get("JIRA_API_TOKEN")
    if user and pw:
        return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    sys.exit(
        "ERROR: no credentials. Set JIRA_PAT (preferred) or JIRA_USER + JIRA_PASS,\n"
        "       via env, ~/.config/issue-ticket-reader/credentials, or an existing\n"
        "       ~/.config/confluence-reader/credentials (reused automatically)."
    )


def opener(auth):
    def _open(url, want_bytes=False, allow_404=False):
        req = urllib.request.Request(url, headers={
            "Authorization": auth,
            "Accept": "*/*" if want_bytes else "application/json",
            "User-Agent": "issue-ticket-reader/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            if allow_404 and e.code in (404, 400):
                return None
            body = e.read()[:500].decode("utf-8", "replace")
            hint = ""
            if e.code == 401:
                hint = "  (credentials rejected — check PAT/password, or CAPTCHA lockout)"
            elif e.code == 403:
                hint = "  (authenticated but not permitted to view this issue)"
            elif e.code == 404:
                hint = "  (no such issue, or no browse permission on its project)"
            sys.exit(f"ERROR: HTTP {e.code} for {url}{hint}\n{body}")
        return data if want_bytes else json.loads(data)
    return _open


# ---------------------------------------------------------------- URL parsing

def resolve(target, base_flag):
    """Return (base_url, issue_key). Accepts a browse URL or a bare KEY-123."""
    s = target.strip()
    if ISSUE_KEY_RE.match(s.upper()) and "/" not in s:
        if not base_flag:
            sys.exit("ERROR: bare issue key given but no --base-url and no JIRA_BASE_URL.")
        return base_flag.rstrip("/"), s.upper()

    p = urllib.parse.urlparse(s)
    if not p.scheme:
        sys.exit(f"ERROR: not a URL or issue key (expected e.g. ABC-123): {s}")
    base = f"{p.scheme}://{p.netloc}"

    # /browse/KEY-123, /jira/software/projects/X/boards/1?selectedIssue=KEY-123,
    # /projects/X/issues/KEY-123, /rest/api/2/issue/KEY-123
    q = urllib.parse.parse_qs(p.query)
    for param in ("selectedIssue", "issueKey", "issue"):
        if param in q and ISSUE_KEY_RE.match(q[param][0].upper()):
            return base, q[param][0].upper()
    m = re.search(r"/(?:browse|issues|issue)/([A-Za-z][A-Za-z0-9_]+-\d+)", p.path)
    if m:
        return base, m.group(1).upper()
    m = re.search(r"\b([A-Z][A-Z0-9_]+-\d+)\b", urllib.parse.unquote(p.path))
    if m:
        return base, m.group(1)
    sys.exit(f"ERROR: cannot extract an issue key from: {s}")


# ---------------------------------------------------------------- body -> text

def html_to_text(view, id_to_local):
    """Rendered Jira HTML -> readable text, with attachments as [IMG: ...] markers."""
    t = view or ""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p>", "\n\n", t)
    t = re.sub(r"(?i)</li>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "  - ", t)
    t = re.sub(r"(?i)</tr>", "\n", t)
    t = re.sub(r"(?i)</t[dh]>", " | ", t)
    for i in range(1, 7):
        t = re.sub(r"(?i)<h%d[^>]*>" % i, "\n" + "#" * i + " ", t)
        t = re.sub(r"(?i)</h%d>" % i, "\n", t)

    def img_repl(mm):
        src = mm.group(1)
        am = re.search(r"/attachment/(?:thumbnail/)?(\d+)", src)
        if am and am.group(1) in id_to_local:
            return f"\n[IMG: {id_to_local[am.group(1)]}]\n"
        base_name = os.path.basename(urllib.parse.urlparse(src).path)
        for local in id_to_local.values():
            if os.path.basename(local) == base_name:
                return f"\n[IMG: {local}]\n"
        return f"\n[IMG (not downloaded): {src}]\n"

    t = re.sub(r'(?is)<img[^>]*?\bsrc="([^"]+)"[^>]*>', img_repl, t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return t.strip()


def adf_to_text(node, id_to_local, depth=0):
    """Minimal Atlassian Document Format walker (Jira Cloud description/comments)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    t = node.get("type")
    kids = node.get("content") or []
    inner = "".join(adf_to_text(k, id_to_local, depth + 1) for k in kids)
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    if t == "paragraph":
        return inner + "\n\n"
    if t == "heading":
        lvl = (node.get("attrs") or {}).get("level", 1)
        return "\n" + "#" * lvl + " " + inner + "\n"
    if t in ("bulletList", "orderedList"):
        return inner
    if t == "listItem":
        return "  - " + inner.strip() + "\n"
    if t in ("codeBlock", "blockquote", "panel"):
        return "\n" + inner.strip() + "\n\n"
    if t in ("tableRow",):
        return inner + "\n"
    if t in ("tableCell", "tableHeader"):
        return inner.strip() + " | "
    if t in ("mediaSingle", "mediaGroup", "table", "doc"):
        return inner
    if t == "media":
        attrs = node.get("attrs") or {}
        mid = str(attrs.get("id", ""))
        local = id_to_local.get(mid)
        return f"\n[IMG: {local}]\n" if local else f"\n[MEDIA: {attrs.get('id')}]\n"
    if t == "mention":
        return "@" + ((node.get("attrs") or {}).get("text", "") or "")
    if t == "inlineCard":
        return (node.get("attrs") or {}).get("url", "")
    return inner


def body_to_text(rendered, raw, id_to_local):
    """Prefer server-rendered HTML; fall back to ADF (Cloud) or raw wiki markup."""
    if isinstance(rendered, str) and rendered.strip():
        return html_to_text(rendered, id_to_local)
    if isinstance(raw, dict):
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", adf_to_text(raw, id_to_local)).strip()
    if isinstance(raw, str) and raw.strip():
        # Jira wiki markup: turn !image.png|thumbnail! into a marker.
        def wiki_img(mm):
            name = mm.group(1).split("|")[0].strip()
            for local in id_to_local.values():
                if os.path.basename(local) == name:
                    return f"\n[IMG: {local}]\n"
            return f"\n[IMG (not downloaded): {name}]\n"
        return re.sub(r"!([^!\n]+\.(?:png|jpe?g|gif|webp|bmp|svg)[^!\n]*)!",
                      wiki_img, raw, flags=re.I).strip()
    return ""


# ---------------------------------------------------------------- attachments

def size_str(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.0f} GB"


def video_frames(path, out_dir, n_frames):
    """Sample n_frames evenly across a video. Returns (frame_paths, duration_s|None)."""
    if not shutil.which("ffmpeg"):
        return [], None
    dur = None
    if shutil.which("ffprobe"):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=60)
            dur = float(r.stdout.strip())
        except Exception:  # noqa: BLE001
            dur = None
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    if dur and dur > 0:
        for i in range(n_frames):
            ts = dur * (i + 0.5) / n_frames
            fp = out_dir / f"frame_{i:02d}_{ts:07.2f}s.jpg"
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{ts:.3f}",
                   "-i", str(path), "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2",
                   "-q:v", "3", str(fp)]
            try:
                subprocess.run(cmd, capture_output=True, timeout=120, check=False)
            except Exception:  # noqa: BLE001
                continue
            if fp.exists() and fp.stat().st_size > 0:
                frames.append(fp)
    else:  # unknown duration: uniform-ish sampling by frame filter
        fp = out_dir / "frame_%02d.jpg"
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(path),
             "-vf", "fps=1/2,scale='min(1280,iw)':-2", "-frames:v", str(n_frames),
             "-q:v", "3", str(fp)],
            capture_output=True, timeout=300, check=False)
        frames = sorted(out_dir.glob("frame_*.jpg"))
    return frames, dur


# ---------------------------------------------------------------- main

def fmt_user(u):
    if not isinstance(u, dict):
        return "—"
    return u.get("displayName") or u.get("name") or u.get("emailAddress") or "—"


def main():
    ap = argparse.ArgumentParser(
        description="Fetch a Jira issue as text + attachments (images, video frames).")
    ap.add_argument("target", help="Jira issue URL (/browse/KEY-123) or bare KEY-123")
    ap.add_argument("-o", "--out", default="./jira_issue", help="output directory")
    ap.add_argument("--base-url", help="Jira base URL (needed for a bare issue key)")
    ap.add_argument("--no-attachments", action="store_true",
                    help="skip downloading attachments")
    ap.add_argument("--frames", type=int, default=8,
                    help="frames to sample per attached video (default 8, 0 = none)")
    ap.add_argument("--changelog", action="store_true", help="include the status/field history")
    ap.add_argument("--all-fields", action="store_true",
                    help="dump every non-empty custom field with its human name")
    args = ap.parse_args()

    creds = load_creds()
    base_flag = args.base_url or creds.get("JIRA_BASE_URL")
    _open = opener(auth_header(creds))
    base, key = resolve(args.target, base_flag)

    out = Path(args.out)
    att_dir = out / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)

    expand = "renderedFields,names" + (",changelog" if args.changelog else "")
    # /rest/api/2 covers Server/DC and Cloud; api/3 is the Cloud-only fallback. A 404 here
    # means either "no such API version" or "no such issue / no browse permission" — Jira
    # deliberately conflates the last two, so try v3 before giving up.
    data = _open(f"{base}/rest/api/2/issue/{key}?expand={expand}", allow_404=True)
    if data is None:
        data = _open(f"{base}/rest/api/3/issue/{key}?expand={expand}", allow_404=True)
    if data is None:
        sys.exit(f"ERROR: HTTP 404 for issue {key} on {base}\n"
                 "       Either the key does not exist, or your account lacks Browse\n"
                 "       Projects permission on that project (Jira returns 404 for both).")
    f = data.get("fields") or {}
    rf = data.get("renderedFields") or {}
    names = data.get("names") or {}

    (out / "issue.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ---- attachments first: we need id -> local path for the [IMG:] markers
    atts = f.get("attachment") or []
    id_to_local, att_lines, n_dl = {}, [], 0
    used = set()
    for a in atts:
        fname = a.get("filename") or f"attachment-{a.get('id')}"
        safe = re.sub(r"[^\w.\-+ ()]", "_", fname).strip() or f"att-{a.get('id')}"
        if safe in used:
            safe = f"{a.get('id')}_{safe}"
        used.add(safe)
        local_rel = f"attachments/{safe}"
        id_to_local[str(a.get("id"))] = local_rel
        mime = a.get("mimeType") or ""
        meta = (f"{mime or '?'}, {size_str(a.get('size'))}, by "
                f"{fmt_user(a.get('author'))} on {(a.get('created') or '')[:19]}")
        if args.no_attachments:
            att_lines.append(f"  - {fname}  ({meta})  [not downloaded: --no-attachments]")
            continue
        url = a.get("content") or f"{base}/secure/attachment/{a.get('id')}/{fname}"
        blob = _open(url, want_bytes=True, allow_404=True)
        if blob is None:
            att_lines.append(f"  - {fname}  ({meta})  [DOWNLOAD FAILED]")
            continue
        (out / local_rel).write_bytes(blob)
        n_dl += 1
        note = ""
        if mime.startswith("image/"):
            note = "  <- Read this file directly"
        elif mime.startswith("video/") and args.frames > 0:
            stem = re.sub(r"\W+", "_", Path(safe).stem)[:40] or "video"
            frames, dur = video_frames(out / local_rel, out / "frames" / stem, args.frames)
            if frames:
                dtxt = f", duration {dur:.0f}s" if dur else ""
                note = (f"  <- VIDEO{dtxt}: {len(frames)} sampled frames in "
                        f"frames/{stem}/ — Read those (audio is NOT transcribed)")
            else:
                note = "  <- VIDEO: frame extraction unavailable (ffmpeg missing/failed)"
        elif mime.startswith("video/"):
            note = "  <- VIDEO: frames skipped (--frames 0)"
        att_lines.append(f"  - {local_rel}  ({meta}){note}")

    # ---- text body
    L = []
    L.append(f"# {key} · {f.get('summary') or '(no summary)'}")
    L.append("")
    st = (f.get("status") or {}).get("name", "?")
    res = (f.get("resolution") or {}).get("name")
    L.append(f"_{(f.get('issuetype') or {}).get('name','?')} · status \"{st}\""
             + (f" · resolution {res}" if res else "")
             + f" · priority {(f.get('priority') or {}).get('name','—')}"
             + f" · {base}/browse/{key}_")
    L.append(f"_reporter {fmt_user(f.get('reporter'))} · assignee "
             f"{fmt_user(f.get('assignee'))} · created {(f.get('created') or '')[:19]}"
             f" · updated {(f.get('updated') or '')[:19]}_")
    extra = []
    if f.get("parent"):
        p = f["parent"]
        extra.append(f"parent {p.get('key')} ({(p.get('fields') or {}).get('summary','')})")
    for label, vals in (("labels", f.get("labels")),
                        ("components", [c.get("name") for c in f.get("components") or []]),
                        ("fixVersions", [v.get("name") for v in f.get("fixVersions") or []]),
                        ("affectsVersions", [v.get("name") for v in f.get("versions") or []])):
        if vals:
            extra.append(f"{label}: {', '.join(str(v) for v in vals if v)}")
    if f.get("duedate"):
        extra.append(f"due {f['duedate']}")
    if extra:
        L.append("_" + " · ".join(extra) + "_")
    L.append("")

    L.append("## Description")
    L.append("")
    desc = body_to_text(rf.get("description"), f.get("description"), id_to_local)
    L.append(desc or "_(empty)_")
    L.append("")

    for field, heading in (("environment", "Environment"),):
        val = body_to_text(rf.get(field), f.get(field), id_to_local)
        if val:
            L += [f"## {heading}", "", val, ""]

    comments = ((f.get("comment") or {}).get("comments")) or []
    rendered_comments = ((rf.get("comment") or {}).get("comments")) or []
    rc_by_id = {c.get("id"): c for c in rendered_comments}
    L.append(f"## Comments ({len(comments)})")
    L.append("")
    if not comments:
        L.append("_(none)_")
        L.append("")
    for i, c in enumerate(comments, 1):
        rc = rc_by_id.get(c.get("id")) or {}
        L.append(f"### {i}. {fmt_user(c.get('author'))} — {(c.get('created') or '')[:19]}"
                 + (f" (edited {(c.get('updated') or '')[:19]})"
                    if c.get("updated") and c.get("updated") != c.get("created") else ""))
        L.append("")
        L.append(body_to_text(rc.get("body"), c.get("body"), id_to_local) or "_(empty)_")
        L.append("")

    links = f.get("issuelinks") or []
    if links:
        L += ["## Linked issues", ""]
        for l in links:
            ty = l.get("type") or {}
            if l.get("outwardIssue"):
                o, rel = l["outwardIssue"], ty.get("outward", "relates to")
            elif l.get("inwardIssue"):
                o, rel = l["inwardIssue"], ty.get("inward", "relates to")
            else:
                continue
            of = o.get("fields") or {}
            L.append(f"  - {rel} {o.get('key')} [{(of.get('status') or {}).get('name','?')}]"
                     f" — {of.get('summary','')}")
        L.append("")

    subs = f.get("subtasks") or []
    if subs:
        L += ["## Subtasks", ""]
        for s in subs:
            sf = s.get("fields") or {}
            L.append(f"  - {s.get('key')} [{(sf.get('status') or {}).get('name','?')}]"
                     f" — {sf.get('summary','')}")
        L.append("")

    L += [f"## Attachments ({len(atts)})", ""]
    L += att_lines or ["_(none)_"]
    L.append("")

    if args.all_fields:
        L += ["## Other non-empty fields", ""]
        skip = {"summary", "description", "comment", "attachment", "issuelinks", "subtasks",
                "status", "issuetype", "priority", "reporter", "assignee", "created",
                "updated", "labels", "components", "fixVersions", "versions", "parent",
                "resolution", "environment", "duedate", "project", "watches", "worklog"}
        for k2, v in sorted(f.items()):
            if k2 in skip or v in (None, [], {}, ""):
                continue
            label = names.get(k2, k2)
            flat = json.dumps(v, ensure_ascii=False)
            if len(flat) > 400:
                flat = flat[:400] + "…"
            L.append(f"  - {label} ({k2}): {flat}")
        L.append("")

    if args.changelog:
        hist = ((data.get("changelog") or {}).get("histories")) or []
        L += [f"## Changelog ({len(hist)} entries)", ""]
        for h in hist:
            for it in h.get("items") or []:
                L.append(f"  - {(h.get('created') or '')[:19]} {fmt_user(h.get('author'))}: "
                         f"{it.get('field')}: {it.get('fromString')!r} -> "
                         f"{it.get('toString')!r}")
        L.append("")

    text = "\n".join(L)
    (out / "issue.txt").write_text(text)
    if rf.get("description"):
        (out / "description.html").write_text(rf["description"])

    print(f"OK  {key}  {f.get('summary')!r}")
    print(f"    text:        {out/'issue.txt'}  ({len(text)} chars)")
    print(f"    attachments: {n_dl}/{len(atts)} downloaded in {att_dir}")
    fdir = out / "frames"
    if fdir.exists():
        n_fr = len(list(fdir.rglob('*.jpg')))
        print(f"    video frames: {n_fr} jpg under {fdir}")
    print(f"    raw:         issue.json"
          + (", description.html" if rf.get("description") else ""))


if __name__ == "__main__":
    main()
