"""Issue 207: run the 541.6 disclosure check on the document.

`regulation/checklist.py` has carried the twenty required disclosures since issue 1 and
`regulation/kill_switch.py` has carried 541.5, which eliminates the obligation to pay
when a required minimum is missing. Nothing ran either of them.

Two things were wrong as a result. An invoice missing a required disclosure raised
`OmittedError`, which aborts the audit, because the only fields checked were the six a
ledger cannot be built without. And an invoice missing something the regulation
requires produced no finding at all, when that finding is the automatic one: no cure
period, no showing of prejudice, and it needs no arithmetic and no tariff.

This module needs no tariff, which is the point. `quayline coverage` reports one
carrier with transcribed rates and eight we hold nothing for, so a check that needs a
rate adjudicates one carrier and tells the other eight nothing. This one reads the same
fixed list for every carrier, every terminal and both directions of trade.

## What it will not do

It will not claim a disclosure is missing when the extractor never looked for it.

Thirteen of the twenty fields are reachable from a bound ledger: twelve labelled
disclosures and the rate, which is per line. Seven are not: the port of discharge, the
basis for the billed party being the proper party, the dispute contact, the digital
means, the dispute timeframes, and both certifications. Those are reported by `unchecked()` and are never
raised as omissions. An omission we cannot see is not a finding, it is a gap in our
coverage, and treating it as a finding would assert against a carrier that it withheld
something we did not look for, which is the shape of a false accusation.

## The safety rule

`find_omissions` returns nothing unless the text layer is **complete**.

A document that decoded but dropped strings is readable and not complete, and a field
may be absent because we could not read it rather than because the carrier withheld it.
541.5 is automatic. Firing it on our own extraction defect is the most expensive error
in this pipeline, because it produces a true-looking automatic remedy against an
innocent carrier. `TextLayer.complete` is stricter than readable on purpose, and this
module refuses to produce a finding without it.

## Trade scoping

Three of the twenty are directional: 541.6(a)(3) and (b)(6) are import only, (b)(7) is
export only. Demanding an import field on an export invoice fabricates a ground, and
scoping to export on an import invoice hides one, so neither direction is a default.
When the direction cannot be determined, the directional fields are not checked and a
warning says so.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from quayline.ingest.bind import BoundLedger
from quayline.ingest.fields import Fields, read_fields
from quayline.ingest.pdftext import TextLayer
from quayline.regulation.checklist import (
    CHECKLIST,
    ChecklistField,
    Scope,
    Trade,
    by_cite,
    required_for,
)
from quayline.regulation.kill_switch import Obligation, Omission, effect_of

__all__ = [
    "DisclosureResult",
    "VerifiableField",
    "check_disclosures",
    "determine_trade",
    "find_omissions",
    "unchecked",
]


@dataclass(frozen=True, slots=True)
class VerifiableField:
    """One 541.6 disclosure this module can actually look for.

    ``present`` reads the bound ledger rather than the raw text, so a field the ledger
    already had to have in order to exist is checked by asking whether it is there. That
    is the cheapest correct check available and it is the same field the engine computed
    from, so the two cannot disagree.
    """

    cite: str
    #: Labels that, if any is present, mean the disclosure was made. Empty means the
    #: check is against the ledger alone, which is the common case.
    labels: tuple[str, ...] = ()
    #: Read the ledger instead of the labels.
    from_ledger: bool = True

    @property
    def field(self) -> ChecklistField:
        return by_cite(self.cite)


#: The twelve labelled disclosures reachable from a bound ledger. The rate is the
#: thirteenth and is proved from the bound lines instead, because a rate is per line.
#:
#: Ordered by clause so a failure names where in the regulation to look. The four that
#: need a ledger rather than a label are the money and the dates the engine already has.
VERIFIABLE: tuple[VerifiableField, ...] = (
    VerifiableField("541.6(a)(1)", ("bill of lading number", "bol number", "b/l")),
    VerifiableField("541.6(a)(2)", ("container number", "container no", "container")),
    VerifiableField("541.6(b)(1)", ("invoice date",)),
    VerifiableField("541.6(b)(2)", ("due date", "invoice due date", "payment due date")),
    VerifiableField("541.6(b)(3)", ("allowed free time", "free time", "free days")),
    VerifiableField("541.6(b)(4)", ("start date of free time", "free time start")),
    VerifiableField("541.6(b)(5)", ("end date of free time", "free time end")),
    VerifiableField("541.6(b)(6)", ("container availability date", "availability date")),
    VerifiableField("541.6(b)(7)", ("earliest return date",)),
    VerifiableField("541.6(b)(8)", ("charged dates", "dates charged")),
    VerifiableField("541.6(c)(1)", ("total", "total amount", "amount due")),
    VerifiableField("541.6(c)(2)", ("rate rule", "tariff rule", "rule")),
)

#: 541.6(c)(3), the specific rate. Not in VERIFIABLE because a rate is per line rather
#: than one labelled value on the document, so it is proved from the bound lines.
_LEDGER_RATE_CITE = "541.6(c)(3)"


def _ledger_states(ledger: BoundLedger) -> bool:
    """Whether the bound ledger proves the disclosure at ``cite`` was made.

    541.6(c)(3) is the rate. It is per line rather than one labelled value on the
    document, so it is proved from the bound lines: an invoice carrying lines whose
    rates are all zero has not stated a rate.
    """
    if _LEDGER_RATE_CITE:
        # The rate is per line. An invoice with lines and a zero rate everywhere is not
        # stating a rate, so the check is that at least one line carries one.
        return bool(ledger.lines) and any(line.rate > 0 for line in ledger.lines)
    return True


@dataclass(frozen=True, slots=True)
class DisclosureResult:
    """What the check found, and what it could not look for."""

    omissions: tuple[Omission, ...] = ()
    obligation: Obligation = Obligation.INTACT
    #: Disclosures we cannot check. Surfaced so a caller reports coverage rather than
    #: implying the checklist ran clean.
    unverified: tuple[ChecklistField, ...] = ()
    warnings: tuple[str, ...] = ()
    #: Whether a complete text layer backed this result. False means no omissions were
    #: raised and none should be.
    complete: bool = True

    @property
    def eliminated(self) -> bool:
        return self.obligation is Obligation.ELIMINATED


def unchecked() -> tuple[ChecklistField, ...]:
    """The 541.6 fields this module cannot check.

    Seven of twenty, and naming them is the point. A caller that says "no omissions"
    without also saying these are unverified has told the reader the invoice complies,
    which is a claim about seven clauses nobody looked at.
    """
    checked = {v.cite for v in VERIFIABLE} | {_LEDGER_RATE_CITE}
    return tuple(f for f in CHECKLIST if f.cite not in checked)


def determine_trade(ledger: BoundLedger) -> Trade | None:
    """The direction of trade, or ``None`` when the document does not say.

    The container availability date is 541.6(b)(6), import only, so its presence
    settles it. There is no export signal in a bound ledger today, so an invoice with no
    availability date is **not** assumed to be an export: that would silently stop
    checking the port of discharge and the availability date, which is the direction
    that fails closed.
    """
    if ledger.availability_date is not None:
        return Trade.IMPORT
    return None


def _labels_present(fields: Fields, labels: Sequence[str]) -> bool:
    return any(label in fields.values for label in labels)


def _field_is_stated(
    ledger: BoundLedger, fields: Fields, spec: VerifiableField, trade: Trade | None
) -> bool:
    """Whether one disclosure was made. All three reasons for true are recorded here.

    A label match is enough on its own, because the carrier writing
    ``Rate Rule: Maersk US Newark Dry`` has made the disclosure whether or not we
    understood the value.
    """
    if spec.labels and _labels_present(fields, spec.labels):
        return True
    if spec.cite == _LEDGER_RATE_CITE:
        return _ledger_states(ledger)
    if spec.cite == "541.6(b)(6)" and trade is Trade.EXPORT:
        return True
    if spec.cite == "541.6(b)(7)" and trade is Trade.IMPORT:
        return True
    return spec.from_ledger and _ledger_proves(ledger, spec.cite)


def _ledger_proves(ledger: BoundLedger, cite: str) -> bool:
    """Ledger-backed proofs, one per clause, each traceable to the binder."""
    proofs: dict[str, bool] = {
        "541.6(a)(1)": bool(ledger.lines) and all(x.bol_number for x in ledger.lines),
        "541.6(a)(2)": bool(ledger.lines) and all(x.container_number for x in ledger.lines),
        "541.6(b)(1)": ledger.invoice_date is not None,
        "541.6(b)(3)": ledger.allowed_free_time_days >= 0,
        "541.6(b)(4)": ledger.free_time_start is not None,
        "541.6(b)(5)": ledger.free_time_end is not None,
        "541.6(b)(6)": ledger.availability_date is not None,
        "541.6(b)(7)": False,
        "541.6(b)(8)": bool(ledger.charged_dates),
        "541.6(c)(1)": ledger.stated_total is not None,
        "541.6(c)(2)": bool(ledger.rate_rule.strip()),
    }
    return proofs.get(cite, False)


def find_omissions(
    ledger: BoundLedger,
    fields: Fields,
    *,
    complete: bool,
    trade: Trade | None = None,
    invoice_ref: str = "",
) -> tuple[Omission, ...]:
    """The disclosures the regulation requires and the document does not make.

    ``complete`` is a required keyword with no default, deliberately.

    An earlier draft defaulted it to ``True`` and every call site passed it anyway,
    which is exactly how a defaulted safety flag stops being read. Making it required
    means the caller has to say whether it read the text layer, and a caller that did
    not is looking at a type error rather than a silent false accusation against a
    carrier.
    """
    if not complete:
        return ()

    direction = trade if trade is not None else determine_trade(ledger)
    applicable = required_for(direction) if direction is not None else _unscoped()

    omissions: list[Omission] = []
    for spec in VERIFIABLE:
        spec_field = spec.field
        if spec_field not in applicable:
            continue
        if _field_is_stated(ledger, fields, spec, direction):
            continue
        omissions.append(
            Omission(field=spec_field, invoice_ref=invoice_ref or _ref(ledger)),
        )
    return tuple(omissions)


def _unscoped() -> tuple[ChecklistField, ...]:
    """Every field that is not directional, for when the trade is undetermined."""
    return tuple(f for f in CHECKLIST if f.scope is Scope.BOTH)


def _ref(ledger: BoundLedger) -> str:
    return ledger.lines[0].container_number if ledger.lines else ""


def check_disclosures(
    ledger: BoundLedger,
    text: TextLayer,
    *,
    trade: Trade | None = None,
) -> DisclosureResult:
    """Run the check and say what it could not do.

    This is the entry point. `find_omissions` is the narrow one and returns nothing
    useful on an incomplete document, because a caller using it directly would have no
    way to tell "nothing missing" from "could not look".
    """
    fields = read_fields_of(text)
    complete = text.complete
    direction = trade if trade is not None else determine_trade(ledger)

    warnings: list[str] = []
    if not complete:
        warnings.append(
            "The document's text layer is incomplete, so a disclosure we cannot see "
            "may be absent rather than withheld. No 541.5 finding was raised, because "
            "an omission we cannot read is our extraction fault and not the carrier's."
        )
    if direction is None:
        warnings.append(
            "The direction of trade could not be determined from the document, so the "
            "directional disclosures in 541.6(a)(3), (b)(6) and (b)(7) were not "
            "checked. Demanding an import field on an export invoice would fabricate "
            "a ground, and scoping to export on an import invoice would hide one."
        )

    omissions = find_omissions(
        ledger,
        fields,
        trade=direction,
        complete=complete,
    )

    return DisclosureResult(
        omissions=omissions,
        obligation=effect_of(omissions),
        unverified=unchecked(),
        warnings=tuple(warnings),
        complete=complete,
    )


def read_fields_of(text: TextLayer) -> Fields:
    """The labelled values on the document."""
    return read_fields(text.lines)
