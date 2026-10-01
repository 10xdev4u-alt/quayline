"""Issue 172: the coverage report, which is the honest limit of the engine.

This is the artifact that answers "where does this work" before anyone buys it. The
category's credibility problem is that its vendors claim total coverage. Printing the
gaps is therefore the sales asset, not the weakness.

Every assertion here is written against the real coverage data rather than a
snapshot. Adding a carrier fails a test, which is the point: a golden file changes
silently and nobody reads the diff.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from quayline.cli.audit_cmd import main
from quayline.cli.coverage_cmd import EXIT_OK
from quayline.engine.warnings import coverage_gaps, limits_for
from quayline.tariffs.uncovered import UNCOVERED


def run(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


# ------------------------------------------------------------------ exit code


def test_the_report_exits_zero_because_an_incomplete_map_is_not_a_failure() -> None:
    """A pipeline must not see an error because coverage is partial.

    Coverage will always be partial while tariffs are being transcribed. A non-zero
    code here would make an honest report look like a broken tool.
    """
    code, _ = run("coverage")
    assert code == EXIT_OK == 0


def test_coverage_is_always_valid_json_on_this_path() -> None:
    _, out = run("coverage", "--json")
    assert json.loads(out)["carriers"]


# --------------------------------------------------------------- what it must say


def test_it_names_every_uncovered_carrier() -> None:
    """Yang Ming, PIL, HMM, COSCO and Evergreen, by name.

    Derived from ``UNCOVERED`` rather than hardcoded, so a carrier added there fails
    this test until the report can explain it.
    """
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    named = {row["carrier"] for row in payload["carriers"]}
    for carrier in (u.carrier for u in UNCOVERED):
        assert carrier in named, f"{carrier} is uncovered and must appear"


def test_an_uncovered_carrier_carries_the_unverified_marker() -> None:
    """AGENTS.md section five. The tier travels with the claim."""
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    for row in payload["carriers"]:
        if row["rules_held"] == 0:
            assert "UNVERIFIED" in row["note"], row


def test_every_uncovered_carrier_states_what_is_missing_and_how_to_get_it() -> None:
    """A gap without a next action is a complaint. A gap with one is a backlog."""
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    rows = {row["carrier"]: row for row in payload["carriers"]}
    for u in UNCOVERED:
        assert rows[u.carrier]["acquisition_task"], f"{u.carrier} needs a task"


def test_a_carrier_we_do_hold_still_carries_its_limits() -> None:
    """Coverage is not a yes or no. Maersk resolves and is still limited.

    Five typed limits, including an unverified detention schedule. A report that said
    only "Maersk: supported" would be the kind of overclaim this is meant to stop.
    """
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    rows = {row["carrier"]: row for row in payload["carriers"]}
    assert "Maersk" in rows
    assert rows["Maersk"]["rules_held"] > 0
    assert rows["Maersk"]["limits"], "a held carrier still has limits and must show them"


def test_the_limit_count_matches_what_the_engine_actually_reports() -> None:
    """Asserted against ``limits_for`` so the report cannot drift from the engine."""
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    rows = {row["carrier"]: row for row in payload["carriers"]}
    assert len(rows["Maersk"]["limits"]) == len(limits_for("Maersk"))
    assert len(rows["MSC"]["limits"]) == len(limits_for("MSC"))


def test_msc_names_its_own_data_gap() -> None:
    """The clearest case in the product.

    MSC publishes no US import demurrage tariff at eight of the nine major gateways
    and passes terminal demurrage through at cost. The controlling instrument is the
    terminal operator's schedule. An engine built from carrier data answers here
    confidently and wrongly.
    """
    _, out = run("coverage", "--json")
    payload = json.loads(out)

    rows = {row["carrier"]: row for row in payload["carriers"]}
    msc_codes = {limit["code"] for limit in rows["MSC"]["limits"]}
    assert "msc_no_us_tariff" in msc_codes


def test_the_global_limits_are_reported_separately() -> None:
    """Some limits apply to every carrier, so they are not a carrier's fault."""
    gaps = coverage_gaps()
    if not gaps:
        pytest.skip("no global limits recorded")

    _, out = run("coverage", "--json")
    payload = json.loads(out)
    assert len(payload["global_limits"]) == len(gaps)


def test_the_report_states_it_is_a_snapshot() -> None:
    """Coverage moves as tariff data is transcribed, so the report says so."""
    _, out = run("coverage")
    assert "today" in out.lower() or "transcribed" in out.lower()


# ---------------------------------------------------------------- human output


def test_the_human_report_names_carriers_and_their_granularity() -> None:
    _, out = run("coverage")

    assert "Maersk" in out
    assert "UNVERIFIED" in out
    assert "Yang Ming" in out


def test_the_human_report_is_readable_without_json() -> None:
    """An operator should not need a parser to find out whether we cover them."""
    _, out = run("coverage")

    assert out.strip(), "the report must print something"
    assert len(out.splitlines()) > 5, "a one line report hides the gaps"
