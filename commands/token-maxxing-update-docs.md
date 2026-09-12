---
description: Write or update the daily token-maxxing session doc (achievement-first) and refresh the index in docs/token_maxxing/.
argument-hint: "[optional title override]"
---

# /token-maxxing-update-docs

Record the current token-maxxing session as a comprehensive, deliberately verbose
markdown doc. Verbosity is a feature here — write thoroughly. The doc must let a future
reader see the **achievement at a glance** at the very top.

## Mode Selection

Parse `$ARGUMENTS`:

- **`--sweep-stale`** → **Sweep Mode** below: audit every existing doc's `Merge status`
  line against git truth and repair whatever drifted, instead of recording a session.
  Skip straight there; ignore Steps 1–5.
- Anything else (including empty, or a title override) → **Recording Mode**, Steps 1–5
  below — today's normal single-session write, unchanged.

## Recording Mode — do this, in order

### 1. Resolve date and title
- Run `date +%F` in bash → `<DATE>`. Never guess the date.
- Derive `<title>`: a short kebab-case slug of this session's activity
  (e.g. `queue-refactor`, `toolbe-test-coverage`, `streaming-deep-dive`).
- If the user passed `$ARGUMENTS`, use it as the title override (kebab-case it).
- Target path: `docs/token_maxxing/<DATE>-<title>.md`

### 2. Create dir/file or update
- Ensure `docs/token_maxxing/` exists (`mkdir -p`).
- If the target file does NOT exist → create it from the template below.
- If it EXISTS → update/append (a day may have multiple work chunks). Keep the
  Achievement section at the top accurate and cumulative; append detail to later sections.

### 3. Write the doc (this template)

```markdown
# Token-Maxxing Session — <DATE>: <Title>

## 🎯 Achievement / End Result
- **Goal of the burn:** <what we set out to do>
- **Concrete changes:** <files, tests, docs touched>
- **Real value delivered:**
  - <bullet>
  - <bullet>
- **Branch:** token-maxxing-<DATE>
- **Merge status:** on branch | merged | abandoned
- **Approx token burn:** <estimate> 🔥

## Context & Motivation
<why this work, how it was chosen>

## What We Did (blow-by-blow)
<verbose narrative of the session>

## Code / Design Details
<key snippets, before/after, architecture notes>

## Decisions & Trade-offs
<choices made and why>

## Follow-ups & YAGNI notes
<what we deliberately did NOT do, future ideas>

## Appendix
<commands run, notable diffs, references>
```

**`Merge status` is written here as a snapshot, not a promise — this workflow never
comes back to fix it.** This command runs *before* the merge (Solo Mode Step 7 / Worker
Mode W3, both ahead of the merge in Solo Step 8 / Coordinator C7), so write it as true
right now: `on branch` for a solo/coordinator-not-yet-run session, or `on branch, NOT
merged — this is a worker session; the coordinator owns landing worker branches` for a
worker. Whoever performs the actual merge afterward (the solo session itself in Step 8,
or the coordinator in C7) owns editing this same line to `merged (commit <sha>)` on the
copy of the file that lands on `main` — that step is specified there, not here, and
skipping it is exactly how a session doc ends up permanently claiming `NOT merged` for
work that has been on `main` for months. **Sweep Mode below is the backstop** for every
doc written before that step existed, and for any future doc a merge step still manages
to skip.

### 4. Update the index
Maintain `docs/token_maxxing/README.md` as a table of all sessions. Create it if absent:

```markdown
# Token-Maxxing Sessions

A log of deliberately high-token-consumption sessions and the real value each delivered.

| Date | Title | Achievement | Doc |
|------|-------|-------------|-----|
| <DATE> | <Title> | <one-liner> | [link](./<DATE>-<title>.md) |
```
Add or update the row for `<DATE>`. Keep rows sorted newest-first.
The branch is not a column in this index (branches are date-identified via the Date
column and deleted at session end); the per-session doc's Achievement block still
records the branch name.

