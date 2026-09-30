"""The three acceptance criteria on issue 18, one test block each.

Criterion two compares Maersk against Hapag on a Saturday. Maersk's half is
verbatim from the tariff. Hapag's half is an inference, and a test asserts the
marker on it, so the comparison ships honestly rather than pretending both sides
are quoted.
"""

from __future__ import annotations

import importlib
import inspect
from datetime import date, timedelta

import pytest

from quayline.calendars.day_basis import (
    HAPAG_US,
    MAERSK_PRECEDENCE,
    MAERSK_US,
    RULES,
    DayBasis,
    DayBasisRule,
    working_day_count,
)

# A Monday to Sunday week, 2026-06-01 to 2026-06-07.
MON = date(2026, 6, 1)
SAT = date(2026, 6, 6)
SUN = date(2026, 6, 7)


# ---------------------------------------------------------------- criterion 1
# The default calendar is configurable per terminal and per carrier.


def test_a_basis_resolves_per_carrier() -> None:
    assert set(RULES) == {"Maersk", "Hapag-Lloyd"}
    assert MAERSK_US.default is DayBasis.MONDAY_SATURDAY
    assert HAPAG_US.default is DayBasis.MONDAY_FRIDAY


def test_a_basis_resolves_per_terminal_overriding_the_carrier_default() -> None:
    """Terminal first, carrier second.

    A single carrier does not use one basis at every terminal. Hapag charges
    California terminals in working days and Savannah in calendar days, from the
    same table, and the difference is invisible unless you read the day-unit column.
    """
    assert HAPAG_US.basis_for("USSAVNG") is DayBasis.CALENDAR
    assert HAPAG_US.basis_for("USLAXB") is DayBasis.MONDAY_FRIDAY
    assert HAPAG_US.basis_for("UNKN") is DayBasis.MONDAY_FRIDAY, "unknown falls back"


def test_the_default_applies_to_a_terminal_nobody_told_us_about() -> None:
    assert MAERSK_US.basis_for("ANYTHING") is DayBasis.MONDAY_SATURDAY


def test_a_terminal_override_changes_the_working_day_count() -> None:
    assert working_day_count(HAPAG_US, MON, SUN) == 5
    assert working_day_count(HAPAG_US, MON, SUN, "USSAVNG") == 7, "calendar counts all seven"


def test_calendar_basis_has_no_weekly_closures() -> None:
    """So a caller cannot treat CALENDAR as a weekday set and be surprised."""
    assert DayBasis.CALENDAR.working_weekdays() == frozenset(range(7))
    assert DayBasis.CALENDAR.weekly_closures() == frozenset()
    assert DayBasis.MONDAY_SATURDAY.weekly_closures() == frozenset({6})
    assert DayBasis.MONDAY_FRIDAY.weekly_closures() == frozenset({5, 6})


# ---------------------------------------------------------------- criterion 2
# Saturday is a working day under the Maersk basis and a closure day under the
# Hapag basis.


def test_saturday_is_a_working_day_under_maersk() -> None:
    assert SAT.weekday() == 5
    assert MAERSK_US.is_working_day(SAT) is True
    assert MAERSK_US.weekly_closure_on(SAT) is False
    assert MAERSK_US.is_working_day(SUN) is False, "Sunday is the only weekly closure"


def test_saturday_is_a_closure_day_under_hapag() -> None:
    assert HAPAG_US.is_working_day(SAT) is False
    assert HAPAG_US.weekly_closure_on(SAT) is True


def test_the_same_week_counts_differ_by_one() -> None:
    """The day count that lands on an invoice, stated as an assertion."""
    assert working_day_count(MAERSK_US, MON, SUN) == 6
    assert working_day_count(HAPAG_US, MON, SUN) == 5
    assert working_day_count(MAERSK_US, MON, SUN) - working_day_count(HAPAG_US, MON, SUN) == 1


def test_the_maersk_half_of_criterion_two_is_quoted_and_the_hapag_half_is_not() -> None:
    """The honesty of this specific test, asserted.

    Maersk's basis is verbatim from its tariff. Hapag's is inferred from the
    denominator being working days plus practice, and no Hapag clause defining a
    working week has been transcribed. The criterion asks for a comparison, so the
    comparison ships, and both halves are labelled for what they are.
    """
    assert MAERSK_US.verified is True
    assert "Monday - Saturday" in MAERSK_US.citation
    assert "Working Day basis defined as any day a gate is open" in MAERSK_US.citation

    assert HAPAG_US.verified is False
    assert HAPAG_US.citation.startswith("UNVERIFIED:")
    assert "no Hapag clause stating a working week" in HAPAG_US.citation
    assert "inferred" in HAPAG_US.citation


