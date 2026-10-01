"""Issue 27: everything we do not hold, named, with a task attached.

Five carriers with no usable rates: Yang Ming, PIL, HMM, COSCO and Evergreen.
Each row below states what exists, what is missing, and the named acquisition
task that would close the gap. Holes are cheap. Wrong rates are not.

Why a register rather than five comments

A comment saying "rates not held" is true on the day it is written and invisible
every day after. A register is queryable: the resolver asks it whether a carrier
is covered before pricing, the coverage report renders it, and a test asserts
that no resolver returns a rate for any carrier in it. The day a transcription
lands, the row is deleted in a diff somebody reviews, and every consumer updates
at once because there was only ever one list.

What each row holds besides the gap

HMM and COSCO are not empty rows. HMM's own demurrage definition concedes the
charge is compensatory against terminal land use cost, which supports a
duplication challenge and engages 541.6(e)(2). COSCO's FMC answer in Docket 24-01
sets the lowest evidence bar in the category — screenshots showing the facility
was unavailable, without even asserting an attempt — and its 7-day dispute window
is arguably non-compliant with 541.8(a). Those are usable findings about carriers
whose rates we cannot price, and the register keeps both halves together so the
usable part is not lost with the missing part.
"""

from __future__ import annotations

from dataclasses import dataclass

from quayline.tariffs.resolution import CarrierCoverage, Granularity


@dataclass(frozen=True, slots=True)
class UncoveredCarrier:
    """One carrier we cannot price, with what would close the gap.

    `holds` is what we have that is usable today, because "nothing" is rarely the
    full story and the usable part should survive alongside the gap. `acquire` is
    the named task, specific enough that two people reading it would do the same
    thing.
    """

    carrier: str
    holds: str
    missing: str
    acquire: str


#: The register. Five rows, each with a task. Deleting a row is how a transcription
#: lands, and it is a diff.
UNCOVERED: tuple[UncoveredCarrier, ...] = (
    UncoveredCarrier(
        carrier="Yang Ming",
        holds="Nothing usable. One of the nine FMC data submitters, so a tariff exists.",
        missing="The tariff itself. Not located.",
        acquire="Request the current US import demurrage and detention tariff via the FMC data submission channel, citing submitter status.",
    ),
    UncoveredCarrier(
        carrier="PIL",
        holds="Nothing usable. Not an FMC data submitter, so no regulatory channel exists.",
        missing="The tariff itself. Not located anywhere.",
        acquire="Request the tariff directly from PIL's US agency, in writing, and record the request date for the backlog.",
    ),
    UncoveredCarrier(
        carrier="HMM",
        holds=(
            "Rule numbers and a usable admission: HMM's own demurrage definition "
            "concedes the charge is compensatory against terminal land use cost, "
            "which supports a duplication challenge and engages 541.6(e)(2). Zero "
            "free time on canceled-booking detention is also recorded."
        ),
        missing="Rates, which sit behind a JavaScript form and did not survive extraction.",
        acquire="Transcribe the rate tables by driving the form for each US gateway, or obtain a static PDF from HMM's agency.",
    ),
    UncoveredCarrier(
        carrier="COSCO",
        holds=(
            "Dispute policy only: Docket 24-01 sets the lowest evidence bar in the "
            "category (screenshots of unavailability, no attempt required), the "
            "dispute window is 7 days after out-gate (arguably non-compliant with "
            "541.8(a)), and the Equipment Interchange Receipt is required."
        ),
        missing="Rate tables, which are not on the public site.",
        acquire="Locate the current US demurrage and detention rate tables via COSCO's agency or a filed tariff copy.",
    ),
    UncoveredCarrier(
        carrier="Evergreen",
        holds="Rules 036-I01 import and 036-E01 export, plus the terminal directory transcribed in issue 26.",
        missing="Rate attachments to the rules.",
        acquire="Obtain the rate attachments to Rules 036-I01 and 036-E01.",
    ),
)

BY_CARRIER: dict[str, UncoveredCarrier] = {u.carrier: u for u in UNCOVERED}


def is_uncovered(carrier: str) -> bool:
    """Whether a carrier is in the register. The predicate the resolver and the
    coverage report share, so there is one definition of "we do not hold this"."""
    return carrier in BY_CARRIER


def acquisition_tasks() -> dict[str, str]:
    """Every gap with its named task, for the research backlog in issue 83.

    A dict keyed by carrier so the backlog can track each task independently.
    Specific enough that two people reading a task would do the same thing, which
    is the test a task description has to pass.
    """
    return {u.carrier: u.acquire for u in UNCOVERED}


def coverage_entries() -> tuple[CarrierCoverage, ...]:
    """These five as coverage rows, so the #28 report renders them.

    Returns `CarrierCoverage` rows with zero rules held and `verified` False,
    which is exactly what "uncovered" means in that report's terms. Built here
    rather than in the report so there is one list of uncovered carriers, and the
    report cannot drift from it.
    """
    return tuple(
        CarrierCoverage(
            carrier=u.carrier,
            granularity=Granularity.NONE_HELD,
            rules_held=0,
            verified=False,
            note=f"UNVERIFIED: {u.missing} Acquire: {u.acquire}",
        )
        for u in UNCOVERED
    )


__all__ = [
    "BY_CARRIER",
    "UNCOVERED",
    "UncoveredCarrier",
    "acquisition_tasks",
    "coverage_entries",
    "is_uncovered",
]
