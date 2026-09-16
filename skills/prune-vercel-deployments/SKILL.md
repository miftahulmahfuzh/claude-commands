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

1. **Prunes existing deployments** for a project, keeping only the one(s) with an active
   alias (i.e. whatever is actually live) — safe by construction, cannot take the site down.
2. **Stops it from refilling**: checks whether the repo already disables Vercel preview
   deployments, and if not, proposes the `vercel.json` change to do so — but always asks
   before committing, because it trades away preview-URL testing.

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

## `--safe` has a floor, and it isn't "just the live one"

`--safe` skips **any** deployment with an active alias — and a per-branch alias
(`<project>-git-<branch>-<team>.vercel.app`) stays active for as long as that branch exists on
GitHub, however stale. A repo that pushes many short-lived branches (a swarm/worktree workflow,
one branch per phase) accumulates one alias — and therefore one permanently un-prunable
deployment — per branch that's never been deleted. `vercel remove <project> --safe --yes`
eventually returns `Could not find unaliased deployments`, but that floor can still be dozens of
deployments, not one. Getting below it means deleting the stale git branches themselves (out of
scope for this skill — that's a repo/branch-hygiene decision, not a storage-cleanup one) or
dropping `--safe` after manually confirming none of the targets are actually live.

Measured 2026-09-16 on `run-insights`: 350 deployments before this run, 77 left at the `--safe`
floor after two full passes (243 removed) — and every other project in the same team pruned to a
similar non-zero floor (1-14 remaining) rather than down to a single deployment.

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
