"""GRAPHITE-01 phase 1: lifecycle, crash recovery, caps, cancellation, records.

Every test drives the harness with the scripted model: no live inference, no
API key, no network and no spend. Charges are synthetic.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import socket
from decimal import Decimal

import pytest
from graphite_fixtures import (
    Clock,
    brief,
    controller,
    provider,
    reader_script,
    register,
    spec,
    started,
)

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.graphite import ScriptedModel
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite.model import crash, fail, text, tool
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, RunState
from carbon.development_session.model_provider import ENGY_MODELS, select
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import AUTONOMOUS, COMPACT
from carbon.development_session.research_agent_policy import PROMPT as BURGERS_PROMPT
from carbon.development_session.research_loop import SELECTION_TOOL, run_epoch
from carbon.development_session.research_tools import TOOLS as MINER_TOOLS

READER = ROLES[RoleName.READER]


def _reservation(model_id):
    return select(
        provider_id="engy-anthropic",
        model_id=model_id,
        credential={"kind": "file", "reference": "unset"},
    ).reservation_nano


# -- lifecycle ---------------------------------------------------------------------------
def test_a_reader_session_runs_behind_the_campaign_controller(tmp_path):
    model = ScriptedModel(reader_script())
    graphite = provider(tmp_path / "graphite", model)
    control = controller(tmp_path, graphite)
    register(control)
    task = spec(graphite)
    assert control.launch(task, "k1") == "dispatched"
    run_id = graphite.run_id_for("k1")
    assert graphite.status(run_id).state is RunState.RUNNING

    assert graphite.run(run_id) == "succeeded"
    assert control.poll("k1") == "completed"

    # Each request carried exactly the role's prompt, tools and starting rung:
    # the closed manifest, then the engine's compaction tool the v2 limits
    # rule adds (OWNER-GRAPHITE-MINER-01 §6), the same on every turn.
    assert len(model.requests) == 3
    for request in model.requests:
        assert request["instructions"] == READER.prompt
        assert [t["name"] for t in request["tools"]] == [*READER.tools, COMPACT]
        assert request["model"] == READER.start_model
    # Usage is the ledger's settled charge: three synthetic 100-micro calls.
    assert graphite.usage(run_id).settled == Decimal("0.0003")
    budget = control.budget()
    assert Decimal(budget["committed"]) == Decimal("0.0003")
    kinds = [e["kind"] for e in control.ledger()]
    assert "artifact" in kinds and "terminal" in kinds
    assert control.verify_ledger()["consistent"]
    assert control.halts() == []

    record = graphite.session_record(run_id)
    assert record["provider"] == "graphite"
    assert record["role"]["prompt_digest"] == digest(READER.prompt.encode())
    assert record["role"]["tool_manifest"] == list(READER.tools)
    assert record["model"]["model"] == READER.start_model
    assert record["model"]["settings"]["max_output_tokens"] > 0
    assert record["literature"]["snapshot_digest"].startswith("sha256:")
    assert record["checkout"]["commit"] == "1" * 40
    assert record["live_inference"] is False
    assert not any(record["authority"].values())
    assert len(record["calls"]) == 3
    for call in record["calls"]:
        assert call["reservation"]["provider_nanodollars"] == _reservation(
            READER.start_model
        )
        assert call["settlement"]["provider_nanodollars"] == 100_000
        assert call["charge"]["basis"].startswith("provider-reported")
    assert record["outcome"]["state"] == "succeeded"


def test_the_export_is_data_and_names_its_session_record(tmp_path):
    graphite, run_id = started(tmp_path / "graphite")
    graphite.run(run_id)
    [artifact] = graphite.artifacts(run_id)
    body = json.loads(artifact.body)
    assert body["authority_granted"] is False
    assert body["session_record_digest"] == digest(canonical(body["session_record"]))
    assert body["outcome"]["status"] == "STOPPED"
    assert "Report" in json.dumps(body["outcome"]["agent_output"])


def test_start_is_idempotent_and_find_resolves_the_key(tmp_path):
    graphite = provider(tmp_path / "graphite")
    task = spec(graphite)
    first = graphite.start(task, "k1")
    assert graphite.start(task, "k1") == first
    assert graphite.find("k1") == first
    assert graphite.find("k2") is None
    assert len(list((tmp_path / "graphite" / "runs").iterdir())) == 1


def test_an_unregistered_brief_or_wrong_role_opens_nothing(tmp_path):
    graphite = provider(tmp_path / "graphite")
    task = spec(graphite)
    stranger = ctl.TaskSpec(
        **{**task.__dict__, "instructions_digest": "sha256:" + "9" * 64}
    )
    with pytest.raises(ProviderUnavailable, match="unknown_brief"):
        graphite.start(stranger, "k1")
    attacker = spec(graphite, brief(RoleName.ATTACKER))
    wrong = ctl.TaskSpec(**{**attacker.__dict__, "role": "construction_research"})
    with pytest.raises(ProviderUnavailable, match="role_boundary_mismatch"):
        graphite.start(wrong, "k2")
    assert list((tmp_path / "graphite" / "runs").iterdir()) == []


def test_no_network_is_touched_by_a_whole_session(tmp_path, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    graphite, run_id = started(tmp_path / "graphite")
    assert graphite.run(run_id) == "succeeded"


# -- crash recovery ------------------------------------------------------------------------
def _reference(root):
    graphite, run_id = started(root)
    graphite.run(run_id)
    return graphite, run_id


def test_crash_recovery_at_every_checkpoint_never_resends(tmp_path):
    reference, run_id = _reference(tmp_path / "reference")
    boundaries = reference._checkpoints
    expected = reference.session_record_digest(run_id)
    assert boundaries >= 8
    for point in range(1, boundaries + 1):
        root = tmp_path / f"crash-{point:02d}"
        # The model service outlives the crashed process, as a provider does.
        model = ScriptedModel(reader_script())
        crashed, run_id = started(root, model, crash_at_checkpoint=point)
        with pytest.raises(ctl.SimulatedCrash):
            crashed.run(run_id)
        resumed = provider(root, model)
        assert resumed.status(run_id).state is RunState.RUNNING
        assert resumed.run(run_id) == "succeeded", point
        # Three model turns in all: a journalled reply is never sent again.
        assert len(model.requests) == 3, point
        assert resumed.session_record_digest(run_id) == expected, point


def test_crash_with_a_call_in_flight_keeps_its_reservation_and_never_resends(
    tmp_path,
):
    model = ScriptedModel([crash(), text("never reached")])
    graphite, run_id = started(tmp_path / "graphite", model)
    with pytest.raises(ctl.SimulatedCrash):
        graphite.run(run_id)
    resumed = provider(tmp_path / "graphite", model)
    assert resumed.run(run_id) == "failed"
    assert resumed.session_record(run_id)["outcome"]["failure"]["code"] == (
        "reconciliation_required"
    )
    assert len(model.requests) == 1
    usage = resumed.usage(run_id)
    assert usage.settled == 0
    assert usage.pending == Decimal(_reservation(READER.start_model)) / 10**9


def test_crash_before_finishing_resumes_without_a_model_call(tmp_path):
    model = ScriptedModel(reader_script())
    graphite, run_id = started(tmp_path / "graphite", model, crash_at="before_finish")
    with pytest.raises(ctl.SimulatedCrash):
        graphite.run(run_id)
    resumed = provider(tmp_path / "graphite", model)
    assert resumed.run(run_id) == "succeeded"
    assert len(model.requests) == 3


@pytest.mark.parametrize("point", ctl.CRASH_POINTS[:3])
def test_controller_crash_during_launch_reconciles_to_one_session(tmp_path, point):
    graphite = provider(tmp_path / "graphite")
    control = controller(tmp_path, graphite, crash_at=point)
    register(control)
    task = spec(graphite)
    with pytest.raises(ctl.SimulatedCrash):
        control.launch(task, "k1")
    control.close()
    revived = controller(tmp_path, provider(tmp_path / "graphite"))
    outcome = revived.recover()
    assert outcome["k1"] in ("dispatched", "not_dispatched")
    if outcome["k1"] == "dispatched":
        runs = list((tmp_path / "graphite" / "runs").iterdir())
        assert [p.name for p in runs] == [graphite.run_id_for("k1")]
    # Relaunching the same key never opens a second session.
    assert revived.launch(task, "k1") == outcome["k1"]


def test_provider_crash_after_opening_is_found_by_its_key(tmp_path):
    graphite = provider(tmp_path / "graphite", crash_at="after_open")
    control = controller(tmp_path, graphite)
    register(control)
    with pytest.raises(ctl.SimulatedCrash):
        control.launch(spec(graphite), "k1")
    control.close()
    revived = controller(tmp_path, provider(tmp_path / "graphite"))
    assert revived.recover() == {"k1": "dispatched"}


# -- caps and cancellation -----------------------------------------------------------------
def test_the_per_run_money_cap_is_the_controllers_reservation(tmp_path):
    # 0.01 USD per run; each synthetic reply is charged 3,000 micro (0.003).
    model = ScriptedModel(
        [tool("lit_search", {"query": "operator"})] * 6, charged_micro=3000
    )
    graphite, run_id = started(
        tmp_path / "graphite",
        model,
        grant_changes={"worst_case_run_cost": "0.01"},
    )
    assert graphite.per_run_ceiling_nano() == 10_000_000
    assert graphite.run(run_id) == "failed"
    failure = graphite.session_record(run_id)["outcome"]["failure"]
    assert failure == {"code": "run_cap_reached", "dimension": "provider_nanodollars"}
    # Three calls fit: 3 x 0.003 settled plus the next reservation exceeds 0.01.
    assert len(model.requests) == 3
    usage = graphite.usage(run_id)
    assert usage.settled + usage.pending <= Decimal("0.01")


def test_an_operator_call_cap_narrows_a_run(tmp_path):
    model = ScriptedModel([tool("lit_search", {"query": "operator"})] * 6)
    graphite, run_id = started(tmp_path / "graphite", model, max_calls_per_run=2)
    assert graphite.run(run_id) == "failed"
    assert graphite.session_record(run_id)["outcome"]["failure"] == {
        "code": "run_cap_reached",
        "dimension": "provider_attempts",
    }
    assert len(model.requests) == 2


def test_the_elapsed_limit_refuses_a_call_that_cannot_finish_in_time(tmp_path):
    model = ScriptedModel(reader_script())
    graphite = provider(tmp_path / "graphite", model)
    # 100 seconds cannot hold one call's 120-second provider timeout.
    task = spec(graphite, max_runtime_s=100)
    run_id = graphite.start(task, "k1").provider_run_id
    assert graphite.run(run_id) == "failed"
    assert graphite.session_record(run_id)["outcome"]["failure"] == {
        "code": "run_cap_reached",
        "dimension": "elapsed_seconds",
    }
    assert model.requests == []


def test_the_grant_ceiling_refuses_a_launch_before_the_provider_sees_it(tmp_path):
    graphite = provider(
        tmp_path / "graphite",
        grant_changes={
            "monetary_ceiling": "1.00",
            "cleanup_allowance": "0.10",
            "worst_case_run_cost": "0.40",
            "max_concurrency": 5,
        },
    )
    control = controller(tmp_path, graphite)
    register(control, ceiling="0.90")
    register(control, campaign="c2", ceiling="0.90")
    assert control.launch(spec(graphite), "k1") == "dispatched"
    assert control.launch(spec(graphite, campaign="c2"), "k2") == "dispatched"
    with pytest.raises(ctl.ControllerError, match="grant_ceiling_reached"):
        control.launch(spec(graphite), "k3")
    assert graphite.find("k3") is None


def test_cancellation_mid_run_stops_before_the_next_call(tmp_path):
    graphite = provider(tmp_path / "graphite", ScriptedModel([]))
    control = controller(tmp_path, graphite)
    register(control)
    phases = []

    def cancel_now():
        phases.append(control.cancel("k1"))

    model = ScriptedModel(
        [
            tool("lit_search", {"query": "operator"}),
            {
                **tool("lit_card", {"card_id": "fixture-operator-0001"}),
                "hook": cancel_now,
            },
            text("must never be requested"),
        ]
    )
    graphite.model = model
    control.launch(spec(graphite), "k1")
    run_id = graphite.run_id_for("k1")
    assert graphite.run(run_id) == "cancelled"
    # While the worker was still executing, the cancel was not yet verified.
    assert phases == ["cleanup_incomplete"]
    assert len(model.requests) == 2 and model.remaining == 1
    assert control.verify_cancel("k1") == "cancelled"
    assert control.halts() == []
    record = graphite.session_record(run_id)
    assert record["outcome"]["state"] == "cancelled"
    assert all(call["settlement"] is not None for call in record["calls"])


def test_cancel_before_the_worker_starts_runs_nothing(tmp_path):
    model = ScriptedModel(reader_script())
    graphite, run_id = started(tmp_path / "graphite", model)
    graphite.cancel(run_id)
    status = graphite.status(run_id)
    assert status.state is RunState.CANCELLED and status.workers_terminated
    assert graphite.run(run_id) == "cancelled"
    assert model.requests == []


def test_the_runtime_limit_cancels_through_the_controller(tmp_path):
    clock = Clock()
    graphite = provider(tmp_path / "graphite")
    control = controller(tmp_path, graphite, clock=clock)
    register(control)
    control.launch(spec(graphite, max_runtime_s=600), "k1")
    clock.advance(601)
    assert control.poll("k1") == "cancelled"
    assert graphite.run(graphite.run_id_for("k1")) == "cancelled"


def test_a_rejected_call_is_typed_and_never_retried(tmp_path):
    model = ScriptedModel([fail(401, "authentication_error"), text("unused")])
    graphite, run_id = started(tmp_path / "graphite", model)
    assert graphite.run(run_id) == "failed"
    assert graphite.session_record(run_id)["outcome"]["failure"] == {
        "code": "provider_call_failed",
        "outcome": "auth_credential",
    }
    assert len(model.requests) == 1
    assert graphite.usage(run_id).settled == 0


# -- session records ---------------------------------------------------------------------------
def test_the_session_record_is_deterministic(tmp_path):
    first, run_id = _reference(tmp_path / "one")
    second, other = _reference(tmp_path / "two")
    assert run_id == other
    one = first.session_record(run_id)
    two = second.session_record(run_id)
    assert canonical(one) == canonical(two)
    assert first.session_record_digest(run_id) == second.session_record_digest(run_id)
    text_form = canonical(one).decode()
    assert str(tmp_path) not in text_form
    # Every field the ticket names is present.
    for field in (
        "provider",
        "model",
        "role",
        "literature",
        "checkout",
        "calls",
        "grant",
        "caps",
    ):
        assert field in one
    assert (
        one["model"]["settings"] == second.session_record(run_id)["model"]["settings"]
    )
    assert one["role"]["model"] in ENGY_MODELS


@pytest.mark.parametrize(
    "path, value, detail",
    [
        (("role", "prompt_digest"), "sha256:" + "0" * 64, "role_changed"),
        (("role", "tool_manifest"), ["lit_search"], "role_changed"),
        (
            ("literature", "snapshot_digest"),
            "sha256:" + "0" * 64,
            "literature_snapshot_changed",
        ),
        (("model", "model"), "kimi-k3", "model_selection_changed"),
        (("caps", "provider_nanodollars"), None, "grant_or_caps_changed"),
        (("grant", "grant_id"), "another-grant", "grant_or_caps_changed"),
    ],
)
def test_a_tampered_session_record_refuses_to_resume(tmp_path, path, value, detail):
    model = ScriptedModel(reader_script())
    graphite, run_id = started(tmp_path / "graphite", model)
    record_path = tmp_path / "graphite" / "runs" / run_id / "session-open.json"
    opened = json.loads(record_path.read_bytes())
    opened[path[0]][path[1]] = value
    record_path.chmod(0o600)
    record_path.write_bytes(canonical(opened))
    assert graphite.run(run_id) == "failed"
    failure = graphite.session_record(run_id)["outcome"]["failure"]
    assert failure["code"] == "session_record_mismatch"
    assert failure["detail"] in (detail, "model_selection_changed")
    assert model.requests == []


def test_capabilities_are_dispatchable_and_say_no_live_inference(tmp_path):
    graphite = provider(tmp_path / "graphite")
    caps = graphite.capabilities()
    assert caps.provider == gp.PROVIDER and caps.dispatchable
    assert "no live inference" in caps.basis


def test_a_tampered_brief_refuses_to_resume(tmp_path):
    model = ScriptedModel(reader_script())
    graphite, run_id = started(tmp_path / "graphite", model)
    [path] = list((tmp_path / "graphite" / "briefs").iterdir())
    document = json.loads(path.read_bytes())
    document["initial_observation"]["objective"] = "read the hidden cases"
    path.chmod(0o600)
    path.write_bytes(canonical(document))
    assert graphite.run(run_id) == "failed"
    assert graphite.session_record(run_id)["outcome"]["failure"] == {
        "code": "session_record_mismatch",
        "detail": "brief_changed",
    }
    assert model.requests == []


def test_a_brief_registered_against_another_prompt_opens_nothing(tmp_path, monkeypatch):
    graphite = provider(tmp_path / "graphite")
    task = spec(graphite)
    changed = dataclasses.replace(READER, prompt=READER.prompt + "\nChanged.")
    monkeypatch.setitem(gp.ROLES, RoleName.READER, changed)
    with pytest.raises(ProviderUnavailable, match="brief_role_changed"):
        graphite.start(task, "k1")
    assert graphite.find("k1") is None


# -- the research loop repair --------------------------------------------------------------
def _stop_transport(request):
    return {
        "model": request["model"],
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "stop"}],
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def test_the_loop_repair_leaves_historical_epochs_unchanged(tmp_path):
    from test_cw1_research_ledger import ledger

    meter = ledger(tmp_path / "historical")
    args = {
        "owner": "alice",
        "epoch": 1,
        "sdk": None,
        "credential_file": None,
        "initial_observation": {"fixture": True},
        "transport": _stop_transport,
    }
    asyncio.run(run_epoch(meter, **args))
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["prompt"] == BURGERS_PROMPT
    assert plan["tools"] == json.loads(canonical([*MINER_TOOLS, SELECTION_TOOL]))
    with pytest.raises(ValueError, match="both"):
        asyncio.run(run_epoch(ledger(tmp_path / "half"), **args, instructions="x"))
    with pytest.raises(ValueError, match="legacy policy"):
        asyncio.run(
            run_epoch(
                ledger(tmp_path / "policy"),
                **args,
                instructions="x",
                tools=[],
                agent_policy=AUTONOMOUS,
            )
        )


class _ProbeTools:
    """A role's `sdk`: answers every call with a fixed record; runs nothing."""

    async def call(self, name, arguments, identity):
        return {"status": "OK", "probe": True}


