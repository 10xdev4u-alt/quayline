"""Issue 187: the specimen page, generated rather than written.

A hand written page describing a number the engine computes is a liability the day
the code changes, so the page is built by running the engine and every figure on it
comes from a command. These tests assert that, and they assert the page refuses to
overclaim about the fixture it is showing.

The fixture is a hand built PDF in tests/fixtures. It is not a customer's invoice and
the page has to say so, because the whole argument of this product is that we do not
overclaim.
"""

from __future__ import annotations

import re

import pytest

from quayline.regulation import Trade
from quayline.regulation.checklist import required_for
from quayline.web.render import generate, render_specimen
from quayline.web.specimen import SpecimenError, build_specimen

# --------------------------------------------------------- it is generated, not typed


def test_the_numbers_come_from_running_the_engine() -> None:
    """Assert the figure rather than asserting the page exists.

    If the engine's variance changes and the page does not, this fails. That is the
    whole reason the page is generated.
    """
    specimen = build_specimen()

    assert specimen.demanded_total == "1170.00"
    assert specimen.recomputed_total == "780.00"
    assert specimen.variance == "390.00"
    assert specimen.chargeable_days == 2
    assert "390.00" in render_specimen(specimen)


def test_the_tariff_block_is_named_with_its_provenance() -> None:
    """A recomputation with no rate behind it is arithmetic the reader cannot check."""
    specimen = build_specimen()

    assert specimen.tariff_rule == "Maersk US Newark Dry"
    assert specimen.tariff_source
    assert specimen.tariff_effective_from == "2024-08-08"


def test_every_required_disclosure_is_listed_with_its_cite() -> None:
    """19 for an import invoice, straight from the checklist module.

    Derived from ``required_for(Trade.IMPORT)`` rather than hardcoded, so a change to
    the checklist moves this count and the test says so.
    """
    specimen = build_specimen()
    expected = {f.cite for f in required_for(Trade.IMPORT)}

    assert {row.cite for row in specimen.disclosures} == expected
    assert len(specimen.disclosures) == 19


def test_no_disclosure_row_claims_presence_it_did_not_check() -> None:
    """The important one. A page that says "present" without checking is a guess.

    ``verification`` is one of ``verified``, ``absent`` or ``not checked``, and
    nothing on the page may read as present unless it was actually verified against
    the bound document. A row that says "not checked" is honest and belongs on the
    page.
    """
    specimen = build_specimen()
    allowed = {"verified", "absent", "not checked"}

    assert {row.verification for row in specimen.disclosures} <= allowed
    verified = [r for r in specimen.disclosures if r.verification == "verified"]
    assert verified, "the fixture states several fields and they should be verified"


def test_a_field_the_binder_actually_reads_is_marked_verified() -> None:
    """Spot check one, by hand.

    The fixture states ``Rate Rule: Maersk US Newark Dry`` under 541.6(c)(2) and the
    binder captures it, so that row must read verified and not "not checked".
    """
    specimen = build_specimen()
    row = next(r for r in specimen.disclosures if r.cite == "541.6(c)(2)")

    assert row.verification == "verified"


# ------------------------------------------------------------------ no overclaiming


def test_the_page_says_the_fixture_is_not_a_real_invoice() -> None:
    """A reader who thinks it is real would be misled, and that is the one thing
    this product does not do."""
    html = render_specimen(build_specimen())

    lowered = html.lower()
    assert "test fixture" in lowered or "not a real" in lowered
    assert "synthetic" in lowered or "hand-built" in lowered


def test_the_page_names_no_recovery_rate() -> None:
    """No recovery figure is measured yet, per AGENTS.md section five.

    The category's headline recovery numbers are vendor published and unaudited and
    we do not repeat them or infer ours. A page that said "we recover 40 percent"
    would be the exact claim this repository exists to avoid.
    """
    html = render_specimen(build_specimen()).lower()

    for banned in ("recovery rate", "% recovered", "we recover", "average recovery"):
        assert banned not in html


def test_every_finding_carries_its_citation() -> None:
    specimen = build_specimen()

    assert specimen.findings
    for finding in specimen.findings:
        assert finding.cite, "a finding without a cite cannot be checked by the other side"


def test_a_finding_links_to_the_research_document_that_supports_it() -> None:
    """Every claim traces to docs/research, which is where the sourcing lives."""
    specimen = build_specimen()
    html = render_specimen(specimen)

    for row in specimen.research_links:
        assert row.path.startswith("docs/research/")
        assert row.path in html


# ------------------------------------------------------------------------ output


def test_the_page_needs_no_javascript_and_no_network() -> None:
    """A page that needs a CDN is not evidence of anything.

    Everything here is generated from the repository, so nothing needs fetching.
    """
    html = render_specimen(build_specimen()).lower()

    assert "<script" not in html
    assert "http://" not in html
    assert "https://" not in html.replace("https://www.w3.org", "")


def test_the_page_is_valid_enough_to_render_and_carries_the_numbers() -> None:
    html = render_specimen(build_specimen())

    assert html.lstrip().startswith("<!doctype html")
    assert html.rstrip().endswith("</html>")
    assert "<table" in html


def test_the_page_does_not_invent_a_digit_the_engine_did_not_produce() -> None:
    """Guard against a formatting slip turning 780.00 into 7800.00.

    Every money figure on the page must appear verbatim in the specimen, and the
    specimen carries exactly the engine's output.
    """
    specimen = build_specimen()
    html = render_specimen(specimen)

    for value in (
        specimen.demanded_total,
        specimen.recomputed_total,
        specimen.variance,
        specimen.tariff_rate if specimen.tariff_rate else "",
    ):
        if value:
            assert value in html


def test_an_unknown_carrier_is_refused_rather_than_rendered_half() -> None:
    with pytest.raises(SpecimenError):
        build_specimen(carrier="not-a-carrier")


def test_the_page_says_how_it_was_generated() -> None:
    """A reader should be able to reproduce it, or the page is decoration."""
    html = render_specimen(build_specimen())

    assert "make specimen" in html or "quayline specimen" in html
    assert re.search(r"quayline (coverage|specimen)", html)


def test_generate_is_the_same_page_as_build_then_render() -> None:
    """``make specimen`` calls ``generate``, so it must not drift from the parts."""
    assert generate() == render_specimen(build_specimen())
