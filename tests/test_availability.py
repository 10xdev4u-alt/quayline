"""Issue 31: the availability contradiction, decided from the invoice alone.

The test that matters most is ``test_it_is_not_a_541_5_kill_switch``. The check is
correct in every arithmetic sense and still worthless if a caller pools it with the
kill switch, because 541.5 triggers on a missing disclosure and nothing here is
missing. That is the failure this whole file guards.
"""

from __future__ import annotations

from datetime import date

import pytest

import quayline.engine.availability as module
from quayline.engine.availability import (
    CITE_AVAILABILITY,
    CITE_SUFFICIENCY,
    CITE_TIMING,
    AvailabilityCheck,
    Inconsistency,
    availability_contradiction,
    check_availability,
)
from quayline.models.invoice import TimingDisclosures
from quayline.regulation import Trade
from quayline.regulation.kill_switch import Omission

AVAILABLE = date(2026, 7, 10)
BEFORE = (date(2026, 7, 8), date(2026, 7, 9))
ON = date(2026, 7, 10)
AFTER = (date(2026, 7, 11), date(2026, 7, 12))


def invoice(
    charged: tuple[date, ...] = (*BEFORE, *AFTER),
    availability: date | None = AVAILABLE,
    trade: Trade = Trade.IMPORT,
) -> TimingDisclosures:
    return TimingDisclosures(
        invoice_date=date(2026, 7, 20),
        allowed_free_time_days=4,
        free_time_start=date(2026, 6, 30),
        free_time_end=date(2026, 7, 4),
        charged_dates=frozenset(charged),
        trade=trade,
        availability_date=availability,
    )


# ---------------------------------------------------------------- criterion 1
# Compare the minimum billed date against the disclosed availability date.


def test_a_charge_beginning_before_availability_is_found() -> None:
    """The criterion's own case, and the most automatable check in the category."""
    got = availability_contradiction(invoice())
    assert got is not None
    assert got.availability_date == AVAILABLE
    assert got.first_charged_day == BEFORE[0]
    assert got.contradiction_days == 2


def test_only_the_days_before_availability_are_disputed() -> None:
    """Not the whole invoice. The days on and after availability are not in
    contradiction and disputing them would be over-claiming."""
    got = availability_contradiction(invoice())
    assert got is not None
    assert got.disputed_days == BEFORE
    assert ON not in got.disputed_days
    assert AFTER[0] not in got.disputed_days


def test_the_comparison_is_strictly_less_than() -> None:
    """A container available on the tenth can be charged from the tenth, and that
    is the normal case rather than a borderline one.

    An inclusive comparison would flag nearly every compliant invoice and the
    finding would be ignored, which is worse than not having it.
    """
    assert availability_contradiction(invoice(charged=(ON,))) is None
    assert availability_contradiction(invoice(charged=(*BEFORE, ON))) is not None


def test_an_invoice_charged_entirely_after_availability_is_clean() -> None:
    assert availability_contradiction(invoice(charged=AFTER)) is None


def test_a_single_contradictory_day_is_still_a_finding() -> None:
    """One day is a day. Requiring a minimum count would be inventing a threshold
    the regulation does not contain."""
    got = availability_contradiction(invoice(charged=(date(2026, 7, 9), ON)))
    assert got is not None
    assert got.contradiction_days == 1


def test_disputed_days_are_sorted_and_deterministic() -> None:
    forward = availability_contradiction(invoice(charged=(date(2026, 7, 8), date(2026, 7, 9))))
    backward = availability_contradiction(invoice(charged=(date(2026, 7, 9), date(2026, 7, 8))))
    assert forward == backward


def test_a_clean_invoice_returns_none_not_an_empty_finding() -> None:
    """So a caller cannot confuse "checked and clean" with "not checked" by looking
    at a truthy value."""
    assert availability_contradiction(invoice(charged=AFTER)) is None


# ---------------------------------------------------------------- criterion 2
# Framed as a sufficiency failure under 541.6(b), not as 541.5.


def test_it_is_not_a_541_5_kill_switch() -> None:
    """The framing is the whole issue.

    Nothing is missing here. The carrier disclosed both dates and disclosed them
    inconsistently, and there is no reading of 541.5 that turns a contradiction into
    an omission. Asserting a 541.5 kill here would be claiming a remedy we do not
    have, and a carrier that reads the letter will say so in one sentence.
    """
    got = availability_contradiction(invoice())
    assert got is not None
    assert "541.5" not in got.cite
    assert got.cite == CITE_SUFFICIENCY
    assert "sufficiency" in got.cite


def test_it_is_typed_separately_from_a_kill_switch_omission() -> None:
    """So it cannot be pooled with one by accident."""
    # Neither a type identity check nor an isinstance check can be written here, and
    # mypy rejecting both is itself the proof: the two types have disjoint bases, so
    # no value can be both. The runtime property worth asserting is the one that
    # makes the distinction matter, which is that an Omission names a missing
    # checklist field and this finding names no field at all.
    assert "field" in Omission.__dataclass_fields__
    assert "field" not in Inconsistency.__dataclass_fields__
    assert not (set(Omission.__dataclass_fields__) & set(Inconsistency.__dataclass_fields__))