def _probe_transport(request):
    return {
        "model": request["model"],
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "probe-" + str(len(request["input"])),
                "name": "graphite_probe",
                "arguments": "{}",
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


_PROBE_TOOL = {
    "type": "function",
    "name": "graphite_probe",
    "strict": True,
    "description": "probe",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _role_epoch(meter, **extra):
    return asyncio.run(
        run_epoch(
            meter,
            owner="alice",
            epoch=1,
            sdk=_ProbeTools(),
            credential_file=None,
            initial_observation={"fixture": True},
            transport=_probe_transport,
            instructions="a closed role",
            tools=[_PROBE_TOOL],
            **extra,
        )
    )


def test_a_role_without_its_own_call_cap_keeps_the_shared_48(tmp_path):
    """GRAPHITE-D26: omitted, the shared MAX_PROVIDER_CALLS (48) caps the
    epoch and the plan records it exactly as before."""
    from test_cw1_research_ledger import ledger

    from carbon.development_session.research_agent_policy import MAX_PROVIDER_CALLS

    meter = ledger(tmp_path / "default")
    report = _role_epoch(meter)
    assert MAX_PROVIDER_CALLS == 48
    assert report["status"] == "STOPPED"
    assert report["reason"] == "epoch provider-call ceiling"
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 48
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["max_provider_calls"] == 48


def test_a_role_call_cap_is_recorded_and_bounds_the_epoch(tmp_path):
    from test_cw1_research_ledger import DEVELOPMENT_CEILINGS, ledger

    meter = ledger(
        tmp_path / "role",
        ceilings={
            **DEVELOPMENT_CEILINGS,
            "provider_attempts": 200,
            "provider_nanodollars": 10**10,
        },
    )
    report = _role_epoch(meter, max_provider_calls=60)
    assert report["reason"] == "epoch provider-call ceiling"
    assert meter.status(owner="alice")["used"]["provider_attempts"] == 60
    plan = json.loads((meter.root / "epoch-1" / "plan.json").read_bytes())
    assert plan["max_provider_calls"] == 60


def test_a_call_cap_without_a_role_is_refused(tmp_path):
    from test_cw1_research_ledger import ledger

    args = {
        "owner": "alice",
        "epoch": 1,
        "sdk": None,
        "credential_file": None,
        "initial_observation": {"fixture": True},
        "transport": _stop_transport,
    }
    meter = ledger(tmp_path / "no-role")
    with pytest.raises(ValueError, match="only a role"):
        asyncio.run(run_epoch(meter, **args, max_provider_calls=150))
    assert not (meter.root / "epoch-1").exists()
    for bad in (0, -1, True, 150.0, "150"):
        with pytest.raises(ValueError, match="positive integer"):
            _role_epoch(ledger(tmp_path / ("bad-" + str(bad))), max_provider_calls=bad)
