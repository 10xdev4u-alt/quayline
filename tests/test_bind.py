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

from conftest import build_pdf
from quayline.ingest.bind import (
    BindError,
    OmittedError,
    UnreadableDocumentError,
    bind_ledger,
)
from quayline.ingest.fields import read_fields
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


def test_a_missing_total_is_now_an_omission_rather_than_a_third_state() -> None:
    """Issue 185 narrowed this. 541.6(c)(1) requires the total on the invoice.

    Until then a document could bind with ``stated_total`` of ``None`` and callers
    branched on ``has_money``. Binding the rate rule under 541.6(c)(2) makes a
    document that states a rule but no total unreadable, so the absent branch became
    unreachable and was removed rather than left as dead code.

    A test that keeps exercising an unreachable branch is coverage of nothing.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08, 2026-07-09",
        "Rate Rule: Maersk US Newark Dry",
        "Rate: 100.00",
        "Amount: 200.00",
    )

    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert caught.value.cite == "541.6(c)(1)"
    assert caught.value.field == "total"


def test_the_fixture_binds_the_carriers_own_rate_rule() -> None:
    """541.6(c)(2), read off the document rather than typed by an operator.

    The fixture states ``Maersk US Newark Dry``, which is a real rule in the
    transcribed corpus, so a caller that has the corpus can price this invoice. The
    name is carried verbatim because the letter quotes the carrier's own words.
    """
    bound = bind_ledger(extract_text_layer(INVOICE_PDF.read_bytes()))

    assert bound.rate_rule == "Maersk US Newark Dry"
    assert bound.stated_total == Decimal("1170.00")
    assert bound.lines[0].container_number == "MAEU1234567"
    assert bound.lines[0].chargeable_days == 3


def test_a_document_stating_money_binds_to_a_money_ledger() -> None:
    """The money path, on a hand built document because the fixture omits timing."""
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Rate Rule: Maersk US Newark Dry",
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
    assert bound.rate_rule == "Maersk US Newark Dry"


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


def test_a_missing_rate_rule_is_an_omission_not_an_unboundable_document() -> None:
    """The three states narrowed when issue 185 bound the rate rule.

    This test used to assert that a document stating timing but no money binds. It
    no longer does, because 541.6(c)(2) requires the carrier to name the rule it
    billed under and ``engine/amount.py`` cannot proceed without it. A document with
    no rule is an omission against the carrier, which is the strongest finding the
    engine produces, so refusing to bind it is the correct outcome rather than a
    regression.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Charged Dates: 2026-07-08, 2026-07-09",
    )

    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert caught.value.cite == "541.6(c)(2)"


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
        "Rate Rule: Maersk US Newark Dry",
        "Rate: 100.00",
        "Amount: 200.00",
        "TOTAL: 200.00",
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
        "Rate Rule: Maersk US Newark Dry",
        "Rate: 100.00",
        "Amount: 300.00",
        "TOTAL: 300.00",
    )
    with pytest.raises(BindError) as caught:
        bind_ledger(text)

    assert "sometime" in str(caught.value)


# ------------------------------------------- 541.6(c)(2), the disclosed rate rule


def test_the_disclosed_rate_rule_is_captured() -> None:
    """541.6(c)(2). The carrier must name the rule it billed under.

    It is on the invoice, so it is a bindable field rather than an operator input.
    Nothing downstream can price a charge without it, and issue 185 exists because
    the binder was throwing it away.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Charged Dates: 2026-07-09, 2026-07-10",
        "Rate Rule: Maersk US Newark Dry",
        "Rate: 100.00",
        "Amount: 200.00",
        "TOTAL: 200.00",
    )
    bound = bind_ledger(text)

    assert bound.rate_rule == "Maersk US Newark Dry"


def test_a_missing_rate_rule_is_an_omission_carrying_5416c2() -> None:
    """The carrier's disclosure is absent, which is a finding and not our gap.

    ``AGENTS.md`` section five and the three-state rule in ``result.py`` both point
    the same way: absent is not the same as zero, and absent is not our problem.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Charged Dates: 2026-07-09, 2026-07-10",
    )

    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert caught.value.cite == "541.6(c)(2)"
    assert caught.value.field == "rate rule"


