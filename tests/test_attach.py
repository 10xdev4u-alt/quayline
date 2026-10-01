"""Issue 181: attaching a capture to a claim.

Issue 176 built a packet where automatic claims file and contested claims block.
Correct, and it means no contested claim has ever been filed by this code, because
nothing put evidence on one.

Every capture in this module is built from real bytes, so the digest is computed by
``Capture.from_bytes`` rather than supplied, and a test that asserted a digest string
would be asserting on a literal rather than on a hash.

The three refusals are the point of the issue

1. **Unauthenticated.** ``Capturer`` is required by the type, but ``Capture`` still
   checks, because Python does not check argument types and a record whose capturer
   is a bare string would otherwise report itself as attested.
2. **Expired.** ``docs/research/004-evidence.md`` records a one year limit on
   recorded-image availability. Filing on expired evidence loses the claim, and an
   expired capture silently filing is worse than a blocked one.
3. **Wrong ground.** Evidence attached to a ground nothing claims on is dropped by
   ``assemble`` and reported by ``orphaned_evidence``. Attaching is where that starts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from quayline.evidence.capture import Capture, Capturer, Register, Retained, Retention
from quayline.evidence.checklist import Artifact, Ground
from quayline.evidence.packet import Claim, assemble, orphaned_evidence
from quayline.filing.evidence import (
    EvidenceRefusedError,
    attach_capture,
    blockers_for,
    items_for,
)

BY = Capturer(name="R. Alvarez", affiliation="riverav@example.com")
WHEN = datetime(2026, 7, 15, 9, 30, tzinfo=UTC)
TODAY = date(2026, 7, 20)
PNG = b"\x89PNG\r\n\x1a\n" + b"appointment screenshot bytes"


def capture(artifact_id: str = "appt-01", **kwargs: object) -> Capture:
    return Capture.from_bytes(artifact_id, PNG, WHEN, BY, **kwargs)  # type: ignore[arg-type]


# ------------------------------------------------------------------- the digest


def test_the_evidence_item_carries_the_digest_of_the_bytes_we_hold() -> None:
    """Not a caller supplied digest. The whole point of a digest is what it covers."""
    shot = capture()
    item = attach_capture(shot, Ground.APPOINTMENT_UNAVAILABLE, Artifact.APPOINTMENT_SCREENSHOT)

    assert shot.sha256 in item.source
    assert item.description == shot.artifact_id
    assert item.ground is Ground.APPOINTMENT_UNAVAILABLE


def test_two_captures_of_different_bytes_get_different_digests() -> None:
    """A digest that did not change with the bytes would be a constant."""
    one = Capture.from_bytes("a", b"one", WHEN, BY)
    two = Capture.from_bytes("b", b"two", WHEN, BY)

    assert one.sha256 != two.sha256


def test_the_same_bytes_capture_to_the_same_digest() -> None:
    """Which is what makes it checkable by the other side."""
    one = Capture.from_bytes("a", PNG, WHEN, BY)
    two = Capture.from_bytes("b", PNG, WHEN, BY)

    assert one.sha256 == two.sha256


# ------------------------------------------------------------------- refusals


def test_an_unauthenticated_capture_is_refused() -> None:
    """``Capturer`` is required by the type but not verified by it.

    Python does not check argument types, so a record whose capturer is a bare
    string would report itself as authenticated. The capture module already has an
    ``is_authenticated`` check and this is where it gets used.
    """
    forged = Capture(
        artifact_id="appt-01",
        captured_at=WHEN,
        captured_by="R. Alvarez",  # type: ignore[arg-type]
        sha256="deadbeef",
    )

    with pytest.raises(EvidenceRefusedError) as caught:
        attach_capture(forged, Ground.APPOINTMENT_UNAVAILABLE, Artifact.APPOINTMENT_SCREENSHOT)

    assert "who took it" in str(caught.value)


def test_an_expired_capture_is_refused() -> None:
    """One year, per the research note. Filing on it loses the claim."""
    old = Capture.from_bytes("appt-01", PNG, datetime(2024, 1, 1, tzinfo=UTC), BY)

    with pytest.raises(EvidenceRefusedError) as caught:
        attach_capture(
            old,
            Ground.APPOINTMENT_UNAVAILABLE,
            Artifact.APPOINTMENT_SCREENSHOT,
            as_of=date(2026, 7, 20),
        )

    assert "expired" in str(caught.value).lower()
    assert "2024-12-31" in str(caught.value), "the message names the expiry date"
    assert "566" in str(caught.value), "and how long ago that was"


def test_a_capture_inside_the_window_is_accepted() -> None:
    """The refusal has to have a live side, or it is a broken gate."""
    item = attach_capture(
        capture(),
        Ground.APPOINTMENT_UNAVAILABLE,
        Artifact.APPOINTMENT_SCREENSHOT,
        as_of=TODAY,
    )

    assert item.ground is Ground.APPOINTMENT_UNAVAILABLE


def test_expiry_is_measured_from_the_capture_not_from_today() -> None:
    """The window runs from when the dispute's clock started, not from the audit.

    ``Retention`` says this explicitly and this is the test that holds it to it.
    """
    shot = capture()
    retention = Retention(as_of=TODAY)

    assert retention.expires_on(shot) == shot.captured_at.date() + timedelta(days=365)
    assert retention.state(shot) is Retained.REQUIRED


# ------------------------------------------------- the effect on filing


def test_a_contested_claim_with_no_evidence_is_blocked() -> None:
    """The gate exists and this is the case it exists for."""
    packet = assemble(
        (Claim(ground=Ground.APPOINTMENT_UNAVAILABLE, title="No appointment offered"),)
    )

    assert packet.can_file is False
    assert "no evidence attached" in packet.reason_not_filed()


def test_a_contested_claim_with_an_attached_capture_files() -> None:
    """The whole issue, in one assertion.

    Issue 176 produced a packet where every contested claim blocked. This is the
    other side of that gate, and until this passed no contested claim could be
    filed by this code at all.
    """
    shot = capture()
    packet = assemble(
        (
            Claim(
                ground=Ground.APPOINTMENT_UNAVAILABLE,
                title="No appointment offered",
                days=(date(2026, 7, 8),),
            ),
        ),
        (attach_capture(shot, Ground.APPOINTMENT_UNAVAILABLE, Artifact.APPOINTMENT_SCREENSHOT),),
    )

    assert packet.can_file is True
    assert packet.evidence_for(Ground.APPOINTMENT_UNAVAILABLE)


def test_the_blocker_names_the_artifact_a_carrier_would_ask_for() -> None:
    """\"validation failed\" teaches a carrier nothing and they can answer nothing."""
    packet = assemble((Claim(ground=Ground.CONTRACT_CONDITION, title="Condition not met"),))

    reason = packet.reason_not_filed()
    assert "no evidence attached" in reason
    blockers = blockers_for(packet)
    assert blockers
    assert blockers[0].claim.ground is Ground.CONTRACT_CONDITION
    assert blockers[0].reason in packet.reason_not_filed()
    assert blockers[0].reason.startswith("no evidence attached")


