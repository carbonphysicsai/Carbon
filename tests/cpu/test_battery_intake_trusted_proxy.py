"""PLT-15: explicit proxy identity, public guards and mandatory request binding.

Only synthetic fixed snapshots, throwaway loopback listeners and test keys;
no tunnel, operator deployment, real chain or credential is used.
"""

import json
import socket
import threading
import time
from contextlib import contextmanager

import pytest
from test_battery_intake import (
    DIGEST,
    MINER,
    OTHER,
    STRATEGY,
    backend,  # noqa: F401 - fixture registered for request.getfixturevalue
    build,
    facts,
    post,
    refs,  # noqa: F401 - fixture registered for request.getfixturevalue
    signed,
)

from carbon.battery import intake as ib
from carbon.battery import intake_client as ic
from scripts.dev.battery_validator_service import service as svc

HEADER = "CF-Connecting-IP"
RECORD = "OWNER-FIXTURE-INTAKE-EXPOSURE-99"


@pytest.fixture
def deployed(tmp_path, request):
    return build(
        tmp_path, request.getfixturevalue("refs"), request.getfixturevalue("backend")
    )


def proxy_config(**updates):
    return {
        "host": "127.0.0.1",
        "port": 0,
        "exposure": {"via": "trusted_proxy", "header": HEADER, "record": RECORD},
        **updates,
    }


def authority(tmp_path):
    agent = tmp_path / ".agent"
    agent.mkdir()
    (agent / "DECISIONS.md").write_text(
        f"## Non-production fixture — {RECORD}: synthetic test only\n", encoding="utf-8"
    )
    return tmp_path


def test_proxy_exposure_requires_a_record_carrier_and_commitment(tmp_path):
    repo = authority(tmp_path)
    config = proxy_config()
    ib.require_exposure(config, repository=repo)
    assert ib.publicly_exposed(config)
    ib.require_isolation(config, {"backend": "carrier", "require_commitment": True})
    for change, code in (
        (
            {"backend": "direct", "require_commitment": True},
            "intake_exposure_needs_carrier",
        ),
        (
            {"backend": "carrier", "require_commitment": False},
            "intake_exposure_needs_commitment",
        ),
    ):
        with pytest.raises(ib.IntakeUnavailable, match=f"^{code}$"):
            ib.require_isolation(config, change)
    with pytest.raises(
        ib.IntakeUnavailable, match="^intake_exposure_needs_commitment$"
    ):
        ib.require_isolation(
            {"host": "0.0.0.0"}, {"backend": "carrier", "require_commitment": False}
        )
    ib.require_isolation(
        {"host": "127.0.0.1"}, {"backend": "direct", "require_commitment": False}
    )
    for record in (None, "OWNER-OTHER-01", "OWNER-INTAKE-EXPOSURE-98"):
        bad = proxy_config(
            exposure={"via": "trusted_proxy", "header": HEADER, "record": record}
        )
        with pytest.raises(ib.IntakeUnavailable, match="^intake_exposure_unrecorded$"):
            ib.require_exposure(bad, repository=repo)
    for host in ("0.0.0.0", "192.0.2.1", "::"):
        with pytest.raises(ib.IntakeUnavailable, match="^intake_proxy_needs_loopback$"):
            ib.require_exposure(proxy_config(host=host), repository=repo)


@pytest.mark.parametrize(
    "exposure",
    [
        {},
        [],
        True,
        {"via": "cloudflare_tunnel", "header": HEADER, "record": RECORD},
        {"via": "trusted_proxy", "header": "", "record": RECORD},
        {"via": "trusted_proxy", "header": "Bad:Header", "record": RECORD},
        {"via": "trusted_proxy", "header": "x\r\ny", "record": RECORD},
        {"via": "trusted_proxy", "header": HEADER, "record": RECORD, "fallback": True},
    ],
)
def test_proxy_configuration_is_closed(exposure):
    with pytest.raises(ib.IntakeUnavailable, match="^intake_config_exposure$"):
        ib.proxy_header(proxy_config(exposure=exposure))


