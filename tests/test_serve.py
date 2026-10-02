"""Issue 191: a real intake, so a client is not emailing us a PDF to run a CLI.

The whole reason this exists. Today the journey is a client emails a PDF, someone runs
`quayline audit` by hand, and pastes the letter into an email. This is the missing
piece.

The security position is part of the design, not a footnote

Local only. Loopback bind, no accounts, nothing on disk, no request logging. A dispute
letter carries a client's container number and a disputed amount, and a hosted version
of this with no authentication is the kind of thing that ends a company. That is stated
in the issue and repeated in the module docstring and on the startup line.
"""

from __future__ import annotations

import io
import ipaddress
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import redirect_stdout
from http.server import HTTPServer
from pathlib import Path
from uuid import uuid4

import pytest

from quayline.cli.audit_cmd import EXIT_ENGINE_ERROR, EXIT_FILE_WORTHY, main
from quayline.cli.serve_cmd import build_runner
from quayline.serve.app import MAX_UPLOAD_BYTES, build_handler
from quayline.serve.pages import FORM_PAGE
from quayline.serve.security import BindRefusedError, assert_loopback

FIXTURE = Path("tests/fixtures/born_digital_invoice.pdf")


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """A real server on a real port, so the tests exercise the socket not a stub."""
    handler = build_handler(build_runner())
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def post(url: str, path: str, fields: dict[str, str], pdf: bytes) -> tuple[int, str]:
    """A multipart POST built with the stdlib, which is what the server parses."""
    boundary = f"----q{uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="pdf"; '
        f'filename="invoice.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
    )
    parts.append(pdf + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"{url}{path}",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


# ------------------------------------------------------------------- the security


def test_it_refuses_any_bind_that_is_not_loopback() -> None:
    """A dispute letter carries a container number and a disputed amount.

    Loopback only, by default, with no flag to widen it. A hosted version needs
    accounts, tenancy, storage and TLS, and pretending otherwise is how a container
    number ends up on the internet.
    """
    with pytest.raises(BindRefusedError):
        assert_loopback("0.0.0.0")
    with pytest.raises(BindRefusedError):
        assert_loopback("192.168.1.10")


def test_loopback_is_accepted_in_every_form_it_takes() -> None:
    """IPv4 and IPv6 loopback, and the two spellings of the v4 one."""
    for host in ("127.0.0.1", "localhost", "::1", "127.0.1.1"):
        assert ipaddress.ip_address(assert_loopback(host))


def test_a_name_binds_as_a_literal_so_the_check_and_the_bind_cannot_disagree() -> None:
    """``assert_loopback`` returns an address, never a name.

    A name handed to the bind is a DNS answer taken a second after the check. On a
    machine whose hosts file points ``localhost`` at a routable address the check passes
    and the server answers on the network, which is the one outcome this module exists
    to prevent. So the name is resolved here and the literal is what comes back.
    """
    for host in ("localhost", "127.0.0.1", "::1", "127.0.1.1"):
        bound = assert_loopback(host)
        assert ipaddress.ip_address(bound), f"{host!r} bound as a name, not an address"


def test_a_name_that_resolves_off_loopback_is_refused() -> None:
    """The gap that review caught: a name whose answer is routable must not bind.

    ``/etc/hosts`` cannot be edited from a test, so the resolver is injected. Without
    this there is no way to prove the check holds for the answer the machine would
    actually give, which is the only answer that matters.
    """

    def to_a_routable_address(_name: str) -> list[str]:
        return ["192.168.1.10"]

    with pytest.raises(BindRefusedError) as caught:
        assert_loopback("localhost", resolver=to_a_routable_address)
    assert "192.168.1.10" in str(caught.value), "the answer should be named"


def test_a_name_that_resolves_to_nothing_is_refused() -> None:
    def to_nothing(_name: str) -> list[str]:
        return []

    with pytest.raises(BindRefusedError):
        assert_loopback("localhost", resolver=to_nothing)


def test_a_name_resolving_to_both_families_binds_the_first_loopback() -> None:
    def to_both_families(_name: str) -> list[str]:
        return ["127.0.0.1", "::1"]

    assert assert_loopback("localhost", resolver=to_both_families) == "127.0.0.1"


def test_a_resolved_name_binds_on_a_real_socket() -> None:
    """The name has to resolve to something ``HTTPServer`` can actually bind.

    ``HTTPServer`` is an ``AF_INET`` socket. A resolver that handed back ``::1`` first
    would pass every security check and then fail the bind with ``Address family for
    hostname not supported``. That is how this was briefly broken, and it looks like a
    security module refusing to serve rather than a resolver disagreeing with a socket.
    """
    for host in ("localhost", "localhost.localdomain", "127.0.0.1"):
        address = assert_loopback(host)
        httpd = HTTPServer((address, 0), build_handler(build_runner()))
        try:
            assert httpd.server_address[0] == address
        finally:
            httpd.server_close()


def test_a_refused_bind_names_the_host_it_refused() -> None:
    with pytest.raises(BindRefusedError) as caught:
        assert_loopback("10.0.0.5")
    assert "10.0.0.5" in str(caught.value)


# ------------------------------------------------------------------- the endpoint


def test_a_real_pdf_audits_over_http_and_returns_the_same_numbers(server: str) -> None:
    status, body = post(
        server,
        "/audit",
        {"carrier": "Maersk", "terminal": "newark"},
        FIXTURE.read_bytes(),
    )
    payload = json.loads(body)

    assert status == 200
    assert payload["carrier"] == "Maersk"
    assert payload["demanded_total"] == "1170.00"
    assert payload["recomputed_total"] == "780.00"
    assert payload["variance"] == "390.00"


def test_the_endpoint_agrees_with_the_cli_byte_for_byte(server: str) -> None:
    """The point of the issue. Two paths, one engine, no drift.

    ``quayline audit ... --json`` and ``POST /audit`` must return the same document.
    A second implementation of anything here would be a second chance to be wrong on a
    client's number.
    """
    _, body = post(
        server, "/audit", {"carrier": "Maersk", "terminal": "newark"}, FIXTURE.read_bytes()
    )

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(
            [
                "audit",
                str(FIXTURE),
                "--carrier",
                "Maersk",
                "--terminal",
                "newark",
                "--json",
            ]
        )

    from_http = json.loads(body)
    from_cli = json.loads(buffer.getvalue())

    # The endpoint adds ``exit_code`` so a pipeline can read the CLI contract off a
    # JSON body. Everything else must be identical, field for field.
    assert from_http.pop("exit_code") == EXIT_FILE_WORTHY
    assert from_http == from_cli


def test_the_exit_code_contract_carries_over(server: str) -> None:
    """0, 1, 2, so a pipeline built on the CLI works against the endpoint.

    The code travels in the body rather than as the HTTP status, because ``2`` is not
    an HTTP status and sending it produced ``HTTP/1.0 2`` the first time.
    """
    status, raw = post(
        server, "/audit", {"carrier": "Maersk", "terminal": "newark"}, FIXTURE.read_bytes()
    )

    assert status == 200
    assert json.loads(raw)["exit_code"] == EXIT_FILE_WORTHY == 1


def test_an_engine_failure_is_two_and_says_why(server: str) -> None:
    status, body = post(
        server,
        "/audit",
        {"carrier": "not-a-carrier", "terminal": "newark"},
        FIXTURE.read_bytes(),
    )
    payload = json.loads(body)

    # The exit code travels in the body, because the header carries an HTTP status.
    assert status == 400, "an engine error is a bad request, not a 2"
    assert payload["exit_code"] == EXIT_ENGINE_ERROR == 2
    assert payload["error"]


def test_a_missing_carrier_is_refused_with_a_message(server: str) -> None:
    status, body = post(server, "/audit", {"terminal": "newark"}, FIXTURE.read_bytes())

    assert status == 400
    assert "carrier" in json.loads(body)["error"].lower()


def test_a_missing_file_is_refused(server: str) -> None:
    status, body = post(server, "/audit", {"carrier": "Maersk"}, b"")
    payload = json.loads(body)

    assert status == 400
    assert "pdf" in payload["error"].lower()


def test_an_oversized_upload_is_refused_and_the_limit_is_stated(server: str) -> None:
    """The limit has to be in the message, or an operator guesses at it."""
    # A declared length over the limit, with a small body behind it, so the server
    # refuses on the header and we assert on the message without moving eight megabytes
    # through a test socket. The oversize path is about the Content-Length check, and
    # that is what this exercises.
    request = urllib.request.Request(
        f"{server}/audit",
        data=b"%PDF-1.4\nsmall",
        headers={
            "Content-Type": "multipart/form-data; boundary=----q",
            "Content-Length": str(MAX_UPLOAD_BYTES + 1),
        },
    )
    try:
        urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode())
        assert exc.code == 400
        assert str(MAX_UPLOAD_BYTES) in payload["error"]
        assert payload["exit_code"] == EXIT_ENGINE_ERROR
    else:
        raise AssertionError("expected the oversize upload to be refused")


