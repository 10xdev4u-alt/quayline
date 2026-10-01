"""Issue 79: the command line interface, with a human line and a machine line.

Two readers, so two formats. An operator wants to know whether to send a letter and
how much is at stake. A pipeline wants the whole result and a predictable exit code.
One format serving both gives you a machine format nobody can read or a human format
somebody has to scrape.

The exit codes are the contract

- ``0``  nothing worth filing. A clean invoice, or only informational findings.
- ``1``  filing worthy findings. A letter should be prepared.
- ``2``  the engine could not answer. An unreadable document, an unknown carrier, a
  field we could not bind. This is our failure.

Code ``2`` is separate from ``1`` on purpose. A command that returned the same code
for "nothing found" and "I could not read the file" lets a pipeline read its own
extraction bug as a clean audit, which is how a broken month looks like a good one.

What the human line carries

The claim strategy from ``engine/ordering.py``, the recomputed figure and what is
uncomputable, and the 541.8(a) mitigation deadline anchored on the invoice issuance
date printed on the document. Not on a cargo date: a carrier who invoices late has
already failed 541.7(a), and the mitigation window is a separate entitlement that
runs from the invoice.

What the JSON carries

Everything on the ``AuditResult``, with money serialised as string or null rather
than float. ``Decimal`` through a JSON encoder becomes a float, and a demand of
4760.005 is not representable in binary, so a float would quietly change the number
in a demand letter. Null is used for an absent figure and never zero, which is the
three-state rule in ``result.py`` surviving serialisation.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO

from quayline.cli.coverage_cmd import add_parser as add_coverage_parser
from quayline.cli.coverage_cmd import run_coverage
from quayline.engine.audit import audit
from quayline.engine.ordering import order_findings, strategy_for
from quayline.engine.recovery import estimate_for
from quayline.engine.result import AuditResult
from quayline.evidence.packet import render
from quayline.filing.dispute import dispute_for
from quayline.ingest.bind import BindError, bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.regulation.deadline import InvoiceIssued, dispute_request_deadline

#: Nothing worth filing.
EXIT_CLEAN = 0
#: Filing worthy findings.
EXIT_FILE_WORTHY = 1
#: The engine could not answer. Our failure, not the carrier's.
EXIT_ENGINE_ERROR = 2


class EngineError(RuntimeError):
    """The command could not produce an audit, and says why in one line."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quayline",
        description=(
            "Audit a demurrage and detention invoice under 46 CFR Part 541 from "
            "the disclosures on the document itself."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("audit", help="audit one invoice PDF")
    run.add_argument("path", type=Path, help="the invoice PDF")
    run.add_argument(
        "--carrier",
        required=True,
        help=(
            "carrier name as published, for example 'Maersk' or 'Hapag-Lloyd'. "
            "Required because 541.6 does not ask a carrier to name itself on the "
            "invoice face."
        ),
    )
    run.add_argument("--terminal", default="", help="terminal or gateway, where it matters")
    run.add_argument("--invoice-ref", default="", help="override the invoice reference")
    run.add_argument("--json", action="store_true", help="emit the full result as JSON")
    run.add_argument(
        "--packet",
        action="store_true",
        help=(
            "print the rendered dispute packet, the letter a carrier reads. "
            "Mutually exclusive with --json."
        ),
    )
    add_coverage_parser(sub)
    return parser


def _money(value: Decimal | None) -> str | None:
    """A ``Decimal`` as a string, or ``None``.

    String, not float. A ``Decimal`` through a JSON encoder becomes a float, and
    binary floating point cannot hold every cent, so a demand letter would carry a
    number nobody quoted.
    """
    return None if value is None else str(value)


def _date(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def _as_json(result: AuditResult) -> dict[str, Any]:
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


def _human(result: AuditResult, invoice_date: Any) -> str:
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


@dataclass(frozen=True, slots=True)
class _Run:
    result: AuditResult
    invoice_date: Any


def _audit_one(args: argparse.Namespace) -> _Run:
    if not args.path.exists():
        raise EngineError(f"no such file: {args.path}")

    data = args.path.read_bytes()
    result = audit(data, args.carrier, args.terminal, invoice_ref=args.invoice_ref)
    bound = bind_ledger(extract_text_layer(data))
    return _Run(result=result, invoice_date=bound.invoice_date)


def main(argv: list[str] | None = None, stream: TextIO | None = None) -> int:
    """Run one command. Returns the exit code, prints to ``stream`` or stdout."""
    out = stream if stream is not None else sys.stdout
    parser = _parser()

    if argv is not None and not argv:
        parser.print_usage(out)
        return EXIT_ENGINE_ERROR

    args = parser.parse_args(argv)

    if getattr(args, "packet", False) and getattr(args, "json", False):
        out.write(
            "--packet and --json cannot be combined. The packet is the letter a "
            "carrier reads and the JSON is the machine result, and silently "
            "choosing one would hand a pipeline prose.\n"
        )
        return EXIT_ENGINE_ERROR

    if args.command == "coverage":
        return run_coverage(args, out)

    try:
        run = _audit_one(args)
    except (EngineError, BindError, KeyError, ValueError) as exc:
        if args.json:
            json.dump({"error": str(exc)}, out, indent=2)
            out.write("\n")
        else:
            out.write(f"Could not audit that document.\n{exc}\n")
        return EXIT_ENGINE_ERROR

    result = run.result

    if args.json:
        json.dump(_as_json(result), out, indent=2)
        out.write("\n")
    elif args.packet:
        packet = dispute_for(result)
        out.write(render(packet))
        verdict = "can be filed" if packet.can_file else "cannot be filed"
        out.write(f"\nThis packet {verdict} as it stands.\n")
    else:
        out.write(_human(result, run.invoice_date) + "\n")

    return EXIT_FILE_WORTHY if result.findings else EXIT_CLEAN


__all__ = [
    "EXIT_CLEAN",
    "EXIT_ENGINE_ERROR",
    "EXIT_FILE_WORTHY",
    "EngineError",
    "main",
]
