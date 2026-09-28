"""Issue 59: the packet, with each ground carrying only the evidence for it.

A packet that mixes grounds is not a bad packet, it is a packet that cannot be
worked. A carrier's dispute respondent reads it, decides which parts they can
concede, and closes the rest. If the evidence for a government hold is sitting
underneath a day count claim, the respondent has to unweave it before they can
concede anything, and the easiest response to a packet that takes work is to
reject the packet.

Grounds, not categories

Grouping by category is the obvious design and it is the wrong one. "Timing" and
"documentation" are not grounds, they are filing instructions, and putting the
service contract under documentation means the respondent has to work out which of
nine claims it actually supports. A ground is the thing the carrier has to
concede or refuse, and there is one packet section per ground.

Automatic claims first

A claim resting on a disclosure the carrier did not make is automatic. 46 U.S.C.
41104(d) and the 541.5 note make the remedy apply without notice, without a cure
period, and without a showing of prejudice, so there is nothing for us to prove
and no evidence to file. Those go first, for two reasons. The reader learns what
this dispute is actually about before they hit the parts that need work, and a
respondent who concedes the automatic claims has conceded the dispute, which
changes what the rest of the packet is for.

The fail-closed rule

A ground with no evidence is reported as blocked. It is never silently omitted,
and this is the property the whole module exists to guarantee. The failure is not
that we drop a ground, it is that we quietly file the other eight and discover the
omission eleven weeks later when the claim is time barred. A packet that says it
is blocked is a packet somebody can act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from quayline.evidence.checklist import Artifact, Ground

#: Dates printed before a claim's day list is summarised.
_DAYS_SHOWN = 3


@dataclass(frozen=True, slots=True)
class Claim:
    """One thing being disputed, on one ground.

    ``automatic`` means the remedy applies without a showing from us, because the
    carrier failed to make a disclosure 541.6 requires. It does not mean the claim
    is easy to establish; it means there is nothing left to establish.
    """

    ground: Ground
    title: str
    days: tuple[date, ...] = ()
    amount_at_stake: Decimal | None = None
    basis: str = ""
    automatic: bool = False

    @property
    def needs_evidence(self) -> bool:
        return not self.automatic


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One artifact, attached to exactly one ground.

    The single ground is the point. An item that supports two grounds is two
    items, filed twice, and the duplication is visible to the reader instead of
    being an assumption buried in a helper.
    """

    ground: Ground
    kind: Artifact
    description: str
    source: str = ""

    def __str__(self) -> str:
        return f"{self.kind.value} ({self.description})"


@dataclass(frozen=True, slots=True)
class GroundSection:
    """One ground, its claim, its evidence, and whether it can be filed."""

    claim: Claim
    evidence: tuple[EvidenceItem, ...]
    blocked: bool
    reason: str = ""

    @property
    def is_automatic(self) -> bool:
        return self.claim.automatic


@dataclass(frozen=True, slots=True)
class Packet:
    """The assembled packet, in claim order, automatic claims first."""

    sections: tuple[GroundSection, ...] = field(default_factory=tuple)

    @property
    def blocked_sections(self) -> tuple[GroundSection, ...]:
        return tuple(s for s in self.sections if s.blocked)

    @property
    def can_file(self) -> bool:
        """The gate. Any blocked ground blocks the whole packet.

        Not "the unblocked ones still get filed". A packet with one blocked ground
        is a packet whose day count is wrong, and filing eight of nine claims
        against a carrier while quietly dropping the ninth is how a partial win
        becomes a total loss on the tenth.
        """
        return not self.blocked_sections

    def reason_not_filed(self) -> str:
        if self.can_file:
            return ""
        return "; ".join(f"{s.claim.ground.value}: {s.reason}" for s in self.blocked_sections)

    def section_for(self, ground: Ground) -> GroundSection | None:
        return next((s for s in self.sections if s.claim.ground is ground), None)

    def evidence_for(self, ground: Ground) -> tuple[EvidenceItem, ...]:
        """Only the evidence for one ground. Never anything else."""
        section = self.section_for(ground)
        return section.evidence if section else ()


def order_claims(claims: tuple[Claim, ...]) -> tuple[Claim, ...]:
    """Claim order, automatic claims first.

    A stable sort, so two automatic claims stay in the order they were given. A
    claim order that reshuffles on every run is a packet that is hard to diff
    between two drafts of the same letter, and the diff is most of the review.
    """
    return tuple(sorted(claims, key=lambda c: not c.automatic))


