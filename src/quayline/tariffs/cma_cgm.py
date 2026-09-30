"""Issue 19: CMA CGM's demurrage is a bundle, so only the whole line is disputable.

> "In the United States, 'Demurrage' issued at water port locations **includes both
> storage & demurrage charges**, and is applicable to all containers, regardless of
> ownership by merchant or carrier."

You cannot dispute a portion of the line as storage versus demurrage. Only the
whole line. That sentence is the entire module: everything else here is the
machinery that stops a partial storage credit from being proposed, computed, or
quoted.

Why the bundle matters more than it looks

Every other carrier's demurrage line is arguably separable into a terminal storage
component and a carrier equipment component, and the duplication challenge in
issue 21 lives in exactly that seam. CMA CGM closes the seam by definition: the
line *is* both, so there is nothing to split. A check that proposes "credit the
storage portion" on a CMA CGM line is not aggressive, it is incoherent, and the
respondent's reply writes itself.

What is transcribed and what is not

Baltimore from 2026-02-22 is **verified**: 4 free days, tier 1 at $305. The
generic national block is **UNVERIFIED**: US standard at 4 free working days then
$285, $345, $385, and reefer at 2 free days demurrage and $500 to $600 per day,
both without the day ranges that would make them contiguous tiers and both from a
tariff whose Baltimore exception is the only part independently confirmed.

So Baltimore resolves and the generic block does not. That asymmetry is deliberate
and it is asserted, because the day a generic transcription lands the asymmetry
should flip loudly rather than silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: Verbatim from the CMA CGM US tariff. Quoted rather than paraphrased because it
#: is the sentence a letter will cite, and the bundle is defined by these words.
BUNDLE_QUOTE = (
    "In the United States, 'Demurrage' issued at water port locations includes both "
    "storage & demurrage charges, and is applicable to all containers, regardless of "
    "ownership by merchant or carrier."
)

#: Baltimore, verified, from 2026-02-22: 4 free days, tier 1 at $305.
BALTIMORE_EFFECTIVE = "2026-02-22"
BALTIMORE_FREE_DAYS = 4
BALTIMORE_TIER_1 = "305"

#: The generic national block is UNVERIFIED. US standard and reefer figures exist
#: in the research without the day ranges that would make them tiers.
GENERIC_STATUS = (
    "UNVERIFIED: US standard (4 free working days, then $285, $345, $385) and "
    "reefer (2 free demurrage, $500-$600/day) lack transcribed day ranges. "
    "Baltimore tier 1 at $305 from 2026-02-22 is the only verified CMA CGM rate."
)


@dataclass(frozen=True, slots=True)
class BundleLine:
    """A CMA CGM demurrage line, which is storage and demurrage together."""

    invoice_ref: str
    amount: str
    verified: bool = True

    def storage_portion(self) -> None:
        """There is none to compute. The method exists so the refusal is explicit
        rather than an AttributeError, because an AttributeError reads as "not yet
        implemented" and this is "never"."""
        raise NotImplementedError(
            "CMA CGM demurrage bundles storage and demurrage by tariff definition. "
            "There is no storage portion to compute. Dispute the whole line or do "
            "not dispute it."
        )


def validate_credit(line: BundleLine, amount: str) -> None:
    """Refuse a partial storage credit on a CMA CGM line.

    Raises rather than returning False, because a proposed credit that reaches this
    function is already halfway into a letter, and a boolean invites the caller to
    handle it gracefully. There is nothing graceful about crediting part of a
    bundle: the whole line or nothing.
    """
    if Decimal(amount) != Decimal(line.amount):
        msg = (
            f"partial storage credit of {amount} against a CMA CGM line of "
            f"{line.amount}. {BUNDLE_QUOTE} Only the whole line is disputable."
        )
        raise ValueError(msg)


def baltimore_tier_1() -> dict[str, str]:
    """The one verified CMA CGM rate, as data rather than prose."""
    return {
        "cluster": "Baltimore SeaGirt",
        "free_days": str(BALTIMORE_FREE_DAYS),
        "tier_1_rate": BALTIMORE_TIER_1,
        "effective": BALTIMORE_EFFECTIVE,
        "verified": "true",
    }


def generic_status() -> str:
    """The generic block's standing, in one string a report can print."""
    return GENERIC_STATUS


#: Rail ramps invert the usual pattern: demurrage free time in working days,
#: detention free time in calendar days. Ten free working days demurrage, the most
#: generous allowance found, against three to four at ocean terminals. Seven free
#: calendar days detention. No rates transcribed for either, so structure without
#: pricing, like the Hapag schedules in issue 13.
RAIL_DEMURRAGE_FREE_DAYS = 10
RAIL_DETENTION_FREE_DAYS = 7


def rail_allowance() -> dict[str, object]:
    """The rail inversion, as data. Ten working days demurrage, seven calendar
    days detention, no rates."""
    return {
        "demurrage_free_days": RAIL_DEMURRAGE_FREE_DAYS,
        "demurrage_unit": "working days",
        "detention_free_days": RAIL_DETENTION_FREE_DAYS,
        "detention_unit": "calendar days",
        "verified_rates": False,
    }


__all__ = [
    "BALTIMORE_EFFECTIVE",
    "BALTIMORE_FREE_DAYS",
    "BALTIMORE_TIER_1",
    "BUNDLE_QUOTE",
    "GENERIC_STATUS",
    "RAIL_DEMURRAGE_FREE_DAYS",
    "RAIL_DETENTION_FREE_DAYS",
    "BundleLine",
    "baltimore_tier_1",
    "generic_status",
    "rail_allowance",
    "validate_credit",
]
