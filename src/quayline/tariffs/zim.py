"""Issue 25: what we hold for ZIM, which is rules without rates.

The problem, stated once: **ZIM's rules verify but its per-port rate to tier
mapping did not survive extraction.** A plausible wrong rate is worse than a hole,
so the rates are marked UNVERIFIED and the resolver returns nothing for them. What
is recorded here is what survived: the rules, the triggers, the service
distinction, and the structure.

Two triggers, no norm

Detention free time begins on the day of **interchange**. Rail demurrage free time
begins the **day following discharge**. Two different triggers in one tariff, which
is recorded here as evidence that there is no industry norm to default to. A
module that assumed one trigger for both would be wrong on half the charges, and
the wrong half would depend on the equipment.

The service string decides the day basis

Charge days are calendar, including weekends and holidays, for Standard service.
Expedited and Fast services calculate in working days. So the service string is a
**required input** for the charge basis: without it there is no way to know
whether a Saturday counts, and a Saturday counted wrong is a day wrong in every
direction downstream.

Rail is two invoices

Rail demurrage is carrier-only and rail operators invoice storage separately. Same
double-invoice structure as MSC, and the same rule applies: deduplicate before
disputing, or double-count and lose credibility.

The calculator disclaims itself

ZIM's calculator states that the final issued invoice shall prevail and supersede
any prior calculations or displayed amounts. So a figure produced by the
calculator is not a rate we hold, it is a number the carrier has already reserved
the right to contradict. Recorded here so nobody treats a calculator output as a
transcribed schedule.

Source: usa-dd-rate-tables-effective-2025-04-20.pdf, rules ZIMU-136-003, 136-004,
136-005.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: The source. Named, because the rules below verify against it and the rates do
#: not survive from it, and those are two different facts about one document.
SOURCE_PDF = "usa-dd-rate-tables-effective-2025-04-20.pdf"

#: The rules that verify.
RULES = ("ZIMU-136-003", "ZIMU-136-004", "ZIMU-136-005")


class Service(StrEnum):
    """The service string, which decides the day basis.

    Required, not defaulted. Standard is calendar days including weekends and
    holidays; Expedited and Fast are working days. A caller that does not know the
    service string does not know whether a Saturday counts, and there is no safe
    default: assuming calendar overcharges working-day services and assuming
    working-day undercharges calendar ones.
    """

    STANDARD = "standard"
    EXPEDITED = "expedited"
    FAST = "fast"


class ClockTrigger(StrEnum):
    """When free time starts, which differs by charge kind.

    Recorded as evidence that there is no industry norm. Detention begins on the
    day of interchange. Rail demurrage begins the day following discharge. One
    tariff, two triggers, and a module that assumed one would be wrong on half the
    charges.
    """

    INTERCHANGE = "day of interchange"
    DAY_AFTER_DISCHARGE = "day following discharge"


#: Which trigger starts which clock. The table is the point: two rows that refuse
#: to be one rule.
TRIGGER_BY_CHARGE: dict[str, ClockTrigger] = {
    "detention": ClockTrigger.INTERCHANGE,
    "rail_demurrage": ClockTrigger.DAY_AFTER_DISCHARGE,
}


@dataclass(frozen=True, slots=True)
class ChargeBasis:
    """The day basis for a ZIM charge, once the service string is known."""

    service: Service
    calendar_days: bool

    @property
    def basis(self) -> str:
        return "calendar, including weekends and holidays" if self.calendar_days else "working days"


def charge_basis(service: Service | None) -> ChargeBasis | None:
    """The day basis, or None when the service string is absent.

    Returns None rather than raising, because an unknown service string is the
    normal state of an invoice that does not name it, and an error would stop an
    audit that has other findings worth making. None means "cannot determine",
    which is a hole, not a failure.
    """
    if service is None:
        return None
    return ChargeBasis(service=service, calendar_days=service is Service.STANDARD)


@dataclass(frozen=True, slots=True)
class RailStructure:
    """The double-invoice structure, documented so it is checked.

    ZIM rail demurrage is carrier-only. The rail operator invoices storage
    separately. Dispute the carrier invoice without checking for the operator
    invoice and the same container is priced twice.
    """

    carrier_bills: str = "rail demurrage only"
    operator_bills: str = "storage, separately invoiced"

    def reminds_to_deduplicate(self) -> str:
        return (
            f"ZIM bills {self.carrier_bills}; the rail operator bills "
            f"{self.operator_bills}. Check for the operator invoice before disputing "
            f"the carrier one, or double-count and lose credibility."
        )


__all__ = [
    "RULES",
    "SOURCE_PDF",
    "TRIGGER_BY_CHARGE",
    "ChargeBasis",
    "ClockTrigger",
    "RailStructure",
    "Service",
    "charge_basis",
]
