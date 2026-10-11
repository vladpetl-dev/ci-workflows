#!/usr/bin/env bash
# Protect the default branch of a repository with a ruleset: changes only through pull requests,
# the given status checks must pass, no force-push or deletion. Also enables auto-merge (used by
# Renovate) and branch deletion after merge. Re-running updates the same ruleset.
#
# Usage: scripts/protect-branch.sh owner/repo "check one" ["check two" ...]
#   e.g. scripts/protect-branch.sh vladpetl-dev/kyb-investigator "backend / build" "security / trivy" "ai-review / review"
# Needs `gh` authenticated with admin rights on the repo (GH_TOKEN works).
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 owner/repo \"check\" [\"check\" ...]" >&2
  exit 2
fi
repo=$1
shift

checks=$(printf '%s\n' "$@" | jq -R '{context: .}' | jq -s .)
body=$(jq -n --argjson checks "$checks" '{
  name: "default-branch-protection",
  target: "branch",
  enforcement: "active",
  conditions: {ref_name: {include: ["~DEFAULT_BRANCH"], exclude: []}},
  bypass_actors: [],
  rules: [
    {type: "deletion"},
    {type: "non_fast_forward"},
    {type: "pull_request", parameters: {
      required_approving_review_count: 0,
      dismiss_stale_reviews_on_push: false,
      require_code_owner_review: false,
      require_last_push_approval: false,
      required_review_thread_resolution: false}},
    {type: "required_status_checks", parameters: {
      strict_required_status_checks_policy: false,
      required_status_checks: $checks}}
  ]}')

existing=$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "default-branch-protection") | .id')
if [ -n "$existing" ]; then
  gh api -X PUT "repos/$repo/rulesets/$existing" --input - <<<"$body" > /dev/null
  echo "updated ruleset $existing on $repo"
else
  gh api -X POST "repos/$repo/rulesets" --input - <<<"$body" --jq '"created ruleset \(.id) on '"$repo"'"'
fi
gh api -X PATCH "repos/$repo" -F allow_auto_merge=true -F delete_branch_on_merge=true > /dev/null
echo "required checks: $*"