def test_proxy_mode_loads_only_from_owner_configuration(tmp_path):
    repo = authority(tmp_path)
    config = {
        **proxy_config(port=8467),
        "schema": ib.SCHEMA,
        "deployment": "fixture-deployment.json",
        "transport_journal": "fixture-transport.sqlite3",
        "inbox": "fixture-inbox.sqlite3",
        "receiver": "fixture-public-receiver",
    }
    path = tmp_path / "intake.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    loaded = ib.load_config(path, repository=repo)
    assert ib.proxy_header(loaded) == HEADER
    with pytest.raises(ib.IntakeUnavailable, match="^intake_config_exposure$"):
        ib.proxy_header({**config, "exposure_record": "OWNER-INTAKE-EXPOSURE-98"})


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "not-an-ip",
        "192.0.2.1:443",
        "192.0.2.1, 198.51.100.1",
        "[::1]",
        "fe80::1%lo",
        " 192.0.2.1",
        "192.0.2.1 ",
        "1" * 1000,
    ],
)
def test_invalid_proxy_header_never_reaches_the_route(deployed, value, monkeypatch):
    intake, _ = deployed
    intake.proxy_header = HEADER

    def never(*args):
        raise AssertionError("invalid proxy identity reached a route")

    monkeypatch.setattr(intake, "route", never)
    headers = {} if value is None else {HEADER: value}
    answer = intake.handle("GET", ib.INFO_PATH, headers, b"", "127.0.0.1")
    assert (answer.status, answer.body) == (400, {"refused": "peer_header_invalid"})
    assert intake.limits._buckets == {}


def test_only_the_explicit_proxy_and_single_header_can_supply_identity():
    headers = {HEADER: "192.0.2.1"}
    assert ib.peer_identity(headers, "203.0.113.9", None) == "203.0.113.9"
    assert ib.peer_identity(headers, "203.0.113.9", HEADER) is None
    assert ib.peer_identity(headers, "127.0.0.2", HEADER) is None
    assert (
        ib.peer_identity(
            {**headers, HEADER.lower(): "198.51.100.2"}, "127.0.0.1", HEADER
        )
        is None
    )
    assert ib.peer_identity({HEADER.lower(): "192.0.2.1"}, "::1", HEADER) == "192.0.2.1"
    assert (
        ib.peer_identity({HEADER: "2001:0db8:0:0:0:0:0:1"}, "127.0.0.1", HEADER)
        == "2001:db8::1"
    )
    assert (
        ib.peer_identity({HEADER: "::ffff:192.0.2.1"}, "127.0.0.1", HEADER)
        == "192.0.2.1"
    )


def test_proxy_request_buckets_are_per_validated_ip_and_direct_headers_are_ignored(
    deployed,
):
    intake, _ = deployed
    intake.limits = ib.PeerLimits(burst=1, rate=0)
    for ip, status in (("192.0.2.1", 200), ("198.51.100.1", 429)):
        assert (
            intake.handle("GET", ib.INFO_PATH, {HEADER: ip}, b"", "127.0.0.1").status
            == status
        )
    assert "exposure" not in intake.public().body
    intake.proxy_header = "X-Verified-Client"
    intake.limits = ib.PeerLimits(burst=1, rate=0)
    for ip, status in (
        ("192.0.2.1", 200),
        ("192.0.2.1", 429),
        ("198.51.100.1", 200),
        ("::ffff:192.0.2.1", 429),
    ):
        assert (
            intake.handle(
                "GET", ib.INFO_PATH, {"X-Verified-Client": ip}, b"", "127.0.0.1"
            ).status
            == status
        )
    assert intake.public().body["exposure"] == {"via": "trusted_proxy"}
    assert HEADER not in json.dumps(intake.public().body)


