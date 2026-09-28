"""The four acceptance criteria on issue 29, one test block each.

This is the first module that takes a real document and produces a number, so the
tests here are mostly about whether the number is defensible rather than whether the
code runs. Every case is built from the four 541.6(b) disclosures plus a gate
calendar, which is the entire data dependency of the product's highest yield check.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from quayline.engine.daycount import CITE_ACCURACY, Direction, Discrepancy, recompute
from quayline.models.invoice import (
    CITE_ALLOWANCE,
    CITE_AVAILABILITY,
    CITE_CHARGED_DATES,
    REQUIRED_FOR_RECOMPUTATION,
    TimingDisclosures,
)
from quayline.regulation import Trade


def jul(d: int) -> date:
    """July 2026 by day of month. A function rather than a lambda so it is typed and
    the tests do not carry a noqa for a rule they did not choose."""
    return date(2026, 7, d)


START = date(2026, 6, 30)
# Hapag, four working days from Tue 30 June 2026. Independence Day is observed Friday
# 3 July and is forgiven, so it extends rather than consuming, and the window walks
# 1, 2, skip 3, skip 4 Sat, skip 5 Sun, 6, 7. Last free day is Tuesday 7 July.
RECOMPUTED_END = jul(7)


def invoice(**overrides: object) -> TimingDisclosures:
    base: dict[str, object] = {
        "invoice_date": date(2026, 7, 20),
        "allowed_free_time_days": 4,
        "free_time_start": START,
        "free_time_end": jul(6),
        "charged_dates": frozenset(jul(d) for d in (6, 7, 8, 9, 10)),
        "trade": Trade.IMPORT,
        "availability_date": START,
    }
    base.update(overrides)
    return TimingDisclosures(**base)  # type: ignore[arg-type]


def clean_invoice(**overrides: object) -> TimingDisclosures:
    base: dict[str, object] = {
        "invoice_date": date(2026, 7, 20),
        "allowed_free_time_days": 4,
        "free_time_start": START,
        "free_time_end": RECOMPUTED_END,
        "charged_dates": frozenset(jul(d) for d in (8, 9, 10)),
        "trade": Trade.IMPORT,
        "availability_date": START,
    }
    base.update(overrides)
    return TimingDisclosures(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- criterion 1
# The check recomputes the chargeable window from declared free-time start and
# allowance.


def test_the_end_is_recomputed_from_start_and_allowance_not_taken_from_the_invoice() -> None:
    """The invoice states an end of 6 July. Its own start and allowance say 7 July.

    A checker that used the stated end would find nothing. Using the declared start
    and declared allowance is what makes this a recomputation rather than a
    restatement of what the carrier said.
    """
    result = recompute(invoice(free_time_end=RECOMPUTED_END), "Hapag-Lloyd", terminal="USLAXB")
    assert result.declared_free_time_end == RECOMPUTED_END
    assert result.recomputed_free_time_end == RECOMPUTED_END
    assert result.free_time_end_disagrees is False

    misstated = recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB")
    assert misstated.declared_free_time_end == jul(6)
    assert misstated.free_time_end_disagrees is True


def test_the_expected_window_is_every_chargeable_day_after_the_recomputed_end() -> None:
    result = recompute(clean_invoice(), "Hapag-Lloyd", terminal="USLAXB")
    assert result.expected_dates == (jul(8), jul(9), jul(10))
    assert result.billed_dates == (jul(8), jul(9), jul(10))
    assert result.day_set_reconciles is True
    assert result.clean is True


def test_charging_days_inside_the_free_time_allowance_is_an_overbill() -> None:
    result = recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB")
    over = result.overbilled
    assert over is not None
    assert over.direction is Direction.OVERBILLED
    assert set(over.dates) == {jul(6), jul(7)}
    assert CITE_ALLOWANCE in over.detail


def test_nothing_chargeable_at_all_yields_an_empty_expected_window() -> None:
    """A carrier that charges only inside the allowance bills nothing legitimate."""
    result = recompute(
        invoice(charged_dates=frozenset({jul(1), jul(2)})), "Hapag-Lloyd", terminal="USLAXB"
    )
    assert result.expected_dates == ()
    assert set(result.overbilled.dates) == {jul(1), jul(2)}  # type: ignore[union-attr]


# ---------------------------------------------------------------- criterion 2
# It compares against the billed day set and reports both directions.


def test_both_directions_can_be_reported_on_one_invoice() -> None:
    """Charges two days early, misses one day it should have charged.

    Over and under on the same invoice is the case that makes the symmetry
    worth having, and it is not hypothetical: a carrier whose start date is wrong
    in one direction produces exactly this.
    """
    result = recompute(
        invoice(charged_dates=frozenset({jul(6), jul(7), jul(9), jul(10)})),
        "Hapag-Lloyd",
        terminal="USLAXB",
    )
    assert result.overbilled is not None
    assert set(result.overbilled.dates) == {jul(6), jul(7)}
    assert result.underbilled is not None
    assert set(result.underbilled.dates) == {jul(8)}
    assert result.underbilled.direction is Direction.UNDERBILLED
    assert result.day_set_reconciles is False


def test_the_underbilled_set_is_reported_even_though_it_favours_the_customer() -> None:
    """The symmetry stated as a test.

    A checker that reported only the favourable direction would be a checker the
    customer could replace with their own spreadsheet. The underbilled set is also
    evidence that a carrier is not billing consistently.
    """
    # Week of 13 to 17 July, so nothing here is a weekend and the only finding is
    # the missing day. An earlier version of this test used 8 to 12 July and asserted
    # no overbill, which was wrong: the 10th and 11th are a weekend and billing them
    # under a Monday to Friday basis is a genuine overbill. The assertion would have
    # failed for the right reason and been fixed for the wrong one.
    result = recompute(
        invoice(
            free_time_end=RECOMPUTED_END,
            charged_dates=frozenset({jul(13), jul(14), jul(16), jul(17)}),
        ),
        "Hapag-Lloyd",
        terminal="USLAXB",
    )
    assert result.overbilled is None
    under = result.underbilled
    assert under is not None, "a gap in the billed run must be reported"
    assert jul(15) in under.dates
    assert "did not charge" in under.detail


def test_a_clean_invoice_produces_no_discrepancies() -> None:
    result = recompute(clean_invoice(), "Hapag-Lloyd", terminal="USLAXB")
    assert result.discrepancies == ()
    assert result.clean is True
    assert "billed days reconcile" in result.as_letter()


def test_the_stated_end_mismatch_is_reported_separately_from_the_day_set() -> None:
    """A carrier can get the arithmetic right and still misstate the end.

    ``day_set_reconciles`` and ``clean`` are separate properties, and the
    distinction is the point: reconciling days while misstating the end means the
    start should be questioned too.
    """
    result = recompute(
        invoice(free_time_end=jul(6), charged_dates=frozenset({jul(8), jul(9), jul(10)})),
        "Hapag-Lloyd",
        terminal="USLAXB",
    )
    assert result.day_set_reconciles is True
    assert result.free_time_end_disagrees is True
    assert result.clean is False
    stated = next(d for d in result.discrepancies if d.direction is Direction.STATED_VS_RECOMPUTED)
    assert CITE_ACCURACY in stated.citation
    assert "do not support" in stated.detail


# ---------------------------------------------------------------- criterion 3
# Overbilled days are listed by date.


def test_overbilled_days_are_listed_by_date_in_a_letter() -> None:
    result = recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB")
    lines = "\n".join(result.as_letter().splitlines())
    for day in (jul(6), jul(7)):
        assert f"  {day.isoformat()}" in lines
    assert CITE_CHARGED_DATES in lines


def test_every_date_in_the_letter_is_iso_formatted() -> None:
    """A dispute letter that says 7/8/2026 in one place and 2026-07-08 in another
    is a letter a carrier's respondent can decline to parse."""
    for text in (recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB").as_letter(),):
        for token in re.findall(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b", text):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", token), token


def test_the_date_list_is_sorted_and_deduplicated() -> None:
    over = recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB").overbilled
    assert over is not None
    assert list(over.dates) == sorted(over.dates)
    assert len(set(over.dates)) == len(over.dates)


# ---------------------------------------------------------------- criterion 4
# A test covers a carrier billing a Saturday under a working-day basis.


def test_a_saturday_billed_under_a_working_day_basis_is_an_overbill() -> None:
    """The criterion.

    4 July 2026 is a Saturday. Under Hapag's Monday to Friday basis it is not a
    working day, so the carrier cannot bill it. Under Maersk's Monday to Saturday
    basis it can, and that is the difference between the same date being a
    legitimate charge and a recovery.
    """
    # 11 July 2026 is a Saturday and falls after the recomputed end of 7 July, so
    # the day unit is the only possible reason it is not chargeable.
    assert jul(11).weekday() == 5
    result = recompute(
        invoice(
            free_time_end=RECOMPUTED_END,
            charged_dates=frozenset({jul(8), jul(9), jul(10), jul(11)}),
        ),
        "Hapag-Lloyd",
        terminal="USLAXB",
    )
    over = result.overbilled
    assert over is not None
    assert over.dates == (jul(11),)
    assert "day unit" in over.detail
    assert CITE_ACCURACY in over.citation


def test_the_same_saturday_is_a_legitimate_charge_under_a_monday_to_saturday_basis() -> None:
    """Maersk, not Hapag. The same date, the opposite result, and the reason is
    issue 18's working day basis rather than anything about the date."""
    result = recompute(
        invoice(
            free_time_end=RECOMPUTED_END,
            charged_dates=frozenset({jul(8), jul(9), jul(10), jul(11)}),
        ),
        "Maersk",
        terminal="USNYC",
    )
    assert result.overbilled is None, "a Saturday is a chargeable calendar day for Maersk"

    # The day set does not fully reconcile, and it should not. Maersk counts the
    # Saturday of 4 July as a working day, so its free time ends a day earlier than
    # Hapag's, and 5, 6 and 7 July are days the disclosures say should have been
    # charged. That is the underbilled set doing its job, and asserting a clean
    # result here would have meant either hiding it or misunderstanding the basis.
    assert result.underbilled is not None
    assert set(result.underbilled.dates) == {jul(5), jul(6), jul(7)}


def test_a_saturday_inside_the_allowance_is_still_an_overbill_under_both_bases() -> None:
    """Being a working day for Maersk does not make Saturday free.

    A Saturday inside the allowance consumes a day under Maersk and is skipped
    under Hapag, and in both cases charging it separately is wrong. Asserted so the
    two reasons for excluding a date stay distinct.
    """
    for carrier in ("Hapag-Lloyd", "Maersk"):
        result = recompute(
            invoice(charged_dates=frozenset({jul(4), jul(10)})),
            carrier,
            terminal="USLAXB",
        )
        assert result.overbilled is not None, carrier
        assert jul(4) in result.overbilled.dates, carrier
        assert CITE_ALLOWANCE in result.overbilled.detail, carrier


# ---------------------------------------------------------------- the model


def test_the_model_requires_the_four_disclosures_the_recomputation_relies_on() -> None:
    assert REQUIRED_FOR_RECOMPUTATION == {
        "allowed_free_time_days": CITE_ALLOWANCE,
        "free_time_start": "541.6(b)(4)",
        "charged_dates": CITE_CHARGED_DATES,
    }
    for field in REQUIRED_FOR_RECOMPUTATION:
        assert hasattr(clean_invoice(), field), field


def test_the_model_rejects_an_invoice_missing_its_own_disclosures() -> None:
    """Every rejection quotes the clause that requires the missing disclosure.

    The cites are escaped. pytest.raises takes a regex and 541.6(b)(6) read as one
    is "541.6b6", which matches nothing, so the first version of this test passed an
    unescaped cite and would have kept passing after the messages changed. A test
    that cannot fail on a string it is checking is decoration.
    """
    with pytest.raises(ValueError, match=re.escape(CITE_AVAILABILITY)):
        invoice(availability_date=None)
    with pytest.raises(ValueError, match="at least one day"):
        invoice(allowed_free_time_days=0)
    with pytest.raises(ValueError, match=re.escape(CITE_CHARGED_DATES)):
        invoice(charged_dates=frozenset())
    with pytest.raises(ValueError, match="precedes"):
        invoice(free_time_end=date(2026, 6, 1))


def test_charged_dates_are_typed_as_a_set_not_a_list() -> None:
    """A carrier listing a date twice is a different defect from one charging a day
    it should not have. The duplicate case belongs to the arithmetic issue, and the
    frozenset annotation is what keeps it out of this module.

    Asserted as an annotation rather than a runtime rejection, because Python does
    not enforce it, and pretending otherwise in a test would be the kind of
    confidence this repository has been auditing out of itself for ten issues.
    """
    hints = TimingDisclosures.__dataclass_fields__["charged_dates"].type
    assert hints is not None
    assert "frozenset" in str(hints)


def test_an_export_invoice_needs_no_availability_date() -> None:
    export = invoice(trade=Trade.EXPORT, availability_date=None, earliest_return_date=jul(6))
    assert export.trade is Trade.EXPORT
    assert recompute(export, "Hapag-Lloyd", terminal="USLAXB").overbilled is not None


def test_an_unknown_carrier_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(KeyError):
        recompute(clean_invoice(), "MSC")


def test_discrepancies_are_immutable() -> None:
    result = recompute(invoice(), "Hapag-Lloyd", terminal="USLAXB")
    over = result.overbilled
    assert over is not None
    assert isinstance(over, Discrepancy)
    with pytest.raises(AttributeError):
        over.dates = ()  # type: ignore[misc]