# ------------------------------------------------------------- bulk attachment


def test_a_register_turns_into_items_for_the_grounds_a_packet_claims() -> None:
    """The batch path, so a caller does not loop by hand and get the order wrong."""
    claims = (
        Claim(ground=Ground.APPOINTMENT_UNAVAILABLE, title="No appointment"),
        Claim(ground=Ground.CONTRACT_CONDITION, title="Condition", automatic=True),
    )
    register = Register(captures=(capture("appt-01"),))

    items = items_for(claims, register, as_of=TODAY)

    assert [i.ground for i in items] == [Ground.APPOINTMENT_UNAVAILABLE]
    assert orphaned_evidence(claims, items) == ()


def test_an_automatic_claim_needs_no_capture() -> None:
    """Demanding a screenshot for an omission we did not need to prove is noise."""
    claims = (Claim(ground=Ground.DISCLOSURE_OMITTED, title="Not disclosed", automatic=True),)

    assert items_for(claims, Register(), as_of=TODAY) == ()


def test_every_item_from_a_register_is_itself_authenticated() -> None:
    """A register can hold a forged record, so each attachment is checked."""
    forged = Capture(
        artifact_id="forged",
        captured_at=WHEN,
        captured_by="someone",  # type: ignore[arg-type]
        sha256="0" * 64,
    )
    claims = (Claim(ground=Ground.APPOINTMENT_UNAVAILABLE, title="No appointment"),)

    with pytest.raises(EvidenceRefusedError):
        items_for(claims, Register(captures=(forged,)), as_of=TODAY)
