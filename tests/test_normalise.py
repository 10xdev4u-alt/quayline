"""Issue 48: what a number is, before it is compared to another number.

The load bearing tests are the two the issue names: a VAT-bearing line and a
non-USD line. Everything else checks the machinery, and a suite that checks the
machinery without asserting those two would pass while the issue's central claims
go untested.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quayline.ingest import normalise as module
from quayline.ingest.normalise import Basis, Money, normalise, variance_on_same_basis

D = Decimal


# ---------------------------------------------------------------- criterion 1
# Amounts carry a currency and a tax component.


def test_every_amount_carries_currency_tax_and_basis() -> None:
    """The three facts without which a number cannot be compared."""
    money = Money(amount=D("102.00"), currency="USD", tax_rate=D("0.02"), basis=Basis.GROSS)
    assert money.currency == "USD"
    assert money.tax_rate == D("0.02")
    assert money.basis is Basis.GROSS


def test_currency_is_normalised_to_uppercase() -> None:
    """usd and USD are the same currency, and a comparison that treats them as
    different refuses pairs it should accept."""
    assert Money.net("100", "usd").currency == "USD"
    assert Money.net("100", "Usd").currency == "USD"


def test_a_negative_tax_rate_is_refused() -> None:
    """A negative tax rate is a data error, not a rebate."""
    with pytest.raises(ValueError, match="data error"):
        Money(amount=D("100"), tax_rate=D("-0.02"))


def test_constructors_state_the_basis() -> None:
    assert Money.gross("102.00", tax_rate="0.02").basis is Basis.GROSS
    assert Money.net("100.00").basis is Basis.NET


def test_amounts_are_immutable() -> None:
    with pytest.raises(AttributeError):
        Money.net("100").amount = D("0")  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# Variance validation runs on the same basis on both sides.


def test_gross_and_net_normalise_to_the_same_number() -> None:
    """CMA CGM 2 percent VAT: 102 gross is 100 net. Compared without normalising,
    the two differ by exactly the tax, which looks precisely like an overbilling."""
    assert normalise(Money.gross("102.00", tax_rate="0.02")).money == Money.net("100.00")
    assert variance_on_same_basis(Money.gross("102.00", tax_rate="0.02"), Money.net("100.00")) == D(
        "0.00"
    )


def test_net_against_net_compares_directly() -> None:
    assert variance_on_same_basis(Money.net("4800"), Money.net("2400")) == D("2400")


def test_a_zero_tax_gross_is_its_own_net() -> None:
    assert normalise(Money.gross("100.00", tax_rate="0")).money == Money.net("100.00")


def test_unstated_basis_refuses_in_both_directions() -> None:
    """Assuming gross understates every net figure and assuming net overstates
    every gross one. The third state exists because both defaults are wrong."""
    assert normalise(Money(D("100"), basis=Basis.UNSTATED)).ok is False
    assert "neither" in normalise(Money(D("100"), basis=Basis.UNSTATED)).reason
    assert variance_on_same_basis(Money(D("100"), basis=Basis.UNSTATED), Money.net("100")) is None
    assert variance_on_same_basis(Money.net("100"), Money(D("100"), basis=Basis.UNSTATED)) is None


def test_comparable_to_requires_same_currency_and_stated_bases() -> None:
    assert Money.net("100", "USD").comparable_to(Money.net("100", "USD")) is True
    assert Money.net("100", "USD").comparable_to(Money.net("100", "EUR")) is False
    assert Money.net("100").comparable_to(Money(D("100"), basis=Basis.UNSTATED)) is False


# ---------------------------------------------------------------- criterion 3
# A VAT-bearing line.


def test_a_vat_bearing_line_normalises_before_comparison() -> None:
    """The criterion's case. A 2 percent VAT line at 102 against a net expectation
    of 100 is exact, not a 2.00 variance."""
    line = Money.gross("102.00", tax_rate="0.02")
    expected = Money.net("100.00")
    assert line.net_amount == D("100")
    assert variance_on_same_basis(line, expected) == D("0")


def test_a_vat_line_against_a_wrong_expectation_still_finds_it() -> None:
    """Normalisation does not hide real variances. 102 gross against 90 net is
    10, not 12."""
    assert variance_on_same_basis(Money.gross("102.00", tax_rate="0.02"), Money.net("90.00")) == D(
        "10"
    )


# ---------------------------------------------------------------- criterion 4
# A non-USD detention line.


def test_a_non_usd_line_refuses_comparison_against_usd() -> None:
    """Detention billed in the currency of the inland place. We hold no foreign
    exchange rates, so converting would manufacture variance out of currency
    movement. Refused with None, not guessed."""
    assert variance_on_same_basis(Money.net("100.00", "EUR"), Money.net("100.00", "USD")) is None
    assert variance_on_same_basis(Money.net("100.00", "USD"), Money.net("100.00", "EUR")) is None


def test_same_currency_non_usd_compares() -> None:
    """The refusal is about mixing currencies, not about non-USD figures."""
    assert variance_on_same_basis(Money.net("200.00", "EUR"), Money.net("150.00", "EUR")) == D(
        "50.00"
    )


def test_normalise_keeps_the_currency() -> None:
    """Net in its own currency. Normalisation removes tax, never converts."""
    got = normalise(Money.gross("102.00", "EUR", "0.02"))
    assert got.ok is True
    assert got.money is not None
    assert got.money.currency == "EUR"
    assert got.money.amount == D("100")
    assert got.money.basis is Basis.NET


# ---------------------------------------------------------------- what it is not


def test_there_is_no_fx_conversion_anywhere() -> None:
    """No rates held, no conversion offered. A conversion function would be used
    the first time a cross-currency pair needed comparing, and the rate it used
    would be uncertified."""
    assert not hasattr(module, "convert")
    assert not hasattr(module, "to_usd")
    assert not hasattr(module, "exchange_rate")


def test_net_amount_is_none_for_unstated_not_the_figure() -> None:
    """Returning the figure unchanged would silently treat unstated as net, which
    overstates every gross figure it touches."""
    assert Money(D("100"), basis=Basis.UNSTATED).net_amount is None


def test_issue_48_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 48" in flat
    assert "pure artifact" in flat


def test_normalised_is_immutable() -> None:
    got = normalise(Money.net("100"))
    with pytest.raises(AttributeError):
        got.money = None  # type: ignore[misc]
