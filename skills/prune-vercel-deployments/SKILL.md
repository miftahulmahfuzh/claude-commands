---
name: prune-vercel-deployments
description: Use when a Vercel usage/billing email warns about approaching a free-tier "Deployment Storage" cap, or when asked to prune, clean up, or delete old/stale Vercel deployments, or to stop preview deployments from accumulating. Works in any Vercel-linked GitHub repo on this machine, not tied to one project. Deployment Storage is a *different* quota from Vercel Blob object storage — for orphaned Blob objects (shots/, nina/, etc.) use reap-orphaned-blobs instead; this skill won't move that number.
---

# Prune Vercel deployments

## The two quotas people conflate

Vercel's "Deployment Storage" cap is the retained build output of every deployment
ever made (Production **and** Preview). It is unrelated to Vercel Blob object storage.
An email naming "Deployment Storage" means **old deployments**, not orphaned files in
a Blob store — don't reach for a Blob reaper here.

**It is also a team-wide quota**, shared across every project under that Vercel team/scope,
not per-project. Before assuming one repo is the culprit, check deployment volume across
all projects in the team (`vercel project ls --scope <team>`, compare "Updated" recency) —
the loudest one is usually whichever repo pushes to `main` (or any branch) most often, since
every push retains a full build.

## What this skill does

1. **Clears orphaned branch aliases** — Vercel never removes a branch's alias when the
   branch is deleted from git, and `--safe` treats any aliased deployment as live, so this
   is nearly always the real blocker before a prune pass can do anything. Safe by
   construction (only touches aliases whose branch is provably gone) — do this by default,
   no need to ask.
2. **Prunes existing deployments** for a project, keeping only the one(s) with an active
   alias (i.e. whatever is actually live) — safe by construction, cannot take the site down.
3. **Stops it from refilling**: checks whether the repo already disables Vercel preview
   deployments, and if not, proposes the `vercel.json` change to do so — but always asks
   before committing, because it trades away preview-URL testing.

Since this project is on Vercel's **free tier**, every bit of the Deployment Storage cap is
worth reclaiming — run Step 0 by default rather than treating it as optional cleanup.

## Step 0 — Clear orphaned branch aliases

