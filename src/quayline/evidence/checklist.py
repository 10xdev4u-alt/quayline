"""Issue 63: what each carrier will not accept a dispute without.

The failure this module exists to prevent is not a rejected dispute, it is a
rejected dispute that took eleven weeks to produce. A carrier will not tell you
what is missing, it will say the submission is incomplete, and the clock that was
supposed to be running in your favour is not running at all.

Why a checklist and not a form

The requirements are per carrier and they are not the same, and they are not even
the same shape. MSC wants a shipper statement and only when the ground is a
government hold. CMA CGM wants credible evidence for *each covered day*, which is
not an artifact at all, it is a cardinality rule over a date set. ONE wants a
requested outcome and, separately, standing or authorisation, which is a power of
attorney and is a different kind of object from everything else on the list.

A single flat list of documents would encode the easy cases and get the other two
wrong in ways that pass review, so the type carries the shape of the requirement
rather than a filename.

UNVERIFIED, and why it matters more here than anywhere else

Every requirement in this module is UNVERIFIED. The source is the paraphrase in
issue 63, which came from carrier guidance pages we have not transcribed. There is
not one verbatim clause in this file.

That is a weaker position than the rest of the engine is in, and it is stated
plainly rather than hidden because the failure mode is specific: a checklist
marked UNVERIFIED that is wrong produces a submission the carrier rejects, and a
rejected submission is worse than an incomplete one, because it is evidence that
we asked. A checklist marked VERIFIED that is wrong would be a false statement in
a filing. So the marker travels on the carrier record, the gate refuses to be
quiet about it, and nothing here may be cited in a letter.

``assert_all_transcribed`` exists to make that check mechanical. When a clause is
transcribed for a carrier, the carrier flips to VERIFIED and this returns the
outstanding work. Until then it is a to-do list, not a formality.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Artifact(StrEnum):
    """A thing a carrier asks for, named as the carrier names it.

    Not filenames. A carrier does not ask for a ``bol.txt``, it asks for the bill
    of lading number, and the difference is that the number is a fact we already
    hold while the file is a thing someone has to go and find.
    """

    BOL_NUMBER = "bill of lading number"
    CONTAINER_NUMBER = "container number"
    EXPLANATION = "comprehensive explanation"
    SERVICE_CONTRACT = "service contract documentation"
    APPOINTMENT_SCREENSHOT = "appointment unavailability screenshot"
    SHIPPER_STATEMENT = "shipper statement"
    PER_DAY_EVIDENCE = "credible evidence for each covered day"
    SPECIFIC_CHARGES = "the specific charges disputed"
    REQUESTED_OUTCOME = "the requested outcome"
    POWER_OF_ATTORNEY = "power of attorney"


#: How many dates a finding names before it summarises the rest. A letter that
#: lists every gap in a forty day dispute is not a letter anyone reads, and a
#: finding whose detail is a wall of dates gets pasted into a ticket and lost.
_DATES_SHOWN = 5


class Ground(StrEnum):
    """When a conditional requirement applies.

    Modelled as a set because a dispute can be on two grounds at once, and
    "contract condition and government hold" is a real pairing.
    """

    #: Not a factual cause. A ground for the case where the carrier did not make a
    #: disclosure 541.6 requires, which is why the remedy is automatic and the
    #: packet files it without evidence. It lives here rather than in packet.py so
    #: that a disclosure claim and a factual claim cannot collide, which is not a
    #: distinction one can make at a call site.
    DISCLOSURE_OMITTED = "disclosure omitted"
    CONTRACT_CONDITION = "contract condition"
    APPOINTMENT_UNAVAILABLE = "appointment unavailable"
    GOVERNMENT_HOLD = "government hold"


@dataclass(frozen=True, slots=True)
class Requirement:
    """One thing this carrier needs, and when it needs it.

    ``applies_on`` empty means always required. Otherwise the requirement is live
    only if the dispute is on one of those grounds, and a caller that passes the
    wrong grounds gets a wrong checklist without an error, which is why the ground
    set is a required argument to :func:`evaluate` rather than a default.
    """

    artifact: Artifact
    applies_on: frozenset[Ground] = frozenset()
    note: str = ""

    @property
    def is_conditional(self) -> bool:
        return bool(self.applies_on)

    def applies_to(self, grounds: frozenset[Ground]) -> bool:
        if not self.applies_on:
            return True
        return bool(self.applies_on & grounds)


@dataclass(frozen=True, slots=True)
class CarrierRequirements:
    """One carrier's submission checklist, and how sure we are of it."""

    carrier: str
    requirements: tuple[Requirement, ...]
    source: str
    verified: bool
    note: str = ""

    def live(self, grounds: frozenset[Ground]) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.applies_to(grounds))


