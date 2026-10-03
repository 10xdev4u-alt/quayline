"""Issue 38: one result shape, so downstream does not have to guess.

Six result types existed before this, each with its own way of saying "you cannot
file this":

- ``engine/amount.AmountResult.overbilled``
- ``engine/daycount.DayCountResult.overbilled``
- ``evidence/packet.Packet.can_file``
- ``ingest/validate.ValidationReport.can_file``
- ``evidence/checklist.SubmissionReport.can_submit``
- ``regulation/vacatur.LiabilityFinding.eliminates_obligation``

Six names for one concept, and a caller holding two of them has to know which is
which. That is the argument for the issue: every new check is another shape, and
after four more findings the spread is four more things to rework rather than one.

The three-state rule

The design decision everything else follows from. A quantity in a dispute is in one
of three states and the type has to hold all three:

``value``
    We computed it. Zero is a value. A tariff that genuinely prices the first
    container at nothing produces a recomputed total of zero, and that is a finding
    worth filing.
``None``
    We could not compute it. The tariff did not resolve, the field is missing, the
    input was absent.
``absent entirely``
    Not applicable to this invoice. An export invoice has no container
    availability date, and that is different from having one we could not read.

The failure this prevents is the oldest one in the category: a system that cannot
compute a number prints zero, zero looks like a result, and zero gets quoted. A
letter that says "the correct total is $0.00" when the real answer is "we could not
resolve that tariff" is a claim we cannot support and cannot withdraw.

So ``recomputed_total`` is ``None`` when the tariff did not resolve, and there is no
code path anywhere in this package that turns that ``None`` into a zero. Variance
follows the same rule: ``None`` when either side is unknown, never zero. The
invariant is enforced in ``AuditResult.__post_init__``, so a caller cannot construct
an inconsistent one.

Blocking, and only blocking

One property, ``can_file``, and a finding is either a blocker or it is not. The
four previous gates each had a way to be soft, and every one of those ways is a
place where a letter went out on a document we had not actually verified. There is
no severity field and no warning list that can be waived, for the reason issue 42
gave: a field someone eventually passes as ``False`` and files anyway.

What is *not* here

No quality score, no confidence, no partial value, no ordering. Ordering is issue
34, and doing it in the contract would put a presentation decision into the type
every checker returns.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from quayline.engine.daycount import DayCountResult
from quayline.engine.disclosure import UncheckedField
from quayline.evidence.checklist import Ground
from quayline.regulation.checklist import ChecklistField
from quayline.regulation.kill_switch import Obligation

#: A finding code is a stable identifier, not a sentence. Codes are what a caller
#: filters on and what a test asserts, and a code that changes when the wording
#: improves is a code nothing downstream can depend on.
CODE_TARIFF_UNRESOLVED = "tariff_unresolved"
CODE_AMOUNT_VARIANCE = "amount_variance"
CODE_DAYCOUNT_VARIANCE = "daycount_variance"
CODE_FIELD_OMITTED = "field_omitted"
CODE_AVAILABILITY_CONTRADICTION = "availability_contradiction"
CODE_VALIDATION_FAILED = "validation_failed"
CODE_EVIDENCE_MISSING = "evidence_missing"


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing the audit found.

    ``grounds`` is here because the packet groups by ground, and a finding that
    cannot say which ground it belongs to has to be guessed at render time. Guessed
    at render time means evidence for the wrong claim appears under the right
    heading, which is the mixing failure issue 59 exists to prevent.
    """

    code: str
    cite: str
    summary: str
    detail: str = ""
    grounds: tuple[Ground, ...] = ()
    days: tuple[date, ...] = ()

    def on_ground(self, ground: Ground) -> bool:
        return ground in self.grounds


