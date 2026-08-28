# Do Command - Execute Tasks by TaskID

Execute a task from any package's `todos.md` by TaskID. Supporting work is delegated to
subagents; **the main context does code implementation only**.

Like `/implement`, `/do` **does not write implementation plans**. It adopts the plan `/analyze`
wrote, or works from the task description for small tasks. Anything big enough to need a plan
gets one from `/analyze`.

## Arguments
- Required: `{TaskID}` (e.g. `P0-DB-A236`, `P1-CB-B789`)
- Optional: `--note="{additional instructions}"`

## TaskID Format

`Priority-PackageCode-4CharID` — validate before searching:

```regex
^P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}$
```

- **Priority**: P0–P4 · **PackageCode**: 2–3 uppercase letters · **4CharID**: `[A-Z0-9]{4}`

---

## Pipeline

### Phase 1: Preparation (Subagents 1 → 2 → 3)

All preparation happens in isolated subagent contexts.

#### Step 1: Locate Task — `task-locator` (haiku)

**Input:** `task_id`

Searches every `.workflows/todos.md` for the TaskID, validates that exactly one matches,
extracts the package path from the file location and the task's metadata.

```yaml
status: success
package_path: "{path}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{title}"
  context: "{context}"
  plan_file: "{path or empty}"
  depends_on: ["{TaskID}"]
```

#### Step 2: Load Context — `context-loader` (opus)

Reads `todos.md`, `package_readme.md`, `analysis_report.md`, and **synthesizes** — it returns a
context packet, never raw file contents.

```yaml
context_packet:
  task_description: "{1-2 sentences}"
  docs_summary: "{key points only}"
  file_references: ["{file}"]
  related_tasks: ["{TaskID}"]
```

#### Step 3: Generate Execution Brief — `plan-generator` (opus)

A brief is routing information — target files and steps. It is **not** an implementation plan,
and this subagent writes no plan files.

1. **Plan file exists** (`.workflows/plan/{TaskID}.md`) → **adopt it.** Read it and translate it
   into the brief. Do not re-plan. Plans adopted from a `/analyze` plan set were reconciled
   against the other phases; regenerating one discards that.
2. **No plan file, EASY or NORMAL** → build the brief from the task description and context
   packet.
3. **No plan file, HARD** → **stop.** Return an error naming `/analyze`. A HARD task without a
   plan is exactly the case that needs one, and this is not the command that writes it.

`plan-generator` creates no branches. Branch isolation belongs to `/analyze`, which cuts a
worktree when it plans.

```yaml
task:
  id: "{TaskID}"
  title: "{title}"
  difficulty: "EASY|NORMAL|HARD"
  type: "{Bug|Feature|Refactor|Docs}"
  plan_source: "adopted:{path}" | "brief-only"

execution:
  target_files:
    - path: "{relative/path}"
      action: "create|modify|delete"
      description: "{what to do}"
  approach: |
    {2–3 sentences}
  steps:
    - "{Step 1}"

validation:
  success_criteria: ["{criterion}"]
  test_command: "{command}"
```

### Phase 2: Execution (Main Context)

**The only phase in the main context.**

1. Display the task summary from the brief
2. For each `target_file`: read, apply the steps, write
3. Run `test_command` if provided
4. Return the completion report

**The main context does NOT:** read `todos.md` or any `.workflows` file · read documentation ·
update `todos.md` · run git · write plans.

```yaml
completion_report:
  task_id: "{TaskID}"
  status: "success|failure"
  modified_files: ["{file}"]
  error_message: "{if failure}"
```

### Phase 3: Completion (Subagents 4 → 5 → 6)

#### Step 4: `completion-handler` (opus)

Marks the task complete in `todos.md` (`- [ ]` → `- [x]`, completion metadata, move to
**Completed Tasks**, update Quick Stats), updates `analysis_report.md` if a documented finding
was resolved, and — for a plan-set phase — ticks the phase in the plan index and unblocks the
next phase's task. Then dispatches:

#### Step 5: `readme-updater` (opus)

Identifies the single package most influenced by the change, and updates
`{package_path}/.workflows/package_readme.md`. If none exists, it runs `/update-readme
{package_path}` automatically — no asking, no manual bootstrap in a separate session.

Runs **before** the pusher so README updates are committed with the code.

#### Step 6: `pusher` (haiku)

Stages, writes a conventional-commit message, commits, pushes.

---

## Context Isolation

