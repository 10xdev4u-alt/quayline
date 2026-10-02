"""The intake page, assembled from the engine's own output.

The day grid on the landing page is not a mock. It is the fixture the test suite already
audits, run through the same ``bind_ledger`` and ``audit`` and ``build_strip`` the
uploaded path runs through, and the money is read off the resulting ``AuditResult``
rather than typed into a template.

That is the reason this module exists. A hero written by hand would drift from the
engine within a week, and a demo that disagrees with the product is worse than no demo.
If the engine changes a figure, this page changes with it, and a test fails if the two
stop agreeing.

The cost is that the landing page audits a PDF on every request. That is a few
milliseconds on a file the repository already holds, on a server that is explicitly
loopback only. It is not a demo shortcut, it is the real computation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from quayline.cli.audit_render import resolve_disclosed
from quayline.engine.audit import audit
from quayline.engine.result import AuditResult
from quayline.ingest.bind import bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.web.daystrip import DayStrip, build_strip
from quayline.web.document import intake_document

#: The same fixture ``tests/test_serve.py`` audits. Born digital, one real transcribed
#: Maersk rate, and nothing from a client.
FIXTURE = Path("tests/fixtures/born_digital_invoice.pdf")

#: Stated on the page itself, because the numbers above are this example and not a
#: customer. An invented client, or a recovery percentage, would be the fastest way to
#: lose the only thing this project has going for it.
FIXTURE_NOTE = (
    "The days above are the worked example this site is built on: a synthetic invoice "
    "carrying one real rate transcribed from Maersk's own published tariff. It is not a "
    "client, no client has used this yet, and no recovery rate is claimed anywhere."
)


def _day(value: date | None) -> str:
    """A date for the rail, or a plain statement that we do not have one.

    The rail is a claim about the document, so a missing date is stated rather than
    rendered as ``None`` or an exception.
    """
    return value.isoformat() if value else "not disclosed"


def _money(value: Decimal | None) -> str:
    """A figure for display, carrying its currency.

    The symbol stays on the number rather than moving into the column label. A reader
    scanning the ledger wants each row to be self-describing, and a bare ``1,170.00``
    on a line about a carrier's bill is one more thing to work out.
    """
    if value is None:
        return "not computed"
    return f"${value:,.2f}"


#: What the page needs from the engine: the strip, the result, and the rail.
Landing = tuple["DayStrip", "AuditResult", list[tuple[str, str]]]


@lru_cache(maxsize=1)
def example_audit() -> Landing:
    """Audit the fixture once and hand back what the page needs.

    Cached because the landing page is the first request on every visit and the
    computation is identical every time. The tuple is the strip, the audit result, and
    the rail, built together so a change to any of them cannot half-apply.
    """
    if not FIXTURE.is_file():
        msg = f"the worked example is missing at {FIXTURE}, so the page cannot show it"
        raise FileNotFoundError(msg)
    pdf = FIXTURE.read_bytes()
    bound = bind_ledger(extract_text_layer(pdf))
    result = audit(
        pdf,
        "Maersk",
        "newark",
        resolve_disclosed(bound.rate_rule, "newark"),
        invoice_ref="",
    )
    strip = build_strip(result)
    rail = [
        ("carrier", "Maersk"),
        ("terminal", "Newark, NJ, dry"),
        ("rule", bound.rate_rule),
        ("invoice date", _day(bound.invoice_date)),
        ("free time", f"{bound.allowed_free_time_days} days"),
        ("disclosed end", _day(bound.free_time_end)),
        ("recomputed end", _day(strip.recomputed_free_time_end)),
    ]
    return strip, result, rail


def landing_document() -> str:
    """The intake page, with the argument already made before anything is uploaded."""
    strip, result, rail = example_audit()
    return intake_document(
        days=strip.days,
        rail_pairs=rail,
        money=(
            _money(result.demanded_total),
            _money(result.recomputed_total),
            _money(result.variance),
        ),
        fixture_note=FIXTURE_NOTE,
    )


__all__ = ["FIXTURE", "FIXTURE_NOTE", "example_audit", "landing_document"]
