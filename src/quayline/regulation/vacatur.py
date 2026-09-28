"""The vacated 541.4, what replaced it, and the statute behind the kill switch.

541.4 was severed and vacated. Any check that keys on it is wrong, and the failure
is silent, because the reasoning still looks correct and only the citation is dead.

    World Shipping Council v. FMC, No. 24-1088, 152 F.4th 215 (D.C. Cir. 2025-09-23)

severed and vacated the section. 90 FR 60580 removed it from the CFR effective
2025-12-29. RIN 3072-AD08, Docket FMC-2025-0107.

What that changed: a wrong party invoice is no longer a per se non-payable defect.
The closed list of who a carrier may invoice disappeared, and a rule built on it
now has no basis. A check that said "this was invoiced to the wrong party, therefore
not owed" was the strongest form of that rule and it is gone.

What survived, and it is the interesting part

541.6(a)(4) is untouched. The carrier must still state "the basis for why the
billed party is the proper party of interest and thus liable for the charge".

So the closed list is gone and the obligation to articulate privity, consignee
status or a contractual pass through is intact. That is the strongest hook available
after the vacatur, and an invoice that names a liable party with no articulated
basis is missing a required minimum under 541.6, which is a 541.5 event.

The distinction worth holding onto: after the vacatur a carrier cannot be faulted
for invoicing the wrong person without more, and it can be faulted for not saying
why that person is liable. Both are true at once and the second is the live one.

The statute behind 541.5, and it is narrower than the regulation

46 U.S.C. 41104(f):

    Failure to include the information required under subsection (d) on an invoice
    with any demurrage or detention charge shall eliminate any obligation of the
    charged party to pay the applicable charge.

Two things. It keys to subsection (d), which is the statutory information list, not
to 541.6, which is the regulatory one. And it is per invoice: "on an invoice with
any demurrage or detention charge", and "the applicable charge". One invoice missing
a disclosure eliminates the obligation for that invoice. It is not a finding about
the carrier, it is not a licence to stop paying that carrier, and it does not
survive the next correctly presented invoice.

Getting that wrong in the customer's favour is a real risk, because "this carrier
once omitted something" is the kind of sentence that ends up in a letter and reads
like a general authorisation to withhold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quayline.regulation.checklist import ChecklistField, by_cite
from quayline.regulation.kill_switch import Omission

# The case that took 541.4 out of the CFR.
VACATUR_CITATION = (
    "World Shipping Council v. FMC, No. 24-1088, 152 F.4th 215 (D.C. Cir. 2025-09-23)"
)
VACATUR_REMOVAL = "90 FR 60580, effective 2025-12-29 (RIN 3072-AD08, Docket FMC-2025-0107)"

# 46 U.S.C. 41104(f), verbatim. The statute the regulation implements.
STATUTE_41104_F = (
    "Failure to include the information required under subsection (d) on an invoice with any "
    "demurrage or detention charge shall eliminate any obligation of the charged party to pay "
    "the applicable charge."
)

LIABILITY_BASIS_CITE = "541.6(a)(4)"


@dataclass(frozen=True, slots=True)
class CaseCitation:
    """One decision, enough to identify it and what it did.

    The docket number is the identity, not the party name. There are two decisions
    named World Shipping Council v. FMC and they are about different rules, so a
    lookup keyed on the party name returns the wrong one. That is a real hazard in
    any citation engine and it is why the subject sits on the record here.
    """

    docket: str
    reported: str | None
    decided: date
    subject: str
    holding: str
    citation_text: str

    def __str__(self) -> str:
        return self.citation_text


# The vacatur. Removes 541.4.
WORLD_SHIPPING_COUNCIL_5414 = CaseCitation(
    docket="No. 24-1088",
    reported="152 F.4th 215",
    decided=date(2025, 9, 23),
    subject="46 CFR 541.4, invoices to a person other than the person liable for the charge",
    holding=(
        "Severed and vacated 541.4. A wrong party invoice is no longer a per se non-payable "
        "defect, because the closed list of who may be invoiced is gone with the section."
    ),
    citation_text=VACATUR_CITATION,
)

# The other World Shipping Council case. Same party, different rule, and it has
# nothing to do with demurrage invoicing.
WORLD_SHIPPING_COUNCIL_5421 = CaseCitation(
    docket="No. 24-1298",
    reported=None,
    decided=date(2026, 3, 31),
    subject="46 CFR 542.1, unreasonable refusal of vessel space",
    holding=(
        "Upheld 46 CFR 542.1 on unreasonable refusal of vessel space. Nothing about demurrage "
        "or detention invoicing. Same named party as the vacatur and a different rule, which "
        "is why the docket number is the identity here."
    ),
    citation_text="World Shipping Council v. FMC, No. 24-1298 (D.C. Cir. 2026-03-31)",
)

# Keyed by docket, never by party name. Two cases, one party name.
CASES_BY_DOCKET: dict[str, CaseCitation] = {
    WORLD_SHIPPING_COUNCIL_5414.docket: WORLD_SHIPPING_COUNCIL_5414,
    WORLD_SHIPPING_COUNCIL_5421.docket: WORLD_SHIPPING_COUNCIL_5421,
}

# The vacated section, kept as a name so a check can refuse it explicitly rather
# than by accident.
VACATED_SECTION = "541.4"


def case_for(docket: str) -> CaseCitation:
    """Look up by docket number. Not by party name, and there is a reason."""
    try:
        return CASES_BY_DOCKET[docket]
    except KeyError:
        raise KeyError(
            f"no recorded case with docket {docket!r}. Held: "
            f"{', '.join(sorted(CASES_BY_DOCKET))}. Note that looking a case up by party "
            f"name returns the wrong one of two."
        ) from None


def refuses_vacated_basis() -> None:
    """Always raises. A wrong party invoice is not a per se non-payable defect.

    A check that keys on the vacated section has no basis, and the reasoning around
    it usually still reads correctly, which is what makes it dangerous. So there is
    no way to ask this module for a 541.4 finding and get one.
    """
    raise VacatedRuleError(
        f"{VACATED_SECTION} was severed and vacated by {VACATUR_CITATION} and removed from "
        f"the CFR by {VACATUR_REMOVAL}. A wrong party invoice is not a per se non-payable "
        f"defect. Use {LIABILITY_BASIS_CITE} instead, which survives: the carrier must "
        f"still state the basis on which the billed party is liable."
    )


class VacatedRuleError(RuntimeError):
    """A check tried to rely on a vacated section."""


@dataclass(frozen=True, slots=True)
class LiabilityFinding:
    """Whether the invoice articulates why the billed party is liable.

    Two outcomes and the difference between them is the whole post-vacatur hook.

    Absent means the disclosure is missing, which is a 541.6 required minimum, which
    is a 541.5 event. That is the strong case and it is the live one.

    Present but conclusory is a different problem. The carrier said something, so
    nothing is missing, so 541.5 does not fire. The argument available is 545.5(d) on
    the clarity of the policy rather than a non-payability claim, and pretending
    otherwise would be arguing a defence that is not there.
    """

    verdict: str
    detail: str
    omission: Omission | None
    field: ChecklistField

    @property
    def eliminates_obligation(self) -> bool:
        """Only the absent case does. A conclusory basis is not a 541.5 event."""
        return self.omission is not None

    def describe(self) -> str:
        if self.omission is not None:
            return f"{LIABILITY_BASIS_CITE} is not stated. {self.detail}"
        return f"{LIABILITY_BASIS_CITE} is stated but not particularised. {self.detail}"


# Words that assert a conclusion without articulating a basis. Kept short on
# purpose: a long list of synonyms is a fuzzy matcher in a dispute letter, and the
# 545.5(d) argument is about the clarity of the policy rather than about matching
# adjectives.
CONCLUSORY_PHRASES: tuple[str, ...] = (
    "as per contract",
    "per our agreement",
    "you are liable",
    "liable for charge",
    "responsible for payment",
    "proper party of interest",
)


def check_liability_basis(basis: str | None, invoice_ref: str = "") -> LiabilityFinding:
    """541.6(a)(4). Is the basis for liability stated, and is it particularised?

    ``basis`` is what the carrier wrote, verbatim, or None if the disclosure is
    missing entirely.
    """
    field = by_cite(LIABILITY_BASIS_CITE)

    if basis is None or not basis.strip():
        return LiabilityFinding(
            verdict="absent",
            detail=(
                "A wrong party invoice is not a per se defect after the vacatur, but the "
                "carrier must still state why this party is liable, and it did not."
            ),
            omission=Omission(field=field, invoice_ref=invoice_ref or "the invoice"),
            field=field,
        )

    lowered = basis.casefold()
    if any(phrase in lowered for phrase in CONCLUSORY_PHRASES):
        return LiabilityFinding(
            verdict="conclusory",
            detail=(
                "The stated basis asserts liability rather than articulating it. Nothing is "
                "missing, so this is not a 541.5 event. It is a 545.5(d) argument about the "
                "clarity of the carrier's policy, and it should not be filed as non-payability."
            ),
            omission=None,
            field=field,
        )

    return LiabilityFinding(
        verdict="particularised",
        detail="The stated basis names a contractual or status basis rather than asserting liability.",
        omission=None,
        field=field,
    )


__all__ = [
    "CASES_BY_DOCKET",
    "LIABILITY_BASIS_CITE",
    "STATUTE_41104_F",
    "VACATED_SECTION",
    "VACATUR_CITATION",
    "VACATUR_REMOVAL",
    "WORLD_SHIPPING_COUNCIL_5414",
    "WORLD_SHIPPING_COUNCIL_5421",
    "CaseCitation",
    "LiabilityFinding",
    "VacatedRuleError",
    "case_for",
    "check_liability_basis",
    "refuses_vacated_basis",
]
