"""The four acceptance criteria on issue 1, one test block each.

The counts are asserted against a real structure rather than a number someone
wrote down. Four identifying, eight timing, three rate, three dispute, two
certification, twenty in all, and every group the regulation actually defines.
A field that moves between groups changes what a dispute letter has to argue,
so the shape is part of the law here, not an implementation detail.
"""

from __future__ import annotations

import inspect
from collections import Counter

import pytest

from quayline.regulation import (
    CHECKLIST,
    GROUP_HEADINGS,
    SECTION_541_5,
    SECTION_541_6,
    ChecklistField,
    Scope,
    Trade,
    by_cite,
    effect_of,
    required_for,
)
from quayline.regulation.kill_switch import Obligation, Omission

# ---------------------------------------------------------------- criterion 1
# Each of the twenty fields carries its cite, the verbatim regulatory text, and
# the group letter.


def test_twenty_fields() -> None:
    assert len(CHECKLIST) == 20


def test_every_field_carries_cite_text_group_and_heading() -> None:
    for field in CHECKLIST:
        assert field.cite, f"a field is missing its cite: {field}"
        assert field.text, f"{field.cite} is missing its regulatory text"
        assert field.group in GROUP_HEADINGS, f"{field.cite} has unknown group {field.group!r}"
        assert field.heading == GROUP_HEADINGS[field.group], (
            f"{field.cite} claims heading {field.heading!r} but group {field.group!r} "
            f"is titled {GROUP_HEADINGS[field.group]!r}"
        )


def test_cites_are_unique_and_well_formed() -> None:
    cites = [f.cite for f in CHECKLIST]
    assert len(cites) == len(set(cites)), "two fields share a cite"
    for cite in cites:
        assert cite.startswith("541.6("), f"{cite} is not a 541.6 reference"


def test_text_is_verbatim_not_a_paraphrase() -> None:
    """The clauses as published, with their trailing punctuation intact.

    541.6 is written as a list, so four clauses end in "; and" and the rest end
    in ";" or a full stop. If a future edit tidies those away, this fails,
    because a dispute letter that quotes tidied text is quoting something the
    regulation does not say.
    """
    joined = " ".join(f.text for f in CHECKLIST)
    # Spot checks against the published wording, chosen to catch paraphrase
    # dressed as a copy.
    assert by_cite("541.6(a)(1)").text == "The Bill of Lading number(s);"
    assert by_cite("541.6(a)(3)").text == "For imports, the port(s) of discharge; and"
    assert by_cite("541.6(b)(7)").text == "For exports, the earliest return date; and"
    assert "e.g., the tariff name and rule number" in by_cite("541.6(c)(2)").text
    assert "46 CFR 545.5; and" in by_cite("541.6(e)(1)").text
    # The conjunction survives in exactly five clauses: (a)(3), (b)(7), (c)(2),
    # (d)(2) and (e)(1). Every one of those is the second to last clause of its
    # group, which is what "and" means in a list.
    assert {f.cite for f in CHECKLIST if f.text.endswith("; and")} == {
        "541.6(a)(3)",
        "541.6(b)(7)",
        "541.6(c)(2)",
        "541.6(d)(2)",
        "541.6(e)(1)",
    }
    # Twenty clauses join to 1732 characters. The floor is set well under that
    # so it only trips on losing whole text, and the real protection against a
    # dropped clause is the per group contiguity check below, which fails the
    # moment a group or an item goes missing.
    assert len(joined) > 1200, "the extracted text looks truncated"


def test_statement_strips_list_punctuation_and_text_does_not() -> None:
    for field in CHECKLIST:
        if field.text.endswith("; and"):
            assert field.statement == field.text[: -len("; and")], field.cite
        elif field.text.endswith((";", ".")):
            assert field.statement == field.text[:-1], field.cite
        assert not field.statement.endswith((";", ".")), field.cite


