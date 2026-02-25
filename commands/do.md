# Do Command - Execute Tasks by TaskID (Redesigned)

Execute tasks from any package's todos.md using TaskID. **Supporting work delegated to subagents; main context reserved for code implementation only.**

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Prep Phase     │    │  Main Context   │    │  Post Phase     │
│  (Sequential    │───▶│  (Code Only)     │───▶│  (Single        │
│   Subagents)    │    │                  │    │   Subagent)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Context Isolation:** All file reading, planning, and documentation updates happen in isolated subagent contexts. The main context ONLY performs code implementation.

## Arguments
- Required: `{TaskID}` (e.g., `P0-DB-A236`, `P1-CB-B789`)
- Optional: `--note="{additional instructions}"` (provides context/reminders)

## TaskID Format
Format: `Priority-PackageCode-4CharID`
- **Priority**: P0, P1, P2, P3, P4
- **PackageCode**: 2-3 letter uppercase code (e.g., DB, CB, CC, TP)
- **4CharID**: 4-character alphanumeric (A-Z, 0-9)

Examples:
- `P0-DB-A236` → P0 task in DB package
- `P1-CB-B789` → P1 task in Chatbot Bowl package
- `P2-CC-C123` → P2 task in Core Cache package

## Process Flow (Subagent-Based)

### Phase 1: Preparation (Subagents 1 → 2 → 3)

All preparation work happens in isolated subagent contexts to keep the main context clean.

#### Step 1: Locate Task (Subagent 1)
**Dispatch:** Task Locator subagent

**Input:**
```yaml
task_id: "{TaskID}"
```

**Actions:**
1. Search all `.workflows/todos.md` files for TaskID
2. Validate uniqueness (exactly one match)
3. Extract package path from file location
4. Extract task metadata (priority, difficulty, type, title, context)

**Output:**
```yaml
status: success
package_path: "{path}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{title}"
  context: "{context}"
```

**See:** `.subagents/task-locator.md` for full specification

#### Step 2: Load Context (Subagent 2)
**Dispatch:** Context Loader subagent

**Input:**
```yaml
package_path: "{path}"
task_metadata: {...}
```

**Actions:**
1. Read task details from todos.md
2. Read package_readme.md (if exists)
3. Read analysis_report.md (if exists)
4. **Synthesize** into concise context packet (no raw file contents)

**Output:**
```yaml
status: success
context_packet:
  task_description: "{1-2 sentence description}"
  docs_summary: "{key points only}"
  file_references: ["{file}"]
  related_tasks: ["{TaskID}"]
```

**See:** `.subagents/context-loader.md` for full specification

#### Step 3: Generate Execution Brief (Subagent 3)
**Dispatch:** Plan Generator subagent

**Input:**
```yaml
task_metadata: {...}
context_packet: {...}
user_note: "{from --note flag}"  # optional
```

**Actions:**
1. Analyze task difficulty
2. **For EASY/NORMAL:** Create simple step-by-step brief
3. **For HARD:** Create detailed plan file + git branch + confirmation prompt

**Output (Execution Brief):**
```yaml
# Execution Brief for {TaskID}

task:
  id: "{TaskID}"
  title: "{title}"
  difficulty: "EASY|NORMAL|HARD"
  type: "{Bug|Feature|Refactor|Docs}"

execution:
  target_files:
    - path: "{relative/path}"
      action: "create|modify|delete"
      description: "{what to do}"

  approach: |
    {Concise approach - 2-3 sentences}

  steps:
    - "{Step 1}"
    - "{Step 2}"

hard_task_config:  # HARD only
  branch_name: "feature/{slug}-{TaskID}"
  plan_file: ".workflows/plan/{TaskID}-plan.md"
  confirmation_required: true

validation:
  success_criteria: ["{criterion}"]
  test_command: "{command}"
```

**See:** `.subagents/plan-generator.md` for full specification

### Phase 2: Execution (Main Context)

**CRITICAL:** This is the ONLY phase that runs in the main context.

#### Step 4: Execute Implementation (Main Context)

**Input:** Clean execution brief from Subagent 3

