"""Hapag-Lloyd: the customs hold, and the part of it that is bad for us.

A customs hold is the cleanest clock stop in the category. Hapag-Lloyd publishes it,
it applies to both haulage modes, and it excludes the hold days from the free time
count rather than merely pausing the meter. There is no argument to have about what
it means.

The complication is not the rule. It is that the rule is good and the surrounding
reality is not, and a tool that reports the win without the rest would be lying by
omission.

What the carrier published, verbatim

From the Detention and Demurrage Tariff Guide for the United States. The language
below appears identically in the May 2026 and the October 2024 editions, which is
stronger provenance than a single dated document, because a rule that survives two
reissues under rewriting is a rule the carrier intends to keep.

    When a container is put on customs hold for no fault of the customer, Hapag-
    Lloyd stops the Line Demurrage/Detention clock and restarts it when the hold is
    released. This policy applies to both Carrier Haulage and Merchant Haulage on-
    carriage.

    If the container is held inside the Marine or Rail Terminal, then the Line
    Demurrage clock begins at the release date. The hold and release dates and all
    days in between are not counted towards free time days. In this case, the
    customer is responsible for any storage charges that are imposed by the terminal
    operator during the hold days. In the instance when Hapag-Lloyd collects
    terminal charges on behalf of the terminal operator, Hapag-Lloyd will invoice
    these pass-through charges to the customer.

    If the container is held by Customs outside the terminal or at a Customs
    warehouse, then the detention clock begins at the release date. The detention
    free time starts the day after the date of customs release. In this case, the
    customer will be responsible for any storage charges that are applied by the
    Warehouse Operator or the government body during the hold days.

Three things the research corpus flattened, corrected here

**The restart anchor is locus dependent, and asymmetric.** The general sentence stops
both the demurrage and the detention clock. The restart sentence does not follow the
same symmetry. Inside the terminal the guide names the *demurrage* clock. Outside the
terminal or at a customs warehouse it names the *detention* clock. So which clock
resumes on release depends on where the container was sitting, and the guide does not
say what happens to the other one. The corpus summarised this as "a customs hold
pauses both clocks", which is right about the stop and wrong about the restart.

**The rule is conditioned on fault.** "for no fault of the customer". A hold the
customer caused, by filing late or by a documentation problem, is outside the policy
entirely. The corpus did not carry the condition.

**Pass-through charges are collected too.** Where Hapag-Lloyd collects terminal
charges on the operator's behalf, it invoices them onward. So the hold is not merely
chargeable, it is chargeable twice over in the worst case, once as the line's own
storage and once as a pass-through.

The adverse side is not a caveat, it is the reason this is worth modelling

Hapag-Lloyd expressly keeps terminal storage chargeable during a customs hold, in both
locus branches. So a hold dispute recovers the *line charge* and not the *storage*.

A customs hold is still worth disputing, and the numbers favour doing so: the line
charge is the one carrying the free time arithmetic, and it is the one the clock stop
actually cancels. But a dispute letter that says "customs hold, charge not owed" and
stops there is asking for the storage to be waived as well, and it will be refused on
the carrier's own published text.

So every finding from this module carries the limit in its own text. A tool that
returns a recovery figure without the limit attached is worse than no tool, because
the number is right and the conclusion drawn from it will not be.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

# Verbatim from the Detention and Demurrage Tariff Guide for the United States.
# Two editions, May 2026 and October 1 2024, both at
# hapag-lloyd.com/content/dam/website/downloads/detention_demurrage/.
# The research corpus held an abridged version of this with an ellipsis in it,
# which is not a verbatim quote, so the full paragraphs are transcribed here.

HAPAG_CUSTOMS_HOLD_EDITION = "May 2026, and identically in the October 1 2024 edition"
HAPAG_CUSTOMS_HOLD_URL = (
    "https://www.hapag-lloyd.com/content/dam/website/downloads/"
    "detention_demurrage/Detention_and_Demurrage_Guide_USA_May_2026.pdf"
)

GENERAL_TERM = (
    "When a container is put on customs hold for no fault of the customer, Hapag-Lloyd "
    "stops the Line Demurrage/Detention clock and restarts it when the hold is released. "
    "This policy applies to both Carrier Haulage and Merchant Haulage on-carriage."
)

CONDITION = "for no fault of the customer"

INSIDE_TERMINAL_TERM = (
    "If the container is held inside the Marine or Rail Terminal, then the Line Demurrage "
    "clock begins at the release date. The hold and release dates and all days in between "
    "are not counted towards free time days. In this case, the customer is responsible for "
    "any storage charges that are imposed by the terminal operator during the hold days. In "
    "the instance when Hapag-Lloyd collects terminal charges on behalf of the terminal "
    "operator, Hapag-Lloyd will invoice these pass-through charges to the customer."
)

OUTSIDE_TERMINAL_TERM = (
    "If the container is held by Customs outside the terminal or at a Customs warehouse, "
    "then the detention clock begins at the release date. The detention free time starts "
    "the day after the date of customs release. In this case, the customer will be "
    "responsible for any storage charges that are applied by the Warehouse Operator or the "
    "government body during the hold days."
)


class HoldLocus(StrEnum):
    """Where the container was sitting while held.

    Not a detail. It selects which clock restarts, and the guide treats the two
    branches differently.
    """

    INSIDE_TERMINAL = "inside_terminal"
    OUTSIDE_TERMINAL = "outside_terminal"


class RestartClock(StrEnum):
    """Which clock the guide says resumes on release."""

    DEMURRAGE = "demurrage"
    DETENTION = "detention"


# What the clock stop is worth, stated in the module so no caller can report a
# recovery without it. A customs hold dispute recovers the line charge.
RECOVERY_LIMIT = (
    "recovers the line charge only. Terminal or warehouse storage incurred during the "
    "hold stays chargeable under the carrier's own published terms, and where the carrier "
    "collects those charges on the operator's behalf it invoices them onward as "
    "pass-through."
)


@dataclass(frozen=True, slots=True)
class HoldWindow:
    """A customs hold. Both endpoints are days the customer can see on the paperwork."""

    start: date
    release: date

    def __post_init__(self) -> None:
        if self.release < self.start:
            raise ValueError(f"hold released {self.release} before it started {self.start}")

    @property
    def days(self) -> int:
        """Inclusive of both endpoints, because both are days the container was held."""
        return (self.release - self.start).days + 1

    def overlaps(self, first: date, last: date) -> int:
        """Days of the hold falling inside an inclusive date range."""
        start = max(self.start, first)
        end = min(self.release, last)
        return max(0, (end - start).days + 1)


@dataclass(frozen=True, slots=True)
class Finding:
    """A customs hold that stops a clock, carrying what it is worth."""

    locus: HoldLocus
    clock: RestartClock
    restart_on: date
    hold_days: int
    free_time_days_lost_to_hold: int
    text: str
    recovery_limit: str
    citation: str

    def describe(self) -> str:
        return f"{self.citation} {self.text} This {self.recovery_limit}"


def customs_hold(
    hold: HoldWindow,
    locus: HoldLocus,
    free_time_days: int,
    clock_started: date,
    *,
    no_fault_of_customer: bool = True,
) -> Finding | None:
    """Assess a customs hold on a Hapag-Lloyd charge.

    ``clock_started`` is the day free time began accruing before the hold.
    ``free_time_days`` is the allowance. The hold is exclusive of the free time count,
    so free time is not consumed while the container is held and the clock resumes at
    release.

    Returns None when the policy does not apply. The guide conditions the whole policy
    on the hold being "for no fault of the customer", so a customer-caused hold is
    outside it and no clock stops.

    ``free_time_days_lost_to_hold`` is how many days of the allowance the hold would
    have consumed had it counted. When the hold spans the whole free time window the
    answer is the full allowance and nothing is chargeable, which is the strongest form
    of this argument and the case worth testing.
    """
    if not no_fault_of_customer:
        return None

    clock = RestartClock.DEMURRAGE if locus is HoldLocus.INSIDE_TERMINAL else RestartClock.DETENTION
    free_time_window_end = clock_started + timedelta(days=free_time_days - 1)
    lost = hold.overlaps(clock_started, free_time_window_end)

    if locus is HoldLocus.INSIDE_TERMINAL:
        text = (
            f"the container was held inside the Marine or Rail Terminal from "
            f"{hold.start.isoformat()} to {hold.release.isoformat()}, {hold.days} days, so "
            f"the Line Demurrage clock begins at the release date {hold.release.isoformat()} "
            f"and the hold and release dates and all days in between are not counted "
            f"towards free time days. {lost} of {free_time_days} free time days fall "
            f"inside the hold and are not chargeable."
        )
        citation = "Hapag-Lloyd D&D Guide, Demurrage Under Customs Hold"
    else:
        text = (
            f"the container was held by Customs outside the terminal or at a Customs "
            f"warehouse from {hold.start.isoformat()} to {hold.release.isoformat()}, "
            f"{hold.days} days, so the detention clock begins at the release date "
            f"{hold.release.isoformat()} and the detention free time starts the day after "
            f"the date of customs release. {lost} of {free_time_days} free time days fall "
            f"inside the hold and are not chargeable."
        )
        citation = "Hapag-Lloyd D&D Guide, Demurrage Under Customs Hold"

    return Finding(
        locus=locus,
        clock=clock,
        restart_on=hold.release,
        hold_days=hold.days,
        free_time_days_lost_to_hold=lost,
        text=text,
        recovery_limit=RECOVERY_LIMIT,
        citation=citation,
    )


# Which clock restarts, by locus, and nothing else. The guide's stop sentence names
# both; its restart sentences do not, and the two branches name different ones.
RESTART_BY_LOCUS: dict[HoldLocus, RestartClock] = {
    HoldLocus.INSIDE_TERMINAL: RestartClock.DEMURRAGE,
    HoldLocus.OUTSIDE_TERMINAL: RestartClock.DETENTION,
}

__all__ = [
    "CONDITION",
    "GENERAL_TERM",
    "HAPAG_CUSTOMS_HOLD_EDITION",
    "HAPAG_CUSTOMS_HOLD_URL",
    "INSIDE_TERMINAL_TERM",
    "OUTSIDE_TERMINAL_TERM",
    "RECOVERY_LIMIT",
    "RESTART_BY_LOCUS",
    "Finding",
    "HoldLocus",
    "HoldWindow",
    "RestartClock",
    "customs_hold",
]
