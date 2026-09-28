"""US federal holidays, with the observed-day shifting, per 5 U.S.C. 6103.

What this is and is not

This is a *reference* calendar. It is not the authority on when a container
terminal was shut, and the difference matters, so it is stated first.

5 U.S.C. 6103(b) opens "For the purpose of statutes relating to pay and leave of
employees". It governs federal employees' leave. A marine terminal closing on
July 3rd is a business practice that happens to align with it, and a terminal that
stays open on a federal holiday is not breaking 6103, because 6103 does not reach
it.

What the carriers' tariffs actually say is "bank holiday", unexpanded. So the
reference calendar supplies the defensible default and the terminal's own published
hours supply the truth, which is why per-terminal injection exists here rather than
being bolted on later. Issue 12 asks for it as an acceptance criterion and it is the
right shape: a calendar that cannot be overridden by the terminal that owns the fact
is worse than no calendar.

The one thing this calendar got right that a naive one does not

The Saturday shift does not apply to everyone. 6103(b) closes with:

    This subsection, except subparagraph (B) of paragraph (1), does not apply to
    an employee whose basic workweek is Monday through Saturday.

So for a Monday to Friday workweek a Saturday holiday moves back to Friday, and
for a Monday to Saturday workweek it does not move at all, because Saturday is
already a working day.

Maersk's published working day basis is Monday to Saturday. So under Maersk a
holiday falling on a Saturday is not observed on the Friday, it is observed on the
Saturday, and a naive calendar that shifts every Saturday back one day produces a
day count that is wrong by one on every Maersk dispute involving a Saturday holiday.

That is the single most valuable thing in this module and it comes entirely from
reading the closing sentence of subsection (b).

Sunday is not symmetric, and is not handled the same way

For a Monday to Friday workweek a Sunday holiday is observed on the Monday. That is
standard federal practice and it is what terminals do. It is not stated in
6103(b)(1), which is the Saturday provision, so it is recorded here as practice
rather than as a quotation.

For a Monday to Saturday workweek, 6103(b)(2) does the work and it shifts the other
way:

    Instead of a holiday that occurs on a regular weekly non-workday of an employee
    whose basic workweek is other than Monday through Friday, except the regular
    weekly non-workday administratively scheduled for the employee instead of
    Sunday, the workday immediately before that regular weekly nonworkday is a legal
    public holiday for the employee.

Sunday is the non-workday for a Monday to Saturday employee, so the workday
immediately before it is Saturday. A Sunday holiday is observed on the Saturday
before, not the Monday after.

Inauguration Day is excluded, on purpose

6103(c) makes 20 January of each fourth year a holiday, but only for federal
employees in named District of Columbia, Maryland and Virginia roles. No container
terminal is one of those, so it is not modelled. Recording why it is absent is
better than leaving a reader to wonder whether January 20 was forgotten.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.calendars.closures import ClosureType

HOLIDAY_COUNT = 11

CITATION = "5 U.S.C. 6103"
SOURCE = "https://www.law.cornell.edu/uscode/text/5/6103"

# Verbatim, 6103(b), the sentence that decides whether any of this applies.
MONDAY_TO_SATURDAY_EXCLUSION = (
    "This subsection, except subparagraph (B) of paragraph (1), does not apply to an "
    "employee whose basic workweek is Monday through Saturday."
)

# Verbatim, 6103(b)(2).
NON_MONDAY_FRIDAY_RULE = (
    "Instead of a holiday that occurs on a regular weekly non-workday of an employee "
    "whose basic workweek is other than Monday through Friday, except the regular "
    "weekly non-workday administratively scheduled for the employee instead of "
    "Sunday, the workday immediately before that regular weekly nonworkday is a "
    "legal public holiday for the employee."
)


class WorkWeek(StrEnum):
    """The basic workweek, which decides whether 6103(b) applies at all."""

    MONDAY_FRIDAY = "monday_friday"
    MONDAY_SATURDAY = "monday_saturday"

    @property
    def saturday_shift_applies(self) -> bool:
        """False for Monday to Saturday, per the closing sentence of 6103(b)."""
        return self is WorkWeek.MONDAY_FRIDAY


class Holiday(StrEnum):
    """The eleven legal public holidays listed in 6103(a).

    In the order 6103(a) lists them. Juneteenth was added by Pub. L. 117-17 in
    2021, and its absence from a carrier's free time language predates that.
    """

    NEW_YEARS_DAY = "new_years_day"
    MARTIN_LUTHER_KING_JR_DAY = "martin_luther_king_jr_day"
    WASHINGS_BIRTHDAY = "washings_birthday"
    MEMORIAL_DAY = "memorial_day"
    JUNETEENTH = "juneteenth"
    INDEPENDENCE_DAY = "independence_day"
    LABOR_DAY = "labor_day"
    COLUMBUS_DAY = "columbus_day"
    VETERANS_DAY = "veterans_day"
    THANKSGIVING_DAY = "thanksgiving_day"
    CHRISTMAS_DAY = "christmas_day"


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth given weekday of a month, for example the third Monday of January."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last given weekday of a month, for example the last Monday of May."""
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    return last_day - timedelta(days=(last_day.weekday() - weekday) % 7)


