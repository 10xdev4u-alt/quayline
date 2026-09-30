"""Issue 7: the three elements per day per charge, with the third marked required.

The load bearing test is ``test_a_day_with_one_and_two_but_not_three_is_flagged``.
A suite that checks each element in isolation would pass while the interaction the
issue names goes untested, because the failure is specifically a day that looks
claimable until the third question is asked.
"""

from __future__ import annotations

from datetime import date

import pytest

import quayline.regulation.evergreen as module
from quayline.regulation.evergreen import (
    DayAssessment,
    Element,
    claimable_days,
    third_element_gaps,
)

JULY_8 = date(2026, 7, 8)
JULY_9 = date(2026, 7, 9)


def met(evidence: str = "gate roster showing no pickup window") -> Element:
    return Element(met=True, evidence=evidence)


def unmet() -> Element:
    return Element(met=False)


def assessment(
    day: date = JULY_8,
    one: Element | None = None,
    two: Element | None = None,
    three: Element | None = None,
    waive_three: bool = False,
) -> DayAssessment:
    return DayAssessment(
        day=day,
        charge_ref="INV-1 demurrage",
        unable_to_move=one if one is not None else met(),
        outside_control=two if two is not None else met("port authority closure notice"),
        no_incentive_effect=three if three is not None else met("rate exceeded drayage cost"),
        element_three_required=not waive_three,
    )


# ---------------------------------------------------------------- criterion 1
# Every assessment records all three, and the third is required.


def test_an_assessment_records_all_three_elements() -> None:
    a = assessment()
    assert a.unable_to_move.met is True
    assert a.outside_control.met is True
    assert a.no_incentive_effect.met is True
    assert a.complete is True


def test_the_third_element_is_required_by_default() -> None:
    """The one shippers skip. A default that silently waived it would reproduce the
    exact failure this module exists to stop."""
    a = assessment(three=unmet())
    assert a.complete is False
    assert a.third_unmet is True


def test_waiving_the_third_is_deliberate_and_named() -> None:
    a = assessment(three=unmet(), waive_three=True)
    assert a.complete is True
    assert a.element_three_required is False


def test_a_met_element_with_no_evidence_is_refused() -> None:
    """An element marked met with nothing behind it is a claim with nothing behind
    it."""
    with pytest.raises(ValueError, match="no evidence"):
        Element(met=True, evidence="   ")


def test_the_assessment_is_immutable() -> None:
    a = assessment()
    with pytest.raises(AttributeError):
        a.day = JULY_9  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# A packet refuses an unflagged third-element gap.


def test_a_day_with_one_and_two_but_not_three_is_flagged() -> None:
    """The criterion's case and the failure the issue names.

    Elements one and two met, three required and unmet: a day that looks claimable
    until the third question is asked.
    """
    a = assessment(three=unmet())
    assert a.third_unmet is True
    assert a.complete is False
    flag = a.flag()
    assert "element 3" in flag
    assert "where complaints die" in flag
    assert JULY_8.isoformat() in flag
    assert "INV-1 demurrage" in flag


def test_a_complete_day_has_no_flag() -> None:
    assert assessment().flag() == ""


def test_claimable_days_refuses_incomplete_days_by_default() -> None:
    """The default is what runs when nobody thought about it, and an unflagged
    incomplete day in a letter is a day the respondent dismantles first."""
    days = (assessment(), assessment(day=JULY_9, three=unmet()))
    assert claimable_days(days) == (days[0],)


def test_claimable_days_passes_everything_when_flagging_is_allowed() -> None:
    """Allowed is not the same as unflagged. The caller takes the days and the
    obligation to attach each flag."""
    days = (assessment(), assessment(day=JULY_9, three=unmet()))
    assert claimable_days(days, allow_flagged=True) == days
    assert days[1].flag() != ""


def test_a_day_missing_element_one_is_not_a_third_element_gap() -> None:
    """Different failure, different handling. The third-element rule is specifically
    about days that look claimable."""
    a = assessment(one=unmet(), three=unmet())
    assert a.third_unmet is False
    assert a.complete is False
    assert "element 1" in a.flag()


def test_third_element_gaps_names_exactly_the_failure_mode() -> None:
    days = (
        assessment(),
        assessment(day=JULY_9, three=unmet()),
        assessment(day=date(2026, 7, 10), one=unmet()),
    )
    gaps = third_element_gaps(days)
    assert len(gaps) == 1
    assert gaps[0].day == JULY_9


# ---------------------------------------------------------------- the case


def test_the_case_is_cited() -> None:

    flat = " ".join((module.__doc__ or "").split())
    assert "Evergreen Shipping Agency v. FMC" in flat
    assert "106 F.4th 1113" in flat
    assert "not a bright-line rule" in flat


def test_the_module_states_why_three_is_hard() -> None:
    """Elements one and two are facts about the world. Three is a counterfactual
    about incentives, which is why it gets skipped."""
    flat = " ".join((module.__doc__ or "").split())
    assert "counterfactual" in flat


def test_issue_7_is_the_provenance() -> None:

    assert "Issue 7" in (module.__doc__ or "")


def test_the_assessment_is_deterministic() -> None:
    assert assessment() == assessment()
    assert assessment().flag() == assessment().flag()