@dataclass(frozen=True, slots=True)
class Submission:
    """What we actually have.

    ``days_covered`` is the days the dispute is about. ``evidence_for_days`` is the
    days we can evidence. The gap between them is the finding, and it is a count
    rather than a missing artifact because a carrier asked for evidence per day and
    there is no single document that satisfies it.
    """

    carrier: str
    artifacts: frozenset[Artifact]
    grounds: frozenset[Ground]
    days_covered: frozenset[date] = frozenset()
    evidence_for_days: frozenset[date] = frozenset()

    def __post_init__(self) -> None:
        unevidenced = self.days_covered - self.evidence_for_days
        if unevidenced and Artifact.PER_DAY_EVIDENCE not in self.artifacts:
            # Not an error. Evidence per day can be supplied as the dates
            # themselves, which is the normal case, and demanding a token for it
            # would make the common path look like an exception.
            pass


@dataclass(frozen=True, slots=True)
class Finding:
    """Something blocking submission, named precisely enough to act on."""

    carrier: str
    artifact: Artifact
    reason: str
    detail: str = ""

    def __str__(self) -> str:
        """The artifact as the carrier names it, which is the value and not the
        enum member. ``REQUESTED_OUTCOME`` is a name we invented in this file and
        is exactly the kind of thing the person assembling the packet cannot act
        on, which is the whole reason this string exists.
        """
        return f"{self.carrier} will not accept this without {self.artifact.value}: {self.reason}"


@dataclass(frozen=True, slots=True)
class SubmissionReport:
    """Whether this may be submitted, and what is missing if it may not."""

    carrier: str
    findings: tuple[Finding, ...]
    unverified: bool

    @property
    def can_submit(self) -> bool:
        """The gate. One boolean, no severity, for the same reason as issue 42.

        A severity field here would be a field someone eventually passes as False
        and files anyway.
        """
        return not self.findings

    def reason_not_submitted(self) -> str:
        if self.can_submit:
            return ""
        return "; ".join(str(f) for f in self.findings)

    def unmet_days(self) -> tuple[date, ...]:
        """The per-day evidence gap, sorted.

        Separate from findings because it is a set difference rather than a missing
        artifact, and a letter that lists forty undated gaps is not a letter.
        """
        gap = self._days_covered - self._evidence_for_days
        return tuple(sorted(gap))

    _days_covered: frozenset[date] = frozenset()
    _evidence_for_days: frozenset[date] = frozenset()


#: MSC. Paraphrased from issue 63; no clause transcribed.
MSC = CarrierRequirements(
    carrier="MSC",
    requirements=(
        Requirement(Artifact.BOL_NUMBER),
        Requirement(Artifact.CONTAINER_NUMBER),
        Requirement(Artifact.EXPLANATION),
        Requirement(
            Artifact.SERVICE_CONTRACT,
            applies_on=frozenset({Ground.CONTRACT_CONDITION}),
            note="only where the dispute rests on the service contract",
        ),
        Requirement(
            Artifact.APPOINTMENT_SCREENSHOT,
            applies_on=frozenset({Ground.APPOINTMENT_UNAVAILABLE}),
            note="only where an appointment was refused",
        ),
        Requirement(
            Artifact.SHIPPER_STATEMENT,
            applies_on=frozenset({Ground.GOVERNMENT_HOLD}),
            note="only where a government body held the container",
        ),
    ),
    source="MSC dispute guidance, paraphrased in issue 63",
    verified=False,
    note=(
        "UNVERIFIED: no MSC clause has been transcribed. The three unconditional "
        "items and the three conditional ones are all from a paraphrase, and the "
        "paraphrase does not say whether an unnecessary artifact is harmful. "
        "Supplying a shipper statement for a dispute that had no government hold "
        "may itself be read as an admission, which is why the grounds are modelled "
        "rather than assumed."
    ),
)

