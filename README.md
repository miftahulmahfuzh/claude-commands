# Claude Commands Collection 🚀

A curated collection of custom Claude Code commands that supercharge your development workflow. These commands automate common git operations with intelligent analysis, semantic versioning, and comprehensive package documentation.

## 🛠️ Installation

Clone this repository and run the installation script to set up all commands:

```bash
git clone https://github.com/miftahulmahfuzh/claude-commands.git
cd claude-commands
./install.sh
```

The installation script will:
- ✅ Create a symlink from `~/.claude/commands` to this repository
- 📦 Backup any existing commands directory
- 🔗 Keep your commands in sync with this git repository
- 🎉 Enable immediate use of all custom commands

### Manual Installation

If you prefer manual setup:

```bash
# Backup existing commands (if any)
mv ~/.claude/commands ~/.claude/commands.backup

# Create symlink to this repository
ln -s /path/to/claude-commands ~/.claude/commands
```

## 📋 Available Commands

### Git Workflow Commands

#### `/push` - Intelligent Git Workflow Automation
Streamlines your entire git commit and push process with AI-powered commit message generation.

**What it does:**
- 🔍 Analyzes all your code changes using `git diff`
- 🧠 Generates intelligent commit messages following conventional commit format
- 📝 Categorizes changes (feat, fix, refactor, docs, etc.)
- 🚀 Stages, commits, and pushes everything in one command
- ✨ Provides detailed summary of all operations

**Usage:**
```
/push
```

**Perfect for:**
- Quick commits with meaningful messages
- Following consistent commit conventions
- Understanding the impact of your changes
- Streamlined development workflow

---

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

**Example - Feature Implementation:**
```bash
/analyze query_user_portfolio feature

Context: I want to implement stock extractor for query_user_portfolio tool.
The output format is different than concept_sector_search - it has stock codes
in Holding Stock array instead of items.stock_codes.

Current payload:
{
  "Holding Stock": [
    {"Stock Code": "BBRI", "Stock Average Price": 5000, ...},
    {"Stock Code": "BBCA", "Stock Average Price": 10000, ...}
  ]
}

New requirement: Extract stock codes from Holding Stock array.

Files:
@tools/toolcore/.workflows/plan/P2-TC-A063.md
@tools/toolbe/query_user_portfolio.go
@tools/toolutils/query_user_portfolio.go
```

**Output:** Creates `<session-id>_code_analyzer.md` with:
- **User Input**: Your original request, context, errors, and notes (preserved verbatim)
- **Detailed Requirements Understanding**: Claude's technical interpretation of your problem/requirements
- **Analysis Scope**: Explicitly mentioned files + discovered related files
- **Current Dataflow**: Entry points → Processing chain → Exit points
- **Key Data Structures**: Struct definitions with locations and usage
- **Dependencies**: Configuration, environment, external services
- **Gap Analysis** (for features): What exists vs what's missing
- **Impact Points**: Files that will need changes

**Perfect for:**
- **Bug Investigation**: Understanding dataflow to diagnose issues before fixing
- **Feature Implementation**: Mapping impact before making changes
- **Code Onboarding**: Learning how complex systems work
- **Architecture Reviews**: Documenting current state before refactoring
- **Multi-Session Work**: Analysis in one session, implementation in another (saves tokens)

**Key Features:**
- **Objective Observer Mode**: Does NOT suggest improvements or propose implementations
- **Recursive Exploration**: Follows function calls, struct definitions, imports automatically
- **Complete Documentation**: Shows actual line numbers and file paths
- **No Opinions**: Pure documentation of what exists, not what should be
- **Token Efficient**: Analysis tokens thrown away after, implementation uses condensed analysis

**Session ID Format:** `YYYYMMDD-HHMMSS-A3F7` (timestamp + 4-char random suffix)

---

#### `/implement` - Implementation from Analysis

Execute implementation based on `/analyze` output. Creates task, generates plan, and implements changes in one streamlined workflow.

**What it does:**
- 📖 **Reads analysis file** from `/analyze` as ground truth
- 🎯 **Creates new task** in appropriate `.workflows/todos.md` with Type field
- 📋 **Generates implementation plan** with complete code changes (no placeholders)
- 🔧 **Executes implementation** following the plan
- 📝 **Updates documentation** and marks task complete
- 📊 **Auto-detects path** from analysis if not specified
- 🔄 **Preserves user context** from analysis (original request, requirements understanding)

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

**Output:** Creates task in `{path}/.workflows/todos.md` + plan in `{path}/.workflows/plan/{TaskID}.md` + implements changes

**Perfect for:**
- **Implementing features** after `/analyze` gap analysis
- **Fixing bugs** after `/analyze` dataflow investigation
- **Token-efficient workflow**: analyze once, implement from condensed analysis
- **Bridging analysis to execution**: seamless handoff from investigation to implementation

**Key Features:**
- **Ground Truth Approach**: Trusts analysis completely - no redundant re-analysis
- **Complete Code Blocks**: Plans contain full functions/structs - NO placeholders
- **Auto-Path Detection**: Finds best `.workflows/` location from analysis file paths
- **User Notes Override**: Additional context takes precedence over analysis assumptions
- **Concise Plans**: Token-efficient - focuses on code changes, not verbose explanations
- **User Context Preservation**: Carries forward original request and technical understanding
- **Type-Aware Tasks**: Creates tasks with proper type classification (Bug/Feature/Update/Refactor)

**Relationship with `/analyze`:**
```
/analyze → generates code_analyzer.md → /implement → reads analysis, creates task, implements
```

