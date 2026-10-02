"""Issue 81: the visual system, in one place.

Every colour, every measurement and every duration the site uses is written here once
and emitted as CSS custom properties. No other module is allowed to write a hex value.
That rule is what makes the design reviewable: a reviewer reads this file and knows the
whole palette, and if a colour shows up anywhere else, something has drifted.

The palette is not decorative. Three of the values are data states, and they mean
exactly one thing each:

``--sea``     a day that fell inside the disclosed free-time allowance
``--rust``    a day the carrier billed
``--signal``  the one day we say was billed in error, and the excess that follows

The remaining three are ground, surface and text. If a fourth accent ever appears, it
has to earn its place by meaning something a reader can act on.

A note on the stylesheet in this module
---------------------------------------

It is a plain string, not an f-string. An earlier version of this page was an f-string
with doubled braces so the CSS would survive ``str.format``, which is a trap: the
doubled braces reach the browser as ``{{``, that is not valid CSS, and a browser
discards an entire stylesheet over one malformed declaration. The page rendered
unstyled while every test passed. The tokens above are interpolated by a loop instead,
which cannot corrupt the hand-written part.
"""

from __future__ import annotations

from typing import Final

#: The palette. Six values: three surfaces, three data states.
TOKENS: Final[dict[str, str]] = {
    # Ground, surface, edge. A deep slate blue, the colour of water at a quay at night,
    # chosen over near-black so the rust and signal read as painted metal rather than
    # as glowing text on a void.
    "--quay": "#12171C",
    "--deck": "#1B2229",
    "--edge": "#2C353D",
    # Text. Not pure white. Terminal signage is never pure white and the glare of
    # #FFFFFF on a dark ground is what makes dashboards look cheap.
    "--chalk": "#EAEFF2",
    "--slate": "#8A9BA6",
    # The three data states. Rust and sea are also used as text inside a cell, so both
    # clear 4.5:1 against --deck, not just 3:1. Rust at #D2603A was 4.19 and failed.
    "--sea": "#4FA88B",
    "--rust": "#DC7048",
    "--signal": "#E8C55A",
    # The border on a control a person has to find and operate. --edge is a hairline
    # between static content and is allowed to be quiet; this one is the edge of an
    # interactive component, so it carries the 3:1 that WCAG asks of a control boundary.
    "--edge-strong": "#66747F",
}

#: Measured steps. A flat scale keeps vertical rhythm from being argued about.
SPACE: Final[dict[str, str]] = {
    "--gap-tight": "0.5rem",
    "--gap": "1rem",
    "--gap-loose": "2rem",
    "--pad": "clamp(1.25rem, 4vw, 3rem)",
    "--rail": "17rem",
    "--measure": "68ch",
}

#: Durations. Short on purpose. A finance tool that makes you wait to look at a number
#: is performing delay rather than progress.
MOTION: Final[dict[str, str]] = {
    "--beat": "140ms",
    "--stagger": "26ms",
    "--settle": "420ms",
    "--ease": "cubic-bezier(0.2, 0, 0.1, 1)",
}

#: The three stacks. Two families, both resolved from the system, because nothing is
#: fetched. The grotesque is set uppercase and tight for the stencil moments, which is
#: how container numbers and stencilled signage are set. The monospace carries every
#: amount and every date, because the money has to align in a column and shipping
#: documents are monospaced.
FONT_UI: Final[str] = (
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)
FONT_DATA: Final[str] = (
    "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
)


def root_variables() -> str:
    """The ``:root`` block. Built by a loop so no brace is ever hand-doubled.

    Family and weight are separate tokens. A weight inside the ``font-family`` value,
    as in ``font-family: 800 system-ui``, is not valid: the parser takes ``800`` as a
    family name, no such family exists, and the browser falls through to its default
    serif. That is how a heading meant to be a heavy grotesque rendered as Times.
    """
    lines = [
        f"  --font-stencil: {FONT_UI};",
        f"  --font-text: {FONT_UI};",
        f"  --font-data: {FONT_DATA};",
        "  --weight-stencil: 800;",
        "  --weight-label: 700;",
    ]
    for group in (TOKENS, SPACE, MOTION):
        for name, value in group.items():
            lines.append(f"  {name}: {value};")
    return ":root {\n" + "\n".join(lines) + "\n}"


BASE_CSS: Final[str] = """
*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--quay);
  color: var(--chalk);
  font-family: var(--font-text);
  font-size: clamp(15px, 1.6vw, 17px);
  line-height: 1.62;
  -webkit-font-smoothing: antialiased;
}

/* The stencil. Container numbers, section labels, anything that is a label on a
   physical object. Uppercase with tight tracking, because loose uppercase is the
   single clearest tell of a page nobody art-directed. */
.stencil {
  font-family: var(--font-stencil);
  font-weight: var(--weight-stencil);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.7rem;
  color: var(--slate);
}

/* Every number on the page. Tabular figures so columns line up to the pixel, and a
   slashed zero so a container number is never read as the letter O. */
.data {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums slashed-zero;
  font-feature-settings: 'tnum' 1, 'zero' 1;
}

h1 {
  font-family: var(--font-stencil);
  font-weight: var(--weight-stencil);
  font-size: clamp(1.9rem, 5vw, 3.1rem);
  line-height: 1.06;
  letter-spacing: -0.035em;
  text-wrap: balance;
  margin: 0 0 0.6rem;
}

a { color: var(--signal); text-decoration-thickness: 1px; text-underline-offset: 3px; }
a:hover { color: var(--chalk); }

/* Buttons live in the base sheet because two different pages have one and neither
   owns it. They were intake-only until the result page shipped and then came out
   unstyled, which is the same class of bug as a component emitted with no rule. */
button {
  background: var(--chalk);
  color: var(--quay);
  border: 1px solid var(--chalk);
  padding: 0.7rem 1.1rem;
  font-family: var(--font-stencil);
  font-weight: var(--weight-label);
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background var(--beat) var(--ease), color var(--beat) var(--ease),
    border-color var(--beat) var(--ease);
}
button:hover { background: var(--signal); border-color: var(--signal); color: var(--quay); }
button[disabled] { opacity: 0.5; cursor: progress; }

/* The page shell every single-column page uses. */
.wrap { max-width: 62rem; margin: 0 auto; padding: var(--pad); }

/* The footer every page carries. In the base sheet because three pages have one. */
.foot { border-top: 1px solid var(--edge); margin-top: var(--pad); padding-top: var(--gap);
  color: var(--slate); max-width: var(--measure); }
.foot p { margin: 0 0 0.7rem; }

/* Focus is a rectangle, not a glow. A glow on a dark ground disappears at the edges
   where it matters. */
:focus-visible {
  outline: 2px solid var(--signal);
  outline-offset: 3px;
  border-radius: 1px;
}

.sr {
  position: absolute;
  width: 1px; height: 1px;
  margin: -1px; padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
  }
}
"""


def stylesheet() -> str:
    """The full base stylesheet: variables then rules."""
    return root_variables() + BASE_CSS


__all__ = [
    "BASE_CSS",
    "FONT_DATA",
    "FONT_UI",
    "MOTION",
    "SPACE",
    "TOKENS",
    "root_variables",
    "stylesheet",
]
