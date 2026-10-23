"""A guard that fails a test when anything tries to leave the machine.

`no_outbound()` patches the socket layer: every connect, connect_ex,
create_connection, sendto and name lookup that is not loopback or a local
(AF_UNIX) socket is recorded and refused with `OutboundBlocked`. A test runs
the flow under it and asserts `guard.attempts == []`: a refused attempt the
code under test swallowed is still recorded, so "nothing leaves the machine"
is asserted, not inferred from a quiet run.

Loopback stays open: the Control Center and its test servers listen there,
and a signer socket is local by construction.
"""

from __future__ import annotations

import contextlib
import ipaddress
import socket


class OutboundBlocked(OSError):
    """A connection or lookup that would have left the machine."""


def _local_host(host) -> bool:
    if host is None:
        return True
    if type(host) is bytes:
        host = host.decode("ascii", "replace")
    if host in ("", "localhost") or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _local_address(family, address) -> bool:
    if family not in (socket.AF_INET, socket.AF_INET6):
        return True  # AF_UNIX and the like never leave the machine.
    host = address[0] if type(address) is tuple and address else address
    return _local_host(host)


class Guard:
    def __init__(self):
        self.attempts = []

    def refuse(self, kind, target):
        self.attempts.append((kind, repr(target)))
        raise OutboundBlocked(f"outbound {kind} blocked: {target!r}")


@contextlib.contextmanager
def no_outbound(monkeypatch):
    """Refuse and record every non-local connection for the block's length."""
    guard = Guard()
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex
    sendto = socket.socket.sendto
    getaddrinfo = socket.getaddrinfo
    create_connection = socket.create_connection

    def guarded_connect(self, address):
        if not _local_address(self.family, address):
            guard.refuse("connect", address)
        return connect(self, address)

    def guarded_connect_ex(self, address):
        if not _local_address(self.family, address):
            guard.refuse("connect", address)
        return connect_ex(self, address)

    def guarded_sendto(self, data, *rest):
        address = rest[-1]
        if not _local_address(self.family, address):
            guard.refuse("sendto", address)
        return sendto(self, data, *rest)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _local_host(host):
            guard.refuse("lookup", host)
        return getaddrinfo(host, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        if not _local_host(address[0]):
            guard.refuse("connect", address)
        return create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    try:
        yield guard
    finally:
        monkeypatch.setattr(socket.socket, "connect", connect)
        monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
        monkeypatch.setattr(socket.socket, "sendto", sendto)
        monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
        monkeypatch.setattr(socket, "create_connection", create_connection)
