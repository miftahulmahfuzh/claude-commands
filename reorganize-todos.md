# Reorganize Todos Command

Reorganizes and cleans up existing `{directory_path}/.workflows/todos.md` by ensuring complete TaskID coverage and proper task organization.

## Arguments
- Required: `{directory_path}` (e.g., `chatbot/bowl`)

## Purpose

A focused command that handles three critical cleanup operations:
1. **TaskID Coverage**: Ensures every task (active and completed) has a unique TaskID
2. **Task Organization**: Properly separates active and completed tasks
3. **Archive Management**: Compresses 80% of oldest completed tasks and removes related workflow files

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

### Step 3: Scan ALL Tasks for Missing TaskIDs and Uniqueness

#### 🔴 CRITICAL: TaskID Uniqueness Requirement

**EVERY TaskID in the todos.md file MUST BE UNIQUE.**

1. **Before generating ANY new TaskID**: You MUST scan the ENTIRE todos.md file and collect ALL existing TaskIDs
2. **Verify uniqueness**: The new TaskID you generate MUST NOT exist anywhere in the file
3. **If duplicate found**: You MUST rename ALL duplicate TaskIDs to new, unique values
4. **If task has no TaskID**: You MUST generate a new, unique TaskID for that task

**Failure to ensure TaskID uniqueness is a critical error.**

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
1. **Collect ALL existing TaskIDs** from entire file (Active Tasks, Completed Tasks, Archive)
2. **Analyze task content** to determine priority:
   - Critical issues, security, crashes → P0
   - High priority bugs, important features → P1
   - Medium tasks, documentation → P2
   - Low priority improvements → P3
   - Backlog/future items → P4

3. **Generate next available 4CharID**:
   - Get existing TaskIDs: extract all current 4CharIDs
   - Find next in sequence: A000, A001, ..., A999, B000, etc.

4. **CRITICAL: Verify TaskID uniqueness**:
   - Check if generated TaskID already exists in collected TaskIDs
   - If it exists, generate next available ID until you find a unique one
   - **Do NOT use any TaskID that already exists in the file**

5. **Create TaskID**: `{Priority}-{PackageCode}-{4CharID}`

6. **Update task format**:
   ```markdown
   # Before: - [ ] Add validation for empty input
   # After:  - [ ] **P2-DB-A123** Add validation for empty input
   ```

#### 3.3 Detect and Fix Duplicate TaskIDs
After collecting all TaskIDs:
1. Check if ANY TaskID appears more than once
2. If duplicates found, rename EACH duplicate to a new, unique TaskID
3. Generate new unique TaskIDs using next available sequence
4. Update all references to use the new TaskIDs
5. **Do NOT proceed until all TaskIDs are unique**

### Step 4: Create/Verify Completed Tasks Section

#### 🔴 CRITICAL: todos.md File Structure - Exactly 4 Sections

**The todos.md file MUST contain exactly these 4 sections:**

1. **Header with Quick Stats** (metadata and statistics)
2. **Active Tasks** (with P0-P4 subsections)
3. **Completed Tasks** (simple list)
4. **Archive** (single-line compressed format)

**IF the file contains ANY other sections (e.g., "Recent Activity", "Notes", "Recently Completed", "This Week", "This Month", etc.), you MUST DELETE those sections entirely.**

#### 4.1 Check if Completed Tasks Section Exists
Look for:
```markdown
## Completed Tasks
```

#### 4.2 Create Completed Tasks Section if Missing
```markdown
## Completed Tasks

- [x] **{TaskID}** {Task description}
  - **Completed**: {YYYY-MM-DD HH:MM:SS}
  - **Method**: {brief description of what was done}
  - **Files Modified**: {list of files changed}
  - **Impact**: {summary of impact}
```

**IMPORTANT**: Completed Tasks is a SIMPLE LIST with NO time-based subsections (no "Recently Completed", "This Week", "This Month").

#### 4.3 Move ALL Completed Tasks from Active Tasks Section
1. **Find ALL completed tasks** (tasks with `- [x]`) **anywhere in the file**
2. **CRITICAL: Scan the ENTIRE Active Tasks section** for ANY checkmarked tasks:
   - Search EVERY line in Active Tasks section for `- [x]` pattern
   - NO checkmarked task should remain in Active Tasks section
   - MOVE ALL checkmarked tasks without exception

3. **Move ALL found completed tasks** from Active Tasks to Completed Tasks section:
   - Add to the simple list in Completed Tasks section (newest first)
   - Older than 30 days → Archive section (see Step 5)

4. **Add completion details**:
   - **Completed**: Current timestamp
   - **Method**: "Task reorganization"
   - **Files Modified**: "todos.md"
   - **Impact**: "Added TaskID and proper organization"

