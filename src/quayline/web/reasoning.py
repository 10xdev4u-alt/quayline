"""Issue 197: the engine's reasoning, shown next to the day it belongs to.

Three pages show the day grid as a row of coloured boxes with a word in each. None of
them shows why. The engine has worked out why, in a sentence, with the clause attached,
and that sentence is the entire product argument.

For the fixture the engine says:

    OVERBILLED on 2026-07-08
    "were charged although the stated allowance under 541.6(b)(3) exhausted on
     2026-07-08"                                                    541.6(b)(8)

That is a claim a carrier's dispute respondent can check against the document in front
of them. Asserting a number and withholding the arithmetic is the least credible posture
available to a product whose whole value is that it is checkable, and it is what the
grid did until now.

The words here are the engine's
-------------------------------

The detail sentence is rendered as the engine wrote it, and the citation is rendered as
the engine states it. Nothing is paraphrased, because a paraphrase is the place an
overclaim gets in, and this project has already had one of those reviewed out of a page
in this same release.

Direction gets the one place this module adds words of its own, because
``OVERBILLED`` is an enum name and a shipper does not know what that means. The mapping
is in :data:`DIRECTION_WORD` and nothing else in this module invents prose.

Why the citations are real text
-------------------------------

A carrier respondent reads this on paper, in a filing, sometimes months later. A tooltip
is gone by then. So every citation is in the markup, in full, in a monospace face, where
it can be selected, copied and printed.
"""

from __future__ import annotations

from typing import Any

from quayline.engine.daycount import Discrepancy
from quayline.web.intake import esc

#: What each direction means to the person who receives the letter. Enum names are for
#: us. The four entries below are the only words this module adds to the engine's output.
DIRECTION_WORD: dict[str, str] = {
    "overbilled": "the carrier billed a day that free time covers",
    "stated_versus_recomputed": "the stated free time end contradicts the carrier's own rule",
    "underbilled": "the carrier billed less than the rule allows",
}

#: The direction shown when the engine produces one this module does not have a word for.
#: It is honest about that rather than guessing, and a new direction should fail the
#: test that checks the table is complete rather than reaching here quietly.
UNKNOWN_DIRECTION = "a discrepancy the engine reported"


def direction_word(direction: Any) -> str:
    """The plain sentence for a direction, or a statement that we have no word for it."""
    key = getattr(direction, "value", direction)
    return DIRECTION_WORD.get(str(key), UNKNOWN_DIRECTION)


def _days(dates: Any) -> str:
    """The dates a discrepancy covers, in the data face, as a comma separated run."""
    values = sorted(value for value in dates if value is not None)
    if not values:
        return "no single day"
    return ", ".join(value.isoformat() for value in values)


def discrepancy_row(item: Discrepancy) -> str:
    """One discrepancy: which days, what happened, and the clause that says so."""
    return (
        '<li class="disc">'
        f'<span class="disc-days data">{esc(_days(item.dates))}</span>'
        f'<span class="disc-what">{esc(direction_word(item.direction))}</span>'
        f'<span class="disc-detail">{esc(item.detail)}</span>'
        f'<span class="disc-cite data">{esc(item.citation)}</span>'
        "</li>"
    )


def days_with_findings(day_count: Any) -> dict[str, list[Discrepancy]]:
    """Map each day to the discrepancies that touch it.

    A discrepancy can cover several days, as ``stated_versus_recomputed`` does, and a day
    can carry more than one. The grid uses this to mark the cells that have something to
    say, which is a different question from how many discrepancies exist.
    """
    found: dict[str, list[Discrepancy]] = {}
    if day_count is None:
        return found
    for item in day_count.discrepancies:
        for value in item.dates:
            if value is None:
                continue
            found.setdefault(value.isoformat(), []).append(item)
    return found


def reasoning_panel(day_count: Any) -> str:
    """The engine's reasoning for the days that have some, and nothing for those that do not.

    Rendered empty, not omitted, when there is nothing. An absent panel and a panel
    saying "nothing found" are different messages and only one of them is honest here:
    this is the engine's view of one invoice and it may be silent for reasons that are
    not good news, so the page says what it checked rather than implying all is well.
    """
    if day_count is None or not day_count.discrepancies:
        return ""
    rows = "".join(discrepancy_row(item) for item in day_count.discrepancies)
    return (
        '<section class="reason">'
        '<h2 class="reason-h">Why the engine says this</h2>'
        '<p class="reason-lede">Each line is the engine\'s own finding, with the clause '
        "it rests on. Nothing here is written by hand.</p>"
        f'<ul class="discs">{rows}</ul>'
        "</section>"
    )


DISCREPANCY_CSS = """
/* The reasoning panel. It sits directly under the grid because it is the answer to the
   question the grid raises. */
.reason { margin-top: var(--gap-loose); border-top: 1px solid var(--edge); padding-top: var(--gap); }
.reason-h {
  font-family: var(--font-stencil); font-weight: var(--weight-stencil);
  font-size: clamp(1.05rem, 2.4vw, 1.3rem); letter-spacing: -0.02em; margin: 0 0 0.4rem;
}
.reason-lede { color: var(--slate); max-width: var(--measure); margin: 0 0 var(--gap); }
.discs { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
.disc {
  display: grid; gap: 0.3rem;
  border: 1px solid var(--edge); border-left: 2px solid var(--signal);
  background: var(--deck); padding: 0.75rem 0.9rem;
}
.disc-days { color: var(--signal); font-size: 0.82rem; }
.disc-what { font-weight: 700; font-size: 0.92rem; }
.disc-detail { color: var(--chalk); max-width: var(--measure); }
/* The citation is the part a respondent checks, so it gets the data face and its own
   line rather than being appended to the prose. */
.disc-cite { color: var(--slate); font-size: 0.8rem; }
.disc-cite::before { content: '46 CFR '; color: var(--slate); }

/* A day that carries a discrepancy gets a marker in the grid. The marker is a shape and
   a border weight, not only a colour, so it survives a colour-blind reader. */
.day[data-flagged='true'] { border-color: var(--signal); }
.day[data-flagged='true'] .n::after {
  content: ''; display: inline-block; width: 0.34rem; height: 0.34rem;
  margin-left: 0.3rem; vertical-align: 0.55em;
  background: var(--signal); border-radius: 50%;
}
@media (max-width: 40rem) {
  .disc { border-left-width: 3px; }
}
"""


__all__ = [
    "DIRECTION_WORD",
    "DISCREPANCY_CSS",
    "UNKNOWN_DIRECTION",
    "days_with_findings",
    "direction_word",
    "discrepancy_row",
    "reasoning_panel",
]
