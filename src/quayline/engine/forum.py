"""Issue 5: who loses when nobody can prove it.

Before the FMC, the carrier bears the burden. 46 U.S.C. 41310(b)(2) puts the burden
of establishing reasonableness for D&D charges on the common carrier. In a private
dispute, it does not: the filer proves its claim like any other claimant, and an
unanswered question cuts against whoever asked it.

The postures reverse, and evidence that wins one often loses the other. A gap in
the carrier's documentation is an adverse inference at the Commission and a hole in
our letter everywhere else. So the two forums are two engines with different priors,
not one engine with a flag, because a flag is a parameter somebody forgets to set
and the default it falls back to decides cases.

What differs and what does not

The checkers are shared. Arithmetic is arithmetic in both forums, and a variance is
a variance. What changes is the **default on a gap**: missing evidence, an
unverified block, an unanswered question, a silence where a document should be.

- **FMC engine.** The carrier bears the burden of establishing reasonableness. A
  gap in the carrier's showing cuts against the carrier. Our letter says what is
  missing and why the absence itself supports the claim.
- **Private engine.** We bear the burden of our own claim. A gap in our evidence
  cuts against us. Our letter says what we proved and does not ask the respondent
  to disprove anything.

Neither engine invents facts. An adverse inference is not a finding that the
missing document would have supported us; it is a procedural consequence the forum
assigns to the absence. The distinction matters because the first is something we
would have to prove and cannot, and the second is something the forum does for us.

Every finding names its engine

`EvaluatedFinding.forum` states which engine produced it. A finding that does not
say which forum's rules it was evaluated under is a finding that can be quoted in
the wrong forum, and a 41310(b)(2) adverse inference quoted in a private dispute
is an argument the respondent will dismantle in one paragraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Forum(StrEnum):
    """Where the dispute is heard. The forum sets the burden, and the burden sets
    what a gap means."""

    #: A charge complaint before the Federal Maritime Commission. 46 U.S.C.
    #: 41310(b)(2): the common carrier bears the burden of establishing
    #: reasonableness.
    FMC_CHARGE_COMPLAINT = "fmc_charge_complaint"
    #: A private dispute with the carrier. The filer proves its claim.
    PRIVATE_DISPUTE = "private_dispute"


class Party(StrEnum):
    """Who bears the burden on a question."""

    CARRIER = "carrier"
    FILER = "filer"


@dataclass(frozen=True, slots=True)
class BurdenRule:
    """One question, and who loses it when nobody can answer.

    `question` names the gap in plain words, because a rule keyed by code is a rule
    nobody can audit without the code table open. `bearer` is who must produce or
    lose, and it is a function of the forum, which is the whole point of this
    module.
    """

    question: str
    bearer: Party
    consequence: str


#: The questions both engines know how to lose. Each maps a gap to its bearer per
#: forum, so adding a question is a row in a table rather than a branch somewhere.
BURDEN_TABLE: dict[str, dict[Forum, BurdenRule]] = {
    "reasonableness_of_charge": {
        Forum.FMC_CHARGE_COMPLAINT: BurdenRule(
            question="Is the charge reasonable?",
            bearer=Party.CARRIER,
            consequence=(
                "46 U.S.C. 41310(b)(2). The carrier establishes reasonableness or "
                "loses it. Silence on a gap is an adverse inference, not a neutral fact."
            ),
        ),
        Forum.PRIVATE_DISPUTE: BurdenRule(
            question="Is the charge reasonable?",
            bearer=Party.FILER,
            consequence=(
                "The filer proves its claim. A gap in our evidence is a hole in our "
                "letter, and no inference fills it."
            ),
        ),
    },
    "accuracy_of_disclosures": {
        Forum.FMC_CHARGE_COMPLAINT: BurdenRule(
            question="Are the invoice disclosures accurate?",
            bearer=Party.CARRIER,
            consequence=(
                "The billing party certified them. An inaccuracy the carrier cannot "
                "explain cuts against the carrier."
            ),
        ),
        Forum.PRIVATE_DISPUTE: BurdenRule(
            question="Are the invoice disclosures accurate?",
            bearer=Party.FILER,
            consequence=(
                "We allege the inaccuracy, so we prove it. The contradiction must be "
                "shown from the document, not asserted."
            ),
        ),
    },
    "carrier_performance": {
        Forum.FMC_CHARGE_COMPLAINT: BurdenRule(
            question="Did the carrier's performance contribute to the charges?",
            bearer=Party.CARRIER,
            consequence=(
                "The (e)(2) certification is the carrier's own representation. A "
                "documented delay it cannot rebut cuts against it."
            ),
        ),
        Forum.PRIVATE_DISPUTE: BurdenRule(
            question="Did the carrier's performance contribute to the charges?",
            bearer=Party.FILER,
            consequence=(
                "We allege the contribution, so we document the delay. An unsourced "
                "delay is an allegation, and an allegation loses."
            ),
        ),
    },
}


def burden_on(question: str, forum: Forum) -> BurdenRule:
    """Who bears the burden on a question, in a forum. Raises on an unknown
    question.

    Raising is deliberate. An unlisted question defaulting to either party would be
    a burden assigned by accident, and the party it lands on would deserve to know
    it was deliberate.
    """
    try:
        return BURDEN_TABLE[question][forum]
    except KeyError:
        msg = (
            f"no burden rule for {question!r}. Add it to BURDEN_TABLE with a bearer "
            f"for each forum, so the assignment is deliberate."
        )
        raise KeyError(msg) from None


def default_on_gap(question: str, forum: Forum) -> str:
    """What a gap means, in words a letter can use.

    Not a finding. A sentence about who loses an unanswered question, which is what
    an operator needs before deciding whether to file on thin evidence.
    """
    rule = burden_on(question, forum)
    loser = "the carrier" if rule.bearer is Party.CARRIER else "us"
    return (
        f"On {rule.question} the burden lies with {rule.bearer.value}, so an "
        f"unanswered question cuts against {loser}. {rule.consequence}"
    )


@dataclass(frozen=True, slots=True)
class EvaluatedFinding:
    """A finding with the forum it was evaluated under stated on it.

    A finding that does not say which engine produced it can be quoted in the wrong
    forum, and a 41310(b)(2) adverse inference quoted in a private dispute is an
    argument the respondent dismantles in one paragraph.
    """

    code: str
    summary: str
    forum: Forum
    cite: str = ""
    detail: str = ""

    @property
    def burden(self) -> BurdenRule | None:
        """The burden rule behind this finding, if its question is catalogued."""
        question = _QUESTION_BY_CODE.get(self.code)
        if question is None:
            return None
        return burden_on(question, self.forum)


#: Which catalogued question each finding code belongs to. Absent means the finding
#: does not turn on a burden question, which is true of most arithmetic.
_QUESTION_BY_CODE: dict[str, str] = {
    "amount_variance": "reasonableness_of_charge",
    "daycount_variance": "reasonableness_of_charge",
    "availability_contradiction": "accuracy_of_disclosures",
    "liability_basis_conclusory": "accuracy_of_disclosures",
}


def evaluate(
    code: str, summary: str, forum: Forum, cite: str = "", detail: str = ""
) -> EvaluatedFinding:
    """Wrap a finding with its forum. The only constructor, so the forum is never
    omitted by accident."""
    return EvaluatedFinding(code=code, summary=summary, forum=forum, cite=cite, detail=detail)


__all__ = [
    "BURDEN_TABLE",
    "BurdenRule",
    "EvaluatedFinding",
    "Forum",
    "Party",
    "burden_on",
    "default_on_gap",
    "evaluate",
]
