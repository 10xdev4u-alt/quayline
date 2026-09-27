"""The regulation layer: what a compliant invoice must contain, and what a
non compliant one costs the carrier.

Two modules carry the load.

``checklist`` is 46 CFR 541.6, the twenty required disclosures. Generated from
the eCFR rather than typed, so the text is diffable against the published
source.

``kill_switch`` is 46 CFR 541.5, which turns a missing disclosure into
elimination of the obligation to pay. It is the strongest ground available in
this part, and the one most easily misused.
"""

from __future__ import annotations

from quayline.regulation.checklist import (
    CHECKLIST,
    GROUP_HEADINGS,
    ChecklistField,
    Scope,
    Trade,
    by_cite,
    required_for,
)
from quayline.regulation.kill_switch import Obligation, Omission, effect_of
from quayline.regulation.source import SECTION_541_5, SECTION_541_6, Provenance

__all__ = [
    "CHECKLIST",
    "GROUP_HEADINGS",
    "SECTION_541_5",
    "SECTION_541_6",
    "ChecklistField",
    "Obligation",
    "Omission",
    "Provenance",
    "Scope",
    "Trade",
    "by_cite",
    "effect_of",
    "required_for",
]
