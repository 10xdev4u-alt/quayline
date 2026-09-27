"""46 CFR 541.7 and 541.8: the three thirty day clocks, and the dates they run from.

Part 541 contains three separate thirty day periods. They look identical and they
are anchored to three different things, and confusing them is the single easiest
way to void a claim that would otherwise have been won.

    541.7(a)   the billing party must INVOICE within 30 days of the date the
               charge was last incurred
    541.8(a)   the billed party must REQUEST within at least 30 days of the
               invoice issuance date
    541.8(b)   the billing party must RESOLVE within 30 days of receiving the
               request

Read together with 541.7(b) and (c), an NVOCC chain can run to ninety days, which
is the figure in the issue.

Why the anchors are separate types

Each clock takes an anchor that carries only the date that clock is allowed to
read. 541.7(a) cannot be handed an invoice date, and 541.8(a) cannot be handed a
cargo date, because the types do not permit it. This is deliberate, and the
alternative was tried first and is worse.

The two errors this prevents, both of which flip the outcome on real invoices:

The out gate error. Demurrage stops accruing on the last chargeable day, which is
not the day the container left the terminal. A terminal closed over a weekend
means the out gate is Monday while the last chargeable day is Friday. Anchoring
541.7(a) on the out gate hands the carrier the closure days as extra time, and
the mistake is invisible because both dates are plausible and both are on the
paperwork.

The invoice date error. Anchoring 541.7(a) on the invoice issuance date makes the
elapsed time zero by construction, so the invoice is always timely and 541.7(a)
never fires. It is a dead letter rule, and it looks like it is working. A test
asserts precisely that failure so the deadness is on the record.

Both mistakes are more forgiving to the carrier than the regulation is. That is
the direction to be suspicious of, generally, when a computation in this domain
favours the party we are auditing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from quayline.regulation.source import PART_541, SECTION_541_7, SECTION_541_8

DAYS = 30

# "within thirty (30) calendar days from" the anchor. Calendar days, not business
# days, and the regulation adds no holiday or closure allowance. The last day of
# the period is the anchor plus thirty, so issuing on that day is timely.
_PERIOD = timedelta(days=DAYS)


class BillingParty(StrEnum):
    """Who issued the invoice. Determines which subsection governs."""

    OCEAN_CARRIER = "ocean_carrier"
    TERMINAL_OPERATOR = "terminal_operator"
    NVOCC = "nvocc"

    @property
    def governed_by_541_7_b(self) -> bool:
        """Only an NVOCC has its own receipt clock.

        541.7(b) reads "If the billing party is a non-vessel-operating common
        carrier", and that is the whole of the condition. An ocean carrier and a
        terminal operator both run on 541.7(a).
        """
        return self is BillingParty.NVOCC


class Timeliness(StrEnum):
    TIMELY = "timely"
    LATE = "late"


# ---------------------------------------------------------------- anchors
# One type per clock, holding only the date that clock may read.


@dataclass(frozen=True, slots=True)
class ChargeIncurred:
    """541.7(a) and 541.7(d) anchor: the date the charge was last incurred.

    The last chargeable day. Not the out gate, not the vessel discharge, not the
    customs release, and not the invoice date. See the module docstring for what
    each of those substitutions costs.
    """

    last_chargeable_day: date


@dataclass(frozen=True, slots=True)
class InvoiceIssued:
    """541.7(b) and 541.8(a) anchor: an invoice issuance date.

    541.7(b) uses the issuance date of the invoice the NVOCC received. 541.8(a)
    uses the issuance date of the invoice the billed party received. Two different
    invoices in the NVOCC case, hence two separate values in the chain below.
    """

    issuance_date: date


@dataclass(frozen=True, slots=True)
class RequestReceived:
    """541.8(b) anchor: the date the billing party received the request."""

    day: date


@dataclass(frozen=True, slots=True)
class DisputeNotice:
    """541.7(c) anchor: the date the NVOCC notified its billing party.

    ARGUABLE. 541.7(c) says the NVOCC's billing party "must then provide an
    additional thirty (30) calendar days for the NVOCC to dispute the charge
    upon this notice". Read one way the thirty days runs from the notice date,
    which is how it is modelled. Read another way it extends the NVOCC's own
    541.7(b) deadline. The text does not say which, and the difference is real
    money. Treated as arguable until it is adjudicated, per AGENTS.md section
    five.
    """

    day: date


# ---------------------------------------------------------------- the clocks


def invoice_deadline(charge_incurred: ChargeIncurred) -> date:
    """541.7(a). The last day a billing party may issue the invoice.

    Applies to an ocean carrier and a terminal operator, and to the ocean
    carrier's invoice to an NVOCC.
    """
    return charge_incurred.last_chargeable_day + _PERIOD


def reissue_deadline(charge_incurred: ChargeIncurred) -> date:
    """541.7(d). The last day a corrected invoice may issue.

    Identical to 541.7(a), and that is the point. 541.7(d) permits a billing
    party to reissue to the correct billed party, but only "provided that such
    issuance is within thirty (30) calendar days from the date on which the
    charge was last incurred". Reissuing does not restart the clock and does not
    grant thirty days from the reissue.
    """
    return invoice_deadline(charge_incurred)


def nvocc_invoice_deadline(carrier_invoice: InvoiceIssued) -> date:
    """541.7(b). An NVOCC's own deadline to invoice its billed party.

    Measured from the issuance date of the carrier invoice it received, not from
    the charge. This is the second layer of the chain and it is why an NVOCC
    invoice can arrive ninety days after the container left.
    """
    return carrier_invoice.issuance_date + _PERIOD


def nvocc_extension(dm1_notice: DisputeNotice) -> date:
    """541.7(c). The additional thirty days, running from the NVOCC's notice.

    ARGUABLE, see DisputeNotice. Note also that this extends the NVOCC's window
    to dispute; it does not extend the ocean carrier's own 541.7(a) deadline,
    which expired long before.
    """
    return dm1_notice.day + _PERIOD


def dispute_request_deadline(invoice: InvoiceIssued) -> date:
    """541.8(a). The last day the billed party may request mitigation.

    Anchored on the invoice issuance date as printed on the document, which is
    the one date on an invoice the carrier cannot choose after the fact. Never
    anchor this on a cargo date. A carrier who invoices late has already failed
    541.7(a); the mitigation window is a separate entitlement and it runs from
    the invoice, not from the cargo.
    """
    return invoice.issuance_date + _PERIOD


def resolution_deadline(request: RequestReceived) -> date:
    """541.8(b). The last day the billing party must attempt to resolve.

    "Must attempt to resolve", not "must resolve", and 541.8(b) expressly allows
    a later date "as agreed upon by both parties". So this is a deadline for the
    attempt, not a guarantee of a refund.
    """
    return request.day + _PERIOD


# ---------------------------------------------------------------- outcomes


def assess(
    charge_incurred: ChargeIncurred, issued: InvoiceIssued, party: BillingParty
) -> Timeliness:
    """Whether an invoice met the deadline that governs its issuer.

    For an NVOCC the governing subsection is 541.7(b) and the anchor is the
    carrier invoice it received, which is not the value this function is given.
    Callers holding an NVOCC chain should use :func:`assess_chain`, which knows
    about the two layers. This function exists so that 541.7(a) and 541.7(b)
    cannot be confused by accident, since answering with the wrong one produces a
    confident wrong answer rather than an error.
    """
    if party.governed_by_541_7_b:
        raise ValueError(
            "an NVOCC runs on 541.7(b), measured from the carrier invoice it received, "
            "not on the date the charge was incurred. Use assess_chain."
        )
    return (
        Timeliness.TIMELY
        if issued.issuance_date <= invoice_deadline(charge_incurred)
        else Timeliness.LATE
    )


@dataclass(frozen=True, slots=True)
class NvoccChain:
    """The two layer invoice chain in 541.7(a) and (b), plus the (c) extension.

    carrier_invoice is the ocean carrier's invoice to the NVOCC. nvocc_invoice is
    the NVOCC's invoice to its billed party. notice is the NVOCC's 541.7(c)
    notification, if it sent one.
    """

    charge_incurred: ChargeIncurred
    carrier_invoice: InvoiceIssued
    nvocc_invoice: InvoiceIssued
    notice: DisputeNotice | None = None

    def carrier_timeliness(self) -> Timeliness:
        """541.7(a). The ocean carrier's obligation, from the charge."""
        return (
            Timeliness.TIMELY
            if self.carrier_invoice.issuance_date <= invoice_deadline(self.charge_incurred)
            else Timeliness.LATE
        )

    def nvocc_timeliness(self) -> Timeliness:
        """541.7(b). The NVOCC's obligation, from the carrier invoice it received.

        The NVOCC gets thirty days from receipt regardless of how long the carrier
        took. A carrier that invoiced late has not given the NVOCC more time, and
        a NVOCC that billed within thirty of receipt met 541.7(b) even though the
        chain as a whole took longer than thirty days from the charge.
        """
        return (
            Timeliness.TIMELY
            if self.nvocc_invoice.issuance_date <= nvocc_invoice_deadline(self.carrier_invoice)
            else Timeliness.LATE
        )

    def dispute_deadline(self) -> date:
        """The NVOCC's outer limit to dispute, once 541.7(c) is taken into account.

        Without a notice the NVOCC's window is its 541.8(a) mitigation window on
        the invoice it issued. With a notice, 541.7(c) provides the additional
        thirty days, and the later of the two governs. ARGUABLE, see
        :class:`DisputeNotice`.
        """
        base = dispute_request_deadline(self.nvocc_invoice)
        if self.notice is None:
            return base
        return max(base, nvocc_extension(self.notice))

    def total_elapsed_days(self) -> int:
        """Days from the last chargeable day to the NVOCC's invoice.

        The figure that makes the ninety day chain concrete, and the number a
        carrier will quote to suggest the charge is stale. It is not a deadline
        by itself: 541.7 is satisfied or not satisfied per layer, and the NVOCC
        layer is measured from receipt.
        """
        return (self.nvocc_invoice.issuance_date - self.charge_incurred.last_chargeable_day).days


