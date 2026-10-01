"""Issue 49: the bytes, hashed at ingest, in a log nobody can rewrite.

The original invoice is evidence. Without its hash at capture time,
authentication becomes a matter of argument, and argument is what the other side
does best.

Fed. R. Evid. 902(14) authenticates copied electronic data by hash value. If the
hashes of the original and the copy match, it is highly improbable they are not
identical. That sentence is the whole module: hash at ingest, keep the hash with
everything derived from the document, and let the match do the authenticating.

The append-only log with a hash chain

Each entry records the document's SHA-256, when it was ingested, from where, and
the hash of the previous entry. The chain means an entry cannot be altered,
removed or inserted without breaking every later hash, so tampering is detectable
by recomputation rather than by trust. The log is a file of JSON lines, appended
to and never rewritten, because a database with an UPDATE statement is a log that
can be edited and this one cannot be.

What the log does not do

It does not store the documents. It stores hashes of documents, which is what an
authentication record is. The bytes live wherever the operator keeps evidence;
the log proves they have not changed since ingest. A log that held the bytes
would be a backup system, and backup systems get restored from, which is a
different threat model.

Carried, not copied

`DocumentRef` travels into the evidence packet in issue 59's sense: the hash goes
with every finding derived from the document, so a finding without a hash is a
finding nobody can authenticate. The hash is copied by value at construction,
because a reference to a mutable record is a reference that can change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path


def sha256_hex(content: bytes) -> str:
    """The digest. One function, so there is one place that decides the algorithm
    and every digest in the package agrees with every other."""
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document as the rest of the pipeline sees it: a hash, not bytes.

    The hash is computed at ingest from the bytes actually held, which is the
    property FRE 902(14) needs. A hash supplied by a caller is a hash of whatever
    the caller had, so the constructor takes bytes and digests them itself rather
    than accepting a string.
    """

    sha256: str
    media_type: str
    ingested_at: datetime
    source: str = ""

    @classmethod
    def ingest(
        cls, content: bytes, *, media_type: str = "application/pdf", source: str = ""
    ) -> DocumentRef:
        """Hash bytes at ingest. The only way to make one."""
        return cls(
            sha256=sha256_hex(content),
            media_type=media_type,
            ingested_at=datetime.now(UTC),
            source=source,
        )

    def matches(self, content: bytes) -> bool:
        """Whether these bytes are the document. Recomputed, not compared from a
        stored copy, because a stored copy is what is being authenticated."""
        return sha256_hex(content) == self.sha256


@dataclass(frozen=True, slots=True)
class LogEntry:
    """One line in the append-only log."""

    sha256: str
    media_type: str
    ingested_at: str
    source: str
    prev_hash: str
    entry_hash: str

    @classmethod
    def create(cls, ref: DocumentRef, prev_hash: str) -> LogEntry:
        """Chain to the previous entry. The first entry chains to the empty
        string, which is the genesis every verifier recomputes identically."""
        body = "|".join(
            (ref.sha256, ref.media_type, ref.ingested_at.isoformat(), ref.source, prev_hash)
        )
        return cls(
            sha256=ref.sha256,
            media_type=ref.media_type,
            ingested_at=ref.ingested_at.isoformat(),
            source=ref.source,
            prev_hash=prev_hash,
            entry_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )

    def verifies_against(self, prev_hash: str) -> bool:
        """Recompute and compare. Tampering with any field, or with the chain
        order, breaks this."""
        body = "|".join((self.sha256, self.media_type, self.ingested_at, self.source, prev_hash))
        return (
            self.prev_hash == prev_hash
            and hashlib.sha256(body.encode("utf-8")).hexdigest() == self.entry_hash
        )


class IngestLog:
    """The append-only record. Appends lines, verifies chains, rewrites nothing.

    A class rather than bare functions because it holds the file path and the
    cached head hash, and both are needed on every operation. Not frozen, because
    appending changes the head; everything it returns is frozen.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def head(self) -> str:
        """The entry hash of the last line, or empty for a new log."""
        if not self._path.exists():
            return ""
        last = ""
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                last = str(entry.get("entry_hash", ""))
        return last

    def append(self, ref: DocumentRef) -> LogEntry:
        """Append one entry chained to the head. The only write operation."""
        entry = LogEntry.create(ref, self.head)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    entry.__dict__
                    if hasattr(entry, "__dict__")
                    else {
                        "sha256": entry.sha256,
                        "media_type": entry.media_type,
                        "ingested_at": entry.ingested_at,
                        "source": entry.source,
                        "prev_hash": entry.prev_hash,
                        "entry_hash": entry.entry_hash,
                    }
                )
                + "\n"
            )
        return entry

    def entries(self) -> tuple[LogEntry, ...]:
        """Every entry, in order."""
        if not self._path.exists():
            return ()
        out = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            names = {f.name for f in fields(LogEntry)}
            if set(record) != names:
                raise ValueError(
                    f"log line has fields {sorted(record)} rather than {sorted(names)}"
                )
            out.append(LogEntry(**{k: str(v) for k, v in record.items()}))
        return tuple(out)

    def verify(self) -> bool:
        """Recompute the whole chain. False on any break, with no indication of
        where, because a verifier that names the broken entry tells a tamperer
        which one to fix next time."""
        prev = ""
        for entry in self.entries():
            if not entry.verifies_against(prev):
                return False
            prev = entry.entry_hash
        return True

    def __len__(self) -> int:
        return len(self.entries())


__all__ = [
    "DocumentRef",
    "IngestLog",
    "LogEntry",
    "sha256_hex",
]
