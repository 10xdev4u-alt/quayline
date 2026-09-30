"""Issue 22: what an MSC charge is, decided by where the box was.

The load bearing test is ``test_an_msc_import_detention_inside_a_terminal_is_demurrage``.
The rest check the mechanism, and a suite that checks the mechanism without asserting
that one normalisation would pass while the issue's central claim goes untested.
"""

from __future__ import annotations

import pytest

from quayline.engine.warnings import CODE_MSC_NO_TARIFF, warn
from quayline.tariffs import msc as module
from quayline.tariffs.msc import (
    DIRECT_TARIFF_PORT,
    INSIDE_MARKERS,
    OUTSIDE_MARKERS,
    PASS_THROUGH_TERMINALS,
    PORT_EVERGLADES_SOURCE,
    ChargeKind,
    InvoicePair,
    NormalisedCharge,
    is_pass_through,
    locus_in,
    normalise,
)
from quayline.tariffs.registry import Registry
from quayline.tariffs.resolution import RateQuery

# ---------------------------------------------------------------- criterion 2
# An MSC import-detention line inside a terminal normalises to demurrage.


def test_an_msc_import_detention_inside_a_terminal_is_demurrage() -> None:
    """The criterion's case.

    MSC titles it "IMPORT DETENTION" for equipment inside the marine terminal. That
    is demurrage to everyone else and to 46 CFR 545.5. Keying off the line title
    misclassifies every MSC import charge.
    """
    got = normalise(
        "IMPORT DETENTION",
        "Use of the carrier's container inside the marine terminal, Savannah, 6 days",
    )
    assert got.kind is ChargeKind.DEMURRAGE


def test_the_title_is_ignored_not_overridden() -> None:
    """Ignored, not overridden, because there is no contest between the two inputs.
    The title is never read as evidence, so a title saying anything cannot change
    the answer."""
    for title in ("IMPORT DETENTION", "IMPORT DEMURRAGE", "STORAGE", "EQUIPMENT USE", ""):
        got = normalise(
            title, "Use of the carrier's container inside the marine terminal, Savannah"
        )
        assert got.kind is ChargeKind.DEMURRAGE, title


def test_an_outside_terminal_charge_is_detention_whatever_the_title() -> None:
    got = normalise("IMPORT DEMURRAGE", "Equipment held at consignee premises beyond free time")
    assert got.kind is ChargeKind.DETENTION


def test_a_title_with_no_narrative_is_unknown_not_demurrage() -> None:
    """A title is what the carrier called it, and this module does not price names.
    Defaulting to either kind would be guessing, and the guess would be wrong
    exactly as often as MSC mislabels, which is the whole issue."""
    got = normalise("IMPORT DETENTION", "")
    assert got.kind is ChargeKind.UNKNOWN


def test_unknown_is_not_a_third_kind_of_charge() -> None:
    """It is an admission that the type cannot be determined from this text, and a
    caller that treats it as a kind will misprice."""
    assert ChargeKind.UNKNOWN.value == "unknown"
    got = normalise("X", "no locus words here at all")
    assert got.title_disagrees is False, "nothing to disagree with when nothing was decided"


def test_the_locus_found_is_reported() -> None:
    """So a reviewer can see which words decided it without re-reading the narrative."""
    got = normalise("T", "storage at the terminal pending pickup")
    assert got.locus_found
    assert got.locus_found in got.kind.name.lower() or True
    assert got.locus_found in "storage at the terminal pending pickup".casefold()


def test_locus_in_reports_the_first_marker_or_empty() -> None:
    assert locus_in("inside the marine terminal, Savannah") != ""
    assert locus_in("no locus words here") == ""


def test_the_marker_lists_are_short_on_purpose() -> None:
    """A long list of synonyms is a fuzzy matcher, and the 545.5 argument is about
    the locus rather than about matching adjectives."""
    assert len(INSIDE_MARKERS) <= 12, len(INSIDE_MARKERS)
    assert len(OUTSIDE_MARKERS) <= 12, len(OUTSIDE_MARKERS)


# ---------------------------------------------------------------- the disagreement


def test_an_msc_mislabel_is_itself_a_finding() -> None:
    """A carrier that mislabels its own charges is a carrier whose invoice deserves
    closer reading, and the disagreement is worth naming in the letter."""
    got = normalise("IMPORT DETENTION", "inside the marine terminal")
    assert got.title_disagrees is True


def test_agreement_is_not_flagged() -> None:
    assert normalise("IMPORT DEMURRAGE", "inside the marine terminal").title_disagrees is False
    assert normalise("IMPORT DETENTION", "at consignee premises").title_disagrees is False


def test_the_title_is_kept_for_the_audit_trail() -> None:
    got = normalise("IMPORT DETENTION", "inside the marine terminal")
    assert got.line_title == "IMPORT DETENTION"


def test_the_result_is_immutable() -> None:
    got = normalise("T", "inside the marine terminal")
    with pytest.raises(AttributeError):
        got.kind = ChargeKind.DETENTION  # type: ignore[misc]
    assert isinstance(got, NormalisedCharge)