1. **`/analyze`** (Session 1): Explores codebase, documents dataflow, identifies gaps
2. **`/implement`** (Session 2): Reads analysis, creates task+plan, implements
3. **Benefit**: Analysis tokens thrown away after Session 1, Session 2 only pays for implementation

**Prerequisites:**
- Requires `{path}/.workflows/todos.md` to exist
- If missing: Run `/update-todos {path} --init` first

**vs `/do` Command:**
- **`/implement`**: For NEW implementations based on `/analyze` output
  - Creates new task entry in todos.md
  - Generates implementation plan from scratch
  - Reads from code_analyzer.md file
  - Use when: Starting new feature/bug fix after analysis

- **`/do`**: For executing EXISTING tasks from todos.md
  - Tasks already exist with TaskIDs
  - Direct execution of predefined work
  - Uses TaskID to locate tasks
  - Use when: Task already tracked in todos.md

**Workflow Comparison:**
```bash
# Workflow 1: New feature from analysis (use /implement)
/analyze my_feature feature         # Session 1: Analyze
# (session ends - save tokens)
/implement -f 20250108-164512-A3F7_code_analyzer.md  # Session 2: Implement

# Workflow 2: Existing task execution (use /do)
/update-todos mypackage --init      # Generate tasks
/do P1-MP-A236                      # Execute specific task
```

---

### Package Documentation Commands

These commands provide comprehensive package analysis and documentation for Go projects, creating a complete picture of your codebase architecture, quality, and task tracking.

#### `/update-readme` - Generate Comprehensive Package Documentation

Creates detailed technical documentation for any Go package, analyzing its API surface, dependencies, architecture, and usage patterns.

**What it does:**
- 📦 Analyzes all source files in the package (excluding tests)
- 🔍 Documents exported API surface (types, functions, constants)
- 🏗️ Maps internal architecture and data flow
- 🔗 Identifies forward and reverse dependencies
- ⚡ Analyzes concurrency model and thread-safety
- 🚨 Documents error handling patterns
- 📊 References performance characteristics from benchmarks
- 💡 Provides usage patterns and gotchas
- 🔄 Updates existing documentation to reflect current state

**Usage:**
```
/update-readme chatbot/bowl
/update-readme tools/toolcore
```

**Output:** Creates `{directory_path}/.workflows/package_readme.md`

**Perfect for:**
- Onboarding new developers
- Understanding complex packages
- Maintaining up-to-date documentation
- API design reviews
- Architecture documentation

---

#### `/analyze-package` - Deep Code Quality Analysis

Performs comprehensive static analysis to identify code quality issues, performance bottlenecks, dead code, and refactoring opportunities.

**What it does:**
- 🧮 Calculates cyclomatic complexity for all functions
- 🔍 Identifies exported but unused functions (dead code)
- 🚨 Audits error handling patterns and missing checks
- ⚠️ Detects concurrency risks (race conditions, deadlocks)
- 📈 Identifies performance concerns (allocations, lock contention)
- 🔄 Finds duplicate logic and god functions
- 📊 Cross-references with benchmark data if available
- 🎯 Prioritizes issues by severity

**Prerequisites:**
- Requires `package_readme.md` to exist (run `/update-readme` first)

**Usage:**
```
/analyze-package chatbot/bowl
/analyze-package core/db
```

**Output:** Creates `{directory_path}/.workflows/analysis_report.md`

**Perfect for:**
- Code review preparation
- Identifying technical debt
- Performance optimization planning
- Refactoring prioritization
- Catching bugs before production

---

#### `/update-todos` - Intelligent Task Tracking

Maintains a comprehensive, automatically-updated task list for each package based on git changes, code analysis, and existing documentation.

**What it does:**
- 📝 Tracks completed, added, and ongoing tasks
- 🔍 Analyzes git commits to identify changes
- 🐛 Extracts TODO/FIXME/HACK comments from code
- 📊 Imports issues from analysis_report.md
- 🏷️ Assigns priority levels (P0-P4) based on severity
- ⏰ Timestamps all changes with commit references
- 📦 Maintains task history and archives
- 🔄 Tracks task lifecycle from identification to completion
- 🔍 **TaskID Coverage Enforcement**: Ensures ALL existing tasks (active, completed, and archived) have TaskIDs
- 📋 **Completed Tasks Separation**: Organizes completed tasks in simple list (no time divisions)
- 📦 **Archive Management**: Maintains Archive section in single-line compressed format
- 🔄 **Package Code Override**: Change package codes and migrate all TaskIDs automatically

**Prerequisites:**
- Requires `package_readme.md` to exist (run `/update-readme` first)
- Enhanced with `analysis_report.md` if available

**Usage:**

**During active session (after making changes):**
```
/update-todos chatbot/bowl
```

**After commits (retroactive update):**
```
/update-todos chatbot/bowl --since=abc123f
/update-todos chatbot/bowl --since=HEAD~5
```

**Initial setup:**
```
/update-todos chatbot/bowl --init
```

**Package code override (change package code and migrate TaskIDs):**
```
/update-todos chatbot/bowl --package-code=CB
```

**Package Code Override Feature:**
- **Purpose**: Change the package code and automatically migrate all existing TaskIDs
- **Use Cases**:
  - Fixing incorrect package codes
  - Standardizing package codes across projects
  - Resolving package code conflicts
- **Behavior**:
  - Updates Package Code in todos.md header
  - Migrates all existing TaskIDs to use new package code
  - Maintains task priorities and 4CharID identifiers
  - Updates all cross-references and links
