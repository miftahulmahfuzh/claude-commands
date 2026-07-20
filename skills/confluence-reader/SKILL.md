---
name: confluence-reader
description: Use when you need to READ a Confluence page an agent cannot open in a browser — a PRD, spec, or design doc behind login (URLs like wiki.*, /display/SPACE/Page, /pages/viewpage.action?pageId=, /x/tiny, or /wiki/spaces/). Pulls the body as readable text plus inline images as local files you can Read. Covers Confluence Server/Data Center and Cloud. This is the READ counterpart to confluence-writer.
---

# Confluence Reader

## Overview

You can't click a Confluence link, and print-to-PDF or copy-paste loses images and structure. Confluence has a clean REST API — hit it with the user's credentials to pull the page body as text **and** download every inline image as a local file you can `Read`.

**Core principle: fetch via REST, don't scrape the login-walled HTML.** `confluence_fetch.py` (stdlib only, no pip) resolves the pageId from any URL form, downloads `body.view` + `body.storage`, converts the body to readable text with `[IMG: images/<file>]` markers, and saves each attachment into `images/` so you can open the ones that matter.

## Prerequisite: credentials

The script reads auth in this order (nothing is ever printed):

1. **`CONFLUENCE_PAT`** env — sent as `Authorization: Bearer` (**preferred**; Server/DC ≥7.9 and Cloud both support Personal Access Tokens — Profile → Settings → Personal Access Tokens).
2. **`CONFLUENCE_USER` + `CONFLUENCE_PASS`** env — HTTP Basic (or `CONFLUENCE_API_TOKEN` in place of the password on Cloud).
3. **Credentials file** — `$CONFLUENCE_CREDENTIALS_FILE`, else `~/.config/confluence-reader/credentials`. Shell-style `KEY=VALUE` lines; see `credentials.example`.

`CONFLUENCE_BASE_URL` (env or file) is needed only when you pass a bare numeric pageId instead of a full URL.

**Never ask the user to paste a password into the chat** — it lands in the transcript. Point them at `credentials.example` and have them fill `~/.config/confluence-reader/credentials`, or export a PAT. If a password was already pasted, use it, then tell them to rotate it.

## The method

```bash
# Any of these URL forms work — the script resolves the pageId itself:
python3 confluence_fetch.py "https://wiki.example.com/display/TPS/Some+Page" -o ./prd
python3 confluence_fetch.py "https://wiki.example.com/pages/viewpage.action?pageId=110615147" -o ./prd
python3 confluence_fetch.py "https://wiki.example.com/x/a9qXBg" -o ./prd      # tiny link
python3 confluence_fetch.py 110615147 --base-url https://wiki.example.com -o ./prd
```

Then:
1. `Read ./prd/page.txt` — the full body as text. Scan the `[IMG: images/<file>]` markers to see where each image sits in context.
2. `Read ./prd/images/<file>` — open only the images that matter (mockups, tables-as-images). You don't need all of them.
3. `page.view.html` / `page.storage.html` are the raw bodies, kept for when the text conversion drops something (nested tables, macros).

Put output in a scratch dir, not the user's repo, unless asked.

## Output layout

```
prd/
  page.txt            # readable body; header line has pageId + version + canonical URL
  page.view.html      # raw rendered HTML
  page.storage.html   # raw storage-format XHTML (macros, structure)
  images/             # every attachment, original filenames
```

## Quick reference

| Task | How |
|---|---|
| Read a page behind login | `confluence_fetch.py <url> -o ./out` then Read `out/page.txt` |
| Skip image download (text only, faster) | add `--no-images` |
| Bare pageId | add `--base-url https://wiki.host` (or set `CONFLUENCE_BASE_URL`) |
| Find where an image appears | grep the `[IMG: images/...]` marker in `page.txt` |
| Confirm the version you read | header line of `page.txt` (`v37`) — pages change |

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `no credentials` error | Neither env nor creds file set | Export `CONFLUENCE_PAT`, or fill `~/.config/confluence-reader/credentials` |
| `no page found for space=… title=…` | Title in the `/display/` URL doesn't match exactly (rename, spaces vs `+`) | Use the `viewpage.action?pageId=` URL or the numeric id instead |
| `numeric pageId given but no --base-url` | Bare id, no base configured | Add `--base-url` or set `CONFLUENCE_BASE_URL` |
| REST returns 200 but empty results | Anonymous request / wrong/insufficient creds | Verify creds: `GET /rest/api/user/current` should return your username |
| Page pasted a password into chat | Interactive auth prompt | Use a PAT or the credentials file; rotate any exposed password |

## Notes

- Stdlib only (`urllib`) — runs anywhere Python 3 is present, no `pip install`.
- Server/DC vs Cloud is auto-handled: both expose `/rest/api/content`; the script resolves Cloud `/wiki/spaces/.../pages/<id>` and Server `/display/…`, tiny `/x/…`, and `viewpage.action` URLs.
- To WRITE back to Confluence, use the **confluence-writer** skill.
