# Subagent 3: Plan Generator

**Purpose:** Create execution brief based on task difficulty. This is the final prep subagent that produces the clean handoff to main context.

## Input

```yaml
task_metadata:
  priority: "P0-P4"
  difficulty: "EASY|NORMAL|HARD"
  type: "Bug|Feature|Refactor|Docs"
  title: "{brief title}"
  context: "{task context}"

context_packet:
  task_description: "{full task description}"
  docs_summary: "{synthesized summary}"
  file_references:
    - "{file_path}"
  related_tasks:
    - "{TaskID}"

user_note: "{additional instructions from --note flag}"  # optional
```

## Actions

### 1. Analyze Task

- Review task metadata (difficulty, type, priority)
- Review context packet (task description, file references)
- Consider user note if provided
- Determine execution approach based on difficulty and type

### 2. Generate Execution Brief

Create execution brief in the specified YAML format (see Output section below).

**For EASY/NORMAL tasks:**
- Simple step-by-step approach
- Direct file modifications
- No branch creation

**For HARD tasks:**
- Detailed implementation plan
- Create plan file at `.workflows/plan/{TaskID}-plan.md`
- Create git branch
- Request user confirmation

### 3. HARD Task Special Actions (if difficulty is HARD)

1. **Create detailed plan file:**
   ```bash
   mkdir -p {package_path}/.workflows/plan
   cat > {package_path}/.workflows/plan/{TaskID}-plan.md << 'EOF'
   # Implementation Plan: {TaskID}

   **Task**: {task_description}
   **Difficulty**: HARD
   **Branch**: feature/{slug}-{TaskID}
   **Created**: {YYYY-MM-DD HH:MM:SS}

   ## Analysis Phase
   - Current state assessment
   - Dependencies identification
   - Risk assessment
   - Testing strategy

   ## Implementation Phases
   - Phase 1: {description}
   - Phase 2: {description}
   - ...

   ## Rollback Strategy
   - How to undo changes if needed
   - Safe rollback points

   ## Success Criteria
   - {measurable success criteria}
   EOF
   ```

2. **Create git branch:**
   ```bash
   git checkout -b feature/{task-description-slug}-{TaskID}
   ```

3. **Set confirmation flag in brief:**
   ```yaml
   confirmation_required: true
   ```

## Output

**On Success (EASY/NORMAL):**
```yaml
# Execution Brief for {TaskID}

task:
  id: "{TaskID}"
  title: "{Brief task title}"
  difficulty: "EASY|NORMAL"
  type: "{Bug|Feature|Refactor|Docs}"

execution:
  target_files:
    - path: "{relative/path/to/file.ext}"
      action: "{create|modify|delete}"
      description: "{What to do with this file}"

  approach: |
    {Concise implementation approach - 2-3 sentences max}

  steps:
    - "{Step 1: specific action}"
    - "{Step 2: specific action}"
    - "{Step 3: specific action}"

validation:
  success_criteria:
    - "{Criterion 1}"
    - "{Criterion 2}"
  test_command: "{command to verify}"  # if applicable
```

**On Success (HARD):**
```yaml
# Execution Brief for {TaskID}

task:
  id: "{TaskID}"
  title: "{Brief task title}"
  difficulty: "HARD"
  type: "{Bug|Feature|Refactor|Docs}"

execution:
  target_files:
    - path: "{relative/path/to/file.ext}"
      action: "{create|modify|delete}"
      description: "{What to do}"

  approach: |
    {Concise implementation approach - 2-3 sentences}

  steps:
    - "{Step 1: specific action}"
    - "{Step 2: specific action}"

hard_task_config:
  branch_name: "feature/{slug}-{TaskID}"
  plan_file: ".workflows/plan/{TaskID}-plan.md"
  confirmation_required: true

validation:
  success_criteria:
    - "{Criterion 1}"
  test_command: "{command to verify}"
```

**On Error:**
```yaml
status: "error"
error_type: "invalid_input|plan_creation_failed|branch_creation_failed"
error_message: "{clear error message}"
```

## Execution Brief Field Specifications

### task.id
- Format: `P{Priority}-{PackageCode}-{4CharID}`
- Example: `P1-DB-A236`

### execution.target_files
Array of files to modify:

