"""Prospective direct kit selection shares the Launchpad tools route."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_direct_submission import _recipe

from scripts.dev.miner_launchpad import runner, tool_door


def _bundle_recipe():
    from test_library_bundles import fixture

    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.library_bundles import bundle_ref

    manifest, source, wheels, lock, license_text = fixture()
    selected = bundle_ref(manifest, source, wheels, lock, license_text)
    definition = _recipe().to_dict()
    definition["source"] = {"kind": "bundle", "bundle_ref": selected.to_dict()}
    definition["procedure"]["entrypoint"] = {
        "module": "carbon_candidate.build",
        "name": "build",
    }
    return ConstructionRecipe.from_dict(definition)


@pytest.mark.parametrize(
    ("session", "version"),
    [
        (tool_door.DIRECT_DEVELOPMENT_SESSION, "1.2"),
        (tool_door.DIRECT_DEVELOPMENT_V13_SESSION, "1.3"),
    ],
)
def test_direct_browser_session_selects_exact_installed_kit(
    tmp_path, monkeypatch, session, version
):
    """The prospective alias adds 1.3 without changing the historical door."""
    configuration = tmp_path / "operator-profile.json"
    seen = []
    attached = object()

    @asynccontextmanager
    async def selected(path, *, version):
        seen.append((path, version))
        yield attached, object()

    monkeypatch.setattr(
        "carbon.miner_mcp.standard_cli.attached_installed_direct_development",
        selected,
    )
    target = {
        "intake_url": "http://127.0.0.1:9080",
        "receiver_hotkey": "5" + "a" * 47,
    }
    host = SimpleNamespace(
        configuration=configuration,
        _configuration=lambda: {"direct_intake_target": target},
    )

    async def open_selected():
        async with tool_door.runner_opener(host)(session) as actual:
            assert actual == tool_door.DirectToolsAttachment(attached, target)

    asyncio.run(open_selected())
    assert seen == [(Path(configuration), version)]

    class Host:
        def __init__(self):
            self.configuration = configuration
            self.tool_sessions = SimpleNamespace(open=self.open_session)

        def open_session(self, value, *, exclusive_token):
            assert value == session
            assert exclusive_token is None
            return {"open": True}

        def owned_campaign(self, _campaign):
            raise AssertionError("direct session must not open a product campaign")

    monkeypatch.setattr(runner, "RunnerAdapter", Host)
    assert tool_door.route(Host(), session, "open", {}) == {
        "campaign": session,
        "open": True,
    }


def test_real_mcp_factory_preserves_historical_launch_replay_shape():
    """The shared Operation contract must construct the actual MCP tools."""
    try:
        import mcp.server.mcpserver  # noqa: F401 - check the pinned SDK layout
    except ModuleNotFoundError:
        if os.environ.get("CARBON_REQUIRE_MCP") == "1":
            pytest.fail("Pinned MCP SDK required for Launchpad tool registration")
        pytest.skip("Pinned MCP SDK tool registration runs in canonical Linux")
    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    tools = {tool.name: tool for tool in make_operation_tools(object())}
    assert set(tools) == {"carbon_" + name for name in OPERATIONS}
    launch = tools["carbon_launch"]
    historical = OPERATIONS["launch"].replay_optional
    assert historical == frozenset(
        {"construction_level", "construction_variant_digest", "arm"}
    )
    assert historical.isdisjoint(launch.parameters["properties"])
    assert historical <= set(launch.fn_metadata.arg_model.model_fields)


def test_direct_v13_tools_action_uses_exact_installed_signer_and_pinned_receiver(
    tmp_path, monkeypatch
):
    from carbon.registry.model import ChallengeKey

    target = {
        "intake_url": "http://127.0.0.1:9080",
        "receiver_hotkey": "5" + "a" * 47,
    }
    connection = SimpleNamespace(miner_key=object(), chain_context=object())
    adapter = SimpleNamespace(
        challenge=ChallengeKey("synthetic-linear-field-2d", "1.3"),
        connection=connection,
        owner="owner-hotkey",
        composition=SimpleNamespace(
            tasks=SimpleNamespace(ledger=SimpleNamespace(root=tmp_path))
        ),
    )
    door = object.__new__(tool_door.DirectToolDoor)
    door.adapter, door.intake_target = adapter, target
    captured = []

    def submitted(url, signer, **kwargs):
        captured.append((url, signer, kwargs))
        return {"state": "RECONSTRUCTED", "task_id": "exact-task"}

    monkeypatch.setattr(
        "carbon.development_session.direct_submission.submit_and_wait", submitted
    )
    result = asyncio.run(door.submit_construction({"recipe": _recipe().to_dict()}))
    assert result["ok"] is True
    assert result["result"] == {"state": "RECONSTRUCTED", "task_id": "exact-task"}
    assert result["score_status"] == "SCORE_UNAVAILABLE"
    assert result["official_eligible"] is False
    assert len(captured) == 1
    assert captured[0][0] == target["intake_url"]
    assert captured[0][1] is connection.miner_key
    assert captured[0][2]["receiver"] == target["receiver_hotkey"]
    assert captured[0][2]["context"] is connection.chain_context
    assert captured[0][2]["recipe"].digest == _recipe().digest

    def staged(url, signer, **kwargs):
        captured.append((url, signer, kwargs))
        return {
            "schema": "carbon.construction.source-stage-result.v1",
            "complete": True,
        }

    monkeypatch.setattr(
        "carbon.development_session.direct_source_submission.stage_graph", staged
    )
    stage = asyncio.run(door.stage_construction_graph({"recipe": _recipe().to_dict()}))
    assert stage["ok"] is True and stage["official_eligible"] is False
    assert captured[1][0] == target["intake_url"]
    assert captured[1][1] is connection.miner_key
    assert captured[1][2]["owner"] == "owner-hotkey"
    assert captured[1][2]["ledger"] is adapter.composition.tasks.ledger
    assert captured[1][2]["receiver"] == target["receiver_hotkey"]

    def submit_session(campaign, value, *, exclusive_token):
        assert campaign == tool_door.DIRECT_DEVELOPMENT_V13_SESSION
        assert value["recipe"] == _recipe().to_dict()
        assert exclusive_token is None
        return result

    def stage_session(campaign, value, *, exclusive_token):
        assert campaign == tool_door.DIRECT_DEVELOPMENT_V13_SESSION
        assert value["recipe"] == _recipe().to_dict()
        assert exclusive_token is None
        return stage

    class Host:
        configuration = tmp_path / "operator-profile.json"
        tool_sessions = SimpleNamespace(
            submit_construction=submit_session,
            stage_construction_graph=stage_session,
        )

        def owned_campaign(self, _):
            raise AssertionError("construction submission must not open Battery")

    monkeypatch.setattr(runner, "RunnerAdapter", Host)
    assert (
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_V13_SESSION,
            "submit_construction",
            {"recipe": _recipe().to_dict()},
        )
        == result
    )
    assert (
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_V13_SESSION,
            "stage_construction_graph",
            {"recipe": _recipe().to_dict()},
        )
        == stage
    )
    from scripts.dev.miner_launchpad.controller import Rejected

    with pytest.raises(Rejected, match="construction_session_required"):
        tool_door.route(
            Host(),
            tool_door.DIRECT_DEVELOPMENT_SESSION,
            "stage_construction_graph",
            {"recipe": _recipe().to_dict()},
        )


def test_direct_v13_submission_and_staging_refuse_before_receiver_contact():
    from carbon.registry.model import ChallengeKey

    door = object.__new__(tool_door.DirectToolDoor)
    door.adapter = SimpleNamespace(
        challenge=ChallengeKey("synthetic-linear-field-2d", "1.3")
    )
    recipe = _recipe().to_dict()
    wrong_challenge = {**recipe, "challenge": {**recipe["challenge"], "version": "1.2"}}

    for operation in (door.submit_construction, door.stage_construction_graph):
        door.intake_target = None
        assert asyncio.run(operation({"recipe": recipe})) == {
            "ok": False,
            "error": "construction_intake_unconfigured",
        }

        # Neither malformed input nor a recipe bound to another Challenge
        # reaches the profile-pinned receiver.
        door.intake_target = {
            "intake_url": "http://127.0.0.1:9080",
            "receiver_hotkey": "5" + "a" * 47,
        }
        assert asyncio.run(operation({})) == {
            "ok": False,
            "error": "construction_recipe_required",
        }
        assert asyncio.run(operation({"recipe": wrong_challenge})) == {
            "ok": False,
            "error": "construction_recipe_challenge_mismatch",
        }


def test_direct_bundle_cli_uses_remote_signed_attachment(tmp_path, monkeypatch, capsys):
    from carbon.miner_mcp import standard_cli
    from carbon.registry.model import ChallengeKey

    profile = tmp_path / "profile.json"
    recipe_file = tmp_path / "recipe.json"
    recipe = _bundle_recipe()
    recipe_file.write_text(json.dumps(recipe.to_dict()), encoding="utf-8")
    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": "5" + "a" * 47}
    connection = SimpleNamespace(
        challenge=ChallengeKey("synthetic-linear-field-2d", "1.3"),
        miner_key=object(),
        chain_context=object(),
    )
    observed = []

    @asynccontextmanager
    async def attached(selected):
        assert selected == profile
        observed.append("entered")
        try:
            yield connection, target
        finally:
            observed.append("exited")

    def staged(url, signer, **kwargs):
        observed.append((url, signer, kwargs))
        return {"complete": True}

    monkeypatch.setattr(standard_cli, "attached_remote_material_stage", attached)
    monkeypatch.setattr(
        "carbon.development_session.direct_source_submission.stage_bundle", staged
    )
    result = asyncio.run(
        standard_cli.stage_installed_direct_bundle(profile, tmp_path, recipe_file)
    )
    assert result == {
        "ok": True,
        "result": {"complete": True},
        "official_eligible": False,
    }
    assert observed[0] == "entered" and observed[-1] == "exited"
    url, signer, passed = observed[1]
    assert url == target["intake_url"]
    assert signer is connection.miner_key
    assert passed["directory"] == tmp_path
    assert passed["recipe"].digest == recipe.digest
    assert passed["receiver"] == target["receiver_hotkey"]
    assert passed["context"] is connection.chain_context
    with pytest.raises(standard_cli.AttachRefused) as refused:
        asyncio.run(
            standard_cli.stage_installed_direct_bundle(
                profile, Path("relative"), recipe_file
            )
        )
    assert refused.value.code == "construction_bundle_directory_invalid"

    async def selected(*args):
        assert args == (profile, tmp_path, recipe_file)
        return result

    monkeypatch.setattr(standard_cli, "stage_installed_direct_bundle", selected)
    assert (
        standard_cli.main(
            [
                "--configuration",
                str(profile),
                "--direct-development",
                "--direct-version",
                "1.3",
                "--stage-bundle",
                str(tmp_path),
                "--recipe",
                str(recipe_file),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"]["complete"] is True


def test_remote_stage_attachment_needs_no_local_docker_or_image(tmp_path, monkeypatch):
    import contextlib

    from carbon.chain import external_signer
    from carbon.development_session import (
        direct_research_composition,
        intake_targets,
        miner_network,
        research_campaign,
    )
    from carbon.miner_mcp import standard_cli
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import controller, runner

    target = {"intake_url": "http://127.0.0.1:9080", "receiver_hotkey": "5" + "a" * 47}
    owner = "5" + "b" * 47
    public = {"netuid": standard_cli.CARBON_NETUID, "hotkey": owner}
    cfg = {
        "enabled": True,
        "campaigns_root": str(tmp_path),
        "principal": owner,
        "paths": {"miner_public": str(tmp_path / "public.json")},
        "direct_intake_target": target,
    }
    network = SimpleNamespace(
        netuid=standard_cli.CARBON_NETUID,
        context=object(),
        publisher_hotkey="5" + "c" * 47,
    )
    signer = object()
    events = []

    def poison(*args, **kwargs):
        raise AssertionError("remote signed upload touched local Docker/image loader")

    monkeypatch.setattr(standard_cli, "_direct_material", lambda version: dict)
    monkeypatch.setattr(standard_cli, "private_json", lambda path: cfg)
    monkeypatch.setattr(standard_cli, "load_direct_installed_source", poison)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(miner_network, "binding", lambda **kwargs: network)
    monkeypatch.setattr(
        research_campaign,
        "private_file",
        lambda path: SimpleNamespace(read_bytes=lambda: json.dumps(public).encode()),
    )
    monkeypatch.setattr(external_signer, "miner_signer", lambda value, socket: signer)
    monkeypatch.setattr(intake_targets, "validate", lambda values: values)
    monkeypatch.setattr(docker_runtime, "doctor", poison)
    monkeypatch.setattr(docker_runtime, "load_image_identity", poison)

    @contextlib.contextmanager
    def lock(path):
        events.append(("lock", path))
        try:
            yield
        finally:
            events.append(("unlock", path))

    class Connection:
        def __init__(self, **kwargs):
            self.challenge = SimpleNamespace(
                challenge_id="synthetic-linear-field-2d", version="1.3"
            )
            self.miner_key = kwargs["miner_key"]
            self.chain_context = kwargs["chain_context"]
            events.append(("connection", kwargs["root"]))

    async def requester(connection, challenge):
        events.append(("registered", challenge))
        return owner

    monkeypatch.setattr(controller, "owner_lock", lock)
    monkeypatch.setattr(
        direct_research_composition, "DirectDevelopmentConnection", Connection
    )
    monkeypatch.setattr(standard_cli, "_requester", requester)

    async def exercise():
        async with standard_cli.attached_remote_material_stage(
            tmp_path / "profile.json"
        ) as (connection, selected):
            assert connection.miner_key is signer
            assert connection.chain_context is network.context
            assert selected == target
            assert events[-1][0] == "registered"

    asyncio.run(exercise())
    assert [event[0] for event in events] == [
        "lock",
        "connection",
        "registered",
        "unlock",
    ]

    public["hotkey"] = "5" + "d" * 47
    with pytest.raises(standard_cli.AttachRefused) as wrong_owner:
        asyncio.run(exercise())
    assert wrong_owner.value.code == "registration_wrong_network"
    public["hotkey"] = owner

    network.netuid = standard_cli.CARBON_NETUID + 1
    with pytest.raises(standard_cli.AttachRefused) as wrong_chain:
        asyncio.run(exercise())
    assert wrong_chain.value.code == "registration_wrong_network"
    network.netuid = standard_cli.CARBON_NETUID

    cfg.pop("direct_intake_target")
    with pytest.raises(standard_cli.AttachRefused) as no_receiver:
        asyncio.run(exercise())
    assert no_receiver.value.code == "construction_intake_unconfigured"
    cfg["direct_intake_target"] = target

    async def wrong_registration(connection, challenge):
        return "5" + "e" * 47

    monkeypatch.setattr(standard_cli, "_requester", wrong_registration)
    with pytest.raises(standard_cli.AttachRefused) as changed_owner:
        asyncio.run(exercise())
    assert changed_owner.value.code == "campaign_owner_changed"
