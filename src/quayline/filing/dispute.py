"""Issue 176: turning an audit result into a dispute packet.

The last break in the chain. Bytes go in, an ``AuditResult`` comes out, and without
this module the letter stops there.

Why one letter renderer and not two

``evidence/packet.py`` and ``engine/ordering.py`` both render. The decision recorded
in issue 176 is that a claim is a concession, and a carrier concedes one thing at a
time, so the filed document is grouped by ground. ``packet.render`` groups by ground
and is the letter. ``ordering.strategy_for`` stays as the metadata the packet carries
about itself, and ``ordering.render_letter`` was renamed ``render_digest`` rather
than deleted: it renders the tier order and no evidence, so it is a triage view and
not a second opinion on what gets sent.

Which findings become automatic claims

A finding grounded in ``Ground.DISCLOSURE_OMITTED`` is automatic. 541.5 makes the
remedy apply without a showing from us because the carrier failed to make a
disclosure the regulation requires. There is nothing left to establish.

Everything else needs evidence, and ``assemble`` blocks it when there is none. That
asymmetry is load bearing: an omission filed as contested demands evidence we do not
have, and a contested claim filed as automatic asserts a fact we cannot support.

Money never comes from a guess

``amount_at_stake`` is the money already on the ``AuditResult``. Where the document
stated no total and the tariff did not resolve, it is ``None`` and it stays ``None``.
A claim saying zero dollars is a claim about the carrier's arithmetic that we have
not made.

Two findings on one ground merge rather than raising

``assemble`` refuses two claims on one ground, because two sections under one heading
let a carrier concede one and refuse the other without appearing to contradict
itself. The engine legitimately produces two day-count findings on the same ground,
as it does on the real fixture, so the builder merges their days rather than passing
the duplicate through and crashing. Merging is the only option that keeps the one
ground one section rule intact.
"""

from __future__ import annotations

from decimal import Decimal

from quayline.engine.result import (
    CODE_AMOUNT_VARIANCE,
    CODE_AVAILABILITY_CONTRADICTION,
    CODE_DAYCOUNT_VARIANCE,
    AuditResult,
    Finding,
)
from quayline.evidence.checklist import Ground
from quayline.evidence.packet import Claim, EvidenceItem, Packet, assemble

#: The code to the claim title it produces. A code is a stable identifier and a
#: title is a sentence, so they live apart and only meet here.
_TITLES: dict[str, str] = {
    CODE_DAYCOUNT_VARIANCE: "Chargeable days exceed the disclosed allowance",
    CODE_AMOUNT_VARIANCE: "The charge exceeds the recomputed amount",
    CODE_AVAILABILITY_CONTRADICTION: "Charged from a date before availability",
}

#: The codes that stand for money, where the result carries any. A code absent from
#: this set produces a claim with no amount rather than a zero amount.
_MONEY_CODES = frozenset({CODE_AMOUNT_VARIANCE, CODE_DAYCOUNT_VARIANCE})


def _is_automatic(finding: Finding) -> bool:
    """Whether the remedy applies without a showing from us.

    541.5 omission only. A finding carrying no ground is not automatic, because we
    cannot tell what kind of claim it is and refusing to guess is the posture of
    this whole package.
    """
    return Ground.DISCLOSURE_OMITTED in finding.grounds


def _amount_for(finding: Finding, result: AuditResult) -> Decimal | None:
    """The money this claim stands for, or ``None``.

    Only where the result actually computed money. The variance is the demand minus
    the recomputation, so it is what a successful dispute would credit, and it is
    ``None`` whenever either side was unknown. A negative variance is not money we
    would claim, so it is ``None`` rather than an absolute value.
    """
    if finding.code not in _MONEY_CODES:
        return None
    if result.variance is None or result.variance <= 0:
        return None
    return result.variance


def claims_for(result: AuditResult) -> tuple[tuple[Claim, ...], tuple[EvidenceItem, ...]]:
    """The claims and evidence an audit result supports.

    Split out from :func:`dispute_for` so a caller that wants to attach its own
    evidence has somewhere to start, and so a test can check the builder against
    ``assemble`` rather than only against the finished packet.
    """
    claims: list[Claim] = []
    position: dict[Ground, int] = {}
    #: Deliberately always empty. A contested claim gets no evidence item from the
    #: finding that produced it, because a fabricated EvidenceItem would satisfy the
    #: packet gate without attesting to anything. The gate is only real while a
    #: contested claim arrives with no evidence and blocks. Evidence comes from
    #: ``filing.evidence.attach_capture`` and from nowhere else.
    evidence: tuple[EvidenceItem, ...] = ()

    for finding in result.findings:
        grounds = finding.grounds or (Ground.DISCLOSURE_OMITTED,)
        ground = grounds[0]
        automatic = _is_automatic(finding)
        amount = _amount_for(finding, result)

        if ground in position:
            at = position[ground]
            existing = claims[at]
            claims[at] = Claim(
                ground=ground,
                title=existing.title,
                days=tuple(sorted(set(existing.days) | set(finding.days))),
                amount_at_stake=existing.amount_at_stake or amount,
                basis=existing.basis or finding.cite,
                automatic=existing.automatic and automatic,
            )
            continue

        position[ground] = len(claims)
        claims.append(
            Claim(
                ground=ground,
                title=_TITLES.get(finding.code, finding.summary or finding.code),
                days=tuple(sorted(finding.days)),
                amount_at_stake=amount,
                basis=finding.cite,
                automatic=automatic,
            )
        )

    return tuple(claims), evidence


def dispute_for(result: AuditResult) -> Packet:
    """The packet for an audit result, assembled by the packet module itself.

    Grouping, ordering and the blocked marks all come from
    ``evidence.packet.assemble``. Nothing here reimplements them, because a second
    copy of the grouping rules is a second opinion on what a concession is.
    """
    claims, evidence = claims_for(result)
    return assemble(claims, evidence)


__all__ = ["claims_for", "dispute_for"]
