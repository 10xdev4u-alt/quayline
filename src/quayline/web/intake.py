"""Issue 81: the intake page. The day grid is the hero, not a form.

The empty state shows the real fixture: Maersk, Newark dry, the eleven days the engine
actually computed, and the 390.00 it actually found. A visitor sees the whole argument
this product makes and the exact shape of its evidence before handing a file to a
process they cannot see. It is labelled as the fixture it is.

The grid is the product. A demurrage dispute is a calendar argument, so a calendar is
what leads. A carrier says three days were owed, the disclosed rule allows two, and
the entire product exists to point at the third.

State is carried by the cell's label and its border, not by colour alone. Rust, sea and
signal are three accents with three meanings, but a reader who cannot separate rust from
sea still gets the answer from the word in the cell and the legend under the grid.
"""

from __future__ import annotations

import html
from typing import Any

from quayline.web.design import stylesheet

#: Which accent each engine day state maps to. This is the only place the mapping lives.
STATE_ACCENT: dict[str, str] = {
    "free": "var(--sea)",
    "billed": "var(--rust)",
    "disputed": "var(--signal)",
}

#: Plain words for the same three states, used in the cell and the legend.
STATE_WORD: dict[str, str] = {
    "free": "free",
    "billed": "billed",
    "disputed": "disputed",
}

GRID_CSS = """
.manifest {
  display: grid;
  grid-template-columns: var(--rail) minmax(0, 1fr);
  gap: var(--gap-loose);
  align-items: start;
  max-width: 78rem;
  margin: 0 auto;
  padding: var(--pad);
}

/* The rail is the SHIPPER / CONSIGNEE block of a bill of lading: bordered, labelled,
   stacked. Every value in it comes off the document or out of the engine. */
.rail { border: 1px solid var(--edge); background: var(--deck); }
.rail dl { margin: 0; }
.rail div { padding: 0.7rem 0.9rem; border-bottom: 1px solid var(--edge); }
.rail div:last-child { border-bottom: 0; }
.rail dt { margin: 0 0 0.2rem; }
.rail dd { margin: 0; font-size: 0.95rem; word-break: break-word; }

.head {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: var(--gap-tight);
  border-bottom: 1px solid var(--edge);
}

.lede { max-width: var(--measure); color: var(--slate); margin: 0 0 var(--gap-loose); }

/* The grid. One cell per day, laid out as a track that wraps. Each cell states its own
   day number and date, so the grid is readable with the colour stripped out. */
.days { display: grid; grid-template-columns: repeat(auto-fit, minmax(4.1rem, 1fr)); gap: 0.4rem; }
.day {
  border: 1px solid var(--edge);
  background: var(--deck);
  padding: 0.55rem 0.6rem;
  min-height: 5.4rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.3rem;
}
.day .n { font-size: 1.5rem; line-height: 1; }
.day .when { font-size: 0.72rem; color: var(--slate); }
.day .state {
  font-size: 0.66rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}
.day[data-state='free'] { border-color: color-mix(in srgb, var(--sea) 55%, var(--edge)); }
.day[data-state='free'] .state { color: var(--sea); }
.day[data-state='billed'] { border-color: color-mix(in srgb, var(--rust) 55%, var(--edge)); }
.day[data-state='billed'] .state { color: var(--rust); }
/* The disputed day is the one the whole page is about. It gets the high-vis treatment
   terminals paint on anything that must not be run over. */
.day[data-state='disputed'] {
  border-color: var(--signal);
  box-shadow: inset 0 0 0 1px var(--signal);
}
.day[data-state='disputed'] .state { color: var(--signal); }

.legend { display: flex; flex-wrap: wrap; gap: var(--gap); margin-top: 0.6rem; }
.legend span { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; color: var(--slate); }
.legend i { width: 0.7rem; height: 0.7rem; border: 1px solid; display: inline-block; }

/* The money. The excess is the largest number on the page because it is the reason
   anyone is here. */
.ledger { display: grid; gap: 0.15rem; margin: var(--gap-loose) 0 0; padding: 0; border: 0; }
.ledger div { display: flex; justify-content: space-between; gap: var(--gap); padding: 0.5rem 0; border-bottom: 1px solid var(--edge); }
.ledger dt { margin: 0; color: var(--slate); }
.ledger dd { margin: 0; font-size: 1.02rem; }
.ledger .excess { border-bottom: 0; padding-top: 0.9rem; }
.ledger .excess dt { color: var(--signal); font-weight: 700; }
.ledger .excess dd { font-size: clamp(1.8rem, 6vw, 2.9rem); color: var(--signal); line-height: 1; }

.drop {
  margin-top: var(--gap-loose);
  border: 1px dashed var(--edge);
  background: var(--deck);
  padding: var(--gap-loose) var(--gap);
  text-align: center;
  transition: border-color var(--beat) var(--ease), background var(--beat) var(--ease);
}
.drop[data-over='true'] { border-color: var(--signal); background: color-mix(in srgb, var(--signal) 8%, var(--deck)); }
.drop label { display: block; max-width: var(--measure); margin: 0 auto; color: var(--slate); }

/* The file input is the one control a browser draws for itself, and its default is a
   grey chrome button that looks broken on a dark ground. The button is restyled and the
   filename is given the data face so a carrier invoice number lines up. */
.drop input[type='file'] {
  display: block;
  width: 100%;
  margin: var(--gap) 0 0;
  padding: 0.5rem;
  border: 1px solid var(--edge);
  background: var(--quay);
  color: var(--slate);
  font-family: var(--font-data);
  font-size: 0.82rem;
}
.drop input[type='file']::file-selector-button {
  margin-right: 0.7rem;
  padding: 0.5rem 0.9rem;
  border: 1px solid var(--edge);
  background: var(--deck);
  color: var(--chalk);
  font-family: var(--font-stencil);
  font-weight: var(--weight-label);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}
.drop input[type='file']::file-selector-button:hover { border-color: var(--signal); color: var(--signal); }

.controls { display: flex; flex-wrap: wrap; gap: var(--gap); margin-top: var(--gap); text-align: left; }
.controls > div { flex: 1 1 9rem; min-width: 0; }
.controls label { display: block; margin-bottom: 0.3rem; }
.controls input {
  width: 100%;
  background: var(--quay);
  border: 1px solid var(--edge);
  color: var(--chalk);
  padding: 0.6rem 0.7rem;
  font-family: var(--font-data);
  font-size: 0.95rem;
}
.controls input:hover { border-color: var(--slate); }
button {
  flex: 1 1 100%;
  background: var(--chalk);
  color: var(--quay);
  border: 0;
  padding: 0.85rem 1rem;
  font: 800 0.82rem/1 var(--font-stencil);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background var(--beat) var(--ease);
}
button:hover { background: var(--signal); }
button[disabled] { opacity: 0.5; cursor: progress; }

.foot { grid-column: 1 / -1; border-top: 1px solid var(--edge); margin-top: var(--pad); padding-top: var(--gap); color: var(--slate); max-width: var(--measure); }
.foot p { margin: 0 0 0.7rem; }

@media (max-width: 56rem) {
  .manifest { grid-template-columns: minmax(0, 1fr); }
  .rail { order: 2; }
  .head, .lede, .days, .ledger, .drop, .foot { grid-column: 1; }
}
@media (max-width: 24rem) {
  .days { grid-template-columns: repeat(auto-fit, minmax(4.4rem, 1fr)); }
  .day { min-height: 4.6rem; padding: 0.45rem; }
}
"""


