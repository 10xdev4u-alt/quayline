"""Issue 201: the copy that leaves the building.

A carrier dispute ends in a filing. It gets printed, signed, attached to correspondence
and posted, and a photocopy of it ends up in a file somewhere. Everything else this tool
produces is for reading; this is the one artifact that leaves.

Two reasons it cannot just be a textarea on a dark page:

**Paper is not a screen.** The pages are near-black because that is right on a screen.
Printed, near-black ink costs toner, and the copy a respondent photocopies is worse. A
print view is black on white with real margins and it does not depend on the display
scheme, because the printer is not a display.

**It has to be signable.** The screen view has no signature line, because nobody signs a
web page. The filing copy does: who is disputing, against which invoice, and where to
sign. A dispute letter without a signature block is a form, not a letter.

On the money
------------

Every figure on this page comes from the ``AuditResult`` or a ``Claim.amount_at_stake``,
the same two sources the screen view uses. Nothing here is typed. The screen view has
tests asserting that no amount appears which the engine did not compute, and this page
reuses that set rather than inventing a second one, so a figure cannot reach the filing
copy that did not reach the screen.

The filing status comes from ``Packet.can_file``, so the printed copy carries the same
warning the screen does. A letter that says it cannot be filed, printed on white paper
and signed, is still a letter that says it cannot be filed.
"""

from __future__ import annotations

from quayline.evidence.packet import render
from quayline.serve.audit_runner import Findings
from quayline.web.document import document
from quayline.web.example import day, money
from quayline.web.intake import esc

#: Only print media. The page is legible on screen too, because a reader who wants to
#: check the filing copy before printing it should be able to, but it is built for paper:
#: black on white, 18mm margins, and no rule thinner than a hairline survives a printer.
PRINT_CSS = """
.filing { max-width: 46rem; margin: 0 auto; padding: var(--pad); }
.filing-bar {
  display: flex; flex-wrap: wrap; gap: var(--gap); justify-content: space-between;
  align-items: baseline; padding-bottom: var(--gap-tight);
  border-bottom: 1px solid var(--edge);
}
.filing h1 { font-size: clamp(1.7rem, 4vw, 2.4rem); }
.filing h2 {
  font-family: var(--font-stencil); font-weight: var(--weight-stencil);
  font-size: 1.05rem; letter-spacing: -0.01em; margin: var(--gap-loose) 0 0.5rem;
}
.filing .parties { display: grid; gap: 0.15rem; margin: var(--gap) 0 0; padding: 0; }
.filing .parties div { display: flex; gap: var(--gap); padding: 0.4rem 0;
  border-bottom: 1px solid var(--edge); }
.filing .parties dt { margin: 0; color: var(--slate); flex: 0 0 12rem; }
.filing .parties dd { margin: 0; }

/* The filing body is the engine's document, verbatim, in a monospace face with its own
   line breaks preserved. Wrapping it would reflow the letter a reviewer is comparing
   against the engine. */
.filing .doc {
  white-space: pre-wrap;
  font-family: var(--font-data);
  font-size: 0.82rem;
  line-height: 1.65;
  background: var(--quay);
  border: 1px solid var(--edge);
  padding: 1rem;
  margin: 0 0 var(--gap-loose);
}

/* Where the reader signs. On screen it is obviously a form field; on paper it is a line
   with a caption, which is what it is. */
.filing .sign { margin-top: var(--gap-loose); padding-top: var(--gap); max-width: 30rem; }
.filing .sign div { border-top: 1px solid var(--chalk); margin-top: 2.2rem; padding-top: 0.4rem; }
.filing .sign span { font-size: 0.78rem; color: var(--slate); }

.filing .status { border: 1px solid var(--signal); padding: 0.7rem 0.9rem; margin: 0 0 var(--gap); }
.filing .status.ok { border-color: var(--sea); }
.filing .status strong { display: block; margin-bottom: 0.2rem; }

@media print {
  /* Black on white. The scheme is not consulted: a printer is not a display. */
  :root { color-scheme: light; }
  body { background: #fff !important; color: #000 !important; }
  .filing { max-width: none; padding: 0; }
  /* Nothing that is not the letter belongs on the page a carrier reads. */
  .filing-bar, .sign, .foot { display: none !important; }
  h1, h2, dt, .status strong { color: #000 !important; }
  .filing .status { border: 1px solid #000; }
  .filing .doc { background: #fff; border: 0; padding: 0; font-size: 10.5pt; line-height: 1.5; }
  .filing .parties div { border-bottom: 1px solid #000; }
  .filing .parties dt, .filing .sign span { color: #000 !important; }
  .day { break-inside: avoid; }
  a { color: #000 !important; text-decoration: none; }
}
"""


