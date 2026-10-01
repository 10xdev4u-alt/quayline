"""Issue 167: binding an extracted text layer to a structured ledger.

The stage four test. These tests are written against the real fixture PDF, not a
hand-written string, because the failure this issue exists to prevent is a binder
that works on a tidy example and falls over on a real carrier file.

The fixture at ``tests/fixtures/born_digital_invoice.pdf`` is a born-digital file
whose text layer parses cleanly today. It states seven free time days from
2026-06-30 to 2026-07-07 and charges three dates from 2026-07-08. Under a
seven day working allowance ending 2026-07-07, charging the eighth, ninth and
tenth is the shape of a correct charge, so the fixture gives the binder something
honest to bind.

The second fixture, ``tests/fixtures/charge_table.pdf``, holds the container,
days, rate and amount columns plus a stated total, and states **no free time at
all**. That is not a binding failure. It is a 541.6(b)(4) omission, and 541.5
makes it automatic, so it raises ``OmittedError`` rather than ``BindError``. Keeping
those two apart is the point of the issue: conflating "the carrier left it out"
with "we could not read it" would report our own extraction defect as an
accusation, which is the most expensive error available in this pipeline.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from quayline.ingest.bind import BindError, OmittedError, bind_ledger
from quayline.ingest.pdftext import TextLayer, TextLayerStatus, extract_text_layer

FIXTURES = Path(__file__).parent / "fixtures"
INVOICE_PDF = FIXTURES / "born_digital_invoice.pdf"
TABLE_PDF = FIXTURES / "charge_table.pdf"


def layer(*lines: str) -> TextLayer:
    """A readable, complete text layer built from lines.

    Complete, not merely readable, because the binder refuses a partial document
    and a test that wanted to reach the binder must not trip that guard on the way.
    """
    return TextLayer(status=TextLayerStatus.READABLE, lines=tuple(lines))


# ------------------------------------------------------- binding the real fixture


def test_the_real_fixture_binds_to_the_dates_it_states() -> None:
    """The load bearing test. A real carrier PDF, bound, no hand written input."""
    text = extract_text_layer(INVOICE_PDF.read_bytes())
    ledger = bind_ledger(text)

    assert ledger.free_time_start == date(2026, 6, 30)
    assert ledger.free_time_end == date(2026, 7, 7)
    assert ledger.allowed_free_time_days == 7


def test_asking_for_money_that_was_never_stated_is_refused() -> None:
    """The gate. ``to_ledger`` is the only route to a Ledger and it checks."""
    text = extract_text_layer(INVOICE_PDF.read_bytes())
    bound = bind_ledger(text)

    with pytest.raises(BindError) as caught:
        bound.to_ledger()

    assert "no Ledger to build" in str(caught.value)


def test_the_narrative_fixture_states_no_money_and_says_so() -> None:
    """It states free time and dates, and no rate and no total.

    So the binder returns a ``TimingLedger`` with ``stated_total`` of ``None``.
    A zero here would be our arithmetic spoken in the carrier's mouth, and zero is
    a claim about their arithmetic while ``None`` is a claim about our reading.
    """
    text = extract_text_layer(INVOICE_PDF.read_bytes())
    bound = bind_ledger(text)

    assert bound.has_money is False
    assert bound.stated_total is None
    assert bound.lines[0].container_number == "MAEU1234567"
    assert bound.lines[0].bol_number == "MAEU123456789"
    assert bound.lines[0].chargeable_days == 3
    assert "no total" in bound.why_no_money()


def test_a_document_stating_money_binds_to_a_money_ledger() -> None:
    """The money path, on a hand built document because the fixture omits timing."""
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Charged Dates: 2026-07-08, 2026-07-09, 2026-07-10",
        "Days: 3",
        "Rate: 100.00",
        "Amount: 300.00",
        "TOTAL: 300.00",
    )
    bound = bind_ledger(text)

    assert bound.has_money is True
    assert bound.stated_total == Decimal("300.00")
    assert bound.to_ledger().stated_total == Decimal("300.00")


def test_the_charge_table_fixture_is_a_carrier_omission_not_our_failure() -> None:
    """It states money and no free time. 541.5 makes that automatic."""
    text = extract_text_layer(TABLE_PDF.read_bytes())

    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert caught.value.cite == "541.6(b)(4)"
    assert "541.5" in str(caught.value)
    assert isinstance(caught.value, BindError)


# ------------------------------------------------------------------ failing closed


def test_a_missing_allowance_is_an_omission_carrying_its_cite() -> None:
    """A document that does not state the allowance is a 541.5 finding.

    Defaulting the allowance to zero would turn a missing disclosure into an
    overcharge finding against the carrier on a document where the carrier omitted
    nothing, because we simply failed to find it.
    """
    text = layer("Start Date of Free Time: 2026-06-30", "End Date of Free Time: 2026-07-07")
    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert caught.value.field == "allowance"
    assert caught.value.cite == "541.6(b)(3)"


def test_a_missing_total_is_not_a_failure_at_all() -> None:
    """The narrative fixture proves it. Timing alone is a bindable document."""
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08, 2026-07-09",
    )
    bound = bind_ledger(text)

    assert bound.has_money is False


def test_an_unparseable_date_carries_the_offending_line() -> None:
    """A gate that blocks without naming the line teaches the carrier nothing.

    The error has to quote what was actually read, so the person holding the
    document can see which line we could not use.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: not a date",
        "End Date of Free Time: 2026-07-07",
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)
    assert "not a date" in str(caught.value)


def test_an_incomplete_text_layer_is_refused_before_any_field_is_read() -> None:
    """Partial text is our failure, not the carrier's.

    A document that dropped strings may be missing a field for a reason that has
    nothing to do with the carrier, and auditing it would report a missing
    disclosure that is our own fault.
    """
    text = TextLayer(
        status=TextLayerStatus.READABLE,
        lines=("Allowed Free Time: 7 days",),
        undecodable_strings=3,
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)
    assert "complete" in str(caught.value).lower()


def test_an_absent_text_layer_is_refused() -> None:
    text = TextLayer(status=TextLayerStatus.ABSENT, lines=())
    with pytest.raises(BindError):
        bind_ledger(text)


def test_a_negative_allowance_is_refused_rather_than_becoming_a_dispute() -> None:
    """Same reasoning as validate.py. A minus sign is our parse, not their bill."""
    text = layer(
        "Allowed Free Time: -3 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08",
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)

    assert not isinstance(caught.value, OmittedError)
    assert "our misreading" in str(caught.value)


def test_a_repeated_charged_date_is_refused_rather_than_double_counted() -> None:
    """Duplicates belong to the arithmetic check, not to the day set."""
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08, 2026-07-08",
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)

    assert "repeat" in str(caught.value)


def test_one_unreadable_charged_date_fails_the_whole_bind() -> None:
    """A partial day set prices an incomplete window, so partial is not enough."""
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08, sometime, 2026-07-10",
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)

    assert "sometime" in str(caught.value)
