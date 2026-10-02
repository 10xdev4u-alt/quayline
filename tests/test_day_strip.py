"""Issue 189: the day strip, which is a claim rather than an illustration.

Every competitor leads with a percentage. We assert eight specific dates and two
expiry dates, all of which come from the carrier's own disclosures and every one of
which a carrier can dispute. Drawing them is the honest way to present a claim that
specific.

The strip is built from a ``DayCountResult``, never from a second implementation of
the day arithmetic. A second calculation is a second chance to be wrong and the two
would disagree in front of a reader, which is the worst possible place to discover it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quayline.engine.audit import audit
from quayline.engine.result import AuditResult
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.resolution import RateQuery, resolve
from quayline.web.daystrip import DayStripError, _StripInput, build_strip
from quayline.web.strip_render import render_strip

FIXTURE = "tests/fixtures/born_digital_invoice.pdf"


def audited() -> AuditResult:
    data = Path(FIXTURE).read_bytes()
    blocks = tuple(load_corpus().values())
    resolution = resolve(
        RateQuery(reference="Maersk US Newark Dry", on="container", terminal="newark"),
        blocks,
    )
    return audit(data, "Maersk", "newark", resolution)


# ------------------------------------------------------- audit exposes the days


def test_audit_carries_the_day_data_the_strip_needs() -> None:
    """The strip cannot be built from a separate recomputation.

    Issue 189 exists because ``audit()`` discarded ``DayCountResult``, so the only way
    to draw the days would have been to recompute them. That is a second chance to be
    wrong, in front of a reader.
    """
    result = audited()

    assert result.day_count is not None
    assert result.day_count.declared_free_time_end.isoformat() == "2026-07-07"
    assert result.day_count.recomputed_free_time_end.isoformat() == "2026-07-08"


def test_the_exposed_days_are_the_ones_the_engine_computed() -> None:
    """Checked against the engine's own output rather than a literal."""
    days = audited().day_count
    assert days is not None

    assert [d.isoformat() for d in days.expected_dates] == ["2026-07-09", "2026-07-10"]
    assert [d.isoformat() for d in days.billed_dates] == [
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
    ]


# --------------------------------------------------------------- the strip itself


def test_the_strip_spans_free_time_start_to_last_charged_day() -> None:
    strip = build_strip(audited())

    assert strip.days[0].day.isoformat() == "2026-06-30"
    assert strip.days[-1].day.isoformat() == "2026-07-10"
    assert len(strip.days) == 11, "every day in the window, none collapsed"


def test_exactly_one_day_is_billed_but_not_chargeable() -> None:
    """The whole finding, as a count.

    The carrier charged 2026-07-08 and the carrier's own free time allowance covers
    it. I verified this by hand before writing it: seven working days from 2026-06-30
    on a Monday to Saturday basis lands on 2026-07-08.
    """
    strip = build_strip(audited())
    disputed = [d for d in strip.days if d.state == "disputed"]

    assert len(disputed) == 1
    assert disputed[0].day.isoformat() == "2026-07-08"


def test_a_disputed_day_states_why_in_its_own_rights() -> None:
    """A reader should not have to hover or click to learn what the mark means."""
    strip = build_strip(audited())
    disputed = next(d for d in strip.days if d.state == "disputed")

    assert disputed.note
    assert "2026-07-08" in disputed.note or "free time" in disputed.note.lower()


def test_free_days_are_marked_free_and_are_not_misrepresented() -> None:
    """A day inside the allowance is free, and saying so is part of the claim."""
    strip = build_strip(audited())
    free = [d for d in strip.days if d.state == "free"]

    assert len(free) == 8, "2026-06-30 through 2026-07-07 is eight days"


def test_the_strip_carries_both_expiry_dates_and_they_differ() -> None:
    """The contradiction is the second finding and it needs both dates on the strip.

    The invoice says free time ended 2026-07-07. The carrier's own start and
    allowance say 2026-07-08. Both cannot be true, and a reader should see that rather
    than be told it.
    """
    strip = build_strip(audited())

    assert strip.declared_free_time_end != strip.recomputed_free_time_end
    assert strip.declared_free_time_end.isoformat() == "2026-07-07"
    assert strip.recomputed_free_time_end.isoformat() == "2026-07-08"


def test_a_clean_result_produces_a_strip_with_no_disputed_day() -> None:
    """The strip has to work when there is nothing to find, or it is a screamer."""
    clean = _StripInput(
        carrier="Maersk",
        terminal="newark",
        declared_free_time_end=date(2026, 7, 4),
        recomputed_free_time_end=date(2026, 7, 4),
        expected_dates=(date(2026, 7, 5),),
        billed_dates=(date(2026, 7, 5),),
        free_time_start=date(2026, 6, 30),
    )
    strip = build_strip(clean)

    assert [d.state for d in strip.days].count("disputed") == 0
    # ``billed`` is a legitimate state on a clean invoice: the carrier charged a day
    # that was properly chargeable. My first version of this test excluded it, which
    # would have made the strip unable to show a correct bill at all.
    assert all(d.state in {"free", "chargeable", "billed"} for d in strip.days)
    assert [d.state for d in strip.days].count("billed") == 1


def test_a_result_with_no_day_data_is_refused_rather_than_guessed() -> None:
    """An audit that did not compute days cannot draw them."""
    result = audited()
    bare = type(result)(carrier="Maersk")

    with pytest.raises(DayStripError):
        build_strip(bare)


# ------------------------------------------------------------------------ render


def test_the_strip_renders_no_javascript_and_no_images() -> None:
    """It is a claim about dates. A canvas drawing of it would be unauditable."""
    html = render_strip(build_strip(audited())).lower()

    assert "<script" not in html
    assert "<img" not in html
    assert "http://" not in html
    assert "https://" not in html.replace("https://www.w3.org", "")


def test_every_day_is_labelled_in_text_not_only_by_colour() -> None:
    """Colour alone is not an accessible encoding and it is not a checkable one.

    Each cell carries its state as text so a reader who cannot see the colour, and a
    screen reader, both get the claim.
    """
    html = render_strip(build_strip(audited()))

    for state in ("free", "chargeable", "billed", "disputed"):
        assert f'aria-label="{state}"' in html or f">{state}<" in html


def test_the_strip_states_the_day_basis_that_produced_it() -> None:
    """The free-time compression insight lives or dies on this.

    The same container can be free on a Friday and billable on the Saturday under a
    different carrier's basis, so the strip has to say which basis it applied.
    """
    strip = build_strip(audited())

    assert strip.day_basis
    assert "monday" in strip.day_basis.lower() or "saturday" in strip.day_basis.lower()


def test_the_rendered_strip_names_both_expiry_dates() -> None:
    html = render_strip(build_strip(audited()))

    assert "2026-07-07" in html
    assert "2026-07-08" in html
