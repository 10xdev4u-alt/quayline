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
from enum import StrEnum

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


class FreightTerm(StrEnum):
    """How freight was paid on the bill of lading.

    This is the document that sets liability, which is why 541.6(a)(4) is a real hook
    after the vacatur of 541.4. The closed list of who may be invoiced is gone. The
    obligation to articulate why *this* party is liable is not.
    """

    PREPAID = "prepaid"
    COLLECT = "collect"
    #: The bill of lading does not say, or we have not seen it.
    UNSTATED = "not stated"


# ESTIMATE, not law, and the distinction matters.
#
# Prepaid freight is paid by the shipper at origin, so the goods are the buyer's by
# the time anything is owed; industry practice puts demurrage and detention on the
# consignee. Collect freight is payable by the consignee at destination, so the
# shipper remains the party that owes the transport, and practice puts the charges
# on the shipper.
#
# This is how the trade reads the bill of lading, not a rule in Part 541. Part 541
# does not say it, no carrier tariff says it, and it is not uniform. It is marked
# ESTIMATE here, per AGENTS.md section five, and it is used only to say which
# question to ask. It is never used to assert that a particular party was wrong.
# Asserting that would be a legal conclusion with no clause under it, which is the
# exact failure the vacatur issue was about.
#: The two parties a freight term decides between. Named so the evidence list and the
#: question are generated from one place rather than typed twice.
FREIGHT_PREPAID_PARTY = "the consignee"
FREIGHT_COLLECT_PARTY = "the shipper"

FREIGHT_TERM_ESTIMATE = (
    "ESTIMATE: industry practice, not a rule in 46 CFR Part 541. Prepaid freight "
    "typically places demurrage and detention on the consignee; collect freight "
    "typically places it on the shipper. No carrier tariff in our research states "
    "this, and practice is not uniform."
)


@dataclass(frozen=True, slots=True)
class FreightTermReading:
    """What a freight term ordinarily implies, and how sure we are.

    ``ordinarily_liable`` is ``None`` when the term is unstated, which is the case
    that produces the strongest question rather than the weakest answer.
    """

    term: FreightTerm
    ordinarily_liable: str | None
    rationale: str

    @property
    def determined(self) -> bool:
        return self.ordinarily_liable is not None


def freight_term_reading(term: FreightTerm) -> FreightTermReading:
    """The ordinary consequence of a freight term. ESTIMATE, see the constant."""
    match term:
        case FreightTerm.PREPAID:
            return FreightTermReading(
                term=term,
                ordinarily_liable="the consignee",
                rationale=(
                    "Freight was prepaid at origin, so the consignee is the party that "
                    "bought the goods and freight was paid on its behalf"
                ),
            )
        case FreightTerm.COLLECT:
            return FreightTermReading(
                term=term,
                ordinarily_liable="the shipper",
                rationale=(
                    "Freight is collect at destination, so the shipper remains the party "
                    "that owes the transport and has not paid it"
                ),
            )
        case FreightTerm.UNSTATED:
            return FreightTermReading(
                term=term,
                ordinarily_liable=None,
                rationale=(
                    "The bill of lading does not state a freight term, so nothing in the "
                    "document determines who bears the charge and the carrier must say so "
                    "on the invoice"
                ),
            )


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
    freight: FreightTermReading | None = None
    #: Who the carrier invoiced. Optional because the check is also run before we
    #: know who was billed, and a question naming nobody is worse than a generic one.
    billed_party: str = ""

    @property
    def eliminates_obligation(self) -> bool:
        """Only the absent case does. A conclusory basis is not a 541.5 event."""
        return self.omission is not None

    def evidence(self) -> tuple[str, ...]:
        """What a respondent has to produce, named before anything is demanded.

        The bill of lading first, because it is the instrument that sets liability
        and it is in the shipper's own hands, not the carrier's. Both freight terms
        after it, because a respondent who reads the bill of lading and finds
        "prepaid" needs to be told what that ordinarily implies before they decide
        the carrier was right, and a respondent who finds "collect" needs the same.
        """
        items = ["the bill of lading for the shipment, showing the freight term"]
        if self.freight is not None:
            items.append(
                f"the prepaid term, which ordinarily places these charges on "
                f"{FREIGHT_PREPAID_PARTY}"
            )
            items.append(
                f"the collect term, which ordinarily places them on {FREIGHT_COLLECT_PARTY}"
            )
        return tuple(items)

    def question_for_carrier(self) -> str:
        """The one question the respondent has to answer, in their words.

        Not an accusation. A 541.6(a)(4) question is answered by producing a document
        or by explaining why none exists, and the letter should make that easy.
        """
        freight = self.freight
        who = freight.ordinarily_liable if freight else None
        if freight is None or who is None:
            return (
                "Which party does the carrier contend is liable for these charges, and "
                "what in the bill of lading or the contract between the parties makes it so?"
            )
        named = self.billed_party or "this party"
        return (
            f"The bill of lading shows freight {freight.term.value}, which ordinarily "
            f"places these charges on {who}. On what basis is {named} liable instead?"
        )

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
    "party of interest",
    "party in interest",
)


def check_liability_basis(
    basis: str | None,
    invoice_ref: str = "",
    *,
    freight_term: FreightTerm = FreightTerm.UNSTATED,
    billed_party: str = "",
) -> LiabilityFinding:
    """541.6(a)(4). Is the basis for liability stated, and is it particularised?

    ``basis`` is what the carrier wrote, verbatim, or None if the disclosure is
    missing entirely.

    ``freight_term`` and ``billed_party`` do not change the verdict. They change what
    the letter asks for, which is the difference between demanding a document and
    asking a question the respondent can answer from one they already hold.
    """
    field = by_cite(LIABILITY_BASIS_CITE)
    freight = freight_term_reading(freight_term)

    if basis is None or not basis.strip():
        return LiabilityFinding(
            verdict="absent",
            detail=(
                "A wrong party invoice is not a per se defect after the vacatur, but the "
                "carrier must still state why this party is liable, and it did not."
            ),
            omission=Omission(field=field, invoice_ref=invoice_ref or "the invoice"),
            field=field,
            freight=freight,
            billed_party=billed_party,
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
            freight=freight,
            billed_party=billed_party,
        )

    return LiabilityFinding(
        verdict="particularised",
        detail="The stated basis names a contractual or status basis rather than asserting liability.",
        omission=None,
        field=field,
        freight=freight,
        billed_party=billed_party,
    )


__all__ = [
    "CASES_BY_DOCKET",
    "FREIGHT_COLLECT_PARTY",
    "FREIGHT_PREPAID_PARTY",
    "FREIGHT_TERM_ESTIMATE",
    "LIABILITY_BASIS_CITE",
    "STATUTE_41104_F",
    "VACATED_SECTION",
    "VACATUR_CITATION",
    "VACATUR_REMOVAL",
    "WORLD_SHIPPING_COUNCIL_5414",
    "WORLD_SHIPPING_COUNCIL_5421",
    "CaseCitation",
    "FreightTerm",
    "FreightTermReading",
    "LiabilityFinding",
    "VacatedRuleError",
    "case_for",
    "check_liability_basis",
    "freight_term_reading",
    "refuses_vacated_basis",
]
