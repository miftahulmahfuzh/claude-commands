# Version Update Command

Automate semantic versioning and changelog maintenance for the current branch.

## Execution Steps

### 1. Fetch latest remote data
- Run `git fetch origin` to ensure local refs are current

### 2. Get current branch information
- Determine current active branch name
- Get the latest commit hash on this branch
- **Branch Mode Detection:**
  - If current branch is `main` or `master`: **Direct Mode**
  - If current branch is NOT `main` or `master`: **Merge Mode**

### 3. Identify latest tagged version
- Find the most recent semantic version tag on origin/main (format: vX.Y.Z)
- Extract the commit hash of this tagged version
- If there is no tag, then use the first commit hash

### 4. Analyze code differences

**For Direct Mode (already on main):**
- Compare the tagged commit against current HEAD on main
- No branch switching required

**For Merge Mode (feature branch):**
- Compare the tagged commit against the current branch's latest commit

Generate detailed diff analysis including:
- Files modified, added, or deleted
- Function/method changes
- Breaking changes identification
- New features added
- Bug fixes implemented
- Performance improvements
- Dependencies modified

### 5. Extract commit history
- Retrieve all commit messages between the tagged version and current branch HEAD
- Parse commit messages for conventional commit patterns
- Categorize changes by type (feat, fix, refactor, docs, etc.)

### 6. Determine version increment
- Apply semantic versioning rules:
  - MAJOR (X): Breaking changes detected
  - MINOR (Y): New features added without breaking changes
  - PATCH (Z): Only bug fixes and non-breaking changes
- Calculate new version number

### 7. Generate updated CHANGELOG.md
- Create new changelog entry following "Keep a Changelog" format
- Include:
  - New version number and date
  - Categorized changes (Added, Changed, Deprecated, Removed, Fixed, Security)
  - Detailed descriptions based on diff analysis and commit messages
- Preserve existing changelog history below new entry

### 8. Commit and push changelog

**For Direct Mode (already on main):**
- Stage the updated CHANGELOG.md
- Commit with message: "docs: update changelog for vX.Y.Z"
- Push directly to origin/main

**For Merge Mode (feature branch):**
- Stage the updated CHANGELOG.md
- Commit with message: "docs: update changelog for vX.Y.Z"
- Push changes to current branch on origin

### 9. Merge to main (Merge Mode ONLY)

**Skip this step entirely if in Direct Mode (already on main)**

**For Merge Mode only:**
- Switch to origin/main branch
- Pull latest changes to ensure current
- Merge current branch into main
- Resolve any conflicts if they occur

### 10. Create and push version tag

**For Direct Mode:**
- Already on main, create tag directly
- Create annotated git tag with new version number
- Include changelog entry in tag annotation
- Push both the commit and new tag to origin

**For Merge Mode:**
- After merge completes, create tag on main
- Create annotated git tag with new version number
- Include changelog entry in tag annotation
- Push both the merge commit and new tag to origin

### 11. Return to original branch (Merge Mode ONLY)

**Skip this step if in Direct Mode (already on main)**

**For Merge Mode only:**
- Switch back to the original working branch
- Pull any updates from origin

## Error Handling

- Verify git repository exists and is clean before starting
- Check for uncommitted changes and prompt user action
- Validate that origin/main exists and is accessible
- **For Merge Mode:** Ensure current branch is not main before attempting merge
- **For Direct Mode:** Confirm user wants to version directly from main
- Verify no merge conflicts exist before proceeding (Merge Mode only)
- Confirm tag doesn't already exist before creation

## Output Requirements

Provide detailed summary including:
- **Branch mode used:** Direct Mode (main) or Merge Mode (feature branch)
- Version increment rationale
- Key changes identified
- Changelog entries created
- Git operations performed
- Any warnings or issues encountered

## Execution Flow Summary

```
         ┌─────────────────────────┐
         │ Check current branch    │
         └────────┬────────────────┘
                  │
             ┌────▼────┐
             │ main?   │
             └─┬────┬──┘
               │    │
           YES │    │ NO
               │    │
     ┌─────────┘    └──────────┐
     │                         │
┌────▼─────────────────┐  ┌────▼─────────────────────┐
│ DIRECT MODE          │  │ MERGE MODE               │
├──────────────────────┤  ├──────────────────────────┤
│ 1. Analyze diff      │  │ 1. Analyze diff          │
│ 2. Generate changelog│  │ 2. Generate changelog    │
│ 3. Commit on main    │  │ 3. Commit on branch      │
│ 4. Push main         │  │ 4. Push branch           │
│ 5. Create tag        │  │ 5. Switch to main        │
│ 6. Push tag          │  │ 6. Merge branch          │
│ 7. DONE ✓            │  │ 7. Create tag            │
│                      │  │ 8. Push merge + tag      │
│                      │  │ 9. Return to branch      │
│                      │  │ 10. DONE ✓               │
└──────────────────────┘  └──────────────────────────┘
```
