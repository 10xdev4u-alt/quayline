"""Issue 37: the engine saying what it does not know, in a form a machine can read.

The test that matters most is ``test_warnings_do_not_affect_finding_ordering``. A
warning that changed a claim's position would be a presentation control wearing a
diagnostic's clothes, and the ordering in issue 34 is the thing most worth keeping
stable.
"""

from __future__ import annotations

from datetime import date

import pytest

import quayline.engine.warnings as module
from quayline.engine.ordering import order_findings
from quayline.engine.result import CODE_FIELD_OMITTED, AuditResult, Finding
from quayline.engine.warnings import (
    CODE_CLOSURE_INFERRED,
    CODE_HAPAG_HAULAGE_REQUIRED,
    CODE_MAERSK_DETENTION_UNVERIFIED,
    CODE_MSC_DOUBLE_INVOICE,
    CODE_MSC_NO_TARIFF,
    CODE_ONE_NO_STATIC_TABLE,
    CODE_SHALLOW_EXTRACTION,
    CODE_TARIFF_NOT_HELD,
    LIMITS,
    ModelLimit,
    Severity,
    Warning,
    coverage_gaps,
    limits_for,
    warn,
)
from quayline.evidence.checklist import Ground

DAYS = (date(2026, 7, 8), date(2026, 7, 9))


# ---------------------------------------------------------------- criterion 1
# Warnings are typed and carry a severity.


def test_every_catalogued_limit_has_a_code_and_a_severity() -> None:
    for code, limit in LIMITS.items():
        assert limit.code == code, "the dict key and the record must agree"
        assert isinstance(limit.severity, Severity), code


def test_severity_answers_one_question() -> None:
    """How much should this narrow what may be concluded. Not whether to file."""
    assert {s.value for s in Severity} == {"notice", "caveat", "limit"}


def test_every_limit_tells_the_operator_what_to_do() -> None:
    """A limit with no remedy is a dead end, and dead ends are why people stop
    reading warnings."""
    for code, limit in LIMITS.items():
        assert len(limit.remedy) > 20, code
        assert limit.message, code


def test_warnings_are_typed_not_strings() -> None:
    """The whole point of the issue. A string cannot be filtered or counted."""
    w = warn(CODE_TARIFF_NOT_HELD)
    assert isinstance(w, Warning)
    assert isinstance(w.severity, Severity)
    assert isinstance(w.limit, ModelLimit)
    assert w.code == CODE_TARIFF_NOT_HELD


def test_firing_an_uncatalogued_code_raises() -> None:
    """So adding a limit is a diff somebody reviews.

    The alternative is a string in a module somewhere, which is the state issue 37
    was opened to end.
    """
    with pytest.raises(KeyError, match="not catalogued"):
        warn("some_limit_nobody_wrote_down")


def test_a_carrierless_limit_applies_to_everyone() -> None:
    """An incomplete text layer is not carrier specific."""
    shallow = LIMITS[CODE_SHALLOW_EXTRACTION]
    assert shallow.carriers == frozenset()
    for carrier in ("MSC", "ONE", "Maersk", "Hapag-Lloyd", "ZIM"):
        assert shallow.applies_to(carrier) is True


def test_a_carrier_limit_does_not_leak_to_others() -> None:
    assert LIMITS[CODE_MSC_NO_TARIFF].applies_to("MSC") is True
    assert LIMITS[CODE_MSC_NO_TARIFF].applies_to("Maersk") is False


def test_limits_for_ranks_the_most_severe_first() -> None:
    """An operator reads the first one and stops, so the LIMIT has to be first."""
    severities = [lim.severity for lim in limits_for("MSC")]
    rank = {Severity.LIMIT: 0, Severity.CAVEAT: 1, Severity.NOTICE: 2}
    assert severities == sorted(severities, key=lambda s: rank[s])