@contextmanager
def proxy_http(intake, host="127.0.0.1"):
    intake.proxy_header = HEADER
    server = ib.listener(proxy_config(host=host), intake)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_proxy_requires_identity_before_body_reads_and_supports_local_probe(
    deployed, monkeypatch
):
    intake, _ = deployed
    reads = []
    original = ib.read_body

    def counted(*args, **kwargs):
        reads.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(ib, "read_body", counted)
    with proxy_http(intake) as server:
        host, port = server.server_address
        url = f"http://{host}:{port}"
        assert ic.post(url, b"{}", {}) == (400, {"refused": "peer_header_invalid"})
        assert reads == []
        assert svc.probe_intake(proxy_config(port=port))["answer"] == "ok"
        assert len(reads) == 1
        assert ic.post(url, b"{}", {HEADER: "192.0.2.1"})[0] == 400
        assert len(reads) == 2


def test_proxy_connection_limits_separate_clients_and_keep_global_cap(deployed):
    intake, _ = deployed
    with proxy_http(intake) as server:
        held = []
        try:
            for _ in range(ib.MAX_CONNECTIONS_PER_PEER):
                client = socket.create_connection(server.server_address, timeout=3)
                client.sendall(
                    (
                        f"POST {ib.PATH} HTTP/1.1\r\nHost: fixture\r\n{HEADER}: 192.0.2.1\r\nContent-Length: 2\r\n\r\n{{"
                    ).encode()
                )
                held.append(client)
            until = time.monotonic() + 3
            while (
                intake.client_connections.open() != ib.MAX_CONNECTIONS_PER_PEER
                and time.monotonic() < until
            ):
                time.sleep(0.01)
            assert intake.client_connections.open() == ib.MAX_CONNECTIONS_PER_PEER
            url = f"http://127.0.0.1:{server.server_address[1]}"
            assert ic.post(url, b"{}", {HEADER: "192.0.2.1"}) == (
                503,
                {"refused": "capacity"},
            )
            assert ic.post(url, b"{}", {HEADER: "198.51.100.1"})[0] == 400
            assert server.slots.open() <= ib.MAX_CONNECTIONS
        finally:
            for client in held:
                client.sendall(b"}")
                client.recv(65536)
                client.close()
        until = time.monotonic() + 3
        while intake.client_connections.open() and time.monotonic() < until:
            time.sleep(0.01)
        assert intake.client_connections.open() == 0
    slots = ib.ConnectionSlots()
    assert all(
        slots.acquire("127.0.0.1", shared_proxy=True) for _ in range(ib.MAX_CONNECTIONS)
    )
    assert not slots.acquire("127.0.0.1", shared_proxy=True)
    direct = ib.ConnectionSlots()
    assert all(direct.acquire("192.0.2.1") for _ in range(ib.MAX_CONNECTIONS_PER_PEER))
    assert not direct.acquire("192.0.2.1")


def test_service_preflight_guards_the_tunnel_even_on_loopback():
    config = proxy_config()
    for deployment, code in (
        ({"backend": "direct"}, "intake_exposure_needs_carrier"),
        (
            {"backend": "carrier", "require_commitment": False},
            "intake_exposure_needs_commitment",
        ),
    ):
        with pytest.raises(svc.ServiceRefused, match=f"^{code}$"):
            svc.check_exposure(config, deployment)
    assert svc.check_exposure(
        config, {"backend": "carrier", "require_commitment": True}
    ) == {
        "bind": "loopback",
        "host": "127.0.0.1",
        "exposure_record": RECORD,
        "via": "trusted_proxy",
        "tls": False,
    }


def test_ipv6_loopback_proxy_listener_and_health_probe(deployed):
    intake, _ = deployed
    with proxy_http(intake, host="::1") as server:
        assert server.address_family == socket.AF_INET6
        port = server.server_address[1]
        found = svc.probe_intake(proxy_config(host="::1", port=port))
        assert found["listening"] and found["answer"] == "ok"
        assert intake.limits._buckets.keys() == {"127.0.0.1"}


