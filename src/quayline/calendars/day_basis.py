"""Which days are working days, per carrier and per terminal.

The default is Monday to Friday. That default is wrong for the largest carrier in the
category and nobody notices, because a Saturday dispute under a Monday to Friday
calendar produces a day count that is one short and an invoice that looks
reasonable.

Maersk's published working day basis is Monday to Saturday. Sunday is the only weekly
closure. A carrier working six days a week, in a business where the sixth day is the
busiest, is not an oddity to be corrected. It is the tariff.

The rule resolves per terminal, not per carrier alone

A single carrier does not use one basis at every terminal. Hapag charges California
terminals in working days and every other gateway in calendar days, from the same
table, and the difference is invisible unless you read the day-unit column.

So a basis is looked up terminal first and carrier second, and the carrier default
exists only for terminals nobody has told us about. A per-terminal override is not
a refinement, it is the normal case.

The published tariff prevails over everything here, including this module

Maersk's own tariff says:

    In the event of any discrepancies between the below and our public tariff, the
    public tariff prevails.

That sentence is about the carrier's summary sheet disagreeing with the carrier's
tariff. It applies with more force to us. Every basis in this module is a
transcription, and a transcription of a tariff that the tariff itself says controls
is a convenience, not an authority. Where a dispute turns on the working week, quote
the tariff. Where a dispute turns on the closure, quote the terminal's published
hours. Do not quote this module, and never quote our research corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.calendars.closures import ClosureType

# Maersk's own words about itself. Cited because it is the sentence that makes the
# default wrong.
MAERSK_PRECEDENCE = (
    "In the event of any discrepancies between the below and our public tariff, the "
    "public tariff prevails."
)

MAERSK_WORKING_DAY = (
    "Working Day basis defined as any day a gate is open for container pickup "
    "Monday - Saturday. Partial day closures are considered as a full working day and "
    "count towards freetime."
)


class DayBasis(StrEnum):
    """Which days count as working days."""

    MONDAY_SATURDAY = "monday_saturday"
    MONDAY_FRIDAY = "monday_friday"
    CALENDAR = "calendar"

    def working_weekdays(self) -> frozenset[int]:
        """The date.weekday() values that are working days.

        CALENDAR returns every day, because under a calendar basis nothing is a
        closure. That is the point of the enum, and it is why a caller cannot treat
        CALENDAR as a weekday set and be surprised.
        """
        if self is DayBasis.CALENDAR:
            return frozenset(range(7))
        if self is DayBasis.MONDAY_SATURDAY:
            return frozenset({0, 1, 2, 3, 4, 5})
        return frozenset({0, 1, 2, 3, 4})

    def weekly_closures(self) -> frozenset[int]:
        """The days of the week this basis treats as closed, absent anything else."""
        return frozenset(range(7)) - self.working_weekdays()


@dataclass(frozen=True, slots=True)
class DayBasisRule:
    """One carrier's basis, with per-terminal overrides on top.

    ``terminal_overrides`` is a real part of the type rather than a convention, and a
    test asserts a per-terminal basis can be resolved for a carrier whose default
    differs from it.

    The overrides are a tuple of pairs rather than a dict on purpose. A frozen
    dataclass holding a dict is a lie about immutability: the attribute cannot be
    rebound but the mapping can still be mutated, and a per-terminal basis that
    changes mid audit is precisely the defect this repository exists to prevent. The
    first version of this type had a dict and a test caught it by trying to hash it.
    """

    carrier: str
    default: DayBasis
    source: str
    citation: str
    verified: bool
    terminal_overrides: tuple[tuple[str, DayBasis], ...] = ()
    note: str = ""

    def basis_for(self, terminal: str) -> DayBasis:
        """Terminal first, carrier default second."""
        for code, basis in self.terminal_overrides:
            if code == terminal:
                return basis
        return self.default

    def is_working_day(self, day: date, terminal: str = "") -> bool:
        return day.weekday() in self.basis_for(terminal).working_weekdays()

    def weekly_closure_on(self, day: date, terminal: str = "") -> bool:
        return day.weekday() in self.basis_for(terminal).weekly_closures()


MAERSK_US = DayBasisRule(
    carrier="Maersk",
    default=DayBasis.MONDAY_SATURDAY,
    source="Maersk US demurrage tariff, working day definition",
    citation=MAERSK_WORKING_DAY,
    verified=True,
    note="Sunday is the only weekly closure.",
)

# UNVERIFIED, and the reason is specific rather than a shrug. Hapag's tariff uses the
# notation DOD + 4WD, which tells us free time is counted in working days, and the
# gateway table marks terminals as working or calendar. Neither is a definition of
# which weekdays are working days. Monday to Friday is inferred from the carrier
# excluding weekends in practice and is almost certainly right, and it is not quoted
# from anywhere, so it is marked.
#
# Issue 18's second criterion asks for a Saturday comparison against Maersk, and this
# is the Hapag half of it. Shipping the comparison with this marker attached is more
# useful than shipping a quote we do not have, and a test asserts the marker so it
# cannot be quietly promoted.
HAPAG_US = DayBasisRule(
    carrier="Hapag-Lloyd",
    default=DayBasis.MONDAY_FRIDAY,
    terminal_overrides=(
        ("USLAXB", DayBasis.MONDAY_FRIDAY),
        ("USLAXTP", DayBasis.MONDAY_FRIDAY),
        ("USLGB", DayBasis.MONDAY_FRIDAY),
        ("USOKL", DayBasis.MONDAY_FRIDAY),
        ("USSAVNG", DayBasis.CALENDAR),
        ("USNYC", DayBasis.CALENDAR),
        ("USHOU", DayBasis.CALENDAR),
    ),
    source="UNVERIFIED working week. Terminal day units from the Hapag US gateway table",
    citation=(
        "UNVERIFIED: Hapag-Lloyd free time is denominated in working days, and the gateway "
        "table marks individual terminals as working or calendar day. Neither is a "
        "definition of which weekdays are working days, and no Hapag clause stating a "
        "working week has been transcribed. Monday to Friday is inferred."
    ),
    verified=False,
    note=(
        "Terminal overrides are day UNIT, not working week. A California terminal bills "
        "in working days post free time and a Savannah terminal bills in calendar days. "
        "That is issue 9's subject and this enum is not yet the place to resolve it."
    ),
)

RULES: dict[str, DayBasisRule] = {r.carrier: r for r in (MAERSK_US, HAPAG_US)}


def working_day_count(rule: DayBasisRule, first: date, last: date, terminal: str = "") -> int:
    """Count working days in an inclusive range under one carrier's basis.

    The whole point of this module in one function. The same Saturday is a working
    day under Maersk and not under a Monday to Friday basis, so the same range yields
    different counts, and the difference is a day of demurrage on the invoice.
    """
    if last < first:
        raise ValueError(f"last {last} precedes first {first}")
    working = rule.basis_for(terminal).working_weekdays()
    span = (last - first).days
    # Ask date for its own weekday rather than taking toordinal() % 7.
    #
    # date.toordinal() is 1-based and date.weekday() is 0=Monday, so the two differ
    # by one and ordinal % 7 labels every day as the next day of the week. The
    # first version of this function did that, which excluded Saturday and counted
    # Sunday instead. A whole week total still came to six, because one error
    # replaced the other, and a test asserting only the total passed for entirely
    # the wrong reason.
    return sum(
        1 for offset in range(span + 1) if (first + timedelta(days=offset)).weekday() in working
    )


__all__ = [
    "MAERSK_PRECEDENCE",
    "MAERSK_WORKING_DAY",
    "RULES",
    "ClosureType",
    "DayBasis",
    "DayBasisRule",
    "working_day_count",
]
