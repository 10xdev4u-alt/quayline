"""Issue 5: two engines with different priors, and a finding that says which one made it.

The load bearing test is ``test_the_fmc_engine_inverts_the_default_burden``. The
rest check the machinery, and a suite that checks the machinery without asserting
the inversion would pass while the issue's central claim goes untested.
"""

from __future__ import annotations

import inspect

import pytest

from quayline.engine import forum as module
from quayline.engine.forum import (
    BURDEN_TABLE,
    BurdenRule,
    Forum,
    Party,
    burden_on,
    default_on_gap,
    evaluate,
)

# ---------------------------------------------------------------- the inversion


def test_the_fmc_engine_inverts_the_default_burden() -> None:
    """Criterion two. Before the FMC the carrier bears it; in a private dispute we
    do. The same gap, opposite loser, and that is the whole issue."""
    assert burden_on("reasonableness_of_charge", Forum.FMC_CHARGE_COMPLAINT).bearer is Party.CARRIER
    assert burden_on("reasonableness_of_charge", Forum.PRIVATE_DISPUTE).bearer is Party.FILER


def test_the_inversion_holds_for_every_catalogued_question() -> None:
    """Not just reasonableness. A table where one row inverts and two do not is a
    table whose author stopped halfway."""
    for question in BURDEN_TABLE:
        assert burden_on(question, Forum.FMC_CHARGE_COMPLAINT).bearer is Party.CARRIER, question
        assert burden_on(question, Forum.PRIVATE_DISPUTE).bearer is Party.FILER, question


def test_a_gap_cuts_against_opposite_parties() -> None:
    """The consequence, in words a letter can use."""
    fmc = default_on_gap("reasonableness_of_charge", Forum.FMC_CHARGE_COMPLAINT)
    private = default_on_gap("reasonableness_of_charge", Forum.PRIVATE_DISPUTE)
    assert "cuts against the carrier" in fmc
    assert "cuts against us" in private
    assert "41310(b)(2)" in fmc
    assert "41310" not in private, "the private engine cites no statute for its burden"


def test_the_private_engine_never_claims_a_statutory_burden() -> None:
    """There is none. A private letter invoking 41310(b)(2) would be quoting a forum
    it is not in, which is the misquotation this module exists to stop."""
    for question in BURDEN_TABLE:
        rule = burden_on(question, Forum.PRIVATE_DISPUTE)
        assert "41310" not in rule.consequence, question
        assert "U.S.C." not in rule.consequence, question


# ---------------------------------------------------------------- criterion 1
# Two engines with different priors.


def test_two_forums_exist() -> None:
    assert {f.value for f in Forum} == {"fmc_charge_complaint", "private_dispute"}


def test_the_burden_is_a_function_of_forum_not_a_flag() -> None:
    """Not one engine with a parameter. A flag is something somebody forgets to set,
    and the default it falls back to decides cases."""
    assert not hasattr(module, "Engine")
    assert not hasattr(module, "evaluate_with_burden_shifted")
    for question, per_forum in BURDEN_TABLE.items():
        assert set(per_forum) == {Forum.FMC_CHARGE_COMPLAINT, Forum.PRIVATE_DISPUTE}, question


def test_an_unknown_question_raises_rather_than_defaulting() -> None:
    """An unlisted question defaulting to either party would be a burden assigned by
    accident, and the party it lands on would deserve to know it was deliberate."""
    with pytest.raises(KeyError, match="no burden rule"):
        burden_on("whether_it_will_rain", Forum.FMC_CHARGE_COMPLAINT)


def test_the_fmc_burden_cites_the_statute() -> None:
    assert (
        "41310(b)(2)"
        in burden_on("reasonableness_of_charge", Forum.FMC_CHARGE_COMPLAINT).consequence
    )


# ---------------------------------------------------------------- criterion 3
# Documentation states which engine produced each finding.


def test_every_evaluated_finding_names_its_engine() -> None:
    """A finding that does not say which forum's rules it was evaluated under can be
    quoted in the wrong forum."""
    finding = evaluate("amount_variance", "money differs", Forum.FMC_CHARGE_COMPLAINT)
    assert finding.forum is Forum.FMC_CHARGE_COMPLAINT


def test_the_forum_is_required_not_defaulted() -> None:
    """The only constructor takes it positionally, so it cannot be omitted by
    accident. A default forum is a forum assigned by accident."""
    params = inspect.signature(evaluate).parameters
    assert params["forum"].default is inspect.Parameter.empty


def test_a_finding_knows_its_burden_rule() -> None:
    finding = evaluate("amount_variance", "money differs", Forum.FMC_CHARGE_COMPLAINT)
    rule = finding.burden
    assert rule is not None
    assert isinstance(rule, BurdenRule)
    assert rule.bearer is Party.CARRIER


def test_a_finding_outside_the_table_has_no_burden_rule() -> None:
    """Most arithmetic does not turn on a burden question, and saying so is better
    than inventing one."""
    finding = evaluate("tariff_unresolved", "no rate held", Forum.PRIVATE_DISPUTE)
    assert finding.burden is None


def test_the_finding_is_immutable() -> None:
    finding = evaluate("a", "b", Forum.FMC_CHARGE_COMPLAINT)
    with pytest.raises(AttributeError):
        finding.forum = Forum.PRIVATE_DISPUTE  # type: ignore[misc]


def test_the_result_is_deterministic() -> None:
    assert evaluate("a", "b", Forum.FMC_CHARGE_COMPLAINT) == evaluate(
        "a", "b", Forum.FMC_CHARGE_COMPLAINT
    )


# ---------------------------------------------------------------- what it is not


def test_neither_engine_invents_facts() -> None:
    """An adverse inference is a procedural consequence the forum assigns to an
    absence, not a finding that the missing document would have supported us. The
    module never produces a fact, only a bearer and a consequence."""
    rule = burden_on("reasonableness_of_charge", Forum.FMC_CHARGE_COMPLAINT)
    assert "adverse inference" in rule.consequence
    assert "would have supported" not in rule.consequence


def test_issue_5_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 5" in flat
    assert "41310(b)(2)" in flat


def test_the_module_states_what_reverses() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "postures reverse" in flat
    assert "wins one often loses the other" in flat