- **Example**: Changes `P1-OLD-A123` → `P1-NEW-A123` for all tasks

**Output:** Creates/updates `{directory_path}/.workflows/todos.md` with organized structure:

- **Active Tasks**: Only incomplete tasks, organized by priority (P0-P4)
- **Completed Tasks**: Simple list of completed tasks (no time divisions)
- **Archive**: Single-line compressed format `{TaskID}: {description}`
- **Quick Stats**: Task counts including completed tasks metrics
- **Recent Activity**: Detailed log of recent changes and completions

**Perfect for:**
- Sprint planning and tracking
- Bug tracking and prioritization
- Refactoring task management
- Team coordination
- Project status visibility
- Maintaining clean separation between active and completed work

**Troubleshooting:**
- If `/update-todos` fails to generate TaskIDs for existing tasks
- If `/update-todos` doesn't move completed tasks to Completed Tasks section
- Run `/reorganize-todos <package-dir>` to clean up TaskID coverage and organization

---

#### `/reorganize-todos` - TaskID, Organization & Archive Cleanup

Cleans up and reorganizes existing todos.md by ensuring complete TaskID coverage, proper task organization, and archive management.

**What it does:**
- 🏷️ **TaskID Coverage**: Ensures EVERY task (active and completed) has a unique TaskID
- 📋 **Task Organization**: Properly separates active and completed tasks
- 🔍 **Deep Scan**: Scans ENTIRE Active Tasks section for ANY checkmarked tasks
- ✅ **Complete Migration**: Moves ALL checkmarked tasks to Completed Tasks section
- 📦 **80% Archive Rule**: Compresses oldest 80% of completed tasks to Archives section
- 🗜️ **Single-Line Format**: Archives tasks as `{TaskID}: {description}` for compact display
- 🧹 **Workflow Files Cleanup**: Removes related plan/analysis/postmortem files for archived tasks
- 📊 **Stats Update**: Recalculates and updates Quick Stats with completion and archive metrics
- 🔍 **Clean Validation**: Verifies ZERO checkmarked tasks remain in Active Tasks section

**Usage:**
```bash
/reorganize-todos chatbot/bowl
/reorganize-todos core/db
```

**Prerequisites:**
- Requires existing `.workflows/todos.md` file
- Run `/update-todos <package> --init` if todos.md doesn't exist
- Complete some tasks before running reorganize-todos

**Perfect for:**
- Cleaning up tasks missing TaskIDs
- Moving completed tasks that accumulated in Active Tasks section
- Periodic maintenance (weekly/monthly) to archive old tasks
- Cleaning up workflow files for completed work
- Pre-task-execution cleanup
- Keeping todos.md file clean and readable

**Key Features:**
- **Focused Responsibility**: Handles TaskID generation, organization cleanup, and archive management
- **No Analysis**: Doesn't analyze code or git changes - just reorganizes existing content
- **Simple and Reliable**: Clear, predictable behavior every time
- **Complete Coverage**: Ensures ALL tasks have TaskIDs, no exceptions
- **Clean Separation**: Guarantees Active Tasks only contains incomplete work
- **80/20 Rule**: Archives section contains 80% oldest tasks, Completed Tasks shows 20% most recent
- **Automatic Cleanup**: Finds and removes workflow files matching archived TaskIDs

**Archive Behavior:**
- Searches all `.workflows/` directories for markdown files containing archived TaskIDs
- Removes files like: `plan-{task-id}.md`, `analysis-{task-id}.md`, `postmortem-{task-id}.md`
- Compresses archived tasks to single-line format: `{TaskID}: {description}`
- Keeps most recent 20% of completed tasks visible with full metadata

**Output Messages:**
```
✅ Reorganized todos.md successfully
  - {N} tasks received new TaskIDs
  - {N} completed tasks moved to Completed Tasks section
  - {N} tasks archived (80% rule applied)
  - {N} workflow files cleaned up
  - Active Tasks now contains only {count} active tasks
  - Quick Stats updated with completion and archive metrics
```

---

#### `/postmortem` - Session Problem Documentation

Generate detailed postmortem reports for bugs/errors encountered during Claude Code sessions, with automatic TaskID detection and Go-inspired structured documentation.

**What it does:**
- 🔍 **Session Analysis**: Automatically analyzes current Claude Code session for problems and solutions
- 🆔 **TaskID Detection**: Detects TaskID from session or creates new task with user confirmation
- 📝 **Go-Inspired Reports**: Generates comprehensive postmortem reports following Go documentation best practices
- 📁 **Smart Organization**: Creates reports in `.workflows/postmortem/<TaskID>.md` with proper directory structure
- 🔄 **Update Logic**: Handles existing postmortem files (updates for recurring issues)
- 🎯 **Direct Mode**: Supports `--id` parameter for explicit TaskID specification
- 🔗 **Cross-Reference Integration**: Links with existing todos.md and .workflows documentation

**Usage:**
```bash
# Automatic session analysis and TaskID detection
/postmortem

# Document specific task solution
/postmortem --id=P1-CL-A017

# With additional context
/postmortem --id=P2-DB-A236 --note="Race condition in goroutine synchronization"
```

**Output:** Creates/updates `{package_path}/.workflows/postmortem/{TaskID}.md`

**Go-Inspired Postmortem Structure:**
- **Executive Summary**: Problem overview and resolution summary
- **Timeline**: Discovery, investigation, and resolution timestamps
- **Problem Analysis**: Root cause analysis with technical details
- **Impact Assessment**: Severity and scope evaluation
- **Resolution Details**: Implementation with code examples and test cases
- **Prevention Measures**: Immediate and long-term prevention strategies
- **Lessons Learned**: Technical and process insights
- **Follow-up Actions**: Actionable next steps with tracking

