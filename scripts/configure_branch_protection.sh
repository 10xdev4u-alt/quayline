#!/usr/bin/env bash
# Apply the branch policy declared in config/branch_protection.json.
#
# The point of a script is that the policy is reproducible, and the point of the
# tests over config/branch_protection.json is that the script cannot be pointed at
# a policy that quietly contradicts AGENTS.md. Neither is worth much if the script
# fails halfway and leaves the repository in a state nobody intended, so this one
# checks its own capability first and verifies its own result last.
#
# Two surfaces, in this order, and the order is not cosmetic:
#
#   1. Repository settings. Merge methods live only here. There is no branch
#      protection field for them, so a script that only touches protection leaves
#      squash available.
#   2. Branch protection on main. Reviews, required checks, conversation
#      resolution, force pushes.
#
# Usage:
#   scripts/configure_branch_protection.sh            apply
#   scripts/configure_branch_protection.sh --check    report only, change nothing
#
# Requires an authenticated gh with admin on the repository. Branch protection is
# an admin only surface, and the failure mode for a collaborator is a 403 that
# says nothing about which step was wrong.

set -euo pipefail

REPO="${QUAYLINE_REPO:-10xdev4u-alt/quayline}"
BRANCH="${QUAYLINE_BRANCH:-main}"
POLICY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/branch_protection.json"
CODEOWNERS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.github/CODEOWNERS"

CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

step() { printf '\n=== %s\n' "$1"; }
fail() { printf 'FAILED: %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- capability
# Fail before touching anything. Issue 92 was a collaborator discovered as a 403
# halfway through a sequence of calls, which is a confusing way to find out.
step "Checking capability before changing anything"

gh auth status >/dev/null 2>&1 || fail "gh is not authenticated. Run: gh auth login"

CALLER="$(gh api "repos/$REPO" --jq '.permissions.admin')"
[[ "$CALLER" == "true" ]] || fail "the active gh account is not an admin on $REPO.
    Branch protection is an admin only surface. Switch accounts first:
      gh auth switch --user 10xdev4u-alt
    then re-run this script."

# CODEOWNERS only takes effect from the default branch, so it must already be
# merged before require_code_owner_reviews means anything. Warn rather than fail,
# because the first run necessarily precedes the merge that lands the file.
if gh api "repos/$REPO/contents/.github/CODEOWNERS?ref=$BRANCH" >/dev/null 2>&1; then
    echo "CODEOWNERS is on $BRANCH. Approvals will be restricted to the two named accounts."
else
    echo "WARNING: CODEOWNERS is not yet on $BRANCH, so require_code_owner_reviews"
    echo "         will not restrict approvers until this pull request merges."
fi

# ---------------------------------------------------------------- apply
if [[ "$CHECK_ONLY" -eq 0 ]]; then
    step "Applying repository merge methods"
    gh api -X PATCH "repos/$REPO" \
        --input <(jq '.repository
                       | with_entries(select(.key | startswith("$") | not))' "$POLICY") >/dev/null
    echo "squash is now $(jq -r '.repository.allow_squash_merge | if . then "ALLOWED" else "blocked" end' "$POLICY")"

    step "Applying branch protection on $BRANCH"
    # Every key beginning with $ is documentation. Strip them recursively rather
    # than by name, so adding a comment to a new key cannot break the apply step.
    gh api -X PUT "repos/$REPO/branches/$BRANCH/protection" \
        --input <(jq 'def clean:
                       walk(if type == "object"
                            then with_entries(select(.key | startswith("$") | not))
                            else . end);
                     .branch_protection | clean' "$POLICY") >/dev/null
    echo "protection applied"
fi

# ---------------------------------------------------------------- verify
# Read back rather than trust the write. Every field below is asserted against
# the live API, not against the file we just sent.
step "Verifying against the live API"

repo_json="$(gh api "repos/$REPO")"
prot_json="$(gh api "repos/$REPO/branches/$BRANCH/protection")"

check() { # description, actual, expected
    if [[ "$2" == "$3" ]]; then
        printf '  ok    %-42s %s\n' "$1" "$2"
    else
        printf '  WRONG %-42s got %s, want %s\n' "$1" "$2" "$3"
        FAILED=1
    fi
}

FAILED=0
check "allow_merge_commit"  "$(jq -r '.allow_merge_commit'      <<<"$repo_json")" "true"
check "allow_squash_merge"  "$(jq -r '.allow_squash_merge'      <<<"$repo_json")" "false"
check "allow_rebase_merge"  "$(jq -r '.allow_rebase_merge'      <<<"$repo_json")" "true"
check "delete_branch_on_merge" "$(jq -r '.delete_branch_on_merge' <<<"$repo_json")" "true"
check "approving_review_count"  "$(jq -r '.required_pull_request_reviews.required_approving_review_count' <<<"$prot_json")" "1"
check "dismiss_stale_reviews"   "$(jq -r '.required_pull_request_reviews.dismiss_stale_reviews'          <<<"$prot_json")" "true"
check "require_code_owner_reviews" "$(jq -r '.required_pull_request_reviews.require_code_owner_reviews' <<<"$prot_json")" "true"
check "status_check: make validate" "$(jq -r '.required_status_checks.contexts | join(",")' <<<"$prot_json")" "make validate"
check "status_check: strict"     "$(jq -r '.required_status_checks.strict' <<<"$prot_json")" "true"
check "enforce_admins"           "$(jq -r '.enforce_admins.enabled'       <<<"$prot_json")" "true"
check "conversation_resolution"  "$(jq -r '.required_conversation_resolution.enabled' <<<"$prot_json")" "true"
check "required_linear_history"  "$(jq -r '.required_linear_history.enabled' <<<"$prot_json")" "false"
check "allow_force_pushes"       "$(jq -r '.allow_force_pushes.enabled'   <<<"$prot_json")" "false"
check "allow_deletions"          "$(jq -r '.allow_deletions.enabled'      <<<"$prot_json")" "false"

# The code owner list, checked against the file that actually governs approvals.
EXPECTED_OWNERS="$(jq -r '.codeowners.accounts | sort | join(" ")' "$POLICY")"
ACTUAL_OWNERS="$(grep -oE '@[A-Za-z0-9_-]+' "$CODEOWNERS" | tr -d '@' | sort -u | tr '\n' ' ' | sed 's/ $//')"
check "CODEOWNERS accounts" "$ACTUAL_OWNERS" "$EXPECTED_OWNERS"

echo
if [[ "$FAILED" -ne 0 ]]; then
    fail "the live policy does not match config/branch_protection.json.
    Do not merge anything until this agrees. Inspect with:
      gh api repos/$REPO/branches/$BRANCH/protection"
fi
printf 'Policy verified against the live API. See %s for what each setting is for.\n' "$POLICY"