5. **VERIFICATION**: After moving, double-check that **ZERO checkmarked tasks remain** in Active Tasks section

### Step 5: Compress and Archive Old Completed Tasks

#### 5.1 Calculate Archive Target (80% Rule)
- Count total completed tasks in Completed Tasks section
- Calculate 80% threshold: `archive_count = total_completed * 0.8`
- Keep the most recent 20% visible, archive the oldest 80%

#### 5.2 Identify Tasks to Archive
- Sort completed tasks by completion date (oldest first)
- Select the oldest 80% for archiving
- Keep the most recent 20% in Completed Tasks section

#### 5.3 Move Tasks to Archive Section
1. **Create Archive section if missing** (at the end of file):
```markdown
## Archive

### {YYYY-MM}
<!-- Compressed format: one line per task -->
```

2. **Compress each archived task to single line**:
```markdown
# Before (in Completed Tasks):
- [x] **P2-DB-A123** Add validation for empty input
  - **Completed**: 2025-01-10 14:30:00
  - **Method**: Implemented validation logic
  - **Files Modified**: src/validate.go
  - **Impact**: Improved error handling

# After (in Archive):
- P2-DB-A123: Add validation for empty input
```

3. **Trace and Remove Relevant Workflow Files**:
   - Search all `.workflows/` directories for markdown files containing the TaskID as substring
   - Look for patterns like:
     - `{task-id}.md`
     - `plan-{task-id}.md`
     - `analysis-{task-id}.md`
     - `postmortem-{task-id}.md`
     - `{task-id}-*.md`
     - `*-{task-id}.md`
   - Remove these files to clean up workspace
   - Skip removal if file doesn't exist

4. **Bash command pattern** for finding related workflow files:
```bash
# Find all .md files in any .workflows folder containing the TaskID
find . -type d -name ".workflows" -exec find {} -name "*{task-id}*.md" \; 2>/dev/null
```

#### 5.4 Update Archive Section Format
- **Single-line format with bullet**: `- {TaskID}: {task description}`
- **Sort by TaskID** for easy reference
- **No completion metadata** (date, method, files, impact)
- **No checkboxes** (tasks are completed and archived)
- Archive section is read-only - items stay compressed, never expanded back

### Step 6: Update Quick Stats
Recalculate and update:
- Total Active Tasks
- P0-P4 task counts
- Blocked tasks count
- Completed tasks counts (Today, This Week, This Month)
- Archived tasks count

### Step 7: Validation

#### 7.1 TaskID Uniqueness Validation (CRITICAL)
- **Scan ENTIRE file** and collect ALL TaskIDs
- **Verify NO duplicate TaskIDs exist** - every TaskID must be unique
- If duplicates found, STOP and rename all duplicates to unique TaskIDs
- **Do NOT proceed until ALL TaskIDs are unique**

#### 7.2 TaskID Coverage Validation
- **EVERY task** must have TaskID format: `P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}`
- **NO tasks** should have plain text descriptions without TaskID
- **ALL TaskIDs** must be unique

#### 7.3 File Structure Validation (CRITICAL)
- **Verify EXACTLY 4 sections exist**: Header+Quick Stats, Active Tasks, Completed Tasks, Archive
- **If any other sections exist** (e.g., "Recent Activity", "Notes", "Recently Completed", "This Week", "This Month", "Archives"), DELETE them entirely
- The file must contain ONLY the 4 required sections

#### 7.4 Organization Validation
- **ZERO completed tasks** in Active Tasks section - **MUST VERIFY NO CHECKMARKED TASKS REMAIN**
- **ALL completed tasks** in Completed Tasks section - no orphaned completed tasks
- Completed Tasks section is a simple list with NO time-based subsections
- **CRITICAL**: Active Tasks section must contain ONLY `- [ ]` (unchecked) tasks

#### 7.5 Archive Validation
- **Archive section exists** with single-line format only
- **Approximately 80%** of completed tasks are archived
- **Approximately 20%** most recent tasks remain visible
- **All archived tasks** have compressed format: `- {TaskID}: {description}`
- **No checkboxes** in Archive section

#### 7.6 Workflow Files Cleanup Validation
- Verify workflow files for archived tasks are removed
- Check `.workflows/` directories for orphaned files
- Confirm no broken references remain

#### 7.7 Format Validation
- Checkboxes properly formatted: `- [ ]` or `- [x]`
- TaskIDs in bold format: `**{TaskID}**`
- No duplicate tasks

## Output Messages

### Success Messages:
```
✅ Reorganized todos.md successfully
  - {N} tasks received new TaskIDs
  - {N} duplicate TaskIDs fixed and renamed
  - {N} completed tasks moved to Completed Tasks section
  - {N} tasks archived (80% rule applied)
  - {N} workflow files cleaned up
  - {N} unnecessary sections removed
  - Active Tasks now contains only {count} active tasks
  - Quick Stats updated with completion and archive metrics
  - File now contains exactly 4 required sections
```