def assess_chain(chain: NvoccChain) -> Timeliness:
    """Worst of the two layers.

    A chain fails if either layer fails. The carrier being timely does not rescue
    a late NVOCC invoice, and an NVOCC being timely on receipt does not rescue a
    late carrier invoice. When 541.7 fails, the billed party is not required to
    pay the charge at all, which is a larger outcome than a mitigation, so the
    layers do not net off against each other.
    """
    if chain.carrier_timeliness() is Timeliness.LATE:
        return Timeliness.LATE
    return chain.nvocc_timeliness()


# ---------------------------------------------------------------- cure rights


@dataclass(frozen=True, slots=True)
class CureRight:
    """A provision letting a billing party remedy its own defect."""

    cite: str
    error_corrected: str
    anchor_type: type[ChargeIncurred]
    resets_clock: bool


# The only one. Read against the whole of Part 541 as of 2026-09-24, whose
# sections are 541.1 purpose, 541.2 scope, 541.3 definitions, 541.4 reserved,
# 541.5 failure to include required information, 541.6 contents of invoice,
# 541.7 issuance, 541.8 mitigation requests, 541.9 to 541.98 reserved, and
# 541.99 an OMB control number.
#
# 541.7(d) is the only provision that authorises a billing party to fix its own
# error by issuing again, and its scope is narrow. It applies "if the billing
# party invoices an incorrect person", which is a misdirected invoice. It does not
# authorise reissuing to cure a missing disclosure.
CURE_RIGHTS: tuple[CureRight, ...] = (
    CureRight(
        cite="541.7(d)",
        error_corrected="invoiced the incorrect person",
        anchor_type=ChargeIncurred,
        resets_clock=False,
    ),
)

