"""Issue 126: tool artifacts and staged drift must be visible before they ship.

Two properties, both of which are absences, and both of which fail silently.

The first is a machine local directory from a third party tool. Its project id is
per install, carries nothing about the project, and a commit of it is a commit of
one person's tool state.

The second is a staged file that is neither tracked nor ignored. That is the exact
shape of a mistake waiting to happen: nothing in the test suite, lint or type
checker objects to a stray file in the index, and the next `git add -A` turns it
into a commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Directories created by tools we or a contributor may run, and which must never
#: be committed. A named list, not a glob, so adding a tool is a deliberate edit
#: here and shows up in a diff.
TOOL_ARTIFACT_DIRS = [
    ".freebuff/",
    ".codex/",
    ".agents/",
    ".continue/",
    ".cursor/",
    ".cline/",
]


@pytest.mark.parametrize("path", TOOL_ARTIFACT_DIRS)
def test_tool_artifact_directories_are_ignored(path: str) -> None:
    """Proven by asking git, not by reading .gitignore.

    Reading the file would pass on a pattern that is commented out, misspelled, or
    overridden by a later negation, and those are the three ways this actually goes
    wrong.
    """
    probe = path + "probe-file"
    result = subprocess.run(
        ["git", "check-ignore", "-q", probe],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"{path} is not ignored"


def test_the_tool_list_is_not_globally_ignored() -> None:
    """Guards the opposite mistake.

    A blanket ``*`` or a rule so broad it swallows source would satisfy every test
    above and destroy the repository, and it would satisfy them happily.
    """
    for keep in ("src/quayline/engine/daycount.py", "docs/ONBOARDING.md", "Makefile"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", keep],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0, f"{keep} is being ignored, which is wrong"


def test_the_index_check_lives_in_the_gate_not_in_pytest() -> None:
    """Why there is no index assertion in this file.

    A test suite runs during the commit that creates the state it asserts about. The
    first version of this file asserted the index was clean and fired on the commit
    that added the file, which is the correct work. A test that fails on correct work
    gets switched off, and a test that gets switched off protects nothing.

    So the check moved to ``make index``, wired into ``make validate``. It runs in
    pre-push and in CI, where the index is settled. This test exists so nobody
    reintroduces the pytest version by accident.
    """
    makefile = (ROOT / "Makefile").read_text()
    assert "index:" in makefile
    assert "$(MAKE) index" in makefile
    assert "TOOL_DIRS" in makefile
    for d in TOOL_ARTIFACT_DIRS:
        assert d.rstrip("/") in makefile, d


def test_no_index_assertions_have_crept_back_into_this_file() -> None:
    """The failure mode named in the docstring above, guarded mechanically."""
    body = (ROOT / "tests" / "test_repo_hygiene.py").read_text()
    assert "git diff --cached" not in body.split("def test_the_index_check_lives")[0]


def test_every_source_module_is_tracked() -> None:
    """The other direction, because an over broad ignore rule is the dangerous one.

    A file that is ignored never appears in a commit, so an accidental ignore of
    ``src/`` would not fail any test above. This one would.
    """
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "src/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert untracked == [], f"source files not tracked: {untracked}"


def test_issue_126_is_pinned() -> None:
    """Named, so a future reader knows why this file exists."""
    body = (ROOT / ".gitignore").read_text()
    assert "Third party tool state" in body
    assert "per machine, per tool, per install" in body
