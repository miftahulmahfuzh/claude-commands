---
name: fetch-gdocs-content
description: Use when you need to READ a Google Docs, Sheets, Slides or Drive file an agent cannot open in a browser — a PRD, spec, API contract, or meeting note behind a docs.google.com/document/d/, /spreadsheets/d/, /presentation/d/ or drive.google.com/file/d/ link, whether shared with "anyone with the link" or private to the user's own Google account. Also use when a pasted copy of a Google Doc arrived with its links, tables, or images missing.
---

# Fetch Google Docs Content

## Overview

You can't click a Google Docs link, and a pasted copy loses links, tables and images. Google exposes an **export** endpoint for every Doc, Sheet and Slide — hit it directly and you get the real content as local files you can `Read`.

**Core principle: export, don't scrape.** `gdocs_fetch.py` (stdlib only, no pip) resolves the file id from any Google URL form, exports it, writes `meta.json` recording *when* you fetched and the content hash, and falls back to the user's Google sign-in when the document isn't public.

## Invocation

```
/fetch-gdocs-content <google-url> <what the user wants to know>
```

The second argument is the point of the call. **Fetching is step one, not the deliverable.** The notes usually reference a repo file (`@docs/foo.md`) or ask a question of the content — answer *that*, against the actual code, after reading what came back. Dumping the document back verbatim is a failed invocation.

## The method

```bash
S=~/.claude/skills/fetch-gdocs-content/gdocs_fetch.py
python3 $S "https://docs.google.com/document/d/<id>/edit?usp=sharing" -o ./gdoc
```

Then `Read ./gdoc/content.md`.

Defaults by type: Docs → `markdown`, Sheets → `csv`, Slides → `pdf`, Drive files → raw download. Put output in a scratch dir, not the user's repo, unless asked.

**Use `markdown`, not `txt`, for Docs.** MEASURED: the `txt` export silently drops every hyperlink — a PRD whose first line linked to the source spec exported as bare text with the URL gone. Markdown keeps links, headings and list depth.

For a doc with screenshots, use `-f zip`: you get the HTML plus every inline image under `images/`, which you can `Read` individually.

## When it's private: one-time Google sign-in

The script tries anonymous export first. If the file isn't link-shared, it needs the user's account. Ask them to run this **themselves** (it opens a browser):

```bash
gcloud auth login --enable-gdrive-access --no-activate <their-google-account>
```

Then re-run with `--account <their-google-account>`.

- `--enable-gdrive-access` is what adds the Drive scope; a plain `gcloud auth login` token cannot read Drive.
- **`--no-activate` matters.** Without it, signing in to read one doc silently switches their active gcloud account, and their next `gcloud`/`gsutil`/`bq` command runs as the wrong identity.
- The script sends the token to `docs.google.com/export` first, which needs no GCP project. Only if that fails does it try the Drive API, which may demand `--quota-project <project>`.
- The token is never printed, logged, or written to `meta.json`.

In Claude Code, suggest the user type `! gcloud auth login --enable-gdrive-access --no-activate <account>` so the browser flow runs in their own terminal.

## Output layout

```
gdoc/
  content.md       # or .csv / .pdf / .zip depending on type and -f
  images/          # only with -f zip
  meta.json        # fetched_at_utc, sha256, auth_mode, every attempt made
```

## Quick reference

| Task | How |
|---|---|
| Public doc | `gdocs_fetch.py <url> -o ./gdoc` |
| Private doc | user runs the `gcloud auth login` above, then `--account <email>` |
| Keep links and headings | default (`-f markdown`); never `-f txt` |
| Doc with screenshots | `-f zip`, then Read `images/*` |
| One sheet of a workbook | paste the URL including `#gid=…` — the gid is honoured |
| Whole workbook | `-f zip` (every sheet as CSV) or `-f xlsx` |
| Confirm nothing changed since last time | compare `sha256` in `meta.json` |
| Don't touch the network twice | `--anon-only` or `--auth-only` to pin one path |

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Analysis contradicts the doc the user is looking at | **The doc changed under you.** MEASURED: a doc grew from 5.3 KB to 8.7 KB mid-conversation and the new half answered the exact question being analysed | Re-fetch before relying on any earlier pull; compare `meta.json` `sha256`. Quote `fetched_at_utc` when reporting |
| Got HTML full of "Sign in" instead of content | Not link-shared | Run the sign-in above. Note an inaccessible doc answers **404 with `text/html`**, not a redirect — status code alone is not the signal, which is why detection is content-based |
| "no gcloud credential" | Never signed in, or the refresh token expired | `gcloud auth login --enable-gdrive-access --no-activate <account>` |
| "credential has no Drive scope" | Signed in without `--enable-gdrive-access` | Re-run the login with that flag; it re-consents |
| Drive API 403 "API has not been used in project 32555940559" | Drive API wants a quota project | `--quota-project <gcp-project>`, or rely on the `docs.google.com` path the script tries first |
| User's next `gcloud` command runs as the wrong account | `gcloud auth login` without `--no-activate` | `gcloud config set account <their-original>` |
| Links missing from the text | `-f txt` | Use the markdown default |

## Security

Shared docs routinely carry live credentials — API keys, access tokens, user ids pasted into example `curl` commands. **Tell the user when you see one**, name what kind it is, and recommend restricting the doc and rotating the value. Don't echo a secret into the transcript beyond what's needed to identify it, and never reuse one to call a third-party API without explicit permission.

## Notes

- Stdlib only (`urllib`, `zipfile`) — no `pip install`. Needs `gcloud` only for the private path.
- Accepts any URL form (`/edit`, `/view`, `?usp=sharing`, `/d/e/` published links, `?id=`) or a bare file id.
- A doc with Google's multi-tab feature: pass the URL including `?tab=t.…` to export one tab.
- To read a Confluence page instead, use the **confluence-reader** skill.
