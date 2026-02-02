#!/bin/bash
# Dispatch script for Task Locator Subagent
# Usage: ./dispatch-task-locator.sh "{TaskID}"

set -e

TASK_ID="$1"

if [ -z "$TASK_ID" ]; then
  echo "error: TaskID required"
  echo "usage: $0 \"{TaskID}\""
  exit 1
fi

# Read the subagent prompt template
SUBAGENT_PROMPT="$(cat <<EOF
You are Subagent 1: Task Locator for the /do command.

**Your Task:** Find TaskID "$TASK_ID" across all .workflows/todos.md files and extract task metadata.

**Actions:**
1. Search for the TaskID using: find . -name "todos.md" -path "*/.workflows/*" -exec grep -l "$TASK_ID" {} \;
2. Validate uniqueness (exactly one match required)
3. Extract package path from the found file location
4. Extract task metadata from the todos.md entry

**TaskID Format to Validate:** ^P[0-4]-[A-Z]{2,3}-[A-Z0-9]{4}$

**Output Format (YAML):**

On Success:
\`\`\`yaml
status: success
package_path: "{path_to_package}"
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{brief title}"
  context: "{task context}"
  status: "pending|in_progress|blocked"
todos_location: "{relative_path_to_todos_md}"
\`\`\`

On Error:
\`\`\`yaml
status: error
error_type: "not_found|duplicate|invalid_format"
error_message: "{clear error message}"
suggestions:
  - "{suggestion 1}"
\`\`\`

**Important:**
- If TaskID not found, return error with helpful message
- If found in multiple files, return error with disambiguation options
- Only return YAML output, nothing else
EOF
)"

# The subagent prompt would be used with the Task tool
# This script is a placeholder for the dispatch mechanism
echo "$SUBAGENT_PROMPT"
