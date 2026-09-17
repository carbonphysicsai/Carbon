"""Runner bridge fixtures test control/disclosure only; never adaptive evidence."""

import http.client
import json
import threading

import pytest
from test_miner_launchpad_admission import managed, reserve

from carbon.development_session.profile import canonical
from scripts.dev.miner_launchpad.controller import Controller, Rejected, Server
from scripts.dev.miner_launchpad.runner import RunnerAdapter


def adapter(tmp_path, monkeypatch):
    value, control, manifest = managed(tmp_path)
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3")
    cfg = {"profile_id": "opaque-profile", "principal": "alice"}
    monkeypatch.setattr(
        bridge, "configured", lambda: (cfg, value.admission, value.root)
    )
    monkeypatch.setattr(bridge, "_start", lambda *args: None)
    manifest["provider"] = {"model": "fixture-model"}
    manifest["implementation"] = {"revision": "fixture-revision"}
    manifest["images"] = ["fixture-image"]
    with value.db() as db:
        db.execute("UPDATE campaign SET manifest=? WHERE id=1", (canonical(manifest),))
    return bridge, value, control


def test_disabled_profile_has_no_fallback_or_side_effect(tmp_path):
    bridge = RunnerAdapter(tmp_path / "browser.sqlite3")
    assert bridge.preflight()["available"] is False
    with pytest.raises(Rejected, match="admission"):
        bridge.launch({"profile": "anything"}, "request-key-000001")
    assert bridge.recent() == []


def test_opaque_launch_replay_and_another_key_share_grant_identity(
    tmp_path, monkeypatch
):
    bridge, _, _ = adapter(tmp_path, monkeypatch)
    first = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")
    assert (
        bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
        == first["id"]
    )
    assert (
        bridge.launch({"profile": "opaque-profile"}, "request-key-000002")["id"]
        == first["id"]
    )
    assert len(bridge.recent()) == 1
    for body in (
        {"profile": "wrong"},
        {"profile": "opaque-profile", "command": "arbitrary"},
        {"root": "/private"},
    ):
        with pytest.raises(Rejected):
            bridge.launch(body, "request-key-000003")


def test_projection_withholds_private_operations_and_retains_attempt_failure(
    tmp_path, monkeypatch
):
    bridge, value, _ = adapter(tmp_path, monkeypatch)
    first = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")
    reserve(value)
    value.finish(
        "op",
        owner="miner-requester",
        state="FAILED_INFRA",
        actual={"research_trials": 1},
        result={
            "provider_error": "SECRET-SENTINEL",
            "private_seed": "PROTECTED-SENTINEL",
        },
    )
    value.note(
        owner="miner-requester",
        kind="operational_error",
        body={"raw": "SECRET-SENTINEL"},
    )
    value.note(
        owner="miner-requester",
        kind="hypothesis",
        body={
            "hypothesis": "try a smaller legal model",
            "private_path": "SECRET-SENTINEL",
        },
    )
    result = bridge.get(first["id"])
    raw = json.dumps(result)
    assert "SECRET-SENTINEL" not in raw and "PROTECTED-SENTINEL" not in raw
    assert str(tmp_path) not in raw
    assert result["attempted_experiments"] == 1
    assert result["completed_experiments"] == 0
    assert result["operations"][0]["state"] == "FAILED_INFRA"
    assert result["final_results"] == []


def test_revoked_grant_still_allows_stop_and_retained_readback(tmp_path, monkeypatch):
    bridge, value, control = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    value.admission.path.unlink()
    assert bridge.control(identity, "stop")["state"] == "STOPPING"
    assert control.status()["desired"] == "STOP"
    assert bridge.get(identity)["id"] == identity


def test_changed_final_source_withheld_not_replaced_by_saved_feedback(
    tmp_path, monkeypatch
):
    bridge, value, _ = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    directory = value.root / "epoch-1/final"
    directory.mkdir(parents=True)
    (directory / "comparison-ref.json").write_bytes(
        canonical(
            {
                "root": "/unauthorized-private-directory",
                "registration_digest": "fake",
                "report_digest": "fake",
            }
        )
    )
    result = bridge.get(identity)
    assert result["final_results"] == [
        {
            "epoch": 1,
            "mode": "DEVELOPMENT_EVALUATION",
            "status": "READBACK_UNAVAILABLE",
            "result": None,
        }
    ]


def test_restart_fences_stale_state_without_replaying_dispatch(tmp_path, monkeypatch):
    bridge, value, control = adapter(tmp_path, monkeypatch)
    identity = bridge.launch({"profile": "opaque-profile"}, "request-key-000001")["id"]
    reserve(value)
    recovered = RunnerAdapter(bridge.database)
    assert recovered.get(identity)["state"] == "RECONCILIATION_REQUIRED"
    assert control.status()["generation"] > value.generation
    assert recovered.get(identity)["usage"]["reserved"]["research_trials"] == 1


def test_research_http_authentication_and_closed_requests(tmp_path):
    store = Controller(tmp_path / "browser.sqlite3")
    runner = RunnerAdapter(store.database)
    token = "nonspending-engineering-session-token"
    server = Server(store, token, 0, research_runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, authenticated=True):
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {
            "Host": server.origin.removeprefix("http://"),
            "Content-Type": "application/json",
            "Idempotency-Key": "fixture-request-001",
        }
        if authenticated:
            headers["Authorization"] = "Bearer " + token
        client.request(
            method,
            path,
            body='{"profile":"fixture"}' if method == "POST" else None,
            headers=headers,
        )
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        client.close()
        return result

    try:
        assert request("GET", "/api/v1/research", False)[0] == 401
        assert request("POST", "/api/v1/research", False)[0] == 401
        assert request("GET", "/api/v1/research")[1]["preflight"]["available"] is False
        assert request("POST", "/api/v1/research")[0] == 409
        assert request("GET", "/api/v1/research/../../private")[0] == 404
        assert runner.recent() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
