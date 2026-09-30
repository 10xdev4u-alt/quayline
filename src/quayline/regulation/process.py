"""Issue 4: what 541.8 is, what it is not, and where the money comes from.

541.8(a) gives the billed party at least thirty days from invoice issuance to
request mitigation, refund or waiver. 541.8(b) requires the billing party to
**attempt to resolve** within thirty days, or later by mutual agreement.

Attempt to resolve is not resolve. There is no requirement that the carrier pay
anything. 541.8 provides a compliant channel and a deadline, and **zero
substantive entitlement**. The money comes from 541.5, 541.7, 541.6 accuracy, or
41102(c), and every finding this module produces says so in its text.

The failure this exists to stop is specific: **treating 541.8 as a payment
entitlement produces disputes that lose.** A letter demanding money "under 541.8"
asks for something the section does not grant, and the respondent's easiest reply
is to quote the section back. The channel is real, the deadline is real, and the
money is elsewhere. Conflating the three is how a valid process complaint becomes
an invalid payment demand.

The three tiers

``SUBSTANTIVE``
    A finding that carries money. 541.5 on a missing disclosure, 541.7 on a late
    invoice, 541.6 accuracy on a contradiction, 41102(c) on a false certification.
    These are the only findings a recovery estimate may be built from.

``PROCESS``
    A finding about the channel or the deadline. A published dispute window shorter
    than thirty days, a missing contact under 541.6(d)(1), a resolution attempt
    that never happened. Real, worth sending, and it carries **no money by
    construction**: there is no amount field on this type, so there is nothing for
    an estimator to sum.

``INFORMATIONAL``
    Context for the letter. What the carrier published, what we checked, what we
    could not check. Never money, never a claim.

(a) is a floor, (b) is a ceiling with a bilateral escape hatch

A carrier publishing a 7-day dispute window violates 541.8(a) directly. That is
arguably a 541.6(d)(3) failure — the invoice's stated timeframes do not comply with
the billing practices in this part — and a 541.6(d)(3) failure is therefore a 541.5
failure, because (d)(3) is a required disclosure. **Arguably**, not certainly, and
the test asserts the marker rather than the conclusion. The chain has two links and
the second one has not been adjudicated, so the finding carries `arguable` and the
letter may not present it as settled.

The (b) side is softer still. "Attempt to resolve" is satisfied by a good-faith
response, and a later date agreed by both parties extends the ceiling. A carrier
that answered on day 40 with the billed party's agreement has complied. So a (b)
finding needs the absence of agreement as part of its facts, and the constructor
requires it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.regulation.checklist import by_cite

#: 541.8(a): at least thirty days from issuance to request.
MINIMUM_DISPUTE_DAYS = 30

#: 541.8(b): attempt to resolve within thirty days of receipt.
RESOLUTION_WINDOW_DAYS = 30

CITE_541_8_A = "541.8(a)"
CITE_541_8_B = "541.8(b)"
CITE_DISPUTE_TIMEFRAMES = "541.6(d)(3)"

#: Where the money comes from. Never 541.8. Stated once so every process finding
#: can quote it rather than paraphrase it, because a paraphrase drifts and the
#: drift is always toward implying 541.8 grants something.
ENTITLEMENT_SOURCES = "541.5, 541.7, 541.6 accuracy, or 46 U.S.C. 41102(c)"


class ProcessTier(StrEnum):
    """The three tiers. Money lives in exactly one of them."""

    #: Carries money. The only tier a recovery estimate may be built from.
    SUBSTANTIVE = "substantive"
    #: About the channel or the deadline. Real, worth sending, no amount by
    #: construction.
    PROCESS = "process"
    #: Context for the letter. Never money, never a claim.
    INFORMATIONAL = "informational"


@dataclass(frozen=True, slots=True)
class ProcessFinding:
    """A finding about the dispute process, which cannot carry money.

    There is deliberately no amount field. A process finding with an amount would
    be a payment demand under 541.8, which is the failure this module exists to
    stop. The type cannot express it, so no caller can construct it.
    """

    tier: ProcessTier
    cite: str
    summary: str
    detail: str = ""
    entitlement: str = ENTITLEMENT_SOURCES

    def __post_init__(self) -> None:
        if self.tier is not ProcessTier.PROCESS and self.tier is not ProcessTier.INFORMATIONAL:
            msg = (
                f"a ProcessFinding cannot be {self.tier.value}. Substantive findings "
                f"belong to their own modules, and putting one here would let a money "
                f"claim travel under a process cite."
            )
            raise ValueError(msg)

    def states_no_entitlement(self) -> bool:
        """Whether the finding says where the money comes from, and that it is not
        541.8."""
        return "never from 541.8" in self.detail or "never from 541.8" in self.summary


@dataclass(frozen=True, slots=True)
class DisputeWindow:
    """The window a carrier publishes for mitigation, refund or waiver requests."""

    published_days: int
    invoice_issued: date
    source: str = ""

    @property
    def meets_floor(self) -> bool:
        """541.8(a) is a floor of thirty days."""
        return self.published_days >= MINIMUM_DISPUTE_DAYS

    @property
    def deadline(self) -> date:
        """The last day a request may be made under the published window."""
        return self.invoice_issued + timedelta(days=self.published_days)


def check_dispute_window(window: DisputeWindow) -> ProcessFinding | None:
    """A published window shorter than thirty days.

    Returns ``None`` when the floor is met, because a compliant window is not a
    finding, it is the absence of one, and the absence should not appear in a
    letter as though it were.

    A short window is **arguably** a 541.6(d)(3) failure: the invoice's stated
    timeframes do not comply with the billing practices in this part. Arguably,
    because the chain runs published window to (d)(3) to 541.5, and the second link
    has not been adjudicated. The finding carries the marker and the letter must
    present it as unsettled.
    """
    if window.meets_floor:
        return None
    by_cite(CITE_DISPUTE_TIMEFRAMES)
    return ProcessFinding(
        tier=ProcessTier.PROCESS,
        cite=CITE_DISPUTE_TIMEFRAMES,
        summary=(
            f"The carrier publishes a {window.published_days}-day dispute window, below "
            f"the 541.8(a) floor of {MINIMUM_DISPUTE_DAYS} days."
        ),
        detail=(
            f"Arguable {CITE_DISPUTE_TIMEFRAMES} failure: the stated timeframes do not "
            f"comply with the billing practices in this part, which is therefore "
            f"arguably a 541.5 failure. Substantive entitlement, if any, comes from "
            f"{ENTITLEMENT_SOURCES}, never from 541.8."
        ),
    )


@dataclass(frozen=True, slots=True)
class ResolutionAttempt:
    """What happened after a mitigation, refund or waiver request was made."""

    requested_on: date
    answered_on: date | None
    as_of: date
    #: A later deadline agreed by both parties under 541.8(b), if any. A date, not
    #: a flag, because an agreement moves the ceiling rather than removing it. A
    #: boolean would clear a carrier that breaks the agreed deadline too.
    extended_to: date | None = None

    @property
    def ceiling(self) -> date:
        """The date an answer is due by: the agreed extension, or thirty days."""
        if self.extended_to is not None:
            return self.extended_to
        return self.requested_on + timedelta(days=RESOLUTION_WINDOW_DAYS)

    @property
    def overdue(self) -> bool:
        """Past the applicable ceiling, answered or not.

        An unanswered request is overdue only once the ceiling has passed as of the
        evaluation date. Without that comparison a request made yesterday with no
        reply yet produces "silence is not an attempt", accusing a carrier that is
        still inside its window. `as_of` is required rather than defaulted to
        today, because a check evaluated "now" gives a different answer every day
        it runs, and a finding that appears and disappears with the calendar is not
        a finding.
        """
        end = self.answered_on if self.answered_on is not None else self.as_of
        return end > self.ceiling


def check_resolution_attempt(attempt: ResolutionAttempt) -> ProcessFinding | None:
    """A (b) finding needs the absence of agreement as part of its facts.

    A carrier that answered on day 40 with the billed party's agreement has
    complied, so "answered late" without the agreement question is not a finding,
    it is half a finding. The constructor carries `mutually_extended`, and this
    function reads it.
    """
    if not attempt.overdue:
        return None
    if attempt.answered_on is None:
        detail = (
            f"No response to a request made {attempt.requested_on.isoformat()}, due by "
            f"{attempt.ceiling.isoformat()}. 541.8(b) requires an attempt to resolve, "
            f"and silence past the ceiling is not an attempt. Substantive entitlement, "
            f"if any, comes from {ENTITLEMENT_SOURCES}, never from 541.8."
        )
    else:
        late_by = (attempt.answered_on - attempt.ceiling).days
        if attempt.extended_to is not None:
            detail = (
                f"Answered {late_by} day(s) past the mutually extended deadline of "
                f"{attempt.ceiling.isoformat()}. The extension moved the ceiling; it did "
                f"not remove it. Substantive entitlement, if any, comes from "
                f"{ENTITLEMENT_SOURCES}, never from 541.8."
            )
        else:
            detail = (
                f"Answered {late_by} day(s) past the 541.8(b) window with no mutual "
                f"extension. Substantive entitlement, if any, comes from "
                f"{ENTITLEMENT_SOURCES}, never from 541.8."
            )
    return ProcessFinding(
        tier=ProcessTier.PROCESS,
        cite=CITE_541_8_B,
        summary="The carrier did not attempt to resolve within the 541.8(b) window.",
        detail=detail,
    )


__all__ = [
    "CITE_541_8_A",
    "CITE_541_8_B",
    "CITE_DISPUTE_TIMEFRAMES",
    "ENTITLEMENT_SOURCES",
    "MINIMUM_DISPUTE_DAYS",
    "RESOLUTION_WINDOW_DAYS",
    "DisputeWindow",
    "ProcessFinding",
    "ProcessTier",
    "ResolutionAttempt",
    "check_dispute_window",
    "check_resolution_attempt",
]
