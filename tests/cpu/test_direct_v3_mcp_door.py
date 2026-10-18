"""The direct-v3 MCP tool registration uses the authenticated task service.

This exercises real SDK signing and typed MCP tool calls with a retained
terminal task. The worker is not run and no official authority is earned.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import sqlite3
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_v3_durable_tasks import _fixture
from test_direct_v3_user_door import _sdk

from carbon import research
from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.auth import BittensorHotkeyVerifier, BittensorMessageSigner
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
from carbon.development_session.bundle_construction_worker import direct_child_identity
from carbon.development_session.direct_research_composition import (
    DirectDevelopmentConnection,
    compose_synthetic_direct_development,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_image import LibraryWorkerImage
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.development_session.research_tools import (
    DIRECT_PREFIX,
    DirectResearchMinerTools,
)
from carbon.miner_mcp.standard_cli import (
    AttachRefused,
    DirectDevelopmentAttachment,
    _guard_previous_direct_parents,
    _requester,
    attached_direct_development,
    attached_installed_direct_development,
    cleanup_installed_direct_development,
    load_direct_installed_source,
    refusal_code,
)
from carbon.miner_mcp.standard_cli import (
    main as miner_mcp_main,
)
from carbon.miner_mcp.standard_server import _create_direct_server
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal
from scripts.dev.miner_launchpad.tool_door import DirectToolDoor
from tests.cpu._signer_harness import in_thread_signer


class _Adapter:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def observe(self, *, minimum_finalized_block):
        del minimum_finalized_block
        return self.snapshot


def test_parent_switch_refuses_retained_running_until_original_root_reconciles(
    tmp_path, monkeypatch
):
    request, original, discovery = _fixture(tmp_path, monkeypatch)
    fixed = original()
    image, parent = fixed.image, fixed.inference_image
    fixed.close()
    previous = tmp_path / "kit-1.1" / parent.image_id[7:]
    selected = tmp_path / "kit-1.1" / ("5" * 64)
    ledger = CampaignLedger(previous / "ledger")

    def prior_provider():
        return DirectDevelopmentTasksV3(
            root=previous / "direct-tasks",
            requester="miner",
            ledger=ledger,
            owner="miner",
            discovery=discovery,
            image=image,
            inference_image=parent,
        )

    prior = prior_provider()
    running = prior.start_research_task(request).task
    prior._transition(running, research.DirectTaskStateV3.RUNNING)
    with (
        pytest.raises(AttachRefused) as active,
        _guard_previous_direct_parents(selected),
    ):
        pytest.fail("a live prior supervisor cannot be bypassed")
    assert active.value.code == "direct_previous_parent_unresolved"
    prior.close()
    with (
        pytest.raises(AttachRefused) as refusal,
        _guard_previous_direct_parents(selected),
    ):
        pytest.fail("a retained RUNNING task cannot be bypassed")
    assert refusal.value.code == "direct_previous_parent_unresolved"
    reconciled = prior_provider()
    assert (
        reconciled.get_research_result(
            research.DirectGetTaskRequestV3(request.challenge_key, running.task_id)
        ).task.state
        is research.DirectTaskStateV3.FAILED_INFRA
    )
    reconciled.close()
    with _guard_previous_direct_parents(selected):
        pass
    child = direct_child_identity(running.task_id.value, "build")
    with ledger.db() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
            (
                child,
                "miner",
                "research",
                "sha256:" + "8" * 64,
                "RESERVED",
                b"{}",
                None,
                None,
                1.0,
            ),
        )
    with (
        pytest.raises(AttachRefused) as reserved,
        _guard_previous_direct_parents(selected),
    ):
        pytest.fail("an old RESERVED child cannot be bypassed")
    assert reserved.value.code == "direct_previous_parent_unresolved"
    with ledger.db() as db:
        db.execute("UPDATE operations SET state='FAILED_INFRA' WHERE id=?", (child,))
    with _guard_previous_direct_parents(selected):
        pass


class _Connection:
    def __init__(self, gateway, snapshot, signer):
        self.chain_context = gateway.context
        self.publisher = gateway.receiver
        self.miner_key = signer
        self.service = SimpleNamespace(gateway=gateway)
        self.snapshot = snapshot

    async def check_registration(self):
        return self.snapshot

    async def check_cleanup_registration(self):
        return self.snapshot


@pytest.mark.parametrize("version", ["1.1", "1.2"])
def test_direct_development_connection_uses_live_signed_gateway(
    tmp_path, monkeypatch, version
):
    """The trusted connection uses the maintained reader and socket signer."""
    keypair = _sdk()
    miner = keypair.create_from_uri("//Alice")
    publisher = keypair.create_from_uri("//Bob")
    context = ChainContext(
        CARBON_NETWORK,
        "ws://127.0.0.1:9944",
        "dev",
        "0x" + "1" * 64,
        CARBON_NETUID,
    )
    snapshot = MetagraphSnapshot(
        context,
        10,
        "0x" + "2" * 64,
        time.time_ns() // 1_000_000,
        (
            Participant(0, publisher.ss58_address, "publisher-cold", 1),
            Participant(1, miner.ss58_address, "miner-cold", 2),
        ),
    )

    async def capture(_reader, received_context):
        assert received_context == context
        return snapshot

    monkeypatch.setattr("carbon.chain.sdk.BittensorReader.capture", capture)
    with in_thread_signer(miner) as signer:
        connection = DirectDevelopmentConnection(
            root=tmp_path / "direct-auth",
            version=version,
            chain_context=context,
            publisher=publisher.ss58_address,
            miner_key=signer,
        )
        assert connection.challenge.version == version
        assert connection.service.gateway.challenge == connection.challenge
        assert asyncio.run(
            _requester(connection, challenge=connection.challenge)
        ) == digest(
            canonical(
                [
                    "carbon.authenticated.requester.v1",
                    context.genesis_hash,
                    context.netuid,
                    miner.ss58_address,
                    "miner-cold",
                    2,
                ]
            )
        ).removeprefix(
            "sha256:"
        )
        assert connection.transport.path.is_file()


def _signed_probe(gateway, snapshot, signer, challenge):
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(challenge),
    )
    body = message(
        gateway.context,
        snapshot.snapshot_id,
        challenge,
        session="direct-v3-mcp",
        request="direct-mcp-bootstrap-1",
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode(
                "ascii"
            )
        },
    )
    headers = BittensorMessageSigner(signer).sign(
        body, receiver=gateway.receiver, nonce_ns=time.time_ns()
    )
    return asyncio.run(gateway.receive(body, headers)).requester.value


def test_direct_v3_typed_mcp_discovery_and_retained_task(tmp_path, monkeypatch):
    keypair = _sdk()
    miner = keypair.create_from_uri("//Alice")
    validator = keypair.create_from_uri("//Bob")
    context = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)
    request, provider, _discovery = _fixture(tmp_path, monkeypatch)
    now = time.time_ns()
    snapshot = MetagraphSnapshot(
        context,
        10,
        "0x" + "2" * 64,
        now // 1_000_000,
        (
            Participant(0, validator.ss58_address, "validator-cold", 1),
            Participant(1, miner.ss58_address, "miner-cold", 2),
        ),
    )
    gateway = AuthenticatedGateway(
        context,
        request.challenge_key,
        validator.ss58_address,
        _Adapter(snapshot),
        BittensorHotkeyVerifier(),
        ReceiptJournal(tmp_path / "transport.sqlite3", context),
    )
    with in_thread_signer(miner) as signer:
        owner = _signed_probe(gateway, snapshot, signer, request.challenge_key)
        tasks = provider(owner)
        try:
            started = tasks.start_research_task(request)
            task_id = started.task.task_id
            tasks.cancel_research_task(
                research.DirectCancelTaskRequestV3(
                    request.challenge_key, task_id, "direct-mcp-cancel-001"
                )
            )
            image, inference_image, ledger = (
                tasks.image,
                tasks.inference_image,
                tasks.ledger,
            )
            tasks.close()
            composition, wrapper = compose_synthetic_direct_development(
                version="1.1",
                root=tmp_path / "tasks",
                owner=owner,
                ledger=ledger,
                image=image,
                inference_image=inference_image,
                gateway=gateway,
            )
            tasks = composition.tasks
            adapter = DirectResearchMinerTools(
                connection=_Connection(gateway, snapshot, signer),
                wrapper=wrapper,
                composition=composition,
                owner=owner,
            )
            signed_info = asyncio.run(
                adapter.call("get_challenge_info", {}, "direct-mcp-read-info-001")
            )
            assert signed_info["reply"]["status"] == "OK"
            unbound_recipe = {
                **request.recipe,
                "source": {
                    "kind": "bundle",
                    "bundle_ref": {
                        **request.recipe["source"]["bundle_ref"],
                        "bundle_digest": "sha256:" + "9" * 64,
                    },
                },
            }
            refused_start = asyncio.run(
                adapter.call(
                    "start_research_task",
                    {"recipe": unbound_recipe},
                    "direct-mcp-bad-start-001",
                )
            )
            assert refused_start["reply"]["status"] != "OK"
            assert refused_start["task"] is None
            assert tasks.queued_tasks() == ()
            signed_observation = asyncio.run(
                adapter.call(
                    "get_research_result",
                    {"task_id": task_id.value},
                    "direct-mcp-read-task-001",
                )
            )
            assert signed_observation["task"]["state"] == "CANCELLED"

            async def attached_read():
                binding = DirectDevelopmentAttachment(
                    root=tmp_path,
                    version="1.1",
                    owner=owner,
                    connection=_Connection(gateway, snapshot, signer),
                    ledger=ledger,
                    image=image,
                    inference_image=inference_image,
                )
                async with attached_direct_development(binding) as (bound, selected):
                    assert selected is binding
                    return await bound.call(
                        "get_challenge_info", {}, "direct-attached-read-001"
                    )

            attached_info = asyncio.run(attached_read())
            assert attached_info["reply"]["status"] == "OK"
            if importlib.util.find_spec("mcp") is None:
                if os.environ.get("CARBON_REQUIRE_MCP") == "1":
                    pytest.fail("Pinned MCP SDK required for direct tool registration")
                pytest.skip("Pinned MCP SDK registration runs in canonical Linux")
            server = _create_direct_server(adapter)
            tools = {item.name: item for item in asyncio.run(server.list_tools())}
            assert set(tools) == {
                DIRECT_PREFIX + operation
                for operation in composition.tasks.discovery.manifest.supported_operations
            }
            assert all(not name.startswith("carbon_research_v2__") for name in tools)
            assert set(
                tools[DIRECT_PREFIX + "start_research_task"].input_schema["properties"]
            ) == {"operation_id", "recipe"}
            from mcp.server.mcpserver.exceptions import ToolError

            with pytest.raises(ToolError):
                asyncio.run(
                    server.call_tool(
                        DIRECT_PREFIX + "start_research_task",
                        {"recipe": request.recipe, "bundle_path": "/tmp/other"},
                    )
                )

            info = asyncio.run(
                server.call_tool(DIRECT_PREFIX + "get_challenge_info", {})
            ).structured_content
            assert info["reply"]["status"] == "OK"
            assert (
                info["reply"]["result"]["public_train_digest"]
                == request.public_train_digest
            )
            manifest = asyncio.run(
                server.call_tool(DIRECT_PREFIX + "get_interaction_manifest", {})
            ).structured_content
            assert manifest["reply"]["status"] == "OK"
            assert (
                "start_research_task"
                in manifest["reply"]["result"]["supported_operations"]
            )

            observed = asyncio.run(
                server.call_tool(
                    DIRECT_PREFIX + "get_research_result",
                    {"task_id": task_id.value},
                )
            ).structured_content
            assert observed["task"]["state"] == "CANCELLED"
            assert observed["task"]["task_id"]["value"] == task_id.value
            assert observed["public_result"] is None
            assert observed["requires_reconciliation"] is False
            assert observed["official_eligible"] is False

            cancelled = asyncio.run(
                server.call_tool(
                    DIRECT_PREFIX + "cancel_research_task",
                    {"task_id": task_id.value},
                )
            ).structured_content
            assert cancelled["reply"]["result"]["disposition"] == "TOO_LATE"
            assert cancelled["task"]["state"] == "CANCELLED"

            door = DirectToolDoor(adapter)
            assert door.describe()["development_only"] is True
            page = asyncio.run(door.observe(task_id.value))
            assert page["ok"] is True
            assert page["task"]["taskId"] == task_id.value
            assert page["task"]["status"] == "cancelled"
            assert page["task"]["official_eligible"] is False
        finally:
            tasks.close()


def test_direct_v3_mcp_requires_exact_composition():
    """A caller or ordinary v2 adapter cannot mount direct operations."""
    with pytest.raises(TypeError, match="trusted direct-v3"):
        _create_direct_server(SimpleNamespace())


def test_installed_direct_development_uses_profile_signer_and_refuses_missing_child(
    tmp_path, monkeypatch, capsys
):
    """A normal installed profile creates the real signed connection."""
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK
    from carbon.development_session import (
        gpu_practice,
        miner_network,
        research_campaign,
        research_image,
    )
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS, validated_profile

    request, fixed_provider, discovery = _fixture(tmp_path, monkeypatch)
    fixed = fixed_provider()
    parent = fixed.inference_image
    old_image = fixed.image
    gpu_parent = replace(
        parent, image_id="sha256:" + "5" * 64, config_digest="sha256:" + "5" * 64
    )
    other_gpu_parent = replace(
        parent, image_id="sha256:" + "6" * 64, config_digest="sha256:" + "6" * 64
    )
    fixed.close()
    keypair = _sdk()
    miner = keypair.create_from_uri("//Alice")
    publisher = keypair.create_from_uri("//Bob")
    context = ChainContext(
        CARBON_NETWORK,
        "ws://127.0.0.1:9944",
        "dev",
        "0x" + "1" * 64,
        CARBON_NETUID,
    )
    snapshot = MetagraphSnapshot(
        context,
        10,
        "0x" + "2" * 64,
        time.time_ns() // 1_000_000,
        (
            Participant(0, publisher.ss58_address, "publisher-cold", 1),
            Participant(1, miner.ss58_address, "miner-cold", 2),
        ),
    )

    async def capture(_reader, received_context):
        assert received_context == context
        return snapshot

    monkeypatch.setattr("carbon.chain.sdk.BittensorReader.capture", capture)
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        lambda _revision: {"source_tree_digest": parent.source_tree_digest},
    )
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: (
            other_gpu_parent
            if path.name == "other-gpu-worker-image.json"
            else gpu_parent if path.name == "gpu-worker-image.json" else parent
        ),
    )
    monkeypatch.setattr(gpu_practice, "gpu_image_backend", lambda _image: "jax")
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **_kwargs: SimpleNamespace(eligible=True),
    )
    monkeypatch.setattr(
        research_image,
        "load_analysis_image",
        lambda _path: SimpleNamespace(parent_image=parent.image_id),
    )
    monkeypatch.setattr(research_image, "verify_image", lambda _image: None)
    monkeypatch.setattr(
        miner_network,
        "binding",
        lambda **_kwargs: SimpleNamespace(
            netuid=CARBON_NETUID,
            context=context,
            publisher_hotkey=publisher.ss58_address,
        ),
    )
    owner_root = tmp_path / "campaigns"
    owner_root.mkdir(mode=0o700)
    public_path = tmp_path / "miner-public.json"
    public_path.write_text(
        json.dumps({"netuid": CARBON_NETUID, "hotkey": miner.ss58_address}),
        encoding="utf-8",
    )
    public_path.chmod(0o600)
    with in_thread_signer(miner) as signer:
        paths = {field: str(tmp_path / field) for field in PATH_FIELDS}
        paths.update(
            operator_config=str(tmp_path / "operator-config.json"),
            signer_socket=str(signer._path),
            miner_public=str(public_path),
        )
        configuration = tmp_path / "runner-profile.json"
        cfg = {
            "schema": "carbon.launchpad.runner-profile.v2",
            "profile_id": "direct-development-test",
            "principal": miner.ss58_address,
            "enabled": True,
            "paths": paths,
            "accepted_revision": "a" * 40,
            "campaigns_root": str(owner_root),
            "gpu_image": str(tmp_path / "gpu-worker-image.json"),
            "runtime": {
                "implementation": {"revision": "a" * 40},
                "gpu_research": {},
            },
        }
        assert validated_profile(cfg) == cfg
        target = {
            "intake_url": "http://127.0.0.1:9080",
            "receiver_hotkey": publisher.ss58_address,
        }
        assert (
            validated_profile({**cfg, "direct_intake_target": target})[
                "direct_intake_target"
            ]
            == target
        )
        with pytest.raises(ValueError, match="receiver-paired"):
            validated_profile(
                {**cfg, "direct_intake_target": {**target, "receiver_hotkey": "bad"}}
            )
        configuration.write_bytes(canonical(cfg))
        configuration.chmod(0o600)
        source = load_direct_installed_source(configuration, version="1.1")
        assert source.parent == gpu_parent
        assert gpu_parent.image_id[7:] in source.root.parts
        assert source.signer.ss58_address == miner.ss58_address
        other_configuration = tmp_path / "other-runner-profile.json"
        other_cfg = {
            **cfg,
            "gpu_image": str(tmp_path / "other-gpu-worker-image.json"),
        }
        assert validated_profile(other_cfg) == other_cfg
        other_configuration.write_bytes(canonical(other_cfg))
        other_configuration.chmod(0o600)
        other_source = load_direct_installed_source(other_configuration, version="1.1")
        assert other_source.root != source.root
        assert other_source.cache_root == source.cache_root
        with monkeypatch.context() as stale:
            stale_gpu_parent = replace(
                gpu_parent, source_tree_digest="sha256:" + "7" * 64
            )
            stale.setattr(
                docker_runtime,
                "load_image_identity",
                lambda path: (
                    stale_gpu_parent if path.name == "gpu-worker-image.json" else parent
                ),
            )
            with pytest.raises(ValueError) as error:
                load_direct_installed_source(configuration, version="1.1")
            assert "exact accepted source revision" in str(error.value)
            assert refusal_code(error.value) == "carbon_updated_rerun_installer"

        async def signed_missing_child():
            async with attached_installed_direct_development(
                configuration, version="1.1"
            ) as (adapter, selected):
                info = await adapter.call(
                    "get_challenge_info", {}, "installed-direct-info-001"
                )
                missing = await adapter.call(
                    "start_research_task",
                    {"recipe": request.recipe},
                    "installed-direct-missing-001",
                )
                assert adapter.composition.tasks.queued_tasks() == ()
                return info, missing, selected.owner

        info, missing, old_owner = asyncio.run(signed_missing_child())
        assert info["reply"]["status"] == "OK"
        assert missing["reply"]["status"] != "OK"
        assert missing["task"] is None
        assert "REFERENCE_NOT_FOUND" in json.dumps(missing["reply"])

        old_ledger = CampaignLedger(source.root / "ledger")
        installed_child = LibraryWorkerImage(
            replace(old_image.provisioned, parent_image=gpu_parent.image_id),
            gpu_parent,
            old_image.bundle_ref,
        )
        old_tasks = DirectDevelopmentTasksV3(
            root=source.root / "direct-tasks",
            requester=old_owner,
            ledger=old_ledger,
            owner=old_owner,
            discovery=discovery,
            image=None,
            inference_image=gpu_parent,
            image_resolver=lambda _bundle: installed_child,
        )
        started = old_tasks.start_research_task(request).task
        old_tasks._transition(started, research.DirectTaskStateV3.RUNNING)
        old_tasks.close()
        other_ledger = CampaignLedger(other_source.root / "ledger")
        other_child = LibraryWorkerImage(
            replace(old_image.provisioned, parent_image=other_gpu_parent.image_id),
            other_gpu_parent,
            old_image.bundle_ref,
        )
        other_tasks = DirectDevelopmentTasksV3(
            root=other_source.root / "direct-tasks",
            requester=old_owner,
            ledger=other_ledger,
            owner=old_owner,
            discovery=discovery,
            image=None,
            inference_image=other_gpu_parent,
            image_resolver=lambda _bundle: other_child,
        )
        second = other_tasks.start_research_task(request).task
        other_tasks._transition(second, research.DirectTaskStateV3.RUNNING)
        other_tasks.close()
        # A failed registration may leave a parent but never create a task
        # store. It sorts before both retained roots and must not hide them.
        empty_root = source.root.parent / ("0" * 64)
        empty_root.mkdir()
        (empty_root / "research-auth").mkdir()
        empty_db_root = source.root.parent / ("1" * 64)
        empty_db_ledger = CampaignLedger(empty_db_root / "ledger")
        empty_parent = replace(
            gpu_parent,
            image_id="sha256:" + "1" * 64,
            config_digest="sha256:" + "1" * 64,
        )
        empty_db_tasks = DirectDevelopmentTasksV3(
            root=empty_db_root / "direct-tasks",
            requester=old_owner,
            ledger=empty_db_ledger,
            owner=old_owner,
            discovery=discovery,
            image=None,
            inference_image=empty_parent,
            image_resolver=lambda _bundle: installed_child,
        )
        empty_db_tasks.close()
        child = direct_child_identity(started.task_id.value, "build")
        with old_ledger.db() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    child,
                    old_owner,
                    "research",
                    "sha256:" + "8" * 64,
                    "RESERVED",
                    b"{}",
                    None,
                    None,
                    1.0,
                ),
            )

        from carbon.development_session import research_carrier

        def settle_old_child(ledger, *, owner, identity):
            assert (owner, identity) == (old_owner, child)
            with ledger.db() as db:
                db.execute(
                    "UPDATE operations SET state='FAILED_INFRA' WHERE id=?", (identity,)
                )

        with monkeypatch.context() as upgrade:
            upgrade.setattr(research_carrier, "reconcile_worker", settle_old_child)
            upgrade.setattr(
                research_campaign,
                "accepted_implementation",
                lambda _revision: {"source_tree_digest": "sha256:" + "9" * 64},
            )
            with pytest.raises(ValueError) as old_refusal:
                load_direct_installed_source(configuration, version="1.1")
            assert refusal_code(old_refusal.value) == "carbon_updated_rerun_installer"
            with (
                pytest.raises(AttachRefused) as switch,
                _guard_previous_direct_parents(other_source.root),
            ):
                pytest.fail("unfinished old parent cannot be bypassed")
            assert switch.value.code == "direct_previous_parent_unresolved"
            (empty_root / "direct-tasks").mkdir()
            with pytest.raises(AttachRefused) as partial:
                asyncio.run(cleanup_installed_direct_development(configuration))
            assert partial.value.code == "direct_previous_parent_unresolved"
            (empty_root / "direct-tasks").rmdir()
            empty_ledger = CampaignLedger(empty_root / "ledger")
            with empty_ledger.db() as db:
                db.execute(
                    "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        "terminal-old-operation",
                        old_owner,
                        "research",
                        "sha256:" + "8" * 64,
                        "FAILED_INFRA",
                        b"{}",
                        None,
                        None,
                        1.0,
                    ),
                )
            with pytest.raises(AttachRefused) as ledger_custody:
                asyncio.run(cleanup_installed_direct_development(configuration))
            assert ledger_custody.value.code == "direct_previous_parent_unresolved"
            with empty_ledger.db() as db:
                db.execute("DELETE FROM operations WHERE id='terminal-old-operation'")
            cleanup = asyncio.run(cleanup_installed_direct_development(configuration))
            assert cleanup == {
                "status": "DIRECT_CLEANUP_COMPLETE",
                "retained_tasks_checked": 2,
            }
            empty_db_store = empty_db_root / "direct-tasks" / "direct-tasks.sqlite3"
            for table, body in (
                ("direct_task_images", "orphan-image"),
                ("direct_evidence", b"orphan-evidence"),
            ):
                with sqlite3.connect(empty_db_store) as db:
                    db.execute(
                        f"INSERT INTO {table} VALUES(?,?)", ("orphan-task", body)
                    )
                with pytest.raises(AttachRefused) as orphan:
                    asyncio.run(cleanup_installed_direct_development(configuration))
                assert orphan.value.code == "direct_previous_parent_unresolved"
                with sqlite3.connect(empty_db_store) as db:
                    db.execute(f"DELETE FROM {table} WHERE id='orphan-task'")
            with empty_db_ledger.db() as db:
                db.execute(
                    "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        "settled-no-task",
                        old_owner,
                        "research",
                        "sha256:" + "8" * 64,
                        "FAILED_INFRA",
                        b"{}",
                        None,
                        None,
                        1.0,
                    ),
                )
            with pytest.raises(AttachRefused) as settled:
                asyncio.run(cleanup_installed_direct_development(configuration))
            assert settled.value.code == "direct_previous_parent_unresolved"
            with empty_db_ledger.db() as db:
                db.execute("DELETE FROM operations WHERE id='settled-no-task'")
            missing_ledger = empty_db_ledger.path.with_suffix(".missing")
            empty_db_ledger.path.rename(missing_ledger)
            try:
                with pytest.raises(AttachRefused) as missing:
                    asyncio.run(cleanup_installed_direct_development(configuration))
                assert missing.value.code == "direct_previous_parent_unresolved"
            finally:
                missing_ledger.rename(empty_db_ledger.path)
        assert old_ledger.operation_state(child, owner=old_owner) == "FAILED_INFRA"
        with _guard_previous_direct_parents(other_source.root):
            pass
        old_store = source.root / "direct-tasks" / "direct-tasks.sqlite3"
        with sqlite3.connect(old_store) as db:
            binding = db.execute(
                "SELECT identity FROM direct_binding WHERE id=1"
            ).fetchone()[0]
            changed = json.loads(binding)
            changed[1] = "different-owner"
            db.execute(
                "UPDATE direct_binding SET identity=? WHERE id=1",
                (json.dumps(changed),),
            )
        with pytest.raises(AttachRefused) as wrong_owner:
            asyncio.run(cleanup_installed_direct_development(configuration))
        assert wrong_owner.value.code == "direct_previous_parent_unresolved"
        with sqlite3.connect(old_store) as db:
            db.execute("UPDATE direct_binding SET identity=? WHERE id=1", (binding,))
            image_binding = db.execute(
                "SELECT identity FROM direct_task_images"
            ).fetchone()[0]
            db.execute("UPDATE direct_task_images SET identity='malformed'")
        with pytest.raises(AttachRefused) as malformed:
            asyncio.run(cleanup_installed_direct_development(configuration))
        assert malformed.value.code == "direct_previous_parent_unresolved"
        with sqlite3.connect(old_store) as db:
            db.execute("UPDATE direct_task_images SET identity=?", (image_binding,))
        assert (
            miner_mcp_main(
                [
                    "--configuration",
                    str(configuration),
                    "--direct-development",
                    "--cleanup-only",
                ]
            )
            == 0
        )
        assert (
            json.loads(capsys.readouterr().out)["status"] == "DIRECT_CLEANUP_COMPLETE"
        )

        with monkeypatch.context() as upgraded:
            new_source = "sha256:" + "9" * 64
            new_base = replace(
                parent,
                image_id="sha256:" + "a" * 64,
                config_digest="sha256:" + "a" * 64,
                source_tree_digest=new_source,
            )
            new_gpu = replace(
                other_gpu_parent,
                image_id="sha256:" + "b" * 64,
                config_digest="sha256:" + "b" * 64,
                source_tree_digest=new_source,
            )
            upgraded.setattr(
                research_campaign,
                "accepted_implementation",
                lambda _revision: {"source_tree_digest": new_source},
            )
            upgraded.setattr(
                docker_runtime,
                "load_image_identity",
                lambda path: (
                    new_gpu if path.name == "other-gpu-worker-image.json" else new_base
                ),
            )
            upgraded.setattr(
                research_image,
                "load_analysis_image",
                lambda _path: SimpleNamespace(parent_image=new_base.image_id),
            )
            updated_configuration = tmp_path / "updated-runner-profile.json"
            updated_cfg = {
                **other_cfg,
                "accepted_revision": "b" * 40,
                "runtime": {
                    "implementation": {"revision": "b" * 40},
                    "gpu_research": {},
                },
            }
            assert validated_profile(updated_cfg) == updated_cfg
            updated_configuration.write_bytes(canonical(updated_cfg))
            updated_configuration.chmod(0o600)

            async def attached_after_cleanup():
                async with attached_installed_direct_development(
                    updated_configuration, version="1.1"
                ) as (adapter, _selected):
                    return await adapter.call(
                        "get_challenge_info", {}, "after-direct-cleanup-001"
                    )

            assert asyncio.run(attached_after_cleanup())["reply"]["status"] == "OK"

        if importlib.util.find_spec("mcp") is None:
            if os.environ.get("CARBON_REQUIRE_MCP") == "1":
                pytest.fail("Pinned MCP SDK required for direct HTTP route")
            return
        import threading

        from test_miner_launchpad import auth
        from test_miner_launchpad import request as http_request

        from scripts.dev.miner_launchpad import controller
        from scripts.dev.miner_launchpad.runner import RunnerAdapter

        runner = RunnerAdapter(tmp_path / "runner.sqlite3", configuration=configuration)
        server = controller.Server(
            controller.Controller(tmp_path / "controller.sqlite3"),
            "x" * 40,
            port=0,
            research_runner=runner,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            from carbon.challenge_kit.synthetic_linear_field_2d import (
                bundle_material_v4,
            )

            path = "/api/v1/tools/direct-development"
            code, _, body = http_request(server, path, headers=auth())
            assert code == 200 and json.loads(body)["open"] is False
            code, _, body = http_request(server, path + "/open", "POST", {}, auth())
            assert code == 200, body
            opened = json.loads(body)
            assert opened["development_only"] is True
            assert opened["challenge"]["version"] == "1.2"
            code, _, body = http_request(
                server,
                path + "/start",
                "POST",
                {
                    "arguments": {
                        "recipe": {
                            **request.recipe,
                            "challenge": bundle_material_v4()["construction_kit"],
                        },
                        "operation_id": "direct-http-missing-child-001",
                    }
                },
                auth(),
            )
            assert code == 200, body
            refused = json.loads(body)
            assert refused["result"]["task"] is None
            assert b"REFERENCE_NOT_FOUND" in body
            assert http_request(server, path + "/close", "POST", {}, auth())[0] == 200
        finally:
            server.shutdown()
            server.server_close()
            runner.close()
