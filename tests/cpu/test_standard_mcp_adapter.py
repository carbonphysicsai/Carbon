"""Transport-neutral adapter keeps the existing research controller authoritative."""

import asyncio
import base64
from types import SimpleNamespace

import pytest

from carbon import research
from carbon.development_session.profile import CHALLENGE
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import PREFIX, ResearchMinerTools
from carbon.miner_mcp.standard import (
    AdapterCode,
    AdapterFailure,
    ResearchToolAdapter,
    ResearchToolRequest,
)

OPERATION_ID = "external-operation-0001"
TASK_ID = "rtsk_" + "a" * 64


def workspace(action="inventory", arguments=None):
    return {
        "kind": "workspace",
        "strategy": None,
        "action": action,
        "arguments": {} if arguments is None else arguments,
        "hypothesis": "Inspect available public inputs",
        "expected_effect": "Learn the current permitted research scope",
    }


def practice():
    return {
        "kind": "practice",
        "strategy": {"parameters": {"steps": 512}},
        "action": None,
        "arguments": None,
        "hypothesis": "A bounded training update improves practice",
        "expected_effect": "Measure the effect under existing physics gates",
    }


def reply(operation):
    return {
        "protocol": research.RESEARCH_NAMESPACE,
        "operation": operation,
        "reply": {"status": "OK"},
        "terminal_task": None,
        "public_result": None,
        "requires_reconciliation": False,
    }


def make_adapter(*, ledger=None, owner="alice"):
    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(executor=SimpleNamespace(owner=owner)),
        ledger=ledger,
        owner=owner,
    )
    return sdk, ResearchToolAdapter(sdk, principal=owner)


def call(adapter, operation, arguments, identity=OPERATION_ID):
    return asyncio.run(
        adapter.call(ResearchToolRequest(operation, identity, arguments))
    )


@pytest.mark.parametrize("operation", research.SUPPORTED_OPERATIONS)
def test_all_operations_use_existing_sdk_and_stable_identity(operation, monkeypatch):
    sdk, adapter = make_adapter()
    seen = []

    async def receive(self, name, arguments, identity, *, transport_request_id=None):
        assert self is sdk
        seen.append((name, arguments, identity, transport_request_id))
        return reply(operation)

    monkeypatch.setattr(ResearchMinerTools, "call", receive)
    if operation == "start_research_task":
        args = workspace()
    elif operation == "get_research_result":
        args = {"task_id": TASK_ID, "poll_sequence": 0}
    elif operation == "cancel_research_task":
        args = {"task_id": TASK_ID}
    elif operation in {
        "dry_validate",
        "compile_strategy",
        "inspect_prior_alignment",
        "inspect_resources",
        "forecast_resources",
    }:
        args = {"strategy": {"parameters": {"steps": 512}}}
        if operation == "forecast_resources":
            args["seconds"] = 40
    else:
        args = {}
    original = repr(args)
    result = call(adapter, operation, args)
    assert result.operation_id == OPERATION_ID
    assert result.operation == operation
    assert result.official_eligible is False
    assert not result.requires_reconciliation
    assert seen[0][0] == PREFIX + operation
    assert seen[0][2] == OPERATION_ID
    assert seen[0][3].startswith("mcp-")
    assert repr(args) == original
    if "strategy" in args:
        assert "strategy_json" in seen[0][1]
        assert "strategy" not in seen[0][1]
    if operation == "start_research_task":
        assert seen[0][1]["arguments_json"] == "{}"


@pytest.mark.parametrize(
    "operation,args,identity",
    [
        ("submit", {}, OPERATION_ID),
        ("get_challenge_info", {"principal": "bob"}, OPERATION_ID),
        ("get_challenge_info", {}, "session-id"),
        ("get_challenge_info", {}, "../" + OPERATION_ID),
        ("get_challenge_info", {}, "x" * 129),
        ("dry_validate", {"strategy": "{}"}, OPERATION_ID),
        ("dry_validate", {"strategy": {1: "coerced"}}, OPERATION_ID),
        ("dry_validate", {"strategy": {"x": float("nan")}}, OPERATION_ID),
        ("dry_validate", {"strategy": {"x": (1, 2)}}, OPERATION_ID),
        ("dry_validate", {"strategy": {"x": "a" * 16385}}, OPERATION_ID),
        ("forecast_resources", {"strategy": {}, "seconds": True}, OPERATION_ID),
        ("forecast_resources", {"strategy": {}, "seconds": 601}, OPERATION_ID),
        (
            "get_research_result",
            {"task_id": TASK_ID, "poll_sequence": True},
            OPERATION_ID,
        ),
        (
            "get_research_result",
            {"task_id": TASK_ID, "poll_sequence": 10000},
            OPERATION_ID,
        ),
        ("cancel_research_task", {"task_id": "other-user-root"}, OPERATION_ID),
        ("start_research_task", workspace("eval"), OPERATION_ID),
        ("start_research_task", {**workspace(), "strategy": {}}, OPERATION_ID),
        ("start_research_task", {**practice(), "arguments": {}}, OPERATION_ID),
    ],
)
def test_invalid_transport_values_rejected_before_sdk(
    operation, args, identity, monkeypatch
):
    _, adapter = make_adapter()

    async def forbidden(*args, **kwargs):
        pytest.fail("invalid transport request reached SDK")

    monkeypatch.setattr(ResearchMinerTools, "call", forbidden)
    with pytest.raises(AdapterFailure) as error:
        call(adapter, operation, args, identity)
    assert error.value.code is AdapterCode.INVALID_ARGUMENT
    assert not error.value.dispatch_may_have_occurred


