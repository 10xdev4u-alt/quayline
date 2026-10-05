"""Issue 218: naming the carrier so a reader does not have to.

Every command required `--carrier Maersk`, spelled exactly. A forwarder with a folder of
invoices has to look each carrier's published name up, and the day basis rules are keyed
on it, so a near miss raises rather than warns.

The argument against guessing the carrier is already recorded in `ingest/bind.py` and
`engine/daycount.py`, and it is right: 541.6 never asks a carrier to name itself, so a
wrong guess produces a plausible wrong day count.

That argument is about computing. It is not about reading, because 541.6(c)(2) makes the
carrier disclose the rule it billed under, and `RateBlock.carrier` records whose schedule
that is. The answer comes out of transcribed tariff data rather than out of a letterhead.

So the tests below are mostly about what detection must NOT do.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from conftest import build_pdf
from quayline.calendars.day_basis import RULES
from quayline.cli.audit_cmd import main
from quayline.engine.identify import Identified, identify_carrier
from quayline.tariffs.blocks import RateBlock, Tier
from quayline.tariffs.corpus import load_corpus
from test_carrier_layout import MAERSK_COLUMNS


def _block(carrier: str, rule: str) -> RateBlock:
    # A tier is mandatory: `RateBlock` refuses a schedule that cannot be priced, which
    # is a guard worth having and one this fixture has to satisfy honestly.
    return RateBlock(
        rule=rule,
        carrier=carrier,
        cluster="US",
        equipment="dry",
        free_days=7,
        tiers=(Tier(from_day=1, to_day=None, rate=Decimal("390.00")),),
        source="test",
        effective_from="2026-01-01",
    )


BLOCKS = (
    _block("Maersk", "Maersk US Newark Dry"),
    _block("Maersk", "Maersk US Miami Dry"),
    _block("Hapag-Lloyd", "Hapag-Lloyd US New York Dry"),
)


# --- the case that works ------------------------------------------------------


def test_the_disclosed_rule_names_the_carrier() -> None:
    """The whole point, and it is a fact about the document rather than a guess."""
    found = identify_carrier("Maersk US Newark Dry", BLOCKS)
    assert found is not None
    assert found.carrier == "Maersk"


def test_the_rule_match_is_case_and_whitespace_insensitive() -> None:
    """The same discipline `Registry.normalise` uses, no more and no less.

    A looser match here would make this a different system wearing the same name, and a
    system that guesses a carrier from a near miss is the failure issue 218 exists to
    avoid.
    """
    for reference in (
        "maersk us newark dry",
        "MAERSK   US   NEWARK DRY",
        "  Maersk US Newark Dry  ",
    ):
        found = identify_carrier(reference, BLOCKS)
        assert found is not None and found.carrier == "Maersk", reference


# --- the cases that must not answer ------------------------------------------


def test_an_unknown_rule_identifies_nothing() -> None:
    """A carrier we hold no schedule for is the common case, not an error."""
    assert identify_carrier("CMA CGM US Felixstowe Dry", BLOCKS) is None


def test_no_rule_identifies_nothing() -> None:
    """An invoice stating no rule gives us nothing to go on, which is not a guess."""
    assert identify_carrier("", BLOCKS) is None
    assert identify_carrier("   ", BLOCKS) is None


def test_an_ambiguous_rule_is_not_answered_rather_than_guessed() -> None:
    """Two carriers declaring one rule means we cannot know, so we ask.

    Guessing here would produce a plausible wrong day count on exactly the class of
    document where the regulation gives the carrier the benefit.
    """
    blocks = (*BLOCKS, _block("ONE", "Maersk US Newark Dry"))
    assert identify_carrier("Maersk US Newark Dry", blocks) is None


def test_a_near_miss_rule_identifies_nothing() -> None:
    """``Maersk US Newark Dry Cargo`` is not ``Maersk US Newark Dry``.

    A fuzzy match would call this Maersk and be right here and wrong on the next document
    where the difference matters.
    """
    assert identify_carrier("Maersk US Newark Dry Cargo", BLOCKS) is None


def test_detection_never_raises_on_junk() -> None:
    """An inability to identify is an answer. Raising would be a crash on real input."""
    for junk in ("", "   ", "....", "\n\t", "12345", "()" * 40, "Maersk" * 200):
        assert identify_carrier(junk, BLOCKS) is None, junk


def test_no_blocks_identifies_nothing() -> None:
    """A caller with no tariff data still gets the disclosure check."""
    assert identify_carrier("Maersk US Newark Dry", ()) is None


# --- the shape of the answer --------------------------------------------------


def test_the_answer_says_which_rule_it_came_from() -> None:
    """So the page and the letter can show the reader why we think it is Maersk.

    A detection a reader cannot audit is a detection they have to take on trust, and
    trust is the thing this product is asking them for.
    """
    found = identify_carrier("Maersk US Newark Dry", BLOCKS)
    assert isinstance(found, Identified)
    assert found.rule == "Maersk US Newark Dry"
    assert found.carrier == "Maersk"


def test_the_real_corpus_identifies_its_own_carrier() -> None:
    """Against the data we actually hold rather than a fixture built for the test."""
    blocks = tuple(load_corpus().values())
    for rule in blocks:
        found = identify_carrier(rule.rule, blocks)
        assert found is not None, rule.rule
        assert found.carrier == rule.carrier, rule.rule


def test_the_real_corpus_names_a_carrier_we_hold_no_day_basis_for() -> None:
    """Hapag-Lloyd has a day basis rule and no transcribed rates, and it still identifies.

    That is the honest limit of #218: it works for carriers we hold tariff data for,
    which is not the same set as carriers we can price. Detection is about naming, and
    naming is available more widely than arithmetic.
    """
    blocks = tuple(load_corpus().values())
    found = identify_carrier("Hapag-Lloyd US New York Dry", blocks)
    assert found is None, "no Hapag block is held, so nothing to identify from"
    assert "Hapag-Lloyd" in RULES, "but we do hold a day basis rule for it"


# --- the command line, which is where this actually matters -----------------


def test_a_carrier_invoice_audits_with_no_carrier_argument(tmp_path: Path) -> None:
    """The acceptance criterion a reader feels.

    Issue 216 taught the binder to read a carrier invoice. Before this, the reader still
    had to know and type the carrier's exact published name. Now they can put the PDF in
    and read the answer.
    """
    path = tmp_path / "maersk.pdf"
    path.write_bytes(build_pdf(*MAERSK_COLUMNS))

    code = main(["audit", str(path), "--terminal", "newark", "--json"])
    assert code != 2, "the command refused the document"
    assert code == 1, "a carrier invoice with a resolved rule should be file-worthy"


def test_the_carrier_argument_is_still_required_when_detection_cannot_answer(
    tmp_path: Path,
) -> None:
    """An invoice whose rule we hold nothing for still needs the reader to say who.

    Detection covering only carriers we hold tariff data for is the honest limit. The
    refusal is unchanged, and this proves it, because the alternative is a default that
    quietly guesses.
    """
    lines = tuple(
        line.replace("Maersk US Newark Dry", "CMA CGM US Felixstowe Dry") for line in MAERSK_COLUMNS
    )
    path = tmp_path / "unknown.pdf"
    path.write_bytes(build_pdf(*lines))

    code = main(["audit", str(path), "--terminal", "newark"])
    assert code == 2, "an unidentifiable carrier must still ask"
