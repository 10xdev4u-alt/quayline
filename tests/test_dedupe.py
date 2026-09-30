"""Issue 36: two views of the same dollars, priced once.

The load bearing test is ``test_the_reported_recovery_equals_the_variance_not_the_sum``.
The demotion is only worth anything if the number at the end is the arithmetic
variance, and a test that checks the demotion happened without checking the number
is a test that the mechanism exists rather than that it works.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import quayline.engine.dedupe as module
from quayline.engine.dedupe import (
    DEMOTION_NOTE,
    DIAGNOSTIC_SUFFIX,
    demote_daycount,
    is_diagnostic,
    original_code,
)
from quayline.engine.recovery import ClaimBasis, _money_for, basis_of, estimate
from quayline.engine.recovery import ValuedFinding as Valued
from quayline.engine.result import (
    CODE_AMOUNT_VARIANCE,
    CODE_DAYCOUNT_VARIANCE,
    CODE_FIELD_OMITTED,
    AuditResult,
    Finding,
)

D = Decimal
DAYS = (date(2026, 7, 8), date(2026, 7, 9))


def finding(code: str = CODE_DAYCOUNT_VARIANCE, detail: str = "the day count differs") -> Finding:
    return Finding(code=code, cite="541.6(b)(8)", summary="days", detail=detail, days=DAYS)


def valued(code: str, amount: str | None) -> Valued:
    return Valued(code=code, amount=D(amount) if amount is not None else None)


# ---------------------------------------------------------------- criterion 1
# When a recomputed total exists, the day-count finding drops to informational.


def test_a_resolved_tariff_demotes_the_day_count_finding() -> None:
    (demoted,) = demote_daycount((finding(),), tariff_resolved=True)
    assert demoted.code == CODE_DAYCOUNT_VARIANCE + DIAGNOSTIC_SUFFIX
    assert is_diagnostic(demoted) is True
    assert basis_of(demoted.code) is ClaimBasis.INFORMATIONAL


def test_an_unresolved_tariff_leaves_everything_untouched() -> None:
    """Without a recomputed total the day count is the only priced view, so it
    keeps its money."""
    original = (finding(), finding(CODE_AMOUNT_VARIANCE))
    assert demote_daycount(original, tariff_resolved=False) == original


def test_only_day_count_is_demoted() -> None:
    """Arithmetic, omissions and everything else pass through. Demotion is about one
    specific overlap, not a general rewriting pass."""
    findings = (
        finding(CODE_AMOUNT_VARIANCE),
        finding(CODE_FIELD_OMITTED),
        finding("tariff_unresolved"),
        finding("brand_new"),
    )
    demoted = demote_daycount(findings, tariff_resolved=True)
    assert [f.code for f in demoted] == [f.code for f in findings]


def test_demotion_preserves_order_and_identity() -> None:
    pair = (finding(CODE_AMOUNT_VARIANCE), finding())
    demoted = demote_daycount(pair, tariff_resolved=True)
    assert [f.summary for f in demoted] == [f.summary for f in pair]
    assert [f.cite for f in demoted] == [f.cite for f in pair]
    assert [f.days for f in demoted] == [f.days for f in pair]


def test_the_input_tuple_is_not_mutated() -> None:
    original = (finding(),)
    demote_daycount(original, tariff_resolved=True)
    assert original[0].code == CODE_DAYCOUNT_VARIANCE


# ---------------------------------------------------------------- criterion 2
# A note on the demoted finding explains why.


def test_the_demoted_finding_names_the_reason() -> None:
    (demoted,) = demote_daycount((finding(),), tariff_resolved=True)
    assert demoted.detail.startswith(DEMOTION_NOTE)
    assert "the day count differs" in demoted.detail, "the original detail is kept"
    assert "authoritative" in demoted.detail


def test_the_note_is_one_constant_not_assembled_per_call() -> None:
    """Every demoted finding says the same thing, so the wording is reviewable in
    one place rather than constructed at six call sites."""
    assert "authoritative" in DEMOTION_NOTE
    assert "remains in the audit" in DEMOTION_NOTE
    assert "carries no money" in DEMOTION_NOTE


# ---------------------------------------------------------------- criterion 3
# The reported recovery equals the arithmetic variance, not the sum.


def test_the_reported_recovery_equals_the_variance_not_the_sum() -> None:
    """The criterion, end to end.

    Day count at 2400 and arithmetic at 2400, tariff resolved. Naive summation prices
    4800. The reported recovery is 2400.
    """
    result = AuditResult(
        carrier="Maersk", demanded_total=D("5100"), recomputed_total=D("2700"), variance=D("2400")
    )
    demoted = demote_daycount((finding(), finding(CODE_AMOUNT_VARIANCE)), tariff_resolved=True)
    valued_findings = tuple(Valued(code=f.code, amount=_money_for(f.code, result)) for f in demoted)
    got = estimate(valued_findings, D("5100"))
    assert got.uncapped == D("2400"), "only the arithmetic variance counts"
    assert got.amount == D("2400")


def test_a_demoted_finding_contributes_no_money() -> None:
    result = AuditResult(
        carrier="M", demanded_total=D("5100"), recomputed_total=D("2700"), variance=D("2400")
    )
    (demoted,) = demote_daycount((finding(),), tariff_resolved=True)
    assert _money_for(demoted.code, result) is None


def test_an_undemoted_day_count_still_prices() -> None:
    """The other half of the same property. Demotion is conditional, so without it
    the money is there."""
    result = AuditResult(
        carrier="M", demanded_total=D("5100"), recomputed_total=D("2700"), variance=D("2400")
    )
    assert _money_for(CODE_DAYCOUNT_VARIANCE, result) == D("2400")


# ---------------------------------------------------------------- the mechanism


def test_original_code_recovers_the_pre_demotion_code() -> None:
    (demoted,) = demote_daycount((finding(),), tariff_resolved=True)
    assert original_code(demoted) == CODE_DAYCOUNT_VARIANCE
    assert original_code(finding()) == CODE_DAYCOUNT_VARIANCE


def test_a_caller_filtering_on_the_original_code_still_matches() -> None:
    """Prefix matching, so the audit trail is continuous across the demotion."""
    (demoted,) = demote_daycount((finding(),), tariff_resolved=True)
    assert demoted.code.startswith(original_code(demoted))


def test_is_diagnostic_is_false_for_a_normal_finding() -> None:
    assert is_diagnostic(finding()) is False
    assert is_diagnostic(finding(CODE_AMOUNT_VARIANCE)) is False


def test_the_suffix_is_one_string_in_one_place() -> None:
    assert DIAGNOSTIC_SUFFIX == "_diagnostic"
    assert "DIAGNOSTIC_SUFFIX" in module.__all__


def test_demotion_is_deterministic() -> None:
    findings = (finding(), finding(CODE_AMOUNT_VARIANCE))
    assert demote_daycount(findings, tariff_resolved=True) == demote_daycount(
        findings, tariff_resolved=True
    )


def test_issue_36_is_the_provenance() -> None:
    assert "Issue 36" in (module.__doc__ or "")


def test_the_module_names_both_views_of_the_dollars() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "days times rate" in flat
    assert "demanded minus recomputed" in flat
