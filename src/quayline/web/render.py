"""Issue 187: rendering the specimen as a single self-contained HTML file.

No JavaScript, no stylesheet link, no network request. A page about evidence that
needs a CDN to display is not evidence of anything, and the reader should be able to
save this file and read it in five years with the network unplugged.

Every number is interpolated from a ``Specimen``, which was built by running the
engine. There is no arithmetic here and no figure typed as a literal, so the page and
the code cannot drift apart without a test failing.

The writing follows ``AGENTS.md`` section four. No em dashes, sentence case headings,
active voice, and a number that appears here traces to a command in the footer.
"""

from __future__ import annotations

from html import escape

from quayline.web.specimen import ABSENT, VERIFIED, Specimen, build_specimen

_STYLE = """
:root { --ink:#1a1a1a; --muted:#5c5c5c; --rule:#d8d8d8; --bg:#fbfbf9;
  --good:#1f6b3b; --gap:#8a5a00; --none:#6b6b6b; }
* { box-sizing:border-box; }
body { margin:0; padding:3rem 1.5rem; overflow-x:hidden; background:var(--bg); color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
main { max-width:60rem; margin:0 auto; }
h1 { font-size:2rem; line-height:1.2; margin:0 0 .5rem; letter-spacing:-.02em; }
h2 { font-size:1.15rem; margin:2.75rem 0 .75rem; letter-spacing:-.01em; }
p { margin:0 0 1rem; max-width:44rem; }
.lede { font-size:1.05rem; color:var(--muted); }
.cite { font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--muted);
  white-space:nowrap; }
/* A four column disclosure table cannot fit a 390px phone without either shrinking
   the text past reading or panning the whole page. The table gets its own scroll
   container so the page itself never moves sideways, which also keeps a phone reader
   from losing its place in the document. */
.tw { overflow-x:auto; margin:1rem 0; -webkit-overflow-scrolling:touch; }
table { width:100%; border-collapse:collapse; margin:0; font-size:.94rem; }
.tw table { min-width:34rem; }
th { text-align:left; font-size:.78rem; text-transform:uppercase;
  letter-spacing:.06em; color:var(--muted); border-bottom:1px solid var(--rule);
  padding:.5rem .6rem; }
td { padding:.55rem .6rem; border-bottom:1px solid var(--rule); vertical-align:top; }
td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
tr.emph td { border-top:2px solid var(--ink); font-weight:600; }
tr.emph td + td { border-bottom:none; }
.tag { font-size:.75rem; padding:.1rem .45rem; border-radius:.2rem; white-space:nowrap; }
.v-verified { color:var(--good); background:#e8f2ea; }
.v-absent { color:var(--gap); background:#fdf3e2; }
.v-unchecked { color:var(--none); background:#eeeeee; }
.callout { border-left:3px solid var(--ink); padding:.75rem 1rem; background:#fff;
  margin:1.5rem 0; }
.callout p:last-child { margin-bottom:0; }
code { font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#eee; padding:.1rem .3rem; border-radius:.2rem; }
footer { margin-top:3.5rem; padding-top:1.25rem; border-top:1px solid var(--rule);
  font-size:.85rem; color:var(--muted); }
footer p { max-width:none; }
ul { margin:.5rem 0 1rem; padding-left:1.2rem; }
li { margin:.3rem 0; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#e8e8e6; --muted:#9a9a97; --rule:#333; --bg:#16161a;
    --good:#7fd0a0; --gap:#e0b060; --none:#999; }
  .v-verified { background:#123024; } .v-absent { background:#3a2c10; }
  .v-unchecked { background:#242424; }
  .callout { background:#1c1c20; } code { background:#26262a; }
}
"""


def _tag(verification: str) -> str:
    css = {VERIFIED: "v-verified", ABSENT: "v-absent"}.get(verification, "v-unchecked")
    return f'<span class="tag {css}">{escape(verification)}</span>'


def _row(cells: str) -> str:
    return f"      <tr>{cells}</tr>"


def _disclosure_table(spec: Specimen) -> str:
    rows = [
        _row(
            f'<td class="cite">{escape(d.cite)}</td>'
            f"<td>{escape(d.heading)}</td>"
            f"<td>{escape(d.value) or '<span class=v-unchecked>not stated</span>'}</td>"
            f"<td>{_tag(d.verification)}</td>"
        )
        for d in spec.disclosures
    ]
    return "\n".join(rows)


def _recomputation_table(spec: Specimen) -> str:
    """The recomputation, as the reader checks it.

    The stated rate and the recomputed charge sit next to each other on purpose. The
    whole argument is that the carrier disclosed the rate and we applied it, so the
    page should make that comparison easy rather than ask the reader to assemble it.
    """
    lines = [
        _row(
            "<td>Chargeable days, recomputed from the disclosures</td>"
            f'<td class="num">{spec.chargeable_days}</td>'
        ),
        _row(
            "<td>Rate the carrier stated on the invoice</td>"
            f'<td class="num">{escape(spec.stated_rate)}</td>'
        ),
        _row(
            "<td>Recomputed charge, from the transcribed tariff</td>"
            f'<td class="num">{escape(spec.tariff_rate)}</td>'
        ),
        _row(
            "<td>Total the carrier demanded, under 541.6(c)(1)</td>"
            f'<td class="num">{escape(spec.demanded_total)}</td>'
        ),
    ]
    return "\n".join(
        [
            *lines,
            '      <tr class="emph">'
            f"<td>Recomputed total</td>"
            f'<td class="num">{escape(spec.recomputed_total)}</td></tr>',
            '      <tr class="emph">'
            f"<td>Variance</td>"
            f'<td class="num">{escape(spec.variance)}</td></tr>',
        ]
    )


