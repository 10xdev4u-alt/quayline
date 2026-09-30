"""Issue 33: the most dangerous field on the invoice.

The load bearing test is ``test_a_single_delay_invalidates_the_whole_invoice``.
Everything else checks the mechanism around it, and a suite that checks the
mechanism without asserting that one delay voids the whole invoice would pass
while the issue's central claim goes untested.
"""

from __future__ import annotations

from datetime import date

import pytest

from quayline.regulation import certification as cert
from quayline.regulation.certification import (
    CITE_CIVIL_PENALTIES,
    CITE_E2,
    CITE_UNREASONABLE_PRACTICE,
    EVIDENCE_NEEDED,
    CarrierCausedDelay,
    DelayKind,
    e2_field,
    evidence_needed,
)
from quayline.regulation.certification import (
    test_certification as run_certification,
)
from quayline.regulation.checklist import by_cite
from quayline.regulation.kill_switch import Obligation, Omission, effect_of

JULY_2 = date(2026, 7, 2)
JULY_5 = date(2026, 7, 5)


def delay(on: date = JULY_2, kind: DelayKind = DelayKind.ROLLOVER) -> CarrierCausedDelay:
    return CarrierCausedDelay(occurred=on, kind=kind, source="rollover notice R-441")


# ---------------------------------------------------------------- criterion 1
# Absence is already a hard void from the presence check.


def test_absence_is_a_hard_void_through_the_existing_path() -> None:
    """No new code. The omission check the kill switch already runs fires on a
    missing (e)(2), and duplicating it here would create a second place the same
    absence is evaluated.

    Asserted so the absence stays routed through one path even as this module grows.
    """
    omission = Omission(field=by_cite(CITE_E2), invoice_ref="INV-1")
    assert effect_of([omission]) is Obligation.ELIMINATED
    assert e2_field() is by_cite(CITE_E2), "the same clause, not a second copy of it"


def test_the_e2_cite_is_the_checklist_field() -> None:
    field = by_cite(CITE_E2)
    assert field.cite == "541.6(e)(2)"
    assert "did not cause or contribute" in field.text


# ---------------------------------------------------------------- criterion 2
# When affirmed, the check reports it is testable and lists the evidence needed.


def test_an_affirmed_certification_with_no_delays_stands() -> None:
    """A certification we cannot falsify is a certification that stands, and knowing
    that before the letter goes out is the difference between a demand and an
    embarrassment."""
    result = run_certification(())
    assert result.invalidated is False
    assert result.voids_invoice is False
    assert "makes no claim about the carrier" in result.sentence()


def test_the_result_carries_what_was_consulted() -> None:
    result = run_certification(())
    assert result.evidence_consulted == EVIDENCE_NEEDED


def test_the_result_is_immutable() -> None:
    result = run_certification((delay(),))
    with pytest.raises(AttributeError):
        result.invalidated = False  # type: ignore[misc]


def test_the_test_is_deterministic() -> None:
    assert run_certification((delay(),)) == run_certification((delay(),))


# ---------------------------------------------------------------- criterion 3
# The evidence list: rollover notices, schedule vs arrival, delivery timestamps.


def test_the_evidence_list_names_all_three() -> None:
    """Closed, because an open-ended "anything showing fault" is how a vague
    suspicion becomes a filed claim."""
    assert evidence_needed() == EVIDENCE_NEEDED
    joined = " ".join(EVIDENCE_NEEDED)
    assert "rollover" in joined
    assert "schedule against its actual arrival" in joined
    assert "delivery order timestamps" in joined


def test_the_evidence_list_is_exactly_three() -> None:
    """A fourth item added quietly is a fourth kind of evidence nobody agreed to
    require."""
    assert len(EVIDENCE_NEEDED) == 3


def test_the_delay_kinds_are_exactly_the_evidence_kinds() -> None:
    """So a delay can always be evidenced by something on the list, and something
    on the list always maps to a kind. A mismatch in either direction is a test the
    module cannot pass."""
    assert {k.value for k in DelayKind} == {
        "booking rollover",
        "vessel late against schedule",
        "delivery order issued late",
    }


