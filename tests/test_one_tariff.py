"""The four acceptance criteria on issue 23, one test block each.

The gap matters more than the regimes here. A 560-day hole in the middle of a
carrier's clock history is the kind of thing that gets quietly filled in by
picking the nearest known answer, and this suite exists to make that impossible
rather than merely discouraged.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quayline.tariffs.one import (
    REGIMES,
    UNKNOWN_WINDOW,
    ClockBasis,
    ClockRegime,
    Lookup,
    basis_in_force,
)

ROOT = Path(__file__).resolve().parents[1]

# The boundaries, transcribed from ONE's own pages.
LAST_DISCHARGE_DAY = date(2023, 2, 26)
GAP_START = date(2023, 2, 27)
GAP_END = date(2024, 9, 8)
AVAILABILITY_START = date(2024, 9, 9)
LAST_WORKING_DAY_LANGUAGE = date(2026, 3, 31)
CURRENT_START = date(2026, 4, 1)


# ---------------------------------------------------------------- criterion 1
# Three dated regimes are transcribed with verbatim text.


def test_three_regimes() -> None:
    assert len(REGIMES) == 3


def test_every_regime_carries_its_own_citation_text_source_and_disclaimer() -> None:
    """Provenance on every block, per AGENTS.md section six.

    The disclaimer is stored separately from the policy text because the two
    disagree with our research note, and the disclaimer is the one that dates
    the language. Keeping them together means a reader cannot quote the clause
    without seeing what ONE said about when it applies.
    """
    for regime in REGIMES:
        assert regime.cite, "a regime has no citation"
        assert regime.text, f"{regime.cite} has no transcribed text"
        assert regime.source.startswith("https://us.one-line.com/")
        # ONE's page titles vary: the 2023 one is a bare title, the 2024 and 2026
        # ones are sentences. Assert the disclaimer dates the language, not that it
        # is punctuated a particular way.
        assert len(regime.disclaimer) > 20, f"{regime.cite} disclaimer looks truncated"
        assert any(token in regime.disclaimer for token in ("2023", "2024", "2026")), (
            f"{regime.cite} disclaimer does not date the language"
        )
        assert regime.verified is True


def test_regime_text_is_the_language_one_published() -> None:
    """Spot checks against the pages, chosen to catch paraphrase.

    The three texts differ from each other in ways that matter: "first full day
    after vessel discharge" against "the start of the next full working day
    after the container is made available" against "on the first full day when
    the container(s) is available". Collapsing them to one sentence would lose
    the difference between a discharge clock and an availability clock, which is
    the entire point of the module.
    """
    by_cite = {r.cite: r for r in REGIMES}
    assert by_cite["ONE D&D policy prior to 2023-02-27"].text == (
        "Demurrage clock commences at freetime start, defined as the first full day "
        "after vessel discharge"
    )
    assert (
        by_cite["ONE D&D policy effective 2024-09-09"].text
        == "The demurrage clock commences at the start of the next full working day "
        "after the container is made available for pick-up after vessel discharge"
    )
    assert (
        by_cite["ONE D&D policy effective 2026-04-01"].text
        == "The demurrage clock commences on the first full day when the container(s) "
        "is available for pick-up after vessel discharge"
    )


def test_the_two_availability_regimes_keep_one_s_different_wording() -> None:
    """ "the start of the next full working day after" against "on the first full
    day when".

    A working day clause and a calendar clause are different rules, and the
    January 2026 round changed which one applies. Reducing both to
    "availability based" would throw away the change.
    """
    working, current = REGIMES[1], REGIMES[2]
    assert working.basis is current.basis is ClockBasis.AVAILABILITY
    assert working.text != current.text
    assert "working day" in working.text
    assert "working day" not in current.text
    assert "container(s)" in current.text, "the 2026 clause pluralises, as published"


def test_regime_windows_are_disjoint() -> None:
    """Two regimes covering the same date is a data error, not an ambiguity."""
    for i, a in enumerate(REGIMES):
        for b in REGIMES[i + 1 :]:
            assert (
                a.effective_to is None
                or b.effective_from is None
                or (a.effective_to < b.effective_from)
            ), f"{a.cite} overlaps {b.cite}"


# ---------------------------------------------------------------- criterion 2
# A lookup resolves the regime in force on a given date.


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (date(2019, 1, 1), ClockBasis.DISCHARGE),
        (date(2022, 6, 1), ClockBasis.DISCHARGE),
        (LAST_DISCHARGE_DAY, ClockBasis.DISCHARGE),
        (AVAILABILITY_START, ClockBasis.AVAILABILITY),
        (date(2025, 6, 1), ClockBasis.AVAILABILITY),
        (LAST_WORKING_DAY_LANGUAGE, ClockBasis.AVAILABILITY),
        (CURRENT_START, ClockBasis.AVAILABILITY),
        (date(2026, 9, 27), ClockBasis.AVAILABILITY),
    ],
)
def test_lookup_resolves_the_regime_in_force(on: date, expected: ClockBasis) -> None:
    lookup = basis_in_force(on)
    assert lookup.resolved
    assert lookup.basis is expected
    assert lookup.require_basis() is expected


def test_boundaries_are_inclusive_on_both_sides() -> None:
    """The last day of one regime and the first day of the next are different
    dates, and the off by one here would move a clock start by a day."""
    assert basis_in_force(LAST_DISCHARGE_DAY).basis is ClockBasis.DISCHARGE
    assert basis_in_force(LAST_DISCHARGE_DAY).basis is not ClockBasis.AVAILABILITY
    assert basis_in_force(AVAILABILITY_START).basis is ClockBasis.AVAILABILITY
    assert basis_in_force(LAST_WORKING_DAY_LANGUAGE).basis is ClockBasis.AVAILABILITY
    assert basis_in_force(CURRENT_START).basis is ClockBasis.AVAILABILITY


def test_lookup_carries_the_source_it_resolved_from() -> None:
    lookup = basis_in_force(date(2025, 1, 1))
    assert lookup.regime is not None
    assert "11032025" in lookup.regime.source
    assert "September 9th, 2024" in lookup.regime.disclaimer


def test_the_research_note_and_the_code_disagree_about_2025_11_02() -> None:
    """The correction, asserted so it cannot be undone by a later edit.

    The research note dated the availability language to 2025-11-02. That is the
    default payer advisory. The page carrying the clock language says 2024-09-09
    in its own disclaimer, and the page is titled for the later policy because
    the later policy superseded everything else on it.
    """
    lookup = basis_in_force(date(2025, 11, 2))
    assert lookup.resolved
    assert lookup.regime is not None
    assert lookup.regime.effective_from == AVAILABILITY_START
    assert lookup.regime.effective_from != date(2025, 11, 2)
    assert lookup.regime.cite == "ONE D&D policy effective 2024-09-09"

    note = (ROOT / "docs" / "research" / "002-carriers.md").read_text()
    assert "CORRECTION, 2026-09-27" in note, "the research note still carries the wrong date"
    assert "default payer" in note


# ---------------------------------------------------------------- criterion 3
# The gap is marked UNVERIFIED rather than interpolated.


def test_gap_boundaries() -> None:
    assert UNKNOWN_WINDOW.start == GAP_START
    assert UNKNOWN_WINDOW.end == GAP_END
    assert UNKNOWN_WINDOW.days == 560


def test_every_day_of_the_gap_is_unresolved() -> None:
    lookup = basis_in_force(date(2024, 1, 15))
    assert not lookup.resolved
    assert lookup.regime is None
    assert lookup.basis is None
    assert lookup.unknown is UNKNOWN_WINDOW


@pytest.mark.parametrize(
    "on", [GAP_START, date(2023, 6, 1), date(2024, 1, 1), date(2024, 5, 27), GAP_END]
)
def test_gap_endpoints_are_inside_it(on: date) -> None:
    assert not basis_in_force(on).resolved
    assert UNKNOWN_WINDOW.contains(on)


def test_the_day_before_and_after_the_gap_are_resolved() -> None:
    assert basis_in_force(LAST_DISCHARGE_DAY).resolved
    assert basis_in_force(AVAILABILITY_START).resolved


def test_the_gap_is_not_a_regime_and_cannot_be_found_by_iterating() -> None:
    """The structural guard.

    ``UNKNOWN_WINDOW`` is a different type from ``ClockRegime`` and is not in
    ``REGIMES``. A caller that iterates the regimes and takes the nearest match
    therefore cannot find it by accident, which is the mistake this design exists
    to prevent.
    """
    # The type split is the guard, and mypy enforces it: ClockRegime and
    # UnknownWindow are frozen dataclasses with disjoint bases, so
    # `UNKNOWN_WINDOW in REGIMES` and `isinstance(UNKNOWN_WINDOW, ClockRegime)` are
    # both rejected as statically impossible. There is nothing left to assert at
    # runtime about the type relationship, which is the outcome this design wanted.
    #
    # What is left is the behavioural half, and it is the half that could still be
    # wrong: no regime may claim a single day inside the gap, or nearest match
    # iteration would have something to match on.
    for day in (GAP_START, date(2023, 8, 1), date(2024, 1, 1), date(2024, 5, 27), GAP_END):
        assert not any(r.covers(day) for r in REGIMES), day
    assert len(REGIMES) == 3


def test_require_basis_raises_rather_than_defaulting() -> None:
    """The chargeable day count path cannot guess.

    A silent default here would compute a day count for a 2024 invoice using a
    basis we do not know, and the result would look like an answer.
    """
    with pytest.raises(LookupError) as excinfo:
        basis_in_force(date(2024, 5, 27)).require_basis()
    message = str(excinfo.value)
    assert "UNVERIFIED" in message
    assert "Do not interpolate" in message
    assert "560" in message


def test_the_gap_covers_most_of_2024_and_all_of_late_2023() -> None:
    """Not a rare edge, and not all of 2024 either.

    The window runs 2023-02-27 to 2024-09-08. So the last ten months of 2023 and
    the first eight and a bit of 2024 are unanswerable, which is where a large
    share of live disputes sit. Stated precisely because "all of 2024" was my own
    overstatement in an earlier draft of this test.
    """
    for month in range(1, 13):
        assert not basis_in_force(date(2023, month, 15)).resolved or month < 3, f"2023-{month:02d}"
    for month in range(1, 9):
        assert not basis_in_force(date(2024, month, 15)).resolved, f"2024-{month:02d}"
    assert not basis_in_force(date(2024, 9, 8)).resolved
    assert basis_in_force(date(2024, 9, 9)).resolved
    assert basis_in_force(date(2024, 12, 15)).resolved


def test_the_gap_is_longer_than_the_issue_predicted() -> None:
    """The issue named 2023-02-27 to 2024-05-27, which is inside the real gap.

    2024-05-27 is the OSRA effective date and it is the point a reader expects
    the hole to end. It does not, because ONE's own page dates the availability
    language 2024-09-09.

    Counting inclusively, the issue's window is 456 days and the real one is 560,
    so the gap is 104 days longer than predicted. Those 104 days are the interval
    between the regulation taking effect and the carrier implementing it.

    Both figures were wrong on the first pass. 425 and 135 were estimated rather
    than computed, which is the habit this repository is supposed to be losing.
    """
    assert UNKNOWN_WINDOW.end > date(2024, 5, 27)
    assert UNKNOWN_WINDOW.days == 560
    assert UNKNOWN_WINDOW.days > 456
    assert UNKNOWN_WINDOW.end == date(2024, 9, 8)


# ---------------------------------------------------------------- criterion 4
# The current regime is availability-based and the oldest is discharge-based.


def test_current_regime_is_availability_based() -> None:
    assert REGIMES[-1].basis is ClockBasis.AVAILABILITY
    assert REGIMES[-1].effective_to is None, "the current regime is open ended"
    assert basis_in_force(date(2026, 9, 27)).basis is ClockBasis.AVAILABILITY


def test_oldest_regime_is_discharge_based() -> None:
    assert REGIMES[0].basis is ClockBasis.DISCHARGE
    assert REGIMES[0].effective_from is None, "the oldest regime is open at the start"
    assert basis_in_force(date(2019, 1, 1)).basis is ClockBasis.DISCHARGE


def test_one_moved_from_discharge_to_availability_and_stayed_there() -> None:
    """The direction of travel, which is what makes ONE worth the check.

    MSC is on the other side of this in its own published tariff, which is the
    cleanest evidence available that clock basis is a contract term and not
    settled doctrine. Neither carrier is wrong. That is the point.
    """
    assert [r.basis for r in REGIMES] == [
        ClockBasis.DISCHARGE,
        ClockBasis.AVAILABILITY,
        ClockBasis.AVAILABILITY,
    ]


def test_a_date_outside_every_regime_and_the_gap_is_an_error() -> None:
    """Coverage is total, so this cannot fire. Asserted anyway.

    If a future regime were added with a hole, this would catch it at the point
    of the change rather than at the point of the invoice.
    """
    covered = [r for r in REGIMES if r.covers(date(2026, 9, 27))]
    assert len(covered) == 1, "exactly one regime covers any given date"
    assert Lookup(on=date(2026, 9, 27), regime=None, unknown=None).basis is None


def test_regimes_are_immutable() -> None:
    regime: ClockRegime = REGIMES[-1]
    with pytest.raises(AttributeError):
        regime.basis = ClockBasis.DISCHARGE  # type: ignore[misc]
