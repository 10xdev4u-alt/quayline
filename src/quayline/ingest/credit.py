"""Issue 45: a credit note is a document, not a minus sign.

A credit note is not a negative invoice. Reconciling one as a negative line item
produces wrong balances — because a negative line participates in sums, averages
and variances as though it were a charge that happened to be negative — and wrong
dispute counts, because a credited dispute looks open when it is settled and
settled when it is merely reduced.

ZIM's dispute process issues an invoice crediting the billed party for the amount.
That credit is a response to a dispute, which means it has a direction: it points
at the original invoice and settles it, partially or fully. A negative line has
no direction. It sits in a list of charges and drags every total it touches.

What a credit carries

A reference to the original invoice, without which it cannot be reconciled
against anything. An amount, which is what was credited. And a date, which is
when the carrier conceded it, because a credit issued after filing changes what
the letter should ask for.

Balances reconcile, they do not sum

`reconcile` takes a charge and its credits and returns the outstanding balance.
Credits apply against the original charge in date order, oldest first, because a
carrier crediting specifically against one line of a multi-line invoice means
that line. An over-credit — credits totalling more than the charge — is refused
rather than carried as a negative balance, because a negative outstanding is not
money owed to anyone, it is a data error wearing a number.

The queue shows both sides

A dispute resolved by credit note appears in the queue as resolved, with the
charge and its credit both visible. Hiding the credit would understate what was
recovered; hiding the charge would overstate it. Showing both without double
counting is the whole requirement, and it is why the queue counts disputes
rather than summing amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreditNote:
    """A carrier's concession, pointing at the invoice it settles.

    `original_ref` is required and has no default, because a credit without a
    reference cannot be reconciled against anything and an unreferenceable credit
    is how a balance goes wrong silently.
    """

    original_ref: str
    amount: Decimal
    credited_on: date
    credit_ref: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.original_ref.strip():
            msg = "a credit without an original invoice reference cannot be reconciled"
            raise ValueError(msg)
        if self.amount <= 0:
            msg = f"a credit of {self.amount} is not a concession. Credits are positive amounts against a charge."
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Balance:
    """A charge with its credits applied, in date order."""

    original_ref: str
    charged: Decimal
    credited: Decimal
    outstanding: Decimal
    credits: tuple[CreditNote, ...]

    @property
    def settled(self) -> bool:
        """Nothing left outstanding. A settled dispute is resolved, not open."""
        return self.outstanding == 0

    @property
    def partially_credited(self) -> bool:
        return 0 < self.credited < self.charged


def reconcile(original_ref: str, charged: Decimal, credits: tuple[CreditNote, ...]) -> Balance:
    """Apply credits oldest-first against a charge.

    Refuses unrelated credits rather than skipping them, because a credit for a
    different invoice applied here would settle the wrong dispute. Refuses
    over-credit rather than carrying a negative balance, because a negative
    outstanding is a data error, not money owed to anyone.
    """
    for credit in credits:
        if credit.original_ref != original_ref:
            msg = (
                f"credit {credit.credit_ref or '(unnamed)'} references "
                f"{credit.original_ref!r}, not {original_ref!r}. Credits apply "
                f"against the invoice they name."
            )
            raise ValueError(msg)
    ordered = tuple(sorted(credits, key=lambda c: (c.credited_on, c.credit_ref)))
    total = sum((c.amount for c in ordered), Decimal(0))
    if total > charged:
        msg = (
            f"credits total {total} against a charge of {charged}. Over-credit is "
            f"refused rather than carried as a negative balance."
        )
        raise ValueError(msg)
    return Balance(
        original_ref=original_ref,
        charged=charged,
        credited=total,
        outstanding=charged - total,
        credits=ordered,
    )


@dataclass(frozen=True, slots=True)
class QueueEntry:
    """One dispute in the queue, showing the charge and its credit together."""

    original_ref: str
    balance: Balance

    @property
    def status(self) -> str:
        if self.balance.settled:
            return "resolved by credit"
        if self.balance.partially_credited:
            return "partially credited"
        return "open"

    def summary(self) -> str:
        base = f"{self.original_ref}: charged {self.balance.charged}, "
        if self.balance.settled:
            return base + f"credited {self.balance.credited} in full. Resolved."
        if self.balance.partially_credited:
            return (
                base + f"credited {self.balance.credited}, {self.balance.outstanding} outstanding."
            )
        return base + "no credits. Open."


def queue(charges: dict[str, Decimal], credits: tuple[CreditNote, ...]) -> tuple[QueueEntry, ...]:
    """The dispute queue: every charge with its credits, settled and open alike.

    Both sides visible, nothing double counted. Settled disputes stay in the queue
    rather than vanishing, because a resolved dispute that disappears is a recovery
    nobody can report.
    """
    by_ref: dict[str, list[CreditNote]] = {}
    for credit in credits:
        by_ref.setdefault(credit.original_ref, []).append(credit)
    return tuple(
        QueueEntry(
            original_ref=ref,
            balance=reconcile(ref, amount, tuple(by_ref.get(ref, ()))),
        )
        for ref, amount in sorted(charges.items())
    )


__all__ = [
    "Balance",
    "CreditNote",
    "QueueEntry",
    "queue",
    "reconcile",
]
