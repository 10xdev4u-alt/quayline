"""Issue 31: the availability contradiction, decided from the invoice alone.

The most automatable check in the category, and the one with the shortest route to
a carrier saying nothing back.

541.6(b)(6) requires the container availability date on an import invoice.
541.6(b)(8) requires the specific dates charged. Every subsection of 541.6(b) opens
with "must be accurate". So a carrier that certifies availability on the tenth and
bills from the eighth has certified two things that cannot both be true, and it
has certified both of them. **The contradiction is internal to the document the
carrier signed.** No terminal API, no gate log, no witness, no photograph.

Why this is framed as a sufficiency failure and not a 541.5 inaccuracy

The framing is the whole issue and it is easy to get wrong.

541.5 is a **kill switch**, and it triggers on a *missing* required disclosure with
no showing and no cure period. It does not apply here, because nothing is missing.
The carrier disclosed both dates. It disclosed them in a way that cannot be
reconciled, and there is no version of 541.5 that reads a contradiction as an
omission. Treating it as a 541.5 kill would be claiming a remedy we do not have,
and a carrier that reads the letter will say so.

The correct frame is **sufficiency under 541.6(b)**: the disclosures the carrier
made are internally inconsistent, so the charge cannot be substantiated on this
invoice. That is a weaker remedy and an honest one, and it is the one a tribunal
will actually entertain.

The distinction is encoded in the type. This returns an ``Inconsistency``, not an
``Omission``, so it cannot be pooled with the kill switch by accident.

On confidence

The issue calls this high confidence and that is right, but the word needs
qualifying or it becomes the category's favourite failure. It is high confidence
**relative to the invoice**: we are certain of the contradiction and we are certain
we need nothing external to establish it. It is not high confidence about what the
carrier will do about it, and it is not a prediction of recovery. A carrier may
simply reissue. The `disputed_days` are exactly the days at issue, and nothing
here estimates their value, because a value estimate needs a tariff we may not hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quayline.models.invoice import (
    CITE_AVAILABILITY,
    CITE_CHARGED_DATES,
    TimingDisclosures,
)
from quayline.regulation import Trade

#: 541.6(b) as a whole, because the contradiction is between two subsections of it
#: and neither subsection is wrong on its own.
CITE_TIMING = "541.6(b)"

#: The sufficiency framing. Not 541.5. See the module docstring.
CITE_SUFFICIENCY = f"{CITE_TIMING}, as a sufficiency failure"


@dataclass(frozen=True, slots=True)
class Inconsistency:
    """Two disclosures on one invoice that cannot both be true.

    Deliberately a different type from ``regulation.kill_switch.Omission``. The two
    findings have different remedies, different evidentiary burdens and different
    letter language, and pooling them would let a 541.5 kill switch be asserted
    against a contradiction, which is a claim we would lose.
    """

    availability_date: date
    first_charged_day: date
    disputed_days: tuple[date, ...]
    cite: str = CITE_SUFFICIENCY

    @property
    def contradiction_days(self) -> int:
        return len(self.disputed_days)

    def as_sentence(self) -> str:
        """The finding, in one sentence, with the dates in it.

        Dates in the text rather than in an attachment, because a respondent who has
        to open a second document to check the claim has already started deciding
        whether to bother.
        """
        earliest = self.disputed_days[0].isoformat() if self.disputed_days else "none"
        return (
            f"The invoice states the container was available on "
            f"{self.availability_date.isoformat()} under 541.6(b)(6), and charges for "
            f"{self.contradiction_days} day(s) beginning {earliest} under 541.6(b)(8). "
            f"Both are certified, and they cannot both be accurate."
        )


def availability_contradiction(invoice: TimingDisclosures) -> Inconsistency | None:
    """The contradiction, or ``None`` when there is not one.

    Returns ``None`` rather than an empty finding so that a caller cannot
    distinguish "checked, clean" from "not checked" by looking at a truthy value.

    The comparison is strictly less than, not less than or equal. A container
    available on the tenth can be charged from the tenth, and a same-day charge is
    the normal case rather than a borderline one. Anything else would flag almost
    every compliant invoice and the finding would be ignored.
    """
    availability = invoice.availability_date
    if availability is None:
        return None
    if invoice.trade is not Trade.IMPORT:
        # 541.6(b)(6) is import only. On an export there is no availability date to
        # contradict, and inventing one would be a finding with no clause under it.
        return None

    first = invoice.first_charged_day
    if first >= availability:
        return None

    disputed = tuple(sorted(d for d in invoice.charged_dates if d < availability))
    if not disputed:
        return None
    return Inconsistency(
        availability_date=availability,
        first_charged_day=first,
        disputed_days=disputed,
    )


@dataclass(frozen=True, slots=True)
class AvailabilityCheck:
    """The result, carrying the fact that no external data was consulted.

    ``requires_external_data`` is a constant rather than a field. The reason this
    check needs nothing is the reason it is cheap and the reason it is worth running
    first, and a caller that could pass ``False`` would eventually pass ``False`` on a
    check that does need something.
    """

    inconsistency: Inconsistency | None = None

    @property
    def found(self) -> bool:
        return self.inconsistency is not None

    @property
    def requires_external_data(self) -> bool:
        return False

    @property
    def confidence_basis(self) -> str:
        """Why this is high confidence, stated so it cannot be quoted bare.

        The confidence is about the contradiction, not the outcome. A carrier may
        reissue the invoice, and nothing in this module predicts that it will not.
        """
        return (
            "High confidence as to the contradiction, which rests only on two "
            "disclosures the carrier certified. Not a prediction of recovery, and "
            "not a claim about what the carrier will do."
        )

    def as_sentence(self) -> str:
        if self.inconsistency is None:
            return "No availability contradiction in the disclosed timing."
        return self.inconsistency.as_sentence()


def check_availability(invoice: TimingDisclosures) -> AvailabilityCheck:
    """Run the check. Pure, total, and never raises for a clean invoice."""
    return AvailabilityCheck(inconsistency=availability_contradiction(invoice))


__all__ = [
    "CITE_AVAILABILITY",
    "CITE_CHARGED_DATES",
    "CITE_SUFFICIENCY",
    "CITE_TIMING",
    "AvailabilityCheck",
    "Inconsistency",
    "availability_contradiction",
    "check_availability",
]
