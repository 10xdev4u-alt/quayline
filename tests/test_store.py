"""Issue 49: the bytes, hashed at ingest, in a log nobody can rewrite.

The load bearing test is ``test_a_tampered_log_fails_verification``. Every other
test here checks that good records verify, and all of those would pass against a
log that nobody can tamper with because nobody tried. A chain that has never seen
an edit is a chain whose tamper-evidence is untested.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quayline.evidence.checklist import Artifact, Ground
from quayline.evidence.packet import EvidenceItem
from quayline.ingest import store as module
from quayline.ingest.store import DocumentRef, IngestLog, sha256_hex

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "born_digital_invoice.pdf"


def log_at(tmp_path: Path) -> IngestLog:
    return IngestLog(tmp_path / "ingest.jsonl")


def ref_for(content: bytes = b"invoice bytes") -> DocumentRef:
    return DocumentRef.ingest(content, source="carrier portal")


# ---------------------------------------------------------------- criterion 1
# Every ingested document records a SHA-256 computed at ingest.


def test_the_digest_is_sha256_of_the_bytes_held() -> None:
    """Not supplied by the caller. A caller-supplied digest is a digest of whatever
    the caller had, which defeats the entire purpose."""
    content = FIXTURE.read_bytes()
    assert ref_for(content).sha256 == hashlib.sha256(content).hexdigest()
    assert len(ref_for(content).sha256) == 64


def test_different_bytes_give_different_digests() -> None:
    assert ref_for(b"a").sha256 != ref_for(b"b").sha256


def test_matches_recomputes_rather_than_comparing_a_stored_copy() -> None:
    """A stored copy is what is being authenticated, so comparing against one
    would be circular."""
    content = FIXTURE.read_bytes()
    ref = ref_for(content)
    assert ref.matches(content) is True
    assert ref.matches(content + b"x") is False


def test_a_ref_is_immutable() -> None:
    with pytest.raises(AttributeError):
        ref_for().sha256 = "x"  # type: ignore[misc]


def test_ingest_stamps_time_and_source() -> None:
    before = datetime.now(UTC)
    ref = DocumentRef.ingest(b"x", source="portal")
    assert before <= ref.ingested_at <= datetime.now(UTC)
    assert ref.source == "portal"
    assert ref.media_type == "application/pdf"


# ---------------------------------------------------------------- criterion 2
# The hash is written to an append-only log.


def test_appending_chains_each_entry_to_the_last(tmp_path: Path) -> None:
    log = log_at(tmp_path)
    first = log.append(ref_for(b"one"))
    second = log.append(ref_for(b"two"))
    assert first.prev_hash == ""
    assert second.prev_hash == first.entry_hash
    assert first.entry_hash != second.entry_hash


def test_the_log_has_no_write_operation_but_append(tmp_path: Path) -> None:
    """No update, no delete, no rewrite. A log with an UPDATE statement is a log
    that can be edited."""
    assert not hasattr(log_at(tmp_path), "update")
    assert not hasattr(log_at(tmp_path), "delete")
    assert not hasattr(log_at(tmp_path), "rewrite")
    assert not hasattr(log_at(tmp_path), "remove")


def test_a_tampered_log_fails_verification(tmp_path: Path) -> None:
    """The test this whole file is for.

    Edit one byte of one entry's digest in the file, and the chain breaks. That is
    the property FRE 902(14) needs: tampering detectable by recomputation rather
    than by trust.
    """
    log = log_at(tmp_path)
    log.append(ref_for(b"one"))
    log.append(ref_for(b"two"))
    assert log.verify() is True

    path = tmp_path / "ingest.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["sha256"] = "0" * 64
    lines[0] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert log.verify() is False


def test_a_reordered_log_fails_verification(tmp_path: Path) -> None:
    """Swapping two lines breaks the chain, because each entry commits to its
    predecessor. Insertion and deletion break it the same way."""
    log = log_at(tmp_path)
    log.append(ref_for(b"one"))
    log.append(ref_for(b"two"))
    path = tmp_path / "ingest.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")
    assert log.verify() is False


def test_a_malformed_line_is_not_silently_skipped(tmp_path: Path) -> None:
    """A corrupt line that vanishes into a skip is a hole nobody can see."""
    log = log_at(tmp_path)
    log.append(ref_for(b"one"))
    path = tmp_path / "ingest.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"sha256": "x"}\n')
    with pytest.raises((ValueError, KeyError)):
        log.entries()


def test_an_empty_log_verifies(tmp_path: Path) -> None:
    """Vacuously. There is nothing to have tampered with."""
    assert IngestLog(tmp_path / "new.jsonl").verify() is True


def test_len_counts_entries(tmp_path: Path) -> None:
    log = log_at(tmp_path)
    assert len(log) == 0
    log.append(ref_for(b"one"))
    assert len(log) == 1


# ---------------------------------------------------------------- criterion 3
# The hash is carried into the evidence packet.


def test_a_ref_travels_by_value_not_by_reference() -> None:
    """Copied at construction, because a reference to a mutable record is a
    reference that can change."""
    ref = ref_for(b"bytes")
    assert ref.sha256 == sha256_hex(b"bytes")
    assert isinstance(ref.sha256, str)


def test_the_packet_can_carry_the_hash() -> None:
    """The hash goes with every finding derived from the document, so a finding
    without one is a finding nobody can authenticate."""
    ref = ref_for(FIXTURE.read_bytes())
    item = EvidenceItem(
        ground=Ground.GOVERNMENT_HOLD,
        kind=Artifact.BOL_NUMBER,
        description=f"bill of lading, sha256:{ref.sha256}",
        source="carrier portal",
    )
    assert ref.sha256 in str(item)


# ---------------------------------------------------------------- criterion 4
# The hash is recomputed and matches on a fixture.


def test_the_fixture_hash_is_recomputed_and_matches() -> None:
    """A real PDF from the corpus, hashed at ingest and matched by recomputation.
    Not a hash compared against a stored string, which would prove only that two
    copies of one string agree."""
    content = FIXTURE.read_bytes()
    ref = DocumentRef.ingest(content, source="tests/fixtures/born_digital_invoice.pdf")
    assert ref.matches(content) is True

    log_path = FIXTURE.parent / "_probe.jsonl"
    try:
        log = IngestLog(log_path)
        log.append(ref)
        assert log.verify() is True
        assert log.entries()[0].sha256 == ref.sha256
    finally:
        log_path.unlink(missing_ok=True)


def test_sha256_hex_is_the_single_digest_function() -> None:
    assert sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_issue_49_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 49" in flat
    assert "902(14)" in flat


def test_the_module_states_what_the_log_does_not_store() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "does not store the documents" in flat
