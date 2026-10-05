"""Issue 224: when a reader types a carrier the invoice contradicts, say so.

#218 refuses to *guess* a carrier. This catches the case where the reader guesses one,
which is the same failure arriving by a different door: a wrong day basis gives a wrong
free time expiry, which gives a wrong number, which looks entirely plausible.

The design constraint that shaped everything here: **a warning that fires on most
documents is worse than no warning.** Detection only works for carriers we hold tariff
data for, which is one of nine, so a warning on every undetectable document would train
people to ignore warnings and make the real one invisible.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from decimal import Decimal
from pathlib import Path

from conftest import build_pdf
from quayline.cli.audit_cmd import main
from quayline.engine.disagreement import Disagreement, check_supplied
from quayline.engine.identify import identify_carrier
from quayline.tariffs.blocks import RateBlock, Tier
from quayline.tariffs.corpus import load_corpus
from test_carrier_layout import MAERSK_COLUMNS


def _block(carrier: str, rule: str) -> RateBlock:
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
    _block("Hapag-Lloyd", "Hapag-Lloyd US New York Dry"),
)


# --- agreement is silent -----------------------------------------------------


def test_a_carrier_that_agrees_produces_no_warning() -> None:
    """The common case for a reader who typed the right thing, and it must be silent.

    A warning that fires when everything is fine is how warnings get ignored.
    """
    assert check_supplied("Maersk", "Maersk US Newark Dry", BLOCKS) is None


def test_no_warning_when_nothing_can_be_detected() -> None:
    """The seven carriers we cannot price. A warning here would be noise.

    Detection works for one carrier of nine. If this warned, seven invoices in nine
    would carry a warning and the one that matters would be lost among them.
    """
    assert check_supplied("MSC", "MSC US Felixstowe Dry", BLOCKS) is None


def test_no_warning_when_the_reader_supplied_nothing() -> None:
    """That is the #220 case and the runner already labels it as inferred."""
    assert check_supplied("", "Maersk US Newark Dry", BLOCKS) is None


# --- disagreement is loud ---------------------------------------------------


def test_a_carrier_that_disagrees_warns() -> None:
    """The whole issue."""
    result = check_supplied("Maersk", "Hapag-Lloyd US New York Dry", BLOCKS)

    assert result is not None
    assert result.supplied == "Maersk"
    assert result.detected == "Hapag-Lloyd"
    assert result.rule == "Hapag-Lloyd US New York Dry"


def test_the_warning_names_both_carriers_and_the_rule() -> None:
    """All three, or the reader cannot act on it.

    Naming only the detected carrier invites the reader to think the tool is simply
    correcting them, which it is not doing.
    """
    result = check_supplied("Maersk", "Hapag-Lloyd US New York Dry", BLOCKS)
    assert result is not None

    message = result.as_sentence()
    assert "Maersk" in message
    assert "Hapag-Lloyd" in message
    assert "Hapag-Lloyd US New York Dry" in message


def test_the_warning_does_not_say_which_one_is_right() -> None:
    """Deliberately. The reader may know something the invoice does not.

    A forwarder can reissue an invoice under a group name. If we said "you are wrong",
    a reader who is right would have no way to say so.
    """
    result = check_supplied("Maersk", "Hapag-Lloyd US New York Dry", BLOCKS)
    assert result is not None

    message = result.as_sentence().lower()
    for verdict in ("you are wrong", "incorrect", "invalid", "must be", "should be"):
        assert verdict not in message, f"the warning tells the reader what is true: {verdict!r}"


def test_the_warning_says_the_reader_keeps_their_value() -> None:
    """Because the computation uses what the reader supplied.

    This is the difference between warning and overriding, and it has to be visible or
    the reader cannot tell which number produced the letter.
    """
    result = check_supplied("Maersk", "Hapag-Lloyd US New York Dry", BLOCKS)
    assert result is not None
    assert "computed" in result.as_sentence().lower()


def test_carrier_names_are_compared_as_written_and_case_insensitively() -> None:
    """`maersk` and `Maersk` are the same carrier and must not raise a warning.

    A warning that fires on capitalisation teaches readers to ignore it.
    """
    assert check_supplied("maersk", "Maersk US Newark Dry", BLOCKS) is None


def test_a_carrier_name_with_surrounding_space_does_not_warn() -> None:
    """The form strips it, but a reader pasting a name with a trailing space should be fine."""
    assert check_supplied("  Maersk  ", "Maersk US Newark Dry", BLOCKS) is None


def test_the_real_corpus_agrees_with_itself() -> None:
    """Against the data we hold, every block's own carrier agrees with its rule."""
    blocks = tuple(load_corpus().values())
    for block in blocks:
        found = identify_carrier(block.rule, blocks)
        assert found is not None, block.rule
        assert check_supplied(block.carrier, block.rule, blocks) is None, block.rule


def test_disagreement_is_a_value_and_carries_its_rule() -> None:
    """Frozen and slotted like everything else here, so a caller cannot mutate a warning."""
    result = check_supplied("Maersk", "Hapag-Lloyd US New York Dry", BLOCKS)
    assert result is not None
    assert isinstance(result, Disagreement)
    try:
        result.supplied = "MSC"  # type: ignore[misc]
    except (AttributeError, TypeError):
        return
    raise AssertionError("a warning a caller can edit is not a warning")


# --- it reaches the reader ---------------------------------------------------


def test_the_command_line_warns_on_stderr_and_still_succeeds(tmp_path: Path) -> None:
    """A warning, not a failure. The reader may know something the document does not.

    The exit code is the thing to check: a warning that changes the exit code stops the
    command being usable in a script, and the disagreement is not an error in the document.
    """

    # The invoice keeps its Maersk rule, which is the one schedule we hold. The reader
    # types Hapag-Lloyd. That is the disagreement: we can name a carrier from the rule and
    # it is not the one supplied.
    path = tmp_path / "m.pdf"
    path.write_bytes(build_pdf(*MAERSK_COLUMNS))

    captured = io.StringIO()
    with redirect_stderr(captured):
        code = main(["audit", str(path), "--carrier", "Hapag-Lloyd", "--terminal", "newark"])

    warning = captured.getvalue()
    assert "warning" in warning.lower()
    assert "Hapag-Lloyd" in warning and "Maersk US Newark Dry" in warning
    assert code != 2, "a disagreement must not stop the command"


def test_the_command_line_is_silent_when_the_carrier_agrees(tmp_path: Path) -> None:
    """Silence on the common case, or the warning means nothing."""

    path = tmp_path / "m.pdf"
    path.write_bytes(build_pdf(*MAERSK_COLUMNS))

    captured = io.StringIO()
    with redirect_stderr(captured):
        main(["audit", str(path), "--carrier", "Maersk", "--terminal", "newark"])

    assert "warning" not in captured.getvalue().lower()