**Actions:**
1. Display task summary from brief
2. **For HARD tasks:** Request user confirmation
3. For each `target_file`:
   - Read file
   - Apply changes per `steps`
   - Write file
4. Run `test_command` if provided
5. Return completion status

**What Main Context Does NOT Do:**
- ❌ Read todos.md or any .workflows files
- ❌ Read documentation files (package_readme.md, analysis_report.md)
- ❌ Update todos.md
- ❌ Perform git operations
- ❌ Create plans

**Output:**
```yaml
completion_report:
  task_id: "{TaskID}"
  status: "success|failure"
  modified_files: ["{file}"]
  error_message: "{if failure}"
```

**See:** `.subagents/main-context-executor.md` for full specification

### Phase 3: Completion (Subagent 4)

#### Step 5: Complete Task (Subagent 4)
**Dispatch:** Completion Handler subagent

**Input:**
```yaml
completion_report: {...}
```

**Actions:**
1. Update todos.md:
   - Mark task as completed (`- [ ]` → `- [x]`)
   - Add completion metadata (timestamp, method, files)
   - Move to Completed Tasks section
2. Update related files:
   - package_readme.md if API changed
   - analysis_report.md if complexity/behavior changed
3. Git operations:
   - Stage modified files
   - **Spawn Pusher subagent** to commit and push changes
   - For HARD tasks: provide merge instructions
4. Update quick stats

**Output:**
```
✅ Task Completed: {TaskID}
📦 Package: {package}
📄 Modified: {files}
📝 Updated: {docs}
💾 Commit: {commit_hash}
🌿 Branch: {branch}  # for HARD tasks
```

**See:** `.subagents/completion-handler.md` for full specification

## Context Isolation Summary

| Phase | Context | Files Read | Files Written |
|-------|---------|------------|---------------|
| **Subagent 1** | Isolated | All todos.md | None |
| **Subagent 2** | Isolated | todos.md, docs | None |
| **Subagent 3** | Isolated | None (uses data) | Plan file (HARD) |
| **Main Context** | Clean | Target files only | Target files only |
| **Subagent 4** | Isolated | todos.md, related files | todos.md, related files |

**Main Context NEVER Loads:** todos.md, package_readme.md, analysis_report.md, plan files

## Search Strategy

### Direct TaskID Search
1. **Single Command Search**: Use direct TaskID search for maximum efficiency:
   ```bash
   find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "{TaskID}" {} \;
   ```

2. **Uniqueness Validation**: The TaskID system guarantees uniqueness across codebase, so direct search is sufficient and optimal

3. **Path Extraction**: Extract package path from the found todos.md file location
   - If found at `./db/.workflows/todos.md` → package path is `db`
   - If found at `./chatbot/bowl/.workflows/todos.md` → package path is `chatbot/bowl`

### TaskID Validation
Use regex to validate TaskID format before search:
```regex
^P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}$
```

### Performance Optimization
- Direct search eliminates multi-step lookups
- Single `find` command is more efficient than package code indexing
- No need for caching or complex indexing structures
- Ripgrep can be used for even faster searches:
  ```bash
  rg -l "{TaskID}" --type-add 'todos:*todos.md' --type todos
  ```

### Error Handling
- **TaskID not found**: Clear error message with format validation help
- **Multiple matches**: Should never happen with proper TaskID generation, but handled for safety
- **Invalid format**: Provide expected format examples

## Output Messages

### Success Messages:
```
✅ Task Completed: P1-DB-A236
📦 Package: db
📄 Modified: manager.go
📝 Updated: todos.md, package_readme.md
💾 Commit: abc1234
🌿 Branch: main
```

### HARD Task Success Messages:
```
✅ HARD Task Completed: P1-BC-A123
📦 Package: broadcast
📄 Modified: manager.go, validator.go, connector.go
📝 Updated: todos.md, package_readme.md, analysis_report.md
💾 Commit: def5678
🌿 Branch: feature/refactor-broadcast-manager-P1-BC-A123

🔀 Merge Instructions:
   1. Review changes on branch: feature/refactor-broadcast-manager-P1-BC-A123
   2. Run tests: go test ./broadcast -v
   3. If satisfied, merge:
      git checkout main
      git merge feature/refactor-broadcast-manager-P1-BC-A123
      git push origin main
   4. Cleanup branch:
      git branch -d feature/refactor-broadcast-manager-P1-BC-A123

📄 Plan reference: .workflows/plan/P1-BC-A123-plan.md
```

