"""The four acceptance criteria on issue 2, one test block each.

The failure this guards against is silent. A check that keys on a vacated section
produces reasoning that still reads correctly, and only the citation is dead.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path

import pytest

from quayline.regulation.checklist import CHECKLIST, by_cite
from quayline.regulation.kill_switch import Obligation, Omission, effect_of
from quayline.regulation.vacatur import (
    LIABILITY_BASIS_CITE,
    STATUTE_41104_F,
    VACATED_SECTION,
    VACATUR_CITATION,
    VACATUR_REMOVAL,
    WORLD_SHIPPING_COUNCIL_5414,
    WORLD_SHIPPING_COUNCIL_5421,
    VacatedRuleError,
    case_for,
    check_liability_basis,
    refuses_vacated_basis,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "quayline"
LIABILITY_FIELD = "The basis for why the billed party is the proper party of interest"


# ---------------------------------------------------------------- criterion 1
# No check cites 541.4 as a basis for non-payability.


def test_asking_for_a_541_4_finding_always_raises() -> None:
    with pytest.raises(VacatedRuleError) as excinfo:
        refuses_vacated_basis()
    message = str(excinfo.value)
    assert VACATUR_CITATION in message
    assert VACATUR_REMOVAL in message
    assert LIABILITY_BASIS_CITE in message, "the error must point at the hook that survives"


def test_the_vacated_section_is_not_in_the_checklist() -> None:
    """541.4 is [Reserved] in the eCFR as of 2026-09-24, so it is not a required
    minimum and cannot be a 541.5 event through the checklist path either."""
    assert not any(f.cite.startswith("541.4") for f in CHECKLIST)
    assert by_cite("541.6(a)(4)").text.startswith(LIABILITY_FIELD)


def test_no_module_under_src_cites_541_4_as_a_basis_for_non_payability() -> None:
    """Scanned rather than asserted, because the hazard is a citation appearing in
    a file someone has not read.

    Two kinds of mention are legitimate. The section inventory, which records it
    as reserved. And vacatur.py, whose entire job is to hold the record of why it is
    gone. Anything else is a bug, and the exemption is by filename so it cannot be
    widened by adding a reassuring word to a line.
    """
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "vacatur.py":
            continue
        text = path.read_text()
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "541.4" not in line:
                continue
            allowed = "reserved" in line.casefold() or "vacat" in line.casefold()
            if not allowed:
                offenders.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_the_research_note_records_the_removal_date() -> None:
    note = (ROOT / "docs" / "research" / "001-regulation.md").read_text()
    assert "removed 2025-12-29" in note
    assert "152 F.4th 215" in note
    assert "FMC-2025-0107" in note


# ---------------------------------------------------------------- criterion 2
# A check exists for 541.6(a)(4), testing that the liability basis is articulated.


def test_an_absent_liability_basis_is_a_541_5_event() -> None:
    """The strongest surviving hook after the vacatur.

    A wrong party invoice is not a per se defect any more, but the carrier must
    still say why this party is liable. A missing disclosure is a 541.6 required
    minimum, which is a 541.5 event.
    """
    finding = check_liability_basis(None, "INV-4471")
    assert finding.verdict == "absent"
    assert finding.eliminates_obligation is True
    assert finding.omission is not None
    assert finding.omission.cite == LIABILITY_BASIS_CITE
    assert effect_of([finding.omission]) is Obligation.ELIMINATED


def test_a_conclusory_basis_is_not_a_541_5_event() -> None:
    """And this is the distinction the issue is really about.

    The carrier said something, so nothing is missing, so 541.5 does not fire. The
    available argument is 545.5(d) on the clarity of the policy, and filing it as
    non-payability would be arguing a defence that is not there.
    """
    finding = check_liability_basis("You are liable for this charge as per contract.")
    assert finding.verdict == "conclusory"
    assert finding.eliminates_obligation is False
    assert finding.omission is None
    assert "545.5(d)" in finding.detail
    assert "not a 541.5 event" in finding.detail


def test_a_blank_basis_is_treated_as_absent() -> None:
    """Whitespace is not a disclosure."""
    for blank in ("", "   ", "\t\n"):
        assert check_liability_basis(blank).verdict == "absent"


def test_a_particularised_basis_passes() -> None:
    finding = check_liability_basis(
        "Consignee of record under bill of lading MAEU123456789, terms prepaid"
    )
    assert finding.verdict == "particularised"
    assert finding.eliminates_obligation is False


@pytest.mark.parametrize(
    "phrase",
    ["as per contract", "per our agreement", "you are liable", "responsible for payment"],
)
def test_the_conclusory_phrases_are_the_ones_listed(phrase: str) -> None:
    assert check_liability_basis(f"{phrase}").verdict == "conclusory"


def test_the_absence_message_does_not_claim_a_wrong_party_defect() -> None:
    """After the vacatur the message must not reason from who was invoiced.

    It has to reason from what the carrier failed to say. A message that says
    "invoiced the wrong party" would be reasoning from the vacated section while
    sounding new.
    """
    detail = check_liability_basis(None).detail
    assert "not a per se defect" in detail
    assert "must still state" in detail


# ---------------------------------------------------------------- criterion 3
# The two World Shipping Council cases are distinguished in code comments.


def test_the_two_cases_are_distinguished_by_docket() -> None:
    assert WORLD_SHIPPING_COUNCIL_5414.docket == "No. 24-1088"
    assert WORLD_SHIPPING_COUNCIL_5421.docket == "No. 24-1298"
    assert WORLD_SHIPPING_COUNCIL_5414.docket != WORLD_SHIPPING_COUNCIL_5421.docket
    assert WORLD_SHIPPING_COUNCIL_5414.citation_text != WORLD_SHIPPING_COUNCIL_5421.citation_text


def test_both_cases_name_the_same_party_and_different_rules() -> None:
    """The hazard, stated as a test.

    A lookup keyed on the party name returns one of these and it may be the wrong
    one. So the registry is keyed by docket and the subject sits on each record.
    """
    assert "World Shipping Council" in WORLD_SHIPPING_COUNCIL_5414.citation_text
    assert "World Shipping Council" in WORLD_SHIPPING_COUNCIL_5421.citation_text
    assert "542.1" in WORLD_SHIPPING_COUNCIL_5421.subject
    assert "541.4" in WORLD_SHIPPING_COUNCIL_5414.subject
    assert "Nothing about demurrage" in WORLD_SHIPPING_COUNCIL_5421.holding


def test_looking_a_case_up_by_party_name_is_not_offered() -> None:
    with pytest.raises(KeyError, match="docket"):
        case_for("World Shipping Council v. FMC")
    assert case_for("No. 24-1088").subject.startswith("46 CFR 541.4")


def test_the_module_docstring_names_both_cases() -> None:
    text = " ".join((importlib.import_module("quayline.regulation.vacatur").__doc__ or "").split())
    assert "24-1088" in text
    assert "per invoice" in text
    assert "not a licence to stop paying that carrier" in text


# ---------------------------------------------------------------- criterion 4
# 46 U.S.C. 41104(f) is a per-invoice defense, not a permanent bar.


def test_the_statute_is_quoted_verbatim() -> None:
    assert STATUTE_41104_F == (
        "Failure to include the information required under subsection (d) on an invoice with "
        "any demurrage or detention charge shall eliminate any obligation of the charged party "
        "to pay the applicable charge."
    )


def test_the_statute_is_scoped_to_one_invoice_and_its_applicable_charge() -> None:
    """Per invoice, not per carrier.

    The words that carry it are "on an invoice with any demurrage or detention
    charge" and "the applicable charge". Singular, both of them.
    """
    assert "on an invoice" in STATUTE_41104_F
    assert "the applicable charge" in STATUTE_41104_F
    assert "shall eliminate any obligation" in STATUTE_41104_F
    assert not re.search(r"\bany carrier\b", STATUTE_41104_F)


def test_the_kill_switch_is_per_invoice_and_carries_nothing_forward() -> None:
    """The engine, not just the prose.

    ``effect_of`` takes the omissions for one invoice and returns one obligation.
    There is no carrier argument on it, so there is nothing to persist, and nothing
    that could turn into a standing authorisation to withhold.
    """
    params = list(inspect.signature(effect_of).parameters)
    assert params == ["omissions"], params

    omitted = [Omission(field=by_cite("541.6(a)(4)"), invoice_ref="INV-4471")]
    assert effect_of(omitted) is Obligation.ELIMINATED
    assert effect_of([]) is Obligation.INTACT, "the next invoice is judged on its own"


def test_the_module_warns_against_the_general_authorisation_reading() -> None:
    """The customer-favourable misreading is the real risk here.

    "This carrier once omitted something" reads like a licence to stop paying that
    carrier, and 41104(f) does not say that.
    """
    text = " ".join((importlib.import_module("quayline.regulation.vacatur").__doc__ or "").split())
    assert "does not survive the next correctly presented invoice" in text
    assert "general authorisation to withhold" in text


def test_vacated_section_constant_is_usable_for_an_explicit_refusal() -> None:
    """So a caller migrating an old check has something to branch on."""
    assert VACATED_SECTION == "541.4"
    with pytest.raises(VacatedRuleError, match=re.escape(VACATED_SECTION)):
        refuses_vacated_basis()


def test_case_records_are_immutable() -> None:
    with pytest.raises(AttributeError):
        WORLD_SHIPPING_COUNCIL_5414.docket = "No. 99-9999"  # type: ignore[misc]