#: CMA CGM. Paraphrased from issue 63; no clause transcribed.
CMA_CGM = CarrierRequirements(
    carrier="CMA CGM",
    requirements=(
        Requirement(Artifact.BOL_NUMBER),
        Requirement(Artifact.CONTAINER_NUMBER),
        Requirement(
            Artifact.PER_DAY_EVIDENCE,
            note="per covered day, not per dispute. This is a cardinality rule and is "
            "evaluated against the day sets, not against the artifact set.",
        ),
    ),
    source="CMA CGM dispute guidance, paraphrased in issue 63",
    verified=False,
    note=(
        "UNVERIFIED: no CMA CGM clause has been transcribed. The per-day rule is the "
        "one that matters and it is the one we understand least; whether a gap of "
        "one day voids the whole submission or just that day is not something the "
        "paraphrase settles, and the difference is the whole value of the dispute."
    ),
)

#: ONE. Paraphrased from issue 63; no clause transcribed.
ONE = CarrierRequirements(
    carrier="ONE",
    requirements=(
        Requirement(Artifact.BOL_NUMBER),
        Requirement(Artifact.CONTAINER_NUMBER),
        Requirement(Artifact.SPECIFIC_CHARGES),
        Requirement(Artifact.PER_DAY_EVIDENCE),
        Requirement(Artifact.REQUESTED_OUTCOME),
        Requirement(
            Artifact.POWER_OF_ATTORNEY,
            note="standing or authorisation. ONE will not act on a letter from a party "
            "that has not shown it may act for the billed party, so this is a power "
            "of attorney and not a form of address.",
        ),
    ),
    source="ONE dispute guidance, paraphrased in issue 63",
    verified=False,
    note=(
        "UNVERIFIED: no ONE clause has been transcribed. The power of attorney is "
        "the item most likely to be modelled wrongly, because it is a standing "
        "question about who may file rather than a fact about the charge. It is a "
        "hard requirement here, and if ONE in fact accepts an agent letter with a "
        "signed authorisation that is not a power of attorney, this requirement is "
        "over-strict and will block submissions that ONE would have accepted."
    ),
)

REQUIREMENTS: dict[str, CarrierRequirements] = {
    "MSC": MSC,
    "CMA CGM": CMA_CGM,
    "ONE": ONE,
}


def evaluate(
    submission: Submission, *, requirements: CarrierRequirements | None = None
) -> SubmissionReport:
    """Check one submission against its carrier's checklist.

    Pure and total. An unknown carrier is a finding rather than an exception,
    because a submission addressed to a carrier we have no checklist for is exactly
    the submission that gets rejected without an explanation.
    """
    spec = requirements or REQUIREMENTS.get(submission.carrier)
    if spec is None:
        return SubmissionReport(
            carrier=submission.carrier,
            findings=(
                Finding(
                    carrier=submission.carrier,
                    artifact=Artifact.EXPLANATION,
                    reason="we hold no submission checklist for this carrier",
                    detail="refusing to guess a checklist we have not transcribed",
                ),
            ),
            unverified=True,
        )

    findings: list[Finding] = []
    for requirement in spec.live(submission.grounds):
        if requirement.artifact is Artifact.PER_DAY_EVIDENCE:
            continue
        if requirement.artifact not in submission.artifacts:
            findings.append(
                Finding(
                    carrier=spec.carrier,
                    artifact=requirement.artifact,
                    reason="required and not supplied",
                    detail=requirement.note,
                )
            )

    gap = submission.days_covered - submission.evidence_for_days
    if any(r.artifact is Artifact.PER_DAY_EVIDENCE for r in spec.live(submission.grounds)) and gap:
        shown = ", ".join(d.isoformat() for d in sorted(gap)[:_DATES_SHOWN])
        more = f" and {len(gap) - _DATES_SHOWN} more" if len(gap) > _DATES_SHOWN else ""
        findings.append(
            Finding(
                carrier=spec.carrier,
                artifact=Artifact.PER_DAY_EVIDENCE,
                reason=f"{len(gap)} of {len(submission.days_covered)} covered day(s) have no evidence",
                detail=f"first: {shown}{more}",
            )
        )

    return SubmissionReport(
        carrier=spec.carrier,
        findings=tuple(findings),
        unverified=not spec.verified,
        _days_covered=submission.days_covered,
        _evidence_for_days=submission.evidence_for_days,
    )


def assert_all_transcribed() -> dict[str, str]:
    """Carriers still marked UNVERIFIED, with why.

    A to-do list, not an assertion. It exists so that closing this gap is a visible
    task with a name on it rather than a property everyone assumes was handled.
    """
    return {spec.carrier: spec.note for spec in REQUIREMENTS.values() if not spec.verified}
