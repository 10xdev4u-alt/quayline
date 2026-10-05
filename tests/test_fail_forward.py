"""Issue 222: an unreadable invoice must still be worth something to the person holding it.

Today an unreadable invoice is a dead end. The reader is told we could not read it and they
have nothing to act on, which is honest and useless.

What we can honestly hand back, without claiming anything we cannot support:

- **What we read**, verbatim, each labelled value with the line it came from.
- **The 541.6 checklist**, all twenty clauses, each marked found, not checked, or not
  applicable to the direction of trade.
- **A letter asking the carrier to supply the unverified disclosures**, by clause.

The framing is the whole constraint. Issue 214 closed the bug of accusing a carrier of
omitting a disclosure *we could not read*, so this letter alleges nothing. It requests, and
notes what 541.5 says about a missing one. A great many invoices genuinely are incomplete,
and asking is both true and useful where accusing would be neither.

These tests are mostly about what must NOT appear, because that is where the risk is.
"""

from __future__ import annotations

from conftest import build_pdf
from quayline.ingest.bind import bind_ledger
from quayline.ingest.fields import read_fields
from quayline.ingest.pdftext import extract_text_layer
from quayline.regulation.checklist import CHECKLIST
from quayline.regulation.deadline import DAYS as MITIGATION_DAYS
from quayline.web.failforward import fail_forward_page, request_letter, unread_report
from test_carrier_layout import MAERSK_COLUMNS

# A document in no layout we read. Real input looks like this more often than not.
UNREADABLE = (
    "FORWARDER STATEMENT OF ACCOUNT",
    "Reference 4471-B",
    "Settlement of charges for the month of August.",
    "Container MSKU1234567 remained at Newark beyond the free period.",
    "Please remit to the address below within the usual terms.",
    "Queries 020 7946 0000",
)


def _letter() -> str:
    text = extract_text_layer(build_pdf(*UNREADABLE))
    return request_letter(unread_report(text, read_fields(text.lines)))


# --- what we read -------------------------------------------------------------


def _fail_forward() -> str:
    """The page for the unreadable fixture."""
    text = extract_text_layer(build_pdf(*UNREADABLE))
    return fail_forward_page(text, read_fields(text.lines))


def test_the_page_shows_what_was_read_verbatim() -> None:
    """A reader handed a refusal needs to see that we did read their invoice.

    Not a summary. The line as it appears on the document, so they can check it.

    The fixture for this reads **nothing**, which is the honest common case for a document
    in a layout we do not know, so the assertion that matters is that the page says so
    rather than showing an empty list. A second fixture with one readable label proves the
    verbatim path.
    """
    page = _fail_forward()
    assert "FORWARDER STATEMENT OF ACCOUNT" in page, (
        "we read the text, so the page shows it. An empty list would tell the reader we "
        "got nothing, which is not true and hides the whole story of this page."
    )
    assert "None of it is laid out as a field" in page

    partial = build_pdf(
        "Reference: 4471-B",
        "Container: MSKU1234567",
        "Queries: 020 7946 0000",
    )
    text = extract_text_layer(partial)
    page = fail_forward_page(text, read_fields(text.lines))
    assert "Reference: 4471-B" in page, "a readable line must be quoted back verbatim"


def test_the_page_says_what_it_could_not_read() -> None:
    """Stated plainly, because that is the situation."""
    page = _fail_forward()
    assert "could not read" in page.lower() or "not a layout" in page.lower()


# --- the checklist -----------------------------------------------------------


def test_every_clause_of_the_twenty_is_listed() -> None:
    """All twenty, so a reader is not left wondering whether one was quietly dropped."""
    page = _fail_forward()
    for field in CHECKLIST:
        assert field.cite in page, f"{field.cite} is missing from the checklist"


def test_each_clause_is_marked_rather_than_left_blank() -> None:
    """A tick beside a clause we never looked at is a lie in a tick's clothing."""
    page = _fail_forward()
    assert "not checked" in page.lower()
    assert page.lower().count("not checked") >= 10, (
        "most clauses cannot be checked from an unreadable document, and the page has to "
        "say so rather than implying they were clear"
    )


# --- the letter --------------------------------------------------------------


def test_the_letter_requests_and_does_not_allege() -> None:
    """The distinction that issue 214 turned on, applied to prose.

    We could not read the document. So we may not say the carrier withheld anything.
    """
    text = extract_text_layer(build_pdf(*UNREADABLE))
    letter = request_letter(unread_report(text, read_fields(text.lines)))
    lowered = letter.lower()

    for accusation in ("withheld", "omitted", "failed to disclose", "did not disclose", "breach"):
        assert accusation not in lowered, (
            f"the letter says {accusation!r}, which alleges something about a carrier on a "
            f"document we could not read. That is issue 214's bug in prose."
        )


def test_the_letter_states_the_541_5_consequence_accurately() -> None:
    """Asking is only useful if the reader knows what asking is worth."""
    letter = _letter()
    assert "541.5" in letter
    assert "obligation to pay" in letter.lower()


def test_the_letter_names_the_mitigation_window() -> None:
    """A request outside the window is worthless, and the reader will not know that.

    `regulation/deadline.py` already holds the 30 days of 541.8(a), so this is read from
    there rather than typed into a template.
    """
    letter = _letter()
    assert str(MITIGATION_DAYS) in letter
    assert "541.8" in letter


def test_the_letter_asks_for_specific_clauses() -> None:
    """A general complaint can be ignored. A list of clause numbers cannot."""
    letter = _letter()
    assert "541.6(c)(2)" in letter, "the rate rule is the disclosure most worth asking for"
    assert "541.6(b)(1)" in letter


def test_the_letter_is_copyable_without_javascript() -> None:
    """A reader may have the script blocked, and then they are selecting by hand."""
    page = _fail_forward()
    assert "<textarea" in page, "the letter must be selectable even with no script"
    assert "readonly" in page


def test_a_readable_document_never_reaches_this_path() -> None:
    """The control. This page says we could not read the document, so it must be true."""
    text = extract_text_layer(build_pdf(*MAERSK_COLUMNS))
    # A readable document binds, which is what keeps this out of the request path.
    assert bind_ledger(text).rate_rule == "Maersk US Newark Dry"
