"""Issue 19: CMA CGM demurrage is a bundle, so only the whole line is disputable.

The load bearing test is ``test_no_partial_storage_credit_can_be_proposed``. The
bundle rule is only worth anything if nothing in the codebase can propose the
credit it forbids, and a suite that checks the rule's text without asserting that
would pass while a caller prices half a line.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import cma_cgm as module
from quayline.tariffs.cma_cgm import (
    BALTIMORE_EFFECTIVE,
    BALTIMORE_FREE_DAYS,
    BALTIMORE_TIER_1,
    BUNDLE_QUOTE,
    GENERIC_STATUS,
    BundleLine,
    baltimore_tier_1,
    generic_status,
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
