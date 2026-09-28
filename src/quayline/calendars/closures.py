"""Closure types, and the policies that say which ones a carrier forgives.

A closure is not a boolean and the carriers do not treat it as one. The cheapest
possible model, "the terminal was shut so the day was not charged", is wrong for
every carrier in the category, and wrong in a direction that is expensive:

    Hapag-Lloyd forgives an UNSCHEDULED shutout even after free time has expired,
    and charges a SCHEDULED closure. Same closed gate, opposite treatment.

    Maersk forgives nothing, ever, and a day a terminal closed for lack of
    appointment demand still counts as a working day unless the party had made an
    appointment.

    CMA CGM in California forgives the lot.

A boolean cannot hold those three, and neither can a set that does not distinguish
the two windows a closure can act in.

The two windows, and why both exist

    extends_free_time         a closure here pushes the end of the free time
                              allowance out, so the container is not charged
    excluded_after_free_time  a closure here is still forgiven once the allowance
                              is spent

They are not the same set for any carrier we have verified, and Hapag is the
clearest case. Bank holidays and shutout days extend free time, and a scheduled
closure does too. Only an unscheduled shutout survives past the point where free
time is gone, because that is the only one of the four that the carrier could not
have planned for. A terminal that published its holiday schedule has made the
closure its own, and after the allowance is spent the carrier bills calendar days.

The consequence for a dispute

A Hapag Saturday in the post free time window is charged. An unscheduled shutout
in the same window is not. So the winning argument on a Hapag demurrage bill is
frequently not about the rate or the free time arithmetic at all. It is about one
specific day, and whether it was the terminal's fault or the carrier's, and the
only way to tell them apart is to know which kind of closure it was.

That is the whole reason this is a typed set and not a flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClosureType(StrEnum):
    """What kind of closure it was.

    The distinction that matters most is between a closure the carrier planned and
    one it did not, so SCHEDULED_CLOSURE and UNSCHEDULED_SHUTOUT are separate
    members rather than a flag on a shutout. Maersk's own words draw the line by
    cause, not by notice: lack of appointment demand is chargeable, a gate that
    was not open when the party arrived is not.
    """

    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    SCHEDULED_CLOSURE = "scheduled_closure"
    UNSCHEDULED_SHUTOUT = "unscheduled_shutout"
    APPOINTMENT_UNAVAILABLE = "appointment_unavailable"
    CUSTOM = "custom"


ALL_CLOSURE_TYPES = tuple(ClosureType)


@dataclass(frozen=True, slots=True)
class ClosurePolicy:
    """Which closures a carrier forgives, in each of the two windows.

    ``extends_free_time`` is the set forgiven while free time remains.
    ``excluded_after_free_time`` is the set still forgiven once it is spent.

    Both are sets of :class:`ClosureType`, never a bool. There is no honest
    encoding of these three carriers' rules as a bool, and writing one would mean
    dropping the Hapag scheduled/unscheduled distinction, which is the single most
    valuable distinction in this module.
    """

    name: str
    extends_free_time: frozenset[ClosureType]
    excluded_after_free_time: frozenset[ClosureType]
    source: str
    citation: str
    verified: bool

    def forgives(self, closure: ClosureType, *, after_free_time: bool = False) -> bool:
        """Whether this carrier does not charge for a day of this kind.

        ``after_free_time`` selects the window. The default is the free time
        window because a day inside the allowance is not chargeable by anyone, and
        asking about it is usually a caller checking its own arithmetic.
        """
        forgiven = self.excluded_after_free_time if after_free_time else self.extends_free_time
        return closure in forgiven

    def unmentioned_types(self) -> frozenset[ClosureType]:
        """Closure types this policy says nothing about.

        Present so an unmodelled type is visible rather than silently charged. A
        policy that forgives nothing and says nothing is Maersk's position and it
        is a position, but a new type should never arrive as a default.
        """
        named = self.extends_free_time | self.excluded_after_free_time
        return frozenset(ALL_CLOSURE_TYPES) - named


# Verbatim from the Hapag-Lloyd Detention and Demurrage Tariff Guide for the
# United States, October 1 2024 edition:
#   "Any unscheduled closures of relevant terminals and depots will be treated as
#    unforeseen shutout days and will be excluded from Detention and Demurrage
#    charge assessments."
# Hapag is the only carrier we have verified forgiving a closure after free time
# has expired, and only for the unplanned kind. Scheduled closures are charged.
HAPAG_US = ClosurePolicy(
    name="Hapag-Lloyd US",
    extends_free_time=frozenset(
        {
            ClosureType.HOLIDAY,
            ClosureType.SCHEDULED_CLOSURE,
            ClosureType.UNSCHEDULED_SHUTOUT,
        }
    ),
    excluded_after_free_time=frozenset({ClosureType.UNSCHEDULED_SHUTOUT}),
    source="Hapag-Lloyd D&D Guide USA, October 1 2024",
    citation=(
        "Any unscheduled closures of relevant terminals and depots will be treated as "
        "unforeseen shutout days and will be excluded from Detention and Demurrage charge "
        "assessments."
    ),
    verified=True,
)

# Verbatim from the Maersk tariff working day definition:
#   "Working Day basis defined as any day a gate is open for container pickup
#    Monday - Saturday. Partial day closures are considered as a full working day
#    and count towards freetime. In the event a terminal closes on a day due to
#    lack of appointment demand, that day shall be considered a working day for
#    containers a party had an opportunity to make a timely appointment for, but
#    chose not to do so. If a party made an appointment for a container but the
#    terminal was closed, then that date shall not be considered a Working Day."
#
# The last sentence is APPOINTMENT_UNAVAILABLE forgiven, and the second to last is
# the reason it is the only forgiven type. Maersk forgives a closure you booked into
# and nothing else, including its own scheduled ones.
MAERSK_US = ClosurePolicy(
    name="Maersk US",
    extends_free_time=frozenset({ClosureType.APPOINTMENT_UNAVAILABLE}),
    excluded_after_free_time=frozenset(),
    source="Maersk US demurrage tariff, working day definition",
    citation=(
        "If a party made an appointment for a container but the terminal was closed, then "
        "that date shall not be considered a Working Day with respect to that container."
    ),
    verified=True,
)

# CMA CGM already billed on a calendar day basis before the FMC rule, and its
# California gateway carries a carve out from the calendar day basis. UNVERIFIED
# as a closure policy: the carve out is recorded in the research corpus from the
# tariff and issue 20 owns it, but no CMA CGM clause stating a closure policy has
# been transcribed. Carried because the issue asks for it and because shipping a
# hole is cheaper than shipping a guess.
CMA_CGM_US_CALIFORNIA = ClosurePolicy(
    name="CMA CGM US, California gateway",
    extends_free_time=frozenset(ALL_CLOSURE_TYPES),
    excluded_after_free_time=frozenset(ALL_CLOSURE_TYPES),
    source="UNVERIFIED, not transcribed. See issue 20",
    citation=(
        "UNVERIFIED: CMA CGM forgives every closure type at its California gateways. The "
        "California carve out is in our research corpus from the tariff, but no clause "
        "stating it has been transcribed from the carrier's own document."
    ),
    verified=False,
)

POLICIES: dict[str, ClosurePolicy] = {
    p.name: p for p in (HAPAG_US, MAERSK_US, CMA_CGM_US_CALIFORNIA)
}

__all__ = [
    "ALL_CLOSURE_TYPES",
    "CMA_CGM_US_CALIFORNIA",
    "HAPAG_US",
    "MAERSK_US",
    "POLICIES",
    "ClosurePolicy",
    "ClosureType",
]
