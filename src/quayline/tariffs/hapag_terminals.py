"""Hapag-Lloyd per-terminal demurrage schedules, issue 13.

Hapag is the only carrier publishing per-terminal granularity, so it is the
reference implementation everyone else maps onto. Source:
USA_CH_Port_Demurrage_Import_Effective_August_01_2025.pdf, effective 2025-08-01,
published 2025-06-27.

What is recorded here and what is not

Every terminal below carries its free-time notation, its free-time basis, and its
charge basis per the gateway table. Those three are transcribed and verified.

The **rate tiers are not transcribed**. The research holds spot rates —
Savannah 40 foot dry at $265, $350, $515 and New York at $625, $970, $1330 —
without the day ranges that would make them contiguous tiers, and a tier without
day ranges is a number without a meaning. So no `RateBlock` exists for any Hapag
terminal yet, and the resolver returns nothing for Hapag until one does.

That is deliberate and it is the same rule as everywhere else in this repository:
a plausible wrong rate is worse than a hole. The schedules below are priced at
nothing, resolve to nothing, and are still worth holding, because the free-time
basis and the tier unit are what make a weekend cost nothing in Los Angeles and
two days at the tier rate in Savannah, and that distinction is invisible unless
you read the day-unit column.

The contiguity checker in this module is tested against the Maersk corpus, which
does hold transcribed tiers. The mechanism is proven where the data exists, and
waits where it does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from quayline.tariffs.blocks import Tier

#: The source. One PDF, one effective date, one publish date.
SOURCE_PDF = "USA_CH_Port_Demurrage_Import_Effective_August_01_2025.pdf"
EFFECTIVE_DATE = "2025-08-01"
PUBLISHED_DATE = "2025-06-27"


class TierUnit(StrEnum):
    """What a post-free-time day is counted in."""

    #: Calendar days. A weekend costs two days at the tier rate.
    CALENDAR = "calendar"
    #: Working days. A weekend in California accrues nothing.
    WORKING = "working"


@dataclass(frozen=True, slots=True)
class TerminalSchedule:
    """One terminal's demurrage schedule, without rates.

    `free_time` is the notation as published, e.g. "DOD + 4WD": discharge plus
    four working days. `tier_unit` is what a chargeable day is counted in. Neither
    is a rate, and neither can price anything, which is why this type has no tiers
    and no amount. It answers "how are days counted here" and nothing else.
    """

    terminal: str
    code: str
    free_time: str
    tier_unit: TierUnit
    source_pdf: str = SOURCE_PDF
    effective_date: str = EFFECTIVE_DATE

    @property
    def working_day_charging(self) -> bool:
        """Whether post-free-time days are working days rather than calendar days."""
        return self.tier_unit is TierUnit.WORKING


#: The nine required terminals, plus Seattle SSA from the same table. Every row
#: transcribed from the gateway table, nothing inferred.
SCHEDULES: tuple[TerminalSchedule, ...] = (
    TerminalSchedule("Savannah GA", "USSVNG", "DOD + 4WD", TierUnit.CALENDAR),
    TerminalSchedule("Los Angeles APMT", "USLAXB", "DOD + 4WD", TierUnit.WORKING),
    TerminalSchedule("Los Angeles Trapac", "USLAXTP", "DOD + 4WD", TierUnit.WORKING),
    TerminalSchedule("Long Beach all", "USLGB", "DOD + 4WD", TierUnit.WORKING),
    TerminalSchedule("New York all other", "USNYC", "DOD + 4WD", TierUnit.CALENDAR),
    TerminalSchedule("Houston", "USHOU", "DOD + 4WD", TierUnit.CALENDAR),
    TerminalSchedule("Oakland OICT", "USOKL", "DOD + 4WD", TierUnit.WORKING),
    TerminalSchedule("Charleston", "USCHS", "DOD + 4WD", TierUnit.CALENDAR),
    TerminalSchedule("Baltimore SeaGirt", "USBAL", "DOD + 4WD", TierUnit.CALENDAR),
    TerminalSchedule("Seattle SSA", "USSEA", "DOD + 4WD", TierUnit.CALENDAR),
)

BY_CODE: dict[str, TerminalSchedule] = {s.code: s for s in SCHEDULES}

#: Spot rates from the research that lack day ranges and therefore cannot become
#: tiers. Recorded so they are visible rather than lost, and marked so they are
#: never priced. A tier without day ranges is a number without a meaning.
UNVERIFIED_SPOT_RATES: tuple[str, ...] = (
    "Savannah 40 foot dry $265, $350, $515, day ranges not transcribed",
    "New York 40 foot dry $625, $970, $1330, day ranges not transcribed",
    "New York regular reefers most expensive non-reefer block, day ranges not transcribed",
    "New York operating reefers $1105, $1480, $1800, day ranges not transcribed",
)


def tiers_are_contiguous(tiers: tuple[Tier, ...]) -> bool:
    """Whether a tier sequence has no gap and no overlap.

    Built for the Hapag schedules once their rates land, and proven now against
    the Maersk corpus, which holds transcribed tiers. A gap means days nobody
    prices; an overlap means days priced twice. Both are data errors, not tariff
    features.
    """
    if not tiers:
        return True
    days = sorted((t.from_day, t.to_day) for t in tiers if isinstance(t, Tier))
    if days[0][0] != 1:
        return False
    for (_, prev_end), (next_start, _) in pairwise(days):
        if prev_end is None:
            return False
        if next_start != prev_end + 1:
            return False
    return days[-1][1] is None


__all__ = [
    "BY_CODE",
    "EFFECTIVE_DATE",
    "PUBLISHED_DATE",
    "SCHEDULES",
    "SOURCE_PDF",
    "UNVERIFIED_SPOT_RATES",
    "TerminalSchedule",
    "TierUnit",
    "tiers_are_contiguous",
]
