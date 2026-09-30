"""Issue 13: Hapag per-terminal schedules with provenance, and no invented rates.

The load bearing tests are the two the issue names directly:
``test_savannah_is_calendar_day`` and ``test_la_apmt_is_working_day``. Everything
else checks the structure around them, and a suite that checks the structure
without asserting those two would pass while the issue's central claim goes
untested.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quayline.tariffs import hapag_terminals as module
from quayline.tariffs.blocks import Tier
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.hapag_terminals import (
    BY_CODE,
    EFFECTIVE_DATE,
    PUBLISHED_DATE,
    SCHEDULES,
    SOURCE_PDF,
    UNVERIFIED_SPOT_RATES,
    TierUnit,
    tiers_are_contiguous,
)

FIXTURES = "tests/fixtures/tariffs"


# ---------------------------------------------------------------- the nine terminals


def test_all_nine_required_terminals_are_present() -> None:
    """The criterion's list, by code. A missing terminal is a gateway we cannot
    reason about, and a gateway we cannot reason about is a hole that should fail
    loudly rather than silently."""
    codes = {s.code for s in SCHEDULES}
    for required in (
        "USSVNG",
        "USLAXB",
        "USLAXTP",
        "USLGB",
        "USNYC",
        "USHOU",
        "USOKL",
        "USCHS",
        "USBAL",
    ):
        assert required in codes, required


def test_every_schedule_records_free_time_basis_and_tier_unit() -> None:
    """Criterion two, minus the rates. Free-day notation, free-time basis and
    charge basis are transcribed; rate tiers are not held, so no schedule claims
    to price anything."""
    for schedule in SCHEDULES:
        assert schedule.free_time, schedule.code
        assert schedule.tier_unit in (TierUnit.CALENDAR, TierUnit.WORKING), schedule.code
        assert not hasattr(schedule, "tiers")
        assert not hasattr(schedule, "rate")


def test_every_schedule_carries_provenance() -> None:
    for schedule in SCHEDULES:
        assert schedule.source_pdf == SOURCE_PDF
        assert schedule.effective_date == EFFECTIVE_DATE


def test_the_source_is_the_named_pdf_with_both_dates() -> None:
    assert SOURCE_PDF == "USA_CH_Port_Demurrage_Import_Effective_August_01_2025.pdf"
    assert EFFECTIVE_DATE == "2025-08-01"
    assert PUBLISHED_DATE == "2025-06-27"


def test_free_time_is_discharge_plus_four_working_days_everywhere() -> None:
    """The table is uniform on free time and split on tier unit. That split is the
    whole reason this module exists."""
    assert {s.free_time for s in SCHEDULES} == {"DOD + 4WD"}


# ---------------------------------------------------------------- criterion 3
# Savannah calendar, LA APMT working.


def test_savannah_is_calendar_day() -> None:
    """A weekend in Savannah costs two days at the tier rate."""
    assert BY_CODE["USSVNG"].tier_unit is TierUnit.CALENDAR
    assert BY_CODE["USSVNG"].working_day_charging is False


def test_la_apmt_is_working_day() -> None:
    """A weekend in Los Angeles accrues nothing."""
    assert BY_CODE["USLAXB"].tier_unit is TierUnit.WORKING
    assert BY_CODE["USLAXB"].working_day_charging is True


def test_the_california_terminals_are_all_working_day() -> None:
    for code in ("USLAXB", "USLAXTP", "USLGB", "USOKL"):
        assert BY_CODE[code].tier_unit is TierUnit.WORKING, code


def test_the_gulf_and_east_coast_terminals_are_all_calendar() -> None:
    for code in ("USSVNG", "USNYC", "USHOU", "USCHS", "USBAL", "USSEA"):
        assert BY_CODE[code].tier_unit is TierUnit.CALENDAR, code


def test_schedules_are_immutable() -> None:
    with pytest.raises(AttributeError):
        BY_CODE["USSVNG"].free_time = "x"  # type: ignore[misc]


def test_by_code_covers_every_schedule() -> None:
    assert set(BY_CODE) == {s.code for s in SCHEDULES}
    assert len(BY_CODE) == len(SCHEDULES), "duplicate terminal codes"


# ---------------------------------------------------------------- criterion 4
# Tiers contiguous, no gap or overlap.


def test_contiguity_holds_on_the_maersk_corpus() -> None:
    """The mechanism proven where transcribed tiers exist.

    The Hapag schedules carry no tiers yet, so the checker cannot be proven on
    them. It is proven here against all eight Maersk rows, which is the same
    property on real data.
    """
    corpus = load_corpus(FIXTURES)
    assert len(corpus) == 8
    for rule, block in corpus.items():
        assert tiers_are_contiguous(block.tiers) is True, rule


def test_a_gap_is_not_contiguous() -> None:

    tiers = (Tier(1, 4, Decimal("0")), Tier(6, 8, Decimal("300")))
    assert tiers_are_contiguous(tiers) is False, "day 5 is priced by nobody"


def test_an_overlap_is_not_contiguous() -> None:

    tiers = (Tier(1, 5, Decimal("0")), Tier(5, 8, Decimal("300")))
    assert tiers_are_contiguous(tiers) is False, "day 5 is priced twice"


def test_a_non_terminal_open_tier_is_not_contiguous() -> None:
    """An open-ended tier in the middle leaves every later day unpriced."""

    tiers = (Tier(1, 4, Decimal("0")), Tier(5, None, Decimal("300")), Tier(9, 13, Decimal("345")))
    assert tiers_are_contiguous(tiers) is False


def test_tiers_must_start_at_day_one() -> None:

    assert tiers_are_contiguous((Tier(5, 8, Decimal("300")),)) is False


def test_an_empty_tier_list_is_vacuously_contiguous() -> None:
    """There is nothing to be gapped. The Hapag schedules are not tier lists, so
    this is about the checker, not about them."""
    assert tiers_are_contiguous(()) is True


def test_the_last_tier_must_be_open_ended() -> None:

    assert tiers_are_contiguous((Tier(1, 4, Decimal("0")), Tier(5, 8, Decimal("300")))) is False


# ---------------------------------------------------------------- what is absent


def test_no_hapag_rates_are_priced() -> None:
    """The spot rates lack day ranges and therefore cannot become tiers. Recorded
    as UNVERIFIED notes so they are visible rather than lost, and never priced."""
    assert len(UNVERIFIED_SPOT_RATES) == 4
    for note in UNVERIFIED_SPOT_RATES:
        assert "day ranges not transcribed" in note


def test_the_savannah_and_new_york_spot_rates_are_recorded() -> None:
    joined = " ".join(UNVERIFIED_SPOT_RATES)
    assert "$265" in joined and "$350" in joined and "$515" in joined
    assert "$625" in joined and "$970" in joined and "$1330" in joined
    assert "$1105" in joined and "$1480" in joined and "$1800" in joined


def test_issue_13_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 13" in flat or "issue 13" in flat


def test_the_module_states_why_there_are_no_rate_blocks() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "plausible wrong rate is worse than a hole" in flat
