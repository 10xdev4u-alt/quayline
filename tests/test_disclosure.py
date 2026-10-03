"""Issue 207: the 541.6 disclosure check, run on the document.

`regulation/checklist.py` has carried all twenty required disclosures since issue 1.
`regulation/kill_switch.py` has carried 541.5. Nothing ran them.

    grep -c "CHECKLIST\\|required_for\\|by_cite" src/quayline/engine/audit.py
    0

That left two failures. A missing disclosure crashed the audit, because the only
fields checked were the six the ledger cannot be built without. And a document that
was missing something the regulation requires produced no finding, when 541.5 makes
that finding automatic: no cure period, no showing of prejudice.

What is checked, and what is not

A disclosure can only be found absent if the extractor could see it. Thirteen of the
twenty are reachable from a bound ledger: twelve labelled disclosures plus the rate,
which is per line. Seven are not, and no test below claims one of them is checked. The uncheckable ones are returned by `unchecked()` so a caller can
report coverage honestly instead of implying the checklist ran clean.

The tests that matter most are the ones about a field that is *not* claimed missing.
`test_contact_information_is_never_claimed_omitted` and its neighbours are the tests
that stop this becoming a machine for accusing carriers of things.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from quayline.engine.disclosure import (
    _LEDGER_RATE_CITE,
    VERIFIABLE,
    check_disclosures,
    determine_trade,
    find_omissions,
    unchecked,
)
from quayline.ingest.bind import BoundLedger, bind_ledger
from quayline.ingest.fields import Fields, read_fields
from quayline.ingest.pdftext import TextLayer, TextLayerStatus, extract_text_layer
from quayline.regulation.checklist import CHECKLIST, Trade
from quayline.regulation.kill_switch import Obligation, effect_of

FIXTURE = Path(__file__).parent / "fixtures" / "born_digital_invoice.pdf"


def _layer() -> TextLayer:
    return extract_text_layer(FIXTURE.read_bytes())


def _ledger() -> BoundLedger:
    return bind_ledger(_layer())


def _fields(extra: dict[str, str] | None = None) -> Fields:
    """The fixture's labelled values, optionally with one more added.

    Injected labels are lowercased the way ``read_fields`` lowercases real ones.

    Without that, ``_fields({"Port of Discharge": ...})`` put a capitalised key into a
    dict whose keys are all lowercased, so the label lookup missed and the test for "a
    stated port is not an omission" passed for the wrong reason. It was asserting that a
    port the carrier wrote down still counted as omitted, which is the opposite of what
    it claimed.
    """
    base = read_fields(_layer().lines)
    if not extra:
        return base
    merged = {**base.values, **{label.lower(): value for label, value in extra.items()}}
    return Fields(values=merged, line_of=base.line_of)


def _ledger_without(*labels: str) -> tuple[BoundLedger, Fields]:
    """Bind the fixture with lines mentioning ``labels`` removed.

    Stripping a label from ``Fields`` is not the same as removing the disclosure: the
    ledger was bound from the whole text and would still prove the field. So the lines
    go too, and the binder has to reach the same conclusion from what is left.
    """
    real = _layer()
    kept = tuple(
        line for line in real.lines if not any(label.lower() in line.lower() for label in labels)
    )
    layer = TextLayer(
        status=real.status,
        lines=kept,
        streams_decoded=real.streams_decoded,
        undecodable_strings=real.undecodable_strings,
    )
    return bind_ledger(layer), read_fields(kept)


# --- What the fixture actually says -----------------------------------------


def test_fixture_states_the_invoice_date() -> None:
    """The baseline. Without this the other tests prove nothing about the omission."""
    assert _ledger().invoice_date is not None


def test_fixture_omits_the_invoice_due_date_and_the_port() -> None:
    """541.6(b)(2) and 541.6(a)(3), and it is the whole point of #207.

    The fixture states thirteen labelled fields including the invoice date, the free
    time window, the charged dates, the rate rule, the rate and the total. It states no
    due date and no port of discharge.

    So the reference document in this repository, the one the day count, the
    recomputation and the letter are all tested against, is non-compliant in two places.
    That is not a defect in the fixture. It is the finding, on a real document, with a
    real number attached.
    """
    omissions = find_omissions(_ledger(), _fields(), complete=True)
    assert {o.cite for o in omissions} == {"541.6(b)(2)", "541.6(a)(3)"}


def test_the_due_date_omission_eliminates_the_obligation() -> None:
    """541.5 is disjunctive. One omission is the whole remedy."""
    omissions = find_omissions(_ledger(), _fields(), complete=True)
    assert effect_of(omissions) is Obligation.ELIMINATED


def test_the_omission_names_the_clause_and_the_statement() -> None:
    omissions = find_omissions(_ledger(), _fields(), complete=True)
    assert "541.6(b)(2)" in omissions[0].describe()
    assert "due date" in omissions[0].describe().lower()


def test_a_complete_invoice_is_intact() -> None:
    """Zero omissions on a document that complies is the case that keeps the check honest."""
    # Add both missing labels, so the document complies.
    full = _fields({"due date": "2026-08-19", "Port of Discharge": "Newark, NJ"})
    assert find_omissions(_ledger(), full, complete=True) == ()
    assert effect_of(()) is Obligation.INTACT


# --- The fields this must never claim ---------------------------------------


@pytest.mark.parametrize(
    "cite",
    ["541.6(d)(1)", "541.6(d)(2)", "541.6(d)(3)", "541.6(e)(1)", "541.6(e)(2)"],
)
def test_unextractable_disclosures_are_never_claimed_omitted(cite: str) -> None:
    """The test that stops this becoming an accusation machine.

    The basis for the billed party, the dispute contact, the digital means, the
    timeframes and both certifications cannot be detected as absent. The fixture states
    none of them. If this check claimed them, it would assert a carrier withheld five
    things we never looked for, and 541.5 would fire on a fabrication.

    They are reported by `unchecked()` with a reason each, so the caller is not left
    claiming compliance on clauses nobody looked at.
    """
    omissions = find_omissions(_ledger(), _fields(), complete=True)
    assert cite not in {o.cite for o in omissions}
    assert cite in {u.cite for u in unchecked()}


def test_the_port_of_discharge_is_scoped_to_imports() -> None:
    """541.6(a)(3) is import only. On an export invoice there is no discharge port, so
    demanding one would fabricate a ground rather than find an omission."""
    for trade in (Trade.IMPORT, Trade.EXPORT):
        omissions = find_omissions(_ledger(), _fields(), complete=True, trade=trade)
        found = "541.6(a)(3)" in {o.cite for o in omissions}
        assert found is (trade is Trade.IMPORT), f"wrong for {trade}"


# --- Incomplete documents ----------------------------------------------------


def _damaged(
    status: TextLayerStatus | None = None,
    lines: tuple[str, ...] | None = None,
    undecodable_strings: int = 7,
) -> TextLayer:
    """The fixture's text layer, made incomplete in one specific way.

    A `**kwargs` version of this was untyped and mypy rejected every call, which is the
    third time in this repository that a convenience helper cost more than it saved.
    """
    real = _layer()
    return TextLayer(
        status=real.status if status is None else status,
        lines=real.lines if lines is None else lines,
        streams_decoded=real.streams_decoded,
        undecodable_strings=undecodable_strings,
    )


def test_an_incomplete_text_layer_raises_no_omissions() -> None:
    """The safety rule, and the reason `TextLayer.complete` exists.

    A document that decoded but dropped strings is readable and not complete. A field
    may be absent because we could not read it. Claiming a 541.5 omission on the
    strength of our own extraction defect is the most expensive error available in this
    pipeline, because the remedy is automatic and the accusation is false.
    """
    damaged = _damaged()
    assert damaged.complete is False
    result = check_disclosures(_ledger(), damaged)
    assert result.omissions == ()
    assert result.obligation is Obligation.INTACT
    assert result.complete is False


def test_the_same_document_is_intact_when_complete() -> None:
    """The control. Identical lines, no dropped strings, and the omission appears.

    Without this the test above could pass because the check does nothing at all.
    """
    intact = _damaged(undecodable_strings=0)
    assert intact.complete is True
    assert check_disclosures(_ledger(), intact).omissions != ()


def test_an_unreadable_document_raises_no_omissions() -> None:
    absent = _damaged(status=TextLayerStatus.ABSENT, lines=())
    result = check_disclosures(_ledger(), absent)
    assert result.omissions == ()
    assert result.obligation is Obligation.INTACT


def test_incompleteness_is_reported_rather_than_hidden() -> None:
    """When we decline to check, we say so. Silence would read as a clean invoice."""
    result = check_disclosures(_ledger(), _damaged(undecodable_strings=2))
    assert result.omissions == ()
    assert any("incomplete" in w.lower() for w in result.warnings)


def test_the_unverified_fields_are_reported_on_every_result() -> None:
    """A caller that reports zero omissions without these has claimed the invoice
    complies on six clauses nobody looked at."""
    result = check_disclosures(_ledger(), _layer())
    assert result.unverified == unchecked()
    assert len(result.unverified) == 6


# --- Why each clause is unchecked, issue 212 ---------------------------------


def test_every_unchecked_clause_carries_a_reason() -> None:
    """A bare list reads as a roadmap. Issue 212 exists because it was one.

    "We did not get to it" and "doing it would accuse a carrier that complied" are
    different states, and a caller reporting coverage has to be able to tell them apart.
    """
    for entry in unchecked():
        assert entry.reason, f"{entry.cite} is unchecked with no reason given"


def test_the_reason_quotes_the_words_that_make_it_unsafe() -> None:
    """Each reason has to be checkable against the regulation, or it is an opinion.

    The three that look checkable and are not all hinge on a word like "or": a clause
    that permits an alternative we cannot see cannot have its absence established.
    """
    reasons = {u.cite: u.reason.lower() for u in unchecked()}

    # 541.6(d)(1) permits "or other appropriate contact information".
    assert "or other appropriate contact" in reasons["541.6(d)(1)"]

    # 541.6(d)(2) permits "a URL address, QR code, or digital watermark", and a QR code
    # does not appear in a text layer. This is the sharpest one in the set.
    assert "qr code" in reasons["541.6(d)(2)"]
    assert "text layer" in reasons["541.6(d)(2)"]


def test_the_port_of_discharge_is_checked_now() -> None:
    """541.6(a)(3) is a fact on the document, so absence is detectable. Issue 212."""
    assert "541.6(a)(3)" in {v.cite for v in VERIFIABLE}
    assert "541.6(a)(3)" not in {u.cite for u in unchecked()}


def test_a_missing_port_of_discharge_is_an_omission_on_an_import() -> None:
    """The control for the test above, and the reason the label exists.

    The fixture states no port, so removing nothing and scoping to import finds it. That
    is a false-negative-friendly check: it only fires on a stated label, so it can miss a
    port the carrier disclosed in some other layout, which loses an argument. It cannot
    claim an omission where the carrier wrote the port down.
    """
    omissions = find_omissions(_ledger(), _fields(), complete=True, trade=Trade.IMPORT)
    assert "541.6(a)(3)" in {o.cite for o in omissions}


def test_a_stated_port_of_discharge_is_not_an_omission() -> None:
    """And it can pass, which is what stops it being a check that only ever fires."""
    omissions = find_omissions(
        _ledger(),
        _fields({"Port of Discharge": "Newark, NJ"}),
        complete=True,
        trade=Trade.IMPORT,
    )
    assert "541.6(a)(3)" not in {o.cite for o in omissions}


def test_an_export_invoice_owes_no_port_of_discharge() -> None:
    """541.6(a)(3) is import only. Demanding it on an export is a fabricated ground."""
    omissions = find_omissions(_ledger(), _fields(), complete=True, trade=Trade.EXPORT)
    assert "541.6(a)(3)" not in {o.cite for o in omissions}


def test_the_unchecked_reason_is_not_empty_for_every_clause() -> None:
    """Every reason must be a sentence, not a placeholder that shipped."""
    for entry in unchecked():
        assert len(entry.reason) > 40, f"{entry.cite} has a reason too short to check"
        assert entry.reason.endswith("."), f"{entry.cite} reason is not a sentence"


def test_the_checked_and_unchecked_sets_partition_the_checklist() -> None:
    """Every one of the twenty is in exactly one set, so nothing is silently lost."""
    checked = {v.cite for v in VERIFIABLE} | {_LEDGER_RATE_CITE}
    reported = {u.cite for u in unchecked()}
    assert not checked & reported
    assert checked | reported == {f.cite for f in CHECKLIST}
    assert len(checked) + len(reported) == 20


# --- Trade scoping ----------------------------------------------------------


def test_trade_is_determined_by_the_availability_date() -> None:
    """The availability date is import only, 541.6(b)(6), so it settles the direction."""
    assert determine_trade(_ledger()) is Trade.IMPORT


def test_export_trade_does_not_demand_the_availability_date() -> None:
    """Over demanding is a fabricated ground, and `required_for` exists to prevent it.

    Scoped to export, 541.6(b)(6) drops out and 541.6(b)(7) comes in. The fixture is an
    import document and states no earliest return date, so the export reading finds two
    omissions rather than the one the import reading finds. Both readings are correct
    for the trade they describe, which is the whole reason neither is a default.
    """
    omissions = find_omissions(_ledger(), _fields(), complete=True, trade=Trade.EXPORT)
    found = {o.cite for o in omissions}
    assert "541.6(b)(6)" not in found, "an export invoice owes no availability date"
    assert "541.6(b)(7)" in found, "an export invoice owes the earliest return date"


def test_import_trade_demands_the_availability_date() -> None:
    """The fixture states it. Remove the line and it becomes an omission."""
    ledger, fields = _ledger_without("availability")
    assert ledger.availability_date is None
    omissions = find_omissions(ledger, fields, complete=True, trade=Trade.IMPORT)
    assert "541.6(b)(6)" in {o.cite for o in omissions}


def test_the_fixture_states_the_availability_date() -> None:
    """The control for the test above. Without it, that test could pass for free."""
    assert _ledger().availability_date is not None


def test_unknown_trade_checks_only_the_directional_free_fields() -> None:
    """No signal means we do not know the direction.

    Neither direction is a safe default: demanding an import field on an export
    invoice fabricates a ground, and scoping to export on an import invoice hides one.
    So an undetermined trade checks everything except the directional fields, and says
    that it did not scope.
    """
    ledger, fields = _ledger_without("availability")
    assert determine_trade(ledger) is None
    omissions = find_omissions(ledger, fields, complete=True)
    found = {o.cite for o in omissions}
    assert "541.6(b)(2)" in found
    assert "541.6(b)(6)" not in found, "an unscoped check must not demand a directional field"
    assert "541.6(b)(7)" not in found


# --- The money consequence ---------------------------------------------------


def test_the_variance_is_untouched_by_the_check() -> None:
    """A 541.5 finding and a variance are different remedies and both stand.

    541.5 needs no arithmetic. The variance needs the recomputation. An omission does
    not make the variance wrong and the variance does not excuse the omission, so the
    check reads the ledger and never touches the money.
    """
    ledger = _ledger()
    assert ledger.stated_total == Decimal("1170.00")
