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
    FREIGHT_TERM_ESTIMATE,
    LIABILITY_BASIS_CITE,
    STATUTE_41104_F,
    VACATED_SECTION,
    VACATUR_CITATION,
    VACATUR_REMOVAL,
    WORLD_SHIPPING_COUNCIL_5414,
    WORLD_SHIPPING_COUNCIL_5421,
    FreightTerm,
    VacatedRuleError,
    case_for,
    check_liability_basis,
    freight_term_reading,
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


# ---------------------------------------------------------------- issue 32
# The freight term evidence, and the party of interest case.


def test_absence_eliminates_the_obligation() -> None:
    """Criterion one. Absence is a missing 541.6 required minimum, so 541.5 fires."""
    finding = check_liability_basis(None, "INV-1")
    assert finding.verdict == "absent"
    assert finding.eliminates_obligation is True
    assert finding.omission is not None


def test_a_generic_formula_is_a_soft_defect() -> None:
    """Criterion two. Something was said, so nothing is missing and 541.5 does not
    fire. The available argument is 545.5(d), and claiming otherwise argues a defence
    that is not there."""
    finding = check_liability_basis("as per contract")
    assert finding.verdict == "conclusory"
    assert finding.eliminates_obligation is False
    assert finding.omission is None


def test_party_of_interest_with_no_privity_is_conclusory() -> None:
    """Criterion four.

    A carrier asserting the billed party is the party of interest has restated the
    conclusion. Nothing about privity, nothing about the bill of lading, nothing a
    respondent could check.
    """
    for phrase in (
        "party of interest",
        "proper party of interest",
        "party in interest",
        "Party Of Interest",
    ):
        assert check_liability_basis(phrase).verdict == "conclusory", phrase


def test_a_particularised_basis_is_not_conclusory() -> None:
    """Otherwise the phrase list grows until every basis is a defect."""
    finding = check_liability_basis(
        "demurrage is for the consignee as named on the bill of lading, freight prepaid"
    )
    assert finding.verdict == "particularised"
    assert finding.eliminates_obligation is False


def test_the_evidence_list_names_the_bill_of_lading_and_both_freight_terms() -> None:
    """Criterion three.

    The bill of lading is the instrument that sets liability and it is in the
    shipper's hands, not the carrier's. Both freight terms follow because a
    respondent who finds one of them needs to be told what it ordinarily implies
    before they conclude the carrier was right.
    """
    items = check_liability_basis(None).evidence()
    assert items[0].startswith("the bill of lading")
    assert "prepaid" in items[1]
    assert "consignee" in items[1]
    assert "collect" in items[2]
    assert "shipper" in items[2]


def test_the_evidence_list_is_the_same_for_every_verdict() -> None:
    """What a respondent must produce does not depend on how badly they did."""
    lists = {
        check_liability_basis(None).evidence(),
        check_liability_basis("party of interest").evidence(),
        check_liability_basis("freight prepaid per the bill of lading").evidence(),
    }
    assert len(lists) == 1


def test_prepaid_ordinarily_places_the_charge_on_the_consignee() -> None:
    """ESTIMATE, and marked as one. See the module constant."""
    reading = freight_term_reading(FreightTerm.PREPAID)
    assert reading.ordinarily_liable == "the consignee"
    assert reading.determined is True


def test_collect_ordinarily_places_the_charge_on_the_shipper() -> None:
    reading = freight_term_reading(FreightTerm.COLLECT)
    assert reading.ordinarily_liable == "the shipper"
    assert reading.determined is True


def test_an_unstated_term_determines_nothing() -> None:
    """Which is the case that produces the strongest question, not the weakest
    answer."""
    reading = freight_term_reading(FreightTerm.UNSTATED)
    assert reading.ordinarily_liable is None
    assert reading.determined is False
    assert "does not state" in reading.rationale


def test_the_freight_practice_is_marked_an_estimate() -> None:
    """Part 541 does not say it, no carrier tariff in our research says it, and it
    is not uniform. Asserting it as law would be a legal conclusion with no clause
    under it, which is the failure the vacatur issue was about."""
    assert FREIGHT_TERM_ESTIMATE.startswith("ESTIMATE")
    assert "not a rule in 46 CFR Part 541" in FREIGHT_TERM_ESTIMATE
    assert "No carrier tariff in our research states this" in FREIGHT_TERM_ESTIMATE


def test_the_practice_is_never_used_to_assert_a_party_was_wrong() -> None:
    """The reading produces a question, never a verdict. A finding whose verdict
    flipped on the freight term would be a legal conclusion, and there is no clause
    for it."""
    verdicts = {check_liability_basis(None, freight_term=term).verdict for term in FreightTerm}
    assert verdicts == {"absent"}


def test_the_question_names_the_party_and_the_term() -> None:
    finding = check_liability_basis(
        None, freight_term=FreightTerm.COLLECT, billed_party="Consignee"
    )
    question = finding.question_for_carrier()
    assert "collect" in question
    assert "shipper" in question
    assert "Consignee" in question
    assert question.endswith("?"), "a question, not an accusation"


def test_an_unstated_freight_term_produces_a_generic_question() -> None:
    finding = check_liability_basis(None)
    question = finding.question_for_carrier()
    assert "bill of lading" in question
    assert "this party" not in question


def test_the_freight_term_does_not_change_the_verdict() -> None:
    """It changes what the letter asks for, not what it alleges."""
    for basis in (None, "party of interest", "freight prepaid"):
        assert {
            check_liability_basis(basis, freight_term=term).verdict for term in FreightTerm
        } == {check_liability_basis(basis).verdict}


def test_the_finding_stays_immutable_with_the_new_fields() -> None:
    finding = check_liability_basis(None, freight_term=FreightTerm.PREPAID)
    with pytest.raises(AttributeError):
        finding.billed_party = "someone"  # type: ignore[misc]


def test_issue_32_is_the_provenance_of_the_freight_work() -> None:
    flat = " ".join((check_liability_basis.__doc__ or "").split())
    assert flat, "the check must document what its new parameters do"
