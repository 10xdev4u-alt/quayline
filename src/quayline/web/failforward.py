"""Issue 222: an unreadable invoice must still be worth something to the person holding it.

Issue 214 made an unreadable document fail honestly. Honesty is not the same as usefulness,
and an honest refusal that leaves a reader with nothing they can act on is a dead end.

What this module hands back, none of which requires claiming anything we cannot support:

- **What we read**, verbatim, each labelled value with the line it came from.
- **The 541.6 checklist**, all twenty clauses, each marked as one of *could not be checked*,
  *found* or *not applicable to this direction of trade*.
- **A letter asking the carrier to supply the unverified disclosures**, by clause, noting
  what 541.5 says about a missing required minimum and naming the 541.8(a) window in which
  a mitigation request has to arrive.

## The framing is the whole constraint

Issue 214's bug was accusing a carrier of withholding a disclosure *we could not read*, and
541.5 makes that accusation automatic, so it does not get corrected by disputing it. This
module is the same hazard in prose, and it is the reason the letter **requests** rather than
alleging.

That is not a softening. A great many carrier invoices genuinely are missing required
disclosures, because the disclosures cost the carrier nothing to omit and everything to
supply. Asking for them by clause number is true on the documents that need it and harmless
on the ones that do not, which is the only property worth having here.

## What this deliberately does not do

It does not guess a carrier, and it does not claim a single omission. There is no
`OmittedError` anywhere in it, because we have not established that anything is missing and
the reader can check that themselves against the list.

It is also not a fallback for a document we *can* read. `audit()` produces findings for
those, and a page saying "we could not read this" alongside findings would be a different
claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from quayline.ingest.fields import Fields
from quayline.ingest.pdftext import TextLayer
from quayline.regulation.checklist import CHECKLIST, ChecklistField, Scope, Trade
from quayline.regulation.deadline import DAYS as MITIGATION_DAYS
from quayline.regulation.kill_switch import consequence_text
from quayline.web.design import stylesheet
from quayline.web.intake import COMPONENT_CSS, esc

__all__ = [
    "CLAUSE_STATUS",
    "FAIL_FORWARD_CSS",
    "ClauseRow",
    "fail_forward_page",
    "request_letter",
    "unread_report",
]

#: How many lines of the document to show when nothing parsed. Enough to prove we read it,
#: few enough that the page is not a dump of somebody's invoice.
_SAMPLE_LINES = 8

#: What we can say about each clause, and the words used on the page.
FOUND = "found"
UNCHECKED = "not checked"
NOT_APPLICABLE = "not applicable here"

CLAUSE_STATUS = (FOUND, UNCHECKED, NOT_APPLICABLE)

FAIL_FORWARD_CSS = """
.failforward { margin-top: var(--gap-loose); border: 1px solid var(--edge-strong);
  background: var(--deck); padding: 1rem 1.1rem; }
.failforward h2 { margin: 0 0 0.5rem; font-family: var(--font-stencil);
  font-weight: var(--weight-stencil); letter-spacing: 0.02em; text-transform: uppercase; }
.failforward p { max-width: var(--measure); }
.failforward ol.read { margin: 0.6rem 0 0; padding-left: 1.2rem;
  font-family: var(--font-data); font-size: 0.8rem; color: var(--slate); }
.failforward ol.read li { margin: 0.2rem 0; }

.clauses { margin-top: var(--gap-loose); border: 1px solid var(--edge); }
.clauses > header { padding: 0.8rem 1rem; border-bottom: 1px solid var(--edge); }
.clauses table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.clauses th { text-align: left; padding: 0.5rem 1rem; font-family: var(--font-stencil);
  font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--slate); }
.clauses td { padding: 0.5rem 1rem; border-top: 1px solid var(--edge);
  vertical-align: top; }
.clauses td.cite { font-family: var(--font-data); white-space: nowrap; color: var(--signal); }
.clauses td.state { white-space: nowrap; font-family: var(--font-data); }
.clauses tr.found td.state { color: var(--sea); }
.clauses tr.na td.state { color: var(--slate); }

