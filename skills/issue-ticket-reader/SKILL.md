---
name: issue-ticket-reader
description: Use when you need to READ a Jira bug/issue/task ticket an agent cannot open in a browser — URLs like project.*/browse/KEY-123, /jira/…?selectedIssue=KEY-123, *.atlassian.net/browse/KEY-123, or a bare key like UATP-2960. Pulls description, all comments, links, subtasks and metadata as readable text, downloads every attachment locally (images you can Read, videos sampled into frames). Covers Jira Server/Data Center and Cloud. Reuses the confluence-reader credentials.
---

# Issue Ticket Reader

## Overview

You can't click a Jira link, and a screenshot of the ticket loses the comment thread and
attachments — which is usually where the actual bug report lives. Jira has a clean REST API:
hit it with the user's credentials to pull the whole ticket as text **and** land every
attachment on disk so you can `Read` the screenshots.

**Core principle: fetch via REST, don't scrape the login-walled HTML.** `issue_fetch.py`
(stdlib only, no pip) resolves the issue key from any URL form, downloads the issue with
`renderedFields`, converts description + every comment to readable text with
`[IMG: attachments/<file>]` markers placed where the image actually sits, and saves each
attachment under `attachments/`. Attached videos are sampled into JPEG frames with ffmpeg.

This is the Jira counterpart to **confluence-reader** (pages) — same credential store.

## Prerequisite: credentials

Auth is read in this order; nothing is ever printed:

1. **`JIRA_PAT`** env → `Authorization: Bearer` (preferred; Jira Server/DC ≥8.14 and Cloud
   both support Personal Access Tokens — Profile → Personal Access Tokens).
2. **`JIRA_USER` + `JIRA_PASS`** env → HTTP Basic (`JIRA_API_TOKEN` in place of the password
   on Cloud).
3. **`$JIRA_CREDENTIALS_FILE`**, else `~/.config/issue-ticket-reader/credentials`
   (shell-style `KEY=VALUE`; see `credentials.example`).
4. **Fallback: `~/.config/confluence-reader/credentials`** — `CONFLUENCE_PAT` /
   `CONFLUENCE_USER` / `CONFLUENCE_PASS` / `CONFLUENCE_API_TOKEN` are reused as the Jira
   credentials. Jira and Confluence normally sit behind one user directory, so **if
   confluence-reader is already set up, this skill needs no new setup.**
   `CONFLUENCE_BASE_URL` is deliberately *not* reused — Jira lives on a different host, so
   pass a full ticket URL (or set `JIRA_BASE_URL`).

**Never ask the user to paste a password into the chat** — it lands in the transcript. Point
them at `credentials.example`, or have them export a PAT. If a password was already pasted,
use it, then tell them to rotate it.

## The method

```bash
S=~/.claude/skills/issue-ticket-reader

# Normal case — full ticket URL, output to a scratch dir:
python3 $S/issue_fetch.py "https://project.example.com/browse/UATP-2960" -o ./ticket

# Other accepted forms:
python3 $S/issue_fetch.py "https://example.atlassian.net/browse/ABC-12" -o ./ticket
python3 $S/issue_fetch.py "https://project.example.com/jira/software/…?selectedIssue=ABC-12"
python3 $S/issue_fetch.py UATP-2960 --base-url https://project.example.com -o ./ticket
```

Then:
1. `Read ./ticket/issue.txt` — summary, metadata, description, **every comment in order**,
   linked issues, subtasks, attachment inventory. The `[IMG: attachments/<file>]` markers
   show where each image was embedded.
2. `Read ./ticket/attachments/<file>` — open the screenshots that matter. Lines marked
   `<- Read this file directly` are images.
3. For a video attachment, `Read ./ticket/frames/<name>/frame_*.jpg` — evenly-spaced
   samples, filename carries the timestamp (`frame_03_0012.50s.jpg`).
4. `issue.json` / `description.html` are the raw payloads, for when the text conversion
   drops something (nested tables, custom macros, unusual custom fields).

Put output in a scratch dir, not the user's repo, unless asked.

## Output layout

```
ticket/
  issue.txt              # readable ticket: metadata, description, all comments, links, subtasks
  issue.json             # full raw REST payload (every field, unconverted)
  description.html       # server-rendered description HTML
  attachments/           # every attachment, original filenames
  frames/<video-stem>/   # sampled JPEG frames, one dir per attached video
```

## Flags

| Flag | Effect |
|---|---|
| `-o DIR` | output directory (default `./jira_issue`) |
| `--base-url URL` | required only for a bare `KEY-123` |
| `--no-attachments` | text only, faster; attachments still listed, not downloaded |
| `--frames N` | frames sampled per video (default 8; `0` disables) |
| `--changelog` | append the field/status history (who moved it, when) |
| `--all-fields` | dump every non-empty custom field with its human-readable name (Sprint, Story Points, …) |

## What this cannot do

State these plainly rather than implying otherwise:

- **Video audio is not transcribed.** No local speech-to-text is installed. A screen
  recording is understood only from its sampled frames — narration and system sound are
  lost. If the bug is only explained verbally, say so and ask the user.
- **Sampled frames can miss the moment.** 8 frames over a 3-minute recording is one every
  ~22s; a flash of an error toast can fall between samples. Raise `--frames` (e.g. `--frames 40`)
  when the ticket hinges on a transient UI state.
- **`.mov`/`.mp4` only as far as ffmpeg supports it** — if ffmpeg is absent, the line reads
  `frame extraction unavailable` and the video is downloaded but unread.
- **Attachments that are documents** (pdf, xlsx, docx) are downloaded but not converted;
  Read a pdf directly, and handle spreadsheets with a separate tool.

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `no credentials` | Neither env, jira creds file, nor confluence creds file has a usable pair | Export `JIRA_PAT`, or fill `~/.config/issue-ticket-reader/credentials` |
| `HTTP 401` | Wrong PAT/password, or Jira locked the account behind a CAPTCHA after failed logins | Log in via browser once to clear the CAPTCHA, then retry; prefer a PAT |
| `HTTP 403` | Authenticated, but no permission on that project | Ask the user to grant Browse Projects, or have them export the ticket |
| `HTTP 404` | Wrong key, or no browse permission (Jira returns 404 to hide existence) | Verify the key; check the project is one the user can see |
| `bare issue key given but no --base-url` | Passed `ABC-12` with nothing else | Add `--base-url`, or set `JIRA_BASE_URL`, or paste the full URL |
| `[IMG (not downloaded): …]` in the text | Image is embedded from another issue/external URL, not an attachment of this one | Fetch that other issue, or note the image is external |
| Comments look truncated | Jira caps `fields.comment` at the first ~20 comments on some versions | Check `issue.json` → `comment.total` vs `comments` length; page the rest via `/rest/api/2/issue/KEY/comment?startAt=N` |

## Notes

- Stdlib only (`urllib`) — no `pip install`. ffmpeg/ffprobe used only when a video is attached.
- Server/DC vs Cloud is auto-handled: tries `/rest/api/2/issue/…` and falls back to
  `/rest/api/3/…`; Cloud's ADF description/comment bodies are walked into text, Server's
  wiki markup goes through the rendered HTML.
- Read the **whole comment thread** before concluding anything about the bug. On this kind of
  ticket the reproduction steps, the real error, and "actually it's fixed" often live in
  comment 4, not the description.
- To read a Confluence **page** instead, use **confluence-reader**. To write back, **confluence-writer**.
