"""Issue 7: the three things a complainant must show, per day, per charge.

*Evergreen Shipping Agency v. FMC*, 106 F.4th 1113 (D.C. Cir. 2024). For each
shipment, each date, and each charge, the complainant must show:

1. Unable to pick up or return on that specific date.
2. The reason was outside their control.
3. The charge could not have incentivized earlier return.

**Element three is the one shippers skip, and it is where a complaint dies.** The
court held the incentive principle is not a bright-line rule and does not replace
the general reasonableness standard. A shipper that proves it could not move the
box and that the reason was a port closure has proved two thirds of nothing, because
the question the court asks third is whether the charge, as priced, could have made
any difference to when the box moved.

Why element three is hard

Elements one and two are facts about the world. The gate was closed, the
appointment system was down, the chassis pool was empty. Element three is a
counterfactual about incentives: given the charge as priced, could the shipper
have moved the box earlier, and would the price have changed the decision?

That is a harder sentence to write, which is why it gets skipped, and a skipped
third element is not a weaker claim, it is an incomplete one. The packet rule in
this module is therefore not "element three required" but "element three required
or flagged": a day may be claimed with the third element unmet, but only with the
gap named on the face of the claim, so nobody files it believing it is complete.

What the assessment records

Each element is a dated, sourced statement or it is absent. "Unable to pick up"
with no date is not element one, it is a complaint about the general situation.
"The port was congested" with no source is not element two, it is an allegation.
And element three is marked required in the type, which means a `DayAssessment`
that lacks it is constructible but not claimable without the flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Element:
    """One of the three, with its evidence or its absence.

    `met` is True only when `evidence` names a dated, sourced record. An element
    whose evidence is "the terminal was congested" is not met, and the constructor
    does not check that because the constructor cannot read English. What it does
    check is that a met element carries a non-empty evidence string, so "met with
    nothing behind it" is unrepresentable.
    """

    met: bool
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.met and not self.evidence.strip():
            msg = (
                "an element marked met with no evidence is a claim with nothing "
                "behind it. Either name the record or leave the element unmet."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DayAssessment:
    """The three elements for one date and one charge.

    `element_three_required` defaults True, because the third element is the one
    shippers skip and a default that silently waived it would reproduce the exact
    failure this module exists to stop. Setting it False is a deliberate act with a
    name on it, for the rare charge where incentive analysis genuinely does not
    apply.
    """

    day: date
    charge_ref: str
    unable_to_move: Element
    outside_control: Element
    no_incentive_effect: Element
    element_three_required: bool = True

    @property
    def complete(self) -> bool:
        """All three met, or the third waived."""
        if not (self.unable_to_move.met and self.outside_control.met):
            return False
        return not (self.element_three_required and not self.no_incentive_effect.met)

    @property
    def third_unmet(self) -> bool:
        """Elements one and two met, three required and unmet.

        The exact shape of the failure the issue names: a day that looks claimable
        until the third question is asked.
        """
        return (
            self.unable_to_move.met
            and self.outside_control.met
            and self.element_three_required
            and not self.no_incentive_effect.met
        )

    def flag(self) -> str:
        """The gap named on the face of the claim, or empty when complete."""
        if self.complete:
            return ""
        missing = []
        if not self.unable_to_move.met:
            missing.append("element 1 (unable to move on this date)")
        if not self.outside_control.met:
            missing.append("element 2 (reason outside control)")
        if self.third_unmet:
            missing.append(
                "element 3 (the charge could not have incentivized earlier return). "
                "This is the element shippers skip and where complaints die."
            )
        return (
            f"{self.day.isoformat()} {self.charge_ref}: incomplete Evergreen showing, "
            f"missing {'; '.join(missing)}."
        )


def claimable_days(
    assessments: tuple[DayAssessment, ...], *, allow_flagged: bool = False
) -> tuple[DayAssessment, ...]:
    """The days a packet may claim.

    Complete assessments always pass. Incomplete ones pass only with
    `allow_flagged`, and then only with their flag attached by the caller. The
    default refuses, because the default is what runs when nobody thought about
    it, and an unflagged incomplete day in a letter is a day the respondent will
    dismantle first.
    """
    if allow_flagged:
        return assessments
    return tuple(a for a in assessments if a.complete)


def third_element_gaps(assessments: tuple[DayAssessment, ...]) -> tuple[DayAssessment, ...]:
    """Days meeting one and two but not three. The failure mode, named."""
    return tuple(a for a in assessments if a.third_unmet)


__all__ = [
    "DayAssessment",
    "Element",
    "claimable_days",
    "third_element_gaps",
]
