"""Source readback boundary diagnostics using existing signed engineering fixtures.

No numerical research, real registration, provider request or chain transaction.
"""

import http.client
import json
import threading
from pathlib import Path

import pytest
from test_cw1_development_testnet_operator import source_handoff
from test_miner_launchpad import launchpad

from carbon.audit import DevelopmentEvidenceLedger
from carbon.development_testnet.execution import load_source_handoff
from carbon.orchestration import public_projection
from scripts.dev.miner_launchpad.development import (
    MAX_SOURCE_BYTES,
    DevelopmentSources,
    SourceUnavailable,
    source_pin,
)


def test_existing_source_uses_domain_projection_and_persists(tmp_path):
    path, _ = source_handoff(tmp_path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    assert store.attach(path) == identity
    reopened = DevelopmentSources(store.database)
    value = reopened.get(identity)
    assert value["status"] == "VERIFIED_SOURCE"
    assert value["mode"] == "DEVELOPMENT_EVALUATION"
    assert value["campaign_launched_by_launchpad"] is False
    expected = public_projection(load_source_handoff(path).evidence.account)
    assert value["receipt"] == expected
    assert reopened.recent() == [value]
    encoded = reopened.export(identity).decode()
    for forbidden in (
        str(tmp_path),
        "signature_hex",
        "transport_context",
        "verification_keys",
        "evidence_ledger",
        "case_digest",
        "seed",
    ):
        assert forbidden not in encoded


def test_revocation_is_rechecked_and_never_exports_stale_receipt(tmp_path):
    path, _ = source_handoff(tmp_path)
    source = load_source_handoff(path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    ledger = DevelopmentEvidenceLedger(source.evidence_ledger, source.verification_keys)
    ledger.revoke(source.evidence.account.receipt_id, "sha256:" + "1" * 64)
    assert store.get(identity)["receipt"] is None
    assert store.get(identity)["status"] == "READBACK_UNAVAILABLE"
    with pytest.raises(SourceUnavailable):
        store.export(identity)


def test_replaced_handoff_cannot_change_frozen_attachment(tmp_path):
    path, _ = source_handoff(tmp_path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    value = json.loads(path.read_bytes())
    value["intent_identity"] = "changed-after-attachment"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert store.get(identity)["status"] == "READBACK_UNAVAILABLE"
    with pytest.raises(SourceUnavailable):
        store.attach(path)


def test_missing_source_never_leaks_private_path(tmp_path):
    path, _ = source_handoff(tmp_path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    path.unlink()
    value = store.get(identity)
    assert value["receipt"] is None
    assert str(path) not in json.dumps(value)


def test_unknown_identity_cannot_be_a_path(tmp_path):
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    for identity in ("missing", "../private-key", str(tmp_path)):
        with pytest.raises(SourceUnavailable):
            store.get(identity)


def test_source_bounds_and_relative_paths(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(SourceUnavailable):
        source_pin(path)
    with pytest.raises(SourceUnavailable):
        source_pin(Path("relative.json"))


def test_modified_private_export_fails_existing_carbon_verification(tmp_path):
    path, _ = source_handoff(tmp_path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    source = load_source_handoff(path)
    source.account_report.write_bytes(b"{}")
    assert store.get(identity)["status"] == "READBACK_UNAVAILABLE"


def test_http_readback_authentication_and_no_path_or_write_route(tmp_path):
    path, _ = source_handoff(tmp_path)
    store = DevelopmentSources(tmp_path / "launchpad.sqlite3")
    identity = store.attach(path)
    server = launchpad.Server(
        launchpad.Controller(store.database), "x" * 40, 0, development_sources=store
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def request(route, *, authenticated=True, method="GET"):
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Host": server.authority}
        if authenticated:
            headers["Authorization"] = "Bearer " + "x" * 40
        if method == "POST":
            headers["Content-Type"] = "application/json"
        client.request(
            method, route, body="{}" if method == "POST" else None, headers=headers
        )
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    try:
        assert request("/api/v1/development", authenticated=False)[0] == 401
        status, body = request("/api/v1/development")
        assert status == 200
        assert body["sources"] == [store.get(identity)]
        assert request("/api/v1/development/" + identity)[1] == store.get(identity)
        assert request("/api/v1/development/../../private-key")[0] == 404
        assert request("/api/v1/development", method="POST")[0] == 404
        path.unlink()
        _, fresh = request("/api/v1/development/" + identity)
        assert fresh["receipt"] is None
        assert fresh["status"] == "READBACK_UNAVAILABLE"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
