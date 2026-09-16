#!/usr/bin/env python3
"""Remove Vercel per-branch aliases whose git branch no longer exists.

--safe (in prune-deployments.sh) never touches a deployment with an active
alias. Vercel creates one alias per branch (`<project>-git-<branch>-<suffix>
.vercel.app`) but never removes it when the branch is deleted from git — so
a repo that cycles through many short-lived branches (a swarm/worktree
workflow, one branch per task) accumulates a permanent floor of un-prunable
deployments, one per branch that was ever pushed and never had its alias
cleaned up. This script finds and removes exactly those orphaned aliases so
prune-deployments.sh can then reclaim the deployments they were pinning.

It only ever removes an alias whose branch is provably gone from git (local
+ origin, after a --prune fetch). It never deletes a git branch and never
touches a deployment or alias for a branch that still exists.

Usage:
  clear-orphaned-aliases.py <project-name> <repo-path> [--scope TEAM] [--apply]

  --scope TEAM   Vercel team scope (e.g. jmt-arot). Also assumed to be the
                 trailing hostname segment before .vercel.app — true for
                 every project observed so far; pass --suffix to override.
  --suffix SUF   Hostname suffix segment if it differs from --scope.
  --apply        Actually remove the stale aliases. Without it, dry-run only.

Dry-run by default. Always run once without --apply and read the report
before re-running with it.
"""
import argparse
import re
import subprocess
import sys


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def paginated_alias_listing(scope):
    """Return the concatenated raw text of every `vercel alias ls` page."""
    pages = []
    next_cursor = None
    for _ in range(50):  # hard stop; a real account never needs this many pages
        cmd = ["vercel", "alias", "ls", "--scope", scope]
        if next_cursor:
            cmd += ["--next", next_cursor]
        res = sh(cmd)
        text = res.stdout + res.stderr
        pages.append(text)
        m = re.search(r"--next (\d+)", text)
        if not m:
            break
        next_cursor = m.group(1)
    return "\n".join(pages)


def live_branch_slugs(repo_path):
    sh(["git", "-C", repo_path, "fetch", "origin", "--prune"])
    res = sh(["git", "-C", repo_path, "branch", "-a"])
    slugs = set()
    for line in res.stdout.splitlines():
        line = line.strip().lstrip("*+").strip()
        if not line or "HEAD ->" in line:
            continue
        line = line.removeprefix("remotes/origin/")
        slugs.add(line.replace("/", "-"))
    return slugs


def is_live(alias_slug, live_slugs):
    # Vercel truncates a long branch name and appends a 6-hex-char hash to
    # keep the alias under its length limit, e.g. branch
    # "task-10-the-collection-comes-back-to-where-you" becomes alias slug
    # "task-10-the-collection-comes-ba-e0e2b3". The alias is therefore a
    # PREFIX of the real branch name, not the other way around — check
    # live.startswith(base), never alias.startswith(live).
    base = re.sub(r"-[0-9a-f]{6}$", "", alias_slug)
    return any(live == alias_slug or live.startswith(base) for live in live_slugs)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project")
    ap.add_argument("repo_path")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--suffix", default=None)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    suffix = args.suffix or args.scope

    live = live_branch_slugs(args.repo_path)
    text = paginated_alias_listing(args.scope)
    pattern = re.compile(
        rf"{re.escape(args.project)}-git-([a-z0-9-]+)-{re.escape(suffix)}\.vercel\.app"
    )
    alias_slugs = sorted(set(pattern.findall(text)))

    stale = [s for s in alias_slugs if not is_live(s, live)]
    kept = [s for s in alias_slugs if is_live(s, live)]

    print(f"{args.project}: {len(alias_slugs)} branch aliases, "
          f"{len(kept)} live, {len(stale)} stale")
    if not stale:
        return

    for s in stale:
        print(f"  stale: {args.project}-git-{s}-{suffix}.vercel.app")

    if not args.apply:
        print("\nDry run — nothing removed. Re-run with --apply to remove these.")
        return

    ok = fail = 0
    for s in stale:
        alias = f"{args.project}-git-{s}-{suffix}.vercel.app"
        res = sh(
            ["vercel", "alias", "rm", alias, "--yes", "--scope", args.scope],
            stdin=subprocess.DEVNULL,
        )
        out = res.stdout + res.stderr
        success = "success" in out.lower()
        print(f"  {'removed' if success else 'FAILED'}: {alias}", flush=True)
        ok += success
        fail += not success

    print(f"\nremoved={ok} failed={fail}")
    if ok:
        print("Re-run prune-deployments.sh now to reclaim the freed deployments.")


if __name__ == "__main__":
    sys.exit(main())
