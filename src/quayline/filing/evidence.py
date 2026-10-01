"""Issue 181: attaching a capture to a claim.

Issue 176 built a packet where automatic claims file and contested claims block.
Correct, and it means no contested claim had ever been filed by this code, because
nothing put evidence on one. This is the join.

What this module is

A capture, checked, turned into an ``EvidenceItem`` that a ground's claim can carry.
The checks are the substance and the conversion is three lines.

Three refusals, each for a named reason

**Unauthenticated.** ``Capture`` requires a ``Capturer`` by type, which stops an
unattributed record being constructed. It does not make the capturer *correct*,
because Python does not check argument types, and ``Capture.is_authenticated`` exists
precisely for that. A record whose capturer is a bare string reports itself as
attested unless something checks.

**Expired.** ``docs/research/004-evidence.md`` records a one year limit on
recorded-image availability. The window runs forward from when the evidence was
taken, because that is when the dispute's clock started running against the carrier.
Filing on expired evidence loses the claim, and a capture that expires silently is
worse than one that never attached.

**Wrong ground.** ``assemble`` drops evidence attached to a ground nothing claims on,
and ``orphaned_evidence`` reports it. That behaviour is right, and it is why
attachment is a function rather than a field: the ground is checked against the claim
set by the assembler, and this module's job is to refuse the artifacts that should
never have been offered.

The digest travels

``EvidenceItem.source`` carries the sha256, so a carrier or a panel can check the
artifact against the letter. A digest computed from the bytes we hold is only worth
something if it reaches the document, and ``Capture.from_bytes`` already refuses a
caller supplied one.
"""

from __future__ import annotations

from datetime import date

from quayline.evidence.capture import Capture, Register, Retained, Retention
from quayline.evidence.checklist import Artifact, Ground
from quayline.evidence.packet import Claim, EvidenceItem, GroundSection, Packet

#: The artifact a ground asks for when the caller does not name one. Named the way
#: the carrier names it, because a carrier does not ask for a file.
_DEFAULT_ARTIFACT: dict[Ground, Artifact] = {
    Ground.APPOINTMENT_UNAVAILABLE: Artifact.APPOINTMENT_SCREENSHOT,
    Ground.CONTRACT_CONDITION: Artifact.SERVICE_CONTRACT,
    Ground.GOVERNMENT_HOLD: Artifact.EXPLANATION,
}


class EvidenceRefusedError(RuntimeError):
    """The capture cannot be attached, and says which of the three reasons why."""


def _source_for(capture: Capture) -> str:
    """The provenance string on the evidence item.

    Digest first, because it is the part a third party can check. The artifact id
    comes with it because a digest identifies a file, not which file in this dispute
    it is.
    """
    return f"sha256:{capture.sha256} ({capture.artifact_id})"


def attach_capture(
    capture: Capture,
    ground: Ground,
    artifact: Artifact | None = None,
    *,
    as_of: date | None = None,
    retention: Retention | None = None,
) -> EvidenceItem:
    """Turn a capture into an evidence item for one ground.

    Refuses an unattested capture and an expired one, both with the reason in the
    message. ``as_of`` is the date the dispute is being assessed on, which is not
    necessarily today, because a packet assembled for filing on a deadline needs the
    state of the evidence on that deadline rather than on the day it was printed.
    """
    if not capture.is_authenticated():
        raise EvidenceRefusedError(
            f"capture {capture.artifact_id} is not authenticated: we cannot say who "
            f"took it or when, so it cannot support a claim. The capturer type makes "
            f"attribution required and is_authenticated makes it verified."
        )

    if as_of is not None:
        window = retention or Retention(as_of=as_of)
        state = window.state(capture)
        if state is not Retained.REQUIRED:
            remaining = window.days_remaining(capture)
            raise EvidenceRefusedError(
                f"capture {capture.artifact_id} expired on "
                f"{window.expires_on(capture).isoformat()}, {abs(remaining)} day(s) "
                f"before {as_of.isoformat()}. The evidence standard in "
                f"docs/research/004-evidence.md records a one year limit on a "
                f"recorded image, and a claim filed on expired evidence loses it."
            )

    return EvidenceItem(
        ground=ground,
        kind=artifact or _DEFAULT_ARTIFACT.get(ground, Artifact.EXPLANATION),
        description=capture.artifact_id,
        source=_source_for(capture),
    )


def items_for(
    claims: tuple[Claim, ...],
    register: Register,
    *,
    as_of: date | None = None,
) -> tuple[EvidenceItem, ...]:
    """Every evidence item a set of claims can carry from a register.

    Only grounds that are claimed *and* need evidence get one. An automatic claim
    demands nothing, so attaching a screenshot to it is noise in the letter.

    Each capture is passed through :func:`attach_capture`, so a forged or expired
    record in the register refuses here rather than becoming an item nobody checked.
    A register can hold either, because a register is a container and containers do not
    validate their contents.
    """
    wanted = {claim.ground for claim in claims if claim.needs_evidence}
    items: list[EvidenceItem] = []
    for capture in register.captures:
        for ground in sorted(wanted, key=lambda g: g.value):
            items.append(attach_capture(capture, ground, as_of=as_of))
    return tuple(items)


def blockers_for(packet: Packet) -> tuple[GroundSection, ...]:
    """The grounds blocking a packet, and why each one is blocked.

    A thin read over ``Packet.blocked_sections`` that returns the sections rather
    than the joined reason string, because a caller that wants to say which artifact
    is missing needs the ground and cannot get it back out of a string.
    """
    return packet.blocked_sections


__all__ = [
    "EvidenceRefusedError",
    "attach_capture",
    "blockers_for",
    "items_for",
]
