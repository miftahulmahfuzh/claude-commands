# Postmortem Command - Session Problem Documentation

Generate detailed postmortem reports for bugs/errors encountered during Claude Code sessions, with automatic TaskID detection and structured documentation.

## Arguments
- **Optional**: `--id={TaskID}` (e.g., `--id=P2-PR-A021`) - Specify TaskID explicitly
- **Optional**: `--note="{additional context}"` - Provide extra context about the problem

## Process Flow

### Step 1: Session Analysis and TaskID Detection

#### 1.1 Analyze Current Session Context
1. **Session Review**: Examine the current Claude Code session for:
   - Files modified and changes made
   - Error messages or problems discussed
   - Solutions implemented
   - Commands executed (especially `/do` commands)
   - User descriptions of problems being solved

2. **TaskID Detection**: Search for TaskID references in the session:
   ```bash
   # Look for patterns like:
   # - /do P1-CL-A017
   # - Task P2-DB-A236
   # - TaskID P0-CB-B789
   ```

#### 1.2 Handle TaskID Scenarios

**Scenario A: TaskID Found in Session**
1. **Extract TaskID**: Parse the TaskID from session context
2. **Validate Format**: Ensure TaskID follows `P[0-4]-[CODE]-[ID]` format
3. **Locate Task**: Find the todos.md file containing this TaskID
4. **Uniqueness Check**: Verify TaskID appears in exactly one todos.md file

**Scenario B: No TaskID Found**
1. **Problem Analysis**: Analyze session content to understand the problem/solution
2. **Package Detection**: Identify most relevant package based on:
   - Files modified in the session
   - Problem domain and context
   - Codebase structure understanding

3. **Propose New Task**:
   ```
   🔍 No TaskID found in current session
   📝 Session Analysis: {brief description of problem solved}
   🎯 Proposed Task: {task description}
   📦 Suggested Package: {package_path}/.workflows/todos.md

   💡 Edit the path if needed, then confirm to create task:
   todos file: {proposed_path}
   ```

4. **User Interaction**:
   - Wait for user to confirm or edit the path
   - If user confirms: Create new task entry in specified todos.md
   - If user edits: Use the modified path
   - Generate TaskID: `P{priority}-{package_code}-{4CharID}`

5. **Task Creation Process**:
   ```markdown
   - [x] **{TaskID}** {task description}
     - **Completed**: {YYYY-MM-DD HH:MM:SS}
     - **Method**: {description of solution implemented}
     - **Files Modified**: {list of files changed}
     - **Session**: Postmortem documentation created via /postmortem
   ```

### Step 2: Postmortem Report Generation

#### 2.1 Directory Structure Setup
1. **Create Directory**: Ensure `.workflows/postmortem/` directory exists
   ```bash
   mkdir -p {package_path}/.workflows/postmortem/
   ```

2. **File Path**: Determine postmortem file location:
   ```
   {package_path}/.workflows/postmortem/{TaskID}.md
   ```

#### 2.2 Go-Inspired Postmortem Template Structure

