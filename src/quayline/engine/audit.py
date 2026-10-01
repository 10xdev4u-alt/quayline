"""Issue 167, second half: the orchestrator, and the entry point the package lacked.

This is the module ``result.py`` meant to have behind it. ``AuditResult`` is
documented as "the only result shape this package returns", and until now nothing in
``src/`` produced one. ``tests/test_ordering.py`` had a local helper that built one,
which was the only ``audit`` in the repository and was unreachable from outside the
test suite.

What it does, in order

1. Extract the text layer. No OCR. A document with no text layer is refused.
2. Bind it. A required disclosure that is absent is a 541.5 finding, not a stop.
3. Recompute the day count from the invoice's own disclosures, which is the check
   that needs no external data and no tariff.
4. Run the availability contradiction check, also from the invoice alone.
5. Compare the money, but only when both the document and the tariff state it.

What it deliberately does not do

**It never invents a recomputed total.** When the tariff does not resolve, or the
invoice states no rate, ``recomputed_total`` is ``None``. That is the rule in
``result.py`` and this is the place it would be easiest to break, because a
orchestrator is exactly where a "reasonable default" gets added by someone in a
hurry. So there is a test asserting ``None``, not zero.

**It does not guess the carrier.** 541.6 never asks a carrier to name itself on the
invoice face, so ``carrier`` is a parameter and an unknown one raises. Defaulting
would produce a day count from a rule we do not hold, which is the MSC problem from
section one of the onboarding guide arrived at from the other direction.

**It does not swallow a binding failure.** An unreadable document raises. The
caller has to decide whether to stop, and that decision is not this module's to make
silently.

Why the checks are ordered this way

The day count comes before the money on purpose. It needs no tariff, so it is
computable on more documents than the money check is, and a day count finding is
one the carrier cannot argue with because they disclosed every input to it.
"""

from __future__ import annotations

from decimal import Decimal

from quayline.calendars.day_basis import RULES as DAY_BASIS_RULES
from quayline.engine.amount import compare as compare_amount
from quayline.engine.availability import availability_contradiction
from quayline.engine.daycount import recompute
from quayline.engine.dedupe import demote_daycount
from quayline.engine.result import (
    CODE_AMOUNT_VARIANCE,
    CODE_AVAILABILITY_CONTRADICTION,
    CODE_DAYCOUNT_VARIANCE,
    CODE_TARIFF_UNRESOLVED,
    AuditResult,
    Finding,
    variance_of,
    variance_pct_of,
)
from quayline.evidence.checklist import Ground
from quayline.ingest.bind import BoundLedger, OmittedError, bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.models.invoice import (
    CITE_CHARGED_DATES,
    CITE_FREE_TIME_END,
    CITE_FREE_TIME_START,
    CITE_TOTAL,
    TimingDisclosures,
)
from quayline.tariffs.resolution import Resolution

#: 541.5, the omission clause, verified in issue 1. Carried on the omission finding
#: because an automatic finding is the strongest one the engine produces and the
#: letter has to cite it.
CITE_OMISSION = "541.5"

#: 541.6(a)(3), the invoice date. Required by the type and needed by the deadline
#: arithmetic, so an absent one is an omission rather than a default.
CITE_INVOICE_DATE = "541.6(a)(3)"


class EngineError(RuntimeError):
    """The engine cannot answer, and says why.

    Distinct from ``BindError``, which is a document problem, and from ``KeyError``,
    which is an unknown carrier. This one means the engine ran and hit a wall.
    """


