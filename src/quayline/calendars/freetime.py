"""Free time, extended for the closures the carrier forgives.

This is where the calendar layer stops being four modules that each know something
and becomes an answer.

Hapag's rule, in the carrier's own words, from the May 2026 D&D Guide: bank
holidays and shutout days are excluded from free time calculations and free days
are extended by the corresponding number of days.

So a bank holiday in the middle of an allowance does not consume one of the
allowance's days. It pushes the expiry out by one, and the container sits there
another day for nothing. That is an extension, not a discount, and the difference
matters because the extension is what produces the expiry date the carrier then
bills from.

And then the asymmetry, which is the whole reason this is worth modelling

Once the allowance is gone, the carrier bills calendar days, and:

    an UNSCHEDULED shutout is still forgiven
    a SCHEDULED closure is charged

Same closed gate, opposite treatment, decided by who planned it. An unscheduled
shutout extends the window and is then never billed. A scheduled closure does not
extend the window and is billed from the moment the allowance runs out. The corpus
puts it exactly right: the asymmetry is the rule.

How the walk works

Day by day from the start, classifying each one and either counting it or skipping
it:

    a day that is not a working day under this carrier's basis is skipped
    a working day the carrier forgives is skipped and extends the window
    anything else counts toward the allowance

The order matters and the second case is the interesting one. A Saturday under
Hapag is not a working day, so it is skipped, and it is not a forgiven closure, so
it is not reported as an extension. A Saturday under Maersk IS a working day, so
it counts outright. Same day, two carriers, and the difference is the Mon to Sat
basis from issue 18 showing up in a free time expiry date.

Every day is reported with its verdict and its reason, and never collapsed to a
count, because the count is not the answer. The answer is a date a carrier agreed
to, and a dispute letter has to be able to show how it was reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.calendars.closures import CLOSURE_POLICY_FOR, ClosurePolicy, ClosureType
from quayline.calendars.day_basis import RULES as DAY_BASIS_RULES
from quayline.calendars.day_basis import DayBasisRule
from quayline.calendars.holidays import federal_holidays

CARRIER_HAPAG = "Hapag-Lloyd"
CARRIER_MAERSK = "Maersk"

CITATION_HAPAG_FREE_TIME = (
    "Bank holidays and shutout days are excluded from free time calculations, and free "
    "days are extended by the corresponding number of days."
)
CITATION_HAPAG_POST = (
    "Any unscheduled closures of relevant terminals and depots will be treated as "
    "unforeseen shutout days and will be excluded from Detention and Demurrage charge "
    "assessments."
)


class Verdict(StrEnum):
    """What happened to a day on the way to the expiry date."""

    COUNTED = "counted"
    SKIPPED_NOT_A_WORKING_DAY = "skipped_not_a_working_day"
    EXTENDED = "extended"


@dataclass(frozen=True, slots=True)
class DayNote:
    """One day on the walk, with the reason it did or did not count."""

    day: date
    verdict: Verdict
    reason: str
    closure: ClosureType | None = None

    def as_letter_line(self) -> str:
        return f"{self.day.isoformat()}  {self.verdict.value:26}  {self.reason}"


@dataclass(frozen=True, slots=True)
class FreeTimeResult:
    """The expiry date, and the walk that produced it."""

    carrier: str
    terminal: str
    start: date
    allowance_days: int
    last_free_day: date
    counted_days: int
    extension_days: int
    notes: tuple[DayNote, ...]

    def notes_for(self, verdict: Verdict) -> tuple[DayNote, ...]:
        return tuple(n for n in self.notes if n.verdict is verdict)

    def as_letter(self) -> str:
        lines = [
            f"{self.carrier} at {self.terminal or 'unspecified terminal'}, "
            f"free time {self.allowance_days} working days from {self.start.isoformat()}",
            f"last free day {self.last_free_day.isoformat()}, "
            f"extended by {self.extension_days} day(s) for forgiven closures",
        ]
        lines.extend(n.as_letter_line() for n in self.notes)
        return "\n".join(lines)


def _holidays_for(year: int) -> dict[date, ClosureType]:
    """Both the observed and the statutory date of every federal holiday.

    A Monday to Friday workweek observes a Saturday holiday on the Friday, so the
    observed date is the one the gate is shut. A carrier working Monday to Saturday
    has the Saturday as a working day, so the statutory date is the one that bites.
    Carrying both means the caller does not have to know which regime it is in.
    """
    out: dict[date, ClosureType] = {}
    for holiday in federal_holidays(year):
        out[holiday.observed_date] = ClosureType.HOLIDAY
        out.setdefault(holiday.statutory_date, ClosureType.HOLIDAY)
    return out


def free_time(
    carrier: str,
    start: date,
    allowance_days: int,
    *,
    terminal: str = "",
    extra_closures: frozenset[tuple[date, ClosureType]] = frozenset(),
) -> FreeTimeResult:
    """Walk forward from ``start`` until ``allowance_days`` working days are counted.

    ``start`` is day one, matching the carrier notation DOD + 4WD where the
    discharge day is day zero and the fourth working day after it is the last free
    day. The day itself is not counted; the walk begins the following day.

    ``extra_closures`` is where a caller puts closures it has been told about, a
    terminal's own calendar or a customs hold, typed with the same vocabulary the
    carrier policies use so the policy can be asked about it.
    """
    if allowance_days < 1:
        raise ValueError(f"allowance must be at least one day, got {allowance_days}")

    basis: DayBasisRule = DAY_BASIS_RULES[carrier]
    policy: ClosurePolicy = CLOSURE_POLICY_FOR[carrier]
    working_week = basis.basis_for(terminal).working_weekdays()

    # Two years of holidays, because a December start walks into January.
    holidays: dict[date, ClosureType] = {}
    for year in range(start.year, start.year + 2):
        holidays.update(_holidays_for(year))
    injected = dict(extra_closures)

    notes: list[DayNote] = []
    counted = 0
    extended = 0
    day = start
    last_counted = start

    while counted < allowance_days:
        day = day + timedelta(days=1)
        closure = holidays.get(day) or injected.get(day)

        if day.weekday() not in working_week:
            notes.append(
                DayNote(
                    day,
                    Verdict.SKIPPED_NOT_A_WORKING_DAY,
                    "not a working day under this carrier's basis",
                )
            )
            continue

        if closure is not None and policy.forgives(closure):
            extended += 1
            notes.append(
                DayNote(
                    day,
                    Verdict.EXTENDED,
                    f"{closure.value} forgiven, free time extended by one day",
                    closure,
                )
            )
            continue

        counted += 1
        last_counted = day
        reason = (
            f"{closure.value} not forgiven by this carrier, so it counts"
            if closure is not None
            else "working day, gate open"
        )
        notes.append(DayNote(day, Verdict.COUNTED, reason, closure))

    return FreeTimeResult(
        carrier=carrier,
        terminal=terminal,
        start=start,
        allowance_days=allowance_days,
        last_free_day=last_counted,
        counted_days=counted,
        extension_days=extended,
        notes=tuple(notes),
    )


def post_expiry_charged(carrier: str, closure: ClosureType) -> bool:
    """Whether a closure of this kind is billed once the allowance is spent.

    The asymmetry, as a function. Hapag forgives an unscheduled shutout forever and
    charges a scheduled one from the moment the allowance runs out, which is the
    rule the corpus calls the whole point.

    No date argument, deliberately. Whether a scheduled closure is forgiven does not
    depend on when it happened, only on what kind it was, and an earlier version
    took a date and ignored it. If a rule ever does turn out to depend on the date,
    that is a change in the carrier's policy and the policy table is where it
    belongs.
    """
    return not CLOSURE_POLICY_FOR[carrier].forgives(closure, after_free_time=True)


__all__ = [
    "CARRIER_HAPAG",
    "CARRIER_MAERSK",
    "CITATION_HAPAG_FREE_TIME",
    "CITATION_HAPAG_POST",
    "DayNote",
    "FreeTimeResult",
    "Verdict",
    "free_time",
    "post_expiry_charged",
]