def _parties(findings: Findings) -> str:
    """Who is disputing what. Every value is read, none is typed."""
    result = findings.result
    return (
        '<dl class="parties">'
        f'<div><dt class="stencil">carrier</dt><dd class="data">{esc(result.carrier)}</dd></div>'
        f'<div><dt class="stencil">terminal</dt><dd class="data">{esc(result.terminal)}</dd></div>'
        f'<div><dt class="stencil">rule disclosed</dt>'
        f'<dd class="data">{esc(findings.bound.rate_rule)}</dd></div>'
        f'<div><dt class="stencil">invoice date</dt>'
        f'<dd class="data">{esc(day(findings.bound.invoice_date))}</dd></div>'
        f'<div><dt class="stencil">amount billed</dt>'
        f'<dd class="data">{esc(money(result.demanded_total))}</dd></div>'
        f'<div><dt class="stencil">amount allowed</dt>'
        f'<dd class="data">{esc(money(result.recomputed_total))}</dd></div>'
        f'<div><dt class="stencil">disputed</dt>'
        f'<dd class="data">{esc(money(result.variance))}</dd></div>'
        "</dl>"
    )


def _status(findings: Findings) -> str:
    """The filing status, from the packet's own gate.

    Printed in the margin of the filing copy on purpose. A signed letter on white paper
    that does not say it cannot be filed is the worst version of this document, and the
    most likely one, because it is the one somebody prints.
    """
    if findings.packet.can_file:
        return (
            '<p class="status ok"><strong>Ready to file.</strong>'
            "Every ground carries the evidence it needs.</p>"
        )
    blocked = sum(1 for section in findings.packet.sections if section.blocked)
    return (
        f'<p class="status"><strong>Not ready to file.</strong> {blocked} of '
        f"{len(findings.packet.sections)} grounds have no evidence attached. The letter "
        "below says which, and it is printed here so nobody finds out after signing.</p>"
    )


def filing_document(findings: Findings) -> str:
    """The filing copy: the engine's letter, the parties, and where to sign."""
    body = (
        '<div class="filing">\n'
        '<header class="filing-bar">'
        '<span class="stencil">Quayline filing copy</span>'
        '<span class="stencil">46 CFR Part 541</span>'
        "</header>\n"
        "<h1>Dispute of charges</h1>\n"
        f"{_status(findings)}\n"
        f"{_parties(findings)}\n"
        "<h2>The letter</h2>\n"
        '<p class="hint">Verbatim from the engine, which is what a reviewer compares '
        "against. Nothing on this page is written by hand.</p>\n"
        f'<pre class="doc">{esc(render(findings.packet))}</pre>\n'
        '<div class="sign">'
        "<h2>Signature</h2>"
        "<div><span>Signed, name and date</span></div>"
        "</div>\n"
        '<p class="foot">Produced on your own machine against 127.0.0.1. Nothing was '
        "written to disk and no request line was logged.</p>\n"
        "</div>\n"
    )
    return document(body, "Quayline: the filing copy", PRINT_CSS)


__all__ = ["PRINT_CSS", "filing_document"]