| Phase | Context | Reads | Writes |
|---|---|---|---|
| `task-locator` | isolated | all `todos.md` | none |
| `context-loader` | isolated | `todos.md`, docs | none |
| `plan-generator` | isolated | plan file, if any | none |
| **Main context** | clean | target files only | target files only |
| `completion-handler` | isolated | `todos.md`, plan index | `todos.md`, plan index |
| `readme-updater` | isolated | `package_readme.md` | `package_readme.md` |
| `pusher` | isolated | `git diff` | git only |

**The main context never loads** `todos.md`, `package_readme.md`, `analysis_report.md`, or plan
files. Preserve this when editing the flow: don't move doc-reading or git into the main-context
step, and don't have subagents write code.

---

## Plan-Set Phase Tasks

A task carrying a `**Plan Set**:` field is one phase of a plan `/analyze` wrote. Three rules:

1. **Check `Depends on:` first.** If any prerequisite TaskID is incomplete, stop and name it.
   The phase's plan quotes code as it will look *after* the earlier phases land.
2. **Adopt the plan, never regenerate it** (Step 3).
3. **Stay on the plan set's branch.** No new branch — the plan set owns one and every phase
   lands on it. If the current worktree is not the one the plan index names, stop and print the
   `cd` command.

## Blocked Tasks

Status `blocked`: display what blocks it, ask `Continue anyway? [y/N]`, proceed if confirmed.

## Drift

If the real code no longer matches what an adopted plan quotes, the rule is `/implement`'s:
small drift → follow the plan's intent and note it; large drift → stop and say
`Re-run /analyze to re-plan against the current tree.`

---

## Search Strategy

```bash
find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "{TaskID}" {} \;
# or
rg -l "{TaskID}" --type-add 'todos:*todos.md' --type todos
```

TaskIDs are unique across the repo, so a direct search is sufficient — no indexing, no caching.
Extract the package path from the match: `./chatbot/bowl/.workflows/todos.md` → `chatbot/bowl`.

---

## Messages

**Progress:**
```
🔍 Locating task... (task-locator)
📁 Found: P1-DB-A236 in db/.workflows/todos.md
📋 Loading context... (context-loader)
📋 Generating brief... (plan-generator)  [adopted .workflows/plan/P1-DB-A236.md]

🎯 Executing: P1-DB-A236 (main context)
  📄 manager.go → modify
✅ Implementation complete

📝 Completing... (completion-handler)
```

**Success:**
```
✅ Task Completed: P1-DB-A236
📦 Package: db
📄 Modified: manager.go
📝 Updated: todos.md, package_readme.md
💾 Commit: abc1234
🌿 Branch: main
```

**Errors:**
```
✗ Invalid TaskID format: 'INVALID'
  Expected: P[0-4]-[CODE]-[ID], e.g. P0-DB-A236

✗ Task 'P0-DB-Z999' not found
  Available in DB: P0-DB-A236, P1-DB-A237

✗ Task P1-DB-A236 missing Difficulty field
  Run: /update-todos {package_path}

✗ HARD task P1-BC-A123 has no plan file.
  /do does not write implementation plans. Run /analyze first,
  then /implement -f <SLUG>_PLAN.md.

✗ P1-TC-A002 depends on P1-TC-A001 (phase 1), which is not complete.
```

---

## Agents

Deployed to `~/.claude/agents/` by `sync.sh`, dispatched by `subagent_type`:

| Agent | Model | Purpose |
|---|---|---|
| `task-locator` | haiku | find the TaskID, extract metadata |
| `context-loader` | opus | load and synthesize context |
| `plan-generator` | opus | execution brief — adopts a plan, never writes one |
| `completion-handler` | opus | update `todos.md`, dispatch readme-updater and pusher |
| `readme-updater` | opus | update the most-impacted `package_readme.md` |
| `pusher` | haiku | stage, commit, push |

> Step 4 (execution) runs in the **main context** and has no agent file, by design.

---

## Integration

**Before:** `/update-todos <package>` to make sure tasks are current.
**After:** `/analyze-package <package>` if the change was major.

**Multi-phase work:** `/do` takes one TaskID per session by design. For a sequence of related
changes, `/analyze` decomposes the work into phases with reconciled plans and `/implement`
creates one task per phase; `/do` then executes them one at a time.

## Examples

```bash
/do P2-CL-A001                                       # EASY — brief from the task text
/do P1-DB-A236 --note="also handle the bulk path"    # NORMAL — brief + note
/do P1-TC-A002                                       # phase 2 of a plan set — adopts its plan
```
