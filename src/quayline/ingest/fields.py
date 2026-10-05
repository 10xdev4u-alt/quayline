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

#: ``Label: value``. How the reference fixture states everything.
_LABELLED = re.compile(r"^(?P<label>[A-Za-z][A-Za-z /]*?):\s*(?P<value>.+?)\s*$")

#: ``Label      value``. How carriers state it, with the value in a column.
#:
#: Issue 216. The gap is two or more spaces, and that threshold is the whole safety
#: argument: a value contains single spaces routinely, so one space cannot be a delimiter
#: without splitting "USD 1,170.00" into a label of "USD". Two spaces do not occur inside
#: an invoice field value, and where one does the split is wrong in the safe direction,
#: producing a value we cannot parse rather than a number we will act on.
_COLUMN = re.compile(r"^(?P<label>[A-Za-z][A-Za-z0-9 /&'().]*?)\s{2,}(?P<value>\S.*?)\s*$")

#: How a carrier writes a date that is not ISO, not US slash, and not spelled out.
#: ``DD-MON-YYYY``, which is the style Maersk, Hapag and most of them use, and which
#: neither of the original four formats covered.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%d/%m/%Y",
)


#: Carrier wording, mapped to the label this repository uses.
#:
#: Issue 216. Each entry records whose wording it came from, because an alias without an
#: origin is a guess and a guess about a **date** is the most expensive kind of guess in
#: this codebase: a wrong date yields a plausible wrong day count, which is the failure
#: this whole repository exists to avoid.
#:
#: Deliberately conservative. Only mappings that appear on a real invoice are here, and
#: a word we cannot place confidently is left out, so the field stays unreadable and
#: issue 214 turns that into an honest refusal rather than a wrong number.
#:
#: Lower case, because ``read_fields`` lower cases every label it stores.
CARRIER_ALIASES: dict[str, str] = {
    # Maersk. Source: a US import detention and demurrage invoice, columns, uppercase.
    "invoice date": "invoice date",
    "b/l number": "bill of lading number",
    "b/l no": "bill of lading number",
    "bl number": "bill of lading number",
    "consignor b/l": "bill of lading number",
    "discharge port": "port of discharge",
    "port of discharge": "port of discharge",
    "free time allowed": "allowed free time",
    "free days allowed": "allowed free time",
    "free time commences": "start date of free time",
    "free time starts": "start date of free time",
    "free time expires": "end date of free time",
    "free time ends": "end date of free time",
    "container available": "container availability date",
    "available from": "container availability date",
    "availability": "container availability date",
    "detention days": "days",
    "demurrage days": "days",
    "per day charge": "rate",
    "per day rate": "rate",
    "daily rate": "rate",
    "detention total": "amount",
    "demurrage total": "amount",
    "total due": "total",
    "amount due": "total",
    "charged dates": "charged dates",
    "dates charged": "charged dates",
    "rate rule": "rate rule",
    "tariff rule": "rate rule",
}


#: The same table read backwards: canonical label to every carrier word that means it.
#:
#: Built once at import. The forward table maps what a carrier wrote to what this
#: repository calls it, and a lookup needs the other direction, because the document
#: stores the carrier's word and the binder asks for ours.
_BY_CANONICAL: dict[str, tuple[str, ...]] = {}
for _carrier_word, _canonical_name in CARRIER_ALIASES.items():
    _BY_CANONICAL.setdefault(_canonical_name, ())
    if _carrier_word not in _BY_CANONICAL[_canonical_name]:
        _BY_CANONICAL[_canonical_name] += (_carrier_word,)


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

    def canonical(self, label: str) -> str:
        """The label this repository uses for whatever the document called it.

        Issue 216. Translation happens here rather than in ``read_fields`` so the raw
        label survives, which matters because an error message that quotes our
        canonical name back at a reader holding a carrier invoice helps nobody.
        """
        return CARRIER_ALIASES.get(label, label)

    def get(self, *labels: str) -> str | None:
        """The first of ``labels`` the document states, in either vocabulary.

        Issue 216: each label is tried as written and again through ``CARRIER_ALIASES``,
        so a caller asks for the field it means and does not have to know that four
        different carriers each call the free time start something different.
        """
        for label in labels:
            wanted = label.lower()
            # The label as the caller wrote it, then every carrier word that means it.
            for name in (wanted, *_BY_CANONICAL.get(wanted, ())):
                found = self.values.get(name)
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
        stripped = raw.strip()
        if not stripped:
            continue
        matched = _LABELLED.match(stripped) or _COLUMN.match(stripped)
        if matched is None:
            continue
        label = matched.group("label").strip().lower()
        value = matched.group("value").strip()
        # A label with nothing after it is a heading. Reading it as a disclosure of the
        # empty string would make every ruled section of an invoice look like a field.
        if not label or not value:
            continue
        if label not in values:
            values[label] = value
            line_of[label] = stripped
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