def test_the_catalogue_is_the_full_answer_to_what_we_do_not_know() -> None:
    """Issue 84 renders this and issue 83 works from it. One function of one dict, so
    it cannot drift from the catalogue."""
    assert len(coverage_gaps()) == len(LIMITS)


def test_coverage_gaps_is_deterministic() -> None:
    assert coverage_gaps() == coverage_gaps()


# ---------------------------------------------------------------- criterion 2
# An MSC audit emits the pass-through and double-invoice warning.


def test_msc_emits_the_pass_through_warning() -> None:
    codes = {lim.code for lim in limits_for("MSC")}
    assert CODE_MSC_NO_TARIFF in codes


def test_msc_emits_the_double_invoice_warning() -> None:
    codes = {lim.code for lim in limits_for("MSC")}
    assert CODE_MSC_DOUBLE_INVOICE in codes


def test_both_msc_limits_are_a_limit_not_a_caveat() -> None:
    """An MSC pass-through audit is not a weak audit of MSC. It is an audit of a
    document whose controlling instrument is somebody else's schedule, and calling
    that a caveat invites a reader to treat a number as narrower-but-usable."""
    for code in (CODE_MSC_NO_TARIFF, CODE_MSC_DOUBLE_INVOICE):
        assert LIMITS[code].severity is Severity.LIMIT, code


def test_the_pass_through_warning_says_who_controls_the_instrument() -> None:
    """Otherwise the operator does not know what to go and get."""
    assert "terminal operator" in LIMITS[CODE_MSC_NO_TARIFF].message
    assert "terminal operator" in LIMITS[CODE_MSC_NO_TARIFF].remedy


def test_the_double_invoice_warning_says_neither_invoice_is_wrong() -> None:
    """Because that is what makes it hard, and the message has to carry it."""
    assert "twice" in LIMITS[CODE_MSC_DOUBLE_INVOICE].message


# ---------------------------------------------------------------- criterion 3
# A Hapag detention audit without haulage mode emits the missing-input warning.


def test_hapag_detention_without_haulage_mode_warns() -> None:
    w = warn(CODE_HAPAG_HAULAGE_REQUIRED, "the query carried no freight term")
    assert w.code == CODE_HAPAG_HAULAGE_REQUIRED
    assert w.severity is Severity.CAVEAT


def test_the_hapag_warning_names_the_document_the_answer_is_in() -> None:
    """The remedy is one step: read the checkbox. A warning that says "insufficient
    input" is actionable by nobody."""
    assert "bill of lading" in LIMITS[CODE_HAPAG_HAULAGE_REQUIRED].remedy
    assert "haulage mode" in LIMITS[CODE_HAPAG_HAULAGE_REQUIRED].message


def test_the_hapag_warning_is_a_caveat_not_a_limit() -> None:
    """A figure computed for one mode is a true statement about a case the operator
    has not established applies. That is narrower, not absent."""
    assert LIMITS[CODE_HAPAG_HAULAGE_REQUIRED].severity is Severity.CAVEAT


def test_the_detail_travels_with_the_warning() -> None:
    w = warn(CODE_HAPAG_HAULAGE_REQUIRED, "the query carried no freight term")
    assert "freight term" in str(w)


# ---------------------------------------------------------------- criterion 4
# Warnings do not affect finding ordering.


def test_warnings_do_not_affect_finding_ordering() -> None:
    """A warning that moved a claim would be a presentation control in a
    diagnostic's clothes."""
    result = (
        AuditResult(carrier="MSC")
        .with_finding(Finding(code=CODE_FIELD_OMITTED, cite="c", summary="void"))
        .with_finding(Finding(code="amount_variance", cite="c", summary="money", days=DAYS))
    )
    with_warnings = AuditResult(
        carrier="MSC",
        findings=result.findings,
        warnings=(str(warn(CODE_MSC_NO_TARIFF)), str(warn(CODE_MSC_DOUBLE_INVOICE))),
    )
    assert [o.code for o in order_findings(result)] == [
        o.code for o in order_findings(with_warnings)
    ]


