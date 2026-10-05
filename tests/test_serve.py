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

from conftest import build_pdf
from quayline.cli.audit_cmd import EXIT_ENGINE_ERROR, EXIT_FILE_WORTHY, main
from quayline.cli.audit_render import resolve_disclosed
from quayline.cli.serve_cmd import build_runner, find_runner
from quayline.serve import app as serve_app
from quayline.serve.app import MAX_UPLOAD_BYTES, build_handler
from quayline.serve.pages import letter_page
from quayline.serve.security import BindRefusedError, assert_loopback
from quayline.web.document import script_hash
from test_carrier_layout import MAERSK_COLUMNS

FIXTURE = Path("tests/fixtures/born_digital_invoice.pdf")


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    """A real server on a real port, so the tests exercise the socket not a stub."""
    handler = build_handler(build_runner(), find_runner(resolve_disclosed))
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
    for host in ("127.0.0.1", "localhost", "127.0.1.1", "LOCALHOST"):
        assert ipaddress.ip_address(assert_loopback(host)).version == 4


def test_a_name_binds_as_a_literal_so_the_check_and_the_bind_cannot_disagree() -> None:
    """``assert_loopback`` returns an address, never a name.

    A name handed to the bind is a DNS answer taken a second after the check. On a
    machine whose hosts file points ``localhost`` at a routable address the check passes
    and the server answers on the network, which is the one outcome this module exists
    to prevent. So the name is resolved here and the literal is what comes back.
    """
    for host in ("localhost", "localhost.localdomain", "127.0.0.1"):
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
        httpd = HTTPServer(
            (address, 0), build_handler(build_runner(), find_runner(resolve_disclosed))
        )
        try:
            assert httpd.server_address[0] == address
        finally:
            httpd.server_close()


def test_an_ipv6_literal_is_refused_rather_than_failing_the_bind() -> None:
    """``::1`` is loopback, but this server cannot bind it.

    ``HTTPServer`` is an ``AF_INET`` socket, so accepting ``::1`` passes the security
    check and then dies with ``Address family for hostname not supported``. That reads
    as a security module declining to serve rather than a socket disagreeing with a
    check, and it is a worse error than the one we can give up front.
    """
    with pytest.raises(BindRefusedError) as caught:
        assert_loopback("::1")
    assert "AF_INET" in str(caught.value), "the message should say why"


