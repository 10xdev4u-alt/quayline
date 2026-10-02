"""Issue 191: the ``serve`` subcommand, and the one seam between CLI and intake.

This module exists because ``audit_cmd`` needs the intake and the intake needs the
command line's audit functions. Two modules cannot import each other, so this is the
third one: ``audit_cmd`` imports the parser from here, and here we build the callable
that renders an audit and hand it to the server.

``serve.app`` imports nothing from ``cli`` except ``cli.exit_codes``, which is a leaf.
That is what keeps the dependency pointing one way and every module importable on its
own, which is the property that was missing when this was first written.
"""

from __future__ import annotations

from typing import Any

from quayline.cli.audit_render import as_human, as_json, resolve_disclosed
from quayline.serve.app import run_server
from quayline.serve.audit_runner import AuditRunner, find_runner
from quayline.serve.audit_runner import build_runner as _build_runner


def add_parser(sub: Any) -> None:
    """Register ``serve`` on the existing command line."""
    parser = sub.add_parser(
        "serve",
        help="run the local intake, so an invoice can be audited without a terminal",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "loopback only, and there is no flag to widen it. A non loopback host is "
            "refused, because this holds a container number and a disputed amount and "
            "has no authentication. See quayline.serve.security."
        ),
    )


def build_runner() -> AuditRunner:
    """Build the audit callable the server uses, out of the command line's own parts.

    Top level imports, which is only possible because ``serve.audit_runner`` no longer
    imports this package's audit module. The intake declares what it needs and this
    supplies it, so ``audit_cmd`` can import the parser below without closing a loop.
    """
    return _build_runner(resolve_disclosed, as_json, as_human)


def serve_intake(host: str, port: int, out: Any) -> int:
    """Run the intake until interrupted. Returns a CLI exit code."""
    return run_server(host, port, build_runner(), find_runner(resolve_disclosed), out)


__all__ = ["add_parser", "build_runner", "find_runner", "serve_intake"]
