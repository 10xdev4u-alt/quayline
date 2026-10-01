"""Issue 176: turning an audit result into a dispute packet.

The last break in the chain. Bytes go in, an ``AuditResult`` comes out, and without
this module the letter stops there. ``evidence/packet.py`` assembles and renders a
packet and nothing reachable from an audit builds one.

Every test here runs against the real fixture PDF, so the claims, days and citations
in the assertions are the ones the engine actually produces rather than ones written
to fit.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from quayline.engine.audit import audit
from quayline.engine.result import (
    CODE_DAYCOUNT_VARIANCE,
    CODE_FIELD_OMITTED,
    AuditResult,
    Finding,
)
from quayline.evidence.checklist import Artifact, Ground, Submission, evaluate
from quayline.evidence.packet import Claim, assemble, orphaned_evidence, render
from quayline.filing.dispute import claims_for, dispute_for
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.resolution import RateQuery, resolve

FIXTURES = Path(__file__).parent / "fixtures"
INVOICE_PDF = FIXTURES / "born_digital_invoice.pdf"


def audited(resolve_tariff: bool = True) -> AuditResult:
    """The real fixture, audited, with the disclosed rule resolved.

    ``resolve_tariff`` mirrors what the CLI does: resolve the rate rule the carrier
    disclosed under 541.6(c)(2) against the transcribed corpus. Issue 185 exists
    because nothing did that and the money check was unreachable outside a test.
    """
    resolution = None
    if resolve_tariff:
        resolution = resolve(
            RateQuery(reference="Maersk US Newark Dry", on="container", terminal="newark"),
            tuple(load_corpus().values()),
        )
    return audit(INVOICE_PDF.read_bytes(), "Maersk", "newark", resolution)


# ------------------------------------------------------------- the ground rules


def test_an_omission_finding_makes_the_whole_claim_automatic() -> None:
    """The merge rule, and it is the opposite of what I first wrote.

    The fixture produces two day-count findings on the same ground. With no tariff
    resolved both are omissions and the claim is automatic. With the tariff resolved
    they are demoted to diagnostics, and the first version of the merge used ``and``,
    which demoted a claim that needs no evidence into one that does, blocking a packet
    on evidence 541.5 says nobody has to supply.

    The rule is ``or``: an omission on the ground means the claim needs no showing,
    whatever else landed on it. A carrier that failed to disclose cannot demand proof
    of a disclosure that does not exist.
    """
    with_tariff = audited()
    without = audited(resolve_tariff=False)

    assert with_tariff.recomputed_total == Decimal("780.00")

    # Without a tariff the only findings are the two day-count ones, both omissions,
    # so the single claim is automatic and needs nothing.
    bare = dispute_for(without)
    assert [s.is_automatic for s in bare.sections] == [True]

    # With the tariff resolved there is also an amount variance, which is a different
    # ground and is contested, because the carrier disclosed everything and we are
    # asking it to redo a multiplication rather than to supply a missing disclosure.
    full = dispute_for(with_tariff)
    assert {s.claim.ground for s in full.sections} == {
        Ground.DISCLOSURE_OMITTED,
        Ground.CONTRACT_CONDITION,
    }
    omitted = full.section_for(Ground.DISCLOSURE_OMITTED)
    arithmetic = full.section_for(Ground.CONTRACT_CONDITION)
    assert omitted is not None and omitted.is_automatic is True
    assert arithmetic is not None and arithmetic.is_automatic is False


def test_the_amount_variance_claim_carries_the_money() -> None:
    """The claim a shipper cares about, with a number on it."""
    packet = dispute_for(audited())
    money = [s for s in packet.sections if s.claim.amount_at_stake is not None]

    assert money, "the amount variance claim states the exposure"
    assert money[0].claim.amount_at_stake == Decimal("390.00")


def test_claims_carry_the_days_the_findings_named() -> None:
    """A claim without its days is a claim the carrier cannot answer."""
    result = audited(resolve_tariff=False)
    packet = dispute_for(result)

    daycount = [f for f in result.findings if f.code == CODE_DAYCOUNT_VARIANCE]
    assert daycount, "the fixture produces a day count finding"

    claimed = {d for section in packet.sections for d in section.claim.days}
    for finding in daycount:
        assert set(finding.days) <= claimed, "every day a finding names must reach a claim"


def test_each_ground_gets_at_most_one_section() -> None:
    """``assemble`` refuses two claims on one ground, so this cannot be two."""
    grounds = [s.claim.ground for s in dispute_for(audited()).sections]

    assert len(grounds) == len(set(grounds))


def test_no_evidence_is_orphaned() -> None:
    """Evidence attached to a ground nothing claims on is a caller bug.

    ``assemble`` drops it silently and ``orphaned_evidence`` reports it, so the
    builder has to ask rather than assume.
    """
    claims, evidence = claims_for(audited())

    assert orphaned_evidence(claims, evidence) == ()


def test_the_packet_is_assembled_with_the_packet_module_not_a_copy() -> None:
    """One assembler. A second copy of the grouping rules is a second opinion."""
    result = audited()
    claims, evidence = claims_for(result)

    assert dispute_for(result).sections == assemble(claims, evidence).sections


# ------------------------------------------------------------ what it renders


def test_the_letter_names_every_cited_ground() -> None:
    packet = dispute_for(audited())
    text = render(packet)

    for section in packet.sections:
        assert section.claim.ground.value in text


def test_the_letter_carries_the_dates_and_not_just_a_count() -> None:
    """A carrier has to be able to check which days we mean."""
    assert "2026-07-08" in render(dispute_for(audited()))


def test_the_letter_states_the_remedy_for_an_automatic_claim() -> None:
    """The whole point of 541.5 is that the remedy needs no showing.

    Built from an explicit omission rather than from the fixture, because the
    fixture's findings are diagnostics now that the tariff resolves and a diagnostic
    is not automatic.
    """

    omitted = AuditResult(
        carrier="Maersk",
        findings=(
            Finding(
                code=CODE_FIELD_OMITTED,
                cite="541.6(c)(2)",
                summary="the invoice does not name the rate rule it billed under",
                grounds=(Ground.DISCLOSURE_OMITTED,),
            ),
        ),
    )
    text = render(dispute_for(omitted))

    assert "nothing from you" in text
    assert "automatic, no showing required" in text


def test_a_packet_with_no_findings_renders_without_claiming_a_dispute() -> None:
    """No findings must not produce a letter that reads like a dispute."""
    empty = type(audited())(carrier="Maersk", invoice_ref="MAEU1234567", findings=())
    text = render(dispute_for(empty))

    assert "no dispute" in text.lower()
    assert "NOT FILED" not in text


# --------------------------------------------------------------- money and gates


def test_a_claim_states_no_money_when_there_is_none() -> None:
    """No tariff resolved means no money on the claim.

    Not zero. Zero is a claim about the carrier's arithmetic and ``None`` is a claim
    about our reading of the document. Run without a resolved rate rule, which is the
    case for eight of the nine major gateways today.
    """
    for section in dispute_for(audited(resolve_tariff=False)).sections:
        assert section.claim.amount_at_stake is None


def test_the_packet_blocks_rather_than_silently_dropping() -> None:
    """A blocked ground stays in the packet marked blocked.

    Filing eight of nine claims and quietly dropping the ninth is how a partial win
    becomes a total loss, and the omission is only discoverable weeks later when
    the claim is time barred.
    """
    packet = dispute_for(audited())

    for section in packet.blocked_sections:
        assert section.reason, "a blocked section must say why"
        assert "NOT FILED" in render(packet)


def test_a_contested_finding_with_no_evidence_blocks_its_claim() -> None:
    """``assemble`` refuses to file an unsupported assertion. Prove it holds here."""
    packet = assemble((Claim(ground=Ground.APPOINTMENT_UNAVAILABLE, title="No appointment"),))

    assert packet.can_file is False
    assert "no evidence attached" in packet.reason_not_filed()


def test_carriers_with_no_transcribed_checklist_are_a_finding_not_a_crash() -> None:
    """An unknown carrier is the submission that gets rejected without explanation."""
    report = evaluate(
        Submission(carrier="Unknown Line", artifacts=frozenset(), grounds=frozenset())
    )

    assert report.can_submit is False
    assert report.unverified is True
    assert "no submission checklist" in report.findings[0].reason


def test_the_specific_charges_artifact_is_what_a_carrier_is_asked_for() -> None:
    """A carrier asks for "the specific charges disputed", not for a file name."""
    assert Artifact.SPECIFIC_CHARGES.value == "the specific charges disputed"


def test_money_is_never_invented_from_a_missing_total() -> None:
    result = audited(resolve_tariff=False)
    assert result.recomputed_total is None

    for section in dispute_for(result).sections:
        assert section.claim.amount_at_stake is None
        assert section.claim.amount_at_stake != Decimal(0)


@pytest.mark.parametrize("day", ["2026-07-07", "2026-07-08"])
def test_every_overbilled_day_reaches_the_letter(day: str) -> None:
    """The specific days the engine found are in the document the carrier reads."""
    assert day in render(dispute_for(audited()))