def test_a_file_that_is_not_a_pdf_is_refused_before_the_engine_runs(server: str) -> None:
    status, body = post(server, "/audit", {"carrier": "Maersk"}, b"just some text")

    assert status == 400
    assert "%PDF" in json.loads(body)["error"]


# ---------------------------------------------------------------------- delivery


def test_the_letter_endpoint_returns_the_rendered_packet(server: str) -> None:
    status, body = post(
        server,
        "/letter",
        {"carrier": "Maersk", "terminal": "newark"},
        FIXTURE.read_bytes(),
    )

    assert status == 200
    assert "Automatic claims" in body
    assert "Amount at stake: 390.00" in body


def test_the_letter_carries_the_day_strip_because_it_is_the_strongest_asset(server: str) -> None:
    """A client should see the finding without having to ask for it."""
    _, body = post(
        server,
        "/letter",
        {"carrier": "Maersk", "terminal": "newark"},
        FIXTURE.read_bytes(),
    )

    # The letter is HTML-wrapped, and the strip is the reason a client should not
    # have to ask for it.
    assert "day by day" in body or "Day by day" in body
    assert "Amount at stake: 390.00" in body


def test_the_root_serves_a_form_a_person_can_actually_use(server: str) -> None:
    with urllib.request.urlopen(f"{server}/") as response:
        assert response.status == 200
        text = response.read().decode()

    assert "<form" in text and 'type="file"' in text
    assert 'name="carrier"' in text
    assert 'enctype="multipart/form-data"' in text, "a file field needs it"
    assert "<script" not in text.lower(), "a form does not need JavaScript to work"


