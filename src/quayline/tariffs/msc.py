"""Issue 22: what an MSC charge is, decided by where the box was.

MSC titles its "IMPORT DETENTION" for equipment **inside** the marine terminal.
That is demurrage to everyone else and to 46 CFR 545.5. Keying off the invoice
line title misclassifies every MSC import charge, because the title says detention
and the physical facts say demurrage.

So the charge type is derived from the physical locus described in the charge
narrative, never from the line title. The title is what the carrier called it. The
narrative is where the carrier said where the container was. Only one of those is
evidence.

The locus rule, stated once

- **Inside** the marine terminal, the port, the yard, the berth: **demurrage**.
  The box is occupying terminal space.
- **Outside** the terminal, at the consignee, on the road, at a depot: **detention**.
  The box is occupying the carrier's equipment.

MSC tariff section 2.1 describes use of the carrier's container inside the marine
terminal. The section is about detention in name and demurrage in fact, which is
the whole issue in one paragraph.

What this module does not do

It does not price MSC. MSC publishes no U.S. import demurrage tariff at eight of
the nine major gateways and passes terminal demurrage through at cost, so there is
almost nothing to transcribe. The one direct schedule is Port Everglades, 4 working
days free, 20 foot $65 and 40 foot $110, and it is recorded here as the single
verified row rather than as the start of a table that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChargeKind(StrEnum):
    """What the charge is, by physical locus. Never by line title."""

    #: The box was inside the terminal. Terminal space.
    DEMURRAGE = "demurrage"
    #: The box was outside the terminal. The carrier's equipment.
    DETENTION = "detention"
    #: The narrative names no locus. Not a third kind of charge: an admission that
    #: the type cannot be determined from this text.
    UNKNOWN = "unknown"


#: Words that place the box inside the terminal. Lowercase fragments, matched as
#: substrings, because a narrative is prose and prose varies. Kept short on
#: purpose: a long list of synonyms is a fuzzy matcher, and the 545.5 argument is
#: about the locus rather than about matching adjectives.
INSIDE_MARKERS: tuple[str, ...] = (
    "inside the marine terminal",
    "inside the terminal",
    "within the terminal",
    "at the terminal",
    "on terminal",
    "marine terminal",
    "port storage",
    "terminal storage",
    "use of the carrier's container inside",
)

#: Words that place the box outside it.
OUTSIDE_MARKERS: tuple[str, ...] = (
    "outside the terminal",
    "outside the marine terminal",
    "at consignee",
    "at the consignee",
    "consignee's premises",
    "on the road",
    "at depot",
    "at the depot",
    "merchant haulage",
    "carrier's equipment outside",
)


@dataclass(frozen=True, slots=True)
class NormalisedCharge:
    """A charge line with its kind decided by locus."""

    kind: ChargeKind
    locus_found: str
    #: The title, kept for the audit trail. It is evidence of what the carrier
    #: called it, which matters when the title and the locus disagree.
    line_title: str = ""

    @property
    def title_disagrees(self) -> bool:
        """Whether the carrier's own title contradicts the locus.

        An MSC "IMPORT DETENTION" inside a terminal is the case this module exists
        for. The disagreement is itself a finding, because a carrier that mislabels
        its own charges is a carrier whose invoice deserves closer reading.
        """
        if self.kind is ChargeKind.UNKNOWN or not self.line_title:
            return False
        titled = self.line_title.casefold()
        if self.kind is ChargeKind.DEMURRAGE:
            return "detention" in titled
        return "demurrage" in titled


def locus_in(narrative: str) -> str:
    """The first locus marker found in the narrative, or empty."""
    lowered = narrative.casefold()
    for marker in INSIDE_MARKERS + OUTSIDE_MARKERS:
        if marker in lowered:
            return marker
    return ""


def normalise(line_title: str, narrative: str) -> NormalisedCharge:
    """Decide what a charge is, from where the box was.

    The narrative is read and the title is not, except as an audit trail. A caller
    that passes only a title gets `UNKNOWN`, because a title is what the carrier
    called it and this module does not price names.
    """
    lowered = narrative.casefold()
    for marker in INSIDE_MARKERS:
        if marker in lowered:
            return NormalisedCharge(
                kind=ChargeKind.DEMURRAGE, locus_found=marker, line_title=line_title
            )
    for marker in OUTSIDE_MARKERS:
        if marker in lowered:
            return NormalisedCharge(
                kind=ChargeKind.DETENTION, locus_found=marker, line_title=line_title
            )
    return NormalisedCharge(kind=ChargeKind.UNKNOWN, locus_found="", line_title=line_title)


#: MSC's only direct U.S. import demurrage schedule. Port Everglades, 4 working
#: days free, 20 foot $65, 40 foot $110. Recorded as the single verified row it is,
#: not as the start of a table that does not exist.
PORT_EVERGLADES_SOURCE = "MSC US import demurrage tariff, Port Everglades"

__all__ = [
    "INSIDE_MARKERS",
    "OUTSIDE_MARKERS",
    "PORT_EVERGLADES_SOURCE",
    "ChargeKind",
    "NormalisedCharge",
    "locus_in",
    "normalise",
]
