"""Issue 61: who took the capture, and when.

Every screenshot in a dispute is an assertion that a page said something on a
date. Two things about that assertion are not in the image: who made it, and when.
A PNG of a terminal gate roster carries no more authority than a line of text
quoting it, and the difference is entirely in the provenance that sits outside the
file.

902(13) certifications are not mandatory

Rivera v. Village of Farmingdale held that testimony from the person who took the
screenshots, confirming they personally downloaded the postings and confirmed the
identities, was sufficient to show a reasonable likelihood of posting. That is the
route this module supports: a named capturer with a date is a filing in itself, so
a dispute must never be blocked on obtaining a certification.

The limit, stated once and loudly

A 902(13) certification establishes **authenticity only**. It does not establish
admissibility, and it does not establish that the posting said what the filer says
it said. Both facts can be true at once, and conflating them is how a carrier
argues that our exhibit is fine but our claim is not, which is a longer
conversation than the one we thought we were having.

The retention window is UNVERIFIED

365 days is a working default, not a transcribed rule. It was chosen to be longer
than any plausible bar rather than to be correct, and being wrong toward keeping
evidence is the safe direction. Transcribing the actual window is open work, and
:data:`_CLAIM_RETENTION` is the one place that has to change when it is done.

So this module records provenance. It deliberately does not score a capture, rate
one, or expose anything a caller might report as evidence quality. There is no
field that says "this exhibit is good", because the judgement of admissibility is
made by a tribunal and encoded nowhere in this repository.

Why the identity is not optional

A capture with no capturer is not a weaker capture, it is an unusable one. It
cannot be corroborated by testimony, because there is nobody to give it, and it
cannot be defended at all when the carrier disputes it. Rather than allow one to be
constructed and lose it later, the type has no way to express it: there is no
optional capturer, and construction raises.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

# UNVERIFIED. The specific retention window for a freight claim was not transcribed
# for this issue. 365 days is a working default chosen to be longer than any
# plausible bar rather than to be correct, and being wrong toward keeping evidence
# is the safe direction. Transcribing the actual window is open work.
_CLAIM_RETENTION = timedelta(days=365)


class Retained(StrEnum):
    """Whether a record still has to exist."""

    #: Still inside the retention window. Missing it loses the claim.
    REQUIRED = "required"
    #: Past the window. Keep it anyway, it costs nothing, but a missing one is not
    #: a finding.
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class Capturer:
    """The person who took the capture, identified well enough to be deposed.

    Not a username. A username identifies an account, and the account is not the
    person who can testify, and the whole point of Rivera is that the *person* is
    what matters.
    """

    name: str
    #: Something that ties this person to the record independently of their word.
    #: An employer email is the usual answer. Free text rather than a typed
    #: EmployeeId, because the shape of an employer's directory is not ours to
    #: decide and requiring a particular one would exclude contractors.
    affiliation: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            msg = "an unnamed capturer cannot give testimony, which is the point"
            raise ValueError(msg)
        if not self.affiliation.strip():
            msg = "a capturer with no affiliation cannot be corroborated independently"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Capture:
    """One captured artifact, with the provenance the file itself cannot carry.

    ``sha256`` is computed at construction from the bytes. It is not optional and
    not caller supplied, because a caller supplied digest is a digest of whatever
    the caller had rather than of what we hold, and the difference is the whole
    point of a digest.
    """

    artifact_id: str
    captured_at: datetime
    captured_by: Capturer
    sha256: str
    media_type: str = "image/png"
    description: str = ""

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            msg = (
                "a capture with no timezone cannot be compared to a terminal's local "
                "time, and a two hour ambiguity is enough to move a day boundary"
            )
            raise ValueError(msg)
        if self.captured_at > datetime.now(UTC):
            msg = "a capture cannot have been taken in the future"
            raise ValueError(msg)

    @classmethod
    def from_bytes(
        cls,
        artifact_id: str,
        content: bytes,
        captured_at: datetime,
        captured_by: Capturer,
        **attributes: str,
    ) -> Capture:
        """Build a capture, taking the digest from the bytes we actually hold.

        ``attributes`` carries the optional descriptive fields. They are passed
        through rather than listed because they are neither provenance nor
        something a caller can get wrong in a way that matters here, and six named
        parameters for a constructor is a sign the type is doing too much.
        """
        return cls(
            artifact_id=artifact_id,
            captured_at=captured_at,
            captured_by=captured_by,
            sha256=hashlib.sha256(content).hexdigest(),
            **attributes,
        )

    def is_authenticated(self) -> bool:
        """True only when we can actually say who took this and when.

        The isinstance check is not defensive noise. The type makes captured_by
        required but cannot make it correct, because Python does not check argument
        types, and a record whose capturer is a bare string would otherwise report
        itself as authenticated. Failing closed here means a malformed record is
        inert rather than silently usable.
        """
        return isinstance(self.captured_by, Capturer) and bool(
            self.captured_by.name and self.captured_at
        )


@dataclass(frozen=True, slots=True)
class Retention:
    """How long a record must survive, and whether it is still required.

    UNVERIFIED on the window. The specific retention period for a freight claim
    was not transcribed for this issue, and 365 days is a working default chosen to
    be *longer* than any plausible bar rather than to be correct. Being wrong in the
    direction of keeping things longer is the safe direction for evidence.
    """

    as_of: date
    window: timedelta = _CLAIM_RETENTION

    def expires_on(self, capture: Capture) -> date:
        """The date this record stops being required."""
        return capture.captured_at.date() + self.window

    def state(self, capture: Capture) -> Retained:
        """Required until the window has run out from the capture.

        The window runs forward from when the evidence was taken, because that is
        when the dispute's clock started running against the carrier and therefore
        when our need for the record began.
        """
        return Retained.REQUIRED if self.as_of <= self.expires_on(capture) else Retained.OPTIONAL

    def days_remaining(self, capture: Capture) -> int:
        """Negative once the window has passed.

        Signed rather than clamped, because "expired 40 days ago" and "expired
        sometime" are different facts and a clamp loses the first one.
        """
        return (self.expires_on(capture) - self.as_of).days


@dataclass(frozen=True, slots=True)
class Register:
    """Every capture in a dispute."""

    captures: tuple[Capture, ...] = ()

    def unauthenticated(self) -> tuple[Capture, ...]:
        """Captures we cannot attribute. Always empty; see :meth:`Capture.is_authenticated`."""
        return tuple(c for c in self.captures if not c.is_authenticated())

    def by_capturer(self) -> dict[str, tuple[Capture, ...]]:
        """Grouped by person, for the Rivera question of who can testify."""
        grouped: dict[str, list[Capture]] = {}
        for capture in self.captures:
            if not capture.is_authenticated():
                continue
            grouped.setdefault(capture.captured_by.name, []).append(capture)
        return {k: tuple(v) for k, v in grouped.items()}

    def attestable_by(self, capturer: Capturer) -> bool:
        """Whether this person can give testimony covering something in the register.

        Matched on affiliation as well as name, so a name collision across two
        employers does not let the wrong person swear to the capture. Malformed
        records are skipped rather than raising, so one bad row cannot stop
        somebody being assessed.
        """
        return any(
            c.is_authenticated()
            and c.captured_by.name == capturer.name
            and c.captured_by.affiliation == capturer.affiliation
            for c in self.captures
        )

    def attests_all(self) -> bool:
        """Whether one person can account for the whole register.

        The practical Rivera question. A register captured by three people needs
        three testimonies, and knowing that in advance is the difference between
        planning for it and discovering it at the deposition.
        """
        return len(self.by_capturer()) <= 1
