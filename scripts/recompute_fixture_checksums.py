"""Recompute every tariff fixture checksum. A write operation, run by hand.

Issue 39. The loader refuses a fixture whose checksum does not recompute, so a
deliberate transcription edit needs its checksum updated or the corpus fails to
load. This script does that, one file at a time, printing what changed so the diff
is reviewable before it is committed.

It recomputes. It never edits numbers. A script that touched the rates would be a
script that could silently rewrite the corpus, which is the one thing the checksum
exists to catch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quayline.tariffs.corpus import checksum_of

ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "tariffs"


def main() -> int:
    changed = 0
    for path in sorted(ROOT.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            print(f"skip {path.name}: not an object")
            continue
        old = record.get("checksum", "")
        new = checksum_of(record)
        if old != new:
            record["checksum"] = new
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(f"{path.name}: {old[:12] or '(none)'} -> {new[:12]}")
            changed += 1
        else:
            print(f"{path.name}: unchanged")
    print(f"{changed} fixture(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
