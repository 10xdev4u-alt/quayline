"""The intake document, assembled.

Split from :mod:`quayline.web.intake` on purpose. That module is the system: tokens,
grid, ledger, rail. This one is the page: head, script, markup, and the one inline
script that makes it feel like a product.

On the script
-------------

The page works with no script at all. The form is a real form, the submit is a real
submit, and the server answers with a letter page. Everything the script adds is
enhancement: dragging a file onto the zone instead of clicking a file input, a staged
progress state while the engine runs, and a staggered reveal of the day grid.

It is inline, which means the Content-Security-Policy cannot use ``'unsafe-inline'``
for scripts without giving that away to anything else on the page. So the policy pins
the SHA-256 of this exact script text. If the script changes by one byte the page stops
working, which is a bug we would want. :func:`script_hash` is what the server puts in
the header, and it is computed from the same constant, so the two cannot drift.
"""

from __future__ import annotations

import base64
import hashlib

from quayline.web.design import stylesheet
from quayline.web.intake import (
    COMPONENT_CSS,
    INTAKE_CSS,
    day_cells,
    esc,
    ledger,
    legend,
    rail,
)
from quayline.web.reasoning import (
    DISCREPANCY_CSS,
    days_with_findings,
    reasoning_panel,
)

#: Staged progress, the staggered reveal, the count up, and the drop target. Plain ES2017,
#: no library, no network. Every branch is guarded so a failure here degrades to the
#: no-script page rather than a blank one.
SCRIPT = """
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Stagger the day cells in from the left. This is the one moment the page has, and it
     is the reason the grid reads as a sequence of days rather than a table. */
  var cells = document.querySelectorAll('.day');
  for (var i = 0; i < cells.length; i++) {
    var cell = cells[i];
    cell.style.opacity = reduce ? '1' : '0';
    cell.style.transition = 'opacity ' + (reduce ? '1ms' : '380ms') + ' ease-out';
    cell.style.transitionDelay = reduce ? '0ms' : (i * 26) + 'ms';
    cell.style.transform = reduce ? 'none' : 'translateY(6px)';
    requestAnimationFrame(function (el, done) {
      return function () {
        el.style.opacity = '1';
        el.style.transform = 'none';
        if (done) { done(); }
      };
    }(cell, i === cells.length - 1 ? markDone : null));
  }

  function markDone() { document.body.dataset.revealed = 'true'; }

  /* Count the excess up to its value. The number is already correct in the markup, so
     this only ever changes presentation.

     rAF alone is not enough. A browser stops firing animation frames in a background
     tab, so a reader who switched away during the first second came back to $0.00,
     which is worse than no animation at all. The final value is therefore also written
     on a timer, and the whole thing is skipped when the document is hidden. */
  var excess = document.querySelector('.excess dd');
  if (excess && !reduce && document.visibilityState !== 'hidden') {
    var target = parseFloat((excess.textContent || '').replace(/[^0-9.]/g, ''));
    if (!isNaN(target) && target > 0) {
      var settled = false;
      var settle = function () {
        if (!settled) { settled = true; excess.textContent = '$' + target.toFixed(2); }
      };
      var t0 = null;
      var step = function (stamp) {
        if (settled) { return; }
        if (t0 === null) { t0 = stamp; }
        var p = Math.min(1, (stamp - t0) / 700);
        var eased = 1 - Math.pow(1 - p, 3);
        if (p >= 1) { settle(); return; }
        excess.textContent = '$' + (target * eased).toFixed(2);
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
      setTimeout(settle, 900);
    }
  }

  /* Drag and drop onto the zone. The file input stays exactly where it was, and stays
     the thing a keyboard uses, because a drag target that only works with a pointer is
     not an affordance, it is a decoration. */
  var zone = document.querySelector('.drop');
  var input = document.getElementById('pdf');
  if (zone && input) {
    ['dragenter', 'dragover'].forEach(function (name) {
      zone.addEventListener(name, function (e) {
        e.preventDefault();
        zone.dataset.over = 'true';
      });
    });
    ['dragleave', 'drop'].forEach(function (name) {
      zone.addEventListener(name, function (e) {
        e.preventDefault();
        zone.dataset.over = 'false';
      });
    });
    zone.addEventListener('drop', function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
  }

  /* Staged progress. A PDF takes a moment to read and recompute. Saying which step we
     are on is worth more than a spinner, because the steps are the product. */
  var form = document.querySelector('form');
  if (form) {
    form.addEventListener('submit', function () {
      var button = form.querySelector('button');
      if (button) { button.disabled = true; button.textContent = 'reading the invoice'; }
      var status = document.getElementById('status');
      if (status) { status.textContent = 'reading the disclosures, then recomputing every day'; }
    });
  }
}());
"""


