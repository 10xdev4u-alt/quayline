"""The regulation layer: what a compliant invoice must contain, and what a
non compliant one costs the carrier.

Two modules carry the load.

``checklist`` is 46 CFR 541.6, the twenty required disclosures. Generated from
the eCFR rather than typed, so the text is diffable against the published
source.

``kill_switch`` is 46 CFR 541.5, which turns a missing disclosure into
elimination of the obligation to pay. It is the strongest ground available in
this part, and the one most easily misused.

``deadline`` is 46 CFR 541.7 and 541.8, the three thirty day clocks and the
dates they run from. Each clock takes an anchor type that can only carry the
date that clock is allowed to read, because the errors available here all
favour the carrier and all produce confident answers.
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
from quayline.regulation.deadline import (
    CURE_RIGHTS,
    UNCURABLE_DEFECTS,
    BillingParty,
    ChargeIncurred,
    DisputeNotice,
    InvoiceIssued,
    NvoccChain,
    RequestReceived,
    Timeliness,
    assess_chain,
    dispute_request_deadline,
    invoice_deadline,
    nvocc_invoice_deadline,
    reissue_deadline,
)
from quayline.regulation.kill_switch import Obligation, Omission, effect_of
from quayline.regulation.source import (
    PART_541,
    SECTION_541_5,
    SECTION_541_6,
    SECTION_541_7,
    SECTION_541_8,
    Provenance,
)

__all__ = [
    "CHECKLIST",
    "CURE_RIGHTS",
    "GROUP_HEADINGS",
    "PART_541",
    "SECTION_541_5",
    "SECTION_541_6",
    "SECTION_541_7",
    "SECTION_541_8",
    "UNCURABLE_DEFECTS",
    "BillingParty",
    "ChargeIncurred",
    "ChecklistField",
    "DisputeNotice",
    "InvoiceIssued",
    "NvoccChain",
    "Obligation",
    "Omission",
    "Provenance",
    "RequestReceived",
    "Scope",
    "Timeliness",
    "Trade",
    "assess_chain",
    "by_cite",
    "dispute_request_deadline",
    "effect_of",
    "invoice_deadline",
    "nvocc_invoice_deadline",
    "reissue_deadline",
    "required_for",
]
