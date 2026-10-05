"""Issue 224: when a reader types a carrier the invoice contradicts, say so, and do not override them.

`engine/identify.py` refuses to guess a carrier, and `ingest/bind.py` refuses to guess one
for the day basis. Both are right, and neither covers this: a reader who types `Maersk` and
uploads a Hapag-Lloyd invoice has *guessed*, and a wrong day basis produces a wrong free
time expiry, which produces a wrong number, which looks entirely plausible.

The failure #218 was written to prevent arriving through the front door instead of the back
one.

## The constraint that shaped this, and it is the whole design

**A warning that fires on most documents is worse than no warning.**

Detection works for the one carrier of nine whose tariff we have transcribed. A warning on
"we could not tell" would therefore appear on seven invoices in nine, and the one that
matters would be buried among them. So:

- supplied and detected **agree**: silence.
- detection finds **nothing**: silence. Not "we could not check", not a hint. Nothing.
- supplied and detected **differ**: a warning, naming both, naming the rule.

Three outcomes, two of them silent, and that ratio is the design.

## Why nothing is overridden

A forwarder can reissue an invoice under a group name, and a carrier can bill under a
schedule a related entity published. The reader may know something the document does not.

Silently replacing their answer would make this module a guesser, which is precisely what
`engine/identify.py` exists not to be. So the disagreement is reported as information, the
computation uses what the reader supplied, and the warning says so in as many words. A
reader who is right can ignore it and know they ignored it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from quayline.engine.identify import identify_carrier
from quayline.tariffs.blocks import RateBlock

__all__ = ["Disagreement", "check_supplied"]


@dataclass(frozen=True, slots=True)
class Disagreement:
    """The carrier a reader supplied, and the one the invoice names.

    Both are kept. Reporting only the detected one invites the reader to think the tool is
    correcting them, which it is not doing.
    """

    supplied: str
    detected: str
    #: The rule reference the detection came from, so the disagreement is checkable against
    #: the document rather than being a claim about it.
    rule: str

    def as_sentence(self) -> str:
        """One line a reader can act on.

        Deliberately does not say which carrier is right. It cannot know, and a reader who
        supplied a group name the invoice contradicts has no way to reply to a message that
        told them they were wrong.

        Says "the figures" rather than "the figures above" because this one string is
        rendered in three places. On the page the warning sits above the verdict and on the
        command line it sits below them.
        """
        return (
            f"You named {self.supplied} but this invoice names the rate rule "
            f"{self.rule!r}, which we hold a {self.detected} schedule for. The figures were "
            f"computed with {self.supplied}, which is what you asked for. If that is "
            f"wrong, change it and run it again."
        )


def check_supplied(
    supplied: str, declared_rule: str, blocks: Sequence[RateBlock]
) -> Disagreement | None:
    """Whether the reader's carrier disagrees with what the invoice names.

    Returns ``None`` for the two silent cases, which are the common ones.
    """
    typed = supplied.strip()
    if not typed:
        # Nothing was supplied, so nothing can disagree. `carrier_inferred` on the result
        # already covers that case and says it was read from the rule.
        return None

    found = identify_carrier(declared_rule, blocks)
    if found is None:
        # We hold no schedule under this rule, so we have no view on the carrier at all.
        # Saying anything here would be a warning on seven invoices in nine.
        return None

    if typed.casefold() == found.carrier.casefold():
        return None

    return Disagreement(supplied=typed, detected=found.carrier, rule=found.rule)
