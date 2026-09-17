"""Readable tool SDK binds the real versioned B-07 contracts without inference."""

from types import SimpleNamespace

import pytest

from carbon import research
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import (
    FIELDS,
    PREFIX,
    TOOLS,
    ResearchMinerTools,
    _json,
    public_wire,
)


def test_tool_surface_is_the_existing_twelve_namespaced_operations():
    assert [t["name"] for t in TOOLS] == [
        PREFIX + x for x in research.SUPPORTED_OPERATIONS
    ]
    assert set(FIELDS) == set(research.SUPPORTED_OPERATIONS)
    assert all(t["strict"] for t in TOOLS)
    assert "submit" not in FIELDS


def test_sdk_constructs_workspace_and_real_recipe_requests(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner="miner",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=ledger,
        owner="miner",
    )
    req = sdk._request(
        "start_research_task",
        {
            "kind": "workspace",
            "strategy_json": None,
            "action": "inventory",
            "arguments_json": "{}",
            "hypothesis": "inspect available own files",
            "expected_effect": "find public inputs",
        },
        "engineering-test-task-0001",
    )
    assert type(req.task_spec) is research.DevelopmentWorkspaceTaskSpecV1
    assert req.training_support_ref == composition.discovery.info.training_support_ref
    assert req.requested_resource_class_ref == composition.inspection.resource_class_ref
    assert (
        research.load_canonical(
            research.canonical_bytes(req), research.StartResearchTaskRequest
        )
        == req
    )
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": {"steps": 512, "enforce_mean": True},
    }
    practice = sdk._request(
        "start_research_task",
        {
            "kind": "practice",
            "strategy_json": canonical(strategy).decode(),
            "action": None,
            "arguments_json": None,
            "hypothesis": "preserve the initial mean",
            "expected_effect": "small mean defect",
        },
        "engineering-practice-0001",
    )
    assert type(practice.task_spec) is research.PracticeTaskSpec
    assert practice.task_spec.strategy == strategy
    with pytest.raises(ValueError):
        sdk._request("inspect_prior_alignment", {"strategy_json": "{}"}, "prior")
    assert public_wire(req)["task_spec"]["action"] == "inventory"
    with pytest.raises(ValueError):
        public_wire(object())
    composition.tasks.close()


@pytest.mark.parametrize("raw", ["[]", '{"a":1,"a":2}', '{"a":NaN}', "x" * 17000])
def test_json_arguments_reject_duplicate_nonfinite_or_unbounded_values(raw):
    with pytest.raises(ValueError):
        _json(raw)