def audit(
    data: bytes,
    carrier: str,
    terminal: str = "",
    tariff: Resolution | None = None,
    invoice_ref: str = "",
) -> AuditResult:
    """Run a document through the engine and return the one result shape.

    ``carrier`` and ``terminal`` are parameters because 541.6 does not require the
    carrier to name itself on the invoice face. An unknown carrier raises ``KeyError``
    rather than defaulting, because a day count computed from a rule we do not hold
    is a plausible wrong answer, which is the failure this whole package is built to
    avoid.

    ``tariff`` is the resolved rate block, or ``None`` when it does not resolve.
    Passing ``None`` is legitimate and produces ``recomputed_total`` of ``None`` with
    a ``tariff_unresolved`` finding. That is not a degraded mode, it is the correct
    answer for eight of MSC's nine major gateways.

    Everything else comes off the document. ``invoice_ref`` overrides the container
    number when a caller has the real invoice number, which the text layer does not
    carry.
    """
    if carrier not in DAY_BASIS_RULES:
        raise KeyError(
            f"no day basis rule for carrier {carrier!r}. The carrier is a parameter "
            f"because 541.6 never asks a carrier to name itself on the invoice "
            f"face, and defaulting would compute a day count from a rule we do "
            f"not hold."
        )

    text = extract_text_layer(data)
    bound = bind_ledger(text)

    if bound.invoice_date is None:
        raise OmittedError("invoice date", CITE_INVOICE_DATE)

    disclosures = TimingDisclosures(
        invoice_date=bound.invoice_date,
        allowed_free_time_days=bound.allowed_free_time_days,
        free_time_start=bound.free_time_start,
        free_time_end=bound.free_time_end,
        charged_dates=frozenset(bound.charged_dates),
        availability_date=bound.availability_date,
    )

    computed = recompute(disclosures, carrier, terminal=terminal)

    findings: list[Finding] = []
    for discrepancy in computed.discrepancies:
        lines = discrepancy.as_letter_lines()
        findings.append(
            Finding(
                code=CODE_DAYCOUNT_VARIANCE,
                cite=f"{CITE_FREE_TIME_START}, {CITE_FREE_TIME_END}, {CITE_CHARGED_DATES}",
                summary=lines[0] if lines else "the chargeable day count disagrees",
                detail="\n".join(lines),
                grounds=(Ground.DISCLOSURE_OMITTED,),
                days=discrepancy.dates,
            )
        )

    contradiction = availability_contradiction(disclosures)
    if contradiction is not None:
        findings.append(
            Finding(
                code=CODE_AVAILABILITY_CONTRADICTION,
                cite=contradiction.cite,
                summary=contradiction.as_sentence(),
                detail=(
                    f"The carrier discloses an availability date of "
                    f"{contradiction.availability_date.isoformat()} and charges from "
                    f"{contradiction.first_charged_day.isoformat()}, so "
                    f"{contradiction.contradiction_days} chargeable day(s) fall "
                    f"before the container was available."
                ),
                days=contradiction.disputed_days,
            )
        )

    demanded = bound.stated_total
    recomputed: Decimal | None = None
    if demanded is None:
        # The document states no money. There is nothing to compare, and zero would
        # be our arithmetic in the carrier's mouth.
        pass
    elif tariff is None or not tariff.resolved or tariff.block is None:
        findings.append(
            Finding(
                code=CODE_TARIFF_UNRESOLVED,
                cite=CITE_TOTAL,
                summary=(
                    "the rate rule the carrier billed under does not resolve to a "
                    "transcribed rate, so the charge cannot be recomputed"
                ),
                detail=(
                    tariff.withheld_reason
                    if tariff is not None
                    else "no tariff block was supplied, so the rate rule the carrier "
                    "billed under was never resolved"
                ),
            )
        )
    else:
        amount = compare_amount(
            tariff.block,
            len(computed.expected_dates),
            demanded,
        )
        recomputed = amount.recomputed_total
        if amount.overbilled:
            lines = amount.as_letter_lines()
            findings.append(
                Finding(
                    code=CODE_AMOUNT_VARIANCE,
                    cite=CITE_TOTAL,
                    summary=lines[0] if lines else "the charge exceeds the recomputed amount",
                    detail="\n".join(lines),
                )
            )

    tariff_resolved = recomputed is not None
    ordered = demote_daycount(tuple(findings), tariff_resolved=tariff_resolved)

    variance = variance_of(demanded, recomputed)

    return AuditResult(
        carrier=carrier,
        invoice_ref=invoice_ref or _invoice_ref(bound),
        terminal=terminal,
        demanded_total=demanded,
        recomputed_total=recomputed,
        variance=variance,
        variance_pct=variance_pct_of(variance, recomputed),
        computed_free_time_expiry=computed.recomputed_free_time_end,
        computed_charge_days=len(computed.expected_dates),
        findings=ordered,
    )


def _invoice_ref(bound: BoundLedger) -> str:
    """The first container number, which is the only reference we extracted.

    Not a real invoice number. Returning a container and calling it an invoice
    reference would be the kind of small lie that costs credibility later, so it is
    derived and named for what it is.
    """
    if not bound.lines:
        return ""
    return bound.lines[0].container_number


__all__ = ["EngineError", "OmittedError", "audit"]
