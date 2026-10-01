"""Issue 34: what the letter leads with, and why.

A letter that leads with the availability argument and buries a 541.5 omission gets
read as a negotiation. A letter that leads with the omission gets read as a
compliance notice. Those are different documents and they get different responses,
so the order is not a presentation preference, it is the argument.

The four tiers

``HARD_VOID``
    A required 541.6 disclosure is absent. 541.5 fires with no notice, no cure period
    and no showing of prejudice. There is no argument to make and no relationship
    needed, which means leading with anything else spends the reader's attention on
    our weaker point first.

``DEADLINE``
    Invoiced outside the 541.7(a) window, or a dispute window shorter than Part 541
    allows. Wins on the face of the rule. Still not an omission, so still not a kill
    switch, but it needs no evidence packet and no witness, which is what makes it
    second.

``ARITHMETIC``
    The day count and the money. Recomputed from the carrier's own disclosures, so
    it is arithmetic rather than argument. It is strong and it is the most expensive
    to explain, because the reader has to follow a computation before they can
    evaluate it.

``SOFT_DEFECT``
    Stated but conclusory, unevidenced, or otherwise imperfect. Real, worth sending,
    and it must not be allowed to imply a stronger case than it carries.

Why this order and not strongest-first

A reader processes the first claim by deciding what kind of document this is. Lead
with arithmetic and they have already begun treating it as a computation to check,
and the omission later in the letter reads as a second complaint rather than as the
event that makes the rest unnecessary.

Lead with the omission and the letter is a compliance notice from the first line. The
carrier's internal routing sends it to whoever owns regulatory compliance, and the
deadline and arithmetic claims get answered by the person who was not going to
concede them anyway.

So the order is by **strength of remedy**, not by strength of evidence, and not by
how much work each claim took us to establish. The cheapest claim to prove leads,
because it is the one the reader can act on immediately.

What this is not

It is not a priority queue and there is no partial order. Two findings in the same
tier are ordered by the number of days at stake, then by their code, so the output is
deterministic and two runs over the same audit produce the same letter. A letter that
reshuffles between drafts cannot be diffed, and the diff is most of the review.

It is also not a waiver. Ordering does not drop anything, does not mark anything
soft, and does not change whether the audit can be filed. That is
``engine.result.can_file`` and it is not this module's business.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quayline.engine.result import (
    CODE_AMOUNT_VARIANCE,
    CODE_AVAILABILITY_CONTRADICTION,
    CODE_DAYCOUNT_VARIANCE,
    CODE_EVIDENCE_MISSING,
    CODE_FIELD_OMITTED,
    CODE_TARIFF_UNRESOLVED,
    CODE_VALIDATION_FAILED,
    AuditResult,
    Finding,
)

#: The tier a finding belongs to. Ordered by strength of remedy, which is not the
#: same as order of discovery and not the same as how much work it took.
TIER_HARD_VOID = "hard void"
TIER_DEADLINE = "deadline"
TIER_ARITHMETIC = "arithmetic"
TIER_SOFT_DEFECT = "soft defect"

#: Every code to its tier. A closed map, so a finding whose code is not here is a
#: decision someone has not made yet, and the sort says so rather than guessing.
TIER_BY_CODE: dict[str, str] = {
    # 541.5. The only automatic remedy in the category.
    CODE_FIELD_OMITTED: TIER_HARD_VOID,
    # 541.7(a). Wins on the face of the rule, needs no evidence packet.
    "deadline_window_exceeded": TIER_DEADLINE,
    "dispute_window_short": TIER_DEADLINE,
    # Recomputed from the carrier's own disclosures. Arithmetic, not argument.
    CODE_DAYCOUNT_VARIANCE: TIER_ARITHMETIC,
    CODE_AMOUNT_VARIANCE: TIER_ARITHMETIC,
    # Internal contradiction. Strong, and it reads as arithmetic because it is two
    # disclosed numbers that cannot both be true.
    CODE_AVAILABILITY_CONTRADICTION: TIER_ARITHMETIC,
    # Everything below is real and worth sending, and must not imply more.
    CODE_TARIFF_UNRESOLVED: TIER_SOFT_DEFECT,
    CODE_VALIDATION_FAILED: TIER_SOFT_DEFECT,
    CODE_EVIDENCE_MISSING: TIER_SOFT_DEFECT,
    "liability_basis_conclusory": TIER_SOFT_DEFECT,
}

#: A code nobody has classified. Not a fifth tier and not a hard void: a finding that
#: has not been placed should not lead a letter, and should be visible rather than
#: silently dropped.
TIER_UNCLASSIFIED = "unclassified"


def tier_of(finding: Finding) -> str:
    return TIER_BY_CODE.get(finding.code, TIER_UNCLASSIFIED)


@dataclass(frozen=True, slots=True)
class OrderedFinding:
    """A finding with everything the sort needs, and nothing else.

    ``days_at_stake`` is the tiebreak within a tier. It is a count, not money,
    because a dollar figure needs a tariff we may not hold and a day count does not.
    Comparing two claims by dollars would mean pricing at least one of them from a
    rate the carrier never certified.
    """

    finding: Finding
    tier: str
    days_at_stake: int

    @property
    def code(self) -> str:
        return self.finding.code

    def days_worth(self) -> Decimal | None:
        """A money figure for the tier, when we actually hold the tariff.

        ``None`` rather than zero when the total is unknown, for the reason issue 38
        set out. This is a convenience for the letter and it is not allowed to become
        a second place a zero gets invented.
        """
        if self.days_at_stake == 0:
            return None
        return Decimal(self.days_at_stake)


def _days_at_stake(finding: Finding) -> int:
    return len(finding.days)


def order_findings(result: AuditResult) -> tuple[OrderedFinding, ...]:
    """Every finding, in letter order.

    Tier first, then days at stake descending, then code ascending. The last key
    exists only so the order is total: two findings with no days and the same tier
    would otherwise have no defined order, and a letter whose claim order depends on
    set iteration is a letter nobody can diff.
    """
    tiers = (TIER_HARD_VOID, TIER_DEADLINE, TIER_ARITHMETIC, TIER_SOFT_DEFECT, TIER_UNCLASSIFIED)
    rank = {tier: i for i, tier in enumerate(tiers)}
    return tuple(
        sorted(
            (
                OrderedFinding(finding=f, tier=tier_of(f), days_at_stake=_days_at_stake(f))
                for f in result.findings
            ),
            key=lambda o: (rank[o.tier], -o.days_at_stake, o.code),
        )
    )


@dataclass(frozen=True, slots=True)
class ClaimStrategy:
    """What the letter is, decided from its contents.

    ``leading_ground`` is the ground of the first hard-void or deadline claim, which
    is the claim the whole document is built around. A letter with no such claim
    leads with its strongest arithmetic, and saying so explicitly is better than
    letting the reader work it out from paragraph order.
    """

    leading_ground: object | None
    leading_code: str
    leading_tier: str
    tier_counts: dict[str, int]
    document_kind: str

    def headline(self) -> str:
        if self.leading_tier == TIER_HARD_VOID:
            return "Compliance notice"
        if self.leading_tier == TIER_DEADLINE:
            return "Time-barred claim"
        if self.leading_tier == TIER_ARITHMETIC:
            return "Recomputation"
        if self.leading_tier == TIER_UNCLASSIFIED:
            return "Query, not yet a dispute"
        return "Dispute"


def strategy_for(result: AuditResult) -> ClaimStrategy:
    """Read the ordered findings and say what document this is.

    Pure, and it changes nothing. ``can_file`` is unaffected by ordering, so a letter
    cannot become fileable by being ordered well.
    """
    ordered = order_findings(result)
    counts: dict[str, int] = {}
    for item in ordered:
        counts[item.tier] = counts.get(item.tier, 0) + 1

    lead = ordered[0] if ordered else None
    ground = None
    if lead is not None and lead.finding.grounds:
        ground = lead.finding.grounds[0]

    kind = "Dispute"
    if not ordered:
        kind = "Nothing to send"
    elif lead is not None and lead.tier == TIER_HARD_VOID:
        kind = "Compliance notice"
    elif lead is not None and lead.tier == TIER_DEADLINE:
        kind = "Time-barred claim"
    elif lead is not None and lead.tier == TIER_UNCLASSIFIED:
        kind = "Query, not yet a dispute"
    elif lead is not None and lead.tier == TIER_ARITHMETIC:
        kind = "Recomputation"

    return ClaimStrategy(
        leading_ground=ground,
        leading_code=lead.code if lead else "",
        leading_tier=lead.tier if lead else TIER_UNCLASSIFIED,
        tier_counts=counts,
        document_kind=kind,
    )


def render_digest(strategy: ClaimStrategy, ordered: tuple[OrderedFinding, ...]) -> str:
    """The triage digest: what to argue first, and why.

    **Not the letter.** The letter is ``evidence.packet.render``, grouped by ground
    because a claim is a concession and a carrier concedes one thing at a time. This
    is ordered by tier because a reviewer needs to see the strongest claim first.

    Renamed from ``render_letter`` in issue 176. Two functions both documented as
    rendering a letter is how a filing path ends up with two opinions on what gets
    sent, and only one of them was reachable from an audit. The name now says what
    this actually produces.
    """
    lines = [strategy.headline(), ""]
    if not ordered:
        lines.append("No findings. There is no dispute to make.")
        return "\n".join(lines) + "\n"

    for item in ordered:
        lines.append(f"## {item.finding.summary}")
        lines.append(f"Tier: {item.tier}")
        lines.append(f"Basis: {item.finding.cite}")
        if item.days_at_stake:
            lines.append(f"Days at stake: {item.days_at_stake}")
        lines.append("")
    return "\n".join(lines) + "\n"


__all__ = [
    "TIER_ARITHMETIC",
    "TIER_BY_CODE",
    "TIER_DEADLINE",
    "TIER_HARD_VOID",
    "TIER_SOFT_DEFECT",
    "TIER_UNCLASSIFIED",
    "ClaimStrategy",
    "OrderedFinding",
    "order_findings",
    "render_digest",
    "strategy_for",
    "tier_of",
]
