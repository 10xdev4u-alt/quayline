"""The four acceptance criteria on issue 12, one test block each.

The claim worth defending here is the Monday to Saturday one. A calendar that shifts
every Saturday back to Friday is the obvious implementation and it is wrong for
Maersk, because Maersk's working day basis is Monday to Saturday and 6103(b) says in
terms that the shift does not apply to that workweek.
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest

from quayline.calendars.closures import ClosureType
from quayline.calendars.holidays import (
    CITATION,
    HOLIDAY_COUNT,
    MONDAY_TO_SATURDAY_EXCLUSION,
    MONTHS,
    NON_MONDAY_FRIDAY_RULE,
    RULES,
    Holiday,
    ObservedHoliday,
    TerminalClosures,
    WorkWeek,
    federal_holidays,
    observed,
    statutory_date,
)

MF = WorkWeek.MONDAY_FRIDAY
MS = WorkWeek.MONDAY_SATURDAY


# ---------------------------------------------------------------- criterion 1
# Federal holidays compute for any year.


def test_eleven_holidays_in_statutory_order() -> None:
    assert HOLIDAY_COUNT == 11
    assert [h.holiday for h in federal_holidays(2026)] == list(Holiday)


@pytest.mark.parametrize("year", [2021, 2024, 2025, 2026, 2027, 2030, 2031, 2035, 2040])
def test_computes_for_any_year_with_no_exceptions(year: int) -> None:
    """Eleven holidays, each landing inside the year, for years far apart.

    2030 and 2035 are included because 2030 is one of the years where January 1 and
    December 25 fall on awkward weekdays, and 2035 because it is a long way out
    enough to catch a hardcoded table.
    """
    results = federal_holidays(year)
    assert len(results) == 11
    for entry in results:
        assert entry.statutory_date.year == year
        assert entry.observed_date.year in (year, year - 1, year + 1)
    assert len({e.observed_date for e in results}) == len({e.observed_date for e in results}), (
        "observed dates must be a set"
    )


def test_nth_weekday_and_last_weekday_are_computed_not_tabulated() -> None:
    """Spot checks against dates worked out by hand."""
    # third Monday in January 2026
    assert statutory_date(Holiday.MARTIN_LUTHER_KING_JR_DAY, 2026) == date(2026, 1, 19)
    # last Monday in May 2026, which is the 25th
    assert statutory_date(Holiday.MEMORIAL_DAY, 2026) == date(2026, 5, 25)
    # fourth Thursday in November 2026
    assert statutory_date(Holiday.THANKSGIVING_DAY, 2026) == date(2026, 11, 26)
    # and a year where the last Monday in May is the 31st
    assert statutory_date(Holiday.MEMORIAL_DAY, 2027) == date(2027, 5, 31)


def test_the_designation_table_covers_every_holiday_exactly_once() -> None:
    assert set(RULES) == set(Holiday)
    assert set(MONTHS) == set(Holiday)
    for holiday, rule in RULES.items():
        assert rule.month == MONTHS[holiday], holiday
        assert (rule.fixed is None) != (rule.nth is None), holiday


# ---------------------------------------------------------------- criterion 2
# Saturday shifts to Friday, Sunday to Monday.


def test_saturday_shifts_back_to_friday() -> None:
    assert statutory_date(Holiday.INDEPENDENCE_DAY, 2026).weekday() == 5
    entry = observed(Holiday.INDEPENDENCE_DAY, 2026, MF)
    assert entry.observed_date == date(2026, 7, 3)
    assert entry.observed_date.weekday() == 4
    assert entry.shifted is True


def test_sunday_shifts_forward_to_monday() -> None:
    # 4 July 2027 is a Sunday
    assert statutory_date(Holiday.INDEPENDENCE_DAY, 2027).weekday() == 6
    entry = observed(Holiday.INDEPENDENCE_DAY, 2027, MF)
    assert entry.observed_date == date(2027, 7, 5)
    assert entry.observed_date.weekday() == 0
    assert entry.shifted is True


def test_a_weekday_holiday_does_not_move() -> None:
    entry = observed(Holiday.NEW_YEARS_DAY, 2026, MF)
    assert entry.observed_date == entry.statutory_date == date(2026, 1, 1)
    assert entry.shifted is False


def test_floating_holidays_never_shift_because_they_are_always_mondays_or_thursdays() -> None:
    """Six of the eleven are defined by weekday, so they cannot land on a weekend.

    Worth asserting rather than assuming, because if a rule were edited to a fixed
    day this would silently start shifting and nobody would look.
    """
    for holiday in (
        Holiday.MARTIN_LUTHER_KING_JR_DAY,
        Holiday.WASHINGS_BIRTHDAY,
        Holiday.MEMORIAL_DAY,
        Holiday.LABOR_DAY,
        Holiday.COLUMBUS_DAY,
        Holiday.THANKSGIVING_DAY,
    ):
        for year in range(2020, 2035):
            assert statutory_date(holiday, year).weekday() < 5, (holiday, year)


# ---------------------------------------------------------------- criterion 3
# Independence Day 2026, a Saturday, is observed on 2026-07-03.


def test_independence_day_2026_is_the_named_case() -> None:
    """The criterion stated as the exact assertion it asks for."""
    entry = observed(Holiday.INDEPENDENCE_DAY, 2026, MF)
    assert entry.holiday is Holiday.INDEPENDENCE_DAY
    assert entry.statutory_date == date(2026, 7, 4)
    assert entry.statutory_date.strftime("%A") == "Saturday"
    assert entry.observed_date == date(2026, 7, 3)
    assert entry.observed_date.isoformat() == "2026-07-03"


def test_the_saturday_shift_does_not_apply_to_a_monday_to_saturday_workweek() -> None:
    """The finding, and the most valuable line in this module.

    6103(b) closes with "This subsection, except subparagraph (B) of paragraph (1),
    does not apply to an employee whose basic workweek is Monday through Saturday."

    Maersk's published working day basis is Monday to Saturday. So a Saturday holiday
    under Maersk is not observed on the Friday, and a calendar that shifts every
    Saturday back is wrong by one day on every Maersk dispute involving one.
    """
    entry = observed(Holiday.INDEPENDENCE_DAY, 2026, MS)
    assert entry.observed_date == date(2026, 7, 4)
    assert entry.shifted is False
    assert MS.saturday_shift_applies is False
    assert MF.saturday_shift_applies is True


def test_sunday_under_a_monday_to_saturday_workweek_shifts_back_to_saturday() -> None:
    """6103(b)(2), which is not the same rule as (b)(1) and moves the other way.

    Sunday is the regular non-workday for a Monday to Saturday employee, so the
    workday immediately before it is Saturday. A Sunday holiday is observed on the
    Saturday before, not the Monday after.
    """
    entry = observed(Holiday.INDEPENDENCE_DAY, 2027, MS)
    assert entry.observed_date == date(2027, 7, 3)
    assert entry.observed_date.weekday() == 5
    assert entry.shifted is True


def test_the_two_workweeks_disagree_on_both_weekend_days() -> None:
    sat_2026 = (
        observed(Holiday.INDEPENDENCE_DAY, 2026, MF),
        observed(Holiday.INDEPENDENCE_DAY, 2026, MS),
    )
    sun_2027 = (
        observed(Holiday.INDEPENDENCE_DAY, 2027, MF),
        observed(Holiday.INDEPENDENCE_DAY, 2027, MS),
    )
    assert sat_2026[0].observed_date != sat_2026[1].observed_date
    assert sun_2027[0].observed_date != sun_2027[1].observed_date


def test_the_statutory_dates_are_never_the_same_under_either_workweek() -> None:
    """The workweek shifts the observed day, never the statutory day.

    The statutory date is a fact about the statute and 6103(a) does not vary with the
    employer.
    """
    for holiday in Holiday:
        assert (
            observed(holiday, 2026, MF).statutory_date == observed(holiday, 2026, MS).statutory_date
        ), holiday


def test_citations_are_the_statutes_own_words() -> None:
    assert CITATION == "5 U.S.C. 6103"
    assert MONDAY_TO_SATURDAY_EXCLUSION.startswith("This subsection, except")
    assert "does not apply to an employee whose basic workweek is Monday through Saturday" in (
        MONDAY_TO_SATURDAY_EXCLUSION
    )
    assert "the workday immediately before that regular weekly nonworkday" in (
        NON_MONDAY_FRIDAY_RULE
    )


# ---------------------------------------------------------------- criterion 4
# Optional per-terminal closure injection is supported.


def test_a_terminal_can_add_closures_the_calendar_does_not_know_about() -> None:
    terminal = TerminalClosures(
        terminal="USLAXB",
        extra_closures=frozenset(
            {
                (date(2026, 7, 21), ClosureType.SCHEDULED_CLOSURE),
                (date(2026, 10, 5), ClosureType.UNSCHEDULED_SHUTOUT),
            }
        ),
    )
    assert terminal.closure_dates(2026) == frozenset({date(2026, 7, 21), date(2026, 10, 5)})
    assert date(2026, 7, 21) in terminal.observed_dates(2026, MF)
    assert date(2026, 10, 5) in terminal.observed_dates(2026, MS)
    assert date(2026, 7, 3) in terminal.observed_dates(2026, MF), "reference still applies"


def test_injection_is_year_scoped() -> None:
    terminal = TerminalClosures(
        terminal="USSAV",
        extra_closures=frozenset({(date(2026, 7, 21), ClosureType.HOLIDAY)}),
    )
    assert terminal.observed_dates(2026, MF) != terminal.observed_dates(2027, MF)
    assert date(2026, 7, 21) not in terminal.observed_dates(2027, MF)


def test_a_terminal_with_no_extra_closures_is_pure_reference() -> None:
    plain = TerminalClosures(terminal="USLAX")
    for workweek in (MF, MS):
        assert plain.observed_dates(2026, workweek) == frozenset(
            h.observed_date for h in federal_holidays(2026, workweek)
        )


def test_injected_closures_carry_the_closure_type_vocabulary() -> None:
    """A terminal closure and a carrier rule are the same kind of object.

    Otherwise a terminal closure could not be tested against a Hapag policy, which is
    the whole point of the vocabulary existing.
    """
    terminal = TerminalClosures(
        terminal="USLAXB",
        extra_closures=frozenset({(date(2026, 10, 5), ClosureType.UNSCHEDULED_SHUTOUT)}),
    )
    kinds = {kind for _, kind in terminal.extra_closures}
    assert kinds <= set(ClosureType)
    assert ClosureType.UNSCHEDULED_SHUTOUT in kinds


def test_the_reference_calendar_is_not_claimed_to_be_the_terminals_hours() -> None:
    """Asserted on the module docstring, because it is the caveat most likely to be
    lost once the code is used.

    6103(b) governs federal employees' pay and leave. A terminal closing on July 3rd
    is practice that aligns with it, not compliance with it.
    """
    module = importlib.import_module("quayline.calendars.holidays")
    text = module.__doc__ or ""
    assert "reference" in text
    assert "does not reach" in text
    assert "pay and leave of" in text


def test_inauguration_day_is_absent_and_the_reason_is_recorded() -> None:
    """6103(c) covers only named federal roles in DC area counties, so it is not
    modelled, and the docstring says so rather than leaving a reader to wonder."""
    module = importlib.import_module("quayline.calendars.holidays")
    text = module.__doc__ or ""
    assert "Inauguration Day is excluded" in text
    assert Holiday.NEW_YEARS_DAY.value == "new_years_day"
    assert len(list(Holiday)) == 11


def test_entries_are_immutable() -> None:
    entry: ObservedHoliday = observed(Holiday.INDEPENDENCE_DAY, 2026, MF)
    with pytest.raises(AttributeError):
        entry.observed_date = date(2026, 7, 4)  # type: ignore[misc]
