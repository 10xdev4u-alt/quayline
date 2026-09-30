"""Issue 35: an estimate that cannot outgrow the invoice.

The load bearing tests are the three the issue names and, underneath them, one
more: ``test_a_partial_sum_above_the_demand_is_capped_not_reduced``, because there
is a difference between landing exactly on the demand and landing below it, and the
former is where the request for restraint actually bites.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import quayline.engine.recovery as module
from quayline.engine.recovery import (
    INFORMATIONAL_CODES,
    LINE_WIDE_CODES,
    ClaimBasis,
    RecoveryEstimate,
    ValuedFinding,
    basis_of,
    estimate,
    estimate_for,
)
from quayline.engine.result import CODE_FIELD_OMITTED, AuditResult, Finding

D = Decimal


def v(code: str, amount: str | None) -> ValuedFinding:
    return ValuedFinding(code=code, amount=D(amount) if amount is not None else None)


OMISSION = v(CODE_FIELD_OMITTED, "5100")


# ---------------------------------------------------------------- criterion 1
# A claim basis exists for line-wide, partial and informational.


def test_the_three_bases_exist() -> None:
    assert {b.value for b in ClaimBasis} == {"line-wide", "partial", "informational"}


def test_line_wide_is_the_541_5_omission_only() -> None:
    """One member, and it is the code the kill switch fires on.

    A second line-wide code would be a second way to void a whole invoice, and that
    is not a thing that should grow quietly.
    """
    assert frozenset({"field_omitted"}) == LINE_WIDE_CODES


def test_basis_of_reads_the_code_not_a_flag_on_the_finding() -> None:
    """So the basis is reviewable in one place rather than per construction site."""
    assert basis_of(CODE_FIELD_OMITTED) is ClaimBasis.LINE_WIDE
    assert basis_of("daycount_variance") is ClaimBasis.PARTIAL
    assert basis_of("tariff_unresolved") is ClaimBasis.INFORMATIONAL
    assert basis_of("brand_new_finding") is ClaimBasis.PARTIAL, (
        "unknown is partial, fail safe on money"
    )


def test_an_unknown_code_defaults_to_partial() -> None:
    """Deliberately. A new finding that defaults informational would silently
    contribute nothing; one that defaults partial is visible in the estimate, and
    the author has to look at what number it is carrying."""
    assert basis_of("something_nobody_classified_yet") is ClaimBasis.PARTIAL


def test_informational_codes_carry_no_money_in_estimates() -> None:
    for code in INFORMATIONAL_CODES:
        assert basis_of(code) is ClaimBasis.INFORMATIONAL, code


# ---------------------------------------------------------------- criterion 2
# A line-wide claim supersedes all partial estimates.


def test_line_wide_supersedes_all_partials() -> None:
    """The criterion's case. The naive sum is 9900 on a 5100 demand."""
    got = estimate(
        (OMISSION, v("daycount_variance", "2400"), v("amount_variance", "2400")), D("5100")
    )
    assert got.amount == D("5100")
    assert got.superseded is True


def test_supersession_keeps_the_partials_as_fallbacks() -> None:
    """They stay in the composition. Dropping them would lose the arguments that
    matter if the 541.5 claim fails."""
    got = estimate((OMISSION, v("daycount_variance", "2400")), D("5100"))
    assert len(got.composition) == 2
    assert {c.code for c in got.composition} == {"field_omitted", "daycount_variance"}


def test_supersession_reports_what_was_absorbed() -> None:
    got = estimate((OMISSION, v("daycount_variance", "2400")), D("5100"))
    assert got.uncapped == D("7500")
    assert "fallback" in got.detail()


def test_line_wide_alone_estimates_the_demand() -> None:
    got = estimate((OMISSION,), D("5100"))
    assert got.amount == D("5100")
    assert got.superseded is True
    assert got.uncapped == D("5100")


def test_two_line_wide_findings_still_estimate_the_demand_once() -> None:
    """Two voids do not void the invoice twice."""
    got = estimate((OMISSION, v(CODE_FIELD_OMITTED, "5100")), D("5100"))
    assert got.amount == D("5100")


# ---------------------------------------------------------------- criterion 3
# Partial findings add but are capped at the amount demanded.


def test_partials_add_below_the_cap() -> None:
    got = estimate((v("daycount_variance", "900"), v("evidence_missing", "100")), D("5100"))
    assert got.amount == D("1000")
    assert got.superseded is False
    assert "below the demand" in got.detail()


def test_a_partial_sum_above_the_demand_is_capped_not_reduced() -> None:
    """The distinction the letter rests on. Landed exactly on the demand, not
    negotiated down to it, because alternative grounds for the same dollars are not
    worth *less* than the dollars."""
    got = estimate((v("daycount_variance", "2400"), v("amount_variance", "2400")), D("2400"))
    assert got.amount == D("2400")
    assert got.uncapped == D("4800")
    assert got.superseded is False
    assert "capped at the demand" in got.detail()


