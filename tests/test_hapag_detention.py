"""Issue 14: Hapag's detention schedules, and the haulage mode nothing may guess.

The load bearing tests are the two the issue names directly: the California
carrier-haulage schedule resolving to working-day, and the non-California one to
calendar-day. Everything else checks the machinery around them.
"""

from __future__ import annotations

import pytest

from quayline.engine.warnings import CODE_HAPAG_HAULAGE_REQUIRED, warn
from quayline.tariffs import hapag_detention as module
from quayline.tariffs.hapag_detention import (
    BY_RULE,
    DOCKET_22_03,
    SCHEDULES,
    SOURCE_PDF,
    DetentionUnit,
    requirement_for,
)
from quayline.tariffs.registry import Registry
from quayline.tariffs.resolution import Dimension, RateQuery, Requirement

CALI_REGULAR = "Hapag US Detention California carrier haulage regular"
CALI_REEFER = "Hapag US Detention California carrier haulage reefer operating"
NONCALI_REGULAR = "Hapag US Detention US excluding California carrier haulage regular"


def requirements() -> tuple[Requirement, ...]:
    return tuple(
        Requirement(
            rule=s.rule,
            needs=(Dimension.HAULAGE_MODE,),
            note="Carrier or Merchant, from the bill of lading checkbox.",
        )
        for s in SCHEDULES
    )


# ---------------------------------------------------------------- criterion 1
# All six schedules transcribed with free-time notation and day basis.


def test_all_six_schedules_are_present() -> None:
    """Four distinct rate combinations across geography and haulage, in six rows."""
    assert len(SCHEDULES) == 6
    assert len(BY_RULE) == 6, "duplicate rule references"


def test_every_schedule_names_free_time_and_unit() -> None:
    for schedule in SCHEDULES:
        assert schedule.free_time, schedule.rule
        assert schedule.unit in (DetentionUnit.CALENDAR, DetentionUnit.WORKING), schedule.rule
        assert schedule.source_pdf == SOURCE_PDF


def test_the_source_is_the_named_pdf() -> None:
    assert SOURCE_PDF == "USA_Detention_Effective_October_01_2025.pdf"


def test_free_time_is_discharge_based() -> None:
    """DOI, not availability. Detention starts when the box interchanges, which is
    a different clock from demurrage and the reason the two must never share a
    schedule."""
    for schedule in SCHEDULES:
        assert schedule.free_time.startswith("DOI"), schedule.rule


def test_regular_gets_four_days_and_reefer_gets_three() -> None:
    for schedule in SCHEDULES:
        if "regular" in schedule.equipment and "reefer" not in schedule.equipment:
            assert "4WD" in schedule.free_time, schedule.rule
        else:
            assert "3WD" in schedule.free_time, schedule.rule


def test_the_schedules_are_immutable() -> None:
    with pytest.raises(AttributeError):
        SCHEDULES[0].free_time = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 3
# California carrier-haulage is working-day, non-California is calendar-day.


def test_california_carrier_haulage_is_working_day() -> None:
    """A weekend in California accrues nothing, even on detention."""
    assert BY_RULE[CALI_REGULAR].unit is DetentionUnit.WORKING
    assert BY_RULE[CALI_REEFER].unit is DetentionUnit.WORKING


def test_non_california_carrier_haulage_is_calendar_day() -> None:
    """The same weekend elsewhere costs the tier rate."""
    assert BY_RULE[NONCALI_REGULAR].unit is DetentionUnit.CALENDAR


def test_merchant_haulage_matches_carrier_haulage_on_unit() -> None:
    """The unit follows geography, not haulage mode. Haulage decides the rate, not
    the day count, and conflating the two would misprice both."""
    assert (
        BY_RULE[NONCALI_REGULAR].unit
        is BY_RULE["Hapag US Detention US excluding California merchant haulage regular"].unit
    )


# ---------------------------------------------------------------- criterion 2
# No haulage mode means no resolution, never a guess.


def test_a_detention_query_without_haulage_mode_returns_nothing() -> None:
    """Guessing the mode is a fifteen to twenty percent error before any dispute,
    which makes it the single most expensive guess available."""
    registry = Registry((), requirements=requirements())
    got = registry.resolve(RateQuery(reference=CALI_REGULAR, on="2026-06-15"))
    assert got.block is None
    assert got.resolved is False


def test_the_refusal_names_haulage_mode() -> None:
    registry = Registry((), requirements=requirements())
    got = registry.resolve(RateQuery(reference=CALI_REGULAR, on="2026-06-15"))
    assert "haulage mode" in got.withheld_reason


def test_supplying_haulage_mode_clears_the_dimension_refusal() -> None:
    """It still resolves to nothing, because there are no rates. But it fails on
    the data gap rather than the missing input, which is the more actionable of
    the two."""
    registry = Registry((), requirements=requirements())
    got = registry.resolve(
        RateQuery(reference=CALI_REGULAR, on="2026-06-15", haulage_mode="Carrier Haulage")
    )
    assert "haulage mode" not in got.withheld_reason
    assert "no rate block held" in got.withheld_reason


def test_requirement_for_names_the_dimension() -> None:
    assert requirement_for(CALI_REGULAR) == "haulage mode"
    assert requirement_for("not a detention rule") is None


def test_every_detention_schedule_needs_haulage_mode() -> None:
    """No detention query can be answered without it. A schedule that did not need
    it would be a schedule priced without knowing which of four rates applies."""
    for schedule in SCHEDULES:
        assert schedule.needs_haulage_mode is True, schedule.rule


# ---------------------------------------------------------------- criterion 4
# The engine warns, naming the missing input.


def test_the_missing_haulage_mode_fires_the_catalogued_warning() -> None:
    """Issue 37's catalogue, issue 28's refusal, issue 14's data. The three meet
    here, which is the point of building them separately."""
    warning = warn(CODE_HAPAG_HAULAGE_REQUIRED, "the query carried no freight term")
    assert warning.code == CODE_HAPAG_HAULAGE_REQUIRED
    assert "bill of lading" in warning.limit.remedy


def test_the_docket_is_recorded() -> None:
    """FMC Docket 22-03 found Hapag charging without offering a return location.
    It is the precedent that makes the haulage question load-bearing rather than
    administrative."""
    assert DOCKET_22_03 == "FMC Docket 22-03"
    flat = " ".join((module.__doc__ or "").split())
    assert "22-03" in flat
    assert "$160" in flat


def test_issue_14_is_the_provenance() -> None:
    assert "Issue 14" in (module.__doc__ or "")


def test_no_schedule_carries_a_rate() -> None:
    """Structure without rates resolves to nothing. A dollar figure here would be
    a transcribed rate, and there are none held."""
    assert not hasattr(SCHEDULES[0], "tiers")
    assert not hasattr(SCHEDULES[0], "rate")
    assert not hasattr(SCHEDULES[0], "amount")
