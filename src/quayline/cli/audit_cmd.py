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
from pathlib import Path
from typing import Any, TextIO

from quayline.cli.audit_render import (
    as_human as _human,
)
from quayline.cli.audit_render import (
    as_json as _as_json,
)
from quayline.cli.audit_render import (
    resolve_disclosed,
)
from quayline.cli.coverage_cmd import add_parser as add_coverage_parser
from quayline.cli.coverage_cmd import run_coverage
from quayline.cli.evidence_args import KINDS, EvidenceArgsError, capture_request
from quayline.cli.exit_codes import (
    EXIT_CLEAN,
    EXIT_ENGINE_ERROR,
    EXIT_FILE_WORTHY,
)
from quayline.cli.serve_cmd import add_parser as add_serve_parser
from quayline.cli.serve_cmd import serve_intake
from quayline.engine.audit import audit
from quayline.engine.identify import identify_carrier
from quayline.engine.result import AuditResult
from quayline.evidence.capture import Capture, Register
from quayline.evidence.packet import Claim, Packet, assemble, render
from quayline.filing.dispute import dispute_for
from quayline.filing.evidence import EvidenceRefusedError, items_for
from quayline.ingest.bind import BindError, bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.tariffs.corpus import load_corpus

#: Re-exported from ``cli.exit_codes`` so the existing importers of this module keep
#: working. The intake cannot import this module, so the shared numbers had to move
#: somewhere both sides can reach without pointing back.


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
        required=False,
        default="",
        help=(
            "carrier name as published, for example 'Maersk' or 'Hapag-Lloyd'. "
            "Optional since issue 218: when the invoice names a rate rule we hold a "
            "schedule for, the carrier is read from that rule. Supply it for any other "
            "carrier, which is the honest limit of detection."
        ),
    )
    run.add_argument("--terminal", default="", help="terminal or gateway, where it matters")
    run.add_argument("--invoice-ref", default="", help="override the invoice reference")
    run.add_argument("--json", action="store_true", help="emit the full result as JSON")
    run.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="PATH",
        help="an artifact to attach to the packet. Repeatable, and needs --kind, "
        "--capturer and --affiliation",
    )
    run.add_argument(
        "--kind",
        choices=sorted(KINDS),
        help="what the artifact is. Named rather than read off the filename",
    )
    run.add_argument("--capturer", default="", help="who took the artifact. Never defaulted")
    run.add_argument("--affiliation", default="", help="what ties the capturer to the record")
    run.add_argument(
        "--packet",
        action="store_true",
        help=(
            "print the rendered dispute packet, the letter a carrier reads. "
            "Mutually exclusive with --json."
        ),
    )
    add_coverage_parser(sub)

    add_serve_parser(sub)
    return parser


@dataclass(frozen=True, slots=True)
class _Run:
    result: AuditResult
    invoice_date: Any
    evidence: tuple[Capture, ...] = ()


def _audit_one(args: argparse.Namespace) -> _Run:
    if not args.path.exists():
        raise EngineError(f"no such file: {args.path}")

    data = args.path.read_bytes()
    bound = bind_ledger(extract_text_layer(data))
    carrier = args.carrier or _identify(bound.rate_rule)
    result = audit(
        data,
        carrier,
        args.terminal,
        resolve_disclosed(bound.rate_rule, args.terminal),
        invoice_ref=args.invoice_ref,
    )
    return _Run(
        result=result,
        invoice_date=bound.invoice_date,
        evidence=capture_request(args),
    )


def _identify(declared_rule: str) -> str:
    """The carrier the disclosed rule names, or an explanation and nothing else.

    Issue 218. Reads the rate rule the invoice discloses under 541.6(c)(2) and looks it
    up in the transcribed corpus, so the carrier comes out of tariff data somebody read
    and cited rather than out of a letterhead.

    Where that cannot answer, the reader is asked. 541.6 does not require a carrier to
    name itself on the invoice face, and a default would be a guess, and a guess here
    computes a day count from the wrong rule and looks entirely plausible.
    """
    found = identify_carrier(declared_rule, tuple(load_corpus().values()))
    if found is not None:
        return found.carrier
    raise EngineError(
        f"could not tell which carrier this invoice is from. It names the rate rule "
        f"{declared_rule!r}, and either no schedule is transcribed under that name or "
        f"more than one carrier uses it. Say which with --carrier, for example "
        f"--carrier Maersk. `quayline coverage` lists what is held."
    )


def _packet_claims(packet: Packet) -> tuple[Claim, ...]:
    """The claims a packet holds, so it can be re-assembled with evidence."""
    return tuple(section.claim for section in packet.sections)


def _with_evidence(packet: Packet, run: _Run) -> Packet:
    """Attach whatever the operator supplied, re-assembling the packet.

    Re-assembled rather than mutated, because a packet edited after assembly is a
    packet nobody reviewed.
    """
    if not run.evidence:
        return packet
    contested = tuple(section.claim for section in packet.sections if section.claim.needs_evidence)
    if not contested:
        return packet
    items = items_for(
        contested,
        Register(captures=run.evidence),
        as_of=run.invoice_date,
    )
    return assemble(_packet_claims(packet), items)


def _run_non_audit(args: argparse.Namespace, out: TextIO) -> int | None:
    """Run a command that is not an audit. ``None`` means it is an audit.

    Split out because adding the intake pushed ``main`` past the point where a reader
    can hold it, and the fix is fewer returns in one function rather than a suppression.
    """
    if args.command == "coverage":
        return run_coverage(args, out)
    if args.command == "serve":
        return serve_intake(args.host, args.port, out)
    return None


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

    delegated = _run_non_audit(args, out)
    if delegated is not None:
        return delegated

    try:
        run = _audit_one(args)
    except (
        EngineError,
        EvidenceArgsError,
        BindError,
        EvidenceRefusedError,
        KeyError,
        ValueError,
    ) as exc:
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
        try:
            packet = _with_evidence(dispute_for(result), run)
        except (
            EngineError,
            EvidenceArgsError,
            EvidenceRefusedError,
            BindError,
            ValueError,
        ) as exc:
            if args.json:
                json.dump({"error": str(exc)}, out, indent=2)
                out.write("\n")
            else:
                out.write(f"Could not assemble that packet.\n{exc}\n")
            return EXIT_ENGINE_ERROR
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
