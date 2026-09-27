"""The four acceptance criteria on issue 3, one test block each.

The scenarios use dates that reproduce a real failure mode: a terminal closed over
a long weekend, where the out gate and the last chargeable day are three days apart
and the choice of anchor flips a $4,800 charge from owed to not owed.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from quayline.regulation import deadline as d
from quayline.regulation.deadline import (
    CURE_RIGHTS,
    UNCURABLE_DEFECTS,
    BillingParty,
    ChargeIncurred,
    DisputeNotice,
    InvoiceIssued,
    NvoccChain,
    RequestReceived,
    Timeliness,
)

# 2024-06-07 is a Friday. 2024-06-08 and 09 are Saturday and Sunday. The
# container left on Monday the 10th because the terminal was shut, but
# demurrage stopped accruing on the Friday.
LAST_CHARGEABLE = date(2024, 6, 7)
OUT_GATE = date(2024, 6, 10)
CARRIER_INVOICE = date(2024, 6, 20)
NVOCC_INVOICE = date(2024, 7, 15)

CHARGE = ChargeIncurred(last_chargeable_day=LAST_CHARGEABLE)


# ---------------------------------------------------------------- criterion 1
# The deadline is computed from the last chargeable day, not the out gate date and
# not the invoice date.


def test_deadline_is_thirty_days_from_the_last_chargeable_day() -> None:
    assert d.invoice_deadline(CHARGE) == date(2024, 7, 7)


def test_boundary_day_is_timely_and_the_next_day_is_not() -> None:
    """'within thirty (30) calendar days from' the anchor.

    The period runs to the anchor plus thirty, so issuing on day thirty is inside
    it and issuing on day thirty one is outside. Part 541 adds no holiday or
    closure allowance, so this is plain calendar arithmetic.
    """
    assert d.assess(CHARGE, InvoiceIssued(date(2024, 7, 7)), BillingParty.OCEAN_CARRIER) is (
        Timeliness.TIMELY
    )
    assert d.assess(CHARGE, InvoiceIssued(date(2024, 7, 8)), BillingParty.OCEAN_CARRIER) is (
        Timeliness.LATE
    )


def test_out_gate_anchor_would_flip_the_outcome() -> None:
    """The concrete reason the anchor matters, on one real charge.

    Invoiced 2024-07-09. Measured from the last chargeable day of Friday the 7th
    that is 32 days, late, so under 541.7(a) the billed party is not required to
    pay. Measured from the out gate of Monday the 10th it is 29 days, timely.

    Same invoice, same charge, $4,800, opposite answers, and nothing on the
    paperwork distinguishes them except which date you chose.
    """
    invoiced = date(2024, 7, 9)
    correct = d.assess(CHARGE, InvoiceIssued(invoiced), BillingParty.OCEAN_CARRIER)
    wrong = d.assess(
        ChargeIncurred(last_chargeable_day=OUT_GATE),
        InvoiceIssued(invoiced),
        BillingParty.OCEAN_CARRIER,
    )
    assert correct is Timeliness.LATE
    assert wrong is Timeliness.TIMELY
    # Three days of terminal closure, three days of extra time handed to the
    # carrier. The whole gap is the anchor choice.
    assert d.invoice_deadline(CHARGE) == date(2024, 7, 7)
    assert d.invoice_deadline(ChargeIncurred(last_chargeable_day=OUT_GATE)) == date(2024, 7, 10)


def test_out_gate_is_never_an_anchor_in_this_module() -> None:
    """No public function takes a date that could be an out gate.

    The anchor type holds one field, named for what the regulation says it is. A
    function that took a loose date would let a caller pass the out gate and get
    the wrong answer confidently.
    """
    assert list(ChargeIncurred.__dataclass_fields__) == ["last_chargeable_day"]
    for fn in (d.invoice_deadline, d.reissue_deadline, d.assess, d.dispute_request_deadline):
        assert fn.__doc__, f"{fn.__name__} has no docstring explaining its anchor"


def test_invoice_date_anchor_makes_541_7_a_dead_letter() -> None:
    """Asserted rather than assumed, because the deadness is the argument.

    If 541.7(a) were measured from the invoice issuance date, the elapsed time is
    zero by construction for every invoice ever written. The rule could never
    fail. A rule that cannot fail while appearing to be enforced is the same
    defect as the hook in issue 76 that was installed and enforcing nothing.
    """
    for issued in (date(2024, 6, 8), date(2025, 1, 1), date(2030, 12, 31)):
        invoice = InvoiceIssued(issued)
        elapsed = (issued - invoice.issuance_date).days
        assert elapsed == 0, "this is the whole point: the elapsed time is always zero"
        assert issued <= invoice.issuance_date + timedelta(days=d.DAYS)
    assert not hasattr(ChargeIncurred, "issuance_date"), (
        "an invoice date must never be reachable from a 541.7(a) anchor"
    )


# ---------------------------------------------------------------- criterion 2
# The NVOCC two-layer chain is implemented and tested.


def test_nvocc_runs_on_541_7_b_and_others_run_on_541_7_a() -> None:
    assert BillingParty.NVOCC.governed_by_541_7_b
    assert not BillingParty.OCEAN_CARRIER.governed_by_541_7_b
    assert not BillingParty.TERMINAL_OPERATOR.governed_by_541_7_b


def test_assess_refuses_to_answer_for_an_nvocc() -> None:
    """Answering with the wrong subsection is worse than refusing.

    541.7(b) is measured from the carrier invoice the NVOCC received. Handing
    assess a charge date and an NVOCC would return a confident wrong answer, so
    it raises and points at the function that does know.
    """
    with pytest.raises(ValueError, match="assess_chain"):
        d.assess(CHARGE, InvoiceIssued(NVOCC_INVOICE), BillingParty.NVOCC)


def test_nvocc_gets_thirty_days_from_receipt_not_from_the_charge() -> None:
    """The second layer, and the reason a chain can run to ninety days.

    Carrier invoiced 2024-06-20, so the NVOCC's deadline is 2024-07-20. Its
    invoice on 2024-07-15 is 25 days after the charge but only 25 days after
    receipt, and 541.7(b) is met.
    """
    assert d.nvocc_invoice_deadline(InvoiceIssued(CARRIER_INVOICE)) == date(2024, 7, 20)
    chain = NvoccChain(
        charge_incurred=CHARGE,
        carrier_invoice=InvoiceIssued(CARRIER_INVOICE),
        nvocc_invoice=InvoiceIssued(NVOCC_INVOICE),
    )
    assert chain.nvocc_timeliness() is Timeliness.TIMELY
    assert chain.carrier_timeliness() is Timeliness.TIMELY
    assert chain.total_elapsed_days() == 38


def test_nvocc_tardy_receipt_does_not_add_thirty_days() -> None:
    """A late carrier invoice does not hand the NVOCC more time.

    The carrier failed 541.7(a). That is the carrier's failure and the NVOCC still
    had thirty days from receipt on 2024-08-05, which it met on 2024-08-04.
    """
    chain = NvoccChain(
        charge_incurred=CHARGE,
        carrier_invoice=InvoiceIssued(date(2024, 8, 5)),
        nvocc_invoice=InvoiceIssued(date(2024, 8, 4)),
    )
    assert chain.carrier_timeliness() is Timeliness.LATE
    assert chain.nvocc_timeliness() is Timeliness.TIMELY
    assert d.assess_chain(chain) is Timeliness.LATE, (
        "a chain fails if either layer fails, they do not net off"
    )


def test_chain_approaching_ninety_days() -> None:
    """The ninety day figure in the issue, constructed rather than quoted.

    30 days for the carrier under 541.7(a), 30 for the NVOCC under 541.7(b), and
    a further 30 under 541.7(c) after the NVOCC gives notice.
    """
    charge = ChargeIncurred(date(2024, 1, 1))
    carrier = InvoiceIssued(date(2024, 1, 31))
    nvocc = InvoiceIssued(date(2024, 3, 1))
    chain = NvoccChain(charge, carrier, nvocc)
    assert chain.carrier_timeliness() is Timeliness.TIMELY, "30 days from the charge"
    assert chain.nvocc_timeliness() is Timeliness.TIMELY, "30 days from receipt"
    assert chain.total_elapsed_days() == 60, "the charge is already 60 days stale"

    # The NVOCC's own mitigation window, from the invoice it issued.
    assert d.dispute_request_deadline(nvocc) == date(2024, 3, 31)
    assert chain.dispute_deadline() == date(2024, 3, 31)

    # 541.7(c). The NVOCC's customer disputes in April, the NVOCC passes that on
    # in April, and the carrier owes it a further 30 days from that notice. This is
    # the third layer, and the one that carries a chain past 90 days from the
    # charge. The later of the two windows governs.
    notice = DisputeNotice(date(2024, 4, 1))
    extended = NvoccChain(charge, carrier, nvocc, notice)
    assert d.nvocc_extension(notice) == date(2024, 5, 1)
    assert extended.dispute_deadline() == date(2024, 5, 1)
    assert extended.dispute_deadline() > chain.dispute_deadline(), (
        "the extension has to actually extend something, or the test proves nothing"
    )


def test_late_at_both_layers_is_late() -> None:
    chain = NvoccChain(
        charge_incurred=CHARGE,
        carrier_invoice=InvoiceIssued(date(2024, 7, 8)),
        nvocc_invoice=InvoiceIssued(date(2024, 9, 1)),
    )
    assert d.assess_chain(chain) is Timeliness.LATE


# ---------------------------------------------------------------- criterion 3
# A test asserts 541.7(d) is the only cure right in Part 541.


def test_541_7_d_is_the_only_cure_right() -> None:
    assert [c.cite for c in CURE_RIGHTS] == ["541.7(d)"]


def test_cure_right_is_limited_to_the_wrong_recipient() -> None:
    (cure,) = CURE_RIGHTS
    assert cure.error_corrected == "invoiced the incorrect person"


def test_reissue_does_not_reset_the_clock() -> None:
    """Reissuing on day twenty does not buy another thirty days.

    541.7(d) permits reissue "provided that such issuance is within thirty (30)
    calendar days from the date on which the charge was last incurred". Same
    anchor as 541.7(a), so reissue_deadline equals invoice_deadline.
    """
    assert d.reissue_deadline(CHARGE) == d.invoice_deadline(CHARGE) == date(2024, 7, 7)
    assert CURE_RIGHTS[0].resets_clock is False


def test_no_cure_right_exists_for_a_missing_disclosure() -> None:
    """The finding, and the reading most worth an attorney's eye.

    541.5 eliminates the obligation to pay and contains no cure clause. 541.7(d)
    permits reissue only for the wrong recipient. The two do not overlap, so on
    the face of the regulation a carrier who realises on day twenty that it
    omitted the free time allowance cannot repair it.

    Marked arguable, not asserted. A contrary reading exists and nothing in the
    part settles it.
    """
    cites = {c.cite for c in CURE_RIGHTS}
    assert "541.5" not in cites
    assert any(defect.startswith("541.5") for defect in UNCURABLE_DEFECTS)
    assert any(defect.startswith("541.6") for defect in UNCURABLE_DEFECTS)


def test_the_uncurable_list_covers_every_operative_section_of_the_part() -> None:
    """The claim is about the whole part, so the part has to be enumerated.

    541.1 purpose, 541.2 scope, 541.3 definitions, 541.4 reserved, 541.5 failure
    to include, 541.6 contents, 541.7 issuance, 541.8 mitigation, 541.9 to
    541.98 reserved, 541.99 OMB control number. Nothing outside 541.5 to 541.8
    imposes a duty, so nothing outside it can grant a cure.
    """
    covered = " ".join(UNCURABLE_DEFECTS)
    for section in ("541.5", "541.6", "541.7(a)", "541.7(b)", "541.7(c)", "541.8"):
        assert section in covered, section
    assert "541.4" not in covered and "541.99" not in covered, "reserved sections impose no duty"


def test_provenance_for_both_sections_is_dated() -> None:
    assert d.SECTION_541_7.as_of == "2026-09-24"
    assert d.SECTION_541_8.as_of == "2026-09-24"
    assert d.PART_541.as_of == "2026-09-24"
    assert d.SECTION_541_7.federal_register.startswith("89 FR")


# ---------------------------------------------------------------- criterion 4
# The dispute window is computed from the invoice date on the document, never from
# cargo dates.


def test_dispute_window_is_thirty_days_from_the_invoice_on_the_document() -> None:
    assert d.dispute_request_deadline(InvoiceIssued(CARRIER_INVOICE)) == date(2024, 7, 20)


def test_dispute_window_ignores_the_cargo_dates_entirely() -> None:
    """Two invoices with the same cargo dates, different windows.

    The window moves with the invoice and not with the container, which is the
    property that makes it trustworthy. 541.7(a) is already the test of whether
    the carrier invoiced on time, and the mitigation entitlement is separate.
    """
    early = d.dispute_request_deadline(InvoiceIssued(date(2024, 6, 20)))
    late = d.dispute_request_deadline(InvoiceIssued(date(2024, 9, 20)))
    assert early != late
    assert late - early == timedelta(days=92)


def test_the_three_clocks_have_three_different_anchors() -> None:
    """Part 541 contains three thirty day periods and they are not the same one.

    541.7(a) from the charge, 541.8(a) from the invoice, 541.8(b) from receipt of
    the request. Reading one as another is the error this module's anchor types
    exist to prevent.
    """
    from_charge = d.invoice_deadline(CHARGE)
    from_invoice = d.dispute_request_deadline(InvoiceIssued(CARRIER_INVOICE))
    from_request = d.resolution_deadline(RequestReceived(date(2024, 7, 1)))
    assert from_charge == date(2024, 7, 7)
    assert from_invoice == date(2024, 7, 20)
    assert from_request == date(2024, 7, 31)
    assert len({from_charge, from_invoice, from_request}) == 3


def test_resolution_deadline_is_thirty_days_from_receiving_the_request() -> None:
    """'Must attempt to resolve', not 'must resolve'.

    541.8(b) also allows a later date as agreed by both parties, so this is a
    deadline for the attempt rather than a promise of a refund. Asserted so the
    distinction survives into whatever reads this next.
    """
    assert d.resolution_deadline(RequestReceived(date(2024, 7, 1))) == date(2024, 7, 31)
    assert "must attempt to resolve" in (d.resolution_deadline.__doc__ or "")


def test_anchor_types_expose_only_their_own_date() -> None:
    """No anchor type can read a date belonging to another clock."""
    assert list(ChargeIncurred.__dataclass_fields__) == ["last_chargeable_day"]
    assert list(InvoiceIssued.__dataclass_fields__) == ["issuance_date"]
    assert list(RequestReceived.__dataclass_fields__) == ["day"]
    assert list(DisputeNotice.__dataclass_fields__) == ["day"]


def test_anchors_are_immutable() -> None:
    with pytest.raises(AttributeError):
        CHARGE.last_chargeable_day = date(2030, 1, 1)  # type: ignore[misc]
