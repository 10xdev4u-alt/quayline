"""Issue 59: the packet, grouped by ground, automatic claims first."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from quayline.evidence.checklist import Artifact, Ground
from quayline.evidence.packet import (
    Claim,
    EvidenceItem,
    GroundSection,
    assemble,
    order_claims,
    orphaned_evidence,
    render,
)

DAYS = (date(2026, 7, 8), date(2026, 7, 9))
BOND = Artifact.BOL_NUMBER


def timing(automatic: bool = False) -> Claim:
    return Claim(
        ground=Ground.GOVERNMENT_HOLD,
        title="Free time consumed during a government hold",
        days=DAYS,
        amount_at_stake=Decimal("2400.00"),
        basis="the container was held by CBP from 2026-07-01",
        automatic=automatic,
    )


def contract() -> Claim:
    return Claim(
        ground=Ground.CONTRACT_CONDITION,
        title="Free time per the service contract, not the tariff",
        days=DAYS,
        basis="the service contract grants 7 days and the tariff 4",
    )


def no_show() -> Claim:
    """A disclosure claim, which is automatic because there is nothing to show."""
    return Claim(
        ground=Ground.DISCLOSURE_OMITTED,
        title="Service contract not produced",
        automatic=True,
    )


def ev(ground: Ground, description: str = "a document") -> EvidenceItem:
    return EvidenceItem(ground=ground, kind=BOND, description=description, source="a scan")


# ---------------------------------------------------------------- criterion 1
# Evidence items attach to a specific ground.


def test_evidence_lands_under_its_own_ground_only() -> None:
    packet = assemble(
        (timing(), contract()),
        (
            ev(Ground.GOVERNMENT_HOLD, "CBP hold notice"),
            ev(Ground.CONTRACT_CONDITION, "the contract"),
        ),
    )
    assert [e.description for e in packet.evidence_for(Ground.GOVERNMENT_HOLD)] == [
        "CBP hold notice"
    ]
    assert [e.description for e in packet.evidence_for(Ground.CONTRACT_CONDITION)] == [
        "the contract"
    ]


def test_evidence_for_one_ground_never_appears_under_another() -> None:
    """The mixing failure this whole module exists to prevent."""
    packet = assemble((timing(), contract()), (ev(Ground.CONTRACT_CONDITION, "the contract"),))
    text = render(packet)
    gov = text.split("## Free time consumed during a government hold")[1].split("\n## ")[0]
    assert "the contract" not in gov


def test_an_item_supports_exactly_one_ground() -> None:
    """The ground is a single member, so an item cannot quietly cover two.

    Proven by the type rather than by an isinstance dance, since a Ground can never
    also be a tuple.
    """
    item = EvidenceItem(ground=Ground.GOVERNMENT_HOLD, kind=BOND, description="x")
    assert isinstance(item.ground, Ground)
    assert item.ground is Ground.GOVERNMENT_HOLD
    assert len({item.ground}) == 1


def test_evidence_for_a_ground_nobody_claimed_is_reported_not_discarded() -> None:
    """A caller bug that silently drops evidence is found after filing."""
    claims = (contract(),)
    evidence = (ev(Ground.CONTRACT_CONDITION), ev(Ground.GOVERNMENT_HOLD, "stray"))
    packet = assemble(claims, evidence)
    assert [e.description for e in orphaned_evidence(claims, evidence)] == ["stray"]
    assert len(packet.sections) == 1, "a stray must not create a phantom section"


def test_two_claims_on_one_ground_is_refused() -> None:
    """Two sections for one concession means the carrier concedes one and refuses
    the other inside a single heading."""
    with pytest.raises(ValueError, match="two claims on"):
        assemble((timing(), timing()))


def test_a_disclosure_claim_and_a_factual_claim_can_coexist() -> None:
    """The collision that produced Ground.DISCLOSURE_OMITTED.

    Filing a missing disclosure under GOVERNMENT_HOLD was the first draft's
    design and it was wrong, because it made two separate concessions share one
    heading.
    """
    packet = assemble((timing(), no_show()), (ev(Ground.GOVERNMENT_HOLD),))
    assert len(packet.sections) == 2
    assert packet.can_file is True


# ---------------------------------------------------------------- criterion 2
# A ground with no evidence is filing-blocked, not silently omitted.


def test_a_ground_with_no_evidence_blocks_filing() -> None:
    packet = assemble((timing(),), ())
    assert packet.can_file is False
    assert len(packet.blocked_sections) == 1


def test_the_blocked_ground_is_still_in_the_packet() -> None:
    """Never silently omitted. It is present, and marked."""
    text = render(assemble((timing(),), ()))
    assert "Free time consumed during a government hold" in text
    assert "NOT FILED" in text


def test_a_blocked_ground_carries_no_fabricated_evidence() -> None:
    section = assemble((timing(),), ()).section_for(Ground.GOVERNMENT_HOLD)
    assert section is not None
    assert section.evidence == ()
    assert section.reason


def test_one_blocked_ground_blocks_the_whole_packet() -> None:
    """Filing eight of nine and dropping the ninth turns a partial win into a loss."""
    packet = assemble((timing(), contract(), no_show()), (ev(Ground.CONTRACT_CONDITION),))
    assert packet.can_file is False
    assert [s.claim.ground for s in packet.blocked_sections] == [Ground.GOVERNMENT_HOLD]
    assert len(packet.sections) == 3, "the blocked ground is not removed"


def test_an_automatic_ground_is_never_blocked() -> None:
    """There is nothing to prove, so there is nothing to be missing."""
    packet = assemble((no_show(),), ())
    assert packet.can_file is True
    assert packet.blocked_sections == ()


# ---------------------------------------------------------------- criterion 3
# The packet renders in claim order, automatic wins first.


def test_automatic_claims_render_first() -> None:
    packet = assemble(
        (contract(), no_show(), timing()),
        (ev(Ground.CONTRACT_CONDITION), ev(Ground.GOVERNMENT_HOLD)),
    )
    text = render(packet)
    assert text.index("## Service contract not produced") < text.index(
        "## Free time per the service contract"
    )
    assert text.index("## Free time per the service contract") < text.index(
        "## Free time consumed during a government hold"
    )


def test_the_renderer_groups_under_automatic_and_contested() -> None:
    text = render(assemble((no_show(), contract()), (ev(Ground.CONTRACT_CONDITION),)))
    assert text.index("Automatic claims") < text.index("Contested claims")


def test_the_order_is_stable_not_reshuffled() -> None:
    """A claim order that changes between drafts cannot be diffed, and the diff is
    most of the review."""
    claims = (contract(), no_show(), timing())
    first = [c.title for c in order_claims(claims)]
    second = [c.title for c in order_claims(tuple(reversed(claims)))]
    auto = "Service contract not produced"
    assert [t for t in first if t == auto] == [t for t in second if t == auto]
    assert order_claims(claims) == order_claims(claims)


def test_an_automatic_claim_says_it_needs_no_evidence() -> None:
    text = render(assemble((no_show(),), ()))
    assert "automatic, no showing required" in text
    assert "none required" in text


def test_a_contested_claim_names_its_basis() -> None:
    text = render(assemble((contract(),), (ev(Ground.CONTRACT_CONDITION),)))
    assert "the service contract grants 7 days" in text


def test_a_long_day_list_is_summarised_and_actually_truncated() -> None:
    """A ten day claim printed all ten dates and then claimed there were seven more."""
    many = tuple(date(2026, 7, 1) + timedelta(days=i) for i in range(10))
    claim = Claim(ground=Ground.GOVERNMENT_HOLD, title="Long", days=many, basis="b")
    text = render(assemble((claim,), (ev(Ground.GOVERNMENT_HOLD),)))
    assert "(+7 more)" in text
    assert text.count("2026-07-") == 3, "the list itself must be truncated, not just labelled"


def test_a_short_day_list_is_printed_in_full() -> None:
    text = render(assemble((timing(),), (ev(Ground.GOVERNMENT_HOLD),)))
    assert "Days (2): 2026-07-08, 2026-07-09" in text
    assert "more)" not in text


def test_an_empty_packet_says_so() -> None:
    assert "No claims" in render(assemble(()))


def test_the_render_is_deterministic() -> None:
    args = ((contract(), no_show(), timing()), (ev(Ground.GOVERNMENT_HOLD),))
    assert render(assemble(*args)) == render(assemble(*args))


# ---------------------------------------------------------------- criterion 4
# Every filing worthy ground either has evidence or blocks filing.


def test_every_filing_worthy_ground_has_evidence_or_blocks() -> None:
    """The invariant, over a matrix rather than one hand built case."""
    cases = [
        (Ground.GOVERNMENT_HOLD, False),
        (Ground.CONTRACT_CONDITION, False),
        (Ground.APPOINTMENT_UNAVAILABLE, False),
        (Ground.DISCLOSURE_OMITTED, True),
    ]
    for keep_evidence in (True, False):
        for ground, automatic in cases:
            claim = Claim(
                ground=ground, title=f"claim on {ground.value}", basis="b", automatic=automatic
            )
            evidence = (ev(ground),) if keep_evidence else ()
            packet = assemble((claim,), evidence)
            section = packet.section_for(ground)
            assert section is not None
            if claim.needs_evidence and not evidence:
                assert section.blocked is True, (ground, automatic, keep_evidence)
                assert packet.can_file is False
            else:
                assert section.blocked is False, (ground, automatic, keep_evidence)
                if claim.needs_evidence:
                    assert packet.can_file is True


def test_no_section_is_ever_silent() -> None:
    """Whatever the outcome, a section either carries evidence or a reason."""
    packet = assemble((timing(), contract(), no_show()), (ev(Ground.CONTRACT_CONDITION),))
    for section in packet.sections:
        assert section.evidence or section.blocked or section.claim.automatic


def test_a_blocked_section_and_an_evidenced_section_coexist() -> None:
    packet = assemble((timing(), contract()), (ev(Ground.CONTRACT_CONDITION),))
    assert {s.claim.ground: s.blocked for s in packet.sections} == {
        Ground.GOVERNMENT_HOLD: True,
        Ground.CONTRACT_CONDITION: False,
    }


def test_the_ground_section_is_immutable() -> None:
    """A packet edited after assembly is a packet nobody reviewed."""
    section = GroundSection(claim=timing(), evidence=(), blocked=True, reason="r")
    with pytest.raises(AttributeError):
        section.blocked = False  # type: ignore[misc]
