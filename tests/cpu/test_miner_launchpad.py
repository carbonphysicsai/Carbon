"""Native/controller diagnostics; no agent calls or scientific acceptance."""

import concurrent.futures
import http.client
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

MODULE = (
    Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/controller.py"
)
SPEC = importlib.util.spec_from_file_location("carbon_launchpad_controller", MODULE)
launchpad = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launchpad)


def test_direct_script_starts_outside_repository(tmp_path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    process = subprocess.Popen(
        [
            sys.executable,
            str(MODULE),
            "--state-dir",
            str(tmp_path / "state"),
            "--port",
            str(port),
        ],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", "/")
                response = connection.getresponse()
                assert response.status == 200
                assert b"Carbon" in response.read()
                return
            except OSError:
                time.sleep(0.05)
            finally:
                connection.close()
        pytest.fail("Direct controller script did not become ready")
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture
def clock():
    value = [1000.0]
    return value, lambda: value[0]


@pytest.fixture
def controller(tmp_path, clock):
    return launchpad.Controller(tmp_path / "runs.sqlite3", clock[1])


def spec(**changes):
    return {**launchpad.CHOICES, "max_steps": 5, "max_seconds": 100, **changes}


def start(controller, key="request-1234567890", **changes):
    return controller.launch(spec(**changes), key)


def test_validated_input_is_detached():
    value = spec()
    output = launchpad.validate_spec(value)
    value["max_steps"] = 10
    assert output["max_steps"] == 5


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "LIVE"),
        ("mode", "DEVELOPMENT"),
        ("agent", "hermes"),
        ("agent", "mira"),
        ("compute", "lium"),
        ("reasoning", "chutes"),
        ("reasoning", "engy"),
        ("challenge", "burgers"),
        ("max_steps", True),
        ("max_steps", 0),
        ("max_steps", 101),
        ("max_steps", 1.0),
        ("max_steps", "1"),
        ("max_seconds", False),
        ("max_seconds", 0),
        ("max_seconds", 601),
        ("max_seconds", None),
    ],
)
def test_invalid_or_external_profiles_fail_closed(field, value):
    with pytest.raises(launchpad.Rejected):
        launchpad.validate_spec(spec(**{field: value}))


@pytest.mark.parametrize(
    "value", [None, [], {}, spec(secret="do-not-store"), spec(command="echo x")]
)
def test_closed_schema(value):
    with pytest.raises(launchpad.Rejected):
        launchpad.validate_spec(value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b"{",
        b"\xff",
        b"[" * 1500,
    ],
)
def test_invalid_json(raw):
    with pytest.raises(launchpad.Rejected):
        launchpad.parse_json(raw)


def test_duplicate_launch_returns_same_run(controller):
    first = start(controller)
    second = start(controller)
    assert second == first
    assert len(controller.recent()) == 1


def test_conflicting_replay_is_rejected(controller):
    first = start(controller)
    with pytest.raises(launchpad.Rejected, match="idempotency_key_conflict"):
        start(controller, max_steps=7)
    assert controller.get(first["id"])["spec"]["max_steps"] == 5


def test_concurrent_duplicate_launches(controller):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        runs = list(pool.map(lambda _: start(controller), range(20)))
    assert len({run["id"] for run in runs}) == 1
    assert len(controller.recent()) == 1


def test_input_does_not_mutate_persisted_spec(controller):
    value = spec()
    run = controller.launch(value, "request-1234567890")
    value["max_steps"] = 99
    assert controller.get(run["id"])["spec"]["max_steps"] == 5


def test_pause_resume_keeps_progress_and_deadline(controller, clock):
    run = start(controller)
    controller.tick()
    paused = controller.control(run["id"], "pause")
    clock[0][0] += 2
    controller.tick()
    assert controller.get(run["id"])["steps"] == 1
    resumed = controller.control(run["id"], "resume")
    assert resumed["deadline"] == paused["deadline"] == run["deadline"]
    controller.tick()
    assert controller.get(run["id"])["steps"] == 2


def test_repeated_controls_do_not_add_events(controller):
    run = start(controller)
    first = controller.control(run["id"], "pause")
    assert controller.control(run["id"], "pause") == first
    first = controller.control(run["id"], "resume")
    assert controller.control(run["id"], "resume") == first
    first = controller.control(run["id"], "stop")
    assert controller.control(run["id"], "stop") == first


