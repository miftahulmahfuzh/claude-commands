# Implement Command

Execute implementation based on `/analyze` output. Creates task, generates plan, and implements.

## Usage

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

## Process

### Step 1: Read Analysis File

Read the code_analyzer.md file from `-f` parameter. This is your ground truth.

### Step 2: Determine Path

**If `-p` provided:**
- Use that path

**If `-p` NOT provided:**
- Parse all file paths in code_analyzer.md
- Choose most appropriate `.workflows/` location based on:
  - Files with most changes
  - Core package vs dependencies
  - Directory structure depth

**Validation:**
- Check if `{path}/.workflows/todos.md` exists
- If missing: **STOP** and tell user: `Run /update-todos {path} --init first`

### Step 3: Generate TaskID

Use package code from existing todos.md header. Generate next available TaskID:
- Format: `P{Priority}-{PackageCode}-{4CharID}`
- Analyze analysis to determine priority (P0-P4)
- Use next sequential 4CharID (A000, A001... A999, B000...)

### Step 4: Add Task to todos.md

**Add to appropriate priority section in Active Tasks:**
```markdown
- [ ] **{TaskID}** {Brief title from analysis}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Context**: {Summary from "For Feature Implementation: Gap Analysis" section}
  - **Status**: in_progress
  - **Plan**: `.workflows/plan/{TaskID}.md`
```

### Step 5: Create Implementation Plan

Create `{path}/.workflows/plan/{TaskID}.md`:

```markdown
# Implementation Plan: {TaskID}

**TaskID**: {TaskID}
**Created**: {YYYY-MM-DD HH:MM:SS}
**Analysis Source**: {code_analyzer.md filename}
**User Notes**: {-note content if provided}

---

## Summary

{One-paragraph summary from analysis}

## Scope

### Files to Modify
- `file1.go` - {what changes}
- `file2.go` - {what changes}

### Dependencies
- {external packages or services}

---

## Implementation Steps

### Step 1: {Title}
**File**: `{path/file.go}`

**Change**: {description}

**Code**:
```go
// FULL code block - complete functions/structs
// NO placeholders or "..." abbreviations
```

**Impact**: {what breaks/changes}

---

### Step 2: {Title}
{repeat for each step}

---

## Testing Plan
1. {test case}
2. {test case}

## Rollback Plan
{if implementation fails}
```

**CRITICAL:**
- ALL code blocks must be COMPLETE and runnable
- NO placeholders like `// ... existing code`
- NO abbreviated struct definitions
- FULL functions that can be directly implemented

### Step 6: Execute Implementation

Follow the plan sequentially:
1. For each step: Read the file, make changes
2. Mark task as completed in todos.md after implementation
3. Update task status to `completed`

## Output Format

After implementation completes:

```
✓ Implementation complete: {TaskID}

Files modified:
- file1.go
- file2.go

Updated todos.md
Plan saved to: .workflows/plan/{TaskID}.md
```

## Termination

**If successful:**
```
✓ Implementation complete: {TaskID}

Files modified: {count}
Plan: .workflows/plan/{TaskID}.md
```

**If todos.md missing:**
```
✗ Error: todos.md not found in {path}/.workflows/

Run: /update-todos {path} --init
```

## Notes

- Keep implementation plan CONCISE - focus on code changes
- Token efficiency matters - avoid verbose explanations in plan
- Trust the analysis - don't re-analyze what's already documented
- User notes take precedence over analysis assumptions
