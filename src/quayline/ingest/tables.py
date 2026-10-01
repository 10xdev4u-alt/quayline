"""Issue 41: tables, because the money lives in rows and columns.

A D&D invoice has a summary header and a charge table. Generic parsers are
measured worst at line items, which is exactly our shape: the evidence table in
the issue puts line-item accuracy inverse to field accuracy across every vendor
measured. A parser chosen on field accuracy is a parser chosen to fail at the
thing we need most.

So the table path is chosen on line-item score, measured on a fixture corpus, and
the measurement is in this module rather than in a vendor comparison doc. The
corpus fixture carries a summary header above a charge table, because that is the
layout that breaks naive readers: header fields leak into rows, row cells merge
into the header, and a reader that cannot tell the two apart prices neither.

How positions are read

A content stream is a sequence of positioning operators and string operands.
`Td` moves the text position by an offset, `Tm` sets it absolutely, `T*` moves to
the next line, and `Tj`/`TJ` paint a string where the position stands. This module
tokenizes the stream and walks it, emitting a `Cell` per painted string with its
(x, y) in text space.

What is tracked and what is deliberately not

Tracked: `BT`/`ET` boundaries, `Tm`, `Td`, `TD`, `T*`, `Tj`, `TJ`, and the
`Tf`/`Tl` state needed to make `T*` correct. Not tracked: `Tw`/`Tc` spacing
adjustments, `Ts` rise, horizontal scaling, rotated text matrices, and marked
content. A fixture exercising those would need a typesetter rather than a test
author, and a reader that silently mismeasures them is worse than one that says
it does not handle them. Rotation in particular produces cells whose x and y mean
nothing, so a non-axis-aligned `Tm` ends the row rather than placing it.

Rows and columns

Cells sharing a y within `ROW_TOLERANCE` points are one row. Within a row, cells
sorted by x are columns in order, with no attempt to name the columns: naming is
the binder's job in a later issue, and this module's job ends at geometry. A row
with one cell is a header line or a note, not a table row, and the caller decides
which by position rather than by this module guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from quayline.ingest import pdftext as _text

#: Two strings within this many points vertically are the same row. Set from the
#: fixture's 14-point leading with room for rounding: half the leading would merge
#: nothing real and double it would merge adjacent rows.
ROW_TOLERANCE = 7.0

#: An x gap wider than this many points starts a new column. Narrower gaps are
#: kerning and word spacing within one cell's text.
COLUMN_GAP = 25.0

#: Leading used when none was set. PDF default leading for a 12-point font step.
_DEFAULT_LEADING = 12.0
_MATRIX_ARGS = 6
_OFFSET_ARGS = 2

_TOKEN = re.compile(
    rb"(?P<string>\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>)"
    rb"|(?P<number>[+-]?(?:\d+\.?\d*|\.\d+))"
    rb"|(?P<name>/[^\s<>\[\]()/%]+)"
    rb"|(?P<op>[A-Za-z'\"]+)"
)


@dataclass(frozen=True, slots=True)
class Cell:
    """One painted string, where it was painted."""

    x: float
    y: float
    text: str


@dataclass(frozen=True, slots=True)
class PlacedText:
    """Everything one content stream painted, in stream order."""

    cells: tuple[Cell, ...]
    undecodable: int = 0


def _number(token: bytes) -> float:
    try:
        return float(token)
    except ValueError:
        return 0.0


class _Placer:
    """The text-position state for one content stream walk.

    Extracted from `place` so the operator dispatch is methods on state rather
    than branches over locals. Each handler is small enough to read whole, and a
    new operator is a new method rather than another branch in a function that
    already has too many.
    """

    def __init__(self) -> None:
        self.cells: list[Cell] = []
        self.dropped = 0
        self.x = 0.0
        self.y = 0.0
        self.leading = 0.0
        self.in_text = False

    def show(self, raws: list[bytes]) -> None:
        for raw in raws:
            text, ok = _text._decode_string(raw)
            if not ok:
                self.dropped += 1
                continue
            text = text.strip()
            if text:
                self.cells.append(Cell(x=self.x, y=self.y, text=text))

    def _line_feed(self) -> None:
        self.y -= self.leading if self.leading else _DEFAULT_LEADING
        self.x = 0.0

    def move(self, op: str, args: list[bytes]) -> None:
        """Positioning operators. Short stacks are no-ops."""
        if op == "BT":
            self.in_text = True
            self.x, self.y = 0.0, 0.0
        elif op == "ET":
            self.in_text = False
        elif not self.in_text:
            return
        elif op == "Tm":
            self._matrix(args)
        elif op == "Td":
            if len(args) >= _OFFSET_ARGS:
                self.x += _number(args[-2])
                self.y += _number(args[-1])
        elif op == "TD":
            if len(args) >= _OFFSET_ARGS:
                tx, ty = _number(args[-2]), _number(args[-1])
                self.leading = -ty
                self.x += tx
                self.y += ty
        elif op == "T*":
            self._line_feed()
        elif op == "Tl":
            if args:
                self.leading = _number(args[-1])

    def _matrix(self, args: list[bytes]) -> None:
        if len(args) < _MATRIX_ARGS:
            return
        a, b, c, d, e, f = (_number(v) for v in args[-6:])
        # Axis-aligned only. A rotated matrix places text where x and y stop
        # meaning columns and rows, so it ends placement for this run rather
        # than misplacing it.
        if b == 0 and c == 0 and a > 0 and d > 0:
            self.x, self.y = e, f
        else:
            self.in_text = False

    def paint(self, op: str, operands: list[bytes]) -> None:
        """Text-showing operators."""
        if not self.in_text:
            return
        if op == "Tj":
            self.show(operands[-1:])
        elif op == "TJ":
            self.show(operands)
        elif op in {"'", '"'}:
            self._line_feed()
            self.show(operands[-1:])


def place(stream: bytes) -> PlacedText:
    """Walk one content stream, emitting a cell per painted string.

    A small state machine over the token sequence. Operands accumulate on a stack
    and operators consume them, which is how PDF works and also how every
    implementation of it goes wrong when an operator arrives with a short stack.
    Short stacks are skipped rather than raised on, because a content stream with
    one malformed operator still contains every other string on the page.
    """
    placer = _Placer()
    stack: list[bytes] = []
    strings: list[bytes] = []

    for match in _TOKEN.finditer(stream):
        kind = match.lastgroup
        token = match.group(0)
        if kind == "string":
            strings.append(token)
            continue
        if kind in {"number", "name"}:
            stack.append(token)
            continue
        # operators below; strings collected since the last operator belong to it
        op = token.decode("latin-1")
        args, stack = stack, []
        operands, strings = strings, []
        if op in {"BT", "ET", "Tm", "Td", "TD", "T*", "Tl"}:
            placer.move(op, args)
        else:
            placer.paint(op, operands)

    return PlacedText(cells=tuple(placer.cells), undecodable=placer.dropped)


@dataclass(frozen=True, slots=True)
class Table:
    """Rows of cells, in reading order. Columns are positional, not named."""

    rows: tuple[tuple[str, ...], ...]

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int:
        return max((len(r) for r in self.rows), default=0)


def to_rows(cells: tuple[Cell, ...]) -> Table:
    """Cluster cells into rows by y, order columns by x.

    Rows first, because a row is a fact about the page and a column is a fact
    about a row. Within a row, cells join left to right with a gap wider than
    `COLUMN_GAP` starting a new column. Single-cell rows pass through unchanged:
    they are header lines or notes, and deciding which is the caller's job.
    """
    if not cells:
        return Table(rows=())
    ordered = sorted(cells, key=lambda c: (-c.y, c.x))
    rows: list[list[Cell]] = [[ordered[0]]]
    for cell in ordered[1:]:
        if abs(cell.y - rows[-1][0].y) <= ROW_TOLERANCE:
            rows[-1].append(cell)
        else:
            rows.append([cell])
    table: list[tuple[str, ...]] = []
    for row in rows:
        row.sort(key=lambda c: c.x)
        cols: list[str] = [row[0].text]
        for prev, cell in pairwise(row):
            if cell.x - (prev.x + len(prev.text) * 5.0) > COLUMN_GAP:
                cols.append(cell.text)
            else:
                cols[-1] = f"{cols[-1]} {cell.text}"
        table.append(tuple(cols))
    return Table(rows=tuple(table))


@dataclass(frozen=True, slots=True)
class LineItemScore:
    """Line-item precision, recall and F1 against expected rows.

    Measured on rows, not fields, because field accuracy and line-item accuracy
    invert across vendors and the ranking that matters is the line-item one. A row
    matches when its cells equal the expected cells in order; partial credit is a
    field metric wearing a row's clothes.
    """

    expected: int
    matched: int
    extracted: int

    @property
    def precision(self) -> Decimal | None:
        if not self.extracted:
            return None
        return Decimal(self.matched) / Decimal(self.extracted)

    @property
    def recall(self) -> Decimal | None:
        if not self.expected:
            return None
        return Decimal(self.matched) / Decimal(self.expected)

    @property
    def f1(self) -> Decimal | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


def score_lines(expected: tuple[tuple[str, ...], ...], got: Table) -> LineItemScore:
    """Score an extracted table against expected rows.

    Set comparison on rows, so order between rows does not matter but content
    does. Duplicate expected rows each need a distinct extracted match, because a
    table that prints one line twice has two line items and an extractor that
    finds one of them is half right.
    """
    remaining = list(got.rows)
    matched = 0
    for row in expected:
        if row in remaining:
            remaining.remove(row)
            matched += 1
    return LineItemScore(expected=len(expected), matched=matched, extracted=len(got.rows))


__all__ = [
    "COLUMN_GAP",
    "ROW_TOLERANCE",
    "Cell",
    "LineItemScore",
    "PlacedText",
    "Table",
    "place",
    "score_lines",
    "to_rows",
]
