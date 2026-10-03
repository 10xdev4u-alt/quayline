"""Issue 187: the specimen page, built by running the engine.

What this is

A public page that shows one invoice audited end to end: the required disclosures with
their cites, the recomputation with the rate that produced it, and every finding with
its clause. Generated, not written, because a hand written page describing a number the
code computes becomes a liability the day the code changes.

The rule that shapes the whole module

**Nothing on the page may read as verified unless something checked it.** Each
disclosure is one of:

``verified``      the binder read it off the bound document
``absent``        the binder looked and the document does not state it
``not checked``   we have no code that reads this clause

That third state is the honest answer for most of 541.6, and it is the state a page
about a self-auditing engine ought to be willing to print. A reader who counts
fourteen verified and five not checked learns something true. A reader shown twenty
green ticks learns nothing at all, and cannot tell whether we checked or guessed.

The fixture

``tests/fixtures/born_digital_invoice.pdf`` is a hand built PDF. It is shaped to
exercise the parser and priced against a real transcribed tariff, but it is not a
customer's invoice and the page says so in its first paragraph. Quoting it as
evidence of a recovery would be the exact overclaim this product exists to avoid.

No recovery rate appears anywhere. ``AGENTS.md`` section five is explicit that the
category's recovery figures are vendor published and unaudited, that we do not repeat
them, and that we do not infer ours from them. None has been measured.
"""

from __future__ import annotations

import os
from dataclasses import KW_ONLY, dataclass
from decimal import Decimal
from pathlib import Path

from quayline.calendars.day_basis import RULES as DAY_BASIS_RULES
from quayline.cli.coverage_cmd import build_rows
from quayline.engine.audit import audit
from quayline.engine.result import AuditResult
from quayline.ingest.bind import BoundLedger, bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.regulation import Trade
from quayline.regulation.checklist import ChecklistField, required_for
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.resolution import RateQuery, resolve

#: The fixture this page audits. Named here so the page and the tests cannot point at
#: different files.
#: Resolved against this file rather than the working directory. Issue 208: it was the
#: string ``Path(<repo>/tests/fixtures/...)``, which resolved only from
#: the repository root. In the container the landing page raised FileNotFoundError and
#: served nothing at all, because this is the technical specimen and the
#: file was not where the working directory said it was. Overridable for a bundle that
#: is not a checkout.
FIXTURE = Path(
    os.environ.get("QUAYLINE_FIXTURE")
    or Path(__file__).resolve().parents[3] / "tests/fixtures/born_digital_invoice.pdf"
)

#: Terminal and carrier for the fixture, matching what the transcribed corpus holds.
FIXTURE_CARRIER = "Maersk"
FIXTURE_TERMINAL = "newark"

#: The three verification states. A fourth would be a fourth kind of not knowing.
VERIFIED = "verified"
ABSENT = "absent"
NOT_CHECKED = "not checked"


class SpecimenError(RuntimeError):
    """The specimen could not be built, and says which part."""


@dataclass(frozen=True, slots=True)
class Disclosure:
    """One required disclosure, and whether anything verified it."""

    cite: str
    heading: str
    group: str
    text: str
    verification: str
    value: str = ""


@dataclass(frozen=True, slots=True)
class Finding:
    """One finding as the page shows it: code, clause, one line of summary."""

    code: str
    cite: str
    summary: str


@dataclass(frozen=True, slots=True)
class ResearchLink:
    """A claim on the page and the document that supports it."""

    cite: str
    claim: str
    path: str


@dataclass(frozen=True, slots=True)
class Specimen:
    """Everything the page shows, every value taken from the engine."""

    carrier: str
    terminal: str
    invoice_ref: str
    fixture_path: str

    free_time_expires: str
    chargeable_days: int
    demanded_total: str
    recomputed_total: str
    variance: str
    stated_rate: str
    tariff_rule: str
    tariff_rate: str
    tariff_source: str
    tariff_effective_from: str

    disclosures: tuple[Disclosure, ...]
    findings: tuple[Finding, ...]
    research_links: tuple[ResearchLink, ...]
    coverage: tuple[tuple[str, str, int, bool], ...]

    _unused: KW_ONLY
    #: The audit itself, so a renderer can draw the day strip from the day result the
    #: engine computed rather than recomputing it. A second day count would be a
    #: second chance to disagree, in front of a reader.
    audit_result: AuditResult | None = None

    @property
    def verified_count(self) -> int:
        return sum(1 for d in self.disclosures if d.verification == VERIFIED)

    @property
    def unchecked_count(self) -> int:
        return sum(1 for d in self.disclosures if d.verification == NOT_CHECKED)


#: Which binder field establishes which clause. Anything absent from this table is
#: honestly reported as not checked, which is the point of having a table rather than
#: a rule.
_CITE_TO_FIELD: dict[str, str] = {
    "541.6(a)(1)": "container_number",
    "541.6(a)(2)": "bol_number",
    "541.6(a)(3)": "invoice_date",
    "541.6(b)(3)": "allowed_free_time_days",
    "541.6(b)(4)": "free_time_start",
    "541.6(b)(5)": "free_time_end",
    "541.6(b)(6)": "availability_date",
    "541.6(b)(8)": "charged_dates",
    "541.6(c)(1)": "stated_total",
    "541.6(c)(2)": "rate_rule",
    "541.6(c)(3)": "rate",
}


