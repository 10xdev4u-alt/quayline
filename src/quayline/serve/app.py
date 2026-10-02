"""Issue 191: the intake handler.

One handler, one engine, no second implementation

``POST /audit`` and ``quayline audit --json`` return the same document, and a test
asserts it byte for byte. That assertion is the whole design: a client number computed
two ways is a client number that eventually disagrees with the letter we sent them.

Everything is stdlib. ``http.server`` because there is no framework and no dependency,
and ``email`` to parse multipart, which is what the stdlib offers and it handles the
format correctly. Adding ``python-multipart`` for one boundary would be a worse trade
than reading the header properly.

Nothing is written to disk

The upload lives in memory for the length of the request and is gone afterwards. No
temp file, no access log line with a container number in it, no cache. A dispute letter
names a customer and their money, and a server that writes either to a disk it did not
ask permission to use is a server that leaks.

The request log is silenced for the same reason. ``BaseHTTPRequestHandler`` logs every
path to stderr by default, and a query string is not somewhere a container number
should end up.
"""

from __future__ import annotations

import json
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar, TextIO

from quayline.cli.exit_codes import EXIT_CLEAN, EXIT_ENGINE_ERROR
from quayline.ingest.bind import BindError, OmittedError
from quayline.serve.audit_runner import AuditRunner, FindRunner
from quayline.serve.landing import landing_document
from quayline.serve.pages import first_missing, specimen_page
from quayline.serve.security import assert_loopback
from quayline.serve.upload import (
    BODY_CHUNK as _BODY_CHUNK,
)
from quayline.serve.upload import (
    BODY_TIMEOUT as _BODY_TIMEOUT,
)
from quayline.serve.upload import (
    DRAIN_CAP as _DRAIN_CAP,
)
from quayline.serve.upload import (
    DRAIN_TIMEOUT as _DRAIN_TIMEOUT,
)
from quayline.serve.upload import (
    MAX_UPLOAD_BYTES,
    parse_multipart,
)
from quayline.serve.upload import (
    error as _error,
)
from quayline.web.document import script_hash
from quayline.web.result import result_page
from quayline.web.result import script_hash as result_script_hash


def _script_hashes() -> tuple[str, ...]:
    """Every inline script this server can serve, as CSP source expressions.

    Collected rather than hard-coded, so adding a page that ships a script cannot
    leave its digest out of the policy and silently cost it every enhancement.
    """
    return script_hash(), result_script_hash()


def _http_status(exit_code: int) -> int:
    """The CLI exit contract mapped onto HTTP.

    The three codes are not HTTP statuses and must not be sent as one. A pipeline
    built against ``quayline audit`` keys on the exit code, so the exit code travels
    in the body and the header carries something an HTTP client can act on: a bad
    request for our error, a 200 for anything we answered, including "nothing to
    dispute", because that is a successful audit rather than a failed request.
    """
    if exit_code == EXIT_ENGINE_ERROR:
        return 400
    return 200


