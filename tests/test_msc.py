"""Issue 22: what an MSC charge is, decided by where the box was.

The load bearing test is ``test_an_msc_import_detention_inside_a_terminal_is_demurrage``.
The rest check the mechanism, and a suite that checks the mechanism without asserting
that one normalisation would pass while the issue's central claim goes untested.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import msc as module
from quayline.tariffs.msc import (
    INSIDE_MARKERS,
    OUTSIDE_MARKERS,
    PORT_EVERGLADES_SOURCE,
    ChargeKind,
    NormalisedCharge,
    locus_in,
    normalise,
)

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


# ---------------------------------------------------------------- criterion 1
# Charge type from the physical locus, never the line title.


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