```markdown
# Postmortem Report: {TaskID}

## Executive Summary
**Problem**: {brief problem description}
**Impact**: {severity and affected components}
**Resolution**: {solution overview}
**Duration**: {time from discovery to resolution}
**Author**: Claude Code Session

---

## Timeline

### Discovery
- **Time**: {timestamp or approximate time}
- **Method**: {how the problem was discovered}
- **Initial Symptoms**: {what was observed}

### Investigation
- **Time**: {investigation period}
- **Methods**: {debugging steps taken}
- **Key Findings**: {important discoveries during investigation}

### Resolution
- **Time**: {resolution timestamp}
- **Approach**: {solution strategy}
- **Implementation**: {how the fix was implemented}

---

## Problem Analysis

### Root Cause Analysis
**Primary Cause**:
- {main root cause with technical details}

**Contributing Factors**:
- {secondary factors that led to the problem}
- {environmental conditions}
- {system interactions}

### Technical Details
**Affected Components**:
- {list of affected files, functions, modules}

**Error Conditions**:
- {specific error conditions that triggered the problem}
- {edge cases or boundary conditions}

**Failure Mode**:
- {how the failure manifested}
- {cascade effects if any}

---

## Impact Assessment

### Scope of Impact
**Severity**: {Critical/High/Medium/Low}
**Affected Areas**:
- {user-facing impact}
- {system stability impact}
- {data integrity impact}
- {performance impact}

### Business Impact
**User Experience**: {effect on end users}
**System Reliability**: {effect on system stability}
**Development Velocity**: {effect on development process}

---

## Resolution Details

### Solution Strategy
**Approach Rationale**:
- {why this solution was chosen}
- {alternative approaches considered and rejected}

### Implementation Details
**Code Changes**:
```go
// Include relevant code snippets or diffs
// Example:
// Before:
func problematicFunction() error {
    // problematic code
}

// After:
func fixedFunction() error {
    // fixed code with proper error handling
}
```

**Files Modified**:
- `{file_path}` - {description of changes}
- `{file_path}` - {description of changes}

### Testing and Validation
**Test Cases Added**:
```go
func TestFixedBehavior(t *testing.T) {
    // test cases to prevent regression
}
```

**Validation Methods**:
- {how the fix was validated}
- {testing approach}
- {performance benchmarks if relevant}

---

## Prevention Measures

### Immediate Preventive Actions
**Code Changes**:
- {specific changes to prevent recurrence}
- {additional validation or checks added}

**Process Improvements**:
- {development process changes}
- {review checklist updates}

### Long-term Preventive Measures
**Architectural Changes**:
- {broader architectural improvements}
- {design pattern implementations}

**Monitoring Enhancements**:
- {alerting or monitoring to detect similar issues}
- {log improvements}

**Documentation Updates**:
- {documentation to prevent similar mistakes}
- {knowledge sharing measures}

---

## Lessons Learned

### Technical Insights
**What We Learned**:
- {technical knowledge gained}
- {system behavior insights}

**Best Practices Identified**:
- {best practices that could prevent similar issues}
- {coding standards improvements}

### Process Insights
**Development Process**:
- {process improvements discovered}
- {workflow optimizations}

**Knowledge Gaps**:
- {areas where more knowledge/documentation was needed}

---

## Follow-up Actions

### Immediate Actions (Completed)
- [x] {action item - completed during resolution}
- [x] {action item - completed during resolution}

### Short-term Actions (Pending)
- [ ] {action item - to be completed within 1 week}
- [ ] {action item - to be completed within 1 week}

### Long-term Actions (Backlog)
- [ ] {action item - to be completed in future iterations}
- [ ] {action item - to be completed in future iterations}

---

## Related Resources

### Task References
- **TaskID**: {TaskID} in `{todos.md_path}`
- **Related Tasks**: {list of related TaskIDs if any}

### Code References
- **Files**: {list of modified files with line numbers}
- **Commits**: {relevant git commit hashes if available}
- **Branches**: {feature branches if created}

### Documentation
- **Related Docs**: {links to relevant documentation}
- **External Resources**: {external references or research}

---

## Metadata

**Postmortem ID**: {TaskID}
**Created**: {YYYY-MM-DD HH:MM:SS}
**Session Context**: {Claude Code session}
**Last Updated**: {YYYY-MM-DD HH:MM:SS}
**Review Date**: {suggested review date}
**Tags**: {problem-type, bug-category, technology}

---

*This postmortem was automatically generated by Claude Code's /postmortem command*
```

#### 2.3 Update vs Create Logic

**If Postmortem File Exists**:
1. **Load Existing Content**: Read current postmortem report
2. **Update Sections**:
   - Add new "Occurrence" to timeline if this is a recurrence
   - Update "Resolution Details" with new solution approach
   - Add to "Lessons Learned" with new insights
   - Update "Follow-up Actions" with additional items
