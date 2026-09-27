"""The declared branch policy, asserted against AGENTS.md.

``config/branch_protection.json`` is the thing a human edits.
``scripts/configure_branch_protection.sh`` applies it. These tests read the
former and fail if it stops saying what the manual requires, because a policy
file that quietly drifts from the contract is worse than no policy file, since
it still looks authoritative.

Two findings from building this, both worth protecting against regression.

Squash is not a branch protection setting. It lives in repository settings, and
the classic branch protection API has no field for it. A script that only
writes protection leaves squash merging available, and the acceptance criterion
that says "block squash by policy" reads as though protection covers it.

``required_linear_history: true`` is not stricter. It forces squash or rebase
merging, which is exactly what AGENTS.md prohibits, so the correct value is
false and the field name actively misleads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "branch_protection.json"
CODEOWNERS_PATH = ROOT / ".github" / "CODEOWNERS"
SCRIPT_PATH = ROOT / "scripts" / "configure_branch_protection.sh"

# AGENTS.md section one names exactly these two.
NAMED_ACCOUNTS = ("10xdev4u-alt", "the-ai-developer")


def _policy() -> dict[str, Any]:
    assert POLICY_PATH.exists(), f"{POLICY_PATH} is missing"
    parsed: dict[str, Any] = json.loads(POLICY_PATH.read_text())
    return parsed


def _block(name: str) -> dict[str, Any]:
    value: dict[str, Any] = _policy()[name]
    return value


def _protection() -> dict[str, Any]:
    return _block("branch_protection")


def _repository() -> dict[str, Any]:
    return _block("repository")


# ---------------------------------------------------------------- criterion 4
# Allow merge commits and rebase merging, block squash by policy. The criterion
# groups three settings under one heading, and they live on two API surfaces.


def test_merge_commits_allowed() -> None:
    assert _repository()["allow_merge_commit"] is True


def test_squash_blocked() -> None:
    assert _repository()["allow_squash_merge"] is False, (
        "AGENTS.md section eight prohibits squash merges with no exceptions"
    )


def test_rebase_merging_allowed() -> None:
    assert _repository()["allow_rebase_merge"] is True


def test_linear_history_is_false_because_true_would_prohibit_merge_commits() -> None:
    """The field name is misleading and the correct value looks wrong.

    ``required_linear_history`` true forces squash or rebase merging, which is
    the exact opposite of the merge commit policy. Setting it true to look
    strict would break the rule it appears to support.
    """
    assert _protection()["required_linear_history"] is False


def test_squash_is_configured_on_the_repository_surface_not_protection() -> None:
    """The whole reason this test exists.

    A reviewer who assumes protection covers merge methods would look for a
    squash key under branch_protection, not find it, and conclude squash is
    ungoverned. It is governed, on the other surface.
    """
    protection_keys = {k for k in _protection() if not k.startswith("$")}
    assert not any("squash" in k for k in protection_keys), protection_keys
    assert "allow_squash_merge" in _repository()

    body = SCRIPT_PATH.read_text()
    assert "allow_squash_merge" in body
    assert "PATCH" in body, "the script must patch repository settings, not only protection"


# ---------------------------------------------------------------- criterion 1
# Require at least one approving review before merge.


def test_requires_one_approving_review() -> None:
    reviews = _protection()["required_pull_request_reviews"]
    assert reviews["required_approving_review_count"] == 1


def test_count_is_one_not_two() -> None:
    """Two would deadlock the process.

    The author cannot approve their own pull request, so on a two person
    repository requiring two approvals means no change can ever merge.
    """
    assert _protection()["required_pull_request_reviews"]["required_approving_review_count"] < 2


def test_approval_restricted_to_the_two_named_accounts() -> None:
    """The branch protection API has no approver allowlist.

    ``require_code_owner_reviews`` plus a CODEOWNERS file is the only way to say
    that an approval from some other account does not count.
    """
    assert _protection()["required_pull_request_reviews"]["require_code_owner_reviews"] is True
    assert _block("codeowners")["accounts"] == list(NAMED_ACCOUNTS)


def test_codeowners_file_matches_the_policy() -> None:
    """The JSON and the file must not disagree about who can approve.

    CODEOWNERS is what GitHub actually reads. The JSON is a mirror, and a mirror
    that drifts is worse than no mirror.
    """
    assert CODEOWNERS_PATH.exists()
    owners: set[str] = set()
    for raw in CODEOWNERS_PATH.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line.startswith("*"):
            continue
        owners.update(tok.lstrip("@") for tok in line[1:].split())
    assert owners == set(NAMED_ACCOUNTS), owners


def test_stale_reviews_are_dismissed() -> None:
    """Otherwise an approval from before the last push counts forever."""
    assert _protection()["required_pull_request_reviews"]["dismiss_stale_reviews"] is True


# ---------------------------------------------------------------- criterion 2
# Require the gate to pass.


def test_requires_the_gate_status_check() -> None:
    checks = _protection()["required_status_checks"]
    assert checks["contexts"] == ["make validate"]


def test_status_check_name_matches_the_workflow_job() -> None:
    """The context is the job name, not the workflow name.

    A mismatch here is not a warning, it is a pull request that can never merge.
    The check reports under one name and the branch rule requires another, so
    the requirement is never satisfied and the run never blocks.
    """
    workflow = (ROOT / ".github" / "workflows" / "gate.yml").read_text()
    assert "name: gate" in workflow, "the workflow is still named gate"
    assert "name: make validate" in workflow, (
        "the job must be named 'make validate' because that is the string the "
        "branch protection rule requires as a status check context"
    )
    assert _protection()["required_status_checks"]["contexts"] == ["make validate"]


def test_branches_must_be_up_to_date() -> None:
    """strict, which requires the branch to be current with its base.

    Without it a green check can be reporting on a commit that is no longer on
    the branch, which is the same class of defect as the hook that enforced
    nothing while looking configured.
    """
    assert _protection()["required_status_checks"]["strict"] is True


def test_admins_are_subject_to_the_rules() -> None:
    """Otherwise the whole policy is advisory for the account that can bypass it."""
    assert _protection()["enforce_admins"] is True


# ---------------------------------------------------------------- criterion 3
# Require branches to be up to date. Same setting as above, asserted from the
# other side so the two cannot be quietly separated.


def test_up_to_date_requirement_is_the_strict_flag() -> None:
    checks = _protection()["required_status_checks"]
    assert checks["strict"] is True
    assert "make validate" in checks["contexts"]


def test_force_pushes_blocked() -> None:
    assert _protection()["allow_force_pushes"] is False


def test_branch_deletion_blocked() -> None:
    assert _protection()["allow_deletions"] is False


def test_conversation_resolution_required() -> None:
    """AGENTS.md section ten keeps the review conversation as part of the record.

    An unresolved comment is an unfinished review, and merging over it discards
    the only trace that anyone disagreed.
    """
    assert _protection()["required_conversation_resolution"] is True


# ---------------------------------------------------------------- criterion 5
# The setting is recorded in a setup script so it is reproducible.


def test_setup_script_exists_and_is_executable() -> None:
    assert SCRIPT_PATH.exists(), "the branch policy must be reproducible from a script"
    assert SCRIPT_PATH.stat().st_mode & 0o111, "the script is not executable"


def test_script_fails_closed_before_it_changes_anything() -> None:
    """Issue 92 was a collaborator discovered as a 403 halfway through.

    The capability check has to come before the first write, and it has to
    mention the switch command, because "403 Forbidden" on its own tells an
    operator nothing about which step failed or what to do.
    """
    body = SCRIPT_PATH.read_text()
    admin_check = body.index("permissions.admin")
    first_write = body.index("-X PATCH")
    assert admin_check < first_write, "the admin check must precede the first write"
    assert "gh auth switch" in body
    assert "set -euo pipefail" in body


def test_script_verifies_against_the_api_rather_than_trusting_its_write() -> None:
    """A script that reports success after a write it did not check is a
    script that reports success on a partial failure."""
    body = SCRIPT_PATH.read_text()
    assert body.count("gh api") >= 4
    assert "Verifying against the live API" in body
    for field in (
        "allow_squash_merge",
        "required_approving_review_count",
        "make validate",
        "required_linear_history",
        "allow_force_pushes",
    ):
        assert field in body, f"the script never verifies {field}"


def test_script_can_report_without_changing_anything() -> None:
    assert "--check" in SCRIPT_PATH.read_text()


def test_script_supports_a_dry_run_and_a_different_repository() -> None:
    body = SCRIPT_PATH.read_text()
    assert "QUAYLINE_REPO" in body
    assert "QUAYLINE_BRANCH" in body


# ---------------------------------------------------------------- the policy is honest


def test_policy_documents_itself_at_both_surfaces() -> None:
    """The two surfaces are the trap, so the file must say so where an operator
    will actually read it."""
    assert "$schema_note" in _policy()
    assert "two different GitHub API surfaces" in _policy()["$schema_note"]


def test_every_policy_block_explains_the_surface_it_targets() -> None:
    """Each block says which API surface it is written to.

    The two surfaces are the trap in this change, so an operator reading the file
    has to be told which object goes where without reading the script.
    """
    for name, block in (
        ("repository", _repository()),
        ("branch_protection", _protection()),
        ("codeowners", _block("codeowners")),
    ):
        assert "$comment" in block, f"the {name} block has no $comment"

    assert "PATCH" in _repository()["$comment"]
    assert "PUT" in _protection()["$comment"]


def test_counterintuitive_settings_carry_a_comment_of_their_own() -> None:
    """Five values in this file are correct in a way that reads as wrong.

    ``required_linear_history: true`` looks stricter and prohibits merge
    commits. An approval count of 2 looks stricter and deadlocks a two account
    repository. ``strict: true`` is the only thing standing between a green check
    and a commit that is no longer on the branch.

    If someone tidies these explanations away the policy keeps working right up
    until it does not, and it fails plausibly, so the explanations are treated as
    load bearing and tested like the values.
    """
    text = POLICY_PATH.read_text()
    for key in (
        "required_linear_history",
        "required_approving_review_count",
        "allow_squash_merge",
        "strict",
        "restrictions",
        "require_code_owner_reviews",
    ):
        assert f'"${key}"' in text, f"{key} has no comment explaining its value"


@pytest.mark.parametrize("account", NAMED_ACCOUNTS)
def test_named_accounts_are_the_two_from_the_manual(account: str) -> None:
    manual = (ROOT / "AGENTS.md").read_text()
    assert account in manual
