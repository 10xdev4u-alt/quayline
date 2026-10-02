"""The one seam between the intake and the command line.

An uploaded invoice has to be audited exactly the way ``quayline audit`` audits a file
on disk, and a test asserts the two agree to the cent. Sharing the functions gets that.
Sharing the argument parser does not, because the parser wants a path and an upload is
bytes already in memory.

So the intake does not import the command line. It declares what it needs as a
protocol, and ``cli.serve_cmd`` builds the callable from functions it already has. The
dependency points one way, and that is the only reason both modules import cleanly on
their own.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Any, Protocol, cast

from quayline.cli.exit_codes import EXIT_CLEAN, EXIT_FILE_WORTHY
from quayline.engine.audit import audit
from quayline.engine.result import AuditResult
from quayline.evidence.packet import Packet, render
from quayline.filing.dispute import dispute_for
from quayline.ingest.bind import BoundLedger, bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.web.daystrip import DayStrip, build_strip
from quayline.web.strip_render import render_strip


class AuditRunner(Protocol):
    """Renders one audit. The single seam between the intake and the command line.

    The intake needs the command line's tariff resolution and its two output
    formatters, and the command line needs the intake to exist. Rather than let the
    two modules import each other, whoever starts the server hands the intake one of
    these. ``cli.serve_cmd`` builds it from the functions it already has.

    Returning the exit code alongside the body keeps the HTTP status and the shell exit
    code derived from the same value, which is the point of issue 191.
    """

    def __call__(
        self, pdf: bytes, carrier: str, terminal: str, as_json: bool
    ) -> tuple[int, str]: ...


def build_runner(
    resolve_disclosed: Callable[[str, str], Any],
    as_json: Callable[[Any], dict[str, Any]],
    human: Callable[..., str],
) -> AuditRunner:
    """Build the runner from the three command line functions that render an audit."""

    def run(pdf: bytes, carrier: str, terminal: str, want_json: bool) -> tuple[int, str]:
        bound, result = _audit(pdf, carrier, terminal, resolve_disclosed)

        code = EXIT_CLEAN if not result.findings else EXIT_FILE_WORTHY
        if want_json:
            payload = dict(as_json(result))
            payload["exit_code"] = code
            return code, json.dumps(payload, indent=2)

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print(human(result, bound.invoice_date))
            print(render(dispute_for(result)))
            if result.day_count is not None:
                # The day strip goes into the letter, not beside it. It is the strongest
                # thing we have and a client should not have to ask a second question
                # to see which day the carrier charged inside free time.
                print(render_strip(build_strip(result)))
        return code, buffer.getvalue()

    return cast(AuditRunner, run)


class FindRunner(Protocol):
    """Audits and returns structure. The seam the result page is rendered from."""

    def __call__(self, pdf: bytes, carrier: str, terminal: str) -> Findings: ...


__all__ = [
    "AuditRunner",
    "FindRunner",
    "Findings",
    "build_runner",
    "find_runner",
]


def _audit(
    pdf: bytes, carrier: str, terminal: str, resolve_disclosed: Callable[[str, str], Any]
) -> tuple[BoundLedger, AuditResult]:
    """Bind and audit. The two calls the CLI makes once it has parsed its arguments."""
    bound = bind_ledger(extract_text_layer(pdf))
    result = audit(
        pdf,
        carrier,
        terminal,
        resolve_disclosed(bound.rate_rule, terminal),
        invoice_ref="",
    )
    return bound, result


@dataclass(frozen=True, slots=True)
class Findings:
    """What the result page renders, as structure rather than as rendered text.

    Issue 195. The page used to be handed the letter as a finished string and pull the
    day strip back out of it by splitting on the literal ``<div class="strip">``, which
    meant the page's correctness depended on the shape of markup another module
    happened to emit. It holds the objects instead, so nothing on the page has to guess
    at where a tag begins.
    """

    code: int
    result: AuditResult
    bound: BoundLedger
    packet: Packet
    strip: DayStrip | None


def find_runner(resolve_disclosed: Callable[[str, str], Any]) -> FindRunner:
    """Build the structure-returning runner the result page uses.

    Separate from :func:`build_runner` on purpose. The other one has to reproduce the
    command line byte for byte, and it is pinned to that by a test. Changing its
    signature to return objects would break the contract that matters most, to serve a
    page that was parsing markup to get them anyway.
    """

    def run(pdf: bytes, carrier: str, terminal: str) -> Findings:
        bound, result = _audit(pdf, carrier, terminal, resolve_disclosed)
        return Findings(
            code=EXIT_CLEAN if not result.findings else EXIT_FILE_WORTHY,
            result=result,
            bound=bound,
            packet=dispute_for(result),
            strip=build_strip(result) if result.day_count is not None else None,
        )

    return run
