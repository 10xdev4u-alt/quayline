"""Smoke tests proving the toolchain is wired correctly.

These exist to fail loudly when packaging, path configuration or the version
metadata break, not to test behaviour.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import quayline

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports() -> None:
    assert quayline.__name__ == "quayline"


def test_version_is_a_string() -> None:
    assert isinstance(quayline.__version__, str)
    assert quayline.__version__


def test_version_tracks_pyproject() -> None:
    """A drifting version is a real bug when findings cite rule tables by version.

    The version travels into the 902(13) certification template, so a stale value
    would certify the wrong engine.
    """
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert quayline.__version__ == declared


def _validate_target() -> str:
    makefile = (ROOT / "Makefile").read_text()
    marker = "validate:"
    start = makefile.index(marker)
    rest = makefile[start + len(marker) :]
    # The target body runs until the next target or the end of the file.
    end = len(rest)
    for terminator in ("\n\n", "\n.PHONY"):
        if terminator in rest:
            end = min(end, rest.index(terminator))
    return rest[:end]


def test_validate_target_runs_all_four_gate_steps() -> None:
    body = _validate_target()
    for step in ("$(PYTEST)", "$(RUFF) check .", "$(RUFF) format --check .", "$(MYPY)"):
        assert step in body, f"the validate target is missing {step}"


def test_gate_tools_resolve_from_the_project_venv() -> None:
    """The declared dev group has to actually land on disk.

    Checks resolution, not behaviour. It does not import the tools, because
    importing a linter inside a test the linter is meant to check is a good way
    to make both slow.
    """
    venv_bin = ROOT / ".venv" / "bin"
    for tool in ("pytest", "ruff", "mypy"):
        binary = venv_bin / tool
        assert binary.exists(), f"{tool} did not install into the project venv at {binary}"
        assert binary.is_file()


def test_makefile_installs_the_declared_dev_group() -> None:
    """Naming tools on the install line lets an older version on the machine
    satisfy the command and leaves the declared minimums as dead text."""
    makefile = (ROOT / "Makefile").read_text()
    assert "--group dev" in makefile, "make install does not install the declared dev group"
