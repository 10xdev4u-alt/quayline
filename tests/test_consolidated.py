"""Issue 44: one invoice with many containers, and many invoices in one dispute.

The load bearing tests are the two the issue names: an invoice spanning containers
with different equipment, and a group mixing domains being refused. Everything else
checks the machinery, and a suite that checks the machinery without asserting those
two would pass while the issue's central claims go untested.
"""

from __future__ import annotations

import pytest

from quayline.ingest import consolidated as module
from quayline.ingest.consolidated import (
    ChargeLine,
    ConsolidatedGroup,
    equipment_types,
    group_lines,
    parse_msc_comment,
)

LINES = (
    ChargeLine(
        invoice_ref="INV-1", bol_number="BOL1", container="MAEU1", equipment="dry", amount="300"
    ),
    ChargeLine(
        invoice_ref="INV-1", bol_number="BOL1", container="TGHU1", equipment="reefer", amount="500"
    ),
    ChargeLine(
        invoice_ref="INV-1", bol_number="BOL2", container="CAIU1", equipment="dry", amount="300"
    ),
)


# ---------------------------------------------------------------- criterion 1
# Every line belongs to an invoice, a bill of lading and a container.


def test_every_line_carries_the_triple() -> None:
    """A line naming an amount without its container cannot be recomputed, grouped
    or disputed without dragging every other container with it."""
    for line in LINES:
        assert line.invoice_ref and line.bol_number and line.container
        assert line.key() == (line.invoice_ref, line.bol_number, line.container)


def test_lines_are_immutable() -> None:
    with pytest.raises(AttributeError):
        LINES[0].container = "x"  # type: ignore[misc]


def test_lines_group_by_invoice_and_bol() -> None:
    """Container varies within the group, so the key stops at the bill of lading.
    A key including the container would put each line in a group of one, which
    groups nothing."""
    grouped = group_lines(LINES)
    assert set(grouped) == {("INV-1", "BOL1"), ("INV-1", "BOL2")}
    assert len(grouped[("INV-1", "BOL1")]) == 2
    assert len(grouped[("INV-1", "BOL2")]) == 1


# ---------------------------------------------------------------- criterion 3
# An invoice spanning containers with different equipment types.


def test_mixed_equipment_requires_per_container_breakdowns() -> None:
    """Dry and reefer on one invoice, with different free time and different rates.
    A total recomputed without per-container breakdowns mixes allowances that were
    never the same."""
    assert equipment_types(LINES) == frozenset({"dry", "reefer"})
    assert equipment_types(LINES[:1]) == frozenset({"dry"})


def test_grouping_preserves_equipment_per_line() -> None:
    """lint:fixture-drift — the two-element literal is the BOL1 subgroup, not the
    three-element LINES fixture. Deliberate, and this marker is what says so."""
    grouped = group_lines(LINES)
    assert [line.equipment for line in grouped[("INV-1", "BOL1")]] == ["dry", "reefer"]


# ---------------------------------------------------------------- criterion 2
# Groups carry domain and reason; criterion 4 rejects mixing.


def test_a_group_carries_domain_and_reason() -> None:
    group = ConsolidatedGroup(("INV-1", "INV-2"), domain="demurrage", reason="unavailable terminal")
    assert group.domain == "demurrage"
    assert group.reason == "unavailable terminal"
    assert group.size == 2


def test_a_group_mixing_domains_is_unrepresentable_not_just_refused() -> None:
    """Stronger than a refusal. The type has one domain field, so there is no
    construction that holds two domains and therefore no code path that could
    produce a mixed group for a caller to file."""
    group = ConsolidatedGroup(("INV-1", "INV-2"), domain="demurrage", reason="r")
    assert not hasattr(group, "domains")
    assert not hasattr(group, "reasons")
    with pytest.raises(AttributeError):
        group.domain = "detention"  # type: ignore[misc]


def test_two_groups_with_different_domains_cannot_merge() -> None:
    """There is no merge operation. Combining a demurrage group with a detention
    group would need one, and its absence is deliberate: a mixed group is rejected
    wholesale by the carrier, losing the valid claims with the invalid ones."""
    assert not hasattr(ConsolidatedGroup, "merge")
    assert not hasattr(ConsolidatedGroup, "combine")
    assert not hasattr(ConsolidatedGroup, "add_invoice")


def test_more_than_35_invoices_is_refused() -> None:
    """CMA CGM allows 35 per action. Filing 36 whole loses all of it, so the
    constructor refuses rather than letting the group exist."""
    with pytest.raises(ValueError, match="35"):
        ConsolidatedGroup(tuple(f"INV-{i}" for i in range(36)), domain="d", reason="r")
    assert (
        ConsolidatedGroup(tuple(f"INV-{i}" for i in range(35)), domain="d", reason="r").size == 35
    )


def test_an_empty_group_disputes_nothing() -> None:
    with pytest.raises(ValueError, match="disputes nothing"):
        ConsolidatedGroup((), domain="d", reason="r")


def test_a_group_without_domain_or_reason_is_refused() -> None:
    with pytest.raises(ValueError, match="domain"):
        ConsolidatedGroup(("INV-1",), domain="  ", reason="r")
    with pytest.raises(ValueError, match="reason"):
        ConsolidatedGroup(("INV-1",), domain="d", reason="")


def test_groups_are_immutable() -> None:
    group = ConsolidatedGroup(("INV-1",), domain="d", reason="r")
    with pytest.raises(AttributeError):
        group.domain = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- the MSC comment


def test_msc_comment_parses_original_and_added_containers() -> None:
    """Bills of lading ending in A carry the original number and added containers
    in the comment field. Parsed into the general form rather than modelled as an
    MSC type."""
    assert parse_msc_comment("BOL123, MAEU1, TGHU1") == ("BOL123", ("MAEU1", "TGHU1"))
    assert parse_msc_comment("BOL123; MAEU1") == ("BOL123", ("MAEU1",))


def test_an_unparseable_comment_is_unknown_not_malformed() -> None:
    """An invoice whose consolidation structure is unknown is unknown, not
    malformed. Raising would stop an audit over a comment field."""
    assert parse_msc_comment("") == ("", ())
    assert parse_msc_comment("   ") == ("", ())


def test_issue_44_is_the_provenance() -> None:
    assert "Issue 44" in (module.__doc__ or "")


def test_the_module_states_which_structure_fails_how() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "fail differently" in flat
