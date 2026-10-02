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

import base64
import dataclasses
import hashlib
import re
from pathlib import Path

import pytest

from quayline.cli.audit_render import resolve_disclosed
from quayline.engine.daycount import Direction
from quayline.serve.audit_runner import Findings, find_runner
from quayline.serve.landing import landing_document
from quayline.web import result as result_module
from quayline.web.design import stylesheet
from quayline.web.example import FIXTURE
from quayline.web.landing_page import landing_page
from quayline.web.reasoning import (
    DIRECTION_WORD,
    UNKNOWN_DIRECTION,
    days_with_findings,
    direction_word,
    reasoning_panel,
)
from quayline.web.render import generate
from quayline.web.result import result_page


def _result_page() -> str:
    """The result page, built from the fixture so it can be rendered in a test."""

    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    return result_page(findings)


#: Every page that renders components rather than prose. The result page is here for
#: the same reason the landing page was added: it emitted a button and a footer and
#: shipped no rule for either, because those rules turned out to be in the intake's
#: sheet and this page correctly does not carry the intake's form.
PAGES = {
    "intake": landing_document,
    "public landing": landing_page,
    "result": _result_page,
}


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


def test_the_committed_landing_page_matches_its_generator() -> None:
    """A generated page that is committed and stale is a page nobody regenerates.

    ``web/`` is committed so the site can be served from the repository, and that is
    exactly what makes a stale copy dangerous: the generator was fixed and the file
    visitors get was not. It happened once in this pull request, with a section
    rewritten in the generator and the committed file still carrying the old one.

    The specimen has the same exposure and is checked the same way below.
    """
    committed = Path("web/index.html")
    assert committed.is_file(), "run `make landing`; the committed page must exist"
    assert committed.read_text(encoding="utf-8") == landing_page(), (
        "web/index.html is out of date. Run `make landing` and commit the result. "
        "A committed generated page that no longer matches its generator is a page "
        "visitors get an older version of."
    )


def test_the_committed_specimen_matches_its_generator() -> None:
    """Same rule, same reason, for the page that was already here."""
    committed = Path("web/specimen.html")
    if not committed.is_file():
        pytest.skip("the specimen is generated on demand and is not committed here")
    assert committed.read_text(encoding="utf-8") == generate(), (
        "web/specimen.html is out of date. Run `make specimen` and commit the result."
    )


