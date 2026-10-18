"""The page and agent see registered public choices, never guessed opening."""

from types import SimpleNamespace

import pytest

from carbon.battery.unified_contract import contract
from carbon.development_session.unified_construction import (
    UnifiedContract,
    classify,
    digest,
)
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from scripts.dev.miner_launchpad import construction_options as options
from scripts.dev.miner_launchpad import construction_paths, operations, runner
from scripts.dev.miner_launchpad.controller import Rejected


def test_all_registered_changes_are_visible_and_missing_checks_keep_them_closed():
    registered = contract()
    shown = options.build(registered)
    assert shown["ceiling"] is None and not shown["qualification"]
    assert shown["types"][0]["type"] == "parameters"
    assert shown["types"][0]["availability"] == "coming_soon"
    assert {row["type"] for row in shown["types"][1:]} == {
        row["type"] for row in registered.facts()["types"]
    }
    assert all(
        row["availability"] == "coming_soon" and row["reason"]
        for row in shown["types"][1:]
    )
    assert shown["unified_digest"] == registered.digest
    assert shown["launch_mode"] == "composition_bound"


def test_raw_contract_and_unregistered_serving_claims_never_create_availability():
    registered = contract()
    with pytest.raises(ValueError):
        options.build(registered.document)
    shown = options.build(
        registered, [{**registered.facts(), "unified_digest": "sha256:" + "0" * 64}]
    )
    assert shown["submission_path_available"] is False
    # An unregistered serving identity cannot create availability.
    assert all(row["availability"] == "coming_soon" for row in shown["types"][1:])


def test_receiver_mismatch_is_not_treated_as_a_served_contract():
    cfg = {
        "intake_targets": {
            BATTERY_CHALLENGE: [
                {
                    "intake_url": "https://fixture.example.test",
                    "receiver_hotkey": "5" + "A" * 47,
                }
            ]
        }
    }
    public = {**contract().facts(), "receiver": "another receiver"}
    shown = options.for_profile(cfg, lambda url: public)[BATTERY_CHALLENGE]
    assert shown["submission_path_available"] is False
    assert not shown["qualification"]


def test_options_operation_exposes_the_same_document_the_page_reads(monkeypatch):
    cfg = {"paths": {}, "runtime": {}}
    host = runner.RunnerAdapter.__new__(runner.RunnerAdapter)
    # Find the executable implementation's method without initializing a host.
    monkeypatch.setattr(host, "configured", lambda: cfg)
    monkeypatch.setattr(host, "read_intake_facts", lambda url: {})
    monkeypatch.setattr(host, "_model_providers", lambda cfg: [])
    monkeypatch.setattr(runner, "graphite_options", lambda cfg: {})
    shown = host.options_admitted(SimpleNamespace(), {})
    assert shown["schema"] == "carbon.launchpad.launch-options.v2"
    assert shown["construction_paths"] == construction_paths.for_challenges()
    assert "construction_options" not in shown


def test_launch_retires_level_fields_for_new_keys_but_keeps_historical_replay_shape():
    launch = operations.OPERATIONS["launch"]
    retired = {"construction_level", "construction_variant_digest", "arm"}
    assert retired <= launch.replay_optional
    assert retired.isdisjoint(launch.optional)
    operations._closed(
        launch,
        {
            "profile": "p",
            "agent": "none",
            "idempotency_key": "fixture-schema-preservation",
            "construction_level": 2,
        },
    )


