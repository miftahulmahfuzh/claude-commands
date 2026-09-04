# Do Command - Execute Tasks by TaskID

Execute a task from any package's `todos.md` by TaskID. Supporting work is delegated to
subagents; **the main context does code implementation only**.

Like `/implement`, `/do` **does not write implementation plans**. It adopts the plan `/analyze`
wrote, or works from the task description for small tasks. Anything big enough to need a plan
**gets one by running `/analyze` itself** — not by printing the command and stopping.

**A task that carries a plan file takes the adopted path** (Step 1b): the main context reads that
plan and applies it, and neither `context-loader` nor `plan-generator` runs. Only a task with no
plan goes through the brief pipeline.

## Autonomy: this command never waits for a human

A TaskID is handed to `/do` to be **finished**, not to be discussed. From the id to a pushed
commit the session decides everything itself: what an ambiguous line on the card meant, which of
two contradicting sentences in an adopted plan wins, what to do when a test fails in a way the
plan never anticipated. It is written to run at 1am inside a swarm with nobody awake, because
that is when it runs.

The rule that makes that true:

> **Never end a turn with a question this command needs answered to continue.**

Not "ask sparingly" — never. The arithmetic is one-sided:

| | What it costs |
|---|---|
| A decision that turns out wrong | one follow-up commit, or one `/analyze` re-plan — both of which this workflow already handles by design |
| A question asked into an empty room | every hour until someone wakes up, and no code at all |

MEASURED on `nina-character-tuning`: the phase-2 session found its plan's invariant 2 and its
ladder prose contradicting each other, asked with `AskUserQuestion`, and held the prompt for
**eight hours**. Phases 3 and 4 both depend on 2, so a six-phase set built nothing overnight —
and the answer that finally arrived was `invariant 2 wins`, which is rung 1 of the ladder below
and was derivable from the plan in under a minute.

So, concretely:

- **Do not use `AskUserQuestion`**, and do not end a message with "which should I do?",
  "shall I proceed?", `Continue anyway? [y/N]`, or a list of options for someone to pick from.
- **Do not ask permission for what this command already says to do** — locating the task,
  escalating a HARD task to `/analyze` (Step 1c says so out loud), applying the plan, running
  verification, dispatching `completion-handler`, `readme-updater` and `pusher`. Running `/do`
  *is* the authorisation for all of it.
- **Keep the shell unattended too.** No interactive git (`GIT_EDITOR=true`, `--no-edit`, never
  `-i`), no pager (`--no-pager`), and pass the yes-flag to anything that would otherwise prompt.
  A command blocked on stdin is the same outage with no question attached.
