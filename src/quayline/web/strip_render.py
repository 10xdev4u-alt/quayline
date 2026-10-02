"""Issue 189: drawing the strip.

The design brief this file answers

A competitor shows a percentage. A percentage cannot be disputed. We show a calendar
strip where every cell is a claim about a specific day, and the reader can check all of
them against the invoice sitting next to them.

Three rules that decide everything below

**Colour is never the only encoding.** Every cell carries its state as text. A reader
who cannot see the amber still reads "disputed", and so does a screen reader. That is
an accessibility requirement and it is also the honest one: a mark only a colour can
express is a mark nobody can verify.

**No JavaScript, no images.** A canvas rendering of a legal claim cannot be inspected.
This is semantic HTML and CSS, so the DOM is the claim.

**The disputed day is the loudest thing on the page and everything else recedes.**
Not by shouting, but by weight: it carries a border, a fill and a marker, and it is the
only cell with all three. A reader scanning the strip sees one amber cell and stops.
That is the entire argument, delivered in half a second.

Sizing at 390px

The strip has to work on a phone because a freight person reads this standing up in a
yard. It wraps to a grid, days stay readable, and the disputed cell keeps its full
weight at every width. It does not become a horizontal scroll, because a strip you
have to pan is a strip nobody reads.
"""

from __future__ import annotations

from html import escape

from quayline.web.daystrip import BILLED, CHARGEABLE, DISPUTED, FREE, DayStrip, StripDay

_STYLE = """
.strip { margin:1.5rem 0; --free:#c9d4cc; --chg:#8a9ba8; --bill:#3f5a6b;
  --disp:#b3541e; --disp-bg:#fdf0e6; --ink:#1a1a1a; --muted:#5c5c5c; --rule:#d8d8d8; }
.strip h3 { font-size:1rem; margin:0 0 .5rem; letter-spacing:-.01em; }
.ends { display:flex; flex-wrap:wrap; gap:.4rem 1.25rem; font-size:.82rem;
  color:var(--muted); margin:0 0 .75rem; padding:0; list-style:none; }
.ends b { color:var(--ink); font-weight:600; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(5rem,1fr));
  gap:3px; list-style:none; padding:0; margin:0; }
.day { border:1px solid var(--rule); border-radius:.2rem; padding:.4rem .45rem;
  background:#fff; display:flex; flex-direction:column; gap:.1rem; min-height:4.6rem;
  min-width:0; }
.day .d { font:600 1rem/1.1 ui-monospace,SFMono-Regular,Menlo,monospace;
  color:var(--ink); letter-spacing:-.02em; }
.day .w { font-size:.7rem; letter-spacing:.05em; text-transform:uppercase;
  color:var(--muted); }
/* Pinned to the bottom of every cell rather than flowing after the label, so a cell
   whose state text wraps to two lines keeps the same baseline as its neighbours and
   the row reads as one strip instead of a ragged set of boxes. */
.day .s { font-size:.75rem; font-weight:600; margin-top:auto;
  overflow-wrap:anywhere; }
.day.s-free { background:#f4f7f4; } .day.s-free .s { color:#4a6b53; }
.day.s-chargeable { background:#f2f5f7; border-style:dashed; }
.day.s-chargeable .s { color:#5a6d78; }
.day.s-billed { background:#eef2f5; border-color:#9fb0bc; }
.day.s-billed .s { color:var(--bill); }
.day.s-disputed { background:var(--disp-bg); border:2px solid var(--disp);
  box-shadow:inset 0 0 0 1px var(--disp-bg); }
.day.s-disputed .s { color:var(--disp); }
.day.s-disputed .mark { font-size:.66rem; color:var(--disp); font-weight:600;
  letter-spacing:.02em; margin-top:.15rem; }
.legend { display:flex; flex-wrap:wrap; gap:.35rem .9rem; font-size:.78rem;
  margin-top:.9rem; padding:0; list-style:none; color:var(--muted); }
.legend li { display:flex; align-items:center; gap:.3rem; }
.sw { width:.85rem; height:.85rem; border-radius:.15rem; border:1px solid var(--rule);
  display:inline-block; }
.sw.s-free { background:#f4f7f4; } .sw.s-chargeable { background:#f2f5f7;
  border-style:dashed; } .sw.s-billed { background:#eef2f5; border-color:#9fb0bc; }
.sw.s-disputed { background:var(--disp-bg); border:2px solid var(--disp); }
.note { font-size:.82rem; color:var(--muted); margin:.75rem 0 0; max-width:38rem; }
.note b { color:var(--ink); }
@media (prefers-color-scheme: dark) {
  .strip { --free:#2a3a30; --chg:#2a3843; --bill:#8aa8bd; --disp:#e08a4e;
    --disp-bg:#2b1a10; --ink:#e8e8e6; --muted:#9a9a97; --rule:#333; }
  .day, .ends b, .note b { background:#1c1c20; }
  .day.s-free { background:#182219; } .day.s-free .s { color:#8fc0a0; }
  .day.s-chargeable { background:#1a1f24; } .day.s-chargeable .s { color:#93a8b6; }
  .day.s-billed { background:#1d2830; } .day.s-billed .s { color:var(--bill); }
  .day.s-disputed .s, .day.s-disputed .mark { color:var(--disp); }
  .sw { border-color:#444; }
  .sw.s-free { background:#182219; } .sw.s-chargeable { background:#1a1f24; }
  .sw.s-billed { background:#1d2830; border-color:#4a5c68; }
}
"""

_WEEKDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTH = (
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

#: Short label per state. The text is the encoding, not a caption for the colour.
_STATE_TEXT = {
    FREE: "free",
    CHARGEABLE: "chargeable",
    BILLED: "billed",
    DISPUTED: "disputed",
}


def _label(day: StripDay) -> str:
    d = day.day
    return f"{d.day} {_MONTH[d.month]} {d.strftime('%a')}"


def _cell(day: StripDay) -> str:
    mark = '<span class="mark">&#9650; charged anyway</span>' if day.is_disputed else ""
    return (
        f'      <li class="day s-{day.state}" aria-label="{_STATE_TEXT[day.state]}"'
        f' title="{escape(day.note)}">'
        f'<span class="d">{escape(str(day.day.day))}</span>'
        f'<span class="w">{escape(_WEEKDAY[day.day.weekday()])}</span>'
        f'<span class="s">{escape(_STATE_TEXT[day.state])}</span>'
        f"{mark}"
        "</li>"
    )


def _legend() -> str:
    return "".join(
        f'<li><span class="sw s-{state}"></span>{text}</li>' for state, text in _STATE_TEXT.items()
    )


def render_strip(strip: DayStrip) -> str:
    """The strip, as one self-contained fragment.

    A fragment rather than a whole document because the specimen page embeds it, and a
    second full page inside a page is a document nested in a document.
    """
    end_row = (
        '<ul class="ends">'
        f"<li>carrier states free time ends <b>{strip.declared_free_time_end.isoformat()}"
        "</b></li>"
        f"<li>carrier inputs give <b>{strip.recomputed_free_time_end.isoformat()}</b></li>"
        f"<li>day basis <b>{escape(strip.day_basis)}</b></li>"
        "</ul>"
    )

    if strip.clean:
        conclusion = (
            '<p class="note">Every day the carrier charged falls inside the '
            "allowance their own start date and free time give. There is nothing "
            "here to dispute.</p>"
        )
    else:
        days = ", ".join(d.day.isoformat() for d in strip.disputed)
        conclusion = (
            f'<p class="note"><b>{days}</b> was charged while free time still covered '
            f"it. Free time runs to {strip.recomputed_free_time_end.isoformat()} on "
            f"the carrier's own {escape(strip.day_basis)} basis, so the carrier "
            f"disclosed a free time end of "
            f"{strip.declared_free_time_end.isoformat()} that their own start date and "
            "allowance do not support.</p>"
        )

    return f"""<div class="strip">
  <style>{_STYLE}</style>
  <h3>Day by day, from the disclosures</h3>
  {end_row}
  <ul class="grid">
{chr(10).join(_cell(d) for d in strip.days)}
  </ul>
  <ul class="legend">{_legend()}</ul>
  {conclusion}
</div>
"""


__all__ = ["render_strip"]
