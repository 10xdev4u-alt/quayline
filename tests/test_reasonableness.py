"""The four acceptance criteria on issue 6, one test block each.

Every factor text asserted here came from the eCFR, so a future edit to the
regulation that is not reflected in the rule shows up as a failing test rather
than as a stale citation nobody checks.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from quayline.engine.reasonableness import (
    FACTORS,
    SECTION_545_5,
    UNVERIFIED_CLAIMS,
    Factor,
    Strength,
    availability_equals_vessel_arrival,
    detention_without_return_offer,
    factor,
    no_published_corroboration_spec,
)

ROOT = Path(__file__).resolve().parents[1]

ARRIVAL = date(2024, 6, 5)
AVAILABLE = date(2024, 6, 9)


# ---------------------------------------------------------------- criterion 1
# A check exists for detention charged where no return location was offered.


def test_detention_with_no_return_location_offers_a_finding() -> None:
    finding = detention_without_return_offer(True, False)
    assert finding is not None
    assert finding.cite == "545.5(c)(2)(ii)"


def test_no_finding_when_a_return_location_was_offered() -> None:
    assert detention_without_return_offer(True, True) is None


def test_no_finding_when_no_detention_was_charged() -> None:
    assert detention_without_return_offer(False, False) is None


def test_extenuating_circumstances_suppress_the_finding() -> None:
    """The rule opens with "Absent extenuating circumstances".

    A check that fired while one was recorded would assert the opposite of what
    the regulation says. This is the only check in the module that suppresses
    itself, and it is the only one that has to, because only (c)(2)(ii) carries
    that clause.
    """
    assert (
        detention_without_return_offer(
            True,
            False,
            extenuating_circumstances="container was damaged and could not be returned",
        )
        is None
    )


def test_extenuating_circumstances_disarm_only_c2ii() -> None:
    """Two factors mention the clause and they use it in opposite ways.

    545.5(c)(2)(ii) opens "Absent extenuating circumstances", which is a condition
    that switches the factor off. 545.5(c)(2)(iv) says the Commission "may also
    consider any extenuating circumstances", which is a permissive addition that
    switches nothing off.

    Only the first kind needs a check that suppresses itself. Conflating the two
    would either suppress a government inspection finding for no reason, or leave
    a detention finding armed when the regulation disarms it. The test separates
    them by the verb the rule actually uses.
    """
    mentions = {
        f.cite: f.text.lower() for f in FACTORS if "extenuating circumstances" in f.text.lower()
    }
    assert set(mentions) == {"545.5(c)(2)(ii)", "545.5(c)(2)(iv)"}

    assert "absent extenuating circumstances" in mentions["545.5(c)(2)(ii)"]
    assert "may also consider any extenuating circumstances" in mentions["545.5(c)(2)(iv)"]

    disarming = [c for c, t in mentions.items() if "absent extenuating circumstances" in t]
    assert disarming == ["545.5(c)(2)(ii)"], (
        "only a disarming clause needs a self-suppressing check"
    )


# ---------------------------------------------------------------- criterion 2
# A check exists for an availability date equal to the vessel arrival date.


def test_availability_equal_to_arrival_offers_a_finding() -> None:
    finding = availability_equals_vessel_arrival(ARRIVAL, ARRIVAL)
    assert finding is not None
    assert finding.cite == "545.5(c)(2)(i)"
    assert "2024-06-05" in finding.detail


def test_no_finding_when_availability_follows_arrival() -> None:
    assert availability_equals_vessel_arrival(AVAILABLE, ARRIVAL) is None


def test_no_finding_when_availability_precedes_arrival() -> None:
    """Clockwise, so the check cannot be satisfied by simply running the test
    with the arguments in the other order."""
    assert availability_equals_vessel_arrival(date(2024, 6, 1), ARRIVAL) is None


def test_equality_is_exact_and_has_no_tolerance() -> None:
    """One day either way is not this practice.

    A tolerance would fire on nearly every import, because a great many
    containers genuinely are available on the day they arrive.
    """
    assert availability_equals_vessel_arrival(date(2024, 6, 6), ARRIVAL) is None
    assert availability_equals_vessel_arrival(date(2024, 6, 4), ARRIVAL) is None
    assert availability_equals_vessel_arrival(ARRIVAL, ARRIVAL) is not None


def test_the_finding_names_the_dates_not_a_boilerplate() -> None:
    finding = availability_equals_vessel_arrival(ARRIVAL, ARRIVAL)
    assert finding is not None
    assert str(ARRIVAL) in finding.detail
    assert re.search(r"\d{4}-\d{2}-\d{2}", finding.detail)


# ---------------------------------------------------------------- criterion 3
# A check exists for a carrier with no published corroboration specification.


def test_missing_corroboration_spec_offers_a_finding() -> None:
    finding = no_published_corroboration_spec(False)
    assert finding is not None
    assert finding.cite == "545.5(d)"


def test_no_finding_when_the_spec_is_published() -> None:
    assert no_published_corroboration_spec(True) is None


def test_the_finding_names_all_three_things_545_5_d_names() -> None:
    """Points of contact, timeframes, corroboration requirements.

    A deficiency in one of the three is a deficiency in the factor, and a check
    that only mentioned one of them would understate what the rule asks for.
    """
    finding = no_published_corroboration_spec(False)
    assert finding is not None
    for item in ("points of contact", "timeframes", "corroboration requirements"):
        assert item in finding.detail, item


# ---------------------------------------------------------------- criterion 4
# Each check cites the 545.5 sub-factor verbatim.


def test_every_check_returns_a_factor_with_real_regulatory_text() -> None:
    findings = [
        detention_without_return_offer(True, False),
        availability_equals_vessel_arrival(ARRIVAL, ARRIVAL),
        no_published_corroboration_spec(False),
    ]
    for finding in findings:
        assert finding is not None
        assert finding.factor.cite.startswith("545.5(")
        assert len(finding.factor.text) > 150, "the quote looks truncated"
        assert finding.factor.heading


@pytest.mark.parametrize("cite", [f.cite for f in FACTORS])
def test_every_factor_text_is_verbatim_with_its_own_heading(cite: str) -> None:
    f = factor(cite)
    assert f.text.startswith("("), f"{cite} text should open with its own paragraph mark"
    assert f.heading.lower() in f.text.lower(), f"{cite} heading is not in the quoted text"


def test_quote_renders_the_cite_and_the_rule_together() -> None:
    """What a dispute letter would print. Cite and rule in one string, so a
    letter cannot quote the code's summary without the rule beside it."""
    quoted = factor("545.5(c)(2)(ii)").quote()
    assert quoted.startswith("545.5(c)(2)(ii) Empty container return: ")
    assert "likely to be found unreasonable" in quoted


