# Update Todos Command

Update `{directory_path}/.workflows/todos.md` based on git changes, code analysis, and existing documentation.

## Arguments
- Required: `{directory_path}` (e.g., `chatbot/bowl`)
- Optional: `--since=<commit_hash>` (default: `HEAD~1`)
- Optional: `--init` (force initialization mode even if todos.md exists)
- Optional: `--package-code=<CODE>` (override package code and migrate all TaskIDs)

## Execution Modes

### Mode 1: Active Session Update (Default when context is available)
User is in active coding session and wants to log what just happened.

Use context from:
- Current conversation history (what bugs were fixed, features added)
- Git diff of uncommitted/staged changes
- Code comments added in this session

### Mode 2: Post-Commit Update (Default when --since provided or no session context)
User already committed changes and wants to retroactively update todos.

Use:
- Git diff between commits
- Commit messages
- Changed files analysis

### Mode 3: Package Code Override (When --package-code provided)
User wants to change the package code and migrate all existing TaskIDs.

Use:
- Current todos.md file
- All existing TaskIDs need migration
- Update Package Code in header
- Rebuild TaskIDs with new package code

### Mode 4: Initialization (When --init or todos.md doesn't exist)
User wants to create initial todos.md or regenerate it.

Use:
- Existing documentation files
- Static code analysis
- Current state of package

## Prerequisites Check

### Required Files
1. `{directory_path}/.workflows/package_readme.md`
   - If missing: abort and tell user to run `/update-readme {directory_path}`
   - Why: Need to understand package structure to identify issues

### Optional Files (enhance analysis)
2. `{directory_path}/.workflows/analysis_report.md`
   - If present: extract issues to add as tasks
   - If missing: skip advanced analysis tasks

3. `{directory_path}/.workflows/unittest_guide.md`
   - If present: check test coverage mentions
   - If missing: note in todos that test documentation is missing

### Directory Setup
- Verify `{directory_path}/.workflows/` exists
- Create if missing
- Check if `todos.md` exists to determine mode

## Process Flow

### Step 1: Determine Execution Mode

```
IF --package-code flag present:
    MODE = Package Code Override
ELSE IF --init flag present OR todos.md doesn't exist:
    MODE = Initialization
ELSE IF conversation context has code changes OR git has uncommitted changes:
    MODE = Active Session Update
ELSE IF --since flag present OR last commit touches {directory_path}:
    MODE = Post-Commit Update
ELSE:
    ABORT: "No changes detected. Nothing to update."
```

### Step 1.1: Generate Package Code
For each package, generate a unique 2-3 letter code:
- Extract from package name (last part of path)
- `db` → `DB`
- `chatbot/bowl` → `CB` (from Chatbot Bowl)
- `core/cache` → `CC` (from Core Cache)
- `tools/processor` → `TP` (from Tools Processor)
- If conflict exists across packages, use longer code or add number suffix

### Step 1.2: TaskID Generation System

#### 🔴 CRITICAL: TaskID Uniqueness Requirement

**EVERY TaskID in the todos.md file MUST BE UNIQUE.**

1. **Before generating ANY new TaskID**: You MUST scan the ENTIRE todos.md file and collect ALL existing TaskIDs
2. **Verify uniqueness**: The new TaskID you generate MUST NOT exist anywhere in the file
3. **If duplicate found**: You MUST rename ALL duplicate TaskIDs to new, unique values
4. **If task has no TaskID**: You MUST generate a new, unique TaskID for that task

**Failure to ensure TaskID uniqueness is a critical error.**

#### TaskID Format
Format: `Priority-PackageCode-4CharID`

**Generation Logic:**
1. Scan ENTIRE todos.md file and collect ALL existing TaskIDs (Active Tasks, Completed Tasks, Archive sections)
2. Extract all used 4CharIDs for this package
3. Generate next available 4CharID in sequence:
   - Start with `A000`, `A001`, ..., `A999`
   - Then `B000`, `B001`, ..., `B999`
   - Continue through `Z999`
4. **CRITICAL**: Verify the generated TaskID does NOT exist in the collected TaskIDs
5. If it exists, increment to the next available ID until you find a unique one
6. Combine: `[Priority]-[PackageCode]-[4CharID]`

