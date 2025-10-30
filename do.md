# Do Command - Execute Tasks by TaskID

Execute tasks from any package's todos.md using TaskID without needing to specify the package directory path.

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

## Process Flow

### Step 1: Locate Task
1. **Parse TaskID**: Extract priority, package code, and 4CharID
2. **Direct Search**: Search for the exact TaskID in all todos.md files:
   ```bash
   find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "{TaskID}" {} \;
   ```
3. **Validate Uniqueness**: Ensure TaskID appears in exactly one file
4. **Error Handling**:
   - If TaskID not found: `✗ Error: Task '{TaskID}' not found in any todos.md files`
   - If TaskID found in multiple files: `✗ Error: TaskID '{TaskID}' is not unique - found in {path1} and {path2}`
   - Extract package path from the found file location

### Step 2: Load Task Context
Read from the found `{package_path}/.workflows/todos.md`:
1. **Task Details**: Extract full task description, context, and status
2. **Package Context**: Load package_readme.md to understand package structure
3. **Analysis Context**: Load analysis_report.md if exists for additional context
4. **Related Files**: Parse file references in task description

### Step 3: Parse Additional Notes
If `--note` parameter provided:
1. **Parse Note Content**: Extract additional instructions, file references, or context
2. **Merge with Task**: Append note to task context as "Additional Instructions"
3. **Update Priority**: If note indicates urgency, consider priority escalation

### Step 4: Prepare Execution Plan
Create execution plan based on task type and difficulty:

#### Check Task Difficulty First
1. **Extract Difficulty**: Read the `- **Difficulty**: {EASY|NORMAL|HARD}` field from task
2. **HARD Task Special Handling**: If Difficulty is HARD, execute special workflow:
   - Create new branch (see Step 4.1)
   - Create detailed implementation plan (see Step 4.2)
   - Get user confirmation before proceeding

#### 4.1 HARD Task Branch Creation (MANDATORY)
For tasks with `**Difficulty**: HARD`:

1. **Create Dedicated Branch**:
   ```bash
   git checkout -b feature/{task-description-slug}-{TaskID}
   # Example: git checkout -b feature/refactor-broadcast-manager-P1-BC-A123
   ```

2. **Announce Branch Creation**:
   ```
   🔒 HARD Task Detected - Creating Branch: feature/{task-description-slug}-{TaskID}
   📋 Task requires detailed planning and isolation
   ```

3. **Verify Branch Created**: Ensure branch is successfully created and checked out

#### 4.2 HARD Task Detailed Planning (MANDATORY)
For tasks with `**Difficulty**: HARD`:

1. **Create Implementation Plan Document**:
   ```
   📋 Detailed Implementation Plan for {TaskID}

   **Task**: {task_description}
   **Difficulty**: HARD
   **Branch**: feature/{task-description-slug}-{TaskID}

   **Analysis Phase**:
   - Current state assessment
   - Dependencies identification
   - Risk assessment
   - Testing strategy

   **Implementation Phases**:
   - Phase 1: {description}
   - Phase 2: {description}
   - ...

   **Rollback Strategy**:
   - How to undo changes if needed
   - Safe rollback points
   ```

2. **Save Plan to File (MANDATORY)**:
   ```bash
   # Save detailed plan to .workflows/plan/{TaskID}-plan.md
   cat > .workflows/plan/{TaskID}-plan.md << 'EOF'
   # Implementation Plan: {TaskID}

   **Task**: {task_description}
   **Difficulty**: HARD
   **Branch**: feature/{task-description-slug}-{TaskID}
   **Created**: {YYYY-MM-DD HH:MM:SS}

   ## Analysis Phase
   {detailed analysis content}

   ## Implementation Phases
   {implementation phases content}

   ## Rollback Strategy
   {rollback strategy content}

   ## Success Criteria
   {measurable success criteria}
   EOF
   ```

3. **Confirm Plan Saved**:
   ```
   📄 Plan saved to: .workflows/plan/{TaskID}-plan.md
   📋 Reference available during implementation
   ```

4. **Get User Confirmation**:
   ```
   🤔 Ready to implement HARD task {TaskID}
   📋 Branch: feature/{task-description-slug}-{TaskID}
   📄 Plan saved to: .workflows/plan/{TaskID}-plan.md

   Continue with implementation? [y/N]
   ```

5. **Wait for User Input**: Only proceed with explicit user confirmation

#### Standard Task Execution plan

##### Bug Fix Tasks
- Analyze error context and reproduction steps
- Identify affected code locations
- Plan fix implementation and testing approach

