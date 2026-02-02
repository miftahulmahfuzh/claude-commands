#!/bin/bash
# Dispatch script for Plan Generator Subagent
# Usage: ./dispatch-plan-generator.sh "{TaskID}" "{priority}" "{difficulty}" "{type}" "{title}" "{context}" "{user_note}"

set -e

TASK_ID="$1"
PRIORITY="$2"
DIFFICULTY="$3"
TYPE="$4"
TITLE="$5"
CONTEXT="$6"
USER_NOTE="${7:-}"

if [ -z "$TASK_ID" ] || [ -z "$DIFFICULTY" ]; then
  echo "error: TaskID and difficulty required"
  echo "usage: $0 \"{TaskID}\" \"{priority}\" \"{difficulty}\" \"{type}\" \"{title}\" \"{context}\" \"{user_note?}\""
  exit 1
fi

# Get package code from TaskID (e.g., P1-DB-A236 -> DB)
PACKAGE_CODE=$(echo "$TASK_ID" | cut -d'-' -f2)

# Read the subagent prompt template
SUBAGENT_PROMPT="$(cat <<EOF
You are Subagent 3: Plan Generator for the /do command.

**Your Task:** Create execution brief based on task difficulty. This produces the clean handoff to main context.

**Input:**
\`\`\`yaml
task_metadata:
  id: "$TASK_ID"
  priority: "$PRIORITY"
  difficulty: "$DIFFICULTY"
  type: "$TYPE"
  title: "$TITLE"
  context: "$CONTEXT"
  package_code: "$PACKAGE_CODE"

user_note: "$USER_NOTE"
\`\`\`

**Actions:**
1. Analyze task difficulty: $DIFFICULTY
2. Generate execution brief in YAML format
3. If HARD: Create detailed plan file + git branch + set confirmation_required

**Execution Brief Format (EASY/NORMAL):**
\`\`\`yaml
# Execution Brief for $TASK_ID

task:
  id: "$TASK_ID"
  title: "{Brief task title}"
  difficulty: "$DIFFICULTY"
  type: "$TYPE"

execution:
  target_files:
    - path: "{relative/path/to/file.ext}"
      action: "{create|modify|delete}"
      description: "{What to do}"

  approach: |
    {Concise approach - 2-3 sentences}

  steps:
    - "{Step 1}"
    - "{Step 2}"

validation:
  success_criteria:
    - "{Criterion}"
  test_command: "{command}"
\`\`\`

**Execution Brief Format (HARD):**
\`\`\`yaml
# Execution Brief for $TASK_ID

task:
  id: "$TASK_ID"
  title: "{Brief task title}"
  difficulty: "HARD"
  type: "$TYPE"

execution:
  target_files:
    - path: "{relative/path/to/file.ext}"
      action: "{create|modify|delete}"
      description: "{What to do}"

  approach: |
    {Concise approach}

  steps:
    - "{Step 1}"
    - "{Step 2}"

hard_task_config:
  branch_name: "feature/{slug}-$TASK_ID"
  plan_file: ".workflows/plan/$TASK_ID-plan.md"
  confirmation_required: true

validation:
  success_criteria:
    - "{Criterion}"
  test_command: "{command}"
\`\`\`

**HARD Task Additional Actions:**
1. Create detailed plan file at .workflows/plan/$TASK_ID-plan.md
2. Create git branch: feature/{slug}-$TASK_ID
3. Set confirmation_required: true in brief

**Important:**
- Brief must be VALID YAML
- Keep approach concise (2-3 sentences max)
- Steps must be specific and actionable
- For HARD tasks, ALWAYS create plan file and branch
- Only return YAML brief, nothing else
EOF
)"

echo "$SUBAGENT_PROMPT"