# Defects with no cure provision anywhere in the part.
#
# ARGUABLE, and this is the reading most worth having an attorney look at.
# 541.5 eliminates the obligation to pay when a required minimum is missing, and
# it contains no cure clause. 541.7(d) permits reissue only for the wrong
# recipient. The two do not overlap, so on the face of the regulation a carrier
# who realises on day twenty that it omitted the free time allowance has no
# route to repair it, and the obligation is already eliminated.
#
# Marked arguable rather than asserted, because a contrary reading exists: a
# carrier could argue that reissuing a corrected invoice is permitted as a matter
# of general practice, or that 541.5 speaks only to the invoice as issued and
# leaves a corrected one outside its scope. Nothing in the part settles it and no
# decision has been found either way.
UNCURABLE_DEFECTS: tuple[str, ...] = (
    "541.5 failure to include required information",
    "541.6 missing required disclosure",
    "541.7(a) invoice issued late",
    "541.7(b) NVOCC invoice issued late",
    "541.7(c) NVOCC notice not given",
    "541.8 mitigation request refused or ignored",
)

__all__ = [
    "CURE_RIGHTS",
    "DAYS",
    "PART_541",
    "SECTION_541_7",
    "SECTION_541_8",
    "UNCURABLE_DEFECTS",
    "BillingParty",
    "ChargeIncurred",
    "CureRight",
    "DisputeNotice",
    "InvoiceIssued",
    "NvoccChain",
    "RequestReceived",
    "Timeliness",
    "assess",
    "assess_chain",
    "dispute_request_deadline",
    "invoice_deadline",
    "nvocc_extension",
    "nvocc_invoice_deadline",
    "reissue_deadline",
    "resolution_deadline",
    "timedelta",
]
