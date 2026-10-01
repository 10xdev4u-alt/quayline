"""Issue 27: everything we do not hold, named, with a task attached.

The load bearing test is ``test_no_resolver_returns_a_rate_for_an_uncovered_carrier``.
The register is only worth anything if the refusal is mechanical rather than
documented, and a suite that checks the rows without asserting the refusal would
pass while an unverified rate quietly resolves.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import uncovered as module
from quayline.tariffs.registry import Registry
from quayline.tariffs.resolution import RateQuery, coverage_report, unverified_carriers
from quayline.tariffs.uncovered import (
    BY_CARRIER,
    UNCOVERED,
    UncoveredCarrier,
    acquisition_tasks,
    coverage_entries,
    is_uncovered,
)

# ---------------------------------------------------------------- the register


def test_all_five_carriers_are_registered() -> None:
    assert {u.carrier for u in UNCOVERED} == {"Yang Ming", "PIL", "HMM", "COSCO", "Evergreen"}


def test_each_row_carries_an_explicit_unverified_marker_in_code() -> None:
    """Criterion one. Not a comment: a row in a register the resolver reads."""
    assert len(UNCOVERED) == 5
    for row in UNCOVERED:
        assert isinstance(row, UncoveredCarrier)
        assert row.missing, row.carrier
        assert row.acquire, row.carrier
    assert len(BY_CARRIER) == 5


def test_each_row_says_what_exists_not_just_what_is_missing() -> None:
    """HMM's admission and COSCO's dispute policy are usable findings about
    carriers whose rates we cannot price. "Nothing" would lose them with the gap."""
    assert "admission" in BY_CARRIER["HMM"].holds
    assert "Docket 24-01" in BY_CARRIER["COSCO"].holds
    assert "036-I01" in BY_CARRIER["Evergreen"].holds


def test_is_uncovered_is_the_single_definition() -> None:
    """One predicate the resolver and the report share, so "we do not hold this"
    cannot mean two things in two places."""
    for carrier in ("Yang Ming", "PIL", "HMM", "COSCO", "Evergreen"):
        assert is_uncovered(carrier) is True, carrier
    assert is_uncovered("Maersk") is False
    assert is_uncovered("Hapag-Lloyd") is False
    assert is_uncovered("") is False


def test_the_register_is_immutable() -> None:
    with pytest.raises(AttributeError):
        BY_CARRIER["HMM"].missing = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# Named acquisition tasks.


def test_every_gap_has_a_named_task() -> None:
    """Criterion two. Specific enough that two people reading it would do the same
    thing, which is the test a task description has to pass."""
    tasks = acquisition_tasks()
    assert set(tasks) == {"Yang Ming", "PIL", "HMM", "COSCO", "Evergreen"}
    for carrier, task in tasks.items():
        assert len(task) > 40, carrier
        assert "tariff" in task.lower() or "rate" in task.lower(), carrier


def test_the_tasks_name_different_channels() -> None:
    """FMC submission, direct agency request, form transcription, filed copy. Five
    copies of "obtain the tariff" would be one task pretending to be five."""
    tasks = list(acquisition_tasks().values())
    assert len({t.split(",")[0] for t in tasks}) == 5


# ---------------------------------------------------------------- criterion 3
# No resolver returns a rate for an uncovered carrier.


def test_no_resolver_returns_a_rate_for_an_uncovered_carrier() -> None:
    """A plausible wrong rate is worse than a hole, so the refusal is mechanical:
    there is no block to resolve against, and an empty registry refuses everything."""
    for carrier in ("Yang Ming", "PIL", "HMM", "COSCO", "Evergreen"):
        got = Registry(()).resolve(RateQuery(reference=f"{carrier} test", on="2026-06-15"))
        assert got.block is None, carrier
        assert got.resolved is False, carrier


def test_the_refusal_says_it_is_our_hole() -> None:
    got = Registry(()).resolve(RateQuery(reference="HMM test", on="2026-06-15"))
    assert "hole in our tariff data" in got.withheld_reason


# ---------------------------------------------------------------- criterion 4
# Visible in the coverage report.


def test_the_five_appear_in_coverage_as_unusable() -> None:
    """Built from the same rows, so the report cannot drift from the register."""
    rows = coverage_entries()
    assert len(rows) == 5
    report = coverage_report(rows)
    assert all(not c.usable for c in report)
    assert set(unverified_carriers(rows)) == {"Yang Ming", "PIL", "HMM", "COSCO", "Evergreen"}


def test_coverage_notes_carry_the_gap_and_the_task() -> None:
    for row in coverage_entries():
        assert "UNVERIFIED" in row.note
        assert "Acquire:" in row.note


def test_deleting_a_row_is_how_a_transcription_lands() -> None:
    """The register shrinks by deletion in a diff somebody reviews, and every
    consumer updates at once because there was only ever one list."""
    assert len(UNCOVERED) == 5
    assert len(BY_CARRIER) == 5
    assert len(coverage_entries()) == 5


def test_issue_27_is_the_provenance() -> None:
    assert "Issue 27" in (module.__doc__ or "")


def test_the_module_states_holes_are_cheap() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Holes are cheap" in flat
    assert "Wrong rates are not" in flat