### Warning Messages:
```
⚠️ Warning: Found {N} tasks without TaskIDs - assigned automatically
⚠️ Warning: Found {N} duplicate TaskIDs - renamed all to unique TaskIDs
⚠️ Warning: Created Completed Tasks section - {N} tasks moved
⚠️ Warning: Found {N} completed tasks in Active Tasks section - moved
⚠️ Warning: Archived {N} old tasks (80% rule) - {N} workflow files removed
⚠️ Warning: Removed {N} unnecessary sections to comply with 4-section structure
⚠️ Warning: Some workflow files not found for archived tasks
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
- [x] **P2-CB-A124** Update docs
  - **Completed**: 2025-01-14 19:00:00
  - **Method**: Task reorganization
  - **Files Modified**: todos.md
  - **Impact**: Added TaskID and proper organization

- [x] **P0-CB-A125** Fix crash
  - **Completed**: 2025-01-11 14:30:00
  - **Method**: Task reorganization
  - **Files Modified**: todos.md
  - **Impact**: Added TaskID and proper organization
```

### When there are many completed tasks (80% archiving):
```bash
# Input todos.md has 10 completed tasks:
## Completed Tasks
- [x] **P2-CB-A120** Recent task 1
- [x] **P1-CB-A119** Recent task 2
- [x] **P2-CB-A118** Task from 3 days ago
- [x] **P3-CB-A117** Task from 5 days ago
- [x] **P1-CB-A116** Task from 6 days ago
- [x] **P2-CB-A115** Task from 2 weeks ago
- [x] **P3-CB-A114** Task from 3 weeks ago
- [x] **P1-CB-A113** Task from 4 weeks ago
- [x] **P2-CB-A112** Old task from last month

# Output todos.md (80% = 8 tasks archived, 20% = 2 tasks visible):
## Completed Tasks
- [x] **P2-CB-A120** Recent task 1
  - **Completed**: 2025-01-14 19:00:00
  - **Method**: ...
- [x] **P1-CB-A119** Recent task 2
  - **Completed**: 2025-01-14 18:00:00
  - **Method**: ...

## Archive

### 2025-01
- P1-CB-A112: Old task from last month
- P1-CB-A113: Task from 4 weeks ago
- P3-CB-A114: Task from 3 weeks ago
- P2-CB-A115: Task from 2 weeks ago
- P1-CB-A116: Task from 6 days ago
- P3-CB-A117: Task from 5 days ago
- P2-CB-A118: Task from 3 days ago

# Workflow files removed:
# - .workflows/plan-P1-CB-A112.md
# - .workflows/postmortem-P3-CB-A114.md
# - (etc. for all archived tasks)
```

## Best Practices

### When to Use:
- After running `/update-todos --init` to clean up initial tasks
- When you notice tasks without TaskIDs
- When you notice duplicate TaskIDs in the file
- When completed tasks accumulate in Active Tasks section
- When file has extra sections that should be removed
- Before major task management operations
- Periodic maintenance (weekly/monthly) to archive old tasks and clean up workflow files

### Before Running:
- Ensure todos.md exists (run `/update-todos --init` if needed)
- Backup important todos.md if needed
- Review current task organization

### After Running:
- Verify Active Tasks only contains incomplete work
- Verify ALL TaskIDs are unique
- Check Completed Tasks section for proper organization (simple list, 20% most recent visible)
- Review Archive section for compressed old tasks
- Confirm file has exactly 4 sections (no extra sections)
- Confirm workflow files for archived tasks are cleaned up
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
- **Single Purpose**: Handles TaskID uniqueness verification, TaskID coverage, organization cleanup, and archive management
- **No Analysis**: Doesn't analyze code or git changes
- **No Content Generation**: Only reorganizes and compresses existing content
- **Simple and Reliable**: Clear, predictable behavior with 80/20 rule for archiving
- **Strict Structure**: Enforces exactly 4 sections in todos.md file

### Critical Requirements:
1. **TaskID Uniqueness**: Every TaskID in the file must be unique - duplicates are renamed
2. **TaskID Coverage**: Every task must have a TaskID - missing TaskIDs are generated
3. **4-Section Structure**: File must contain exactly 4 sections - extra sections are deleted
4. **Organization**: Completed tasks in Completed Tasks section only, no time-based subsections

### Complementary to update-todos:
- `update-todos` → Content analysis and new task generation
- `reorganize-todos` → TaskID uniqueness verification, coverage, organization cleanup, and archive management
- `do` → Task execution using TaskIDs

This separation ensures each command has a clear, focused responsibility and reduces complexity.