def build_handler(run_audit: AuditRunner, find_fn: FindRunner) -> type[BaseHTTPRequestHandler]:
    """The handler class. Built as a function so the tests can build their own."""

    class Handler(BaseHTTPRequestHandler):
        """One intake, three routes, no state.

        Stateless on purpose. Nothing is kept between requests, so there is no session
        to steal and nothing to clean up, and the only thing a request can do is
        compute an answer and go.
        """

        server_version = "Quayline"
        sys_version = ""
        #: Applied by :meth:`_send`, which picks the strict or page form.
        _csp = "default-src 'none'"
        #: Silence the access log. A request line is not a place for a container number.
        quiet: ClassVar[bool] = True

        def log_message(self, format: str, *args: Any) -> None:
            if not self.quiet:
                super().log_message(format, *args)

        # ------------------------------------------------------------- responses

        def _send(self, code: int, body: str, content_type: str) -> None:
            payload = body.encode("utf-8")
            # JSON gets the strictest policy and the pages get inline styles, because
            # they are self contained by design: no external stylesheet, no font CDN,
            # nothing to fetch. A CSP that blocked them would be a policy that breaks
            # the product to satisfy itself, and the first version of this did exactly
            # that and rendered an unstyled form.
            #
            # The pages also carry an inline script, for the drop target, the staged
            # progress and the day grid reveal. It is pinned by digest rather than
            # allowed with ``unsafe-inline``, so the policy still refuses every other
            # script, and the digest is computed from the same constant that gets
            # served. The page works with no script at all, so this is enhancement and
            # not a requirement.
            self._csp = (
                f"default-src 'none'; style-src 'unsafe-inline'; script-src '{script_hash()}'"
                if content_type.startswith("text/html")
                else "default-src 'none'"
            )
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            # Nothing here is a document a third party should frame or embed.
            self.send_header("Content-Security-Policy", self._csp)
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, exit_code: int, payload: dict[str, Any]) -> None:
            """Send JSON. ``exit_code`` is the CLI contract, mapped to an HTTP status.

            Named for what it is rather than ``code``, because passing a raw ``2`` here
            once sent ``HTTP/1.0 2`` to a client, and passing ``400`` here once sent
            HTTP 200 with an error body. The mapping lives in :func:`_http_status` and
            the CLI code travels inside the body.
            """
            self._send(
                _http_status(exit_code),
                json.dumps(payload, indent=2),
                "application/json; charset=utf-8",
            )

        def _html(self, exit_code: int, body: str) -> None:
            self._send(_http_status(exit_code), body, "text/html; charset=utf-8")

        def _drain(self, length: int, chunk: int = 65536) -> None:
            """Read and discard the start of a request body we are about to refuse.

            Refusing without reading leaves the client's socket holding an unread
            request, and the client sees a broken connection rather than our message,
            which is the one response an operator cannot act on. Bounded by both
            ``length`` and a cap, with a socket timeout, because a client that declares
            eight megabytes and sends twelve bytes would otherwise hold the handler
            open. The point is to leave the socket usable, not to buffer a hostile
            upload.
            """
            # Drain a bounded amount, with a socket timeout so a client that declared
            # more than it is sending cannot hold the handler open. Draining fully would
            # mean reading exactly the megabytes the limit exists to refuse, and a
            # declared length with a short body behind it is the shape that hangs.
            with suppress(OSError):
                self.connection.settimeout(_DRAIN_TIMEOUT)
            remaining = min(length, _DRAIN_CAP)
            while remaining > 0:
                try:
                    data = self.rfile.read(min(chunk, remaining))
                except (TimeoutError, OSError):
                    break
                if not data:
                    break
                remaining -= len(data)

        def _not_found(self, path: str, routes: str) -> None:
            """A 404, sent as a 404.

            Kept separate from :meth:`_json` because an HTTP status and an exit code
            are different numbers that mean different things, and passing one where
            the other belongs is exactly the confusion this module documents.
            """
            self._send(
                404,
                json.dumps({"error": f"no route {path}. Try {routes}."}),
                "application/json; charset=utf-8",
            )

        # ---------------------------------------------------------------- routes

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._html(200, landing_document())
                return
            if self.path == "/specimen":
                self._html(200, specimen_page())
                return
            self._not_found(self.path, "/, /specimen, /audit or /letter")

        def _body(self) -> bytes | None:
            """The raw request body, or ``None`` having refused it.

            The two transport level checks, split from the four content ones so neither
            method is a wall of returns. A validator that returns seven times is doing
            its job; a reviewer cannot tell which of the seven became unreachable.
            """
            length_header = self.headers.get("Content-Length")
            if not length_header or not length_header.isdigit():
                self._json(*_error("no Content-Length, so the upload size is unknown."))
                return None
            length = int(length_header)
            if length > MAX_UPLOAD_BYTES:
                self._drain(length)
                self._json(
                    *_error(
                        f"the upload is {length} bytes and the limit is "
                        f"{MAX_UPLOAD_BYTES}. A carrier invoice is a few hundred "
                        f"kilobytes, so this is a mistake rather than a document."
                    )
                )
                return None
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._json(*_error("send the file as multipart/form-data."))
                return None
            body = self._read_exactly(length)
            if body is None:
                self._json(
                    *_error(
                        f"the request declared {length} bytes and the connection ended "
                        f"first. A partial upload is refused rather than audited, "
                        f"because a truncated PDF has no honest answer."
                    )
                )
                return None
            return body

        def _read_exactly(self, length: int) -> bytes | None:
            """Read exactly ``length`` bytes, or ``None`` if the client stops early.

            ``HTTPServer`` is a ``TCPServer``: one connection is served at a time. So an
            unguarded ``rfile.read(length)`` is a denial of service, because a client
            that declares a Content-Length and then sends nothing holds every other
            request until it gives up. The timeout bounds that, and returning ``None``
            for a short read stops a truncated body being audited as if it were whole.

            The read is chunked rather than one call because a single ``read`` on a
            socket file object can return fewer bytes than asked for without meaning
            end of file.
            """
            self.connection.settimeout(_BODY_TIMEOUT)
            chunks: list[bytes] = []
            remaining = length
            try:
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, _BODY_CHUNK))
                    if not chunk:
                        return None
                    chunks.append(chunk)
                    remaining -= len(chunk)
            except (TimeoutError, OSError):
                return None
            return b"".join(chunks)

        def _read_upload(self) -> tuple[bytes, dict[str, str]] | None:
            """The PDF and the fields, or ``None`` having already answered.

            Transport checks live in :meth:`_body` and content checks in
            :func:`first_missing`, so this is three lines and each of those is
            reviewable on its own. A validator that returns seven times in one function
            is doing its job, but a reviewer cannot prove none of the seven became
            unreachable, so it is split.
            """
            body = self._body()
            if body is None:
                return None

            content_type = self.headers.get("Content-Type", "")
            try:
                fields, pdf = parse_multipart(body, content_type)
            except ValueError as exc:
                self._json(*_error(str(exc)))
                return None

            missing = first_missing(fields, pdf)
            if missing is not None:
                self._json(*_error(missing))
                return None
            return pdf, fields

        def do_POST(self) -> None:
            if self.path not in ("/audit", "/letter"):
                self._not_found(self.path, "/audit or /letter")
                return

            upload = self._read_upload()
            if upload is None:
                return
            pdf, fields = upload

            carrier, terminal = fields["carrier"], fields.get("terminal", "")
            # One branch, one runner. The two routes want different things and running
            # both would audit the same PDF twice, which on a one-connection server means
            # every other request waits for work nobody asked for.
            structured = self.path == "/letter"
            try:
                if structured:
                    findings = find_fn(pdf, carrier, terminal)
                    code = findings.code
                else:
                    code, output = run_audit(pdf, carrier, terminal, True)
            except (BindError, KeyError, ValueError, OmittedError) as exc:
                # Every one of these is an answer we can give a person: the document is
                # unreadable, the carrier is one we have no clock rule for, or a
                # required disclosure is absent. A traceback would be the one response
                # this endpoint must never send.
                self._send(
                    400,
                    json.dumps({"error": str(exc), "exit_code": EXIT_ENGINE_ERROR}),
                    "application/json; charset=utf-8",
                )
                return

            if structured:
                self._html(code, result_page(findings))
            else:
                self._send(_http_status(code), output, "application/json; charset=utf-8")

    return Handler


def run_server(
    host: str,
    port: int,
    run_audit: AuditRunner,
    find_fn: FindRunner,
    out: TextIO | None = None,
) -> int:  # pragma: no cover - blocking
    """Serve until interrupted. Refuses a non-loopback host before binding.

    Two runners, because the two routes want different things. ``/audit`` has to
    reproduce the command line exactly, so it gets the text runner that is pinned to
    that by a test. ``/letter`` renders a page, and a page wants the objects, so it
    gets the runner that returns them.
    """
    assert_loopback(host)
    say = out.write if out is not None else print
    httpd = HTTPServer((host, port), build_handler(run_audit, find_fn))
    shown = "localhost" if host in ("127.0.0.1", "localhost") else host
    say(f"Quayline intake on http://{shown}:{httpd.server_address[1]}\n")
    say("Loopback only. Nothing is stored: uploads are read and discarded.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        say("\nstopped\n")
    finally:
        httpd.server_close()
    return EXIT_CLEAN


__all__ = ["MAX_UPLOAD_BYTES", "AuditRunner", "build_handler", "run_server"]