.ask { margin-top: var(--gap-loose); }
.ask .letter { width: 100%; min-height: 18rem; background: var(--quay); color: var(--chalk);
  border: 1px solid var(--edge-strong); padding: 1rem; font-family: var(--font-data);
  font-size: 0.82rem; line-height: 1.6; white-space: pre-wrap; }
"""


@dataclass(frozen=True, slots=True)
class ClauseRow:
    """One 541.6 clause and what we can say about it."""

    field: ChecklistField
    status: str


def _trade_guess(text: TextLayer) -> Trade | None:
    """Which direction this looks like, or ``None`` if it says nothing.

    Used only to mark the three directional clauses, and only where the document is
    unreadable, so an import-only clause on an export invoice is marked not applicable
    rather than outstanding. A wrong guess here would tell a reader a clause does not
    apply when it does, so it is deliberately conservative: it needs a positive signal.
    """
    haystack = " ".join(text.lines).casefold()
    if "export" in haystack or "to order" in haystack:
        return Trade.EXPORT
    if "import" in haystack or "discharge port" in haystack or "arrival" in haystack:
        return Trade.IMPORT
    return None


def _found(cite: str, fields: Fields) -> bool:
    """Whether a labelled value for this clause is on the document.

    A presence check, never an absence claim. We are recording that we saw something,
    which is the only direction this module is allowed to speak in.
    """
    probe = {
        "541.6(b)(1)": ("invoice date",),
        "541.6(b)(2)": ("due date", "invoice due date", "payment due date"),
        "541.6(b)(3)": ("allowed free time", "free time allowed", "free days"),
        "541.6(b)(4)": ("start date of free time", "free time commences", "free time starts"),
        "541.6(b)(5)": ("end date of free time", "free time expires", "free time ends"),
        "541.6(b)(6)": ("container availability date", "container available", "availability"),
        "541.6(b)(7)": ("earliest return date",),
        "541.6(b)(8)": ("charged dates", "dates charged"),
        "541.6(c)(1)": ("total", "total amount", "total due", "amount due"),
        "541.6(c)(2)": ("rate rule", "tariff rule", "charged under"),
        "541.6(c)(3)": ("rate", "per day charge", "per day rate"),
        "541.6(a)(1)": ("bill of lading number", "b/l number"),
        "541.6(a)(2)": ("container number", "container"),
        "541.6(a)(3)": ("port of discharge", "discharge port"),
    }.get(cite, ())
    return any(label in fields.values for label in probe)


def unread_report(text: TextLayer, fields: Fields) -> tuple[ClauseRow, ...]:
    """All twenty clauses, marked. No clause is ever marked missing.

    ``not checked`` is the common case and it means exactly what it says: we did not look,
    so we are not saying. A reader can check those themselves against their own invoice in
    about two minutes, which is the point of the page.
    """
    trade = _trade_guess(text)
    rows: list[ClauseRow] = []
    for field in CHECKLIST:
        if field.scope is Scope.BOTH or trade is None:
            status = FOUND if _found(field.cite, fields) else UNCHECKED
        elif field.scope.value != trade.value:
            status = NOT_APPLICABLE
        else:
            status = FOUND if _found(field.cite, fields) else UNCHECKED
        rows.append(ClauseRow(field=field, status=status))
    return tuple(rows)


def request_letter(rows: tuple[ClauseRow, ...]) -> str:
    """A letter asking for the disclosures we could not verify, by clause.

    Reads nothing and alleges nothing. It asks, because asking is true on an invoice that
    is missing something and harmless on one that is not.

    The two regulatory facts it does state are the ones that make asking worth doing: 541.5
    on a missing required minimum, and the 541.8(a) window in which the request has to
    arrive. A request outside the window is worth nothing and the reader would not know.
    """
    outstanding = [r for r in rows if r.status == UNCHECKED]
    clauses = ", ".join(r.field.cite for r in outstanding) or "the twenty disclosures"
    found_notes = ", ".join(
        f"{r.field.cite} ({r.field.statement})" for r in rows if r.status == FOUND
    )
    return (
        "REQUEST FOR REQUIRED INVOICE INFORMATION\n"
        "\n"
        "To the billing party,\n"
        "\n"
        "This is a request under 46 CFR 541.8(a) for the disclosures 46 CFR 541.6 requires "
        "on a demurrage or detention invoice. We have not received enough of the invoice to "
        "verify them, and we are asking rather than asserting that anything is missing.\n"
        "\n"
        f"CLAUSES WE COULD NOT VERIFY FROM THE INVOICE\n{clauses}\n"
        "\n"
        + (
            f"WHAT THE INVOICE DID STATE\n{found_notes}\n\n"
            if found_notes
            else "WHAT THE INVOICE DID STATE\nNothing we could read.\n\n"
        )
        + f"WHY THIS MATTERS\n{consequence_text()}\n"
        "\n"
        "TIMING\n"
        f"541.8(a) gives us at least {MITIGATION_DAYS} calendar days from the invoice date "
        "to make this request, and 541.8(b) gives you "
        f"{MITIGATION_DAYS} calendar days from receiving it to resolve the request. A "
        "request outside that window is not one the rule lets us make, which is why we are "
        "sending this rather than waiting to be sure.\n"
        "\n"
        "WHAT WE WOULD LIKE\n"
        "The disclosures named above, on the face of a corrected or supplementary invoice, "
        "or in writing against the clause numbers.\n"
    )


def fail_forward_page(text: TextLayer, fields: Fields) -> str:
    """What we read, what we could not check, and a letter to send.

    Deliberately not styled as an error. The reader did nothing wrong, the tool did, and a
    page that looks like a refusal invites them to close the tab.
    """
    rows = unread_report(text, fields)
    letter = request_letter(rows)

    # Show what we read. Labelled values when there are any, and otherwise the document's
    # own first lines, because an empty list would tell the reader we got nothing when in
    # fact we read the text perfectly well and it was laid out in a way we do not parse.
    # That distinction is the whole story of this page and it should not be hidden.
    if fields.values:
        items = [fields.line_of.get(k, k) for k in sorted(fields.values)]
        read_block = '<ol class="read">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ol>"
    else:
        sample = "".join(f"<li>{esc(line)}</li>" for line in text.lines[:_SAMPLE_LINES])
        read_block = (
            "<p>We read the text of this document. None of it is laid out as a field we "
            "recognise, which is the problem. The first lines, so you can see we got "
            "them:</p>"
            f'<ol class="read">{sample}</ol>'
        )

    table_rows = "".join(
        f'<tr class="{_css_class(status)}">'
        f'<td class="cite">{esc(row.field.cite)}</td>'
        f"<td>{esc(row.field.statement)}</td>"
        f'<td class="state">{esc(status)}</td>'
        "</tr>"
        for row, status in ((r, r.status) for r in rows)
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Quayline: what we read</title>\n"
        f"<style>{stylesheet()}{COMPONENT_CSS}{FAIL_FORWARD_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="wrap">\n'
        '<section class="failforward">'
        "<h2>We could not read this invoice</h2>"
        "<p>Not a layout Quayline knows, so the day count and the money cannot be "
        "checked. Nothing below alleges anything against the carrier, and nothing below is "
        "a finding. What it is: everything we did read, the twenty disclosures the "
        "regulation requires, marked for you to check yourself, and a letter asking for "
        "the ones we could not.</p>"
        "<h3>What we read</h3>"
        f"{read_block}"
        "</section>\n"
        '<section class="clauses">'
        "<header><h2>What 46 CFR 541.6 requires</h2></header>"
        "<table><thead><tr><th>Clause</th><th>Required disclosure</th><th>Here</th></tr>"
        f"</thead><tbody>{table_rows}</tbody></table>"
        "</section>\n"
        '<section class="ask">'
        "<h2>A letter asking for the rest</h2>"
        '<p class="hint">It alleges nothing and asks for clauses by number. Copy it, or '
        "select it by hand.</p>"
        f'<textarea class="letter" readonly aria-label="Request for required invoice '
        f'information">{esc(letter)}</textarea>'
        "</section>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )


def _css_class(status: str) -> str:
    if status == FOUND:
        return "found"
    if status == NOT_APPLICABLE:
        return "na"
    return ""
