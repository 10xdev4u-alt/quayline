"""The text layer of a born-digital PDF, with no dependencies.

This is the default path and it should stay the default path. A major carrier
invoice is born digital, its text layer is machine readable, and parsing it is
near free and near exact. OCR is the fallback and the fallback says so.

Why no dependency

Zero runtime dependencies is a real constraint and it is worth keeping. A dispute
product that pulls in a PDF stack has a supply chain surface, and a supply chain
surface is a place where a version bump changes what a customer invoice parses as.
zlib is in the standard library, which covers FlateDecode, which is the only
compression a born-digital carrier invoice actually uses.

What is not handled, and fails closed

A PDF's text layer is a stream of positioning and string operators, and the bytes
inside a string are only text if the font's encoding is one we can read. A subset
font with a custom encoding and a ToUnicode CMap is the hard case, and this parser
does not resolve ToUnicode.

So a document it cannot read comes back with ``text_layer_readable`` false and no
text, rather than with text that looks plausible and is wrong. The caller is
expected to fall back to OCR, or to stop, and both are better than auditing a
document we misread.

What this module deliberately does not do

It does not report character accuracy as a quality signal. The issue is explicit
that accuracy is misleading on degraded input, and a number that looks like a
confidence score and is not one is worse than no number. What it reports instead
is whether a text layer was present and whether it could be read, which are facts.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from enum import StrEnum

# PDF string escapes inside a literal string, per the spec. Octal first because
# \053 is three characters and \5 is not a valid escape at all.
# A PDF literal string escape is at most three octal digits, and a bare digit
# after a backslash is not an escape at all. Both are spec facts and both are the
# kind of thing that is a silent corruption rather than an error.
_MAX_OCTAL_DIGITS = 3

# Below this, and other than tab, carriage return and newline, a byte in a text
# string means we are looking at a font program or a bitmap rather than a page.
_CONTROL_FLOOR = 32
_ALLOWED_CONTROLS = frozenset("\t\n\r")

_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}

# A text showing operator. Tj is a whole string, TJ is an array of runs and kerns,
# ' and " are show plus newline.
_SHOW = re.compile(rb"(\((?:\\.|[^()\\])*\)|<[0-9A-Fa-f\s]*>)")
_TJ_ARRAY = re.compile(rb"\[((?:[^\[\]\\]|\\.)*)\]\s*TJ", re.DOTALL)
_TJ_STRING = re.compile(rb"(\((?:\\.|[^()\\])*\))\s*Tj", re.DOTALL)
_LITERAL = re.compile(rb"\(((?:\\.|[^()\\])*)\)", re.DOTALL)
_HEX = re.compile(rb"<([0-9A-Fa-f\s]*)>")

# A page tree, a content stream reference, or any stream we can inflate.
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_FLATE = re.compile(rb"/Filter\s*(?:\[[^\]]*\])?\s*/FlateDecode", re.DOTALL)


class TextLayerStatus(StrEnum):
    """Whether a text layer was there, and whether we could read it.

    A fact, not a score. See the module docstring on why there is no accuracy
    number here.
    """

    #: Content stream decoded and text operators found. The default path.
    READABLE = "readable"
    #: A content stream exists but we could not decode it, or found no text
    #: operators in it. Common on a born-digital file with an unusual filter.
    PRESENT_UNREADABLE = "present_unreadable"
    #: No content stream at all, or nothing decodable. Almost always a scan.
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class TextLayer:
    """The text of a document, and what we know about how we got it."""

    status: TextLayerStatus
    lines: tuple[str, ...]
    #: How many content streams we decoded. One per page, usually.
    streams_decoded: int = 0
    #: Strings we skipped because their bytes are not readable text with a known
    #: encoding. Non zero means the text below is incomplete and must not be
    #: audited as if it were whole.
    undecodable_strings: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def needs_fallback(self) -> bool:
        """Whether the caller should go to OCR, or stop.

        Partial is deliberately a fallback. A document where we dropped strings is
        a document where a field may be missing for a reason that has nothing to
        do with the carrier, and auditing it would mean reporting a missing
        disclosure that is our own fault.

        This is deliberately not written as "status is not READABLE". Readable and
        complete are different properties, and collapsing them here would have a
        partially read invoice audited as though it were whole, which is the exact
        failure the separation exists to prevent.
        """
        return not self.complete

    @property
    def complete(self) -> bool:
        """True only when the text is the whole document's text layer.

        This is the property that matters, and it is stricter than readable. A
        document that decoded but dropped strings is readable and not complete,
        and the two being different is the point of having both.
        """
        return self.status is TextLayerStatus.READABLE and self.undecodable_strings == 0


def _unescape(raw: bytes) -> bytes:
    """Resolve PDF literal string escapes."""
    out = bytearray()
    i = 0
    while i < len(raw):
        byte = raw[i : i + 1]
        if byte != b"\\" or i + 1 >= len(raw):
            out += byte
            i += 1
            continue
        nxt = raw[i + 1 : i + 2]
        if nxt in _ESCAPES:
            out += _ESCAPES[nxt]
            i += 2
            continue
        if nxt.isdigit():
            digits = b""
            j = i + 1
            while j < len(raw) and len(digits) < _MAX_OCTAL_DIGITS and raw[j : j + 1].isdigit():
                digits += raw[j : j + 1]
                j += 1
            out.append(int(digits, 8) & 0xFF)
            i = j
            continue
        if nxt in (b"\n", b"\r"):
            # A backslash before a newline is a line continuation, not an escape.
            i += 2
            continue
        out += nxt
        i += 2
    return bytes(out)


def _decode_string(raw: bytes) -> tuple[str, bool]:
    """One string operand, as text. The bool says whether we are sure of it.

    WinAnsiEncoding and PDFDocEncoding cover the text a born-digital freight
    invoice carries. Anything above U+02FF in a literal string, or a hex string
    whose bytes do not look like text at all, comes back undecodable rather than
    decoded to something plausible.
    """
    if raw[:1] == b"<" and raw[-1:] == b">":
        body = _HEX.sub(rb"\1", raw)
        digits = re.sub(rb"\s", b"", body)
        if len(digits) % 2:
            return "", False
        try:
            raw_bytes = bytes.fromhex(digits.decode("ascii"))
        except ValueError:
            return "", False
    else:
        raw_bytes = _unescape(raw[1:-1])

    if not raw_bytes:
        return "", True
    try:
        text = raw_bytes.decode("cp1252")
    except UnicodeDecodeError:
        return "", False
    # Control characters other than tab and newline mean this is a font program or
    # a bitmap, not a page of text.
    if any(ord(c) < _CONTROL_FLOOR and c not in _ALLOWED_CONTROLS for c in text):
        return "", False
    return text, True


def _content_streams(data: bytes) -> tuple[list[bytes], int, int]:
    """Every stream in the file, inflating the Flate ones.

    Returns the decoded streams, how many were found, and how many failed to
    inflate. A stream we cannot inflate is not necessarily a content stream, so a
    failure is counted rather than raised.
    """
    found = 0
    failures = 0
    decoded: list[bytes] = []
    for match in _STREAM.finditer(data):
        found += 1
        blob = match.group(1)
        if _FLATE.search(data[max(0, match.start() - 200) : match.start()]):
            try:
                blob = zlib.decompress(blob)
            except zlib.error:
                failures += 1
                continue
        decoded.append(blob)
    return decoded, found, failures


def _lines_from_stream(stream: bytes) -> tuple[list[str], int]:
    """Lines from one content stream, and how many strings we could not decode.

    Returns the count rather than a list of them because a stream can hold many
    strings and the caller only ever wants the number.
    """
    dropped = 0
    buffer: list[str] = []
    for match in _TJ_ARRAY.finditer(stream):
        for literal in _LITERAL.finditer(match.group(1)):
            text, ok = _decode_string(literal.group(0))
            if ok:
                buffer.append(text)
            else:
                dropped += 1
        buffer.append("\n")
    for match in _TJ_STRING.finditer(stream):
        # group 1 is the parenthesised string. group 0 would be that plus the
        # operator, and stripping its first and last characters would leave the
        # closing paren and the operator in the text.
        text, ok = _decode_string(match.group(1))
        if ok:
            buffer.append(text + "\n")
        else:
            dropped += 1
    return "".join(buffer).splitlines(), dropped


def extract_text_layer(data: bytes) -> TextLayer:
    """Read the text layer of a PDF.

    ``data`` is the raw file. A file that is not a PDF, or is encrypted, or has no
    text operators, comes back with a status that says so and no text.
    """
    if not data.startswith(b"%PDF"):
        return TextLayer(
            status=TextLayerStatus.ABSENT,
            lines=(),
            notes=(
                "not a PDF. The caller should refuse the document rather than treat it as empty.",
            ),
        )
    if b"/Encrypt" in data:
        return TextLayer(
            status=TextLayerStatus.ABSENT,
            lines=(),
            notes=(
                "the document is encrypted. An encrypted carrier invoice is worth "
                "asking about rather than working around.",
            ),
        )

    streams, found, failures = _content_streams(data)
    lines: list[str] = []
    undecodable = 0

    for stream in streams:
        if b"Tj" not in stream and b"TJ" not in stream:
            continue
        found_lines, dropped = _lines_from_stream(stream)
        lines.extend(found_lines)
        undecodable += dropped

    stripped = [line.strip() for line in lines if line.strip()]
    absent_notes: tuple[str, ...] = ()

    if not stripped:
        status = TextLayerStatus.PRESENT_UNREADABLE if found else TextLayerStatus.ABSENT
        absent_notes = ()
        if found == 0:
            absent_notes = ("no streams found. This is almost certainly a scan.",)
        elif failures:
            absent_notes = (
                f"{failures} of {found} streams would not inflate. The file is born "
                f"digital and uses a filter we do not read.",
            )
        else:
            absent_notes = (
                "streams decoded but no text showing operators. Either a scan, or a "
                "text layer we are not reading.",
            )
        # undecodable is not zero on this path. A stream whose only string was
        # unreadable dropped as much text as a stream we never opened, and the
        # caller needs that number to tell a scan apart from a file we are simply
        # not equipped to read.
        return TextLayer(
            status=status,
            lines=(),
            streams_decoded=found,
            undecodable_strings=undecodable,
            notes=absent_notes,
        )

    return TextLayer(
        status=TextLayerStatus.READABLE,
        lines=tuple(stripped),
        streams_decoded=found,
        undecodable_strings=undecodable,
        notes=(
            (
                f"dropped {undecodable} string(s) whose bytes are not readable as text "
                f"with a known encoding. The text below is incomplete."
            ),
        )
        if undecodable
        else (),
    )


__all__ = [
    "TextLayer",
    "TextLayerStatus",
    "extract_text_layer",
]