def test_a_document_with_a_rate_rule_always_states_a_total() -> None:
    """A named rule with no money is the extraction error this module exists for.

    The rule tells us what the carrier says it billed under, so a total is what
    checking that rule means. Without one there is nothing to compare and the
    document is not auditable for money.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Charged Dates: 2026-07-09, 2026-07-10",
        "Rate Rule: Maersk US Newark Dry",
    )

    with pytest.raises(OmittedError) as caught:
        bind_ledger(text)

    assert "total" in caught.value.field


def test_the_rate_rule_is_carried_verbatim_not_normalised() -> None:
    """We quote the carrier's own words back at them.

    Normalising here would mean the letter cites a rule name the carrier never wrote,
    and a carrier who cannot find that rule in their own tariff has no way to answer.
    """
    text = layer(
        "Allowed Free Time: 7 days",
        "Start Date of Free Time: 2026-06-30",
        "End Date of Free Time: 2026-07-07",
        "Container Number: MAEU1234567",
        "Bill of Lading Number: MAEU123456789",
        "Charged Dates: 2026-07-09",
        "Rate Rule:  Maersk  US Newark Dry  ",
        "Rate: 100.00",
        "Amount: 100.00",
        "TOTAL: 100.00",
    )

    # Outer whitespace is stripped by the label scan, inner spacing is preserved,
    # because the carrier's rule name is the thing we are obliged to quote.
    assert bind_ledger(text).rate_rule == "Maersk  US Newark Dry"


# --- A document we cannot read is not an omission, issue 214 ------------------


def realistic_invoice() -> bytes:
    """A carrier invoice shaped the way carriers shape them.

    Columns rather than `Label: value`, uppercase names, the carrier's own date style,
    and different words for the same facts. This is not a hostile document. It is what
    the binder meets on any real carrier PDF, and until issue 214 every test in this
    repository used a fixture whose every line ended in a colon.

    **Issue 216 taught the binder to read this**, so it is no longer the example of a
    document we cannot read. `unreadable_invoice` below is, and the tests that need a
    genuine extraction failure use that instead.
    """
    return build_pdf(
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
        "Detention Days       3",
        "Per Day Charge       390.00",
        "Detention Total      1,170.00",
        "",
        "Total Due            USD 1,170.00",
        "Disputes: charges@maersk.example",
    )


def test_the_carrier_layout_is_now_read() -> None:
    """Issue 216 taught the binder to read columns. This is the record of that.

    Issue 214 asserted the opposite, that a carrier-shaped invoice yielded almost nothing,
    and it was right at the time. A document shaped like a real invoice now yields the
    labels the engine needs, which is the whole point of #216.
    """

    text = extract_text_layer(realistic_invoice())
    fields = read_fields(text.lines)
    assert len(fields.values) >= 10, (
        f"only {len(fields.values)} labels read from a carrier-shaped invoice"
    )


def unreadable_invoice() -> bytes:
    """A document in no layout this binder knows, so issue 214's guarantee has a subject.

    Prose and references, no field at all. This is what a forwarder statement looks like
    to the extractor, and the binder has to refuse it rather than accuse a carrier of
    withholding things it may well have stated.
    """
    return build_pdf(
        "FORWARDER STATEMENT OF ACCOUNT",
        "Reference 4471-B",
        "Please remit to the address below within the usual terms.",
        "Queries 020 7946 0000",
    )


def test_an_unreadable_field_is_not_reported_as_an_omission() -> None:
    """The shipping blocker, and the assertion that matters most in this file.

    Every line of the reference fixture is `Label: value`. A carrier invoice is not. On
    one, the binder raised `OmittedError` for 541.6(b)(4), which says in its own message
    that this is "a finding against the carrier, not an extraction fault". The document
    states the free time start, as `Free Time Commences`. We simply could not read it.

    That turns our extraction defect into an automatic 541.5 finding that eliminates the
    obligation to pay, on a compliant invoice, and the claim gets filed.
    """

    text = extract_text_layer(unreadable_invoice())
    with pytest.raises(UnreadableDocumentError) as caught:
        bind_ledger(text)

    message = str(caught.value)

    # Not "the word carrier is absent". The message does mention the carrier, to say it
    # is *not* at fault, and a guard that forbade the word would push the wording
    # towards vagueness rather than towards accuracy. What it must not do is assert the
    # carrier withheld anything.
    assert "does not state it" not in message, (
        "that is `OmittedError`'s phrasing and it asserts the carrier withheld the field"
    )
    assert "makes the omission automatic" not in message, (
        "an extraction failure must not claim the automatic consequence in 541.5"
    )
    assert "not a finding about the carrier" in message, (
        "the message should say plainly that this is our limitation and not a finding"
    )
    assert "read" in message.lower(), "the message should say we could not read it"


def test_an_extraction_failure_is_a_different_type_from_an_omission() -> None:
    """Two failures, two types. `OmittedError` means the carrier did not disclose.

    Collapsing them is what produced the bug, so the types must not be assignable to one
    another and a caller must be able to tell them apart without reading a string.
    """

    assert issubclass(UnreadableDocumentError, BindError)
    assert issubclass(OmittedError, BindError)
    assert not issubclass(UnreadableDocumentError, OmittedError)
    assert not issubclass(OmittedError, UnreadableDocumentError)


def test_the_extraction_failure_names_the_field_it_could_not_read() -> None:
    """The person holding the document has to know which line defeated us."""

    text = extract_text_layer(unreadable_invoice())
    with pytest.raises(UnreadableDocumentError) as caught:
        bind_ledger(text)
    assert caught.value.field