def test_a_warning_never_blocks_a_filing() -> None:
    """Otherwise a model limit becomes a gate nobody reviewed. Filing is
    ``can_file``, decided by findings, and only findings."""
    result = AuditResult(carrier="MSC").with_finding(
        Finding(code=CODE_FIELD_OMITTED, cite="c", summary="void")
    )
    assert result.can_file is False
    assert warn(CODE_MSC_NO_TARIFF).severity is Severity.LIMIT
    assert not hasattr(warn(CODE_MSC_NO_TARIFF), "blocks")
    assert not hasattr(Severity, "BLOCKS")


def test_no_severity_value_implies_a_filing_disposition() -> None:
    """The names are about trust. If one of them were called "blocking" the type
    would be a gate wearing a diagnostic."""
    for severity in Severity:
        assert "block" not in severity.name.casefold()
        assert "file" not in severity.name.casefold()


def test_a_warning_is_not_a_finding() -> None:
    """A finding is a claim about a carrier. A warning is a claim about us, and
    conflating them puts a statement about our own coverage in a letter addressed to
    a carrier as though it were an accusation."""
    # isinstance is rejected by mypy as unreachable, because the two types have
    # disjoint bases, and that rejection is the proof rather than a nuisance. What
    # carries the meaning is the shape: a Warning has no cite it can put in a letter
    # and no method that claims a ground, because it is a claim about us.
    w = warn(CODE_MSC_NO_TARIFF)
    assert not hasattr(w, "cite_541")
    assert not hasattr(w, "grounds_claimed")
    assert not hasattr(w, "on_ground")
    assert not hasattr(w, "summary")


def test_a_warning_can_carry_a_ground_without_claiming_one() -> None:
    """It can be filed under a ground for grouping, which is not the same as being
    a claim on that ground.
    """
    w = warn(CODE_CLOSURE_INFERRED, grounds=(Ground.CONTRACT_CONDITION,))
    assert w.grounds == (Ground.CONTRACT_CONDITION,)
    assert not hasattr(w, "on_ground")


# ---------------------------------------------------------------- the shape


def test_a_warning_is_immutable() -> None:
    with pytest.raises(AttributeError):
        warn(CODE_TARIFF_NOT_HELD).detail = "x"  # type: ignore[misc]


def test_the_catalogue_holds_one_limit_many_warnings() -> None:
    """One limit, many invoices. A report needs both, and a single type would have to
    be one or the other."""
    a = warn(CODE_MSC_NO_TARIFF, "lane A")
    b = warn(CODE_MSC_NO_TARIFF, "lane B")
    assert a.limit is b.limit
    assert a.detail != b.detail


def test_a_warning_renders_readably() -> None:
    text = str(warn(CODE_TARIFF_NOT_HELD))
    assert text.startswith("[limit]")
    assert len(text) > 40


def test_every_limit_the_issue_named_is_catalogued() -> None:
    """The three examples in the issue's evidence section, by code."""
    for code in (
        CODE_MSC_NO_TARIFF,
        CODE_MSC_DOUBLE_INVOICE,
        CODE_HAPAG_HAULAGE_REQUIRED,
        CODE_MAERSK_DETENTION_UNVERIFIED,
        CODE_ONE_NO_STATIC_TABLE,
    ):
        assert code in LIMITS, code


def test_the_maersk_limit_is_a_limit_not_a_caveat() -> None:
    """We hold a Maersk detention block and could not transcribe it confidently, so
    nothing may be quoted. That is absent coverage, not narrow coverage."""
    assert LIMITS[CODE_MAERSK_DETENTION_UNVERIFIED].severity is Severity.LIMIT
    assert "may be quoted" in LIMITS[CODE_MAERSK_DETENTION_UNVERIFIED].message


def test_issue_37_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 37" in flat
    assert "quoted at a carrier" in flat


def test_the_module_says_why_a_string_was_not_enough() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "cannot be filtered" in flat
    assert "coverage report" in flat
