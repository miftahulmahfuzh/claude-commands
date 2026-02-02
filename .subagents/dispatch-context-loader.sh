#!/bin/bash
# Dispatch script for Context Loader Subagent
# Usage: ./dispatch-context-loader.sh "{package_path}" "{priority}" "{difficulty}" "{type}" "{title}" "{context}"

set -e

PACKAGE_PATH="$1"
PRIORITY="$2"
DIFFICULTY="$3"
TYPE="$4"
TITLE="$5"
CONTEXT="$6"

if [ -z "$PACKAGE_PATH" ]; then
  echo "error: package_path required"
  echo "usage: $0 \"{package_path}\" \"{priority}\" \"{difficulty}\" \"{type}\" \"{title}\" \"{context}\""
  exit 1
fi

# Read the subagent prompt template
SUBAGENT_PROMPT="$(cat <<EOF
You are Subagent 2: Context Loader for the /do command.

**Your Task:** Load and synthesize relevant context from package documentation files.

**Input:**
\`\`\`yaml
package_path: "$PACKAGE_PATH"
task_metadata:
  priority: "$PRIORITY"
  difficulty: "$DIFFICULTY"
  type: "$TYPE"
  title: "$TITLE"
  context: "$CONTEXT"
\`\`\`

**Actions:**
1. Read task details from {package_path}/.workflows/todos.md
2. Read package_readme.md if exists
3. Read analysis_report.md if exists
4. Synthesize into concise context packet

**Output Format (YAML):**

On Success:
\`\`\`yaml
status: success
context_packet:
  task_description: "{full task description in 1-2 sentences}"
  docs_summary: |
    {Synthesized summary with bullet points}
  file_references:
    - "{relative/path/to/file.ext}"
  related_tasks:
    - "{TaskID}"
  package_structure:
    main_module: "{module_name}"
    key_files:
      - "{file}"
\`\`\`

**Important:**
- Synthesize, don't copy raw content
- Keep docs_summary concise (3-5 bullet points max)
- Extract file references from task and docs
- Only return YAML output, nothing else
EOF
)"

echo "$SUBAGENT_PROMPT"
