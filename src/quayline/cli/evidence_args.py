"""Issue 183: turning ``--evidence`` arguments into captures.

Split out of ``audit_cmd.py`` so the command module stays under the four hundred
line limit in ``AGENTS.md`` section six, and so the argument handling is testable
without running an audit.

Three refusals, all of them refusals to guess

**No capturer.** ``Capturer`` refuses an empty name and an empty affiliation, and the
command refuses before that. A default capturer would be a fabricated witness, which
is the one thing an evidence record must not be.

**No kind.** A file called ``evidence.png`` does not say whether it is an appointment
screenshot or a service contract, and attaching the wrong kind to a claim is a filing
error a carrier can use against us. So the kind is named. The table below maps a short
name to the ``Artifact`` enum's own wording, which is the wording that appears in a
carrier's own rules.

**No naive timestamps.** The capture time is the file's modification time converted to
UTC. ``Capture.__post_init__`` refuses a naive timestamp, and a local time we cannot
vouch for is worse than none.

The media type is the one thing inferred, and it says so: an unrecognised extension
becomes ``application/octet-stream`` rather than a guess at a real type.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from quayline.evidence.capture import Capture, Capturer

#: Short name to the carrier's own wording for the artifact.
KINDS: dict[str, str] = {
    "appointment": "appointment unavailability screenshot",
    "contract": "service contract documentation",
    "charges": "the specific charges disputed",
    "explanation": "comprehensive explanation",
    "bol": "bill of lading number",
    "statement": "shipper statement",
}

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".json": "application/json",
}


class EvidenceArgsError(RuntimeError):
    """The evidence flags do not describe a capture we can build."""


def media_type_for(path: Path) -> str:
    """A media type from the extension, honest about the guess."""
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def capture_request(args: argparse.Namespace) -> tuple[Capture, ...]:
    """Build one capture per ``--evidence`` path, or refuse the whole set.

    All of them or none. A partly attached dispute is worse than a blocked one,
    because the letter goes out carrying half the evidence and nobody notices which
    half is missing until the carrier asks.
    """
    paths = [Path(e) for e in getattr(args, "evidence", []) or []]
    if not paths:
        return ()

    if not args.capturer or not args.affiliation:
        raise EvidenceArgsError(
            "--evidence needs --capturer and --affiliation. A capture with no "
            "attested capturer cannot support a claim, and a default one would be a "
            "fabricated witness."
        )
    if not args.kind:
        raise EvidenceArgsError(
            "--evidence needs --kind. The artifact kind is named rather than read "
            "off the filename, because a file called evidence.png does not say "
            "whether it is an appointment screenshot or a service contract."
        )

    capturer = Capturer(name=args.capturer, affiliation=args.affiliation)
    captures = []
    for path in paths:
        if not path.exists():
            raise EvidenceArgsError(f"no such evidence file: {path}")
        captures.append(
            Capture.from_bytes(
                path.name,
                path.read_bytes(),
                datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                capturer,
                media_type=media_type_for(path),
                description=f"{path} attached by the operator",
            )
        )
    return tuple(captures)


__all__ = ["KINDS", "EvidenceArgsError", "capture_request", "media_type_for"]