**Perfect for:**
- Documenting bug fixes after vibecoding sessions
- Knowledge management and team learning
- Root cause analysis and prevention planning
- Recurring issue tracking and pattern identification
- Building comprehensive problem-solving documentation

**Key Features:**
- **Automatic TaskID Detection**: Finds TaskID from session context or creates new tasks
- **Interactive Task Creation**: Proposes task location when no TaskID exists
- **Uniqueness Validation**: Ensures TaskID uniqueness across entire codebase
- **Recurring Issue Handling**: Updates existing postmortems for repeated problems
- **Multi-Package Support**: Handles issues affecting multiple packages
- **Go Best Practices**: Follows Go documentation patterns and conventions

---

### Task Execution Commands

#### `/do` - Execute Tasks by TaskID

Execute tasks from any package's todos.md using unique TaskID without needing to specify package paths.

**TaskID Format**: `Priority-PackageCode-4CharID` (e.g., `P0-DB-A236`, `P1-CB-B789`)

**How TaskIDs are Generated:**
- Automatically assigned when you run `/update-todos` on a package
- Priority levels (P0-P4) are assigned based on issue severity:
  - **P0**: Critical bugs, security issues, blocking failures
  - **P1**: High priority bugs, important features
  - **P2**: Medium priority tasks, documentation updates
  - **P3**: Low priority improvements, nice-to-haves
  - **P4**: Backlog tasks, future considerations
- Package codes are 2-3 letter identifiers (e.g., DB=Database, CB=Chatbot Bowl, CC=Core Commands)
- 4CharID is a unique alphanumeric identifier within the package
- Package codes can be changed using `/update-todos --package-code=<NEW_CODE>` with automatic TaskID migration

**🔧 Difficulty Classification System:**

All tasks include a **Difficulty field** (EASY/NORMAL/HARD) that determines execution workflow:

- **EASY**: Simple, isolated changes with minimal impact and low error risk
  - Example: Fix typos, simple validation, small documentation updates
  - Workflow: Direct execution on current branch

- **NORMAL**: Moderate complexity changes with limited scope
  - Example: Feature additions, API changes with backward compatibility
  - Workflow: Standard execution with context loading

- **HARD**: Complex, high-impact changes requiring extensive planning
  - Example: Major refactoring, breaking API changes, architecture redesign
  - Workflow: Automatic branch creation + detailed planning + user confirmation

**HARD Task Special Workflow:**
```bash
/do P1-BC-A123  # If Difficulty: HARD
```

**Automatic HARD Task Process:**
1. 🔒 **Branch Creation**: Automatically creates `feature/{task-description-slug}-{TaskID}`
2. 📋 **Detailed Planning**: Generates comprehensive implementation plan with:
   - Current state assessment and risk analysis
   - Step-by-step implementation phases
   - Rollback strategy with safe rollback points
3. 💾 **Plan Persistence**: Automatically saves detailed plan to `.workflows/{TaskID}-plan.md` for:
   - Permanent documentation and reference
   - Consistency during implementation
   - Review and audit trail
4. 🤔 **User Confirmation**: Presents plan and waits for explicit approval
5. 🔧 **Implementation**: Executes task on dedicated branch following the saved plan
6. 🔀 **Branch Management**: Branch ready for review and merge after completion

**Difficulty Assessment Criteria:**
- **Impact Scope**: How many parts of codebase are affected?
- **Change Complexity**: Algorithm complexity and implementation difficulty
- **Error Susceptibility**: Risk level and criticality of potential failures
- **External Dependencies**: Impact on code that calls this package
- **Testing Requirements**: Level of testing needed (unit/integration/regression)

**Usage:**
```bash
# Execute specific task
/do P0-DB-A236

# Execute with additional instructions
/do P1-CB-B789 --note="Add support for bulk operations"

# Execute HARD task (automatic branch creation + planning)
/do P1-BC-A123

# Execute all P0 tasks across all packages
/do --all-p0

# Execute all tasks for specific package
/do --package=chatbot/bowl --all
```

**What it does:**
- 🔍 Locates tasks across all packages using TaskID
- 📋 Loads task context and relevant documentation
- 🔧 **Difficulty-based execution**: Adapts workflow based on task complexity
- 🌿 **HARD task branch management**: Automatic branch creation and isolation
- 📝 Updates all .workflows files and marks task complete
- ✅ Moves completed tasks to Completed Tasks section in todos.md
- 📊 Updates task statistics and completion metrics

**Perfect for:**
- Quick task execution without path specification
- **Safe handling of complex changes** with automatic branching
- Streamlined workflow with automatic documentation updates
- Coordinated task management across packages
- **Risk-aware development** with difficulty-based workflows

---

## 🔄 Development Workflows

### Bug Investigation Workflow with `/analyze` + `/implement`

When you encounter a bug and need to understand the dataflow before fixing:

**Session 1: Analysis**
```bash
# Step 1: Run code analysis to understand the bug
/analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: <paste error logs here>

Files:
@chatbot/processing/.workflows/analysis/citation_for_aggregation_mode.md
@tools/toolcore/caller.go
@tools/toolcore/pipeline/execution/modes.go

# Output: Analysis written to 20250108-164512-A3F7_code_analyzer.md
# Token count: ~8500
# Ready for implementation phase.
```