3. **Preserve History**: Keep previous occurrences as learning opportunities
4. **Update Metadata**: Refresh timestamps and add recurrence indicator

**If Postmortem File Doesn't Exist**:
1. **Create New Report**: Generate complete postmortem using template
2. **Populate from Session**: Fill all sections based on session analysis
3. **Create Directory**: Ensure `.workflows/postmortem/` exists
4. **Save Report**: Write new postmortem file

### Step 3: Session Context Analysis

#### 3.1 Extract Session Information
1. **File Changes**: Parse modified files and their changes
2. **Problem Statements**: Extract problem descriptions from user messages
3. **Solution Approaches**: Document solution strategies discussed
4. **Implementation Details**: Capture code changes and rationale
5. **User Feedback**: Include user insights and feedback

#### 3.2 Generate Contextual Content
1. **Technical Depth**: Provide appropriate technical details for Go developers
2. **Code Snippets**: Include relevant before/after code examples
3. **Error Patterns**: Document specific Go error patterns and solutions
4. **Best Practices**: Connect solutions to Go best practices

### Step 4: Cross-Reference Integration

#### 4.1 Link to Existing Documentation
1. **Task Integration**: Reference the original task in todos.md
2. **Analysis Reports**: Link to related analysis_report.md if exists
3. **Package Documentation**: Reference package_readme.md for context

#### 4.2 Update Related Files
1. **Todos Reference**: Add note in todos.md about postmortem creation
2. **Cross-Links**: Update related documentation with postmortem references

### Step 5: Quality Assurance

#### 5.1 Content Validation
1. **Technical Accuracy**: Ensure Go-specific details are correct
2. **Completeness**: Verify all template sections are appropriately filled
3. **Clarity**: Ensure explanations are clear and actionable
4. **Consistency**: Maintain consistent formatting and terminology

#### 5.2 File System Validation
1. **Directory Structure**: Ensure proper directory creation
2. **File Paths**: Verify all file paths are correct and accessible
3. **Permissions**: Ensure proper file read/write permissions

## --id Parameter Workflow

### Explicit TaskID Specification
When `--id={TaskID}` is provided:

1. **Parameter Validation**:
   ```bash
   # Validate TaskID format
   if [[ ! "$TaskID" =~ ^P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}$ ]]; then
     echo "✗ Error: Invalid TaskID format: '$TaskID'"
     echo "  Expected format: P[0-4]-[CODE]-[ID]"
     exit 1
   fi
   ```

2. **Uniqueness Check**:
   ```bash
   # Search for TaskID across all todos.md files
   found_files=$(find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "$TaskID" {} \;)

   if [ $(echo "$found_files" | wc -l) -eq 0 ]; then
     echo "✗ Error: TaskID '$TaskID' not found in any todos.md files"
     exit 1
   elif [ $(echo "$found_files" | wc -l) -gt 1 ]; then
     echo "✗ Error: TaskID '$TaskID' found in multiple files:"
     echo "$found_files"
     echo "Please update duplicate TaskIDs to ensure uniqueness across codebase"
     exit 1
   fi
   ```

3. **Automatic Path Resolution**:
   ```bash
   # Extract package path from found todos.md file
   todos_file=$(echo "$found_files" | head -n 1)
   package_path=$(dirname "$todos_file")
   postmortem_path="$package_path/postmortem/$TaskID.md"
   ```

## Output Messages

### Success Messages:
```
🔍 Analyzing session context...
📋 TaskID detected: P1-CL-A017
📁 Found in: ./.workflows/todos.md
📝 Generating postmortem report...
📄 Postmortem created: ./.workflows/postmortem/P1-CL-A017.md
✅ Postmortem documentation completed successfully

📊 Summary:
- Problem: {problem description}
- Solution: {solution approach}
- Files: {count} files documented
- Duration: {session duration}
```

