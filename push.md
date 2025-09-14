# Push Command

# /home/miftah/.claude/commands/push.md

Automate git workflow with intelligent commit message generation based on code analysis.

## Execution Steps
1. **Validate git repository state**
   - Verify current directory is a git repository
   - Check if remote origin is configured
   - Ensure there are staged or unstaged changes to commit

2. **Analyze current changes**
   - Run `git status` to identify modified, added, and deleted files
   - Generate `git diff HEAD` to capture all changes since last commit
   - Parse diff output to understand:
     - File types affected (source code, config, docs, tests)
     - Lines added/removed per file
     - Function/class/method modifications
     - Import/dependency changes
     - Configuration updates

3. **Categorize changes by type**
   - **Feature additions**: New functions, classes, or significant functionality
   - **Bug fixes**: Error handling, corrections, patches
   - **Refactoring**: Code restructuring without behavior changes
   - **Documentation**: README, comments, docstrings
   - **Configuration**: Environment files, build configs, dependencies
   - **Tests**: Test additions, modifications, or deletions
   - **Style**: Formatting, linting, minor cosmetic changes

4. **Generate intelligent commit message**
   - Create concise, descriptive commit message following conventional commit format
   - Structure: `<type>(<scope>): <description>`
   - Examples:
     - `feat(auth): add OAuth2 login integration`
     - `fix(api): resolve null pointer in user validation`
     - `refactor(database): optimize query performance`
     - `docs(readme): update installation instructions`
   - Include multiple types if changes span categories
   - Limit subject line to 50 characters, body to 72 characters per line

5. **Stage and commit changes**
   - Execute `git add .` to stage all changes
   - Run `git commit -m "<generated_message>"` with the formulated message
   - Capture commit hash for reference

6. **Push to remote**
   - Identify current branch name
   - Execute `git push origin <current_branch>`
   - Handle any push conflicts or authentication prompts

7. **Verify push success**
   - Confirm remote repository received the commit
   - Display pushed commit hash and branch information

## Error Handling
- Exit if not in a git repository with clear error message
- Check for uncommitted changes - if none exist, inform user and exit
- Handle merge conflicts on push by providing resolution guidance
- Detect authentication failures and prompt for credentials
- Verify remote connectivity before attempting push
- If push is rejected (non-fast-forward), suggest pull/rebase strategy
- Validate commit message length and format before committing

## Output Requirements
Display comprehensive summary including:
- Number of files modified, added, deleted
- Lines of code changed per file type
- Generated commit message with reasoning
- Commit hash created
- Push status and target branch
- Any warnings or conflicts encountered
- Time taken for complete operation
