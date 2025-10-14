# Reorganize Todos Command

Reorganizes and cleans up existing `{directory_path}/.workflows/todos.md` by ensuring complete TaskID coverage and proper task organization.

## Arguments
- Required: `{directory_path}` (e.g., `chatbot/bowl`)

## Purpose

A focused command that handles two critical cleanup operations:
1. **TaskID Coverage**: Ensures every task (active and completed) has a unique TaskID
2. **Task Organization**: Properly separates active and completed tasks

## Process Flow

### Step 1: Validate File Exists
```bash
# Check if todos.md exists
if [ ! -f "{directory_path}/.workflows/todos.md" ]; then
    echo "✗ Error: todos.md not found"
    echo "Please run: /update-todos {directory_path} --init"
    echo "Then complete some tasks before running reorganize-todos"
    exit 1
fi
```

### Step 2: Extract Package Information
1. **Read todos.md header** to get:
   - Package Path
   - Package Code
   - Current TaskIDs (if any)

2. **If Package Code missing**, generate from directory name:
   - `db` → `DB`
   - `chatbot/bowl` → `CB`
   - `core/cache` → `CC`
   - Use last part of path and create 2-3 letter code

### Step 3: Scan ALL Tasks for Missing TaskIDs

#### 3.1 Find Tasks Without TaskIDs
Search for patterns:
```bash
# Active tasks without TaskID
- [ ] {task description}

# Completed tasks without TaskID
- [x] {task description}
```

#### 3.2 Assign TaskIDs to Missing Tasks
For each task without TaskID:
1. **Analyze task content** to determine priority:
   - Critical issues, security, crashes → P0
   - High priority bugs, important features → P1
   - Medium tasks, documentation → P2
   - Low priority improvements → P3
   - Backlog/future items → P4

2. **Generate next available 4CharID**:
   - Get existing TaskIDs: extract all current 4CharIDs
   - Find next in sequence: A000, A001, ..., A999, B000, etc.

3. **Create TaskID**: `{Priority}-{PackageCode}-{4CharID}`

4. **Update task format**:
   ```markdown
   # Before: - [ ] Add validation for empty input
   # After:  - [ ] **P2-DB-A123** Add validation for empty input
   ```

### Step 4: Create/Verify Completed Tasks Section

#### 4.1 Check if Completed Tasks Section Exists
Look for:
```markdown
## Completed Tasks
```

#### 4.2 Create Completed Tasks Section if Missing
```markdown
## Completed Tasks

### Recently Completed
- [x] **{TaskID}** {Task description}
  - **Completed**: {YYYY-MM-DD HH:MM:SS}
  - **Method**: {brief description of what was done}
  - **Files Modified**: {list of files changed}
  - **Impact**: {summary of impact}

### This Week

### This Month
```

#### 4.3 Move All Completed Tasks
1. **Find ALL completed tasks** (tasks with `- [x]`)
2. **Move from Active Tasks** to appropriate time section:
   - Completed today → "Recently Completed"
   - Completed within 7 days → "This Week"
   - Completed within 30 days → "This Month"
   - Older than 30 days → Archive section

3. **Add completion details**:
   - **Completed**: Current timestamp
   - **Method**: "Task reorganization"
   - **Files Modified**: "todos.md"
   - **Impact**: "Added TaskID and proper organization"

### Step 5: Update Quick Stats
Recalculate and update:
- Total Active Tasks
- P0-P4 task counts
- Blocked tasks count
- Completed tasks counts (Today, This Week, This Month)

### Step 6: Validation

#### 6.1 TaskID Coverage Validation
- **EVERY task** must have TaskID format: `P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}`
- **NO tasks** should have plain text descriptions without TaskID
- **ALL TaskIDs** must be unique

#### 6.2 Organization Validation
- **ZERO completed tasks** in Active Tasks section
- **ALL completed tasks** in Completed Tasks section
- Proper time-based organization

#### 6.3 Format Validation
- Checkboxes properly formatted: `- [ ]` or `- [x]`
- TaskIDs in bold format: `**{TaskID}**`
- No duplicate tasks

## Output Messages

