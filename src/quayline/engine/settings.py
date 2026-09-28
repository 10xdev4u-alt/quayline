"""Operator settings, read from a config file and reviewed like any other policy.

The tolerance band used to be a module constant in ``amount.py``. That was wrong
for two reasons and one of them was only noticed in review.

It was wrong because it is the only number in this repository with no source. Every
other figure is transcribed from a carrier, quoted from a regulation, or marked as
an estimate with the arithmetic shown. A band that decides whether a finding gets
filed belongs somewhere a reader will look for it and somewhere an operator can
change it, not in the middle of a pricing function.

And it was wrong because a constant in a pricing module reads as a fact about
pricing. ``TOLERANCE = Decimal("0.02")`` in the same file as the arithmetic looks
like part of how rates work. It is not. It is a decision about how aggressively to
litigate, and those are different things that happen to sit in one module.

The file is read at import time rather than on every comparison, because it does not
change during a run and because a settings object that can be re-read mid audit is a
settings object that can be inconsistent mid audit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "audit.json"


class SettingsError(ValueError):
    """The config is missing, malformed, or says something we will not guess at."""


@dataclass(frozen=True, slots=True)
class Tolerance:
    """A fraction, and an honest description of where it came from."""

    fraction: Decimal
    origin: str

    def band_for(self, amount: Decimal) -> Decimal:
        return abs(amount) * self.fraction

    def as_letter(self) -> str:
        return f"{self.fraction:.0%}"


def _require(raw: Any, key: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SettingsError(
            f"config/audit.json: {key!r} must be an object, got {type(raw).__name__}"
        )
    return raw


def load_tolerance(path: Path = CONFIG_PATH) -> Tolerance:
    """Read the tolerance band from the shipped config.

    Refuses rather than defaulting. A missing or malformed config would otherwise
    mean the engine silently files on a band nobody chose, and the whole point of
    moving the number out of the code is that it is a decision rather than a
    constant. Falling back to a hardcoded value would put it straight back.
    """
    if not path.exists():
        raise SettingsError(
            f"no audit config at {path}. The tolerance band is a decision about filing "
            f"aggression, not a constant, and there is no safe fallback for it."
        )
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SettingsError(f"config/audit.json is not valid JSON: {exc}") from exc

    block = _require(_require(raw, "root").get("tolerance"), "tolerance")
    literal = block.get("default_fraction")
    if not isinstance(literal, str):
        raise SettingsError(
            f"tolerance.default_fraction must be a string so the decimal is exact, got "
            f"{type(literal).__name__}. A float here would be a band nobody chose."
        )
    try:
        fraction = Decimal(literal)
    except InvalidOperation as exc:
        raise SettingsError(f"tolerance.default_fraction {literal!r} is not a decimal") from exc
    if not Decimal(0) <= fraction < 1:
        raise SettingsError(
            f"tolerance.default_fraction {fraction} must be at least 0 and under 1. A band "
            f"of 1 or more forgives every charge, which is not a tolerance."
        )
    return Tolerance(fraction=fraction, origin=f"config/audit.json: {path.name}")


# Read once, at import. A settings value that can be re-read mid audit is a
# settings value that can be inconsistent mid audit.
TOLERANCE = load_tolerance()


__all__ = [
    "CONFIG_PATH",
    "TOLERANCE",
    "SettingsError",
    "Tolerance",
    "load_tolerance",
]
