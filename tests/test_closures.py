"""The four acceptance criteria on issue 8, one test block each.

The matrix at the top of this file is the thing the whole module exists to
express. Three carriers, three answers, on the same closed gate.
"""

from __future__ import annotations

import inspect

import pytest

from quayline.calendars import freetime
from quayline.calendars.closures import (
    ALL_CLOSURE_TYPES,
    CMA_CGM_US_CALIFORNIA,
    HAPAG_US,
    MAERSK_US,
    POLICIES,
    ClosurePolicy,
    ClosureType,
)

SATURDAY = ClosureType.WEEKEND
HOLIDAY = ClosureType.HOLIDAY
SCHEDULED = ClosureType.SCHEDULED_CLOSURE
UNSCHEDULED = ClosureType.UNSCHEDULED_SHUTOUT
APPOINTMENT = ClosureType.APPOINTMENT_UNAVAILABLE
CUSTOM = ClosureType.CUSTOM


# ---------------------------------------------------------------- criterion 1
# Closure types exist for weekend, holiday, shutout, appointment-unavailable and
# custom.


def test_the_five_named_types_exist() -> None:
    named = {t.value for t in ClosureType}
    assert named == {
        "weekend",
        "holiday",
        "scheduled_closure",
        "unscheduled_shutout",
        "appointment_unavailable",
        "custom",
    }


def test_scheduled_and_unscheduled_are_separate_members() -> None:
    """Not a flag on one type. A flag is how this distinction gets lost.

    Maersk draws the line by cause rather than by notice: lack of appointment demand
    is chargeable, a gate that was not open when the party arrived is not. Both are
    "the terminal was shut", which is the only thing a boolean could see.
    """
    assert SCHEDULED is not UNSCHEDULED
    assert len(ALL_CLOSURE_TYPES) == 6
    assert all(isinstance(t, ClosureType) for t in ALL_CLOSURE_TYPES)


# ---------------------------------------------------------------- criterion 2
# A closure policy is a typed set of excluded closure types, not a boolean.


def test_a_policy_is_a_typed_set() -> None:
    for policy in POLICIES.values():
        assert isinstance(policy.extends_free_time, frozenset)
        assert isinstance(policy.excluded_after_free_time, frozenset)
        for member in policy.extends_free_time | policy.excluded_after_free_time:
            assert isinstance(member, ClosureType), policy.name


def test_no_policy_field_is_a_bool() -> None:
    """The criterion stated as a property of the type.

    A bool here would be a value that cannot say what it means. ``forgives=
    True`` does not distinguish a Hapag Saturday from a Hapag unscheduled shutout,
    and those two land on opposite sides of a real dispute.
    """
    for policy in POLICIES.values():
        for name in ("extends_free_time", "excluded_after_free_time", "extends_free_time_inferred"):
            assert not isinstance(getattr(policy, name), bool), f"{policy.name}.{name} is a bool"
        # verified is a bool and is entitled to be, it is metadata about the source
        # rather than a term of the rule. The prohibition is on the rule being a flag.
        assert isinstance(policy.verified, bool)
        assert set(policy.__dataclass_fields__) == {
            "name",
            "extends_free_time",
            "excluded_after_free_time",
            "source",
            "citation",
            "verified",
            "note",
            "extends_free_time_inferred",
        }
        # note is provenance about a doubtful entry, added when freetime.py turned out
        # to be the first module that actually exercises this policy. It is a string and
        # is entitled to be; the prohibition is on the rule being a flag.
        assert isinstance(policy.note, str)
        # The inferred set joined the fields in issue 112, and it exists so that the
        # guess is a value the default path cannot reach rather than a note nobody
        # reads. Exact set equality above, so a field added here has to be added
        # there.
        assert isinstance(policy.extends_free_time_inferred, frozenset)


def test_the_two_windows_differ_for_hapag() -> None:
    """The reason the policy has two sets rather than one.

    Hapag forgives an unscheduled shutout inside free time and after it, and the
    two windows are the reason the policy has two sets rather than one. The
    scheduled/unscheduled pair is the most valuable thing this module encodes.

    Scheduled closures are not asserted here at all. That entry is inferred, and
    issue 112 moved it out of the sourced set; see the opt in tests below.
    """
    assert HAPAG_US.forgives(SCHEDULED, after_free_time=True) is False
    assert HAPAG_US.forgives(UNSCHEDULED) is True
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True


def test_the_windows_differ_where_the_carrier_makes_them_differ() -> None:
    """Not every policy has two different sets, and that is correct.

    Hapag's differ, and that is the case worth having modelled. CMA CGM California
    forgives every closure type in both windows, so its two sets are identical, and
    asserting otherwise would be asserting something false to look thorough.

    Maersk's second set is empty, which is also a real position rather than an
    omission: it forgives nothing once the allowance is spent.
    """
    assert HAPAG_US.extends_free_time != HAPAG_US.excluded_after_free_time
    assert CMA_CGM_US_CALIFORNIA.extends_free_time == (
        CMA_CGM_US_CALIFORNIA.excluded_after_free_time
    )
    assert MAERSK_US.excluded_after_free_time == frozenset()


