# Claude Commands Collection 🚀

A curated collection of custom Claude Code commands that supercharge your development workflow. These commands automate common git operations with intelligent analysis, semantic versioning, and comprehensive package documentation.

## 🛠️ Installation

Clone this repository and run the sync script to set up all commands and agents:

```bash
git clone https://github.com/miftahulmahfuzh/claude-commands.git
cd claude-commands
./sync.sh
```

The sync script will:
- ✅ Copy commands to `~/.claude/commands/`
- ✅ Copy agents to `~/.claude/agents/`
- ✅ Copy skills to `~/.claude/skills/`
- 🎉 Enable immediate use of all custom commands, agents, and skills

### Manual Installation

If you prefer manual setup:

```bash
# Create directories if needed
mkdir -p ~/.claude/commands ~/.claude/agents ~/.claude/skills

# Copy commands, agents, and skills
cp commands/* ~/.claude/commands/
cp agents/* ~/.claude/agents/
cp -r skills/* ~/.claude/skills/
```

## 📋 Available Commands

### Version Management

#### `/up-version` - Automated Semantic Versioning
Automates the entire version release process with intelligent semantic versioning and changelog generation.

**What it does:**
- 🏷️ Finds your latest version tag on main branch
- 📊 Analyzes all changes since the last release
- 📈 Determines appropriate version bump (major/minor/patch)
- 📝 Generates/updates CHANGELOG.md with categorized changes
- 🔀 Merges changes to main branch
- 🏷️ Creates and pushes new version tag
- 🔄 Returns you to your original branch

**Usage:**
```
/up-version
```

**Perfect for:**
- Release management
- Maintaining semantic versioning
- Automated changelog generation
- Professional project maintenance

---

### Code Analysis Commands

#### `/analyze` - Code Archaeology & Dataflow Tracing

Perform comprehensive code archaeology and dataflow tracing for bug investigation or feature implementation. Generates detailed analysis documents that serve as ground truth for implementation.

**What it does:**
- 🔍 **Traces dataflow** from entry points to exit points across entire codebase
- 📖 **Documents data transformations** at each step of processing
- 🗺️ **Maps dependency chains** by following function calls and struct definitions
- 🏗️ **Identifies implicit dependencies** (config, environment, database schema)
- 📊 **Generates structured analysis** with complete dataflow documentation
- 🎯 **Supports bug investigation** and feature implementation analysis
- 🔄 **Enables multi-session workflow** - analysis in one session, implementation in another

**Usage:**
```bash
/analyze <target> [bug|feature|update|refactor]

Context: <optional context or description>
Error: <optional error logs for bug investigation>
Note: <optional additional notes or constraints>

Files:
@file1.go
@file2.go
```

**Analysis Types:**
- `bug`: Bug investigation (errors, wrong behavior)
- `feature`: New requirements (new module, architecture, features)
- `update`: Feature update (struct changes, API breaking changes)
- `refactor`: Refactoring (major/minor changes, renaming, consolidation)

**Example - Bug Investigation:**
```bash
/analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: 2025-01-08 10:23:45 ERROR citation not found in response

Files:
@chatbot/processing/.workflows/analysis/citation_for_aggregation_mode.md
@tools/toolcore/caller.go
@tools/toolcore/pipeline/execution/modes.go
```

**Output:** Creates `<session-id>_code_analyzer.md` with complete dataflow documentation

**Perfect for:**
- **Bug Investigation**: Understanding dataflow to diagnose issues before fixing
- **Feature Implementation**: Mapping impact before making changes
- **Code Onboarding**: Learning how complex systems work
- **Architecture Reviews**: Documenting current state before refactoring
- **Multi-Session Work**: Analysis in one session, implementation in another (saves tokens)

---

#### `/implement` - Implementation from Analysis

Execute implementation based on `/analyze` output. Creates task, generates plan, and implements changes using **subagent-based architecture** for context isolation.

**What it does:**
- 📖 **Reads analysis file** from `/analyze` as ground truth
- 🎯 **Creates new task** in appropriate `.workflows/todos.md` with Type field
- 🤖 **Uses subagent for documentation work** (todos.md update + plan creation)
- 💻 **Main context ONLY does code implementation** (keeps context clean)
- 📋 **Generates implementation plan** with complete code changes (no placeholders)
- 🔧 **Executes implementation** following the plan
- 📝 **Updates documentation** and marks task complete
- 📊 **Auto-detects path** from analysis if not specified
- 🔄 **Preserves user context** from analysis (original request, requirements understanding)
- 📚 **Auto-refreshes package_readme.md** via a dedicated README Updater subagent (sonnet model) — locates the single most-impacted package and updates its `package_readme.md`. If none exists, automatically invokes `/update-readme` to create one (no manual bootstrap needed). Runs before the Pusher so README changes are committed together with code.

**Usage:**
```bash
/implement -f <code_analyzer.md> [-p <path>] [-note <additional note>]
```

**Arguments:**
- `-f`: Path to `<session-id>_code_analyzer.md` (required)
- `-p`: Path to directory containing `.workflows/` (optional - auto-detected from analysis)
- `-note`: Additional context/notes (optional)

**Example:**
```bash
/implement -f 20250108-164512-A3F7_code_analyzer.md -p tools/toolcore -note keep in mind query_user_portfolio has different output than stock_analysis
```

**Subagent Architecture:**
- **Steps 1-3**: Read analysis, determine path, generate TaskID (main context)
- **Steps 4-5**: Update todos.md + create implementation plan (subagent - isolated context)
- **Step 6**: Execute implementation (main context - clean, only code), then dispatch the **completion-handler** agent (shared with `/do`) which chains **readme-updater** (sonnet) and **pusher** (haiku) to finalize docs and commit code + README together

**Context Management Benefits:**
1. **Keeps main context clean**: Documentation work isolated in subagent
2. **Reduces token usage**: Main context only contains code implementation details
3. **Improves focus**: No documentation pollution during code changes
4. **Preserves handoff clarity**: Subagent returns structured output (TaskID, priority, title, plan path)

**Output:** Creates task in `{path}/.workflows/todos.md` + plan in `{path}/.workflows/plan/{TaskID}.md` + implements changes

