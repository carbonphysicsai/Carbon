"""Operator composition checks; fixtures confer no real model/chain acceptance."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sqlite3
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_receiver as receiver
from carbon.development_session.profile import canonical

OWNER = "5" + "1" * 47
OTHER = "5" + "2" * 47
RECEIVER = "5" + "3" * 47
POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX task/owner-only ledger")


def _config(tmp_path):
    return {
        "schema": receiver.SCHEMA,
        "root": str(tmp_path / "receiver"),
        "runner_profile": str(tmp_path / "profile.json"),
        "host": "127.0.0.1",
        "port": 8767,
        "receiver_hotkey": RECEIVER,
        "lifetime_seconds": 30,
        "measure_query": True,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("host", "0.0.0.0"),
        ("port", True),
        ("port", 0),
        ("lifetime_seconds", 0),
        ("lifetime_seconds", True),
        ("measure_query", 1),
        ("receiver_hotkey", "validator"),
        ("root", "relative"),
        ("runner_profile", None),
        ("exposure", {}),
    ],
)
def test_closed_private_configuration_refuses_untrusted_shape(
    tmp_path, monkeypatch, field, value
):
    cfg = {**_config(tmp_path), field: value}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    with pytest.raises(ValueError):
        receiver.load_config(tmp_path / "config.json")


def test_configuration_retains_explicit_finite_measurement_policy(
    tmp_path, monkeypatch
):
    cfg = _config(tmp_path)
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    assert receiver.load_config(tmp_path / "config.json")["measure_query"] is True


def test_main_uses_process_stop_and_closed_failure_without_private_text(
    tmp_path, monkeypatch, capsys
):
    def fail(*args, **kwargs):
        assert isinstance(kwargs["stop"], threading.Event)
        raise ValueError("PRIVATE PATH MUST NOT APPEAR")

    monkeypatch.setattr(receiver, "serve", fail)
    monkeypatch.setattr(receiver.signal, "signal", lambda *_: None)
    assert receiver.main(["--config", str(tmp_path / "config.json")]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "direct_receiver_unavailable"
    }


def test_shutdown_refuses_to_release_unreconciled_provider_lock(tmp_path):
    calls = []
    provider = SimpleNamespace(
        _views={"task": SimpleNamespace(task_id="task")},
        requires_reconciliation=lambda _: True,
        close=lambda: calls.append("CLOSED"),
    )
    pool = receiver.OwnerProviders(tmp_path, None, None, None)
    pool._providers[OWNER] = provider
    with pytest.raises(receiver.ReceiverUnavailable, match="cleanup_unresolved"):
        pool.close()
    assert calls == []


@POSIX
def test_owner_provider_restart_shares_exact_ledger_and_refuses_work_during_stop(
    tmp_path,
):
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    root = receiver._private_directory(tmp_path / "owners")
    pool = receiver.OwnerProviders(root, discovery, parent, tmp_path / "cache")
    one, two = pool(OWNER), pool(OTHER)
    assert pool(OWNER) is one
    assert one.discovery is two.discovery is discovery
    assert one.owner == OWNER and two.owner == OTHER
    assert one.ledger.root != two.ledger.root
    first_root = one.ledger.root
    pool.cancel()
    with pytest.raises(Unavailable, match="direct_receiver_stopping"):
        pool(OWNER)
    pool.close()
    restarted = receiver.OwnerProviders(root, discovery, parent, tmp_path / "cache")
    restarted.restore()
    assert restarted(OWNER).ledger.root == first_root
    assert len(restarted._providers) == 2
    restarted.cancel()
    restarted.close()


@POSIX
def test_real_loopback_bootstrap_stages_and_admits_same_owner_without_model_dispatch(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _headers, _snapshot, _Verifier

    from carbon import research
    from carbon.challenge_validator import direct_intake
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
    from carbon.level4 import staging, submission
    from carbon.reconstruction.worker.model import WorkerImageIdentity
    from carbon.transport.models import message

    cfg = _config(tmp_path)
    # Port zero is injected after config validation only for this disposable
    # unit fixture. Production requires a fixed configured target port.
    cfg["port"] = 0
    monkeypatch.setattr(receiver, "load_config", lambda _: cfg)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    monkeypatch.setattr(
        receiver,
        "installed_source",
        lambda _: (
            {"revision": "a" * 40, "source_tree_digest": "sha256:" + "6" * 64},
            parent,
            SimpleNamespace(context=CONTEXT, publisher_hotkey=RECEIVER),
            tmp_path / "cache",
        ),
    )
    now = time.time_ns()
    snapshot = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER), timestamp_ms=now // 1_000_000
    )
    reader = SimpleNamespace()

    async def capture(context):
        assert context == CONTEXT
        return snapshot

    reader.capture = capture
    dispatched = []

    def forbidden(*_):
        dispatched.append(True)
        raise AssertionError("this fixture must not dispatch a model")

    monkeypatch.setattr(DirectDevelopmentTasksV3, "run_queued_task", forbidden)
    # This fixture checks ingress and custody, not execution. A slow CI host
    # must not turn the queued-task assertion into a model dispatch.
    monkeypatch.setattr(direct_intake, "_advance_loop", lambda *args: args[1].wait())
    stop, retained = threading.Event(), {}

    def ready(facts):
        target = facts["direct_intake_target"]
        assert target["receiver_hotkey"] == RECEIVER
        with urllib.request.urlopen(
            target["intake_url"] + direct_intake.INFO_PATH
        ) as stream:
            public = json.load(stream)
        assert public["challenge"] == {
            "id": "synthetic-linear-field-2d",
            "version": "1.3",
        }
        assert public["score_pack"] is None
        key = research.ChallengeKey(public["challenge"]["id"], "1.3")
        document = b'{"untrusted":"inert fixture source"}'
        fingerprint = submission.name(document)
        manifest = canonical({"documents": {"forward": fingerprint}})
        nonce = time.time_ns()

        def post(tool, fields, number):
            body = message(
                CONTEXT,
                public["snapshot"]["id"],
                key,
                session="bootstrap-fixture",
                request=f"bootstrap-call-{number:04}",
                tool=tool,
                fields=fields,
            )
            request = urllib.request.Request(
                target["intake_url"] + direct_intake.SUBMIT_PATH,
                data=body,
                headers={
                    **_headers(body, nonce + number, hotkey=OWNER),
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request) as stream:
                return json.load(stream)

        for index, (name, raw) in enumerate(
            (
                (staging.WORKSPACE_PREFIX + fingerprint[7:] + ".json", document),
                (staging.WORKSPACE_MANIFEST, manifest),
            ),
            1,
        ):
            call = research.ServiceCall(
                research.RESEARCH_NAMESPACE,
                "stage_research_source",
                research.DirectStageSourceRequestV1(
                    key, name, 0, len(raw), submission.name(raw), None, raw
                ),
            )
            reply = post(
                research.RESEARCH_NAMESPACE,
                {
                    "call_base64": base64.b64encode(
                        research.canonical_bytes(call)
                    ).decode()
                },
                index,
            )
            assert reply["schema"] == direct_intake.SOURCE_REPLY_SCHEMA

        from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

        kit = bundle_material_v5()["construction_kit"]
        recipe = {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": submission.name(manifest)},
            "procedure": {
                "entrypoint": None,
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": kit["interface_digest"],
            },
        }
        admitted = post(
            direct_intake.SUBMIT_TOOL,
            {
                "strategy_json": json.dumps(recipe),
                "contract_digest": public["served_contracts"][0]["digest"],
            },
            3,
        )
        assert admitted["outcome"]["state"] == "ADMITTED"
        retained["task"] = admitted["outcome"]["task_id"]
        stop.set()

    class Verifier(_Verifier):
        def verify(self, headers, *args, **kwargs):
            return super().verify(
                {key.lower(): value for key, value in headers.items()},
                *args,
                **kwargs,
            )

    receiver.serve(
        tmp_path / "config.json",
        stop=stop,
        reader=reader,
        verifier=Verifier(),
        ready=ready,
    )
    assert retained["task"] and not dispatched
    owner_root = (
        Path(cfg["root"]) / "owners" / hashlib.sha256(OWNER.encode()).hexdigest()
    )
    assert (owner_root / "tasks" / "direct-tasks.sqlite3").is_file()
    assert (owner_root / "ledger" / "campaign.sqlite3").is_file()
    with sqlite3.connect(owner_root / "tasks" / "direct-tasks.sqlite3") as db:
        assert db.execute(
            "SELECT profile FROM direct_task_measurements"
        ).fetchall() == [("COLD_QUERY_V2",)]
        assert (
            json.loads(db.execute("SELECT view FROM direct_tasks").fetchone()[0])[
                "state"
            ]
            == "CANCELLED"
        )


@POSIX
def test_listener_cancels_before_waiting_and_does_not_return_with_worker_active(
    monkeypatch,
):
    from carbon.challenge_validator import direct_intake

    stop, started, release, finished = (threading.Event() for _ in range(4))
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()

    def advance(*_):
        started.set()
        assert release.wait(5)
        finished.set()

    def closing():
        assert started.is_set()
        assert not finished.is_set()
        release.set()

    def ready(_):
        assert started.wait(5)
        stop.set()

    monkeypatch.setattr(direct_intake, "_advance_loop", advance)
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    direct_intake.serve_loopback(
        intake,
        {"host": "127.0.0.1", "port": 0},
        stop=stop,
        ready=ready,
        closing=closing,
    )
    assert finished.is_set()


@POSIX
def test_failed_readiness_stops_worker_before_return(monkeypatch):
    from carbon.challenge_validator import direct_intake

    stop, finished = threading.Event(), threading.Event()
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()

    def advance(*_):
        stop.wait()
        finished.set()

    def ready(_):
        raise ValueError("readiness refused")

    monkeypatch.setattr(direct_intake, "_advance_loop", advance)
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    with pytest.raises(ValueError, match="readiness refused"):
        direct_intake.serve_loopback(
            intake, {"host": "127.0.0.1", "port": 0}, stop=stop, ready=ready
        )
    assert stop.is_set() and finished.is_set()


@POSIX
def test_incomplete_headers_cannot_hold_graceful_shutdown(monkeypatch):
    from carbon.challenge_validator import direct_intake

    stop = threading.Event()
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.window, intake.context = object(), object()
    monkeypatch.setattr(direct_intake, "SOCKET_TIMEOUT_S", 0.1)
    monkeypatch.setattr(direct_intake, "_advance_loop", lambda *a: stop.wait())
    monkeypatch.setattr(direct_intake, "refresher", lambda *a, **kw: kw["stop"].wait())
    clients = []

    def ready(address):
        connection = socket.create_connection(address, timeout=2)
        clients.append(connection)
        connection.sendall(b"GET / HTTP/1.1\r\nX-Incomplete:")
        stop.set()

    started = time.monotonic()
    try:
        direct_intake.serve_loopback(
            intake, {"host": "127.0.0.1", "port": 0}, stop=stop, ready=ready
        )
        assert time.monotonic() - started < 3
        assert clients[0].recv(1) == b""
    finally:
        for client in clients:
            client.close()
