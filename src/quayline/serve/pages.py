"""The three HTML pages the intake serves.

Apart from ``app.py`` because they are documents, not protocol handling, and they change
for different reasons. A page changes when the product's story changes. The handler
changes when the wire format does.

Styles are inline, with no stylesheet to fetch, no font from a CDN, and no script. That
is deliberate three times over: it works with no network, it is a fixed amount of code
an operator can read before trusting it with a client's invoice, and it leaves a browser
nothing to phone home about. The one consequence is that the response header has to
permit inline style, which ``app._send`` decides per content type.
"""

from __future__ import annotations

from quayline.cli.exit_codes import EXIT_CLEAN, EXIT_FILE_WORTHY
from quayline.web.render import render_specimen
from quayline.web.specimen import SpecimenError, build_specimen

FORM_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quayline: audit an invoice</title>
<style>
:root { --ink:#1a1a1a; --muted:#5c5c5c; --rule:#d8d8d8; --bg:#fbfbf9; --disp:#b3541e; }
* { box-sizing:border-box; }
body { margin:0; padding:3rem 1.5rem; background:var(--bg); color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
main { max-width:38rem; margin:0 auto; }
h1 { font-size:1.6rem; letter-spacing:-.02em; margin:0 0 .4rem; }
.lede { color:var(--muted); margin:0 0 1.5rem; }
label { display:block; font-size:.85rem; margin:.9rem 0 .25rem; }
input, select { width:100%; padding:.5rem .6rem; font:inherit; font-size:.95rem;
  border:1px solid var(--rule); border-radius:.2rem; background:#fff; color:inherit; }
input[type=file] { padding:.4rem; }
button { margin-top:1.4rem; width:100%; padding:.65rem; font:inherit; font-weight:600;
  border:1px solid var(--ink); border-radius:.2rem; background:var(--ink); color:var(--bg);
  cursor:pointer; }
.note { font-size:.85rem; color:var(--muted); margin-top:1.5rem;
  border-top:1px solid var(--rule); padding-top:1rem; }
code { font:13px ui-monospace,SFMono-Regular,Menlo,monospace; background:#eee;
  padding:.1rem .3rem; border-radius:.2rem; }
h2 { font-size:1rem; margin:2.5rem 0 .3rem; }
.carriers { font-size:.85rem; color:var(--muted); }
.carriers b { color:var(--disp); }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e6; --muted:#9a9a97; --rule:#333; --bg:#16161a; --disp:#e08a4e; }
  input, select, button { background:#1c1c20; }
  input, select { border-color:#3a3a3f; }
  code { background:#26262a; }
}
</style>
</head>
<body>
<main>
  <h1>Audit a demurrage invoice</h1>
  <p class="lede">
    Drop a carrier PDF and we recompute the charge from the disclosures on the document
    itself, under 46 CFR Part 541. No account, nothing stored, the file is read and
    discarded.
  </p>

  <form method="post" action="/letter" enctype="multipart/form-data">
    <label for="pdf">Invoice PDF</label>
    <input type="file" id="pdf" name="pdf" accept="application/pdf" required>

    <label for="carrier">Carrier, as published</label>
    <input type="text" id="carrier" name="carrier" value="Maersk" required
           list="known" autocomplete="off">
    <datalist id="known">
      <option value="Maersk"></option>
      <option value="Hapag-Lloyd"></option>
      <option value="ONE"></option>
      <option value="MSC"></option>
      <option value="CMA CGM"></option>
      <option value="ZIM"></option>
      <option value="Evergreen"></option>
    </datalist>

    <label for="terminal">Terminal, where it matters</label>
    <input type="text" id="terminal" name="terminal" placeholder="newark" autocomplete="off">

    <button type="submit">Audit and show the dispute letter</button>
  </form>

  <p class="note">
    <strong>This runs on your machine.</strong> It is bound to
    <code>127.0.0.1</code> only and refuses any other interface. Nothing is stored:
    the upload is read into memory for the length of the request and discarded, and no
    request line is logged.
    <br><br>
    We hold transcribed rate data for <b>one carrier</b> today. For anyone else the day
    count is recomputed and the money is not, which the answer says plainly rather than
    hiding. Run <code>quayline coverage</code> for the full list.
  </p>
</main>
</body>
</html>
"""


def first_missing(fields: dict[str, str], pdf: bytes) -> str | None:
    """The first thing the upload is missing, or ``None`` when it has everything.

    One function rather than three sequential checks, because three checks means three
    returns and a reviewer has to prove none of them became unreachable.
    """
    if not fields.get("carrier"):
        return (
            "a carrier is required, and 541.6 does not ask a carrier to name itself on "
            "the invoice face."
        )
    if not pdf:
        return "no pdf file in the upload."
    if not pdf.startswith(b"%PDF"):
        return (
            "that file does not start with %PDF, so it is not a PDF. Checked before "
            "parsing rather than letting the parser guess."
        )
    return None


def _esc(text: str) -> str:
    """Escape for HTML text content. Used on the letter prose, never on the strip."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def letter_page(packet_text: str, code: int) -> str:
    """The dispute letter inside a page, so it renders as a letter and not as text."""
    verdict = (
        "can be filed as it stands"
        if code == EXIT_CLEAN
        else "needs evidence before it is filed"
        if code == EXIT_FILE_WORTHY
        else "the engine could not answer"
    )
    # The strip is real markup and must not be escaped, so the text and the strip are
    # separated rather than escaped as one blob.
    marker = '<div class="strip">'
    head, _, tail = packet_text.partition(marker)
    if tail:
        strip_html, _, rest = (marker + tail).partition("</div>\n")
        strip_html += "</div>"
        rest = rest.replace("&lt;", "<").replace("&gt;", ">")
        body = _esc(head) + strip_html + _esc(rest)
    else:
        body = _esc(packet_text)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quayline: the dispute letter</title>
<style>
body {{ margin:0; padding:3rem 1.5rem; background:#fbfbf9; color:#1a1a1a;
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:52rem; margin:0 auto; }}
h1 {{ font-size:1.35rem; letter-spacing:-.02em; margin:0 0 .3rem; }}
.verdict {{ font-size:.9rem; color:#8a5a00; margin:0 0 2rem; }}
pre {{ white-space:pre-wrap; font:14px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#fff; border:1px solid #d8d8d8; border-radius:.3rem; padding:1.25rem; }}
.back {{ display:inline-block; margin-top:1.5rem; font-size:.9rem; }}
@media (prefers-color-scheme: dark) {{
  body {{ background:#16161a; color:#e8e8e6; }}
  pre {{ background:#1c1c20; border-color:#333; }}
  .verdict {{ color:#e0b060; }}
}}
</style></head>
<body><main>
<h1>The dispute letter</h1>
<p class="verdict">This packet {verdict}.</p>
<pre>{body}</pre>
<p><a class="back" href="/">Audit another</a></p>
</main></body></html>
"""


def specimen_page() -> str:
    """The full specimen, including the day strip, from the same generator."""
    try:
        return render_specimen(build_specimen())
    except SpecimenError as exc:
        return f"<!doctype html><p>specimen unavailable: {exc}</p>"


__all__ = ["FORM_PAGE", "first_missing", "letter_page", "specimen_page"]
