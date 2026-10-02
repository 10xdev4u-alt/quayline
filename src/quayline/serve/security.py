"""Issue 191: what this intake is allowed to do.

One rule, and it is the whole module

**Loopback only.** A dispute letter carries a client's container number, its bill of
lading and a disputed amount. Serving that on an interface a network can reach, with no
authentication, is how a container number ends up on the internet, and it is the kind
of mistake that ends a company rather than the kind that gets a CVE.

There is no flag to widen this. A hosted version of Quayline needs accounts, tenancy,
storage with a retention policy, TLS, rate limiting and an audit log of who saw which
invoice. None of that exists, so the honest shape today is a tool that runs on a machine
you control.

Why no flag at all

A flag would be a setting somebody flips on a deadline and forgets. And the reason
anyone would want to widen it is to demo it from a laptop on hotel wifi, which is
exactly the situation where the port is scanned within minutes. Refusing loudly is
cheaper than the incident.

What it costs to actually host this

Written down so the next person knows the shape of the work rather than assuming it is
one line of config: identity, per-tenant storage, encryption at rest, TLS
termination, request rate limits, an audit trail of access, and a deletion policy that
is actually enforced. Six pieces, none of them small. Issue 191 is deliberately not
that milestone.
"""

from __future__ import annotations

import ipaddress

#: Hosts we will bind. Loopback in both families, plus the two names that resolve to it.
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})


class BindRefusedError(PermissionError):
    """The requested interface is not loopback, and this tool will not serve on it."""


def assert_loopback(host: str) -> str:
    """Return ``host`` if it is loopback, refuse it otherwise.

    Accepts a name or a literal. A name is only accepted when it is one of the known
    loopback names, because resolving it would mean a DNS answer at startup and a DNS
    answer can change between the check and the bind.
    """
    candidate = host.strip().lower()
    if candidate in _LOOPBACK_NAMES:
        return candidate
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise BindRefusedError(
            f"refusing to bind {host!r}: it is neither a loopback address nor a "
            f"loopback name ({', '.join(sorted(_LOOPBACK_NAMES))}). This intake "
            f"holds a client's container number and a disputed amount and has no "
            f"authentication, so it serves on loopback only."
        ) from exc
    if not address.is_loopback:
        raise BindRefusedError(
            f"refusing to bind {host!r}: {address} is routable. This intake holds a "
            f"client's container number and a disputed amount and has no "
            f"authentication, so it serves on loopback only."
        )
    return candidate


__all__ = ["BindRefusedError", "assert_loopback"]
