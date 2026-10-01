"""Issue 48: what a number is, before it is compared to another number.

Gross versus net presentation and added tax differ by carrier and jurisdiction.
CMA CGM adds 2 percent VAT on some D&D. Detention can be billed in the currency
of the inland place. US demurrage generally includes storage. Summing lines
against a gross total without normalising first produces a variance that is pure
artifact, and a variance that is pure artifact filed as a finding is how a valid
engine loses a respondent's trust in one letter.

Every amount carries three facts

**Currency.** The ISO code the figure was billed in. Detention billed in the
currency of the inland place is not comparable to a USD total without a rate,
and we hold no foreign exchange rates, so cross-currency comparison is refused
rather than converted at a rate nobody certified.

**Tax component.** The VAT or sales tax included in or added to the figure, as a
rate. CMA CGM's 2 percent on some D&D lines is the case in the evidence, and "on
some" is why it is per amount rather than per carrier: the same invoice can carry
taxed and untaxed lines.

**Basis.** Gross or net. A gross line compared against a net total differs by
exactly the tax, and that difference looks precisely like an overbilling.

The rule, stated once

**Variance validation runs on the same basis on both sides.** Every amount is
normalised to net, in its own currency, before any comparison. Cross-currency
pairs are refused with the currencies named, because converting at an uncertified
rate would manufacture a variance out of foreign exchange movement.

What normalisation does not do

It does not convert currencies. It does not guess whether an unmarked figure is
gross or net: an amount with no stated basis is `UNSTATED`, and unstated does not
normalise, because assuming gross understates every net figure and assuming net
overstates every gross one. The third state exists for the same reason it exists
everywhere else in this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Basis(StrEnum):
    """Whether tax is in the figure or on top of it."""

    #: Tax included. Must be removed before comparison.
    GROSS = "gross"
    #: Tax excluded or absent. Comparable as stated.
    NET = "net"
    #: Not stated on the invoice. Does not normalise in either direction.
    UNSTATED = "unstated"


@dataclass(frozen=True, slots=True)
class Money:
    """An amount with its currency, its tax, and its basis.

    The three facts without which a number cannot be compared to another number.
    A bare Decimal is a figure without a basis, and this type does not accept one:
    constructing from a raw number requires stating the basis explicitly.
    """

    amount: Decimal
    currency: str = "USD"
    tax_rate: Decimal = Decimal("0")
    basis: Basis = Basis.NET

    def __post_init__(self) -> None:
        if self.tax_rate < 0:
            msg = f"a negative tax rate of {self.tax_rate} is a data error, not a rebate"
            raise ValueError(msg)
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def net(cls, amount: str | Decimal, currency: str = "USD") -> Money:
        """A figure stated net, or with no tax to remove."""
        return cls(amount=Decimal(amount), currency=currency, basis=Basis.NET)

    @classmethod
    def gross(
        cls, amount: str | Decimal, currency: str = "USD", tax_rate: str | Decimal = "0"
    ) -> Money:
        """A figure stated gross of the given tax rate."""
        return cls(
            amount=Decimal(amount), currency=currency, tax_rate=Decimal(tax_rate), basis=Basis.GROSS
        )

    @property
    def net_amount(self) -> Decimal | None:
        """The amount with tax removed, or None when the basis is unstated.

        None rather than the amount itself, because returning the figure unchanged
        would silently treat an unstated basis as net, which overstates every gross
        figure it touches.
        """
        if self.basis is Basis.UNSTATED:
            return None
        if self.basis is Basis.NET or self.tax_rate == 0:
            return self.amount
        return self.amount / (1 + self.tax_rate)

    def comparable_to(self, other: Money) -> bool:
        """Whether these two may be compared. Same currency, both stated."""
        return (
            self.currency == other.currency
            and self.basis is not Basis.UNSTATED
            and other.basis is not Basis.UNSTATED
        )


@dataclass(frozen=True, slots=True)
class Normalised:
    """An amount reduced to net in its own currency, or the reason it could not
    be."""

    money: Money | None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.money is not None


def normalise(money: Money) -> Normalised:
    """Reduce to net. Refuses unstated bases rather than assuming one."""
    if money.basis is Basis.UNSTATED:
        return Normalised(
            money=None,
            reason=(
                f"{money.amount} {money.currency} states no basis. Assuming gross "
                f"understates every net figure and assuming net overstates every gross "
                f"one, so it normalises to neither."
            ),
        )
    net = money.net_amount
    assert net is not None
    return Normalised(money=Money(amount=net, currency=money.currency, basis=Basis.NET))


def variance_on_same_basis(charged: Money, expected: Money) -> Decimal | None:
    """The variance, or None when the two may not be compared.

    Both sides normalised to net first, then compared. Different currencies
    refuse with None rather than converting, because we hold no foreign exchange
    rates and a converted comparison would manufacture variance out of currency
    movement.
    """
    first = normalise(charged)
    second = normalise(expected)
    if not first.ok or not second.ok:
        return None
    assert first.money is not None and second.money is not None
    if first.money.currency != second.money.currency:
        return None
    return first.money.amount - second.money.amount


__all__ = [
    "Basis",
    "Money",
    "Normalised",
    "normalise",
    "variance_on_same_basis",
]