### Progress Messages:
```
🔍 Locating task... (Subagent 1)
📁 Found: P1-DB-A236 in db/.workflows/todos.md

📋 Loading context... (Subagent 2)
📋 Generating brief... (Subagent 3)

🎯 Executing: P1-DB-A236 (Main Context)
📄 Target Files: 1
  📄 manager.go → modify
✅ Implementation complete

📝 Completing task... (Subagent 4)
✅ Task Completed: P1-DB-A236
```

### HARD Task Progress Messages:
```
🔍 Locating task... (Subagent 1)
📁 Found: P1-BC-A123 in broadcast/.workflows/todos.md

📋 Loading context... (Subagent 2)
📋 Generating detailed plan... (Subagent 3)
🔒 Creating branch: feature/refactor-broadcast-manager-P1-BC-A123
📄 Plan saved: .workflows/plan/P1-BC-A123-plan.md

🤔 Ready to implement HARD task P1-BC-A123
   Branch: feature/refactor-broadcast-manager-P1-BC-A123
   Plan: .workflows/plan/P1-BC-A123-plan.md
Continue with implementation? [y/N] y

🎯 Executing: P1-BC-A123 (Main Context)
📄 Target Files: 3
  📄 manager.go → modify
  📄 validator.go → create
  📄 connector.go → modify
✅ Implementation complete

📝 Completing task... (Subagent 4)
✅ HARD Task Completed: P1-BC-A123
```

### Error Messages:
```
✗ Error: Invalid TaskID format: 'INVALID'
  Expected format: P[0-4]-[CODE]-[ID]

✗ Error: Task 'P0-DB-Z999' not found
  Available tasks in DB: P0-DB-A236, P1-DB-A237, P2-DB-A238

✗ Error: Task P1-DB-A236 missing Difficulty field
  All tasks must have: - **Difficulty**: {EASY|NORMAL|HARD}
  Run: /update-todos {package_path} to fix

✗ Error: HARD task P1-BC-A123 requires branch creation
  Unable to create branch: {git_error_message}
  Check git status and try again
```

## Special Cases

### HARD Tasks (Difficulty: HARD)
**All subagent coordination:**

1. **Subagent 3 (Plan Generator)** handles:
   - Detailed plan creation at `.workflows/plan/{TaskID}-plan.md`
   - Git branch creation: `feature/{slug}-{TaskID}`
   - User confirmation prompt

2. **Main Context** executes implementation on branch

3. **Subagent 4 (Completion Handler)** provides:
   - Merge instructions (no auto-push for HARD tasks)
   - Plan file reference

### Blocked Tasks
If task status is 'blocked':
1. Display blocking information
2. Ask for confirmation: `Task is blocked by {dependency}. Continue anyway? [y/N]`
3. If confirmed, proceed with execution

### Tasks Requiring External Input
If task requires user decisions during implementation (main context):
1. Pause execution at decision point
2. Present options clearly
3. Wait for user input
4. Continue with chosen approach

## Token Efficiency

| Metric | Original | Redesigned | Improvement |
|--------|----------|------------|-------------|
| Context size before implementation | All docs + plans | Clean brief only | ~80% reduction |
| Context size during implementation | Same + file edits | Target files only | ~70% reduction |
| Context pollution | High (docs + git ops) | None (subagent handles) | 100% reduction |

## Subagent Specifications

Full specifications for each subagent are in `.subagents/`:

| File | Purpose |
|------|---------|
| `task-locator.md` | Find TaskID, extract metadata |
| `context-loader.md` | Load and synthesize context |
| `plan-generator.md` | Create execution brief |
| `main-context-executor.md` | Code implementation logic |
| `completion-handler.md` | Update docs, git operations |

## Integration with Other Commands

