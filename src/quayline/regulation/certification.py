"""Issue 33: the most dangerous field on the invoice.

541.6(e)(2) requires the billing party to certify that its performance did not
cause or contribute to the underlying invoiced charges. That is a **factual
representation by the carrier**, about its own conduct, on a document it signed.

Two consequences follow that no other disclosure on the invoice has:

1. **A false statement is a 541.5 failure.** The required minimum information must
   not only be present, it must be accurate. An (e)(2) certification that is
   factually wrong means the invoice does not carry the required certification in
   any meaningful sense.
2. **A false statement is a 46 U.S.C. 41102(c) violation**, with civil penalties
   under 41107. An unreasonable practice in the handling of property. No other
   invoice defect in this package carries a penalty provision behind it.

That is why the field is the most dangerous one on the invoice, in both
directions. For the carrier, because affirming it falsely is a federal violation
and not just a billing dispute. For us, because asserting it is false without a
documented delay is an accusation we cannot support.

The single-delay rule

**One documented carrier-caused delay invalidates the certification for the whole
invoice**, not just for the days it covers.

The certification is a blanket representation about the invoice. It does not say
"our performance did not cause the charges on July 8th". It says it did not cause
or contribute to the underlying invoiced charges, full stop. A representation that
is false in any part is false, and there is no reading of it under which the true
days survive and the false ones fall away. The respondent cannot concede the delay
and keep the certification.

This is also why the test is worth running when we expect to lose it. A
certification we cannot falsify is a certification that stands, and knowing that
before the letter goes out is the difference between a demand and an embarrassment.

What makes a delay documented

Three kinds of evidence, and the list is closed because an open-ended "anything
showing the carrier was at fault" is how a vague suspicion becomes a filed claim:

- **Booking rollover notices.** The carrier moved the box off the sailing it was
  booked on. Dated, carrier-issued, and the most direct possible evidence that the
  carrier's performance contributed.
- **Vessel schedule against actual arrival.** The published schedule and the
  actual port call, side by side. A late vessel that pushed availability past free
  time is carrier performance, not terminal congestion.
- **Delivery order timestamps.** When the carrier released the box versus when it
  could have. A delivery order issued late, with no customs or terminal hold to
  explain it, is the carrier holding its own customer's freight.

Each is a dated, sourced record of a specific event. "The terminal was congested"
is not a documented delay. "Appointments were hard to get" is not a documented
delay. The test needs a date, a kind, and a source, or it has nothing to stand on.

Absence is already handled

A missing (e)(2) certification is an omission like any other, and the kill switch
fires on it without anything from this module. Criterion one is therefore a test
against the existing path, not new code. New code that duplicated the omission
check would create a second place the same absence is evaluated, and two places
evaluating the same absence is how they eventually disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from quayline.regulation.checklist import by_cite

#: 541.6(e)(2), verbatim from the checklist.
CITE_E2 = "541.6(e)(2)"

#: The penalty provisions behind a false certification.
CITE_UNREASONABLE_PRACTICE = "46 U.S.C. 41102(c)"
CITE_CIVIL_PENALTIES = "46 U.S.C. 41107"


class DelayKind(StrEnum):
    """The three documented ways a carrier's performance shows up in the record.

    Closed, because the test needs a date, a kind and a source, and an open-ended
    "the carrier was at fault somehow" is how a vague suspicion becomes a filed
    claim.
    """

    #: The carrier rolled the booking to a later sailing.
    ROLLOVER = "booking rollover"
    #: The vessel arrived after its published schedule.
    LATE_VESSEL = "vessel late against schedule"
    #: The delivery order was issued late with no hold to explain it.
    LATE_DELIVERY_ORDER = "delivery order issued late"


@dataclass(frozen=True, slots=True)
class CarrierCausedDelay:
    """One documented delay event.

    ``source`` is what makes it documented rather than alleged: the rollover
    notice reference, the schedule and actual arrival pair, the timestamp. A delay
    with no source is a suspicion, and a suspicion filed as a 41102(c) violation
    is a good way to lose the whole dispute.
    """

    occurred: date
    kind: DelayKind
    source: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            msg = (
                "a delay with no source is an allegation, not evidence. The test in "
                "this module needs a dated, sourced record, and a suspicion filed as "
                "a 41102(c) violation loses the whole dispute."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class CertificationTest:
    """The result of testing an affirmed certification against the record.

    ``invalidated`` is True when at least one documented delay exists. False means
    the certification stands as far as we can tell, which is itself useful: a letter
    that does not allege a false certification is a letter that cannot be embarrassed
    by one.
    """

    invalidated: bool
    delays: tuple[CarrierCausedDelay, ...] = ()
    evidence_consulted: tuple[str, ...] = ()

    @property
    def voids_invoice(self) -> bool:
        """A false (e)(2) is a 541.5 failure.

        The required certification is not meaningfully present when it is factually
        wrong, so the obligation is eliminated by the same path as an absence.
        """
        return self.invalidated

    def sentence(self) -> str:
        if not self.invalidated:
            return (
                "The (e)(2) certification was tested against the delays on record and "
                "stands. This letter makes no claim about the carrier's performance."
            )
        kinds = ", ".join(sorted({d.kind.value for d in self.delays}))
        return (
            f"The carrier certified under 541.6(e)(2) that its performance did not cause "
            f"or contribute to these charges, and the record shows {len(self.delays)} "
            f"documented carrier-caused delay(s): {kinds}. A representation false in any "
            f"part is false, so the certification fails for the whole invoice."
        )


#: What to consult before alleging anything. Closed, for the reason the delay kinds
#: are closed.
EVIDENCE_NEEDED: tuple[str, ...] = (
    "booking rollover notices for the shipment",
    "the vessel schedule against its actual arrival",
    "delivery order timestamps against any holds on record",
)


def evidence_needed() -> tuple[str, ...]:
    """The closed evidence list, so a caller cannot assemble its own."""
    return EVIDENCE_NEEDED


def test_certification(
    delays: tuple[CarrierCausedDelay, ...],
    *,
    evidence_consulted: tuple[str, ...] = EVIDENCE_NEEDED,
) -> CertificationTest:
    """Test an affirmed certification against documented delays.

    Takes the delays, not the invoice, because the certification is about the
    carrier's conduct and the invoice is about the carrier's arithmetic. Conflating
    them is how a dispute about money becomes an accusation about conduct without
    anybody deciding to make one.

    One delay is enough. The certification is a blanket representation, so a single
    documented carrier-caused delay falsifies the whole statement rather than the
    days it covers.
    """
    return CertificationTest(
        invalidated=bool(delays),
        delays=delays,
        evidence_consulted=evidence_consulted,
    )


def e2_field() -> object:
    """The checklist field this hooks to, so the absence path and this module read
    the same clause."""
    return by_cite(CITE_E2)


__all__ = [
    "CITE_CIVIL_PENALTIES",
    "CITE_E2",
    "CITE_UNREASONABLE_PRACTICE",
    "EVIDENCE_NEEDED",
    "CarrierCausedDelay",
    "CertificationTest",
    "DelayKind",
    "e2_field",
    "evidence_needed",
    "test_certification",
]
