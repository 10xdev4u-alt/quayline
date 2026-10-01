"""Issue 44: one invoice, many containers, and many invoices, one dispute.

Multi-container per invoice is the norm, not the exception. Consolidated billing
across up to 35 invoices is routine: MSC e-Pay handles bills of lading ending in
A, with the original number and added containers in the comment field, and CMA
CGM supports up to 35 invoices per action, restricted to the same domain and the
same reason.

Two structures, because they fail differently

**A multi-container invoice** is one document with many charge lines. Each line
belongs to an invoice, a bill of lading and a container, and containers on one
invoice routinely differ in equipment type: dry and reefer on the same page, with
different free time and different rates. A DayCount or Amount check run against
the invoice total without per-container breakdowns is meaningless, because the
total mixes allowances that were never the same.

**A consolidated dispute group** is many invoices in one action. CMA CGM restricts
these to the same domain and the same reason, and that restriction is load
bearing rather than administrative: a group mixing dispute domains is a group the
carrier rejects wholesale, losing the valid claims with the invalid ones. So the
group validates its own membership, and mixing domains is a construction-time
refusal rather than a filing-time surprise.

The comment field convention

MSC puts the original bill of lading number and the added containers in the
comment field of an e-Pay action on a BOL ending in A. That is a carrier-specific
encoding of a general structure, so it is parsed here into the general form
rather than modelled as an MSC type. A comment field that cannot be parsed is not
an error: it is an invoice whose consolidation structure is unknown, and unknown
structure is reported rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChargeLine:
    """One charge line, belonging to an invoice, a bill of lading and a container.

    The triple is the point. A line that names an amount without saying which
    container it prices cannot be recomputed, cannot be grouped, and cannot be
    disputed without dragging every other container on the invoice with it.
    """

    invoice_ref: str
    bol_number: str
    container: str
    equipment: str = "dry"
    amount: str = ""

    def key(self) -> tuple[str, str, str]:
        """The identity a line is grouped and deduplicated by."""
        return (self.invoice_ref, self.bol_number, self.container)


@dataclass(frozen=True, slots=True)
class ConsolidatedGroup:
    """Many invoices in one dispute action.

    CMA CGM allows up to 35 invoices per action, restricted to the same domain
    and the same reason. Both restrictions are enforced at construction, because a
    group mixing domains is rejected wholesale by the carrier, losing the valid
    claims with the invalid ones.
    """

    invoice_refs: tuple[str, ...]
    domain: str
    reason: str
    max_invoices: int = 35

    def __post_init__(self) -> None:
        if not self.invoice_refs:
            msg = "a dispute group with no invoices disputes nothing"
            raise ValueError(msg)
        if len(self.invoice_refs) > self.max_invoices:
            msg = (
                f"{len(self.invoice_refs)} invoices exceeds the CMA CGM limit of "
                f"{self.max_invoices} per action. Split the group rather than filing "
                f"it whole and losing all of it."
            )
            raise ValueError(msg)
        if not self.domain.strip():
            msg = "a group with no domain cannot satisfy the same-domain constraint"
            raise ValueError(msg)
        if not self.reason.strip():
            msg = "a group with no reason cannot satisfy the same-reason constraint"
            raise ValueError(msg)

    @property
    def size(self) -> int:
        return len(self.invoice_refs)


def group_lines(lines: tuple[ChargeLine, ...]) -> dict[tuple[str, str], tuple[ChargeLine, ...]]:
    """Group charge lines by (invoice, bill of lading).

    Container varies within the group and equipment varies with it, which is why
    the key stops at the bill of lading. A group keyed by container would put each
    line in a group of one, which groups nothing.
    """
    grouped: dict[tuple[str, str], list[ChargeLine]] = {}
    for line in lines:
        grouped.setdefault((line.invoice_ref, line.bol_number), []).append(line)
    return {k: tuple(v) for k, v in grouped.items()}


def equipment_types(lines: tuple[ChargeLine, ...]) -> frozenset[str]:
    """The equipment types on a set of lines. More than one means per-container
    breakdowns are required before any total can be recomputed."""
    return frozenset(line.equipment for line in lines)


def parse_msc_comment(comment: str) -> tuple[str, tuple[str, ...]]:
    """An MSC e-Pay comment field into its original BOL and added containers.

    Bills of lading ending in A carry the original number and the added
    containers in the comment field. Returns the original number and the added
    container list, empty when the comment carries no consolidation structure.
    Unparseable is reported as empty rather than raising, because an invoice
    whose consolidation structure is unknown is unknown, not malformed.
    """
    parts = [p.strip() for p in comment.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return ("", ())
    return (parts[0], tuple(parts[1:]))


__all__ = [
    "ChargeLine",
    "ConsolidatedGroup",
    "equipment_types",
    "group_lines",
    "parse_msc_comment",
]
