"""Issue 34: what the letter leads with, and why.

The load bearing test is ``test_a_fixture_with_every_tier_orders_hard_void_first``.
Everything else checks one tier or one tiebreak, and a set of tests that each check
one thing will happily pass while the whole ordering is wrong.
"""

from __future__ import annotations

from datetime import date

import quayline.engine.ordering as module
from quayline.engine.ordering import (
    TIER_ARITHMETIC,
    TIER_BY_CODE,
    TIER_DEADLINE,
    TIER_HARD_VOID,
    TIER_SOFT_DEFECT,
    TIER_UNCLASSIFIED,
    OrderedFinding,
    order_findings,
    render_digest,
    strategy_for,
    tier_of,
)
from quayline.engine.result import (
    CODE_AMOUNT_VARIANCE,
    CODE_AVAILABILITY_CONTRADICTION,
    CODE_DAYCOUNT_VARIANCE,
    CODE_FIELD_OMITTED,
    CODE_TARIFF_UNRESOLVED,
    AuditResult,
    Finding,
)
from quayline.evidence.checklist import Ground

ONE = (date(2026, 7, 8),)
TWO = (date(2026, 7, 8), date(2026, 7, 9))


def f(
    code: str, summary: str = "s", days: tuple[date, ...] = (), grounds: tuple[Ground, ...] = ()
) -> Finding:
    return Finding(code=code, cite="x", summary=summary, days=days, grounds=grounds)


#: Every tier present, in the reverse of the order we want, so a stable sort that did
#: nothing would fail.
EVERY_TIER = (
    f(CODE_TARIFF_UNRESOLVED, "tariff did not resolve"),
    f("liability_basis_conclusory", "basis stated but conclusory"),
    f(CODE_DAYCOUNT_VARIANCE, "day count differs", TWO),
    f(CODE_AMOUNT_VARIANCE, "money differs", ONE),
    f("deadline_window_exceeded", "invoiced outside the window"),
    f(CODE_FIELD_OMITTED, "rates not disclosed"),
)


def audit(*findings: Finding) -> AuditResult:
    r = AuditResult(carrier="Maersk")
    for finding in findings:
        r = r.with_finding(finding)
    return r


# ---------------------------------------------------------------- the four tiers


def test_a_fixture_with_every_tier_orders_hard_void_first() -> None:
    """Criterion three. The one test that would catch a sort that does nothing."""
    ordered = order_findings(audit(*EVERY_TIER))
    tiers = [o.tier for o in ordered]
    assert tiers[0] == TIER_HARD_VOID, tiers
    assert tiers.index(TIER_DEADLINE) < tiers.index(TIER_ARITHMETIC)
    assert tiers.index(TIER_ARITHMETIC) < tiers.index(TIER_SOFT_DEFECT)
    assert set(tiers) == {
        TIER_HARD_VOID,
        TIER_DEADLINE,
        TIER_ARITHMETIC,
        TIER_SOFT_DEFECT,
    }


def test_the_tier_order_is_hard_void_then_deadline_then_arithmetic_then_soft() -> None:
    """Criterion one, as an explicit sequence rather than an emergent property."""
    order = [o.tier for o in order_findings(audit(*EVERY_TIER))]
    assert order == [
        TIER_HARD_VOID,
        TIER_DEADLINE,
        TIER_ARITHMETIC,
        TIER_ARITHMETIC,
        TIER_SOFT_DEFECT,
        TIER_SOFT_DEFECT,
    ]


def test_every_known_code_is_classified() -> None:
    """A code nobody placed should surface, not silently sort somewhere."""
    for code in TIER_BY_CODE:
        assert TIER_BY_CODE[code] in {
            TIER_HARD_VOID,
            TIER_DEADLINE,
            TIER_ARITHMETIC,
            TIER_SOFT_DEFECT,
        }, code


def test_only_the_omission_is_a_hard_void() -> None:
    """541.5 is the one automatic remedy in the category. Nothing else qualifies,
    and promoting anything else to it would be claiming a kill switch we do not
    have."""
    hard = [c for c, t in TIER_BY_CODE.items() if t == TIER_HARD_VOID]
    assert hard == [CODE_FIELD_OMITTED]


