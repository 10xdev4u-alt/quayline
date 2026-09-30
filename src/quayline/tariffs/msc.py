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

#: The fifteen pass-through terminals, MSC tariff section 1.1: each terminal bills
#: and collects its own demurrage except the terminals listed, for which MSC
#: passes through at cost. Codes where the research or this repository already
#: establishes them; names only where it does not, because an invented UN/LOCODE
#: is a guess wearing a standard. Unmapped names resolve by name match, and the
#: mapping table in issue 26 will fill the codes when it lands.
PASS_THROUGH_TERMINALS: tuple[tuple[str, str | None], ...] = (
    ("Garden City Savannah", "USSVNG"),
    ("North Charleston", "USCHS"),
    ("Wando", "USCHS"),
    ("Napoleon Avenue", None),
    ("LBCT", "USLGB"),
    ("Trapac Oakland", "USOKL"),
    ("VIT", None),
    ("NIT", None),
    ("Portsmouth", None),
    ("Richmond", None),
    ("Barbours Cut", None),
    ("Bayport", None),
    ("Wilmington NC", None),
    ("Husky Tacoma", None),
    ("Trapac LAX", "USLAXTP"),
)

#: MSC's one direct-tariff gateway. Port Everglades: 4 working days free, 20 foot
#: , 40 foot . Not pass-through, so it resolves to the direct schedule
#: rather than refusing with the MTO warning.
DIRECT_TARIFF_PORT = "Port Everglades"


def is_pass_through(port_or_terminal: str) -> bool:
    """Whether an MSC lane runs through a pass-through terminal.

    Matches by code or by name fragment, because invoices name terminals both
    ways and a matcher that only reads codes misses half of them. Case
    insensitive, for the same reason.
    """
    key = port_or_terminal.casefold()
    return any(
        (code is not None and code.casefold() == key)
        or name.casefold() in key
        or key in name.casefold()
        for name, code in PASS_THROUGH_TERMINALS
    )


@dataclass(frozen=True, slots=True)
class InvoicePair:
    """Two invoices that may price the same container twice.

    On a pass-through lane the terminal operator bills storage directly and MSC
    bills line D&D through, so the same box can appear on two invoices and
    neither is arithmetically wrong. Disputing both without deduplicating prices
    the container twice, which is how a valid dispute loses credibility.
    """

    msc_line_invoice_ref: str
    terminal_storage_invoice_ref: str | None = None

    @property
    def needs_dedupe(self) -> bool:
        """Whether both sides exist to be double-counted."""
        return self.terminal_storage_invoice_ref is not None

    def dedupe_note(self) -> str:
        """What to check before disputing either side."""
        if not self.needs_dedupe:
            return "No terminal storage invoice on record. Nothing to deduplicate."
        return (
            f"Terminal storage invoice {self.terminal_storage_invoice_ref} and MSC line "
            f"invoice {self.msc_line_invoice_ref} may price the same container. "
            f"Deduplicate before disputing, or double-count and lose credibility."
        )


__all__ = [
    "DIRECT_TARIFF_PORT",
    "INSIDE_MARKERS",
    "OUTSIDE_MARKERS",
    "PASS_THROUGH_TERMINALS",
    "PORT_EVERGLADES_SOURCE",
    "ChargeKind",
    "NormalisedCharge",
    "is_pass_through",
    "locus_in",
    "normalise",
]
