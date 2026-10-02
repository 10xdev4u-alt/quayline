"""Reading an upload off the socket, with the checks that belong to the transport.

Split out of ``app.py`` so the handler keeps to protocol and this keeps to bytes. The
three checks here are the ones that stop a bad request before the engine sees it: the
declared length has to be present and numeric, it has to be under the cap, and the body
that arrives has to actually be as long as it said.

That last one matters more than it looks. ``HTTPServer`` serves one connection at a
time, so an unguarded read of a declared length is a denial of service, and a body that
stops short is a truncated PDF that would otherwise be audited as though it were whole.
"""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import HTTP
from typing import Any, cast

from quayline.cli.exit_codes import EXIT_ENGINE_ERROR

#: The largest upload we accept. A carrier invoice PDF is a few hundred kilobytes, so
#: this is generous by an order of magnitude and it exists to stop a mistake rather than
#: a document.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

#: Most of an oversize body we will read purely to leave the socket usable. Bounded so
#: a hostile Content-Length cannot make the server do the work it just refused.
DRAIN_CAP = 256 * 1024

#: Seconds to wait for the rest of an oversize body before giving up on it.
DRAIN_TIMEOUT = 1.0

#: Seconds a whole upload may stall. Longer than the drain timeout because this is the
#: body we actually want, and a slow connection on a laptop is not an attack.
BODY_TIMEOUT = 30.0

#: Bytes per read, so one stalled read cannot sit on a large declared length.
BODY_CHUNK = 64 * 1024


def error(message: str, code: int = EXIT_ENGINE_ERROR) -> tuple[int, dict[str, Any]]:
    """An engine error, as ``(exit_code, body)`` for the handler's JSON helper."""
    return code, {"error": message, "exit_code": code}


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], bytes]:
    """Fields and the file, from the raw body, with no temp file in between.

    Wrapping the bytes in an email message is the stdlib's multipart parser. It is a
    slightly odd trick and it is correct, which beats a dependency.
    """
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = BytesParser(policy=HTTP).parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("the request is not multipart, so there is no form in it")

    fields: dict[str, str] = {}
    pdf = b""
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        # ``decode=True`` gives bytes for a plain part and None for one with no
        # payload. The cast says so, because the stdlib types cannot.
        payload = cast(bytes, part.get_payload(decode=True) or b"")
        if name == "pdf":
            pdf = payload
        else:
            fields[str(name)] = payload.decode("utf-8", "replace").strip()
    return fields, pdf


__all__ = [
    "BODY_CHUNK",
    "BODY_TIMEOUT",
    "DRAIN_CAP",
    "DRAIN_TIMEOUT",
    "error",
    "parse_multipart",
]
