"""Comparing a demand against a recomputed total, with a tolerance band.

This is the second independent path to the day count. The timing recomputation in
``engine/daycount.py`` works out how many days should have been charged from the
free time disclosures. This one works out what those days are worth from the rate
the carrier itself named, and checks the demand against it.

Two paths that disagree is a much stronger signal than either alone. A day count
that is wrong in one direction and a total that is right can both be plausible on
their own, and a carrier has to explain both.

The tolerance band is ours, and it is an estimate

Two percent. It is not sourced from anything. It is our judgement that a dispute
filed over a rounding difference costs more to pursue than it recovers, because a
carrier that sees five cents of noise will ignore the letter that contains it, and
the letter that contains it is also the one that finds the $4,800.

It is marked ESTIMATE here, per AGENTS.md section five, and it is applied to the
demand rather than to the recomputed total, so widening it for a larger invoice
does not need a second rule.

What the band is not for

It is not for a rate we are unsure of. An UNVERIFIED block compared with a
tolerance band produces a number that looks like a finding and rests on nothing,
and the marker travels on the result so it cannot be quoted without the caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quayline.models.invoice import CITE_RATE_RULE, CITE_RATES, CITE_TOTAL
from quayline.tariffs.blocks import RateBlock, Tier

# ESTIMATE, ours, not sourced. See the module docstring.
TOLERANCE = Decimal("0.02")


@dataclass(frozen=True, slots=True)
class AmountResult:
    """The comparison, and whether it found anything."""

    block: RateBlock
    chargeable_days: int
    declared_total: Decimal
    recomputed_total: Decimal
    difference: Decimal
    difference_pct: Decimal
    within_tolerance: bool
    breakdown: tuple[tuple[Tier, int, Decimal], ...]

    @property
    def overbilled(self) -> bool:
        return self.difference > 0 and not self.within_tolerance

    @property
    def quoted(self) -> str:
        """Whether the block is verified enough to be quoted in a letter.

        An UNVERIFIED block still produces a comparison, because the arithmetic is
        worth doing, but the result carries the marker and a caller should not put
        the number in front of a carrier without the caveat.
        """
        return (
            "VERIFIED"
            if self.block.verified
            else f"UNVERIFIED: {self.block.note or self.block.source}"
        )

    def as_letter_lines(self) -> list[str]:
        if self.within_tolerance:
            return [
                f"Recomputed total ${self.recomputed_total} against a demand of "
                f"${self.declared_total}, within the {TOLERANCE:.0%} tolerance band."
            ]
        verb = "exceeds" if self.difference > 0 else "falls below"
        lines = [
            f"{CITE_RATE_RULE} and {CITE_RATES} resolve to {self.block.rule}, under which "
            f"{self.chargeable_days} chargeable day(s) from the start of the stay come to "
            f"${self.recomputed_total}. The demand of ${self.declared_total} under "
            f"{CITE_TOTAL} {verb} that by ${abs(self.difference)} "
            f"({abs(self.difference_pct):.2%}), outside the {TOLERANCE:.0%} tolerance band.",
        ]
        for tier, days, subtotal in self.breakdown:
            lines.append(f"  {days} day(s) at {tier}, {subtotal}")
        if not self.block.verified:
            lines.append(f"  {self.quoted}")
        return lines


def compare(
    block: RateBlock,
    chargeable_days: int,
    declared_total: Decimal,
    *,
    tolerance: Decimal = TOLERANCE,
) -> AmountResult:
    """Price the days and compare against the demand.

    ``chargeable_days`` comes from the timing recomputation, not from
    ``len(charged_dates)``. The tiers are indexed from the start of the stay, so a
    gap in the billed dates shifts every band boundary and pricing the dates
    present would compound the error.
    """
    recomputed = block.price(chargeable_days)
    difference = declared_total - recomputed
    pct = (
        (difference / recomputed).quantize(Decimal("0.0001"))
        if recomputed > 0
        else (Decimal("0") if difference == 0 else Decimal("-1"))
    )
    band = abs(recomputed) * tolerance
    return AmountResult(
        block=block,
        chargeable_days=chargeable_days,
        declared_total=declared_total,
        recomputed_total=recomputed,
        difference=difference,
        difference_pct=pct,
        within_tolerance=abs(difference) <= band,
        breakdown=block.breakdown(chargeable_days),
    )


__all__ = ["CITE_RATES", "CITE_RATE_RULE", "CITE_TOTAL", "TOLERANCE", "AmountResult", "compare"]
