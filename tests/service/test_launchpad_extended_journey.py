"""T04 stages9-15: existing Launchpad host through HTTP and the MCP SDK.

Fixtures only: published development keys, fake commitment chain, scripted
preparation/practice, throwaway loopback validators and tmp_path state.
No provider, real chain, Docker, production signer or host resource is used.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import test_launchpad_production_journey as production
from test_commitment_poster import signer as _signer
from test_launchpad_commitment import wired as _wired
from test_launchpad_truthful_refusals import journey as _commit_journey
from test_miner_signer_commit import short_dir as _short_dir

from carbon.battery import remote_submission as rs
from carbon.development_session import intake_targets
from carbon.development_session.profile import canonical, digest
from carbon.reconstruction import challenge_contracts as cc
from scripts.dev.miner_launchpad import budget_view
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.runner import FROZEN_ON_OLD_REVISION

# Reuse the original fixtures, including dependency names; no second executor.
signer = _signer
wired = _wired
short_dir = _short_dir
journey = _commit_journey
battery = production.battery
intake_battery = production.intake_battery
refs = production.refs


@pytest.fixture(params=["http", "mcp"])
def door(request):
    """The existing HTTP server or an actual MCP SDK client, over one host."""

    def connect(launchpad):
        if request.param == "http":
            server, token = launchpad.http()

            def call(operation, body):
                status, value = production.post(
                    server, token, "/api/v1/operations/" + operation, body
                )
                assert status == 200 or "error" in value, value
                return value

            return call

        from mcp import Client

        from carbon.development_session.chain_onboarding import carbon_testnet_context
        from carbon.miner_mcp.mcp_operations import make_operation_tools
        from carbon.miner_mcp.open_tier import create_open_tier_server

        server = create_open_tier_server(
            reader=production.Registered(), context=carbon_testnet_context()
        )
        for tool in make_operation_tools(launchpad.host):
            server._tool_manager._tools[tool.name] = tool

        def call(operation, body):
            async def exchange():
                async with Client(server, mode="legacy") as session:
                    result = await session.call_tool("carbon_" + operation, body)
                    if result.is_error:
                        return production.refusal_of(result)
                    return result.structured_content["payload"]

            return asyncio.run(exchange())

        return call

    return connect


def observed(call, identity):
    value = call("observe", {"campaign": identity})
    assert "error" not in value, value
    return value


def test_9_commitment_order_digest_and_same_tempo_through_doors(wired, tmp_path, door):
    from types import SimpleNamespace

    from test_launchpad_commitment import CONTRACT, frozen_campaign, join, root_of
    from test_launchpad_truthful_refusals import TOKEN, serve

    from carbon.battery.daemon import commitment_digest
    from scripts.dev.miner_launchpad.journey_fixture import FIXTURE_CHALLENGE

    host = wired.host
    identity = frozen_campaign(host)
    server, thread = serve(tmp_path, host)
    # Adapter only: HTTP and MCP still reach the original real host/gates.
    holder = SimpleNamespace(host=host, http=lambda: (server, TOKEN))
    try:
        call = door(holder)
        refused = call(
            "submit", {"campaign": identity, "idempotency_key": "t04-before-commit"}
        )
        assert refused["error"] == "commitment_required"
        assert refused["next_step"] == supervision.NEXT_ACTIONS["commitment_required"]
        assert (
            wired.chain.prepared
            == wired.chain.broadcasts
            == wired.signer.requests
            == []
        )
        chosen = json.loads(
            (root_of(host, identity) / "epoch-1/selected-recipe.json").read_bytes()
        )
        expected = commitment_digest(
            FIXTURE_CHALLENGE["id"], CONTRACT, digest(canonical(chosen["strategy"]))
        )
        admitted = call(
            "commit", {"campaign": identity, "idempotency_key": "t04-first-commit"}
        )
        assert admitted["commitment"]["digest"] == expected
        assert admitted["commitment"]["plan"]["needed"] is True
        join(host)
        first = observed(call, identity)
        assert first["commitment"]["state"] == "COMMITTED"
        assert wired.chain.prepared == [expected]
        assert len(wired.chain.broadcasts) == 1
        call(
            "commit",
            {
                "campaign": identity,
                "recommit": True,
                "idempotency_key": "t04-same-tempo-commit",
            },
        )
        join(host)
        refused = observed(call, identity)["last_refusal"]
        assert refused["code"] == "ALREADY_COMMITTED_THIS_TEMPO"
        assert refused["next_action"] == supervision.NEXT_ACTIONS[refused["code"]]
        assert len(wired.chain.broadcasts) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_10_receiver_mismatch_is_not_signed_or_admitted(
    intake_battery, tmp_path, monkeypatch, door
):
    from test_battery_intake import MINER, VALIDATOR
    from test_battery_intake_service_e2e import serving
    from test_battery_validator_service import throwaway

    from carbon.battery import intake
    from scripts.dev.miner_launchpad import prelaunch

    battery = intake_battery
    identity = production.practised_and_frozen(battery)
    made = throwaway(
        tmp_path / "receiver-validator",
        port=production.free_port(),
        intake_changes={"receiver": VALIDATOR.ss58_address},
    )
    signed = []

    def never_sign(*args, **kwargs):
        signed.append(True)
        raise AssertionError("receiver mismatch must refuse before signing")

    monkeypatch.setattr(rs, "_signed", never_sign)
    call = door(battery)
    with serving(made, chain=production.AdvancingChain()) as live:
        battery.cfg = {**battery.cfg, "intakes": {production.BATTERY: live.url}}
        warning = next(
            row
            for row in prelaunch.evaluation(battery.cfg)["challenges"]
            if row["challenge_id"] == production.BATTERY
        )
        assert warning["warning"] == "intake_receiver_not_pinned"
        assert warning["receiver_pinned"] is False and warning["next_step"]
        battery.cfg = {
            **battery.cfg,
            "receivers": {production.BATTERY: MINER.ss58_address},
        }
        accepted = call(
            "submit", {"campaign": identity, "idempotency_key": "t04-wrong-receiver"}
        )
        assert "error" not in accepted, accepted
        battery.join()
        view = observed(call, identity)
        assert view["last_refusal"]["code"] == "intake_receiver_mismatch"
        assert view["last_refusal"]["next_action"]
        assert view["journey"]["submitted_epochs"] == []
        assert view["journey"]["frozen_awaiting_submission"] is True
        assert intake.Inbox(live.config["inbox"]).counts() == {
            "RECEIVED": 0,
            "ADMITTED": 0,
            "REFUSED": 0,
        }
    assert signed == []
    assert not rs._record_path(battery.campaign_root(identity), 1).exists()


def test_11_two_paired_loopback_targets_keep_refusal_and_verdict_independent(
    intake_battery, tmp_path, refs, monkeypatch, door
):
    from test_battery_intake import OTHER, VALIDATOR, signed
    from test_battery_intake_service_e2e import open_pool, serving
    from test_battery_validator_service import throwaway

    from carbon.battery import deployment, intake, multi_intake

    battery = intake_battery
    identity = production.practised_and_frozen(battery)
    empty_commitments = production.CommitmentStandIn()
    monkeypatch.setattr(
        deployment, "_commitment_reader", lambda config: empty_commitments
    )
    refused = throwaway(
        tmp_path / "refusing-validator",
        port=production.free_port(),
        deployment_changes={"require_commitment": True},
        intake_changes={"receiver": VALIDATOR.ss58_address},
    )
    admitted = throwaway(
        tmp_path / "admitting-validator",
        port=production.free_port(),
        deployment_changes={"rule": "v2"},
        intake_changes={"receiver": OTHER.ss58_address},
    )
    open_pool(refused, refs)
    open_pool(admitted, refs)
    receivers = {key.ss58_address: key for key in (VALIDATOR, OTHER)}
    signed_receivers = []

    def sign(key, facts, body):
        signed_receivers.append(facts["receiver"])
        return signed(key, body, receiver=receivers[facts["receiver"]])

    monkeypatch.setattr(rs, "_signed", sign)
    call = door(battery)
    with (
        serving(refused, chain=production.AdvancingChain()) as first,
        serving(admitted, chain=production.AdvancingChain()) as second,
    ):
        pairs = [
            {"intake_url": first.url, "receiver_hotkey": VALIDATOR.ss58_address},
            {"intake_url": second.url, "receiver_hotkey": OTHER.ss58_address},
        ]
        battery.cfg = {**battery.cfg, "intake_targets": {production.BATTERY: pairs}}
        result = call(
            "submit", {"campaign": identity, "idempotency_key": "t04-multi-submit"}
        )
        assert "error" not in result, result
        battery.join()
        view = observed(call, identity)
        assert view["last_refusal"] is None, view["last_refusal"]
        assert intake.Inbox(first.config["inbox"]).counts()["REFUSED"] == 1
        assert intake.Inbox(second.config["inbox"]).counts()["ADMITTED"] == 1
        # Both actual intake transport journals survive, including the
        # refusing target; a refusal is not a fabricated admission record.
        for live in (first, second):
            assert Path(live.config["transport_journal"]).is_file()
            assert Path(live.config["inbox"]).is_file()
    root = battery.campaign_root(identity)
    directories = [intake_targets.journal(root, pair) for pair in pairs]
    assert directories[0] != directories[1] and all(
        path.is_dir() for path in directories
    )
    # Both transports return202 and retain their own submission identity.
    # The worker subsequently refuses one at admission;202 is not a verdict.
    for directory, pair in zip(directories, pairs):
        record = json.loads(rs._record_path(directory, 1).read_bytes())
        assert record["url"] == pair["intake_url"]
        assert record["epoch"] == 1 and record["submission_id"]
    assert rs._record_path(directories[0], 1) != rs._record_path(directories[1], 1)
    saved = json.loads((root / "epoch-1" / multi_intake.STATUS_NAME).read_bytes())
    assert saved["outcome"] == {"state": "MULTI_VALIDATOR"}
    assert [row["state"] for row in saved["validators"]] == ["REFUSED", "SCORED"]
    assert saved["validators"][0]["code"] == "commitment_required"
    assert set(signed_receivers) == set(receivers)
    (shown,) = view["final_results"]
    assert shown["status"] == "MULTI_VALIDATOR_OUTCOME"
    assert [row["state"] for row in shown["validators"]] == ["REFUSED", "SCORED"]
    assert shown["validators"][0]["code"] == "commitment_required"
    assert "score" not in shown and shown["reward"] is False
    assert not shown["qualification"]
    public = json.dumps(shown)
    for hidden in ("important_score", '"score"', "seed", "pool_version"):
        assert hidden not in public, hidden
    assert shown["validators"][1]["result"]["sealed"] is True
    assert (
        "screening" not in shown["validators"][1]["result"]
        or shown["validators"][1]["result"]["screening"] is None
    )
    assert call("campaign_view", {"campaign": identity})["outcomes"]


@pytest.fixture
def ladder_facts_server():
    """Only the loopback ladder facts transport; not a validator/verdict stand-in."""
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    state = {
        "challenge": {"id": production.BATTERY},
        "served_contracts": [],
        "tools": [],
    }

    class Facts(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Facts)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def read(address):
        assert address == url
        with urllib.request.urlopen(address, timeout=10) as response:
            return json.load(response)

    try:
        yield url, state, read
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_12_new_level_hints_do_not_downgrade_the_current_composition(battery, door):
    from carbon.development_session import construction_level as cl
    from scripts.dev.miner_launchpad import levels

    call = door(battery)
    expected = cl.resolve_composition(production.BATTERY)
    assert expected is not None
    for level in (1, 2, 3):
        result = call(
            "launch",
            {
                "agent": "none",
                "challenge": production.BATTERY,
                "challenge_version": "1.0",
                "construction_level": level,
                "idempotency_key": f"t04-composition-hint-{level}",
            },
        )
        assert "error" not in result, result
        battery.join()
        with battery.host.db() as db:
            row = dict(
                db.execute(
                    "SELECT * FROM launchpad_campaigns WHERE id=?", (result["id"],)
                ).fetchone()
            )
        # This fixture's preparation omits the manifest's level argument.
        # Inspect the writer-owned admission directly, authenticating both
        # the saved request and its version/digest rather than a substitute.
        recorded = json.loads(row["launch_request"])
        captured = levels.checked_capture(row, recorded[levels.CONSTRUCTION_ADMISSION])
        found = levels.replay_binding(
            recorded,
            {"id": recorded["challenge"], "version": recorded["challenge_version"]},
            recorded["agent"],
            battery.cfg,
            captured,
        )
        assert found["kind"] == cl.COMPOSITION
        assert found["digest"] == expected["digest"]


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_12_historical_level_target_gates_precede_signing(
    battery, monkeypatch, door, ladder_facts_server, level
):
    """Explicit historical admission fixture; never revive legacy new-launch selection.

    The original handoff's L1-L3 selectors predate default composition. Keep
    historical frozen variants covered, and separately assert the current
    composition behavior above. This tests pre-sign door gates, not a real
    level verdict or security acceptance.
    """
    from carbon.battery import campaign as battery_campaign
    from carbon.development_session import construction_level as cl
    from scripts.dev.miner_launchpad import levels

    url, facts, read = ladder_facts_server
    found = cl.with_target(cl.resolve(production.BATTERY, level), url)
    entry = {key: found[key] for key in ("level", "variant", "digest")}
    facts["served_contracts"] = [entry]
    battery.cfg = {**battery.cfg, "intakes": {production.BATTERY: url}}
    battery.host.read_intake_facts = read
    monkeypatch.setattr(cl, "READ_TARGET", lambda challenge, address: read(address))
    binding = levels.launch_binding
    manifest = battery_campaign.manifest_document

    def historical_binding(*args, **kwargs):
        return binding(*args, **{**kwargs, "legacy": True})

    def level_manifest(*args, **kwargs):
        return manifest(*args, **{**kwargs, "construction_level": found})

    # Adapt only this test's preparation to the existing live prepare's
    # construction_level argument; no shared production-journey fixture edit.
    with monkeypatch.context() as setup:
        setup.setattr(levels, "launch_binding", historical_binding)
        setup.setattr(battery_campaign, "manifest_document", level_manifest)
        call = door(battery)
        launched = call(
            "launch",
            {
                "agent": "none",
                "challenge": production.BATTERY,
                "challenge_version": "1.0",
                "construction_level": level,
                "idempotency_key": f"t04-legacy-level-{level}",
            },
        )
        assert "error" not in launched, launched
        battery.join()
    identity = launched["id"]
    assert battery.view(identity)["state"] == "READY"
    facts["served_contracts"] = []
    absent = call("commit", {"campaign": identity})
    assert absent["error"] == "level_not_served_by_target"
    assert absent["next_step"] == supervision.NEXT_ACTIONS[absent["error"]]
    facts["served_contracts"] = [entry]
    if level == 4:
        refused = call("commit", {"campaign": identity})
        assert refused["error"] == "level4_envelope_transport_unavailable"
        assert refused["next_step"] == supervision.NEXT_ACTIONS[refused["error"]]
    else:
        # Correct served facts pass the target gate and reach the distinct
        # unfrozen-candidate gate. The response cannot be a manufactured PASS.
        next_gate = call("commit", {"campaign": identity})
        assert next_gate["error"] == "freeze_a_candidate_first"
    assert battery.view(identity)["in_flight"] is None
    assert not (battery.campaign_root(identity) / "commitment-request.json").exists()


def test_13_cpu_practice_refuses_torch_before_worker_and_keeps_jax(
    battery, monkeypatch, door
):
    from test_battery_intake_service_e2e import TORCH

    from carbon.battery.research import BatteryPractice

    invoked = []
    original = BatteryPractice.__call__

    def practice(self, identity, strategy):
        invoked.append(strategy)
        assert strategy.get("parameters", {}).get("backend", "jax") != "pytorch"
        return original(self, identity, strategy)

    monkeypatch.setattr(BatteryPractice, "__call__", practice)
    identity = battery.launch("t04-torch-scope-launch")
    call = door(battery)
    before = battery.ledger(identity).status(owner=battery.owner(identity))["used"][
        "research_trials"
    ]
    call(
        "practice",
        {
            "campaign": identity,
            "strategy": TORCH,
            "hypothesis": "scope negative control",
            "idempotency_key": "t04-torch-practice",
        },
    )
    battery.join()
    view = observed(call, identity)
    assert view["last_refusal"] is None
    assert view["refusals"][-1]["correction_code"] == "backend_not_served"
    assert view["refusals"][-1]["field"] == "strategy_json"
    assert view["refusals"][-1]["authority_granted"] is False
    assert invoked == []
    assert (
        battery.ledger(identity).status(owner=battery.owner(identity))["used"][
            "research_trials"
        ]
        == before
    )
    call(
        "practice",
        {
            "campaign": identity,
            "strategy": production.KNN,
            "hypothesis": "existing JAX practice remains available",
            "idempotency_key": "t04-jax-practice",
        },
    )
    battery.join()
    view = observed(call, identity)
    assert view["last_refusal"] is None, view["last_refusal"]
    assert view["completed_experiments"] == 1 and invoked == [production.KNN]


def test_14_old_revision_submit_is_typed_and_preserves_frozen_candidate(battery, door):
    identity = production.practised_and_frozen(battery)
    root = battery.campaign_root(identity)
    frozen = (root / "epoch-1/selected-recipe.json").read_bytes()
    manifest = (root / "campaign-manifest.json").read_bytes()
    battery.cfg = {
        **battery.cfg,
        "accepted_revision": "b" * 40,
        "runtime": {**battery.cfg["runtime"], "implementation": {"revision": "b" * 40}},
    }
    call = door(battery)
    refused = call(
        "submit", {"campaign": identity, "idempotency_key": "t04-old-revision-submit"}
    )
    assert refused["error"] == FROZEN_ON_OLD_REVISION
    assert refused["next_step"] == supervision.NEXT_ACTIONS[FROZEN_ON_OLD_REVISION]
    battery.join()
    view = observed(call, identity)
    assert view["in_flight"] is None and view["state"] != "INTERRUPTED"
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True
    assert (root / "epoch-1/selected-recipe.json").read_bytes() == frozen
    assert (root / "campaign-manifest.json").read_bytes() == manifest
    assert not (root / "interruptions.jsonl").exists()


def test_15_budget_status_is_admissions_own_verdict_without_invented_numbers(
    battery, door
):
    call = door(battery)
    budget_view._status.cache_clear()
    try:
        expected = cc.budget_status(production.BATTERY, production.KNN)
        assert expected["status"] == "NOT_SET"
        assert (
            cc.check_compute_budget(cc.CONTRACTS[production.BATTERY], production.KNN)
            is None
        )
        value = call(
            "budget_status",
            {"challenge": production.BATTERY, "strategy": production.KNN},
        )
        assert value == expected
        assert all(value[key] is None for key in ("unit", "used", "allowed", "within"))
    finally:
        budget_view._status.cache_clear()