- **Decide with the ladder in [Deciding Without Asking](#deciding-without-asking), then write the
  decision down** in `completion_report.decisions`. A recorded decision is reviewable over
  breakfast and costs one commit to overturn; a waiting prompt is reviewable never.

The user can interrupt at any moment, and that is their steering: always available, always
obeyed. What is removed is this command's *requirement* for it.

**Stopping is allowed; blocking is not.** A stop ends the session cleanly — the task left in a
truthful state, the reason printed in a Next block, the swarm told (Step 7), the work on disk
surviving. A block is a live session holding an unanswered question and building nothing. Every
terminating branch in this file is a stop; there are no blocks.

## Arguments
- Required: `{TaskID}` (e.g. `P0-DB-A236`, `P1-CB-B789`)
- Optional: `--note="{additional instructions}"`
- Optional: `--no-escalate` — on a HARD task with no plan, print the `/analyze` command and stop
  instead of running it. Escalation is the default (Step 1c); this is the way out of it, and the
  only way out.

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
python3 ~/.claude/skills/task/session.py rename "do-P1-DB-A236" --no-widen
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

### Phase 1: Preparation (Subagent 1, then one of three routes)

All preparation happens in isolated subagent contexts. **Which route is taken is decided by the
locator's output** — the plan file first, then the difficulty — see Step 1b.

#### Step 1: Locate Task — `task-locator` (haiku)

**Input:** `task_id`

Searches every `.workflows/todos.md` for the TaskID, validates that exactly one matches,
extracts the package path from the file location and the task's metadata.

```yaml
status: success
package_path: "{path}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"       # HARD if the line says HARD anywhere
  difficulty_line: "{the **Difficulty**: line, verbatim}"
  type: "Bug|Feature|Refactor|Docs"
  title: "{title}"
  context: "{context}"
  plan_file: "{path or empty}"
  depends_on: ["{TaskID}"]
  depends_on_incomplete: ["{TaskID}"]
```

#### Step 1b: Fork on the Plan File (Main Context)

One check, on the locator's output, and it chooses the whole rest of Phase 1:

| `plan_file` | `difficulty` | Route | What runs |
|---|---|---|---|
| non-empty | any | **adopted path** | nothing else in Phase 1 — straight to Phase 2 with the path |
| empty | EASY, NORMAL | **brief path** | Step 2 and Step 3, below |
| empty | HARD | **escalation** | Step 1c — `/analyze`, and no subagent in between |

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

**Difficulty never overrides a plan that exists.** A HARD task cannot reach the adopted path
without a plan, because the path is defined by the plan existing; and a HARD task that *has* one
is an ordinary adopted-path run, not an escalation. Difficulty only decides which of the two
plan-less routes is taken.

#### Step 1c: Escalate a HARD Task With No Plan (Main Context)

A HARD task with no plan is the case that needs a plan. `/do` does not write one — so it **runs
the command that does**, here, before any other subagent is dispatched:

```
⤴ P1-TP-A023 is HARD and has no plan file. Escalating to /analyze.
  Difficulty read as: {task_metadata.difficulty_line}
  /do writes no plans, so it is running the command that does. Nothing else about this
  task has been touched.
```

Then invoke the `/analyze` slash command, with the locator's fields as its arguments:

```
/analyze {package_path} {bug|feature|update|refactor, from task_metadata.type}

Escalated from /do {TaskID} — HARD, no plan file.

{task_metadata.title}

{task_metadata.context, verbatim}

This card is the deliverable. Plan against it, and treat {TaskID} in
{package_path}/.workflows/todos.md as the origin card the plan set supersedes.
```

**Let it run per its own spec, and do not ask the user first.** `/analyze` is the full unattended
workflow: it cuts a worktree, writes the plan set, and — orchestration being its default —
launches the run itself. So the escalation is not a handoff back to a human with a command to
paste, it is the work continuing. The one exception is `--no-escalate`, which prints the command
and stops.

**Nothing of `/do`'s own pipeline runs after this.** No `context-loader`, no `plan-generator`, no
`completion-handler`, no `pusher`: the analyze run owns the task from here, and the phases it
creates are executed by `/implement`, each carrying its own plan. Escalating *before* the two
opus subagents is the whole point — dispatching them to reach a refusal spends two opus calls to
learn what the locator's `difficulty` and `plan_file` already said.

**An ambiguous difficulty line escalates.** A card whose `**Difficulty**:` reads
`NORMAL to fix, HARD to decide` is a card saying the deciding is the hard part, which is planning
work — so any `**Difficulty**:` line containing HARD takes this route, and the banner quotes the
literal line so the user can see what it read. Planning something that turns out easy costs a
worktree; brief-pathing something that turns out hard costs a wrong change in the main context
with no analysis behind it.

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
   the case that needs one, and this is not the command that writes it. This is now a backstop:
   Step 1c escalates such a task before this subagent is dispatched, so reaching it means the
   fork was skipped — the main context takes the returned error to Step 1c rather than to the
   user.

Neither case is a dead end for the user. A task that *has* a plan never reaches this subagent —
Step 1b routed it away — and `plan-generator` refuses one that arrives anyway rather than
summarizing it, so the lossy route cannot come back through a later edit to the fork.

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

Anything the plan leaves ambiguous is settled here, by the ladder in **Deciding Without
Asking**, and never by a question — this is the phase where the eight-hour stall happened.

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
  decisions: ["{fork} → {choice} ({the rung that decided it})"]
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

#### Step 7: Report to the Swarm (Main Context, only if there is one)

A phase run by an orchestrator has a session waiting on it. Report in **both** halves, in this
order — the file is the record, the message is the notification, and doing only one leaves either
a silent coordinator or a set nobody can resume:

```bash
python3 ~/.claude/skills/swarm/swarm.py find --plan <the plan file this task used>
```

`{"swarm": false, ...}` means this task belongs to no swarm — say nothing, do nothing, done. Every
`swarm.py` read exits 0 when there is no ledger, so an ordinary task is never affected by any of
this.

Otherwise `find` returns the `slug`, the `phase`, the `coordinator` to address and the `peers`:

```bash
python3 ~/.claude/skills/swarm/swarm.py report --slug <slug> --phase <N> \
    --status done --commit <sha from pusher> --task <TaskID> --note "<one line>"
```

Check that name is still in `ListAgents` first. Session names are mutable and reused —
one listed as `agentic-golang-30` renamed itself to `analyze-carry-similarity-branch` a
minute later — so a name read earlier can deliver this report to an unrelated session. If
the coordinator is gone, the ledger write above already recorded the outcome: say so and
stop.

then `SendMessage` the coordinator — `DONE`, the TaskID, the commit, and one line on what
actually changed. Report `failed` the same way, with the reason: a coordinator that is told a
phase failed can strand its dependents deliberately, while one left guessing stalls the whole set.

**Mesh messages** go to peers directly, and only these: `READY` when an Interface Contract item
a dependent is waiting on now exists, `NEED` before assuming a dependency landed, `WARN` before
deleting a worktree or branch a peer is sitting in. A message states a fact and never delegates
work — "I deleted `SortRows`" is a mesh message; "please delete `SortRows` for me" is not, and
asking a peer to do what this session could not is permission laundering.

This step runs **after** `pusher`, because the commit sha is part of the report and an unpushed
commit is not something another machine can resume from.

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
| report | main | `swarm.py find` output only | the swarm ledger, one message |

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

Status `blocked` is **not** a question to put to the user. It is a claim to check against the one
piece of evidence the locator already returned, `depends_on_incomplete`:

- **Non-empty** → stop and name the blocker. The dependency is real; the plan quotes code as it
  will look after that TaskID lands, and applying it first produces conflicts that read like
  drift.
- **Empty** → the status is stale bookkeeping from before the prerequisites landed. **Proceed**,
  and say so in one line: `Status reads blocked; depends_on all complete — proceeding.`
  `completion-handler` corrects the status as part of completing the task.

A `blocked` status with no incomplete dependency and nobody awake is exactly the shape of stall
this command refuses: the answer is derivable, so derive it.

## Drift

If the real code no longer matches what an adopted plan quotes, the rule is `/implement`'s:
small drift → follow the plan's intent and note it; large drift → stop and say
`Re-run /analyze to re-plan against the current tree.`

Neither branch is a question. "Small or large?" is itself a decision this session makes: a moved
line, a renamed local, an added field the plan does not touch → small. A function that is gone, a
changed signature, a restructured file → large. When the two readings are genuinely balanced,
**treat it as large and stop** — re-planning costs one `/analyze`, while applying a plan to a tree
it no longer describes costs a wrong change with the plan's authority behind it.

---

## Deciding Without Asking

Every case below used to be a question. All of them are now decisions this session makes,
states, and records:

- the adopted plan's intent is ambiguous at a specific step
- **two parts of the plan contradict each other**
- the task's **Context** and its plan disagree
- `--note` and the plan disagree
- applying a step would touch code outside the task's stated scope
- the test command fails for a reason nothing in the plan anticipated
- the task reads `blocked` but nothing incomplete blocks it

### The precedence ladder

Read down; **the first rung that speaks to the question decides it.** This is the order in which
the plan's parts were written and reconciled, so a higher rung survived more scrutiny. It is the
same ladder `/implement` states — a phase planned by `/analyze` and executed here must be decided
identically whichever command picks it up.

1. **A stated invariant**, in the adopted plan or its plan index. Invariants are what
   `plan-reconciler` held constant across every phase; prose is what one `phase-planner` wrote
   alone, blind to the others. When an invariant and a paragraph disagree, **the invariant wins
   and the prose is the stale half.**
2. **The plan's exit criteria**, or the brief's `success_criteria` — the published definition of
   done.
3. **The plan's code blocks.** Complete by construction and reconciled; the prose around them is
   commentary on them.
4. **The plan index's Why and Requirements table**, for a plan-set phase — the `R` this phase
   **Satisfies** outranks an incidental sentence about how.
5. **The task text** in `todos.md` (as the locator returned it), then `--note`, which never
   overrides the plan.
6. **The surrounding code's existing convention** — last rung, and the usual one on the brief
   path, where there is no plan above it.

### Tie-break rules, when the ladder runs out

- **Take the reversible option.** Prefer what a follow-up commit can undo over what rewrites a
  migration, drops a column, or rewrites published history.
- **Take the narrower blast radius.** A change inside the task's stated scope beats an equivalent
  change outside it, even when the outside one is tidier.
- **Never widen scope to settle an ambiguity** — that is drift, and the Drift rule above applies.
- **A failing test is never settled by relaxing the check.** Fix the code, or stop. Never delete
  a test, loosen an assertion, or drop a guard to make a task report success.
- **Between "do less" and "do more", do exactly what the success criteria demand.**

### Record it, or it did not happen

Recording is what makes deciding cheap, and it costs no waiting:

1. **Print it when you make it**, one line:
   `⚖ Decided: {the fork} → {choice}. Rung {n}: {the invariant/criterion that decided it}.`
2. **Carry it in `completion_report.decisions`**, so `completion-handler` writes it into
   `todos.md` and `pusher` puts it in the commit body — the artefacts that outlive this window.
3. **Leave it where the choice is not self-evident** — one comment in the code naming the rung
   that forced it, so the next reader does not re-litigate it.
4. **If it is a swarm phase, put it in the ledger `--note`** (Step 7), where the coordinator and
   every later phase can see it.

### The one thing that still stops — and it is a stop, not a question

If a fork is genuinely undecidable *and* every branch is irreversible — destroying data,
rewriting published history, an unrepeatable migration — do not ask and do not wait. Land and
push whatever already verified, report `failed` to the swarm with the fork in one line (Step 7),
and print the **Undecidable** block from the Messages section. A session that exits with a report
lets its coordinator strand the dependents deliberately or re-plan; a session holding a prompt
strands them silently and indefinitely.

Reach for it only when the ladder has genuinely nothing to say. Rung 1 usually does.

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

**Progress — escalation** (HARD, no plan file). One haiku call, then the command that plans:
```
🏷️  Session renamed: do-P1-TP-A023
🔍 Locating task... (task-locator)
📁 Found: P1-TP-A023 in tools/toolpicker/.workflows/todos.md — no plan file

⤴ P1-TP-A023 is HARD and has no plan file. Escalating to /analyze.
  Difficulty read as: **Difficulty**: NORMAL to fix, HARD to decide
  /do writes no plans, so it is running the command that does. Nothing else about
  this task has been touched.

▶ /analyze tools/toolpicker bug
```
Nothing after that line belongs to `/do`; what the user watches from there is `/analyze`.

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

✗ HARD task P1-BC-A123 has no plan file.        (--no-escalate only)
  /do does not write implementation plans. Run /analyze first,
  then /implement -f <SLUG>_PLAN.md — the plan index, never the
  <session-id>_code_analyzer.md, which /implement refuses.
  Without --no-escalate this is not an error: Step 1c runs /analyze itself.

✗ P1-TC-A002 depends on P1-TC-A001 (phase 1), which is not complete.
```

**Undecidable** (rare — every branch irreversible, see *Deciding Without Asking*):
```
✗ P1-NIN-A001 stopped at an irreversible fork. Not asking; reporting.
  The fork: {one line}
  Ladder consulted: invariants, exit criteria, code blocks, Why — none of them decide it.
  Every branch is irreversible: {why}
  Landed and pushed: {commit(s), or "nothing"}
  Swarm: reported failed to {coordinator}

Next — decide it and re-plan against the current tree, in a new session:

  cd {worktree}
  /analyze {package_path} {type} — re-planning {TaskID}: {the fork}
```
The session is over when this prints. It is a stop, not a prompt: nothing waits for input, and
the swarm has already been told.

**A decision the ladder produced is printed where it is made, and again on success:**
```
⚖ Decided: anger ceiling at band `off` — 0 vs 4 → 4. Rung 1: plan invariant 2
  ("the shipped ladder renders byte for byte") outranks the ceiling prose.
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
