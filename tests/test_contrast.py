"""Contrast, computed rather than asserted as a hex value.

A palette is easy to write and hard to check by eye, and the failure mode is specific:
a colour that looked right against the page looked wrong against a card, because the
card is a different ground. Rust at 4.19:1 passed a glance on both.

So these tests do the arithmetic. They will still pass after a palette change, and they
will fail the moment a change puts a pair under the ratio it owes, which is the only
moment anyone needs to be told about.
"""

from __future__ import annotations

import re

import pytest

from quayline.web.design import BASE_CSS, MOTION, SPACE, TOKENS
from quayline.web.intake import GRID_CSS as GRID_CSS_SRC

#: The two grounds the palette sits on.
GROUND = {"quay": TOKENS["--quay"], "deck": TOKENS["--deck"]}


def _channel(value: int) -> float:
    srgb = value / 255
    return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    """Relative luminance, per the WCAG definition."""
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(foreground: str, background: str) -> float:
    """Contrast ratio between two hex colours, 1.0 to 21.0."""
    first, second = luminance(foreground), luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


#: Text colours, and what each one is used for. The ratio owed is 4.5 for body text.
TEXT_PAIRS = [
    ("--chalk", "body and heading text on the page ground"),
    ("--slate", "muted text, labels and the lede"),
    ("--sea", "the word free inside a day cell, on the cell surface"),
    ("--rust", "the word billed inside a day cell, on the cell surface"),
    ("--signal", "the disputed label and the excess figure"),
]

#: Non-text boundaries. WCAG asks 3:1 for the edge of a control someone has to find.
BOUNDARY_PAIRS = [("--edge-strong", "the border on a file input and a text field")]


@pytest.mark.parametrize(("token", "use"), TEXT_PAIRS)
@pytest.mark.parametrize("ground", sorted(GROUND))
def test_text_colour_clears_its_ratio_on_every_ground(token: str, use: str, ground: str) -> None:
    ratio = contrast(TOKENS[token], GROUND[ground])
    assert ratio >= 4.5, (
        f"{token} is {ratio:.2f}:1 on --{ground} for {use}, and needs 4.5:1. "
        f"Rust at #D2603A was 4.19:1 on --deck and failed exactly this way."
    )


@pytest.mark.parametrize(("token", "use"), BOUNDARY_PAIRS)
@pytest.mark.parametrize("ground", sorted(GROUND))
def test_control_boundary_clears_three_to_one(token: str, use: str, ground: str) -> None:
    ratio = contrast(TOKENS[token], GROUND[ground])
    assert ratio >= 3.0, f"{token} is {ratio:.2f}:1 on --{ground} for {use}, and needs 3:1"


def test_the_button_label_clears_its_ratio_in_both_states() -> None:
    """The submit button is quay on chalk, and quay on signal on hover.

    Hover is the state nobody looks at, which is why it is asserted here rather than
    left to the next person who changes the accent.
    """
    resting = contrast(TOKENS["--quay"], TOKENS["--chalk"])
    hovering = contrast(TOKENS["--quay"], TOKENS["--signal"])
    assert resting >= 4.5, f"the resting button label is {resting:.2f}:1"
    assert hovering >= 4.5, f"the hover button label is {hovering:.2f}:1"


def test_every_text_token_is_exercised_somewhere_in_the_shipped_css() -> None:
    """A token can pass a contrast test and still never reach the page.

    That is the quiet version of the same failure: a colour added for a state that is
    never rendered. Each one is asserted to be referenced by the CSS that ships.
    """
    css = BASE_CSS + GRID_CSS_SRC
    for token, use in TEXT_PAIRS:
        assert f"var({token})" in css, f"{token} is never used for {use}"


def test_no_colour_is_invented_in_the_component_stylesheet() -> None:
    """The palette is closed. A literal in the components is a decision nobody made."""
    css = BASE_CSS + GRID_CSS_SRC
    allowed = {value.upper() for value in TOKENS.values()}
    stray = [
        found for found in re.findall(r"#[0-9A-Fa-f]{3,8}\b", css) if found.upper() not in allowed
    ]
    assert not stray, f"the component stylesheet writes colours outside the table: {stray}"


def test_space_and_motion_never_hold_a_colour() -> None:
    """A colour landing in the wrong group is a colour no contrast check would see."""
    for name in (*SPACE, *MOTION):
        assert not name.startswith(("--sea", "--rust", "--signal", "--chalk")), name