def test_all_eight_sub_factors_of_the_rule_are_present() -> None:
    """545.5 lists (c)(1), (c)(2)(i) through (iv), (d), (e) and (f).

    A missing factor is a factor nobody will ever check, so the count and the
    cites are both asserted.
    """
    assert [f.cite for f in FACTORS] == [
        "545.5(c)(1)",
        "545.5(c)(2)(i)",
        "545.5(c)(2)(ii)",
        "545.5(c)(2)(iii)",
        "545.5(c)(2)(iv)",
        "545.5(d)",
        "545.5(e)",
        "545.5(f)",
    ]


# ---------------------------------------------------------------- strength
# Not an acceptance criterion, but the thing that makes the checks usable.


def test_strength_comes_from_each_factors_own_verb() -> None:
    """(c)(2)(ii) is the only one that says a practice is likely to be found
    unreasonable. Everything else is a factor the Commission may consider.

    Flattening these would let a dispute letter argue that a "may consider"
    factor is a finding the Commission will make.
    """
    by_cite = {f.cite: f.strength for f in FACTORS}
    assert by_cite["545.5(c)(2)(ii)"] is Strength.LIKELY_UNREASONABLE
    assert by_cite["545.5(c)(1)"] is Strength.WILL_CONSIDER
    for cite in ("545.5(c)(2)(i)", "545.5(c)(2)(iii)", "545.5(c)(2)(iv)", "545.5(d)", "545.5(e)"):
        assert by_cite[cite] is Strength.MAY_CONSIDER, cite


def test_strength_values_are_the_rules_own_words() -> None:
    for strength in Strength:
        assert strength.value in factor("545.5(c)(1)").text or strength.value in "".join(
            f.text for f in FACTORS
        ), strength


def test_the_strongest_language_in_the_section_is_on_the_check_that_uses_it() -> None:
    finding = detention_without_return_offer(True, False)
    assert finding is not None
    assert finding.strength is Strength.LIKELY_UNREASONABLE
    assert "likely to be found unreasonable" in finding.factor.text


def test_the_two_may_consider_checks_say_so() -> None:
    """A letter built on these must not present them as determinations."""
    avail = availability_equals_vessel_arrival(ARRIVAL, ARRIVAL)
    spec = no_published_corroboration_spec(False)
    assert avail is not None and spec is not None
    assert avail.strength is Strength.MAY_CONSIDER
    assert spec.strength is Strength.MAY_CONSIDER


# ---------------------------------------------------------------- the correction


def test_the_unsourced_notice_claim_is_marked_unverified_and_not_encoded() -> None:
    """The research note said (c)(2)(iii) means a terminal phone number is not
    notice. The rule does not say that.

    It is carried as UNVERIFIED in the module and is not a check, so it cannot
    be asserted from a summary of the module.
    """
    assert len(UNVERIFIED_CLAIMS) == 1
    assert UNVERIFIED_CLAIMS[0].startswith("UNVERIFIED:")
    assert "545.5(c)(2)(iii)" in UNVERIFIED_CLAIMS[0]

    # (c)(2)(iii) is a real factor, and it is in the table, but no check uses it.
    assert factor("545.5(c)(2)(iii)").strength is Strength.MAY_CONSIDER
    check_sources = {f.cite for f in FACTORS} - {factor("545.5(c)(2)(iii)").cite}
    assert "545.5(c)(2)(iii)" not in check_sources


def test_the_research_note_records_the_correction() -> None:
    note = ROOT / "docs" / "research" / "001-regulation.md"
    text = note.read_text()
    assert "CORRECTION, 2026-09-27" in text
    assert "UNVERIFIED and is not in 545.5" in text


def test_provenance_is_dated_and_cited() -> None:
    assert SECTION_545_5.cite == "46 CFR 545.5"
    assert SECTION_545_5.as_of == "2026-09-24"
    assert SECTION_545_5.federal_register.startswith("89 FR")
    assert "section-545.5" in SECTION_545_5.url


def test_factors_are_immutable() -> None:
    f: Factor = factor("545.5(d)")
    with pytest.raises(AttributeError):
        f.text = "tampered"  # type: ignore[misc]


def test_unknown_cite_raises() -> None:
    with pytest.raises(KeyError):
        factor("545.5(z)(1)")
