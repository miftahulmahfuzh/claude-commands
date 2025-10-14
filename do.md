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
Create execution plan based on task type:

#### Bug Fix Tasks
- Analyze error context and reproduction steps
- Identify affected code locations
- Plan fix implementation and testing approach

#### Feature Implementation Tasks
- Understand feature requirements from task description
- Identify integration points and dependencies
- Plan implementation steps and validation approach

#### Refactoring Tasks
- Analyze current code structure and issues
- Plan refactoring approach to maintain functionality
- Identify tests needed to validate refactoring

#### Documentation Tasks
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
   📋 Context: {task_context}
   ```

2. **Load Required Files**: Read source files mentioned in task
3. **Implement Solution**: Make necessary code changes
4. **Update Documentation**: Update relevant .workflows files
5. **Update Task Status**: Mark task as completed in todos.md

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
3. **Move to Archive**: If archive section exists, move completed task there
4. **Update Quick Stats**: Recalculate task counts

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
📄 Modified: manager.go (lines 45-67)
📄 Updated: todos.md, analysis_report.md
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

### Warning Messages:
```
⚠️ Warning: Task P2-DB-A236 is marked as blocked
⚠️ Warning: Task has high priority - consider impact assessment
⚠️ Warning: Multiple files modified - review changes carefully
```

### Error Messages:
```
✗ Error: Invalid TaskID format: 'INVALID'
  Expected format: P[0-4]-[CODE]-[ID]

✗ Error: Package code 'XX' not found
  Available packages: DB, CB, CC, TP

✗ Error: Task 'P0-DB-Z999' not found
  Available tasks in DB: P0-DB-A236, P1-DB-A237, P2-DB-A238
```

## Special Cases

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

### Simple Bug Fix
```bash
/do P0-DB-A236
```
→ Finds and fixes race condition in db package

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

### Complex Refactoring
```bash
/do P1-TP-D456 --note="Maintain backward compatibility, add deprecated wrappers"
```
→ Refactors while preserving API compatibility