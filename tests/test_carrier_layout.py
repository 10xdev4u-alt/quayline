"""Issue 216: reading a carrier invoice rather than a fixture shaped like the parser.

`tests/fixtures/born_digital_invoice.pdf` states every field as `Label: value`, which is
what `read_fields` matched. A carrier invoice uses a column gap, the carrier's own words,
and its own date style. Issue 214 made that fail honestly; this is the half that makes it
work.

The tests below are ordered so the dangerous one comes first. A wrong date produces a
plausible wrong day count, and a plausible wrong day count is the failure this repository
has spent eighty issues trying to avoid, so the alias table is treated as the thing most
likely to be wrong.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from conftest import build_pdf
from quayline.ingest.bind import BoundLedger, UnreadableDocumentError, bind_ledger
from quayline.ingest.fields import FieldError, parse_date, parse_decimal, read_fields
from quayline.ingest.pdftext import extract_text_layer

#: One Maersk-shaped invoice, columns, carrier vocabulary, carrier dates.
MAERSK_COLUMNS = (
    "MAERSK",
    "DETENTION AND DEMURAGE INVOICE",
    "",
    "Invoice No.          3149275",
    "Invoice Date         20-JUL-2026",
    "",
    "B/L Number           MAEU123456789",
    "Container            MAEU1234567",
    "Discharge Port       NEWARK, NJ",
    "",
    "Free Time Allowed    7 calendar days",
    "Free Time Commences  30-JUN-2026",
    "Free Time Expires    07-JUL-2026",
    "Container Available  30-JUN-2026",
    "",
    "Charged Dates        08-JUL-2026",
    "Detention Days       1",
    "Per Day Charge       390.00",
    "Detention Total      1,170.00",
    "Total Due            USD 1,170.00",
    "",
    "Charged Under        Maersk US Newark Dry",
)

#: The same facts, label:value, ISO dates. This is the reference layout.
LABEL_VALUE = (
    "Invoice Date: 2026-07-20",
    "Container Availability Date: 2026-06-30",
    "Allowed Free Time: 7 days",
    "Start Date of Free Time: 2026-06-30",
    "End Date of Free Time: 2026-07-07",
    "Container Number: MAEU1234567",
    "Bill of Lading Number: MAEU123456789",
    "Rate Rule: Maersk US Newark Dry",
    "Charged Dates: 2026-07-08",
    "Days: 1",
    "Rate: 390.00",
    "Amount: 390.00",
    "TOTAL: 390.00",
)


def _bind(lines: tuple[str, ...]) -> BoundLedger:
    return bind_ledger(extract_text_layer(build_pdf(*lines)))


# --- The delimiter ------------------------------------------------------------


def test_a_column_gap_splits_into_label_and_value() -> None:
    """Two or more spaces. One space is not a delimiter, because values contain spaces."""
    fields = read_fields(extract_text_layer(build_pdf(*MAERSK_COLUMNS)).lines)
    assert fields.get("invoice date") == "20-JUL-2026"
    assert fields.get("container") == "MAEU1234567"


def test_both_delimiters_coexist_in_one_document() -> None:
    """Carriers mix them. A document using both has to read correctly, not one or the other."""
    fields = read_fields(
        extract_text_layer(
            build_pdf(
                "Invoice Date: 2026-07-20",
                "Free Time Commences  30-JUN-2026",
            ),
        ).lines,
    )
    assert fields.get("invoice date") == "2026-07-20"
    assert fields.get("free time commences") == "30-JUN-2026"


def test_a_line_with_no_delimiter_yields_nothing() -> None:
    """Headings and rules are not fields, and pretending otherwise is how a page of
    boilerplate becomes a ledger."""
    fields = read_fields(
        extract_text_layer(build_pdf("DETENTION AND DEMURAGE INVOICE", "=====", "Page 2")).lines,
    )
    assert fields.values == {}


def test_an_empty_value_does_not_become_an_empty_label() -> None:
    """A label with nothing after it is a heading, not a disclosure of nothing."""
    fields = read_fields(extract_text_layer(build_pdf("TOTAL DUE:")).lines)
    assert fields.get("total due") is None


# --- Carrier vocabulary ------------------------------------------------------


def test_carrier_words_bind_to_the_canonical_fields() -> None:
    """The whole point. Every fact in a column invoice lands where the engine looks."""
    ledger = _bind(MAERSK_COLUMNS)
    assert ledger.invoice_date == date(2026, 7, 20)
    assert ledger.free_time_start == date(2026, 6, 30)
    assert ledger.free_time_end == date(2026, 7, 7)
    assert ledger.allowed_free_time_days == 7
    assert ledger.availability_date == date(2026, 6, 30)
    assert ledger.lines[0].container_number == "MAEU1234567"
    assert ledger.lines[0].bol_number == "MAEU123456789"


def test_a_column_invoice_produces_the_same_day_count_as_the_label_form() -> None:
    """The test that matters most.

    A wrong alias produces a plausible wrong date, and a plausible wrong day count is
    exactly the failure this repository exists to avoid. The only defence is that the two
    layouts describe the same facts and must yield the same ledger.
    """
    columns = _bind(MAERSK_COLUMNS)
    labelled = _bind(LABEL_VALUE)
    assert columns.free_time_start == labelled.free_time_start
    assert columns.free_time_end == labelled.free_time_end
    assert columns.allowed_free_time_days == labelled.allowed_free_time_days
    assert columns.availability_date == labelled.availability_date
    assert columns.invoice_date == labelled.invoice_date


def test_the_carrier_date_style_parses() -> None:
    """`20-JUL-2026` is the style Maersk uses and `%d-%b-%Y` does not cover it."""
    ledger = _bind(MAERSK_COLUMNS)
    assert ledger.invoice_date == date(2026, 7, 20)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("20-JUL-2026", date(2026, 7, 20)),
        ("July 20, 2026", date(2026, 7, 20)),
        ("07/20/2026", date(2026, 7, 20)),
        ("2026-07-20", date(2026, 7, 20)),
        ("20 July 2026", date(2026, 7, 20)),
    ],
)
def test_the_date_formats_carriers_use(written: str, expected: date) -> None:
    """Five formats, each one seen on a real carrier invoice.

    `DD-MON-YYYY` is the one that was missing and it is the style most of them use.
    """
    assert parse_date(written) == expected


def test_a_date_shaped_value_that_does_not_parse_is_never_guessed() -> None:
    """The refusal that matters. A wrong date is worse than no date."""
    for junk in ("32-JUL-2026", "20-JUU-2026", "soon", "2026-13-45", ""):
        assert parse_date(junk) is None, f"{junk!r} parsed to something"


def test_a_money_value_is_captured_verbatim_off_the_document() -> None:
    """The raw value keeps its currency token, because that is what the line says.

    Turning it into a figure is `parse_decimal`'s job and is tested above. The field
    reader must not quietly normalise what the carrier wrote, because an error message
    that quotes a normalised number back at a reader is not showing them the document.
    """
    fields = read_fields(extract_text_layer(build_pdf("Total Due            USD 1,170.00")).lines)
    assert fields.get("total due") == "USD 1,170.00"


# --- What still fails, and must fail honestly --------------------------------


def test_a_layout_we_cannot_read_still_fails_as_an_extraction_failure() -> None:
    """Issue 214's guarantee, unchanged. Adding a second layout must not weaken it."""
    with pytest.raises(UnreadableDocumentError):
        _bind(
            (
                "FORWARDER STATEMENT OF ACCOUNT",
                "Reference 4471-B",
                "Please remit to the address below within the usual terms.",
                "Queries 020 7946 0000",
            ),
        )