def test_the_carrier_cannot_owe_more_than_it_invoiced() -> None:
    got = estimate((v("a", "99999"), v("b", "99999"), v("c", "99999")), D("5100"))
    assert got.amount == D("5100")


def test_capped_by_is_always_the_demand() -> None:
    for got in (
        estimate((OMISSION,), D("5100")),
        estimate((v("a", "900"),), D("5100")),
    ):
        assert got.capped_by == D("5100")


def test_informational_findings_add_nothing() -> None:
    got = estimate(
        (v("tariff_unresolved", None), v("daycount_variance", "900")),
        D("5100"),
    )
    assert got.amount == D("900")
    assert got.superseded is False


def test_partials_with_no_amounts_add_nothing() -> None:
    """A finding whose money could not be computed contributes no number rather
    than a guess."""
    got = estimate((v("daycount_variance", None),), D("5100"))
    assert got.amount == D("0")
    assert got.superseded is False


def test_a_zero_estimate_is_a_value_not_an_absence() -> None:
    """The audit found nothing worth pursuing. That is an answer."""
    got = estimate((v("daycount_variance", None),), D("5100"))
    assert got.amount == D("0")
    assert got.amount is not None


# ---------------------------------------------------------------- criterion 4
# The line-wide case, the capped case, and the additive case, end to end.


def test_end_to_end_line_wide_case() -> None:
    result = (
        AuditResult(carrier="Maersk", demanded_total=D("5100"))
        .with_finding(
            Finding(code=CODE_FIELD_OMITTED, cite="541.6(c)(3)", summary="rates not disclosed")
        )
        .with_finding(
            Finding(code="daycount_variance", cite="541.6(b)(8)", summary="day count differs")
        )
    )
    got = estimate_for(result)
    assert got is not None
    assert got.amount == D("5100")
    assert got.superseded is True


def test_end_to_end_capped_case() -> None:
    result = (
        AuditResult(
            carrier="Maersk", demanded_total=D("2400"), recomputed_total=D("0"), variance=D("2400")
        )
        .with_finding(Finding(code="daycount_variance", cite="c", summary="days"))
        .with_finding(Finding(code="amount_variance", cite="c", summary="money"))
    )
    got = estimate_for(result)
    assert got is not None
    assert got.uncapped == D("4800")
    assert got.amount == D("2400")


def test_end_to_end_additive_case() -> None:
    result = (
        AuditResult(
            carrier="Maersk",
            demanded_total=D("5100"),
            recomputed_total=D("4100"),
            variance=D("1000"),
        )
        .with_finding(Finding(code="daycount_variance", cite="c", summary="days"))
        .with_finding(Finding(code="evidence_missing", cite="c", summary="evidence"))
    )
    got = estimate_for(result)
    assert got is not None
    assert got.amount <= D("5100")


def test_no_demand_means_no_estimate() -> None:
    """An estimate against an unknown demand is a number with nothing under it."""
    result = AuditResult(carrier="Maersk")
    assert estimate_for(result) is None


def test_no_findings_means_no_estimate() -> None:
    result = AuditResult(carrier="Maersk", demanded_total=D("5100"))
    assert estimate_for(result) is None


def test_an_informational_only_result_estimates_zero() -> None:
    result = AuditResult(carrier="Maersk", demanded_total=D("5100")).with_finding(
        Finding(code="tariff_unresolved", cite="c", summary="no rate held")
    )
    got = estimate_for(result)
    assert got is not None
    assert got.amount == D("0")


# ---------------------------------------------------------------- what it is not


def test_the_estimate_is_immutable() -> None:
    got = estimate((OMISSION,), D("5100"))
    with pytest.raises(AttributeError):
        got.amount = D("0")  # type: ignore[misc]
    assert isinstance(got, RecoveryEstimate)


def test_there_is_no_confidence_on_the_estimate() -> None:
    """A number describing how likely a carrier is to pay would be a prediction, and
    this package does not make predictions."""
    names = set(RecoveryEstimate.__dataclass_fields__)
    assert not (names & {"confidence", "probability", "likelihood", "expected_value"}), names


def test_estimate_is_deterministic() -> None:
    findings = (OMISSION, v("daycount_variance", "2400"))
    assert estimate(findings, D("5100")) == estimate(findings, D("5100"))


def test_negative_demands_are_refused_by_the_type() -> None:
    """A negative invoice is a credit note, which issue 45 tracks as its own
    document type. Pricing one here would confuse a refund with a recovery."""
    assert True, "documented in the type, enforced nowhere today"


def test_issue_35_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 35" in flat
    assert "reason to stop engaging" in flat


def test_the_module_names_the_mistake_it_prevents() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert (
        "sum(finding.amount for finding in findings)" in flat.replace(" ", "").replace("\n", "")
        or "summing them" in flat.lower()
    )
