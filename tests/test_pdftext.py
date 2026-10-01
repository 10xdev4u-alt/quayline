"""Issue 40: the text layer is the default path, and the parser says so honestly.

The load bearing tests here are the two cross checks against poppler. A parser
tested only against its own output proves it is self consistent, which is a much
weaker claim, and it is how a paren bug survived long enough to be found by a
reference implementation rather than by me.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

from quayline.ingest.pdftext import TextLayer, TextLayerStatus, extract_text_layer

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "born_digital_invoice.pdf"
HAS_POPPLER = shutil.which("pdftotext") is not None
HAS_QPDF = shutil.which("qpdf") is not None


# ---------------------------------------------------------------- pdf builders


def _pdf(content: bytes, *, flate: bool = False) -> bytes:
    """A minimal but genuinely valid PDF with one content stream.

    Hand built so there is no dependency in the test path either. The newline
    before endstream is not optional, which is something the first version of
    these tests got wrong three separate ways.
    """
    payload = zlib.compress(content) if flate else content
    extra = b"/Filter /FlateDecode " if flate else b""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< "
        + extra
        + b"/Length "
        + str(len(payload)).encode()
        + b" >>\nstream\n"
        + payload
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


# ---------------------------------------------------------------- the fixture


def test_the_fixture_is_a_real_pdf() -> None:
    data = fixture_bytes()
    assert data.startswith(b"%PDF")
    assert data.rstrip().endswith(b"%%EOF")
    assert b"trailer" in data and b"startxref" in data


def test_the_fixture_carries_the_disclosures_the_engine_needs() -> None:
    """Field names taken from 541.6(b) itself, so a field binder is written against
    the clause rather than against our abbreviations."""
    text = extract_text_layer(fixture_bytes()).text
    for label in (
        "Invoice Date:",
        "Container Availability Date:",
        "Allowed Free Time:",
        "Start Date of Free Time:",
        "End Date of Free Time:",
        "Container Number:",
        "Bill of Lading Number:",
        "Charged Dates:",
    ):
        assert label in text, label


# ---------------------------------------------------------------- criterion 1
# A text-layer parse path exists and is the default.


def test_a_born_digital_fixture_parses_with_no_ocr_in_the_path() -> None:
    """No OCR, no third party library, no network. stdlib and a byte stream."""
    layer = extract_text_layer(fixture_bytes())
    assert layer.status is TextLayerStatus.READABLE
    assert layer.needs_fallback is False
    assert len(layer.lines) == 14
    assert "DEMURRAGE AND DETENTION INVOICE" in layer.text


def test_a_flate_compressed_stream_reads_the_same_way() -> None:
    """The only compression a born digital carrier invoice uses."""
    layer = extract_text_layer(
        _pdf(b"BT\n/F1 10 Tf\n72 700 Td\n(COMPRESSED FIXTURE LINE) Tj\nET\n", flate=True)
    )
    assert layer.status is TextLayerStatus.READABLE
    assert layer.complete
    assert "COMPRESSED FIXTURE LINE" in layer.text


def test_a_tj_array_reads_its_runs() -> None:
    """Kerned text is the normal case in a real invoice, not the simple one."""
    layer = extract_text_layer(_pdf(b"BT /F1 10 Tf [(Kerned) -500 (Text)] TJ ET"))
    assert "Kerned" in layer.text
    assert "Text" in layer.text
    assert layer.complete


def test_escapes_and_octal_sequences_resolve() -> None:
    layer = extract_text_layer(_pdf(rb"BT (Parentheses \( \) and a backslash \\ ok) Tj ET"))
    assert "Parentheses ( )" in layer.text
    assert "backslash \\" in layer.text

    octal = extract_text_layer(_pdf(rb"BT (\101\102\103) Tj ET"))
    assert octal.text == "ABC"


# ---------------------------------------------------------------- criterion 2
# The parser reports whether a text layer was present, and flags when it falls back.


def test_a_non_pdf_is_refused_rather_than_treated_as_empty() -> None:
    layer = extract_text_layer(b"this is not a pdf at all")
    assert layer.status is TextLayerStatus.ABSENT
    assert layer.lines == ()
    assert layer.needs_fallback is True
    assert "refuse the document" in layer.notes[0]


def test_an_encrypted_document_is_reported_rather_than_worked_around() -> None:
    layer = extract_text_layer(b"%PDF-1.4\n/Encrypt 9 0 R\ntrailer\n%%EOF\n")
    assert layer.status is TextLayerStatus.ABSENT
    assert "encrypted" in layer.notes[0]


def test_a_document_with_no_streams_is_flagged_as_a_scan() -> None:
    layer = extract_text_layer(b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n%%EOF\n")
    assert layer.status is TextLayerStatus.ABSENT
    assert layer.needs_fallback is True
    assert "scan" in layer.notes[0]


def test_streams_with_no_text_operators_are_present_but_unreadable() -> None:
    layer = extract_text_layer(_pdf(b"q 1 0 0 1 0 0 cm Q"))
    assert layer.status is TextLayerStatus.PRESENT_UNREADABLE
    assert layer.needs_fallback is True
    assert layer.notes


def test_one_bad_string_does_not_discard_the_page() -> None:
    """Salvage and count. A carrier invoice with one glyph from a subset font is
    still a born-digital invoice we can mostly read, and throwing the whole layer
    away would force OCR on a document OCR is worse at."""
    layer = extract_text_layer(
        _pdf(b"BT (Container Number: MAEU1234567) Tj (\x00\x01binary) Tj ET")
    )
    assert layer.status is TextLayerStatus.READABLE
    assert "MAEU1234567" in layer.text
    assert layer.undecodable_strings == 1
    assert layer.complete is False
    assert layer.needs_fallback is True, "a partial layer must fall back, not be audited"
    assert "incomplete" in layer.notes[0]


def test_a_page_where_everything_failed_says_so_and_still_counts() -> None:
    """Zero readable text is not readable, whatever the operators looked like. And
    the count survives, because that is the difference between a scan and a file we
    are simply not equipped to read."""
    layer = extract_text_layer(_pdf(b"BT (\x00\x01\x02binary) Tj ET"))
    assert layer.status is TextLayerStatus.PRESENT_UNREADABLE
    assert layer.lines == ()
    assert layer.needs_fallback is True
    assert layer.undecodable_strings == 1, "a fully unreadable layer still dropped text"


def test_fallback_and_completeness_are_different_properties() -> None:
    """Readable is not complete, and conflating them would be an audit error.

    A document that decoded but dropped strings is readable and not complete. With
    one flag, a field we failed to read would look like a field the carrier failed
    to disclose, and we would file a 541.5 claim against our own parser.
    """
    for layer in (extract_text_layer(fixture_bytes()), extract_text_layer(b"not a pdf")):
        assert isinstance(layer, TextLayer)
        assert isinstance(layer.needs_fallback, bool)
        assert isinstance(layer.complete, bool)
    assert extract_text_layer(fixture_bytes()).complete is True
    assert extract_text_layer(b"not a pdf").complete is False


# ---------------------------------------------------------------- criterion 3
# Character accuracy is not used as a quality signal.


def test_the_text_layer_reports_no_accuracy_score() -> None:
    """The criterion as an absence.

    There is no accuracy field, no confidence, no score. Asserted so adding one is a
    deliberate act rather than something a future contributor does because a number
    looks like it should be there.
    """
    fields = set(TextLayer.__dataclass_fields__)
    banned = {"accuracy", "confidence", "score", "quality", "ocr_accuracy", "character_accuracy"}
    assert not (fields & banned), fields & banned


def test_the_status_values_are_facts_about_bytes_not_about_us() -> None:
    assert {m.value for m in TextLayerStatus} == {"readable", "present_unreadable", "absent"}


def test_the_module_docstring_says_why_there_is_no_score() -> None:
    text = " ".join((importlib.import_module("quayline.ingest.pdftext").__doc__ or "").split())
    assert "misleading" in text
    assert "worse than no number" in text
    assert "near free and near exact" in text


# ---------------------------------------------------------------- criterion 4
# A born-digital fixture with no OCR in the path, cross checked against poppler.


@pytest.mark.skipif(not HAS_POPPLER, reason="poppler is not installed")
def test_our_output_is_identical_to_poplers() -> None:
    """The test that would have caught the bug I shipped.

    extract_text_layer was returning the closing paren and the Tj operator at the end
    of every line. It passed every other test in this file, because the other tests
    checked that a string was present rather than that the text was right. One run
    against an independent implementation found it.
    """
    result = subprocess.run(
        ["pdftotext", "-layout", str(FIXTURE), "-"], capture_output=True, text=True, check=True
    )
    theirs = [line for line in result.stdout.splitlines() if line.strip()]
    mine = [line for line in extract_text_layer(fixture_bytes()).lines if line.strip()]
    assert mine == theirs, f"ours:\n{mine}\npoppler:\n{theirs}"


@pytest.mark.skipif(not HAS_POPPLER, reason="poppler is not installed")
def test_no_line_of_ours_carries_an_operator() -> None:
    """The specific regression, named, so tightening the cross check cannot lose it."""
    for line in extract_text_layer(fixture_bytes()).lines:
        assert ") Tj" not in line
        assert ") TJ" not in line
        assert line == line.strip()


@pytest.mark.skipif(not HAS_QPDF, reason="qpdf is not installed")
def test_qpdf_agrees_the_fixture_is_well_formed() -> None:
    """A third opinion that the file is a PDF and not something our reader tolerates."""
    result = subprocess.run(
        ["qpdf", "--check", str(FIXTURE)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
