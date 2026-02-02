# Subagent 2: Context Loader

**Purpose:** Load and synthesize relevant context from package documentation files.

## Input

```yaml
package_path: "{path_to_package}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{brief title}"
  context: "{task context}"
```

## Actions

1. **Read task details** from `{package_path}/.workflows/todos.md`
   - Extract full task description
   - Identify related tasks (if any)
   - Note any special instructions or notes

2. **Read package documentation** from `{package_path}/.workflows/package_readme.md` (if exists)
   - Extract package structure overview
   - Identify relevant modules/components
   - Note any important conventions or patterns

3. **Read analysis report** from `{package_path}/.workflows/analysis_report.md` (if exists)
   - Extract relevant analysis for this task
   - Note complexity metrics if applicable
   - Identify any dependencies or integration points

4. **Synthesize into context packet**:
   - Concise task description (1-2 sentences)
   - Relevant docs summary (key points only, not raw content)
   - File references (files mentioned in task/docs)
   - Related tasks (TaskIDs of dependencies or related work)

## Output

**On Success:**
```yaml
status: "success"
context_packet:
  task_description: "{full task description in 1-2 sentences}"
  docs_summary: |
    {Synthesized summary of relevant documentation}
    - Key point 1
    - Key point 2
  file_references:
    - "{relative/path/to/file.ext}"
    - "{relative/path/to/file.ext}"
  related_tasks:
    - "{TaskID}"
  package_structure:
    main_module: "{module_name}"
    key_files:
      - "{file}"
      - "{file}"
```

**On Warning (missing files):**
```yaml
status: "success"
warning: "Some documentation files not found"
missing_files:
  - "package_readme.md"
  - "analysis_report.md"
context_packet:
  # ... (available context only)
```

**On Error:**
```yaml
status: "error"
error_type: "todos_not_found|package_not_found"
error_message: "{clear error message}"
```

## File Locations to Read

| File | Location | Required |
|------|----------|----------|
| todos.md | `{package_path}/.workflows/todos.md` | Yes |
| package_readme.md | `{package_path}/.workflows/package_readme.md` | No |
| analysis_report.md | `{package_path}/.workflows/analysis_report.md` | No |

## Synthesis Guidelines

**For task_description:**
- Combine title + context into 1-2 clear sentences
- Focus on WHAT needs to be done, not WHY
- Include key constraints or requirements if mentioned

**For docs_summary:**
- Extract ONLY relevant information for this task
- Use bullet points for clarity
- Don't include raw file contents
- Maximum 3-5 bullet points

**For file_references:**
- List files explicitly mentioned in task
- Add files from docs that are relevant to task type
- Use relative paths from package root

**For related_tasks:**
- Extract TaskIDs mentioned in task context
- Note dependency relationships if clear
- Empty array if no related tasks found

## Error Handling

| Scenario | Response |
|----------|----------|
| todos.md not found | `error_type: todos_not_found` - suggest `/update-todos` |
| package_path invalid | `error_type: package_not_found` - verify path from Subagent 1 |
| package_readme.md missing | `warning` - continue with available context |
| analysis_report.md missing | `warning` - continue with available context |

## Example Output

```yaml
status: success
context_packet:
  task_description: "Add input validation to ProcessData function to prevent nil pointer crashes"
  docs_summary: |
    - ProcessData is in manager.go, handles database query results
    - Existing validator module at db/validator/ with ValidateInput function
    - Related to P0-DB-A235 (nil pointer fix) - use similar validation pattern
  file_references:
    - "db/manager.go"
    - "db/validator/validator.go"
  related_tasks:
    - "P0-DB-A235"
  package_structure:
    main_module: "db"
    key_files:
      - "manager.go"
      - "validator.go"
```

## Implementation Notes

- Read files sequentially to minimize memory usage
- Synthesize immediately after reading each file (don't accumulate raw content)
- Use grep/sed for targeted extraction when possible
- Return structured YAML for easy parsing by next subagent
- Context packet should be concise (aim for < 500 words total)