**Example:**
- Package `db` has existing tasks: `P1-DB-A236`, `P0-DB-A237`
- Scan entire file, find these are the only TaskIDs
- Next task with P1 priority → Check if `P1-DB-A238` exists → If not, use it
- Next task with P0 priority → Check if `P0-DB-A238` exists → If not, use it

### Step 2: Package Code Override Process (When --package-code provided)

1. **Validate New Package Code**:
   - Check format: 2-3 uppercase letters (A-Z)
   - Verify no conflicts with existing package codes in project
   - Ensure it's different from current package code

2. **Load Current todos.md**:
   - Read all existing tasks and their TaskIDs
   - Extract current package code from header
   - Build migration map of old TaskID → new TaskID

3. **Generate TaskID Migration Map**:
   ```
   Old TaskID: P1-OLD-A123 → New TaskID: P1-NEW-A123
   Old TaskID: P0-OLD-B456 → New TaskID: P0-NEW-B456
   ```
   - Keep same priority and 4CharID
   - Only change the package code portion

4. **Update Header**:
   - Change "Package Code: OLD" to "Package Code: NEW"

5. **Migrate All TaskIDs**:
   - Update TaskIDs in Active Tasks section
   - Update TaskIDs in Recent Activity section
   - Update TaskIDs in Archive section
   - Update all task references and cross-links

6. **Validate Migration**:
   - Ensure no duplicate TaskIDs after migration
   - Verify all TaskIDs use new package code
   - Check Quick Stats still match

### Step 3: Load Context Files (Other Modes)

Read in order:
1. `package_readme.md` - understand package structure
2. `analysis_report.md` (if exists) - get known issues
3. `unittest_guide.md` (if exists) - check test documentation
4. `todos.md` (if exists) - get existing tasks

### Step 4: Critical Pre-processing - Ensure Complete TaskID Coverage and Organization

#### ⚠️ CRITICAL: Scan EVERY Task in todos.md for TaskIDs and Uniqueness

**BEFORE processing ANY changes, perform comprehensive scan of the ENTIRE todos.md file:**

1. **Check ALL Sections**: Active Tasks, Completed Tasks, Archive sections
2. **Collect ALL existing TaskIDs** into a set for uniqueness verification
3. **Look for ANY tasks without TaskIDs**:
   - Active tasks: `- [ ] {description}` (missing **{TaskID}**)
   - Completed tasks: `- [x] {description}` (missing **{TaskID}**)
   - Plain text descriptions without TaskID prefixes
4. **Assign TaskIDs to ALL missing tasks** using the TaskID generation system in Step 1.2
5. **NEVER skip this step** - even if todos.md looks complete, scan it thoroughly
6. **Priority-based TaskID assignment**:
   - Analyze task content to determine appropriate priority (P0-P4)
   - Generate TaskID: `{Priority}-{PackageCode}-{4CharID}`
   - **CRITICAL**: Verify generated TaskID is unique against collected TaskIDs
   - **If duplicate found**: Generate a new, unique TaskID
   - Update ALL occurrences of the task description with the new TaskID

7. **Detect and Fix Duplicate TaskIDs**:
   - After collecting all TaskIDs, check for duplicates
   - If ANY TaskID appears more than once, you MUST rename each duplicate
   - Generate new unique TaskIDs for all duplicates using next available sequence
   - Update all references to use the new TaskIDs

#### ⚠️ CRITICAL: Handle Completed Tasks Organization

After TaskID assignment and duplicate detection, check for completed tasks organization:

1. **Verify Completed Tasks Section Exists**:
   - If `## Completed Tasks` section doesn't exist, CREATE IT
   - Use this exact structure (simple list, no time divisions):
     ```markdown
     ## Completed Tasks

     - [x] **{TaskID}** {Task description}
       - **Completed**: {YYYY-MM-DD HH:MM:SS}
       - **Method**: {brief description}
       - **Files Modified**: {list of files}
       - **Impact**: {summary}

     - [x] **{TaskID}** {Task description}
       - **Completed**: {YYYY-MM-DD HH:MM:SS}
       - **Method**: {brief description}
       - **Files Modified**: {list of files}
     ```

2. **Move ALL Checkmarked Tasks**:
   - Find ALL tasks with `- [x]` format
   - Move them from Active Tasks to Completed Tasks section (simple list, newest first)
   - Add completion details (timestamp, method, files, impact)
   - **Do NOT leave any completed tasks in Active Tasks section**

