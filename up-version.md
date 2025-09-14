# Version Update Command

# /home/miftah/.claude/commands/up-version.md

Automate semantic versioning and changelog maintenance for the current branch.

## Execution Steps

1. **Fetch latest remote data**
   - Run `git fetch origin` to ensure local refs are current

2. **Identify latest tagged version on origin/main**
   - Find the most recent semantic version tag on origin/main (format: vX.Y.Z)
   - Extract the commit hash of this tagged version
   - If there is no tag, then use the first commit hash

3. **Get current branch information**
   - Determine current active branch name
   - Get the latest commit hash on this branch

4. **Analyze code differences**
   - Compare the tagged commit against the current branch's latest commit
   - Generate detailed diff analysis including:
     - Files modified, added, or deleted
     - Function/method changes
     - Breaking changes identification
     - New features added
     - Bug fixes implemented
     - Performance improvements
     - Dependencies modified

5. **Extract commit history**
   - Retrieve all commit messages between the tagged version and current branch HEAD
   - Parse commit messages for conventional commit patterns
   - Categorize changes by type (feat, fix, refactor, docs, etc.)

6. **Determine version increment**
   - Apply semantic versioning rules:
     - MAJOR (X): Breaking changes detected
     - MINOR (Y): New features added without breaking changes
     - PATCH (Z): Only bug fixes and non-breaking changes
   - Calculate new version number

7. **Generate updated CHANGELOG.md**
   - Create new changelog entry following "Keep a Changelog" format
   - Include:
     - New version number and date
     - Categorized changes (Added, Changed, Deprecated, Removed, Fixed, Security)
     - Detailed descriptions based on diff analysis and commit messages
   - Preserve existing changelog history below new entry

8. **Commit and push changelog**
   - Stage the updated CHANGELOG.md
   - Commit with message: "docs: update changelog for vX.Y.Z"
   - Push changes to current branch on origin

9. **Merge to main**
   - Switch to origin/main branch
   - Pull latest changes to ensure current
   - Merge current branch into main
   - Resolve any conflicts if they occur

10. **Create and push version tag**
    - Create annotated git tag with new version number
    - Include changelog entry in tag annotation
    - Push both the merge commit and new tag to origin

11. **Return to original branch**
    - Switch back to the original working branch
    - Pull any updates from origin

## Error Handling

- Verify git repository exists and is clean before starting
- Check for uncommitted changes and prompt user action
- Validate that origin/main exists and is accessible
- Ensure current branch is not main before attempting merge
- Verify no merge conflicts exist before proceeding
- Confirm tag doesn't already exist before creation

## Output Requirements

Provide detailed summary including:
- Version increment rationale
- Key changes identified
- Changelog entries created
- Git operations performed
- Any warnings or issues encountered