def test_the_result_page_is_rendered_from_structure_not_from_rendered_markup() -> None:
    """The page must not parse text another module already rendered.

    The previous version pulled the day strip back out of the finished letter by
    splitting on the literal ``<div class="strip">``. That made the page's correctness
    depend on the shape of markup ``render_strip`` happened to emit, and it fails
    silently rather than loudly.

    So the guard is structural: the runner returns objects, and the page never calls a
    renderer to get something to take apart.
    """

    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    assert isinstance(findings, Findings)
    assert findings.packet.sections, "the packet carries structure the page can read"
    assert findings.strip is not None and findings.strip.days

    source = Path(result_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("render_strip", "render(dispute_for", "partition('<div class=\"strip\"'>"):
        assert forbidden not in source, f"the result page must not use {forbidden}"


def test_a_blocked_ground_is_shown_as_blocked_rather_than_omitted() -> None:
    """A ground that vanishes is the failure this whole module exists to prevent.

    A carrier's respondent decides what they can concede. A ground silently missing
    from the packet is a claim lost without anyone being told, and it surfaces eleven
    weeks later when the claim is time barred.
    """

    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    page = result_page(findings)
    assert page.count('class="section"') == len(findings.packet.sections), (
        "one section per ground, so a blocked ground is still on the page"
    )
    blocked = [s for s in findings.packet.sections if s.blocked]
    assert blocked, "the fixture has a blocked ground, which is the case worth testing"
    for section in blocked:
        assert section.reason in page, "and the reason it is blocked is stated"
    assert "needs evidence" in page


def test_the_result_page_states_what_the_reader_must_do_next() -> None:
    """An empty screen is an invitation to act. This one has to tell them what."""

    page = result_page(find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark"))
    assert "What to do next" in page
    assert 'id="copy"' in page, "the letter can be copied in one action"
    # The fixture's packet is blocked, so the page must not tell the reader to send it.
    assert "cannot be sent yet" in page
    assert "Send the letter" not in page


def test_the_letter_is_readable_without_javascript() -> None:
    """The copy button is an enhancement over a textarea that already holds the text.

    A reader with scripting blocked must still be able to read the letter and select
    it by hand, which is what makes the button safe to offer at all.
    """

    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    page = result_page(findings)
    assert page.count("<textarea") == 1 and "readonly" in page
    assert "Dispute of charges" in page, "the whole letter is in the markup"
    # The script only ever copies. It never fetches and it never rewrites the page, so
    # the page without it is the same page.
    copy = result_module.COPY_SCRIPT
    assert "writeText" in copy
    for forbidden in ("fetch", "XMLHttpRequest", "innerHTML"):
        assert forbidden not in copy, f"the copy script must not use {forbidden}"


def test_the_copy_script_is_pinned_by_digest() -> None:
    """Same rule as the intake: one inline script, pinned by base64 digest."""
    page = result_page(find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark"))
    assert page.count("<script") == 1
    expression = result_module.script_hash()
    assert expression.startswith("sha256-")
    assert len(base64.b64decode(expression.split("-", 1)[1], validate=True)) == 32
    served = re.search(r"<script>(.*)</script>", page, re.S)
    assert served is not None
    digest = hashlib.sha256(served.group(1).encode()).digest()
    assert base64.b64encode(digest).decode() == expression.split("-", 1)[1]


def test_a_blocked_packet_is_never_told_to_send() -> None:
    """The failure this project exists to prevent, in the words a reader actually sees.

    ``packet.can_file`` is false whenever a ground has no evidence. A page that says
    "send this" anyway hands a client a packet their carrier's respondent will reject,
    and the reader cannot tell that from the page.
    """
    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    assert findings.packet.can_file is False, "the fixture is the blocked case"
    page = result_page(findings)
    assert "Send the letter" not in page
    assert "cannot be sent yet" in page
    assert "BLOCKED" in page, "and the letter itself marks the ground as blocked"


def test_a_clean_result_is_never_labelled_disputed() -> None:
    """No findings means nothing to dispute, whatever the arithmetic says.

    ``audit`` only records an amount finding for an overbill, so a variance can exist
    with no dispute behind it. The ledger's last row is labelled from the verdict rather
    than assumed.
    """
    real = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    assert real.result.findings, "the fixture is the disputed case"
    clean = dataclasses.replace(
        real,
        result=dataclasses.replace(real.result, findings=()),
        packet=dataclasses.replace(real.packet, sections=()),
    )
    page = result_page(clean)
    assert "Nothing to dispute" in page
    # The ledger row, not the day cell, which is labelled disputed in every result
    # because the fixture genuinely has a disputed day.
    assert "<dt>disputed</dt>" not in page, "no dispute is claimed, so no row is labelled one"
    assert "<dt>difference</dt>" in page


def test_the_engine_reasoning_is_shown_on_every_page_that_shows_the_grid() -> None:
    """A grid of coloured boxes with no argument behind it is an assertion.

    The engine computes a sentence per discrepancy and a clause to stand on. If a page
    shows the days and withholds that, the reader has to take the word on faith, which
    is the least credible posture available to a product whose value is that it is
    checkable.
    """
    for name, build in PAGES.items():
        page = build()
        assert page.count('class="day"') > 0, f"{name} shows a grid"
        assert 'class="reason"' in page, f"{name} shows a grid but not its reasoning"
        cites = re.findall(r'class="disc-cite[^"]*"[^>]*>([^<]+)<', page)
        assert cites, f"{name} cites nothing, so nothing on it can be checked"
        for cite in cites:
            assert re.search(r"541\.\d|\d+ U\.S\.C|46 CFR", cite), (
                f"{name} shows a citation that is not one: {cite!r}"
            )


def test_the_cited_sentences_are_the_engines_own() -> None:
    """Nothing on the panel may say more than ``Discrepancy.detail`` says.

    The temptation is to write "the carrier overcharged you" where the engine says "were
    charged although the stated allowance under 541.6(b)(3) exhausted on 2026-07-08".
    The second is the sentence a respondent can check, and paraphrasing it is exactly how
    an overclaim gets onto a page.
    """
    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    day_count = findings.result.day_count
    assert day_count is not None, "the fixture is the case that produces a day count"
    panel = reasoning_panel(day_count)
    for item in day_count.discrepancies:
        assert item.detail in panel, f"the engine's own words must survive: {item.detail}"
        assert item.citation in panel


def test_a_day_is_only_marked_when_the_engine_flagged_it() -> None:
    """No invented findings. A dot on a day is a claim that something is wrong there."""
    findings = find_runner(resolve_disclosed)(FIXTURE.read_bytes(), "Maersk", "newark")
    flagged = days_with_findings(findings.result.day_count)
    assert findings.strip is not None, "the fixture produces a strip"
    every = {day.day.isoformat() for day in findings.strip.days}
    assert flagged, "the fixture has discrepancies"
    assert set(flagged) <= every, "a flagged day has to be a day that exists"
    clean = [day for day in every if day not in flagged]
    assert clean, "and most days are not flagged"
    page = result_page(findings)
    assert page.count('data-flagged="true"') == len(flagged)
    assert page.count('data-flagged="false"') == len(every) - len(flagged)


def test_the_direction_table_has_no_gaps() -> None:
    """A new direction must fail here rather than fall through to a shrug.

    ``DIRECTION_WORD`` is the only place this module writes words of its own, so it is
    also the only place a new engine value could arrive unannounced.
    """
    seen = {member.value for member in Direction}
    missing = sorted(seen - set(DIRECTION_WORD))
    # ``clean`` is the absence of a discrepancy and never reaches a discrepancy row,
    # so it needs no wording.
    missing = [name for name in missing if name != "clean"]
    assert not missing, f"the engine can report {missing} and this module has no words"
    assert direction_word(Direction.OVERBILLED).startswith("the carrier billed")
    assert direction_word(object()) == UNKNOWN_DIRECTION


def test_the_reasoning_survives_with_scripting_blocked() -> None:
    """It is server-rendered markup, so there is nothing to block."""
    for name, build in PAGES.items():
        page = build()
        panel = page.split('class="reason"', 1)[1] if 'class="reason"' in page else ""
        assert "541.6(b)(8)" in panel or "541." in panel, f"{name} inlines the clause"