def esc(value: object) -> str:
    """Escape for a text node or a double-quoted attribute."""
    return html.escape(str(value), quote=True)


def day_cells(days: Any) -> str:
    """One cell per day. The number, the date, and the state in words."""
    cells = []
    for index, day in enumerate(days, start=1):
        state = day.state
        accent = STATE_ACCENT.get(state, "var(--slate)")
        cells.append(
            f'<div class="day" data-state="{esc(state)}" '
            f'style="--accent:{accent}">'
            f'<span class="n data">{esc(index)}</span>'
            f'<span class="when data">{esc(day.day.isoformat()[5:])}</span>'
            f'<span class="state">{esc(STATE_WORD.get(state, state))}</span>'
            f"</div>"
        )
    return '<div class="days">' + "".join(cells) + "</div>"


def legend() -> str:
    """The key. Names every state, so the grid reads without relying on colour."""
    items = [
        ("free", "inside the disclosed free time"),
        ("billed", "billed by the carrier"),
        ("disputed", "billed in error, this is the day"),
    ]
    out = []
    for state, gloss in items:
        out.append(
            f'<span><i style="border-color:{STATE_ACCENT[state]}"></i>'
            f"<b>{esc(state)}</b> {esc(gloss)}</span>"
        )
    return '<p class="legend">' + "".join(out) + "</p>"


def rail(pairs: list[tuple[str, str]]) -> str:
    """The manifest rail. Label above value, the way a form reads."""
    rows = "".join(
        f'<div><dt class="stencil">{esc(k)}</dt><dd class="data">{esc(v)}</dd></div>'
        for k, v in pairs
    )
    return f'<aside class="rail"><dl>{rows}</dl></aside>'


def ledger(billed: str, allowed: str, excess: str) -> str:
    """The three figures. The excess is set largest because it is the point."""
    return (
        '<dl class="ledger">'
        f'<div><dt>billed by the carrier</dt><dd class="data">{esc(billed)}</dd></div>'
        f'<div><dt>allowed by the disclosed rule</dt><dd class="data">{esc(allowed)}</dd></div>'
        f'<div class="excess"><dt>disputed</dt><dd class="data">{esc(excess)}</dd></div>'
        "</dl>"
    )


__all__ = [
    "GRID_CSS",
    "STATE_ACCENT",
    "STATE_WORD",
    "day_cells",
    "esc",
    "ledger",
    "legend",
    "rail",
    "stylesheet",
]
