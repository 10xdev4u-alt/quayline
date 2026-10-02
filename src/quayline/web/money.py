"""Issue 201: how the money is worded on a page, in one place.

Two pages print figures from the same result and both have to agree about what the
variance is called. When the decision lived in ``result.py`` and ``filing.py`` wrote its
own label, a negative variance printed as disputed money on a signed filing, which is the
worst place on this project for that particular error.

So the case analysis is here, and neither page words the money itself.

Three cases, because two of them are not a dispute
---------------------------------------------------

- No findings: nothing to dispute.
- Only an unresolved tariff: the days may be right and the money is unknown. That is not
  a dispute and must not be labelled one.
- Anything else: a dispute, and the amount at stake is the variance, but only when it is
  positive. A negative variance means the carrier billed less than the recomputation
  allows, which is not money to dispute.

Both callers get a label from :func:`disputed_label` and a stake from
:func:`verdict_of`. A page cannot opt out of the reasoning, which is the point.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from quayline.web.example import money

#: The label when there is a dispute and the variance is positive.
DISPUTED = "disputed"

#: The label otherwise. "difference" is deliberately dull: a negative variance is not a
#: win, it is the carrier having under-charged, and calling it anything better would be
#: the kind of sentence that gets quoted back at us.
DIFFERENCE = "difference"

#: What the headline figure reads when nothing is in dispute.
NOTHING = "nothing"


def verdict_of(result: Any) -> tuple[str, str, str]:
    """``(heading, stake, verdict)`` for one result.

    ``verdict`` is one of ``dispute``, ``unresolved`` or ``clean``. The stake is the
    string a page should show as its headline number, already money-formatted.
    """
    findings = result.findings
    if not findings:
        return "Nothing to dispute on this invoice.", NOTHING, "clean"

    substantive = [f for f in findings if "tariff_unresolved" not in f.code]
    if not substantive:
        return "We could not price this invoice.", "not priced", "unresolved"

    if result.variance is not None and result.variance > 0:
        return "There is a dispute here.", money(result.variance), "dispute"
    return "There is a finding here.", "see the grounds", "dispute"


def disputed_label(result: Any) -> str:
    """What to call the variance on this page. Never both words at once.

    A negative variance prints as a difference, not as disputed money, and a result whose
    only finding is an unresolved tariff has no figure to dispute.
    """
    _heading, stake, verdict = verdict_of(result)
    if verdict == "dispute" and stake not in (NOTHING, "not priced") and positive(result.variance):
        return DISPUTED
    return DIFFERENCE


def positive(variance: Decimal | None) -> bool:
    """Whether a variance is money in dispute. Negative variance is not."""
    return variance is not None and variance > 0


__all__ = [
    "DIFFERENCE",
    "DISPUTED",
    "NOTHING",
    "disputed_label",
    "positive",
    "verdict_of",
]
