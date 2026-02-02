# Subagent 1: Task Locator

**Purpose:** Find TaskID across all `.workflows/todos.md` files and extract task metadata.

## Input

```yaml
task_id: "{TaskID}"  # e.g., P1-DB-A236
```

## Actions

1. **Search for TaskID** across all todos.md files:
   ```bash
   find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "{TaskID}" {} \;
   ```

2. **Validate uniqueness**:
   - If zero matches: Return error "Task '{TaskID}' not found"
   - If multiple matches: Return error with disambiguation options
   - If exactly one match: Proceed

3. **Extract package path** from the found file location:
   - `./db/.workflows/todos.md` → package_path: `db`
   - `./chatbot/bowl/.workflows/todos.md` → package_path: `chatbot/bowl`

4. **Extract task metadata** from todos.md entry:
   ```yaml
   priority: "P0|P1|P2|P3|P4"
   difficulty: "EASY|NORMAL|HARD"
   type: "Bug|Feature|Refactor|Docs"
   title: "{brief task title}"
   context: "{task context summary}"
   status: "pending|in_progress|blocked"
   ```

## Output

**On Success:**
```yaml
status: "success"
package_path: "{path_to_package}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{brief title}"
  context: "{task context}"
  status: "pending|in_progress|blocked"
todos_location: "{relative_path_to_todos_md}"
```

**On Error:**
```yaml
status: "error"
error_type: "not_found|duplicate|invalid_format"
error_message: "{clear error message}"
suggestions:
  - "{suggestion 1}"
  - "{suggestion 2}"
```

## TaskID Format Validation

Use regex before searching:
```regex
^P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}$
```

If invalid format:
```yaml
status: "error"
error_type: "invalid_format"
error_message: "Invalid TaskID format: '{TaskID}'"
expected_format: "P[0-4]-[CODE]-[ID]"
examples:
  - "P0-DB-A236"
  - "P1-CB-B789"
```

## Error Handling

| Scenario | Response |
|----------|----------|
| TaskID not found | `error_type: not_found` with suggestion to check available tasks |
| Multiple matches | `error_type: duplicate` with list of matching locations |
| Invalid format | `error_type: invalid_format` with examples |
| Missing todos.md | `error_type: not_found` with suggestion to run `/update-todos` |

## Implementation Notes

- Use `ripgrep` (rg) for faster search if available: `rg -l "{TaskID}" --type-add 'todos:*todos.md' --type todos`
- Package path is extracted from todos.md file location
- Task metadata is parsed from the markdown task entry in todos.md
- Return structured YAML for easy parsing by next subagent