**Perfect for:**
- **Implementing features** after `/analyze` gap analysis
- **Fixing bugs** after `/analyze` dataflow investigation
- **Token-efficient workflow**: analyze once, implement from condensed analysis
- **Bridging analysis to execution**: seamless handoff from investigation to implementation
- **Clean context during implementation**: documentation work isolated in subagent

**Key Features:**
- **Ground Truth Approach**: Trusts analysis completely - no redundant re-analysis
- **Complete Code Blocks**: Plans contain full functions/structs - NO placeholders
- **Auto-Path Detection**: Finds best `.workflows/` location from analysis file paths
- **User Notes Override**: Additional context takes precedence over analysis assumptions
- **Concise Plans**: Token-efficient - focuses on code changes, not verbose explanations
- **User Context Preservation**: Carries forward original request and technical understanding
- **Type-Aware Tasks**: Creates tasks with proper type classification (Bug/Feature/Update/Refactor)
- **Interactive Clarification**: Asks clarifying questions with recommendations when confused - never guesses
- **🤖 Subagent for Steps 4 & 5**: Documentation work delegated to subagent to keep main context clean for code implementation
- **💻 Main Context for Step 6 Only**: Pure code implementation in clean context - no documentation pollution

**Relationship with `/analyze`:**
```
/analyze → generates code_analyzer.md → /implement → reads analysis, creates task, implements
```

1. **`/analyze`** (Session 1): Explores codebase, documents dataflow, identifies gaps
2. **`/implement`** (Session 2): Reads analysis, creates task+plan via subagent, implements code in clean main context
3. **Benefit**: Analysis tokens thrown away after Session 1, Session 2 only pays for implementation with minimal context

**Prerequisites:**
- Requires `{path}/.workflows/todos.md` to exist
- If missing: Run `/update-todos {path} --init` first

**vs `/do` Command:**
- **`/implement`**: For NEW implementations based on `/analyze` output
  - Creates new task entry in todos.md
  - Generates plan from scratch
  - Reads from code_analyzer.md file
  - Use when: Starting new feature/bug fix after analysis

- **`/do`**: For executing EXISTING tasks from todos.md
  - Tasks already exist with TaskIDs
  - Direct execution of predefined work
  - Uses TaskID to locate tasks
  - Use when: Task already tracked in todos.md

---

### Task Execution Commands

#### `/do` - Execute Tasks by TaskID (Redesigned)

Execute tasks from any package's todos.md using TaskID. **Supporting work delegated to subagents; main context reserved for code implementation only.**

**Architecture Overview:**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Prep Phase     │    │  Main Context   │    │  Post Phase     │
│  (Sequential    │───▶│  (Code Only)    │───▶│  (Single        │
│   Subagents)    │    │                 │    │   Subagent)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Context Isolation:** All file reading, planning, and documentation updates happen in isolated subagent contexts. The main context ONLY performs code implementation.

**What it does:**
- 🔍 **Locates tasks** across all packages using TaskID
- 📋 **Loads task context** and relevant documentation (via subagents)
- 🔧 **Executes implementation** in clean main context (code only)
- 📝 **Updates documentation** and marks task complete (via subagent)
- ✅ **Moves completed tasks** to Completed Tasks section (via subagent)
- 📚 **Auto-refreshes package_readme.md** via a dedicated README Updater subagent (sonnet model) — updates the most-impacted package's `package_readme.md`, or auto-invokes `/update-readme` to create one if missing. Runs before the Pusher so README updates are committed with the code.

**Usage:**
```bash
/do P0-DB-A236
/do P1-CB-B789 --note="Add support for bulk operations"
```

**Subagent Pipeline:**

**Phase 1: Preparation (Subagents 1 → 2 → 3)**
- **Subagent 1: Task Locator** - Search all todos.md files, extract task metadata
- **Subagent 2: Context Loader** - Load docs, synthesize into concise context packet
- **Subagent 3: Plan Generator** - Create execution brief in YAML format

**Phase 2: Execution (Main Context)**
- Receive clean execution brief
- Load target files, apply changes, run tests
- Return completion report

**Phase 3: Completion (Subagent 4 + README Updater + Pusher)**
- Update todos.md (mark completed, move section)
- Update related files (analysis_report.md)
- Spawn **README Updater subagent** (sonnet) — refreshes the most-impacted `package_readme.md`, or auto-runs `/update-readme {package_path}` if no `package_readme.md` exists yet (engineers no longer need to bootstrap it manually in a separate session)
- Git operations via **Pusher subagent** (add, commit, push) — runs last so code + README updates are committed together
- Provide merge instructions for HARD tasks

**Token Efficiency:**
| Metric | Original | Redesigned | Improvement |
|--------|----------|------------|-------------|
| Context size before implementation | All docs + plans | Clean brief only | ~80% reduction |
| Context size during implementation | Same + file edits | Target files only | ~70% reduction |

**Perfect for:**
- Quick task execution without path specification
- **Clean context during implementation** - only target files in main context
- Safe handling of complex changes with automatic branching
- Streamlined workflow with automatic documentation updates
- Coordinated task management across packages

---

### Debugging Commands

#### `/dbg` - Go Debugger (Delve) Workflows

Drive the Go debugger (**Delve / `dlv`**) in **batch mode** to trace runtime behavior, instead of relying solely on server logs. This replaces the "paste logs → guess which `log.Debug` fired → infer dataflow statically" loop with **real runtime values**: actual call sequences, argument values, variable state, goroutine stacks, and post-mortem analysis.

**What it does:**
- 🔬 **Traces real dataflow** - prints every call to matching functions with arguments + return values (no code changes)
- 🎯 **Breakpoint-debugs tests** - batch command scripts (no interactive stepping loop), ideal for deterministic bugs
- 🪦 **Post-mortem analysis** - inspects a crashed/hung server's frozen state from a core dump (every variable in every goroutine, offline)
- 🧵 **Concurrency-aware** - built for a streaming HTTP server where breakpoints would freeze the server and cause heisenbugs

**Usage:**
```bash
/dbg <what you want to debug>

Context: <symptom / suspected area>
Error: <optional logs>
```

Claude then picks the right workflow and drives `dlv` for you.

**The three workflows (project-local helper scripts in `cmd/dlv/`):**

