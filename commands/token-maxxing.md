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

### 2. Recall recent sessions (spawn a subagent)
Give the workflow memory so today doesn't repeat what we already finished, and so we can
choose to *continue* prior work.

Spawn a **fresh subagent** to read the most recent token-maxxing docs:
- List `docs/token_maxxing/*.md` (excluding `README.md`), sort by ISO filename **descending**,
  take the top **5**. If fewer exist, take what's there. If none exist, skip this step —
  everything is fresh.
- The subagent reads those docs **in full** and returns a compact digest. For each session:
  title, achievement one-liner, **merge status**, and any items under
  "Follow-ups & YAGNI notes".
- From the digest, the subagent produces two buckets:
  - **`completed`** — work that is done and merged; do NOT re-propose these verbatim.
  - **`continuation-candidates`** — open follow-ups, unmerged branches, or ideas explicitly
    deferred; these are ripe to *continue or improve* today.

Hold both buckets for Step 4.

### 3. Survey the repo (read-only, cheap)
Skim for grounding — do NOT do deep work yet:
- Recent commits: `git log --oneline -15`
- Open work: any `.workflows/todos.md` and `**/analysis_report.md` files (`find . -name todos.md` , `find . -name analysis_report.md`)
- Test-coverage gaps: packages with few/no `*_test.go` files
- Stale or thin docs under `docs/` , `**/analysis_report.md` , `**/package_readme.md` and `**/unittest_guide.md`
- Obvious smells: large files, TODO/FIXME markers, dead code

### 4. Propose a menu of 3–5 ideas
Blend fresh ideas with continuations. Every option is tagged:
- **🆕 Fresh** — new work that does NOT collide with anything in the `completed` bucket.
- **🔁 Continue/improve** — drawn from `continuation-candidates` (deepen, finish, or improve
  a prior session's work).

Aim for a mix of both (e.g. 3 fresh + 1–2 continuations) unless a theme narrows it.
Rank by value. For EACH idea give:
- **Tag** — 🆕 or 🔁 (for 🔁, name the prior session it continues)
- **What** — one crisp sentence
- **Why it's real value** — not busywork
- **Scope** — files/packages touched, rough size
- **🔥 Burn potential** — low / med / high (how many tokens it will credibly consume)

Bias the menu toward `$ARGUMENTS` if provided. Keep the fresh ideas varied across sessions by
drawing from this catalog (don't propose the same set every day):

- **Refactor** a subsystem for clarity/quality (e.g. `chatbot/queue`, `chatbot/cancellation`, `tools/toolcore/pipeline`)
- **Test coverage** — raise coverage in one package with real, meaningful tests
- **Audit** — hunt races/leaks/edge cases in a concurrency-heavy package
- **Docs rewrite** — modernize an architecture/overview doc under `docs/`
- **Deep-dive teaching** — explain one feature/function end-to-end for the user
- **gofmt + lint** — sweep formatting/lint issues across a package (`gofmt`, `golangci-lint`)
- **YAGNI hunt** — find and remove dead/speculative code

End the menu with: **"Pick a number, or say `surprise me` (I pick the highest-value one) or `reroll` (new menu)."**

### 5. Let the user choose
- A number → that idea.
- `surprise me` → pick the highest-value idea yourself.
- `reroll` → generate a fresh menu (go back to step 4).

### 6. Confirm scope briefly
One short exchange to lock scope. Adjust to user feedback.

### 7. Create / reuse today's branch
```bash
git checkout main && git pull --ff-only 2>/dev/null; \
git checkout -b "token-maxxing-<DATE>" 2>/dev/null || git checkout "token-maxxing-<DATE>"
```
One branch per day — reuse it if it already exists. All work lands here; do NOT merge
to `main` automatically (the user reviews and merges later).

### 8. Roll
Do the work. Commit real increments with clear messages. Follow the project's skills
(TDD, systematic-debugging, etc.) as normal — quality still matters. Be thorough and
verbose; exhaustive-but-correct is the goal, not terse.

### 9. Auto-write the session doc when done
When you judge the work complete (or at a natural stopping point), **spawn a fresh
subagent** to run the `/token-maxxing-update-docs` workflow so the session is recorded
without you having to be asked. Give the subagent a full summary of what happened this
session. You may also let the user trigger it manually.
