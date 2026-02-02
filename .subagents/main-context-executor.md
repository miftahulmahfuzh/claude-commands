# Main Context: Code Implementation

**Purpose:** Pure code implementation only. This is the ONLY phase that runs in the main context.

## Input

The main context receives a **clean execution brief** (YAML format) from Subagent 3 (Plan Generator).

```yaml
# Execution Brief for {TaskID}

task:
  id: "{TaskID}"
  title: "{Brief task title}"
  difficulty: "{EASY|NORMAL|HARD}"
  type: "{Bug|Feature|Refactor|Docs}"

execution:
  target_files:
    - path: "{relative/path/to/file.ext}"
      action: "{create|modify|delete}"
      description: "{What to do}"

  approach: |
    {Concise implementation approach - 2-3 sentences}

  steps:
    - "{Step 1: specific action}"
    - "{Step 2: specific action}"

hard_task_config:  # Only for HARD tasks
  branch_name: "feature/{slug}-{TaskID}"
  plan_file: ".workflows/plan/{TaskID}-plan.md"
  confirmation_required: true

validation:
  success_criteria:
    - "{Criterion 1}"
  test_command: "{command to verify}"
```

## Actions

### 1. Receive and Display Brief

```bash
🎯 Executing: {TaskID}
📦 Difficulty: {EASY|NORMAL|HARD}
🔧 Type: {Bug|Feature|Refactor|Docs}
📄 Target Files: {count} files

{approach from brief}
```

### 2. HARD Task Confirmation (if applicable)

If `hard_task_config.confirmation_required: true`:

```bash
🔒 HARD Task Detected
🌿 Branch: {branch_name}
📄 Plan: {plan_file}

Continue with implementation? [y/N]
```

**Wait for user input** before proceeding.

### 3. Load and Modify Files

For each `target_file` in `execution.target_files`:

```bash
📄 Loading: {path}
🔧 {action}: {description}
```

**Actions by file action type:**

| Action | Steps |
|--------|-------|
| `create` | Create new file with content |
| `modify` | Read file → Apply changes per `steps` → Write file |
| `delete` | Delete file |

**For each file:**
1. Read the file content
2. Apply changes according to `execution.steps`
3. Write the modified content back
4. Display confirmation: `✅ {path}: {action}`

### 4. Run Validation (if provided)

If `validation.test_command` is specified:

```bash
🧪 Running: {test_command}
```

**Interpret results:**
- Exit code 0: Tests pass → Continue
- Non-zero exit code: Tests fail → Report failure, continue to completion report

### 5. Return Completion Report

**On Success:**
```yaml
completion_report:
  task_id: "{TaskID}"
  status: "success"
  modified_files:
    - "{file_path}"
    - "{file_path}"
  test_results: "passed"  # if tests were run
```

**On Failure:**
```yaml
completion_report:
  task_id: "{TaskID}"
  status: "failure"
  error_message: "{clear error description}"
  failed_at: "{step or file where failure occurred}"
  modified_files:
    - "{file_path}"  # any files that were modified before failure
```

## What Main Context Does NOT Do

| Action | Why Not | Who Handles It |
|--------|--------|----------------|
| Read todos.md | Not needed for implementation | Subagent 1 |
| Read documentation files | Context already synthesized | Subagent 2 |
| Update todos.md | Post-execution work | Subagent 4 |
| Update package_readme.md | Post-execution work | Subagent 4 |
| Perform git operations | Post-execution work | Subagent 4 |
| Create plans | Already created by Subagent 3 | Subagent 3 |

## Output Format

**Standard Output:**
```
🎯 Executing: {TaskID}
📦 Difficulty: {EASY|NORMAL|HARD}
🔧 Type: {type}

{approach}

📄 Target Files: {count}
{for each file}
  📄 {path}
     🔧 {action}: {description}

{if test_command}
🧪 Running: {test_command}
✅ Tests passed

✅ Implementation complete: {TaskID}
📄 Files modified: {count}
📦 Handoff to post-execution phase...
```

**Error Output:**
```
🎯 Executing: {TaskID}

📄 Loading: {path}
❌ Error: {error message}

✗ Implementation failed: {TaskID}
📍 Failed at: {step}
📦 Handoff to post-execution phase (with failure status)...
```

## File Modification Process

### Reading Files
```bash
# Use Read tool to get file content
Read /path/to/file.ext
```

### Applying Changes
Follow `execution.steps` sequentially:
- Each step is a specific action
- Apply changes to the file content
- Maintain file structure and formatting

### Writing Files
```bash
# Use Write tool to save modified content
Write /path/to/file.ext
```

## Error Handling

| Error | Handler |
|-------|---------|
| File not found | Report error, include in completion report as failure |
| Read permission denied | Report error, include in completion report as failure |
| Write permission denied | Report error, include in completion report as failure |
| Test command fails | Report failure, but still continue to completion report |
| Step unclear | Use AskUserQuestion to clarify, then continue |

## Context State After Execution

**Files on disk:**
- Target files are modified (in working directory)
- Uncommitted changes in git

**Files NOT modified:**
- todos.md (untouched)
- package_readme.md (untouched)
- analysis_report.md (untouched)
- Any other .workflows files (untouched)

**Git state:**
- Working directory has changes
- No commits made
- No branches changed (except HARD task branch already created)

## Example Flow

**Input Brief:**
```yaml
# Execution Brief for P1-DB-A236

task:
  id: "P1-DB-A236"
  title: "Add input validation"
  difficulty: "NORMAL"
  type: "Feature"

execution:
  target_files:
    - path: "db/manager.go"
      action: "modify"
      description: "Add validation before ProcessData call"

  approach: |
    Add validator.ValidateInput() call at line 45 before ProcessData().
    Import db/validator package. Return error on validation failure.

  steps:
    - "Add import for db/validator package"
    - "Add validation check at manager.go:45"
    - "Return error early if validation fails"

validation:
  success_criteria:
    - "ProcessData validates input before processing"
  test_command: "go test ./db -run TestProcessDataValidation"
```

**Execution:**
```
🎯 Executing: P1-DB-A236
📦 Difficulty: NORMAL
🔧 Type: Feature

Add validator.ValidateInput() call at line 45 before ProcessData().
Import db/validator package. Return error on validation failure.

📄 Target Files: 1
  📄 db/manager.go
     🔧 modify: Add validation before ProcessData call

📄 Loading: db/manager.go
🔧 Applying changes...
   - Adding import for db/validator package
   - Adding validation check at line 45
   - Adding early return on validation failure
✅ db/manager.go: modified

🧪 Running: go test ./db -run TestProcessDataValidation
✅ Tests passed

✅ Implementation complete: P1-DB-A236
📄 Files modified: 1
📦 Handoff to post-execution phase...
```

**Completion Report:**
```yaml
completion_report:
  task_id: "P1-DB-A236"
  status: "success"
  modified_files:
    - "db/manager.go"
  test_results: "passed"
```

## Implementation Notes

- Main context is the ONLY place where code is modified
- All file operations use Read/Write tools
- Steps are followed sequentially
- Error at any step stops further modifications
- Completion report always includes status and modified files list
- Test failures don't prevent completion report
- Main context does NOT commit changes or update documentation