def test_provenance_is_dated_and_citable() -> None:
    assert SECTION_541_6.cite == "46 CFR 541.6"
    assert SECTION_541_6.as_of == "2026-09-24"
    assert SECTION_541_6.federal_register.startswith("89 FR")
    assert SECTION_541_6.effective == "2024-05-28"
    assert "section-541.6" in SECTION_541_6.url
    assert "541.5" in str(SECTION_541_5)


# ---------------------------------------------------------------- criterion 2
# A test asserts exactly four (a), eight (b), three (c), three (d), two (e)
# fields.


def test_group_counts_match_the_regulation() -> None:
    counts = Counter(f.group for f in CHECKLIST)
    assert counts == {"a": 4, "b": 8, "c": 3, "d": 3, "e": 2}
    assert sum(counts.values()) == 20


def test_item_numbers_are_contiguous_within_each_group() -> None:
    """(b) is (1) through (8) with nothing missing or renumbered.

    A gap would mean a clause was dropped in extraction, and a dropped clause
    means a real omission goes undetected, which means a real charge survives
    that should not have.
    """
    for group in GROUP_HEADINGS:
        items = [f.cite.rsplit("(", 1)[1].rstrip(")") for f in CHECKLIST if f.group == group]
        assert items == [str(n) for n in range(1, len(items) + 1)], f"group ({group})"


def test_group_headings_are_the_published_ones() -> None:
    assert GROUP_HEADINGS == {
        "a": "Identifying information",
        "b": "Timing information",
        "c": "Rate information",
        "d": "Dispute information",
        "e": "Certifications",
    }


# ---------------------------------------------------------------- criterion 3
# Each field records whether it is import-only or export-only.


def test_three_fields_are_one_directional() -> None:
    scoped = {f.cite: f.scope for f in CHECKLIST if f.scope is not Scope.BOTH}
    assert scoped == {
        "541.6(a)(3)": Scope.IMPORT_ONLY,
        "541.6(b)(6)": Scope.IMPORT_ONLY,
        "541.6(b)(7)": Scope.EXPORT_ONLY,
    }


def test_scope_follows_the_regulations_own_lead_in() -> None:
    """The scope is read off the clause, not assigned by hand.

    541.6 writes the direction into the text itself, "For imports," and "For
    exports,", so the classification cannot drift from the language it is
    derived from.
    """
    for field in CHECKLIST:
        if field.scope is Scope.IMPORT_ONLY:
            assert field.text.startswith("For imports,"), field.cite
        elif field.scope is Scope.EXPORT_ONLY:
            assert field.text.startswith("For exports,"), field.cite
        else:
            assert not field.text.startswith(("For imports,", "For exports,")), field.cite


def test_required_for_filters_to_the_relevant_direction() -> None:
    """Imports are checked against nineteen disclosures, exports against
    eighteen, out of a checklist of twenty.

    The asymmetry is not a rounding error, it is the regulation. An import needs
    both the port of discharge under (a)(3) and the container availability date
    under (b)(6). An export needs only the earliest return date under (b)(7).

    So no real invoice is ever checked against all twenty. A checker that asked
    an export invoice for a container availability date would be demanding a
    fact that does not exist, would record it as an omission, and 541.5 would
    then eliminate a charge that was properly owed. Over demanding is not a
    harmless default here, it manufactures false grounds.
    """
    imports = required_for(Trade.IMPORT)
    exports = required_for(Trade.EXPORT)
    assert len(imports) == 19
    assert len(exports) == 18
    assert by_cite("541.6(b)(7)") not in imports
    assert by_cite("541.6(a)(3)") not in exports
    assert by_cite("541.6(b)(6)") not in exports
    assert by_cite("541.6(c)(1)") in imports
    assert by_cite("541.6(c)(1)") in exports


def test_every_field_applies_to_at_least_one_direction() -> None:
    for field in CHECKLIST:
        assert field.applies_to(Trade.IMPORT) or field.applies_to(Trade.EXPORT), field.cite


# ---------------------------------------------------------------- criterion 4
# A test asserts 541.5 is keyed to omission and never to inaccuracy.


