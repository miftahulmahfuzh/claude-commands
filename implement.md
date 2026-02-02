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

**Extract from new sections:**
- **User Input**: Original user request, context, error messages, notes
- **Detailed Requirements Understanding**: Claude's technical interpretation
- **Analysis Type**: Bug | Feature | Update | Refactor (informs implementation approach)

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

### Step 4 & 5: Update todos.md and Create Implementation Plan via Subagent

**CRITICAL: You MUST use a subagent for Steps 4 and 5.**

This keeps the main context clean for the actual code implementation work.

**DO NOT** update todos.md or create the implementation plan in the main context.

#### Subagent Instructions

Dispatch a subagent with the following prompt template:

```
You are implementing Steps 4 and 5 of the /implement command.

**Inputs:**
- Analysis file: {code_analyzer.md path}
- Path: {path}
- TaskID: {TaskID}
- Priority: {P0-P4}
- Package code: {from todos.md header}
- Note: {additional note if provided}

**Step 4: Add Task to todos.md**

Read {path}/.workflows/todos.md and add the task to the appropriate priority section:

```markdown
- [ ] **{TaskID}** {Brief title from analysis}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Type**: {Bug|Feature|Update|Refactor}
  - **Context**: {Summary from "Detailed Requirements Understanding" section}
  - **Status**: in_progress
  - **Plan**: `.workflows/plan/{TaskID}.md`
```

Tip: Use the "Detailed Requirements Understanding" section for context - it's already technical and precise.

**Step 5: Create Implementation Plan**

Create {path}/.workflows/plan/{TaskID}.md with this structure:

```markdown
# Implementation Plan: {TaskID}

**TaskID**: {TaskID}
**Type**: {Bug|Feature|Update|Refactor}
**Created**: {YYYY-MM-DD HH:MM:SS}
**Analysis Source**: {code_analyzer.md filename}

---

## User Context

<Copy from "User Input" section - preserves original request>

## Requirements Understanding

<Copy from "Detailed Requirements Understanding" section - technical interpretation>

---

## Summary

{One-paragraph technical summary - reference "Detailed Requirements Understanding"}

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

**CRITICAL Plan Requirements:**
- ALL code blocks must be COMPLETE and runnable
- NO placeholders like `// ... existing code`
- NO abbreviated struct definitions
- FULL functions that can be directly implemented

**Your Output:**
When complete, report back with:
1. TaskID created
2. Priority level assigned
3. Brief task title
4. Full path to plan file created
5. Summary of what was done

**Important:**
- Keep the implementation plan CONCISE - focus on code changes
- Trust the analysis - don't re-analyze what's already documented
- If any aspect of the analysis is unclear, ask for clarification using AskUserQuestion
- When in doubt, ask - never guess and proceed
```

#### After Subagent Completes

The subagent will return:
- **TaskID**: The generated task identifier
- **Priority**: P0-P4 level
- **Title**: Brief task title
- **Plan path**: `.workflows/plan/{TaskID}.md`

Verify these values before proceeding to Step 6.

### Step 4 (Original): Add Task to todos.md

**DELEGATED TO SUBAGENT** - See Step 4 & 5 above.

### Step 5 (Original): Create Implementation Plan

**DELEGATED TO SUBAGENT** - See Step 4 & 5 above.

### Step 6: Execute Implementation (Main Context)

**CRITICAL: This step runs in the MAIN context after the subagent completes.**

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

## Handling Confusion

### During Implementation Plan Creation (Step 5 - Subagent)

If any aspect of the analysis is unclear, ambiguous, or has multiple valid approaches:

1. **STOP** and ask clarifying questions using the `AskUserQuestion` tool
2. **Provide your own recommendation** with rationale for each option
3. **Wait for user response** before proceeding

**Common scenarios requiring clarification:**
- Multiple ways to implement a feature
- Ambiguous error handling requirements
- Conflicting signals in the analysis
- Breaking changes that affect other code
- Performance vs simplicity trade-offs

**Example question format:**
```
Question: How should we handle X?
Options:
- Option A (Recommended): Do Y because Z
- Option B: Do Q because R
```

### During Code Implementation (Step 6 - Main Context)

If issues arise during actual code changes:

1. **STOP** and identify the confusion
2. **Ask clarifying questions** using `AskUserQuestion` tool
3. **Provide your own recommendation** based on:
   - Code consistency with existing patterns
   - Best practices for the language/framework
   - Minimal changes principle
4. **Wait for user response** before making changes

**Common scenarios requiring clarification:**
- Actual code structure differs from analysis
- Unexpected dependencies or side effects
- Missing information in the analysis
- Conflicts with other files not in scope
- Need for additional refactoring discovered during implementation

## Notes

- Keep implementation plan CONCISE - focus on code changes
- Token efficiency matters - avoid verbose explanations in plan
- Trust the analysis - don't re-analyze what's already documented
- **User Context** section preserves why this work is being done
- **Requirements Understanding** section is your technical blueprint
- If `-note` provided, it supplements (not replaces) the analysis
- Success Criteria from Requirements Understanding should drive testing plan
- **When in doubt, ask - never guess and proceed**

## Context Management

**Why use a subagent for Steps 4 & 5:**

The subagent handles all the documentation work (updating todos.md and creating the implementation plan) in a separate context. This:

1. **Keeps main context clean**: The main conversation only contains the actual code implementation work
2. **Reduces token usage**: Documentation details don't pollute the main context during code changes
3. **Improves focus**: When implementing code, the main context has only relevant implementation details
4. **Preserves handoff clarity**: The subagent returns structured output (TaskID, priority, title, plan path) that the main context uses

**Data flow:**
```
Main Context (Steps 1-3)
    → Generate TaskID, prepare inputs
    ↓
Subagent (Steps 4-5)
    → Update todos.md
    → Create implementation plan
    → Return: TaskID, Priority, Title, Plan path
    ↓
Main Context (Step 6)
    → Execute implementation with clean context
```