@pytest.mark.parametrize("field", ["width", "depth"])
@pytest.mark.parametrize("operation", ["dry_validate", "compile_strategy"])
def test_v3_notice_is_added_to_the_shared_public_result_without_changing_admission(
    tmp_path,
    operation,
    field,
):
    import json

    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.development_session.research_tools import ResearchMinerTools

    manifest = {
        "challenge": challenge_ref(BATTERY_CHALLENGE),
        "construction_level": {"variant": "battery-l4-graph-v3"},
    }
    (tmp_path / "campaign-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=None,
        ledger=SimpleNamespace(root=tmp_path),
        owner="fixture",
    )
    strategy = {"parameters": {"composition_graphs": "sha256:" + "1" * 64, field: 16}}
    args = {"strategy_json": json.dumps(strategy)}
    original = {"result": {"accepted": True, "issues": []}}
    answer = sdk._construction_result(operation, args, original)
    (notice,) = answer["result"]["construction_notices"]
    assert notice["fields"] == [field]
    assert notice["blocking"] is False
    assert notice["text"] == (
        "width and depth are ignored at Level 4: the graph sets the layers. "
        "They'll be refused from graph-v4."
    )
    assert answer["result"]["accepted"] is True and answer["result"]["issues"] == []
    assert original == {"result": {"accepted": True, "issues": []}}
    # Negative controls: no graph, no inert fields, v4 or another operation.
    assert (
        sdk._construction_result(
            operation,
            {"strategy_json": json.dumps({"parameters": {field: 16}})},
            original,
        )
        is original
    )
    assert (
        sdk._construction_result(
            operation,
            {
                "strategy_json": json.dumps(
                    {"parameters": {"composition_graphs": "sha256:" + "1" * 64}}
                )
            },
            original,
        )
        is original
    )
    assert sdk._construction_result("inspect_resources", args, original) is original
    manifest["construction_level"]["variant"] = "battery-l4-graph-v4"
    (tmp_path / "campaign-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    assert sdk._construction_result(operation, args, original) is original


def test_pre_sign_preview_uses_the_same_classifier_and_stops_changed_construction(
    monkeypatch,
):
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": {
            "steps": 48,
            "width": 16,
            "depth": 1,
            "muon_spectral": True,
            "optimizer_family": "muon",
        },
    }
    answer = classify(strategy, contract())
    assert answer["refusal"] is not None
    host = runner.RunnerAdapter.__new__(runner.RunnerAdapter)
    with pytest.raises(Rejected) as refused:
        host._design_refusal(strategy)
    assert refused.value.code == answer["refusal"]