@pytest.mark.parametrize("tool", ["battery_submit", "battery_status", *ib.LEVEL4_TOOLS])
def test_every_authenticated_tool_refuses_another_receiver(deployed, tool):
    from carbon.transport.models import message

    intake, _ = deployed
    body = message(
        intake.context,
        facts(intake)["snapshot"]["id"],
        intake.challenge,
        session="fixture",
        request="wrong-receiver",
        tool=tool,
        fields={},
    )
    answer = intake.handle(
        "POST", ib.PATH, signed(MINER, body, receiver=OTHER), body, "192.0.2.1"
    )
    assert (answer.status, answer.body) == (401, {"refused": "AUTH_WRONG_RECEIVER"})
    assert intake.inbox.received() == []


def test_receiver_is_checked_even_on_a_replayed_body(deployed):
    intake, _ = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="fixture")
    assert post(intake, MINER, body).status == 202
    assert post(intake, MINER, body, receiver=OTHER).body == {
        "refused": "AUTH_WRONG_RECEIVER"
    }
    assert intake.handle("POST", ib.PATH, {}, body, "192.0.2.1").status == 401
    assert len(intake.inbox.received()) == 1


@pytest.mark.parametrize("reader", [None, "empty"])
def test_commitment_required_admission_never_executes_an_unbound_submission(
    deployed, reader, monkeypatch
):
    intake, target = deployed

    class EmptyChain:
        def read(self, hotkey):
            return None

    target.require_commitment = True
    target.commitments = None if reader is None else EmptyChain()

    def never(*args, **kwargs):
        raise AssertionError("unbound recipe reached execution")

    monkeypatch.setattr(target.backend, "reconstruct", never)
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="fixture")
    sid = post(intake, MINER, body).body["submission_id"]
    moved = ib.work_once(intake.inbox, target)
    assert moved["admitted"] == 0 and moved["processed"] == 0
    row = intake.inbox.row(sid)
    assert row["state"] == "REFUSED"
    expected = (
        "commitment_reader_unavailable" if reader is None else "commitment_required"
    )
    assert row["failure"] == {"failure": {"code": expected}}
    with target.store.db() as database:
        assert database.execute("SELECT COUNT(*) FROM submissions").fetchone() == (0,)


def test_effective_cached_private_target_cannot_be_exposed(deployed, monkeypatch):
    from types import SimpleNamespace

    from carbon.battery import deployment
    from carbon.battery.worker import CarrierBackend

    intake, target = deployed
    config = proxy_config(inbox=str(intake.inbox.path), deployment="fixture")
    ib.require_public_target({"host": "127.0.0.1"}, target)
    with pytest.raises(ib.IntakeUnavailable, match="^intake_exposure_needs_carrier$"):
        ib.require_public_target(config, target)
    # A nominal carrier stand-in tests only the guard; it is never executed.
    carrier = object.__new__(CarrierBackend)
    with pytest.raises(
        ib.IntakeUnavailable, match="^intake_exposure_needs_commitment$"
    ):
        ib.require_public_target(
            config, SimpleNamespace(backend=carrier, require_commitment=False)
        )
    ib.require_public_target(
        config, SimpleNamespace(backend=carrier, require_commitment=True)
    )
    monkeypatch.setattr(ib, "load_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(
        deployment,
        "load_config",
        lambda path: {"backend": "carrier", "require_commitment": True},
    )
    monkeypatch.setattr(ib, "_when_host_ready", lambda *args: target)

    def never(*args):
        raise AssertionError("cached private target reached the listener")

    monkeypatch.setattr(ib, "_serve", never)
    with pytest.raises(ib.IntakeUnavailable, match="^intake_exposure_needs_carrier$"):
        ib.serve("fixture", repository="fixture")