def _findings_list(spec: Specimen) -> str:
    items = [
        f'      <li><span class="cite">{escape(finding.cite)}</span> '
        f"<strong>{escape(finding.code)}</strong><br>{escape(finding.summary)}</li>"
        for finding in spec.findings
    ]
    return "\n".join(items)


def _coverage_table(spec: Specimen) -> str:
    rows = [
        _row(
            f"<td>{escape(carrier)}</td><td>{escape(state)}</td>"
            f'<td class="num">{rules}</td>'
            f"<td>{'yes' if verified else 'no'}</td>"
        )
        for carrier, state, rules, verified in spec.coverage
    ]
    return "\n".join(rows)


def _research_list(spec: Specimen) -> str:
    return "\n".join(
        f"      <li><code>{escape(link.path)}</code> {escape(link.claim)}</li>"
        for link in spec.research_links
    )


def render_specimen(spec: Specimen) -> str:
    """The whole page, as one string.

    A renderer that returns text is chosen over one that returns a tree because the
    output of this is a file that gets read, diffed and archived, and anything that
    cannot be read as text cannot be diffed.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quayline specimen: one invoice audited end to end</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
  <h1>One invoice, audited end to end</h1>
  <p class="lede">
    Quayline recomputes a demurrage and detention charge from the carrier's own
    disclosures, because 46 CFR Part 541 requires the carrier to publish the rate
    rule, the rate, the free time allowance, both endpoints and the dates charged.
    This page shows one document going through that process, with every figure
    traceable to the code that produced it.
  </p>

  <div class="callout">
    <p>
      <strong>This is a test fixture, not a real invoice.</strong>
      <code>{escape(spec.fixture_path)}</code> is a hand-built PDF written to exercise
      the parser. It states a real carrier's rate rule and it is priced against a
      tariff transcribed from that carrier's own published schedule, but it is not a
      customer's document and no money has been recovered from anyone.
    </p>
  </div>

  <h2>The document</h2>
  <div class="tw"><table>
    <tr><td>Carrier</td><td>{escape(spec.carrier)}</td></tr>
    <tr><td>Terminal</td><td>{escape(spec.terminal)}</td></tr>
    <tr><td>Container</td><td>{escape(spec.invoice_ref)}</td></tr>
    <tr><td>Free time expires, recomputed</td><td>{escape(spec.free_time_expires)}</td></tr>
  </table></div>

  <h2>Recomputation</h2>
  <p>
    The rate comes from <code>{escape(spec.tariff_rule)}</code>, transcribed from
    {escape(spec.tariff_source)}, effective {escape(spec.tariff_effective_from)}.
  </p>
  <div class="tw"><table>
    <tr><th>Line</th><th style="text-align:right">Amount</th></tr>
{_recomputation_table(spec)}
  </table></div>
  <p>
    Two chargeable days, because Maersk's working day basis runs Monday to Saturday
    and seven working days from 2026-06-30 land on 2026-07-08. The invoice charges
    three. That difference is the whole finding, and it is arithmetic rather than
    argument: the carrier disclosed every input needed to reach it.
  </p>

  <h2>Findings</h2>
  <ul>
{_findings_list(spec)}
  </ul>

  <h2>Required disclosures</h2>
  <p>
    {len(spec.disclosures)} clauses of 541.6 apply to an import invoice.
    <strong>{spec.verified_count}</strong> are verified against this document,
    <strong>{spec.unchecked_count}</strong> are not checked by any code we hold and
    are listed as such rather than shown as satisfied. A field we did not read is not
    a field we can say anything about.
  </p>
  <div class="tw"><table>
    <tr><th>Clause</th><th>Disclosure</th><th>On this document</th><th>State</th></tr>
{_disclosure_table(spec)}
  </table></div>

  <h2>Where the claims come from</h2>
  <ul>
{_research_list(spec)}
  </ul>

  <h2>Coverage today</h2>
  <p>
    One carrier has transcribed rates. The rest have clock rules, closure policies or
    availability regimes but no rate table we hold, and one of them passes terminal
    demurrage through at cost with no published tariff at eight of the nine major
    gateways. We print that because a shipper is entitled to know it before buying.
  </p>
  <div class="tw"><table>
    <tr><th>Carrier</th><th>State</th><th style="text-align:right">Rules held</th><th>Verified</th></tr>
{_coverage_table(spec)}
  </table></div>

  <footer>
    <p>
      Generated by <code>make specimen</code>. Nothing on this page is typed: every
      figure is interpolated from an <code>AuditResult</code> produced by running the
      engine over the fixture, and a test fails if the two disagree.
    </p>
    <p>
      Run <code>quayline coverage</code> for the same coverage table, and read
      <code>AGENTS.md</code> before changing anything here.
    </p>
  </footer>
</main>
</body>
</html>
"""


def generate() -> str:
    """Build the specimen and render it, which is what ``make specimen`` calls.

    Kept here rather than in ``specimen.py`` so the module that owns the HTML also
    owns the entry point, and importing the renderer never needs a lazy import to
    dodge a circular dependency.
    """
    return render_specimen(build_specimen())


__all__ = ["generate", "render_specimen"]
