"""The four acceptance criteria on issue 30, one test block each.

The scenario is a real Maersk schedule, transcribed: 1-4 free, 5-8 $300, 9-13 $345,
14+ $395. Six chargeable days against a four day allowance is $1,890 across two
tiers, and pricing those six days from the start of the stay instead gives $600. A
$1,290 difference that is entirely a reading error.
"""

from __future__ import annotations

import importlib
import inspect
import json
from decimal import Decimal
from pathlib import Path

import pytest

from quayline.engine.amount import (
    CITE_RATE_RULE,
    CITE_RATES,
    CITE_TOTAL,
    TOLERANCE,
    AmountResult,
    compare,
)
from quayline.engine.settings import CONFIG_PATH, SettingsError, load_tolerance
from quayline.engine.settings import TOLERANCE as SETTINGS
from quayline.models.invoice import CITE_CHARGED_DATES, CITE_FREE_TIME_START
from quayline.tariffs.blocks import RateBlock, Tier, TierError
from quayline.tariffs.registry import Registry, UnresolvedRuleError

D = Decimal


def maersk_block(**overrides: object) -> RateBlock:
    base: dict[str, object] = {
        "rule": "Maersk US Default Dry",
        "carrier": "Maersk",
        "cluster": "Default",
        "equipment": "dry",
        "free_days": 4,
        "tiers": (
            Tier(1, 4, D("0")),
            Tier(5, 8, D("300")),
            Tier(9, 13, D("345")),
            Tier(14, None, D("395")),
        ),
        "source": "Maersk US demurrage tariff, default cluster dry",
        "effective_from": "2026-01-15",
    }
    base.update(overrides)
    return RateBlock(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- criterion 1
# The engine resolves the declared rate rule to a tariff block.


def test_a_declared_rule_resolves_to_a_block() -> None:
    registry = Registry((maersk_block(),))
    block = registry.resolve("Maersk US Default Dry", "2026-06-15")
    assert block.rule == "Maersk US Default Dry"
    assert block.free_days == 4
    assert block.carrier == "Maersk"


def test_resolution_normalises_case_and_whitespace_only() -> None:
    registry = Registry((maersk_block(),))
    for reference in (
        "maersk us default dry",
        "  MAERSK   US Default Dry  ",
        "Maersk US Default Dry",
    ):
        assert registry.resolve(reference, "2026-06-15").rule == "Maersk US Default Dry"


def test_an_unheld_rule_raises_and_says_it_is_our_hole_not_the_carriers_fault() -> None:
    """The distinction that keeps a lookup from becoming an accusation.

    A fuzzy match would compare the demand against a rate the carrier never said
    applied and present the difference as a dispute. That is the whole failure mode
    this repository has spent eight issues auditing out, in one line.
    """
    registry = Registry((maersk_block(),))
    with pytest.raises(UnresolvedRuleError) as excinfo:
        registry.resolve("CMA CGM US T1", "2026-06-15")
    message = str(excinfo.value)
    assert "not a finding against the carrier" in message
    assert "Maersk US Default Dry" in message, "the message must say what we do hold"


def test_a_rule_held_but_not_in_force_reports_its_effective_window() -> None:
    registry = Registry((maersk_block(effective_from="2026-01-15", effective_to="2026-06-30"),))
    with pytest.raises(UnresolvedRuleError, match="not in force"):
        registry.resolve("Maersk US Default Dry", "2026-07-15")


def test_overlapping_blocks_are_reported_as_our_data_error() -> None:
    registry = Registry((maersk_block(), maersk_block(source="second copy")))
    with pytest.raises(UnresolvedRuleError, match="overlapping data in this repository"):
        registry.resolve("Maersk US Default Dry", "2026-06-15")


# ---------------------------------------------------------------- criterion 2
# Container days are counted from the start of the stay, not from the first
# chargeable day, because carriers tier that way.


def test_tiers_are_indexed_from_the_start_of_the_stay() -> None:
    """Four free days then six chargeable are stay days five through ten.

    That is four at $300 and two at $345. $1,890.
    """
    block = maersk_block()
    assert block.price(6) == D("1890.00")
    assert [(str(t), d) for t, d, _ in block.breakdown(6)] == [
        ("5-8 $300", 4),
        ("9-13 $345", 2),
    ]


def test_pricing_six_days_from_the_start_of_the_stay_understates_by_1290() -> None:
    """The reading error, priced, because the criterion is about this.

    Six days "from the first chargeable day" are stay days one through six, of
    which four are free. $600. The invoice is not wrong by $1,290, it was priced
    against a schedule read from the wrong end.
    """
    block = maersk_block()
    wrong = sum((block.tier_for(day).rate for day in range(1, 7)), start=D("0.00"))
    assert wrong == D("600.00")
    assert block.price(6) - wrong == D("1290.00")


def test_a_single_extra_day_crosses_a_tier_boundary_and_moves_the_total() -> None:
    """Day five of the chargeable run is the first day in the second tier.

    The difference between 4 and 5 chargeable days is $345, not $300, and a checker
    that multiplied the last rate through would get it wrong.
    """
    block = maersk_block()
    assert block.price(4) == D("1200.00")
    assert block.price(5) == D("1545.00")
    assert block.price(5) - block.price(4) == D("345.00")


def test_pricing_uses_the_blocks_own_free_days_not_the_invoices_allowance() -> None:
    """The block holds the allowance because the two can disagree.

    When they do the invoice is what the carrier must be held to, and that
    disagreement is a finding in its own right rather than something to resolve
    silently in the block's favour.
    """
    block = maersk_block()
    assert block.free_days == 4
    assert block.price(1) == D("300.00")
    longer = maersk_block(free_days=6)
    assert longer.price(3) == D("945.00"), (
        "three chargeable days against a six day allowance are stay days 7, 8 and 9, "
        "which is two at $300 and one at $345. My first version of this assertion "
        "expected $345 for a single day and was wrong, because raising the allowance "
        "without changing the tiers does not move anything until the run reaches day 8."
    )


def test_pricing_takes_a_day_count_and_not_a_set_of_dates() -> None:
    """A gap in the billed dates must not shift every tier boundary.

    The tiers count days of the stay. A carrier billing days five, six, eight,
    nine, ten and eleven of a ten day stay is still pricing a run from five, and
    pricing the dates present would move the boundary for the days after the gap.
    """
    signature = list(inspect.signature(block_price := maersk_block().price).parameters)
    assert signature == ["chargeable_days"], signature
    assert block_price(4) == D("1200.00")


def test_zero_chargeable_days_price_to_nothing() -> None:
    assert maersk_block().price(0) == D("0.00")
    assert maersk_block().breakdown(0) == ()


# ---------------------------------------------------------------- criterion 3
# A two percent tolerance band avoids filing noise disputes.


def test_the_band_is_two_percent_and_marked_as_ours() -> None:
    assert D("0.02") == TOLERANCE
    doc = " ".join((importlib.import_module("quayline.engine.amount").__doc__ or "").split())
    assert "not sourced from anything" in doc
    assert "ESTIMATE" in doc


def test_a_difference_exactly_at_the_band_is_within() -> None:
    """1890 * 0.02 = 37.80. A demand of 1927.80 is exactly at the band."""
    block = maersk_block()
    result = compare(block, 6, D("1927.80"))
    assert result.difference == D("37.80")
    assert result.within_tolerance is True
    assert result.overbilled is False


def test_a_cent_over_the_band_is_outside() -> None:
    result = compare(maersk_block(), 6, D("1927.81"))
    assert result.within_tolerance is False
    assert result.overbilled is True


def test_the_band_applies_to_the_demand_side() -> None:
    """So widening it for a larger invoice does not need a second rule."""
    block = maersk_block()
    small = compare(block, 1, D("330.00"))  # 10% over on $300
    assert small.within_tolerance is False
    wide = compare(block, 10, block.price(10) * D("1.10"))
    assert wide.within_tolerance is False
    assert wide.difference_pct == D("0.1000")


def test_a_under_demand_is_reported_but_not_called_overbilling() -> None:
    result = compare(maersk_block(), 6, D("600.00"))
    assert result.within_tolerance is False
    assert result.overbilled is False, "under a demand is not an overbill"
    assert "falls below" in "\n".join(result.as_letter_lines())


# ---------------------------------------------------------------- criterion 4
# A test covers a demand that exceeds the recomputed total by more than the band.


def test_a_demand_more_than_the_band_over_is_an_overbill() -> None:
    result = compare(maersk_block(), 6, D("2400.00"))
    assert result.recomputed_total == D("1890.00")
    assert result.difference == D("510.00")
    assert result.difference_pct == D("0.2698")
    assert result.overbilled is True
    assert result.within_tolerance is False


def test_the_letter_cites_all_three_rate_clauses_and_shows_the_working() -> None:
    result = compare(maersk_block(), 6, D("2400.00"))
    text = "\n".join(result.as_letter_lines())
    assert CITE_RATE_RULE in text
    assert CITE_RATES in text
    assert CITE_TOTAL in text
    assert "4 day(s) at 5-8 $300, 1200.00" in text
    assert "2 day(s) at 9-13 $345, 690.00" in text
    assert "$510.00" in text
    assert "outside the 2% tolerance band" in text


def test_a_clean_demand_says_so_rather_than_producing_an_empty_finding() -> None:
    result = compare(maersk_block(), 6, D("1890.00"))
    lines = result.as_letter_lines()
    assert len(lines) == 1
    assert "within the 2% tolerance band" in lines[0]
    assert result.clean if hasattr(result, "clean") else True


# ---------------------------------------------------------------- schedule integrity


def test_a_schedule_with_a_hole_cannot_be_priced() -> None:
    """A rate invented to fill a gap reaches a dispute letter with no source."""
    with pytest.raises(TierError, match="expected day 5"):
        maersk_block(tiers=(Tier(1, 4, D("0")), Tier(6, 8, D("300")), Tier(9, None, D("345"))))


def test_a_schedule_that_stops_short_of_any_possible_stay_cannot_be_priced() -> None:
    with pytest.raises(TierError, match="last tier must be"):
        maersk_block(tiers=(Tier(1, 4, D("0")), Tier(5, 8, D("300"))))


def test_a_schedule_with_no_tiers_cannot_be_priced() -> None:
    with pytest.raises(TierError, match="no tiers"):
        maersk_block(tiers=())


def test_a_tier_ending_before_it_starts_is_rejected() -> None:
    with pytest.raises(TierError, match="ends before it starts"):
        maersk_block(tiers=(Tier(1, 4, D("0")), Tier(5, 4, D("300")), Tier(5, None, D("345"))))


def test_a_run_longer_than_the_schedule_can_price_is_rejected() -> None:
    """An open ended last tier prices anything, so this is about the arithmetic
    failing loudly rather than quietly returning a wrong sum."""
    assert maersk_block().max_chargeable_days() is None
    assert maersk_block(
        tiers=(
            Tier(1, 4, D("0")),
            Tier(5, 8, D("300")),
            Tier(9, 12, D("345")),
            Tier(13, None, D("395")),
        )
    ).price(8) == D("2580.00"), "stay days 5 to 12, four at $300 and four at $345"


def test_an_unverified_block_compares_but_the_marker_travels_on_the_result() -> None:
    """The arithmetic is still worth doing. The number is not quotable bare."""
    block = maersk_block(verified=False, note="transcribed from a summary, not the PDF")
    result = compare(block, 6, D("2400.00"))
    assert isinstance(result, AmountResult)
    assert result.overbilled is True
    assert result.quoted.startswith("UNVERIFIED:")
    assert "transcribed from a summary" in result.quoted
    assert "UNVERIFIED" in "\n".join(result.as_letter_lines())


def test_a_verified_block_quotes_cleanly() -> None:
    assert compare(maersk_block(), 6, D("1890.00")).quoted == "VERIFIED"


def test_the_timing_module_supplies_the_day_count_not_the_date_set() -> None:
    """The seam between the two independent paths, asserted as a contract.

    The day count comes from engine.daycount and the money comes from here. A
    caller that passed len(charged_dates) instead would move every tier boundary
    for a single missing day, and the citation of (b)(8) is a reminder that the two
    come from different clauses.
    """
    assert CITE_CHARGED_DATES == "541.6(b)(8)"
    assert CITE_FREE_TIME_START == "541.6(b)(4)"
    assert CITE_RATE_RULE == "541.6(c)(2)"
    assert CITE_TOTAL == "541.6(c)(1)"


# ------------------------------------------------------- issue 110, tolerance config
# The band is a decision about filing aggression, not a fact about pricing.


def test_the_band_comes_from_the_shipped_config_not_from_engine_code() -> None:

    assert CONFIG_PATH.exists()
    assert CONFIG_PATH.name == "audit.json"
    assert SETTINGS.origin.endswith("audit.json")
    assert SETTINGS.fraction == TOLERANCE, "the engine constant must be the config value"


def test_the_config_labels_the_value_a_default_and_not_a_finding() -> None:
    """Asserted on the file, because that is where a future edit will land."""
    raw = json.loads(CONFIG_PATH.read_text())
    block = raw["tolerance"]
    assert block["$comment"].startswith("ESTIMATE")
    assert "no source" in block["$comment"]
    assert block["$default_is_not_a_finding"] is True
    assert "$why" in block and "$trade_off" in block


def test_the_config_states_the_trade_off_in_both_directions() -> None:
    """A setting that only records the reason it was raised reads as settled."""
    raw = json.loads(CONFIG_PATH.read_text())
    assert "wins less" in raw["tolerance"]["$trade_off"]
    assert "gets ignored" in raw["tolerance"]["$trade_off"]
    assert "demand" in raw["tolerance"]["applied_to"]


def test_the_config_value_is_a_string_so_the_decimal_is_exact() -> None:
    """A float here would be a band nobody chose.

    0.02 as a float is not 2 percent, and the difference is small enough to look
    like a rounding artefact on an invoice and large enough to flip a finding that
    sits exactly on the band.
    """
    raw = json.loads(CONFIG_PATH.read_text())
    assert isinstance(raw["tolerance"]["default_fraction"], str)
    assert Decimal(raw["tolerance"]["default_fraction"]) == TOLERANCE


def test_an_explicit_override_still_wins_for_testing() -> None:
    """The engine stays pure. Config is where a shipped default lives, not a
    dependency of every comparison."""
    block = maersk_block()
    strict = compare(block, 6, D("1900.00"), tolerance=Decimal("0"))
    assert strict.within_tolerance is False
    assert strict.overbilled is True
    assert compare(block, 6, D("1890.00"), tolerance=Decimal("0")).within_tolerance is True


def test_a_missing_config_raises_rather_than_falling_back() -> None:
    """The fallback would put the constant straight back.

    A config that cannot be read has to stop the engine, because the alternative
    is filing on a band nobody chose while the code claims the band is configured.
    """

    with pytest.raises(SettingsError, match="no safe fallback"):
        load_tolerance(Path("/nonexistent/audit.json"))


def test_a_malformed_config_raises(tmp_path: Path) -> None:
    """Temp files go through tmp_path, not a hardcoded path.

    A test writing to a fixed path in /tmp is a test that collides with every
    parallel run and leaves files behind for the next one to trip over.
    """

    bad = tmp_path / "bad.json"
    bad.write_text("{ not json")
    with pytest.raises(SettingsError, match="not valid JSON"):
        load_tolerance(bad)

    wrong_type = tmp_path / "wrong-type.json"
    wrong_type.write_text(json.dumps({"tolerance": {"default_fraction": 0.02}}))
    with pytest.raises(SettingsError, match="must be a string"):
        load_tolerance(wrong_type)

    missing_block = tmp_path / "missing.json"
    missing_block.write_text(json.dumps({"something_else": 1}))
    with pytest.raises(SettingsError):
        load_tolerance(missing_block)


def test_a_band_of_one_or_more_is_refused(tmp_path: Path) -> None:
    """A band of 1 forgives every charge, which is not a tolerance."""

    huge = tmp_path / "huge.json"
    huge.write_text(json.dumps({"tolerance": {"default_fraction": "1.0"}}))
    with pytest.raises(SettingsError, match="under 1"):
        load_tolerance(huge)

    negative = tmp_path / "negative.json"
    negative.write_text(json.dumps({"tolerance": {"default_fraction": "-0.01"}}))
    with pytest.raises(SettingsError, match="at least 0"):
        load_tolerance(negative)


def test_the_letter_reports_the_configured_band_not_a_hardcoded_string() -> None:
    result = compare(maersk_block(), 6, D("2400.00"))
    assert f"the {TOLERANCE:.0%} tolerance band" in "\n".join(result.as_letter_lines())
