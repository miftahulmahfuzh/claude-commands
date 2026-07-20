#!/usr/bin/env python3
"""Fetch a Confluence page as readable text + inline images, for an agent to read.

Works against Confluence Server/Data Center and Cloud. Stdlib only (urllib) — no pip.

Auth (in priority order):
  1. Env: CONFLUENCE_PAT              -> sent as `Authorization: Bearer <PAT>` (preferred)
  2. Env: CONFLUENCE_USER + CONFLUENCE_PASS (or _API_TOKEN) -> HTTP Basic
  3. Credentials file (shell-style KEY=VALUE lines), from:
       $CONFLUENCE_CREDENTIALS_FILE, else ~/.config/confluence-reader/credentials
     Recognized keys: CONFLUENCE_BASE_URL, CONFLUENCE_USER, CONFLUENCE_PAT,
                      CONFLUENCE_PASS, CONFLUENCE_API_TOKEN
Credentials are never printed. Prefer a PAT over a password.

Usage:
  confluence_fetch.py <url-or-pageId> [-o OUTDIR] [--base-url URL] [--no-images]

Examples:
  confluence_fetch.py https://wiki.example.com/display/TPS/Some+Page
  confluence_fetch.py 110615147 --base-url https://wiki.example.com -o ./prd
  confluence_fetch.py https://wiki.example.com/pages/viewpage.action?pageId=110615147
"""
import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CRED_KEYS = (
    "CONFLUENCE_BASE_URL", "CONFLUENCE_USER", "CONFLUENCE_PAT",
    "CONFLUENCE_PASS", "CONFLUENCE_API_TOKEN",
)


def load_creds_file():
    path = os.environ.get("CONFLUENCE_CREDENTIALS_FILE") or os.path.expanduser(
        "~/.config/confluence-reader/credentials"
    )
    creds = {}
    if os.path.isfile(path):
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in CRED_KEYS:
                creds[k] = v
    return creds


def get(name, file_creds):
    return os.environ.get(name) or file_creds.get(name)


def auth_header(file_creds):
    pat = get("CONFLUENCE_PAT", file_creds)
    if pat:
        return "Bearer " + pat
    user = get("CONFLUENCE_USER", file_creds)
    pw = get("CONFLUENCE_PASS", file_creds) or get("CONFLUENCE_API_TOKEN", file_creds)
    if user and pw:
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return "Basic " + token
    sys.exit(
        "ERROR: no credentials. Set CONFLUENCE_PAT (preferred) or "
        "CONFLUENCE_USER + CONFLUENCE_PASS, via env or a credentials file.\n"
        "See the skill README for the credentials-file format."
    )


def opener(auth):
    def _open(url, want_bytes=False, follow=True):
        req = urllib.request.Request(url, headers={
            "Authorization": auth,
            "Accept": "application/json" if not want_bytes else "*/*",
            "User-Agent": "confluence-reader/1.0",
        })
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
            final = r.geturl()
        return (data, final) if want_bytes else (json.loads(data), final)
    return _open


def resolve(url_or_id, base_url_flag, _open):
    """Return (base_url, page_id)."""
    s = url_or_id.strip()
    if s.isdigit():
        if not base_url_flag:
            sys.exit("ERROR: numeric pageId given but no --base-url and no "
                     "CONFLUENCE_BASE_URL in env/credentials.")
        return base_url_flag.rstrip("/"), s

    p = urllib.parse.urlparse(s)
    if not p.scheme:
        sys.exit(f"ERROR: not a URL or numeric id: {s}")
    base = f"{p.scheme}://{p.netloc}"
    q = urllib.parse.parse_qs(p.query)

    # viewpage.action?pageId=NNN
    if "pageId" in q:
        return base, q["pageId"][0]

    # Cloud: /wiki/spaces/SPACE/pages/NNN/Title
    m = re.search(r"/pages/(\d+)", p.path)
    if m:
        return base, m.group(1)

    # Server tiny link: /x/AbCdEf  -> follow redirect to a resolvable URL
    if re.match(r"^/x/[\w-]+/?$", p.path):
        _, final = _open(s, want_bytes=True)
        fq = urllib.parse.parse_qs(urllib.parse.urlparse(final).query)
        if "pageId" in fq:
            return base, fq["pageId"][0]
        m = re.search(r"/pages/(\d+)", urllib.parse.urlparse(final).path)
        if m:
            return base, m.group(1)
        s, p = final, urllib.parse.urlparse(final)  # fall through to /display

    # Server: /display/SPACE/Page+Title  -> resolve via CQL/title search
    m = re.match(r"^/display/([^/]+)/(.+?)/?$", p.path)
    if m:
        space = urllib.parse.unquote(m.group(1))
        title = urllib.parse.unquote_plus(m.group(2))
        api = (base + "/rest/api/content?" + urllib.parse.urlencode(
            {"spaceKey": space, "title": title, "limit": 1}))
        data, _ = _open(api)
        results = data.get("results", [])
        if not results:
            sys.exit(f"ERROR: no page found for space={space!r} title={title!r}")
        return base, results[0]["id"]

    sys.exit(f"ERROR: cannot extract a pageId from: {s}")