def test_a_body_that_stops_short_is_refused_not_audited(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A truncated upload has no honest answer, so it is refused.

    ``HTTPServer`` serves one connection at a time, so an unguarded read of a declared
    length is also a denial of service: declare a size, send nothing, hold the server.
    The timeout is cut to a second here rather than the thirty seconds production uses,
    because the behaviour under test is the refusal and not how long a person waits.
    """
    monkeypatch.setattr(serve_app, "_BODY_TIMEOUT", 1.0)
    boundary = f"----q{uuid4().hex}"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="carrier"\r\n\r\nMaersk\r\n'.encode()
        + f"--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        f"{server}/audit",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body) + 4096),
        },
    )
    try:
        urllib.request.urlopen(request, timeout=20)
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read())
        assert "ended" in payload["error"] or "declared" in payload["error"], payload
        assert payload["exit_code"] == EXIT_ENGINE_ERROR
    else:
        raise AssertionError("a short body was accepted as a complete upload")


def test_an_invoice_cannot_inject_markup_into_the_letter_page() -> None:
    """The packet text is invoice-derived, so it is untrusted input.

    The letter page escapes the packet and splices in the strip as real markup. The
    escape has to be the last thing that happens to the text, otherwise angle brackets
    from an invoice come out as tags. This pins that ordering, because an earlier
    version un-escaped entities after escaping them and looked injectable.
    """
    hostile = (
        "Dear carrier, you charged inside free time.\n"
        '<div class="strip">\n<table><tr><td>2026-07-06</td></tr></table>\n</div>\n'
        "<script>alert(1)</script><img src=x onerror=alert(2)>"
    )
    page = letter_page(hostile, EXIT_FILE_WORTHY)
    assert "<script>alert(1)</script>" not in page
    assert "<img src=x onerror=alert(2)>" not in page
    assert "&lt;script&gt;" in page, "it should be present as text, not dropped"
    assert '<div class="strip">' in page, "and the strip is still real markup"


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


def test_the_reference_fixture_places_itself_by_its_rate_rule(server: str) -> None:
    """Issue 220 replaced the test that used to sit here.

    That test asserted a missing carrier is refused before anything is read, on the
    reasoning that 541.6 does not ask a carrier to name itself. The reasoning holds for
    *guessing* and not for *reading*, because 541.6(c)(2) makes the carrier disclose the
    rule it billed under. The fixture names `Maersk US Newark Dry`, so it places itself
    and the upload succeeds with no carrier field at all.

    The refusal is still covered, by `test_an_unidentifiable_carrier_asks_for_the_name`,
    which is the case where the invoice genuinely does not say who it is.
    """
    status, body = post(server, "/letter", {"terminal": "newark"}, FIXTURE.read_bytes())

    assert status == 200, body[:300]
    assert "Maersk" in body


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

    # The page renders the packet as structure rather than as one preformatted blob,
    # so each ground appears as its own section carrying its own stake.
    assert status == 200
    assert 'class="section"' in body
    assert "541.6" in body, "each section names the ground it rests on"
    assert "390.00" in body, "the amount at stake is on the page"
    assert "needs evidence" in body, "a ground that cannot be sent yet says so"


def test_the_letter_carries_the_day_strip_because_it_is_the_strongest_asset(server: str) -> None:
    """A client should see the finding without having to ask for it."""
    _, body = post(
        server,
        "/letter",
        {"carrier": "Maersk", "terminal": "newark"},
        FIXTURE.read_bytes(),
    )

    # The strip is the reason a client should not have to ask for it, and it is now
    # the same day grid every other page uses rather than markup spliced into a blob.
    assert body.count('class="day"') == 11
    assert 'data-state="disputed"' in body
    assert "390.00" in body


def test_the_root_serves_a_form_a_person_can_actually_use(server: str) -> None:
    with urllib.request.urlopen(f"{server}/") as response:
        assert response.status == 200
        text = response.read().decode()

    assert "<form" in text and 'type="file"' in text
    assert 'name="carrier"' in text
    assert 'enctype="multipart/form-data"' in text, "a file field needs it"
    # The page ships one inline script for the drop target, the staged progress and the
    # day grid reveal. It is enhancement: the form above is a real form posting to a real
    # route, so a reader with the script blocked keeps the whole product. What must not
    # be possible is an external script, and the policy test below is what proves it.
    assert text.count("<script") == 1, "exactly one inline script, ours"
    assert "http://" not in text and "https://" not in text.replace("127.0.0.1", "")


def test_the_page_states_it_is_local_and_not_a_hosted_service(server: str) -> None:
    """The whole security position, on the page, where an operator will read it."""
    with urllib.request.urlopen(f"{server}/") as response:
        body = response.read().decode()

    lowered = body.lower()
    assert "localhost" in lowered or "127.0.0.1" in lowered
    assert "nothing is stored" in lowered or "written to disk" in lowered
    # The fixture is labelled as a fixture. An invented client on the hero would be the
    # fastest way to lose the only credibility this project has.
    assert "not a client" in lowered, "the worked example must say it is not a client"
    assert "no recovery rate is claimed" in lowered


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
    # The inline script is pinned by digest rather than waved through with
    # unsafe-inline, so the policy still refuses every other script on the page.
    assert "unsafe-inline" not in page_csp.split("script-src")[1], (
        "script-src must not allow inline generally, only our one digest"
    )
    assert f"script-src '{script_hash()}'" in page_csp, (
        "the digest has to be the one for the script actually served"
    )

    assert json_csp == "default-src 'none'", (
        "a JSON response has no style block and gets the strict policy with no exception"
    )


def test_an_unknown_path_is_a_clean_404_not_a_traceback(server: str) -> None:
    try:
        urllib.request.urlopen(f"{server}/nope")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
        assert "no route" in exc.read().decode()
    else:
        raise AssertionError("expected a 404")


def test_healthz_answers_without_touching_the_engine(server: str) -> None:
    """The container health check, and it must be cheap and total.

    It runs on every poll, so anything that loads the tariff corpus or runs an audit
    makes start-up ordering matter and turns a restart loop into a confusing failure.
    """
    with urllib.request.urlopen(f"{server}/healthz") as response:
        assert response.status == 200
        body = response.read().decode()
    assert json.loads(body)["status"] == "ok"


def test_healthz_needs_no_carrier_and_no_upload(server: str) -> None:
    """It is a GET with no parameters, so a probe needs no knowledge of the product."""
    with urllib.request.urlopen(f"{server}/healthz") as response:
        assert response.status == 200


def test_healthz_says_it_is_json(server: str) -> None:
    """A JSON body labelled text/html is a lie a client cannot check.

    CodeRabbit found this on #211 and it is right. A JSON health client that trusts the
    content type is entitled to reject a `text/html` response, and a probe that fails on
    a healthy service turns into an operator restarting something that is fine.
    """
    with urllib.request.urlopen(f"{server}/healthz") as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "application/json"
        assert json.loads(response.read().decode())["status"] == "ok"


def test_the_pages_stay_html(server: str) -> None:
    """The control, so the fix above did not relabel the pages."""
    with urllib.request.urlopen(f"{server}/") as response:
        assert response.headers.get_content_type() == "text/html"


# --- The carrier is read from the invoice, issue 220 ------------------------


def test_a_reader_can_post_a_carrier_invoice_with_no_carrier_field(server: str) -> None:
    """The whole point, and it is the last thing between a reader and running this.

    Issue 218 made the carrier readable from the disclosed rate rule. Until the form
    used it, a reader still had to type the carrier's exact published name, and a
    near miss raised rather than warned.
    """
    body = _carrier_invoice_pdf()
    code, page = post(f"{server}", "/letter", {}, body)

    assert code != 400, f"the intake refused a carrier invoice: {page[:400]}"
    assert "541.6" in page, "no findings rendered, so nothing was audited"
    assert "Maersk" in page


def test_the_page_says_the_carrier_was_inferred_and_from_which_rule(server: str) -> None:
    """A reader who did not name the carrier needs to see where the answer came from.

    A verdict with no stated basis asks for trust the tool has not earned, and #218
    carries the rule reference on `Identified` for exactly this.
    """
    _, page = post(f"{server}", "/letter", {}, _carrier_invoice_pdf())

    assert "Maersk US Newark Dry" in page, "the page must show the rule the carrier was read from"


def test_the_carrier_field_is_not_required(server: str) -> None:
    """The form itself, so a reader is not stopped before they can try."""
    with urllib.request.urlopen(f"{server}/") as response:
        body = response.read().decode()
    assert 'name="carrier"' in body
    assert 'id="carrier" required' not in body
    assert "required" not in body.split('id="carrier"')[1].split(">")[0]


def test_an_unidentifiable_carrier_asks_for_the_name(server: str) -> None:
    """Not an error page. An extra question, naming the rule we could not place."""
    body = _carrier_invoice_pdf(replace_rule="CMA CGM US Felixstowe Dry")
    code, page = post(f"{server}", "/letter", {}, body)

    assert code == 400
    assert "CMA CGM US Felixstowe Dry" in page, (
        "the message must name the rule, so the reader knows which carrier to say"
    )
    assert "carrier" in page.lower()


def _carrier_invoice_pdf(replace_rule: str = "") -> bytes:
    """A Maersk-shaped column invoice, built the way issue 216's fixture is."""
    if replace_rule:
        lines = tuple(line.replace("Maersk US Newark Dry", replace_rule) for line in MAERSK_COLUMNS)
    else:
        lines = MAERSK_COLUMNS
    return build_pdf(*lines)


def test_the_rail_says_the_carrier_was_read_not_typed(server: str) -> None:
    """The trust point, and the reason #218 carries the rule on `Identified`.

    A reader who did not type a carrier and got a verdict has no way to tell whether the
    tool read the invoice or guessed at it. "read from the rule" is the difference between
    an answer and a claim.
    """
    _, page = post(server, "/letter", {"terminal": "newark"}, FIXTURE.read_bytes())

    assert "read from the rule" in page, (
        "the page must say the carrier came off the document, not from the reader"
    )


def test_a_carrier_the_reader_typed_is_not_labelled_as_read(server: str) -> None:
    """Otherwise the label becomes decoration and stops meaning anything."""
    _, page = post(
        server, "/letter", {"carrier": "Maersk", "terminal": "newark"}, FIXTURE.read_bytes()
    )

    assert "read from the rule" not in page, "the reader named the carrier themselves"


def test_an_unreadable_document_answers_with_a_page_not_a_refusal(server: str) -> None:
    """Issue 222. A reader who gave us a document gets a document back.

    A refusal is honest and useless. This page lists what we read, marks the twenty
    disclosures for the reader to check, and hands them a letter. The status is **200** on
    purpose: it is a successful answer to a request, not a failed one.
    """
    body = build_pdf(
        "FORWARDER STATEMENT OF ACCOUNT",
        "Reference 4471-B",
        "Settlement of charges for the month of August.",
    )
    status, page = post(server, "/letter", {}, body)

    assert status == 200, f"an unreadable document should still answer, got {status}"
    assert "FORWARDER STATEMENT OF ACCOUNT" in page, "we read the text, so show it"
    assert "541.6(c)(2)" in page, "every clause must be listed for the reader to check"
    assert "<textarea" in page, "the letter must be selectable with no script"


def test_the_unreadable_page_never_says_the_carrier_withheld_anything(server: str) -> None:
    """Issue 214's bug, in a different medium.

    We could not read the document. So we may not allege anything about the carrier, and
    541.5 makes an allegation automatic rather than arguable.
    """
    body = build_pdf("FORWARDER STATEMENT OF ACCOUNT", "Reference 4471-B")
    _, page = post(server, "/letter", {}, body)

    lowered = page.lower()
    for word in ("withheld", "failed to disclose", "did not disclose", "breach"):
        assert word not in lowered, f"the page says {word!r} about a carrier we could not read"


def test_the_page_shows_the_disagreement_above_the_verdict(server: str) -> None:
    """Above, not in the rail.

    A rail row is something a reader scans. This is something they have to act on before
    filing, because a wrong day basis produces a wrong number.
    """

    # The invoice names a rule we hold, so detection can answer. The reader typed a
    # different carrier, which is the disagreement.
    body = build_pdf(*MAERSK_COLUMNS)

    status, page = post(server, "/letter", {"carrier": "Hapag-Lloyd", "terminal": "newark"}, body)

    assert status == 200, page[:300]
    assert "Check the carrier" in page
    assert "Maersk US Newark Dry" in page
    # Match the element, not the word. `page.index("verdict")` finds `.verdict` in the
    # stylesheet, which is at the top of the document, so the first version of this test
    # asserted against the CSS and would have passed whatever the page did.
    header = '<header class="verdict">'
    assert page.index("Check the carrier") < page.index(header), (
        "the warning must come before the verdict header, not after it"
    )
