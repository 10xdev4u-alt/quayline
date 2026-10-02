"""Issue 195: the result page, rendered from structure.

This is the screen a client lands on after handing over their invoice, and it was the
last one still on the old cream palette with its own hardcoded hex values, so the client
started on one product and finished on another.

The letter is not a preformatted blob
-------------------------------------

The previous version was handed the letter as a finished string and pulled the day
strip back out of it by splitting on the literal ``<div class="strip">`` and
``</div>\\n``. That is a page whose correctness depends on the shape of markup another
module happened to emit, and it fails silently rather than loudly.

The packet already carries the structure: ``GroundSection`` has a ``claim`` with a
ground, a title, the days, the amount at stake and a basis, plus ``blocked``,
``blocked``'s reason and whether the claim is automatic. So the page reads objects. A
ground with no evidence is shown as blocked and named, because a ground that vanishes is
the failure this whole module exists to prevent.

On the money
------------

The amount at stake is the largest number on the page. A blocked ground still has a
number, and showing it is the point: the client learns what the dispute is worth on the
same screen that tells them it needs work.
"""

from __future__ import annotations

from quayline.evidence.packet import GroundSection
from quayline.serve.audit_runner import Findings
from quayline.web.design import stylesheet
from quayline.web.example import day, money
from quayline.web.intake import (
    COMPONENT_CSS,
    STATE_ACCENT,
    STATE_WORD,
    day_cells,
    esc,
    ledger,
    legend,
    rail,
)

RESULT_CSS = """
/* Single column, so the rail lays out as a header block rather than a narrow column. */
.rail dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); }
.rail div { border-bottom: 0; border-right: 1px solid var(--edge); }

/* The verdict line. The number that decides whether anyone keeps going. */
.verdict { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--gap);
  justify-content: space-between; padding-bottom: var(--gap); border-bottom: 1px solid var(--edge); }
.verdict .tag { color: var(--signal); }
.verdict .amount { font-size: clamp(2.2rem, 8vw, 3.6rem); line-height: 1; color: var(--signal); }
.verdict .amount.calm { color: var(--chalk); }

.section { margin-top: var(--gap-loose); border: 1px solid var(--edge); background: var(--deck); }
.section > header { display: flex; flex-wrap: wrap; gap: var(--gap); align-items: baseline;
  justify-content: space-between; padding: 0.8rem 1rem; border-bottom: 1px solid var(--edge); }
.section .body { padding: 1rem; }
.section .basis { margin: 0.6rem 0 0; color: var(--slate); max-width: var(--measure); }
.section dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr)); gap: 0.8rem; margin: 0; }
.section dt { margin: 0 0 0.2rem; }
.section dd { margin: 0; }

.flag { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.66rem;
  letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700;
  border: 1px solid; padding: 0.2rem 0.45rem; }
.flag.blocked { color: var(--signal); border-color: var(--signal); }
.flag.clear   { color: var(--sea);   border-color: var(--sea); }

/* What to do next. The reader has an action to take and it should not be a guess. */
.next { margin-top: var(--gap-loose); border-left: 2px solid var(--signal); padding: 0.8rem 0 0.8rem 1rem; }
.next h2 { margin: 0 0 0.4rem; font-size: 0.95rem; font-family: var(--font-stencil);
  font-weight: var(--weight-stencil); letter-spacing: 0.02em; text-transform: uppercase; }
.next p { margin: 0 0 0.5rem; max-width: var(--measure); color: var(--slate); }

/* The copyable letter. A textarea, so it works with no script and the reader can
   select the text by hand if the button is blocked. */
.letter { width: 100%; min-height: 16rem; background: var(--quay); color: var(--chalk);
  border: 1px solid var(--edge-strong); padding: 1rem;
  font-family: var(--font-data); font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; }
.actions { display: flex; flex-wrap: wrap; gap: var(--gap); margin-top: var(--gap); align-items: center; }
.actions button { flex: 0 0 auto; }
.hint { color: var(--slate); font-size: 0.8rem; }
@media (max-width: 40rem) { .verdict .amount { font-size: 2.4rem; } }
"""


def _rail_pairs(findings: Findings) -> list[tuple[str, str]]:
    """What was read off the document, so the reader can check it is the right one."""
    bound = findings.bound
    return [
        ("carrier", findings.result.carrier),
        ("terminal", findings.result.terminal),
        ("rule", bound.rate_rule),
        ("invoice date", day(bound.invoice_date)),
        ("free time", f"{bound.allowed_free_time_days} days"),
        ("disclosed end", day(bound.free_time_end)),
    ]


