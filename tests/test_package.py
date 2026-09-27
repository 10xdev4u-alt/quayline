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