#: Currency tokens carriers put in front of or behind an amount.
_CURRENCY = re.compile(
    r"(?i)\b(usd|eur|gbp|jpy|cad|aud|chf|dollars?|euros?)\b|[$\u20ac\u00a3\u00a5]"
)


def _ungroup(token: str) -> str:
    """Return ``token`` with thousands separators removed, or raise.

    Issue 216. The version this replaces stripped every comma unconditionally, so
    ``1.170`` parsed as one pound one hundred and seventy, on an invoice that may have
    been stating one thousand one hundred and seventy. A thousandfold error in a dispute
    letter is worse than no number, because it is plausible.

    Three cases, and only the last one is refused:

    - Both separators present. The **last** one is the decimal point, whichever it is,
      and the other groups thousands. ``1,170.00`` and ``1.170,00`` both mean 1170.00.
      This is unambiguous, and it is the only case in which both conventions can appear
      in one amount.
    - One separator kind, more than once. It is thousands grouping, and the group sizes
      are checked, so ``1,1,70`` is refused rather than read as eleven.
    - One separator, once. Accepted only when one or two digits follow, because a
      thousands group is always exactly three. ``1170.00`` and ``1170,00`` are both
      1170.00, while ``1.170`` and ``1,170`` are refused: one thousand one hundred and
      seventy in New York, one pound one hundred and seventy in Rotterdam, and nothing
      in the document says which.
    """
    commas, dots = token.count(","), token.count(".")
    if commas and dots:
        return _with_both_separators(token)
    if commas > 1 or dots > 1:
        return _with_grouping(token, "," if commas > 1 else ".")
    if commas == 1 or dots == 1:
        return _with_one_separator(token, "," if commas == 1 else ".")
    if not token:
        raise ValueError("empty amount")
    return token


def _with_both_separators(token: str) -> str:
    """The last separator is the decimal point; the other groups thousands."""
    if token.rfind(",") > token.rfind("."):
        written, frac, grouping = token[: token.rfind(",")], token[token.rfind(",") + 1 :], "."
    else:
        written, frac, grouping = token[: token.rfind(".")], token[token.rfind(".") + 1 :], ","
    whole = written.replace(",", "").replace(".", "")
    if not whole.isdigit() or not frac.isdigit():
        raise ValueError("unreadable amount")
    # Validate the grouping as written, separators still on. Removing them first is what
    # let `1,1,70` through as eleven: the evidence of a bad grouping is what the removal
    # destroys.
    if any(sep in written for sep in ",.") and not _grouping_is_legal(written, grouping):
        raise ValueError("bad thousands grouping either side of the decimal point")
    return f"{whole}.{frac}"


def _with_grouping(token: str, separator: str) -> str:
    """Thousands separators appearing more than once, with checked group sizes."""
    grouped, _, frac = token.rpartition(separator)
    if not frac.isdigit() or not _grouping_is_legal(grouped, separator):
        raise ValueError("unreadable thousands grouping")
    return grouped.replace(separator, "")


def _with_one_separator(token: str, separator: str) -> str:
    """One separator, once. A decimal point unless three digits follow, which refuses."""
    whole, _, frac = token.rpartition(separator)
    digits = whole.replace(",", "").replace(".", "")
    if not frac.isdigit() or len(frac) == _GROUP_SIZE or not digits.isdigit():
        raise ValueError("a single separator before three digits is ambiguous, refused")
    return f"{digits}.{frac}"


def _grouping_is_legal(grouped: str, separator: str) -> bool:
    """Whether a written-out thousands grouping could be a real one.

    A legal grouping is a first group of one to three digits and every group after it
    exactly three: ``1,170,000``, never ``11,70,000``.
    """
    parts = grouped.split(separator)
    if not _MIN_GROUPS <= len(parts) <= _MAX_GROUPS:
        return False
    if not all(part.isdigit() for part in parts):
        return False
    head, *rest = parts
    if not 1 <= len(head) <= _FIRST_GROUP_MAX:
        return False
    return all(len(part) == _GROUP_SIZE for part in rest)


#: Digits in a thousands group after the first, and the widest a first group may be.
_GROUP_SIZE = 3
_FIRST_GROUP_MAX = 3
#: A written grouping needs at least a first group and one three-digit group.
_MIN_GROUPS = 2
#: An invoice amount with more groups than this is not an invoice amount.
_MAX_GROUPS = 12


def parse_decimal(raw: str, field: str, where: str) -> Decimal:
    """An amount as carriers write it, or a refusal.

    Issue 216: strips a currency token and handles both thousands conventions. Refuses
    anything it cannot read rather than guessing, because a wrong amount here becomes a
    demand figure in a letter a person signs.
    """
    cleaned = _CURRENCY.sub(" ", raw).strip().replace(" ", "")
    try:
        token = _ungroup(cleaned)
    except ValueError as exc:
        raise FieldError(
            f"the {field} is not an amount we can read without guessing. The line says "
            f"{where!r}. Refused rather than risk stating a thousand times the figure."
        ) from exc
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