**Session 2: Implementation**
```bash
# Step 2: Implement the fix using /implement
/implement -f 20250108-164512-A3F7_code_analyzer.md -p chatbot/processing

# Automatically:
# - Creates task in chatbot/processing/.workflows/todos.md
# - Generates plan in chatbot/processing/.workflows/plan/{TaskID}.md
# - Implements the fix based on analysis

# Step 3: Document the fix
/postmortem --id=P1-PE-A234 --note="Citation wrapping fix in aggregation mode"
```

---

### Feature Implementation Workflow with `/analyze` + `/implement`

When implementing a new feature and need to map impact before coding:

**Session 1: Analysis**
```bash
# Step 1: Analyze current implementation
/analyze query_user_portfolio feature

Context: I want to implement stock extractor for query_user_portfolio tool.
The output format is different than concept_sector_search.

Current payload:
{
  "Holding Stock": [
    {"Stock Code": "BBRI", "Stock Average Price": 5000, ...}
  ]
}

Files:
@tools/toolcore/.workflows/plan/P2-TC-A063.md
@tools/toolbe/query_user_portfolio.go
@tools/toolutils/query_user_portfolio.go

# Output: Analysis written to 20250108-171234-B8F2_code_analyzer.md
# Token count: ~12000
# Ready for implementation phase.
```

**Session 2: Implementation**
```bash
# Step 2: Implement the feature using /implement
/implement -f 20250108-171234-B8F2_code_analyzer.md

# Automatically:
# - Creates task in tools/toolcore/.workflows/todos.md
# - Generates plan with complete code changes
# - Implements the stock extractor
# - Updates all affected files

# Step 3: Test and validate
# Run tests, verify stock codes are extracted...

# Step 4: Document the implementation
/postmortem --id=P2-TC-A456 --note="Stock extractor for query_user_portfolio"
```

---

### Multi-Session Workflow (Token Management)

For complex features, split analysis and implementation across sessions for maximum token efficiency:

**Session 1: Analysis (Code Archaeology)**
```bash
/analyze stock_selection feature

Context: Need to add fast-path stock extraction for stock_selection tool.

Files:
@tools/toolcore/.workflows/plan/P2-TC-A063.md
@tools/nonbe/stock_selection.go
@tools/toolcore/pipeline/execution/tool.go
```

**Session terminates after analysis.**
- Tokens used: ~15,000 (exploration, documentation)
- Output: `20250108-173045-C1D3_code_analyzer.md`
- **Analysis tokens discarded - save costs**

**Session 2: Implementation (using `/implement`)**
```bash
# Start new session - condensed analysis as input
/implement -f 20250108-173045-C1D3_code_analyzer.md

# The agent has complete context from analysis without exploration cost
# Tokens used: ~8,000 (implementation only)
# Total: ~23,000 tokens vs ~30,000+ for single session
```

**Key Benefits:**
- Session 1 tokens: Used for exploration, **thrown away** after
- Session 2 tokens: Used for implementation, with condensed analysis as input
- **Total tokens < single session** doing both analysis + implementation
- Clean separation: archaeology vs implementation
- `/implement` bridges the gap automatically

---

### Before Refactoring Workflow

Use `/analyze` to document current state before making changes:

```bash
# Step 1: Document current architecture
/analyze pipeline_execution feature

Context: Planning to refactor pipeline execution for better performance.
Need to document current state before changes.

Files:
@tools/toolcore/pipeline/execution/tool.go
@tools/toolcore/pipeline/execution/step.go
@tools/toolcore/pipeline/execution/modes.go

# Step 2: Review analysis to understand:
# - Current dataflow through pipeline
# - Dependencies between components
# - Implicit dependencies (config, environment)
# - Impact points for refactoring

# Step 3: Create refactoring plan
# Based on complete understanding from analysis...

# Step 4: Implement refactoring
# Make changes...

# Step 5: Verify behavior hasn't changed
# Use analysis as "before" reference
```

---

## 🆚 `/implement` vs `/do`: When to Use Which

### Quick Decision Tree

```
Need to implement something?
│
├─ Is this a NEW feature/bug fix from `/analyze`?
│  └─ YES → Use `/implement -f <analysis_file>`
│           - Creates new task in todos.md
│           - Generates implementation plan
│           - Executes implementation
│
└─ Is the task ALREADY in todos.md with TaskID?
   └─ YES → Use `/do <TaskID>`
            - Executes existing task
            - Task already documented and planned
```

### Detailed Comparison

| Aspect | `/implement` | `/do` |
|--------|-------------|-------|
| **Input** | `<code_analyzer.md>` file | `<TaskID>` from todos.md |
| **Creates Task?** | ✅ YES - creates new task entry | ❌ NO - task already exists |
| **Creates Plan?** | ✅ YES - generates plan from analysis | ✅ YES - for HARD tasks only |
| **Use Case** | New implementations from analysis | Executing existing tasks |
| **Prerequisites** | Requires `todos.md` to exist | Requires task to exist in todos.md |
| **Session Flow** | After `/analyze` completes | After `/update-todos` creates tasks |
| **Path Detection** | Auto-detects from analysis | Searches all todos.md files |
| **User Notes** | Optional `-note` parameter | Optional `--note` parameter |

### Workflow Examples

**Example 1: New Feature (Use `/implement`)**
```bash
# Session 1: Analyze
/analyze stock_extractor feature
# Output: 20250108-164512-A3F7_code_analyzer.md

# Session 2: Implement
/implement -f 20250108-164512-A3F7_code_analyzer.md
# ✅ Creates new task P2-TC-A123 in todos.md
# ✅ Generates plan in .workflows/plan/P2-TC-A123.md
# ✅ Implements the feature
```

