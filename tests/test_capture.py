"""Issue 61: the capturer identity, which the image itself cannot carry.

The load bearing test is ``test_no_capture_can_be_constructed_without_a_capturer``.
The acceptance criterion is an absence, and an absence that is checked by
inspecting one object is an absence that a future default quietly restores.
"""

from __future__ import annotations

import hashlib
from dataclasses import MISSING, fields
from datetime import UTC, date, datetime, timedelta

import pytest

import quayline.evidence.capture as module
from quayline.evidence.capture import (
    Capture,
    Capturer,
    Register,
    Retained,
    Retention,
)

CAPTURED = datetime(2026, 7, 1, 14, 30, tzinfo=UTC)
OKAFOR = Capturer(name="D. Okafor", affiliation="freightdesk@example.com")
RUIZ = Capturer(name="A. Ruiz", affiliation="ops@example.com")
PNG = b"\x89PNG\r\n\x1a\n" + b"a gate roster screenshot"


def capture(who: Capturer = OKAFOR, when: datetime = CAPTURED, **kw: str) -> Capture:
    return Capture.from_bytes("roster.png", PNG, when, who, **kw)


# ---------------------------------------------------------------- criterion 1
# Every capture records who took it and when.


def test_a_capture_records_who_and_when() -> None:
    c = capture()
    assert c.captured_by is OKAFOR
    assert c.captured_at == CAPTURED


def test_the_digest_comes_from_the_bytes_we_hold() -> None:
    """A caller supplied digest is a digest of whatever the caller had."""
    assert capture().sha256 == hashlib.sha256(PNG).hexdigest()


def test_different_content_gives_a_different_digest() -> None:
    other = Capture.from_bytes("roster.png", PNG + b"x", CAPTURED, OKAFOR)
    assert other.sha256 != capture().sha256


def test_a_capture_with_no_timezone_is_refused() -> None:
    """A two hour ambiguity is enough to move a day boundary."""
    with pytest.raises(ValueError, match="timezone"):
        capture(when=datetime(2026, 7, 1, 14, 30))


def test_a_capture_dated_in_the_future_is_refused() -> None:
    with pytest.raises(ValueError, match="future"):
        capture(when=datetime.now(UTC) + timedelta(days=1))


def test_an_unnamed_capturer_is_refused() -> None:
    """An unnamed capturer cannot give testimony, which is the whole point."""
    with pytest.raises(ValueError, match="cannot give testimony"):
        Capturer(name="   ", affiliation="x@example.com")


def test_a_capturer_with_no_affiliation_is_refused() -> None:
    """Otherwise the identity rests on their own word alone."""
    with pytest.raises(ValueError, match="corroborated independently"):
        Capturer(name="D. Okafor", affiliation="  ")


def test_the_optional_fields_default_without_provenance() -> None:
    c = capture(description="terminal gate roster, berth 4")
    assert c.media_type == "image/png"
    assert c.description == "terminal gate roster, berth 4"


# ---------------------------------------------------------------- criterion 2
# The record survives the retention period of the dispute.


def test_a_record_inside_the_window_is_required() -> None:
    assert Retention(date(2026, 8, 1)).state(capture()) is Retained.REQUIRED


def test_a_record_past_the_window_is_optional() -> None:
    assert Retention(date(2027, 8, 1)).state(capture()) is Retained.OPTIONAL


def test_the_boundary_day_is_still_required() -> None:
    """One day either side of the boundary, because an off by one on a retention
    window loses a claim."""
    expires = Retention(date(2026, 7, 1)).expires_on(capture())
    assert Retention(expires).state(capture()) is Retained.REQUIRED
    assert Retention(expires + timedelta(days=1)).state(capture()) is Retained.OPTIONAL


def test_the_window_runs_forward_from_the_capture() -> None:
    """The dispute's clock started when the evidence was taken, so our need for the
    record started then too."""
    assert Retention(date(2026, 7, 1)).days_remaining(capture()) == 365


def test_days_remaining_is_signed() -> None:
    """'expired 40 days ago' and 'expired sometime' are different facts."""
    assert Retention(date(2027, 8, 1)).days_remaining(capture()) < 0


def test_the_window_is_declared_unverified() -> None:
    """The real window was not transcribed, and the default is deliberately long."""
    assert Retention(date(2026, 8, 1)).window == timedelta(days=365)
    flat = " ".join((module.__doc__ or "").split())
    assert "UNVERIFIED" in flat


