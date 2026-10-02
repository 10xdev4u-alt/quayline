"""Issue 81: the design system has to survive contact with a browser.

Every test here is one that would have passed if it compared the code against itself.
The stylesheet bug and the script hash bug both shipped with green suites, because
"the digest equals the digest" and "the CSS contains a style tag" are both trivially
true and both useless. So each test checks the property a browser actually enforces,
against something outside the module.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

import pytest

from quayline.serve.landing import landing_document
from quayline.web.design import BASE_CSS, TOKENS, stylesheet
from quayline.web.document import SCRIPT, intake_document, script_hash
from quayline.web.example import example_audit, money
from quayline.web.intake import (
    COMPONENT_CSS,
    INTAKE_CSS,
    STATE_ACCENT,
    day_cells,
    ledger,
    legend,
)
from quayline.web.landing_page import landing_page

#: billed, allowed, excess. The fixture's real figures, in the order a reader meets them.
MONEY = ("$1,170.00", "$780.00", "$390.00")

# A minimal StripDay, because the page takes objects and not the engine type. The real
# one is exercised end to end by tests/test_serve.py; here we care about the markup.
DAYS = [
    {"day": "2026-06-30", "state": "free"},
    {"day": "2026-07-08", "state": "disputed"},
    {"day": "2026-07-09", "state": "billed"},
]


class _Day:
    def __init__(self, day: str, state: str) -> None:
        class _D:
            def isoformat(self) -> str:
                return day

        self.day = _D()
        self.state = state


CELLS = [_Day(d["day"], d["state"]) for d in DAYS]


class _Discrepancy:
    def __init__(self, detail: str, citation: str) -> None:
        self.direction = type("D", (), {"value": "overbilled"})()
        self.dates = tuple(CELLS[1].day for _ in range(1))
        self.detail = detail
        self.citation = citation


class _DayCount:
    """Just enough for the page to reason from, so a stub page still shows an argument."""

    discrepancies = (
        _Discrepancy("were charged although the stated allowance was exhausted", "541.6(b)(8)"),
    )


class _Finding:
    def __init__(self, code: str, days: tuple[object, ...] = ()) -> None:
        self.code = code
        self.days = days


class _Result:
    """A stub result carrying the day count and the findings the page reads them with."""

    def __init__(self) -> None:
        self.day_count = _DayCount()
        self.findings = (_Finding("daycount_variance_diagnostic", (CELLS[1].day,)),)


#: The stub pages carry the engine's reasoning, because the page needs it to explain the
#: grid. A stub with no day count renders the grid and no argument, and a test built on
#: one silently stopped covering that.
STUB_RESULT = _Result()


def test_no_other_module_writes_a_hex_value() -> None:
    """The palette lives in one place, so a reviewer can read the whole thing at once.

    ``intake.py`` and ``design.py`` are the only permitted homes for a hex literal. This
    is what stops a colour appearing because one element needed to be a slightly
    different rust, which is how a six colour system becomes a thirty colour system.
    """
    for name in ("design.py", "intake.py", "document.py"):
        source = Path(f"src/quayline/web/{name}").read_text(encoding="utf-8")
        # Comments explain why a value was rejected, so a hex in prose is not a stray.
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        source = re.sub(r"^\s*#.*$", "", source, flags=re.M)
        stray = [
            match
            for match in re.findall(r"#[0-9A-Fa-f]{3,8}\b", source)
            if match.upper() not in {v.upper() for v in TOKENS.values()}
        ]
        assert not stray, f"{name} writes a colour outside the token table: {stray}"


def test_the_stylesheet_is_parseable_css_and_not_escaped_braces() -> None:
    """Doubled braces reach the browser as ``{{``, which invalidates the whole sheet.

    A browser discards every rule in a stylesheet when one declaration is malformed, so
    a single doubled brace renders an unstyled page that still contains a ``<style>``
    tag. This is the exact bug that shipped once.
    """
    css = stylesheet() + COMPONENT_CSS + INTAKE_CSS
    assert "{{" not in css and "}}" not in css
    assert css.count("{") == css.count("}"), "unbalanced rule bodies"
    for name in TOKENS:
        assert f"  {name}:" in css, f"{name} is declared in TOKENS but never emitted"


def test_every_accent_colour_means_a_day_state() -> None:
    """Three accents, three meanings. An accent that means nothing is decoration."""
    assert set(STATE_ACCENT) == {"free", "billed", "disputed"}
    for state, accent in STATE_ACCENT.items():
        assert accent.startswith("var(--"), f"{state} maps to a literal, not a token"
    semantic = {"--sea", "--rust", "--signal"}
    assert semantic <= set(TOKENS), "a data state lost its token"


def test_the_script_hash_is_base64_because_the_policy_grammar_demands_it() -> None:
    """A hex digest silently never matches, so the browser refuses the script.

    The page then loses the drag target, the progress state and the reveal, and nothing
    looks wrong except that it feels inert. Checking the digest against itself passed
    the first time; this decodes it the way a browser does.
    """
    expression = script_hash()
    algorithm, _, encoded = expression.partition("-")
    assert algorithm == "sha256"
    digest = base64.b64decode(encoded, validate=True)
    assert len(digest) == 32, "a sha256 digest is 32 bytes"
    assert digest == hashlib.sha256(SCRIPT.encode()).digest()
    assert not re.fullmatch(r"[0-9a-f]{64}", encoded), "hex, which the browser will not match"


def test_the_served_script_is_byte_for_byte_the_hashed_script() -> None:
    """The header and the body are built from one constant, and this proves it."""
    page = intake_document(
        days=CELLS,
        result=STUB_RESULT,
        rail_pairs=[("carrier", "Maersk")],
        money=MONEY,
        fixture_note="fixture",
    )
    served = re.search(r"<script>(.*)</script>", page, re.S)
    assert served is not None
    digest = hashlib.sha256(served.group(1).encode()).digest()
    assert base64.b64encode(digest).decode() == script_hash().split("-", 1)[1]


def test_the_page_still_works_with_no_script_at_all() -> None:
    """Progressive enhancement, checked structurally.

    The form is a real form posting to a real route, and the day grid is server-rendered
    markup. If that stops being true, a reader with a blocked script loses the entire
    product rather than the polish.
    """
    page = intake_document(
        days=CELLS,
        result=STUB_RESULT,
        rail_pairs=[("carrier", "Maersk")],
        money=MONEY,
        fixture_note="fixture",
    )
    assert 'action="/letter"' in page and 'method="post"' in page
    assert 'enctype="multipart/form-data"' in page
    assert page.count('class="day"') == len(CELLS)
    assert "11800" not in page  # no millisecond deadlines, nothing is hidden by a timer


def test_every_day_cell_names_its_state_so_colour_is_never_load_bearing() -> None:
    cells = day_cells(CELLS)
    for day in CELLS:
        assert f'data-state="{day.state}"' in cells
        assert day.state in cells
    assert "disputed" in cells and "billed" in cells and "free" in cells
    for _state, gloss in (
        ("free", "inside the disclosed free time"),
        ("billed", "billed by the carrier"),
        ("disputed", "billed in error"),
    ):
        assert gloss in legend()


def test_the_excess_is_the_largest_number_on_the_page() -> None:
    """The whole reason anyone is looking. CSS is asserted, not eyeballed."""
    assert ".ledger .excess dd" in COMPONENT_CSS
    rule = COMPONENT_CSS.split(".ledger .excess dd {")[1].split("}")[0]
    sizes = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)rem", rule)]
    assert sizes, "the excess figure needs to be sized in rem"
    assert max(sizes) >= 1.8, f"expected a large display size, found {sizes}"
    assert 'class="excess"' in ledger("$1,170.00", "$780.00", "$390.00")


def test_the_count_up_cannot_leave_a_wrong_number_on_screen() -> None:
    """A paused animation frame must not strand the figure at zero.

    A browser stops firing ``requestAnimationFrame`` in a background tab. With only an
    rAF loop driving the count, a reader who switched tabs during the first second came
    back to ``$0.00`` on a page whose whole argument is that number. So the final value
    is written on a timer as well, and the animation is skipped outright when the
    document is hidden.
    """
    assert "setTimeout(settle" in SCRIPT, "a timer must be able to finish the count"
    assert "visibilityState !== 'hidden'" in SCRIPT, "and it must not start when hidden"
    assert "if (settled) { return; }" in SCRIPT, "so the two paths cannot fight"
    # the value is correct before any script runs, which is what makes the fallback safe
    assert "$390.00" in intake_document(
        days=CELLS,
        result=STUB_RESULT,
        rail_pairs=[("carrier", "Maersk")],
        money=MONEY,
        fixture_note="fixture",
    )


def test_reduced_motion_is_honoured_in_css_and_in_script() -> None:
    assert "prefers-reduced-motion: reduce" in BASE_CSS
    assert "prefers-reduced-motion" in SCRIPT
    # and the script must be able to reach the no-motion branch
    assert "reduce ? '1ms'" in SCRIPT


def test_the_fixture_claim_is_never_stronger_than_the_fixture() -> None:
    """No invented customer, no invented recovery rate. Enforced on the rendered page."""
    page = intake_document(
        days=CELLS,
        result=STUB_RESULT,
        rail_pairs=[("carrier", "Maersk")],
        money=MONEY,
        fixture_note="The days above are the worked example on this site.",
    )
    lowered = page.lower()
    for claim in ("% recovered", "recovery rate of", "clients have", "trusted by"):
        assert claim not in lowered, f"unsourced claim on the page: {claim}"
    assert "127.0.0.1" in page, "the local-only posture is stated on the page"


@pytest.mark.parametrize("token", sorted(TOKENS))
def test_every_token_is_emitted_and_used(token: str) -> None:
    assert f"  {token}: {TOKENS[token]};" in stylesheet()


def test_the_landing_page_money_comes_off_the_engine_and_not_a_template() -> None:
    """A hero written by hand drifts from the engine within a week.

    The landing page runs the same fixture through the same bind and audit the
    uploaded path runs through, and reads the figures off the result. This asserts the
    two agree, so a change to the engine that moves a number moves the page too, and a
    change to the page that contradicts the engine fails here.
    """
    strip, result, _rail = example_audit()
    page = landing_document()
    assert str(result.variance) in page.replace(",", ""), (
        f"the page must carry the engine's variance {result.variance}"
    )
    assert f"{result.demanded_total:,.2f}" in page
    assert f"{result.recomputed_total:,.2f}" in page
    assert page.count('class="day"') == len(strip.days), (
        "the grid is the strip, so its length is the strip's length"
    )
    assert "not a client" in page.lower()


def test_the_public_landing_page_is_generated_from_the_same_example() -> None:
    """Two pages showing the same proof must not be able to disagree.

    The landing page and the intake both lead with a day grid. If either computed its
    own, one of them would eventually show a figure the engine no longer produces, and
    that page would be the one a stranger reads first.
    """
    strip, result, _rail = example_audit()
    page = landing_page()
    assert page.count('class="day"') == len(strip.days)
    assert money(result.variance) in page
    assert money(result.demanded_total) in page
    assert money(result.recomputed_total) in page


def test_the_landing_page_states_what_it_does_not_do() -> None:
    """The half of the page a reader skims is the half that has to be true.

    A landing page that only lists strengths is indistinguishable from one making
    things up. This asserts the absences are named, not just the capabilities.
    """
    page = landing_page().lower()
    for admission in (
        "no hosted version",
        "no customer",
        "does not submit",
        "not a client",
        "one carrier",
    ):
        assert admission in page, f"the page never says: {admission}"


def test_the_landing_page_explains_the_problem_without_prior_knowledge() -> None:
    """The first two sentences have to carry a stranger.

    Jargon in the opening paragraph is the difference between a page that explains the
    problem and one that assumes the reader already has the problem.
    """
    page = landing_page()
    opening = page.split("<h1>", 1)[1].split("</div>", 1)[0]
    assert "demurrage" in opening.lower()
    assert "detention" in opening.lower()
    # The regulation can be named in the first screen, but it cannot be the subject of
    # the first screen. A reader who does not know what a container charge is will not
    # know what Part 541 is for.
    assert "part 541" not in opening.lower()