##### Feature Implementation Tasks
- Understand feature requirements from task description
- Identify integration points and dependencies
- Plan implementation steps and validation approach

##### Refactoring Tasks
- Analyze current code structure and issues
- Plan refactoring approach to maintain functionality
- Identify tests needed to validate refactoring

##### Documentation Tasks
- Identify what documentation needs updating
- Gather context from code and existing docs
- Plan documentation structure and content

### Step 5: Execute Task
Execute the task following this pattern:

1. **Announce Task**: Display task details and plan
   ```
   🎯 Executing Task: {TaskID}
   📦 Package: {package_path}
   📝 Description: {task_description}
   🔧 Difficulty: {EASY|NORMAL|HARD}
   📋 Context: {task_context}
   ```

2. **HARD Task Special Pre-execution**:
   If Difficulty is HARD:
   ```
   🔒 Implementing HARD Task {TaskID}
   📋 Branch: feature/{task-description-slug}-{TaskID}
   📄 Following detailed implementation plan...
   ```

3. **Load Required Files**: Read source files mentioned in task
4. **Load Implementation Plan**: Read saved plan from `.workflows/plan/{TaskID}-plan.md` for reference
5. **Implement Solution**: Make necessary code changes following the detailed plan
6. **Update Documentation**: Update relevant .workflows files
7. **Update Task Status**: Mark task as completed in todos.md

### Step 6: Update Task Status
After execution:

1. **Mark Completed**: Change checkbox from `- [ ]` to `- [x]`
2. **Add Completion Note**:
   ```markdown
   - [x] **{TaskID}** {task_description}
     - **Completed**: {YYYY-MM-DD HH:MM:SS}
     - **Method**: {brief description of what was done}
     - **Files Modified**: {list of files changed}
   ```
3. **CRITICAL: Move to Completed Tasks Section**:
   - Check if `## Completed Tasks` section exists in todos.md
   - If **NOT exists**, create the section:
     ```markdown
     ## Completed Tasks

     ### Recently Completed
     - [x] **{TaskID}** {task_description}
       - **Completed**: {YYYY-MM-DD HH:MM:SS}
       - **Method**: {brief description of what was done}
       - **Files Modified**: {list of files changed}

     ### This Week

     ### This Month
     ```
   - If **exists**, move completed task to appropriate time-based subsection:
     - Completed today → "Recently Completed"
     - Completed within 7 days → "This Week"
     - Completed within 30 days → "This Month"
     - Older than 30 days → Archive section (if exists)
   - **ENSURE**: Completed task is REMOVED from Active Tasks section
   - **VERIFY**: No completed tasks remain in Active Tasks section

4. **Update Quick Stats**: Recalculate task counts including completion metrics

### Step 7: Update Related Files
Based on task type, update other .workflows files:

#### For Bug Fixes
- Update analysis_report.md if the issue was documented there
- Add note about fix to package_readme.md if it affects API behavior

#### For Feature Implementation
- Update package_readme.md with new API documentation
- Update analysis_report.md if new complexity was introduced

#### For Refactoring
- Update analysis_report.md with improved complexity metrics
- Update package_readme.md if API changed

#### For Documentation Tasks
- Update the target documentation files
- Note in todos.md that documentation was updated

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
✅ Task Completed: P0-DB-A236
📦 Package: db/.workflows/
📝 Fixed race condition in Manager.Start()
🔧 Difficulty: NORMAL
📄 Modified: manager.go (lines 45-67)
📄 Updated: todos.md, analysis_report.md
📋 Task moved to Completed Tasks section
📊 Quick Stats updated with completion metrics
```

### HARD Task Success Messages:
```
✅ HARD Task Completed: P1-BC-A123
📦 Package: broadcast/.workflows/
📝 Refactored InitiateAndManageBroadcast function into smaller methods
🔧 Difficulty: HARD
🌿 Branch: feature/refactor-broadcast-manager-P1-BC-A123
📄 Plan saved to: .workflows/plan/P1-BC-A123-plan.md
📄 Modified: manager.go, validator.go, connector.go, processor.go
📄 Updated: todos.md, package_readme.md, analysis_report.md
📋 Task moved to Completed Tasks section
📊 Quick Stats updated with completion metrics
🔀 Ready for branch merge: feature/refactor-broadcast-manager-P1-BC-A123
```

### Progress Messages:
```
🔍 Locating task P1-DB-A236...
📁 Found in: db/.workflows/todos.md
📋 Loading task context...
🔧 Implementing solution...
📝 Updating documentation...
✅ Task completed successfully
```

### HARD Task Progress Messages:
```
🔍 Locating HARD task P1-BC-A123...
📁 Found in: broadcast/.workflows/todos.md
📋 Loading task context...
🔒 Creating branch: feature/refactor-broadcast-manager-P1-BC-A123
📋 Creating detailed implementation plan...
📄 Saving plan to: .workflows/plan/P1-BC-A123-plan.md
🤔 User confirmation received for HARD task
🔧 Implementing HARD task solution...
📝 Updating documentation...
✅ HARD Task completed successfully
```

### Warning Messages:
```
⚠️ Warning: Task P2-DB-A236 is marked as blocked
⚠️ Warning: Task has high priority - consider impact assessment
⚠️ Warning: Multiple files modified - review changes carefully
```

### HARD Task Warning Messages:
```
⚠️ Warning: HARD task P1-BC-A123 will create new branch
⚠️ Warning: HARD task requires detailed planning before implementation
⚠️ Warning: HARD task plan will be saved to .workflows/plan/P1-BC-A123-plan.md
⚠️ Warning: HARD task affects multiple files - review carefully before merge
```

### Error Messages:
```
✗ Error: Invalid TaskID format: 'INVALID'
  Expected format: P[0-4]-[CODE]-[ID]