# date.weekday() values, named so the observed-day logic below reads as prose
SATURDAY = 5
SUNDAY = 6


@dataclass(frozen=True, slots=True)
class Rule:
    """How 6103(a) designates one holiday.

    ``fixed`` is the day of the month, or None when the holiday floats. ``nth`` is
    the nth given weekday of the month, or None when the holiday is the last one.
    Keeping the two shapes in one record means the designation table below reads in
    the order and the wording of 6103(a) itself.
    """

    fixed: int | None
    month: int
    nth: tuple[int, int] | None = None  # (weekday, n)


# 6103(a), in the order and with the wording it uses.
RULES: dict[Holiday, Rule] = {
    Holiday.NEW_YEARS_DAY: Rule(1, 1),  # January 1
    Holiday.MARTIN_LUTHER_KING_JR_DAY: Rule(None, 1, (0, 3)),  # third Monday in January
    Holiday.WASHINGS_BIRTHDAY: Rule(None, 2, (0, 3)),  # third Monday in February
    Holiday.MEMORIAL_DAY: Rule(None, 5, (0, -1)),  # last Monday in May
    Holiday.JUNETEENTH: Rule(19, 6),  # June 19
    Holiday.INDEPENDENCE_DAY: Rule(4, 7),  # July 4
    Holiday.LABOR_DAY: Rule(None, 9, (0, 1)),  # first Monday in September
    Holiday.COLUMBUS_DAY: Rule(None, 10, (0, 2)),  # second Monday in October
    Holiday.VETERANS_DAY: Rule(11, 11),  # November 11
    Holiday.THANKSGIVING_DAY: Rule(None, 11, (3, 4)),  # fourth Thursday in November
    Holiday.CHRISTMAS_DAY: Rule(25, 12),  # December 25
}

MONTHS: dict[Holiday, int] = {
    Holiday.NEW_YEARS_DAY: 1,
    Holiday.MARTIN_LUTHER_KING_JR_DAY: 1,
    Holiday.WASHINGS_BIRTHDAY: 2,
    Holiday.MEMORIAL_DAY: 5,
    Holiday.JUNETEENTH: 6,
    Holiday.INDEPENDENCE_DAY: 7,
    Holiday.LABOR_DAY: 9,
    Holiday.COLUMBUS_DAY: 10,
    Holiday.VETERANS_DAY: 11,
    Holiday.THANKSGIVING_DAY: 11,
    Holiday.CHRISTMAS_DAY: 12,
}


