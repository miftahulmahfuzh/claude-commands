---
description: Start a deliberately high-token-consumption ("token-maxxing") work session — propose a menu of real-value ideas, pick one, branch, and roll.
argument-hint: "[optional theme, e.g. tests | docs | refactor | audit]"
---

# /token-maxxing

You are kicking off a **token-maxxing session**. Context: leadership wants higher
overall Claude token consumption, and the team wants a defensible record of real
engineering value to justify upgrading the company Claude subscription. So: burn tokens
generously, but bias hard toward **genuinely useful work** so every session is defensible.

Optional theme passed by the user: **$ARGUMENTS**
(If empty, ideas may span anything. If present — e.g. `tests`, `docs`, `refactor`,
`audit`, `teach` — bias the menu toward that theme.)

## Do this, in order

### 1. Get the real date
Run `date +%F` in bash. Never guess the date. Call the result `<DATE>`.

### 2. Survey the repo (read-only, cheap)
Skim for grounding — do NOT do deep work yet:
- Recent commits: `git log --oneline -15`
- Open work: any `.workflows/todos.md` files (`find . -name todos.md`)
- Test-coverage gaps: packages with few/no `*_test.go` files
- Stale or thin docs under `docs/` and `**/package_readme.md`
- Obvious smells: large files, TODO/FIXME markers, dead code

### 3. Propose a menu of 3–5 ideas
Rank by value. For EACH idea give:
- **What** — one crisp sentence
- **Why it's real value** — not busywork
- **Scope** — files/packages touched, rough size
- **🔥 Burn potential** — low / med / high (how many tokens it will credibly consume)

Bias the menu toward `$ARGUMENTS` if provided. Keep ideas varied across sessions by
drawing from this catalog (don't propose the same set every day):

- **Refactor** a subsystem for clarity/quality (e.g. `chatbot/queue`, `chatbot/cancellation`, `tools/toolcore/pipeline`)
- **Test coverage** — raise coverage in one package with real, meaningful tests
- **Audit** — hunt races/leaks/edge cases in a concurrency-heavy package
- **Docs rewrite** — modernize an architecture/overview doc under `docs/`
- **Deep-dive teaching** — explain one feature/function end-to-end for the user
- **gofmt + lint** — sweep formatting/lint issues across a package (`gofmt`, `golangci-lint`)
- **YAGNI hunt** — find and remove dead/speculative code

End the menu with: **"Pick a number, or say `surprise me` (I pick the highest-value one) or `reroll` (new menu)."**

### 4. Let the user choose
- A number → that idea.
- `surprise me` → pick the highest-value idea yourself.
- `reroll` → generate a fresh menu (go back to step 3).

### 5. Confirm scope briefly
One short exchange to lock scope. Adjust to user feedback.

### 6. Create / reuse today's branch
```bash
git checkout main && git pull --ff-only 2>/dev/null; \
git checkout -b "token-maxxing-<DATE>" 2>/dev/null || git checkout "token-maxxing-<DATE>"
```
One branch per day — reuse it if it already exists. All work lands here; do NOT merge
to `main` automatically (the user reviews and merges later).

### 7. Roll
Do the work. Commit real increments with clear messages. Follow the project's skills
(TDD, systematic-debugging, etc.) as normal — quality still matters. Be thorough and
verbose; exhaustive-but-correct is the goal, not terse.

### 8. Auto-write the session doc when done
When you judge the work complete (or at a natural stopping point), **spawn a fresh
subagent** to run the `/token-maxxing-update-docs` workflow so the session is recorded
without you having to be asked. Give the subagent a full summary of what happened this
session. You may also let the user trigger it manually.