### New Task Creation Messages:
```
🔍 Analyzing session context...
📝 No TaskID found in current session
🎯 Problem Identified: {problem description}
📦 Suggested Package: claude-commands/.workflows/todos.md

💡 Edit the path if needed, then confirm to create task:
todos file: claude-commands/.workflows/todos.md

✅ Task created: P1-CL-A017
📝 Generating postmortem report...
📄 Postmortem created: ./.workflows/postmortem/P1-CL-A017.md
```

### --id Parameter Success Messages:
```
🔍 Using specified TaskID: P2-PR-A021
📁 Located in: chatbot/processing/.workflows/todos.md
📝 Generating postmortem report...
📄 Postmortem updated: chatbot/processing/.workflows/postmortem/P2-PR-A021.md
✅ Postmortem documentation completed successfully
```

### Update Messages (Existing Postmortem):
```
🔍 Analyzing session context...
📋 TaskID detected: P1-DB-A236
📁 Found in: db/.workflows/todos.md
📄 Existing postmortem found: db/.workflows/postmortem/P1-DB-A236.md
🔄 Updating existing postmortem with new occurrence...
📝 Postmortem updated with recurrence information
✅ Postmortem update completed successfully
```

### Progress Messages:
```
🔍 Analyzing session for problem patterns...
📋 Extracting technical details...
📁 Locating appropriate todos.md file...
📝 Generating Go-inspired postmortem structure...
📄 Writing comprehensive documentation...
✅ Postmortem generation complete
```

### Warning Messages:
```
⚠️ Warning: Multiple files modified - ensure complete documentation
⚠️ Warning: Session context limited - provide additional details with --note
⚠️ Warning: No test coverage documented - consider adding tests
⚠️ Warning: Problem may affect other packages - review impact scope
```

### Error Messages:
```
✗ Error: Invalid TaskID format: 'INVALID'
  Expected format: P[0-4]-[CODE]-[ID]

✗ Error: TaskID 'P0-DB-Z999' not found in any todos.md files
  Available TaskIDs: Use /do --list to see available tasks

✗ Error: TaskID 'P1-CL-A123' found in multiple locations:
  ./package1/.workflows/todos.md
  ./package2/.workflows/todos.md
  Please update duplicate TaskIDs to ensure uniqueness

✗ Error: Unable to create postmortem directory: {error_message}
  Check permissions and disk space

✗ Error: Cannot write postmortem file: {error_message}
  Check file permissions and directory structure

✗ Error: Session analysis failed - insufficient context
  Use --note parameter to provide additional details
```

## Special Cases

### Recurring Issues
If the same problem occurs multiple times:

1. **Detection**: Recognize patterns from previous postmortems
2. **Cross-Reference**: Link to previous occurrences
3. **Trend Analysis**: Document recurrence patterns
4. **Escalated Prevention**: Enhanced prevention measures for recurring issues

### Multi-Package Impact
If the problem affects multiple packages:

1. **Impact Assessment**: Document all affected packages
2. **Cross-Package Postmortems**: Create linked postmortems in each package
3. **Coordination Notes**: Document coordination between packages
4. **Shared Solutions**: Document common solution approaches

### Security Issues
For security-related problems:

1. **Enhanced Sensitivity**: Additional security considerations
2. **Disclosure Guidelines**: Appropriate level of detail in documentation
3. **Security Review**: Mandatory security review steps
4. **Prevention Priority**: High-priority security prevention measures

## Integration with Other Commands

### Before /postmortem
- Common usage after `/do` command completion
- Can be used after any bug-fixing session
- Works well after `/update-todos` for task context

### After /postmortem
- Run `/update-todos` to reflect postmortem creation
- Consider `/update-readme` if problem documentation affects API docs
- Use `/analyze-package` if problem reveals broader code quality issues

