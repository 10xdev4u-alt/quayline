"""Issue 63: the per carrier submission checklist.

The load bearing test is ``test_each_carrier_blocks_on_its_own_documented_omission``.
A checklist module can pass every per carrier test and still be wrong if the
per carrier tests are the same test with the carrier name swapped, which is a very
easy way to write this file and produces no coverage of the thing that differs.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from quayline.evidence.checklist import (
    CMA_CGM,
    MSC,
    ONE,
    REQUIREMENTS,
    Artifact,
    CarrierRequirements,
    Ground,
    Requirement,
    Submission,
    assert_all_transcribed,
    evaluate,
)

BASE = frozenset({Artifact.BOL_NUMBER, Artifact.CONTAINER_NUMBER})
ALL = frozenset(Artifact)
DAYS = frozenset({date(2026, 7, 8), date(2026, 7, 9)})
EVIDENCED = frozenset(DAYS)
NO_GROUNDS: frozenset[Ground] = frozenset()


def submission(carrier: str, artifacts: frozenset[Artifact] = BASE, **kw: object) -> Submission:
    fields: dict[str, object] = {
        "carrier": carrier,
        "artifacts": artifacts,
        "grounds": NO_GROUNDS,
        "days_covered": DAYS,
        "evidence_for_days": EVIDENCED,
    }
    fields.update(kw)
    return Submission(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------- criterion 1
# A per carrier checklist exists and is validated before submission.


def test_a_checklist_exists_for_every_carrier_we_have_evidence_for() -> None:
    assert set(REQUIREMENTS) == {"MSC", "CMA CGM", "ONE"}


def test_every_carrier_requires_the_identifiers() -> None:
    """The one thing every carrier asks for, which is also the one thing 541.6
    already forces onto the invoice."""
    for spec in REQUIREMENTS.values():
        kinds = {r.artifact for r in spec.requirements}
        assert Artifact.BOL_NUMBER in kinds, spec.carrier
        assert Artifact.CONTAINER_NUMBER in kinds, spec.carrier


def test_the_checklists_actually_differ_from_each_other() -> None:
    """Otherwise the per carrier framing is decoration on a single shared list."""
    shapes = {
        spec.carrier: frozenset(r.artifact for r in spec.requirements)
        for spec in REQUIREMENTS.values()
    }
    assert len(set(shapes.values())) == len(shapes)
    assert shapes["ONE"] - shapes["CMA CGM"] == {
        Artifact.SPECIFIC_CHARGES,
        Artifact.REQUESTED_OUTCOME,
        Artifact.POWER_OF_ATTORNEY,
    }


def test_an_unknown_carrier_is_a_finding_not_an_exception() -> None:
    """A submission to a carrier we have no checklist for is the submission that
    gets rejected without an explanation."""
    report = evaluate(submission("Evergreen"))
    assert report.can_submit is False
    assert "no submission checklist" in report.reason_not_submitted()


def test_every_requirement_is_grounded_in_a_source() -> None:
    for spec in REQUIREMENTS.values():
        assert spec.source
        assert spec.note


def test_the_unverified_marker_travels_on_the_report() -> None:
    """Not on the requirement, on the result the caller is about to act on."""
    report = evaluate(submission("ONE", artifacts=ALL))
    assert report.can_submit is True
    assert report.unverified is True


# ---------------------------------------------------------------- criterion 2
# A missing required item blocks submission with the item named.


def test_a_missing_unconditional_item_blocks_submission_and_is_named() -> None:
    report = evaluate(submission("ONE", artifacts=ALL - {Artifact.REQUESTED_OUTCOME}))
    assert report.can_submit is False
    assert "the requested outcome" in report.reason_not_submitted()
    assert "ONE" in report.reason_not_submitted()


def test_a_finding_names_the_artifact_in_its_own_words() -> None:
    report = evaluate(submission("ONE", artifacts=ALL - {Artifact.SPECIFIC_CHARGES}))
    finding = next(f for f in report.findings if f.artifact is Artifact.SPECIFIC_CHARGES)
    assert finding.artifact.value == "the specific charges disputed"
    assert "required and not supplied" in str(finding)


def test_a_conditional_requirement_does_not_fire_off_its_ground() -> None:
    """Supplying a shipper statement for a dispute with no government hold may be
    read as an admission, so the checklist must not ask for it."""
    report = evaluate(submission("MSC", artifacts=ALL))
    assert report.can_submit is True, report.reason_not_submitted()


def test_a_conditional_requirement_fires_on_its_ground() -> None:
    report = evaluate(
        submission(
            "MSC",
            artifacts=ALL - {Artifact.SHIPPER_STATEMENT},
            grounds=frozenset({Ground.GOVERNMENT_HOLD}),
        )
    )
    assert report.can_submit is False
    assert "shipper statement" in report.reason_not_submitted()


@pytest.mark.parametrize(
    ("ground", "artifact"),
    [
        (Ground.CONTRACT_CONDITION, Artifact.SERVICE_CONTRACT),
        (Ground.APPOINTMENT_UNAVAILABLE, Artifact.APPOINTMENT_SCREENSHOT),
        (Ground.GOVERNMENT_HOLD, Artifact.SHIPPER_STATEMENT),
    ],
)
def test_every_conditional_fires_only_on_its_own_ground(ground: Ground, artifact: Artifact) -> None:
    """The other two conditional artifacts must stay out of the way."""
    for other in Ground:
        if other is ground:
            continue
        report = evaluate(submission("MSC", artifacts=ALL - {artifact}, grounds=frozenset({other})))
        assert report.can_submit is True, (other, report.reason_not_submitted())


def test_two_grounds_at_once_fire_both_requirements() -> None:
    report = evaluate(
        submission(
            "MSC",
            artifacts=ALL - {Artifact.SERVICE_CONTRACT, Artifact.SHIPPER_STATEMENT},
            grounds=frozenset({Ground.CONTRACT_CONDITION, Ground.GOVERNMENT_HOLD}),
        )
    )
    assert {f.artifact for f in report.findings} == {
        Artifact.SERVICE_CONTRACT,
        Artifact.SHIPPER_STATEMENT,
    }


def test_can_submit_is_one_property_with_no_severity() -> None:
    report = evaluate(submission("ONE", artifacts=ALL - {Artifact.REQUESTED_OUTCOME}))
    assert isinstance(report.can_submit, bool)
    assert not hasattr(report, "warnings")
    assert not hasattr(report, "should_submit")


# ---------------------------------------------------------------- criterion 3
# ONE's standing or authorisation requirement models a power of attorney artifact.


def test_one_requires_a_power_of_attorney() -> None:
    assert Artifact.POWER_OF_ATTORNEY in {r.artifact for r in ONE.requirements}


def test_a_missing_power_of_attorney_blocks_one() -> None:
    report = evaluate(submission("ONE", artifacts=ALL - {Artifact.POWER_OF_ATTORNEY}))
    assert report.can_submit is False
    assert "power of attorney" in report.reason_not_submitted()


def test_a_power_of_attorney_is_not_satisfied_by_the_other_identifiers() -> None:
    """Having the bill of lading does not authorise us to file. They are different
    objects and a checklist that let one stand in for the other would let a
    submission through that ONE will reject."""
    report = evaluate(submission("ONE", artifacts=BASE))
    assert report.can_submit is False
    assert "power of attorney" in report.reason_not_submitted()


def test_the_power_of_attorney_is_unconditional_for_one() -> None:
    """It is a standing question, not a ground dependent one."""
    requirement = next(r for r in ONE.requirements if r.artifact is Artifact.POWER_OF_ATTORNEY)
    assert requirement.applies_on == frozenset()
    assert not requirement.is_conditional


def test_the_power_of_attorney_over_strictness_is_recorded() -> None:
    """If ONE in fact accepts a signed authorisation that is not a power of
    attorney, this requirement blocks submissions ONE would have accepted. That
    risk is named rather than assumed away."""
    assert "over-strict" in ONE.note


# ---------------------------------------------------------------- the per day rule


def test_per_day_evidence_is_a_cardinality_rule_not_a_missing_document() -> None:
    report = evaluate(
        submission("CMA CGM", artifacts=BASE, evidence_for_days=frozenset({date(2026, 7, 8)}))
    )
    assert report.can_submit is False
    finding = next(f for f in report.findings if f.artifact is Artifact.PER_DAY_EVIDENCE)
    assert "1 of 2 covered day(s) have no evidence" in finding.reason
    assert "2026-07-09" in finding.detail


def test_full_per_day_evidence_passes_without_a_token_artifact() -> None:
    """Evidence per day is supplied as the dates themselves, so demanding an
    artifact for it would make the common path look like an exception."""
    report = evaluate(submission("CMA CGM", artifacts=BASE))
    assert report.can_submit is True, report.reason_not_submitted()


def test_the_unmet_days_are_available_sorted() -> None:
    report = evaluate(
        submission(
            "CMA CGM",
            artifacts=BASE,
            days_covered=frozenset({date(2026, 7, 10), date(2026, 7, 8), date(2026, 7, 9)}),
            evidence_for_days=frozenset({date(2026, 7, 9)}),
        )
    )
    assert report.unmet_days() == (date(2026, 7, 8), date(2026, 7, 10))
    assert report.unmet_days() == tuple(sorted(report.unmet_days()))


def test_a_long_gap_summarises_rather_than_listing_forty_dates() -> None:
    covered = frozenset(date(2026, 7, 1) + timedelta(days=i) for i in range(12))
    report = evaluate(
        submission("CMA CGM", artifacts=BASE, days_covered=covered, evidence_for_days=frozenset())
    )
    finding = next(f for f in report.findings if f.artifact is Artifact.PER_DAY_EVIDENCE)
    assert "and 7 more" in finding.detail
    assert finding.detail.count("2026-07-") == 5


def test_evidence_for_a_day_we_are_not_disputing_is_not_a_defect() -> None:
    report = evaluate(
        submission(
            "CMA CGM",
            artifacts=BASE,
            days_covered=frozenset({date(2026, 7, 8)}),
            evidence_for_days=frozenset({date(2026, 7, 8), date(2026, 7, 20)}),
        )
    )
    assert report.can_submit is True
    assert report.unmet_days() == ()


# ---------------------------------------------------------------- criterion 4
# Each carrier blocks on its own documented omission.


def test_each_carrier_blocks_on_its_own_documented_omission() -> None:
    """One test, three genuinely different assertions.

    Written as a table on purpose. If MSC, CMA CGM and ONE are checked by three
    copies of the same test with the name changed, the checklist is only ever
    tested against itself.
    """
    cases: list[tuple[str, frozenset[Artifact], str]] = [
        # MSC: the comprehensive explanation is its own unconditional requirement.
        ("MSC", BASE, Artifact.EXPLANATION.value),
        # CMA CGM: per day evidence, and it blocks on a day rather than a document.
        ("CMA CGM", BASE, Artifact.PER_DAY_EVIDENCE.value),
        # ONE: the requested outcome, which no other carrier in the table asks for.
        ("ONE", ALL - {Artifact.REQUESTED_OUTCOME}, Artifact.REQUESTED_OUTCOME.value),
    ]
    for carrier, artifacts, expected in cases:
        kw: dict[str, object] = {}
        if expected == Artifact.PER_DAY_EVIDENCE.value:
            kw["evidence_for_days"] = frozenset({date(2026, 7, 8)})
        report = evaluate(submission(carrier, artifacts, **kw))
        assert report.can_submit is False, carrier
        assert expected in report.reason_not_submitted(), carrier


def test_the_three_omissions_are_three_different_requirements() -> None:
    """Guards the test above against collapsing into one shared item."""
    msc = {r.artifact for r in MSC.requirements}
    cma = {r.artifact for r in CMA_CGM.requirements}
    one = {r.artifact for r in ONE.requirements}
    assert Artifact.EXPLANATION in msc and Artifact.EXPLANATION not in cma | one
    assert Artifact.REQUESTED_OUTCOME in one and Artifact.REQUESTED_OUTCOME not in msc | cma
    assert Artifact.PER_DAY_EVIDENCE in cma and Artifact.PER_DAY_EVIDENCE not in msc


def test_a_complete_submission_passes_for_each_carrier() -> None:
    for carrier in REQUIREMENTS:
        report = evaluate(submission(carrier, artifacts=ALL))
        assert report.can_submit is True, (carrier, report.reason_not_submitted())


# ---------------------------------------------------------------- the unverified gap


def test_nothing_here_is_claimed_verified() -> None:
    """The source is a paraphrase. A false statement in a filing is worse than an
    incomplete one, so the marker stays until a clause is transcribed."""
    outstanding = assert_all_transcribed()
    assert set(outstanding) == {"MSC", "CMA CGM", "ONE"}
    for spec in REQUIREMENTS.values():
        assert spec.verified is False
        assert "UNVERIFIED" in spec.note


def test_assert_all_transcribed_is_a_task_list_not_an_assertion() -> None:
    """It names the work, so closing the gap is visible rather than assumed."""
    for carrier, why in assert_all_transcribed().items():
        assert why, carrier
        assert "no " in why.lower() and "transcribed" in why.lower()


def test_a_transcribed_carrier_flips_the_marker() -> None:
    """Proving the marker is load bearing rather than decorative."""
    verified = CarrierRequirements(
        carrier="Test",
        requirements=(Requirement(Artifact.BOL_NUMBER),),
        source="a transcribed clause",
        verified=True,
    )
    report = evaluate(submission("Test", artifacts=BASE), requirements=verified)
    assert report.can_submit is True
    assert report.unverified is False
    assert "Test" not in assert_all_transcribed()