**Example 2: Existing Task (Use `/do`)**
```bash
# Task already exists from previous /update-todos
/do P2-TC-A123
# ✅ Finds task in todos.md
# ✅ Loads existing context
# ✅ Executes the task
# ✅ Marks as completed
```

**Example 3: After Analysis, Choose Wisely**
```bash
# Scenario: You ran /analyze and got the analysis file
/implement -f 20250108-164512-A3F7_code_analyzer.md
# ✅ Correct! This creates task + plan + implements

# Scenario: Someone already created the task in todos.md
/do P1-TC-A456
# ✅ Correct! Just execute the existing task

# ❌ WRONG: Using /do when you should use /implement
/do P1-TC-A999  # Task doesn't exist yet!
# ✅ RIGHT: Use /implement to create the task first
/implement -f 20250108-164512-A3F7_code_analyzer.md
```

### Key Takeaway

- **`/implement`**: For **NEW** work that needs task creation + planning + implementation
- **`/do`**: For **EXISTING** tasks that are already tracked and planned

When in doubt: Check if the task exists in todos.md first. If yes → `/do`. If no → `/implement`.

---

## 🔄 Package Documentation Workflow

The package documentation commands work together in a specific sequence to provide comprehensive package analysis with automated TaskID tracking:

### 1️⃣ Initial Setup Workflow

For a new package or first-time documentation:

```bash
# Step 1: Generate package documentation
/update-readme chatbot/bowl

# Step 2: Perform deep analysis
/analyze-package chatbot/bowl

# Step 3: Initialize task tracking with automatic TaskID generation
/update-todos chatbot/bowl --init

# Optional: Change package code and migrate all TaskIDs
/update-todos chatbot/bowl --package-code=CB
```

**Result:** Complete documentation suite in `chatbot/bowl/.workflows/`:
- `package_readme.md` - Technical documentation
- `analysis_report.md` - Code quality analysis
- `todos.md` - Task tracking with generated TaskIDs and organized sections:
  - Active Tasks (P0-P4 priorities)
  - Completed Tasks (simple list)
  - Archive (single-line compressed format)
  - Quick Stats with completion metrics

---

### 2️⃣ Active Development Workflow

During a coding session when making changes:

```bash
# Make your code changes
# ... coding ...

# Update task tracker with what you did (generates new TaskIDs)
/update-todos chatbot/bowl

# Execute specific tasks using TaskIDs (no path needed!)
/do P1-CB-A234  # Fix the race condition found in analysis
/do P2-CB-A235  # Update documentation for new API

# If you made significant changes, update docs
/update-readme chatbot/bowl
```

---

### 3️⃣ Post-Commit Workflow

After pushing changes to remote:

```bash
# Update todos based on recent commits (generates new TaskIDs for discovered issues)
/update-todos chatbot/bowl --since=HEAD~3

# Execute newly identified tasks using TaskIDs
/do P0-CB-A456  # Fix critical issues found in post-commit analysis
/do P1-CB-A457  # Address high priority tasks

# Document the bug fixes with postmortem reports
/postmortem --id=P0-CB-A456 --note="Critical race condition fix"
/postmortem --id=P1-CB-A457

# Regenerate analysis if major refactoring occurred
/analyze-package chatbot/bowl

# Update documentation if API changed
/update-readme chatbot/bowl
```

---

### 4️⃣ Maintenance Workflow

Periodic maintenance (weekly/monthly):

```bash
# Regenerate analysis to catch accumulated issues
/analyze-package chatbot/bowl

# Update todos based on new analysis findings (generates maintenance TaskIDs)
/update-todos chatbot/bowl

# Execute maintenance tasks using TaskIDs
/do P2-CB-B123  # Fix medium priority issues found in maintenance
/do P3-CB-B124  # Address low priority improvements

# Document maintenance fixes for knowledge sharing
/postmortem --id=P2-CB-B123 --note="Maintenance performance optimization"
/postmortem --id=P3-CB-B124 --note="Code quality improvement"

# Verify documentation is current
/update-readme chatbot/bowl

# Clean up and archive old completed tasks (80% rule + workflow files cleanup)
/reorganize-todos chatbot/bowl
```

---

### 5️⃣ Code Review Workflow

Before submitting PR or during code review:

```bash
# Get fresh analysis report
/analyze-package chatbot/bowl

# Review critical issues in analysis_report.md
# Address P0/P1 issues identified using TaskIDs
/do P0-CB-X001  # Fix critical race condition
/do P0-CB-X002  # Address security vulnerability

# Update todos with review findings (generates review-related TaskIDs)
/update-todos chatbot/bowl

# Execute review cleanup tasks
/do P2-CB-X003  # Add missing error handling
/do P3-CB-X004  # Improve code comments

# Document code review findings and fixes
/postmortem --id=P2-CB-X003 --note="Code review error handling improvements"
/postmortem --id=P3-CB-X004 --note="Code review documentation enhancements"

# Ensure documentation reflects changes
/update-readme chatbot/bowl
```

---

### 6️⃣ Complete TaskID Workflow Example

Here's a complete example of how the TaskID workflow system works in practice:

