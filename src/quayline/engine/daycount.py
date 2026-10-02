"""Recompute a chargeable window from the invoice's own disclosures.

This is the highest yield check in the product and it needs no tariff data. The
carrier has already told us the allowance, the day free time started, the day it
ended, and every day it charged for. Those four statements plus a gate calendar are
enough to work out what it should have charged, and where the two differ, the
difference is a list of dates.

That is the whole product in one comparison. No rate lookup, no terminal data, no
carrier relationship, and no request for a terminal to correct its own records.

    541.6(b)(3)  the allowed free time in days
    541.6(b)(4)  the start date of free time
    541.6(b)(5)  the end date of free time
    541.6(b)(8)  the specific dates for which demurrage and/or detention were charged

Both directions are reported, and that is not politeness

The comparison is symmetric. Days the carrier charged that the disclosures do not
support are overbilled. Days the disclosures require and the carrier did not charge
are underbilled, which is in the customer's favour and is reported anyway.

A checker that only reports the favourable direction is a checker nobody believes,
because the customer can do that comparison themselves and see a zero. The value
here is that the underbilled set is also evidence. A carrier that underbills on one
invoice and overbills on another is doing the second deliberately, and a tool that
hides the first is hiding the evidence of that.

The recomputation uses the declared start and the declared allowance, not the
declared end

    free time end   recomputed from (b)(4) and (b)(3) under the carrier's basis
    chargeable days every day after that, that the carrier's day unit can bill
    compare         the recomputed set against the billed set from (b)(8)

The declared end under (b)(5) is then a cross check rather than an input. If the
carrier's stated end disagrees with the end its own start and allowance imply, that
is a 541.6 accuracy and sufficiency failure in its own right, and it is reported
separately, because a carrier that misstates the end is a carrier whose start
should be questioned too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.calendars.day_basis import RULES as DAY_BASIS_RULES
from quayline.calendars.freetime import free_time
from quayline.calendars.window import UNITS as CARRIER_UNITS
from quayline.calendars.window import charge_window
from quayline.models.invoice import (
    CITE_ALLOWANCE,
    CITE_CHARGED_DATES,
    CITE_FREE_TIME_END,
    CITE_FREE_TIME_START,
    TimingDisclosures,
)

CITE_ACCURACY = "46 CFR 541.6(a)"


class Direction(StrEnum):
    OVERBILLED = "overbilled"
    UNDERBILLED = "underbilled"
    STATED_VS_RECOMPUTED = "stated_versus_recomputed"
    CLEAN = "clean"


@dataclass(frozen=True, slots=True)
class Discrepancy:
    """A set of dates that do not reconcile, and which way."""

    direction: Direction
    dates: tuple[date, ...]
    detail: str
    citation: str

    @property
    def count(self) -> int:
        return len(self.dates)

    def as_letter_lines(self) -> list[str]:
        if self.direction is Direction.CLEAN:
            return [f"The invoice is internally consistent across {self.citation}."]
        if self.direction is Direction.STATED_VS_RECOMPUTED:
            return [
                f"{self.citation} {self.detail}.",
            ]
        head = (
            f"{self.citation} {self.detail} {self.count} day(s):"
            if self.direction is Direction.OVERBILLED
            else f"{self.citation} {self.detail} {self.count} day(s), in the customer's favour:"
        )
        return [head, *(f"  {d.isoformat()}" for d in self.dates)]


@dataclass(frozen=True, slots=True)
class DayCountResult:
    """Everything the recomputation found, including the clean case."""

    carrier: str
    terminal: str
    #: When free time starts, as stated. Added in issue 189 so a renderer can draw
    #: every day of the stay rather than deriving the start by counting backwards
    #: from the first chargeable day, which is a guess.
    free_time_start: date
    declared_free_time_end: date
    recomputed_free_time_end: date
    expected_dates: tuple[date, ...]
    billed_dates: tuple[date, ...]
    discrepancies: tuple[Discrepancy, ...]

    @property
    def overbilled(self) -> Discrepancy | None:
        return self._find(Direction.OVERBILLED)

    @property
    def underbilled(self) -> Discrepancy | None:
        return self._find(Direction.UNDERBILLED)

    @property
    def free_time_end_disagrees(self) -> bool:
        return self.declared_free_time_end != self.recomputed_free_time_end

    def _find(self, direction: Direction) -> Discrepancy | None:
        return next((d for d in self.discrepancies if d.direction is direction), None)

    @property
    def clean(self) -> bool:
        """No overbilling, no underbilling, and the stated end agrees.

        The last part is included deliberately. An invoice whose day set reconciles
        but whose stated free time end does not is not clean, and a result object
        that said it was would be the kind of clean that hides a problem.
        """
        return not self.discrepancies

    @property
    def day_set_reconciles(self) -> bool:
        """Whether the billed days match, ignoring the stated-end cross check.

        Separated from ``clean`` so a caller can distinguish a carrier that got the
        arithmetic right from one that also stated it correctly.
        """
        return not any(
            d.direction in (Direction.OVERBILLED, Direction.UNDERBILLED) for d in self.discrepancies
        )

    def as_letter(self) -> str:
        lines = [
            f"Day count recomputed from the invoice's own disclosures under "
            f"{CITE_FREE_TIME_START}, {CITE_ALLOWANCE} and {CITE_CHARGED_DATES}.",
            f"Free time stated as ending {self.declared_free_time_end.isoformat()}, "
            f"recomputed to end {self.recomputed_free_time_end.isoformat()}.",
        ]
        if self.clean:
            lines.append("The billed days reconcile with the stated allowance.")
            return "\n".join(lines)
        for discrepancy in self.discrepancies:
            lines.extend(discrepancy.as_letter_lines())
        return "\n".join(lines)


def recompute(
    disclosures: TimingDisclosures,
    carrier: str,
    *,
    terminal: str = "",
    extra_excluded: frozenset[date] = frozenset(),
) -> DayCountResult:
    """Recompute the chargeable window and compare it against what was billed.

    ``carrier`` selects the basis, the day unit and the closure policy. It is a
    parameter rather than something read off the invoice because 541.6 never asks a
    carrier to name itself on the invoice's face, and inferring it is the ingest
    issue's problem, not this one's.
    """
    if carrier not in DAY_BASIS_RULES:
        raise KeyError(f"no day basis rule for carrier {carrier!r}")
    if carrier not in CARRIER_UNITS:
        raise KeyError(f"no day unit record for carrier {carrier!r}")

    # 1. The free time end, recomputed from the start and the allowance.
    ft = free_time(
        carrier,
        disclosures.free_time_start,
        disclosures.allowed_free_time_days,
        terminal=terminal,
    )
    recomputed_end = ft.last_free_day

    # 2. Every day after that which this carrier's day unit can bill, out to the
    #    last day it actually charged for.
    last = disclosures.last_charged_day
    if last <= recomputed_end:
        # Nothing should be chargeable at all. Any billed date is an overbill, and
        # the window is empty, which is the honest representation.
        expected: frozenset[date] = frozenset()
    else:
        window = charge_window(
            carrier,
            recomputed_end + timedelta(days=1),
            last,
            terminal=terminal,
            extra_excluded=extra_excluded,
        )
        expected = frozenset(r.day for r in window.chargeable)

    billed = frozenset(disclosures.charged_dates)
    over = tuple(sorted(billed - expected))
    under = tuple(sorted(expected - billed))
    days_early = tuple(sorted(d for d in billed if d <= recomputed_end))

    discrepancies: list[Discrepancy] = []

    if days_early:
        discrepancies.append(
            Discrepancy(
                direction=Direction.OVERBILLED,
                dates=days_early,
                detail=(
                    f"were charged although the stated allowance under {CITE_ALLOWANCE} "
                    f"exhausted on {recomputed_end.isoformat()}"
                ),
                citation=CITE_CHARGED_DATES,
            )
        )

    late = tuple(d for d in over if d not in days_early)
    if late:
        discrepancies.append(
            Discrepancy(
                direction=Direction.OVERBILLED,
                dates=late,
                detail=(
                    f"are not chargeable under this carrier's day unit at "
                    f"{terminal or 'the unspecified terminal'}"
                ),
                citation=CITE_ACCURACY,
            )
        )

    if under:
        discrepancies.append(
            Discrepancy(
                direction=Direction.UNDERBILLED,
                dates=under,
                detail=(
                    f"follow the stated allowance under {CITE_ALLOWANCE} and the stated "
                    f"start under {CITE_FREE_TIME_START}, so this carrier did not charge"
                ),
                citation=CITE_CHARGED_DATES,
            )
        )

    if disclosures.free_time_end != recomputed_end:
        discrepancies.append(
            Discrepancy(
                direction=Direction.STATED_VS_RECOMPUTED,
                dates=(disclosures.free_time_end, recomputed_end),
                detail=(
                    f"states the free time end as {disclosures.free_time_end.isoformat()}, "
                    f"which its own start under {CITE_FREE_TIME_START} and allowance under "
                    f"{CITE_ALLOWANCE} do not support"
                ),
                citation=f"{CITE_FREE_TIME_END}, {CITE_ACCURACY}",
            )
        )

    return DayCountResult(
        carrier=carrier,
        terminal=terminal,
        free_time_start=disclosures.free_time_start,
        declared_free_time_end=disclosures.free_time_end,
        recomputed_free_time_end=recomputed_end,
        expected_dates=tuple(sorted(expected)),
        billed_dates=tuple(sorted(billed)),
        discrepancies=tuple(discrepancies),
    )


__all__ = [
    "CITE_ACCURACY",
    "DayCountResult",
    "Direction",
    "Discrepancy",
    "TimingDisclosures",
    "recompute",
]
