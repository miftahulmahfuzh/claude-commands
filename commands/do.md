# Do Command - Execute Tasks by TaskID

Execute a task from any package's `todos.md` by TaskID. Supporting work is delegated to
subagents; **the main context does code implementation only**.

Like `/implement`, `/do` **does not write implementation plans**. It adopts the plan `/analyze`
wrote, or works from the task description for small tasks. Anything big enough to need a plan
gets one from `/analyze`.

**A task that carries a plan file takes the adopted path** (Step 1b): the main context reads that
plan and applies it, and neither `context-loader` nor `plan-generator` runs. Only a task with no
plan goes through the brief pipeline.

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

### Phase 0: Name the Session (Main Context)

The moment the TaskID validates — before the locator runs, because the id is the argument and
needs nothing looked up:

```bash
python3 ~/.claude/skills/task/session.py rename "do-P1-DB-A236"
```

Five terminals open on one repo all carry the same derived name — `agentic-8f`, `agentic-d4` —
which says which repo and not which task, so the right window is found by reading scrollback and
`/resume` a week later offers a row of near-identical titles. The TaskID is the one label that
separates them. It is the same rename `/rename` performs: it reaches the running process over the
session's own socket, so the tab title, the `/resume` row and the name peers address all follow
together — **and the tmux window too**, which under tmux is the only one of those the user can
actually see, because the status line covers the terminal's tab title. `--no-tmux` skips that
half.

Use **the TaskID that was asked for**, even on a plan-set phase that sends you through an earlier
task first — the session is named for its errand, not for its current file. And **never let it
stop anything**: it cannot fail by design (no socket, no tmux, a session started some other way →
`renamed: false` with a reason, exit 0), and a task is not worth losing over the name of a window.

This does not breach the main-context rule below: it reads no `.workflows` file, no
documentation, and runs no git. It is one command that names the terminal.

### Phase 1: Preparation (Subagent 1, then one of two routes)

All preparation happens in isolated subagent contexts. **Which route is taken is decided by the
locator's output, not by the difficulty tag** — see Step 1b.

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
  depends_on_incomplete: ["{TaskID}"]
```

#### Step 1b: Fork on the Plan File (Main Context)

One check, on the locator's output, and it chooses the whole rest of Phase 1:

| `plan_file` | Route | What runs |
|---|---|---|
| non-empty | **adopted path** | nothing else in Phase 1 — straight to Phase 2 with the path |
| empty | **brief path** | Step 2 and Step 3, below |

**The adopted path is the point of this command's existence on a plan set.** `/analyze` wrote
that file with complete code and `plan-reconciler` reconciled it against the other phases;
`plan-generator`'s brief schema has nowhere to put code, so routing a cooked plan through it
compresses complete code into a 2–3 sentence `approach` before the main context — the thing that
actually writes the code — ever sees it. That is not a saving, it is a loss. `/implement` has
always read the phase plan directly in its own main context (`implement.md` Step 4); this is the
same behavior, reached from a TaskID instead of from a plan index.

**First, though, honour `depends_on_incomplete`.** If the locator returned any, stop and name
them — on either route. The check lives in the locator because it is already reading every
`todos.md`; refusing here costs one haiku call instead of two opus ones.

**No difficulty tag changes this fork.** A HARD task cannot reach the adopted path without a
plan, because the path is defined by the plan existing — so the HARD refusal in Step 3 still
guards exactly the case it always did.

#### Step 2: Load Context — `context-loader` (opus) — brief path only

Reads `todos.md`, `package_readme.md`, `analysis_report.md`, and **synthesizes** — it returns a
context packet, never raw file contents.

```yaml
context_packet:
  task_description: "{1-2 sentences}"
  docs_summary: "{key points only}"
  file_references: ["{file}"]
  related_tasks: ["{TaskID}"]
```

#### Step 3: Generate Execution Brief — `plan-generator` (opus) — brief path only

A brief is routing information — target files and steps. It is **not** an implementation plan,
and this subagent writes no plan files.

1. **EASY or NORMAL** → build the brief from the task description and the context packet.
2. **HARD** → **stop.** Return an error naming `/analyze`. A HARD task without a plan is exactly
   the case that needs one, and this is not the command that writes it.

There is no third case. A task that *has* a plan never reaches this subagent — Step 1b routed it
away — and `plan-generator` refuses one that arrives anyway rather than summarizing it, so the
lossy route cannot come back through a later edit to the fork.

`plan-generator` creates no branches. Branch isolation belongs to `/analyze`, which cuts a
worktree when it plans.

```yaml
task:
  id: "{TaskID}"
  title: "{title}"
  difficulty: "EASY|NORMAL|HARD"
  type: "{Bug|Feature|Refactor|Docs}"
  plan_source: "brief-only"

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

**The only phase in the main context**, and it opens differently on each route.

**Adopted path** — the plan is the brief:

1. Read the plan file the locator named. This is the one `.workflows` file the main context ever
   opens, and it is opened here and nowhere else.
2. Apply its steps in order. **The code blocks are complete by construction; use them** rather
   than re-deriving the change from the prose around them.
3. Run the plan's own **Verification** commands. A failing build or test is a failure, not a
   caveat.
4. Return the completion report.

A `--note` is applied on top of the plan and **never overrides it** — the same rule
`/implement` states for its own `-note`. If the note and the plan disagree, that is drift in the
request rather than in the tree: follow the plan and say so in the completion report.

**Brief path** — the brief is all there is:

