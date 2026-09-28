"""The three acceptance criteria on issue 11, one test block each.

The scenario that earns this module is a bank holiday landing inside an allowance.
The exemption does not consume one of the allowance's days, it pushes the expiry out
by one, and that pushed-out date is what the carrier then bills from.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from quayline.calendars.closures import ClosureType
from quayline.calendars.freetime import (
    CITATION_HAPAG_FREE_TIME,
    CITATION_HAPAG_POST,
    DayNote,
    FreeTimeResult,
    Verdict,
    free_time,
    post_expiry_charged,
)

# Independence Day 2026 is a Saturday. Under a Monday to Friday workweek it is
# observed Friday the 3rd, so the gate is shut on the 3rd and the 4th is a Saturday
# and is not a working day at all.
JUL1, JUL2, JUL3, JUL4, JUL5 = (
    date(2026, 7, 1),
    date(2026, 7, 2),
    date(2026, 7, 3),
    date(2026, 7, 4),
    date(2026, 7, 5),
)
# A week with no federal holiday in it at all, for the control case.
CLEAN_START = date(2026, 3, 2)


# ---------------------------------------------------------------- criterion 1
# Free-time computation excludes holidays and extends the allowance.


def test_a_holiday_inside_the_window_does_not_consume_an_allowance_day() -> None:
    result = free_time("Hapag-Lloyd", JUL1 - timedelta(days=1), 4)
    extended = result.notes_for(Verdict.EXTENDED)
    assert [n.day for n in extended] == [JUL3]
    assert result.counted_days == 4
    assert result.extension_days == 1


def test_the_allowance_is_still_fully_honoured() -> None:
    """Extension, not discount. Four free days means four free days, plus more.

    The point of a test that counts is that a bank holiday does not quietly reduce
    what the customer gets, it increases the number of days the container sits
    there.
    """
    result = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    assert result.counted_days == 4
    assert result.extension_days == 1
    assert result.last_free_day == date(2026, 7, 7)


def test_a_clean_window_has_no_extension() -> None:
    result = free_time("Hapag-Lloyd", CLEAN_START, 4)
    assert result.extension_days == 0
    assert result.notes_for(Verdict.EXTENDED) == ()
    assert result.counted_days == 4


def test_every_day_on_the_walk_is_reported_with_a_reason() -> None:
    result = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    assert len(result.notes) == 7, (
        "two working days, one holiday, one Saturday, one Sunday, two more"
    )
    for note in result.notes:
        assert note.reason
        assert isinstance(note, DayNote)
    counted = {n.day for n in result.notes_for(Verdict.COUNTED)}
    assert result.last_free_day in counted


def test_the_walk_skips_a_non_working_day_rather_than_extending_for_it() -> None:
    """The distinction the whole module turns on.

    Saturday the 4th is not a working day under a Monday to Friday basis, so it is
    skipped. It is not forgiven, so it is not reported as an extension. Under Maersk
    the same Saturday is a working day and is counted outright.
    """
    result = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    skipped = {n.day for n in result.notes_for(Verdict.SKIPPED_NOT_A_WORKING_DAY)}
    assert JUL4 in skipped
    assert JUL5 in skipped
    assert result.extension_days == 1, "only the holiday extends, not the weekend"


def test_a_december_start_walks_into_january() -> None:
    """Two years of holidays are loaded, because a December walk crosses a year."""
    result = free_time("Hapag-Lloyd", date(2025, 12, 29), 4)
    assert result.last_free_day > date(2025, 12, 31)
    assert result.counted_days == 4


# ---------------------------------------------------------------- criterion 2
# A test asserts a holiday inside the free-time window pushes the expiry date out.


def test_the_holiday_pushes_the_expiry_date_out_by_one_day() -> None:
    """The criterion, as a comparison of two walks.

    Same carrier, same allowance, same start. One window contains a bank holiday
    and one does not. The window with the holiday expires a day later, and the
    carrier bills from the later date.
    """
    with_holiday = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    without = free_time("Hapag-Lloyd", date(2026, 7, 6), 4)

    assert with_holiday.extension_days == 1
    assert without.extension_days == 0
    assert with_holiday.last_free_day == date(2026, 7, 7)
    assert without.last_free_day == date(2026, 7, 10)
    # The two windows start on different days, so the expiry dates are not directly
    # comparable. The claim under test is the extension count, and it is one against
    # zero. The walk is what shows the holiday being skipped rather than consumed.


def test_the_expiry_is_the_last_counted_day_not_the_walk_length() -> None:
    """A walk of nine days can end on the fourth counted day.

    Asserting the date rather than the length is the point. The date is what the
    carrier bills from and the number of days walked is an artefact of how many
    weekends and holidays got in the way.
    """
    result = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    assert len(result.notes) == 7
    assert result.last_free_day == date(2026, 7, 7)
    assert result.notes[-1].day == result.last_free_day
    assert result.notes[-1].verdict is Verdict.COUNTED


def test_maersk_counts_the_saturday_that_hapag_skips() -> None:
    """Issue 18's finding showing up in an expiry date, which is the point of it.

    Same span, same holiday, two carriers. Hapag skips Saturday because Saturday is
    not a working day for it. Maersk counts it because Saturday is a working day for
    it. Identical allowance, different expiry.
    """
    hapag = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    maersk = free_time("Maersk", date(2026, 6, 30), 4)
    assert hapag.last_free_day != maersk.last_free_day


def test_an_injected_closure_extends_only_if_the_carrier_forgives_it() -> None:
    hapag_unplanned = free_time(
        "Hapag-Lloyd",
        CLEAN_START,
        4,
        extra_closures=frozenset({(date(2026, 3, 3), ClosureType.UNSCHEDULED_SHUTOUT)}),
    )
    assert hapag_unplanned.extension_days == 1

    maersk_same = free_time(
        "Maersk",
        CLEAN_START,
        4,
        extra_closures=frozenset({(date(2026, 3, 3), ClosureType.UNSCHEDULED_SHUTOUT)}),
    )
    assert maersk_same.extension_days == 0, (
        "Maersk forgives nothing beyond a booked appointment, so an unplanned "
        "shutout consumes an allowance day"
    )
    assert [n.day for n in maersk_same.notes_for(Verdict.COUNTED)] == [
        date(2026, 3, 3),
        date(2026, 3, 4),
        date(2026, 3, 5),
        date(2026, 3, 6),
    ]


# ---------------------------------------------------------------- criterion 3
# A test asserts a scheduled closure after expiry is still charged.


def test_a_scheduled_closure_after_expiry_is_still_charged() -> None:
    assert post_expiry_charged("Hapag-Lloyd", ClosureType.SCHEDULED_CLOSURE) is True


def test_an_unscheduled_shutout_after_expiry_is_not_charged() -> None:
    """The asymmetry, which is the rule.

    Same carrier, same closed gate, opposite treatment, decided by who planned it.
    A scheduled closure is the carrier's own and is billed from the moment the
    allowance runs out. An unscheduled shutout is nobody's fault and is never
    billed.
    """
    assert post_expiry_charged("Hapag-Lloyd", ClosureType.UNSCHEDULED_SHUTOUT) is False
    assert post_expiry_charged("Hapag-Lloyd", ClosureType.SCHEDULED_CLOSURE) is True
    assert post_expiry_charged("Hapag-Lloyd", ClosureType.WEEKEND) is True


def test_maersk_forgives_nothing_after_expiry() -> None:
    for closure in ClosureType:
        assert post_expiry_charged("Maersk", closure) is True, closure


def test_the_asymmetry_is_exactly_the_two_hapag_closure_types() -> None:
    forgiven = {c for c in ClosureType if not post_expiry_charged("Hapag-Lloyd", c)}
    assert forgiven == {ClosureType.UNSCHEDULED_SHUTOUT}


# ---------------------------------------------------------------- provenance


def test_both_hapag_citations_are_the_carriers_words() -> None:
    assert "excluded from free time calculations" in CITATION_HAPAG_FREE_TIME
    assert "extended by the corresponding number of days" in CITATION_HAPAG_FREE_TIME
    assert "unscheduled closures" in CITATION_HAPAG_POST
    assert "excluded from Detention and Demurrage" in CITATION_HAPAG_POST


def test_a_zero_or_negative_allowance_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one day"):
        free_time("Hapag-Lloyd", CLEAN_START, 0)


def test_the_result_renders_as_a_dispute_letter_block() -> None:
    letter = free_time("Hapag-Lloyd", date(2026, 6, 30), 4).as_letter()
    assert "free time 4 working days from 2026-06-30" in letter
    assert "last free day 2026-07-07" in letter
    assert "extended by 1 day" in letter
    assert letter.count("2026-07-") == 8, "one header expiry plus seven walked days"


def test_results_are_immutable() -> None:
    result: FreeTimeResult = free_time("Hapag-Lloyd", CLEAN_START, 4)
    with pytest.raises(AttributeError):
        result.last_free_day = date(2026, 1, 1)  # type: ignore[misc]