def test_unmentioned_types_are_visible() -> None:
    """So an unmodelled type is never silently charged by default."""
    assert HAPAG_US.unmentioned_types() == frozenset({SATURDAY, APPOINTMENT, CUSTOM})
    assert MAERSK_US.unmentioned_types() == frozenset(
        {SATURDAY, HOLIDAY, SCHEDULED, UNSCHEDULED, CUSTOM}
    )
    assert CMA_CGM_US_CALIFORNIA.unmentioned_types() == frozenset()


def test_policies_are_addressable_by_name() -> None:
    assert set(POLICIES) == {
        "Hapag-Lloyd US",
        "Maersk US",
        "CMA CGM US, California gateway",
    }


# ---------------------------------------------------------------- criterion 3
# A Hapag unscheduled shutout is forgiven while a Hapag Saturday is charged.


def test_hapag_forgives_an_unscheduled_shutout_after_free_time() -> None:
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True


def test_hapag_charges_a_saturday_after_free_time() -> None:
    """The contrast, on the same carrier and the same window.

    Hapag bills calendar days once the allowance is spent, and a Saturday is a
    calendar day. It is not a closure the carrier forgives, it is a day it charges.
    """
    assert HAPAG_US.forgives(SATURDAY, after_free_time=True) is False


def test_the_two_agree_during_free_time_and_split_after_it() -> None:
    """Where the divergence starts, stated from both directions.

    Inside the allowance neither day is chargeable, so the policy barely matters.
    It starts mattering the moment free time is gone, which is exactly when a
    demurrage dispute is being argued.
    """
    assert HAPAG_US.forgives(SATURDAY) is False
    assert HAPAG_US.forgives(UNSCHEDULED) is True
    assert HAPAG_US.forgives(SATURDAY, after_free_time=True) is False
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True


def test_hapag_charges_a_scheduled_closure_after_free_time() -> None:
    """A closure the carrier published is the carrier's own."""
    assert HAPAG_US.forgives(SCHEDULED, after_free_time=True) is False


def test_hapag_citation_is_the_carriers_words() -> None:
    assert HAPAG_US.verified is True
    assert HAPAG_US.citation.startswith("Any unscheduled closures")
    assert "unforeseen shutout days" in HAPAG_US.citation
    assert "excluded from Detention and Demurrage" in HAPAG_US.citation
    assert "October 1 2024" in HAPAG_US.source


# ---------------------------------------------------------------- criterion 4
# A CMA CGM California Saturday is forgiven.


def test_cma_cgm_california_forgives_a_saturday() -> None:
    assert CMA_CGM_US_CALIFORNIA.forgives(SATURDAY) is True
    assert CMA_CGM_US_CALIFORNIA.forgives(SATURDAY, after_free_time=True) is True


@pytest.mark.parametrize("closure", list(ClosureType))
def test_cma_cgm_california_forgives_everything(closure: ClosureType) -> None:
    assert CMA_CGM_US_CALIFORNIA.forgives(closure) is True
    assert CMA_CGM_US_CALIFORNIA.forgives(closure, after_free_time=True) is True


def test_the_unverified_cma_policy_says_so_rather_than_pretending() -> None:
    """It is in the module because the issue asks for it, marked because we have
    not transcribed a clause. A hole is cheap, a guess is not."""
    assert CMA_CGM_US_CALIFORNIA.verified is False
    assert CMA_CGM_US_CALIFORNIA.citation.startswith("UNVERIFIED:")
    assert "issue 20" in CMA_CGM_US_CALIFORNIA.source


# ---------------------------------------------------------------- the comparison


def test_maersk_forgives_only_the_appointment_case() -> None:
    """Its own words: a booked appointment that met a closed gate.

    Everything else is chargeable, including its own scheduled closures, because
    the tariff says a partial day closure is a full working day.
    """
    assert MAERSK_US.forgives(APPOINTMENT) is True
    for closure in (SATURDAY, HOLIDAY, SCHEDULED, UNSCHEDULED, CUSTOM):
        assert MAERSK_US.forgives(closure) is False, closure
    assert MAERSK_US.excluded_after_free_time == frozenset()


def test_the_three_carriers_never_all_agree_on_the_same_closed_gate() -> None:
    """The boolean impossibility, stated as something actually true.

    My first version asserted three distinct answers for every closure type. That is
    false. On a booked appointment that met a closed gate, Hapag and CMA CGM agree and
    Maersk differs. On a custom closure, Hapag and Maersk agree and CMA CGM differs.
    Two distinct answers, not three.

    The claim that survives and is the one worth making is that they never ALL agree.
    A single bool per carrier cannot produce three different answers to one question,
    so no encoding of this data as a flag is complete.
    """
    for closure in ClosureType:
        answers = {
            policy.name: policy.forgives(closure, after_free_time=True)
            for policy in (HAPAG_US, MAERSK_US, CMA_CGM_US_CALIFORNIA)
        }
        assert len(set(answers.values())) >= 2, (closure, answers)

    # After free time, Hapag and Maersk are identical on five of the six types. The
    # single point of divergence is the unplanned shutout, and that is the whole
    # argument. Two carriers that agree everywhere except one case cannot be
    # described by a flag, because the flag has nowhere to put "except".
    divergent = [
        c
        for c in ClosureType
        if HAPAG_US.forgives(c, after_free_time=True) != MAERSK_US.forgives(c, after_free_time=True)
    ]
    assert divergent == [UNSCHEDULED]
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True
    assert MAERSK_US.forgives(UNSCHEDULED, after_free_time=True) is False


