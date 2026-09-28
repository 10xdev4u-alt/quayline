"""The timing disclosures from 46 CFR 541.6(b), as the carrier stated them.

Only the eight timing clauses, because those are the ones that make a charge
recomputable from the invoice alone. The identifying disclosures in (a) and the rate
disclosures in (c) are separate issues and are not here, which is deliberate: a
module that can recompute a day count without a tariff lookup is the highest yield
check in the product, and adding a required field to it is how it stops being one.

Nothing here is a corrected value. Every field is what the carrier wrote, including
when that is wrong, and a field that has been silently repaired cannot be used to
dispute the carrier, because the audit no longer knows what it was auditing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quayline.regulation import Trade

CITE_ALLOWANCE = "541.6(b)(3)"
CITE_FREE_TIME_START = "541.6(b)(4)"
CITE_FREE_TIME_END = "541.6(b)(5)"
CITE_AVAILABILITY = "541.6(b)(6)"
CITE_RETURN_DATE = "541.6(b)(7)"
CITE_CHARGED_DATES = "541.6(b)(8)"

# The five fields a day count cannot be recomputed without, mapped to their cites.
# Kept as a table so the engine can quote a clause for every field it relies on and
# a test can assert no field is missing from it.
REQUIRED_FOR_RECOMPUTATION: dict[str, str] = {
    "allowed_free_time_days": CITE_ALLOWANCE,
    "free_time_start": CITE_FREE_TIME_START,
    "charged_dates": CITE_CHARGED_DATES,
}


@dataclass(frozen=True, slots=True)
class TimingDisclosures:
    """What 46 CFR 541.6(b) requires the carrier to state, as stated.

    ``charged_dates`` is a frozenset because the clauses ask for "the specific
    date(s) for which demurrage and/or detention were charged", and a carrier
    listing a date twice is a different defect from a carrier charging a day it
    should not have. Duplicates are rejected by the type, which is deliberate: the
    duplicate case belongs to the arithmetic issue and is not a day set problem.
    """

    invoice_date: date
    allowed_free_time_days: int
    free_time_start: date
    free_time_end: date
    charged_dates: frozenset[date]
    trade: Trade = Trade.IMPORT
    availability_date: date | None = None
    earliest_return_date: date | None = None

    def __post_init__(self) -> None:
        if self.allowed_free_time_days < 1:
            raise ValueError(
                f"541.6(b)(3) requires an allowance of at least one day, got "
                f"{self.allowed_free_time_days}"
            )
        if self.free_time_end < self.free_time_start:
            raise ValueError(
                f"{CITE_FREE_TIME_END} precedes {CITE_FREE_TIME_START}: "
                f"{self.free_time_end} before {self.free_time_start}"
            )
        if not self.charged_dates:
            raise ValueError(
                f"{CITE_CHARGED_DATES} discloses no dates, so the invoice is charging for "
                f"something it will not name"
            )
        if self.trade is Trade.IMPORT and self.availability_date is None:
            raise ValueError(
                f"{CITE_AVAILABILITY} is required for an import invoice and was not given"
            )

    @property
    def first_charged_day(self) -> date:
        return min(self.charged_dates)

    @property
    def last_charged_day(self) -> date:
        return max(self.charged_dates)

    @property
    def bill_span(self) -> tuple[date, date]:
        return self.first_charged_day, self.last_charged_day


__all__ = [
    "CITE_ALLOWANCE",
    "CITE_AVAILABILITY",
    "CITE_CHARGED_DATES",
    "CITE_FREE_TIME_END",
    "CITE_FREE_TIME_START",
    "CITE_RETURN_DATE",
    "REQUIRED_FOR_RECOMPUTATION",
    "TimingDisclosures",
]
