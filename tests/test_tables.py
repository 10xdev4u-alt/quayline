"""Issue 41: tables, because the money lives in rows and columns.

The load bearing test is ``test_line_item_f1_is_measured_on_the_fixture``. A
table path without a measured score is a path chosen on aesthetics, and the
evidence table in the issue shows line-item accuracy inverting field-accuracy
rankings across every vendor measured. The score is the selection criterion, so
the score is what gets asserted.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from quayline.ingest import tables as module
from quayline.ingest.pdftext import _content_streams
from quayline.ingest.tables import (
    COLUMN_GAP,
    ROW_TOLERANCE,
    Cell,
    LineItemScore,
    PlacedText,
    Table,
    place,
    score_lines,
    to_rows,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "charge_table.pdf"

EXPECTED_ITEMS = (
    ("MAEU1234567", "3", "100.00", "300.00"),
    ("TGHU7654321", "2", "100.00", "200.00"),
)


def placed() -> PlacedText:
    streams, _, _ = _content_streams(FIXTURE.read_bytes())
    return place(streams[0])


def table() -> Table:
    return to_rows(placed().cells)


# ---------------------------------------------------------------- criterion 4
# A fixture where the charge table sits below a summary header.


def test_the_fixture_has_a_header_above_a_table() -> None:
    rows = table().rows
    assert rows[0] == ("DEMURRAGE AND DETENTION INVOICE",)
    assert rows[1] == ("Invoice Date: 2026-07-20",)
    assert rows[2] == ("Container: MAEU1234567",)


def test_header_fields_do_not_leak_into_table_rows() -> None:
    """The layout that breaks naive readers. Header strings stay in single-cell
    rows and no table row contains header text."""
    rows = table().rows
    for row in rows[3:]:
        assert not any("Invoice Date" in c or "DEMURRAGE AND" in c for c in row)


def test_the_table_header_and_both_data_rows_read_correctly() -> None:
    rows = table().rows
    assert rows[3] == ("Container", "Days", "Rate", "Amount")
    assert rows[4] == EXPECTED_ITEMS[0]
    assert rows[5] == EXPECTED_ITEMS[1]


def test_the_total_row_is_separate_from_the_data() -> None:
    """TOTAL sits at the left column with its amount at the right. A reader that
    merged it into the last data row would double-count."""
    assert table().rows[6] == ("TOTAL", "500.00")


def test_every_cell_was_placed_with_no_undecodable_strings() -> None:
    assert placed().undecodable == 0
    assert len(placed().cells) == 17


# ---------------------------------------------------------------- criterion 2
# Line-item F1 measured on the fixture, not field accuracy.


def test_line_item_f1_is_measured_on_the_fixture() -> None:
    """Both line items found, which is recall 1. Precision is measured against
    every row the extractor produced, header included, because a score that
    pre-selects the data rows is a score that assumes what it claims to measure."""
    score = score_lines(EXPECTED_ITEMS, table())
    assert score.expected == 2
    assert score.matched == 2
    assert score.recall == Decimal(1)
    assert score.precision is not None and score.precision < 1
    assert score.f1 is not None


def test_recall_is_one_because_both_items_were_found() -> None:
    assert score_lines(EXPECTED_ITEMS, table()).recall == Decimal(1)


def test_a_missing_row_lowers_recall_not_precision() -> None:
    partial = (EXPECTED_ITEMS[0], ("MISSING", "1", "1.00", "1.00"))
    score = score_lines(partial, table())
    assert score.matched == 1
    assert score.recall == Decimal(1) / Decimal(2)


def test_duplicate_expected_rows_each_need_a_match() -> None:
    """A table printing one line twice has two line items. An extractor finding
    one of them is half right, not fully right."""
    doubled = (EXPECTED_ITEMS[0], EXPECTED_ITEMS[0])
    assert score_lines(doubled, table()).matched == 1


def test_empty_extraction_has_no_precision() -> None:
    """None rather than zero, because zero precision on nothing extracted would
    read as a measured failure rather than an absence of measurement."""
    score = score_lines(EXPECTED_ITEMS, to_rows(()))
    assert score.precision is None
    assert score.f1 is None


def test_no_expected_rows_has_no_recall() -> None:
    assert score_lines((), table()).recall is None


# ---------------------------------------------------------------- criterion 1
# A table-aware extraction path.


def test_positioning_comes_from_tm_operators() -> None:
    """The cells carry the coordinates the stream painted them at, which is what
    makes rows and columns recoverable."""
    cells = placed().cells
    assert all(isinstance(c, Cell) for c in cells)
    xs = {c.x for c in cells}
    assert len(xs) >= 4, "four column positions"


def test_rows_cluster_by_y_within_tolerance() -> None:
    assert ROW_TOLERANCE == 7.0
    rows = table().rows
    assert len(rows) == 7


def test_columns_split_on_gaps_not_on_every_cell() -> None:
    """A gap wider than COLUMN_GAP starts a column. Narrower gaps are kerning
    within one cell's text, and splitting on them would shred every row."""
    assert COLUMN_GAP == 25.0
    assert table().width == 4


def test_a_rotated_matrix_ends_placement_rather_than_misplacing() -> None:
    """Rotation makes x and y meaningless for rows and columns. Misplaced cells
    would silently corrupt the table, so the run ends instead."""
    stream = b"BT 0 1 -1 0 72 700 Tm (TURNED) Tj ET"
    assert place(stream).cells == ()


def test_short_operator_stacks_do_not_lose_the_string() -> None:
    """A Td with no operands is a no-op, and the Tj after it still paints at the
    current position. A malformed operator must not destroy the strings around it,
    which is the property that keeps one bad operator from losing a page."""
    stream = b"BT Td (ORPHAN) Tj ET"
    cells = place(stream).cells
    assert len(cells) == 1
    assert cells[0].text == "ORPHAN"


# ---------------------------------------------------------------- criterion 3
# Chosen on line-item score.


def test_the_score_is_a_row_metric_not_a_field_metric() -> None:
    """A row matches only when its cells equal the expected cells in order. Partial
    credit would be a field metric wearing a row's clothes, and field accuracy is
    what inverts the ranking this issue is about."""
    almost = (("MAEU1234567", "3", "100.00", "299.99"),)
    assert score_lines(almost, table()).matched == 0


def test_the_module_states_why_field_accuracy_is_the_wrong_ranking() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "inverting" in flat or "inverse" in flat
    assert "line-item" in flat


def test_issue_41_is_the_provenance() -> None:
    assert "Issue 41" in (module.__doc__ or "")


def test_the_score_type_is_immutable() -> None:
    score = score_lines(EXPECTED_ITEMS, table())
    assert isinstance(score, LineItemScore)
    with pytest.raises(AttributeError):
        score.matched = 0  # type: ignore[misc]