def _value_of(field_name: str, bound: BoundLedger) -> str:
    """Whatever the bound document holds for this field, as text."""
    if field_name == "charged_dates":
        return ", ".join(d.isoformat() for d in bound.charged_dates)
    value = getattr(bound, field_name, None)
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _disclosures(bound: BoundLedger) -> tuple[Disclosure, ...]:
    """Every required disclosure for an import, with what we can say about it.

    A clause the binder has no field for is ``not checked`` even when the fixture
    might well state it. We did not look, so we do not claim to have looked.
    """
    rows: list[Disclosure] = []
    for clause in required_for(Trade.IMPORT):
        field_name = _CITE_TO_FIELD.get(clause.cite)
        if field_name is None:
            rows.append(
                Disclosure(
                    cite=clause.cite,
                    heading=clause.heading,
                    group=clause.group,
                    text=clause.statement,
                    verification=NOT_CHECKED,
                )
            )
            continue
        value = _value_of(field_name, bound)
        rows.append(
            Disclosure(
                cite=clause.cite,
                heading=clause.heading,
                group=clause.group,
                text=clause.statement,
                verification=VERIFIED if value else ABSENT,
                value=value,
            )
        )
    return tuple(rows)


def _money(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.2f}"


def build_specimen(carrier: str = FIXTURE_CARRIER, terminal: str = FIXTURE_TERMINAL) -> Specimen:
    """Audit the fixture and collect everything the page needs.

    Raises ``SpecimenError`` rather than rendering a half page, because a specimen
    that silently omits the recomputation is the failure this whole module exists to
    prevent.
    """

    if carrier not in DAY_BASIS_RULES:
        raise SpecimenError(
            f"no day basis rule for carrier {carrier!r}. The page would have no free "
            f"time arithmetic to show, and rendering it half would misrepresent what "
            f"the engine checked."
        )

    path = Path(FIXTURE)
    if not path.exists():
        raise SpecimenError(f"no fixture at {path}. The specimen is generated, not typed.")

    data = path.read_bytes()
    bound = bind_ledger(extract_text_layer(data))

    blocks = tuple(load_corpus().values())
    resolution = resolve(
        RateQuery(reference=bound.rate_rule, on="container", terminal=terminal or None),
        blocks,
    )
    if not resolution.resolved or resolution.block is None:
        raise SpecimenError(
            f"the fixture's rate rule {bound.rate_rule!r} does not resolve to a "
            f"transcribed block, so the page would have no rate to show. "
            f"{resolution.withheld_reason}"
        )

    result = audit(data, carrier, terminal, resolution)

    return Specimen(
        carrier=carrier,
        terminal=terminal,
        invoice_ref=result.invoice_ref,
        fixture_path=str(FIXTURE),
        free_time_expires=result.computed_free_time_expiry.isoformat()
        if result.computed_free_time_expiry
        else "",
        chargeable_days=result.computed_charge_days or 0,
        demanded_total=_money(result.demanded_total),
        recomputed_total=_money(result.recomputed_total),
        variance=_money(result.variance),
        stated_rate=f"{bound.lines[0].rate:.2f}",
        tariff_rule=resolution.block.rule,
        tariff_rate=f"{resolution.block.price(result.computed_charge_days or 0):.2f}",
        tariff_source=resolution.block.source,
        tariff_effective_from=resolution.block.effective_from,
        audit_result=result,
        disclosures=_disclosures(bound),
        findings=tuple(Finding(f.code, f.cite, f.summary) for f in result.findings),
        research_links=_RESEARCH_LINKS,
        coverage=_coverage(),
    )


_RESEARCH_LINKS: tuple[ResearchLink, ...] = (
    ResearchLink(
        cite="541.6(c)(2)",
        claim="The carrier must name the rule it billed under, so a charge is recomputable.",
        path="docs/research/001-regulation.md",
    ),
    ResearchLink(
        cite="541.6(b)(3)",
        claim="Free time, its endpoints and the days charged are all disclosed, so the day count is arithmetic rather than argument.",
        path="docs/research/001-regulation.md",
    ),
    ResearchLink(
        cite="541.5",
        claim="An omission of a required disclosure is automatic: no cure period, no showing of prejudice.",
        path="docs/research/001-regulation.md",
    ),
    ResearchLink(
        claim="Maersk charges on a Monday to Saturday working day basis, so free time expires on the eighth here.",
        cite="working day basis",
        path="docs/research/002-carriers.md",
    ),
    ResearchLink(
        claim="The Newark dry schedule prices days five to eight at 390.00.",
        cite="rate tiers",
        path="docs/research/002-carriers.md",
    ),
)


def _coverage() -> tuple[tuple[str, str, int, bool], ...]:
    """Per carrier: state, granularity, rules held, verified.

    The same rows the ``coverage`` command prints, so the page cannot claim coverage
    the command would contradict.
    """
    return tuple((r.carrier, r.state, r.rules_held, r.verified) for r in build_rows())


__all__ = [
    "ABSENT",
    "NOT_CHECKED",
    "VERIFIED",
    "ChecklistField",
    "Disclosure",
    "Finding",
    "ResearchLink",
    "Specimen",
    "SpecimenError",
    "build_specimen",
]
