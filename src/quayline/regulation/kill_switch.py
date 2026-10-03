"""46 CFR 541.5, the kill switch, and the reason it is shaped the way it is.

The regulation is one sentence and it is stronger than it first reads.

    Failure to include any of the required minimum information in this part in a
    demurrage or detention invoice eliminates any obligation of the billed party
    to pay the applicable charge.

Not a discount, not a right to mitigation, not a defence to be argued on the
merits. Elimination. The charge is not owed.

That produces an asymmetry which is easy to get backwards, and getting it
backwards inverts the legal theory of the whole product.

    An invoice that is arithmetically perfect and missing one disclosure
    is not owed at all.

    An invoice that is overstated by half and discloses everything required
    is owed, unless it is defeated on some other ground.

541.5 is a disclosure rule wearing a liability rule's clothes. It is never an
arithmetic rule. A checker that computed the correct charge, noticed a
discrepancy, and reported "not owed" would be applying a defence the billed
party does not have, while throwing away the one it always does.

So the distinction is enforced in the types rather than in the docstring.
``effect_of`` accepts omissions and returns an obligation. There is no
parameter through which a billed amount, a computed amount, or a discrepancy
could arrive, so no caller can key the kill switch to inaccuracy even by
accident. A later issue adds arithmetic. It does not add it here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from quayline.regulation.checklist import ChecklistField


@dataclass(frozen=True, slots=True)
class Omission:
    """A required disclosure that is absent from an invoice.

    This is the only thing that can trigger 541.5. There is deliberately no
    variant of this type that carries a disputed amount, because there is no
    reading of 541.5 under which an amount would matter.
    """

    field: ChecklistField
    invoice_ref: str

    @property
    def cite(self) -> str:
        return self.field.cite

    def describe(self) -> str:
        """A line for a dispute letter, naming the clause and the invoice."""
        return f"{self.field.cite} {self.field.statement} is not stated on {self.invoice_ref}"


class Obligation(StrEnum):
    """What 541.5 has to say about an invoice.

    INTACT means 541.5 is silent, not that the charge is valid. An intact
    charge may still be overstated, still be time barred under 541.7, or still
    be disputed on the merits. Those are separate grounds and separate modules.
    """

    ELIMINATED = "eliminated"
    INTACT = "intact"


def effect_of(omissions: Iterable[Omission]) -> Obligation:
    """Apply 541.5 to the omissions found on an invoice.

    "Failure to include any of the required minimum information" is disjunctive.
    One missing disclosure is enough, so the first omission decides the result
    and the rest are irrelevant to it. They still matter to a dispute letter,
    which is why the caller keeps the full list.
    """
    for _ in omissions:
        return Obligation.ELIMINATED
    return Obligation.INTACT


def consequence_text() -> str:
    """What 541.5 does when a required minimum is missing, in one sentence.

    Lives here rather than in a page template, for one reason: a renderer that types
    the consequence into its own markup is a renderer that will still be claiming it
    after the rule changes. Issue 207 found the result page showing the word
    "automatic" in a column with nothing saying what it automates, which is the kind
    of omission no test can see and every reader can.

    The wording is the regulation's own shape. 541.5 says failure to include any
    required minimum eliminates the obligation to pay, and it says nothing about cure or
    prejudice, so the sentence does not invent either.
    """
    return (
        "46 CFR 541.5: where a required minimum is missing from a demurrage or "
        "detention invoice, the obligation to pay the applicable charge is "
        "eliminated. There is no cure period and no showing of prejudice, so this "
        "does not depend on arguing that anyone was harmed."
    )
