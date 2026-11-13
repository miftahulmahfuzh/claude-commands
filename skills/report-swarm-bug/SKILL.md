---
name: report-swarm-bug
description: Use when the owner reports something wrong with the Analyze-Orchestrator-Implement workflow itself while it runs — "/report-swarm-bug <what happened>", "report this as a swarm bug", "log an aoi bug", "the deck keeps waking the coordinator for nothing, note it", "that phase was told done too early, write it down" — a bug, a redundant or conflicting rule, an inefficiency or anything unexpected in /analyze, /analyze-orchestrator, /implement, /do, their agents, swarm.py or the swarm-deck mod, seen from any repo and any session (coordinator, phase or ordinary).
---

# Report a swarm bug

The owner saw the workflow do something wrong and wants it written down before the evidence is
gone. This skill saves one **aoi-bug note** through the notes server, linked to this session,
and returns to what the session was doing. `/audit-and-resolve-swarm-workflows` reads these
notes on its next run.

It is not `/postmortem`. That command is for the code of the codebase being worked on: what
went wrong in a task, kept in that repo's `.workflows/postmortem/`. This skill is only for the
workflow: a fault in the machinery that ran the task, whichever repo it showed up in, kept in
one place. A bug in the product's code is never an aoi-bug, even when a swarm phase wrote it.

## Two rules

1. **Record, do not diagnose.** This usually runs inside a live coordinator or phase. Read no
   prompt files, open no source, run no `swarm.py verify`. Save the owner's words, the facts
   `capture.sh` prints, and the evidence already on this session's screen. At most one guess,
   labelled unverified. The whole report is a handful of tool calls.
2. **Never fix it in this session.** A fix edits `claude-commands`; `sync.sh` then changes the
   prompts under running phases, and the swarm-deck mod is loaded straight from the repo. The
   fix happens in its own session (step 4) or later.

## Process

### 1. Capture

```bash
bash ~/.claude/skills/report-swarm-bug/capture.sh [slug]
```

It prints the `WHERE`, `VERSIONS` and `LEDGER` lines. Pass the slug when the owner named a set
or the output says several sets are here. `unknown` stays `unknown`: do not go looking.

Then collect the evidence from what this session has already seen: the wake text, the deck row,
the tool result, the two rules that disagreed. Paste it, do not summarize it. If the complaint
is about something not in this session's context (another window's output), say so in EVIDENCE
and leave it for the fix session, which can read the transcript through the note's session link.

### 2. Write the note

Plain text, the `/n` rules: no markdown, no `#` in the body except the hashtags, which go on the
last line. Pass `origin` with `cwd`, `repo` and `claude_session` (this session's id).

```
AOI bug: <one line, the symptom, in the owner's terms>

KIND: bug | redundant | conflict | inefficient | unexpected
SAID: <the owner's words, verbatim>
WHERE: <from capture.sh>
VERSIONS: <from capture.sh>
LEDGER: <from capture.sh, only the phases the report is about>
EVIDENCE: <pasted lines, or "not in this session: <where it is>">
EXPECTED: <one line: what should have happened>
GUESS (unverified): <one line, or none>

#aoi-bug #aoi-open #aoi-<component> #claude-commands
```

`<component>` is one of `deck`, `swarm-py`, `orchestrator`, `implement`, `do`, `analyze`,
`agents`, `docs`. Pick the one the symptom showed up in; two tags when it sits between two.
Take KIND from the owner's words; when unsure, `unexpected`.

Before creating, search `#aoi-open` notes for the same symptom (one `search` call, tag
filtered). A match gets an `append` with the new SAID, WHERE and EVIDENCE under a dated
"Seen again" line, not a second note. How often a fault recurs is what the audit ranks by.

### 3. Link and verify

Call `link_note` with the note id and this session's node id (named in the SessionStart
context). Report "linked" only when a call in this turn returned `linked: true`. If the notes
tools are missing or fail, follow the fallbacks in the `n` skill ("Verify the link"); if the
note itself cannot be saved, write the body to `~/.claude/swarm-deck/aoi-bugs/<timestamp>.txt`
and say so, so the next session with notes access can file it.

### 4. Answer, and what happens next

Reply in three lines or fewer: the note id as a wall link, the KIND and component, and whether
it was new or a repeat. Then go back to the session's work. What happens to the bug is the
owner's call, and the default is nothing:

- **Leave it** (default, and whenever the owner says nothing more). The note stays `#aoi-open`
  for the next audit or a later fix.
- **Fix it now** means a new session, never this one:
  ```bash
  python3 ~/.claude/skills/swarm/swarm.py launch --name fix-<note id> \
      --cwd <the claude-commands repo capture.sh found> --permission-mode <this session's mode> \
      --prompt "Fix AOI bug note <note id> (read it with the notes server, and its linked session's transcript for evidence). Reproduce it first, fix it in this repo, prove it, then close the note as the report-swarm-bug skill's 'Closing a report' section says."
  ```
  While a set is running, tell the owner in one line that the fix reaches live sessions when it
  is deployed (`sync.sh` for prompts, on save for the mod), so the fix session must not deploy
  until the set has landed unless the owner says otherwise. Put that sentence in the prompt too.
- **Fix it here** is honoured only in a session that is not part of a running set and whose cwd
  is the claude-commands repo. Anywhere else, say why and offer the launch.

## Closing a report

Whoever fixes a reported bug (a fix session, an audit, the owner by hand) closes its note:

1. `append` one block: `FIXED <date>: <commit sha>, <one line on what changed>` — or
   `WONTFIX <date>: <why>`, or `DUPLICATE of <note id>`.
2. `update` the body so the tag line carries `#aoi-fixed` (or `#aoi-wontfix`) in place of
   `#aoi-open`. Everything else in the body stays as written: the report is evidence, and the
   audit reads fixed reports too.

A fix is not closed on a guess. FIXED needs a commit and a proof that the reported symptom no
longer happens: a test, or the reproduction re-run.
