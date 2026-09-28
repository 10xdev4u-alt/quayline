"""The four acceptance criteria on issue 16, one test block each.

The scenario that matters is the hold that spans the entire free time window. That
is the case where the argument is strongest, nothing is chargeable, and the adverse
clause is the only thing left to argue about.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from quayline.tariffs.hapag import (
    CONDITION,
    GENERAL_TERM,
    HAPAG_CUSTOMS_HOLD_EDITION,
    HAPAG_CUSTOMS_HOLD_URL,
    INSIDE_TERMINAL_TERM,
    OUTSIDE_TERMINAL_TERM,
    RECOVERY_LIMIT,
    RESTART_BY_LOCUS,
    HoldLocus,
    HoldWindow,
    RestartClock,
    customs_hold,
)

ROOT = Path(__file__).resolve().parents[1]

# A nine day customs examination, which is ordinary for a CBP exam.
HOLD = HoldWindow(start=date(2026, 6, 1), release=date(2026, 6, 9))
FREE_TIME_DAYS = 4
# Free time begins the same day the hold does, so the hold covers all of it.
CLOCK_STARTED = date(2026, 6, 1)


# ---------------------------------------------------------------- criterion 1
# A customs hold pauses demurrage and detention from the release date.


def test_hold_pauses_the_clock_and_the_clock_resumes_at_release() -> None:
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.restart_on == HOLD.release == date(2026, 6, 9)
    assert finding.hold_days == 9


def test_inside_the_terminal_the_guide_names_the_demurrage_clock() -> None:
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.clock is RestartClock.DEMURRAGE
    assert "Line Demurrage clock begins at the release date" in finding.text


def test_outside_the_terminal_the_guide_names_the_detention_clock() -> None:
    finding = customs_hold(HOLD, HoldLocus.OUTSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.clock is RestartClock.DETENTION
    assert "detention clock begins at the release date" in finding.text


def test_the_restart_clock_differs_by_locus() -> None:
    """The asymmetry the research corpus flattened.

    The guide's general sentence stops the demurrage AND the detention clock. Its
    restart sentences do not follow that symmetry, and a summary that says "pauses
    both clocks" is right about the stop and wrong about the restart.
    """
    assert RESTART_BY_LOCUS[HoldLocus.INSIDE_TERMINAL] is RestartClock.DEMURRAGE
    assert RESTART_BY_LOCUS[HoldLocus.OUTSIDE_TERMINAL] is RestartClock.DETENTION
    assert (
        RESTART_BY_LOCUS[HoldLocus.INSIDE_TERMINAL]
        is not RESTART_BY_LOCUS[HoldLocus.OUTSIDE_TERMINAL]
    )


def test_a_customer_caused_hold_is_outside_the_policy() -> None:
    """The guide conditions the whole policy on fault, and the corpus dropped it."""
    assert "for no fault of the customer" in GENERAL_TERM
    assert CONDITION == "for no fault of the customer"
    assert (
        customs_hold(
            HOLD,
            HoldLocus.INSIDE_TERMINAL,
            FREE_TIME_DAYS,
            CLOCK_STARTED,
            no_fault_of_customer=False,
        )
        is None
    )
    assert customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED) is not None


def test_the_policy_covers_both_haulage_modes() -> None:
    assert "Carrier Haulage and Merchant Haulage" in GENERAL_TERM


# ---------------------------------------------------------------- criterion 2
# Hold days are excluded from the free-time count.


def test_hold_days_are_not_counted_towards_free_time() -> None:
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert "not counted towards free time days" in finding.text
    assert finding.free_time_days_lost_to_hold == FREE_TIME_DAYS


def test_hold_days_are_counted_inclusively_at_both_ends() -> None:
    """The guide says the hold and release dates and all days in between.

    Both endpoints are days the container was held, so an inclusive count is what the
    sentence means. An exclusive count would understate a nine day hold as seven.
    """
    assert HOLD.days == 9
    assert HoldWindow(date(2026, 6, 1), date(2026, 6, 1)).days == 1
    assert HoldWindow(date(2026, 6, 1), date(2026, 6, 2)).days == 2


def test_a_hold_outside_the_free_time_window_costs_nothing() -> None:
    """Free time already spent before the hold began.

    The hold is still a clock stop, but it does not rewind free time that was
    already consumed, and a tool that reported the full allowance here would be
    promising a recovery that is not there.
    """
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, date(2026, 5, 1))
    assert finding is not None
    assert finding.free_time_days_lost_to_hold == 0
    assert finding.restart_on == HOLD.release


def test_a_partial_overlap_counts_only_the_overlap() -> None:
    """Free time runs 2026-05-29 to 2026-06-01. The hold starts 2026-06-01."""
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, date(2026, 5, 29))
    assert finding is not None
    assert finding.free_time_days_lost_to_hold == 1
    assert f"1 of {FREE_TIME_DAYS}" in finding.text


# ---------------------------------------------------------------- criterion 3
# The finding text states that the dispute recovers the line charge and not the
# storage.


def test_the_limit_is_on_the_finding_itself() -> None:
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.recovery_limit == RECOVERY_LIMIT
    assert "line charge only" in finding.recovery_limit
    assert "storage" in finding.recovery_limit


def test_the_limit_survives_into_describe() -> None:
    """describe is what a dispute letter would carry, so the limit has to be in it.

    A caller that formats the finding from ``text`` alone would produce a letter
    asking for the storage to be waived, which the carrier's own published terms
    refuse. That is the specific wrong outcome this criterion exists to prevent.
    """
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    described = finding.describe()
    assert RECOVERY_LIMIT in described
    assert "recovers the line charge only" in described


def test_the_pass_through_clause_is_only_in_the_inside_terminal_branch() -> None:
    """Checked and it is not symmetric, which the first version of this test got wrong.

    The guide says, for a hold inside the terminal, "In the instance when
    Hapag-Lloyd collects terminal charges on behalf of the terminal operator,
    Hapag-Lloyd will invoice these pass-through charges to the customer."

    The warehouse branch has no equivalent sentence. It says only that the customer
    is responsible for storage "applied by the Warehouse Operator or the government
    body". So the double charge is a risk specific to the inside-terminal branch,
    where Hapag collects for the terminal, and not to the warehouse branch.

    The module docstring says "in the worst case" and the limit is conditional on
    "where the carrier collects those charges on the operator's behalf", so both are
    already scoped correctly. This test is here so the scoping is asserted rather than
    assumed.
    """
    assert "pass-through" in RECOVERY_LIMIT
    assert "pass-through" in INSIDE_TERMINAL_TERM
    assert "pass-through" not in OUTSIDE_TERMINAL_TERM
    assert "In the instance when Hapag-Lloyd collects terminal charges" in INSIDE_TERMINAL_TERM


def test_both_locus_branches_keep_storage_chargeable() -> None:
    """Not just the terminal branch. The warehouse branch is the same shape."""
    assert "responsible for any storage charges" in INSIDE_TERMINAL_TERM
    assert "responsible for any storage charges" in OUTSIDE_TERMINAL_TERM


# ---------------------------------------------------------------- criterion 4
# A test covers a hold spanning the whole free-time window.


def test_hold_spanning_the_whole_free_time_window_leaves_nothing_chargeable() -> None:
    """The strongest form of this argument.

    A nine day examination that opens on the day free time starts and covers all
    four free days consumes none of the allowance, so there is no demurrage to
    dispute. The clock stops on day one and restarts on day nine, and the four free
    days that would have been spent are the four days of the hold.
    """
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.free_time_days_lost_to_hold == FREE_TIME_DAYS
    assert finding.free_time_days_lost_to_hold - FREE_TIME_DAYS == 0
    assert f"{FREE_TIME_DAYS} of {FREE_TIME_DAYS}" in finding.text
    assert finding.restart_on == HOLD.release


def test_the_hold_covers_every_free_time_day_actually() -> None:
    """Asserted from the dates rather than from the number.

    The free time window is 2026-06-01 through 2026-06-04 and the hold is 2026-06-01
    through 2026-06-09, so every day of the allowance is a day of the hold. This is
    the property the criterion is about, and the count could be right by accident.
    """
    window_start = CLOCK_STARTED
    window_end = CLOCK_STARTED + timedelta(days=FREE_TIME_DAYS - 1)
    assert window_start == HOLD.start
    assert window_end < HOLD.release
    for offset in range(FREE_TIME_DAYS):
        day = window_start + timedelta(days=offset)
        assert HOLD.start <= day <= HOLD.release, day


def test_a_hold_longer_than_free_time_still_loses_only_the_allowance() -> None:
    """Nineteen days of hold against a four day allowance.

    The recovery is the four days. The other fifteen are the carrier's problem and
    the customer's, and the finding must not imply otherwise by counting them.
    """
    long_hold = HoldWindow(date(2026, 6, 1), date(2026, 6, 19))
    finding = customs_hold(long_hold, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    assert finding.hold_days == 19
    assert finding.free_time_days_lost_to_hold == FREE_TIME_DAYS


# ---------------------------------------------------------------- provenance


def test_provenance_names_both_editions_and_the_url() -> None:
    assert "May 2026" in HAPAG_CUSTOMS_HOLD_EDITION
    assert "October 1 2024" in HAPAG_CUSTOMS_HOLD_EDITION
    assert HAPAG_CUSTOMS_HOLD_URL.startswith("https://www.hapag-lloyd.com/")
    assert "Detention_and_Demurrage_Guide_USA_May_2026.pdf" in HAPAG_CUSTOMS_HOLD_URL


def test_the_terms_are_the_carriers_words_not_a_summary() -> None:
    """Spot checks against the guide, chosen so a paraphrase fails.

    The research corpus held an abridged version with an ellipsis in it, which is
    not a verbatim quote and is the reason these are transcribed in full here.
    """
    assert GENERAL_TERM.startswith("When a container is put on customs hold")
    assert "stops the Line Demurrage/Detention clock" in GENERAL_TERM
    assert INSIDE_TERMINAL_TERM.startswith("If the container is held inside the Marine or Rail")
    assert "In the instance when Hapag-Lloyd collects terminal charges" in INSIDE_TERMINAL_TERM
    assert OUTSIDE_TERMINAL_TERM.startswith("If the container is held by Customs outside")
    assert "The detention free time starts the day after" in OUTSIDE_TERMINAL_TERM
    for term in (GENERAL_TERM, INSIDE_TERMINAL_TERM, OUTSIDE_TERMINAL_TERM):
        assert "..." not in term, "an ellipsis is an abridgement, not a quote"


def test_the_research_note_records_the_corrections() -> None:
    text = (ROOT / "docs" / "research" / "002-carriers.md").read_text()
    assert "CORRECTION, 2026-09-27, issue 16" in text
    assert "locus dependent and asymmetric" in text
    assert "conditioned on fault" in text
    assert "not verbatim" in text


def test_hold_window_rejects_a_reversed_range() -> None:
    with pytest.raises(ValueError, match="before it started"):
        HoldWindow(date(2026, 6, 9), date(2026, 6, 1))


def test_findings_and_windows_are_immutable() -> None:
    finding = customs_hold(HOLD, HoldLocus.INSIDE_TERMINAL, FREE_TIME_DAYS, CLOCK_STARTED)
    assert finding is not None
    with pytest.raises(AttributeError):
        finding.recovery_limit = "recovers everything"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        HOLD.start = date(2030, 1, 1)  # type: ignore[misc]