def test_stop_is_terminal_and_stops_steps(controller):
    run = start(controller)
    controller.tick()
    stopped = controller.control(run["id"], "stop")
    for _ in range(5):
        controller.tick()
    assert controller.get(run["id"]) == stopped
    with pytest.raises(launchpad.Rejected, match="invalid_state_transition"):
        controller.control(run["id"], "resume")


def test_completion_never_creates_science_or_submission(controller):
    run = start(controller, max_steps=2)
    controller.tick()
    controller.tick()
    result = controller.get(run["id"])
    assert result["state"] == "COMPLETED"
    assert result["evidence"] == "CONTROLLER_REHEARSAL_ONLY"
    assert result["scientific_result"] is None
    assert result["submission_receipt"] is None
    assert result["external_spend_cents"] == 0
    with pytest.raises(launchpad.Rejected):
        controller.control(run["id"], "stop")


@pytest.mark.parametrize("state", ["QUEUED", "RUNNING", "PAUSED", "INTERRUPTED"])
def test_lifetime_expires_in_all_active_states(controller, clock, state):
    run = start(controller, max_seconds=2)
    if state == "RUNNING":
        controller.tick()
    elif state == "PAUSED":
        controller.control(run["id"], "pause")
    elif state == "INTERRUPTED":
        controller.recover()
    clock[0][0] += 2
    result = controller.get(run["id"])
    assert result["state"] == "EXPIRED"
    with pytest.raises(launchpad.Rejected):
        controller.control(run["id"], "resume")


def test_restart_requires_explicit_resume_and_retains_events(controller, clock):
    run = start(controller)
    controller.tick()
    before = controller.get(run["id"])
    reopened = launchpad.Controller(controller.database, clock[1])
    reopened.recover()
    after = reopened.get(run["id"])
    assert after["state"] == "INTERRUPTED"
    assert after["steps"] == before["steps"]
    assert after["events"][:-1] == before["events"]
    reopened.tick()
    assert reopened.get(run["id"])["steps"] == 1
    reopened.control(run["id"], "resume")
    reopened.tick()
    assert reopened.get(run["id"])["steps"] == 2


def test_restart_retains_paused_and_terminal_states(controller, clock):
    one = start(controller)
    two = start(controller, "request-9876543210")
    controller.control(one["id"], "pause")
    controller.control(two["id"], "stop")
    reopened = launchpad.Controller(controller.database, clock[1])
    reopened.recover()
    assert reopened.get(one["id"])["state"] == "PAUSED"
    assert reopened.get(two["id"])["state"] == "STOPPED"


def test_active_capacity_and_slot_release(controller):
    runs = [start(controller, f"request-000000000{i}") for i in range(4)]
    with pytest.raises(launchpad.Rejected, match="active_run_limit"):
        start(controller, "request-0000000005")
    controller.control(runs[0]["id"], "stop")
    assert start(controller, "request-0000000005")["state"] == "QUEUED"


def test_lock_excludes_second_owner(tmp_path):
    with (
        launchpad.owner_lock(tmp_path / "state"),
        pytest.raises(RuntimeError, match="Another launcher"),
        launchpad.owner_lock(tmp_path / "state"),
    ):
        pass


def test_capabilities_do_not_claim_external_execution():
    data = launchpad.capability_catalog()
    assert data["mode"] == "REHEARSAL"
    assert {entry["id"] for entry in data["unavailable"]} >= {
        "lium",
        "hermes",
        "testnet-registration",
    }