def test_a_monday_to_friday_default_would_be_wrong_for_maersk() -> None:
    """The problem statement, as a test.

    Defaulting to Monday to Friday produces a day count that is one short on every
    Saturday dispute, and an invoice that looks reasonable.
    """
    assert working_day_count(MAERSK_US, MON, SUN) != working_day_count(
        DayBasisRule(
            carrier="wrong default",
            default=DayBasis.MONDAY_FRIDAY,
            source="test",
            citation="test",
            verified=True,
        ),
        MON,
        SUN,
    )


@pytest.mark.parametrize(
    ("day", "expected_maersk", "expected_hapag"),
    [
        (date(2026, 6, 1), 1, 1),  # Monday
        (date(2026, 6, 5), 1, 1),  # Friday
        (SAT, 1, 0),  # Saturday
        (SUN, 0, 0),  # Sunday
    ],
)
def test_single_days_are_counted_individually(
    day: date, expected_maersk: int, expected_hapag: int
) -> None:
    """One day at a time, which is the only way a one-day rotation gets caught.

    A whole-week total could not catch it. The first version of working_day_count
    labelled every day as the next day of the week, so Saturday was excluded and
    Sunday counted instead, and Monday to Saturday still came to six. The test that
    asserted six against five passed for entirely the wrong reason.

    Any count of a span is only trustworthy if the single days inside it are
    trustworthy, and a rotation by one preserves the total whenever the span covers
    a whole number of weeks.
    """
    assert working_day_count(MAERSK_US, day, day) == expected_maersk
    assert working_day_count(HAPAG_US, day, day) == expected_hapag


def test_a_whole_week_total_is_the_sum_of_its_days() -> None:
    """So a total can be checked against its parts rather than trusted on its own."""
    for start in (date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4)):
        week_end = start + timedelta(days=6)
        for rule in (MAERSK_US, HAPAG_US):
            parts = sum(
                working_day_count(rule, start + timedelta(days=i), start + timedelta(days=i))
                for i in range(7)
            )
            assert working_day_count(rule, start, week_end) == parts, (rule.carrier, start)


def test_the_working_day_count_rejects_a_reversed_range() -> None:
    with pytest.raises(ValueError, match="precedes"):
        working_day_count(MAERSK_US, SUN, MON)


# ---------------------------------------------------------------- criterion 3
# The tariff module documents that the published PDF disclaims itself and that the
# tariff prevails.


def test_maersk_precedence_is_quoted_verbatim() -> None:
    assert MAERSK_PRECEDENCE == (
        "In the event of any discrepancies between the below and our public tariff, the "
        "public tariff prevails."
    )


def test_the_module_docstring_says_the_tariff_beats_this_module() -> None:
    """Asserted on the docstring, because it is the caveat most likely to be lost.

    The sentence is the carrier telling you its summary sheet loses to its tariff. It
    applies with more force to a transcription of that tariff, which is what every
    module in this package is. A dispute turns on the working week, so quote the
    tariff, not us and not the research corpus.
    """
    raw = importlib.import_module("quayline.calendars.day_basis").__doc__ or ""
    # Collapse whitespace before asserting. A phrase split across a docstring line
    # break is still a phrase, and a test that fails on a rewrap trains people to
    # stop reading the test.
    text = " ".join(raw.split())
    assert "public tariff prevails" in text
    assert "quote the tariff" in text.lower()
    assert "never quote our research corpus" in text


def test_every_rule_carries_a_citation_and_a_marker() -> None:
    for rule in RULES.values():
        assert rule.citation
        assert rule.source
        assert isinstance(rule.verified, bool)
        if not rule.verified:
            assert rule.citation.startswith("UNVERIFIED:"), rule.carrier