# ---------------------------------------------------------------- criterion 3
# No capture exists without a capturer identity.


def test_no_capture_can_be_constructed_without_a_capturer() -> None:
    """The criterion, as a type property rather than a runtime check.

    ``captured_by`` is not optional and has no default, so there is no call that
    produces a Capture without one. An assertion that a constructed object has a
    capturer would pass today and fail silently the day someone gave the field a
    default of None.
    """
    spec = next(f for f in fields(Capture) if f.name == "captured_by")
    assert spec.default is MISSING
    assert spec.default_factory is MISSING
    assert "captured_by" in Capture.__slots__
    assert "captured_at" in Capture.__slots__


def test_the_constructor_refuses_to_omit_the_capturer() -> None:
    """Omitting it is a TypeError, not a default.

    Presence is what the type guarantees. It does not guarantee the *type* of what
    is passed, because Python does not, and pretending otherwise in a test is how a
    test starts asserting things that are not true.
    """
    with pytest.raises(TypeError, match="captured_by"):
        Capture("id", CAPTURED, sha256="deadbeef")  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="captured_by"):
        Capture(artifact_id="id", captured_at=CAPTURED, sha256="d")  # type: ignore[call-arg]


def test_a_wrong_typed_capturer_does_not_produce_a_valid_attestation() -> None:
    """What actually happens if the type is violated at runtime.

    A raw string survives construction and looks authenticated, but it cannot
    attest to anything, because :meth:`Register.attestable_by` compares a
    Capturer. So a malformed record is inert rather than silently usable, which is
    the best available outcome without a runtime type check.
    """
    bad = Capture("id", CAPTURED, "D. Okafor", "d")  # type: ignore[arg-type]
    assert bad.is_authenticated() is False, "a bare string is not a capturer"
    assert Register((bad,)).attestable_by(OKAFOR) is False
    assert Register((bad,)).unauthenticated() == (bad,)
    assert Register((bad,)).attests_all() is True, "one malformed row, nobody to swear to it"


def test_a_capture_always_reports_itself_authenticated() -> None:
    assert capture().is_authenticated() is True


def test_the_register_finds_no_unauthenticated_capture() -> None:
    """Always empty, because the type prevents the case. Asserted so a change that
    makes provenance optional has somewhere to fail."""
    register = Register((capture(), capture(RUIZ)))
    assert register.unauthenticated() == ()


def test_an_empty_register_is_vacuously_authenticated() -> None:
    assert Register().unauthenticated() == ()


# ---------------------------------------------------------------- the Rivera route


def test_a_register_captured_by_one_person_is_attestable() -> None:
    register = Register((capture(), capture(description="berth 4 roster")))
    assert register.attests_all() is True
    assert register.attestable_by(OKAFOR) is True


def test_a_register_captured_by_three_needs_three_testimonies() -> None:
    """Knowing that in advance is the difference between planning and discovering
    it at the deposition."""
    third = Capturer(name="M. Silva", affiliation="broker@example.com")
    register = Register((capture(), capture(RUIZ), capture(third)))
    assert register.attests_all() is False
    assert sorted(register.by_capturer()) == ["A. Ruiz", "D. Okafor", "M. Silva"]


def test_attestation_matches_affiliation_not_just_name() -> None:
    """A name collision across two employers must not let the wrong person swear."""
    impostor = Capturer(name="D. Okafor", affiliation="someone.else@example.com")
    register = Register((capture(),))
    assert register.attestable_by(impostor) is False
    assert register.attestable_by(OKAFOR) is True


def test_an_empty_register_needs_no_testimony() -> None:
    assert Register().attests_all() is True


# ---------------------------------------------------------------- criterion 4
# Documentation states the limit: a certification proves authenticity only.


def test_the_module_states_the_902_limit() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "authenticity only" in flat
    assert "not establish admissibility" in flat


def test_the_module_cites_the_case_that_makes_testimony_sufficient() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Rivera v. Village of Farmingdale" in flat
    assert "not mandatory" in flat.lower()


def test_no_capture_field_claims_quality_or_admissibility() -> None:
    """There is no field that says an exhibit is good. That judgement belongs to a
    tribunal, and a field that approximated it would be quoted as if it did not."""
    names = {f.name for f in fields(Capture)}
    banned = {
        "quality",
        "score",
        "confidence",
        "admissible",
        "admissibility",
        "authenticity",
        "verified",
        "weight",
        "strength",
    }
    assert not (names & banned), names & banned
