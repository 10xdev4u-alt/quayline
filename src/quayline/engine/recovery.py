"""Issue 35: an estimate that cannot outgrow the invoice it argues against.

The mistake is one line and it is also the most expensive line in the product:

    estimate = sum(finding.amount for finding in findings)

A 541.5 omission voids the whole line. The day-count and arithmetic findings are
**fallback arguments for the same money**, not additive claims. Summing them
produces a figure larger than the invoice, and a recovery number bigger than the
demand hands the carrier the thing it needs most: a reason to stop engaging and
start discrediting.

Three claim bases

``LINE_WIDE``
    The whole line fails. 541.5 on a missing disclosure. The estimate is the
    demand, because there is nothing to prorate, and every partial is a fallback
    argument that only matters if this one loses.

``PARTIAL``
    Some days or some dollars are wrong. These add, up to the demand, because the
    carrier cannot be asked to pay back more than it invoiced.

``INFORMATIONAL``
    Evidence for the letter and not for the money. An unclassified code, a caveat,
    a warning in finding form. Adds nothing and must never be priced.

The cap is not a policy choice

It is arithmetic. The carrier was invoiced nothing beyond the demand, so the
maximum recovery is the demand. An estimate above it is not optimistic, it is
impossible, and a demand letter that asks for more than the invoice is a letter
that tells the respondent the sender does not understand its own arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from quayline.engine.dedupe import DIAGNOSTIC_SUFFIX
from quayline.engine.result import AuditResult


class ClaimBasis(StrEnum):
    """What a finding asks for, in money terms."""

    #: The whole line fails. 541.5.
    LINE_WIDE = "line-wide"
    #: Some days or some dollars are wrong. Adds, up to the demand.
    PARTIAL = "partial"
    #: Evidence for the letter, not for the money. Adds nothing.
    INFORMATIONAL = "informational"


#: Which finding codes are line-wide. Closed, so a new void has to be placed
#: deliberately in a diff somebody reviews.
LINE_WIDE_CODES = frozenset({"field_omitted"})

#: Which codes carry no money. A warning in finding form, or a state note.
INFORMATIONAL_CODES = frozenset({"tariff_unresolved", "validation_note", "evidence_note"})


def basis_of(code: str) -> ClaimBasis:
    """The money shape of a finding, from its code.

    Demoted codes read informational. Issue 36: when the tariff resolves, the
    day-count finding is diagnostic, and a diagnostic that still carried money
    would price the same dollars twice.
    """
    if code.endswith(DIAGNOSTIC_SUFFIX):
        return ClaimBasis.INFORMATIONAL
    if code in LINE_WIDE_CODES:
        return ClaimBasis.LINE_WIDE
    if code in INFORMATIONAL_CODES:
        return ClaimBasis.INFORMATIONAL
    return ClaimBasis.PARTIAL


@dataclass(frozen=True, slots=True)
class ValuedFinding:
    """A finding with the money attached, if it carries any."""

    code: str
    amount: Decimal | None
    days: int = 0

    @property
    def basis(self) -> ClaimBasis:
        return basis_of(self.code)


@dataclass(frozen=True, slots=True)
class RecoveryEstimate:
    """What the audit says the carrier owes, and why it is what it is.

    Frozen and fully explained. An estimate is read by a human deciding whether to
    send a letter, so it carries the composition that produced it rather than
    asking to be trusted.
    """

    #: The number. Never above the demand. Zero is a value: it means the audit
    #: found nothing worth pursuing, not that it found nothing.
    amount: Decimal
    #: The demand it is capped by. ``None`` when the demand itself is unknown, in
    #: which case nothing may be estimated and this whole object should not exist.
    capped_by: Decimal
    #: Which lines produced it.
    composition: tuple[ValuedFinding, ...]
    #: Whether a line-wide claim superseded the partials.
    superseded: bool
    #: The partial sum before the cap, so a reviewer can see what was absorbed.
    uncapped: Decimal

    def detail(self) -> str:
        if self.superseded:
            return (
                f"A line-wide claim voids the whole invoice, so the estimate is the "
                f"demand of {self.capped_by}. {len(self.composition)} partial finding(s) "
                f"are fallback arguments and contribute nothing."
            )
        if self.uncapped > self.capped_by:
            return (
                f"Partial findings total {self.uncapped} against a demand of "
                f"{self.capped_by}, so the estimate is capped at the demand. The carrier "
                f"cannot pay back more than it invoiced."
            )
        return f"Partial findings total {self.uncapped}, below the demand of {self.capped_by}."


def estimate(
    findings: tuple[ValuedFinding, ...],
    demanded: Decimal,
) -> RecoveryEstimate:
    """The recovery estimate for a set of findings against a demand.

    Line-wide first: if any finding voids the whole line, the estimate is the
    demand and the partials are fallback arguments. Otherwise the partials add,
    and the sum is capped at the demand because findings are alternative grounds
    for the same dollars, not additive claims.

    Pure and total. The demanded side is required, because an estimate against an
    unknown demand is a number with nothing under it.
    """
    line_wide = tuple(v for v in findings if v.basis is ClaimBasis.LINE_WIDE)
    if line_wide:
        return RecoveryEstimate(
            amount=demanded,
            capped_by=demanded,
            composition=findings,
            superseded=True,
            uncapped=sum((v.amount for v in findings if v.amount is not None), Decimal(0)),
        )
    partials = tuple(v for v in findings if v.basis is ClaimBasis.PARTIAL)
    total = sum((v.amount for v in partials if v.amount is not None), Decimal(0))
    capped = min(total, demanded)
    return RecoveryEstimate(
        amount=capped,
        capped_by=demanded,
        composition=findings,
        superseded=False,
        uncapped=total,
    )


def estimate_for(result: AuditResult) -> RecoveryEstimate | None:
    """Estimate from an audit result, or ``None`` when there is nothing to price.

    ``None`` when the demand is unknown or when the result carries no findings with
    money in them. A zero estimate is still a value, so it is returned as one; only
    the absence of anything to say is ``None``.
    """
    if result.demanded_total is None:
        return None
    valued = tuple(
        ValuedFinding(code=f.code, amount=_money_for(f.code, result)) for f in result.findings
    )
    if not valued:
        return None
    return estimate(valued, result.demanded_total)


def _money_for(code: str, result: AuditResult) -> Decimal | None:
    """The money a finding stands for. ``None`` for informational codes.

    Deliberately conservative: the variance when we priced it, nothing otherwise. A
    finding without a computable amount contributes no number rather than a guess.
    """
    # basis_of is the single place codes are classified, so a demoted diagnostic
    # and an informational code take the same path here. Two classifications of the
    # same code is how a demotion stops working the next time one of them changes.
    if basis_of(code) is ClaimBasis.INFORMATIONAL:
        return None
    if code in LINE_WIDE_CODES:
        return result.demanded_total
    variance = result.variance
    if variance is not None and variance > 0:
        return variance
    return Decimal(0)


__all__ = [
    "INFORMATIONAL_CODES",
    "LINE_WIDE_CODES",
    "ClaimBasis",
    "RecoveryEstimate",
    "ValuedFinding",
    "basis_of",
    "estimate",
    "estimate_for",
]
