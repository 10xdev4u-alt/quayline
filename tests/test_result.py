"""Issue 38: the public shape of an audit result.

The first test is the one that matters. It locks the field set, because a result type
that grows a field is a public API change, and a public API change that nobody
decided on is a public API change nobody reviewed. Everything else in this file
checks the invariants that keep the three states apart.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

import quayline.engine.result as module
from quayline.engine.result import (
    BLOCKING_CODES,
    CODE_AMOUNT_VARIANCE,
    CODE_TARIFF_UNRESOLVED,
    CODE_VALIDATION_FAILED,
    AuditResult,
    Finding,
    variance_of,
    variance_pct_of,
)
from quayline.evidence.checklist import Ground

#: The shape, written out. A change here is a change to every caller and has to be
#: made deliberately in this file rather than discovered by a downstream break.
PUBLIC_FIELDS = {
    "carrier",
    "invoice_ref",
    "terminal",
    "demanded_total",
    "recomputed_total",
    "variance",
    "variance_pct",
    "computed_free_time_expiry",
    "computed_charge_days",
    "unfilled_fields",
    "warnings",
    "findings",
    # Added in issue 189 so a renderer can show which days were free, chargeable and
    # billed without recomputing them. The lock exists so that adding a field is a
    # decision rather than an accident, and this one is recorded here.
    "day_count",
}


def result(**kw: object) -> AuditResult:
    base: dict[str, object] = {"carrier": "Maersk"}
    base.update(kw)
    return AuditResult(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------- the API surface


def test_the_public_shape_is_locked() -> None:
    """A field added here breaks every caller and has to be a decision."""
    assert {f.name for f in dataclasses.fields(AuditResult)} == PUBLIC_FIELDS


def test_every_public_field_has_a_default() -> None:
    """So a checker that finds nothing can return a result rather than raising."""
    for f in dataclasses.fields(AuditResult):
        assert f.default is not dataclasses.MISSING or f.name == "carrier", f.name


def test_the_result_is_immutable() -> None:
    """Criterion one. A value object, so no caller can edit an audit after the fact."""
    with pytest.raises(AttributeError):
        result().carrier = "MSC"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        result().findings = ()  # type: ignore[misc]


def test_it_is_slotted_so_there_is_no_hidden_state() -> None:
    assert "carrier" in AuditResult.__slots__
    assert not hasattr(result(), "__dict__")


def test_with_finding_returns_a_new_result() -> None:
    """Composition, not mutation. A mutated intermediate is something a caller could
    have observed and quoted."""
    before = result()
    after = before.with_finding(Finding(code=CODE_TARIFF_UNRESOLVED, cite="x", summary="y"))
    assert before.findings == ()
    assert len(after.findings) == 1
    assert before is not after


def test_the_finding_shape_is_locked_too() -> None:
    assert {f.name for f in dataclasses.fields(Finding)} == {
        "code",
        "cite",
        "summary",
        "detail",
        "grounds",
        "days",
    }


# ---------------------------------------------------------------- criterion 2
# The recomputed total is None when the tariff did not resolve, never zero.


def test_an_unresolved_tariff_gives_a_none_total() -> None:
    r = result(recomputed_total=None, demanded_total=Decimal("4800.00"))
    assert r.recomputed_total is None
    assert r.tariff_resolved is False


def test_a_genuine_zero_total_is_a_value_and_not_a_none() -> None:
    """The distinction the whole module is for. A tariff that prices the first day at
    nothing produces zero, and zero is a finding worth filing."""
    r = result(recomputed_total=Decimal("0.00"), demanded_total=Decimal("4800.00"))
    assert r.recomputed_total == Decimal("0.00")
    assert r.recomputed_total is not None
    assert r.tariff_resolved is True, "zero means we priced it, not that we could not"


def test_variance_against_an_unresolved_tariff_is_none_not_zero() -> None:
    """The failure this module exists to prevent.

    A system that cannot price an invoice and subtracts anyway reports that the
    carrier overbilled by exactly the demand. That number would go in a letter.
    """
    assert variance_of(Decimal("4800.00"), None) is None
    assert variance_of(None, Decimal("4800.00")) is None
    assert variance_of(None, None) is None


def test_variance_is_none_when_only_one_side_is_unknown() -> None:
    """One known side is not enough. This is the case a naive
    ``demand - recompute`` gets wrong, because it has one number to work with."""
    assert variance_of(Decimal("1"), None) is None
    assert variance_of(None, Decimal("1")) is None


def test_variance_is_the_difference_when_both_are_known() -> None:
    assert variance_of(Decimal("4800.00"), Decimal("2400.00")) == Decimal("2400.00")
    assert variance_of(Decimal("2400.00"), Decimal("4800.00")) == Decimal("-2400.00")


def test_a_zero_difference_is_a_zero_variance_not_a_none() -> None:
    """A carrier that billed correctly produces zero variance, and that is an answer."""
    assert variance_of(Decimal("2400.00"), Decimal("2400.00")) == Decimal("0.00")


def test_the_invariant_is_enforced_at_construction() -> None:
    """A caller cannot build an inconsistent result even by accident."""
    with pytest.raises(ValueError, match="variance"):
        result(demanded_total=Decimal("4800.00"), recomputed_total=None, variance=Decimal("4800"))
    with pytest.raises(ValueError, match="variance"):
        result(demanded_total=None, recomputed_total=Decimal("1"), variance=Decimal("1"))


def test_a_percentage_of_zero_base_is_none() -> None:
    """The third way this could go wrong. A percentage of zero is not a number."""
    assert variance_pct_of(Decimal("0"), Decimal("0")) is None
    assert variance_pct_of(None, Decimal("100")) is None
    assert variance_pct_of(Decimal("1"), None) is None


def test_the_percentage_is_otherwise_computed() -> None:
    assert variance_pct_of(Decimal("100"), Decimal("400")) == Decimal("25")


# ---------------------------------------------------------------- criterion 3
# Variance is None rather than zero when either side is unknown.


def test_variance_pct_cannot_exist_without_both_totals() -> None:
    with pytest.raises(ValueError, match="variance_pct"):
        result(recomputed_total=None, variance_pct=Decimal("25"))


def test_the_result_never_carries_a_variance_it_cannot_support() -> None:
    r = result(demanded_total=Decimal("4800.00"), recomputed_total=None)
    assert r.variance is None
    assert r.variance_pct is None


# ---------------------------------------------------------------- criterion 4
# One gate, and it is not waivable.


def test_can_file_is_the_only_gate() -> None:
    assert not hasattr(result(), "should_file")
    assert not hasattr(result(), "warnings_waivable")
    assert not hasattr(result(), "severity")


def test_no_blocking_finding_means_it_can_file() -> None:
    assert result().can_file is True
    assert result().reason_not_filed() == ""


def test_a_blocking_finding_stops_it() -> None:
    r = result().with_finding(
        Finding(code=CODE_TARIFF_UNRESOLVED, cite="c", summary="no rate held")
    )
    assert r.can_file is False
    assert "tariff_unresolved" in r.reason_not_filed()


def test_blocking_is_decided_by_the_closed_code_list() -> None:
    """Not by a caller. A caller deciding is how a blocking check gets waived."""
    assert CODE_TARIFF_UNRESOLVED in BLOCKING_CODES
    assert CODE_AMOUNT_VARIANCE in BLOCKING_CODES
    assert CODE_VALIDATION_FAILED in BLOCKING_CODES


def test_an_unknown_code_does_not_block() -> None:
    """Fail open on an unrecognised code, deliberately.

    A new informational finding from a new checker must not block filing by accident,
    which would make every new finding a change to the gate. Anything genuinely
    blocking has to be added to BLOCKING_CODES, where the diff shows it.
    """
    r = result().with_finding(Finding(code="future_finding", cite="c", summary="s"))
    assert r.can_file is True


def test_the_reason_names_every_blocker() -> None:
    r = (
        result()
        .with_finding(Finding(code=CODE_TARIFF_UNRESOLVED, cite="c", summary="no rate held"))
        .with_finding(Finding(code=CODE_VALIDATION_FAILED, cite="c", summary="line sum differs"))
    )
    assert r.reason_not_filed().count(";") == 1
    assert "no rate held" in r.reason_not_filed()
    assert "line sum differs" in r.reason_not_filed()


# ---------------------------------------------------------------- findings


def test_a_finding_carries_its_ground() -> None:
    """So the packet does not have to guess where it belongs."""
    f = Finding(code="c", cite="x", summary="s", grounds=(Ground.GOVERNMENT_HOLD,))
    assert f.on_ground(Ground.GOVERNMENT_HOLD) is True
    assert f.on_ground(Ground.CONTRACT_CONDITION) is False


def test_findings_can_be_queried_by_ground() -> None:
    r = result().with_finding(
        Finding(code="a", cite="c", summary="s", grounds=(Ground.GOVERNMENT_HOLD,))
    )
    assert len(r.findings_on(Ground.GOVERNMENT_HOLD)) == 1
    assert r.findings_on(Ground.CONTRACT_CONDITION) == ()


def test_a_finding_carries_its_days() -> None:
    r = result().with_finding(
        Finding(code="a", cite="c", summary="s", days=(date(2026, 7, 8), date(2026, 7, 9)))
    )
    assert len(r.findings[0].days) == 2


# ---------------------------------------------------------------- what is absent


def test_there_is_no_quality_or_confidence_field() -> None:
    """A number describing how good an audit is, on a result that carries
    ``None`` for the things we could not compute, would be incoherent."""
    names = {f.name for f in dataclasses.fields(AuditResult)} | {
        f.name for f in dataclasses.fields(Finding)
    }
    banned = {"quality", "confidence", "score", "probability", "rating", "grade"}
    assert not (names & banned), names & banned


def test_there_is_no_partial_result() -> None:
    """Partial is how a half-computed audit gets treated as a whole one."""
    assert not hasattr(result(), "is_partial")
    assert not hasattr(result(), "partial")


def test_there_is_no_ordering_in_the_contract() -> None:
    """Ordering is issue 34 and it is a presentation decision. Putting it in the
    type every checker returns would make a layout change a semantic one."""
    assert not hasattr(result(), "ordered")
    assert not hasattr(result(), "render")


def test_issue_38_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 38" in flat
    assert "zero gets quoted" in flat
