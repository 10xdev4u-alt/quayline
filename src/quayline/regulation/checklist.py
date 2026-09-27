"""The 46 CFR 541.6 invoice checklist, as published.

Twenty required disclosures in five groups: four in (a) identifying information,
eight in (b) timing information, three in (c) rate information, three in (d) dispute
information, and two in (e) certifications.

Every ``text`` in this module is verbatim from the eCFR, including the trailing
semicolons and conjunctions that make the regulation read as a list rather than as
twenty independent sentences. A lawyer needs to be able to diff this against the
published text and find nothing, so nothing here has been tidied. ``statement``
strips the trailing punctuation when a field needs to read as a sentence in a
dispute letter.

The text is generated from the eCFR XML by a script rather than typed by hand.
Twenty transcribed clauses is twenty chances to introduce a difference that
matters, and no reviewer would catch it by reading.

What this checklist is for. 541.6 is not an accuracy rule. It is a disclosure
rule, and its only consequence arrives through 541.5, which eliminates the
obligation to pay when a required minimum is missing. See ``kill_switch.py`` for
why that distinction has to be structural rather than a matter of care.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from quayline.regulation.source import SECTION_541_6

__all__ = [
    "CHECKLIST",
    "GROUP_HEADINGS",
    "SECTION_541_6",
    "ChecklistField",
    "Scope",
    "Trade",
    "by_cite",
    "required_for",
]


class Trade(StrEnum):
    """Which direction of trade an invoice covers.

    Part 541 is written for both, with three clauses that apply to one
    direction only. Which direction an invoice is determines which clauses are
    required, and therefore how many of the twenty can be missing without
    eliminating the charge.
    """

    IMPORT = "import"
    EXPORT = "export"


class Scope(StrEnum):
    """Which direction of trade a disclosure applies to.

    Three of the twenty fields are one-directional. 541.6(a)(3) and (b)(6) are
    import only, 541.6(b)(7) is export only. A checker that demanded the
    container availability date on an export invoice would be demanding a fact
    that does not exist, and would manufacture a false omission, and 541.5 would
    then eliminate a charge that was properly owed.
    """

    BOTH = "both"
    IMPORT_ONLY = "import"
    EXPORT_ONLY = "export"


@dataclass(frozen=True, slots=True)
class ChecklistField:
    """One required disclosure from 541.6.

    ``cite`` is the section reference a dispute letter would quote, ``text`` is
    the verbatim regulatory language, and ``scope`` records whether the clause
    applies to imports, exports, or both.
    """

    cite: str
    group: str
    heading: str
    text: str
    scope: Scope

    @property
    def statement(self) -> str:
        """The verbatim text as a standalone sentence.

        541.6 lists its clauses, so the published text ends in a semicolon, a
        conjunction, or both. Those are stripped here and nowhere else, so
        ``text`` stays diffable against the published source.
        """
        cleaned = self.text.rstrip()
        cleaned = re.sub(r";\s*and$", "", cleaned)
        cleaned = re.sub(r"[;.]$", "", cleaned)
        return cleaned.strip()

    def applies_to(self, trade: Trade) -> bool:
        """Whether this field is required for the given direction of trade."""
        if self.scope is Scope.BOTH:
            return True
        return self.scope.value == trade.value


CHECKLIST: tuple[ChecklistField, ...] = (
    ChecklistField(
        cite="541.6(a)(1)",
        group="a",
        heading="Identifying information",
        text="The Bill of Lading number(s);",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(a)(2)",
        group="a",
        heading="Identifying information",
        text="The container number(s);",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(a)(3)",
        group="a",
        heading="Identifying information",
        text="For imports, the port(s) of discharge; and",
        scope=Scope.IMPORT_ONLY,
    ),
    ChecklistField(
        cite="541.6(a)(4)",
        group="a",
        heading="Identifying information",
        text="The basis for why the billed party is the proper party of interest and thus liable for the charge.",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(1)",
        group="b",
        heading="Timing information",
        text="The invoice date;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(2)",
        group="b",
        heading="Timing information",
        text="The invoice due date;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(3)",
        group="b",
        heading="Timing information",
        text="The allowed free time in days;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(4)",
        group="b",
        heading="Timing information",
        text="The start date of free time;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(5)",
        group="b",
        heading="Timing information",
        text="The end date of free time;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(b)(6)",
        group="b",
        heading="Timing information",
        text="For imports, the container availability date;",
        scope=Scope.IMPORT_ONLY,
    ),
    ChecklistField(
        cite="541.6(b)(7)",
        group="b",
        heading="Timing information",
        text="For exports, the earliest return date; and",
        scope=Scope.EXPORT_ONLY,
    ),
    ChecklistField(
        cite="541.6(b)(8)",
        group="b",
        heading="Timing information",
        text="The specific date(s) for which demurrage and/or detention were charged.",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(c)(1)",
        group="c",
        heading="Rate information",
        text="The total amount due;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(c)(2)",
        group="c",
        heading="Rate information",
        text="The applicable detention or demurrage rule (e.g., the tariff name and rule number, terminal schedule, applicable service contract number and section, or applicable negotiated arrangement) on which the daily rate is based; and",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(c)(3)",
        group="c",
        heading="Rate information",
        text="The specific rate or rates per the applicable tariff rule or service contract.",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(d)(1)",
        group="d",
        heading="Dispute information",
        text="The email, telephone number, or other appropriate contact information for questions or request for fee mitigation, refund, or waiver;",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(d)(2)",
        group="d",
        heading="Dispute information",
        text="Digital means, such as a URL address, QR code, or digital watermark, that directs the billed party to a publicly accessible website that provides a detailed description of information or documentation that the billed party must provide to successfully request fee mitigation, refund, or waiver; and",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(d)(3)",
        group="d",
        heading="Dispute information",
        text="Defined timeframes that comply with the billing practices in this part, during which the billed party must request a fee mitigation, refund, or waiver and within which the billing party will resolve such requests.",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(e)(1)",
        group="e",
        heading="Certifications",
        text="The charges are consistent with any of the Federal Maritime Commission's rules related to demurrage and detention, including, but not limited to, this part and 46 CFR 545.5; and",
        scope=Scope.BOTH,
    ),
    ChecklistField(
        cite="541.6(e)(2)",
        group="e",
        heading="Certifications",
        text="The billing party's performance did not cause or contribute to the underlying invoiced charges.",
        scope=Scope.BOTH,
    ),
)

GROUP_HEADINGS: dict[str, str] = {
    "a": "Identifying information",
    "b": "Timing information",
    "c": "Rate information",
    "d": "Dispute information",
    "e": "Certifications",
}

_BY_CITE: dict[str, ChecklistField] = {f.cite: f for f in CHECKLIST}


def by_cite(cite: str) -> ChecklistField:
    """Look up a field by its 541.6 reference, for example ``541.6(b)(3)``."""
    try:
        return _BY_CITE[cite]
    except KeyError:
        raise KeyError(f"no 541.6 field with cite {cite!r}") from None


def required_for(trade: Trade) -> tuple[ChecklistField, ...]:
    """The fields that apply to one direction of trade.

    Nineteen for an import, eighteen for an export, out of a checklist of twenty.
    Imports need the port of discharge under 541.6(a)(3) and the container
    availability date under 541.6(b)(6); exports need only the earliest return
    date under 541.6(b)(7).

    No real invoice is checked against all twenty, and over demanding is not a
    safe default. An omission recorded against a field that could not apply is a
    fabricated ground, and 541.5 would eliminate a charge that was properly owed
    on the strength of it.
    """
    return tuple(f for f in CHECKLIST if f.applies_to(trade))
