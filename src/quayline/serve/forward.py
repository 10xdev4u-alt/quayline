"""Forward a published port to the loopback-only intake, and nothing else.

Issue 208. Why this exists
--------------------------

`quayline serve` binds to loopback and refuses any other address, on purpose. It holds
a container number and a disputed amount and has no authentication, so the bind is a
security property rather than a default.

That property is incompatible with Docker's published ports. Docker's proxy connects
to the container's own IP, 172.x.x.x, not to its loopback interface, so a process
bound to 127.0.0.1 inside a container is unreachable from the host no matter what
`-p` says. The symptom is an empty reply rather than a connection refused, because the
port is open and then closed.

The usual answers are all worse than the problem. `network_mode: host` gives up the
container's network isolation and does not exist on Docker Desktop. Widening the bind
throws away the guarantee. Adding socat to the image is a dependency for fifteen lines
of work.

So the image runs this, and the intake stays on loopback. The forwarding is explicit,
it is one process, it is in the compose file where a reader can see it, and the
alternative to running it is not reaching the container at all.

What it does
------------

Accepts a connection and pipes it to 127.0.0.1 on an internal port. No TLS, no
authentication, no request inspection, no logging of bodies. It is a pipe.

Put an authenticating reverse proxy in front of this before exposing it to a network.
`docs/SELFHOST.md` says so and gives a working configuration.
"""

from __future__ import annotations

import socket
import socketserver
import sys
import threading

__all__ = ["forward", "main"]

#: Read and write chunk size. Large enough that a few hundred reads move an 8 MiB
#: upload, small enough that neither side holds a whole request in memory.
CHUNK = 64 * 1024

#: How long to wait for the outbound thread once the inbound side has finished. It is
#: a daemon thread and would not hold the process open; this only avoids leaking it.
_PIPE_JOIN_TIMEOUT = 5.0


class _ForwardHandler(socketserver.BaseRequestHandler):
    """Pipe one connection to the loopback intake and close both ends."""

    def handle(self) -> None:
        upstream = socket.create_connection((self.server.upstream, self.server.internal))  # type: ignore[attr-defined]
        # Both directions at once, each on its own thread.
        #
        # The first version piped the client to the intake and then the intake back to
        # the client, sequentially. That deadlocks on the first request that keeps its
        # connection open, which is every HTTP/1.1 request: the client sends a body,
        # waits for a response, and does not half-close, so the first pipe waits for an
        # EOF that only comes after the response it is blocking. The suite hung and the
        # container returned an empty reply.
        down = threading.Thread(target=self._pipe, args=(self.request, upstream), daemon=True)
        down.start()
        try:
            self._pipe(upstream, self.request)
        finally:
            down.join(timeout=_PIPE_JOIN_TIMEOUT)
            upstream.close()

    def _pipe(self, source: socket.socket, sink: socket.socket) -> None:
        try:
            while chunk := source.recv(CHUNK):
                sink.sendall(chunk)
        except OSError:
            # The peer went away mid transfer, which is what a browser tab closing
            # looks like from here. Not an error worth a traceback in a health log.
            pass


class _ForwardServer(socketserver.ThreadingTCPServer):
    """A threading server that knows where the intake is listening."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], upstream: str, internal: int) -> None:
        super().__init__(address, _ForwardHandler)
        self.upstream = upstream
        self.internal = internal


def forward(
    listen_port: int,
    internal_port: int,
    host: str = "0.0.0.0",
    ready: threading.Event | None = None,
) -> int:
    """Serve until interrupted. Returns a process exit code.

    ``ready`` is set once the socket is listening, and is what makes this testable.

    The first version bound, started a thread and joined it unconditionally, which
    served correctly and could not be stopped. A caller that cannot shut a listener
    down leaves the port bound for the life of the process, so the test fixture could
    not release it and the suite hung rather than failing. Joining forever is the
    right behaviour for a foreground process and the wrong shape for a library.
    """
    server = _ForwardServer((host, listen_port), "127.0.0.1", internal_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if ready is not None:
        ready.set()
    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


#: Exit code for a usage error, matching the rest of the command line surface.
EXIT_USAGE = 2

_USAGE = "usage: forward <listen-port> [internal-port]"

#: Accepted argument counts. One port means both ends use it, two means they differ.
_ONE_PORT = 1
_BOTH_PORTS = 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (_ONE_PORT, _BOTH_PORTS):
        print(_USAGE, file=sys.stderr)
        return EXIT_USAGE
    try:
        listen = int(args[0])
        internal = int(args[1]) if len(args) == _BOTH_PORTS else listen
    except ValueError:
        print(_USAGE, file=sys.stderr)
        return EXIT_USAGE
    return forward(listen, internal)


if __name__ == "__main__":
    raise SystemExit(main())
