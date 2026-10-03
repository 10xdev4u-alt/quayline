"""Issue 208: the three paths that only worked from the repository root.

Building the container image found all three in about ten minutes, and none of them was
visible to a test suite that runs from the root.

`tariffs/corpus.py`, `web/example.py` and `web/specimen.py` each held a path like
`Path("tests/fixtures/born_digital_invoice.pdf")`. Resolved against the working
directory, that is the repository root and nothing else.

The failure mode was worse than a crash. From anywhere else the corpus did not load, so
every audit returned `tariff_unresolved` and said so confidently: a self-hoster would
conclude their Maersk invoice had no matching rate rather than that the program could
not find its own data. The landing page raised FileNotFoundError and served nothing at
all.

So these tests chdir somewhere useless and require the paths still to resolve. It is the
cheapest possible check and it is the one that would have caught all three.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from quayline.tariffs.corpus import CORPUS_DIR
from quayline.web.example import FIXTURE as EXAMPLE_FIXTURE
from quayline.web.specimen import FIXTURE as SPECIMEN_FIXTURE


@pytest.fixture
def elsewhere(tmp_path: Path) -> object:
    """Run the body from a directory that is not the repository."""
    here = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(here)


def test_the_worked_example_resolves_from_anywhere(elsewhere: Path) -> None:
    assert EXAMPLE_FIXTURE.is_absolute(), "a relative fixture only exists from the root"
    assert EXAMPLE_FIXTURE.is_file(), f"{EXAMPLE_FIXTURE} does not exist"


def test_the_specimen_fixture_resolves_from_anywhere(elsewhere: Path) -> None:
    assert SPECIMEN_FIXTURE.is_absolute(), "a relative fixture only exists from the root"
    assert SPECIMEN_FIXTURE.is_file(), f"{SPECIMEN_FIXTURE} does not exist"


def test_the_corpus_resolves_from_anywhere(elsewhere: Path) -> None:
    assert Path(CORPUS_DIR).is_absolute()
    assert Path(CORPUS_DIR).is_dir(), f"{CORPUS_DIR} does not exist"


def test_no_module_resolves_a_data_path_relative_to_the_working_directory() -> None:
    """The general rule, so a fourth one is caught at the door.

    Scans module-level assignments for a string that names a repository directory. A
    docstring may quote `tests/fixtures/charge_table.pdf` as prose, which is correct and
    is not a runtime path, so only assignments count.

    Written after fixing three of these by hand and missing the fourth, which is the
    argument for having the check.
    """
    offenders: list[str] = []
    src = Path(__file__).resolve().parent.parent / "src" / "quayline"
    # Only the shape that is actually broken: a repository path handed straight to
    # Path() or assigned as a bare string. `tariffs/corpus.py` also mentions
    # "tests/fixtures/tariffs", but it resolves it against Path(__file__), and a
    # check that flagged the fixed file would train people to ignore it.
    patterns = (
        re.compile(r"""Path\(\s*["'](?:tests|config)/"""),
        re.compile(r"""^[A-Z_][A-Z_0-9]*\s*[:=]\s*["'](?:tests|config)/""", re.MULTILINE),
    )
    for module in src.rglob("*.py"):
        for number, line in enumerate(module.read_text().splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                offenders.append(f"{module.relative_to(src)}:{number}")
    assert not offenders, (
        f"these assign a repository path as a bare string, so they only resolve from the "
        f"root: {offenders}. Resolve against Path(__file__) or take an environment "
        f"override, as tariffs/corpus.py now does."
    )