def statutory_date(holiday: Holiday, year: int) -> date:
    """The day 6103(a) designates, before any observed-day shifting."""
    rule = RULES[holiday]
    month = MONTHS[holiday]
    if rule.nth is not None:
        weekday, n = rule.nth
        if n == -1:
            return _last_weekday(year, month, weekday)
        return _nth_weekday(year, month, weekday, n)
    assert rule.fixed is not None, f"{holiday} has neither a fixed day nor a weekday rule"
    return date(year, month, rule.fixed)


@dataclass(frozen=True, slots=True)
class ObservedHoliday:
    """One holiday, as designated and as observed.

    ``statutory_date`` is what 6103(a) says. ``observed_date`` is the day a Monday
    to Friday workweek is actually off, and it equals ``statutory_date`` when no
    shift applies. ``shifted`` exists so a caller can tell an unshifted holiday from
    a shifted one that landed on the same day, which never happens but is cheap to
    assert.
    """

    holiday: Holiday
    statutory_date: date
    observed_date: date
    shifted: bool


def observed(
    holiday: Holiday, year: int, workweek: WorkWeek = WorkWeek.MONDAY_FRIDAY
) -> ObservedHoliday:
    """The statutory date and the observed date for one holiday in one year.

    Monday to Friday: a Saturday moves back to the Friday, a Sunday moves forward to
    the Monday.

    Monday to Saturday: a Saturday does not move at all, because 6103(b) does not
    apply to that workweek, and a Sunday moves *back* to the Saturday before, per
    6103(b)(2) treating Sunday as the regular non-workday.
    """
    statutory = statutory_date(holiday, year)

    if statutory.weekday() == SATURDAY:
        if workweek.saturday_shift_applies:
            return ObservedHoliday(holiday, statutory, statutory - timedelta(days=1), True)
        return ObservedHoliday(holiday, statutory, statutory, False)

    if statutory.weekday() == SUNDAY:
        if workweek.saturday_shift_applies:
            return ObservedHoliday(holiday, statutory, statutory + timedelta(days=1), True)
        return ObservedHoliday(holiday, statutory, statutory - timedelta(days=1), True)

    return ObservedHoliday(holiday, statutory, statutory, False)


def federal_holidays(
    year: int, workweek: WorkWeek = WorkWeek.MONDAY_FRIDAY
) -> tuple[ObservedHoliday, ...]:
    """All eleven legal public holidays for a year, in 6103(a) order."""
    return tuple(observed(h, year, workweek) for h in Holiday)


@dataclass(frozen=True, slots=True)
class TerminalClosures:
    """Per-terminal closure injection, layered over the reference calendar.

    The reference calendar is a default. A terminal's own published hours are the
    fact, and a terminal that works a federal holiday, or closes on an ordinary
    Tuesday, is within its rights and common.

    ``extra_closures`` are additional days, typed with the same
    :class:`~quayline.calendars.closures.ClosureType` vocabulary the carrier policies
    use, so a terminal closure and a carrier rule are the same kind of object and a
    policy can be asked about both.
    """

    terminal: str
    extra_closures: frozenset[tuple[date, ClosureType]] = frozenset()

    def closure_dates(self, year: int) -> frozenset[date]:
        return frozenset(d for d, _ in self.extra_closures if d.year == year)

    def observed_dates(
        self, year: int, workweek: WorkWeek = WorkWeek.MONDAY_FRIDAY
    ) -> frozenset[date]:
        """Every day this terminal is modelled as closed in a year."""
        return frozenset(h.observed_date for h in federal_holidays(year, workweek)) | (
            self.closure_dates(year)
        )


__all__ = [
    "CITATION",
    "HOLIDAY_COUNT",
    "MONDAY_TO_SATURDAY_EXCLUSION",
    "MONTHS",
    "NON_MONDAY_FRIDAY_RULE",
    "RULES",
    "SOURCE",
    "Holiday",
    "ObservedHoliday",
    "Rule",
    "TerminalClosures",
    "WorkWeek",
    "federal_holidays",
    "observed",
    "statutory_date",
]
