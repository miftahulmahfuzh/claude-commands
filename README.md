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
- **Step 6**: Execute implementation (main context - clean, only code)

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
│  (Sequential    │───▶│  (Code Only)     │───▶│  (Single        │
│   Subagents)    │    │                  │    │   Subagent)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Context Isolation:** All file reading, planning, and documentation updates happen in isolated subagent contexts. The main context ONLY performs code implementation.

**What it does:**
- 🔍 **Locates tasks** across all packages using TaskID
- 📋 **Loads task context** and relevant documentation (via subagents)
- 🔧 **Executes implementation** in clean main context (code only)
- 📝 **Updates documentation** and marks task complete (via subagent)
- ✅ **Moves completed tasks** to Completed Tasks section (via subagent)

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

**Phase 3: Completion (Subagent 4)**
- Update todos.md (mark completed, move section)
- Update related files (package_readme.md, analysis_report.md)
- Git operations (add, commit, push)
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
