"""A component a page emits has to have a rule in that page's stylesheet.

This has now gone wrong twice on this project, in two different modules, and both times
the tests were green.

The first was a stylesheet whose rules were all invalid, so the browser dropped every
one of them while a test confirmed a ``<style>`` tag was present. The second was a
landing page that emitted the day grid, the rail, the legend and the ledger but
assembled its CSS from the base sheet and its own additions, without the sheet those
four components are styled in. The page rendered as unstyled lists of numbers, and the
only thing that caught it was looking at a screenshot.

So this file is narrow on purpose. It does not check that the CSS is well formed, which
``test_design`` covers. It checks the join: for every class a page puts in its markup,
is there a rule for it in the CSS that page actually ships.
"""

from __future__ import annotations

import re

import pytest

from quayline.serve.landing import landing_document
from quayline.web.design import stylesheet
from quayline.web.landing_page import landing_page

#: The two pages that render components rather than prose.
PAGES = {"intake": landing_document, "public landing": landing_page}


def _classes(markup: str) -> set[str]:
    found: set[str] = set()
    for attribute in re.findall(r'class="([^"]+)"', markup):
        found.update(attribute.split())
    return found


def _stylesheet(page: str) -> str:
    match = re.search(r"<style>(.*)</style>", page, re.S)
    assert match is not None, "a page that emits components must ship a stylesheet"
    return match.group(1)


def _own_css(page: str) -> str:
    """The page's stylesheet minus the shared base sheet.

    The base is part of the system and both pages carry it by design. What is specific
    to a page is everything after it, and that is the part under test here.
    """
    return _stylesheet(page).replace(stylesheet(), "")


def _styled(classes: set[str], css: str) -> set[str]:
    """Which of these class names the stylesheet has a selector for."""
    selectors = css.replace("\n", " ")
    return {name for name in classes if re.search(rf"\.{re.escape(name)}\b", selectors)}


@pytest.mark.parametrize("name", sorted(PAGES))
def test_every_class_a_page_emits_is_styled_by_that_page(name: str) -> None:
    page = PAGES[name]()
    css = _stylesheet(page)
    emitted = _classes(page)
    unstyled = sorted(emitted - _styled(emitted, css))
    assert not unstyled, (
        f"the {name} page emits {unstyled} but ships no rule for "
        f"{'them' if len(unstyled) > 1 else 'it'}. The markup is there and the CSS is "
        f"not, so it renders as unstyled text."
    )


@pytest.mark.parametrize("name", sorted(PAGES))
def test_a_page_ships_no_other_page_private_rules(name: str) -> None:
    """The other half of the join, and the one that keeps the pages honest.

    A page that pulls in a whole stylesheet it uses three rules from is carrying dead
    weight, and it is carrying it silently. The landing page is the case that matters:
    it borrows the rail, the day grid, the legend and the ledger from the intake, and it
    should be borrowing exactly those and nothing of the intake's form.

    Private means: emitted by the other page and not by this one. The components both
    pages show are not private, and the base sheet is shared by contract, so neither
    counts against a page.
    """
    mine_classes = _classes(PAGES[name]())
    my_css = _own_css(PAGES[name]())
    for other, build in PAGES.items():
        if other == name:
            continue
        private = sorted(_classes(build()) - mine_classes)
        carried = sorted(c for c in private if re.search(rf"\.{re.escape(c)}\b", my_css))
        assert not carried, (
            f"the {name} page ships rules for {carried}, which belong to the {other} "
            f"page and which it never emits"
        )


@pytest.mark.parametrize("name", sorted(PAGES))
def test_a_page_balances_its_tags(name: str) -> None:
    """Unclosed tags are invisible in a string-built page and obvious in a browser.

    These pages are assembled by concatenating fragments, so a missing close is a real
    and easy mistake, and it would silently swallow the rest of the layout.
    """
    page = PAGES[name]()
    for tag in ("div", "main", "aside", "header", "footer", "form", "dl", "ul", "p"):
        opened = len(re.findall(rf"<{tag}\b", page))
        closed = len(re.findall(rf"</{tag}>", page))
        assert opened == closed, f"the {name} page has {opened} <{tag}> and {closed} </{tag}>"
    assert page.count("<!doctype html>") == 1
    assert page.rstrip().endswith("</html>")


def test_the_two_pages_show_the_same_number_of_days() -> None:
    """The visible proof, checked across both pages rather than inside one.

    This is the assertion that would have caught the missing grid CSS on sight, because
    a page whose grid has no rule has a different shape from one whose grid has one.
    """
    intake, landing = landing_document(), landing_page()
    assert intake.count('class="day"') == landing.count('class="day"')
    assert _styled({"day"}, _stylesheet(intake))
    assert _styled({"day"}, _stylesheet(landing))