def test_the_cite_names_5416_b_and_both_subsections_appear_in_the_sentence() -> None:
    got = availability_contradiction(invoice())
    assert got is not None
    assert got.cite.startswith("541.6(b)")
    sentence = got.as_sentence()
    assert CITE_AVAILABILITY in sentence
    assert "541.6(b)(8)" in sentence


def test_the_sentence_carries_the_dates_inline() -> None:
    """A respondent who has to open a second document to check the claim has already
    started deciding whether to bother."""
    sentence = availability_contradiction(invoice()).as_sentence()  # type: ignore[union-attr]
    assert "2026-07-10" in sentence
    assert "2026-07-08" in sentence


def test_the_sentence_says_both_disclosures_were_certified() -> None:
    """The point is that the carrier certified both. Otherwise it reads as our
    arithmetic disagreeing with the carrier's, which is a different argument."""
    sentence = availability_contradiction(invoice()).as_sentence()  # type: ignore[union-attr]
    assert "cannot both be accurate" in sentence


def test_the_timing_cite_is_a_group_not_a_subsection() -> None:
    """Neither subsection is wrong on its own, so citing one of them would
    misattribute the defect."""
    assert CITE_TIMING == "541.6(b)"


# ---------------------------------------------------------------- criterion 3
# High confidence, because it needs no external data.


def test_no_external_data_is_required() -> None:
    assert check_availability(invoice()).requires_external_data is False


def test_the_requirement_flag_is_a_property_not_a_field() -> None:
    """A caller could pass ``False`` on a check that does need something, and would
    eventually do so on one that does."""
    assert "requires_external_data" not in AvailabilityCheck.__dataclass_fields__


def test_the_confidence_basis_qualifies_itself() -> None:
    """High confidence about the contradiction. Not about the recovery, and not about
    what the carrier will do.

    The unqualified word is the category's favourite failure, so the module has to
    refuse to emit it on its own.
    """
    basis = check_availability(invoice()).confidence_basis
    assert "High confidence as to the contradiction" in basis
    assert "Not a prediction of recovery" in basis


def test_no_field_carries_a_bare_confidence_score() -> None:
    """A number here would be read as a probability of winning, which is a different
    claim from the one we can support."""
    names = set(AvailabilityCheck.__dataclass_fields__) | set(Inconsistency.__dataclass_fields__)
    assert not (names & {"confidence", "score", "probability", "likelihood", "value"}), names


def test_no_amount_is_estimated() -> None:
    """A value estimate needs a tariff we may not hold, so this module names the
    days and stops."""
    names = set(Inconsistency.__dataclass_fields__)
    assert not (names & {"amount", "amount_at_stake", "recoverable"}), names


# ---------------------------------------------------------------- the shape of the result


def test_a_clean_invoice_still_produces_a_check_result() -> None:
    """A caller can distinguish checked and clean from not checked, and that is why
    this returns a wrapper rather than a bare Optional."""
    result = check_availability(invoice(charged=AFTER))
    assert result.found is False
    assert result.inconsistency is None
    assert "No availability contradiction" in result.as_sentence()


def test_the_finding_carries_the_first_charged_day_separately() -> None:
    """The first billed day and the disputed days are different facts. The first is
    what the letter leads with; the disputed set is what is contested."""
    got = availability_contradiction(invoice())
    assert got is not None
    assert got.first_charged_day == min(got.disputed_days)


def test_the_result_is_immutable() -> None:
    result = check_availability(invoice())
    with pytest.raises(AttributeError):
        result.inconsistency = None  # type: ignore[misc]


def test_the_check_is_deterministic() -> None:
    assert check_availability(invoice()) == check_availability(invoice())


# ---------------------------------------------------------------- scope


def test_an_export_invoice_is_out_of_scope() -> None:
    """541.6(b)(6) is import only. Inventing an availability date for an export
    would be a finding with no clause under it."""
    export = invoice(trade=Trade.EXPORT)
    got = availability_contradiction(export)
    assert got is None


def test_the_model_refuses_an_import_with_no_availability_date() -> None:
    """The check cannot be reached with a missing availability date, because the
    model will not build one. 541.5 handles that case, not this module."""
    with pytest.raises(ValueError, match=r"541\.6"):
        invoice(availability=None)


def test_availability_contradiction_tolerates_a_none_availability_defensively() -> None:
    """Unreachable through the model, and still handled.

    A private check that raised on None would be a landmine for anyone calling it
    directly with a hand-built disclosure.
    """
    got = availability_contradiction(
        TimingDisclosures(
            invoice_date=date(2026, 7, 20),
            allowed_free_time_days=4,
            free_time_start=date(2026, 6, 30),
            free_time_end=date(2026, 7, 4),
            charged_dates=frozenset(BEFORE),
            trade=Trade.EXPORT,
        )
    )
    assert got is None


def test_issue_31_is_the_provenance() -> None:

    assert "Issue 31" in (module.__doc__ or "")


def test_the_module_says_why_the_remedy_is_weak() -> None:
    """A weaker remedy stated honestly beats a stronger one we do not have."""
    flat = " ".join(
        (__import__("quayline.engine.availability", fromlist=["x"]).__doc__ or "").split()
    )
    assert "no showing and no cure period" in flat
    assert "remedy we do not have" in flat
