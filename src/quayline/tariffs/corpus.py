"""Issue 39: a corpus of real numbers, and a loader that refuses to guess.

The problem this module exists to stop, stated once: **a test that encodes a
plausible but wrong rate is worse than no test**, because it fails green on every
run and teaches everyone who reads it that the wrong number is the real one.

So the rule is that a number in a fixture was read from a primary source we hold a
record of, or the fixture does not exist. There is no synthetic data, no rounded
illustration, no "representative example". A fixture that cannot name its source
PDF and its effective date is not loaded, and the loader raises rather than
skipping, because a skipped fixture is a hole nobody can see and a raised one is a
hole with a name on it.

What the checksum does and does not prove

Every fixture carries a SHA-256 over the transcription: the numbers, the filename,
the effective date, the carrier, the cluster, the equipment and the tiers, in a
canonical order. The loader recomputes it before it returns a single block.

That checksum proves **the fixture has not changed since it was written**. It does
not prove the fixture was ever right. A transcription error made on day one has the
correct checksum on day two. Correctness comes from the source record and from a
second pair of eyes, and nothing in this module substitutes for either. The
checksum's job is narrower and still worth doing: it turns every later edit to a
rate, accidental or deliberate, into a loud failure instead of a quiet drift.

What is here and what is deliberately absent

The Maersk cluster table is transcribed from `docs/research/002-carriers.md`,
researched 2026-09-27 from the carrier's tariff PDFs, with calendar-day charging
effective 2024-08-08. Eight rows, and every one of them is a real row from the
source.

The Hapag detention schedules are **not** here. Issue 14 names the source
(`USA_Detention_Effective_October_01_2025.pdf`) but the six schedules are not
transcribed yet, so there is nothing to check against. Writing a fixture from the
issue's paraphrase would be exactly the plausible-but-wrong test this issue was
opened to forbid.

The CMA CGM, MSC, ONE and ZIM numbers are not here either, for the same reason and
several more. An absent fixture is a hole in the report, and a hole is cheap.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from quayline.tariffs.blocks import RateBlock, Tier

#: Where the transcribed rates live. Checked in, because a corpus that is not in
#: version control is not a corpus, it is a folder on somebody's machine.
#:
#: Resolved against this file rather than left relative to the working directory.
#: Issue 208: it used to be the string ``"tests/fixtures/tariffs"``, which meant the
#: engine resolved rates only when run from the repository root. From anywhere else,
#: including from inside a container, every audit came back ``tariff_unresolved`` and
#: said so confidently, so the failure mode looked like "your carrier has no matching
#: rate" rather than "this program cannot find its own data".
#:
#: ``parents[3]`` is the repository root from ``src/quayline/tariffs/corpus.py``. A
#: checkout, an installed package and the container image all keep that shape; a
#: zipapp or a PyInstaller bundle does not, and `QUAYLINE_CORPUS_DIR` is the override
#: for those.
_DEFAULT_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = os.environ.get("QUAYLINE_CORPUS_DIR") or str(_DEFAULT_ROOT / "tests/fixtures/tariffs")


class FixtureError(ValueError):
    """A fixture that may not be used. The message names the file and the reason."""


def canonical_bytes(record: dict[str, object]) -> bytes:
    """The bytes the checksum covers.

    Canonical JSON: sorted keys, no whitespace, UTF-8. Every field that affects the
    transcribed rate is included, and nothing that does not, so reformatting the
    file cannot break the checksum but changing a number always does.
    """
    covered = {
        "carrier": record["carrier"],
        "cluster": record["cluster"],
        "equipment": record["equipment"],
        "free_days": record["free_days"],
        "tiers": record["tiers"],
        "source_pdf": record["source_pdf"],
        "effective_date": record["effective_date"],
        "rule": record["rule"],
    }
    return json.dumps(covered, sort_keys=True, separators=(",", ":")).encode("utf-8")


def checksum_of(record: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(record)).hexdigest()


def load_fixture(path: str | Path) -> RateBlock:
    """Load one fixture, or raise.

    Refuses, in order: a file that is not valid JSON, a fixture without a source
    PDF or an effective date, a fixture whose checksum does not recompute, and a
    fixture that is marked UNVERIFIED. Each is a different failure with a different
    fix, so each gets its own message rather than one generic one.
    """
    path = Path(path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"{path}: not readable as JSON: {exc}") from exc

    if not isinstance(record, dict):
        raise FixtureError(
            f"{path}: the top level must be an object, found {type(record).__name__}"
        )

    for field in ("source_pdf", "effective_date"):
        if not record.get(field):
            raise FixtureError(
                f"{path}: no {field}. A fixture that cannot name its source is not "
                f"loaded, because a number without a source is a guess with a filename."
            )

    stored = record.get("checksum", "")
    if not stored:
        raise FixtureError(f"{path}: no checksum. Write it with `make fixtures-checksum`.")
    computed = checksum_of(record)
    if stored != computed:
        raise FixtureError(
            f"{path}: checksum mismatch. The transcription changed since it was "
            f"recorded. Either the numbers were edited deliberately, in which case "
            f"recompute with `make fixtures-checksum`, or accidentally, in which case "
            f"this error just saved a demand letter."
        )

    if record.get("verified") is False:
        raise FixtureError(f"{path}: marked UNVERIFIED. {record.get('note', 'No note recorded.')}")

    try:
        tiers = tuple(
            Tier(from_day=t["from_day"], to_day=t.get("to_day"), rate=Decimal(str(t["rate"])))
            for t in record["tiers"]
        )
        return RateBlock(
            rule=str(record["rule"]),
            carrier=str(record["carrier"]),
            cluster=str(record["cluster"]),
            equipment=str(record["equipment"]),
            free_days=int(record["free_days"]),
            tiers=tiers,
            source=str(record["source_pdf"]),
            effective_from=str(record["effective_date"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FixtureError(f"{path}: structurally invalid: {exc}") from exc


def load_corpus(root: str | Path | None = None) -> dict[str, RateBlock]:
    """Every fixture under the corpus directory, keyed by rule.

    One corrupt fixture fails the whole load. A corpus that returns the seven good
    rows and silently drops the eighth is a report about seven rows that reads as a
    report about eight.
    """
    directory = Path(root) if root else Path(CORPUS_DIR)
    blocks: dict[str, RateBlock] = {}
    for path in sorted(directory.glob("*.json")):
        block = load_fixture(path)
        if block.rule in blocks:
            raise FixtureError(f"{path}: duplicate rule {block.rule!r}")
        blocks[block.rule] = block
    if not blocks:
        raise FixtureError(f"{directory}: no fixtures. An empty corpus answers nothing.")
    return blocks


@dataclass(frozen=True, slots=True)
class CorpusReport:
    """What the corpus holds, for issue 84's coverage report."""

    rules: tuple[str, ...]
    carriers: tuple[str, ...]
    clusters: tuple[str, ...]

    @classmethod
    def from_corpus(cls, corpus: dict[str, RateBlock]) -> CorpusReport:
        return cls(
            rules=tuple(sorted(corpus)),
            carriers=tuple(sorted({b.carrier for b in corpus.values()})),
            clusters=tuple(sorted({b.cluster for b in corpus.values()})),
        )


__all__ = [
    "CORPUS_DIR",
    "CorpusReport",
    "FixtureError",
    "canonical_bytes",
    "checksum_of",
    "load_corpus",
    "load_fixture",
]
