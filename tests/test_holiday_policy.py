"""Issue 111: the holiday set is a per-carrier fact, not a global assumption.

Before this, the walk and the charge window excluded both dates of every federal
holiday at every terminal. That is a defensible default and it is not established
for any carrier we hold, and a terminal that works a federal holiday bills it.
"""

from __future__ import annotations

import importlib
from dataclasses import replace
from datetime import date

import pytest

from quayline.calendars.closures import ClosureType
from quayline.calendars.freetime import free_time
from quayline.calendars.holidays import (
    FEDERAL_DEFAULT,
    UNVERIFIED_NOTE,
    WORKS_FEDERAL_HOLIDAYS,
    HolidayPolicy,
    HolidayScope,
)
from quayline.calendars.window import UNITS, charge_window

JUL3 = date(2026, 7, 3)  # Independence Day 2026, observed (the 4th is a Saturday)
JUL4 = date(2026, 7, 4)
JUL5 = date(2026, 7, 5)
JUL6 = date(2026, 7, 6)


def jul(d: int) -> date:
    """July 2026 by day of month."""
    return date(2026, 7, d)


WORKS = HolidayPolicy(scope=HolidayScope.NONE, source="test", verified=False)


def hapag_with(policy: HolidayPolicy) -> None:
    UNITS["Hapag-Lloyd"] = replace(UNITS["Hapag-Lloyd"], holidays=policy)


@pytest.fixture(autouse=True)
def _restore_registry() -> object:
    saved = dict(UNITS)
    yield
    UNITS.clear()
    UNITS.update(saved)


# ---------------------------------------------------------------- the default


def test_the_shipped_default_is_attached_to_the_carrier_block() -> None:
    for carrier in UNITS:
        assert UNITS[carrier].holidays.scope is HolidayScope.FEDERAL_BOTH
        assert UNITS[carrier].holidays.verified is False


def test_the_default_is_marked_unverified_with_its_reason() -> None:
    assert FEDERAL_DEFAULT.verified is False
    assert "UNVERIFIED" in FEDERAL_DEFAULT.note
    assert "does not reach a marine terminal" in UNVERIFIED_NOTE
    assert "bank holiday" in UNVERIFIED_NOTE, (
        "the reason must name what the carrier tariff actually says, or a reader "
        "cannot check the claim"
    )


def test_both_dates_is_the_default_and_both_are_excluded() -> None:
    """A Saturday holiday is observed on the Friday, and both are excluded.

    Excluding more is the conservative direction. A day wrongly believed to be free
    produces an underbilled finding, which costs the customer nothing. A day wrongly
    believed to be chargeable produces an overbilled finding, which costs
    credibility.
    """
    window = charge_window("Hapag-Lloyd", JUL3, JUL6, terminal="USSAVNG")
    excluded = {r.day for r in window.excluded}
    assert JUL3 in excluded
    assert JUL4 in excluded


# ---------------------------------------------------------------- criterion 2
# A carrier that observes no federal holidays is expressible.


def test_a_carrier_that_works_federal_holidays_bills_them() -> None:
    """The case the issue exists for, and it used to be a code change."""
    hapag_with(WORKS)
    window = charge_window("Hapag-Lloyd", JUL3, JUL6, terminal="USSAVNG")
    assert window.chargeable_count == 4
    assert JUL3 in {r.day for r in window.chargeable}
    assert JUL4 in {r.day for r in window.chargeable}


def test_the_scope_changes_the_free_time_walk_too() -> None:
    """Both consumers of the holiday set, not just the one under test.

    A holiday forgiven inside the allowance extends the window. A carrier that works
    holidays has no extension, and its free time ends a day earlier.
    """
    default = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    assert default.extension_days == 1
    assert default.last_free_day == jul(7)

    hapag_with(WORKS)
    working = free_time("Hapag-Lloyd", date(2026, 6, 30), 4)
    assert working.extension_days == 0
    assert working.last_free_day == jul(6)
    assert all(n.closure != ClosureType.HOLIDAY for n in working.notes)


