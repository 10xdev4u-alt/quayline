#!/usr/bin/env bash
# Report the live collaborator and protection state. Change nothing.
#
# Issue 92 recorded a merge that refused even though a valid approval existed,
# because the approving account's collaborator invitation had not been accepted. A
# review from an account with a pending invitation registers as CONTRIBUTOR rather
# than COLLABORATOR, and branch protection does not count it. The approval looks
# given and the merge still says no, and nothing in the error names the cause.
#
# This script exists so the next person does not rediscover that by being blocked.
# It reports. It never accepts an invitation and never changes protection, because a
# setup step that silently grants access is a different tool with a different risk.
#
# Usage:
#   scripts/verify_repository_state.sh
#   make repo-state
#
# Requires an authenticated gh with read access to the repository.
set -euo pipefail

REPO="${REPO:-10xdev4u-alt/quayline}"
OWNER="${REPO%/*}"
NAME="${REPO#*/}"
PANEL=("10xdev4u-alt" "the-ai-developer")

step() { printf '\n=== %s\n' "$1"; }
fail() { printf 'NOT OK: %s\n' "$1"; }
ok()   { printf 'ok:     %s\n' "$1"; }

command -v gh >/dev/null || { printf 'gh is required\n' >&2; exit 1; }

step "pending collaborator invitations for $REPO"
invitations=$(gh api "repos/$REPO/invitations" --jq '.[] | "\(.id)\t\(.invitee.login)\t\(.permissions)"' 2>/dev/null || echo "")
if [ -z "$invitations" ]; then
    printf 'none\n'
    printf '\nNo pending invitations. An approval from a panel account will count.\n'
else
    printf '%s\n' "$invitations"
    printf '\nA pending invitation means an approval from that account registers as\n'
    printf 'CONTRIBUTOR and does not satisfy branch protection. Accept it first:\n\n'
    printf '  gh api --method PATCH repos/%s/invitations/<id> -f %s\n\n' "$REPO" "''"
    printf 'Then re-run this script.\n'
fi

step "panel access on $REPO"
# An account with no access at all is the failure that blocks merges, so it is
# worth naming rather than inferring from a refusal later.
for account in "${PANEL[@]}"; do
    if gh api "repos/$REPO/collaborators/$account/permission" --jq '.permission' >/dev/null 2>&1; then
        level=$(gh api "repos/$REPO/collaborators/$account/permission" --jq '.permission')
        case "$level" in
            admin|write) ok "$account has $level" ;;
            *) fail "$account has $level, which is below what review administration needs" ;;
        esac
    else
        fail "$account has no readable access to $REPO"
    fi
done

step "merge methods on $REPO"
settings=$(gh api "repos/$REPO" --jq '{
    merge: .allow_merge_commit,
    squash: .allow_squash_merge,
    rebase: .allow_rebase_merge,
    delete: .delete_branch_on_merge
}')
printf '%s\n' "$settings"
if [ "$(printf '%s' "$settings" | jq -r .squash)" = "false" ]; then
    ok "squash is disabled, as AGENTS.md section eight requires"
else
    fail "squash is ENABLED. A squash merge loses the co-author trailer's history"
fi

step "branch protection on $NAME"
protection=$(gh api "repos/$REPO/branches/main/protection" 2>/dev/null || echo "")
if [ -z "$protection" ]; then
    fail "no protection object readable for main."
    printf 'A 404 here with a live squash refusal is the two-surface trap in\n'
    printf 'docs/decisions/0001-protection-is-two-api-surfaces.md, not an absence of policy.\n'
    printf 'Apply with: scripts/configure_branch_protection.sh\n'
else
    printf '%s\n' "$protection" | jq '{
        required_reviews: .required_pull_request_reviews,
        enforce_admins: .enforce_admins.enabled,
        conversations: .required_conversation_resolution.enabled,
        force_pushes: .allow_force_pushes.enabled
    }'
    codeowners=$(printf '%s' "$protection" | jq -r '.required_pull_request_reviews.require_code_owner_reviews')
    if [ "$codeowners" = "true" ]; then
        ok "code owner reviews are required, so only CODEOWNERS accounts count"
    else
        fail "code owner reviews are NOT required, so any approval satisfies the gate"
    fi
fi

printf '\nNothing was changed. To apply the declared policy:\n'
printf '  scripts/configure_branch_protection.sh\n'