| Script | Purpose | Replaces |
|--------|---------|----------|
| `dlv_trace.sh` | Print every call to matching funcs with arg + return values | "which `log.Debug` fired?" archaeology |
| `dlv_test.sh` | Batch breakpoint-debug a single test (scripted, no ping-pong) | manual interactive stepping |
| `dlv_core.sh` | Post-mortem a crashed/hung server from a core dump | log forensics on live-server crashes |

**Example - trace a deterministic test:**
```bash
cmd/dlv/dlv_trace.sh --test 'finalizeResponse' ./chatbot/processing -- -test.run TestResume
```

**⚠️ Dependency - this command is different:** Unlike the other commands (which are self-contained markdown), `/dbg` drives **helper scripts that live in the target Go project**, not in this repo. `sync.sh` installs `dbg.md` to `~/.claude/commands/`, but the three `cmd/dlv/*.sh` scripts must exist in the project being debugged. See [**Go Debugging Workflow**](#go-debugging-workflow-with-dbg) below for setup.

**Prerequisites:**
- `dlv` **must be built with the same Go major version as the project toolchain** (e.g. Go 1.25.x emits DWARFv5; a `dlv` built with Go <1.25 cannot read it). Install/upgrade with:
  ```bash
  GOTOOLCHAIN=go1.25.7 go install github.com/go-delve/delve/cmd/dlv@latest
  ```

**Perfect for:**
- **Bug investigation** where logs don't tell the whole story (need actual variable values)
- **Concurrency bugs** in queue / cancellation / streamer code
- **Live-server crashes** - capture a core dump, analyze it offline like you'd analyze logs
- **Complementing `/analyze`** - `/analyze` reads code statically; `/dbg` confirms what *actually* happens at runtime

---

### Token-Maxxing Commands

A pair of commands for **deliberately high-token-consumption work sessions** that still land real, defensible value. Useful when you want to (a) drive up overall Claude usage on purpose, and (b) keep an achievement-first paper trail of the value each session delivered.

#### `/token-maxxing` - Start a Token-Maxxing Session

Kicks off a session by surveying the repo and pitching a ranked menu of genuinely useful things to work on — biased toward real value so the burn is always defensible, never busywork.

**What it does:**
- 🧠 **Recalls recent sessions** — spawns a fresh subagent to read the 5 most recent `docs/token_maxxing/` docs in full, splitting them into `completed` (don't re-propose) and `continuation-candidates` (open follow-ups / unmerged work worth continuing). Gives the workflow memory across days.
- 🔎 **Surveys the repo** (read-only) — recent commits, `.workflows/todos.md`, test-coverage gaps, stale docs, code smells
- 📋 **Proposes 3–5 ranked ideas**, each tagged **🆕 fresh** (new, non-colliding) or **🔁 continue/improve** (deepen a prior session), with what / why-it's-real-value / scope / 🔥 **burn potential** — aiming for a mix of both
- 🎛️ **Optional theme seed** — `/token-maxxing tests` biases the menu; bare = anything. Also supports `surprise me` and `reroll`
- 🌿 **Branches** `token-maxxing-YYYY-MM-DD` off `main` (one per day, reused) — work lands there, **never auto-merged** (review gate before `main`)
- 📝 **Auto-documents** — on completion it spawns a fresh subagent to run `/token-maxxing-update-docs`

**Usage:**
```bash
/token-maxxing              # propose anything
/token-maxxing tests        # bias toward test coverage
/token-maxxing refactor     # bias toward refactors
```

**Idea catalog** (variety source): refactor · test coverage · concurrency audit · docs rewrite · deep-dive teaching · gofmt + lint sweep · YAGNI hunt.

#### `/token-maxxing-update-docs` - Record the Session

Writes or updates a comprehensive, deliberately verbose session log — **achievement-first**, so a future reader sees the payoff at a glance.

**What it does:**
- 📅 Resolves the real date via `date +%F` (never guessed); derives a kebab-case title
- 🗂️ Writes `docs/token_maxxing/YYYY-MM-DD-<title>.md` (creates or updates; one per day)
- 🎯 **Achievement section always at the top** — goal, concrete changes, real value, branch, merge status, 🔥 burn estimate
- 📇 Maintains `docs/token_maxxing/README.md` as a newest-first index table

**Usage:**
```bash
/token-maxxing-update-docs              # auto-derive title from the session
/token-maxxing-update-docs queue-refactor   # explicit title override
```

> **Note:** These commands write into the **target project** (branch + `docs/token_maxxing/`), just like `/dbg` uses project-local scripts. The command files themselves are self-contained markdown, so `sync.sh` installs them like any other command — no extra setup.

---

## 🤖 Available Agents

### `pusher` - Git Commit & Push Agent

A specialized subagent for git commit and push operations using the fast, lightweight haiku model.

**What it does:**
- 🔍 Analyzes all your code changes using `git diff`
- 🧠 Generates intelligent commit messages following conventional commit format
- 📝 Categorizes changes (feat, fix, refactor, docs, etc.)
- 🚀 Stages, commits, and pushes everything in one operation
- ✨ Provides detailed summary of all operations

**Usage:**
In Claude Code, simply type:
```
run pusher
```
This will automatically spawn the Pusher subagent to commit and push all changes.

This agent is also invoked internally by other commands (like `/do` & `/implement`) at the end of implementation.

**Benefits:**
- Uses haiku model for fast, cost-effective operations
- Keeps main context clean by delegating git work
- Consistent commit message formatting

---

## 🧠 Available Skills

Skills live in `skills/<name>/SKILL.md` and are auto-discovered by Claude Code based on their `description` triggers. Most fire on their own from what you're doing; the task-tracking ones below are also directly invocable by name (`/task 14`, `/sync-todos-into-gitlab-board <file>`) because you usually know the card you want. Each skill is a directory so it can ship supporting assets (templates, scripts) alongside the guidance.

### `confluence-writer` - Paste Docs into Confluence Without Broken Formatting

Guidance for getting a document into Confluence with correct formatting, covering both Confluence **Server/Data Center** and **Cloud**.

**What it does:**
- 🎯 **Core trick:** render the doc as HTML → copy the *rendered* page from a browser → paste rich text into the editor (bypasses every markdown/wiki-markup converter)
- 🔎 **Detects the flavor** from the URL (`viewpage.action?pageId=` = Server/DC vs `/wiki/spaces/` = Cloud) and picks the right native importer as a fallback
- 🚑 **Fixes the common failures:** literal `##`/`|` from pasted markdown, and the `HTTP 500 / conf_wikimarkup_conversion_errors` from the flaky wiki-markup importer
- 📄 Ships `template.html` — a ready-to-adapt, clean-pasting HTML skeleton (headings, tables, panels, ASCII-diagram `<pre>`)

**When it triggers:** any time you're writing/publishing to Confluence, or a paste comes out mangled.

### `confluence-reader` - Read a Login-Walled Confluence Page (Text + Images)

The **read** counterpart to `confluence-writer`. When an agent can't open a Confluence link in a browser (a PRD/spec behind login), this pulls the page down via the REST API so the agent can actually read it.

**What it does:**
- 🎯 **Core trick:** hit `/rest/api/content` with the user's credentials → save the body as readable text **and** download every inline image as a local file the agent can `Read` (PDF/copy-paste both lose the images)
- 🔗 **Resolves any URL form** to a pageId: `/display/SPACE/Page`, `/pages/viewpage.action?pageId=`, tiny `/x/…` links, Cloud `/wiki/spaces/.../pages/<id>`, or a bare numeric id
- 🖼️ Body text carries `[IMG: images/<file>]` markers so you know where each screenshot sits in context; open only the ones that matter
- 🔐 **Credentials never touch the chat:** reads a `CONFLUENCE_PAT` (preferred), `CONFLUENCE_USER`/`CONFLUENCE_PASS`, or a git-ignored `~/.config/confluence-reader/credentials` file (`credentials.example` provided)
- 🐍 Ships `confluence_fetch.py` — **stdlib only, no `pip install`**; works on Confluence **Server/Data Center** and **Cloud**

**When it triggers:** any time you need to read a Confluence page/PRD that's behind login.

### `issue-ticket-reader` - Read a Jira Bug/Issue Ticket (Text + Screenshots + Video Frames)

The Jira counterpart to `confluence-reader`. When an agent is handed a ticket link it can't open, this pulls the **whole** ticket — not just the description, but the comment thread and attachments, which is usually where the actual bug report lives.

**What it does:**
- 🎯 **Core trick:** hit `/rest/api/2/issue/<KEY>?expand=renderedFields` with the user's credentials → description **plus every comment in thread order**, linked issues, subtasks, parent, labels/components/versions, as readable text
- 🔗 **Resolves any URL form** to an issue key: `/browse/KEY-123`, `?selectedIssue=KEY-123`, `/projects/X/issues/KEY-123`, Cloud `*.atlassian.net/browse/…`, or a bare `KEY-123` with `--base-url`
- 🖼️ Downloads **every attachment** locally; body text carries `[IMG: attachments/<file>]` markers mapped by attachment id, so screenshots are readable in the position they were embedded
- 🎬 **Attached videos → sampled JPEG frames** via ffmpeg (`--frames N`), timestamp in each filename (`frame_03_0012.50s.jpg`) — the only way an agent gets anything out of a screen recording
- 🔑 **Reuses the `confluence-reader` credentials** — Jira and Confluence normally sit behind one user directory, so if `confluence-reader` is set up this skill needs **zero** new setup (own `JIRA_PAT` / `~/.config/issue-ticket-reader/credentials` still take priority)
- 🧾 Extras: `--changelog` (who moved the status, when), `--all-fields` (non-empty custom fields with human names — Sprint, Story Points), `--no-attachments` for a fast text-only read
- 🐍 Ships `issue_fetch.py` — **stdlib only, no `pip install`**; works on Jira **Server/Data Center** (`api/2`, wiki markup) and **Cloud** (`api/3`, ADF)

**Honest limits, documented in the SKILL.md rather than discovered later:** video **audio is never transcribed** (no local speech-to-text), so a verbally-explained bug is not readable from frames alone; sparse frame sampling can miss a transient error toast (raise `--frames`); and pdf/xlsx attachments are downloaded but not converted.

**When it triggers:** any time you're pointed at a Jira ticket you need to actually read.

### `task` - Task Cards on GitHub Projects or GitLab Issues

Replaces keeping ideas in a notes app where Claude Code can't see them. Capture a
bug/feature/idea in a browser or on a phone, then `/task <id>` in a fresh session
fetches it, brainstorms it, writes the plan, links the plan path back onto the
card, and walks it **Open → In Progress → Completed**. Months later a bug goes in
as a comment, the card returns to Open, and round two starts from the newest
comment rather than the stale body.

**One loop, two backends,** chosen from the `origin` remote's host:

| | Personal repos | Work repos |
|---|---|---|
| Cards | GitHub Issues + a Projects board named `Tasks` | GitLab Issues (self-hosted) |
| Stage | the board's **Status** field | labels `status::open` / `status::in-progress` / `status::completed` |
| Kanban | one board spanning repos | one board **per project** (`board --ensure`) |
| Development | the skill runs the loop, in a **worktree off `origin/main`**, ending in a **PR** | mints a TaskID and hands off to **`/do`** |
| `Completed` | the linked PR is **merged** | the issue is **closed** |

**What it does:**
- 🎫 **Reads the whole card** — body **and every comment in order**. On a returning card the body is the original idea and the newest comment is the bug report; reading only the body is the main way this fails quietly
- 🔁 **Detects the round** from the plan block, so a second visit brainstorms only the delta
- 📝 **Links the plan** in a marker-delimited, append-only block in the issue **body**, not a comment (comments get buried under bug reports)
- 🚦 **Claims the card on fetch** — `/task 14` moves it to In Progress immediately, because running it *is* picking the card up and the board should say what's being worked on right now. If the session ends without proceeding, the skill moves it back to Open. Completed is reached only when the user says so **and** verification actually passed
- 🧼 **Three columns, no doubles** — `board --ensure` shapes the GitLab board as `status::open` | `status::in-progress` | **Closed**, hiding the backlog column that duplicates `status::open`. An *open* card with no stage label is then off the board, so `doctor` reports those under `hiddenFromBoard`
- 🔒 **On GitLab, Completed means the issue is closed** — measured, not chosen: a label list shows open issues only, so a completed card left open sat in the shared repo's issue list forever (the team saw **55 open issues**, 44 of them finished; now **11**). Closing empties a `status::completed` column, which is why the third column is GitLab's built-in Closed list. `effective_stage()` reads a closed issue as Completed whatever its labels say, or every sync would try to "fix" it forever. On GitHub the opposite rule still holds — never *left* closed, because Projects auto-archives closed items off the board, so the close a merged PR performs is undone by the next stage write
- 🌳 **GitHub work happens in a worktree, never the main checkout** — `worktree 14` fetches and branches `task/14-<slug>` off **`origin/main`** into `~/.worktrees/<repo>/`, cut *before* the plan file is written so the plan travels in the pull request. Round two gets its own branch (`-r2`), so round one's merged PR stays intact. `worktree 14 --remove` retires it, refusing a dirty tree without `--force`
- 🔗 **Every GitHub card ends in a linked PR** — `pr 14` pushes the branch, opens the PR with `Closes #14` as its first line, then **reads back from GitHub what it actually linked** and prints it. The closing keyword isn't cosmetic: the board's *Linked pull requests* column reads GitHub's issue↔PR link, and a bare `#14` is only a mention, which leaves the column empty. `links 14` answers "is the board really showing it?" from both the issue and the board field
- ✅ **`finish` makes Completed evidence-based** — it asks GitHub for a **merged** linked PR and exits non-zero if there is none, so a card can't reach Completed while its code is still in review. It then sets Status, comments with the merge commit, and reopens the issue the merge closed
- 🧮 **Owns the TaskID corpus** via `todos.py`: `scan`, `validate`, `mint`, `rename` over every `.workflows/todos.md`, with a rename ledger because TaskIDs appear in commit messages that can't be rewritten
- 🩺 `doctor` on either backend checks auth, scopes, board, labels and columns, and names the fix for whatever is missing

**Never *leaves* the issue closed.** On GitHub `Completed` is the stage only, because Projects auto-archives closed items and the reopen loop would fight the board's own automation. A linked PR does close the issue when merged — unavoidable, since the link is what populates the board column — so every stage write reopens it, in one function rather than remembered at each call site.

**Three things measured rather than assumed** (each broke something first): GitLab CE doesn't enforce scoped-label exclusivity, so a transition rewrites the whole label set in one call and verifies it; in `todos.md` the checkbox is the stage **only** under `## Active Tasks`, since the rolling summary and activity log record what was true at the time; and package codes aren't unique, so TaskID uniqueness is only ever checked on the whole id across every file.

**Layout:** `taskcore.py` (plan-block codec, stages, reference parsing — shared) · `task_gh.py` (gh CLI) · `task_gl.py` (GitLab REST via urllib, no `glab` needed) · `todos.py`. Every module has an offline `selftest` — no token, no network.

**Setup:** GitHub needs `gh auth refresh -s project,read:project` and the built-in **Linked pull requests** field added as a column in the board view (`doctor` reports whether it can see one, plus the worktree root — `TASK_WORKTREES` moves it); GitLab needs a PAT with the `api` scope in `~/.config/task-skill/gitlab` (no admin rights — it inherits your own permissions), then `labels --ensure` and `board --ensure` per project.

### `sync-todos-into-gitlab-board` - Mirror todos.md onto a GitLab Board

`/sync-todos-into-gitlab-board .workflows/todos.md` — one GitLab issue per live task, each landing in the board column its stage says. `todos.md` stays the source of truth for execution; the board is a window onto it, and each card says so and names `/do <TaskID>`.

**What it does:**
- 🆔 **One TaskID, one card — enforced.** Identity is read from **two** channels, the title prefix *and* the `- TaskID:` line in the card's source block, because a title edited in the browser would otherwise hide the card and the next run would create a second one. `audit` exits non-zero on any id held twice or any card claiming two ids, and `apply` **refuses to write** while either exists rather than compounding it — fixing a duplicate needs a human, since the skill won't guess which of two cards is the real one
- 🔁 **Re-running changes nothing** — a second run over an in-sync board reports every card unchanged, verified across 27 cards
- 🗂️ **Respects stages**: `- [ ]` → **Open**, `- [ ]` + `Status: in_progress` → **In Progress**, `- [x]` → **Completed**. The checkbox wins on done-ness (`Status:` is missing from 28 live entries) but `in_progress` is information the checkbox can't carry, and mapping it to Open would file started work as untouched
- 📚 **todos.md is primary, across two sections.** `/do` doesn't just tick the box — it *moves* the entry into `## Completed Tasks`, so a finished task lives there. Reading only `## Active Tasks` made a `/do`-completed task invisible and its card never moved. One exception: an unticked entry can't distinguish "untouched" from "a `/task` session is on it right now", so a card already **In Progress is left alone** rather than dragged back to Open
- 🛑 **Blast-radius guard**: `apply` refuses to create more than `--max-create` (default 10) issues at once unless `--yes` is passed — because widening what counts as a task once took a file from 26 entries to 55 and created 28 permanent cards in a shared repo with no warning
- 🧹 **Repairs non-canonical TaskIDs first**, split two ways: ones with an entry go to `todos.py rename` (deterministic, ~60 assertions, stamps `Former ID`, writes a ledger); ones surviving only as a bare reference in a log section get **one subagent each**, because there's no entry to rename and no single right answer
- 🚧 **`plan` is the default and writes nothing** — creating a GitLab issue needs **Owner** to delete and a Maintainer can only close, so the first run on a repo should be a small `--limit` pilot
- 🙅 **Won't clobber your notes**: a card body is only rewritten when the source marker is missing, or with explicit `--refresh-bodies`

**Ignores echoes.** A `todos.md` carries a rolling summary and an append-only activity log in which the same id repeats. Only entries under `## Active Tasks` become issues — the root file has **27 live entries and 28 echoes**, so missing this roughly doubles the issue count with permanent duplicates.

**Honest cost, documented rather than discovered:** a closed GitLab issue moves to the board's Closed column, out of `status::completed` — so finished work sits as an *open* issue carrying the completed label, which inflates the project's open-issue count. That's the price of a label board.

**When it triggers:** asking to sync/push/mirror a `todos.md` onto GitLab, or wondering why a task isn't on the board.

### `update-ats-cv` - Rebuild an ATS CV PDF, With the 1-Page Rule Enforced

`/update-ats-cv <input.pdf> <what to change>` — parses your existing CV for content **and** visual style, then redraws it from a `*.cv.yaml` content model. The input PDF is never patched, which is exactly what makes "shave 4pt off that one gap" and "extend Skills to the right margin" answerable requests instead of guesswork.

**What it does:**
- 📏 **The page count is an invariant, not a hope.** `--autofit` walks a ladder of (gap, leading, font) triples from loosest to tightest and takes the **first** rung that fits — so a short CV breathes and a long one tightens. If nothing fits it **exits non-zero** saying how many body lines are over, rather than silently spilling onto page 2
- 🎛️ **Every gap is a named token** (`sub_gap`, `head_rule`, `intro_bullets`, `entry_gap`…), so "the two degree lines are too far apart" maps to one number instead of a CSS hunt. Margins, leading, letter-spacing and column geometry are all addressable
- 🔍 **`cv_extract.py` identifies the typeface by advance-width matching**, because CV builders ship flattened PDFs (`iLovePDF`, Chrome print) where font names are stripped to `Type3` and bold is *faked* by overprinting glyphs twice. Width-matching found Lora at 0.65% error where the metadata said nothing
- 🤖 **ATS-correctness is verified, not assumed.** Text is emitted in **document order** — an earlier version batched glyphs by colour, which rendered pixel-identically but made a parser read every heading before any body text. Real Lora weights are used rather than synthetic bold, so extraction is clean
- 👀 **`cv_preview.py --against old.pdf`** builds a before/after sheet, because fit numbers can't show you a widow line or an orphaned heading
- 🧾 `SCHEMA.md` documents every tunable, plus the editing recipes for the asks that actually come up ("make Skills full width", "put Skills and Languages side by side")

**Honest limits:** letter-spacing is applied to headings only — it extracts fine, but there's no reason to risk it on the text an ATS indexes. The layout engine covers the section vocabulary of a standard one-column CV (summary, entries with bullets/sub-rows, column grids); a sidebar or two-column body would need new block types. It needs `pymupdf` + `pyyaml`, unlike the stdlib-only reader skills.

**When it triggers:** editing, restyling, retargeting or regenerating a CV/resume PDF.

---

## 🔄 Development Workflows

### Bug Investigation Workflow with `/analyze` + `/implement`

When you encounter a bug and need to understand the dataflow before fixing:

**Session 1: Analysis**
```bash
/analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: <paste error logs here>

Files:
@chatbot/processing/.workflows/analysis/citation_for_aggregation_mode.md
@tools/toolcore/caller.go
@tools/toolcore/pipeline/execution/modes.go

# Output: Analysis written to 20250108-164512-A3F7_code_analyzer.md
```

**Session 2: Implementation (with subagent architecture)**
```bash
/implement -f 20250108-164512-A3F7_code_analyzer.md -p chatbot/processing

# Automatically via subagent:
# - Creates task in chatbot/processing/.workflows/todos.md
# - Generates plan in chatbot/processing/.workflows/plan/{TaskID}.md

# Main context (clean):
# - Implements the fix based on plan
# - Only target files in context, no documentation pollution
```

**Key Benefits:**
- Session 1 tokens: Used for exploration, **thrown away** after
- Session 2 tokens: Main context has only code implementation details
- **Total tokens < single session** doing both analysis + implementation
- Subagent keeps documentation isolated from code implementation

---

### Go Debugging Workflow with `/dbg`

`/dbg` slots into the existing Go workflow as the **runtime-truth** step. Where `/analyze` reads the code statically and you currently paste server logs for Claude to trace, `/dbg` makes the program *show* what it does — actual call sequences, argument values, and goroutine state.

**Where it fits:**
```
Bug appears
│
├─ Need to understand the code paths?        → /analyze   (static dataflow map)
├─ Need to know what ACTUALLY happens?       → /dbg       (runtime values via Delve)
└─ Ready to fix it?                          → /implement (or /do)
```

**One-time setup per Go project:**

`/dbg` drives three helper scripts that live **inside the Go project** (committed there, alongside the code). Reference copies are vendored in this repo under [`cmd/dlv/`](cmd/dlv) — copy them into your project:

```bash
# From your Go project root (adjust the path to this repo):
cp -r ~/claude-commands/cmd/dlv cmd/dlv
chmod +x cmd/dlv/*.sh

# Make sure dlv matches your toolchain's Go version (DWARF compatibility):
GOTOOLCHAIN=go1.25.7 go install github.com/go-delve/delve/cmd/dlv@latest

# Optional: pre-allow the scripts in the project's .claude/settings.local.json
#   "Bash(dlv:*)", "Bash(cmd/dlv/dlv_trace.sh:*)",
#   "Bash(cmd/dlv/dlv_test.sh:*)", "Bash(cmd/dlv/dlv_core.sh:*)"
```

> Why project-local? The scripts run against the project's packages and test names, and they're committed alongside the code so the whole team shares the same debugging entry points. The `dbg.md` command (synced globally via `sync.sh`) is the reusable "how"; the `cmd/dlv/` scripts (copied per project) are the "what". The copies here are the canonical source — `sync.sh` does **not** install them, since they belong in the target project, not `~/.claude/`.

**Typical session - bug that logs can't explain:**
```bash
/dbg streamer drops Sources box on resume

Context: Sources box disappears only on the second resume
Error: <paste the misleading log line here>

# Claude reproduces it as a go test, then runs:
#   cmd/dlv/dlv_trace.sh --test 'finalizeResponse' ./chatbot/processing -- -test.run TestResume
# and reads the real call sequence + arg values, instead of guessing from logs.
```

**Live-server crash:**
```bash
# You capture a core dump like you'd capture logs:
ulimit -c unlimited; go build -o /tmp/agentic .
GOTRACEBACK=crash /tmp/agentic        # writes a core file on panic

/dbg analyze this core dump  (then hand over /tmp/agentic + the core file)
# Claude runs cmd/dlv/dlv_core.sh to inspect every goroutine's frozen state.
```

**Key Benefits:**
- **Runtime truth over inference** - real values, not best-guess reading of logs
- **No interactive token loop** - batch transcripts, analyzed in one pass
- **Concurrency-safe** - avoids freezing the streaming server / timing heisenbugs
- **Complements, not replaces** - pairs with `/analyze` (static) and `/implement` (fix)

---

### Task-Tracking Workflow with `/task`

The gap this fills: an idea arrives away from the keyboard, goes into a notes app,
and Claude Code never sees it. `/task` makes the browser the front door.

**Personal repos — the skill runs the whole loop:**

```bash
# In a browser (or the GitHub mobile app): + on the Tasks board's Open column.
# A draft item needs no repo at all — that's the "notes app" case.

/task 14                    # claims the card: moves to In Progress at once
                            # reads every comment, brainstorms
                            # on plan approval: cuts a worktree off origin/main,
                            # writes the plan into it, links it on the card
                            # — no prompt
                            # ... build in the worktree, commit ...
                            # opens a PR whose body says "Closes #14", so the
                            # board's Linked pull requests column shows it
                            # you merge; Completed only then, and only once
                            # verification actually passed
```

**Work repos that already have `.workflows/todos.md` — `/task` is the front door,
not a replacement:**

```
GitLab issue (browser/phone)
      │  /task 7
      ▼
brainstorm ─► mint a canonical TaskID into the right package's todos.md
      │       mirror the stage onto the card
      ▼
/do <TaskID>                 # the existing five-subagent pipeline, unchanged
```

That repo's 33 `todos.md` files and `/do` stay authoritative. `/task` adds the
browser-visible half; it does not re-implement the executor.

**Going the other way** — populate the board from work already tracked:

```bash
/sync-todos-into-gitlab-board .workflows/todos.md
# plan first (writes nothing), then apply. Active -> Open, in_progress ->
# In Progress, done -> Completed. Re-running is a no-op.
```

**Why the board never leads reality:** a card sits in `In Progress` only while
genuinely being worked, and reaches `Completed` only when the user says the work
is done *and* verification passed. A card in the wrong column is the one failure
this can't absorb, because you'd trust the board instead of re-reading the code.

---

## 🆚 `/implement` vs `/do`: When to Use Which

### Quick Decision Tree

```
Need to implement something?
│
├─ Is this a NEW feature/bug fix from `/analyze`?
│  └─ YES → Use `/implement -f <analysis_file>`
│           - Creates new task in todos.md
│           - Generates plan via subagent
│           - Implements in clean main context
│
└─ Is the task ALREADY in todos.md with TaskID?
   └─ YES → Use `/do <TaskID>`
            - Executes existing task via subagent pipeline
            - Main context does code implementation only
```

### Detailed Comparison

| Aspect | `/implement` | `/do` |
|--------|-------------|-------|
| **Input** | `<code_analyzer.md>` file | `<TaskID>` from todos.md |
| **Creates Task?** | ✅ YES - creates new task entry | ❌ NO - task already exists |
| **Creates Plan?** | ✅ YES - generates plan from analysis | ✅ YES - for HARD tasks only |
| **Use Case** | New implementations from analysis | Executing existing tasks |
| **Context** | Subagent for docs, main for code | 4 subagents (3 prep + 1 post), main for code |
| **Prerequisites** | Requires `todos.md` to exist | Requires task to exist in todos.md |

### Key Takeaway

- **`/implement`**: For **NEW** work that needs task creation + planning + implementation
- **`/do`**: For **EXISTING** tasks that are already tracked and planned

Both use **subagent architecture** to keep main context clean for code implementation only.

---

## 🎯 Why Use These Commands?

### Code Analysis Commands
- **🔍 Objective Documentation**: Pure dataflow documentation without suggestions or opinions
- **📚 Complete Understanding**: Recursive exploration follows all dependencies automatically
- **🎯 Ground Truth for Implementation**: Analysis serves as foundation for bug fixes and features
- **💰 Token Efficient**: Multi-session workflow separates analysis from implementation
- **🏗️ Architecture Awareness**: Documents implicit dependencies (config, environment, schema)
- **🔄 Multi-Session Support**: Analysis in one session, `/implement` in another saves tokens
- **🌉 Seamless Bridge**: `/implement` automatically creates tasks and plans from analysis output
- **📋 Complete Code Blocks**: Implementation plans contain full functions - NO placeholders
- **🎯 Trust the Analysis**: `/implement` uses analysis as ground truth - no redundant work
- **📝 User Context Preservation**: Original request and technical understanding carried forward
- **🏷️ Type-Aware Analysis**: Supports bug, feature, update, and refactor analysis types
- **❓ Interactive Clarification**: `/implement` asks questions with recommendations when confused - never guesses

### Task Management Commands
- **🎯 Precise**: Execute tasks using unique TaskID without path specification
- **🔄 Automated**: Updates documentation and task status automatically
- **📋 Context-Aware**: Loads all relevant information for task execution (via subagents)
- **⚡ Efficient**: No need to manually locate tasks or update multiple files
- **🆔 TaskID System**: Automatic unique ID generation with priority-based ordering
- **🤖 Subagent Architecture**: All supporting work (search, load, plan, docs, git) isolated in subagents
- **💻 Clean Main Context**: Reserved for code implementation only - no documentation pollution
- **📊 Token Efficiency**: 70-80% context reduction during implementation
- **🔧 Difficulty-Aware**: Adapts execution workflow based on task complexity (EASY/NORMAL/HARD)
- **🌿 Branch Management**: Automatic branch creation for HARD tasks with isolation

### All Commands
- **🛡️ Safe**: Includes comprehensive error handling and validation
- **🔄 Workflow-Aware**: Designed for real development workflows
- **⚙️ Customizable**: Easy to modify for your project's needs

---

## 📁 Project Structure

This repository is organized as follows:

```
claude-commands/
├── commands/              # Slash commands for Claude Code
│   ├── analyze.md         # Code archaeology & dataflow tracing
│   ├── analyze-package.md # Package documentation generator
│   ├── dbg.md             # Go debugger (Delve) batch workflows
│   ├── do.md              # Execute tasks by TaskID
│   ├── implement.md       # Implementation from analysis
│   ├── postmortem.md      # Session problem documentation
│   ├── reorganize-todos.md# Reorganize todos by priority
│   ├── token-maxxing.md   # Start a high-token-consumption session (real-value ideas menu)
│   ├── token-maxxing-update-docs.md # Record the session (achievement-first doc + index)
│   ├── update-readme.md   # Update package README
│   ├── update-todos.md    # Update todos.md
│   └── up-version.md      # Semantic versioning automation
├── agents/                # Specialized subagents
│   └── pusher.md          # Git commit & push (haiku model)
├── skills/                # Auto-discovered skills (each a directory with SKILL.md)
│   ├── confluence-writer/ # Paste docs into Confluence without broken formatting
│   │   ├── SKILL.md       # When-to-use triggers + method + gotchas
│   │   └── template.html  # Clean-pasting HTML skeleton
│   ├── confluence-reader/ # Read a login-walled Confluence page (text + images)
│   │   ├── SKILL.md       # When-to-use triggers + method + gotchas
│   │   ├── confluence_fetch.py  # Stdlib fetcher: URL/pageId -> text + images
│   │   └── credentials.example  # Credentials-file template (PAT or user/pass)
│   ├── issue-ticket-reader/ # Read a Jira ticket (text + comments + attachments)
│   │   ├── SKILL.md       # When-to-use triggers + method + documented limits
│   │   ├── issue_fetch.py # Stdlib fetcher: URL/KEY -> text, images, video frames
│   │   └── credentials.example  # Jira creds template (falls back to confluence-reader's)
│   ├── task/              # Task cards on GitHub Projects or GitLab Issues
│   │   ├── SKILL.md       # The loop: resolve -> brainstorm -> plan -> stages
│   │   ├── DESIGN.md      # Decisions and the alternatives that were rejected
│   │   ├── taskcore.py    # Shared: plan-block codec, stages, reference parsing
│   │   ├── task_gh.py     # GitHub Issues + Projects v2, via the gh CLI
│   │   ├── task_gl.py     # GitLab Issues, via REST + urllib (no glab needed)
│   │   └── todos.py       # The .workflows/todos.md corpus: scan/validate/mint/rename
│   ├── sync-todos-into-gitlab-board/  # Mirror a todos.md onto a GitLab board
│   │   ├── SKILL.md       # Repair -> plan -> apply, and the stage mapping
│   │   └── sync_todos.py  # Idempotent sync; imports the task skill's modules
│   └── update-ats-cv/     # Rebuild an ATS CV PDF from a YAML content model
│       ├── SKILL.md       # Workflow + hard rules (1-page invariant, verify by looking)
│       ├── SCHEMA.md      # Every cv.yaml key: page, theme, the vertical gap map
│       ├── cv_render.py   # The layout engine: cv.yaml -> PDF, with --autofit
│       ├── cv_extract.py  # Source PDF -> spans, rules, text + typeface identification
│       ├── cv_preview.py  # PDF -> PNG, and the before/after comparison sheet
│       └── assets/fonts/  # Vendored Lora 400/500/600/700 + italics (SIL OFL)
├── cmd/
│   └── dlv/               # Delve helper scripts for /dbg (copy into your Go project)
│       ├── dlv_trace.sh   # Call + arg/return tracing
│       ├── dlv_test.sh    # Batch breakpoint-debug a test
│       └── dlv_core.sh    # Post-mortem core-dump analysis
├── sync.sh                # Sync script for installation (commands + agents + skills)
└── README.md
```

After using package documentation commands, your project will have this structure:

```
your-project/
├── chatbot/
│   └── bowl/
│       ├── .workflows/
│       │   ├── package_readme.md       # Technical documentation
│       │   ├── analysis_report.md      # Code quality analysis
│       │   ├── todos.md                # Task tracking
│       │   ├── postmortem/             # Problem documentation
│       │   │   ├── P1-CB-A123.md       # Postmortem for specific bug fix
│       │   │   ├── P0-CB-A456.md       # Postmortem for critical issue
│       │   │   └── P2-CB-B789.md       # Postmortem for feature implementation
│       │   ├── plan/                   # Implementation plans
│       │   │   ├── P1-CB-A123.md       # Detailed plan for task
│       │   │   └── ...
│       │   ├── unittest_guide.md       # (if exists) Test documentation
│       │   └── benchmark_analysis.md   # (if exists) Performance data
│       ├── bowl.go
│       ├── manager.go
│       └── ...
├── 20250108-164512-A3F7_code_analyzer.md    # Code archaeology analysis
└── ...
```

The `.workflows/` directory keeps all package-level documentation organized and separate from source code.

---

## 💡 Best Practices

### For Code Analysis (`/analyze`)
- **Before Fixing Bugs**: Always run `/analyze` to understand dataflow before making changes
- **Before Features**: Use `/analyze` for gap analysis to map impact points
- **Multi-Session Work**: Split complex tasks - analyze in Session 1, implement in Session 2
- **Objective Mode**: Remember that `/analyze` documents WHAT exists, not WHAT SHOULD BE
- **Provide Context**: Include error messages, notes, and constraints for better analysis

### For Task Management
- Use `/implement` for NEW work from `/analyze` output
- Use `/do` for EXISTING tasks in todos.md
- Let subagents handle all documentation and git operations
- Main context should ONLY do code implementation

### For Debugging (`/dbg`)
- **Reproduce first**: turn the bug into a focused `go test`, then debug the test - deterministic and fast
- **Trace before breakpointing**: `dlv_trace.sh` (call + arg values) often reveals the cause without a single breakpoint
- **Keep `dlv` in sync**: rebuild it whenever your project's Go major version changes (DWARF compatibility)
- **Live crashes → core dumps**: hand Claude a core file the way you'd hand it logs - far richer state
- **Commit the `cmd/dlv/` scripts**: they're project-local entry points the whole team shares

---

## 🤝 Contributing

Found a bug or have an idea for a new command? Contributions are welcome!

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/amazing-command`)
3. Test your changes thoroughly
4. Commit your changes (`git commit -m 'feat: add amazing new command'`)
5. Push to the branch (`git push origin feature/amazing-command`)
6. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](https://mit-license.org).

---

## 🙏 Acknowledgments

- Built for [Claude Code](https://claude.ai/code) by Anthropic
- Inspired by the need for smarter development workflows
- Powered by AI-driven code analysis

---

*Happy coding! 🎉*
