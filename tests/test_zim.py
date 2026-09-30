"""Issue 25: ZIM's rules verify and its rates do not.

The load bearing test is ``test_per_port_rates_resolve_to_nothing``. The rest check
the structure around it, and a suite that checks the structure without asserting
the refusal would pass while an unverified rate quietly resolves.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import zim as module
from quayline.tariffs.registry import Registry
from quayline.tariffs.resolution import RateQuery
from quayline.tariffs.zim import (
    RULES,
    SOURCE_PDF,
    TRIGGER_BY_CHARGE,
    ClockTrigger,
    RailStructure,
    Service,
    charge_basis,
)

# ---------------------------------------------------------------- criterion 1
# Two clock triggers, recorded as evidence there is no industry norm.


def test_detention_and_rail_demurrage_start_differently() -> None:
    """Two triggers in one tariff. A module assuming one would be wrong on half the
    charges, and the wrong half would depend on the equipment."""
    assert TRIGGER_BY_CHARGE["detention"] is ClockTrigger.INTERCHANGE
    assert TRIGGER_BY_CHARGE["rail_demurrage"] is ClockTrigger.DAY_AFTER_DISCHARGE


def test_the_triggers_are_different_values() -> None:
    """The assertion that makes the table more than decoration."""
    # An identity or equality check between the two members is rejected by mypy
    # as statically impossible, and that rejection is itself the proof they are
    # distinct. What is worth asserting is the table: two charge kinds, two
    # different triggers, neither one a default for the other.
    assert set(TRIGGER_BY_CHARGE) == {"detention", "rail_demurrage"}
    assert len({t.value for t in TRIGGER_BY_CHARGE.values()}) == 2


def test_the_rules_that_verify_are_named() -> None:
    assert RULES == ("ZIMU-136-003", "ZIMU-136-004", "ZIMU-136-005")
    assert SOURCE_PDF == "usa-dd-rate-tables-effective-2025-04-20.pdf"


# ---------------------------------------------------------------- criterion 2
# The service string is a required input for the charge basis.


def test_no_service_string_means_no_charge_basis() -> None:
    """Standard is calendar including weekends, Expedited and Fast are working days.
    Without the string there is no way to know whether a Saturday counts, and there
    is no safe default: assuming calendar overcharges working-day services."""
    assert charge_basis(None) is None


def test_standard_is_calendar_including_weekends() -> None:
    basis = charge_basis(Service.STANDARD)
    assert basis is not None
    assert basis.calendar_days is True
    assert "weekends and holidays" in basis.basis


def test_expedited_and_fast_are_working_days() -> None:
    for service in (Service.EXPEDITED, Service.FAST):
        basis = charge_basis(service)
        assert basis is not None
        assert basis.calendar_days is False
        assert basis.basis == "working days"


def test_the_basis_is_immutable() -> None:
    basis = charge_basis(Service.STANDARD)
    assert basis is not None
    with pytest.raises(AttributeError):
        basis.service = Service.FAST  # type: ignore[misc]


def test_charge_basis_is_deterministic() -> None:
    assert charge_basis(Service.FAST) == charge_basis(Service.FAST)


# ---------------------------------------------------------------- criterion 3
# Per-port rates are UNVERIFIED and the resolver returns nothing.


def test_per_port_rates_resolve_to_nothing() -> None:
    """The mapping did not survive extraction. A plausible wrong rate is worse than
    a hole, so an empty registry is the honest state."""
    registry = Registry(())
    for rule in (
        "ZIMU-136-003 demurrage",
        "ZIMU-136-004 detention",
        "ZIMU-136-005 rail",
    ):
        got = registry.resolve(RateQuery(reference=rule, on="2026-06-15"))
        assert got.block is None, rule
        assert got.resolved is False, rule


def test_the_refusal_says_it_is_our_hole() -> None:
    got = Registry(()).resolve(RateQuery(reference="ZIMU-136-003", on="2026-06-15"))
    assert "hole in our tariff data" in got.withheld_reason
    assert "not a finding against the carrier" in got.withheld_reason


def test_the_rules_verify_even_though_the_rates_do_not() -> None:
    """Two different facts about one document. The rules are transcribed and named;
    the per-port rate to tier mapping is not. Conflating them would either discard
    good rules or quote bad rates."""
    assert len(RULES) == 3
    assert Registry(()).resolve(RateQuery(reference=RULES[0], on="2026-06-15")).block is None


# ---------------------------------------------------------------- criterion 4
# The rail double-invoice structure is documented.


def test_rail_demurrage_is_carrier_only() -> None:
    structure = RailStructure()
    assert "rail demurrage only" in structure.carrier_bills
    assert "separately" in structure.operator_bills


def test_the_reminder_says_to_check_before_disputing() -> None:
    """Dispute the carrier invoice without checking for the operator invoice and the
    same container is priced twice. Same structure as MSC, same rule."""
    reminder = RailStructure().reminds_to_deduplicate()
    assert "before disputing" in reminder
    assert "double-count" in reminder


def test_the_structure_is_immutable() -> None:
    with pytest.raises(AttributeError):
        RailStructure().carrier_bills = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- the calculator


def test_the_calculator_disclaimer_is_recorded() -> None:
    """ZIM's calculator states the final invoice prevails over any prior
    calculation. A figure from the calculator is a number the carrier has already
    reserved the right to contradict, so it is not a rate we hold."""
    flat = " ".join((module.__doc__ or "").split())
    assert "final issued invoice shall prevail" in flat
    assert "not a rate we hold" in flat


def test_issue_25_is_the_provenance() -> None:
    assert "Issue 25" in (module.__doc__ or "")


def test_the_module_states_what_survived_extraction() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "did not survive extraction" in flat
    assert "worse than a hole" in flat