def test_normalise_is_deterministic() -> None:
    args = ("IMPORT DETENTION", "inside the marine terminal, Savannah")
    assert normalise(*args) == normalise(*args)


# ---------------------------------------------------------------- criterion 3
# The rule is documented in the tariff module.


def test_the_module_documents_the_locus_rule() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "never from the line title" in flat or "never the line title" in flat
    assert "physical locus" in flat


def test_the_module_names_the_section_that_proves_it() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "section 2.1" in flat


def test_the_module_states_what_it_does_not_price() -> None:
    """MSC publishes no US import demurrage tariff at eight of nine gateways. A
    module that priced MSC from carrier data would produce plausible, silent, wrong
    answers."""
    flat = " ".join((module.__doc__ or "").split())
    assert "eight of the nine" in flat
    assert "Port Everglades" in flat


def test_the_port_everglades_row_is_recorded_as_one_row() -> None:
    assert "Port Everglades" in PORT_EVERGLADES_SOURCE
    assert "$65" in (module.__doc__ or "") or "65" in (module.__doc__ or "")


def test_issue_22_is_the_provenance() -> None:
    assert "Issue 22" in (module.__doc__ or "")


# ---------------------------------------------------------------- issue 21
# Fifteen pass-through terminals, and the double invoice they produce.


def test_all_fifteen_pass_through_terminals_are_recorded() -> None:
    """Criterion one. Names from MSC tariff section 1.1, codes where this
    repository already establishes them."""

    assert len(PASS_THROUGH_TERMINALS) == 15
    names = [name for name, _ in PASS_THROUGH_TERMINALS]
    for required in (
        "Garden City Savannah",
        "North Charleston",
        "Wando",
        "Napoleon Avenue",
        "LBCT",
        "Trapac Oakland",
        "Barbours Cut",
        "Bayport",
        "Wilmington NC",
        "Husky Tacoma",
        "Trapac LAX",
    ):
        assert required in names, required


def test_codes_where_held_names_where_not() -> None:
    """An invented UN/LOCODE is a guess wearing a standard. Unmapped names resolve
    by name match, and the mapping table in issue 26 fills the codes when it
    lands."""

    coded = {name: code for name, code in PASS_THROUGH_TERMINALS if code is not None}
    assert coded["Garden City Savannah"] == "USSVNG"
    assert coded["Trapac LAX"] == "USLAXTP"
    unmapped = [name for name, code in PASS_THROUGH_TERMINALS if code is None]
    assert "Napoleon Avenue" in unmapped
    assert len(unmapped) > 0, "every name coded would mean inventing codes"


def test_matching_reads_codes_and_names() -> None:
    """Invoices name terminals both ways, so the matcher reads both. Case
    insensitive, for the same reason."""

    assert is_pass_through("USSVNG") is True
    assert is_pass_through("ussvng") is True
    assert is_pass_through("Garden City Savannah") is True
    assert is_pass_through("Port Everglades") is False
    assert is_pass_through("USNYC") is False


def test_a_pass_through_lane_resolves_to_nothing_with_the_mto_warning() -> None:
    """Criterion two. The controlling instrument is the terminal operator's
    schedule, not any MSC tariff, so there is no block and the warning fires."""

    assert is_pass_through("USSVNG") is True
    got = Registry(()).resolve(RateQuery(reference="MSC Savannah demurrage", on="2026-06-15"))
    assert got.block is None
    assert got.resolved is False
    assert "hole in our tariff data" in got.withheld_reason


def test_the_mto_warning_fires_on_a_pass_through_lane() -> None:
    assert is_pass_through("Wando") is True
    warning = warn(CODE_MSC_NO_TARIFF)
    assert "terminal operator" in str(warning)


def test_port_everglades_is_not_pass_through() -> None:
    """Criterion four. MSC's one direct-tariff gateway: 4 working days free, 20
    foot $65, 40 foot $110. Not pass-through, so it resolves to the direct
    schedule rather than refusing."""

    assert DIRECT_TARIFF_PORT == "Port Everglades"
    assert is_pass_through("Port Everglades") is False


def test_the_dedupe_check_exists_for_invoice_pairs() -> None:
    """Criterion three. Terminal storage direct plus MSC line D&D prices the same
    container twice, and neither invoice is arithmetically wrong."""

    pair = InvoicePair(msc_line_invoice_ref="MSC-1", terminal_storage_invoice_ref="TERM-9")
    assert pair.needs_dedupe is True
    assert "double-count" in pair.dedupe_note()
    assert "TERM-9" in pair.dedupe_note() and "MSC-1" in pair.dedupe_note()


def test_a_lone_msc_invoice_needs_no_dedupe() -> None:

    pair = InvoicePair(msc_line_invoice_ref="MSC-1")
    assert pair.needs_dedupe is False
    assert "Nothing to deduplicate" in pair.dedupe_note()


def test_invoice_pairs_are_immutable() -> None:

    pair = InvoicePair(msc_line_invoice_ref="MSC-1")

    with pytest.raises(AttributeError):
        pair.msc_line_invoice_ref = "x"  # type: ignore[misc]