3. **Respect Archive Section Structure**:
   - Archive section exists as single-line format with bullet: `- {TaskID}: {description}`
   - Example:
     ```markdown
     ## Archive

     ### {YYYY-MM}
     - P1-CB-A112: Old task from last month
     - P1-CB-A113: Task from 4 weeks ago
     ```
   - **NEVER convert Archive items back to full format with checkboxes**
   - Archive is read-only - items stay compressed

4. **Update Quick Stats**:
   - Count active vs completed tasks
   - Update all statistics to reflect new organization

#### ⚠️ CRITICAL: Difficulty Field Assignment and Validation
After TaskID assignment and completed tasks organization:

1. **Analyze ALL Tasks for Difficulty Assignment**:
   - **Scan EVERY section**: Active Tasks, Completed Tasks, Recent Activity, Archive, Blocked
   - **Look for ANY tasks without Difficulty field** - missing `- **Difficulty**: {EASY|NORMAL|HARD}`
   - **NEVER skip this step** - even if tasks look complete, verify Difficulty exists

2. **Assign Difficulty Based on Assessment Criteria**:
   - **EASY**: Simple, isolated changes with minimal impact and low error risk
   - **NORMAL**: Moderate complexity changes with limited scope and some external considerations
   - **HARD**: Complex, high-impact changes with extensive testing requirements and high error susceptibility

3. **Validate Difficulty Assignment**:
   - Ensure Difficulty value matches task complexity and impact assessment
   - HARD tasks must have sufficient context explaining complexity
   - Difficulty must be exactly one of: EASY, NORMAL, HARD (case-sensitive)
   - **Do NOT proceed until ALL tasks have valid Difficulty field**

#### For Active Session Update:
1. Parse conversation history for:
   - Bug descriptions and fixes
   - Feature implementations
   - Refactoring discussions
   - Performance improvements
   - Breaking changes mentioned

2. Run `git diff` on {directory_path}:
   - Staged changes: `git diff --cached -- {directory_path}`
   - Unstaged changes: `git diff -- {directory_path}`

3. Parse code changes for:
   - New functions added
   - Functions modified
   - Functions deleted
   - New TODO/FIXME/HACK comments
   - Removed TODO comments (mark as completed)
   - New error handling
   - New dependencies added

#### For Post-Commit Update:
1. Get commit range:
   ```bash
   git log {since_commit}..HEAD --oneline -- {directory_path}
   ```

2. For each commit, extract:
   - Commit hash (short)
   - Commit message
   - Author and timestamp
   - Files changed in {directory_path}