@dataclass(frozen=True, slots=True)
class AuditResult:
    """The result of an audit, and the only result shape this package returns.

    A value object. Frozen, slotted, and every field is either a value, a ``None``
    meaning "not computable", or a collection. There is no method with a side
    effect, no lazy computation, and no way to reach a number that was not put
    there deliberately.
    """

    # Who and what.
    carrier: str
    invoice_ref: str = ""
    terminal: str = ""

    # Money. ``None`` on either side means not computable, never zero.
    demanded_total: Decimal | None = None
    recomputed_total: Decimal | None = None
    #: demanded minus recomputed. ``None`` when either side is ``None``.
    variance: Decimal | None = None
    variance_pct: Decimal | None = None

    # Time. ``None`` for the same reason, and for a different one on exports, where
    # there is no availability date to compute against.
    computed_free_time_expiry: date | None = None
    computed_charge_days: int | None = None

    # What we could not fill in, and what we want a human to read before filing.
    unfilled_fields: tuple[ChecklistField, ...] = ()
    warnings: tuple[str, ...] = ()

    #: 541.5 applied to the omissions found on the document. ELIMINATED means at least
    #: one required minimum was missing, which is the automatic remedy in this category:
    #: no cure period and no showing of prejudice. Issue 207.
    #:
    #: Carried on the result rather than recomputed by a renderer, because a letter that
    #: derives its own conclusion from a list of findings can disagree with the engine
    #: about whether the obligation survived.
    obligation: Obligation = Obligation.INTACT

    #: 541.6 clauses this build cannot check, each with the reason. Issue 212.
    #:
    #: A result with no omissions and nothing here would read as "the invoice complies",
    #: which is a claim about six clauses nobody looked at. The two travel together so
    #: that reading is not available.
    unverified_fields: tuple[UncheckedField, ...] = ()

    findings: tuple[Finding, ...] = ()

    #: The per day recomputation, kept so a renderer can show which days were free,
    #: which were chargeable and which were billed. Issue 189. ``None`` when no day
    #: arithmetic ran, which is an export audit and nothing else, and never a
    #: recomputation: a second implementation of the day count would be a second
    #: chance to disagree with the engine, in front of a reader.
    day_count: DayCountResult | None = None

    def __post_init__(self) -> None:
        # The three-state rule, enforced. A variance computed against a total we do
        # not have is the exact failure described in the module docstring, and this
        # is where it gets caught.
        if self.variance is not None and (
            self.demanded_total is None or self.recomputed_total is None
        ):
            msg = (
                f"variance is {self.variance} but one of the totals is None. A variance "
                f"against an unknown total is not zero, it is unknown, and reporting it "
                f"as a number is how a system that cannot compute an answer ends up "
                f"quoting one."
            )
            raise ValueError(msg)
        if self.variance_pct is not None and (
            self.variance is None or self.recomputed_total is None
        ):
            msg = "variance_pct is only meaningful when a variance and a recomputed total exist"
            raise ValueError(msg)

    # ---------------------------------------------------------------- blocking

    @property
    def blockers(self) -> tuple[Finding, ...]:
        """Findings that stop the dispute being filed.

        A code is a blocker because it is in :data:`BLOCKING_CODES`, not because a
        caller decided. A caller deciding is how a blocking check gets waived.
        """
        return tuple(f for f in self.findings if f.code in BLOCKING_CODES)

    @property
    def can_file(self) -> bool:
        """The one gate. ``True`` only when nothing blocks."""
        return not self.blockers

    def reason_not_filed(self) -> str:
        if self.can_file:
            return ""
        return "; ".join(f"{f.code}: {f.summary}" for f in self.blockers)

    # ---------------------------------------------------------------- queries

    @property
    def tariff_resolved(self) -> bool:
        """Whether we priced this at all.

        Reads the total, not the findings. An earlier version read the finding code
        and a test caught the two disagreeing, which is the whole argument for having
        the property at all: there must be one fact that says whether we priced the
        invoice, and it has to be the fact rather than a claim someone made about it.

        Zero is a price. A tariff that genuinely prices the first day at nothing was
        resolved.
        """
        return self.recomputed_total is not None

    def findings_on(self, ground: Ground) -> tuple[Finding, ...]:
        """The findings for one ground. A method, because a property taking an
        argument is a query pretending to be a field."""
        return tuple(f for f in self.findings if f.on_ground(ground))

    def with_finding(self, finding: Finding) -> AuditResult:
        """A new result with one finding added. Returns, never mutates.

        Composition is how this type is meant to be built, and a method that
        mutated would make every intermediate result something a caller could have
        observed and quoted.
        """
        return replace(self, findings=(*self.findings, finding))


#: Which codes block. A single closed list, so "is this blocking" is answerable
#: without reading a caller's intent.
#:
#: ``tariff_unresolved`` blocks because a dispute with no recomputed total is not a
#: dispute, it is a query. ``field_omitted`` blocks because that is 541.5, the one
#: automatic remedy in the category. The rest are blocking because filing a letter
#: that contains them while they are unresolved is a false statement.
BLOCKING_CODES: frozenset[str] = frozenset(
    {
        CODE_TARIFF_UNRESOLVED,
        CODE_FIELD_OMITTED,
        CODE_AMOUNT_VARIANCE,
        CODE_DAYCOUNT_VARIANCE,
        CODE_VALIDATION_FAILED,
        CODE_EVIDENCE_MISSING,
    }
)


def variance_of(demanded: Decimal | None, recomputed: Decimal | None) -> Decimal | None:
    """Demanded minus recomputed, or ``None`` if either side is unknown.

    Total, and the only place a variance is ever produced. Not ``demand -
    recompute`` with a zero substituted, which is how a system that could not
    price an invoice ends up claiming the carrier overbilled by exactly the demand.
    """
    if demanded is None or recomputed is None:
        return None
    return demanded - recomputed


def variance_pct_of(variance: Decimal | None, base: Decimal | None) -> Decimal | None:
    """Variance as a share of the recomputed total, or ``None``.

    A zero base is ``None`` rather than a division error or an infinity. A percentage
    of zero is not a number, and reporting one would be the third way this could go
    wrong.
    """
    if variance is None or base is None or base == 0:
        return None
    return (variance / base) * 100


__all__ = [
    "BLOCKING_CODES",
    "CODE_AMOUNT_VARIANCE",
    "CODE_AVAILABILITY_CONTRADICTION",
    "CODE_DAYCOUNT_VARIANCE",
    "CODE_EVIDENCE_MISSING",
    "CODE_FIELD_OMITTED",
    "CODE_TARIFF_UNRESOLVED",
    "CODE_VALIDATION_FAILED",
    "AuditResult",
    "Finding",
    "variance_of",
    "variance_pct_of",
]