def html_to_text(view):
    t = view
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p>", "\n\n", t)
    t = re.sub(r"(?i)</li>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "  - ", t)
    t = re.sub(r"(?i)</tr>", "\n", t)
    t = re.sub(r"(?i)</t[dh]>", " | ", t)
    for i in range(1, 7):
        t = re.sub(r"(?i)<h%d[^>]*>" % i, "\n" + "#" * i + " ", t)
        t = re.sub(r"(?i)</h%d>" % i, "\n", t)
    # Inline images -> [IMG: images/<filename>] so the agent can Read them locally.
    def img_repl(mm):
        src = mm.group(1)
        fname = os.path.basename(urllib.parse.urlparse(src).path)
        return f"\n[IMG: images/{fname}]\n"
    t = re.sub(r'(?is)<img[^>]*?\bsrc="([^"]+)"[^>]*>', img_repl, t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return t.strip()


def main():
    ap = argparse.ArgumentParser(description="Fetch a Confluence page as text + images.")
    ap.add_argument("target", help="Confluence page URL or numeric pageId")
    ap.add_argument("-o", "--out", default="./confluence_page", help="output directory")
    ap.add_argument("--base-url", help="base URL (needed if TARGET is a bare pageId)")
    ap.add_argument("--no-images", action="store_true", help="skip downloading attachments")
    args = ap.parse_args()

    file_creds = load_creds_file()
    base_flag = args.base_url or get("CONFLUENCE_BASE_URL", file_creds)
    auth = auth_header(file_creds)
    _open = opener(auth)

    base, pid = resolve(args.target, base_flag, _open)
    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    content, _ = _open(
        f"{base}/rest/api/content/{pid}?expand=body.view,body.storage,version,space")
    title = content.get("title", f"page-{pid}")
    view = content["body"]["view"]["value"]
    storage = content["body"]["storage"]["value"]
    ver = content.get("version", {}).get("number", "?")

    (out / "page.view.html").write_text(view)
    (out / "page.storage.html").write_text(storage)
    text = f"# {title}\n\n_pageId {pid} · v{ver} · {base}/pages/viewpage.action?pageId={pid}_\n\n"
    text += html_to_text(view)
    (out / "page.txt").write_text(text)

    # Attachments
    n_att = 0
    if not args.no_images:
        att, _ = _open(
            f"{base}/rest/api/content/{pid}/child/attachment?limit=500&expand=version")
        for r in att.get("results", []):
            fname = r["title"]
            dl = r["_links"]["download"]
            url = dl if dl.startswith("http") else base + dl
            try:
                data, _ = _open(url, want_bytes=True)
                (out / "images" / fname).write_bytes(data)
                n_att += 1
            except Exception as e:  # noqa: BLE001 - keep going on a bad attachment
                print(f"  ! failed {fname}: {e}", file=sys.stderr)

    print(f"OK  title={title!r}  pageId={pid}  v{ver}")
    print(f"    text:   {out/'page.txt'}  ({len(text)} chars)")
    print(f"    images: {n_att} file(s) in {out/'images'}")
    print(f"    raw:    page.view.html, page.storage.html")


if __name__ == "__main__":
    main()
