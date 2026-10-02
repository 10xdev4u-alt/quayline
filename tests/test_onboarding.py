"""The onboarding document's own numbers, checked against the repository.

`docs/ONBOARDING.md` opens by telling a new contributor to read it end to end, and
states a count of lines, modules and tests so they can size the thing up. Issue 203
found that count had drifted: it said 50 modules and 1,207 tests against an actual 81
and 1,428, and the module map predated the two packages holding the product's actual
interface.

A stale number in an onboarding document is worse than no number, because it looks
measured. The document already warns that its figures move and asks the reader to treat
`make validate` as authoritative, which is the right advice and also the kind of advice
that means nothing is checked.

So this checks the figures that cost nothing to verify, and only those. Issue counts are
deliberately absent: they need the network, and a test that fails when a device is
offline trains people to ignore it. Those two figures stay dated prose.

The comparison is structural, not textual. Asserting the document contains the literal
string "81 modules" would break when someone writes "across eighty-one modules" and
assert nothing, and asserting it merely mentions 81 would pass on a stale line and a
fresh comment.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "ONBOARDING.md"
SRC = REPO / "src" / "quayline"


def _document() -> str:
    return DOC.read_text()


def _modules() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if p.name != "__init__.py"]


def test_document_exists() -> None:
    assert DOC.is_file(), "the onboarding document is the first thing a contributor reads"


def test_line_count_is_current() -> None:
    lines = sum(len(p.read_text().splitlines()) for p in _modules())
    assert f"{lines:,} lines" in _document(), (
        f"the document's line count is stale, it is {lines:,} now. Measure it, update it, "
        f"and put the commit you measured at on the line."
    )


def test_module_count_is_current() -> None:
    count = len(_modules())
    assert f"{count} modules" in _document(), (
        f"the document's module count is stale, it is {count} now"
    )


def test_test_count_is_current() -> None:
    """The figure has to survive the comma, which is how this check was first wrong.

    Adding a test therefore requires refreshing this figure. That is the point rather
    than an accident: the number is read by people who will never run the suite, and a
    count they cannot trust is worse than one that is two hours out of date.
    """
    collected = subprocess_collect()
    assert f"{collected:,} tests" in _document(), (
        f"the document's test count is stale, it is {collected:,} now"
    )


def subprocess_collect() -> int:
    """Collect test count without running the suite, and without the network."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    ).stdout
    # This project's addopts print one "path: N" line per file and no summary, so the
    # total has to be summed rather than read off the end.
    per_file = re.findall(r"^tests/\S+\.py: (\d+)$", out, re.MULTILINE)
    assert per_file, f"could not read a test count from pytest --collect-only:\n{out[-400:]}"
    return sum(int(n) for n in per_file)


def test_every_package_is_named_in_the_map() -> None:
    """A package missing from the map is one a contributor will not find code in."""
    doc = _document()
    missing = [
        package.name
        for package in sorted(SRC.iterdir())
        if package.is_dir() and package.name != "__pycache__" and f"{package.name}/" not in doc
    ]
    assert not missing, (
        f"the module map omits {missing}. serve/ and web/ hold the intake, the letter and "
        f"the filing copy, and a reader who cannot find them cannot work on them."
    )


def test_every_file_the_map_names_exists() -> None:
    """Two filenames in the map were invented when this was written. Both were caught
    by checking, and this is the check, because a map that names a module that does not
    exist sends a reader looking for code that was never written.

    ``.githooks`` and ``tests`` are outside the package and are legitimately named in
    the prose, so they are exempt rather than listed.
    """
    src = SRC
    outside = {"check_commit_msg", "test_ordering"}
    named = set(re.findall(r"\b([a-z_]+)\.py\b", _document()))
    missing = sorted(name for name in named - outside if not list(src.rglob(name + ".py")))
    assert not missing, (
        f"the document names {missing}, which do not exist under src/quayline. Either the "
        f"map is wrong or the module is missing, and a reader cannot tell which."
    )


def test_snapshot_carries_the_commit_it_was_measured_at() -> None:
    """A figure with no commit on it cannot be checked, and drifts silently."""
    doc = _document()
    measured = re.findall(r"Measured at commit (\w+)", doc)
    assert measured, "the document states figures without saying when they were true"
    for commit in measured:
        assert re.fullmatch(r"[0-9a-f]{7,40}", commit), (
            f"{commit} is not a commit hash, so a reader cannot check the figure against it"
        )


def test_the_document_does_not_claim_to_be_authoritative() -> None:
    assert "`AGENTS.md` is the authority" in _document(), (
        "the document must defer to AGENTS.md, and say so, or it becomes a second "
        "authority that can disagree with the first"
    )