@pytest.fixture
def server(controller):
    server = launchpad.Server(controller, "x" * 40, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def request(server, path, method="GET", body=None, headers=None, raw=False):
    headers = dict(headers or {})
    if body is not None:
        headers.setdefault("Content-Type", "application/json")
        if not raw:
            body = json.dumps(body)
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(method, path, body, headers)
    response = connection.getresponse()
    content = response.read()
    result = (response.status, dict(response.getheaders()), content)
    connection.close()
    return result


def auth(**extra):
    return {"Authorization": "Bearer " + "x" * 40, **extra}


def test_static_page_has_no_auth_secret(server):
    code, headers, body = request(server, "/")
    assert code == 200
    assert ("x" * 40).encode() not in body
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert b"Controller rehearsal only" in body


def test_api_requires_token(server):
    assert request(server, "/api/v1/runs")[0] == 401
    assert request(server, "/api/v1/runs", headers=auth())[0] == 200


def test_rebinding_and_cross_origin_are_denied(server):
    assert request(server, "/", headers={"Host": "attacker.example"})[0] == 403
    assert (
        request(
            server, "/api/v1/runs", headers=auth(Origin="https://attacker.example")
        )[0]
        == 403
    )
    assert request(server, "/api/v1/runs", headers=auth(Origin="null"))[0] == 403


def test_http_full_flow_and_retry(server):
    headers = auth(**{"Idempotency-Key": "request-1234567890"})
    code, _, body = request(server, "/api/v1/runs", "POST", spec(), headers)
    assert code == 200
    run = json.loads(body)
    again = request(server, "/api/v1/runs", "POST", spec(), headers)
    assert json.loads(again[2])["id"] == run["id"]
    base = "/api/v1/runs/" + run["id"]
    assert request(server, base, headers=auth())[0] == 200
    for action, expected in [
        ("pause", "PAUSED"),
        ("resume", "QUEUED"),
        ("stop", "STOPPED"),
    ]:
        code, _, body = request(server, base + "/" + action, "POST", {}, auth())
        assert code == 200
        assert json.loads(body)["state"] == expected


@pytest.mark.parametrize(
    "body", [spec(agent="hermes"), spec(compute="lium"), spec(wallet="secret")]
)
def test_http_does_not_activate_providers(server, body):
    code, _, _ = request(
        server,
        "/api/v1/runs",
        "POST",
        body,
        auth(**{"Idempotency-Key": "request-1234567890"}),
    )
    assert code == 400
    assert server.controller.recent() == []


def test_http_rejects_oversize_and_duplicate_json(server):
    assert (
        request(server, "/api/v1/runs", "POST", " " * 4097, auth(), raw=True)[0] == 413
    )
    assert (
        request(server, "/api/v1/runs", "POST", '{"x":1,"x":2}', auth(), raw=True)[0]
        == 400
    )


def test_secret_and_path_are_not_reflected(server):
    _, _, body = request(server, "/api/v1/runs/not-a-secret", headers=auth())
    assert b"not-a-secret" not in body
    assert ("x" * 40).encode() not in body


def test_failed_event_rolls_back_launch_and_allows_same_retry(controller, monkeypatch):
    original = controller.event

    def fail(*args):
        raise sqlite3.OperationalError("private storage detail")

    monkeypatch.setattr(controller, "event", fail)
    with pytest.raises(sqlite3.OperationalError):
        start(controller)
    assert controller.recent() == []
    monkeypatch.setattr(controller, "event", original)
    assert start(controller)["state"] == "QUEUED"
    assert len(controller.recent()) == 1


@pytest.mark.parametrize("operation", ["recent", "launch", "control"])
def test_http_storage_failure_is_fixed_infrastructure_error(
    server, monkeypatch, operation
):
    run = start(server.controller)

    def fail(*args):
        raise sqlite3.OperationalError("private storage detail")

    monkeypatch.setattr(server.controller, operation, fail)
    if operation == "recent":
        result = request(server, "/api/v1/runs", headers=auth())
    elif operation == "launch":
        result = request(
            server,
            "/api/v1/runs",
            "POST",
            spec(),
            auth(**{"Idempotency-Key": "request-1234567890"}),
        )
    else:
        result = request(server, f"/api/v1/runs/{run['id']}/stop", "POST", {}, auth())
    assert result[0] == 503
    assert json.loads(result[2]) == {"error": "local_infrastructure_unavailable"}


def test_oversized_content_length_is_rejected_without_integer_conversion(server):
    result = request(
        server,
        "/api/v1/runs",
        "POST",
        b"{}",
        auth(**{"Content-Length": "9" * 5000}),
        raw=True,
    )
    assert result[0] == 413
    assert server.controller.recent() == []


def test_http_admission_is_bounded(server):
    for _ in range(16):
        assert server.request_slots.acquire(blocking=False)
    try:
        with pytest.raises((OSError, http.client.RemoteDisconnected)):
            request(server, "/")
    finally:
        for _ in range(16):
            server.request_slots.release()
    assert request(server, "/")[0] == 200


def test_process_exit_releases_owner_lock(tmp_path):
    directory = tmp_path / "state"
    code = (
        "import importlib.util,sys,time; from pathlib import Path; "
        "s=importlib.util.spec_from_file_location('launchpad',sys.argv[1]); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "lock=m.owner_lock(Path(sys.argv[2])); lock.__enter__(); "
        "print('locked',flush=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(MODULE), str(directory)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with (
            pytest.raises(RuntimeError, match="Another launcher"),
            launchpad.owner_lock(directory),
        ):
            pass
    finally:
        process.kill()
        process.wait(timeout=5)
        process.stdout.close()
    with launchpad.owner_lock(directory):
        pass
