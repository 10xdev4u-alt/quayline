"""Issue 167, second half: the orchestrator that runs a document through the engine.

These tests are written against the real fixture PDF and against real tariff data
transcribed from carrier publications. The one thing they deliberately do not do is
mock the engine, because the failure this issue exists to prevent is an
orchestrator that wires the wrong inputs together and looks fine against its own
stubs.

What the orchestrator is

``audit()`` takes bytes, a carrier and a terminal, and returns the one result shape
the package returns: an ``AuditResult``. It runs the binding, the day-count
recomputation, the availability contradiction check and the amount comparison, and it
carries every finding onto the result.

What it will not do

It will not produce a recomputed total when the tariff does not resolve. That is the
rule in ``result.py`` and the orchestrator is where it would be easiest to break, so
there is a test for it that asserts ``None`` rather than zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quayline.engine.audit import audit
from quayline.engine.result import (
    CODE_DAYCOUNT_VARIANCE,
    CODE_TARIFF_UNRESOLVED,
    AuditResult,
)
from quayline.tariffs.corpus import load_fixture
from quayline.tariffs.resolution import Resolution

FIXTURES = Path(__file__).parent / "fixtures"
INVOICE_PDF = FIXTURES / "born_digital_invoice.pdf"


def codes(result: AuditResult) -> set[str]:
    return {f.code for f in result.findings}


# -------------------------------------------------------------- the happy path


def test_a_real_fixture_audits_end_to_end() -> None:
    """The load bearing test. Bytes in, AuditResult out, no mocks anywhere."""
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert isinstance(result, AuditResult)
    assert result.carrier == "Maersk"
    assert result.terminal == "newark"
    assert result.computed_charge_days is not None


def test_the_day_count_is_recomputed_from_the_documents_own_disclosures() -> None:
    """Seven free days from 2026-06-30, under a Monday to Saturday basis.

    I checked this by hand before writing the assertion, because "it computed
    something" is the failure this repository has already shipped once.

    Seven working days from Tuesday 2026-06-30, skipping only Sundays, lands on
    Wednesday 2026-07-08. So free time expires 07-08, and only 07-09 and 07-10 are
    billable. The fixture charges 07-08, 07-09 and 07-10, which is three days
    where two are chargeable.

    So this is an overbill of one day, and the engine finds it. That is not a bug
    in the fixture, it is the whole reason the product exists.
    """
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert result.computed_free_time_expiry == date(2026, 7, 8)
    assert result.computed_charge_days == 2


def test_the_real_fixture_is_an_overbill_of_one_day() -> None:
    """The load bearing finding, asserted on a real carrier PDF.

    Three days charged, two chargeable under the carrier's own stated basis. If
    this stops failing, either the engine regressed or the fixture was edited, and
    both are worth knowing about.
    """
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert CODE_DAYCOUNT_VARIANCE in codes(result)


def test_the_overbilled_day_is_named_in_the_finding() -> None:
    """A finding that does not name the day is a letter a carrier can wave through."""
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    daycount = [f for f in result.findings if f.code == CODE_DAYCOUNT_VARIANCE]
    assert daycount, "expected a day count finding"
    assert any(f.days for f in daycount), "a day count finding must carry the days"
    assert any("2026-07-08" in f.detail for f in daycount)


# ------------------------------------------------- the money, and the absence


def test_no_recomputed_total_when_the_document_states_none() -> None:
    """The rule that matters most.

    The fixture states no rate and no total, so there is no money to compare and
    ``recomputed_total`` must be ``None``. A zero here would be quoted in a demand
    letter as the correct total.
    """
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert result.demanded_total is None
    assert result.recomputed_total is None
    assert result.variance is None


def test_no_variance_is_ever_computed_without_both_totals() -> None:
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert result.variance is None
    assert result.variance_pct is None


# ---------------------------------------------------- the unknown carrier gate


def test_an_unknown_carrier_is_refused_rather_than_defaulted() -> None:
    """A carrier we have no day basis for cannot be audited.

    Defaulting would produce a day count from a rule we do not have, which is the
    MSC problem from section one of the onboarding guide, arrived at from the other
    direction.
    """
    with pytest.raises(KeyError):
        audit(INVOICE_PDF.read_bytes(), carrier="not-a-carrier", terminal="newark")


# ------------------------------------------------------------- what the result says


def test_the_result_carries_the_invoice_reference_from_the_document() -> None:
    result = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert result.invoice_ref != ""


def test_a_second_run_of_the_same_document_agrees_with_the_first() -> None:
    """Determinism. An audit that varies between runs cannot be filed on.

    The result is frozen and every input is a parameter, so two runs are equal. If
    this ever fails, something mutable leaked into the chain.
    """
    first = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")
    second = audit(INVOICE_PDF.read_bytes(), carrier="Maersk", terminal="newark")

    assert first == second


def test_the_audit_does_not_mutate_its_input() -> None:
    """Bytes in, and the caller's bytes are the caller's bytes."""
    raw = INVOICE_PDF.read_bytes()
    before = bytes(raw)

    audit(raw, carrier="Maersk", terminal="newark")

    assert raw == before


# --------------------------------------------------------- money, when stated


def test_a_document_with_money_compares_it() -> None:
    """Built by hand because the fixture states no money.

    One container, two chargeable days at 100.00, 200.00 charged, 200.00 total.
    The charged dates are 07-09 and 07-10, which are exactly the two days the
    Monday to Saturday basis leaves billable after free time expires on 07-08. So
    the day count agrees with the money and there is no variance.

    Getting this right matters more than it looks. An earlier version of this test
    charged 07-08 as well and asserted the invoice was clean, which passed against
    a day count that was wrong. The engine was right and the test was not.
    """
    result = audit(
        _pdf_with(
            "Invoice Date: 2026-07-20",
            "Container Availability Date: 2026-06-30",
            "Allowed Free Time: 7 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-07",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Charged Dates: 2026-07-09, 2026-07-10",
            "Days: 2",
            "Rate: 100.00",
            "Amount: 200.00",
            "TOTAL: 200.00",
        ),
        carrier="Maersk",
        terminal="newark",
    )

    assert result.demanded_total == Decimal("200.00")
    assert result.computed_charge_days == 2


def _pdf_with(*lines: str) -> bytes:
    """A minimal single page PDF whose text layer is exactly these lines.

    Written by hand rather than checked in as a fixture so that a test can state a
    document inline and a reviewer can read what it says. The content stream is the
    part the text layer parser reads, and it is what this function varies.
    """
    body = "BT /F1 12 Tf\n" + "\n".join(f"({_escape(line)}) Tj" for line in lines) + "\nET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


# ------------------------------------------- the money path, on real tariff data


def test_a_charge_is_priced_against_a_real_transcribed_tariff() -> None:
    """The whole chain, with the rate coming from a transcribed carrier PDF.

    The block is loaded from ``tests/fixtures/tariffs/maersk_newark_dry.json``,
    which is the Maersk US Newark dry schedule transcribed from the carrier's own
    tariff with its source, effective date and checksum recorded. Days five to
    eight price at 390.00.

    The document charges two days at 100.00, so the demand is 200.00 and the
    recomputed charge is 780.00. That is an underbill rather than an overbill, and
    ``amount.overbilled`` is False, so there is no amount variance finding. The
    point of the test is that a real rate reached the comparison at all.
    """
    block = load_fixture(FIXTURES / "tariffs" / "maersk_newark_dry.json")
    result = audit(
        _pdf_with(
            "Invoice Date: 2026-07-20",
            "Container Availability Date: 2026-06-30",
            "Allowed Free Time: 7 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-07",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Charged Dates: 2026-07-09, 2026-07-10",
            "Days: 2",
            "Rate: 100.00",
            "Amount: 200.00",
            "TOTAL: 200.00",
        ),
        "Maersk",
        "newark",
        tariff=Resolution(block=block),
    )

    assert result.demanded_total == Decimal("200.00")
    assert result.recomputed_total is not None
    assert result.recomputed_total == block.price(result.computed_charge_days or 0)
    assert result.variance == Decimal("200.00") - result.recomputed_total


def test_an_unresolved_tariff_produces_a_warning_and_never_a_total() -> None:
    """Eight of MSC's nine major gateways. This is the correct answer there.

    A ``Resolution`` with no block and a withheld reason is not a degraded mode.
    It is what an honest engine says when it does not hold the rate, and the
    recomputed total must stay ``None`` rather than fall back to zero.
    """
    result = audit(
        _pdf_with(
            "Invoice Date: 2026-07-20",
            "Container Availability Date: 2026-06-30",
            "Allowed Free Time: 7 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-07",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Charged Dates: 2026-07-09, 2026-07-10",
            "Days: 2",
            "Rate: 100.00",
            "Amount: 200.00",
            "TOTAL: 200.00",
        ),
        "Maersk",
        "newark",
        tariff=Resolution(block=None, warnings=("MSC Savannah has no published tariff",)),
    )

    assert CODE_TARIFF_UNRESOLVED in codes(result)
    assert result.recomputed_total is None
    assert result.variance is None
    assert result.demanded_total == Decimal("200.00")
    unresolved = next(f for f in result.findings if f.code == CODE_TARIFF_UNRESOLVED)
    assert "MSC Savannah" in unresolved.detail
