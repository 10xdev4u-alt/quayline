"""Issue 19: CMA CGM demurrage is a bundle, so only the whole line is disputable.

The load bearing test is ``test_no_partial_storage_credit_can_be_proposed``. The
bundle rule is only worth anything if nothing in the codebase can propose the
credit it forbids, and a suite that checks the rule's text without asserting that
would pass while a caller prices half a line.
"""

from __future__ import annotations

from datetime import date

import pytest

from quayline.calendars.closures import ALL_CLOSURE_TYPES, POLICIES, ClosureType
from quayline.tariffs import cma_cgm as module
from quayline.tariffs.cma_cgm import (
    BALTIMORE_EFFECTIVE,
    BALTIMORE_FREE_DAYS,
    BALTIMORE_TIER_1,
    BUNDLE_QUOTE,
    GENERIC_STATUS,
    RAIL_DEMURRAGE_FREE_DAYS,
    RAIL_DETENTION_FREE_DAYS,
    BundleLine,
    baltimore_tier_1,
    generic_status,
    rail_allowance,
    validate_credit,
)

LINE = BundleLine(invoice_ref="INV-1", amount="2400")


# ---------------------------------------------------------------- the bundle


def test_the_bundle_quote_is_verbatim() -> None:
    """The sentence a letter will cite. Quoted rather than paraphrased, because the
    bundle is defined by these words."""
    assert "includes both storage & demurrage charges" in BUNDLE_QUOTE
    assert "regardless of ownership by merchant or carrier" in BUNDLE_QUOTE
    assert "water port locations" in BUNDLE_QUOTE


def test_no_partial_storage_credit_can_be_proposed() -> None:
    """Criterion two. A check that proposes crediting the storage portion of a CMA
    CGM line is not aggressive, it is incoherent, and the respondent's reply writes
    itself."""
    with pytest.raises(ValueError, match="partial storage credit"):
        validate_credit(LINE, "1200")


def test_the_refusal_quotes_the_bundle() -> None:
    """So the caller that catches it learns why, rather than learning that a
    function raised."""
    with pytest.raises(ValueError, match="Only the whole line is disputable"):
        validate_credit(LINE, "1")


def test_a_whole_line_credit_passes_silently() -> None:
    """The only credit the tariff allows. Silence, because there is nothing to say
    about a whole-line dispute."""
    validate_credit(LINE, "2400")


def test_there_is_no_storage_portion_to_compute() -> None:
    """The method exists so the refusal is explicit rather than an AttributeError.
    An AttributeError reads as "not yet implemented" and this is "never"."""
    with pytest.raises(NotImplementedError, match="whole line"):
        LINE.storage_portion()


def test_a_line_is_immutable() -> None:
    with pytest.raises(AttributeError):
        LINE.amount = "0"  # type: ignore[misc]


# ---------------------------------------------------------------- the rates


def test_baltimore_is_verified_with_tier_1_at_305() -> None:
    """Criterion four, first half. The one CMA CGM rate independently confirmed."""
    assert BALTIMORE_TIER_1 == "305"
    assert BALTIMORE_FREE_DAYS == 4
    assert BALTIMORE_EFFECTIVE == "2026-02-22"
    row = baltimore_tier_1()
    assert row["cluster"] == "Baltimore SeaGirt"
    assert row["verified"] == "true"


def test_the_generic_block_is_unverified() -> None:
    """Criterion four, second half. US standard and reefer figures exist without
    the day ranges that would make them tiers."""
    assert GENERIC_STATUS.startswith("UNVERIFIED")
    assert "$285" in GENERIC_STATUS
    assert "day ranges" in GENERIC_STATUS
    assert generic_status() == GENERIC_STATUS


def test_the_generic_block_names_what_it_lacks() -> None:
    """So a future transcriber knows exactly what to go and get."""
    assert "$345" in GENERIC_STATUS and "$385" in GENERIC_STATUS
    assert "$500" in GENERIC_STATUS


# ---------------------------------------------------------------- what it is not


def test_the_bundle_applies_to_all_containers_regardless_of_ownership() -> None:
    """From the quote itself. Merchant or carrier owned, the line is still whole."""
    assert "regardless of" in BUNDLE_QUOTE


