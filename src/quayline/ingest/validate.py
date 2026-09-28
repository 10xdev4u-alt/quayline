"""Issue 42: the checks that decide whether an extraction can be trusted.

The premise of this issue is that recovery dollars live in the validator, not the
extractor. A parser can be perfect on every character and still hand us a
structurally impossible invoice, and a dispute filed on a structurally impossible
invoice is worse than no dispute, because it burns the one thing a demand has that
a carrier cannot take back: the fact that we checked.

What this module is

Four arithmetic and presence assertions over a structured ledger, each carrying the
citation that makes it checkable by the other side. They run on the extracted
values, so a mistake in extraction and a mistake in the carrier's own arithmetic are
both caught, and they are deliberately the *stricter* of the two comparisons this
project makes.

Why exact equality and not the tolerance band

``engine/amount.py`` applies a two percent band, and that band is an ESTIMATE about
whether a dispute is worth filing. It is the wrong instrument here. The band exists
because a carrier's rounding is a judgment call about money, and we would rather
not spend a letter on it. This module is not judging a carrier. It is asking
whether a set of numbers adds up to itself, and if ``days x rate != amount`` then
either the carrier made an error or we misread a digit, and both of those are worth
stopping for. A two percent band would wave through a misparsed rate, which is the
single most expensive error in the pipeline.

The five checks

1. ``line_sum``            the stated total is the sum of the stated lines. 541.6(c)(1)
2. ``free_time_window``    start plus allowed days is the stated end. 541.6(b)(3)-(5)
3. ``charge_arithmetic``   days times rate is the stated amount. 541.6(c)(2)-(3)
4. ``identifiers_present`` a container and a bill of lading on every line. 541.6(a)
5. ``can_file``            no failures. Not a check of the invoice but of the filing.

What this cannot do

It cannot tell a wrong number from a wrong parse. It can only say the invoice is not
internally consistent, which is the honest limit of arithmetic on extracted values.
A carrier that discloses a consistent but false invoice passes all four.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from quayline.models.invoice import (
    CITE_ALLOWANCE,
    CITE_FREE_TIME_END,
    CITE_FREE_TIME_START,
    CITE_RATE_RULE,
    CITE_TOTAL,
)

# The identifying clauses 541.6(a) requires on the invoice itself. The checklist
# module in issue 1 extracted the clause text; this is the pointer to it.
CITE_IDENTIFIERS = "541.6(a)(1)-(2)"

#: 541.6(b) asks for the start and the end of free time and the days allowed. If
#: the three disagree with each other then at least one of them was misread, and
#: every day count downstream of them inherits the error.
CITE_FREETIME_WINDOW = f"{CITE_FREE_TIME_START}, {CITE_ALLOWANCE}, {CITE_FREE_TIME_END}"


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    """One chargeable line, as extracted.

    ``amount`` is what the carrier billed for this line and ``rate`` is the rate
    they said applied. Both are kept even when ``days x rate`` disagrees with
    ``amount``, because the disagreement is the finding and discarding either side
    of it would destroy the evidence.
    """

    container_number: str
    bol_number: str
    chargeable_days: int
    rate: Decimal
    amount: Decimal

    def __post_init__(self) -> None:
        if self.chargeable_days < 0:
            msg = "a negative day count is an extraction error, not a carrier dispute"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Ledger:
    """A structured extraction, as the validator sees it.

    This is deliberately not a parsed document. The field binder that turns
    ``TextLayer`` into one of these is a separate concern, and keeping them apart
    means this module's arithmetic can be tested exhaustively without inventing
    invoices that no carrier has ever issued.
    """

    lines: tuple[InvoiceLine, ...]
    stated_total: Decimal
    free_time_start: date
    free_time_end: date
    allowed_free_time_days: int

    def __post_init__(self) -> None:
        if self.allowed_free_time_days < 0:
            msg = "negative free time is an extraction error, not a carrier dispute"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Check:
    """One assertion, and whether it held."""

    name: str
    cite: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        mark = "pass" if self.passed else "FAIL"
        return f"[{mark}] {self.name} ({self.cite}): {self.detail}"


@dataclass(frozen=True, slots=True)
class Report:
    """Every check, and whether the dispute may be filed on them."""

    checks: tuple[Check, ...]

    @property
    def failures(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if not c.passed)

    @property
    def can_file(self) -> bool:
        """The gate. False if any check failed.

        This is the property the filing path must consult, and the reason it exists
        as a single boolean is that a caller asking ``if report.failures`` will
        eventually write ``if not report.failures and other_conditions`` and get the
        precedence wrong at 2am. One property, one meaning, not negotiable.
        """
        return not self.failures

    def reason_not_filed(self) -> str:
        """Why filing is blocked, naming every failure.

        Named rather than counted because a carrier that receives "validation
        failed" learns nothing and a carrier that receives "the sum of the lines
        is $4,760 and the total says $8,400" can answer the letter.
        """
        if self.can_file:
            return ""
        return "; ".join(f"{c.name}: {c.detail}" for c in self.failures)


def _check_line_sum(ledger: Ledger) -> Check:
    summed = sum((line.amount for line in ledger.lines), start=Decimal(0))
    passed = summed == ledger.stated_total
    detail = f"{len(ledger.lines)} line(s) sum to {summed}, stated total is {ledger.stated_total}"
    return Check("line_sum", CITE_TOTAL, passed, detail)


def _check_free_time_window(ledger: Ledger) -> Check:
    end = ledger.free_time_start + timedelta(days=ledger.allowed_free_time_days)
    passed = end == ledger.free_time_end
    detail = (
        f"free time starts {ledger.free_time_start} for "
        f"{ledger.allowed_free_time_days} day(s), which ends {end}, "
        f"but the invoice states {ledger.free_time_end}"
    )
    return Check("free_time_window", CITE_FREETIME_WINDOW, passed, detail)


def _check_charge_arithmetic(ledger: Ledger) -> Check:
    wrong = [
        f"line {i} ({line.container_number or '<no container>'}): "
        f"{line.chargeable_days} x {line.rate} is "
        f"{line.chargeable_days * line.rate}, not {line.amount}"
        for i, line in enumerate(ledger.lines, start=1)
        if line.chargeable_days * line.rate != line.amount
    ]
    passed = not wrong
    detail = f"all {len(ledger.lines)} line(s) multiply out exactly" if passed else "; ".join(wrong)
    return Check("charge_arithmetic", f"{CITE_RATE_RULE}, {CITE_TOTAL}", passed, detail)


def _check_identifiers_present(ledger: Ledger) -> Check:
    missing = [
        f"line {i} ({line.container_number or '<no container>'}) is missing "
        f"{'a bill of lading number' if line.container_number else 'both identifiers'}"
        for i, line in enumerate(ledger.lines, start=1)
        if not line.container_number or not line.bol_number
    ]
    passed = not missing
    detail = (
        f"all {len(ledger.lines)} line(s) carry a container and a bill of lading"
        if passed
        else "; ".join(missing)
    )
    return Check("identifiers_present", CITE_IDENTIFIERS, passed, detail)


def validate(ledger: Ledger) -> Report:
    """Run every check. Pure, deterministic, and total.

    The order is the order a person reads them in: does the invoice add up, does its
    timing add up, does its arithmetic add up, is it identified. A reader who stops
    at the first failure should stop at the one that explains the rest.
    """
    return Report(
        checks=(
            _check_line_sum(ledger),
            _check_free_time_window(ledger),
            _check_charge_arithmetic(ledger),
            _check_identifiers_present(ledger),
        )
    )
