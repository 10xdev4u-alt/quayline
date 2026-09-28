"""The four acceptance criteria on issue 9, one test block each.

The scenario that earns this module is a single weekend read at two Hapag
terminals. Same carrier, same allowance, same two days, opposite answers, and the
only place the difference appears is a column labelled tier unit.
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest

from quayline.calendars.closures import CLOSURE_POLICY_FOR, ClosureType
from quayline.calendars.day_basis import MAERSK_US, DayBasis
from quayline.calendars.window import (
    HAPAG,
    MAERSK,
    UNITS,
    CarrierUnits,
    DayUnit,
    charge_window,
    free_time_window,
)

# Friday to Monday, so the span contains a full weekend and no holiday.
FRI, SAT, SUN, MON = date(2026, 6, 5), date(2026, 6, 6), date(2026, 6, 7), date(2026, 6, 8)
# Independence Day 2026 is a Saturday, observed Friday the 3rd.
JUL3, JUL4, JUL5, JUL6 = date(2026, 7, 3), date(2026, 7, 4), date(2026, 7, 5), date(2026, 7, 6)


# ---------------------------------------------------------------- criterion 1
# A charge window enumerates chargeable and excluded days separately.


def test_every_day_is_enumerated_not_summarised() -> None:
    window = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")
    assert len(window.rows) == 4
    assert [r.day for r in window.rows] == [FRI, SAT, SUN, MON]


def test_chargeable_and_excluded_are_separate_tuples() -> None:
    window = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")
    assert [r.day for r in window.chargeable] == [FRI, MON]
    assert [r.day for r in window.excluded] == [SAT, SUN]
    assert len(window.chargeable) + len(window.excluded) == len(window.rows)


def test_every_row_carries_a_reason() -> None:
    """A row that cannot explain itself cannot go in a letter."""
    window = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")
    for row in window.rows:
        assert row.reason and isinstance(row.reason, str)
        assert "excluded" in row.as_letter_line() or "chargeable" in row.as_letter_line()


def test_the_window_renders_as_a_dispute_letter_block() -> None:
    letter = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB").as_letter()
    assert "Hapag-Lloyd at USLAXB" in letter
    assert "unit working" in letter
    assert "2 of 4 days chargeable" in letter
    assert letter.count("2026-06-") == 4


def test_the_free_time_window_is_a_separate_function_nothing_is_chargeable() -> None:
    """A caller counting chargeable days and a caller checking an allowance are
    doing different things and should not look alike at the call site."""
    window = free_time_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")
    assert window.chargeable_count == 0
    assert len(window.excluded) == 4
    assert all("free time allowance" in r.reason for r in window.rows)


def test_a_reversed_range_is_rejected_by_both_windows() -> None:
    for call in (charge_window, free_time_window):
        with pytest.raises(ValueError, match="precedes"):
            call("Hapag-Lloyd", MON, FRI, terminal="USLAXB")


# ---------------------------------------------------------------- criterion 2
# Regional basis overrides work, so Hapag California resolves to working and Hapag
# Savannah to calendar.


def test_hapag_california_resolves_to_working_and_savannah_to_calendar() -> None:
    assert HAPAG.tier_unit_for("USLAXB") is DayUnit.WORKING
    assert HAPAG.tier_unit_for("USSAVNG") is DayUnit.CALENDAR
    assert charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB").unit is DayUnit.WORKING
    assert charge_window("Hapag-Lloyd", FRI, MON, terminal="USSAVNG").unit is DayUnit.CALENDAR


def test_the_free_time_unit_is_the_same_at_every_hapag_terminal() -> None:
    """The allowance does not change by terminal. The unit it is charged in does.

    Both halves matter and the second is the invisible one. A four working day
    allowance is DOD + 4WD whether the container is in Georgia or California.
    """
    for terminal, _unit in HAPAG.terminal_tier_units:
        assert HAPAG.free_time_unit is DayUnit.WORKING, terminal
    assert HAPAG.free_time_unit is DayUnit.WORKING


def test_an_unknown_terminal_falls_back_to_the_carrier_default() -> None:
    assert HAPAG.tier_unit_for("NOWHERE") is DayUnit.CALENDAR
    assert charge_window("Hapag-Lloyd", FRI, MON, terminal="NOWHERE").unit is DayUnit.CALENDAR


def test_maersk_is_calendar_at_every_terminal_which_is_the_opposite_of_hapag() -> None:
    """Why one field cannot carry both carriers. Maersk converted US wide on
    2024-08-08 with no exceptions, so it has no regional split at all."""
    assert MAERSK.tier_unit_default is DayUnit.CALENDAR
    assert MAERSK.terminal_tier_units == ()
    for terminal in ("USSAVNG", "USLAXB", "USNYC", "NOWHERE"):
        assert MAERSK.tier_unit_for(terminal) is DayUnit.CALENDAR, terminal


def test_day_unit_is_a_separate_type_from_the_working_week() -> None:
    """The review of issue 18 flagged overloading DayBasis as the next mistake.

    A California terminal bills post free time in working days because of its day
    unit, not because its working week is Saturday-inclusive. Conflating them
    produces a count that is wrong without looking wrong, so the types are separate
    and this test says so.
    """
    assert {u.value for u in DayUnit} == {"working", "calendar"}
    assert {b.value for b in DayBasis} == {
        "monday_saturday",
        "monday_friday",
        "calendar",
    }
    assert DayUnit is not DayBasis  # type: ignore[comparison-overlap]


# ---------------------------------------------------------------- criterion 3
# A test asserts the same weekend costs two days in Savannah and nothing in Los
# Angeles.


def test_the_same_weekend_costs_two_days_in_savannah_and_nothing_in_los_angeles() -> None:
    """The California trap, as a single assertion.

    One container over a Saturday and a Sunday. Four days of span, identical at
    both terminals, same carrier, same four day allowance. Savannah bills all four
    calendar days including the weekend. Los Angeles bills the two weekdays and
    excludes the weekend because the unit is working days.
    """
    savannah = charge_window("Hapag-Lloyd", FRI, MON, terminal="USSAVNG")
    los_angeles = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")

    assert savannah.unit is DayUnit.CALENDAR
    assert los_angeles.unit is DayUnit.WORKING
    assert savannah.chargeable_count == 4
    assert los_angeles.chargeable_count == 2
    assert savannah.chargeable_count - los_angeles.chargeable_count == 2

    assert {r.day for r in savannah.chargeable} == {FRI, SAT, SUN, MON}
    assert {r.day for r in los_angeles.chargeable} == {FRI, MON}
    assert {r.day for r in los_angeles.excluded} == {SAT, SUN}


def test_the_weekend_is_excluded_at_los_angeles_for_the_right_reason() -> None:
    """Not because Hapag forgives weekends. It does not.

    Saturday is excluded at USLAXB because the unit is working days and Saturday is
    not one. The closure policy's post free time set does not contain WEEKEND, and
    both statements are true and are about different things. The first version of
    this function looked the closure policy up and did not use it, and the reason it
    does not use it is now written down next to the lookup that is deliberately
    absent.
    """
    policy = CLOSURE_POLICY_FOR["Hapag-Lloyd"]
    assert policy.forgives(ClosureType.WEEKEND, after_free_time=True) is False
    window = charge_window("Hapag-Lloyd", FRI, MON, terminal="USLAXB")
    weekend_rows = [r for r in window.excluded if r.day in (SAT, SUN)]
    assert all("weekly closure under this carrier's working week" in r.reason for r in weekend_rows)


def test_a_federal_holiday_is_excluded_at_both_terminals() -> None:
    """4 July 2026 is a Saturday, observed Friday the 3rd, and both dates are
    excluded at a calendar terminal and a working terminal alike.

    Sunday the 5th is the interesting one. It is not an observed date, so at a
    calendar terminal it is chargeable, and at a working terminal it is excluded as a
    weekly closure rather than as a holiday. My first version of this test asserted
    it was excluded at both, which would have meant Sunday being quietly treated as
    a holiday at every terminal and a day wrongly dropped from a Savannah invoice.
    """
    savannah = charge_window("Hapag-Lloyd", JUL3, JUL6, terminal="USSAVNG")
    los_angeles = charge_window("Hapag-Lloyd", JUL3, JUL6, terminal="USLAXB")

    for window, terminal in ((savannah, "USSAVNG"), (los_angeles, "USLAXB")):
        excluded = {r.day for r in window.excluded}
        assert JUL3 in excluded, f"{terminal}: observed date must be excluded"
        assert JUL4 in excluded, f"{terminal}: statutory date must be excluded"
        assert JUL6 in {r.day for r in window.chargeable}, terminal
        assert all("holiday" in r.reason for r in window.excluded if r.day in (JUL3, JUL4)), (
            terminal
        )

    assert JUL5 in {r.day for r in savannah.chargeable}, "Sunday is a calendar day"
    sunday_la = [r for r in los_angeles.excluded if r.day == JUL5]
    assert sunday_la and "weekly closure" in sunday_la[0].reason, (
        "Sunday at a working terminal is a weekly closure, not a holiday, and saying "
        "otherwise would put the wrong reason in a dispute letter"
    )


def test_injected_terminal_closures_are_honoured() -> None:
    window = charge_window(
        "Hapag-Lloyd", FRI, MON, terminal="USSAVNG", extra_excluded=frozenset({SAT})
    )
    excluded = {r.day for r in window.excluded}
    assert excluded == {SAT}
    assert {r.day for r in window.chargeable} == {FRI, SUN, MON}
    assert all(r.reason == "terminal closure" for r in window.excluded)


# ---------------------------------------------------------------- criterion 4
# A test asserts Maersk working days are Monday to Saturday.


def test_maersk_working_days_are_monday_to_saturday() -> None:
    assert MAERSK_US.default.value == "monday_saturday"
    for day in (FRI, SAT, MON):
        assert MAERSK_US.is_working_day(day) is True, day
    assert MAERSK_US.is_working_day(SUN) is False
    assert MAERSK_US.basis_for("").weekly_closures() == frozenset({6})


def test_maersk_charges_the_weekend_because_its_unit_is_calendar() -> None:
    """Maersk's working week includes Saturday and its post free time unit is
    calendar, so the two facts answer different questions and neither cancels the
    other. Saturday is a working day for the free time count and a chargeable
    calendar day afterwards.
    """
    window = charge_window("Maersk", FRI, MON, terminal="USNYC")
    assert window.unit is DayUnit.CALENDAR
    assert window.chargeable_count == 4
    assert MAERSK_US.is_working_day(SAT) is True


def test_every_carrier_unit_block_is_cited_and_marked() -> None:
    for units in UNITS.values():
        assert units.citation
        assert units.source
        assert isinstance(units.verified, bool)
        if not units.verified:
            assert units.citation.startswith("UNVERIFIED:")
    assert set(UNITS) == {"Hapag-Lloyd", "Maersk"}


def test_the_module_docstring_records_the_trap() -> None:
    text = " ".join((importlib.import_module("quayline.calendars.window").__doc__ or "").split())
    assert "California trap" in text
    assert "3WD" in text and "3CD" in text
    assert "separate type from DayBasis" in text


def test_terminal_units_are_a_tuple_so_the_rule_is_genuinely_frozen() -> None:
    assert isinstance(HAPAG.terminal_tier_units, tuple)
    with pytest.raises(AttributeError):
        HAPAG.tier_unit_default = DayUnit.WORKING  # type: ignore[misc]
    assert len({HAPAG, MAERSK}) == 2


def test_a_carrier_units_record_needs_its_own_default() -> None:
    with pytest.raises(TypeError):
        CarrierUnits(carrier="half", free_time_unit=DayUnit.WORKING)  # type: ignore[call-arg]
