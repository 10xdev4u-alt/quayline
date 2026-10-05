"""Issue 84: coverage has to be asked per gateway, because it varies per gateway.

A per-carrier report says "Hapag-Lloyd: not held" and "MSC: not held". Both are true and both
are the wrong shape for the question an operator has, which is about a specific container at a
specific port. MSC publishes a direct tariff at exactly one gateway and none at fifteen others.
No per-carrier row can say that, because the carrier is simultaneously supported and
unsupportable.

The states asserted here are four, not two, and the fourth is the one that is easiest to lose.
"""

from __future__ import annotations

import argparse
import io
import json

import pytest

from quayline.cli.coverage_cmd import add_parser, run_coverage
from quayline.tariffs.gateway_coverage import GatewayRow, gateway_rows, summarise
from quayline.tariffs.hapag_terminals import SCHEDULES
from quayline.tariffs.msc import DIRECT_TARIFF_PORT, PASS_THROUGH_TERMINALS

ROWS = gateway_rows()


def _for(carrier: str) -> tuple[GatewayRow, ...]:
    return tuple(row for row in ROWS if row.carrier == carrier)


# --- the shape ---------------------------------------------------------------


def test_rows_exist_and_are_frozen() -> None:
    """Non-empty, because an empty parse would pass every assertion below vacuously."""
    assert ROWS, "no gateway rows at all"

    row = ROWS[0]
    with pytest.raises((AttributeError, TypeError)):
        row.resolution = "priced"  # type: ignore[misc]


def test_every_row_says_why() -> None:
    """A state with no reason is what this module exists to prevent.

    "Not held" and "not published" send the reader in opposite directions, and a bare state
    collapses them into one indistinguishable word.
    """
    for row in ROWS:
        assert row.reason.strip(), f"{row.carrier} {row.gateway} has no reason"
        assert row.resolution in {"priced", "basis only", "unpublished", "nothing held"}


def test_the_order_is_stable() -> None:
    """A report whose rows reshuffle between runs is hard to diff between two versions."""
    assert gateway_rows() == ROWS
    assert tuple(sorted(ROWS, key=lambda r: (r.carrier, r.resolution, r.gateway))) == ROWS


# --- MSC, the interesting case ----------------------------------------------


def test_msc_has_exactly_one_direct_tariff_gateway() -> None:
    """Eight of the nine major gateways have no MSC tariff. This is that, counted."""
    direct = [row for row in _for("MSC") if row.resolution != "unpublished"]
    assert [row.gateway for row in direct] == [DIRECT_TARIFF_PORT]


def test_msc_pass_through_gateways_are_unpublished_not_merely_unheld() -> None:
    """The distinction the whole issue is about.

    "nothing held" means we could go and acquire the tariff. "unpublished" means the carrier
    has none to acquire, and the controlling schedule belongs to the terminal operator. A
    reader told only the first would spend weeks looking for something that does not exist.
    """
    unpublished = [row for row in _for("MSC") if row.resolution == "unpublished"]
    assert len(unpublished) == len(PASS_THROUGH_TERMINALS)


def test_an_unpublished_row_says_the_terminal_operator_controls_it() -> None:
    """The reason has to name who does hold it, or the row is only half the information."""
    row = next(row for row in _for("MSC") if row.resolution == "unpublished")
    assert "terminal operator" in row.reason


def test_no_msc_row_claims_a_price() -> None:
    """Nothing in this module may imply a figure. Not one gateway resolves to money for MSC."""
    assert all(row.resolution != "priced" for row in _for("MSC"))


# --- Hapag-Lloyd, basis without price ---------------------------------------


def test_every_hapag_gateway_is_basis_only_and_none_is_priced() -> None:
    """Hapag publishes per terminal, which is why coverage is asked per terminal here.

    All ten resolve to a shape and not a price. Reporting any of them as "held" would be the
    overclaim the whole report exists to stop.
    """
    rows = _for("Hapag-Lloyd")
    assert len(rows) == len(SCHEDULES)
    assert {row.resolution for row in rows} == {"basis only"}


def test_a_basis_only_row_says_what_is_missing() -> None:
    """ "basis only" without naming the omission is just "held, but somehow"."""
    for row in _for("Hapag-Lloyd"):
        assert "rate tiers are not transcribed" in row.reason