### Success Messages:
```
✅ Reorganized todos.md successfully
  - {N} tasks received new TaskIDs
  - {N} completed tasks moved to Completed Tasks section
  - Active Tasks now contains only {count} active tasks
  - Quick Stats updated with completion metrics
```

### Warning Messages:
```
⚠️ Warning: Found {N} tasks without TaskIDs - assigned automatically
⚠️ Warning: Created Completed Tasks section - {N} tasks moved
⚠️ Warning: Found {N} completed tasks in Active Tasks section - moved
```

### Error Messages:
```
✗ Error: todos.md not found
  Run: /update-todos {directory_path} --init

✗ Error: Invalid directory path: {directory_path}
  Directory does not exist

✗ Error: Cannot determine package code
  Please check directory structure

✗ Error: Failed to generate unique TaskIDs
  Too many tasks or TaskID generation issue
```

## Examples

### Basic Usage:
```bash
/reorganize-todos chatbot/bowl
```

### When todos.md is missing TaskIDs:
```bash
# Input todos.md has:
# Active Tasks
- [ ] Fix race condition in manager.go
- [x] Add error handling (completed yesterday)
- [ ] Update documentation

# Output todos.md:
# Active Tasks
- [ ] **P1-CB-A123** Fix race condition in manager.go
- [ ] **P2-CB-A124** Update documentation

## Completed Tasks
### Recently Completed
- [x] **P2-CB-A125** Add error handling
  - **Completed**: 2025-01-14 19:00:00
  - **Method**: Task reorganization
  - **Files Modified**: todos.md
  - **Impact**: Added TaskID and proper organization
```

### When Completed Tasks section doesn't exist:
```bash
# Input todos.md has completed tasks in Active section:
## Active Tasks
- [ ] **P1-CB-A123** Fix critical bug
- [x] **P2-CB-A124** Update docs (completed today)
- [x] **P0-CB-A125** Fix crash (completed 3 days ago)

# Output todos.md:
## Active Tasks
- [ ] **P1-CB-A123** Fix critical bug

## Completed Tasks
### Recently Completed
- [x] **P2-CB-A124** Update docs
  - **Completed**: 2025-01-14 19:00:00
  - **Method**: Task reorganization
  - **Files Modified**: todos.md
  - **Impact**: Added TaskID and proper organization

### This Week
- [x] **P0-CB-A125** Fix crash
  - **Completed**: 2025-01-11 14:30:00
  - **Method**: Task reorganization
  - **Files Modified**: todos.md
  - **Impact**: Added TaskID and proper organization
```

## Best Practices

### When to Use:
- After running `/update-todos --init` to clean up initial tasks
- When you notice tasks without TaskIDs
- When completed tasks accumulate in Active Tasks section
- Before major task management operations
- Periodic maintenance (weekly/monthly)

### Before Running:
- Ensure todos.md exists (run `/update-todos --init` if needed)
- Backup important todos.md if needed
- Review current task organization

### After Running:
- Verify Active Tasks only contains incomplete work
- Check Completed Tasks section for proper organization
- Use `/do {TaskID}` to execute tasks with proper TaskIDs

## Integration with Other Commands

### Typical Workflow:
```bash
# Step 1: Initialize task tracking
/update-todos mypackage --init

# Step 2: Clean up and organize tasks
/reorganize-todos mypackage

# Step 3: Execute tasks using TaskIDs
/do P1-MP-A123
/do P0-MP-A124

# Step 4: Continue task management
/update-todos mypackage
/reorganize-todos mypackage  # Periodic cleanup
```

### When Task Issues Found:
```bash
# If tasks missing TaskIDs or organization problems:
/reorganize-todos mypackage

# If you need to add new tasks based on changes:
/update-todos mypackage
/reorganize-todos mypackage  # Clean up any new tasks
```

## Design Philosophy

### Focused Responsibility:
- **Single Purpose**: Only handles TaskID and organization cleanup
- **No Analysis**: Doesn't analyze code or git changes
- **No Content Generation**: Only reorganizes existing content
- **Simple and Reliable**: Clear, predictable behavior

### Complementary to update-todos:
- `update-todos` → Content analysis and new task generation
- `reorganize-todos` → TaskID coverage and organization cleanup
- `do` → Task execution using TaskIDs

This separation ensures each command has a clear, focused responsibility and reduces complexity.