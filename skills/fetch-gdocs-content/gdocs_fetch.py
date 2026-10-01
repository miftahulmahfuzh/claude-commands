#!/usr/bin/env python3
"""Fetch a Google Docs/Sheets/Slides/Drive file as local files you can Read.

Stdlib only. Tries anonymous export first (works for "anyone with the link"),
then falls back to an OAuth bearer token from gcloud for private docs.

Never prints the access token.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (X11; Linux x86_64) gdocs_fetch/1.0"

# kind -> (default format, {format: (extension, drive-api mimeType or None)})
KINDS = {
    "document": ("markdown", {
        "markdown": (".md", "text/markdown"),
        "txt":      (".txt", "text/plain"),
        "html":     (".html", "text/html"),
        "zip":      (".zip", "application/zip"),   # HTML + inline images
        "docx":     (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "pdf":      (".pdf", "application/pdf"),
    }),
    "spreadsheets": ("csv", {
        "csv":      (".csv", "text/csv"),
        "tsv":      (".tsv", "text/tab-separated-values"),
        "xlsx":     (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "pdf":      (".pdf", "application/pdf"),
        "zip":      (".zip", "application/zip"),   # every sheet as CSV
    }),
    "presentation": ("pdf", {
        "pdf":      (".pdf", "application/pdf"),
        "pptx":     (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "txt":      (".txt", "text/plain"),
    }),
    "file": ("bin", {"bin": ("", None)}),  # uploaded binary: download, never export
}

ID_RE = r"[A-Za-z0-9_-]{20,}"


def parse_target(s):
    """Return (kind, file_id, tab, gid). Accepts any Google URL form or a bare id."""
    s = s.strip().strip('"').strip("'")
    if re.fullmatch(ID_RE, s):
        return "document", s, None, None

    u = urlparse(s)
    if "google.com" not in (u.netloc or ""):
        sys.exit(f"not a Google URL and not a bare file id: {s}")
    q = parse_qs(u.query or "")
    tab = (q.get("tab") or [None])[0]
    gid = (q.get("gid") or [None])[0]
    if not gid and u.fragment:
        m = re.search(r"gid=(\d+)", u.fragment)
        if m:
            gid = m.group(1)

    m = re.search(r"/(document|spreadsheets|presentation|file|forms)/d/(?:e/)?(" + ID_RE + ")", u.path)
    if m:
        kind = "file" if m.group(1) in ("file", "forms") else m.group(1)
        return kind, m.group(2), tab, gid
    if "id" in q and re.fullmatch(ID_RE, q["id"][0]):
        return "file", q["id"][0], tab, gid
    m = re.search("(" + ID_RE + ")", u.path)
    if m:
        return "document", m.group(1), tab, gid
    sys.exit(f"could not find a file id in: {s}")


def gcloud_token(account=None):
    """Access token from gcloud, or None. The token is never printed or logged."""
    cmd = ["gcloud", "auth", "print-access-token"]
    if account:
        cmd.append(account)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    tok = p.stdout.strip()
    return tok or None


def token_has_drive(tok):
    try:
        with urlopen("https://oauth2.googleapis.com/tokeninfo?access_token=" + tok, timeout=30) as r:
            scopes = json.load(r).get("scope", "")
    except Exception:
        return False
    return "auth/drive" in scopes


def get(url, token=None, quota_project=None):
    """GET -> (status, content_type, body_bytes, final_url). Never raises on HTTP error."""
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = "Bearer " + token
        if quota_project:
            headers["X-Goog-User-Project"] = quota_project
    try:
        with urlopen(Request(url, headers=headers), timeout=180) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read(), r.geturl()
    except HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read(), url
    except URLError as e:
        return 0, "", str(e.reason).encode(), url


def is_wall(status, ctype, body, want_binary):
    """True when Google handed back a login page / denial instead of the file.

    Detection is content-based on purpose. An inaccessible doc answers 404 with
    text/html; a sign-in redirect answers 200 with an HTML login page. Neither is
    distinguishable by status code alone.
    """
    if status != 200:
        return True
    if want_binary:
        return False
    if "text/html" in ctype.lower():
        head = body[:4000].lower()
        return (b"<html" in head or b"<!doctype html" in head) and (
            b"accounts.google.com" in head or b"sign in" in head or b"signin" in head
            or b"request access" in head or b"errorcode" in head)
    return False


def build_anon_url(kind, fid, fmt, tab, gid):
    if kind == "file":
        return f"https://drive.google.com/uc?export=download&id={fid}"
    url = f"https://docs.google.com/{kind}/d/{fid}/export?format={fmt}"
    if tab:
        url += f"&tab={tab}"
    if gid and kind == "spreadsheets":
        url += f"&gid={gid}"
    return url


def build_api_url(kind, fid, mime):
    if kind == "file" or mime is None:
        return f"https://www.googleapis.com/drive/v3/files/{fid}?alt=media&supportsAllDrives=true"
    from urllib.parse import quote
    return (f"https://www.googleapis.com/drive/v3/files/{fid}/export"
            f"?mimeType={quote(mime)}&supportsAllDrives=true")


def fetch_meta(fid, token, quota_project):
    """Name / modifiedTime / version, so a later re-fetch can be compared. Auth only."""
    if not token:
        return {}
    url = (f"https://www.googleapis.com/drive/v3/files/{fid}"
           "?fields=name,mimeType,modifiedTime,version,lastModifyingUser(displayName)"
           "&supportsAllDrives=true")
    st, _, body, _ = get(url, token, quota_project)
    if st != 200:
        return {}
    try:
        return json.loads(body)
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description="Fetch a Google Doc/Sheet/Slide as local files.")
    ap.add_argument("target", help="Google URL or bare file id")
    ap.add_argument("-o", "--out", help="output directory (default ./gdocs-<id8>)")
    ap.add_argument("-f", "--format", help="export format (doc: markdown|txt|html|zip|docx|pdf)")
    ap.add_argument("--account", help="gcloud account to mint the token with (does not switch your active account)")
    ap.add_argument("--quota-project", default=os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT"),
                    help="sent as X-Goog-User-Project if the Drive API demands one")
    ap.add_argument("--anon-only", action="store_true", help="never attempt authentication")
    ap.add_argument("--auth-only", action="store_true", help="skip the anonymous attempt")
    args = ap.parse_args()

    kind, fid, tab, gid = parse_target(args.target)
    default_fmt, table = KINDS[kind]
    fmt = args.format or default_fmt
    if fmt not in table:
        sys.exit(f"format '{fmt}' not valid for a {kind}; choose from: {', '.join(table)}")
    ext, mime = table[fmt]
    want_binary = ext not in (".md", ".txt", ".html", ".csv", ".tsv")

    out = args.out or f"./gdocs-{fid[:8]}"
    os.makedirs(out, exist_ok=True)

    attempts, body, mode, meta_extra = [], None, None, {}

    if not args.auth_only:
        url = build_anon_url(kind, fid, fmt, tab, gid)
        st, ct, b, final = get(url)
        walled = is_wall(st, ct, b, want_binary)
        attempts.append({"mode": "anonymous", "status": st, "bytes": len(b), "walled": walled})
        if not walled:
            body, mode = b, "anonymous"

    if body is None and not args.anon_only:
        tok = gcloud_token(args.account)
        if not tok:
            attempts.append({"mode": "oauth", "error": "no gcloud credential"})
        elif not token_has_drive(tok):
            attempts.append({"mode": "oauth", "error": "credential has no Drive scope"})
        else:
            # docs.google.com accepts the bearer token directly and needs no GCP
            # quota project; the Drive API is the fallback when it does not.
            for label, url in (("oauth-export", build_anon_url(kind, fid, fmt, tab, gid)),
                               ("oauth-driveapi", build_api_url(kind, fid, mime))):
                st, ct, b, final = get(url, tok, args.quota_project)
                walled = is_wall(st, ct, b, want_binary)
                rec = {"mode": label, "status": st, "bytes": len(b), "walled": walled}
                if walled and st != 200:
                    rec["detail"] = b[:300].decode("utf-8", "replace")
                attempts.append(rec)
                if not walled:
                    body, mode = b, label
                    break
            if body is not None:
                meta_extra = fetch_meta(fid, tok, args.quota_project)

    meta = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_id": fid, "kind": kind, "format": fmt, "tab": tab, "gid": gid,
        "auth_mode": mode, "attempts": attempts,
    }
    if body is None:
        meta["result"] = "FAILED"
        with open(os.path.join(out, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        print(json.dumps(meta, indent=2), flush=True)
        print("\nCould not read this file.", file=sys.stderr)
        print("If it is private, grant this machine read access once:\n"
              "  gcloud auth login --enable-gdrive-access --no-activate <your-google-account>\n"
              "then re-run with --account <your-google-account>.", file=sys.stderr)
        sys.exit(2)

    meta.update(meta_extra)
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    meta["bytes"] = len(body)

    name = "content" + (ext or ".bin")
    path = os.path.join(out, name)
    with open(path, "wb") as f:
        f.write(body)
    written = [path]

    if fmt == "zip" and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith("/") or ".." in n or n.startswith("/"):
                    continue
                sub = os.path.join(out, "images") if "/" in n else out
                os.makedirs(sub, exist_ok=True)
                dest = os.path.join(sub, os.path.basename(n))
                with z.open(n) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                written.append(dest)

    meta["files"] = written
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(json.dumps({k: meta[k] for k in
                      ("fetched_at_utc", "file_id", "kind", "format", "auth_mode",
                       "bytes", "sha256", "files")
                      if k in meta}, indent=2))


if __name__ == "__main__":
    main()
