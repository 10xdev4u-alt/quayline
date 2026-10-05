"""Issue 84: whether a rate resolves *here*, not merely *for this carrier*.

The per-carrier report says Maersk is held and Hapag-Lloyd is not. That is true and it is not
the question an operator actually has. The question is whether the charge on the container
sitting at their gateway can be recomputed, and coverage genuinely varies by gateway within a
single carrier:

- **MSC publishes no US import demurrage tariff at all but one gateway.** Port Everglades is
  direct; fifteen terminal names are pass-through, where the controlling schedule belongs to
  the terminal operator and MSC has nothing to publish. A per-carrier row cannot express that,
  because "MSC" is simultaneously supported at one port and unsupportable at fifteen.
- **Hapag-Lloyd is the only carrier publishing per-terminal granularity.** We hold a schedule
  for ten terminals, transcribed from its own port table, and it gives the free-time notation
  and the tier unit. The rate tiers are *not* transcribed, so at every one of those ten
  gateways we hold the basis and not the price.

So this module answers the per-gateway question and reports three states, not two.

**Priced.** A ``RateBlock`` exists, so a figure resolves.
**Basis only.** We hold what determines the shape of the charge, such as free-time notation and
tier unit, and not the money. Enough to tell a reader whether a weekend costs nothing, and not
enough to compute what Tuesday costs.
**Unpublished.** The carrier itself has no tariff at that gateway. No amount of our effort
changes this one, and saying so is more useful than a row that implies a gap we could close.

Nothing here is a ``RateBlock``, so nothing here can produce a figure. A gateway report that
returned a number would be the overclaim this repository exists to avoid.

## Why this is not duplicated

The gateway lists are read from ``hapag_terminals.SCHEDULES`` and ``msc`` rather than restated,
for the reason ``cli/coverage_cmd.py`` gives for the carrier list: a report that keeps its own
copy of the data is wrong within a month and nobody notices.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.hapag_terminals import SCHEDULES
from quayline.tariffs.msc import DIRECT_TARIFF_PORT, PASS_THROUGH_TERMINALS

__all__ = ["GatewayRow", "Resolution", "gateway_rows"]

#: What we can say about one gateway.
#:
#: ``UNPUBLISHED`` is the one that is easy to leave out and the one that matters most. A reader
#: who is told "MSC not held" may go and acquire the tariff, and find there is nothing to
#: acquire. The truthful answer is that the controlling instrument belongs to somebody else.
Resolution = Literal["priced", "basis only", "unpublished", "nothing held"]


@dataclass(frozen=True, slots=True)
class GatewayRow:
    """One gateway, for one carrier, with the reason attached.

    ``reason`` is required rather than optional. A state without a reason is the thing this
    whole module exists to avoid, because "not held" and "not published" lead to opposite
    responses from the person reading it.
    """

    carrier: str
    gateway: str
    resolution: Resolution
    reason: str

    def headline(self) -> str:
        """One line for the human report."""
        return f"{self.carrier:<14} {self.gateway:<24} {self.resolution}"


def _maersk_gateways() -> Iterator[GatewayRow]:
    """Maersk, at the granularity Maersk actually publishes.

    Maersk's schedules are cluster-wide rather than per terminal, so one cluster covers many
    gateways and naming each of them individually would be a claim about granularity the
    source does not support. Reporting the cluster and saying so is more honest than
    enumerating ports we cannot distinguish.
    """
    for block in load_corpus().values():
        if block.carrier != "Maersk":
            continue
        yield GatewayRow(
            carrier="Maersk",
            gateway=f"cluster {block.cluster}",
            resolution="priced",
            reason=f"tariff transcribed for rule {block.rule}",
        )


def _hapag_gateways() -> Iterator[GatewayRow]:
    """Hapag-Lloyd's ten per-terminal schedules, all of them basis only.

    ``hapag_terminals`` is explicit that the rate tiers are not transcribed, so every one of
    these resolves to a shape and not to a price. Reported per gateway because Hapag is the
    carrier where the difference between terminals is largest and most consequential.
    """
    for schedule in SCHEDULES:
        yield GatewayRow(
            carrier="Hapag-Lloyd",
            gateway=schedule.terminal,
            resolution="basis only",
            reason=(
                f"free time {schedule.free_time} and {schedule.tier_unit} basis transcribed "
                f"from {schedule.source_pdf}; rate tiers are not transcribed, so no figure "
                f"resolves"
            ),
        )


def _msc_gateways() -> Iterator[GatewayRow]:
    """MSC's one direct gateway and its pass-through terminals, which are not its to publish.

    Sorted because the pass-through list pairs several terminal names to one code, and the
    report is read by humans comparing rows.
    """
    yield GatewayRow(
        carrier="MSC",
        gateway=DIRECT_TARIFF_PORT,
        resolution="nothing held",
        reason=(
            "MSC publishes a direct US import demurrage tariff here, so one exists to acquire; "
            "none is transcribed"
        ),
    )
    for name, code in sorted(PASS_THROUGH_TERMINALS):
        suffix = f" ({code})" if code else ""
        yield GatewayRow(
            carrier="MSC",
            gateway=f"{name}{suffix}",
            resolution="unpublished",
            reason=(
                "MSC publishes no US import demurrage tariff at this gateway. It passes "
                "terminal demurrage through at cost, so the controlling schedule belongs to "
                "the terminal operator and there is nothing for us to acquire."
            ),
        )


def gateway_rows() -> tuple[GatewayRow, ...]:
    """Every gateway we can say something definite about, in a stable order.

    Only carriers with per-gateway structure appear. A carrier whose coverage is uniform
    across the country adds a row saying so, which is what the per-carrier report is for.
    """
    rows = (*_maersk_gateways(), *_hapag_gateways(), *_msc_gateways())
    return tuple(sorted(rows, key=lambda row: (row.carrier, row.resolution, row.gateway)))


def summarise() -> dict[str, int]:
    """Counts per resolution, for the JSON output and for the header line.

    ``unpublished`` is reported first in the human rendering for the same reason it exists:
    it is the count that tells a reader where to stop looking.
    """
    counts: dict[str, int] = {}
    for row in gateway_rows():
        counts[row.resolution] = counts.get(row.resolution, 0) + 1
    return counts
