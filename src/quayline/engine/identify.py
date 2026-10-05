"""Issue 218: name the carrier from what the invoice discloses, not from a parameter.

Every command required ``--carrier Maersk``, spelled exactly. This removes that.

## Why guessing the carrier is usually wrong, and why it is not guessing here

``ingest/bind.py`` and ``engine/daycount.py`` both refuse to guess a carrier, and the
reasoning is recorded in both: **541.6 never asks a carrier to name itself on the invoice
face**, so a guess produces a day count computed from the wrong rule, which is
indistinguishable from a right one.

That argument is about *computing*. It does not reach *reading*, because 541.6(c)(2)
makes the carrier disclose the rule it billed under. ``Maersk US Newark Dry`` is the
carrier's own name for its own schedule, and we hold a transcribed block under it, so the
answer comes out of tariff data somebody read and cited rather than out of a logo at the
top of the page.

Two things follow, and both matter.

**Not from the letterhead.** A forwarder's own name is printed on bills it passes on, and
"MAERSK" in a header is weaker evidence than the rule the invoice says it billed under.

**Not by fuzzy match.** ``Registry.normalise`` is case and whitespace only, and that
restraint is deliberate. A looser match here would be a second and weaker system wearing
the same name, and it would be right about ``Maersk US Newark Dry Cargo`` on this document
and wrong on the next one where the difference changes the answer.

## What it cannot do

A carrier we hold no schedule for identifies as nothing. That is the common case and it is
not an error: the disclosure check, the day count and the letter all still run, and the
reader supplies the carrier only when they want the money priced.

The one design choice worth stating is that an **ambiguous** rule returns nothing rather
than picking one. Two carriers declaring one reference means the document does not tell
us which, and on that document the regulation's own preference, that a charge must not be
non-payable unless the omission is certain, is the right default.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from quayline.tariffs.blocks import RateBlock

__all__ = ["Identified", "identify_carrier"]


@dataclass(frozen=True, slots=True)
class Identified:
    """A carrier, and the rule reference it came from.

    The rule is carried so the page and the letter can show the reader *why* we think
    the invoice is Maersk's. A detection a reader cannot audit is a detection they have
    to take on trust, and trust is what this product asks them for.
    """

    carrier: str
    rule: str


def identify_carrier(declared: str, blocks: Sequence[RateBlock]) -> Identified | None:
    """The carrier whose schedule ``declared`` names, or ``None``.

    ``None`` means four different things and deliberately does not distinguish them: no
    rule was disclosed, the rule is one we hold nothing for, two carriers declare it, or
    the reference is a near miss. Every one of those needs the reader to supply the
    carrier, so the caller does the same thing in each case.

    Never raises. Real input is junk more often than it is clean, and an identification
    failure is an answer rather than a fault.
    """
    wanted = " ".join(declared.split()).casefold()
    if not wanted:
        return None

    matches = [b for b in blocks if " ".join(b.rule.split()).casefold() == wanted]
    if len(matches) != 1:
        # Zero is the common case: a carrier we hold nothing for. More than one is
        # ambiguity, and guessing between two carriers would compute a day count from a
        # rule the document did not say it billed under.
        return None

    return Identified(carrier=matches[0].carrier, rule=matches[0].rule)