def test_deep_or_cyclic_input_is_bounded_before_serialization():
    _, adapter = make_adapter()
    value = {}
    value["cycle"] = value
    with pytest.raises(AdapterFailure, match="INVALID_ARGUMENT"):
        call(adapter, "dry_validate", {"strategy": value})


def test_owner_is_trusted_and_cannot_change_between_requests():
    sdk, adapter = make_adapter()
    with pytest.raises(AdapterFailure, match="OWNER_BINDING"):
        ResearchToolAdapter(sdk, principal="bob")
    sdk.owner = "bob"
    with pytest.raises(AdapterFailure, match="OWNER_BINDING"):
        call(adapter, "get_challenge_info", {})


@pytest.mark.parametrize("field", ["connection", "wrapper", "composition", "ledger"])
def test_replacing_controller_binding_rejects_before_dispatch(field):
    sdk, adapter = make_adapter()
    setattr(sdk, field, object())
    with pytest.raises(AdapterFailure, match="OWNER_BINDING"):
        call(adapter, "get_challenge_info", {})


def test_operational_error_is_redacted_and_never_automatically_retried(monkeypatch):
    _, adapter = make_adapter()
    attempts = []

    async def fail(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("private-key /private/controller-journal")

    monkeypatch.setattr(ResearchMinerTools, "call", fail)
    with pytest.raises(AdapterFailure) as error:
        call(adapter, "get_challenge_info", {})
    assert str(error.value) == "OPERATIONAL_STOP"
    assert error.value.dispatch_may_have_occurred
    assert attempts == [1]


def test_cancellation_of_python_await_is_not_reported_as_worker_cleanup(monkeypatch):
    _, adapter = make_adapter()

    async def stop(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(ResearchMinerTools, "call", stop)
    with pytest.raises(asyncio.CancelledError):
        call(adapter, "get_challenge_info", {})


@pytest.mark.parametrize(
    "change",
    [
        {"controller_journal": "private"},
        {"operation": "submit"},
        {"requires_reconciliation": 1},
    ],
)
def test_unexpected_result_shapes_fail_closed(change, monkeypatch):
    _, adapter = make_adapter()

    async def invalid(*args, **kwargs):
        return {**reply("get_challenge_info"), **change}

    monkeypatch.setattr(ResearchMinerTools, "call", invalid)
    with pytest.raises(AdapterFailure) as error:
        call(adapter, "get_challenge_info", {})
    assert error.value.code is AdapterCode.INVALID_RESULT
    assert error.value.dispatch_may_have_occurred


def test_trial_replay_and_adapter_reconstruction_use_one_existing_ledger(
    tmp_path, monkeypatch
):
    from test_cw1_research_ledger import ledger

    meter = ledger(tmp_path)
    sdk, adapter = make_adapter(ledger=meter)

    async def receive(self, name, arguments, identity, *, transport_request_id=None):
        return reply("start_research_task")

    # Retain real ResearchMinerTools.call and its durable proposal charge.
    monkeypatch.setattr(ResearchMinerTools, "_call", receive)
    args = practice()
    call(adapter, "start_research_task", args)
    reopened = ResearchToolAdapter(sdk, principal="alice")
    call(reopened, "start_research_task", args)
    assert meter.status(owner="alice")["used"]["research_trials"] == 1
    args["strategy"]["parameters"]["steps"] = 1024
    with pytest.raises(AdapterFailure, match="OPERATIONAL_STOP"):
        call(reopened, "start_research_task", args)
    assert meter.status(owner="alice")["used"]["research_trials"] == 1


@pytest.mark.parametrize(
    "code", ["practice_recipe_required", "workspace_recipe_forbidden"]
)
def test_registered_sdk_corrections_are_projected_without_legacy_envelopes(
    code, monkeypatch
):
    from carbon.development_session.research_tools import TASK_CORRECTIONS

    _, adapter = make_adapter()

    async def reject(*args, **kwargs):
        return {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "contract_incompatibility",
            "detail": "Request rejected before dispatch",
            "authority_granted": False,
            "correction_code": code,
            "correction": TASK_CORRECTIONS[code],
        }

    monkeypatch.setattr(ResearchMinerTools, "call", reject)
    result = call(adapter, "start_research_task", workspace())
    assert result.payload["correction_code"] == code
    assert "kind=workspace" in result.payload["correction"]
    assert "recipe object" in result.payload["correction"]
    assert "_json" not in result.payload["correction"]
    assert "JSON string" not in result.payload["correction"]
    assert not result.requires_reconciliation
    assert result.payload["authority_granted"] is False


@pytest.mark.parametrize(
    "correction",
    [
        {"correction_code": "practice_recipe_required"},
        {"correction": "private exception message"},
        {"correction_code": "unknown", "correction": "private exception message"},
        {
            "correction_code": "practice_recipe_required",
            "correction": "private exception message",
        },
        {"correction_code": [], "correction": "private exception message"},
    ],
)
def test_unregistered_or_partial_sdk_corrections_never_escape(correction, monkeypatch):
    _, adapter = make_adapter()

    async def reject(*args, **kwargs):
        return {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "contract_incompatibility",
            "detail": "Request rejected before dispatch",
            "authority_granted": False,
            **correction,
        }

    monkeypatch.setattr(ResearchMinerTools, "call", reject)
    with pytest.raises(AdapterFailure, match="INVALID_RESULT") as error:
        call(adapter, "start_research_task", workspace())
    assert "private exception" not in str(error.value)


@pytest.mark.parametrize("token", ["", "contains space", "x" * 129, "é", True])
def test_bad_transmission_identity_is_rejected_before_proposal_charge(tmp_path, token):
    from test_cw1_research_ledger import ledger

    meter = ledger(tmp_path)
    sdk, _ = make_adapter(ledger=meter)
    with pytest.raises(ValueError, match="transport request identity"):
        asyncio.run(
            sdk.call(
                PREFIX + "start_research_task",
                {"kind": "practice"},
                OPERATION_ID,
                transport_request_id=token,
            )
        )
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


@pytest.mark.parametrize("numerical", [False, True])
def test_real_authenticated_workspace_survives_adapter_reconnect(
    tmp_path, monkeypatch, numerical
):
    from test_c08_authenticated_miner_mcp import (
        CONTEXT,
        NOW,
        _Adapter,
        _headers,
        _snapshot,
        _Verifier,
    )

    from carbon.development_session import research_tools
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
    discovery = research.ServiceCall(
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
            "call_base64": base64.b64encode(
                research.canonical_bytes(discovery)
            ).decode()
        },
    )
    owner = asyncio.run(gateway.receive(body, _headers(body, NOW))).requester.value
    from carbon.development_session.research_ledger import (
        DEVELOPMENT_CEILINGS,
        DEVELOPMENT_ELAPSED_SECONDS,
        VERSION,
    )

    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "test-only",
            "implementation": "test-only",
            "owner": owner,
            "objective": "test-only",
            "sampling": "test-only",
            "control": "test-only",
            "selection": "test-only",
            "replica_policy": "test-only",
            "provider": "test-only",
        }
    )
    executions = []

    def failed_worker(*args, **kwargs):
        executions.append(1)
        raise ValueError("injected worker failure; no actual numerical execution")

    from carbon.development_session import research_tasks

    monkeypatch.setattr(research_tasks, "run_script", failed_worker)
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
    sdk = ResearchMinerTools(
        connection=Connection(),
        wrapper=AuthenticatedResearchService(gateway, {owner: composition.service}),
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    try:
        adapter = ResearchToolAdapter(sdk, principal=owner)
        args = workspace("public_material", {"name": "objective"})
        if numerical:
            args = workspace(
                "run_python",
                {
                    "source": "pass",
                    "files": [],
                    "seconds": 40,
                    "hypothesis": "test a bounded failure",
                    "expected_effect": "no duplicate retry",
                },
            )
        first = call(adapter, "start_research_task", args)
        reopened = ResearchToolAdapter(sdk, principal=owner)
        second = call(reopened, "start_research_task", args)
        assert first.payload["terminal_task"]["state"] == (
            "FAILED_INFRA" if numerical else "SUCCEEDED"
        )
        assert (
            first.payload["terminal_task"]["task_id"]
            == second.payload["terminal_task"]["task_id"]
        )
        assert first.payload["public_result"] == second.payload["public_result"]
        assert ledger.status(owner=owner)["used"]["research_trials"] == int(numerical)
        assert executions == ([1] if numerical else [])
        assert ledger.status(owner=owner)["used"]["provider_attempts"] == 0
        assert not first.requires_reconciliation
        if numerical:
            changed = {**args, "hypothesis": "changed request under the same key"}
            with pytest.raises(AdapterFailure, match="OPERATIONAL_STOP"):
                call(reopened, "start_research_task", changed)
            assert ledger.status(owner=owner)["used"]["research_trials"] == 1
            assert executions == [1]
        else:
            conflict = call(reopened, "start_research_task", workspace("inventory"))
            assert conflict.payload["reply"]["status"] == "ERROR"
            assert "IDEMPOTENCY_CONFLICT" in str(conflict.payload["reply"])
    finally:
        composition.tasks.close()
