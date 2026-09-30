"""Issue 17: Maersk at cluster granularity, and the date that pins the rate.

Maersk publishes at cluster granularity, not per port. And its rates pin to the
**origin price calculation date**, not the invoice date: "the free time & charges
applied will be those in place on the origin price calculation date (PCD)". Source:
us-import-demurrage-tariff-effective-01-jan-2026-v2.pdf, header effective
2026-06-20.

A January 2026 rate rise does not reach a container loaded in December 2025. That
is a free win on misapplied-rate disputes and nobody exploits it, because every
engine in the category prices at the charge date or the invoice date. Both are
wrong for Maersk, and both are wrong in the carrier's favour whenever rates rose
in between.

Two lookups, not one

Resolving a Maersk charge takes two steps and they fail independently:

1. **Port to cluster.** Newark resolves to Newark NYC, Miami to Miami PEFLA, and
   so on. A port nobody mapped resolves to Default **with a note saying so**,
   because Default is a real cluster with real rates and silently treating an
   unknown port as Default would price it from a schedule that may not apply.
2. **Cluster plus PCD to block.** The rate in force on the price calculation
   date, not on the invoice date and not today. A block whose effective window
   does not contain the PCD is not the block that priced this container.

Maersk detention is UNVERIFIED and never modelled

The December 2025 advisory gives deltas only, plus ten dollars per tier at all US
locations with free days unchanged. Deltas without a base are not a schedule, and
a schedule built by adding ten dollars to a demurrage table would be a detention
table nobody published. So there is no detention block here, no detention rule in
the cluster map, and a detention query resolves to nothing. The advisory is
recorded so the next person to touch this file meets the reason before the gap.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The source. Header effective 2026-06-20.
SOURCE_PDF = "us-import-demurrage-tariff-effective-01-jan-2026-v2.pdf"
HEADER_EFFECTIVE = "2026-06-20"

#: The lock, verbatim. Quoted rather than paraphrased because it is the sentence a
#: letter will cite, and a paraphrase drifts toward the invoice date.
PCD_APPLICATION = (
    "Application: The free time & charges applied will be those in place on the "
    "origin price calculation date (PCD)"
)

#: The December 2025 advisory gives deltas only. Recorded so the gap is named
#: rather than discovered.
DETENTION_ADVISORY_NOTE = (
    "UNVERIFIED: the December 2025 advisory gives deltas only, plus $10 per tier "
    "at all US locations with free days unchanged. Deltas without a base are not "
    "a schedule. Maersk detention is never modelled from the advisory."
)

#: Port code to cluster, for the ports the tariff names. Anything else resolves to
#: Default with a note, per `resolve_cluster`, because an unmapped port priced
#: from Default silently would be a guess wearing a lookup.
PORT_TO_CLUSTER: dict[str, str] = {
    "USNYC": "Newark NYC",
    "USEWR": "Newark NYC",
    "USMIA": "Miami PEFLA",
    "USPEF": "Miami PEFLA",
    "USPHL": "Philadelphia",
}

DEFAULT_CLUSTER = "Default"


@dataclass(frozen=True, slots=True)
class ClusterResolution:
    """A port resolved to its cluster, with whether the mapping was direct."""

    cluster: str
    direct: bool
    note: str = ""

    @property
    def mapped(self) -> bool:
        return self.direct


def resolve_cluster(port: str) -> ClusterResolution:
    """Port code to cluster. Unmapped ports resolve to Default with a note.

    Default is a real cluster with real rates, so resolving an unknown port to it
    silently would price the container from a schedule that may not apply. The note
    travels with the resolution so the caller knows the mapping was assumed rather
    than transcribed.
    """
    cluster = PORT_TO_CLUSTER.get(port.upper())
    if cluster is not None:
        return ClusterResolution(cluster=cluster, direct=True)
    return ClusterResolution(
        cluster=DEFAULT_CLUSTER,
        direct=False,
        note=(
            f"port {port!r} is not mapped to a Maersk cluster, so Default was used. "
            f"Default is a real cluster, not a fallback rate, and the mapping should "
            f"be transcribed rather than assumed."
        ),
    )


@dataclass(frozen=True, slots=True)
class PCDCheck:
    """Whether the block in force on the price calculation date is the block that
    priced the container."""

    price_calculation_date: str
    block_effective_from: str
    block_effective_to: str | None

    @property
    def in_force(self) -> bool:
        """The block covered the PCD. When False, the carrier applied a rate that
        was not yet, or no longer, in force on the date that pins the price."""
        started = self.price_calculation_date >= self.block_effective_from
        unended = (
            self.block_effective_to is None
            or self.price_calculation_date <= self.block_effective_to
        )
        return started and unended

    def sentence(self) -> str:
        if self.in_force:
            return (
                f"The block in force on the price calculation date "
                f"{self.price_calculation_date} is the block applied. No PCD dispute."
            )
        return (
            f"Maersk pins free time and charges to the origin price calculation date "
            f"({self.price_calculation_date}), but the applied block runs "
            f"{self.block_effective_from}..{self.block_effective_to or 'open'}. "
            f"A January rate rise does not reach a December loading."
        )


def check_pcd(
    price_calculation_date: str, effective_from: str, effective_to: str | None = None
) -> PCDCheck:
    """Compare the invoice's PCD against the block's effective window."""
    return PCDCheck(
        price_calculation_date=price_calculation_date,
        block_effective_from=effective_from,
        block_effective_to=effective_to,
    )


__all__ = [
    "DEFAULT_CLUSTER",
    "DETENTION_ADVISORY_NOTE",
    "HEADER_EFFECTIVE",
    "PCD_APPLICATION",
    "PORT_TO_CLUSTER",
    "SOURCE_PDF",
    "ClusterResolution",
    "PCDCheck",
    "check_pcd",
    "resolve_cluster",
]
