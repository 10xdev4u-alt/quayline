"""Issue 24: ONE's partial-shift rule, and the post-pull invoices it issues routinely."""

from __future__ import annotations

from datetime import date

import pytest

import quayline.tariffs.one as module
from quayline.tariffs.one import (
    EMODAL_COLLECTION_POLICY,
    PostPullFinding,
    flag_post_pull,
)

# ---------------------------------------------------------------- criterion 2
# A charge period beginning after the documented gate-out date is flagged.


def test_a_charge_starting_after_gate_out_is_flagged() -> None:
    finding = flag_post_pull(date(2026, 7, 10), date(2026, 7, 8))
    assert finding is not None
    assert finding.days_after_gate_out == 2
    assert isinstance(finding, PostPullFinding)


def test_a_charge_starting_on_gate_out_day_is_clean() -> None:
    """The pull day itself is still terminal time. Strictly greater, not greater
    or equal, because an inclusive comparison would flag every invoice pulled and
    charged the same day."""
    assert flag_post_pull(date(2026, 7, 8), date(2026, 7, 8)) is None


def test_a_charge_starting_before_gate_out_is_clean() -> None:
    assert flag_post_pull(date(2026, 7, 5), date(2026, 7, 8)) is None


def test_no_documented_gate_out_is_not_an_error() -> None:
    """An undocumented pull is the normal case, not an error, and raising would stop
    an audit that has other findings worth making."""
    assert flag_post_pull(date(2026, 7, 10), None) is None


def test_the_finding_is_immutable() -> None:
    finding = flag_post_pull(date(2026, 7, 10), date(2026, 7, 8))
    assert finding is not None
    with pytest.raises(AttributeError):
        finding.charge_start = date(2026, 7, 8)  # type: ignore[misc]


def test_flag_post_pull_is_deterministic() -> None:
    args = (date(2026, 7, 10), date(2026, 7, 8))
    assert flag_post_pull(*args) == flag_post_pull(*args)


# ---------------------------------------------------------------- criterion 3
# The finding text cites the eModal collection policy.


def test_the_finding_cites_the_emodal_policy() -> None:
    finding = flag_post_pull(date(2026, 7, 10), date(2026, 7, 8))
    assert finding is not None
    assert "eModal" in finding.sentence()
    assert "post-pull" in finding.sentence()


def test_the_policy_is_one_constant_not_a_paraphrase() -> None:
    """Quoted rather than paraphrased, because a paraphrase drifts and the drift is
    always toward softening the carrier's own words."""
    assert "only at eModal facilities" in EMODAL_COLLECTION_POLICY
    assert "routinely" in EMODAL_COLLECTION_POLICY


def test_the_finding_makes_the_no_incentive_argument() -> None:
    """A charge postdating the pull could not have hurried anything at the gate.
    That is an Evergreen element-three argument in miniature, and it is the reason
    this finding is worth more than its days."""
    finding = flag_post_pull(date(2026, 7, 10), date(2026, 7, 8))
    assert finding is not None
    assert "could not have incentivized anything at the gate" in finding.sentence()


def test_the_sentence_carries_both_dates() -> None:
    finding = flag_post_pull(date(2026, 7, 10), date(2026, 7, 8))
    assert finding is not None
    assert "2026-07-10" in finding.sentence()
    assert "2026-07-08" in finding.sentence()


def test_issue_24_is_the_provenance() -> None:
    assert "PostPullFinding" in module.__all__
