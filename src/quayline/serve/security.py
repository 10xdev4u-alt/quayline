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

Why a name is resolved rather than passed through

``assert_loopback`` returns a literal address, never a name. Handing a name to the bind
would mean a DNS answer at bind time that can differ from the answer just checked. On a
machine whose ``/etc/hosts`` points ``localhost`` at a routable address, the check would
pass and the server would answer on the network. So the name is resolved once, every
address it resolves to is verified, and the literal is what gets bound.

What it costs to actually host this

Written down so the next person knows the shape of the work rather than assuming it is
one line of config: identity, per-tenant storage, encryption at rest, TLS
termination, request rate limits, an audit trail of access, and a deletion policy that
is actually enforced. Six pieces, none of them small. Issue 191 is deliberately not
that milestone.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable

#: Hosts we will bind, by name. A name is only accepted when it is on this list.
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})

#: Given a name, the addresses it resolves to. Injectable so a test can decide what
#: ``localhost`` means without editing ``/etc/hosts``.
Resolver = Callable[[str], "list[str]"]

#: ``ipaddress.version`` for IPv4. Spelled out because the literal trips the magic value
#: rule and the constant costs nothing.
IPV4 = 4


class BindRefusedError(PermissionError):
    """The requested interface is not loopback, and this tool will not serve on it."""


def _system_resolver(name: str) -> list[str]:
    """What the machine resolves ``name`` to, IPv4 first.

    Ordered IPv4 first because ``HTTPServer`` is an ``AF_INET`` socket. Returning ``::1``
    here would satisfy every security check and then fail the bind with
    ``Address family for hostname not supported``, which is a confusing way to learn that
    the resolver and the socket disagree. Both answers are still verified as loopback.
    """
    infos = socket.getaddrinfo(name, None, type=socket.SOCK_STREAM)
    found = [str(info[4][0]) for info in infos]

    def rank(address: str) -> int:
        return 0 if ipaddress.ip_address(address).version == IPV4 else 1

    return sorted(found, key=rank)


def _bind_literal(host: str) -> str:
    """Return ``host`` if it is a loopback literal this socket can actually bind."""
    address = ipaddress.ip_address(host)
    if not address.is_loopback:
        raise BindRefusedError(
            f"refusing to bind {host!r}: {address} is routable. This intake holds a "
            f"client's container number and a disputed amount and has no "
            f"authentication, so it serves on loopback only."
        )
    if address.version != IPV4:
        raise BindRefusedError(
            f"refusing to bind {host!r}: {address} is loopback, but this server is an "
            f"AF_INET socket and cannot bind an IPv6 address. Pass 127.0.0.1, or a "
            f"loopback name, which resolves to IPv4."
        )
    return host


def assert_loopback(host: str, resolver: Resolver | None = None) -> str:
    """Return a literal loopback address to bind, or refuse.

    Returns an address, never a name, and that is the whole point. Passing a name on to
    the bind reintroduces the DNS answer this function exists to avoid: the answer could
    differ from the one just checked, or point somewhere routable. On a machine whose
    ``/etc/hosts`` maps ``localhost`` at a routable address, a name would be checked as
    loopback and bound somewhere a network can reach.

    So a name is resolved here, every address it resolves to is verified as loopback,
    and the literal is what comes back. The check and the bind cannot disagree.
    """
    candidate = host.strip().lower()
    try:
        return _bind_literal(candidate)
    except ValueError:
        pass  # not a literal, so it may be a name

    if candidate not in _LOOPBACK_NAMES:
        raise BindRefusedError(
            f"refusing to bind {host!r}: it is neither a loopback address nor a "
            f"loopback name ({', '.join(sorted(_LOOPBACK_NAMES))}). This intake "
            f"holds a client's container number and a disputed amount and has no "
            f"authentication, so it serves on loopback only."
        )

    resolved = (resolver or _system_resolver)(candidate)
    if not resolved:
        raise BindRefusedError(
            f"refusing to bind {host!r}: it resolved to no address at all. An unbound "
            f"name cannot be shown to be loopback."
        )

    # Two separate questions. Routable is a security failure and refuses. IPv6 loopback
    # is not, because ``localhost`` legitimately resolves to both 127.0.0.1 and ::1 on
    # most machines and an AF_INET socket can only take the first kind.
    bindable: list[str] = []
    for address in resolved:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as exc:
            raise BindRefusedError(
                f"refusing to bind {host!r}: it resolved to {address!r}, which is not "
                f"an address at all."
            ) from exc
        if not parsed.is_loopback:
            raise BindRefusedError(
                f"refusing to bind {host!r}: it resolved to {parsed}, which is "
                f"routable. This intake holds a client's container number and a "
                f"disputed amount and has no authentication, so it serves on loopback "
                f"only."
            )
        if parsed.version == IPV4:
            bindable.append(address)
    if not bindable:
        raise BindRefusedError(
            f"refusing to bind {host!r}: it resolved to {', '.join(resolved)}, none of "
            f"which is an IPv4 address this AF_INET server can bind. Pass 127.0.0.1."
        )
    return bindable[0]


__all__ = ["BindRefusedError", "Resolver", "assert_loopback"]
