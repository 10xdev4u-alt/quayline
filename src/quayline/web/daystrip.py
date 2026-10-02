"""Issue 189: the day strip, which is a claim rather than an illustration.

Every competitor in this category leads with a percentage. A percentage cannot be
disputed, which is why it is safe to print and also why it is worthless. This asserts
eight specific dates and two expiry dates, every one of which a carrier can answer,
and every one of which comes from the carrier's own disclosures.

The one rule that shapes this module

**The strip is drawn from a ``DayCountResult`` the engine already computed.** It is
never recomputed here. A second implementation of the day arithmetic would be a second
chance to disagree with the engine, and the disagreement would appear in front of a
reader as a rendering bug rather than as the finding it actually is.

That is why ``AuditResult.day_count`` exists. ``audit()`` used to discard the day
result, which meant the only way to draw these days would have been to derive them
again, and that is exactly the bug the repository already made once with the fixture
that stated four days of free time from June 30 with an end date of July 7.

Four states, and the fourth is the point

``free``          inside the recomputed allowance
``chargeable``    after the allowance, so billable
``billed``        chargeable and the carrier charged it
``disputed``      the carrier charged it and free time covers it

Every competitor draws a chart of their own conclusion. This draws the carrier's own
disclosures with our arithmetic on top, so the reader can check it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from quayline.calendars.day_basis import RULES
from quayline.engine.result import AuditResult

FREE = "free"
CHARGEABLE = "chargeable"
BILLED = "billed"
DISPUTED = "disputed"


class DayStripError(RuntimeError):
    """The strip cannot be drawn, and says which input was missing."""


@dataclass(frozen=True, slots=True)
class StripDay:
    """One day, and everything the engine concluded about it."""

    day: date
    state: str
    note: str = ""

    @property
    def is_disputed(self) -> bool:
        return self.state == DISPUTED


@dataclass(frozen=True, slots=True)
class _StripInput:
    """The minimum the strip needs, so a caller can draw one without an audit.

    Lets the clean case be tested directly, and keeps this module honest about which
    four values actually matter.
    """

    carrier: str
    terminal: str
    declared_free_time_end: date
    recomputed_free_time_end: date
    expected_dates: tuple[date, ...]
    billed_dates: tuple[date, ...]
    free_time_start: date


@dataclass(frozen=True, slots=True)
class DayStrip:
    """Every day in the window, and the two dates that frame it."""

    carrier: str
    terminal: str
    day_basis: str
    declared_free_time_end: date
    recomputed_free_time_end: date
    days: tuple[StripDay, ...]

    @property
    def disputed(self) -> tuple[StripDay, ...]:
        return tuple(d for d in self.days if d.is_disputed)

    @property
    def clean(self) -> bool:
        return not self.disputed

    @property
    def free_time_end_disagrees(self) -> bool:
        return self.declared_free_time_end != self.recomputed_free_time_end


def _classify(day: date, source: _StripInput) -> StripDay:
    """What the engine says about one day.

    A day is free when the recomputed allowance still covers it. The carrier's
    *stated* end does not decide this, and using it would be the mistake the whole
    product is built against: believing the carrier's conclusion instead of their
    inputs.
    """
    if day <= source.recomputed_free_time_end:
        if day in source.billed_dates:
            return StripDay(
                day=day,
                state=DISPUTED,
                note=(
                    f"the carrier billed this day and free time covers it until "
                    f"{source.recomputed_free_time_end.isoformat()}, which is what the "
                    f"carrier's own start and allowance give"
                ),
            )
        return StripDay(day=day, state=FREE, note="inside the disclosed allowance")

    if day in source.billed_dates:
        return StripDay(day=day, state=BILLED, note="chargeable, and billed")
    return StripDay(day=day, state=CHARGEABLE, note="chargeable, and not billed")


def build_strip(result: AuditResult | _StripInput) -> DayStrip:
    """Draw the strip from a day result the engine already computed.

    Refuses an audit that ran no day arithmetic rather than recomputing it. That
    refusal is the entire reason this module does not import ``recompute``.
    """
    if isinstance(result, AuditResult):
        days = result.day_count
        if days is None:
            raise DayStripError(
                "this audit carries no day recomputation, so there are no days to "
                "draw. It is refused rather than recomputed here, because a second "
                "day count would be a second chance to disagree with the engine."
            )
        source = _StripInput(
            carrier=days.carrier,
            terminal=days.terminal,
            declared_free_time_end=days.declared_free_time_end,
            recomputed_free_time_end=days.recomputed_free_time_end,
            expected_dates=days.expected_dates,
            billed_dates=days.billed_dates,
            free_time_start=days.free_time_start,
        )
    else:
        source = result

    if source.carrier not in RULES:
        raise DayStripError(
            f"no day basis rule for carrier {source.carrier!r}. The strip has to say "
            f"which basis produced it, and refusing is better than naming a wrong one."
        )

    last = max(source.billed_dates, default=source.recomputed_free_time_end)
    span: list[date] = []
    cursor = source.free_time_start
    while cursor <= last:
        span.append(cursor)
        cursor += timedelta(days=1)

    rule = RULES[source.carrier]
    return DayStrip(
        carrier=source.carrier,
        terminal=source.terminal,
        day_basis=rule.default.value.replace("_", " "),
        declared_free_time_end=source.declared_free_time_end,
        recomputed_free_time_end=source.recomputed_free_time_end,
        days=tuple(_classify(day, source) for day in span),
    )


__all__ = [
    "BILLED",
    "CHARGEABLE",
    "DISPUTED",
    "FREE",
    "DayStrip",
    "DayStripError",
    "StripDay",
    "build_strip",
]
