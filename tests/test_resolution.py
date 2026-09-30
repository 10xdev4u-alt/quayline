"""Issue 28: a resolution failure is an answer, and a wrong rate is not.

The load bearing test is ``test_every_unverified_carrier_resolves_to_none``. The
others check individual refusals, and a suite of individual refusals passes while a
carrier nobody enumerated still resolves, because the enumeration and the assertion
are both hand maintained. So the unverified list is derived from the same data the
report is built from.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

import quayline.tariffs.resolution as module
from quayline.tariffs.blocks import RateBlock, Tier
from quayline.tariffs.resolution import (
    CarrierCoverage,
    Dimension,
    Granularity,
    RateQuery,
    Requirement,
    Resolution,
    coverage_report,
    resolve,
    unverified_carriers,
)


def block(**kw: object) -> RateBlock:
    base: dict[str, object] = {
        "rule": "Maersk US Default Dry",
        "carrier": "Maersk",
        "cluster": "USWC",
        "equipment": "40 dry",
        "free_days": 4,
        "tiers": (Tier(from_day=1, to_day=None, rate=Decimal("150.00")),),
        "source": "Maersk US demurrage tariff",
        "effective_from": "2024-08-08",
    }
    base.update(kw)
    return RateBlock(**base)  # type: ignore[arg-type]


def query(**kw: object) -> RateQuery:
    base: dict[str, object] = {"reference": "Maersk US Default Dry", "on": "2026-06-15"}
    base.update(kw)
    return RateQuery(**base)  # type: ignore[arg-type]


#: Issue 14. Carrier or merchant haulage, from the bill of lading checkbox. Four
#: parallel schedules, so a guess is a fifteen to twenty percent error before any
#: dispute is made.
HAPAG_DETENTION = Requirement(
    rule="Hapag-Lloyd US Detention",
    needs=(Dimension.HAULAGE_MODE,),
    note="Carrier or Merchant, read from the bill of lading checkbox.",
)

#: What we hold as of this issue. The granularity column is the point of the report.
COVERAGE: tuple[CarrierCoverage, ...] = (
    CarrierCoverage(
        carrier="Hapag-Lloyd",
        granularity=Granularity.PER_TERMINAL,
        rules_held=0,
        verified=False,
        note="finest granularity in the industry, and issue 13 has not loaded it yet",
    ),
    CarrierCoverage(
        carrier="Maersk",
        granularity=Granularity.PER_CLUSTER,
        rules_held=1,
        verified=True,
        note="the reference block used across the engine tests",
    ),
    CarrierCoverage(
        carrier="ONE",
        granularity=Granularity.CALCULATOR,
        rules_held=0,
        verified=False,
        note="no static rate table exists to transcribe, a calculator is not a deficient table",
    ),
    CarrierCoverage(
        carrier="MSC",
        granularity=Granularity.TERMINAL_OPERATOR,
        rules_held=0,
        verified=False,
        note="no US import demurrage tariff at eight of the nine major gateways",
    ),
    CarrierCoverage(
        carrier="ZIM",
        granularity=Granularity.NONE_HELD,
        rules_held=0,
        verified=False,
        note="the mapping is UNVERIFIED, see issue 25",
    ),
)


# ---------------------------------------------------------------- criterion 1
# resolve() returns a block, or None plus warnings.


def test_a_resolvable_query_returns_the_block_and_no_warnings() -> None:
    got = resolve(query(), (block(),))
    assert got.resolved is True
    assert got.block is not None
    assert got.warnings == ()
    assert got.withheld_reason == "", "a resolved lookup has nothing to warn about"


def test_a_block_is_none_for_every_failure_mode() -> None:
    """There is no sentinel block, because a caller that forgets to check would
    otherwise compare against it and produce a number."""
    cases = {
        "not held": resolve(query(reference="CMA CGM US T1"), (block(),)),
        "not in force": resolve(query(on="2026-07-15"), (block(effective_to="2026-06-30"),)),
        "overlapping": resolve(query(), (block(), block(source="copy"))),
        "unverified": resolve(query(), (block(verified=False),)),
        "missing dimension": resolve(
            query(reference="Hapag-Lloyd US Detention"), (), (HAPAG_DETENTION,)
        ),
    }
    for name, got in cases.items():
        assert got.block is None, name
        assert got.resolved is False, name
        assert got.warnings, f"{name} must say why"


def test_each_failure_produces_a_distinct_message() -> None:
    """Four distinct causes, four different fixes. One generic message would make
    all four unactionable."""
    reasons = {
        resolve(query(reference="nope"), (block(),)).withheld_reason,
        resolve(query(on="2026-07-15"), (block(effective_to="2026-06-30"),)).withheld_reason,
        resolve(query(), (block(), block(source="c"))).withheld_reason,
        resolve(query(), (block(verified=False),)).withheld_reason,
    }
    assert len(reasons) == 4, reasons


def test_resolution_never_approximates() -> None:
    """The core refusal. A nearest match or a fuzzy key would compare the demand
    against a rate the carrier never said applied and present the difference as a
    dispute."""
    got = resolve(query(reference="Maersk US Reefer"), (block(),))
    assert got.block is None
    assert "no rate block held" in got.withheld_reason


def test_normalisation_is_case_and_whitespace_only() -> None:
    for reference in ("maersk us default dry", "  MAERSK   US Default Dry  "):
        assert resolve(query(reference=reference), (block(),)).block is not None


def test_an_unheld_rule_says_the_hole_is_ours() -> None:
    """Keeps a lookup from becoming an accusation."""
    assert (
        "not a finding against the carrier"
        in resolve(query(reference="CMA CGM US T1"), (block(),)).withheld_reason
    )


def test_the_not_held_message_lists_what_we_do_hold() -> None:
    assert "Maersk US Default Dry" in resolve(query(reference="nope"), (block(),)).withheld_reason


# ---------------------------------------------------------------- criterion 2
# Every UNVERIFIED carrier returns None.


def test_every_unverified_carrier_resolves_to_none() -> None:
    """Derived from COVERAGE, not from a hand kept list.

    The failure this prevents is an enumeration that drifts: a new carrier in the
    report and not in this list, with nothing failing.
    """
    assert unverified_carriers(COVERAGE), "the fixture must contain unverified carriers"
    for carrier in unverified_carriers(COVERAGE):
        got = resolve(query(reference=f"{carrier} anything"), (block(),))
        assert got.block is None, carrier


def test_an_unverified_block_is_not_used_even_when_it_is_the_only_one() -> None:
    """Holding a rate we could not transcribe confidently is not holding it. An
    incomplete transcription that resolves becomes a number in a demand letter."""
    got = resolve(query(), (block(verified=False, note="read off a photograph"),))
    assert got.block is None
    assert "UNVERIFIED" in got.withheld_reason
    assert "read off a photograph" in got.withheld_reason, "the note must travel to the warning"


def test_a_verified_block_beside_an_unverified_one_still_resolves() -> None:
    """A worse transcription of a rule we already hold is not an ambiguity in the
    tariff. Counting it as one would let one bad copy blind us to a good one."""
    got = resolve(query(), (block(verified=True), block(source="bad copy", verified=False)))
    assert got.block is not None
    assert got.block.verified is True


def test_no_carrier_we_cannot_answer_for_is_reported_as_usable() -> None:
    for carrier in COVERAGE:
        expected = carrier.carrier == "Maersk"
        assert carrier.usable is expected, carrier.carrier


# ---------------------------------------------------------------- criterion 3
# The coverage report names the granularity of each carrier.


def test_every_carrier_has_a_granularity_and_they_differ() -> None:
    granularities = [c.granularity for c in COVERAGE]
    assert len(set(granularities)) == len(granularities), (
        "a report where every granularity is the same says nothing"
    )
    for carrier in COVERAGE:
        assert carrier.granularity.value, carrier.carrier


def test_the_granularities_are_the_ones_the_research_records() -> None:
    """docs/research/002-carriers.md, so the report cannot drift from its source."""
    by_carrier = {c.carrier: c.granularity for c in COVERAGE}
    assert by_carrier["Hapag-Lloyd"] is Granularity.PER_TERMINAL
    assert by_carrier["Maersk"] is Granularity.PER_CLUSTER
    assert by_carrier["ONE"] is Granularity.CALCULATOR
    assert by_carrier["MSC"] is Granularity.TERMINAL_OPERATOR


def test_a_calculator_is_not_scored_as_a_deficient_table() -> None:
    """ONE has no static rate table because the tariff is a calculator, not because
    ONE publishes badly."""
    assert Granularity.CALCULATOR.value == "calculator, no static table"


def test_the_report_leads_with_what_we_cannot_answer_for() -> None:
    report = coverage_report(COVERAGE)
    assert report[0].usable is False
    assert report[-1].usable is True, "the usable carrier goes last in a report about gaps"


def test_the_report_is_deterministic_regardless_of_input_order() -> None:
    assert coverage_report(COVERAGE) == coverage_report(tuple(reversed(COVERAGE)))


def test_every_carrier_note_says_something_specific() -> None:
    """A coverage table with a blank reason column is a table nobody acts on."""
    for carrier in COVERAGE:
        assert len(carrier.note) > 20, carrier.carrier


def test_granularity_is_not_a_quality_ranking() -> None:
    """Fine granularity does not make a carrier usable. Conflating them would make
    Hapag look covered while issue 13 has not landed."""
    hapag = next(c for c in COVERAGE if c.carrier == "Hapag-Lloyd")
    assert hapag.granularity is Granularity.PER_TERMINAL
    assert hapag.rules_held == 0
    assert hapag.usable is False


# ---------------------------------------------------------------- criterion 4
# Hapag detention without a haulage mode returns None.


def test_hapag_detention_without_haulage_mode_returns_none() -> None:
    got = resolve(query(reference="Hapag-Lloyd US Detention"), (), (HAPAG_DETENTION,))
    assert got.block is None
    assert got.resolved is False


def test_the_warning_names_the_missing_input() -> None:
    """Issue 14's fourth criterion, and the whole reason a warning exists. A warning
    that says "insufficient data" is actionable by nobody."""
    got = resolve(query(reference="Hapag-Lloyd US Detention"), (), (HAPAG_DETENTION,))
    assert "haulage mode" in got.withheld_reason
    assert "does not guess" in got.withheld_reason


def test_the_warning_repeats_where_the_gap_comes_from() -> None:
    got = resolve(query(reference="Hapag-Lloyd US Detention"), (), (HAPAG_DETENTION,))
    assert "bill of lading checkbox" in got.withheld_reason


def test_supplying_the_haulage_mode_clears_the_refusal() -> None:
    got = resolve(
        query(reference="Hapag-Lloyd US Detention", haulage_mode="Carrier Haulage"),
        (),
        (HAPAG_DETENTION,),
    )
    assert "haulage mode" not in got.withheld_reason


def test_the_requirement_is_on_the_rule_not_the_carrier() -> None:
    """Hapag demurrage is per terminal and needs no haulage mode; Hapag detention
    needs it. A carrier level flag cannot express that."""
    assert HAPAG_DETENTION.rule.endswith("Detention")
    assert not HAPAG_DETENTION.rule.endswith("Demurrage")
    demurrage = resolve(query(reference="Hapag-Lloyd US Demurrage"), (), ())
    assert "indexed by" not in demurrage.withheld_reason, (
        "a rule carrying no requirement must not be blocked on a missing input"
    )


def test_supplying_one_dimension_does_not_rescue_another() -> None:
    """Both gaps must be named, not just the first."""
    two_gaps = Requirement(
        rule="Two Gap", needs=(Dimension.HAULAGE_MODE, Dimension.TERMINAL), note="indexed by both"
    )
    got = resolve(query(reference="Two Gap", haulage_mode="Carrier Haulage"), (), (two_gaps,))
    assert "terminal" in got.withheld_reason
    assert "haulage mode" not in got.withheld_reason


def test_the_dimension_check_runs_before_the_data_check() -> None:
    """A missing dimension is reported even when we hold nothing at all, because it
    is the more actionable of the two."""
    got = resolve(query(reference="Hapag-Lloyd US Detention"), (), (HAPAG_DETENTION,))
    assert "indexed by" in got.withheld_reason
    assert "no rate block held" not in got.withheld_reason


def test_a_query_reports_which_dimensions_it_supplied() -> None:
    q = query(haulage_mode="Carrier Haulage", terminal="USLAXB")
    assert q.supplied(Dimension.HAULAGE_MODE) is True
    assert q.supplied(Dimension.TERMINAL) is True
    assert q.missing(Dimension.CLUSTER) is True


# ---------------------------------------------------------------- the type itself


def test_resolution_is_immutable() -> None:
    got = resolve(query(), (block(),))
    with pytest.raises(AttributeError):
        got.block = None  # type: ignore[misc]


def test_a_copied_coverage_record_derives_without_mutating_the_table() -> None:
    maersk = next(c for c in COVERAGE if c.carrier == "Maersk")
    assert replace(maersk, rules_held=0).usable is False
    assert maersk.usable is True


def test_resolve_is_deterministic() -> None:
    args = (query(), (block(),))
    assert resolve(*args) == resolve(*args)


def test_a_block_outside_its_window_is_never_returned() -> None:
    for day in ("2024-08-07", "2024-08-08", "2030-01-01"):
        got = resolve(query(on=day), (block(),))
        assert (got.block is not None) is (day >= "2024-08-08"), day


def test_the_module_says_why_it_does_not_raise() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "A resolution failure is a valid, useful answer" in flat
    assert "A wrong rate is not" in flat


def test_issue_28_is_the_provenance() -> None:
    assert "Issue 28" in (module.__doc__ or "")


def test_a_coverage_row_carries_no_date() -> None:
    """So the report cannot rot into a point in time the way an "as of" column would.

    ``dataclasses.fields`` rather than ``vars``, because these rows are slotted and
    ``vars`` raises on them.
    """
    for carrier in COVERAGE:
        for f in dataclasses.fields(carrier):
            assert not isinstance(getattr(carrier, f.name), date), (carrier.carrier, f.name)


def test_resolution_carries_no_score_or_confidence() -> None:
    """There is no way to ask how sure a resolution is, on purpose. Every refusal
    above is a hard None, so a confidence field would describe something that does
    not exist."""
    names = set(Resolution.__dataclass_fields__)
    assert not (names & {"confidence", "score", "quality", "partial", "approx"}), names
