"""Issue 208: the loopback forwarder, tested because pipes are easy to get wrong.

`quayline serve` binds to loopback and refuses anything else, which is a security
property rather than a default. Docker's published ports cannot reach a loopback
process inside a container, because Docker's proxy connects to the container's own IP.
So the container runs this to bridge the two, and the intake keeps its guarantee.

These tests use a real socket on a real port. A mocked pipe tests the mock.
"""

from __future__ import annotations

import http.client
import socket
import threading
import urllib.request
from collections.abc import Iterator
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from quayline.cli.audit_render import resolve_disclosed
from quayline.cli.serve_cmd import build_runner, find_runner
from quayline.serve.app import build_handler
from quayline.serve.forward import forward


@pytest.fixture
def upstream() -> Iterator[int]:
    """A real intake on a real loopback port."""
    handler = build_handler(build_runner(), find_runner(resolve_disclosed))
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def bridged(upstream: int) -> Iterator[int]:
    """The forwarder in front of it, on its own loopback port.

    Waits on ``ready`` rather than sleeping. A fixed sleep is a race that passes on a
    fast machine and hangs on a loaded one, which is the worst kind of test flake.
    """
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    listen = probe.getsockname()[1]
    probe.close()

    ready = threading.Event()
    thread = threading.Thread(
        target=forward,
        args=(listen, upstream),
        kwargs={"host": "127.0.0.1", "ready": ready},
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=10), "the forwarder never started listening"
    try:
        yield listen
    finally:
        # `forward` owns its own socket and stops on KeyboardInterrupt, which a test
        # cannot send it, so the listening thread is a daemon and the run releases the
        # port when the process exits. Nothing to clean up here that is worth a
        # fixture that lies about doing it.
        pass


def test_the_forwarder_carries_a_request_to_the_intake(bridged: int) -> None:
    with urllib.request.urlopen(f"http://127.0.0.1:{bridged}/healthz") as response:
        assert response.status == 200
        assert b'"ok"' in response.read()


def test_the_health_check_reaches_through_the_forwarder(bridged: int) -> None:
    """The container health check runs through the same path a reader does.

    If the bridge carried health checks but not real requests, the container would
    report healthy while every audit failed.
    """
    with urllib.request.urlopen(f"http://127.0.0.1:{bridged}/") as response:
        assert response.status == 200
        assert b"<form" in response.read()


def test_a_forwarded_body_arrives_byte_for_byte() -> None:
    """CodeRabbit found that the first version of this could not fail.

    It posted `application/octet-stream`, which `_body()` rejects before reading a
    byte, and then accepted any error status as proof the pipe worked. A forwarder that
    truncated every upload to zero bytes would have passed it.

    So the assertion is on the bytes that arrived, checked by an upstream that counts
    them, rather than on a status code that a rejection also produces.
    """
    received: list[bytes] = []

    class CountingHandler(BaseHTTPRequestHandler):
        """Reads with a deadline rather than trusting Content-Length.

        A forwarder that drops bytes leaves the upstream blocked in
        `rfile.read(length)` until the client gives up, so a plain read turns a
        truncation bug into a 30 second timeout rather than a legible failure. Setting
        a short deadline makes the test fail in about a second with the count it got.
        """

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.connection.settimeout(5)
            body = b""
            with suppress(TimeoutError, OSError):
                body = self.rfile.read(length)
            received.append(body)
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args: object) -> None:
            """Silence. The test asserts on bytes, not on stderr."""

    upstream_port = _free_port()
    server = HTTPServer(("127.0.0.1", upstream_port), CountingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    listen = _free_port()
    ready = threading.Event()
    threading.Thread(
        target=forward,
        args=(listen, upstream_port),
        kwargs={"host": "127.0.0.1", "ready": ready},
        daemon=True,
    ).start()
    assert ready.wait(timeout=10)

    body = bytes(range(256)) * 8192  # 2 MiB, every byte value, not one repeated byte
    connection = http.client.HTTPConnection("127.0.0.1", listen, timeout=30)
    connection.request(
        "POST",
        "/whatever",
        body=body,
        headers={"Content-Type": "application/octet-stream", "Content-Length": str(len(body))},
    )
    response = connection.getresponse()
    response.read()
    connection.close()

    assert received, "the upstream never received a request"
    assert received[0] == body, (
        f"the forwarder delivered {len(received[0])} bytes of {len(body)}, or the wrong ones"
    )
    server.shutdown()
    server.server_close()


def _free_port() -> int:
    """Bind and release, so the port is very likely free for the next bind."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port: int = probe.getsockname()[1]
    probe.close()
    return port