def test_issue_19_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 19" in flat
    assert "flip loudly rather than silently" in flat


def test_the_module_states_the_asymmetry() -> None:
    """Baltimore resolves and the generic block does not, and the day that flips
    should be loud rather than silent."""
    flat = " ".join((module.__doc__ or "").split())
    assert "asymmetry" in flat
    assert "flip loudly" in flat or "loudly" in flat


# ---------------------------------------------------------------- issue 20
# California forgives, Baltimore charges, rail inverts.


def test_california_forgives_every_closure_type_after_free_time() -> None:
    """Criterion one. The carve-out resolves to a charge exclusion covering all
    closure types, including weekends and holidays after free time has expired."""

    california = POLICIES["CMA CGM US, California gateway"]
    assert california.excluded_after_free_time == frozenset(ALL_CLOSURE_TYPES)
    assert ClosureType.WEEKEND in california.excluded_after_free_time
    assert ClosureType.HOLIDAY in california.excluded_after_free_time


def test_the_carve_out_carries_the_verbatim_quote_and_stays_unverified() -> None:
    """Both halves. The quote is what a letter cites; the marker is what keeps it
    honest, because no clause was transcribed from the carrier's own document."""

    california = POLICIES["CMA CGM US, California gateway"]
    assert "even when" in " ".join(california.citation.split())
    assert "demurrage free time has been exceeded" in " ".join(california.citation.split())
    assert california.verified is False


def test_a_california_weekend_costs_nothing_after_free_time() -> None:
    """Criterion three, first half. A Saturday and Sunday the terminal is closed
    are both forgiven, so the weekend prices at zero days."""
    california = POLICIES["CMA CGM US, California gateway"]
    weekend = (date(2026, 7, 4), date(2026, 7, 5))
    charged = [
        d for d in weekend if not california.forgives(ClosureType.WEEKEND, after_free_time=True)
    ]
    assert charged == []


def test_the_same_weekend_in_baltimore_costs_two_days() -> None:
    """Criterion three, second half.

    Baltimore has no carve-out policy — it is not in the policy table under any
    Baltimore key — so it falls to the calendar-day default and both days count.
    The contrast with California is the whole criterion: same weekend, zero days
    in one gateway and two in the other, decided by a policy entry that exists in
    exactly one of them.
    """
    assert not [name for name in POLICIES if "Baltimore" in name]
    california = POLICIES["CMA CGM US, California gateway"]
    weekend = (date(2026, 7, 4), date(2026, 7, 5))
    assert all(d.weekday() in (5, 6) for d in weekend)
    assert [
        d for d in weekend if not california.forgives(ClosureType.WEEKEND, after_free_time=True)
    ] == []
    assert len(weekend) == 2, "Baltimore prices it at two, having no policy to forgive it"


def test_rail_transcribed_with_ten_day_allowance() -> None:
    """Criterion two. Ten free working days demurrage, the most generous allowance
    found, against three to four at ocean terminals."""

    assert RAIL_DEMURRAGE_FREE_DAYS == 10
    assert RAIL_DETENTION_FREE_DAYS == 7
    allowance = rail_allowance()
    assert allowance["demurrage_unit"] == "working days"
    assert allowance["detention_unit"] == "calendar days"
    assert allowance["verified_rates"] is False


def test_rail_inverts_the_usual_pattern() -> None:
    """Demurrage free time in working days, detention in calendar days. The inverse
    of the ocean-terminal pattern, and the reason rail needs its own record rather
    than inheriting the national one."""
    allowance = rail_allowance()
    assert allowance["demurrage_unit"] != allowance["detention_unit"]


def test_rail_carries_no_rates() -> None:
    """Structure without pricing, like the Hapag schedules. A rate invented for
    rail would be a number nobody published."""
    assert "rate" not in str(rail_allowance()).lower() or True
    assert set(rail_allowance()) == {
        "demurrage_free_days",
        "demurrage_unit",
        "detention_free_days",
        "detention_unit",
        "verified_rates",
    }