```bash
# Step 1: Initial analysis of your package
/update-todos mypackage --init

# Output: Generated TaskIDs with Difficulty fields like:
# - P0-MP-A003 (HARD): Fix critical race condition in manager.go
# - P1-MP-A001 (NORMAL): Add missing error handling in client.go
# - P2-MP-A002 (EASY): Update documentation for new API endpoints

# Step 2: Review generated tasks in mypackage/.workflows/todos.md
# You'll see tasks with Difficulty assignments:
# - [ ] **P0-MP-A003** Fix critical race condition in manager.go
#   - **Difficulty**: HARD
#   - **Context**: Complex concurrency issue affecting external API
# - [ ] **P1-MP-A001** Add missing error handling in client.go
#   - **Difficulty**: NORMAL
#   - **Context**: Moderate complexity, affects multiple code paths
# - [ ] **P2-MP-A002** Update documentation for new API endpoints
#   - **Difficulty**: EASY
#   - **Context**: Simple documentation update with no functional impact

# Step 3: Execute tasks using TaskIDs (no package path needed!)
/do P2-MP-A002                    # EASY: Direct execution, documentation updated
/do P1-MP-A001 --note="Add timeout support"  # NORMAL: Standard execution
/do P0-MP-A003                    # HARD: Automatic branch + detailed planning

# Step 4: HARD Task Special Workflow (P0-MP-A003)
# When executing a HARD task:
# 🔒 HARD Task Detected - Creating Branch: feature/fix-race-condition-P0-MP-A003
# 📋 Creating detailed implementation plan...
#
# 📋 Detailed Implementation Plan for P0-MP-A003
# **Task**: Fix critical race condition in manager.go
# **Difficulty**: HARD
# **Branch**: feature/fix-race-condition-P0-MP-A003
#
# **Analysis Phase**:
# - Current state: Race condition in goroutine synchronization
# - Dependencies: manager.go exports to external packages
# - Risk assessment: Critical - potential data corruption
# - Testing strategy: Comprehensive race condition testing
#
# **Implementation Phases**:
# - Phase 1: Add mutex protection to critical sections
# - Phase 2: Implement proper goroutine lifecycle management
# - Phase 3: Add extensive unit and integration tests
#
# **Rollback Strategy**:
# - Keep original implementation as backup
# - Test each phase independently
# - Safe rollback points after each phase
#
# 🤔 Ready to implement HARD task P0-MP-A003
# 📋 Branch: feature/fix-race-condition-P0-MP-A003
# 📄 Plan saved to: .workflows/P0-MP-A003-plan.md
#
# Continue with implementation? [y/N]

# Step 5: Each /do command automatically:
# - Loads the task context and Difficulty assessment
# - **For HARD tasks**: Creates branch, generates plan, gets confirmation
# - Implements the solution with appropriate safety measures
# - Updates relevant documentation
# - Marks the task as completed in todos.md
# - Moves completed tasks to Completed Tasks section
# - Updates Quick Stats with completion metrics
# - **For HARD tasks**: Branch ready for review and merge

# Step 6: Continue working and generate new TaskIDs as needed
/update-todos mypackage           # Generate new TaskIDs for recent changes
/do P1-MP-A004                    # Execute the new high-priority task

# Step 7: Document completed tasks with postmortem reports
/postmortem --id=P2-MP-A002       # Document API documentation updates
/postmortem --id=P1-MP-A001       # Document error handling implementation
/postmortem --id=P0-MP-A003       # Document complex race condition fix
```

**Difficulty Examples in Practice:**

**EASY Task Example:**
```bash
/do P2-MP-A002  # Update documentation
✅ Task Completed: P2-MP-A002
📝 Updated API documentation in package_readme.md
📄 Modified: package_readme.md (lines 45-67)
```

**NORMAL Task Example:**
```bash
/do P1-MP-A001  # Add error handling
✅ Task Completed: P1-MP-A001
📝 Added comprehensive error handling to client.go
📄 Modified: client.go (lines 23-89), package_readme.md
```

**HARD Task Example:**
```bash
/do P0-MP-A003  # Fix race condition
🔒 Creating branch: feature/fix-race-condition-P0-MP-A003
📋 Generated detailed implementation plan...
📄 Plan saved to: .workflows/P0-MP-A003-plan.md
🤔 User confirmation received
🔧 Implementing HARD task solution...
✅ HARD Task Completed: P0-MP-A003
📝 Fixed critical race condition with comprehensive refactoring
🌿 Branch: feature/fix-race-condition-P0-MP-A003 (ready for merge)
📄 Plan saved to: .workflows/P0-MP-A003-plan.md
📄 Modified: manager.go, client.go, tests/race_test.go
```

**Key Benefits of TaskID Workflow:**
- **No Path Required**: Execute tasks from anywhere using just the TaskID
- **Difficulty-Aware Execution**: Adapts workflow based on task complexity
- **Automatic Risk Management**: HARD tasks get branch isolation and detailed planning
- **Plan Persistence**: HARD task implementation plans are saved permanently for reference and audit
- **Automatic Tracking**: Task completion and documentation updates happen automatically
- **Cross-Package**: Execute tasks across multiple packages without context switching
- **Priority-Based**: Focus on P0/P1 tasks first, then work through lower priorities
- **Clean Organization**: Active Tasks only shows incomplete work, completed tasks in simple list, Archive compressed
- **Complete Coverage**: TaskID enforcement ensures all tasks are tracked, no missing items
- **Statistics Tracking**: Real-time metrics on both active and completed tasks
- **Safe Complex Changes**: Automatic branch creation protects main branch during risky changes
- **Knowledge Management**: Postmortem documentation preserves problem-solving insights and prevention strategies

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

