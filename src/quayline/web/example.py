"""The worked example, computed once, shared by every page that shows it.

Both the intake and the public landing page lead with the same day grid. If they each
computed it separately they would drift, and the day the site and the product disagree
is the day nobody trusts either. So the computation lives here, once, and both pages
read from it.

It is the same fixture ``tests/test_serve.py`` audits: a born-digital invoice carrying
one real rate transcribed from Maersk's own published tariff, and nothing from a client.

The cost is that the first page view runs a recomputation. It is a few milliseconds on
a file the repository already holds, on a server that is explicitly loopback only, and it
is cached after that. It is a real computation rather than a demo shortcut, which is the
only reason the hero cannot disagree with the engine.
"""

from __future__ import annotations

import os
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

#: The fixture the test suite already audits. Born digital, one real transcribed Maersk
#: rate, and nothing belonging to a client.
#: Resolved against this file rather than the working directory. Issue 208: it was the
#: string ``Path(<repo>/tests/fixtures/...)``, which resolved only from
#: the repository root. In the container the landing page raised FileNotFoundError and
#: served nothing at all, because this is the worked example on the landing page and the intake and the
#: file was not where the working directory said it was. Overridable for a bundle that
#: is not a checkout.
FIXTURE = Path(
    os.environ.get("QUAYLINE_FIXTURE")
    or Path(__file__).resolve().parents[3] / "tests/fixtures/born_digital_invoice.pdf"
)

#: Stated on the page itself, because the numbers are this example and not a customer.
#: An invented client, or a recovery percentage, is the fastest way to lose the only
#: thing this project has going for it.
FIXTURE_NOTE = (
    "The days above are the worked example this site is built on: a synthetic invoice "
    "carrying one real rate transcribed from Maersk's own published tariff. It is not a "
    "client, no client has used this yet, and no recovery rate is claimed anywhere."
)

#: What a page needs from the engine: the strip, the result, and the metadata rail.
Example = tuple[DayStrip, AuditResult, list[tuple[str, str]]]


def money(value: Decimal | None) -> str:
    """A figure for display, carrying its currency.

    The symbol stays on the number rather than moving into a column label, so each row
    of a ledger is self-describing to someone scanning it.
    """
    if value is None:
        return "not computed"
    return f"${value:,.2f}"


def day(value: date | None) -> str:
    """A date for display, or a plain statement that the document did not carry one.

    A missing disclosure is a fact about the invoice, so it is stated rather than
    rendered as ``None`` or raised over.
    """
    return value.isoformat() if value else "not disclosed"


@lru_cache(maxsize=1)
def example_audit() -> Example:
    """Audit the fixture once and hand back what the pages need.

    Cached because the landing page is the first request of every visit and the
    computation is identical each time. The strip, the result and the rail come back
    together so a change to any one of them cannot half-apply.
    """
    if not FIXTURE.is_file():
        msg = f"the worked example is missing at {FIXTURE}, so no page can show it"
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
        ("invoice date", day(bound.invoice_date)),
        ("free time", f"{bound.allowed_free_time_days} days"),
        ("disclosed end", day(bound.free_time_end)),
        ("recomputed end", day(strip.recomputed_free_time_end)),
    ]
    return strip, result, rail


__all__ = [
    "FIXTURE",
    "FIXTURE_NOTE",
    "Example",
    "day",
    "example_audit",
    "money",
]