def test_the_availability_contradiction_is_arithmetic_not_a_void() -> None:
    """It is two disclosed numbers that cannot both be true, so it reads as a
    computation. Calling it a 541.5 event is exactly the claim issue 31 refuses."""
    assert TIER_BY_CODE[CODE_AVAILABILITY_CONTRADICTION] == TIER_ARITHMETIC


def test_an_unclassified_code_does_not_lead() -> None:
    """A finding nobody placed must not open a letter."""
    ordered = order_findings(audit(f("brand_new", "new checker"), *EVERY_TIER))
    assert ordered[-1].tier == TIER_UNCLASSIFIED
    assert ordered[0].tier == TIER_HARD_VOID


def test_an_unclassified_code_is_visible_rather_than_dropped() -> None:
    """It sorts last, not away. A finding that vanishes is a finding nobody can
    review."""
    ordered = order_findings(audit(f("brand_new", "new checker")))
    assert len(ordered) == 1
    assert ordered[0].tier == TIER_UNCLASSIFIED
    assert tier_of(f("brand_new", "x")) == TIER_UNCLASSIFIED


# ---------------------------------------------------------------- tiebreaks


def test_within_a_tier_the_most_days_comes_first() -> None:
    """Days, not dollars. A dollar figure needs a tariff we may not hold, and
    comparing two claims by money would price at least one from a rate the carrier
    never certified."""
    ordered = order_findings(
        audit(
            f(CODE_DAYCOUNT_VARIANCE, "one day", ONE), f(CODE_AMOUNT_VARIANCE, "five days", TWO * 2)
        )
    )
    assert [o.days_at_stake for o in ordered] == [4, 1]


def test_a_zero_day_finding_follows_one_within_its_tier() -> None:
    ordered = order_findings(
        audit(f(CODE_TARIFF_UNRESOLVED, "no days"), f(CODE_DAYCOUNT_VARIANCE, "days", ONE))
    )
    assert ordered[0].days_at_stake == 1


def test_ties_break_on_code_so_the_order_is_total() -> None:
    """A letter whose claim order depends on set iteration cannot be diffed, and the
    diff is most of the review."""
    a = audit(f(CODE_AMOUNT_VARIANCE, "a"), f(CODE_DAYCOUNT_VARIANCE, "b"))
    b = audit(f(CODE_DAYCOUNT_VARIANCE, "b"), f(CODE_AMOUNT_VARIANCE, "a"))
    assert [o.code for o in order_findings(a)] == [o.code for o in order_findings(b)]


def test_the_order_is_deterministic() -> None:
    assert order_findings(audit(*EVERY_TIER)) == order_findings(audit(*EVERY_TIER))


def test_the_input_order_does_not_matter() -> None:
    forward = order_findings(audit(*EVERY_TIER))
    backward = order_findings(audit(*reversed(EVERY_TIER)))
    assert [o.code for o in forward] == [o.code for o in backward]


# ---------------------------------------------------------------- the strategy


def test_the_strategy_names_the_leading_ground() -> None:
    """Criterion two. The claim the whole document is built around."""
    result = audit(
        f(CODE_DAYCOUNT_VARIANCE, "arithmetic", ONE, (Ground.GOVERNMENT_HOLD,)),
        f(CODE_FIELD_OMITTED, "void", (), (Ground.DISCLOSURE_OMITTED,)),
    )
    strategy = strategy_for(result)
    assert strategy.leading_ground is Ground.DISCLOSURE_OMITTED
    assert strategy.leading_code == CODE_FIELD_OMITTED


def test_a_void_lead_makes_it_a_compliance_notice() -> None:
    """A letter that leads with the omission gets routed to regulatory compliance,
    and the other claims get answered by the person who was never going to concede
    them."""
    assert strategy_for(audit(f(CODE_FIELD_OMITTED, "void"))).document_kind == "Compliance notice"
    assert strategy_for(audit(f(CODE_FIELD_OMITTED, "void"))).headline() == "Compliance notice"


def test_a_deadline_lead_makes_it_a_time_barred_claim() -> None:
    assert strategy_for(audit(f("deadline_window_exceeded", "late"))).document_kind == (
        "Time-barred claim"
    )


def test_an_arithmetic_lead_makes_it_a_recomputation() -> None:
    assert strategy_for(audit(f(CODE_DAYCOUNT_VARIANCE, "days", ONE))).document_kind == (
        "Recomputation"
    )


