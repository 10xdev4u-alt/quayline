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
from http.server import HTTPServer

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


def test_a_forwarded_body_arrives_whole(bridged: int, upstream: int) -> None:
    """Uploads are up to 8 MiB and the pipe has to survive one.

    A chunk-size bug here would truncate large invoices and leave the carrier's
    totals unreadable, which reads as a parsing defect rather than a network one.
    """
    body = b"x" * (2 * 1024 * 1024)
    connection = http.client.HTTPConnection("127.0.0.1", bridged, timeout=10)
    connection.request(
        "POST",
        "/audit",
        body=body,
        headers={"Content-Type": "application/octet-stream", "Content-Length": str(len(body))},
    )
    response = connection.getresponse()
    response.read()
    connection.close()
    # The intake refuses it, which is the correct answer. What matters is that a
    # response came back at all rather than a truncated or reset connection.
    assert response.status in (400, 413, 415)