def test_sdk_validate_notice_crosses_the_page_and_mcp_doors(tmp_path, monkeypatch):
    """Real SDK result assembly and both external doors; transport is a fixture."""
    import asyncio
    import base64
    import copy
    import json

    from carbon import research
    from carbon.battery.challenge import CHALLENGE
    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.development_session import research_tools
    from carbon.miner_mcp.standard_server import _create_server
    from carbon.research.service import dry_validation_result
    from scripts.dev.miner_launchpad import tool_door
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner
    from scripts.dev.miner_launchpad.tool_fixture import FixtureTools, fixture_adapter

    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": {
            "composition_graphs": "sha256:" + "1" * 64,
            "width": 16,
            "depth": 1,
        },
    }
    manifest = {
        "challenge": challenge_ref(BATTERY_CHALLENGE),
        "construction_level": {"variant": "battery-l4-graph-v3"},
    }
    (tmp_path / "campaign-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    request = research.DryValidateRequest(CHALLENGE, strategy)
    reply = research.ServiceReply(
        research.ReplyStatus.OK, dry_validation_result(request, ())
    )
    public = {"result": {"valid": True, "issues": []}}

    class Connection:
        miner_key, chain_context, publisher = object(), object(), "fixture"

        async def check_registration(self):
            return SimpleNamespace(snapshot_id="fixture")

    class Wrapper:
        async def supervised_call(self, *args, **kwargs):
            return {
                "protocol_reply_base64": base64.b64encode(
                    research.canonical_bytes(reply)
                ),
                "terminal_observation_base64": None,
                "public_result": public,
                "requires_reconciliation": False,
            }

    sdk = research_tools.ResearchMinerTools(
        connection=Connection(),
        wrapper=Wrapper(),
        composition=SimpleNamespace(challenge=CHALLENGE),
        ledger=SimpleNamespace(root=tmp_path),
        owner="fixture",
    )
    monkeypatch.setattr(sdk, "_request", lambda *args: request)
    monkeypatch.setattr(research_tools, "message", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        research_tools,
        "BittensorMessageSigner",
        lambda key: SimpleNamespace(sign=lambda *args, **kwargs: {}),
    )
    output = asyncio.run(
        sdk._call(
            research_tools.PREFIX + "dry_validate",
            {"strategy_json": json.dumps(strategy)},
            "engineering-notice-01",
        )
    )
    assert output["reply"]["status"] == "OK"
    (notice,) = output["public_result"]["result"]["construction_notices"]
    assert notice["fields"] == ["width", "depth"] and not notice["blocking"]
    assert output["public_result"]["result"]["valid"] is True
    fixture = FixtureRunner()
    adapter = fixture_adapter(FixtureTools(fixture), fixture.principal)

    async def call(*args, **kwargs):
        return copy.deepcopy(output)

    monkeypatch.setattr(adapter._sdk, "call", call)
    args = {"operation_id": "page-0123456789abcdef01234567", "strategy": strategy}
    page = asyncio.run(
        tool_door.ToolDoor(adapter).call(research_tools.PREFIX + "dry_validate", args)
    )
    mcp = asyncio.run(
        _create_server(adapter).call_tool(research_tools.PREFIX + "dry_validate", args)
    )
    assert page == {"ok": True, "result": mcp.structured_content}
    assert page["result"]["payload"]["public_result"]["result"][
        "construction_notices"
    ] == [notice]


def test_v3_notice_leaves_freeze_and_submit_guards_unchanged(tmp_path, monkeypatch):
    """Fixture compiler and signer; real freeze pin checks and part transport."""
    from test_launchpad_level4_parts import (
        PART_TOOLS,
        STRATEGY,
        URL,
        LadderIntake,
        _facts,
        _level,
        _submit,
    )

    from carbon.battery import campaign, remote_submission
    from carbon.development_session import construction_level as cl

    found = cl.with_target(_level(4), URL)
    assert found["variant"] == "battery-l4-graph-v3"
    chosen = {**STRATEGY, "parameters": {**STRATEGY["parameters"], "depth": 1}}
    (notice,) = campaign.construction_notices(chosen, found)
    assert notice["blocking"] is False and notice["fields"] == ["width", "depth"]
    monkeypatch.setattr(cl, "READ_TARGET", lambda *args: _facts(found, PART_TOOLS))
    spawned = []

    def compile_fixture(request):
        spawned.append(request["op"])
        return {
            "ok": True,
            "variant": found["variant"],
            "variant_digest": found["digest"],
            "envelope": "fixture envelope",
        }

    monkeypatch.setattr(cl, "RUN", compile_fixture)
    cl._compiled.cache_clear()
    try:
        compiled, envelope = cl.check_freeze(found, chosen, "fixture lowered directory")
        assert compiled["variant_digest"] == found["digest"]
        assert envelope == "fixture envelope" and spawned == ["compile", "level4"]
        monkeypatch.setattr(
            remote_submission,
            "_signed",
            lambda signer, facts, body: {"X-Fixture-Signed": signer},
        )
        intake = LadderIntake(tmp_path, found)
        status, answer, submission = _submit(tmp_path, intake, found, strategy=chosen)
        assert (status, answer["state"], submission) == (200, "SCORED", "sub-1")
        assert "battery_submit" in intake.tools()
        # The display notice cannot weaken the existing exact variant pin.
        cl._compiled.cache_clear()
        monkeypatch.setattr(
            cl,
            "RUN",
            lambda request: {
                "ok": True,
                "variant": found["variant"],
                "variant_digest": "sha256:" + "0" * 64,
            },
        )
        with pytest.raises(cl.LevelRefused) as refused:
            cl.check_freeze(found, chosen, "fixture lowered directory")
        assert refused.value.code == cl.NOT_REGISTERED
    finally:
        cl._compiled.cache_clear()


def _ready_contract(ceiling=None):
    # Synthetic preview data remains structurally DEVELOPMENT_SHADOW_ONLY;
    # it never reaches an intake, deployment, signer or scoring authority.
    doc = contract().document
    doc["ceiling"] = ceiling
    for row in doc["types"]:
        # Every obsolete permission flag stays closed, even on serving fixtures.
        row["within_ceiling"] = False
        for arm in row["arms"]:
            arm["external_allowed"] = False
        for check in row["checks"]:
            check["status"] = "PASS"
        row["registration_digest"] = digest(
            {k: row[k] for k in ("type", "label", "fields", "arms")}
        )
    return UnifiedContract(doc)


@pytest.mark.parametrize("ceiling", [None, 0, 2, 4])
def test_served_checked_changes_are_available_without_ceiling_or_external_permission(
    ceiling,
):
    registered = _ready_contract(ceiling)
    without_route = options.build(registered)
    assert all(
        row["availability"] == "coming_soon" for row in without_route["types"][1:]
    )
    serving = options.build(registered, [_composition_facts(registered)])
    assert all(row["availability"] == "available" for row in serving["types"])
    assert all(row["open"] == "INTERNAL" for row in serving["types"][1:])
    assert all(not row["within_ceiling"] for row in serving["types"][1:])
    assert all("ceiling" not in row["reason"] for row in serving["types"])
    assert not serving["qualification"]


@pytest.mark.parametrize("status", ["FAIL", "UNAVAILABLE"])
def test_required_check_refusal_names_the_change_and_check_without_closing_peers(
    status,
):
    document = _ready_contract().document
    blocked = document["types"][0]
    blocked["checks"][0]["status"] = status
    registered = UnifiedContract(document)
    shown = options.build(registered, [_composition_facts(registered)])
    row = shown["types"][1]
    assert row["availability"] == "coming_soon"
    assert row["label"] in row["reason"]
    assert blocked["checks"][0]["id"] in row["reason"]
    assert "ceiling" not in row["reason"] and "scope" not in row["reason"]
    assert all(row["availability"] == "available" for row in shown["types"][2:])
    assert not shown["qualification"]


@pytest.mark.parametrize("mutation", ["digest", "types", "absent"])
def test_ready_checks_do_not_bypass_missing_or_mismatched_serving_identity(mutation):
    registered = _ready_contract()
    facts = _composition_facts(registered)
    if mutation == "digest":
        facts["served_contracts"][0]["digest"] = "sha256:" + "0" * 64
    elif mutation == "types":
        facts["served_contracts"][0]["variant"] = "unregistered-name"
    else:
        facts = None
    shown = options.build(registered, [facts])
    assert not shown["submission_path_available"]
    for row in shown["types"][1:]:
        assert row["availability"] == "coming_soon"
        assert row["label"] in row["reason"] and "validator" in row["reason"]
    assert not shown["qualification"]


def test_receiver_binding_still_controls_ready_options(monkeypatch):
    from carbon.battery import unified_contract

    registered = _ready_contract()
    monkeypatch.setattr(unified_contract, "contract", lambda: registered)
    receiver = "5" + "A" * 47
    cfg = {
        "intake_targets": {
            BATTERY_CHALLENGE: [
                {
                    "intake_url": "https://fixture.example.test",
                    "receiver_hotkey": receiver,
                }
            ]
        }
    }
    for found_receiver, expected in [
        (receiver, "available"),
        ("another receiver", "coming_soon"),
    ]:
        shown = options.for_profile(
            cfg,
            lambda url, receiver=found_receiver: {
                **_composition_facts(registered),
                "receiver": receiver,
            },
        )[BATTERY_CHALLENGE]
        assert all(row["availability"] == expected for row in shown["types"][1:])
        assert not shown["qualification"]


def test_missing_contract_is_explicit_and_never_a_successful_empty_catalog(monkeypatch):
    from carbon.battery import unified_contract

    def missing():
        raise OSError("fixture private path must not be disclosed")

    monkeypatch.setattr(unified_contract, "contract", missing)
    shown = options.for_profile({})[BATTERY_CHALLENGE]
    assert shown["status"] == "PUBLIC_CONTRACT_UNAVAILABLE"
    assert shown["types"] == [] and shown["ceiling"] is None
    assert "private path" not in str(shown)


def _composition_facts(registered):
    from carbon.reconstruction import development_composition as dc

    found = dc.load(registered.document["challenge"])
    return {
        **registered.facts(),
        "served_contracts": [
            {
                "kind": "composition",
                "level": None,
                "variant": found.version,
                "digest": found.digest,
            }
        ],
    }


def test_old_shadow_facts_do_not_advertise_the_new_composition_route():
    registered = _ready_contract()
    shown = options.build(registered, [registered.facts()])
    assert not shown["submission_path_available"]
    assert all(row["availability"] == "coming_soon" for row in shown["types"])
    shown = options.build(contract(), [_composition_facts(contract())])
    assert shown["submission_path_available"]
    assert all(row["availability"] == "coming_soon" for row in shown["types"][1:])