def assemble(claims: tuple[Claim, ...], evidence: tuple[EvidenceItem, ...] = ()) -> Packet:
    """Group evidence by ground, order the claims, and mark the blocked ones.

    Pure. Two claims on one ground is refused, because a ground is one concession
    and two sections under a single heading let a carrier concede one and refuse
    the other without ever appearing to contradict itself.

    Evidence attached to a ground nothing is claimed on is dropped rather than
    creating a phantom section, and :func:`orphaned_evidence` reports it. It is
    always a caller bug, never a data condition, and a bug that silently discards
    evidence is the kind that gets found after filing.
    """
    ordered = order_claims(claims)
    seen: set[Ground] = set()
    for claim in ordered:
        if claim.ground in seen:
            msg = (
                f"two claims on {claim.ground.value}. A ground is one section, and two "
                f"sections for one concession means the carrier can concede one and "
                f"refuse the other inside a single heading"
            )
            raise ValueError(msg)
        seen.add(claim.ground)

    sections: list[GroundSection] = []
    for claim in ordered:
        own = tuple(e for e in evidence if e.ground is claim.ground)
        if claim.needs_evidence and not own:
            sections.append(
                GroundSection(
                    claim=claim,
                    evidence=(),
                    blocked=True,
                    reason=(
                        "no evidence attached to this ground. Filing it would assert a "
                        "fact we cannot support, and omitting it silently would lose the "
                        "claim without telling anyone"
                    ),
                )
            )
        else:
            sections.append(GroundSection(claim=claim, evidence=own, blocked=False))
    return Packet(tuple(sections))


def orphaned_evidence(
    claims: tuple[Claim, ...], evidence: tuple[EvidenceItem, ...]
) -> tuple[EvidenceItem, ...]:
    """Evidence attached to a ground nothing is claimed on.

    Returned rather than raised so a caller can build the rest of the packet and
    still be told.
    """
    grounds = {c.ground for c in claims}
    return tuple(e for e in evidence if e.ground not in grounds)


def render(packet: Packet) -> str:
    """The packet, as text.

    A renderer that returns a string is chosen over one that returns objects
    because the output of this is a letter, and the letter is what gets reviewed,
    diffed, and sent. Anything that cannot be read as text cannot be reviewed.
    """
    if not packet.sections:
        return "No claims. There is no dispute to make.\n"

    automatic = [s for s in packet.sections if s.is_automatic]
    contested = [s for s in packet.sections if not s.is_automatic]
    out: list[str] = []

    def emit(section: GroundSection) -> None:
        claim = section.claim
        out.append(f"## {claim.title}")
        out.append(f"Ground: {claim.ground.value}")
        basis = (
            "automatic, no showing required" if claim.automatic else (claim.basis or "not stated")
        )
        out.append(f"Basis: {basis}")
        if claim.days:
            shown = ", ".join(d.isoformat() for d in claim.days[:_DAYS_SHOWN])
            more = (
                f" (+{len(claim.days) - _DAYS_SHOWN} more)" if len(claim.days) > _DAYS_SHOWN else ""
            )
            out.append(f"Days ({len(claim.days)}): {shown}{more}")
        if claim.amount_at_stake is not None:
            out.append(f"Amount at stake: {claim.amount_at_stake}")
        if section.blocked:
            out.append(f"NOT FILED: {section.reason}")
        else:
            out.append("Evidence:")
            if not section.evidence:
                out.append("  none required, this ground is automatic")
            for item in section.evidence:
                out.append(f"  - {item}")
        out.append("")

    out.append("Automatic claims")
    out.append("=" * len("Automatic claims"))
    out.append("These need nothing from you. The disclosure was not made.")
    out.append("")
    for section in automatic:
        emit(section)

    out.append("Contested claims")
    out.append("=" * len("Contested claims"))
    out.append("These rest on facts, and the evidence is with each one.")
    out.append("")
    for section in contested:
        emit(section)

    if packet.blocked_sections:
        out.append("This packet cannot be filed as it stands.")
        for section in packet.blocked_sections:
            out.append(f"  - {section.claim.ground.value}: {section.reason}")
    return "\n".join(out) + "\n"
