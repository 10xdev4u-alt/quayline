"""46 CFR 545.5, the reasonableness factors, and the three checks built on them.

545.5 is the standard the carrier defends against, so the factors have to be encoded
with their real force rather than flattened into a list of reasons to complain. The
verbs in the rule are not interchangeable and the difference decides whether a
dispute letter holds up.

    545.5(c)(1)     the Commission "will consider"          a standard
    545.5(c)(2)(ii) detention that does not serve its purpose
                    "are likely to be found unreasonable"  the strongest language
                                                                in the section
    545.5(c)(2)(i)  the Commission "may consider"           a factor
    545.5(c)(2)(iii) the Commission "may consider"          a factor
    545.5(c)(2)(iv) the Commission "may consider"           a factor
    545.5(d)        the Commission "may consider"           a factor
    545.5(e)        the Commission "may consider"           a factor
    545.5(f)        non-preclusion                          nothing follows from a list

Collapsing those into one list would let a dispute letter argue that a factor the
Commission "may consider" is a finding the Commission "will" make. AGENTS.md section
four says a wrong rate in a dispute letter costs more credibility than a missing one
costs recovery, and the same is true of an overstated factor.

A correction to the research corpus

The research note docs/research/001-regulation.md stated that 545.5(c)(2)(iii) means
providing information to contact the terminal for availability does not satisfy the
notice requirement. That is not in the rule. 545.5(c)(2)(iii) says only that the
Commission "may consider the type of notice, to whom notice is provided, the format of
notice, method of distribution of notice, the timing of notice, and the effect of the
notice". The proposition is plausible and is probably supported by FMC adjudication or
a policy statement, but no source was found for it and it is marked UNVERIFIED here and
in the research note rather than asserted.

A dispute letter built on it would have quoted a regulation that does not say it.

What the three checks do

Each returns a finding only when the fact pattern is present, and each finding carries
the verbatim sub-factor so a dispute letter quotes the rule and not the code's summary
of it.

545.5(c)(2)(ii) is the only one that suppresses itself, because the rule opens with
"Absent extenuating circumstances". A check that fires while an extenuating circumstance
is recorded would assert the opposite of what the regulation says.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from quayline.regulation.source import Provenance

SECTION_545_5 = Provenance(
    cite="46 CFR 545.5",
    heading="Interpretation of Shipping Act of 1984, unjust and unreasonable practices",
    as_of="2026-09-24",
    federal_register="89 FR 14378, Feb. 26, 2024",
    effective="2024-05-28",
    url="https://www.ecfr.gov/current/title-46/section-545.5",
)


class Strength(StrEnum):
    """How much force a sub-factor has, taken from its own verb.

    Not a ranking invented by us. Each value is the language the rule uses.
    """

    WILL_CONSIDER = "will consider"
    LIKELY_UNREASONABLE = "are likely to be found unreasonable"
    MAY_CONSIDER = "may consider"


@dataclass(frozen=True, slots=True)
class Factor:
    """One 545.5 sub-factor, verbatim, with the strength the rule gives it."""

    cite: str
    heading: str
    text: str
    strength: Strength

    def quote(self) -> str:
        """A block for a dispute letter: the cite, then the rule as published."""
        return f"{self.cite} {self.heading}: {self.text}"


FACTORS: tuple[Factor, ...] = (
    Factor(
        cite="545.5(c)(1)",
        heading="Incentive principle",
        text="(c) Incentive principle—(1) General. In assessing the reasonableness of demurrage and detention practices and regulations, the Commission will consider the extent to which demurrage and detention are serving their intended primary purposes as financial incentives to promote freight fluidity.",
        strength=Strength.WILL_CONSIDER,
    ),
    Factor(
        cite="545.5(c)(2)(i)",
        heading="Cargo availability",
        text="(2) Particular applications of incentive principle—(i) Cargo availability. The Commission may consider in the reasonableness analysis the extent to which demurrage practices and regulations relate demurrage or free time to cargo availability for retrieval.",
        strength=Strength.MAY_CONSIDER,
    ),
    Factor(
        cite="545.5(c)(2)(ii)",
        heading="Empty container return",
        text="(ii) Empty container return. Absent extenuating circumstances, practices and regulations that provide for imposition of detention when it does not serve its incentivizing purposes, such as when empty containers cannot be returned, are likely to be found unreasonable.",
        strength=Strength.LIKELY_UNREASONABLE,
    ),
    Factor(
        cite="545.5(c)(2)(iii)",
        heading="Notice of cargo availability",
        text="(iii) Notice of cargo availability. In assessing the reasonableness of demurrage practices and regulations, the Commission may consider whether and how regulated entities provide notice to cargo interests that cargo is available for retrieval. The Commission may consider the type of notice, to whom notice is provided, the format of notice, method of distribution of notice, the timing of notice, and the effect of the notice.",
        strength=Strength.MAY_CONSIDER,
    ),
    Factor(
        cite="545.5(c)(2)(iv)",
        heading="Government inspections",
        text="(iv) Government inspections. In assessing the reasonableness of demurrage and detention practices in the context of government inspections, the Commission may consider the extent to which demurrage and detention are serving their intended purposes and may also consider any extenuating circumstances.",
        strength=Strength.MAY_CONSIDER,
    ),
    Factor(
        cite="545.5(d)",
        heading="Demurrage and detention policies",
        text="(d) Demurrage and detention policies. The Commission may consider in the reasonableness analysis the existence, accessibility, content, and clarity of policies implementing demurrage and detention practices and regulations, including dispute resolution policies and practices and regulations regarding demurrage and detention billing. In assessing dispute resolution policies, the Commission may further consider the extent to which they contain information about points of contact, timeframes, and corroboration requirements.",
        strength=Strength.MAY_CONSIDER,
    ),
    Factor(
        cite="545.5(e)",
        heading="Transparent terminology",
        text="(e) Transparent terminology. The Commission may consider in the reasonableness analysis the extent to which regulated entities have clearly defined the terms used in demurrage and detention practices and regulations, the accessibility of definitions, and the extent to which the definitions differ from how the terms are used in other contexts.",
        strength=Strength.MAY_CONSIDER,
    ),
    Factor(
        cite="545.5(f)",
        heading="Non-Preclusion",
        text="(f) Non-Preclusion. Nothing in this rule precludes the Commission from considering factors, arguments, and evidence in addition to those specifically listed in this rule.",
        strength=Strength.MAY_CONSIDER,
    ),
)

_BY_CITE: dict[str, Factor] = {f.cite: f for f in FACTORS}


def factor(cite: str) -> Factor:
    """Look up a sub-factor by cite, for example ``545.5(c)(2)(ii)``."""
    try:
        return _BY_CITE[cite]
    except KeyError:
        raise KeyError(f"no 545.5 factor with cite {cite!r}") from None


@dataclass(frozen=True, slots=True)
class Finding:
    """One check firing, carrying the factor it relies on."""

    factor: Factor
    detail: str

    @property
    def cite(self) -> str:
        return self.factor.cite

    @property
    def strength(self) -> Strength:
        return self.factor.strength

    def describe(self) -> str:
        return f"{self.factor.cite} {self.factor.heading}: {self.detail}"


def detention_without_return_offer(
    detention_charged: bool,
    return_location_offered: bool,
    *,
    extenuating_circumstances: str | None = None,
) -> Finding | None:
    """545.5(c)(2)(ii). Detention charged where the container could not be returned.

    The rule says that absent extenuating circumstances, detention imposed "when it
    does not serve its incentivizing purposes, such as when empty containers cannot
    returned" is likely to be found unreasonable. Note "are likely to be found", which
    is the strongest language anywhere in 545.5, and note the opening clause.

    ``extenuating_circumstances`` is a free text record of why the detention was
    imposed anyway. Supplying one suppresses the finding, because the rule suppresses
    it. A check that fired anyway would assert the opposite of the regulation.
    """
    if extenuating_circumstances is not None:
        return None
    if detention_charged and not return_location_offered:
        return Finding(
            factor=factor("545.5(c)(2)(ii)"),
            detail=(
                "detention was charged and no return location was offered, so the charge "
                "did not serve its incentivizing purpose of promoting freight fluidity"
            ),
        )
    return None


def availability_equals_vessel_arrival(
    availability_date: date, vessel_arrival_date: date
) -> Finding | None:
    """545.5(c)(2)(i). The availability date is the vessel arrival date.

    545.5(c)(2)(i) has the Commission consider the extent to which demurrage relates
    free time to cargo availability for retrieval. An availability date equal to the
    vessel arrival date means the clock is keyed to the vessel schedule rather than
    to the cargo being available, which is the pattern this factor is about.

    Strength is MAY_CONSIDER, not a finding. This is a factor the Commission may
    weigh, and the finding carries that label so a dispute letter cannot present it as
    a determination.

    Strict equality only. A terminal that makes a container available the same day it
    arrives has not committed this practice, and a check loose enough to fire on
    equality plus tolerance would fire on almost every import.
    """
    if availability_date == vessel_arrival_date:
        return Finding(
            factor=factor("545.5(c)(2)(i)"),
            detail=(
                f"container availability date {availability_date.isoformat()} equals the "
                f"vessel arrival date, so free time appears keyed to the vessel schedule "
                f"rather than to cargo availability for retrieval"
            ),
        )
    return None


def no_published_corroboration_spec(specification_published: bool) -> Finding | None:
    """545.5(d). No published corroboration specification.

    545.5(d) has the Commission consider, in assessing dispute resolution policies,
    the extent to which they contain information about points of contact, timeframes,
    and corroboration requirements. A carrier publishing none of the three has a policy
    that is deficient on the face of the factor.

    This is the check that pairs with 541.6(d), which requires the invoice itself to
    carry a contact, a digital means to a published description, and defined
    timeframes. A carrier can satisfy 541.6 and still publish nothing behind it.

    Strength is MAY_CONSIDER. The issue described this as a carrier "scoring as
    unreasonable", which overstates the rule text, and the correction is recorded in
    the research note and in this docstring.
    """
    if not specification_published:
        return Finding(
            factor=factor("545.5(d)"),
            detail=(
                "no published dispute resolution policy stating points of contact, "
                "timeframes, and corroboration requirements was found, so the carrier "
                "cannot be given the opportunity the factor contemplates"
            ),
        )
    return None


# Claims we could not source. Kept in the module so they cannot be asserted from a
# summary of the module instead of from the regulation.
UNVERIFIED_CLAIMS: tuple[str, ...] = (
    "UNVERIFIED: that providing only the terminal's contact details fails to give "
    "notice of cargo availability under 545.5(c)(2)(iii). The rule says the Commission "
    "may consider the type, recipient, format, method, timing and effect of notice, and "
    "nothing more. The proposition may be supported by FMC adjudication or a policy "
    "statement, but no source was found and it is not encoded as a check.",
)


__all__ = [
    "FACTORS",
    "SECTION_545_5",
    "UNVERIFIED_CLAIMS",
    "Factor",
    "Finding",
    "Strength",
    "availability_equals_vessel_arrival",
    "detention_without_return_offer",
    "factor",
    "no_published_corroboration_spec",
]
