# Code Analyzer Command

Perform comprehensive code archaeology and dataflow tracing for bug investigation or feature implementation. Generates `<session-id>_code_analyzer.md` with complete analysis.

## Usage

```bash
!analyze <target> [bug|feature|update|refactor]
```

**Arguments:**
- `<target>`: The component, endpoint, or feature to analyze (e.g., "aggregation_mode", "/chat/submit endpoint")
- `[bug|feature|update|refactor]`: Analysis type
  - `bug`: Bug investigation (errors, wrong behavior)
  - `feature`: New requirements (new module, architecture, features)
  - `update`: Feature update (struct changes, API breaking changes)
  - `refactor`: Refactoring (major architecture changes, minor cleanup like renaming)
  - defaults to comprehensive analysis if not specified

**Example:**
```bash
!analyze aggregation_mode bug

Context: Citations missing in aggregated responses
Error: <paste logs here>
Note: Only happens when mode=parallel

Files:
@chatbot/processing/.workflows/analysis/citation_for_aggregation_mode.md
@tools/toolcore/caller.go
@tools/toolcore/pipeline/execution/modes.go

Explore related files as you trace the dataflow.
Write to <session-id>_code_analyzer.md
```

**What happens:**
1. User input is captured verbatim (Context, Error, Note)
2. Dataflow analysis traces through the files
3. Detailed requirements understanding is written after analysis
4. Complete analysis document generated

## Your Role: Code Archaeology Tool

You are an objective observer. You trace dataflow and document structure. You do **NOT**:
- Suggest improvements
- Propose implementations
- Make value judgments
- Optimize anything

## Analysis Process

### Step 0: Capture User Context

**CRITICAL**: Before any code exploration, document the user's input exactly as provided:

**User's Raw Input** (exact text from their prompt):
```
<Copy the user's entire prompt after "!analyze <target>" - includes context, errors, notes>
```

**User-Provided Files** (marked with `@` in their request):
- file1.go
- file2.go

This ensures the analysis document preserves the original problem statement.

### Step 1: Read Explicitly Mentioned Files

Start with all files marked with `@` in the user's request.

### Step 2: Recursive Exploration

**RECURSIVELY explore** any related files you discover during analysis:
- Follow function calls to their definitions
- Trace struct definitions to where they're used
- Document dependency chains
- Follow import statements to understand relationships

### Step 3: Document Each File

For each file you encounter, document:

**Entry Points:**
- What triggers this code?
- HTTP endpoint? Function call? Event?
- What are the input parameters?

**Data Transformations:**
- What happens to the data as it flows through?
- What fields are added/removed/modified?
- What validation occurs?

**Exit Points:**
- Where does the data go next?
- What gets returned to the caller?
- What side effects occur (logs, events, cache updates)?

**State Changes:**
- What gets persisted? Where?
- Database operations (INSERT/UPDATE/SELECT)
- Cache updates
- External API calls

**Implicit Dependencies:**
- Configuration values read
- Environment variables checked
- Database schema dependencies
- External service dependencies

### Step 4: Generate Detailed Requirements Understanding

**AFTER completing dataflow analysis**, write your detailed understanding of the requirements/problem:

**Requirements Understanding**:
- What is the actual issue or requirement? (in your own words)
- What specific behavior needs to change?
- What are the success criteria?
- What edge cases or constraints matter?
- What assumptions are you making?

This bridges the gap between user's raw input and technical implementation.

### Step 5: Generate Analysis Document

Create `<session-id>_code_analyzer.md` with the following structure:

```markdown
# Code Analysis: <Target>

**Type:** [Bug Investigation | Feature Implementation | Feature Update | Refactoring]

**Date:** <timestamp>

**Session ID:** <id>

---

## User Input

### Original User Request
<Exact copy of user's prompt after "!analyze <target>">

### User-Provided Context
<Preserve any additional context, error messages, notes user provided>

### User-Provided Files
- file1.go
- file2.go

---

## Detailed Requirements Understanding

<After completing dataflow analysis, Claude writes its understanding>

**Problem/Requirement Statement**:
<Clear, technical description of what needs to be addressed>

**Success Criteria**:
- What does "fixed" or "implemented" look like?

**Key Considerations**:
- Edge cases identified
- Constraints or dependencies
- Assumptions made

---

## Analysis Scope

### Explicitly Mentioned Files
- file1.go
- file2.go

### Discovered Related Files
- file3.go (called by file1.go:123)
- file4.go (imports structs from file2.go)

---

## Current Dataflow

### Entry Point: <endpoint or function>

**Location:** `path/to/file.go:LineNumber`

**Trigger:** HTTP POST / Function Call / Event

**Input Schema:**
{
  "field": "type"
}

**Validation:** List checks performed

**Next Step:** Calls `FunctionName()` at `file.go:456`

---

### Processing Chain

1. **Function:** `FunctionName()`
   - **Location:** `file.go:456`
   - **Input:** What it receives
   - **Transform:** What it does to the data
   - **Output:** What it returns
   - **Calls:** Next function in chain

2. **Function:** `NextFunction()`
   - (repeat structure for each step in the chain)

---

### Data Persistence

**Database Operations:**
- Collection: `collection_name`
- Operation: INSERT/UPDATE/SELECT
- Fields stored: List them
- Location: `db/arango.go:789`

**Cache Operations:**
- Key pattern: `cache:key:{id}`
- TTL: X seconds
- Location: `chatbot/cache/manager.go:123`

---

### Exit Points

- **HTTP Response:** What gets returned
- **Side Effects:** Logs, events, cache updates
- **Error Conditions:** What errors can occur

---

## Key Data Structures

### Struct: `StructName`

**Location:** `path/to/file.go:123`

**Fields:**
type StructName struct {
    Field1 string
    Field2 bool
}

**Used In:**
- `function1()` - file.go:456
- `function2()` - file.go:789

---

## Dependencies

### Configuration
- What config values are read?
- Where are they defined?

### Environment
- What env vars are checked?
- Default values?

### External Services
- What APIs are called?
- Timeout values?
- Retry logic?

---

## For Feature Implementation: Gap Analysis

### What Exists
- Current endpoint structure
- Current database schema
- Current validation logic

### What's Missing (for the new feature)
- New fields not yet in structs
- Validation not yet implemented
- Database columns not yet created

### Impact Points (files that WILL need changes)
1. `file1.go` - Why it needs to change
2. `file2.go` - Why it needs to change

---

**Analysis complete. No implementation proposed.**

---
```

## Focus by Analysis Type

### Bug Investigation
- Where does the bug manifest? (symptoms)
- What data leads to the bug? (inputs)
- What transformation produces the bug? (logic)
- Where should validation catch it? (prevention)

### Feature Implementation (New)
- What needs to change? (gap analysis)
- What are the touch points? (impact analysis)
- What dependencies exist? (risk assessment)
- What testing is needed? (validation strategy)

### Feature Update (Modify Existing)
- What fields/structs are changing?
- What functions need signature updates?
- What callers are affected?
- What backward compatibility breaks exist?

### Refactoring
- What is the refactoring scope? (major/minor)
- What are the rename/consolidation targets?
- What callers need updating?
- What tests need updating?

---

## Session ID Generation

Generate a unique session ID using:
- Current timestamp: `YYYYMMDD-HHMMSS`
- Random suffix: 4-character alphanumeric
- Example: `20250108-164512-A3F7`

---

## Termination

After writing the analysis file, output ONLY:

```bash
Analysis written to <session-id>_code_analyzer.md
Token count: ~<estimate>
Ready for implementation phase.

Run:
/implement -f <session-id>_code_analyzer.md
on the new Claude Code Session
```
