"""Test helpers shared across modules.

``build_pdf`` lives here rather than in one test module so two modules can state a
document inline without importing from each other. Cross importing test modules
works until the first refactor moves a helper, and then it fails somewhere
unrelated.
"""

from __future__ import annotations

__all__ = ["build_pdf"]


def build_pdf(*lines: str) -> bytes:
    """A minimal single page PDF whose text layer is exactly these lines.

    Written by hand rather than checked in as a fixture so a test can state a
    document inline and a reviewer can read what it says. The content stream is the
    part ``ingest/pdftext.py`` reads, and it is the only part that varies here.
    """
    body = "BT /F1 12 Tf\n" + "\n".join(f"({_escape(line)}) Tj" for line in lines) + "\nET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(body)} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
