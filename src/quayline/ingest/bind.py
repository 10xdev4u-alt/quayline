"""Issue 167, first half: binding an extracted text layer to a structured ledger.

The ``Ledger`` docstring in ``validate.py`` says the field binder that turns a
``TextLayer`` into a ``Ledger`` is a separate concern. This is that binder, and
writing it showed why it was separate: ``TextLayer`` and ``Ledger`` do not carry
the same fields, so nothing converts between them without deciding what happens to
the ones that have no counterpart.

What the two fixtures state, and why it matters

``born_digital_invoice.pdf`` states free time, both endpoints, the charged dates and
the container. It does **not** state a rate and does **not** state a total.

``charge_table.pdf`` states the container, days, rate, amount and total, and states
**no free time at all**.

So the two fixtures are mirror images of each other, and neither one produces a
``Ledger``. That is not a gap in the binder, it is the honest shape of the problem,
and it forced the design below.

One type, with an absent total

``BoundLedger`` carries what both forms have, and carries ``stated_total`` as
``Decimal | None``. ``None`` means the document stated no total. It is never zero.

Zero is a claim about the carrier's arithmetic. ``None`` is a claim about our
reading of the document. Collapsing them would let a missing rate become a
zero-dollar dispute, and would let ``validate.py`` report a line that adds up
against a total nobody stated.

``to_ledger()`` is the gate. It returns a ``Ledger`` when the money is there and
raises when it is not, so a caller cannot accidentally audit money that was never
disclosed.

What this cannot do

It cannot tell a missing field from a field on a later page we have not been
given, and it does not guess carrier identity. 541.6 never asks a carrier to name
itself on the face of the invoice, so carrier selection is a parameter here, the
same argument ``engine/daycount.py`` makes.

Fail closed, and name the line

Every failure raises ``BindError`` carrying the line that could not be used. A
binder that said "validation failed" would leave the person holding the document
unable to say which line we could not read, which is the failure mode
``docs/research/004-evidence.md`` names for the whole dispute layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from quayline.ingest.fields import (
    FieldError,
    Fields,
    parse_date,
    parse_decimal,
    parse_int,
    read_fields,
)
from quayline.ingest.pdftext import TextLayer
from quayline.ingest.validate import InvoiceLine, Ledger
from quayline.models.invoice import (
    CITE_ALLOWANCE,
    CITE_CHARGED_DATES,
    CITE_FREE_TIME_END,
    CITE_FREE_TIME_START,
    CITE_RATE_RULE,
    CITE_TOTAL,
)

#: 541.5, the omission clause. Encoded in ``regulation/kill_switch.py`` with the
#: section number verified in issue 1. Named here because ``OmittedError`` is the
#: one error that becomes a finding rather than a stop.
CITE_OMISSION = "541.5"

#: Matches a labelled value at the start of a line. The label set is deliberately
#: small: every alias added here is a field we will then claim to have read.
_LABELLED = re.compile(r"^(?P<label>[A-Za-z][A-Za-z /]*?):\s*(?P<value>.+?)\s*$")

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%B %d, %Y")


class BindError(FieldError):
    """The document cannot be bound, and here is the line that says why.

    Subclasses ``FieldError`` so a caller that only wants to stop catches one family
    whether the value was unreadable or the disclosure was absent. The distinction
    that matters downstream is between the two subclasses, not between a bind failure
    and a scan failure.
    """


class OmittedError(BindError):
    """A required disclosure is absent from the document.

    This is the strongest finding the engine makes and it is a different kind of
    thing from an unreadable document, so it is a different type.

    541.5 makes the omission automatic. No cure period, no showing of prejudice.
    ``docs/research/001-regulation.md`` records that, and the check table in the
    README calls it automatic for exactly that reason.

    So the binder must not confuse "the carrier left it out" with "we could not
    read it". The first is the finding. The second is our failure, and reporting
    it against the carrier would be the most expensive error available in this
    pipeline, because it is a false accusation built on our own extraction
    defect.

    ``tests/fixtures/charge_table.pdf`` is a real example. It states a container,
    days, rate, amount and total, and no free time at all.
    """

    def __init__(self, field: str, cite: str) -> None:
        super().__init__(
            f"{cite} requires the {field} and the document does not state it. "
            f"541.5 makes the omission automatic: no cure period and no showing "
            f"of prejudice. This is a finding against the carrier, not an "
            f"extraction fault."
        )
        self.field = field
        self.cite = cite


@dataclass(frozen=True, slots=True)
class BoundLedger:
    """A bound document, with the money present or honestly absent.

    Every field is what the carrier wrote. ``stated_total`` is ``None`` when the
    document states no total, and there is no way to build one with a value, which
    is the point.
    """

    lines: tuple[InvoiceLine, ...]
    free_time_start: date
    free_time_end: date
    allowed_free_time_days: int
    stated_total: Decimal
    #: The days the carrier says it charged for, as stated. 541.6(b)(8).
    charged_dates: tuple[date, ...] = ()
    #: When the invoice says it was issued. 541.6(a)(3).
    invoice_date: date | None = None
    #: When the carrier says the container was available. 541.6(b)(6), and absent
    #: on an export invoice, which is a real absence and not a reading failure.
    availability_date: date | None = None
    #: The rate rule the carrier says it billed under, verbatim. 541.6(c)(2).
    #:
    #: Required, because ``engine/amount.py`` cannot price a charge without it and
    #: issue 185 exists because this field was being thrown away. Absent is an
    #: omission against the carrier, not a gap in our data.
    #:
    #: Not normalised. The letter quotes the carrier's own words back at them, and a
    #: carrier who cannot find the rule name in their own tariff has no way to answer.
    rate_rule: str = ""

    @property
    def has_money(self) -> bool:
        """Always true.

        Kept as a property because callers branch on it, and because the day count
        recomputation is the check that needs no money, so a reader of this type can
        see at a glance that a bound document always states a total. 541.6(c)(1)
        requires it and an absent total is an omission, raised at bind time.
        """
        return True

    def to_ledger(self) -> Ledger:
        """The ``Ledger`` for ``validate.validate``.

        Unconditional since issue 185, when binding the rate rule made the total
        mandatory. It used to refuse when the total was absent, which is the third
        state in ``result.py`` applied to a document that cannot legally reach it.
        """
        return Ledger(
            lines=self.lines,
            stated_total=self.stated_total,
            free_time_start=self.free_time_start,
            free_time_end=self.free_time_end,
            allowed_free_time_days=self.allowed_free_time_days,
        )


def _require(fields: Fields, field: str, *labels: str, cite: str = CITE_OMISSION) -> str:
    """A disclosure the regulation requires, or an omission.

    The ``cite`` defaults to 541.5 because a required field that is absent is an
    omission, and an omission is the finding: automatic, no cure period, no showing of
    prejudice. A caller passes the specific clause where one exists, and the message
    then names the clause the carrier failed to disclose.
    """
    return fields.demand(labels, OmittedError(field, cite))


def _scan(text: TextLayer) -> Fields:
    """Collect labelled values, keeping the line each came from."""
    if text.needs_fallback:
        reason = (
            f"{text.undecodable_strings} string(s) could not be decoded"
            if text.undecodable_strings
            else f"text layer status is {text.status.value}"
        )
        raise BindError(
            f"the text layer is not complete, so the document cannot be bound "
            f"without reporting a missing disclosure that is our own fault. "
            f"Reason: {reason}. It matters because needs_fallback is True, which "
            f"means a field may be missing for a reason that has nothing to do "
            f"with the carrier."
        )

    return read_fields(text.lines)


def _date(fields: Fields, field: str, cite: str, *labels: str) -> date:
    raw = _require(fields, field, *labels, cite=cite)
    parsed = parse_date(raw)
    if parsed is None:
        raise BindError(
            f"the {field} is not a date we can read. The line says "
            f"{fields.quoted(labels[0], raw)!r}."
        )
    return parsed


def _int(fields: Fields, field: str, cite: str, *labels: str) -> int:
    raw = _require(fields, field, *labels, cite=cite)
    value = parse_int(raw, field, fields.quoted(labels[0], raw))
    if value < 0:
        raise BindError(
            f"the {field} is {value}, which is our misreading rather than the "
            f"carrier's bill. The line says {fields.quoted(labels[0], raw)!r}."
        )
    return value


def _decimal(fields: Fields, field: str, cite: str, *labels: str) -> Decimal:
    raw = _require(fields, field, *labels, cite=cite)
    return parse_decimal(raw, field, fields.quoted(labels[0], raw))


def _optional_date(fields: Fields, field: str, *labels: str) -> date | None:
    """A date the document may legitimately not state.

    Distinct from ``require``. An export invoice has no container availability date
    under 541.6(b)(6) and that is not a defect, so the absence is recorded as
    ``None``. A date that is present and unreadable still fails.
    """
    raw = fields.get(*labels)
    if raw is None:
        return None
    parsed = parse_date(raw)
    if parsed is None:
        raise BindError(
            f"the {field} is present but not a date we can read. The line says "
            f"{fields.quoted(labels[0], raw)!r}."
        )
    return parsed


def _charge_lines(fields: Fields) -> tuple[InvoiceLine, ...]:
    """Build invoice lines, taking the money only if the document states it.

    Days come from the stated chargeable days when there is one and from the count
    of charged dates otherwise. Never from the money.
    """
    container = fields.get("container number", "container") or ""
    bol = fields.get("bill of lading number", "bill of lading", "bol") or ""
    days_raw = fields.get("days", "chargeable days")
    days_stated = _int(fields, "days", CITE_ALLOWANCE, "days", "chargeable days") if days_raw else 0
    dates = _charged_dates(fields)
    days = len(dates) if days_stated == 0 else days_stated
    rate = _decimal(fields, "rate", CITE_TOTAL, "rate") if fields.get("rate") else Decimal(0)
    amount = (
        _decimal(fields, "amount", CITE_TOTAL, "amount") if fields.get("amount") else Decimal(0)
    )
    return (
        InvoiceLine(
            container_number=container,
            bol_number=bol,
            chargeable_days=days,
            rate=rate,
            amount=amount,
        ),
    )


def _charged_dates(fields: Fields) -> tuple[date, ...]:
    """541.6(b)(8)'s dates, which arrive as one comma separated line.

    Every entry is required. A partial day set is a recomputation over an incomplete
    window and the carrier cannot be asked to explain arithmetic we did not finish.
    """
    raw = _require(
        fields, "charged dates", "charged dates", "charged date", cite=CITE_CHARGED_DATES
    )
    where = fields.quoted("charged dates", raw)
    days: list[date] = []
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        parsed = parse_date(cleaned)
        if parsed is None:
            raise BindError(
                f"one of the charged dates is not a date we can read: {cleaned!r}. "
                f"The line says {where!r}. Every entry is required, because a partial "
                f"day set prices an incomplete window."
            )
        days.append(parsed)
    if not days:
        raise OmittedError("charged dates", CITE_CHARGED_DATES)
    if len(set(days)) != len(days):
        raise BindError(
            f"the charged dates repeat a day. Duplicates belong to the arithmetic "
            f"check, not to the day set. The line says {where!r}."
        )
    return tuple(sorted(days))


def bind_ledger(text: TextLayer) -> BoundLedger:
    """Bind a text layer to a ledger, or say why it cannot be bound."""
    fields = _scan(text)

    free_time_start = _date(
        fields,
        "free time start",
        CITE_FREE_TIME_START,
        "start date of free time",
        "free time start",
    )
    free_time_end = _date(
        fields,
        "free time end",
        CITE_FREE_TIME_END,
        "end date of free time",
        "free time end",
    )
    allowed = _int(fields, "allowance", CITE_ALLOWANCE, "allowed free time", "free time allowed")
    if allowed < 1:
        raise BindError(
            f"541.6(b)(3) requires an allowance of at least one day, got {allowed}. "
            f"The line says {fields.quoted('allowed free time', 'Allowed Free Time')!r}."
        )

    # 541.6(c)(2). Required by the type and by the money check, so its absence is a
    # finding against the carrier rather than something to work around.
    rate_rule = _require(
        fields,
        "rate rule",
        "rate rule",
        "rate rules",
        "tariff rule",
        "charged under",
        cite=CITE_RATE_RULE,
    )

    total_raw = fields.get("total", "invoice total", "total due")
    total = (
        _decimal(fields, "total", CITE_TOTAL, "total", "invoice total", "total due")
        if total_raw
        else None
    )

    if total is None:
        # The carrier named a rule, so a total is what checking that rule means.
        # 541.6(c)(1) requires the total on the invoice.
        raise OmittedError("total", CITE_TOTAL)
    if fields.get("rate") is None:
        raise BindError(
            "the document states a total but no rate, so the money cannot be "
            "checked. A total with no rate is an extraction error, and it is ours."
        )

    lines = _charge_lines(fields)

    return BoundLedger(
        lines=lines,
        free_time_start=free_time_start,
        free_time_end=free_time_end,
        allowed_free_time_days=allowed,
        stated_total=total,
        charged_dates=_charged_dates(fields),
        rate_rule=rate_rule,
        invoice_date=_optional_date(
            fields, "invoice date", "invoice date", "date of invoice", "issue date"
        ),
        availability_date=_optional_date(
            fields,
            "availability date",
            "container availability date",
            "availability date",
        ),
    )


__all__ = [
    "BindError",
    "BoundLedger",
    "OmittedError",
    "bind_ledger",
]
