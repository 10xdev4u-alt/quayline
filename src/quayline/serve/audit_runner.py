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
from typing import Any, Protocol, cast

from quayline.cli.exit_codes import EXIT_CLEAN, EXIT_FILE_WORTHY
from quayline.engine.audit import audit
from quayline.evidence.packet import render
from quayline.filing.dispute import dispute_for
from quayline.ingest.bind import bind_ledger
from quayline.ingest.pdftext import extract_text_layer
from quayline.web.daystrip import build_strip
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
        bound = bind_ledger(extract_text_layer(pdf))
        result = audit(
            pdf,
            carrier,
            terminal,
            resolve_disclosed(bound.rate_rule, terminal),
            invoice_ref="",
        )

        code = EXIT_FILE_WORTHY if result.findings else EXIT_CLEAN
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


__all__ = ["AuditRunner", "build_runner"]
