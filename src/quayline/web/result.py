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

import base64
import hashlib

from quayline.engine.disclosure import VERIFIABLE
from quayline.engine.result import CODE_FIELD_OMITTED
from quayline.evidence.packet import GroundSection, render
from quayline.regulation.checklist import CHECKLIST
from quayline.regulation.kill_switch import Obligation, consequence_text
from quayline.serve.audit_runner import Findings
from quayline.web.design import stylesheet
from quayline.web.example import day, money
from quayline.web.intake import (
    COMPONENT_CSS,
    STATE_ACCENT,
    STATE_WORD,
    day_cells,
    esc,
    legend,
    rail,
)
from quayline.web.money import disputed_label, verdict_of
from quayline.web.reasoning import (
    DISCREPANCY_CSS,
    days_with_findings,
    reasoning_panel,
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

/* What was not checked. The clauses we could not look at, and why, so the reader can
   tell a clean result from a narrow one. */
.coverage { margin-top: var(--gap-loose); border: 1px solid var(--edge);
  background: var(--deck); }
.coverage > header { padding: 0.8rem 1rem; border-bottom: 1px solid var(--edge);
  display: flex; flex-wrap: wrap; gap: var(--gap); align-items: baseline;
  justify-content: space-between; }
.coverage h2 { margin: 0; font-size: 0.95rem; font-family: var(--font-stencil);
  font-weight: var(--weight-stencil); letter-spacing: 0.02em; text-transform: uppercase; }
.coverage .tally { font-family: var(--font-data); font-size: 0.8rem; color: var(--slate); }
.coverage dl { display: grid; gap: 0.7rem; padding: 1rem; margin: 0;
  grid-template-columns: minmax(7rem, max-content) 1fr; }
.coverage dt { margin: 0; font-family: var(--font-data); font-size: 0.8rem;
  color: var(--signal); }
.coverage dd { margin: 0; color: var(--slate); max-width: var(--measure); }
.coverage p.lede { margin: 0; padding: 1rem 1rem 0; color: var(--slate);
  max-width: var(--measure); }

/* The 541.5 notice. An eliminated obligation is the strongest thing this page can
   say, and it needs to be a statement rather than a word in a column. */
.voided { margin-top: var(--gap-loose); border: 2px solid var(--signal);
  background: var(--deck); padding: 1rem 1.1rem; }
.voided h2 { margin: 0 0 0.5rem; font-size: 0.95rem; font-family: var(--font-stencil);
  font-weight: var(--weight-stencil); letter-spacing: 0.02em; text-transform: uppercase;
  color: var(--signal); }
.voided p { margin: 0; max-width: var(--measure); }
.voided ul { margin: 0.6rem 0 0; padding-left: 1.1rem; max-width: var(--measure); }
.voided li { margin: 0.2rem 0; }

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
/* The filing copy re-uploads the invoice, because the server keeps nothing. The file
   input is collapsed until it is needed: a reader who wants the filing copy should not
   first be shown a second file dialog. */
.actions .filing-go { display: flex; flex-wrap: wrap; gap: var(--gap-tight); align-items: center; margin: 0; }
.actions .filing-go input[type='file'] { flex: 1 1 12rem; min-width: 0; font-size: 0.82rem;
  color: var(--slate); border: 1px solid var(--edge-strong); background: var(--quay);
  padding: 0.5rem; font-family: var(--font-data); }
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
    # Built up rather than chosen between. A ternary over the whole concatenation
    # silently dropped the ground, the stake and the days whenever a section carried no
    # reason, which is the case for every unblocked section.
    details = (
        "<dl>"
        f'<div><dt class="stencil">ground</dt><dd class="data">{esc(claim.ground)}</dd></div>'
        f'<div><dt class="stencil">amount at stake</dt><dd class="data">{esc(stake)}</dd></div>'
        f'<div><dt class="stencil">days</dt><dd class="data">{esc(days_text)}</dd></div>'
        "</dl>"
        f'<p class="basis">{esc(claim.basis)}</p>'
    )
    if section.reason:
        details += f'<p class="basis">{esc(section.reason)}</p>'
    for item in section.evidence:
        details += f'<p class="basis">{esc(item.kind)}: {esc(item.description)}</p>'
    return (
        '<section class="section">'
        f'<header><span class="stencil">{esc(claim.ground)}</span>{_flag(section)}</header>'
        f'<div class="body"><h3>{esc(claim.title)}</h3>{details}</div>'
        "</section>"
    )


def letter_text(findings: Findings) -> str:
    """The filing document, exactly as ``evidence.packet.render`` writes it.

    This used to be a second rendering written here from the packet objects. That was a
    regression of the thing issue 196 removed: the old page parsed the rendered letter to
    get the day strip back out, and this re-rendered the same packet a second time and
    lost what it did not know about.

    Three things went missing, and the worst of them was the line saying the packet
    cannot be filed as it stands. A shipper who copied that letter sent a document that
    nowhere said it was not ready to send, which is the single failure this packet module
    exists to prevent. The automatic and contested split went too, and that grouping is
    what makes a packet workable for a carrier's respondent.

    So there is one document and this is it. ``render`` already groups the claims, already
    states the filing status, and is what a reviewer would diff against the engine
    anyway. A test asserts byte equality rather than containment, because a document that
    lost the filing status and kept everything else would still pass a containment check.
    """
    return render(findings.packet)


def _ledger(findings: Findings, disputed_label: str) -> str:
    """The three figures, with the last one labelled honestly.

    A negative variance means the carrier billed less than the recomputation allows.
    Calling that "disputed" would name money that is not in dispute, so the label
    changes with the sign rather than with the mood.
    """
    result = findings.result
    variance = result.variance
    third = money(variance) if variance is not None else "not computed"
    return (
        '<dl class="ledger">'
        f'<div><dt>billed by the carrier</dt><dd class="data">'
        f"{esc(money(result.demanded_total))}</dd></div>"
        f'<div><dt>allowed by the disclosed rule</dt><dd class="data">'
        f"{esc(money(result.recomputed_total))}</dd></div>"
        f'<div class="excess"><dt>{esc(disputed_label)}</dt>'
        f'<dd class="data">{esc(third)}</dd></div>'
        "</dl>"
    )


def _next_step(findings: Findings, verdict: str) -> str:
    """Tell the reader what to do, and do not tell them to send what cannot be sent.

    ``packet.can_file`` is false whenever any ground is blocked. Telling someone to
    send a packet the packet gate rejects is the failure this project is built to
    prevent, so the send guidance only appears when the gate agrees.
    """
    if verdict == "clean":
        return (
            "<p>No carrier response is needed for this invoice. Keep it: the "
            "recomputation is reproducible from the disclosures printed on the "
            "document.</p>"
        )
    if verdict == "unresolved":
        return (
            "<p>We hold no transcribed rate for this rule, so the money cannot be "
            "priced. The day count above is still the engine's own. Run "
            "<code>quayline coverage</code> for what we do hold.</p>"
        )
    if not findings.packet.can_file:
        blocked = sum(1 for section in findings.packet.sections if section.blocked)
        return (
            f"<p><b>This packet cannot be sent yet.</b> {blocked} of "
            f"{len(findings.packet.sections)} grounds have no evidence attached, and a "
            f"carrier's respondent will not concede a ground that arrives unsupported. "
            f"Each one states what is missing below.</p>"
            f"<p>The letter is still rendered so you can read exactly what is being "
            f"claimed. It is not ready to send.</p>"
        )
    return "<p>Send the letter below to the carrier. Every ground is supported.</p>"


#: The one thing the script does. Copying is an enhancement over a textarea the reader
#: can already select, so the page is complete without it and the button is not the only
#: route to the text.
COPY_SCRIPT = """
(function () {
  var button = document.getElementById('copy');
  var letter = document.getElementById('letter');
  var said = document.getElementById('copied');
  if (!button || !letter) { return; }
  button.addEventListener('click', function () {
    var done = function () { if (said) { said.textContent = 'Copied. Paste it into an email.'; } };
    var failed = function () {
      // Refusing to pretend is the whole point of this fallback. Saying "copied" when
      // nothing was copied is worse than saying nothing.
      letter.focus();
      letter.select();
      if (said) { said.textContent = 'Select the text above and copy it.'; }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(letter.value).then(done, failed);
    } else {
      failed();
    }
  });
}());
"""


def _coverage(findings: Findings) -> str:
    """Which of the twenty clauses were checked, and why the others were not.

    Issue 212. The tally is read from the code rather than typed here, because a coverage
    figure written into a template is a figure that will be wrong the moment coverage
    changes, and nothing will notice. The onboarding document sat wrong for a year on
    exactly this.

    The reasons are the substance. Six clauses cannot be checked for absence from a text
    layer, and the sharpest is 541.6(d)(2), which the regulation lets a carrier satisfy
    with a QR code or a watermark. Neither appears in a text layer, so a missing URL says
    nothing about whether the carrier complied. Saying "we found nothing wrong" without
    this would be claiming compliance on six clauses nobody looked at.
    """
    unverified = findings.result.unverified_fields
    checked = len(VERIFIABLE) + 1
    rows = "".join(
        f"<dt>{esc(entry.cite)}</dt><dd>{esc(entry.reason)}</dd>" for entry in unverified
    )
    return (
        '<section class="coverage">'
        "<header><h2>What was not checked</h2>"
        f'<span class="tally">{checked} of {len(CHECKLIST)} clauses checked</span>'
        "</header>"
        '<p class="lede">These clauses of 46 CFR 541.6 cannot be checked for absence '
        "from an invoice&#x27;s text, so a clean result on the clauses we did check is "
        "not a statement about compliance.</p>"
        f"<dl>{rows}</dl>"
        "</section>"
    )


def _void_notice(findings: Findings) -> str:
    """What 541.5 does, when it fires. Nothing at all when it does not.

    The consequence sentence is read from ``kill_switch`` so a page cannot end up
    describing a remedy the regulation no longer provides. The clause list is built
    from the omissions the engine found, so a reader sees which disclosures are
    missing rather than being told there is something wrong somewhere.
    """
    result = findings.result
    if result.obligation is not Obligation.ELIMINATED:
        return ""
    # The summary already opens with its own clause, because `Omission.describe` puts
    # it there for the letter. Printing the cite again as a chip would show
    # 541.6(b)(2) twice, so the list carries the sentence and the citation rides inside
    # it rather than beside it.
    clauses = "".join(
        f"<li>{esc(f.summary)}</li>" for f in result.findings if f.code == CODE_FIELD_OMITTED
    )
    return (
        '<section class="voided">'
        "<h2>You do not have to pay this</h2>"
        f"<p>{esc(consequence_text())}</p>"
        f"<ul>{clauses}</ul>"
        "</section>"
    )


def result_page(findings: Findings) -> str:
    """The result, as a document rather than a dump."""
    result = findings.result
    flagged = days_with_findings(result.day_count)
    heading, stake, verdict = verdict_of(result)
    next_step = _next_step(findings, verdict)
    label = disputed_label(result)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Quayline: your dispute</title>\n"
        f"<style>{stylesheet()}{COMPONENT_CSS}{DISCREPANCY_CSS}{RESULT_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="wrap">\n'
        '<header class="verdict">'
        f'<span><span class="stencil">verdict</span><br>{esc(heading)}</span>'
        f'<span class="amount{" calm" if verdict != "dispute" else ""} data">'
        f"{esc(stake)}</span>"
        "</header>\n"
        "<main>\n"
        # Which invoice was actually audited. A client who uploaded the wrong PDF
        # should find out here rather than in the carrier's reply.
        f"{_void_notice(findings)}\n"
        f"{_coverage(findings)}\n"
        f"{rail(_rail_pairs(findings))}\n"
        f"{day_cells(findings.strip.days if findings.strip else [], flagged)}\n"
        f"{legend()}\n"
        f"{reasoning_panel(findings.result.day_count, findings.result)}\n"
        f"{_ledger(findings, label)}\n"
        f"{''.join(ground_section(s) for s in findings.packet.sections)}\n"
        '<div class="next">'
        "<h2>What to do next</h2>"
        f"{next_step}"
        "</div>\n"
        "<h2>The letter</h2>\n"
        '<p class="hint">Everything above it is evidence. This is the text to send.</p>\n'
        f'<textarea class="letter" id="letter" readonly aria-label="The dispute letter">'
        f"{esc(letter_text(findings))}</textarea>\n"
        '<div class="actions">'
        '<button type="button" id="copy">Copy the letter</button>'
        # The filing copy needs the invoice again. The server holds nothing between
        # requests on purpose, so the PDF is re-posted from the browser rather than kept.
        # A GET route that recomputed the worked example would hand a client a filing
        # copy about someone else's invoice, which is worse than not having the button.
        '<form class="filing-go" method="post" action="/filing" '
        'enctype="multipart/form-data">'
        '<label class="sr" for="filing-pdf">Your invoice, again</label>'
        '<input id="filing-pdf" type="file" name="pdf" accept="application/pdf" required>'
        '<label class="sr" for="filing-carrier">Carrier</label>'
        f'<input id="filing-carrier" type="hidden" name="carrier" value="{esc(result.carrier)}">'
        '<label class="sr" for="filing-terminal">Terminal</label>'
        f'<input id="filing-terminal" type="hidden" name="terminal" value="{esc(result.terminal)}">'
        '<button type="submit">Get the filing copy</button>'
        "</form>\n"
        '<span class="hint" id="copied" role="status" aria-live="polite"></span>'
        "</div>\n"
        '<p class="hint"><a href="/">Audit another invoice</a></p>\n'
        "</main>\n"
        '<footer class="foot">'
        "<p>This ran on your own machine against 127.0.0.1. Nothing was written to disk "
        "and no request line was logged.</p>"
        "</footer>\n"
        "</div>\n"
        f"<script>{COPY_SCRIPT}</script>\n"
        "</body>\n"
        "</html>\n"
    )


def script_hash() -> str:
    """The CSP source expression for the copy script. Base64, not hex."""
    return "sha256-" + base64.b64encode(hashlib.sha256(COPY_SCRIPT.encode()).digest()).decode()


__all__ = [
    "COPY_SCRIPT",
    "RESULT_CSS",
    "STATE_ACCENT",
    "STATE_WORD",
    "ground_section",
    "letter_text",
    "result_page",
    "script_hash",
]