def test_a_basis_only_row_still_carries_the_free_time_notation() -> None:
    """What we *do* hold is the thing that makes a weekend cost nothing and a Tuesday not."""
    assert any(row.reason.startswith("free time ") for row in _for("Hapag-Lloyd"))


# --- Maersk, and the granularity it does not have ----------------------------


def test_maersk_is_reported_at_cluster_granularity() -> None:
    """Maersk publishes per cluster, so the report says cluster.

    Enumerating individual ports would claim a granularity the source does not have, which is
    the same mistake as inventing a rate: a detail that looks precise and is not.
    """
    rows = _for("Maersk")
    assert rows and all(row.gateway.startswith("cluster ") for row in rows)
    assert {row.resolution for row in rows} == {"priced"}


def test_a_maersk_row_names_the_rule_it_comes_from() -> None:
    """Traceable back to a transcribed source, which is the bar for a `priced` row."""
    for row in _for("Maersk"):
        assert "tariff transcribed for rule " in row.reason


# --- the counts --------------------------------------------------------------


def test_the_four_states_are_all_represented() -> None:
    """If a state ever goes missing the report stops being informative about it."""
    assert set(summarise()) == {"priced", "basis only", "unpublished", "nothing held"}


def test_the_unpublished_count_is_the_largest_and_that_is_informative() -> None:
    """Where the reader should stop looking is the biggest number in the report.

    This is the assertion most likely to need updating when carriers are added, and it is
    here so that a change to it is a decision rather than a silent drift.
    """
    counts = summarise()
    assert counts["unpublished"] == len(PASS_THROUGH_TERMINALS)
    assert counts["unpublished"] > counts["priced"]


def test_summarise_counts_every_row_exactly_once() -> None:
    """No row double-counted, which would inflate the numbers a reader is meant to act on."""
    assert sum(summarise().values()) == len(ROWS)


# --- the report the operator actually reads ----------------------------------


def _coverage_args(*extra: str) -> argparse.Namespace:
    """Parse through the real parser rather than building a Namespace by hand.

    A hand-built Namespace would pass even if the command stopped accepting ``--json``.
    """
    parser = argparse.ArgumentParser()
    add_parser(parser.add_subparsers(dest="command"))
    return parser.parse_args(["coverage", *extra])


def test_the_coverage_command_shows_the_gateway_section() -> None:
    """The module is only worth having if it reaches the command.

    A report module that nothing renders is a library, and the thing an operator reads is the
    command's output.
    """
    out = io.StringIO()
    assert run_coverage(_coverage_args(), out) == 0

    text = out.getvalue()
    assert "Gateways:" in text
    assert "unpublished" in text
    assert DIRECT_TARIFF_PORT in text
    assert text.count("basis only") >= len(SCHEDULES)


def test_every_gateway_appears_in_the_human_report() -> None:
    """A count in the header is not the same as the rows being there.

    Asserted per row rather than as a total, because a truncated list with a correct count
    is exactly the kind of report that gets trusted.
    """
    out = io.StringIO()
    run_coverage(_coverage_args(), out)
    text = out.getvalue()

    missing = [row.gateway for row in ROWS if row.gateway not in text]
    assert not missing, f"{len(missing)} gateway(s) absent from the report: {missing[:3]}"


def test_the_json_report_keeps_gateways_out_of_the_carrier_list() -> None:
    """Folding gateways into ``carriers`` would make a reader count Hapag ten times.

    That is the failure of a report that reshapes its own data for convenience.
    """
    out = io.StringIO()
    run_coverage(_coverage_args("--json"), out)
    data = json.loads(out.getvalue())

    assert len(data["gateways"]) == len(ROWS)
    assert data["gateway_states"] == summarise()

    carriers = {row["carrier"] for row in data["carriers"]}
    assert not carriers & {row.gateway for row in ROWS}, "a gateway leaked into the carrier list"


def test_the_json_report_names_who_controls_an_unpublished_tariff() -> None:
    """The reason has to survive into the machine output.

    JSON is what an integrator reads, and "unpublished" without "the terminal operator holds
    it" leaves them to re-derive the distinction the report exists to make.
    """
    out = io.StringIO()
    run_coverage(_coverage_args("--json"), out)
    data = json.loads(out.getvalue())

    unpublished = [row for row in data["gateways"] if row["resolution"] == "unpublished"]
    assert unpublished
    assert all("terminal operator" in row["reason"] for row in unpublished)