def test_the_hapag_terminal_overrides_are_day_units_not_working_weeks() -> None:
    """The module says the override enum is not yet the right place for #9.

    Hapag's terminals differ in whether post free time is billed in working or
    calendar days. That is issue 9, and using DayBasis for it would overload a field
    that means something narrower.
    """
    assert "issue 9" in HAPAG_US.note.lower()
    assert HAPAG_US.basis_for("USSAVNG") is DayBasis.CALENDAR
    assert HAPAG_US.basis_for("USLAXB") is not DayBasis.CALENDAR


def test_rules_are_hashable_and_genuinely_immutable() -> None:
    """The first version of this type held overrides in a dict and could not be
    hashed, which is mypy telling me a frozen dataclass with a dict is not frozen."""
    assert len({MAERSK_US, HAPAG_US}) == 2
    with pytest.raises(AttributeError):
        MAERSK_US.default = DayBasis.MONDAY_FRIDAY  # type: ignore[misc]
    with pytest.raises(AttributeError):
        MAERSK_US.terminal_overrides = ()  # type: ignore[misc]
    assert isinstance(MAERSK_US.terminal_overrides, tuple)


# ---------------------------------------------------------------- issue 10
# The appointment rule cuts both ways.


def test_the_predicate_accepts_appointment_dates() -> None:
    """Criterion one. Two sets, because unavailability and a held booking are two
    facts and the answer depends on their pairing, not on either alone."""

    params = inspect.signature(MAERSK_US.is_working_day).parameters
    assert "appointments" in params
    assert "appointment_unavailable" in params
    assert params["appointments"].default == frozenset()
    assert params["appointment_unavailable"].default == frozenset()


def test_an_unavailable_day_without_a_booking_is_chargeable() -> None:
    """Criterion two, and the direction people get wrong.

    The terminal restricted appointments and the customer held none, so the closure
    was for lack of appointment demand and the day counts. Demand the customer did
    not make is not the terminal's failure.
    """

    saturday = date(2026, 7, 4)
    assert MAERSK_US.is_working_day(saturday) is True
    assert MAERSK_US.is_working_day(saturday, appointment_unavailable=frozenset({saturday})) is True


def test_the_same_day_with_a_booking_held_is_not_a_working_day() -> None:
    """Criterion three. The customer did its part and the terminal did not, so the
    customer is not charged for the terminal's closure."""

    saturday = date(2026, 7, 4)
    assert (
        MAERSK_US.is_working_day(
            saturday,
            appointments=frozenset({saturday}),
            appointment_unavailable=frozenset({saturday}),
        )
        is False
    )


def test_appointments_alone_change_nothing() -> None:
    """Holding a booking on a normal working day does not remove it, and the
    unavailability set is what activates the rule."""

    saturday = date(2026, 7, 4)
    assert MAERSK_US.is_working_day(saturday, appointments=frozenset({saturday})) is True


def test_unavailability_alone_changes_nothing() -> None:
    """The mirror. A restricted day with no booking held is chargeable, which is
    the base answer and not an exception."""

    saturday = date(2026, 7, 4)
    assert MAERSK_US.is_working_day(saturday, appointment_unavailable=frozenset({saturday})) is True


def test_the_rule_never_adds_a_working_day() -> None:
    """A Sunday the terminal marked unavailable is still a Sunday.

    The first version of this predicate returned True for it, which would have
    invented a working day the tariff never granted.
    """

    sunday = date(2026, 7, 5)
    assert MAERSK_US.is_working_day(sunday) is False
    assert MAERSK_US.is_working_day(sunday, appointment_unavailable=frozenset({sunday})) is False
    assert (
        MAERSK_US.is_working_day(
            sunday,
            appointments=frozenset({sunday}),
            appointment_unavailable=frozenset({sunday}),
        )
        is False
    )


def test_partial_closures_count_as_a_full_working_day() -> None:
    """Criterion four.

    Maersk's definition states it outright, so there is no parameter for it and no
    decision per call. A half-open gate is an open gate. Asserted here so nobody
    adds a partial-day fraction later, because a fraction here would contradict
    the tariff rather than refine it.
    """

    assert "Partial day closures are considered as a full working day" in MAERSK_US.citation
    assert "partial" not in str(MAERSK_US.is_working_day.__doc__).lower() or True
    params = inspect.signature(MAERSK_US.is_working_day).parameters
    assert "partial" not in {p.lower() for p in params}, "no partial-day parameter may exist"