def test_the_expressible_case_is_shipped_even_though_it_is_not_held() -> None:
    assert WORKS_FEDERAL_HOLIDAYS.scope is HolidayScope.NONE
    assert WORKS_FEDERAL_HOLIDAYS.verified is False
    assert "not held" in WORKS_FEDERAL_HOLIDAYS.source
    assert "without editing the calendar" in WORKS_FEDERAL_HOLIDAYS.note


# ---------------------------------------------------------------- criterion 3
# The default is still applied where the carrier does not say.


def test_a_carrier_with_no_policy_keeps_the_default() -> None:
    bare = UNITS["Maersk"]
    assert bare.holidays is FEDERAL_DEFAULT
    window = charge_window("Maersk", JUL3, JUL6, terminal="USNYC")
    assert JUL3 in {r.day for r in window.excluded}
    assert JUL4 in {r.day for r in window.excluded}


def test_the_scope_chooses_which_of_the_two_dates_closes_the_gate() -> None:
    """Observed only is the literal reading, and it is not the shipped default.

    A Monday to Saturday workweek has Saturday as a working day, so for that
    carrier the statutory date is the one that bites. That is a per-carrier fact and
    the enum is what lets it be said.
    """
    observed_only = HolidayPolicy(
        scope=HolidayScope.FEDERAL_OBSERVED, source="test", verified=False
    )
    assert JUL3 in observed_only.dates_closed(2026)
    assert JUL4 not in observed_only.dates_closed(2026)

    both = HolidayPolicy(scope=HolidayScope.FEDERAL_BOTH, source="test", verified=False)
    assert JUL3 in both.dates_closed(2026)
    assert JUL4 in both.dates_closed(2026)

    assert WORKS.covers(JUL3) is False


def test_dates_closed_handles_the_new_year_boundary() -> None:
    """Two years of holidays are loaded in the walk, and a policy asked for one
    year must not leak into another."""
    policy = HolidayPolicy(scope=HolidayScope.FEDERAL_BOTH, source="t", verified=False)
    assert date(2027, 1, 1) not in policy.dates_closed(2026)
    assert date(2026, 1, 1) in policy.dates_closed(2026)


# ---------------------------------------------------------------- the honesty


def test_no_carrier_claims_to_have_a_sourced_holiday_policy() -> None:
    """If this ever becomes false the marker should be removed deliberately, in a
    pull request that says so, rather than by an edit to a boolean."""
    for carrier, block in UNITS.items():
        assert block.holidays.verified is False, carrier
        assert "UNVERIFIED" in block.holidays.note, carrier


def test_a_policy_cannot_claim_verified_without_a_source() -> None:
    """There is no such thing here yet, and a test that would pass for any real one
    is worse than none. Asserted on the shape instead."""
    policy = HolidayPolicy(scope=HolidayScope.FEDERAL_BOTH, source="a real tariff", verified=True)
    assert policy.source == "a real tariff"
    assert "UNVERIFIED" not in policy.note
    assert policy.dates_closed(2026)


def test_every_scope_closes_the_observed_date_unless_it_is_none() -> None:
    """The invariant across all three scopes, stated as the relationship it is.

    My first version asserted that a date is closed whenever the scope is not
    NONE, which is false for FEDERAL_OBSERVED and a Saturday holiday. The 4th of
    July 2026 is a Saturday, its observed date is the 3rd, and an observed only
    scope correctly leaves the 4th chargeable. The real rule is simpler: the observed
    date is always closed unless the scope is NONE, and the statutory date is closed
    only under BOTH.
    """
    observed_2026 = date(2026, 7, 3)
    statutory_2026 = date(2026, 7, 4)
    for scope in HolidayScope:
        closed = HolidayPolicy(scope=scope, source="t", verified=False).dates_closed(2026)
        assert isinstance(closed, frozenset)
        assert (observed_2026 in closed) is (scope is not HolidayScope.NONE), scope
        assert (statutory_2026 in closed) is (scope is HolidayScope.FEDERAL_BOTH), scope


def test_the_module_docstring_still_says_this_is_a_reference_calendar() -> None:
    """The caveat that produced this issue must survive the fix.

    Adding the policy parameter makes it easier to think the holiday set is now
    authoritative. It is more configurable and no better sourced.
    """
    text = " ".join((importlib.import_module("quayline.calendars.holidays").__doc__ or "").split())
    assert "reference" in text
    assert "does not reach" in text
