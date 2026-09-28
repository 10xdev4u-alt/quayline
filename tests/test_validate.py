"""Issue 42: the checks that decide whether an extraction can be trusted."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from quayline.ingest.pdftext import extract_text_layer
from quayline.ingest.validate import Check, InvoiceLine, Ledger, Report, validate

M = Decimal("100.00")
START = date(2026, 6, 30)
END = date(2026, 7, 7)


def line(
    *,
    container: str = "MAEU1234567",
    bol: str = "MAEU123456789",
    days: int = 3,
    rate: Decimal = M,
    amount: Decimal = M * 3,
) -> InvoiceLine:

    return InvoiceLine(
        container_number=container, bol_number=bol, chargeable_days=days, rate=rate, amount=amount
    )


def good_ledger(**overrides: object) -> Ledger:
    fields: dict[str, Any] = {
        "lines": (line(), line(), line()),
        "stated_total": M * 9,
        "free_time_start": START,
        "free_time_end": END,
        "allowed_free_time_days": 7,
    }
    fields.update(overrides)
    return Ledger(**fields)


def by_name(report: Report, name: str) -> Check:
    return next(c for c in report.checks if c.name == name)


# ---------------------------------------------------------------- a clean invoice


def test_a_consistent_invoice_passes_everything() -> None:
    report = validate(good_ledger())
    assert report.can_file is True
    assert report.failures == ()
    assert report.reason_not_filed() == ""


def test_every_check_carries_a_citation() -> None:
    """A finding the other side cannot check the authority for is an opinion."""
    for check in validate(good_ledger()).checks:
        assert check.cite, check.name
        for part in check.cite.split(", "):
            assert re.match(r"^541\.\d", part), (check.name, part)
        assert check.cite


# ---------------------------------------------------------------- criterion 1
# The invoice total equals the sum of its lines.


def test_a_total_that_exceeds_the_sum_of_its_lines_is_caught() -> None:
    report = validate(good_ledger(stated_total=M * 12))
    check = by_name(report, "line_sum")
    assert check.passed is False
    assert "900.00" in check.detail and "1200.00" in check.detail


def test_a_total_that_understates_the_sum_is_also_caught() -> None:
    assert by_name(validate(good_ledger(stated_total=M * 6)), "line_sum").passed is False


def test_an_invoice_with_no_lines_cannot_balance() -> None:
    report = validate(good_ledger(lines=(), stated_total=M * 9))
    assert by_name(report, "line_sum").passed is False
    assert by_name(report, "identifiers_present").passed is True, "no lines, no missing ids"


def test_a_decimal_difference_of_one_cent_is_still_a_failure() -> None:
    """The reason this module does not use the two percent band.

    A cent is not a dispute worth a letter. It is a misparsed digit, and if a
    tolerance swallowed it then the single most expensive error in the pipeline
    would pass validation and be filed as fact.
    """
    report = validate(good_ledger(stated_total=M * 9 + Decimal("0.01")))
    assert by_name(report, "line_sum").passed is False


# ---------------------------------------------------------------- criterion 2
# Free-time start plus allowed days equals the stated end.


def test_a_free_time_window_that_does_not_add_up_is_caught() -> None:
    report = validate(good_ledger(allowed_free_time_days=4))
    check = by_name(report, "free_time_window")
    assert check.passed is False
    assert "2026-07-04" in check.detail
    assert "2026-07-07" in check.detail


def test_the_window_uses_the_carriers_own_three_disclosures() -> None:
    """It compares the carrier against itself. We never supply a date here."""
    shifted = validate(good_ledger(free_time_start=date(2026, 7, 1), free_time_end=END))
    assert by_name(shifted, "free_time_window").passed is False


def test_the_window_holds_when_the_three_agree() -> None:
    report = validate(good_ledger(allowed_free_time_days=7))
    assert by_name(report, "free_time_window").passed is True


# ---------------------------------------------------------------- criterion 3
# Chargeable days times rate equals the stated amount.


def test_a_line_whose_arithmetic_does_not_multiply_out_is_caught() -> None:
    report = validate(
        good_ledger(lines=(line(), line(days=3, amount=M * 3 + M), line()), stated_total=M * 10)
    )
    check = by_name(report, "charge_arithmetic")
    assert check.passed is False
    assert "line 2" in check.detail
    assert "MAEU1234567" in check.detail
    assert "300.00" in check.detail and "400.00" in check.detail


def test_a_wrong_rate_is_caught_and_the_stated_amount_is_kept() -> None:
    """The finding is the disagreement, so neither side of it may be discarded."""
    bad = line(days=2, rate=Decimal("150.00"), amount=M * 2)
    report = validate(good_ledger(lines=(bad,), stated_total=M * 2))
    check = by_name(report, "charge_arithmetic")
    assert check.passed is False
    assert "150.00" in check.detail and "200.00" in check.detail


def test_a_free_time_extension_is_allowed_to_multiply_out() -> None:
    """Not every non-standard line is an error, only every non-multiplying one."""
    extended = line(days=3, rate=M, amount=M * 3)
    assert by_name(validate(good_ledger(lines=(extended,))), "charge_arithmetic").passed is True


# ---------------------------------------------------------------- criterion 4
# A container and a bill of lading on every line.


def test_a_line_with_no_container_is_caught() -> None:
    report = validate(good_ledger(lines=(line(), line(container=""), line())))
    check = by_name(report, "identifiers_present")
    assert check.passed is False
    assert "line 2" in check.detail


def test_a_line_with_no_bill_of_lading_is_caught() -> None:
    report = validate(good_ledger(lines=(line(), line(bol=""), line())))
    check = by_name(report, "identifiers_present")
    assert check.passed is False
    assert "bill of lading" in check.detail


def test_a_line_with_neither_identifier_names_both() -> None:
    report = validate(good_ledger(lines=(line(container="", bol=""),)))
    detail = by_name(report, "identifiers_present").detail
    assert "both identifiers" in detail


# ---------------------------------------------------------------- criterion 5
# A validation failure blocks filing, with the failure named.


def test_any_failure_blocks_filing() -> None:
    report = validate(good_ledger(stated_total=M * 12))
    assert report.can_file is False
    assert report.failures


def test_a_single_failure_blocks_filing() -> None:
    report = validate(good_ledger(allowed_free_time_days=4))
    assert report.can_file is False
    assert len(report.failures) == 1


def test_the_blocking_failure_is_named_with_numbers() -> None:
    """A carrier told 'validation failed' learns nothing and can answer nothing."""
    reason = validate(good_ledger(stated_total=M * 12, allowed_free_time_days=4)).reason_not_filed()
    assert "line_sum" in reason
    assert "free_time_window" in reason
    assert "1200.00" in reason
    assert "900.00" in reason


def test_can_file_is_one_property_that_cannot_be_reshaped() -> None:
    """No flags, no severity, no 'warnings'. Either we file or we do not."""
    report = validate(good_ledger())
    assert isinstance(report.can_file, bool)
    assert "can_file" in dir(report)
    assert not hasattr(report, "should_file")
    assert not hasattr(report, "warnings")


def test_failures_are_the_inverse_of_can_file() -> None:
    for ledger in (good_ledger(), good_ledger(stated_total=M * 12), good_ledger(lines=())):
        report = validate(ledger)
        assert report.can_file is (not report.failures)


# ---------------------------------------------------------------- the shipped fixture


def test_the_issue_40_fixture_is_internally_inconsistent() -> None:
    """The reason the fixture's free time was corrected to seven days.

    born_digital_invoice.pdf shipped in issue 40 stating four days of free time
    from 2026-06-30 with an end date of 2026-07-07. Four days from the thirtieth
    of June is the fourth of July, so the three disclosures disagreed with each
    other and the invoice could not have been issued by anyone.

    Issue 40's parser was character perfect and never noticed, because a parser has
    no opinion about whether a document makes sense. This module does, and it is
    the reason the module exists. The fixture now states seven days, which makes
    the window close exactly.
    """

    fixture = (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "born_digital_invoice.pdf"
    )
    assert "Allowed Free Time: 7 days" in extract_text_layer(fixture.read_bytes()).text
    start = date.fromisoformat("2026-06-30")
    end = date.fromisoformat("2026-07-07")
    assert (end - start).days == 7, "the fixture must state a window that closes exactly"
    ledger = good_ledger(
        free_time_start=start, free_time_end=end, allowed_free_time_days=(end - start).days
    )
    assert validate(ledger).can_file is True


def test_the_original_four_day_wording_is_detected_when_it_reappears() -> None:
    """The regression, pinned. Four days from the thirtieth is the fourth."""
    report = validate(good_ledger(allowed_free_time_days=4))
    assert by_name(report, "free_time_window").passed is False


# ---------------------------------------------------------------- determinism


def test_validation_is_deterministic_and_side_effect_free() -> None:
    ledger = good_ledger(stated_total=M * 12)
    first = validate(ledger)
    second = validate(ledger)
    assert first == second
    assert validate(good_ledger(stated_total=M * 12)) == first


@pytest.mark.parametrize("days", [-1, -7])
def test_a_negative_day_count_is_rejected_at_construction(days: int) -> None:
    """An extraction error, not a carrier dispute, so it raises rather than fails."""
    with pytest.raises(ValueError, match="extraction error"):
        line(days=days)
