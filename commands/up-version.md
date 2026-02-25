# Version Update Command

Automate semantic versioning and changelog maintenance for the current branch.

## Parameters

- `--ver <version>`: (Optional) Specify exact version to use (e.g., `--ver v0.30.1`)
  - When provided, skips semantic versioning analysis
  - Must be in semantic version format (vX.Y.Z)
  - Disables automatic version increment determination

## Execution Steps

### 1. Fetch latest remote data
- Run `git fetch origin` to ensure local refs are current

### 2. Parse command parameters
- Check if `--ver` parameter is provided
- If `--ver` is present:
  - Validate format (must be vX.Y.Z where X, Y, Z are numbers)
  - Use provided version as new version
  - Skip semantic versioning analysis in step 6
- If `--ver` is not present:
  - Proceed with normal semantic versioning analysis

### 3. Get current branch information
- Determine current active branch name
- Get the latest commit hash on this branch
- **Branch Mode Detection:**
  - If current branch is `main` or `master`: **Direct Mode**
  - If current branch is NOT `main` or `master`: **Merge Mode**

### 4. Identify latest tagged version
- Find the most recent semantic version tag on origin/main (format: vX.Y.Z)
- Extract the commit hash of this tagged version
- If there is no tag, then use the first commit hash

### 5. Analyze code differences

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

### 6. Determine version increment
- **If --ver parameter was provided:**
  - Use the manually specified version
  - Skip semantic versioning analysis
  - Validate that provided version doesn't already exist as a tag
- **If no --ver parameter:**
  - Apply semantic versioning rules:
    - MAJOR (X): Breaking changes detected
    - MINOR (Y): New features added without breaking changes
    - PATCH (Z): Only bug fixes and non-breaking changes
  - Calculate new version number

### 7. Extract commit history
- Retrieve all commit messages between the tagged version and current branch HEAD
- Parse commit messages for conventional commit patterns
- Categorize changes by type (feat, fix, refactor, docs, etc.)

### 8. Generate updated CHANGELOG.md
- Create new changelog entry following "Keep a Changelog" format
- Include:
  - New version number and date
  - Categorized changes (Added, Changed, Deprecated, Removed, Fixed, Security)
  - Detailed descriptions based on diff analysis and commit messages
- Preserve existing changelog history below new entry

### 9. Update API_VERSION in .env file
- Check if `.env` file exists in project root directory
- If `.env` exists:
  - Read current file content
  - Look for existing `API_VERSION` variable
  - If `API_VERSION` exists:
    - Update its value to the new version number (without 'v' prefix)
    - Example: `API_VERSION=0.30.1`
  - If `API_VERSION` doesn't exist:
    - Add `API_VERSION=<new_version>` at the end of the file
    - Example: `API_VERSION=0.30.1`
- If `.env` doesn't exist:
  - Create new `.env` file with `API_VERSION=<new_version>`
  - Add appropriate file header comments if needed
- Preserve all other existing `.env` variables and formatting
- Handle edge cases:
  - Files with BOM (Byte Order Mark)
  - Different line ending formats (LF, CRLF)
  - Existing comments around API_VERSION variable

### 10. Commit and push changelog and .env updates

**For Direct Mode (already on main):**
- Stage the updated CHANGELOG.md and .env file (if modified)
- Commit with message: "docs: update changelog for vX.Y.Z"
- Push directly to origin/main

**For Merge Mode (feature branch):**
- Stage the updated CHANGELOG.md and .env file (if modified)
- Commit with message: "docs: update changelog for vX.Y.Z"
- Push changes to current branch on origin

### 11. Merge to main (Merge Mode ONLY)

**Skip this step entirely if in Direct Mode (already on main)**

**For Merge Mode only:**
- Switch to origin/main branch
- Pull latest changes to ensure current
- Merge current branch into main
- Resolve any conflicts if they occur

### 12. Create and push version tag

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

### 13. Return to original branch (Merge Mode ONLY)

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
- **--ver parameter validation:**
  - If provided, validate format matches semantic version pattern (vX.Y.Z)
  - Verify that X, Y, Z are valid numbers
  - Ensure specified version doesn't already exist as a tag
  - Abort with error message if validation fails
- **.env file handling:**
  - Verify .env file is accessible and writable if it exists
  - Handle file permission errors gracefully
  - Preserve file encoding and line endings
  - Create backup of original .env before modification (optional)

## Output Requirements

Provide detailed summary including:
- **Branch mode used:** Direct Mode (main) or Merge Mode (feature branch)
- **Version determination:** Manual (--ver parameter) or Automatic (semantic analysis)
- Version increment rationale (for automatic mode) or specified version (for manual mode)
- Key changes identified
- Changelog entries created
- **.env file updates:** Whether API_VERSION was updated, created, or if .env file was not found
- Git operations performed
- Any warnings or issues encountered
- **If --ver was used:** Note that semantic versioning analysis was skipped

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
│ 3. Update .env file  │  │ 3. Update .env file      │
│ 4. Commit on main    │  │ 4. Commit on branch      │
│ 5. Push main         │  │ 5. Push branch           │
│ 6. Create tag        │  │ 6. Switch to main        │
│ 7. Push tag          │  │ 7. Merge branch          │
│ 8. DONE ✓            │  │ 8. Create tag            │
│                      │  │ 9. Push merge + tag      │
│                      │  │ 10. Return to branch     │
│                      │  │ 11. DONE ✓               │
└──────────────────────┘  └──────────────────────────┘
```