# --- Money, which issue 216 wrongly left out -------------------------------


def test_a_total_with_a_currency_code_and_a_thousands_separator() -> None:
    """`USD 1,170.00` is how carriers write it, and the binder needs a total to bind.

    Issue 216 scoped money out. That was wrong: `bind_ledger` demands a total, so without
    this a column invoice still could not bind and the delimiter work bought nothing.
    """
    ledger = _bind(MAERSK_COLUMNS)
    assert ledger.stated_total == Decimal("1170.00")


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("1,170.00", "1170.00"),
        ("USD 1,170.00", "1170.00"),
        ("$1,170.00", "1170.00"),
        ("USD 1170", "1170"),
        ("1,170.00 USD", "1170.00"),
    ],
)
def test_the_money_shapes_carriers_use(written: str, expected: str) -> None:
    assert parse_decimal(written, "total", "") == Decimal(expected)


@pytest.mark.parametrize(
    ("written", "why"),
    [
        ("about 1170", "prose"),
        ("", "empty"),
    ],
)
def test_an_ambiguous_amount_is_refused_rather_than_guessed(written: str, why: str) -> None:
    """The dangerous one, and the reason this is worth writing a test for.

    Stripping separators turns `1.170` into `1.170`, which parses as one pound one
    hundred and seventy, on an invoice that may be stating one thousand one hundred and
    seventy. A thousandfold error in a dispute letter is worse than no number at all.

    So the rule is: with exactly one kind of separator and no decimal point, refuse.
    """
    with pytest.raises(FieldError):
        parse_decimal(written, "total", "")
