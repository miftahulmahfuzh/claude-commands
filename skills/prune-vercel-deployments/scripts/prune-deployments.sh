#!/usr/bin/env bash
# Delete every Vercel deployment for a project except whichever one currently
# holds an active alias (i.e. anything not live). Loops around Vercel's
# 200-deployments-per-run cap, sleeping through the required 10-minute
# cooldown between batches.
#
# Usage: prune-deployments.sh [project-name] [team-scope]
#   project-name  defaults to .projectName in ./.vercel/project.json
#                 (run `vercel link` first if this repo has never been linked)
#   team-scope    only needed if the CLI can't resolve scope on its own
set -euo pipefail

PROJECT="${1:-}"
SCOPE="${2:-}"

if [ -z "$PROJECT" ] && [ -f .vercel/project.json ]; then
  PROJECT="$(jq -r '.projectName // empty' .vercel/project.json)"
fi

if [ -z "$PROJECT" ]; then
  echo "No project name given and no .vercel/project.json found in $(pwd)." >&2
  echo "Pass one explicitly, or run 'vercel link' in this repo first." >&2
  exit 1
fi

SCOPE_ARGS=()
[ -n "$SCOPE" ] && SCOPE_ARGS=(--scope "$SCOPE")

echo "Pruning non-aliased deployments for '$PROJECT'${SCOPE:+ (scope: $SCOPE)}..."
echo "(--safe means only deployments with no active alias are ever touched.)"
echo

while true; do
  set +e
  OUT="$(vercel remove "$PROJECT" --safe --yes "${SCOPE_ARGS[@]}" 2>&1)"
  STATUS=$?
  set -e
  echo "$OUT"

  if [ $STATUS -ne 0 ] && ! echo "$OUT" | grep -q "Only 200 deployments can get deleted at once"; then
    echo
    echo "vercel remove exited non-zero; stopping rather than looping on an error." >&2
    exit $STATUS
  fi

  if echo "$OUT" | grep -q "Only 200 deployments can get deleted at once"; then
    echo
    echo "Hit the 200-per-run cap. Waiting 10 minutes before the next batch..."
    sleep 600
    echo
    continue
  fi

  break
done

echo
echo "Done — re-run any time. --safe guarantees this only ever removes"
echo "deployments with no active alias, so it can never touch what's live."