```yaml
- path: "{relative/path/from/repo/root}"
  action: "create|modify|delete"
  description: "{what needs to be done with this file}"
```

### execution.approach
- 2-3 sentences maximum
- Describe the implementation approach
- Focus on WHAT, not WHY
- No verbose explanations

### execution.steps
- Specific, actionable steps
- Each step should be clear and independent
- Ordered logically
- Use verb-first language ("Add import", "Create function")

### validation.success_criteria
- Measurable criteria
- What "done" looks like
- Can be verified objectively

### validation.test_command
- Command to verify the changes
- Optional (may not apply to all task types)
- Should be runnable from repo root

## HARD Task Plan Template

The `.workflows/plan/{TaskID}-plan.md` file should contain:

```markdown
# Implementation Plan: {TaskID}

**Task**: {task_description}
**Difficulty**: HARD
**Branch**: feature/{slug}-{TaskID}
**Created**: {YYYY-MM-DD HH:MM:SS}

---

## Analysis Phase

### Current State
{Assessment of current code state}

### Dependencies
{List of dependencies this task has}

### Risk Assessment
{Potential risks and mitigation strategies}

### Testing Strategy
{How the changes will be tested}

---

## Implementation Phases

### Phase 1: {Title}
{Description of phase}
**Files:** {list of files}
**Changes:** {description of changes}
**Validation:** {how to verify this phase}

### Phase 2: {Title}
{repeat for each phase}

---

## Rollback Strategy

{How to undo changes if needed}

### Rollback Points
- After Phase 1: {rollback method}
- After Phase 2: {rollback method}

---

## Success Criteria

- [ ] {measurable criterion 1}
- [ ] {measurable criterion 2}
- [ ] {measurable criterion 3}
```

## Error Handling

| Scenario | Response |
|----------|----------|
| Invalid difficulty value | `error_type: invalid_input` - valid values: EASY, NORMAL, HARD |
| Plan file creation fails | `error_type: plan_creation_failed` - check directory permissions |
| Branch already exists | Include in brief: `branch_exists: true` with switch/delete suggestion |
| Branch creation fails | `error_type: branch_creation_failed` - include git error message |
| Context packet incomplete | Use available context, log warning |

## Implementation Notes

- Execution brief must be VALID YAML
- Keep approach concise (2-3 sentences)
- Steps should be specific and actionable
- For HARD tasks, ALWAYS create plan file and branch
- Confirmation flag signals main context to wait for user input
- Test command should be runnable from repository root
- Success criteria must be measurable and verifiable

## Example Brief (EASY Task)

```yaml
# Execution Brief for P2-CL-A001

task:
  id: "P2-CL-A001"
  title: "Fix typo in error message"
  difficulty: "EASY"
  type: "Bug"

execution:
  target_files:
    - path: "logger.go"
      action: "modify"
      description: "Fix typo at line 45"

  approach: |
    Change "recieved" to "received" in error message at logger.go:45.
    Simple text correction with no functional impact.

  steps:
    - "Read logger.go"
    - "Correct typo at line 45"
    - "Write file back"

validation:
  success_criteria:
    - "Typo corrected in error message"
  test_command: "grep -n 'received' logger.go"
```

## Example Brief (HARD Task)

```yaml
# Execution Brief for P1-BC-A123

task:
  id: "P1-BC-A123"
  title: "Refactor broadcast manager"
  difficulty: "HARD"
  type: "Refactor"

execution:
  target_files:
    - path: "broadcast/manager.go"
      action: "modify"
      description: "Extract methods from InitiateAndManageBroadcast"
    - path: "broadcast/validator.go"
      action: "create"
      description: "New validation module"

  approach: |
    Extract 146-line function into smaller methods following single responsibility.
    Create new validator module for pre-flight checks.

  steps:
    - "Extract validatePreFlightConditions() method"
    - "Extract waitForClientConnection() method"
    - "Create validator.go with validation logic"
    - "Update manager.go to use new methods"

hard_task_config:
  branch_name: "feature/refactor-broadcast-manager-P1-BC-A123"
  plan_file: ".workflows/plan/P1-BC-A123-plan.md"
  confirmation_required: true

validation:
  success_criteria:
    - "InitiateAndManageBroadcast function reduced to < 50 lines"
    - "All tests pass"
  test_command: "go test ./broadcast -v"
```
