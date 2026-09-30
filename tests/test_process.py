"""Issue 4: process-only semantics, and a tier that cannot carry money.

The load bearing test is ``test_a_process_finding_cannot_carry_money``. The module's
whole claim is that 541.8 grants a channel and a deadline and zero entitlement, and a
process finding with an amount field would be a payment demand under 541.8, which is
the failure the module exists to stop.
"""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from quayline.regulation import process as module
from quayline.regulation.process import (
    CITE_541_8_B,
    CITE_DISPUTE_TIMEFRAMES,
    ENTITLEMENT_SOURCES,
    MINIMUM_DISPUTE_DAYS,
    RESOLUTION_WINDOW_DAYS,
    DisputeWindow,
    ProcessFinding,
    ProcessTier,
    ResolutionAttempt,
    check_dispute_window,
    check_resolution_attempt,
)

ISSUED = date(2026, 7, 20)


# ---------------------------------------------------------------- the tier


def test_a_process_finding_cannot_carry_money() -> None:
    """Criterion one. There is no amount field, so there is nothing for an estimator
    to sum, and a payment demand under 541.8 cannot be constructed."""
    assert "amount" not in ProcessFinding.__dataclass_fields__
    assert "variance" not in ProcessFinding.__dataclass_fields__
    assert "recoverable" not in ProcessFinding.__dataclass_fields__


def test_a_substantive_tier_is_refused_at_construction() -> None:
    """Money lives in exactly one tier and it is not this type. A substantive
    finding travelling under a process cite would let a money claim borrow 541.8's
    authority."""
    with pytest.raises(ValueError, match="cannot be substantive"):
        ProcessFinding(tier=ProcessTier.SUBSTANTIVE, cite="x", summary="y")


def test_the_three_tiers_exist_and_money_is_in_one() -> None:
    assert {t.value for t in ProcessTier} == {"substantive", "process", "informational"}


def test_the_tier_is_immutable() -> None:
    finding = ProcessFinding(tier=ProcessTier.PROCESS, cite="x", summary="y")
    with pytest.raises(AttributeError):
        finding.tier = ProcessTier.SUBSTANTIVE  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# Fewer than thirty days raises an arguable 541.6(d)(3) finding.


def test_a_seven_day_window_raises_an_arguable_d3_finding() -> None:
    """The criterion's case. A carrier publishing a 7-day window violates 541.8(a),
    which is arguably a 541.6(d)(3) failure, which is therefore arguably a 541.5
    failure."""
    finding = check_dispute_window(DisputeWindow(published_days=7, invoice_issued=ISSUED))
    assert finding is not None
    assert finding.tier is ProcessTier.PROCESS
    assert finding.cite == CITE_DISPUTE_TIMEFRAMES


def test_the_finding_is_marked_arguable_not_certain() -> None:
    """The chain runs published window to (d)(3) to 541.5, and the second link has
    not been adjudicated. Presenting it as settled would be claiming a remedy on an
    unlitigated reading."""
    finding = check_dispute_window(DisputeWindow(published_days=7, invoice_issued=ISSUED))
    assert finding is not None
    assert "rguable" in finding.detail
    assert "arguably a 541.5 failure" in finding.detail
    assert finding.arguable is True, "a renderer must read the flag, not parse the text"


def test_a_settled_finding_is_not_marked_arguable() -> None:
    """The flag defaults False, so only the findings that need it carry it."""
    assert ProcessFinding(tier=ProcessTier.PROCESS, cite="x", summary="y").arguable is False


def test_a_thirty_day_window_is_not_a_finding() -> None:
    """A compliant window is the absence of a finding, not a finding in favour of
    the carrier, and it should not appear in a letter as though it were."""
    assert check_dispute_window(DisputeWindow(29, ISSUED)) is not None
    assert check_dispute_window(DisputeWindow(30, ISSUED)) is None
    assert check_dispute_window(DisputeWindow(45, ISSUED)) is None


def test_the_boundary_is_exactly_thirty() -> None:
    """541.8(a) is a floor of thirty days. An off-by-one here either accuses a
    compliant carrier or clears a violating one."""
    assert MINIMUM_DISPUTE_DAYS == 30
    assert check_dispute_window(DisputeWindow(29, ISSUED)) is not None
    assert check_dispute_window(DisputeWindow(30, ISSUED)) is None


def test_the_window_deadline_is_computed_from_issuance() -> None:
    assert DisputeWindow(7, ISSUED).deadline == date(2026, 7, 27)
    assert DisputeWindow(30, ISSUED).deadline == date(2026, 8, 19)


# ---------------------------------------------------------------- criterion 3
# The finding text names the real sources, never 541.8.