def test_authenticated_sdk_waits_for_owned_real_workspace_task(tmp_path, monkeypatch):
    import asyncio
    import base64

    from test_c08_authenticated_miner_mcp import (
        CONTEXT,
        NOW,
        _Adapter,
        _headers,
        _snapshot,
        _Verifier,
    )

    from carbon.development_session import research_tools
    from carbon.development_session.profile import CHALLENGE
    from carbon.development_session.research_material import PublicMaterial
    from carbon.miner_mcp.research import AuthenticatedResearchService
    from carbon.transport.gateway import AuthenticatedGateway
    from carbon.transport.models import message
    from carbon.transport.store import ReceiptJournal

    ledger = CampaignLedger(tmp_path / "ledger")
    snapshot = _snapshot()
    gateway = AuthenticatedGateway(
        CONTEXT,
        CHALLENGE,
        "validator",
        _Adapter(snapshot),
        _Verifier(),
        ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        clock_ns=lambda: NOW,
    )
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(CHALLENGE),
    )
    body = message(
        CONTEXT,
        snapshot.snapshot_id,
        CHALLENGE,
        session="test",
        request="bootstrap-request",
        tool=research.RESEARCH_NAMESPACE,
        fields={
            "call_base64": base64.b64encode(research.canonical_bytes(call)).decode()
        },
    )
    owner = asyncio.run(gateway.receive(body, _headers(body, NOW))).requester.value
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner=owner,
        image=SimpleNamespace(),
        public_material=PublicMaterial(None),
        practice=lambda *args: None,
    )

    class Connection:
        chain_context = CONTEXT
        publisher = "validator"
        miner_key = object()

        async def check_registration(self):
            return snapshot

    class Signer:
        nonce = NOW

        def __init__(self, key):
            pass

        def sign(self, body, **kwargs):
            Signer.nonce += 1
            return _headers(body, Signer.nonce)

    monkeypatch.setattr(research_tools, "BittensorMessageSigner", Signer)
    wrapper = AuthenticatedResearchService(gateway, {owner: composition.service})
    sdk = ResearchMinerTools(
        connection=Connection(),
        wrapper=wrapper,
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    info = asyncio.run(
        sdk.call(PREFIX + "get_challenge_info", {}, "engineering-info-0001")
    )
    assert info["reply"]["status"] == "OK"
    result = asyncio.run(
        sdk.call(
            PREFIX + "start_research_task",
            {
                "kind": "workspace",
                "strategy_json": None,
                "action": "public_material",
                "arguments_json": '{"name":"objective"}',
                "hypothesis": "understand the permitted objective",
                "expected_effect": "read the public score and limits",
            },
            "engineering-start-0001",
        )
    )
    assert result["terminal_task"]["state"] == "SUCCEEDED"
    assert (
        result["public_result"]["result"]["document"]["score_rule"]["id"]
        == "burgers-development-balanced-v2"
    )
    assert not result["requires_reconciliation"]
    assert ledger.status(owner=owner)["used"]["provider_attempts"] == 0
    assert ledger.status(owner=owner)["used"]["research_trials"] == 0
    composition.tasks.close()


def test_invalid_trial_is_counted_and_returns_repairable_feedback(tmp_path):
    import asyncio

    from test_cw1_research_ledger import ledger as make_ledger

    meter = make_ledger(tmp_path)
    sdk = ResearchMinerTools(
        connection=None, wrapper=None, composition=None, ledger=meter, owner="alice"
    )
    args = {
        "kind": "practice",
        "strategy_json": "{}",
        "action": None,
        "arguments_json": None,
        "hypothesis": "invalid input",
        "expected_effect": "no execution",
        "extra": True,
    }
    result = asyncio.run(sdk.call(PREFIX + "start_research_task", args, "bad-trial"))
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert meter.status(owner="alice")["used"]["research_trials"] == 1
    assert (
        asyncio.run(sdk.call(PREFIX + "start_research_task", args, "bad-trial"))[
            "status"
        ]
        == result["status"]
    )
    assert meter.status(owner="alice")["used"]["research_trials"] == 1
    note = meter.status(owner="alice")["notes"][0]["body"]
    assert note["hypothesis"] == "invalid input"
    assert note["authority_granted"] is False


@pytest.mark.parametrize(
    ("kind", "strategy", "action", "arguments", "code"),
    [
        (
            "practice",
            None,
            "run_python",
            '{"source":"PRIVATE_SENTINEL"}',
            "practice_recipe_required",
        ),
        ("practice", None, None, None, "practice_recipe_required"),
        ("workspace", "{}", "run_python", "{}", "workspace_recipe_forbidden"),
    ],
)
def test_task_kind_mismatch_returns_safe_correction_without_dispatch(
    tmp_path, kind, strategy, action, arguments, code
):
    import asyncio

    from test_cw1_research_ledger import ledger as make_ledger

    meter = make_ledger(tmp_path)
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: pytest.fail("rejected request executed"),
        practice=lambda *a: pytest.fail("rejected request executed"),
    )
    # No connection/signer/provider exists: rejection must precede authentication
    # and task dispatch. The proposal remains charged in the original ledger.
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    args = {
        "kind": kind,
        "strategy_json": strategy,
        "action": action,
        "arguments_json": arguments,
        "hypothesis": "Inspect public input shapes",
        "expected_effect": "Choose a useful practice recipe",
    }
    try:
        first = asyncio.run(
            sdk.call(PREFIX + "start_research_task", args, "mixed-kind")
        )
        replay = asyncio.run(
            sdk.call(PREFIX + "start_research_task", args, "mixed-kind")
        )
        assert first == replay
        assert first["status"] == "REJECTED_BEFORE_DISPATCH"
        assert first["reason"] == "contract_incompatibility"
        assert first["correction_code"] == code
        assert "kind=workspace" in first["correction"]
        assert first["authority_granted"] is False
        assert "PRIVATE_SENTINEL" not in canonical(first).decode()
        status = meter.status(owner="alice")
        assert status["used"]["research_trials"] == 1
        assert status["used"]["provider_attempts"] == 0
        assert status["used"]["numerical_milliseconds"] == 0
        assert status["notes"][0]["body"]["minimal_safe_design"] == first["correction"]
        # The hint describes an already supported route; it grants no new API.
        corrected = {
            **args,
            "kind": "workspace",
            "strategy_json": None,
            "action": "inventory",
            "arguments_json": "{}",
        }
        request = sdk._request("start_research_task", corrected, "corrected-kind-0001")
        assert type(request.task_spec) is research.DevelopmentWorkspaceTaskSpecV1
    finally:
        composition.tasks.close()
