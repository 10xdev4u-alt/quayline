"""The typed field parsers behind ``ingest/bind.py``.

Split out in issue 185 because ``bind.py`` crossed the four hundred line limit in
``AGENTS.md`` section six. The split is by concern rather than by size: this module
knows how to turn a string into a ``date``, an ``int`` or a ``Decimal`` and how to
collect labelled lines, and knows nothing about what a ledger is.

The error messages are the reason this is a module and not three helpers inside
``bind.py``. Every refusal quotes the line that caused it, because a gate that blocks
without naming the line leaves the person holding the document unable to say what we
could not read. That is the failure mode ``docs/research/004-evidence.md`` names for
the whole dispute layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

#: Matches a labelled value at the start of a line. The label set is deliberately
#: small: every alias added here is a field we will then claim to have read.
_LABELLED = re.compile(r"^(?P<label>[A-Za-z][A-Za-z /]*?):\s*(?P<value>.+?)\s*$")

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%B %d, %Y")


class FieldError(ValueError):
    """The value is present and unreadable. Our problem, so our message.

    The root of the bind error family. ``bind.py`` makes its own ``BindError``
    subclass this rather than the other way round, because this module knows nothing
    about ledgers and ``bind.py`` imports it. One ``except`` at the call site then
    catches both an unreadable value and an absent disclosure, which is what a caller
    that only wants to stop actually wants.
    """


@dataclass(frozen=True, slots=True)
class Fields:
    """Raw labelled values, keeping the line each came from."""

    values: dict[str, str]
    line_of: dict[str, str]

    def get(self, *labels: str) -> str | None:
        for label in labels:
            found = self.values.get(label.lower())
            if found is not None:
                return found
        return None

    def quoted(self, label: str, fallback: str) -> str:
        return self.line_of.get(label.lower(), fallback)

    def demand(self, labels: tuple[str, ...], on_absent: Exception) -> str:
        """A required label, or whatever ``on_absent`` raises.

        The exception is supplied by the caller because the omission type belongs to
        ``bind.py``: whether an absent field is an omission against the carrier under
        541.5, or an extraction fault of ours, is a judgement the binder makes and the
        field scanner has no opinion about.
        """
        found = self.get(*labels)
        if found is None:
            raise on_absent
        return found


def read_fields(lines: tuple[str, ...]) -> Fields:
    """Collect labelled values from the lines, first occurrence winning."""
    values: dict[str, str] = {}
    line_of: dict[str, str] = {}
    for raw in lines:
        matched = _LABELLED.match(raw.strip())
        if matched is None:
            continue
        label = matched.group("label").strip().lower()
        if label not in values:
            values[label] = matched.group("value").strip()
            line_of[label] = raw.strip()
    return Fields(values=values, line_of=line_of)


def parse_date(token: str) -> date | None:
    """A date in one of the accepted formats, or ``None``.

    Three of the four formats are unverified against real carrier invoices and that
    is flagged in the pull request that introduced them. An unrecognised format is
    refused rather than guessed, so a real carrier's date style is a hole we ship
    rather than a silent misreading.
    """
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def parse_int(raw: str, field: str, where: str) -> int:
    token = raw.split(maxsplit=1)[0] if raw.split() else raw
    try:
        return int(token)
    except ValueError as exc:
        raise FieldError(f"the {field} is not a whole number. The line says {where!r}.") from exc


def parse_decimal(raw: str, field: str, where: str) -> Decimal:
    token = raw.replace(",", "").replace("$", "").strip()
    try:
        return Decimal(token)
    except InvalidOperation as exc:
        raise FieldError(
            f"the {field} is not an amount we can read. The line says {where!r}."
        ) from exc


__all__ = [
    "FieldError",
    "Fields",
    "parse_date",
    "parse_decimal",
    "parse_int",
    "read_fields",
]