Run this **before** Step 1, and by default (no need to ask first — it never touches a
branch that still exists, so it can't remove anything actually in use):

```bash
scripts/clear-orphaned-aliases.py <project-name> <repo-path> --scope <team-scope>
```

Dry-run by default; add `--apply` once the report looks right. It:

1. Runs `git fetch origin --prune` in `repo-path`, then lists every local + remote branch
   as the "live" set.
2. Paginates `vercel alias ls --scope <team-scope>` (following `--next <cursor>` until it
   stops appearing) and pulls out every `<project>-git-<slug>-<suffix>.vercel.app` alias.
3. Marks an alias stale unless its slug matches a live branch.
4. With `--apply`, removes each stale alias with `vercel alias rm <alias> --yes --scope
   <team-scope>` (stdin redirected to `/dev/null` — see the gotcha below) and tells you to
   re-run Step 1 afterward to actually reclaim the deployments those aliases were pinning.

**The slug match direction matters and is easy to get backwards.** Vercel truncates a long
branch name and appends a 6-hex-char hash to keep the alias under its length limit — e.g.
branch `task-10-the-collection-comes-back-to-where-you` becomes alias slug
`task-10-the-collection-comes-ba-e0e2b3`. The alias is a **prefix** of the real branch name,
never the reverse. Checking `alias.startswith(live)` (or `live + "-"`) instead of
`live.startswith(alias_minus_hash)` silently matches almost nothing, undercounts "live" by a
lot, and reports every real branch as stale garbage — verified the hard way this session (a
first pass reported `live=1` per project instead of the correct 2-5).

**A fully-merged branch that was simply never deleted still counts as "live" by this
check** — it exists in git, so its alias isn't touched, even though the work landed weeks
ago. `daily-words` had exactly this: four `task/N-*` branches merged into `main` 14-15 days
earlier, never deleted. Closing that gap is a separate, deliberate step — check
`git branch --merged main`, then `git branch -d <branch>` (refuses on anything unmerged, so
it's safe) — and only after that will this script's next run mark their aliases stale.

## Step 1 — Prune existing deployments

```bash
scripts/prune-deployments.sh [project-name] [team-scope]
```

- `project-name` defaults to `.projectName` in `./.vercel/project.json` if the repo has
  been linked (`vercel link`); pass it explicitly otherwise.
- `team-scope` is only needed if the CLI can't resolve it on its own (team-owned projects
  usually need it, e.g. `jmt-arot`).

Under the hood this runs `vercel remove <project> --safe --yes`, where `--safe` means
*"skip deployments with an active alias"* — the flag that makes this non-destructive to
whatever is live. **Never drop `--safe`** unless you have independently verified every
deployment being targeted is not the current production one.

Vercel caps bulk removal at **200 deployments per invocation** and requires a **10-minute
cooldown** before the rest can be removed. The script detects the cap-hit warning and loops
with a `sleep 600` automatically — for a large backlog (hundreds of deployments, e.g. a repo
with a high-frequency CI/CD or multi-agent landing workflow) this can take several cycles.
Let it run in the background; it's idempotent, safe to re-run, and eventually converges to
"nothing left to prune."

Before relying on the exact flags, run `vercel remove --help` once — CLI major version
upgrades have changed flag names before, and this skill was written against Vercel CLI 59.

## Step 2 — Check / disable future preview deployments

**Ask before doing this step.** Disabling all preview deployments removes the ability to
test a branch on a live URL before it merges — some workflows depend on that (probing a
preview URL, minting a preview auth cookie, e2e-checking a route pre-merge). Present the
tradeoff and let the human choose:

- **Disable entirely** — maximum storage savings, no more preview URLs at all.
- **Keep previews, just re-run Step 1 periodically** (or wire it into a post-merge/landing
  hook) — no functionality lost, moderate ongoing storage relief instead of a one-time fix.

If they choose to disable, check `vercel.json` for an existing `git.deploymentEnabled` key.
If absent, add:

```json
{
  "git": {
    "deploymentEnabled": {
      "main": true,
      "*": false
    }
  }
}
```

Replace `"main"` with the repo's actual production branch (`git remote show origin | sed
-n '/HEAD branch/s/.*: //p'` — some repos use `master`). Then commit and push to that
branch, since the check is evaluated against the `vercel.json` in the branch/commit being
pushed — until this lands on the production branch, other branches forked before the
change won't inherit it.

**The `"*": false` line is not optional.** Per Vercel's docs (verified 2026-09-16, single
source of truth: https://vercel.com/docs/project-configuration/git-configuration),
`deploymentEnabled`'s default is `true` for *any branch not explicitly listed* — so
`{"main": true}` alone disables nothing else. You need the wildcard to flip the default.
When a branch matches multiple rules, at least one `true` wins (so `main` matching both
`"main": true` and `"*": false` still deploys) — this is by design, not a conflict to
resolve.

This setting only affects **Git-triggered** deployments (a push, or a PR). A manual `vercel
deploy` from the CLI is unaffected.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Treating this as a Blob-storage problem | Wastes a reap-orphaned-blobs run against the wrong quota — the number won't move |
| Dropping `--safe` | Can delete the deployment the production domain is currently aliased to |
| Assuming one prune pass is enough | Silently leaves the remainder queued past the 200-per-run cap; verify by re-running until the "Found N deployments" line reads 0 |
| Only checking the one repo you're in | The cap is team-wide; a quiet sibling project can be a bigger contributor than the one you suspect |
| `{"main": true}` with no `"*": false` | Every unlisted branch still defaults to `true` — previews keep happening |
| Committing the deploymentEnabled change without asking | Silently removes a preview-based QA step other people/workflows may depend on |
| Hardcoding `"main"` | Breaks (does nothing useful) on a repo whose production branch is `master` or something else |
| Matching alias-slug-startswith-live instead of live-startswith-alias-base | The alias is the truncated one; checking it backwards reports almost every live branch as stale |
| Running a long `vercel alias rm`/`vercel remove` loop backgrounded in this environment | Has died silently mid-run with zero output more than once; run in the foreground (or small batches) and redirect the inner command's stdin from `/dev/null` |
| Naming a shell loop variable `aliases` in zsh | Shadows zsh's own reserved `aliases` builtin (the shell's alias table); the assignment silently fails and the loop iterates over shell aliases instead of your data |
| Treating a merged-but-undeleted branch as garbage without checking | It still counts as "live" for alias purposes; delete it with `git branch -d` (merged-only, safe) first, then re-run Step 0 |

## `--safe` has a floor, and it isn't "just the live one"

`--safe` skips **any** deployment with an active alias — and a per-branch alias
(`<project>-git-<branch>-<team>.vercel.app`) stays active for as long as *the alias itself*
exists, which in practice is forever: Vercel does not remove it when the branch is deleted
from GitHub. A repo that pushes many short-lived branches (a swarm/worktree workflow, one
branch per phase) accumulates one alias — and therefore one permanently un-prunable
deployment — per branch that's ever been pushed, whether or not the branch still exists.
`vercel remove <project> --safe --yes` eventually returns `Could not find unaliased
deployments`, but that floor can still be dozens of deployments, not one.

Getting below the floor is Step 0 (clear the orphaned aliases), not dropping `--safe`.
Reach for `--safe`-less removal only after independently confirming none of the targets are
actually live — Step 0 should make that unnecessary in the overwhelming majority of cases.

Measured 2026-09-16 on `run-insights`: 350 deployments before this run, 77 left at the `--safe`
floor after two full passes (243 removed) — and every other project in the same team pruned to a
similar non-zero floor (1-14 remaining) rather than down to a single deployment. Running Step 0
afterward found 76 of those 77 aliases pointed at git branches that no longer existed at all
(only 2 real branches existed in the repo: `main` and one active feature branch) — removing them
and re-running Step 1 dropped `run-insights` to 2 deployments. The same pass across the other 5
projects in the `jmt-arot` team found 37 more orphaned aliases and freed most of their
outstanding deployments too.

## A benign race the script handles

If something else — another session, another terminal, the Vercel dashboard — deletes a
deployment out from under a batch this script is also removing, `vercel remove` exits
non-zero with `Can't find the deployment ... under the context`. That's not a real failure;
the deployment is gone either way. The script retries a few times with a short backoff
instead of aborting on it. Only the 200-per-run cap message triggers the 10-minute sleep.

## Verified

2026-09-16, against `run-insights` in the `jmt-arot` team: found 283 stale deployments on
one project alone (confirming a single high-frequency repo can dominate a team-wide quota),
exercised the 200-per-run cap warning, cross-checked the `deploymentEnabled` schema against
Vercel's own docs before writing it, and hit the race case above for real (a concurrent
smoke-test run raced the main prune job) — which is what surfaced the need for the retry
logic rather than a hard failure on the first `Can't find the deployment` error.

2026-09-16, same team, Step 0 added and exercised on all 6 projects: found and removed 78
orphaned aliases on `run-insights` (96 deployments freed once removed) and 37 more spread
across `daily-words` (10), `jm-tarot` (15), `hospital-inspection-forms` (1),
`expense-tracking` (11) and `fast-order` (0) — 115 orphaned aliases team-wide. Confirmed all
6 projects already had `deploymentEnabled` correctly set (`{main: true, "*": false}`), so
none of this was new preview traffic — 100% inherited backlog from before that setting
existed, or from branches that got deleted without Vercel ever noticing. Also hit and fixed,
for real, both the truncation-direction matching bug and the zsh `aliases`-variable-name
collision described above.