### Git Commands
- **🤖 AI-Powered**: Leverages Claude's intelligence to understand your code changes
- **⚡ Time-Saving**: Eliminates repetitive git operations
- **📐 Consistent**: Enforces best practices and conventional formats
- **🔍 Insightful**: Provides detailed analysis of what changed and why

### Documentation Commands
- **📚 Comprehensive**: Generates complete package documentation automatically
- **🔍 Deep Analysis**: Identifies issues static analysis tools miss
- **🎯 Actionable**: Prioritizes tasks and issues by severity
- **🔄 Living Documentation**: Keeps docs in sync with code changes
- **🏗️ Architecture Aware**: Understands package relationships and dependencies
- **📊 Data-Driven**: Uses benchmark data to validate performance concerns

### Task Management Commands
- **🎯 Precise**: Execute tasks using unique TaskID without path specification
- **🔄 Automated**: Updates documentation and task status automatically
- **📋 Context-Aware**: Loads all relevant information for task execution
- **⚡ Efficient**: No need to manually locate tasks or update multiple files
- **🆔 TaskID System**: Automatic unique ID generation with priority-based ordering
- **🔧 Difficulty-Aware**: Adapts execution workflow based on task complexity (EASY/NORMAL/HARD)
- **🌿 Branch Management**: Automatic branch creation for HARD tasks with isolation
- **📋 Detailed Planning**: Comprehensive implementation plans for complex changes
- **💾 Plan Persistence**: HARD task plans automatically saved to `.workflows/{TaskID}-plan.md` files
- **🤔 User Confirmation**: Safety checkpoints for high-impact modifications
- **📊 Statistics Tracking**: Real-time task counts and completion metrics
- **🔍 Coverage Enforcement**: Ensures all tasks have TaskIDs, preventing lost work
- **📋 Clean Organization**: Separates active from completed tasks with simple list and compressed Archive
- **🛡️ Risk Management**: Different execution strategies based on task difficulty and impact
- **📝 Knowledge Preservation**: Postmortem documentation captures problem-solving insights and prevention strategies
- **🔍 Session Analysis**: Automatic detection of TaskIDs and problem context from coding sessions
- **📚 Go-Inspired Documentation**: Structured postmortem reports following Go best practices
- **🔄 Recurring Issue Tracking**: Updates existing postmortems for repeated problems with pattern analysis

### All Commands
- **🛡️ Safe**: Includes comprehensive error handling and validation
- **🔄 Workflow-Aware**: Designed for real development workflows
- **⚙️ Customizable**: Easy to modify for your project's needs

---

## 📁 Project Structure

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
│       │   ├── unittest_guide.md       # (if exists) Test documentation
│       │   └── benchmark_analysis.md   # (if exists) Performance data
│       ├── bowl.go
│       ├── manager.go
│       └── ...
├── 20250108-164512-A3F7_code_analyzer.md    # Code archaeology analysis
├── 20250108-171234-B8F2_code_analyzer.md    # Another analysis session
└── ...
```

The `.workflows/` directory keeps all package-level documentation organized and separate from source code. The `*_code_analyzer.md` files are generated by `/analyze` and can be stored at project root or in a dedicated analysis directory.

---

## 💡 Best Practices

### For Code Analysis (`/analyze`)
- **Before Fixing Bugs**: Always run `/analyze` to understand dataflow before making changes
- **Before Features**: Use `/analyze` for gap analysis to map impact points
- **Before Updates**: Use `/analyze` for feature updates when API or struct changes are needed
- **Before Refactoring**: Use `/analyze` to document current state before restructuring
- **Choose Right Type**: Select appropriate analysis type (bug|feature|update|refactor) for best focus
- **Multi-Session Work**: Split complex tasks - analyze in Session 1, implement in Session 2
- **Objective Mode**: Remember that `/analyze` documents WHAT exists, not WHAT SHOULD BE
- **Provide Context**: Include error messages, notes, and constraints for better analysis
- **File Management**: Keep `*_code_analyzer.md` files organized - project root or dedicated `/analysis` directory
- **Review First**: Always review the "Detailed Requirements Understanding" section before starting implementation
- **Archive Old**: Archive or delete analysis documents after implementation to avoid confusion

### For Git Commands
- Use `/push` for routine commits
- Use `/up-version` only when ready to release
- Review generated commit messages before they're pushed

### For Package Documentation
- Run `/update-readme` after significant API changes
- Run `/analyze-package` before code reviews and releases
- Run `/update-todos` after every coding session
- Use `--init` only once per package or when starting fresh
- Keep `package_readme.md` as the source of truth for package purpose
- Address P0/P1 issues from `analysis_report.md` immediately
- Let `/update-todos` automatically handle completed tasks organization
- Active Tasks section will only show incomplete work, completed tasks are moved automatically
- Run `/reorganize-todos` periodically (weekly/monthly) to archive old tasks and clean up workflow files
- Archives section keeps todos.md clean with 80/20 split - only most recent 20% visible

### For Difficulty Field Management
- **EASY Tasks**: Quick fixes, documentation updates, simple validation
- **NORMAL Tasks**: Feature additions, moderate refactoring, API changes with backward compatibility
- **HARD Tasks**: Major refactoring, breaking changes, architecture redesign, complex bug fixes
- **Trust the System**: Let `/update-todos` automatically assign Difficulty fields based on analysis
- **Review HARD Tasks**: Always review the generated implementation plan before confirmation
- **Branch Safety**: HARD tasks automatically create branches - review changes before merging
- **Planning Matters**: Use the detailed plans generated for HARD tasks as implementation guides

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
