"""Operator composition checks; fixtures confer no real model/chain acceptance."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import sqlite3
import sys
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


def _allow_windows_receiver_fixture(monkeypatch):
    if os.name != "nt":
        return
    # The ledger transaction remains real. POSIX runs use the actual flock,
    # owner-only mode gate, and private JSON reader.
    monkeypatch.setitem(
        sys.modules,
        "fcntl",
        SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None),
    )

    def directory(path):
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(receiver, "_private_directory", directory)
    monkeypatch.setattr(
        receiver, "private_json", lambda path: json.loads(path.read_bytes())
    )


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


def test_installed_source_joins_only_exact_owner_candidate_and_installed_images(
    tmp_path, monkeypatch
):
    from carbon.development_session import (
        miner_network,
        research_campaign,
        research_image,
    )
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import installed, runner

    state = tmp_path / "state"
    profile = state / "environment" / "runner-profile.json"
    campaigns = profile.parent / "campaigns"
    accepted = {"revision": "a" * 40, "source_tree_digest": "sha256:" + "a" * 64}
    candidate = {
        "revision": "b" * 40,
        "tree": "c" * 40,
        "source_tree_digest": "sha256:" + "b" * 64,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    worker = SimpleNamespace(
        image_id="sha256:" + "1" * 64,
        source_tree_digest=candidate["source_tree_digest"],
    )
    analysis = SimpleNamespace(
        image_id="sha256:" + "2" * 64, parent_image=worker.image_id
    )
    gpu = SimpleNamespace(
        image_id="sha256:" + "3" * 64,
        source_tree_digest=candidate["source_tree_digest"],
    )
    cfg = {
        "enabled": True,
        "accepted_revision": candidate["revision"],
        "campaigns_root": str(campaigns),
        "runtime": {
            "implementation": candidate,
            "images": [worker.image_id, analysis.image_id],
        },
        "paths": {
            "image_manifest": str(tmp_path / "worker.json"),
            "analysis_image_manifest": str(tmp_path / "analysis.json"),
        },
        "gpu_image": str(tmp_path / "gpu.json"),
    }
    calls = []
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(
        installed,
        "candidate_implementation",
        lambda selected: calls.append(("candidate", selected)) or candidate,
        raising=False,
    )
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        lambda revision: calls.append(("accepted", revision)) or accepted,
    )
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: {"worker.json": worker, "gpu.json": gpu}[path.name],
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _: analysis)
    monkeypatch.setattr(research_image, "verify_image", lambda _: None)
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **_: SimpleNamespace(eligible=True),
    )
    monkeypatch.setattr(miner_network, "binding", lambda **_: "installed-network")
    implementation, parent, network, cache = receiver.installed_source(profile)
    assert (implementation, parent, network) == (candidate, gpu, "installed-network")
    assert cache == campaigns / ".direct-development" / "library-cache"
    assert calls == [("candidate", state)]

    # A present but invalid candidate pin cannot silently use accepted main.
    def invalid_candidate(_):
        raise ValueError("development candidate record differs")

    monkeypatch.setattr(installed, "candidate_implementation", invalid_candidate)
    with pytest.raises(ValueError, match="candidate record differs"):
        receiver.installed_source(profile)
    assert calls == [("candidate", state)]

    monkeypatch.setattr(installed, "candidate_implementation", lambda _: candidate)
    cfg["runtime"]["implementation"] = accepted
    with pytest.raises(ValueError, match="candidate profile differs"):
        receiver.installed_source(profile)
    cfg["runtime"]["implementation"] = candidate
    cfg["runtime"]["images"] = [worker.image_id, gpu.image_id]
    with pytest.raises(ValueError, match="candidate installed images differ"):
        receiver.installed_source(profile)

    # An exact installed profile with no candidate pin remains main-only.
    cfg["accepted_revision"] = accepted["revision"]
    cfg["runtime"]["implementation"] = accepted
    cfg["runtime"]["images"] = [worker.image_id, analysis.image_id]
    gpu.source_tree_digest = accepted["source_tree_digest"]
    monkeypatch.setattr(installed, "candidate_implementation", lambda _: None)
    implementation, parent, _, _ = receiver.installed_source(profile)
    assert (implementation, parent) == (accepted, gpu)
    assert calls[-1] == ("accepted", accepted["revision"])

    # A profile outside the exact installed state path never reads the pin.
    monkeypatch.setattr(installed, "candidate_implementation", invalid_candidate)
    regular = tmp_path / "other-profile.json"
    implementation, parent, _, _ = receiver.installed_source(regular)
    assert (implementation, parent) == (accepted, gpu)
    assert calls[-1] == ("accepted", accepted["revision"])


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
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    authority = {
        "implementation": {"revision": "a" * 40},
        "snapshot": snapshot,
        "receiver": RECEIVER,
    }
    root = receiver._private_directory(tmp_path / "owners")
    pool = receiver.OwnerProviders(
        root, discovery, parent, tmp_path / "cache", **authority
    )
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
    restarted = receiver.OwnerProviders(
        root, discovery, parent, tmp_path / "cache", **authority
    )
    restarted.restore()
    assert restarted(OWNER).ledger.root == first_root
    assert len(restarted._providers) == 2
    restarted.cancel()
    restarted.close()


def test_first_direct_child_reserves_under_frozen_registered_owner_and_reopens(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot
    from test_direct_v3_durable_tasks import _fixture

    from carbon import research
    from carbon.chain.models import (
        CARBON_NETUID,
        CARBON_NETWORK,
        ChainContext,
        Participant,
    )
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session import research_carrier
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    _allow_windows_receiver_fixture(monkeypatch)
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    snapshot = replace(
        snapshot,
        participants=snapshot.participants + (Participant(2, OTHER, "cold2", 2),),
    )
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    implementation = {"revision": "a" * 40}
    root = receiver._private_directory(tmp_path / "owners")

    def pool(observed):
        return receiver.OwnerProviders(
            root,
            discovery,
            parent,
            tmp_path / "cache",
            implementation=implementation,
            snapshot=observed,
            receiver=RECEIVER,
        )

    first = pool(snapshot)
    provider = first(OWNER)
    ledger = provider.ledger
    with ledger.db() as db:
        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["schema"] == "carbon.launchpad.campaign.v1"
    assert frozen["scope"] == "DEVELOPMENT_PUBLIC_SYNTHETIC_ONLY"
    assert frozen["owner"] == OWNER
    assert frozen["admission"]["hotkey"] == OWNER
    assert frozen["admission"]["snapshot_id"] == snapshot.snapshot_id
    assert "ceilings" not in frozen and "grant" not in frozen

    # The real C-03 carrier reaches ledger.reserve before host inspection.
    # A deliberately unavailable host settles FAILED_INFRA; no container or
    # candidate program is launched and no scientific outcome is inferred.
    monkeypatch.setattr(research_carrier, "DockerCLI", object)
    monkeypatch.setattr(
        research_carrier,
        "doctor",
        lambda **_: SimpleNamespace(eligible=False),
    )
    with pytest.raises(ValueError, match="research host ineligible"):
        research_carrier._run_locked(
            ledger,
            owner=OWNER,
            identity="first-build-child",
            source="pass",
            files={},
            image=parent,
            seconds=40,
            provenance="DIRECT_GRAPH_PUBLIC_RECONSTRUCTION",
            extra_resources={},
        )
    assert ledger.operation_state("first-build-child", owner=OWNER) == "FAILED_INFRA"
    with pytest.raises(ValueError, match="authenticated campaign owner differs"):
        ledger.reserve(
            "second-owner-child",
            owner=OTHER,
            phase="research",
            request={"kind": "direct"},
            resources={},
        )
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 1
    request, fixed_factory, _ = _fixture(
        tmp_path, monkeypatch, material=bundle_material_v5()
    )
    fixed = fixed_factory()
    image = fixed.image
    fixed.close()
    monkeypatch.setattr(DirectOwnerImageResolver, "__call__", lambda *_: image)
    queued = provider.start_research_task(request).task
    assert queued.state is research.DirectTaskStateV3.QUEUED
    first.close()

    advanced = replace(
        snapshot,
        finalized_block=snapshot.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=snapshot.timestamp_ms + 1000,
    )
    resumed = pool(advanced)
    resumed.restore()
    assert resumed(OWNER).ledger.generation > ledger.generation
    assert resumed(OWNER).queued_tasks() == (queued.task_id,)
    with resumed(OWNER).ledger.db() as db:
        retained = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert retained == frozen
    resumed.close()

    recycled = replace(
        advanced,
        participants=(
            advanced.participants[0],
            Participant(1, OWNER, "cold", 3),
            advanced.participants[2],
        ),
    )
    cleanup = pool(recycled)
    cleanup.restore()
    assert (
        cleanup._providers[OWNER].ledger.operation_state(
            "first-build-child", owner=OWNER
        )
        == "FAILED_INFRA"
    )
    retained = (
        cleanup._providers[OWNER]
        .get_research_result(
            research.DirectGetTaskRequestV3(
                discovery.info.challenge_key, queued.task_id
            )
        )
        .task
    )
    assert retained.state is research.DirectTaskStateV3.CANCELLED
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        cleanup(OWNER)
    # Revocation of one retained owner does not stop a second registered
    # miner from opening a fresh campaign through the same receiver.
    assert cleanup(OTHER).owner == OTHER
    cleanup.close()


def test_new_owner_uses_refreshed_finalized_snapshot_not_startup_registration(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    _allow_windows_receiver_fixture(monkeypatch)
    from carbon.battery.intake import SnapshotWindow
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    now = time.time()
    startup = replace(
        _snapshot(sender=OTHER, receiver=RECEIVER, context=context),
        timestamp_ms=int(now * 1000),
    )
    window = SnapshotWindow(clock=lambda: now)
    window.add(startup)
    root = receiver._private_directory(tmp_path / "owners")
    pool = receiver.OwnerProviders(
        root,
        DirectFixtureDiscovery(bundle_material_v5(), task_admission=True),
        WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8))),
        tmp_path / "cache",
        implementation={"revision": "a" * 40},
        snapshot=startup,
        window=window,
        receiver=RECEIVER,
    )
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)
    assert list(root.iterdir()) == []
    refreshed = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        finalized_block=startup.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=int(now * 1000) + 1000,
    )
    window.add(refreshed)
    provider = pool(OWNER)
    with provider.ledger.db() as db:
        frozen = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert frozen["admission"]["snapshot_id"] == refreshed.snapshot_id
    assert frozen["admission"]["registered_at_block"] == 2
    pool.close()


def test_lagged_refresh_cannot_restore_revoked_owner_or_background_dispatch(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.interface import Unavailable
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    _allow_windows_receiver_fixture(monkeypatch)
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    now = time.time()
    old = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        timestamp_ms=int(now * 1000),
    )
    revoked = replace(
        old,
        finalized_block=old.finalized_block + 2,
        block_hash="0x" + "4" * 64,
        timestamp_ms=int(now * 1000) + 2000,
        participants=tuple(p for p in old.participants if p.hotkey != OWNER),
    )
    lagged = replace(
        old,
        finalized_block=old.finalized_block + 1,
        block_hash="0x" + "3" * 64,
        timestamp_ms=int(now * 1000) + 1000,
    )
    root = receiver._private_directory(tmp_path / "receiver")
    owners = receiver._private_directory(root / "owners")
    window = receiver.ReceiverSnapshotWindow(root, context, RECEIVER, clock=lambda: now)
    window.add(old)
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    authority = {
        "implementation": {"revision": "a" * 40},
        "snapshot": old,
        "window": window,
        "receiver": RECEIVER,
    }
    parent = WorkerImageIdentity(*("sha256:" + "4" * 64 for _ in range(8)))
    pool = receiver.OwnerProviders(
        owners, discovery, parent, tmp_path / "cache", **authority
    )
    assert pool(OWNER).owner == OWNER
    record = window._record

    def failed_record(*_, **__):
        raise OSError("test-only durable write failure")

    monkeypatch.setattr(window, "_record", failed_record)
    with pytest.raises(OSError, match="durable write failure"):
        window.add(revoked)
    assert window.latest() is None
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)
    monkeypatch.setattr(window, "_record", record)
    window.add(revoked)
    window.add(lagged)
    assert window.latest() == revoked
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        pool(OWNER)

    # The operator advance loop has no new HTTP request. It still cannot
    # dispatch a retained queued child from the old owner's authority.
    adapter = object.__new__(LeanRecipeAdapter)
    adapter.contract_digest = "sha256:" + "7" * 64
    adapter.ledger = SimpleNamespace(submitted_outcomes=lambda _: ("rtsk_" + "1" * 64,))
    adapter.owner = lambda _: pool(OWNER).owner
    adapter._provider = lambda _: pytest.fail("revoked owner dispatched")
    assert adapter.advance() == 0
    pool.close()

    # Restarting against the lagged read cannot roll back the durable block.
    restarted_window = receiver.ReceiverSnapshotWindow(
        root, context, RECEIVER, clock=lambda: now
    )
    restarted_window.add(lagged)
    assert restarted_window.latest() is None
    restarted = receiver.OwnerProviders(
        owners,
        discovery,
        parent,
        tmp_path / "cache",
        **{**authority, "snapshot": lagged, "window": restarted_window},
    )
    restarted.restore()
    with pytest.raises(Unavailable, match="direct_provider_registration_unavailable"):
        restarted(OWNER)
    restarted.close()

    # A contradictory identity at the same finalized block fails closed,
    # including after another restart; only a higher block can recover it.
    restarted_window.add(replace(revoked, block_hash="0x" + "5" * 64))
    assert restarted_window.latest() is None
    conflicted = receiver.ReceiverSnapshotWindow(
        root, context, RECEIVER, clock=lambda: now
    )
    conflicted.add(revoked)
    assert conflicted.latest() is None
    recovered = replace(
        revoked,
        finalized_block=revoked.finalized_block + 1,
        block_hash="0x" + "6" * 64,
        timestamp_ms=int(now * 1000) + 3000,
    )
    conflicted.add(recovered)
    assert conflicted.latest() == recovered


@POSIX
def test_real_loopback_bootstrap_stages_and_admits_same_owner_without_model_dispatch(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _headers, _snapshot, _Verifier

    from carbon import research
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
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
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    monkeypatch.setattr(
        receiver,
        "installed_source",
        lambda _: (
            {"revision": "a" * 40, "source_tree_digest": "sha256:" + "6" * 64},
            parent,
            SimpleNamespace(context=context, publisher_hotkey=RECEIVER),
            tmp_path / "cache",
        ),
    )
    now = time.time_ns()
    snapshot = replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=context),
        timestamp_ms=now // 1_000_000,
    )
    reader = SimpleNamespace()

    async def capture(observed_context):
        assert observed_context == context
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
                context,
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
        view = research.load_canonical(
            db.execute("SELECT view FROM direct_tasks").fetchone()[0],
            research.DirectTaskViewV3,
        )
        assert view.state is research.DirectTaskStateV3.CANCELLED


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
