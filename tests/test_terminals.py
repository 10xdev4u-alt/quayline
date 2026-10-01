"""Issue 26: the terminal directory, transcribed where held and holed where not.

The load bearing test is ``test_uslaxb_resolves_to_apm_terminals``. The rest check
the structure around it, and a suite that checks the structure without asserting
that one resolution would pass while the issue's central claim goes untested.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import terminals as module
from quayline.tariffs.terminals import (
    BY_CODE,
    SOURCE_PDF,
    SOURCE_RULES,
    TERMINALS,
    resolve,
    resolve_schedule_reference,
)

# ---------------------------------------------------------------- criterion 1
# Name, operator and website fields, transcribed where held.


def test_five_terminals_transcribed_with_the_right_fields() -> None:
    """Five rows, not thirty. The research names over thirty including these five,
    and the twenty-five are not transcribed anywhere we hold."""
    assert len(TERMINALS) == 5
    for terminal in TERMINALS:
        assert terminal.code
        assert terminal.name
        assert terminal.source_pdf == SOURCE_PDF
        assert hasattr(terminal, "website")


def test_the_source_is_the_evergreen_policy_with_both_rules() -> None:
    assert SOURCE_PDF == "DMDT_Policy_20250115.pdf"
    assert SOURCE_RULES == ("036-I01", "036-E01")


def test_operators_held_where_established_and_empty_where_not() -> None:
    """An invented operator is a guess wearing a directory. Empty is a field
    awaiting a source."""
    assert BY_CODE["USLAXB"].operator == "APM Terminals"
    for code in ("USLGBE", "USSVNG", "USNFKT", "USBALT"):
        assert BY_CODE[code].operator is None, code


def test_resolved_distinguishes_holes_with_names() -> None:
    assert BY_CODE["USLAXB"].resolved is True
    assert BY_CODE["USSVNG"].resolved is False


def test_terminals_are_immutable() -> None:
    with pytest.raises(AttributeError):
        BY_CODE["USLAXB"].operator = "x"  # type: ignore[misc]


def test_by_code_covers_every_row() -> None:
    assert set(BY_CODE) == {t.code for t in TERMINALS}


# ---------------------------------------------------------------- criterion 2
# Location codes searchable by gateway.


def test_known_codes_resolve() -> None:
    for code in ("USLAXB", "USLGBE", "USSVNG", "USNFKT", "USBALT"):
        assert resolve(code) is BY_CODE[code], code


def test_codes_are_case_insensitive() -> None:
    """Gate tickets and invoices vary case, and a directory that only reads one is
    a directory that misses half its lookups."""
    assert resolve("uslaxb") is BY_CODE["USLAXB"]
    assert resolve("Ussvng") is BY_CODE["USSVNG"]


def test_unknown_codes_return_none_not_a_guess() -> None:
    """Twenty-five of thirty terminals are not transcribed. None is the honest
    answer, and a guess would be a terminal, an operator and a website that nobody
    published."""
    assert resolve("USXYZ") is None
    assert resolve("") is None


def test_resolve_is_deterministic() -> None:
    assert resolve("USLAXB") == resolve("USLAXB")


# ---------------------------------------------------------------- criterion 3
# A 541.6(c)(2) terminal-schedule reference resolves to the operator.


def test_a_terminal_schedule_reference_resolves_to_its_operator() -> None:
    """ "Per the published terminal schedule USLAXB" becomes APM Terminals, whose
    schedule it is. That turns a rule reference the registry cannot price into a
    pointer the operator can answer."""
    assert resolve_schedule_reference("per terminal schedule USLAXB") == "APM Terminals"
    assert resolve_schedule_reference("TERMINAL SCHEDULE USSVNG") is None, (
        "Savannah's operator is not established, so there is nobody to point at"
    )


def test_a_reference_with_no_code_resolves_to_nothing() -> None:
    """A reference nobody can resolve is a reference, not a rate."""
    assert resolve_schedule_reference("per the applicable tariff") is None
    assert resolve_schedule_reference("") is None


def test_an_unmapped_code_in_a_reference_resolves_to_nothing() -> None:
    assert resolve_schedule_reference("per terminal schedule USXYZ") is None


# ---------------------------------------------------------------- criterion 4
# USLAXB resolves to APM Terminals.


def test_uslaxb_resolves_to_apm_terminals() -> None:
    """The criterion's case. Los Angeles APMT is APM Terminals' own designation,
    via the Hapag gateway table naming "Los Angeles APMT, USLAXB"."""
    terminal = resolve("USLAXB")
    assert terminal is not None
    assert terminal.operator == "APM Terminals"
    assert terminal.name == "Los Angeles APMT"


def test_the_directory_is_carrier_published_not_compiled() -> None:
    """A compiled list is somebody's opinion about somebody else's infrastructure.
    A carrier-published directory is citable, which is the difference between
    evidence and assertion."""
    flat = " ".join((module.__doc__ or "").split())
    assert "citable" in flat
    assert "carrier-published" in flat


def test_issue_26_is_the_provenance() -> None:
    assert "Issue 26" in (module.__doc__ or "")


def test_the_module_states_what_is_not_transcribed() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "twenty-five do not" in flat or "twenty-five" in flat
