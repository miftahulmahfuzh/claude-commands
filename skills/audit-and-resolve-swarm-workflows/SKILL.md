---
name: audit-and-resolve-swarm-workflows
description: Use when the swarm workflow (/analyze, /analyze-orchestrator, /implement, /do, their agents, skills/swarm, engineering-principles, the swarm-deck mod and the docs that describe them) needs a health check for redundant, conflicting or stale instructions — "/audit-and-resolve-swarm-workflows", "audit the swarm workflow", "check our workflow for conflicts", "is anything redundant in our commands", "clean up the workflow after we borrowed X", or after a run where an agent met two rules that disagreed.
---

# Audit and resolve the swarm workflows

The swarm workflow is about 7,000 lines of prompts plus `swarm.py` and the swarm-deck mod, and
every new capability or borrowed method adds instructions. Left alone, the same rule gets copied
into several files, the copies drift, and an agent at 3am meets two rules it has to choose
between. This skill finds that, proves it, and fixes it, with the owner in the loop for the
decisions that are really theirs.

**First run: 2026-11-12** (note Z-G86, commit `f369b82`). It found five runtime bugs hiding
behind duplicated prose, among them a plan set landed twice, the first time without its verifier.
Most findings had one cause: a rule copied into 2–6 files.

## The tenets this audit enforces

From the owner (note 9-5LI, memory `borrowing-methods-tenets`), applied inward:

1. **One owner per rule.** Every rule lives in exactly one file, the one that executes it.
   Everywhere else a one-line pointer names the owner. The ownership map is in `CLAUDE.md`
   ("One owner per rule") — read it first, and keep it current.
2. **No two rules an agent has to choose between.** When two disagree, one wins and the other is
   **removed**, not merely outranked.
3. **Every borrowed method still earns its place:** we need it, and we don't already have it.
   A method adopted since the last audit gets that check again, now that it has been used.

## Process

### 1. Load the context

- Read `CLAUDE.md` (the ownership map, the coupling rules such as "/analyze Step 8 and
  plan-reconciler rules 6–7 must stay in step") and `known-intentional.md` beside this file.
  Anything listed there is a decision, not a finding: do not re-report it unless something
  about it changed.
- `git log --oneline <last audit commit>..HEAD -- commands agents skills mods docs CLAUDE.md`
  to see what changed since the last audit. Changed areas get the most attention.
- Build the inventory: every file the swarm workflow loads or describes.
  ```bash
  ls commands/{analyze,analyze-orchestrator,implement,do}.md agents/*.md \
     skills/swarm/SKILL.md skills/swarm/*.py skills/engineering-principles/SKILL.md \
     skills/create-verification-skill/SKILL.md mods/swarm-deck/hooks/*.js \
     mods/swarm-deck/README.md docs/*.md docs/ears/README.md CLAUDE.md README.md
  grep -rln "swarm\|/implement\|/analyze\|completion-handler\|verifier" commands agents skills mods docs \
     --include=*.md --include=*.py --include=*.js | sort -u     # catch new files
  ```
  A file the grep finds that the list above misses is new. Put it in whichever reviewer's scope
  it belongs to.

### 2. Review in parallel

Dispatch **three reviewers in one message**, using the briefs in `reviewer-briefs.md`:
execution, planning, and swarm + swarm-deck. Each is a general-purpose agent, read-only. Each
reports four kinds of finding with file:line quotes of both sides: CONFLICT, DRIFTED DUPLICATE,
STALE, IDENTICAL BLOAT. Paste the `known-intentional.md` entries into each brief so they are
not re-reported.

Add a fourth reviewer only when a method was borrowed since the last audit. Its brief: does that
method still fill a gap nothing else fills, and which existing rules does it now duplicate or
contradict?

Do not review the same files yourself while they run. Wait.

### 3. Verify before you believe

A reviewer told to find problems will find some. Before anything is reported to the owner:

- **Re-check every bug and every conflict yourself**, by reading both quoted sides, and for
  code, the function itself. For a `swarm.py` claim, run it: `verify` against a real ledger
  in `.workflows/orchestration/`, or the case in a scratch git repo.
- Drop what does not hold. Mark what you checked and what you are taking on the reviewer's word.

### 4. Report and decide

Group the findings, worst first:

| Group | What | Example from the first run |
|---|---|---|
| A. Bugs | prose or code that makes a run do the wrong thing | the last phase merged twice, first unverified |
| B. Conflicts | two rules an agent has to choose between | pstack "delete first" vs "deletion lands last" |
| C. Drift / stale | copies that changed meaning; references to what no longer exists | a flag that was never real |
| D. Bloat | near-verbatim copies | the same git-safety story in four files |

For each conflict, recommend a winner:
- The owner in the `CLAUDE.md` map wins over a copy.
- Code with tests wins over prose describing it, unless the code is the bug.
- Between two prose rules, the one that keeps a run unattended and safe wins (the precedence
  ladder, never-ask, verify-before-land).

Ask the owner only about real design forks (the first run had one: delete first or delete
last), with your recommendation. Offer to save the audit as a note.

### 5. Save the audit, then fix

- Save the audit as a note through the notes server (`/n` rules: plain text, hashtags
  `#claude-commands #swarm #audit #decision` on the last line, verify the link). Keep `#` out of
  the body except in hashtags: "principle #1" becomes a tag.
- **Fix directly in this session, not through `/analyze`**, whenever the findings include bugs
  in the swarm machinery itself (landing, `swarm.py`, the executors). A swarm run would hit the
  bugs it is meant to fix. A large, purely textual consolidation may go through `/analyze`.
- Order: bugs first, with a failing test for each code bug (`swarm.py` selftest cases; the
  mod's `claude plugin test`). Then settle the conflicts: delete the losing side. Then
  consolidate: move each rule to its owner, and turn every other copy into a pointer.
- When a fix moves a responsibility (who lands, who commits, who verifies), update in the same
  change: the owner file, every caller, `CLAUDE.md`'s map and summaries,
  `docs/architecture-notes.md`, and `README.md`. `/do` and `/implement` change together.

### 6. Prove it

```bash
python3 skills/swarm/swarm.py selftest
for t in skills/swarm/tests/test_*.py; do python3 "$t" || echo "FAIL $t"; done
(cd mods/swarm-deck && claude plugin test)          # only when the mod's code changed
python3 skills/swarm/swarm.py verify --slug <a real ledger>   # smoke, no --apply
./sync.sh
for d in skills agents commands; do diff -rq --exclude=__pycache__ --exclude='.*' "$d" ~/.claude/"$d"; done
```
Then grep the repo for the stale phrases each finding quoted (the old flag, the old step name,
the removed claim). Every hit must be gone or deliberate.

### 7. Land and record

- Commit and push through the `pusher` agent (haiku) with an explicit `paths` list and a
  message that lists what was fixed, grouped like the report.
- Append the resolution to the audit note: the commit, what was fixed, and **what was left on
  purpose and why**.
- Add each left-on-purpose item to `known-intentional.md` (one line: what, where, why), and
  commit that with the fixes. That file is how the next audit stays short.
- Name anything not yet exercised by a live run (a new landing path, a new ledger state), so
  the owner knows what the next real run is testing.

## What this skill does not do

- It does not add capabilities. A finding that needs a new feature becomes a task card or an
  `/analyze` request, not part of the audit.
- It does not rewrite style. Wording is changed only where two copies disagree, or where a copy
  becomes a pointer.
- It does not touch other repos' `verify-*` skills or `.workflows/` plan sets. Old plan sets
  are legacy by design and stay readable.
