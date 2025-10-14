# Update Todos Command

Update `{directory_path}/.workflows/todos.md` based on git changes, code analysis, and existing documentation.

## Arguments
- Required: `{directory_path}` (e.g., `chatbot/bowl`)
- Optional: `--since=<commit_hash>` (default: `HEAD~1`)
- Optional: `--init` (force initialization mode even if todos.md exists)

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

### Mode 3: Initialization (When --init or todos.md doesn't exist)
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
IF --init flag present OR todos.md doesn't exist:
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
Format: `Priority-PackageCode-4CharID`

**Generation Logic:**
1. Get all existing TaskIDs in current todos.md
2. Extract used 4CharIDs for this package
3. Generate next available 4CharID in sequence:
   - Start with `A000`, `A001`, ..., `A999`
   - Then `B000`, `B001`, ..., `B999`
   - Continue through `Z999`
4. Combine: `[Priority]-[PackageCode]-[4CharID]`

**Example:**
- Package `db` has existing tasks: `P1-DB-A236`, `P0-DB-A237`
- Next task with P1 priority → `P1-DB-A238`
- Next task with P0 priority → `P0-DB-A238`

### Step 2: Load Context Files

Read in order:
1. `package_readme.md` - understand package structure
2. `analysis_report.md` (if exists) - get known issues
3. `unittest_guide.md` (if exists) - check test documentation
4. `todos.md` (if exists) - get existing tasks

### Step 3: Gather Change Data

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

### Step 4: Classify Changes

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

### Step 5: Priority Assignment

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

### Step 6: Generate/Update todos.md

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

---

## Active Tasks

### [P0] Critical
- [ ] **{TaskID}** {Task description} `{file:line if from code comment}`
  - **Context**: {Why this is critical}
  - **Identified**: {date or commit}
  - **Status**: {active|in_progress|blocked}

### [P1] High
- [ ] **{TaskID}** {Task description}
  - **Context**: {Why this matters}
  - **Identified**: {date or commit}
  - **Related**: {link to analysis_report.md section if applicable}
  - **Status**: {active|in_progress|blocked}

### [P2] Medium
- [ ] **{TaskID}** {Task description}
  - **Status**: {active|in_progress|blocked}

### [P3] Low
- [ ] **{TaskID}** {Task description}
  - **Status**: {active|in_progress|blocked}

### [P4] Backlog
- [ ] **{TaskID}** {Task description}
  - **Status**: {active|in_progress|blocked}

### 🚫 Blocked
- [ ] **{TaskID}** {Task description}
  - **Blocked by**: {What's blocking this}
  - **Identified**: {date}
  - **Status**: blocked

---

## Recent Activity

### [{YYYY-MM-DD HH:MM}] - Commit: {short_hash} (or "Session Update")

#### Completed ✓
- [x] **P1-DB-A236** Fixed race condition in Manager.Start() - added mutex protection
  - **Files**: manager.go:45-67
  - **Commit**: abc123f
  - **Impact**: Eliminated crash under high concurrency

- [x] **P2-DB-A237** Refactored bowl creation logic into separate function
  - **Files**: bowl.go:120-145
  - **Why**: Reduced complexity from 15→8, improved readability

#### Added 📝
- [ ] **P1-DB-A238** Implement graceful shutdown for background workers
  - **Reason**: New goroutines added in abc123f need cleanup
  - **Files**: manager.go:89
  - **Status**: active

- [ ] **P2-DB-A239** Document new WithTimeout option in package_readme.md
  - **Reason**: New public API added but not documented
  - **Status**: active

#### Identified 🔍
- [ ] **P1-DB-A240** Potential memory leak in bowl recycling
  - **Location**: bowl.go:234
  - **Evidence**: TODO comment added during debugging
  - **Next**: Profile memory usage under load
  - **Status**: active

- [ ] **P2-DB-A241** Duplicate error handling in 3 functions
  - **Locations**: manager.go:156, manager.go:298, bowl.go:67
  - **Suggestion**: Extract common error wrapper
  - **Status**: active

#### Ongoing 🔄
- [ ] **P1-DB-A242** Multi-stage bowl processing pipeline
  - **Status**: 2 of 4 stages implemented
  - **Commits**: abc123f, def456a
  - **Next**: Implement validation stage
  - **Status**: in_progress

---

{Previous activity sections...}

---

## Archive

### {YYYY-MM}

#### Completed This Month
- [P0] Fixed crash on nil bowl pointer - commit: abc123f (2025-10-01)
- [P1] Optimized manager allocation - 40% faster - commit: def456a (2025-10-05)
- [P2] Cleaned up unused helper functions - commit: ghi789b (2025-10-08)

---

## Notes

### Documentation Status
- package_readme.md: ✓ Up to date (2025-10-09)
- analysis_report.md: ✓ Generated (2025-10-08)
- unittest_guide.md: ✓ Exists

### Known Issues
{Long-standing known issues that aren't tasks yet}

### Future Considerations
{Ideas for major refactoring or features requiring design}
```

### Step 7: Task Deduplication and TaskID Management

Before adding new tasks:
1. Check if identical task exists in Active Tasks
2. Check if similar task exists (>80% text similarity)
3. If duplicate: merge contexts and update priority, keep existing TaskID
4. If similar: link them with "Related to: {TaskID}"

### TaskID Assignment Rules:
1. **New tasks**: Always generate new TaskID using priority + package code + next sequence
2. **Priority changes**: Keep same TaskID, update priority prefix
3. **Merged tasks**: Keep TaskID of higher priority task
4. **Split tasks**: Generate new TaskIDs for split tasks, mark original as completed

### TaskID Tracking:
- Maintain index of all TaskIDs in project for quick lookup
- When searching for tasks: search by TaskID first, then by description
- When referencing tasks in other commands: always use TaskID format

### Step 8: Archive Maintenance

When completing tasks:
1. Move from Active Tasks to current month in Archive
2. Keep full context (files, commits, impact)
3. If Archive > 6 months old, create separate archive file

Every 3 months:
- Reassess P3/P4 tasks - delete if no longer relevant
- Review blocked tasks - unblock or delete
- Update Quick Stats

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
1. Verify all task checkboxes are properly formatted: `- [ ]` or `- [x]`
2. Verify all P0 tasks have context explaining criticality
3. Verify Quick Stats match actual task counts
4. Verify all file references use relative paths from project root
5. Verify all commit hashes are 7 characters
6. Verify no duplicate tasks in Active Tasks section
7. **TaskID Validation**:
   - All tasks have TaskID in format: `P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}`
   - All TaskIDs in Active Tasks are unique
   - TaskID priority prefix matches task section priority
   - TaskID package code matches package code in header
   - No TaskID conflicts with archived tasks

## Output Messages

### Success Messages:
```
✓ Updated todos.md
  - {N} tasks completed
  - {N} new tasks added
  - {N} issues identified
  - {N} tasks moved to archive
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
```

## Do NOT

- Create tasks for test implementation details (that's in .workflows/unittest_guide.md)
- Create tasks for benchmark improvements (that's in .workflows/benchmark_analysis.md)
- Duplicate information from .workflows/package_readme.md
- Add tasks for every minor code style issue
- Create tasks that are too vague ("improve performance", "refactor code")
- Add tasks without context (always explain WHY it matters)
- Keep completed tasks in Active section (move to Archive immediately)
- Create separate task for each TODO if they're related (group them)
- Add tasks that should be in other packages' todos
- Speculate about bugs without evidence from code or reports