def test_the_page_states_it_is_local_and_not_a_hosted_service(server: str) -> None:
    """The whole security position, on the page, where an operator will read it."""
    with urllib.request.urlopen(f"{server}/") as response:
        body = response.read().decode()

    assert "localhost" in body.lower() or "127.0.0.1" in body.lower()
    assert "nothing is stored" in body.lower() or "not stored" in body.lower()


def test_the_policy_does_not_block_the_page_from_rendering(server: str) -> None:
    """A header that is strict enough to be wrong is worse than no header.

    This shipped broken once. The policy was ``default-src 'none'; style-src
    'unsafe-inline'`` and the pages are self contained HTML with an inline
    ``<style>`` block. The browser obeyed the header and served an unstyled form, so
    the product looked broken while every test still passed, because nothing asserted
    the page could style itself.

    The rule the header has to keep: pages may style themselves, nothing else may load.
    """
    with urllib.request.urlopen(f"{server}/") as response:
        page_csp = response.headers["Content-Security-Policy"]
    try:
        urllib.request.urlopen(f"{server}/nope")
    except urllib.error.HTTPError as exc:
        json_csp = exc.headers["Content-Security-Policy"]
    else:
        raise AssertionError("expected a 404")

    assert "style-src 'unsafe-inline'" in page_csp, (
        "the page carries its own inline style block, so the policy must permit it or "
        "the form renders unstyled"
    )
    assert "default-src 'none'" in page_csp, "and still nothing may be fetched"

    assert json_csp == "default-src 'none'", (
        "a JSON response has no style block and gets the strict policy with no exception"
    )


def test_the_stylesheet_is_valid_css_and_not_escaped_braces() -> None:
    """The form rendered unstyled for a second reason, after the header was fixed.

    ``FORM_PAGE`` carried f-string escapes, so the served CSS was ``:root {{ --ink:... }}``.
    A doubled brace is not valid CSS, and a browser discards the whole stylesheet when
    one declaration is malformed. So the page came back unstyled: serif heading, white
    background, every field on one row.

    Asserting that the body contains a ``<style>`` tag is not enough. It did, the whole
    time. This checks the rule bodies are singly braced, because that is the property
    that actually decides whether the page looks designed or looks like a default form.
    """
    css = FORM_PAGE.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "{{" not in css and "}}" not in css, (
        "doubled braces are f-string escapes that leaked into a plain string, which is "
        "invalid CSS and makes the browser drop the whole stylesheet"
    )
    assert css.count("{") == css.count("}"), "unbalanced rule bodies"
    assert ":root" in css and "--ink" in css, "the variables the page reads are declared"


def test_an_unknown_path_is_a_clean_404_not_a_traceback(server: str) -> None:
    try:
        urllib.request.urlopen(f"{server}/nope")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
        assert "no route" in exc.read().decode()
    else:
        raise AssertionError("expected a 404")
