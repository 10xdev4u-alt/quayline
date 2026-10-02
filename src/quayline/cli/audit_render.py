"""Turning an :class:`AuditResult` into something a person or a program can read.

A leaf module, and that is the whole reason it exists. The command line renders audits
to a terminal and the intake renders them over HTTP. The command line also starts the
intake, so the two cannot import each other. Both of them import this instead, and the
dependency points one way.

``as_json`` and ``as_human`` are the two shapes. ``resolve_disclosed`` is here because
it is the tariff lookup both call and it reads like rendering, sitting next to the
output it feeds.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from quayline.engine.ordering import order_findings, strategy_for
from quayline.engine.recovery import estimate_for
from quayline.engine.result import AuditResult
from quayline.regulation.deadline import InvoiceIssued, dispute_request_deadline
from quayline.tariffs.corpus import FixtureError, load_corpus
from quayline.tariffs.resolution import RateQuery, Resolution, resolve


def _money(value: Decimal | None) -> str | None:
    """A ``Decimal`` as a string, or ``None``.

    String, not float. A ``Decimal`` through a JSON encoder becomes a float, and
    binary floating point cannot hold every cent, so a demand letter would carry a
    number nobody quoted.
    """
    return None if value is None else str(value)


def _date(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def as_json(result: AuditResult) -> dict[str, Any]:
    return {
        "carrier": result.carrier,
        "terminal": result.terminal,
        "invoice_ref": result.invoice_ref,
        "demanded_total": _money(result.demanded_total),
        "recomputed_total": _money(result.recomputed_total),
        "variance": _money(result.variance),
        "variance_pct": _money(result.variance_pct),
        "computed_free_time_expiry": _date(result.computed_free_time_expiry),
        "computed_charge_days": result.computed_charge_days,
        "can_file": result.can_file,
        "warnings": list(result.warnings),
        "findings": [
            {
                "code": f.code,
                "cite": f.cite,
                "summary": f.summary,
                "detail": f.detail,
                "days": [d.isoformat() for d in f.days],
                "grounds": [str(g) for g in f.grounds],
            }
            for f in result.findings
        ],
    }


def as_human(result: AuditResult, invoice_date: Any) -> str:
    """The triage line, for someone deciding whether to send a letter."""
    strategy = strategy_for(result)
    ordered = order_findings(result)
    lines = [
        f"{result.carrier} {result.invoice_ref}".strip(),
        f"  terminal          {result.terminal or 'not stated'}",
        f"  document          {strategy.document_kind}",
    ]

    if invoice_date is not None:
        deadline = dispute_request_deadline(InvoiceIssued(issuance_date=invoice_date))
        lines.append(f"  mitigate by       {deadline.isoformat()} (541.8(a))")

    if result.computed_free_time_expiry is not None:
        lines.append(
            f"  free time expires {result.computed_free_time_expiry.isoformat()} "
            f"({result.computed_charge_days} chargeable day(s))"
        )

    demanded = _money(result.demanded_total)
    lines.append(
        f"  demanded          {demanded}"
        if demanded is not None
        else "  demanded          not stated on the document"
    )
    recomputed = _money(result.recomputed_total)
    lines.append(
        f"  recomputed        {recomputed}"
        if recomputed is not None
        else "  recomputed        not computable from what we hold"
    )

    estimate = estimate_for(result)
    if estimate is not None:
        lines.append(f"  at stake          {_money(estimate.amount)}")

    if result.findings:
        lines.append("")
        for item in ordered:
            lines.append(f"  [{item.tier}] {item.code} {item.finding.cite}")
            lines.append(f"      {item.finding.summary}")
    else:
        lines.append("")
        lines.append("  Nothing worth filing.")

    if result.can_file is False:
        lines.append("")
        lines.append("  Not fileable as it stands. Read the blockers above.")

    return "\n".join(lines)


def resolve_disclosed(rate_rule: str, terminal: str) -> Resolution | None:
    """Resolve the rule the carrier disclosed against the transcribed corpus.

    The rule comes off the document under 541.6(c)(2), so nothing is typed by an
    operator. A rule we do not hold resolves to a ``Resolution`` with no block and a
    reason, which ``audit`` turns into a ``tariff_unresolved`` finding rather than a
    guessed rate.

    ``None`` when the corpus cannot be loaded at all, so a missing or corrupt corpus
    is a warning rather than an audit that refuses to run.
    """
    if not rate_rule:
        return None
    try:
        blocks = tuple(load_corpus().values())
    except (FixtureError, OSError):
        return None
    return resolve(
        RateQuery(reference=rate_rule, on="container", terminal=terminal or None),
        blocks,
    )


__all__ = ["as_human", "as_json", "resolve_disclosed"]
