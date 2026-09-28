"""The charge window: which days a carrier can bill, enumerated.

Free time and post free time are denominated in different units, and the unit
changes by terminal. Both halves of that sentence matter and the second half is the
one that is invisible.

Hapag's tariff free time is working days at every gateway. A four day allowance is
"DOD + 4WD" whether the container is in Savannah or Los Angeles. The post free time
tier is a different unit at different terminals, and that is where the money is.

    Savannah GA, USSAVNG   DOD + 4WD   3CD    calendar day tiers
    Los Angeles APMT,      DOD + 4WD   3WD    working day tiers
    Long Beach all, USLGB  DOD + 4WD   3WD    working day tiers
    Oakland OICT, USOKL    DOD + 4WD   3WD    working day tiers
    New York, USNYC        DOD + 4WD   3CD    calendar day tiers
    Houston, USHOU         DOD + 4WD   3CD    calendar day tiers

Same carrier, same allowance, same weekend. In Savannah the weekend costs two days
at the tier rate. In Los Angeles it costs nothing. A container sitting over a
Saturday and a Sunday is a two day charge in Georgia and a zero day charge in
California, and the only place that difference appears is a column labelled "tier
unit" in a table nobody reads to the bottom.

That is the California trap, and it is worth a day count on a real dispute.

DayUnit is a separate type from DayBasis, on purpose

``DayBasis`` in day_basis.py answers "which weekdays are working days for this
carrier". ``DayUnit`` here answers "which kind of day is chargeable at this terminal
after free time has expired". They are different questions with different answers and
for Maersk they have different scopes, one per carrier and one per terminal.

Overloading one field for both is the obvious move and it was flagged in review of
issue 18 as the next mistake waiting to happen. A California terminal bills post free
time in working days and a Savannah terminal in calendar days, which is a unit
question sitting on top of a working week question, and conflating them produces a
count that is wrong without looking wrong.

Every day is enumerated, never inferred from a total

The window returns a row per day with a chargeable flag and a reason. Not a count.
A count cannot be disputed, audited, or shown to a carrier, and the whole value of
this product is a letter a third party can check.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.calendars.day_basis import RULES as DAY_BASIS_RULES
from quayline.calendars.day_basis import DayBasisRule
from quayline.calendars.holidays import FEDERAL_DEFAULT, Holiday, HolidayPolicy

CITATION_HAPAG = (
    "Hapag charges California terminals in working days and every other gateway in "
    "calendar days. The same table shows it."
)
CITATION_MAERSK = (
    "Working Day basis defined as any day a gate is open for container pickup Monday - Saturday."
)


class DayUnit(StrEnum):
    """Which kind of day is chargeable. Separate from the working week by design."""

    WORKING = "working"
    CALENDAR = "calendar"


@dataclass(frozen=True, slots=True)
class CarrierUnits:
    """A carrier's free time unit and its post free time unit, with terminal overrides.

    ``terminal_tier_units`` is a tuple of pairs rather than a dict for the same
    reason as in day_basis: a frozen dataclass holding a dict is a lie about
    immutability, and a per-terminal unit that changes mid audit is the defect this
    repository exists to prevent.
    """

    carrier: str
    free_time_unit: DayUnit
    tier_unit_default: DayUnit
    source: str
    citation: str
    verified: bool
    terminal_tier_units: tuple[tuple[str, DayUnit], ...] = ()
    #: Which federal holiday dates close this carrier's gate.
    #:
    #: It lives here for the same reason the terminal tiers do. A carrier that works
    #: federal holidays, or one on a Monday to Saturday workweek where the Saturday
    #: holiday is the date that bites, is a different fact about that carrier, and a
    #: global default made both of them a code change. Defaulted so a carrier that has
    #: not said anything gets the shipped conservative behaviour.
    holidays: HolidayPolicy = FEDERAL_DEFAULT

    def tier_unit_for(self, terminal: str) -> DayUnit:
        for code, unit in self.terminal_tier_units:
            if code == terminal:
                return unit
        return self.tier_unit_default


# Hapag, transcribed from the US gateway table. Free time is working days everywhere
# on this table, which is the point: the allowance does not change by terminal, the
# unit it is charged in does.
HAPAG = CarrierUnits(
    carrier="Hapag-Lloyd",
    free_time_unit=DayUnit.WORKING,
    tier_unit_default=DayUnit.CALENDAR,
    source="Hapag-Lloyd US gateway table, free time and tier unit columns",
    citation=CITATION_HAPAG,
    verified=True,
    terminal_tier_units=(
        ("USLAXB", DayUnit.WORKING),
        ("USLAXTP", DayUnit.WORKING),
        ("USLGB", DayUnit.WORKING),
        ("USOKL", DayUnit.WORKING),
        ("USSAVNG", DayUnit.CALENDAR),
        ("USNYC", DayUnit.CALENDAR),
        ("USHOU", DayUnit.CALENDAR),
    ),
)

# Maersk converted to calendar day charging US wide on 2024-08-08 with no
# exceptions, per the research corpus. So the post free time unit is calendar at
# every Maersk terminal, which is the opposite of Hapag's pattern and the reason a
# single field cannot carry both carriers.
MAERSK = CarrierUnits(
    carrier="Maersk",
    free_time_unit=DayUnit.WORKING,
    tier_unit_default=DayUnit.CALENDAR,
    source="Maersk US demurrage tariff, calendar day charging from 2024-08-08",
    citation=CITATION_MAERSK,
    verified=True,
)

UNITS: dict[str, CarrierUnits] = {u.carrier: u for u in (HAPAG, MAERSK)}


@dataclass(frozen=True, slots=True)
class DayRow:
    """One day of the window, and whether it can be billed."""

    day: date
    chargeable: bool
    reason: str

    def as_letter_line(self) -> str:
        verdict = "chargeable" if self.chargeable else "excluded"
        return f"{self.day.isoformat()}  {verdict}  {self.reason}"


@dataclass(frozen=True, slots=True)
class ChargeWindow:
    """An inclusive span of days, every one classified.

    ``chargeable`` and ``excluded`` are separate tuples rather than one list with a
    flag, because the acceptance criterion asks for them separately and because a
    dispute letter needs the excluded days with their reasons, not the survivors.
    """

    carrier: str
    terminal: str
    unit: DayUnit
    rows: tuple[DayRow, ...]

    @property
    def chargeable(self) -> tuple[DayRow, ...]:
        return tuple(r for r in self.rows if r.chargeable)

    @property
    def excluded(self) -> tuple[DayRow, ...]:
        return tuple(r for r in self.rows if not r.chargeable)

    @property
    def chargeable_count(self) -> int:
        return len(self.chargeable)

    def as_letter(self) -> str:
        """A block a dispute letter could carry verbatim."""
        lines = [
            f"{self.carrier} at {self.terminal or 'unspecified terminal'}, "
            f"post free time unit {self.unit.value}, "
            f"{self.chargeable_count} of {len(self.rows)} days chargeable"
        ]
        lines.extend(row.as_letter_line() for row in self.rows)
        return "\n".join(lines)


def free_time_window(carrier: str, first: date, last: date, *, terminal: str = "") -> ChargeWindow:
    """The free time window, where nothing is chargeable by anyone.

    A separate function rather than a flag on ``charge_window``. A caller who is
    counting chargeable days is doing something different from a caller checking an
    allowance, and the two should not look alike at the call site.
    """
    if last < first:
        raise ValueError(f"last {last} precedes first {first}")
    units = UNITS[carrier]
    unit = units.tier_unit_for(terminal)
    rows = tuple(
        DayRow(first + timedelta(days=offset), False, "inside the free time allowance")
        for offset in range((last - first).days + 1)
    )
    return ChargeWindow(carrier=carrier, terminal=terminal, unit=unit, rows=rows)


def charge_window(
    carrier: str,
    first: date,
    last: date,
    *,
    terminal: str = "",
    extra_excluded: frozenset[date] = frozenset(),
) -> ChargeWindow:
    """Enumerate a post free time span day by day under a carrier's tier unit.

    Days excluded here: federal holidays on their observed and statutory dates,
    weekly closures when the unit is working, and anything in ``extra_excluded``,
    which is where a caller puts a terminal closure it has been told about.
    """
    if last < first:
        raise ValueError(f"last {last} precedes first {first}")

    units = UNITS[carrier]
    unit = units.tier_unit_for(terminal)
    basis: DayBasisRule = DAY_BASIS_RULES[carrier]

    # CLOSURE_POLICY_FOR is deliberately not consulted here, and the first version
    # of this function looked it up and then did not use it, which is how the reason
    # got written down.
    #
    # The day unit and the closure policy are different mechanisms and they can
    # disagree, which is exactly why merging them would be wrong. A Saturday at a
    # Hapag California terminal is not chargeable because the unit is working days
    # and Saturday is not one, not because the carrier forgives weekends. Hapag does
    # not forgive weekends after free time. Both statements are true and they are
    # about different things, and a checker that reached for the closure policy to
    # answer the working-week question would get Saturday backwards.
    working_week = basis.basis_for(terminal).working_weekdays()
    holidays_closed = units.holidays.dates_closed(first.year) | units.holidays.dates_closed(
        last.year
    )

    rows: list[DayRow] = []
    for offset in range((last - first).days + 1):
        day = first + timedelta(days=offset)

        if day in extra_excluded:
            rows.append(DayRow(day, False, "terminal closure"))
            continue
        if day in holidays_closed:
            rows.append(DayRow(day, False, f"federal holiday, observed {day.isoformat()}"))
            continue
        if unit is DayUnit.CALENDAR:
            rows.append(DayRow(day, True, "calendar day basis, no weekly exclusion"))
            continue
        if day.weekday() not in working_week:
            rows.append(DayRow(day, False, "weekly closure under this carrier's working week"))
            continue
        rows.append(DayRow(day, True, "working day and the gate was open"))

    return ChargeWindow(carrier=carrier, terminal=terminal, unit=unit, rows=tuple(rows))


__all__ = [
    "HAPAG",
    "MAERSK",
    "UNITS",
    "CarrierUnits",
    "ChargeWindow",
    "DayRow",
    "DayUnit",
    "Holiday",
    "charge_window",
    "free_time_window",
]