def test_541_5_fires_on_omission() -> None:
    field = by_cite("541.6(b)(3)")
    assert effect_of([Omission(field=field, invoice_ref="INV-1")]) is Obligation.ELIMINATED


def test_541_5_is_silent_when_nothing_is_missing() -> None:
    assert effect_of([]) is Obligation.INTACT


def test_541_5_needs_only_one_omission() -> None:
    """ "Failure to include any of the required minimum information" is
    disjunctive, so the first omission settles it."""
    omissions = [
        Omission(field=by_cite(c), invoice_ref="INV-1") for c in ("541.6(a)(1)", "541.6(b)(3)")
    ]
    assert effect_of(omissions) is Obligation.ELIMINATED
    assert effect_of(reversed(omissions)) is Obligation.ELIMINATED


def test_541_5_is_keyed_to_omission_and_never_to_inaccuracy() -> None:
    """The criterion, stated as behaviour.

    A perfect invoice missing one disclosure is not owed. A halved invoice that
    discloses everything is owed. If these two ever produce the same answer, or
    if the second one produces anything other than INTACT, the kill switch has
    been wired to the arithmetic and the legal theory is inverted.
    """
    # Arithmetic perfect, one disclosure absent. Not owed at all.
    perfect_but_incomplete = [
        Omission(field=by_cite("541.6(b)(3)"), invoice_ref="ARITHMETIC-EXACT")
    ]
    assert effect_of(perfect_but_incomplete) is Obligation.ELIMINATED

    # Overstated by half, every required disclosure present. 541.5 has nothing
    # to say, and that is the whole point. The overcharge is real and is
    # disputed, but on the arithmetic and not on 541.5, and calling it a 541.5
    # claim would put the strongest ground in the brief next to a defence that
    # does not exist.
    complete_but_overstated: list[Omission] = []
    assert effect_of(complete_but_overstated) is Obligation.INTACT


def test_kill_switch_signature_cannot_receive_an_amount() -> None:
    """The invariant enforced structurally rather than by discipline.

    If a future change adds a parameter for a billed amount, a computed amount,
    or a discrepancy, the kill switch can be keyed to inaccuracy without anyone
    deciding to do it. The signature is the guard.
    """
    params = list(inspect.signature(effect_of).parameters)
    assert params == ["omissions"], f"effect_of gained parameters: {params}"
    assert params[0].endswith("omissions")


def test_omission_carries_no_monetary_or_arithmetic_field() -> None:
    """Same guard one level down, on the type handed to the kill switch."""
    fields = {f.name for f in Omission.__dataclass_fields__.values()}
    assert fields == {"field", "invoice_ref"}, fields
    banned = ("amount", "rate", "charge", "total", "due", "discrepancy", "value", "price")
    assert not {f for f in fields if any(b in f.lower() for b in banned)}, fields


def test_omission_describe_names_the_clause_and_the_invoice() -> None:
    line = Omission(field=by_cite("541.6(b)(3)"), invoice_ref="INV-4471").describe()
    assert line == "541.6(b)(3) The allowed free time in days is not stated on INV-4471"


def test_intact_is_not_a_statement_that_the_charge_is_valid() -> None:
    """INTACT means 541.5 is silent. It is not a clean bill of health.

    Asserted on the docstring because the misreading is the likely one: a
    downstream caller that treats INTACT as "valid" would stop looking at
    541.7 lateness and at the arithmetic, both of which are separate grounds.
    """
    assert Obligation.INTACT.value == "intact"
    assert "not that the charge is valid" in (Obligation.__doc__ or "")


@pytest.mark.parametrize("cite", ["541.9(a)(1)", "541.6(z)(1)", "nonsense"])
def test_by_cite_rejects_unknown_references(cite: str) -> None:
    with pytest.raises(KeyError):
        by_cite(cite)


def test_checklist_field_is_immutable() -> None:
    field: ChecklistField = by_cite("541.6(c)(1)")
    with pytest.raises(AttributeError):
        field.text = "tampered"  # type: ignore[misc]
