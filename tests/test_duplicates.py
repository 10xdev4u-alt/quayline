"""Issue 46: two invoices, one container, priced twice.

The load bearing test is ``test_an_msc_lane_with_both_invoices_is_flagged``. The
rest check the mechanism, and a suite that checks the mechanism without asserting
that case would pass while the issue's central claim goes untested.
"""

from __future__ import annotations

from datetime import date

import pytest

from quayline.ingest import duplicates as module
from quayline.ingest.duplicates import Charge, DoubleInvoice, find_double_invoices

D = date


_FIRST = D(2026, 7, 8)
_LAST = D(2026, 7, 10)


def charge(
    container: str = "MAEU1",
    first: date = _FIRST,
    last: date = _LAST,
    by: str = "MSC",
    instrument: str = "line demurrage",
) -> Charge:
    return Charge(
        container=container, first_day=first, last_day=last, billed_by=by, instrument=instrument
    )


TERMINAL = charge(by="Savannah Terminal Operator", instrument="terminal storage")
CARRIER = charge(
    first=D(2026, 7, 9), last=D(2026, 7, 11), by="MSC", instrument="line demurrage pass-through"
)


# ---------------------------------------------------------------- criterion 1
# Grouped by container and date range across all billing parties.


def test_charges_group_by_container() -> None:
    """Different containers never overlap, however close the dates."""
    assert not charge(container="A").overlaps(charge(container="B"))
    assert charge().overlaps(charge())


def test_overlap_is_date_intersection() -> None:
    assert charge(first=D(2026, 7, 8), last=D(2026, 7, 10)).overlap_days(
        charge(first=D(2026, 7, 9), last=D(2026, 7, 11))
    ) == (D(2026, 7, 9), D(2026, 7, 10))


def test_adjacent_ranges_do_not_overlap() -> None:
    """Touching is not overlapping. A charge ending the 10th and one starting the
    11th share no day, and treating adjacency as overlap would flag every
    consecutive pair on a lane."""
    assert not charge(first=D(2026, 7, 8), last=D(2026, 7, 10)).overlaps(
        charge(first=D(2026, 7, 11), last=D(2026, 7, 12))
    )


def test_a_charge_ending_before_it_starts_is_refused() -> None:
    with pytest.raises(ValueError, match="before it starts"):
        charge(first=D(2026, 7, 10), last=D(2026, 7, 8))


def test_charges_are_immutable() -> None:
    with pytest.raises(AttributeError):
        charge().container = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# An overlapping terminal-plus-carrier pair is flagged before filing.


def test_an_msc_lane_with_both_invoices_is_flagged() -> None:
    """The criterion's case. Terminal storage direct plus MSC line pass-through on
    the same box, overlapping dates. Neither invoice is arithmetically wrong, and
    disputing both prices the container twice."""
    found = find_double_invoices((TERMINAL, CARRIER))
    assert len(found) == 1
    assert isinstance(found[0], DoubleInvoice)


def test_non_overlapping_charges_produce_nothing() -> None:
    assert find_double_invoices((TERMINAL, charge(first=D(2026, 7, 20), last=D(2026, 7, 22)))) == ()


def test_same_party_pairs_are_not_double_invoices() -> None:
    """A carrier billing twice is a duplicate, not a double invoice, and it belongs
    to a different dispute with different evidence."""
    assert find_double_invoices((CARRIER, charge(by="MSC", instrument="detention"))) == ()


def test_two_carriers_without_an_operator_are_not_flagged() -> None:
    """Two carriers billing one box is a different dispute. This module is the
    terminal-plus-carrier shape the evidence names."""
    assert find_double_invoices((CARRIER, charge(by="Maersk", instrument="demurrage"))) == ()


def test_two_operators_without_a_carrier_are_not_flagged() -> None:
    assert (
        find_double_invoices((TERMINAL, charge(by="Port Authority Storage", instrument="storage")))
        == ()
    )


def test_detection_is_deterministic_and_order_free() -> None:
    assert find_double_invoices((TERMINAL, CARRIER)) == find_double_invoices((CARRIER, TERMINAL))


# ---------------------------------------------------------------- criterion 3
# The flag names both parties and both instruments.


def test_the_flag_names_both_parties_and_both_instruments() -> None:
    (found,) = find_double_invoices((TERMINAL, CARRIER))
    sentence = found.sentence()
    assert "Savannah Terminal Operator" in sentence
    assert "MSC" in sentence
    assert "terminal storage" in sentence
    assert "line demurrage pass-through" in sentence


def test_the_flag_names_the_overlapping_dates() -> None:
    (found,) = find_double_invoices((TERMINAL, CARRIER))
    assert found.overlap == (D(2026, 7, 9), D(2026, 7, 10))
    assert "2026-07-09" in found.sentence()


def test_a_single_day_overlap_names_one_day() -> None:
    (found,) = find_double_invoices(
        (
            charge(
                first=D(2026, 7, 8), last=D(2026, 7, 8), by="Port Authority", instrument="storage"
            ),
            charge(first=D(2026, 7, 8), last=D(2026, 7, 12), by="ZIM", instrument="rail demurrage"),
        )
    )
    assert found.overlap == (D(2026, 7, 8),)
    assert " to " not in found.sentence()


def test_the_flag_says_what_not_to_do() -> None:
    (found,) = find_double_invoices((TERMINAL, CARRIER))
    assert "prices the container twice" in found.sentence()


def test_findings_are_immutable() -> None:
    (found,) = find_double_invoices((TERMINAL, CARRIER))
    with pytest.raises(AttributeError):
        found.container = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 4
# Covered above; the rail shape is the second evidence case.


def test_a_zim_rail_pair_is_flagged() -> None:
    """The issue's second evidence case. Rail demurrage is carrier-only with the
    operator invoicing storage separately, which is the same structure as MSC."""
    found = find_double_invoices(
        (
            charge(
                by="Rail Operator Storage",
                instrument="storage",
                first=D(2026, 7, 8),
                last=D(2026, 7, 10),
            ),
            charge(by="ZIM", instrument="rail demurrage", first=D(2026, 7, 9), last=D(2026, 7, 11)),
        )
    )
    assert len(found) == 1
    assert "Rail Operator Storage" in found[0].sentence()


def test_issue_46_is_the_provenance() -> None:
    assert "Issue 46" in (module.__doc__ or "")


def test_the_module_states_what_it_is_not() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "duplicate invoice, not a double invoice" in flat
