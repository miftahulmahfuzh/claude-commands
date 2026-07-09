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

### 5. Report
Print the doc path and the one-line achievement so the user sees the result.