def _flag(section: GroundSection) -> str:
    """Blocked is stated, never implied. A silent omission is the failure mode here."""
    if section.blocked:
        return '<span class="flag blocked">needs evidence</span>'
    return '<span class="flag clear">automatic</span>' if section.is_automatic else ""


def ground_section(section: GroundSection) -> str:
    """One ground, with its claim, its stake and whether it can be sent today."""
    claim = section.claim
    stake = money(claim.amount_at_stake) if claim.amount_at_stake is not None else "no amount"
    days_text = ", ".join(str(value) for value in claim.days) or "no days listed"
    body = (
        "<dl>"
        f'<div><dt class="stencil">ground</dt><dd class="data">{esc(claim.ground)}</dd></div>'
        f'<div><dt class="stencil">amount at stake</dt><dd class="data">{esc(stake)}</dd></div>'
        f'<div><dt class="stencil">days</dt><dd class="data">{esc(days_text)}</dd></div>'
        "</dl>"
        f'<p class="basis">{esc(claim.basis)}</p>'
        f'<p class="basis">{esc(section.reason)}</p>'
        if section.reason
        else f'<p class="basis">{esc(claim.basis)}</p>'
    )
    return (
        '<section class="section">'
        f'<header><span class="stencil">{esc(claim.ground)}</span>{_flag(section)}</header>'
        f'<div class="body"><h3>{esc(claim.title)}</h3>{body}</div>'
        "</section>"
    )


def letter_text(findings: Findings) -> str:
    """The letter as plain text, for the textarea.

    Rendered here rather than taken from the packet renderer, so the copy is the same
    words the reader can see on the page and neither can drift from the other.
    """
    lines = [
        "Dispute of charges",
        "",
        f"Invoice date: {day(findings.bound.invoice_date)}",
        f"Carrier: {findings.result.carrier}",
        f"Terminal: {findings.result.terminal}",
        "",
    ]
    for section in findings.packet.sections:
        lines.append(f"{section.claim.ground}  {section.claim.title}")
        if section.claim.amount_at_stake is not None:
            lines.append(f"  amount at stake: {money(section.claim.amount_at_stake)}")
        lines.append(f"  {section.claim.basis}")
        if section.blocked:
            lines.append(f"  blocked: {section.reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def result_page(findings: Findings) -> str:
    """The result, as a document rather than a dump."""
    result = findings.result
    stake = result.variance
    clean = not result.findings
    heading = "Nothing to dispute on this invoice." if clean else "There is a dispute here."
    next_step = (
        "<p>No carrier response is needed for this invoice. Keep it: the recomputation "
        "is reproducible from the disclosures printed on the document.</p>"
        if clean
        else "<p>Send the letter below to the carrier. Where a ground is marked as "
        "needing evidence, that part cannot be sent yet, and the page says which "
        "evidence is missing.</p>"
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Quayline: your dispute</title>\n"
        f"<style>{stylesheet()}{COMPONENT_CSS}{RESULT_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="wrap">\n'
        '<header class="verdict">'
        f'<span><span class="stencil">verdict</span><br>{esc(heading)}</span>'
        f'<span class="amount{" calm" if clean else ""} data">'
        f"{esc(money(stake) if not clean else 'nothing')}</span>"
        "</header>\n"
        "<main>\n"
        # Which invoice was actually audited. A client who uploaded the wrong PDF
        # should find out here rather than in the carrier's reply.
        f"{rail(_rail_pairs(findings))}\n"
        f"{day_cells(findings.strip.days) if findings.strip else ''}\n"
        f"{legend()}\n"
        f"{ledger(money(result.demanded_total), money(result.recomputed_total), money(result.variance))}\n"
        f"{''.join(ground_section(s) for s in findings.packet.sections)}\n"
        '<div class="next">'
        "<h2>What to do next</h2>"
        f"{next_step}"
        "</div>\n"
        "<h2>The letter</h2>\n"
        '<p class="hint">Everything above it is evidence. This is the text to send.</p>\n'
        f'<textarea class="letter" readonly aria-label="The dispute letter">{esc(letter_text(findings))}</textarea>\n'
        '<div class="actions">'
        '<button type="button" id="copy">Copy the letter</button>'
        '<span class="hint" id="copied" role="status" aria-live="polite"></span>'
        "</div>\n"
        '<p class="hint"><a href="/">Audit another invoice</a></p>\n'
        "</main>\n"
        '<footer class="foot">'
        "<p>This ran on your own machine against 127.0.0.1. Nothing was written to disk "
        "and no request line was logged.</p>"
        "</footer>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )


__all__ = [
    "RESULT_CSS",
    "STATE_ACCENT",
    "STATE_WORD",
    "ground_section",
    "letter_text",
    "result_page",
]