1. Display the task summary from the brief
2. For each `target_file`: read, apply the steps, write
3. Run `test_command` if provided
4. Return the completion report

**On both routes the main context does NOT:** read `todos.md`, `package_readme.md` or
`analysis_report.md` · read documentation · update `todos.md` · run git · write plans.

```yaml
completion_report:
  task_id: "{TaskID}"
  status: "success|failure"
  plan_source: "adopted:{path}" | "brief-only"
  modified_files: ["{file}"]
  drift_notes: ["{if any}"]
  error_message: "{if failure}"
```

### Phase 3: Completion (Subagents 4 → 5 → 6)

#### Step 4: `completion-handler` (opus)

Marks the task complete in `todos.md` (`- [ ]` → `- [x]`, completion metadata, move to
**Completed Tasks**, update Quick Stats), updates `analysis_report.md` if a documented finding
was resolved, and — for a plan-set phase — ticks the phase in the plan index and unblocks the
next phase's task.

It also returns **the next session's command** — `/do {next TaskID}`, or the merge line when the
phase just completed was the last one. It is the only step in this pipeline that has read the plan
index, so the main context prints what it returns instead of deriving it; deriving it would mean
reading `todos.md` in the main context, which is the thing this pipeline exists to prevent.

Then dispatches:

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
| `session.py rename` | main context | nothing | the session's own name |
| `task-locator` | isolated | all `todos.md` | none |
| `context-loader` | isolated — brief path only | `todos.md`, docs | none |
| `plan-generator` | isolated — brief path only | nothing but its inputs | none |
| **Main context** | clean | target files, **and the adopted plan file** | target files only |
| `completion-handler` | isolated | `todos.md`, plan index | `todos.md`, plan index |
| `readme-updater` | isolated | `package_readme.md` | `package_readme.md` |
| `pusher` | isolated | `git diff` | git only |

**The main context never loads** `todos.md`, `package_readme.md` or `analysis_report.md`. It
reads **exactly one plan file — the adopted one — and no other `.workflows` file.**

That is the invariant stated precisely, not weakened. The rule exists to keep the main context
small while code is being edited, which is why it names the three background documents. A plan
file is not background: it is the instruction set for the edit, and the one thing the executor
cannot do its job without — `/implement` has read it in the main context all along. The narrower
reading, that the main context reads nothing at all and the brief must therefore carry
everything, is precisely what produced the summarization this fork removes.

Preserve the rest when editing the flow: don't move doc-reading or git into the main-context
step, and don't have subagents write code.

---

## Plan-Set Phase Tasks

A task carrying a `**Plan Set**:` field is one phase of a plan `/analyze` wrote. Three rules:

1. **Check `Depends on:` first.** If any prerequisite TaskID is incomplete, stop and name it.
   The phase's plan quotes code as it will look *after* the earlier phases land.
2. **Adopt the plan, never regenerate it.** Step 1b routes it to the main context directly, and
   no subagent stands between the plan and the code.
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

**Progress — brief path** (the task has no plan file):
```
🏷️  Session renamed: do-P1-DB-A236
🔍 Locating task... (task-locator)
📁 Found: P1-DB-A236 in db/.workflows/todos.md
📋 Loading context... (context-loader)
📋 Generating brief... (plan-generator)

🎯 Executing: P1-DB-A236 (main context)
  📄 manager.go → modify
✅ Implementation complete

📝 Completing... (completion-handler)
```

**Progress — adopted path** (the task carries a plan). Two fewer opus dispatches, and the line
says so out loud, because a silently shorter run reads like a step was skipped by accident:
```
🏷️  Session renamed: do-P1-TC-A002
🔍 Locating task... (task-locator)
📁 Found: P1-TC-A002 in tools/toolcore/.workflows/todos.md
📖 Adopting plan: .workflows/plan/P1-TC-A002.md  [context-loader + plan-generator skipped]

🎯 Executing: P1-TC-A002 (main context)
  📄 caller.go → modify
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

**Success — a plan-set phase with another phase to go.** End with the hand-off block, exactly as
`completion-handler` returned it, and print nothing after it:
```
✅ Task Completed: P1-TC-A001
📦 Package: toolcore
📄 Modified: caller.go, caller_test.go
📝 Updated: todos.md, PURGE_DIRECT_STREAMING_TOOL_PLAN.md
💾 Commit: abc1234
🌿 Branch: feature/purge-direct-streaming-tool

Next — phase 2 of 4, in a new session:

  cd ~/.worktrees/agentic/purge-direct-streaming-tool
  /do P1-TC-A002
```

**Success — the last phase of a plan set.** No next task exists, so the hand-off is the merge:
```
✅ Task Completed: P1-TC-A004
📦 Package: toolcore
🌿 Branch: feature/purge-direct-streaming-tool

Plan complete — 4/4 phases. Next, to review and merge:

  cd ~/.worktrees/agentic/purge-direct-streaming-tool
  git checkout main && git merge feature/purge-direct-streaming-tool
```

**A task that is not a plan-set phase prints no Next block.** There is no successor to name, and
guessing one would put a wrong command at the end of every EASY task.

Two rules for the block, wherever it appears: the command sits **alone on its own line** so it can
be selected and pasted, and **nothing follows it on that line** — a trailing `# comment` is read
as arguments to the slash command. `/implement` and `/analyze` print the same shape.

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
| `context-loader` | opus | load and synthesize context — **brief path only** |
| `plan-generator` | opus | execution brief for a task with no plan — **brief path only** |
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