### Related Commands
```bash
# Complete workflow for bug documentation
/do P1-CL-A017                    # Fix the bug
/postmortem --id=P1-CL-A017       # Document the solution
/update-todos claude-commands     # Update task status
```

## Best Practices

### For Users
1. **Use After Bug Fixes**: Run `/postmortem` after fixing any non-trivial bug
2. **Provide Context**: Use `--note` for additional technical details
3. **Review Generated Content**: Ensure technical accuracy and completeness
4. **Link to Tasks**: Use `--id` when documenting specific task solutions

### For Postmortem Quality
1. **Technical Depth**: Include sufficient technical details for Go developers
2. **Code Examples**: Provide concrete before/after code snippets
3. **Root Cause Analysis**: Go beyond symptoms to identify true root causes
4. **Actionable Prevention**: Ensure prevention measures are specific and implementable

### For Knowledge Management
1. **Consistent Format**: Follow the Go-inspired template structure
2. **Cross-References**: Link to related documentation and tasks
3. **Regular Review**: Periodically review postmortems for pattern identification
4. **Team Sharing**: Share postmortems with team members for learning

## Examples

### Simple Bug Fix Postmortem
```bash
/postmortem
```
→ Creates postmortem for session-detected bug fix
```
🔍 Analyzing session context...
📋 TaskID detected: P2-CL-A015
📝 Generating postmortem report...
📄 Postmortem created: ./.workflows/postmortem/P2-CL-A015.md
✅ Postmortem completed: Fixed parameter validation bug
```

### Explicit TaskID Postmortem
```bash
/postmortem --id=P1-DB-A236 --note="Race condition in goroutine synchronization"
```
→ Documents specific task solution with additional context
```
🔍 Using specified TaskID: P1-DB-A236
📁 Located in: db/.workflows/todos.md
📝 Generating postmortem with additional context...
📄 Postmortem created: db/.workflows/postmortem/P1-DB-A236.md
✅ Postmortem completed: Race condition documentation with detailed analysis
```

### New Task Creation Postmortem
```bash
/postmortem
```
→ When no TaskID exists, creates new task and documents solution
```
🔍 Analyzing session context...
📝 No TaskID found - session solved memory leak in cache manager
🎯 Proposed Task: Fix memory leak in cache manager goroutine cleanup
📦 Suggested Package: cache/.workflows/todos.md

💡 Edit the path if needed, then confirm to create task:
todos file: cache/.workflows/todos.md

[User confirms]
✅ Task created: P2-CA-A045
📝 Generating postmortem report...
📄 Postmortem created: cache/.workflows/postmortem/P2-CA-A045.md
✅ Postmortem completed: Memory leak documentation with prevention measures
```

### Complex Multi-Package Issue
```bash
/postmortem --id=P0-SY-S001 --note="System-wide deadlock affecting multiple services"
```
→ Documents critical system issue with broad impact
```
🔍 Using specified TaskID: P0-SY-S001
📁 Located in: system/.workflows/todos.md
📝 Generating comprehensive postmortem...
⚠️ Warning: Issue affects multiple packages - documenting cross-package impact
📄 Postmortem created: system/.workflows/postmortem/P0-SY-S001.md
✅ Critical issue postmortem completed with system-wide prevention measures
```

## File Structure After Implementation

```
your-project/
├── .workflows/
│   ├── postmortem/
│   │   ├── P1-CL-A017.md      # Postmortem for CLI command bug
│   │   ├── P2-DB-A236.md      # Postmortem for database race condition
│   │   └── P0-SY-S001.md      # Postmortem for system-wide deadlock
│   ├── todos.md               # Updated with postmortem references
│   └── ...
├── package1/
│   └── .workflows/
│       ├── postmortem/
│       │   └── P2-P1-A123.md  # Package-specific postmortem
│       └── todos.md
└── ...
```

The `/postmortem` command provides comprehensive knowledge management for problem-solving sessions, following Go documentation best practices and integrating seamlessly with the existing .workflows ecosystem.