def script_hash() -> str:
    """The CSP source expression for the inline script, without the quotes.

    Base64, not hex. The policy grammar wants ``'sha256-'`` followed by the standard
    encoding of the digest, and a hex digest silently fails to match: the browser then
    refuses the script and the page quietly loses every enhancement, with the header
    still looking correct and a self-check comparing the digest against itself passing.
    That is what happened the first time.
    """
    digest = hashlib.sha256(SCRIPT.encode()).digest()
    return "sha256-" + base64.b64encode(digest).decode()


def _document(body: str, title: str, extra_style: str = "") -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        f"<style>{stylesheet()}{COMPONENT_CSS}{DISCREPANCY_CSS}{INTAKE_CSS}{extra_style}</style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>\n"
    )


#: The three figures the ledger shows, in the order a reader meets them.
Money = tuple[str, str, str]


def intake_document(
    *,
    days: object,
    day_count: object,
    rail_pairs: list[tuple[str, str]],
    money: Money,
    fixture_note: str,
) -> str:
    """The intake page, with the argument already made before anything is uploaded.

    ``money`` is billed, allowed, excess, in that order. It is one tuple rather than
    three parameters because the three are only ever meaningful together and a reader
    should not have to check the argument order.

    ``day_count`` carries the engine's own reasoning for the grid above it. Without it
    the page would show coloured boxes asserting an answer and withholding the argument,
    which is the posture this project is trying not to have.
    """
    flagged = days_with_findings(day_count)
    body = (
        '<div class="manifest">\n'
        '<header class="head">'
        '<span class="stencil">Quayline</span>'
        '<span class="stencil">46 CFR Part 541</span>'
        "</header>\n"
        f"{rail(rail_pairs)}\n"
        "<main>\n"
        "<h1>They billed you for a day you were entitled to.</h1>\n"
        '<p class="lede">Demurrage and detention are decided one day at a time, so that is '
        "how this page reads. Every day below was recomputed from the disclosures printed "
        "on the invoice itself, under the rule the carrier was required to publish.</p>\n"
        f"{day_cells(days, flagged)}\n"
        f"{legend()}\n"
        f"{reasoning_panel(day_count)}\n"
        f"{ledger(*money)}\n"
        '<form class="drop" method="post" action="/letter" enctype="multipart/form-data">\n'
        '<span class="stencil">your invoice</span>\n'
        '<label for="pdf">Carrier PDF, born digital. It is read in memory and discarded.'
        "</label>\n"
        '<input id="pdf" type="file" name="pdf" accept="application/pdf" required>\n'
        '<div class="controls">\n'
        '<div><label class="stencil" for="carrier">carrier, as published</label>'
        '<input id="carrier" name="carrier" value="Maersk" required></div>\n'
        '<div><label class="stencil" for="terminal">terminal, where it matters</label>'
        '<input id="terminal" name="terminal" value="newark" required></div>\n'
        "</div>\n"
        '<button type="submit">Recompute the days</button>\n'
        '<p class="sr" id="status" role="status" aria-live="polite"></p>\n'
        "</form>\n"
        "</main>\n"
        f'<footer class="foot"><p class="stencil">what this is</p>'
        f"<p>{esc(fixture_note)}</p>"
        "<p>This runs on your own machine, bound to 127.0.0.1 and refusing any other "
        "interface. There is no account, nothing is written to disk, and no request line "
        "is logged. Uploaded bytes live in memory for the length of one request.</p>"
        "<p>We hold a day-count rule and transcribed rates for one carrier. A carrier "
        "we can count days for but hold no rate for still gets the days recomputed and "
        "not the money. A carrier with no day-count rule cannot be audited at all. Run "
        "<code>quayline coverage</code> for the exact list.</p>"
        "</footer>\n"
        "</div>\n"
        f"<script>{SCRIPT}</script>"
    )
    return _document(body, "Quayline: recompute the days")


__all__ = ["SCRIPT", "intake_document", "script_hash"]