def test_a_soft_defect_lead_is_still_a_dispute() -> None:
    strategy = strategy_for(audit(f(CODE_TARIFF_UNRESOLVED, "unresolved")))
    assert strategy.document_kind == "Dispute"
    assert strategy.headline() == "Dispute"


def test_an_unclassified_lead_is_a_query_not_a_dispute() -> None:
    """Saying so is better than letting the reader infer it from paragraph order."""
    assert strategy_for(audit(f("brand_new", "x"))).document_kind == "Query, not yet a dispute"


def test_no_findings_is_nothing_to_send() -> None:
    strategy = strategy_for(AuditResult(carrier="Maersk"))
    assert strategy.document_kind == "Nothing to send"
    assert strategy.leading_code == ""
    assert strategy.tier_counts == {}


def test_the_strategy_counts_every_tier() -> None:
    assert strategy_for(audit(*EVERY_TIER)).tier_counts == {
        TIER_HARD_VOID: 1,
        TIER_DEADLINE: 1,
        TIER_ARITHMETIC: 2,
        TIER_SOFT_DEFECT: 2,
    }


# ---------------------------------------------------------------- the renderer


def test_the_renderer_uses_the_order() -> None:
    """Criterion four."""
    text = render_digest(strategy_for(audit(*EVERY_TIER)), order_findings(audit(*EVERY_TIER)))
    assert text.index("rates not disclosed") < text.index("invoiced outside the window")
    assert text.index("invoiced outside the window") < text.index("day count differs")
    assert text.index("day count differs") < text.index("tariff did not resolve")


def test_the_renderer_leads_with_the_headline() -> None:
    text = render_digest(strategy_for(audit(*EVERY_TIER)), order_findings(audit(*EVERY_TIER)))
    assert text.startswith("Compliance notice")


def test_the_renderer_names_the_citation_for_each_claim() -> None:
    """A claim a respondent cannot check the authority for is an opinion."""
    result = audit(
        Finding(code=CODE_FIELD_OMITTED, cite="541.6(c)(3)", summary="Rates not disclosed")
    )
    text = render_digest(strategy_for(result), order_findings(result))
    assert "541.6(c)(3)" in text


def test_the_renderer_says_nothing_to_send_on_an_empty_audit() -> None:
    result = AuditResult(carrier="Maersk")
    assert "No findings" in render_digest(strategy_for(result), order_findings(result))


def test_the_renderer_is_deterministic() -> None:
    result = audit(*EVERY_TIER)
    assert render_digest(strategy_for(result), order_findings(result)) == render_digest(
        strategy_for(result), order_findings(result)
    )


# ---------------------------------------------------------------- what it is not


def test_ordering_does_not_change_whether_the_audit_can_file() -> None:
    """Otherwise ordering would be a waiver in disguise."""
    blocked = audit(f(CODE_FIELD_OMITTED, "void"))
    assert blocked.can_file is False
    assert order_findings(blocked)
    assert strategy_for(blocked).document_kind == "Compliance notice"


def test_ordering_does_not_drop_or_add_findings() -> None:
    ordered = order_findings(audit(*EVERY_TIER))
    assert len(ordered) == len(EVERY_TIER)
    assert {o.code for o in ordered} == {x.code for x in EVERY_TIER}


def test_there_is_no_partial_order_or_priority_score() -> None:
    """Four tiers, not a ranked list. A partial order would reintroduce the
    judgement this module exists to remove."""
    assert not hasattr(OrderedFinding, "priority")
    assert not hasattr(OrderedFinding, "weight")
    assert not hasattr(OrderedFinding, "score")


def test_days_worth_is_none_rather_than_zero_for_no_days() -> None:
    """Issue 38's rule, still holding in a new place. A zero here would be a
    convenience that becomes a claim."""
    item = OrderedFinding(finding=f("x", "y"), tier=TIER_SOFT_DEFECT, days_at_stake=0)
    assert item.days_worth() is None
    assert item.days_worth() != 0


def test_issue_34_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 34" in flat
    assert "negotiation" in flat
    assert "compliance notice" in flat


def test_the_module_says_why_the_order_is_by_remedy_not_by_evidence() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "strength of remedy" in flat
    assert "not by how much work each claim took" in flat