3. Run `git diff {since_commit}..HEAD -- {directory_path}` and parse:
   - Function-level changes (added/modified/deleted)
   - TODO comment changes
   - Import changes (new dependencies)
   - Test file changes (but don't document test details)

4. Analyze commit messages for keywords:
   - `fix`, `bug`, `crash`, `issue` → completed bug fix
   - `feat`, `add`, `implement` → completed feature
   - `refactor`, `cleanup`, `improve` → completed refactoring
   - `WIP`, `TODO`, `temporary` → ongoing work
   - `breaking` → breaking change (high priority to document)

#### For Initialization:
1. Read all `.go` files in {directory_path} (exclude tests)

2. Extract from code:
   - All TODO comments with location (file:line)
   - All FIXME comments with location
   - All HACK comments with location
   - All BUG comments with location
   - Functions with `panic()` calls (potential issues)
   - Functions with `// deprecated` comments

3. Extract from `analysis_report.md` if exists:
   - Critical Issues section → P0 tasks
   - Refactoring Opportunities → P1/P2 tasks
   - Performance Notes → P1 tasks
   - Dead code candidates → P2 cleanup tasks
   - Functions that should be exported → P2 API tasks

4. Extract from `package_readme.md`:
   - Gotchas section → document or fix
   - Anti-patterns section → create tasks to prevent
   - Missing functionality mentioned in "Notes"

5. Cross-reference with reverse dependencies:
   - If package is heavily used but missing documentation → P1 doc task
   - If exported functions never used → P2 consider unexporting

### Step 5: Classify Changes

#### Completed Tasks ✓
- Removed TODO comments from code
- Bug fixes (from commit messages or session context)
- Features fully implemented
- Refactoring finished
- Tests added (if mentioned but not documented in unittest_guide.md)

#### New Additions 📝
- New functions that need documentation
- New features that need testing
- New dependencies introduced
- New public API that needs examples
- Breaking changes that need migration guide

#### Identified Issues 🔍
- New TODO comments added to code
- Bugs found during session
- Performance problems observed
- Missing error handling (from analysis_report.md)
- Code smells (complex functions, duplicate logic)
- Security concerns (unvalidated input, race conditions)

#### Ongoing Work 🔄
- Partially implemented features
- WIP commits
- Features spanning multiple commits
- Gradual refactoring in progress

#### Blocked Tasks 🚫
- Tasks waiting on external dependencies
- Tasks requiring design decisions
- Tasks blocked by other packages

### Step 6: Difficulty Assessment and Priority Assignment

#### Difficulty Assessment (MANDATORY)

**ALL tasks must have a Difficulty field assigned**. Analyze each task and assign one of three difficulty levels:

**[EASY]** - Simple, low-risk changes:
- Isolated code modifications with minimal dependencies
- Simple bug fixes with clear reproduction steps
- Documentation updates that don't affect API behavior
- Adding or removing non-critical validation
- Small refactoring of single functions (<30 lines)
- Changes with limited or no external API impact
- Low error susceptibility and straightforward testing

**[NORMAL]** - Moderate complexity changes:
- Refactoring multiple related functions or small modules
- Adding new features with limited external dependencies
- Moderate bug fixes affecting multiple code paths
- API changes that require backward compatibility considerations
- Performance optimizations with measurable impact
- Changes affecting multiple files but limited scope
- Moderate error susceptibility requiring careful testing

**[HARD]** - Complex, high-impact changes:
- Major architectural refactoring or redesign
- Breaking API changes requiring migration guides
- Complex algorithm implementations with high performance requirements
- Changes affecting core package functionality used by multiple packages
- Security fixes requiring extensive validation
- Database schema changes or data migration
- High error susceptibility with critical failure modes
- Changes requiring extensive integration and regression testing

#### Difficulty Assessment Examples

**Example 1 - EASY**:
```markdown
- [ ] **P2-CL-A001** Fix typo in error message in logger.go:45
  - **Difficulty**: EASY
  - **Context**: Simple text correction with no functional impact
```

**Example 2 - NORMAL**:
```markdown
- [ ] **P1-DB-A236** Add input validation to ProcessData function
  - **Difficulty**: NORMAL
  - **Context**: Affects multiple code paths but limited to single package
  - **Files**: manager.go, validator.go
```

**Example 3 - HARD**:
```markdown
- [ ] **P1-BC-A123** Refactor InitiateAndManageBroadcast function into smaller methods
  - **Difficulty**: HARD
  - **Context**: 146-line function with cyclomatic complexity of 12, affects external API
  - **Current State**: Function has cyclomatic complexity of 12 and manages 4 different phases
  - **Suggested Split**:
    - `validatePreFlightConditions()`
    - `waitForClientConnection()`
    - `acquireLLMSlot()`
    - `manageBroadcastLoop()`
  - **Impact**: Improved testability, readability, and maintainability
  - **Location**: manager.go:98-242
```

#### Difficulty Assessment Guidelines

**Factors to consider when assigning Difficulty:**

1. **Impact Scope**: How many parts of the codebase are affected?
   - EASY: Single function or small isolated area
   - NORMAL: Multiple related functions within a package
   - HARD: Cross-package changes or external API modifications

2. **Change Complexity**: How complex is the implementation?
   - EASY: Straightforward logic, clear solution
   - NORMAL: Moderate complexity, some edge cases to handle
   - HARD: Complex algorithms, multiple edge cases, significant logic changes

3. **Error Susceptibility**: How likely are errors to occur?
   - EASY: Low risk, simple validation, easy to test
   - NORMAL: Moderate risk, requires careful validation
   - HARD: High risk, critical failure modes, extensive testing needed

4. **External Dependencies**: How does this affect code that calls this package?
   - EASY: No external API changes
   - NORMAL: Minor API changes, backward compatible
   - HARD: Breaking changes or new dependencies required

5. **Testing Requirements**: What level of testing is needed?
   - EASY: Simple unit tests sufficient
   - NORMAL: Unit + some integration testing
   - HARD: Comprehensive unit, integration, and regression testing

#### Priority Assignment

Assign priority tags:

**[P0] Critical** - Must fix immediately:
- Security vulnerabilities
- Data corruption bugs
- Crash-causing issues
- Production blockers
- Breaking changes without migration path

**[P1] High** - Fix soon:
- Performance degradation
- Memory leaks
- Race conditions
- Major refactoring needs (>3 duplicate code blocks)
- Missing critical error handling
- API inconsistencies

**[P2] Medium** - Fix when possible:
- Code quality issues
- Minor refactoring (complex functions >100 lines)
- Missing documentation on public API
- Dead code cleanup
- Test coverage gaps

**[P3] Low** - Nice to have:
- Code style improvements
- Minor optimizations
- Internal documentation
- Convenience functions
- Example code

**[P4] Backlog** - Future consideration:
- Feature requests
- Major architectural changes
- Experimental ideas
- Tech debt without immediate impact

### Step 7: Generate/Update todos.md

#### 🔴 CRITICAL: todos.md File Structure - Exactly 4 Sections

**The todos.md file MUST contain exactly these 4 sections:**

1. **Header with Quick Stats** (metadata and statistics)
2. **Active Tasks** (with P0-P4 subsections)
3. **Completed Tasks** (simple list)
4. **Archive** (single-line compressed format)

**IF the file contains ANY other sections (e.g., "Recent Activity", "Notes", etc.), you MUST DELETE those sections entirely.**

#### Format Structure:

```markdown
# Todos: {package_name}

**Package Path**: `{directory_path}`
**Package Code**: {PACKAGE_CODE}
**Last Updated**: {YYYY-MM-DD HH:MM:SS}
**Total Active Tasks**: {count}

## Quick Stats
- P0 Critical: {count}
- P1 High: {count}
- P2 Medium: {count}
- P3 Low: {count}
- P4 Backlog: {count}
- Blocked: {count}
- Completed: {count}

---

## Active Tasks

### [P0] Critical
- [ ] **{TaskID}** {Task description} `{file:line if from code comment}`
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Context**: {Why this is critical}
  - **Identified**: {date or commit}
  - **Status**: {active|in_progress|blocked}

### [P1] High
- [ ] **{TaskID}** {Task description}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Context**: {Why this matters}
  - **Identified**: {date or commit}
  - **Related**: {link to analysis_report.md section if applicable}
  - **Status**: {active|in_progress|blocked}

### [P2] Medium
- [ ] **{TaskID}** {Task description}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Status**: {active|in_progress|blocked}

### [P3] Low
- [ ] **{TaskID}** {Task description}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Status**: {active|in_progress|blocked}

### [P4] Backlog
- [ ] **{TaskID}** {Task description}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Status**: {active|in_progress|blocked}

### 🚫 Blocked
- [ ] **{TaskID}** {Task description}
  - **Difficulty**: {EASY|NORMAL|HARD}
  - **Blocked by**: {What's blocking this}
  - **Identified**: {date}
  - **Status**: blocked

---

## Completed Tasks

- [x] **{TaskID}** {Task description}
  - **Completed**: {YYYY-MM-DD HH:MM:SS}
  - **Method**: {brief description of what was done}
  - **Files Modified**: {list of files changed}
  - **Impact**: {summary of impact}

- [x] **{TaskID}** {Task description}
  - **Completed**: {YYYY-MM-DD HH:MM:SS}
  - **Method**: {brief description of what was done}
  - **Files Modified**: {list of files changed}

---

## Archive

### {YYYY-MM}
- P1-CB-A112: Old task from last month
- P1-CB-A113: Task from 4 weeks ago
- P3-CB-A114: Task from 3 weeks ago
- P2-CB-A115: Task from 2 weeks ago
```

#### Section Deletion Rule:
- If you find ANY sections other than the 4 listed above (e.g., "Recent Activity", "Notes", "Documentation Status", etc.)
- **DELETE those sections entirely** - do not preserve their content
- The todos.md file must be clean and contain ONLY the 4 required sections

### Step 8: Task Deduplication and TaskID Management

#### 🔴 CRITICAL: TaskID Uniqueness and Duplication Handling

**Before adding ANY new tasks, you MUST perform these checks:**

1. **MANDATORY: Collect ALL Existing TaskIDs**:
   - Scan EVERY section: Active Tasks, Completed Tasks, Archive
   - Build a complete set of all TaskIDs currently in the file
   - **This is NOT optional - ALWAYS perform this check**

2. **MANDATORY: Check for Duplicate TaskIDs**:
   - After collecting all TaskIDs, check if ANY TaskID appears more than once
   - **If duplicates found**: You MUST rename EACH duplicate to a new, unique TaskID
   - Generate new unique TaskIDs using next available sequence
   - Update ALL references to use the new TaskIDs
   - **Do NOT proceed until all TaskIDs are unique**

3. **MANDATORY: Check for Tasks Without TaskIDs**:
   - Scan EVERY section for tasks missing TaskID prefixes
   - Look for patterns: `- [ ] {description}` or `- [x] {description}`
   - Assign TaskIDs to ALL missing tasks
   - **CRITICAL**: Verify each new TaskID is unique against the collected set
   - If a generated TaskID already exists, generate a new one

4. **Check for Completed Tasks Organization**:
   - Verify no `- [x]` tasks remain in Active Tasks section
   - Ensure all completed tasks are in Completed Tasks section (simple list)
   - Create Completed Tasks section if it doesn't exist

5. **Deduplication**:
   - Check if identical task exists in Active Tasks
   - Check if similar task exists (>80% text similarity)
   - If duplicate: merge contexts and update priority, keep existing TaskID
   - If similar: link them with "Related to: {TaskID}"

#### TaskID Assignment Rules:
1. **Existing tasks without TaskIDs**: Assign TaskIDs using current package code and appropriate priority based on content
2. **New tasks**: ALWAYS verify the generated TaskID does NOT exist in the file
3. **Duplicate TaskIDs**: Rename ALL duplicates to new, unique TaskIDs
4. **Priority changes**: Keep same TaskID, update priority prefix
5. **Merged tasks**: Keep TaskID of higher priority task
6. **Split tasks**: Generate new TaskIDs for split tasks, mark original as completed

#### TaskID Tracking:
- Maintain index of all TaskIDs in file for uniqueness verification
- When searching for tasks: search by TaskID first, then by description
- When referencing tasks in other commands: always use TaskID format
- Ensure complete TaskID coverage across all task sections
- **NEVER allow duplicate TaskIDs to exist in the file**

### Step 9: Task Completion and Archive Management

#### Task Completion Process:
When completing tasks:
1. **Move to Completed Tasks**: Move from Active Tasks to Completed Tasks section (simple list, newest first)
2. **Add Completion Details**: Include completion timestamp, method, files modified, and impact
3. **Update Quick Stats**: Recalculate active and completed task counts

#### Archive Maintenance:
Periodically (weekly/monthly):
- Move completed tasks to Archive section when they accumulate
- Archive format: Single-line compressed `- {TaskID}: {description}`
- Archive is read-only - items stay compressed, never expanded back
- **Do NOT add checkboxes, completion details, or metadata to Archive items**

Example Archive structure:
```markdown
## Archive

### {YYYY-MM}
- P1-CB-A112: Old task from last month
- P1-CB-A113: Task from 4 weeks ago
- P3-CB-A114: Task from 3 weeks ago
```

#### Archive Cleanup:
Every 3 months:
- Reassess P3/P4 tasks - delete if no longer relevant
- Review blocked tasks - unblock or delete
- Update Quick Stats
- If Archive section grows large, create separate archive file

## Special Handling

### Breaking Changes
If git diff shows breaking API changes:
- Create P0 task: "Document breaking change in CHANGELOG.md"
- Create P1 task: "Write migration guide for {function/type}"
- Flag all reverse dependencies that need updates

### New Dependencies
If new imports detected:
- Create P2 task: "Document why {package} was added"
- Create P2 task: "Review license compatibility of {package}"
- Note in Recent Activity

### Deleted Code
If functions/types removed:
- Mark any related tasks as completed
- Add to Archive with "Removed" tag
- Check if removal was documented in package_readme.md

### TODO Comments in Code
Map each TODO to a task:
```go
// TODO: add validation for empty input
```
Becomes:
```markdown
- [ ] [P2] Add validation for empty input in ProcessData()
  - **Location**: manager.go:145
  - **Context**: Currently panics on nil input
```

Track TODO lifespan:
- If TODO exists >3 months → escalate to P1
- If TODO exists >6 months → escalate to P0 or delete

### Test Coverage Gaps
If unittest_guide.md exists but shows low coverage:
- Create P2 tasks for missing tests on public functions
- Create P3 tasks for missing tests on internal functions
- Don't create tasks for benchmark tests

## Update Strategy

### For Active Session (Mode 1):
- Add new section at TOP of Recent Activity
- Title: "[{timestamp}] - Session Update"
- Focus on what was discussed/changed in session
- Mark relevant existing tasks as completed
- Git diff is supplementary to conversation context

### For Post-Commit (Mode 2):
- If single commit: add one section
- If 2-5 commits: add one section summarizing all
- If >5 commits: add one section per commit (newest first)
- Title format: "[{timestamp}] - Commit: {short_hash}"
- Focus on commit messages and code diff

### For Initialization (Mode 3):
- Create full structure from template
- Populate Active Tasks from code analysis
- Add single Recent Activity section: "[{timestamp}] - Initial Analysis"
- Mark status: "📊 Baseline established"

## Validation

Before saving todos.md:

### ⚠️ CRITICAL VALIDATION CHECKS

1. **TaskID Uniqueness Verification (MANDATORY)**:
   - **Scan ENTIRE file** and collect ALL TaskIDs
   - **Verify NO duplicate TaskIDs exist** - every TaskID must be unique
   - If duplicates found, STOP and rename all duplicates to unique TaskIDs
   - **Do NOT proceed until ALL TaskIDs are unique**

2. **TaskID Coverage Verification (MANDATORY)**:
   - **Scan EVERY section**: Active Tasks, Completed Tasks, Archive
   - **Verify NO task exists without TaskID** - look for patterns like `- [ ] {text}` or `- [x] {text}`
   - **ALL tasks must have format**: `- [ ] **{TaskID}** {description}` or `- [x] **{TaskID}** {description}`
   - If any task lacks TaskID, STOP and assign TaskIDs before proceeding

3. **File Structure Verification (MANDATORY)**:
   - **Verify EXACTLY 4 sections exist**: Header+Quick Stats, Active Tasks, Completed Tasks, Archive
   - **If any other sections exist** (e.g., "Recent Activity", "Notes"), DELETE them entirely
   - The file must contain ONLY the 4 required sections

4. **Difficulty Field Coverage Verification (MANDATORY)**:
   - **Scan EVERY section**: Active Tasks, Completed Tasks, Archive, Blocked
   - **Verify NO task exists without Difficulty field** - look for tasks missing `- **Difficulty**: {EASY|NORMAL|HARD}`
   - **ALL tasks must have a valid Difficulty value**: EASY, NORMAL, or HARD
   - If any task lacks Difficulty field or has invalid value, STOP and assign proper Difficulty

5. **Completed Tasks Organization Verification (MANDATORY)**:
   - **ZERO completed tasks in Active Tasks section**
   - **ALL `- [x]` tasks must be in Completed Tasks section**
   - Verify Completed Tasks section exists with proper structure (simple list)
   - Archive section must remain in single-line compressed format

6. **Standard Validation**:
   - Verify all task checkboxes are properly formatted: `- [ ]` or `- [x]`
   - Verify all P0 tasks have context explaining criticality
   - Verify Quick Stats match actual task counts (including completed tasks)
   - Verify all file references use relative paths from project root
   - Verify all commit hashes are 7 characters
   - Verify no duplicate tasks in Active Tasks section
   - Verify Archive section uses single-line compressed format (no checkboxes or metadata)

7. **TaskID Format Validation**:
   - **ALL tasks** (active, completed, and archived) have TaskID in format: `P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}`
   - All TaskIDs in the file are unique
   - TaskID priority prefix matches task section priority
   - TaskID package code matches package code in header
   - No TaskID conflicts with archived tasks

8. **Difficulty Field Validation**:
   - **ALL tasks** (active, completed, and archived) have Difficulty field in format: `- **Difficulty**: {EASY|NORMAL|HARD}`
   - Difficulty values are exactly one of: EASY, NORMAL, HARD (case-sensitive)
   - Difficulty assignment aligns with task complexity and impact assessment
   - HARD tasks have sufficient context explaining why they are hard

### ⚠️ VALIDATION ERRORS TO FIX IMMEDIATELY

- If ANY duplicate TaskIDs found: **STOP** and rename all duplicates to unique TaskIDs
- If ANY task lacks TaskID: **STOP** and assign TaskIDs
- If ANY task lacks Difficulty field: **STOP** and assign proper Difficulty
- If ANY completed task in Active Tasks: **MOVE** to Completed Tasks section
- If Completed Tasks section missing: **CREATE** it (simple list, no time divisions)
- If file has sections other than the 4 required: **DELETE** those sections
- If Archive section not in single-line format: **FIX** it (keep compressed)
- If TaskID format wrong: **FIX** it immediately
- If Difficulty value invalid: **FIX** it immediately (must be EASY, NORMAL, or HARD)

5. **Package Code Validation** (when --package-code used):
   - New package code is 2-3 uppercase letters
   - No conflicts with existing package codes in project
   - All TaskIDs successfully migrated to new package code
   - Migration map is valid (no duplicate TaskIDs)

## Output Messages

### Success Messages:
```
✓ Updated todos.md
  - {N} tasks completed
  - {N} new tasks added
  - {N} issues identified
  - {N} tasks moved to archive

✓ Package code updated successfully
  - Old code: {OLD_CODE} → New code: {NEW_CODE}
  - {N} TaskIDs migrated
  - All references updated
```

### Warning Messages:
```
⚠ Warning: Found {N} P0 tasks - immediate attention required
⚠ Warning: Found {N} TODO comments >3 months old
⚠ Warning: {N} blocked tasks need resolution
```

### Error Messages:
```
✗ Error: package_readme.md not found
  Run: /update-readme {directory_path}

✗ Error: No changes detected in {directory_path}
  Either make changes or use --init flag

✗ Error: Invalid commit hash: {hash}
  Use: git log --oneline to find valid commits

✗ Error: Invalid package code: {code}
  Expected format: 2-3 uppercase letters (A-Z)

✗ Error: Package code conflict: {code}
  Already used by: {existing_package_path}

✗ Error: Package code {code} is same as current
  No migration needed

✗ Error: TaskID migration failed
  Duplicate TaskID detected: {taskid}
```

## Do NOT

- Create tasks for test implementation details (that's in .workflows/unittest_guide.md)
- Create tasks for benchmark improvements (that's in .workflows/benchmark_analysis.md)
- Duplicate information from .workflows/package_readme.md
- Add tasks for every minor code style issue
- Create tasks that are too vague ("improve performance", "refactor code")
- Add tasks without context (always explain WHY it matters)
- **⚠️ EVER skip TaskID assignment for existing tasks**
- **⚠️ Leave completed tasks in Active Tasks section**
- **⚠️ Mix completed and active tasks in the same section**
- **⚠️ Assume existing tasks already have TaskIDs - ALWAYS verify**
- **⚠️ Create Completed Tasks section only when needed - ALWAYS verify it exists**
- **⚠️ Expand Archive items back to full format with checkboxes - Archive is read-only**
- **⚠️ Add time-based subsections to Completed Tasks (Recently, This Week, This Month)**
- Add tasks that should be in other packages' todos
- Speculate about bugs without evidence from code or reports

## ⚠️ MANDATORY REQUIREMENTS - NEVER SKIP

1. **ALWAYS verify ALL TaskIDs are unique** - scan entire file and check for duplicates
2. **ALWAYS scan entire todos.md for missing TaskIDs** - even if it looks complete
3. **ALWAYS scan entire todos.md for missing Difficulty fields** - even if it looks complete
4. **ALWAYS move completed tasks to Completed Tasks section** - no exceptions
5. **ALWAYS create Completed Tasks section if it doesn't exist** (simple list, no time divisions)
6. **ALWAYS verify ZERO completed tasks remain in Active Tasks section**
7. **ALWAYS ensure file has exactly 4 sections** - delete any other sections found
8. **ALWAYS respect Archive section format** - single-line compressed, never expand
9. **NEVER add time-based subsections to Completed Tasks** (Recently, This Week, This Month)
10. **NEVER proceed to processing changes until ALL tasks have unique TaskIDs**
11. **NEVER proceed to processing changes until ALL tasks have valid Difficulty fields**
