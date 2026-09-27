"""Ocean Network Express: the availability clock, by dated regime.

ONE is the only major carrier keyed to cargo availability rather than vessel
discharge. Everyone else bills from discharge, so a charge that looks late against
the discharge date can be correct, and on ONE's own invoice the availability date
is a field the carrier certified itself. That makes this the most automatable
check in the category and the only one that needs no external data at all.

Three regimes, all transcribed from ONE's own policy pages, with the language as
published and the disclaimer that dates it.

The 2023 to 2024 window is UNVERIFIED and is not interpolated

There is a 560-day hole. From 2023-02-27 until 2024-09-08 we do not hold the text
of ONE's inbound demurrage clock, and the two regimes either side of it disagree
about the thing that matters, discharge against availability. A charge in that
window might be keyed either way and we cannot say which from anything we hold.

So ``basis_in_force`` returns ``None`` inside the gap rather than picking the
nearer regime. Interpolating would produce a confident answer, and on this
carrier a confident wrong answer is worse than no answer, because the whole
argument rests on the clock having started later than the carrier says. A wrong
answer here is not a weaker result, it is a letter that tells a carrier their
clock was keyed the way we hoped and produces a charge that should have been
paid.

That gap is not a rare edge. It covers the last ten months of 2023 and the first
eight of 2024, so a 2024 charge is often still inside a live dispute window.

A correction to the research corpus

docs/research/002-carriers.md dated the availability-keyed language to 2025-11-02.
That is the date of a different advisory. 2025-11-03 was the change to the default
payer for export demurrage and detention, and the ONE page carrying the clock
language is titled for that later policy while being dated 2024-09-09 in its own
disclaimer.

The research table had picked up the default payer advisory date and attached it
to the clock change. Corrected here, and corrected in the research note.

The 2023-02-27 boundary is also narrower than the note implied. ONE's advisory for
that date concerns OUTBOUND demurrage and the Demurrage Free Receiving Date, not
the inbound availability clock. The note read it as the start of a clock change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

# Transcribed 2026-09-27 from ONE's own policy pages. Each regime quotes the page
# that carries it, including the page's own effective-date disclaimer, because the
# disclaimer and the policy text disagree with our research note and the
# disclaimer wins.


class ClockBasis(StrEnum):
    """What the demurrage clock is keyed to.

    DISCHARGE means the clock runs from the vessel discharge. AVAILABILITY means it
    runs from the terminal making the container available. On ONE these are
    different by up to several days, and the difference is the dispute.
    """

    DISCHARGE = "discharge"
    AVAILABILITY = "availability"


@dataclass(frozen=True, slots=True)
class ClockRegime:
    """One dated regime, with the language ONE published to introduce it.

    ``effective_from`` and ``effective_to`` are inclusive, and either may be None to
    mean open ended. A regime whose bounds overlap another is a data error, and
    the tests assert the three windows are disjoint and gapless outside the
    unknown.
    """

    cite: str
    effective_from: date | None
    effective_to: date | None
    basis: ClockBasis
    text: str
    source: str
    disclaimer: str
    verified: bool

    def covers(self, on: date) -> bool:
        after_start = self.effective_from is None or on >= self.effective_from
        before_end = self.effective_to is None or on <= self.effective_to
        return after_start and before_end


@dataclass(frozen=True, slots=True)
class UnknownWindow:
    """A dated span where the clock basis is not known.

    A separate type rather than a regime with ``basis=None``, so that a caller
    iterating the regimes never picks it up by accident.
    """

    start: date
    end: date
    days: int
    reason: str

    def contains(self, on: date) -> bool:
        return self.start <= on <= self.end


REGIMES: tuple[ClockRegime, ...] = (
    ClockRegime(
        cite="ONE D&D policy prior to 2023-02-27",
        effective_from=None,
        effective_to=date(2023, 2, 26),
        basis=ClockBasis.DISCHARGE,
        text="Demurrage clock commences at freetime start, defined as the first full "
        "day after vessel discharge",
        source="https://us.one-line.com/DemDetPre2272023",
        disclaimer="Demurrage and Detention Prior to February 27, 2023",
        verified=True,
    ),
    ClockRegime(
        cite="ONE D&D policy effective 2024-09-09",
        effective_from=date(2024, 9, 9),
        effective_to=date(2026, 3, 31),
        basis=ClockBasis.AVAILABILITY,
        text="The demurrage clock commences at the start of the next full working day "
        "after the container is made available for pick-up after vessel discharge",
        source="https://us.one-line.com/DemDetPre11032025",
        disclaimer="This policy is effective September 9th, 2024.",
        verified=True,
    ),
    ClockRegime(
        cite="ONE D&D policy effective 2026-04-01",
        effective_from=date(2026, 4, 1),
        effective_to=None,
        basis=ClockBasis.AVAILABILITY,
        text="The demurrage clock commences on the first full day when the "
        "container(s) is available for pick-up after vessel discharge",
        source="https://us.one-line.com/demurragedetention",
        disclaimer="This policy is effective April 1, 2026.",
        verified=True,
    ),
)

# The window we cannot answer for. Not a regime, deliberately, so that no caller
# can reach it by iterating REGIMES and picking the nearest match.
UNKNOWN_WINDOW = UnknownWindow(
    start=date(2023, 2, 27),
    end=date(2024, 9, 8),
    days=560,
    reason=(
        "ONE's inbound demurrage clock text for this window has not been obtained. The "
        "regime before it is discharge-based and the regime after it is availability-"
        "based, so interpolating either way produces a confident answer to a question "
        "we cannot answer."
    ),
)


@dataclass(frozen=True, slots=True)
class Lookup:
    """The answer for one date, which may be that there is no answer."""

    on: date
    regime: ClockRegime | None
    unknown: UnknownWindow | None

    @property
    def basis(self) -> ClockBasis | None:
        """The clock basis, or None inside the unknown window.

        None is a real answer, not an error. A caller that needs a basis has to
        handle the case where we do not have one, which is the point of modelling
        the gap rather than smoothing over it.
        """
        return None if self.regime is None else self.regime.basis

    @property
    def resolved(self) -> bool:
        return self.regime is not None

    def require_basis(self) -> ClockBasis:
        """Basis or an explicit refusal.

        For the code path that computes chargeable days. It cannot guess, so it
        raises rather than defaulting, and the defaulting is what would silently
        produce a wrong chargeable day count for 2024 invoices.
        """
        regime = self.regime
        if regime is not None:
            return regime.basis
        window = self.unknown
        if window is None:
            raise LookupError(f"no ONE clock basis on {self.on.isoformat()}")
        raise LookupError(
            f"ONE's clock basis on {self.on.isoformat()} is UNVERIFIED. It falls inside "
            f"the {window.days} day window {window.start} to {window.end} for which we "
            f"do not hold the policy text. Do not interpolate."
        )


def basis_in_force(on: date) -> Lookup:
    """Resolve the clock regime in force on a date.

    Inside the unknown window this returns a Lookup with no regime. That is the
    designed behaviour, not a limitation that will be filled in later by guessing.
    """
    for regime in REGIMES:
        if regime.covers(on):
            return Lookup(on=on, regime=regime, unknown=None)
    if UNKNOWN_WINDOW.contains(on):
        return Lookup(on=on, regime=None, unknown=UNKNOWN_WINDOW)
    raise LookupError(f"no ONE clock regime covers {on.isoformat()} and it is not in the known gap")


__all__ = [
    "REGIMES",
    "UNKNOWN_WINDOW",
    "ClockBasis",
    "ClockRegime",
    "Lookup",
    "UnknownWindow",
    "basis_in_force",
]
