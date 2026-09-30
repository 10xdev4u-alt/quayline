"""Issue 92: the review panel is closed, and a pull request cannot relax it.

These are assertions about a document, which is normally the wrong thing to test.
It is the right thing here for one reason: the rules in AGENTS.md enforce
themselves only as long as they are present, and nothing in the gate, the lint, or
the type checker notices when a paragraph is deleted. A deleted review rule and a
review rule that was never written look identical to the next person.

So each acceptance criterion is asserted as a presence. The assertions are written
against the words the rule uses, not against a paraphrase, so a rewrite that drops
the substance fails.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Whitespace is collapsed before any search. AGENTS.md is prose, prose is wrapped,
# and a wrapped line turns "no third seat" into "no third\n   seat". Asserting on
# the raw bytes of a wrapped paragraph means a reformat that changes nothing about
# the rule still fails the test, which trains people to ignore it.
AGENTS = " ".join((ROOT / "AGENTS.md").read_text().split())
PANEL = ("10xdev4u-alt", "the-ai-developer")


# ---------------------------------------------------------------- criterion 1
# The panel is a closed list, and there is a rule for a reviewer outside it.


def test_the_panel_is_named_as_a_closed_list() -> None:
    assert "The panel is exactly" in AGENTS
    for account in PANEL:
        assert account in AGENTS
    assert "no third seat" in AGENTS


def test_a_reviewer_outside_the_panel_has_a_procedure() -> None:
    assert "Judge the finding, not the reviewer" in AGENTS
    assert "reviewer outside the panel" in AGENTS.lower()


def test_the_allowlist_is_a_file_not_a_prose_claim() -> None:
    """CODEOWNERS is the binding mechanism, so its existence is the fact that
    matters. The branch protection API has no allowlist field."""
    assert (ROOT / ".github" / "CODEOWNERS").exists()
    owners = (ROOT / ".github" / "CODEOWNERS").read_text()
    for account in PANEL:
        assert account in owners


# ---------------------------------------------------------------- criterion 2
# The rule is about finding validity, not reviewer identity.


def test_validity_is_the_criterion_in_both_directions() -> None:
    """Both halves, because a rule that only says what to do with true findings
    leaves the false ones undecided."""
    assert "not dismissed for coming from an unlisted account" in AGENTS
    assert "not taken for coming from a listed account" in AGENTS


def test_the_precedent_is_recorded() -> None:
    """CodeRabbit's findings were both valid and both were taken. Without that the
    rule reads as theory."""
    assert "CodeRabbit" in AGENTS
    assert "Both of its findings were correct" in AGENTS


# ---------------------------------------------------------------- criterion 3
# When dismissal is right, and it needs a recorded reason.


def test_dismissal_is_not_for_unblocking_a_merge() -> None:
    assert "not the right call to unblock a merge" in AGENTS


def test_dismissal_requires_a_written_reason() -> None:
    assert "write the reason into the dismissal" in AGENTS
    assert "considered dismissal from an oversight" in AGENTS


def test_the_grounds_for_dismissal_are_named() -> None:
    """Three grounds, so somebody does not have to invent the fourth under
    pressure."""
    for ground in ("factually wrong", "not applicable", "conflicts with"):
        assert ground in AGENTS, ground


# ---------------------------------------------------------------- criterion 4
# Approval does not count until collaborator access is active, and the call is named.


def test_the_contributor_versus_collaborator_trap_is_documented() -> None:
    assert "CONTRIBUTOR" in AGENTS
    assert "COLLABORATOR" in AGENTS
    assert "does not count" in AGENTS


def test_the_accept_call_is_named_with_an_empty_body() -> None:
    """The empty body is the part people get wrong, and it is the whole call."""
    assert "gh api --method PATCH" in AGENTS
    assert "invitations/<id> -f ''" in AGENTS
    match = re.search(r"gh api --method PATCH[^\n]*-f ''", AGENTS)
    assert match, "the accept call must be copy pasteable, empty body included"


def test_a_reported_command_exists_for_the_state() -> None:
    """A documented command, not a documented intention."""
    script = ROOT / "scripts" / "verify_repository_state.sh"
    assert script.exists()
    assert script.stat().st_mode & stat.S_IXUSR, "the state script must be executable"


def test_the_state_script_reports_and_does_not_change() -> None:
    """A setup step that silently grants access is a different tool with a
    different risk, so this one must not contain a write."""
    body = (ROOT / "scripts" / "verify_repository_state.sh").read_text()
    assert "--method PATCH" in body, "the accept call is printed, not run"
    for line in body.splitlines():
        if line.strip().startswith("gh api --method PATCH"):
            pytest.fail(f"the script executes a PATCH: {line.strip()}")


def test_make_repo_state_is_wired() -> None:
    makefile = (ROOT / "Makefile").read_text()
    assert "repo-state:" in makefile
    assert "verify_repository_state.sh" in makefile


# ---------------------------------------------------------------- criterion 5
# A pull request does not edit this file to relax its own rules.


def test_the_no_self_relaxation_rule_is_stated() -> None:
    assert "does not edit this file to relax its own rules" in AGENTS
    assert "in force when the pull request was opened" in AGENTS


def test_the_rule_names_what_would_be_a_relaxation() -> None:
    """Otherwise it is a principle rather than a check."""
    for subject in ("review requirement", "commit rules", "the gate", "merge policy"):
        assert subject in AGENTS, subject


def test_reviewers_are_asked_to_check_this_specific_diff() -> None:
    """The enforcement mechanism, and the reason the rule above has teeth."""
    assert "diff on every pull request" in AGENTS, "reviewers must be asked to check this diff"
    assert "section one, two or eight" in AGENTS


# ---------------------------------------------------------------- the trap that started this


def test_the_original_merge_block_is_described() -> None:
    """Three rounds, and the third is the one that cost the merge."""
    assert "changes-requested" in AGENTS
    assert "pending invitation" in AGENTS


def test_issue_92_is_the_provenance() -> None:
    assert "Issue 92" in AGENTS or "issue 92" in AGENTS