**The Achievement cell is a hard cap, not a suggestion: ≤120 characters, one clause,
no commit hashes / worker names / file counts / backtick-quoted identifiers.** This
table exists so a scanning reader (or the recall step of `/token-maxxing`) can judge
relevance from the row alone — every supporting detail (commit sha, files touched,
worker name, exact counts) belongs in the per-session doc's own Achievement section,
reached via the Doc link, never inlined into this cell. If the one-liner you drafted
doesn't fit in 120 characters, that's the signal it's changelog detail, not an
index entry — cut it, don't wrap it. Before writing the row, count the cell's
characters and shorten it if it's over the cap; this check is not optional.

### 5. Report
Print the doc path and the one-line achievement so the user sees the result.

---

## Sweep Mode (`--sweep-stale`)

Audit every doc under `docs/token_maxxing/` (excluding `README.md`) and correct any
`Merge status` line that no longer matches reality, driven by fresh subagents rather than
read one by one in this session's own context. Ground truth always comes from git, never
from another doc's prose or from memory of "that session merged, I remember it."

### S1. Enumerate
`ls docs/token_maxxing/*.md`, excluding `README.md` — this is the full worklist, `<FILES>`.
Could be dozens; that's expected, not a signal to shrink scope.

### S2. Batch and spawn checker subagents, incrementally
Split `<FILES>` into batches of ~8–10 files. Spawn one **fresh, read-only** subagent per
batch — **incrementally**: launch the first batch or two, and as each reports back spawn
the next, rather than firing every batch at once. This bounds concurrent load and lets a
bad first result (a wrong lookup method, a misread doc) get caught and corrected before
it's repeated across the whole corpus.

Each checker subagent, for every file in its batch, does this and **only** this (no
edits, no commits — a subagent racing another subagent's `git commit`/`git push` on
`main` is exactly the hazard a batch design must avoid):

1. Read the doc. Note its current `Merge status` line verbatim.
2. Find the commit that first added this exact file — the doc's own "session doc"
   commit, made before any merge:
   ```bash
   DOC_COMMIT=$(git log --format=%H --follow --diff-filter=A -- "<file>" | tail -1)
   ```
3. Ask git, not the doc, whether that commit is now live on `main`:
   ```bash
   git merge-base --is-ancestor "$DOC_COMMIT" origin/main && echo LANDED || echo NOT-LANDED
   ```
4. If `LANDED`, find the merge commit that carried it in (the first merge reachable from
   `$DOC_COMMIT` on the way to `origin/main`; if there is none, `$DOC_COMMIT` itself is
   already on `main` with no separate merge commit — e.g. a fast-forward):
   ```bash
   git log --format=%H --ancestry-path --merges "$DOC_COMMIT..origin/main" | tail -1
   ```
5. If `NOT-LANDED`, the branch may still be legitimately open — do not guess
   `abandoned`; only report `still on branch` (matching what a correct doc should say
   right now).
6. Compare the doc's *current* line against what step 3/4 just measured. If they already
   agree, report `<file>: accurate, no change`. If they disagree, report a finding:
   `<file> | current: "<line>" | correct: "merged (commit <merge-or-doc-sha>)"` (or the
   accurate on-branch wording) — plus the exact commands run, so the correction is
   checkable, not asserted.

### S3. Apply each batch's findings yourself, per batch
As each batch's subagent reports, apply its flagged corrections directly in this
session — edit the `Merge status` line of every flagged file. Do this per batch, not
after every batch has finished, so an interruption partway through the sweep still leaves
already-fixed files fixed.

### S4. One commit per batch, pushed before the next
`git add` only that batch's corrected files, commit
(`docs(token_maxxing): sweep stale Merge status — batch <n>`), and `git push` before
starting the next batch's spawn in S2. Small, reviewable, individually-pushed commits —
never one giant commit at the very end that a mid-sweep crash would lose entirely.

### S5. Report
Print a summary: total docs checked, how many were already accurate, how many were
corrected (old → new status, one line each), and any the checker couldn't resolve —
name those explicitly rather than silently leaving them be.