### Before /do
- Run `/update-todos <package>` to ensure tasks are current
- Review relevant documentation files for context

### After /do
- Run `/update-todos <package>` to reflect task completion
- Run `/analyze-package <package>` if major changes were made
- Run `/update-readme <package>` if API changed

### Batch Operations
For multiple related tasks:
```bash
# Execute all P0 tasks across all packages
/do --all-p0

# Execute all tasks for specific package
/do --package=db --all

# Execute tasks matching pattern
/do --pattern="race condition"
```

## Best Practices

### For Users
1. **Verify TaskID**: Use correct TaskID format from todos.md
2. **Provide Context**: Use `--note` for additional requirements
3. **Review Changes**: Check modified files after task completion
4. **Update Status**: Let command update todos.md automatically

### For Task Implementation
1. **Follow Task Description**: Stick to what task specifically requests
2. **Document Changes**: Update relevant .workflows files
3. **Maintain Quality**: Follow existing code patterns and standards
4. **Handle Edge Cases**: Consider error conditions and edge cases

### For Task Authors
1. **Be Specific**: Write clear, actionable task descriptions
2. **Provide Context**: Include file locations and error details
3. **Set Appropriate Priority**: Use priority levels correctly
4. **Link Related Tasks**: Use "Related to: {TaskID}" for connections

## Examples

### Simple Bug Fix (EASY)
```bash
/do P2-CL-A001
```
→ Finds and fixes typo in error message
```
🎯 Executing Task: P2-CL-A001
📦 Package: . (root)
📝 Description: Fix typo in error message in logger.go:45
🔧 Difficulty: EASY
📋 Context: Simple text correction with no functional impact
✅ Task Completed: P2-CL-A001
```

### Feature Implementation (NORMAL)
```bash
/do P1-DB-A236
```
→ Adds input validation to ProcessData function
```
🎯 Executing Task: P1-DB-A236
📦 Package: db/.workflows/
📝 Description: Add input validation to ProcessData function
🔧 Difficulty: NORMAL
📋 Context: Affects multiple code paths but limited to single package
📄 Modified: manager.go, validator.go
✅ Task Completed: P1-DB-A236
```

### Complex Refactoring (HARD)
```bash
/do P1-BC-A123
```
→ Refactors complex function into smaller methods
```
🎯 Executing Task: P1-BC-A123
📦 Package: broadcast/.workflows/
📝 Description: Refactor InitiateAndManageBroadcast function into smaller methods
🔧 Difficulty: HARD
📋 Context: 146-line function with cyclomatic complexity of 12
🔒 HARD Task Detected - Creating Branch: feature/refactor-broadcast-manager-P1-BC-A123
📋 Task requires detailed planning and isolation

📋 Detailed Implementation Plan for P1-BC-A123
**Task**: Refactor InitiateAndManageBroadcast function into smaller methods
**Difficulty**: HARD
**Branch**: feature/refactor-broadcast-manager-P1-BC-A123

**Analysis Phase**:
- Current state: 146-line function, complexity 12, 4 phases
- Dependencies: manager.go exports to other packages
- Risk assessment: High - affects external API
- Testing strategy: Unit tests for each new method, integration tests

**Implementation Phases**:
- Phase 1: Extract validatePreFlightConditions()
- Phase 2: Extract waitForClientConnection()
- Phase 3: Extract acquireLLMSlot()
- Phase 4: Extract manageBroadcastLoop()

**Rollback Strategy**:
- Keep original function as backup during refactor
- Test each phase independently
- Safe rollback points after each phase

📄 Plan saved to: .workflows/plan/P1-BC-A123-plan.md

🤔 Ready to implement HARD task P1-BC-A123
📋 Branch: feature/refactor-broadcast-manager-P1-BC-A123
📄 Plan saved to: .workflows/plan/P1-BC-A123-plan.md

Continue with implementation? [y/N]
```

### Feature with Additional Context
```bash
/do P1-CB-B789 --note="Add support for bulk operations, see design.md page 5"
```
→ Implements feature with additional design requirements

### Documentation Task
```bash
/do P2-CC-C123
```
→ Updates documentation in core cache package
