---
description: Write or update the daily token-maxxing session doc (achievement-first) and refresh the index in docs/token_maxxing/.
argument-hint: "[optional title override]"
---

# /token-maxxing-update-docs

Record the current token-maxxing session as a comprehensive, deliberately verbose
markdown doc. Verbosity is a feature here — write thoroughly. The doc must let a future
reader see the **achievement at a glance** at the very top.

## Do this, in order

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
work that has been on `main` for months.

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