def test_the_entitlement_sources_exclude_541_8() -> None:
    assert "541.8" not in ENTITLEMENT_SOURCES
    for source in ("541.5", "541.7", "541.6 accuracy", "41102(c)"):
        assert source in ENTITLEMENT_SOURCES, source


def test_every_dispute_window_finding_names_the_sources() -> None:
    finding = check_dispute_window(DisputeWindow(7, ISSUED))
    assert finding is not None
    assert finding.entitlement == ENTITLEMENT_SOURCES
    assert "never from 541.8" in finding.detail
    assert finding.states_no_entitlement() is True


def test_attempt_to_resolve_is_not_resolve() -> None:
    """The sentence the respondent will try to blur. (b) requires an attempt within
    thirty days, and there is no requirement that the carrier pay anything."""
    flat = " ".join((module.__doc__ or "").split())
    assert "Attempt to resolve is not resolve" in flat
    assert "zero substantive entitlement" in flat


def test_silence_is_not_an_attempt() -> None:
    finding = check_resolution_attempt(
        ResolutionAttempt(requested_on=date(2026, 7, 21), answered_on=None, as_of=date(2026, 9, 1))
    )
    assert finding is not None
    assert finding.tier is ProcessTier.PROCESS
    assert finding.cite == CITE_541_8_B
    assert "silence past the ceiling is not an attempt" in finding.detail
    assert "never from 541.8" in finding.detail


def test_a_late_answer_without_agreement_is_a_finding() -> None:
    finding = check_resolution_attempt(
        ResolutionAttempt(
            requested_on=date(2026, 7, 21), answered_on=date(2026, 9, 1), as_of=date(2026, 9, 2)
        )
    )
    assert finding is not None
    assert "past the 541.8(b) window" in finding.detail
    assert "no mutual extension" in finding.detail


def test_a_late_answer_with_agreement_has_complied() -> None:
    """The bilateral escape hatch. A carrier that answered on day 40 with agreement
    has complied, so "answered late" without the agreement question is half a
    finding."""
    assert (
        check_resolution_attempt(
            ResolutionAttempt(
                requested_on=date(2026, 7, 21),
                answered_on=date(2026, 9, 1),
                as_of=date(2026, 9, 2),
                extended_to=date(2026, 9, 15),
            )
        )
        is None
    )


def test_an_answer_inside_the_window_is_not_a_finding() -> None:
    assert (
        check_resolution_attempt(
            ResolutionAttempt(
                requested_on=date(2026, 7, 21),
                answered_on=date(2026, 8, 10),
                as_of=date(2026, 8, 11),
            )
        )
        is None
    )


def test_the_window_is_thirty_days() -> None:
    assert RESOLUTION_WINDOW_DAYS == 30


# ---------------------------------------------------------------- what it is not


def test_the_module_says_where_the_money_comes_from_up_front() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "The money comes from 541.5, 541.7, 541.6 accuracy, or 41102(c)" in flat


def test_the_module_names_the_failure_it_prevents() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "treating 541.8 as a payment entitlement produces disputes that lose" in flat


def test_issue_4_is_the_provenance() -> None:
    assert "Issue 4" in (module.__doc__ or "")


def test_an_unanswered_request_inside_its_window_is_not_a_finding() -> None:
    """The second CodeRabbit finding on PR 144.

    A request made yesterday with no reply yet produced "silence is not an
    attempt". That accused a carrier still inside its 541.8(b) window. The model
    had no reference date to compare against, so silence was always overdue.
    """
    assert (
        check_resolution_attempt(
            ResolutionAttempt(
                requested_on=date(2026, 7, 21), answered_on=None, as_of=date(2026, 7, 22)
            )
        )
        is None
    )
    assert (
        check_resolution_attempt(
            ResolutionAttempt(
                requested_on=date(2026, 7, 21), answered_on=None, as_of=date(2026, 9, 1)
            )
        )
        is not None
    )


def test_an_answer_after_the_agreed_extension_is_a_finding() -> None:
    """The first CodeRabbit finding on PR 144.

    The old boolean cleared every carrier with an agreement, including one that
    broke the agreed deadline. Agreed to day 45, answered day 90: the extension
    moved the ceiling, it did not remove it.
    """
    finding = check_resolution_attempt(
        ResolutionAttempt(
            requested_on=date(2026, 7, 21),
            answered_on=date(2026, 10, 19),
            as_of=date(2026, 10, 20),
            extended_to=date(2026, 9, 4),
        )
    )
    assert finding is not None
    assert "mutually extended deadline" in finding.detail
    assert "2026-09-04" in finding.detail


def test_as_of_is_required_not_defaulted_to_today() -> None:
    """A check evaluated "now" gives a different answer every day it runs, and a
    finding that appears and disappears with the calendar is not a finding."""
    params = inspect.signature(ResolutionAttempt).parameters
    assert params["as_of"].default is inspect.Parameter.empty
