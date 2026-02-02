#!/bin/bash
# Dispatch script for Completion Handler Subagent
# Usage: ./dispatch-completion-handler.sh "{TaskID}" "{status}" "{modified_files}" "{error_message?}"

set -e

TASK_ID="$1"
STATUS="$2"
MODIFIED_FILES="$3"
ERROR_MESSAGE="${4:-}"

if [ -z "$TASK_ID" ] || [ -z "$STATUS" ]; then
  echo "error: TaskID and status required"
  echo "usage: $0 \"{TaskID}\" \"{status}\" \"{modified_files}\" \"{error_message?}\""
  exit 1
fi

# Read the subagent prompt template
SUBAGENT_PROMPT="$(cat <<EOF
You are Subagent 4: Completion Handler for the /do command.

**Your Task:** Handle all post-execution work - update documentation and perform git operations.

**Input:**
\`\`\`yaml
completion_report:
  task_id: "$TASK_ID"
  status: "$STATUS"
  modified_files:
    $MODIFIED_FILES
  error_message: "$ERROR_MESSAGE"
\`\`\`

**Actions:**
1. Update todos.md:
   - Mark task as completed (- [ ] → - [x])
   - Add completion metadata (timestamp, method, files modified)
   - Move to Completed Tasks section (Recently Completed / This Week / This Month)
   - Ensure task is REMOVED from Active Tasks

2. Update related files:
   - package_readme.md if API changed
   - analysis_report.md if complexity/behavior changed

3. Git operations:
   - Stage modified files
   - Create commit with descriptive message
   - Push to remote (except for HARD tasks - provide merge instructions)

4. Update quick stats in todos.md

**Commit Message Format:**
\`\`\`
{type}({scope}): {description}

{details}

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
\`\`\`

**Output Format:**

On Success:
\`\`\`yaml
status: success
completion_summary:
  task_id: "$TASK_ID"
  package: "{package_name}"
  modified_files: [...]
  updated_files: [...]
  commit_hash: "{commit_hash}"
  branch: "{branch_name}"

final_message: |
  ✅ Task Completed: $TASK_ID
  📦 Package: {package}
  📄 Modified: {files}
  📝 Updated: {docs}
  💾 Commit: {commit_hash}
\`\`\`

**Important:**
- Use current timestamp: $(date '+%Y-%m-%d %H:%M:%S')
- Commit type based on task type (feat/fix/refactor/docs)
- For HARD tasks: provide merge instructions, don't auto-push
- Only return YAML output and final_message
EOF
)"

echo "$SUBAGENT_PROMPT"
