"""Rate blocks and how to price a stay against one.

The tiers are indexed from the start of the stay, not from the first chargeable
day, and that is the whole difficulty.

A real schedule, transcribed from the Maersk US demurrage tariff, default cluster
dry container:

    1-4 free, 5-8 $300, 9-13 $345, 14+ $395

Six chargeable days against a four day allowance are days five through ten of the
stay. That is four days at $300 and two at $345, $1,890, and it is two different
tiers. Counting six days "from the first chargeable day" and pricing them as six
consecutive entries in the schedule prices days one through six, which are four
free days and two chargeable ones, and yields $600. The invoice is not wrong by
$1,290, it is priced against a schedule read from the wrong end.

So ``price`` takes the free time allowance and indexes the tiers from the stay
start. The allowance is not a discount bolted on afterwards, it is the offset that
puts the chargeable days in the right bands.

A gap in the billed days is not a gap in the stay

The tiers count days of the stay, so a carrier that bills days five, six, eight,
nine, ten and eleven of a ten day stay is still pricing a run of days from five.
The arithmetic belongs to the run, not to the set, and a check that priced the
dates present would move every tier boundary for a single missing day.

Which is why the pricing function takes a day count and not a set of dates, and
why the caller gets the day count from the timing recomputation in
``engine/daycount.py`` rather than from ``len(charged_dates)``.

Tiers must be contiguous and total

A schedule with a hole in it, or that stops short of the maximum stay anyone might
bill, cannot be priced. Rather than guess the missing rate, construction fails,
because a rate invented to fill a gap is a number that reaches a dispute letter
with no source behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

CENTS = Decimal("0.01")


class TierError(ValueError):
    """The schedule cannot be priced, and the reason is in the message."""


@dataclass(frozen=True, slots=True, order=True)
class Tier:
    """One band of a schedule.

    ``from_day`` and ``to_day`` are positions in the stay, one based, matching the
    tariff notation "5-8 $300". ``to_day`` is None for an open ended band, which is
    how "14+ $395" is written.
    """

    from_day: int
    to_day: int | None
    rate: Decimal

    def covers(self, stay_day: int) -> bool:
        return stay_day >= self.from_day and (self.to_day is None or stay_day <= self.to_day)

    def __str__(self) -> str:
        top = f"{self.to_day}" if self.to_day is not None else "+"
        return f"{self.from_day}-{top} ${self.rate}"


@dataclass(frozen=True, slots=True)
class RateBlock:
    """A dated schedule for one carrier, cluster and equipment combination.

    ``free_days`` is the allowance. It is stored here as well as on the invoice
    because the two can disagree, and when they do the invoice is what the carrier
    must be held to, so the disagreement is reported rather than silently resolved
    in the block's favour.

    ``effective_from`` and ``effective_to`` bound the block's life, and the
    containment check is a method rather than a lookup so a caller cannot pass a
    date without being told whether the block covers it.
    """

    rule: str
    carrier: str
    cluster: str
    equipment: str
    free_days: int
    tiers: tuple[Tier, ...]
    source: str
    effective_from: str
    effective_to: str | None = None
    verified: bool = True
    note: str = ""

    def __post_init__(self) -> None:
        if self.free_days < 0:
            raise TierError(f"{self.rule}: free days cannot be negative")
        if not self.tiers:
            raise TierError(f"{self.rule}: a schedule with no tiers cannot be priced")
        expected = 1
        for tier in self.tiers:
            if tier.from_day != expected:
                raise TierError(
                    f"{self.rule}: tier starts at day {tier.from_day}, expected day "
                    f"{expected}. A schedule with a hole in it cannot be priced and a "
                    f"rate invented to fill it would reach a dispute letter unsourced."
                )
            if tier.to_day is not None and tier.to_day < tier.from_day:
                raise TierError(f"{self.rule}: tier {tier} ends before it starts")
            if tier.to_day is not None:
                expected = tier.to_day + 1
        if self.tiers[-1].to_day is not None:
            raise TierError(
                f"{self.rule}: the last tier ends at day {self.tiers[-1].to_day} and a "
                f"carrier can hold a container longer than that. The last tier must be "
                f"open ended."
            )

    def tier_for(self, stay_day: int) -> Tier:
        for tier in self.tiers:
            if tier.covers(stay_day):
                return tier
        raise TierError(f"{self.rule}: no tier covers day {stay_day} of the stay")

    def price(self, chargeable_days: int) -> Decimal:
        """Price a run of chargeable days, indexed from the start of the stay.

        ``chargeable_days`` is the number of days charged, not a set of dates. The
        run occupies stay days ``free_days + 1`` through
        ``free_days + chargeable_days``, and the total is the sum of those
        positions under their own tiers.
        """
        if chargeable_days < 0:
            raise TierError(f"cannot price {chargeable_days} chargeable days")
        if chargeable_days == 0:
            return Decimal("0.00")
        total = Decimal("0.00")
        for offset in range(chargeable_days):
            total += self.tier_for(self.free_days + offset + 1).rate
        return total.quantize(CENTS, rounding=ROUND_HALF_UP)

    def breakdown(self, chargeable_days: int) -> tuple[tuple[Tier, int, Decimal], ...]:
        """Per tier, how many days fell in it and what they came to.

        The letter needs this, because "you charged $1,890" is an assertion and
        "four days at $300 under the 5-8 band and two at $345 under the 9-13 band
        is $1,890" is a demonstration.
        """
        counts: dict[Tier, int] = {}
        for offset in range(chargeable_days):
            tier = self.tier_for(self.free_days + offset + 1)
            counts[tier] = counts.get(tier, 0) + 1
        return tuple(
            (tier, days, (tier.rate * days).quantize(CENTS, rounding=ROUND_HALF_UP))
            for tier, days in sorted(counts.items(), key=lambda kv: kv[0].from_day)
        )

    def contains(self, on: str) -> bool:
        """Whether this block was in force on an ISO date."""
        if on < self.effective_from:
            return False
        return self.effective_to is None or on <= self.effective_to

    def max_chargeable_days(self) -> int | None:
        """The longest stay this schedule can price, or None if unbounded."""
        last = self.tiers[-1].to_day
        if last is None:
            return None
        return max(0, last - self.free_days)

    def chain(self) -> Self:
        """Self, kept for symmetry with a future multi block resolution."""
        return self