def test_a_delay_without_a_source_is_refused() -> None:
    """A delay with no source is an allegation, not evidence, and an allegation filed
    as a 41102(c) violation is a good way to lose the whole dispute."""
    with pytest.raises(ValueError, match="allegation"):
        CarrierCausedDelay(occurred=JULY_2, kind=DelayKind.ROLLOVER, source="   ")


# ---------------------------------------------------------------- criterion 4
# A single documented carrier-caused delay invalidates the whole invoice.


def test_a_single_delay_invalidates_the_whole_invoice() -> None:
    """The central claim.

    The certification is a blanket representation about the invoice, not a per-day
    one. A representation false in any part is false, and there is no reading under
    which the true days survive. The respondent cannot concede the delay and keep
    the certification.
    """
    result = run_certification((delay(),))
    assert result.invalidated is True
    assert result.voids_invoice is True


def test_the_sentence_says_the_whole_invoice() -> None:
    sentence = run_certification((delay(),)).sentence()
    assert "fails for the whole invoice" in sentence
    assert "false in any part is false" in sentence


def test_two_delays_do_not_invalidate_twice() -> None:
    """Invalidation is boolean. There is no double void and no stronger void."""
    one = run_certification((delay(),))
    two = run_certification((delay(), delay(JULY_5, DelayKind.LATE_VESSEL)))
    assert one.invalidated is True
    assert two.invalidated is True
    assert one.voids_invoice == two.voids_invoice


def test_a_delay_on_one_day_voids_days_it_does_not_cover() -> None:
    """The point made concrete. A July 2 rollover voids a charge billed July 8
    through 11, because the statement it falsifies was about the whole invoice."""
    result = run_certification((delay(JULY_2),))
    assert result.voids_invoice is True
    assert "whole invoice" in result.sentence()


def test_each_delay_kind_invalidates_on_its_own() -> None:
    """No kind is weaker than the others. A rollover and a late delivery order are
    different facts that falsify the same sentence."""
    for kind in DelayKind:
        assert run_certification((delay(kind=kind),)).invalidated is True, kind


def test_the_sentence_names_the_kind() -> None:
    sentence = run_certification((delay(JULY_5, DelayKind.LATE_DELIVERY_ORDER),)).sentence()
    assert "delivery order issued late" in sentence


# ---------------------------------------------------------------- what it is not


def test_the_certification_is_not_a_kill_switch_finding() -> None:
    """It produces a test result, not an omission. The 541.5 consequence flows from
    the result through the existing path, not from a second omission type."""
    # isinstance is rejected by mypy as unreachable, because the two types have
    # disjoint bases, and that rejection is the proof rather than a nuisance. What
    # carries the meaning is that a CertificationTest has no field naming a missing
    # disclosure, because it is not an omission, and an Omission has one.
    result = run_certification((delay(),))
    assert not hasattr(result, "field")
    assert "field" in Omission.__dataclass_fields__


def test_the_penalty_cites_travel_with_the_module() -> None:
    """41102(c) is the violation and 41107 is the penalties. No other invoice defect
    in this package carries a penalty provision, so getting the cite wrong here is
    worse than getting it wrong anywhere else."""
    assert CITE_UNREASONABLE_PRACTICE == "46 U.S.C. 41102(c)"
    assert CITE_CIVIL_PENALTIES == "46 U.S.C. 41107"
    assert "41102" in (cert.__doc__ or "")
    assert "41107" in (cert.__doc__ or "")


def test_the_module_states_the_field_is_dangerous_in_both_directions() -> None:
    """For the carrier, because a false affirmation is a federal violation and not
    just a billing dispute. For us, because alleging falsity without a documented
    delay is an accusation we cannot support."""
    flat = " ".join((cert.__doc__ or "").split())
    assert "federal violation" in flat
    assert "embarrassment" in flat


def test_the_module_states_why_the_test_is_worth_running_when_we_expect_to_lose() -> None:
    flat = " ".join((cert.__doc__ or "").split())
    assert "knowing that before the letter goes out" in flat


def test_issue_33_is_the_provenance() -> None:
    assert "Issue 33" in (cert.__doc__ or "")
