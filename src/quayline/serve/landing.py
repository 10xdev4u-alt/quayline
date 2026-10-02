"""Issue 81: the intake page's content, assembled.

Thin on purpose. The computation lives in :mod:`quayline.web.example` because the
public landing page shows the same worked example and the two must not be able to
drift apart. This module exists only to hand that example to the document builder in
the shape it wants.
"""

from __future__ import annotations

from quayline.web.document import intake_document
from quayline.web.example import FIXTURE, FIXTURE_NOTE, example_audit, money

__all__ = ["FIXTURE", "FIXTURE_NOTE", "example_audit", "landing_document"]


def landing_document() -> str:
    """The intake page, with the argument already made before anything is uploaded."""
    strip, result, rail = example_audit()
    return intake_document(
        days=strip.days,
        result=result,
        rail_pairs=rail,
        money=(
            money(result.demanded_total),
            money(result.recomputed_total),
            money(result.variance),
        ),
        fixture_note=FIXTURE_NOTE,
    )
