# Subagent 4: Completion Handler

**Purpose:** Handle all post-execution work. This subagent updates documentation and performs git operations.

## Input

```yaml
completion_report:
  task_id: "{TaskID}"
  status: "success|failure"
  modified_files:
    - "{file_path}"
    - "{file_path}"
  error_message: "{if failure}"
```

## Actions

### 1. Update todos.md

**Locate the task:**
```bash
# Find the todos.md containing this TaskID
find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "{TaskID}" {} \;
```

**Mark task as completed:**
```markdown
# Before
- [ ] **{TaskID}** {task_description}

# After
- [x] **{TaskID}** {task_description}
  - **Completed**: {YYYY-MM-DD HH:MM:SS}
  - **Method**: {brief description of what was done}
  - **Files Modified**: {comma-separated list of files}
```

**Move to Completed Tasks section:**
1. Check if `## Completed Tasks` section exists
2. If not, create it:
   ```markdown
   ## Completed Tasks

   ### Recently Completed
   - [x] **{TaskID}** {task_description}
     - **Completed**: {YYYY-MM-DD HH:MM:SS}
     - **Method**: {brief description}
     - **Files Modified**: {files}

   ### This Week

   ### This Month
   ```
3. If exists, move to appropriate time-based subsection:
   - Completed today → "Recently Completed"
   - Completed within 7 days → "This Week"
   - Completed within 30 days → "This Month"
   - Older than 30 days → Archive section (if exists)
4. **ENSURE** task is REMOVED from Active Tasks section
5. **VERIFY** no completed tasks remain in Active Tasks

### 2. Update Related Files

**Update package_readme.md** if API changed:
- Check if task type is "Feature" or "Refactor"
- Check if modified files include exported functions/types
- Update API documentation if applicable
- Add changelog entry for API changes

**Update analysis_report.md** if complexity/behavior changed:
- Check if task type is "Refactor" or "Bug Fix"
- Update complexity metrics if applicable
- Note behavioral changes or fixes
- Update testing coverage if applicable

### 3. Git Operations

**Stage modified files:**
```bash
git add {modified_files}
git add todos.md
git add {related_files_updated}
```

**Create commit:**
```bash
git commit -m "{commit_message}"
```

**Commit message format:**
```
{type}({scope}): {description}

{details}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Commit type mapping:**
| Task Type | Commit Type |
|-----------|-------------|
| Feature | `feat` |
| Bug Fix | `fix` |
| Refactor | `refactor` |
| Docs | `docs` |

**Push to remote:**
```bash
git push origin {current_branch}
```

**For HARD tasks:**
- Provide merge instructions
- Branch is already created (by Subagent 3)
- Don't push immediately - provide instructions for review

### 4. Update Quick Stats

Recalculate and update task counts in todos.md header:
```markdown
## Quick Stats
- Total Tasks: {N}
- Active: {n}
- Completed: {c}
- P0: {n0}, P1: {n1}, P2: {n2}, P3: {n3}, P4: {n4}
```

## Output

**On Success:**
```yaml
status: "success"
completion_summary:
  task_id: "{TaskID}"
  package: "{package_name}"
  modified_files:
    - "{file}"
  updated_files:
    - "todos.md"
    - "{related_files}"
  commit_hash: "{commit_hash}"
  branch: "{branch_name}"
  test_results: "{passed|failed|skipped}"

final_message: |
  ✅ Task Completed: {TaskID}
  📦 Package: {package}
  📄 Modified: {files}
  📝 Updated: {docs_updated}
  💾 Commit: {commit_hash}
  🌿 Branch: {branch_name}  # for HARD tasks
  🔀 Ready for merge  # for HARD tasks
```

**On Partial Success (tests failed):**
```yaml
status: "partial_success"
completion_summary:
  task_id: "{TaskID}"
  package: "{package_name}"
  modified_files:
    - "{file}"
  updated_files:
    - "todos.md"
  test_results: "failed"
  note: "Task completed but tests failed - manual review needed"

final_message: |
  ⚠️ Task Completed with Issues: {TaskID}
  📦 Package: {package}
  📄 Modified: {files}
  ❌ Tests failed - manual review needed
  💾 Commit: {commit_hash}
```

**On Error:**
```yaml
status: "error"
error_type: "todos_update_failed|git_operation_failed|commit_failed"
error_message: "{clear error message}"
suggestions:
  - "{suggestion 1}"
  - "{suggestion 2}"
```

## HARD Task Special Handling

For HARD tasks (difficulty: HARD):

1. **Don't auto-push** - the feature branch should be reviewed first
2. **Provide merge instructions:**
   ```
   🔀 Merge Instructions:
      1. Review changes on branch: {branch_name}
      2. Run tests: {test_command}
      3. If satisfied, merge:
         git checkout main
         git merge {branch_name}
         git push origin main
      4. Cleanup branch:
         git branch -d {branch_name}
   ```
3. **Plan file reference:** Include link to the detailed plan file

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| todos.md | `{package_path}/.workflows/todos.md` | Mark task completed, move to section |
| package_readme.md | `{package_path}/.workflows/package_readme.md` | Update API docs if changed |
| analysis_report.md | `{package_path}/.workflows/analysis_report.md` | Update analysis if complexity changed |

## Error Handling

| Error | Handler | Recovery |
|-------|---------|----------|
| todos.md not found | Log error, suggest `/update-todos` | Mark task as completed but note documentation issue |
| todos.md update fails | Log error with file error details | Changes remain in working directory |
| Git add fails | Log error with git output | Manual git add needed |
| Git commit fails | Log error with git output | Changes staged but not committed |
| Git push fails | Log error with git output | Commit created locally, push manually |
| Related file update fails | Log warning, continue | Task marked complete, note incomplete docs |

## Timestamp Format

Use ISO 8601 format for completion timestamps:
```
{YYYY-MM-DD HH:MM:SS}
```

Example: `2025-02-02 17:30:45`

## Example Output

**Standard Task Success:**
```
✅ Task Completed: P1-DB-A236
📦 Package: db
📄 Modified: manager.go
📝 Updated: todos.md, package_readme.md
💾 Commit: abc1234
🌿 Branch: main
```

**HARD Task Success:**
```
✅ HARD Task Completed: P1-BC-A123
📦 Package: broadcast
📄 Modified: manager.go, validator.go, connector.go
📝 Updated: todos.md, package_readme.md, analysis_report.md
💾 Commit: def5678
🌿 Branch: feature/refactor-broadcast-manager-P1-BC-A123

🔀 Merge Instructions:
   1. Review changes on branch: feature/refactor-broadcast-manager-P1-BC-A123
   2. Run tests: go test ./broadcast -v
   3. If satisfied, merge:
      git checkout main
      git merge feature/refactor-broadcast-manager-P1-BC-A123
      git push origin main
   4. Cleanup branch:
      git branch -d feature/refactor-broadcast-manager-P1-BC-A123

📄 Plan reference: .workflows/plan/P1-BC-A123-plan.md
```

## Implementation Notes

- All file operations happen in isolated subagent context
- Git operations use standard git commands
- Commit messages follow conventional commit format
- For HARD tasks, branch management preserves isolation
- Quick stats update ensures todos.md metrics are accurate
- Completion message provides clear status summary