def test_hapag_and_maersk_disagree_on_both_the_what_and_the_when() -> None:
    """Hapag forgives the unplanned kind forever, Maersk forgives the booked kind
    once. Different types and different windows, for the same closed gate."""
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True
    assert MAERSK_US.forgives(UNSCHEDULED, after_free_time=True) is False
    assert MAERSK_US.forgives(APPOINTMENT, after_free_time=True) is False
    assert HAPAG_US.forgives(APPOINTMENT, after_free_time=True) is False


def test_policies_are_immutable() -> None:
    with pytest.raises(AttributeError):
        HAPAG_US.extends_free_time = frozenset()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        HAPAG_US.verified = True  # type: ignore[misc]


def test_a_policy_is_hashable_and_usable_as_a_key() -> None:
    """Frozen, because a policy is configuration and configuration that mutates
    mid audit is how two invoices on the same policy get different answers."""
    assert len({HAPAG_US, MAERSK_US, CMA_CGM_US_CALIFORNIA}) == 3


def test_closure_policy_requires_both_windows() -> None:
    """A policy with one set cannot be built, which is the point of two."""
    with pytest.raises(TypeError):
        ClosurePolicy(  # type: ignore[call-arg]
            name="half",
            extends_free_time=frozenset(),
            source="nowhere",
            citation="nowhere",
            verified=False,
        )


# ---------------------------------------------------------------- issue 112
# An inferred entry cannot be reached without the opt in.


def test_the_inferred_entry_is_not_in_the_sourced_set() -> None:
    """Separation in the type, not in a note.

    Before issue 112 SCHEDULED_CLOSURE sat inside extends_free_time beside the two
    entries that are transcribed, with a note explaining it was a guess. A caller
    reading the set got the guess silently.
    """
    assert SCHEDULED not in HAPAG_US.extends_free_time
    assert SCHEDULED in HAPAG_US.extends_free_time_inferred
    assert UNSCHEDULED in HAPAG_US.extends_free_time


def test_the_inferred_entry_is_unreachable_without_the_opt_in() -> None:
    """The acceptance criterion, as a reachability test rather than a comment."""
    assert HAPAG_US.forgives(SCHEDULED) is False
    assert HAPAG_US.forgives(SCHEDULED, include_inferred=True) is True


def test_the_opt_in_does_not_change_the_sourced_entries() -> None:
    """Opting in adds the guess. It does not quietly widen anything else."""
    without = HAPAG_US.effective_extends_free_time()
    with_guess = HAPAG_US.effective_extends_free_time(include_inferred=True)
    assert with_guess == without | {SCHEDULED}
    assert without == frozenset({HOLIDAY, UNSCHEDULED})


def test_the_opt_in_has_no_bearing_on_the_second_window() -> None:
    """There is no inferred entry in excluded_after_free_time, and the opt in must
    not manufacture one."""
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True) is True
    assert HAPAG_US.forgives(UNSCHEDULED, after_free_time=True, include_inferred=True) is True
    assert HAPAG_US.forgives(SCHEDULED, after_free_time=True, include_inferred=True) is False


def test_an_inferred_entry_does_not_read_as_unmodelled() -> None:
    """unmentioned_types means unsaid. An inferred entry is something we said."""
    assert SCHEDULED not in HAPAG_US.unmentioned_types()
    assert SCHEDULED in HAPAG_US.effective_extends_free_time(include_inferred=True)


def test_every_inferred_entry_is_named_as_unverified_in_the_note() -> None:
    """The note is kept, but it is now documentation rather than the safeguard."""
    assert "SCHEDULED_CLOSURE" in HAPAG_US.note
    assert "inference" in HAPAG_US.note
    assert "UNVERIFIED" in HAPAG_US.note


def test_no_other_carrier_carries_an_inferred_entry() -> None:
    """So that a future inferred entry has to be added here deliberately."""
    inferred = {
        p.name: p.extends_free_time_inferred
        for p in POLICIES.values()
        if p.extends_free_time_inferred
    }
    assert inferred == {"Hapag-Lloyd US": frozenset({SCHEDULED})}


def test_the_production_path_does_not_opt_in() -> None:
    """freetime.py calls forgives() with no opt in, so the guess is inert in the
    engine and only a caller who has read the note can reach it."""
    source = inspect.getsource(freetime)
    assert "include_inferred" not in source
