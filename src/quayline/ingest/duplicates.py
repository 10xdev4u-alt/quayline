"""Issue 46: two invoices, one container, priced twice.

Two invoices per container are common: terminal storage billed direct to the
shipper plus carrier detention or pass-through demurrage on the same box. MSC
passes terminal demurrage through at cost at fifteen terminals. ZIM rail
demurrage is carrier-only with the rail operator invoicing storage separately.
Neither invoice is arithmetically wrong. Disputing both without deduplicating
prices the container twice, and a double-counted dispute loses credibility
faster than any single error in it.

What counts as an overlap

Two charges overlap when they name the **same container** and their date ranges
**intersect on at least one day**, and they come from **different billing
parties** where one is a terminal operator (or rail operator) and the other is a
carrier. Same-party overlaps are a different problem — a carrier billing twice is
a duplicate invoice, not a double invoice — and same-instrument overlaps are
handled by the arithmetic checks. This module is specifically the terminal-plus-
carrier shape, because that is the shape the evidence names.

The flag names both parties and both instruments

A flag that says "possible double invoice" without naming who billed what is a
finding nobody can act on. The flag carries the container, the overlapping dates,
both billing parties and both instruments, so the operator knows exactly which
two documents to put side by side.

Flagged before filing, not after

The detector runs over the charge set before anything is filed, and an overlap
blocks the pair rather than either invoice alone. Blocking one side would let the
other through unexamined, and the unexamined side is the one that turns out to
have been the correct one to dispute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class Charge:
    """One charge line, from one invoice, by one billing party."""

    container: str
    first_day: date
    last_day: date
    billed_by: str
    instrument: str
    amount: str = ""

    def __post_init__(self) -> None:
        if self.last_day < self.first_day:
            msg = f"charge ends {self.last_day} before it starts {self.first_day}"
            raise ValueError(msg)

    @property
    def days(self) -> frozenset[date]:
        """Every day in the range, inclusive. Materialised because ranges are
        short and set intersection is the overlap test."""
        out = set()
        day = self.first_day
        while day <= self.last_day:
            out.add(day)
            day += timedelta(days=1)
        return frozenset(out)

    def overlaps(self, other: Charge) -> bool:
        """Same container, intersecting dates. Party and instrument are checked
        separately, because overlap is a fact about time and the parties decide
        what kind of overlap it is."""
        return self.container == other.container and bool(self.days & other.days)

    def overlap_days(self, other: Charge) -> tuple[date, ...]:
        return tuple(sorted(self.days & other.days))


def _is_operator(party: str) -> bool:
    """Whether a billing party is a terminal or rail operator rather than a
    carrier. Matched on words carriers do not use for themselves, because the
    distinction is structural: operators bill storage, carriers bill D&D."""
    lowered = party.casefold()
    return any(
        word in lowered
        for word in ("terminal", "port authority", "rail operator", "railroad", "depot", "mto")
    )


@dataclass(frozen=True, slots=True)
class DoubleInvoice:
    """A terminal-plus-carrier overlap, with both sides named."""

    container: str
    overlap: tuple[date, ...]
    operator_party: str
    operator_instrument: str
    carrier_party: str
    carrier_instrument: str

    def sentence(self) -> str:
        """Both parties, both instruments, the dates. Everything needed to put
        the two documents side by side."""
        first, last = self.overlap[0].isoformat(), self.overlap[-1].isoformat()
        span = first if first == last else f"{first} to {last}"
        return (
            f"{self.container}: {self.operator_party} billed {self.operator_instrument} "
            f"and {self.carrier_party} billed {self.carrier_instrument}, overlapping "
            f"on {span}. Disputing both prices the container twice."
        )


def find_double_invoices(charges: tuple[Charge, ...]) -> tuple[DoubleInvoice, ...]:
    """Group by container and date range across all billing parties, and flag
    terminal-plus-carrier overlaps.

    Pure and total. Same-party pairs are skipped, because a carrier billing twice
    is a duplicate rather than a double invoice. Pairs where neither side is an
    operator are skipped, because two carriers billing one box is a different
    dispute with different evidence.
    """
    found: list[DoubleInvoice] = []
    for i, first in enumerate(charges):
        for second in charges[i + 1 :]:
            if not first.overlaps(second):
                continue
            if first.billed_by == second.billed_by:
                continue
            operator, carrier = None, None
            for candidate, other in ((first, second), (second, first)):
                if _is_operator(candidate.billed_by) and not _is_operator(other.billed_by):
                    operator, carrier = candidate, other
            if operator is None or carrier is None:
                continue
            found.append(
                DoubleInvoice(
                    container=first.container,
                    overlap=first.overlap_days(second),
                    operator_party=operator.billed_by,
                    operator_instrument=operator.instrument,
                    carrier_party=carrier.billed_by,
                    carrier_instrument=carrier.instrument,
                )
            )
    return tuple(found)


__all__ = [
    "Charge",
    "DoubleInvoice",
    "find_double_invoices",
]
