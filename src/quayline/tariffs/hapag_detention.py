"""Issue 14: Hapag's detention schedules, and why the haulage mode is not optional.

Geography crossed with haulage mode. Same container, same day, four different
legal rates. Source: USA_Detention_Effective_October_01_2025.pdf.

The six schedules below carry free-time notation, day basis, haulage mode and
equipment, all transcribed from the research. They carry **no dollar rates**,
because the rates are not transcribed anywhere we hold. A schedule without rates
cannot price anything, which is correct: the resolver returns nothing for Hapag
detention until rates land, and returning nothing is what issue 28 built the
machinery for.

The haulage mode requirement

Carrier Haulage or Merchant Haulage, read from the bill of lading checkbox.
Guessing it is a fifteen to twenty percent error before any dispute, which makes
it the single most expensive guess available in this product. So every detention
rule below declares `HAULAGE_MODE` as a required dimension, and a query without
one gets `None` plus the catalogued warning from issue 37 rather than a number.

Hapag errored here once: FMC Docket 22-03 found Hapag charged for 11 containers
without offering a return location, at $160 to $1845 each. The docket is recorded
because it is the precedent that makes the haulage question load-bearing rather
than administrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: The source. Named, because the schedules below verify against it and the rates
#: do not survive from it.
SOURCE_PDF = "USA_Detention_Effective_October_01_2025.pdf"

#: The precedent that makes the haulage question matter.
DOCKET_22_03 = "FMC Docket 22-03"


class Haulage(StrEnum):
    """Who moved the box inland. Read from the bill of lading checkbox, never
    guessed."""

    #: Hapag arranged the inland move.
    CARRIER = "carrier haulage"
    #: The merchant arranged it.
    MERCHANT = "merchant haulage"


class DetentionUnit(StrEnum):
    """What a post-free-time detention day is counted in."""

    CALENDAR = "calendar"
    WORKING = "working"


@dataclass(frozen=True, slots=True)
class DetentionSchedule:
    """One detention schedule: geography, haulage, equipment, free time, unit.

    No rates. The six rows below are the complete structure of Hapag's detention
    offering as transcribed, and structure without rates resolves to nothing,
    which is the honest state until transcription lands.
    """

    geography: str
    california: bool
    haulage: Haulage
    equipment: str
    free_time: str
    unit: DetentionUnit
    source_pdf: str = SOURCE_PDF

    @property
    def rule(self) -> str:
        """The rule reference a query names."""
        geo = "California" if self.california else "US excluding California"
        return f"Hapag US Detention {geo} {self.haulage.value} {self.equipment}"

    @property
    def needs_haulage_mode(self) -> bool:
        """Always true. Every detention schedule is indexed by haulage mode, so
        there is no detention query that can be answered without it."""
        return True


#: All six schedules, transcribed. Four distinct rate combinations across the
#: geography-haulage cross, which is why guessing the mode is a 15-20% error.
SCHEDULES: tuple[DetentionSchedule, ...] = (
    DetentionSchedule(
        "US excluding California",
        False,
        Haulage.CARRIER,
        "regular",
        "DOI + 4WD",
        DetentionUnit.CALENDAR,
    ),
    DetentionSchedule(
        "US excluding California",
        False,
        Haulage.CARRIER,
        "reefer operating",
        "DOI + 3WD",
        DetentionUnit.CALENDAR,
    ),
    DetentionSchedule(
        "California", True, Haulage.CARRIER, "regular", "DOI + 4WD", DetentionUnit.WORKING
    ),
    DetentionSchedule(
        "California", True, Haulage.CARRIER, "reefer operating", "DOI + 3WD", DetentionUnit.WORKING
    ),
    DetentionSchedule(
        "US excluding California",
        False,
        Haulage.MERCHANT,
        "regular",
        "DOI + 4WD",
        DetentionUnit.CALENDAR,
    ),
    DetentionSchedule(
        "US excluding California",
        False,
        Haulage.MERCHANT,
        "reefer operating",
        "DOI + 3WD",
        DetentionUnit.CALENDAR,
    ),
)

BY_RULE: dict[str, DetentionSchedule] = {s.rule: s for s in SCHEDULES}


def requirement_for(rule: str) -> str | None:
    """The dimension a detention query must supply, or None for unknown rules.

    Returns the dimension name rather than a boolean, because the caller needs to
    tell the operator *what* is missing, and "haulage mode" is actionable in a way
    that "insufficient input" is not.
    """
    if rule in BY_RULE:
        return "haulage mode"
    return None


__all__ = [
    "BY_RULE",
    "DOCKET_22_03",
    "SCHEDULES",
    "SOURCE_PDF",
    "DetentionSchedule",
    "DetentionUnit",
    "Haulage",
    "requirement_for",
]