✗ Error: Package code 'XX' not found
  Available packages: DB, CB, CC, TP

✗ Error: Task 'P0-DB-Z999' not found
  Available tasks in DB: P0-DB-A236, P1-DB-A237, P2-DB-A238

✗ Error: Task P1-DB-A236 missing Difficulty field
  All tasks must have: - **Difficulty**: {EASY|NORMAL|HARD}
  Run: /update-todos {package_path} to fix

✗ Error: Invalid Difficulty value for task P1-DB-A236: 'INVALID'
  Valid values: EASY, NORMAL, HARD (case-sensitive)
  Run: /update-todos {package_path} to fix

✗ Error: HARD task P1-BC-A123 requires branch creation
  Unable to create branch: {git_error_message}
  Check git status and try again

✗ Error: HARD task P1-BC-A123 requires plan saving
  Unable to save plan to .workflows/plan/P1-BC-A123-plan.md: {file_error_message}
  Check directory permissions and try again
```

## Special Cases

### HARD Tasks (Difficulty: HARD)
**Special handling for complex, high-impact tasks:**

1. **Automatic Branch Creation**:
   ```bash
   git checkout -b feature/{task-description-slug}-{TaskID}
   ```

2. **Detailed Implementation Plan Required**:
   - Analysis phase with current state assessment
   - Risk assessment and dependency identification
   - Step-by-step implementation phases
   - Rollback strategy with safe rollback points

3. **Plan Persistence Requirements**:
   - Save detailed plan to `.workflows/plan/{TaskID}-plan.md` before implementation
   - Include analysis, phases, rollback strategy, and success criteria
   - Reference plan during implementation for consistency
   - Keep plan file as documentation after task completion

4. **User Confirmation Before Implementation**:
   ```
   🤔 Ready to implement HARD task {TaskID}
   📋 Branch: feature/{task-description-slug}-{TaskID}
   📄 Plan saved to: .workflows/plan/{TaskID}-plan.md

   Continue with implementation? [y/N]
   ```

5. **Enhanced Documentation Requirements**:
   - Update all affected .workflows files
   - Document breaking changes and migration guides
   - Add comprehensive testing requirements
   - Reference saved plan file in task completion notes

6. **Branch Management After Completion**:
   - Task completed on dedicated branch
   - Branch ready for review and merge
   - Merge instructions provided in success message
   - Plan file remains as implementation documentation

### Blocked Tasks
If task status is 'blocked':
1. Display blocking information
2. Ask for confirmation: `Task is blocked by {dependency}. Continue anyway? [y/N]`
3. If confirmed, proceed with execution

### Priority Changes
If note indicates higher priority:
1. Ask for confirmation: `Escalate P2-DB-A236 to P0? [y/N]`
2. If confirmed, update TaskID prefix in todos.md
3. Update task location in appropriate priority section

### Multi-Package Tasks
If task affects multiple packages:
1. Identify all affected packages from task description
2. Load todos.md from each package
3. Create linked tasks in each package with same 4CharID
4. Execute coordinated changes across packages

### Tasks Requiring External Input
If task requires user decisions during implementation:
1. Pause execution at decision point
2. Present options clearly
3. Wait for user input
4. Continue with chosen approach

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
