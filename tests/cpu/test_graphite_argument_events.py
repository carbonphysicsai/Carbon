"""PLT-14: scripted/synthetic telemetry. No live model, host or protected data."""

from __future__ import annotations

import json

import pytest
from graphite_fixtures import RecordingMinerTools, controller, provider, spec, started

from carbon.agent_campaign import boundaries
from carbon.agent_campaign.controller import SimulatedCrash
from carbon.agent_campaign.graphite import argument_events as ae
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool, tools
from carbon.agent_campaign.graphite.provider import SessionMismatch
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import COMPACT
from carbon.development_session.research_loop import SELECT
from carbon.development_session.research_tools import PREFIX

SECRET = "synthetic-value-never-in-events-793f"
PRIVATE = r"C:\synthetic-operator\local\input.json"


def arguments(graphite, run_id):
    return [
        event
        for event in graphite.events(run_id, 0)
        if event["kind"] == "call_arguments"
    ]


def test_coherent_identity_edit_cannot_replace_the_original_opening(
    tmp_path, monkeypatch
):
    model = ScriptedModel([text("done")])
    graphite, run_id = started(tmp_path, model)
    opened = graphite._opened(run_id)
    opening = next(
        e for e in graphite.events(run_id, 0) if e["kind"] == "session_opened"
    )
    assert opening["agent_identity"]["inference"] == "scripted"
    opened["live_inference"] = True
    opened["agent_identity"]["inference"] = "live"
    # Matching the actual object's mode as well cannot replace the original pin.
    # This stays a ScriptedModel; only synthetic metadata is changed.
    monkeypatch.setattr(model, "live", True)
    with pytest.raises(SessionMismatch, match="argument_logging_identity_changed"):
        graphite._loop_limits(opened)
    assert model.requests == []


def test_resumed_actual_model_mode_must_match_its_pinned_identity(
    tmp_path, monkeypatch
):
    model = ScriptedModel([text("done")])
    graphite, run_id = started(tmp_path, model)
    opened = graphite._opened(run_id)
    assert callable(graphite._loop_limits(opened)["tool_observer"])
    monkeypatch.setattr(model, "live", True)
    with pytest.raises(SessionMismatch, match="agent_model_mode_changed"):
        graphite._loop_limits(opened)
    assert model.requests == []


def test_dropping_recorded_run_id_cannot_bypass_the_original_policy_pin(tmp_path):
    graphite, run_id = started(tmp_path, ScriptedModel([text("done")]))
    opened = graphite._opened(run_id)
    del opened["run_id"]
    del opened["argument_logging"]
    path = graphite._dir(run_id) / "session-open.json"
    path.write_bytes(canonical(opened))
    with pytest.raises(SessionMismatch, match="session_run_identity_changed"):
        graphite._opened(run_id)


def event_bytes(graphite, run_id):
    return (graphite._dir(run_id) / "events.jsonl").read_bytes()


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "files",
        "query",
        "hypothesis",
        "strategy_json",
        "name",
        "task_id",
        "path",
        "expected_effect",
        "reason",
        "card_id",
        "evidence_json",
        "api_key",
        PRIVATE,
    ],
)
def test_free_text_unknown_fields_and_private_names_never_enter_projection(field):
    value = ae.snapshot({field: SECRET + PRIVATE})
    encoded = canonical(value)
    assert SECRET.encode() not in encoded
    assert PRIVATE.encode() not in encoded
    assert ae.snapshot({field: "different-secret"}) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "null",
        {},
        "not json",
        "[]",
        '{"query":1,"query":2}',
        "\ud800",
        {"source": "x" * 17000},
        "x" * 17000,
    ],
)
def test_empty_malformed_and_large_inputs_have_closed_records(value):
    record = ae.snapshot(value)
    assert record["schema"] == ae.POLICY
    assert set(record) == {"schema", "shape", "fields", "unknown_fields"}
    assert "x" * 100 not in json.dumps(record)


def test_public_selectors_numbers_and_structured_forecast_are_explicit():
    raw = {
        "kind": "workspace",
        "action": "run_python",
        "arguments_json": json.dumps(
            {"seconds": 60, "source": SECRET, "files": [PRIVATE], "hypothesis": SECRET}
        ),
        "expected_effect": json.dumps(
            {"metric": "score", "direction": "increase", "target": 0.3}
        ),
    }
    record = ae.snapshot(raw)
    fields = record["fields"]
    assert fields["action"] == "run_python" and fields["kind"] == "workspace"
    assert fields["arguments_json"]["fields"]["seconds"] == 60
    assert fields["arguments_json"]["fields"]["source"] == ae.REDACTED
    assert fields["expected_effect"] == {
        "metric": "score",
        "direction": "increase",
        "target": 0.3,
    }
    assert SECRET not in json.dumps(record) and PRIVATE not in json.dumps(record)
    public = ae.snapshot(
        {"action": "public_material", "arguments_json": '{"name":"objective"}'}
    )
    assert public["fields"]["arguments_json"]["fields"]["name"] == "objective"


@pytest.mark.parametrize(
    "value", [True, -1, 2**40, SECRET, PRIVATE, float("nan"), float("inf")]
)
def test_numeric_selector_mutations_are_redacted(value):
    assert ae.snapshot({"seconds": value})["fields"]["seconds"] == ae.REDACTED


def test_known_markers_redact_entire_argument_object_without_marker_hash():
    for marker in (
        "official_seed",
        "hidden_case",
        "validator_private",
        "CARBON-CANARY-synthetic-only",
    ):
        record = ae.snapshot(
            {"action": "run_python", "seconds": 60, "hypothesis": marker}
        )
        assert record["fields"]["seconds"] == ae.REDACTED
        assert marker not in json.dumps(record)
    left = ae.snapshot({"query": SECRET})
    right = ae.snapshot({"query": "another synthetic secret"})
    assert digest(canonical(left)) == digest(canonical(right))


def test_projection_never_invokes_hostile_representation_or_comparison():
    class Hostile:
        def __repr__(self):
            pytest.fail("no repr of private values")

        def __eq__(self, other):
            pytest.fail("no equality hook of private values")

    value = ae.snapshot({"action": Hostile(), "name": "objective", "source": Hostile()})
    assert value["fields"]["source"] == ae.REDACTED
    assert value["fields"]["name"] == ae.REDACTED


def test_every_successful_refused_engine_and_malformed_call_is_recorded(tmp_path):
    calls = [
        tool(PREFIX + "get_challenge_info", {}),
        tool(
            PREFIX + "start_research_task",
            {
                "kind": "workspace",
                "action": "run_python",
                "arguments_json": json.dumps(
                    {"source": SECRET, "files": [PRIVATE], "seconds": 4}
                ),
            },
        ),
        tool(SELECT, {"used_feedback": True}),
        tool(COMPACT, {"findings": SECRET}),
        tool(SECRET, {"path": PRIVATE}),
        tool(PREFIX + "start_research_task", '{"secret":"' + SECRET),
    ]
    model = ScriptedModel([tools(*calls), text("done")])
    miner = RecordingMinerTools()
    graphite, run_id = started(
        tmp_path, model, role=RoleName.CONSTRUCTOR, miner_tools=miner
    )
    assert graphite.run(run_id) == "succeeded"
    observed = arguments(graphite, run_id)
    assert len(observed) == len(calls)
    assert len({event["identity"] for event in observed}) == len(calls)
    assert {SELECT, COMPACT, ae.UNKNOWN_TOOL} <= {event["tool"] for event in observed}
    assert any(event["arguments"]["shape"] == "malformed" for event in observed)
    for event in graphite.events(run_id, 0):
        if event["kind"] in ("call_arguments", "tool_answered", "tool_refused"):
            assert event["arguments"]["schema"] == ae.POLICY
            assert event["arguments_digest"] == digest(canonical(event["arguments"]))
    raw = event_bytes(graphite, run_id)
    assert SECRET.encode() not in raw and PRIVATE.encode() not in raw
    # Logging does not redact the request sent to the trusted SDK.
    assert (
        miner.calls[1][1]["arguments_json"] == calls[1]["arguments"]["arguments_json"]
    )


def test_session_identity_is_derived_from_actual_selection_and_role(tmp_path):
    graphite, run_id = started(tmp_path)
    opened = graphite._opened(run_id)
    identity = opened["agent_identity"]
    assert identity == {
        "implementation": "graphite",
        "role": opened["role"]["name"],
        "model_provider": "engy",
        "model": opened["role"]["model"],
        "inference": "scripted",
    }
    assert opened["argument_logging"] == ae.POLICY
    assert graphite.events(run_id, 0)[0]["agent_identity"] == identity
    assert not {"credential", "credential_ref", "path", "api_key"} & identity.keys()


@pytest.mark.parametrize("mutation", ["model", "policy", "removed"])
def test_session_identity_or_policy_tampering_refuses_before_model_call(
    tmp_path, mutation
):
    model = ScriptedModel([text("done")])
    graphite, run_id = started(tmp_path, model)
    opened = graphite._opened(run_id)
    if mutation == "model":
        opened["agent_identity"]["model"] = SECRET
    elif mutation == "policy":
        opened["argument_logging"] = SECRET
    else:
        del opened["argument_logging"]
        del opened["agent_identity"]
    (graphite._dir(run_id) / "session-open.json").write_bytes(canonical(opened))
    assert graphite.run(run_id) == "failed"
    assert model.requests == []
    assert SECRET.encode() not in event_bytes(graphite, run_id)


def test_requested_canary_still_halts_and_records_finding_without_token_in_events(
    tmp_path,
):
    canary = boundaries.make_canaries(1)[0]
    model = ScriptedModel([tool("lit_search", {"query": canary}), text("done")])
    graphite = provider(tmp_path / "graphite", model)
    control = controller(tmp_path, graphite)
    control.register_campaign(
        "c1",
        role=boundaries.Role.CONSTRUCTION,
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        checkout_digest="sha256:" + "b" * 64,
        profile_digest="sha256:" + "a" * 64,
        ceiling="5.00",
        canaries=[canary],
    )
    control.launch(spec(graphite), "k1")
    run_id = graphite.run_id_for("k1")
    graphite.run(run_id)
    assert canary.encode() not in event_bytes(graphite, run_id)
    control.poll("k1")
    assert control.admission_ledgers()["findings"]
    assert any("protected_data_exposure" in halt for halt in control.halts())
    event = next(
        event for event in graphite.events(run_id, 0) if event["kind"] == "tool_refused"
    )
    assert graphite.event_canary_hit(run_id, event, [canary]) is True
    assert (
        graphite.event_canary_hit(run_id, event, ["CARBON-CANARY-unregistered"])
        is False
    )
    intent = next(
        (graphite._dir(run_id) / "ledger").rglob(event["identity"] + "-intent.json")
    )
    intent.unlink()
    with pytest.raises(
        ProviderUnavailable, match="canary_argument_evidence_unavailable"
    ):
        graphite.event_canary_hit(run_id, event, [canary])


def test_private_intent_failure_is_not_reported_as_no_exposure(tmp_path):
    canary = boundaries.make_canaries(1)[0]
    graphite, run_id = started(
        tmp_path, ScriptedModel([tool("lit_search", {"query": canary}), text("done")])
    )
    graphite.run(run_id)
    event = next(
        event for event in graphite.events(run_id, 0) if event["kind"] == "tool_refused"
    )
    root = graphite._dir(run_id) / "ledger"
    path = next(root.rglob(event["identity"] + "-intent.json"))
    path.write_text('{"private_path":"' + SECRET, encoding="utf-8", newline="\n")
    with pytest.raises(ProviderUnavailable) as failure:
        graphite.event_canary_hit(run_id, event, [canary])
    assert SECRET not in str(failure.value) and str(path) not in str(failure.value)


def test_crash_resume_replays_without_duplicate_argument_events(tmp_path):
    model = ScriptedModel(
        [tool("lit_search", {"query": "public batteries"}), text("done")]
    )
    graphite, run_id = started(tmp_path, model, crash_at="before_finish")
    with pytest.raises(SimulatedCrash):
        graphite.run(run_id)
    before = event_bytes(graphite, run_id)
    resumed_model = ScriptedModel([])
    resumed = provider(tmp_path, resumed_model)
    assert resumed.run(run_id) == "succeeded"
    assert len(arguments(resumed, run_id)) == 1
    assert resumed_model.requests == []
    assert event_bytes(resumed, run_id).startswith(before)


def test_public_argument_replay_conflict_is_refused(tmp_path):
    graphite, run_id = started(tmp_path)
    observer = graphite._loop_limits(graphite._opened(run_id))["tool_observer"]
    observer("epoch-1-tool-000", PREFIX + "start_research_task", '{"seconds":40}')
    with pytest.raises(SessionMismatch, match="argument_event_replay_conflict"):
        observer("epoch-1-tool-000", PREFIX + "start_research_task", '{"seconds":41}')


def test_unknown_result_status_cannot_add_a_private_path_to_events(tmp_path):
    miner = RecordingMinerTools({PREFIX + "get_challenge_info": {"status": PRIVATE}})
    graphite, run_id = started(
        tmp_path,
        ScriptedModel([tool(PREFIX + "get_challenge_info", {}), text("done")]),
        role=RoleName.CONSTRUCTOR,
        miner_tools=miner,
    )
    graphite.run(run_id)
    assert PRIVATE.encode() not in event_bytes(graphite, run_id)
    event = next(
        event
        for event in graphite.events(run_id, 0)
        if event["kind"] == "tool_answered"
    )
    assert event["status"] == ae.REDACTED


def test_not_run_calls_are_observed_before_a_terminal_result(tmp_path):
    from test_cw1_research_ledger import ledger
    from test_research_loop_limits import (
        INFO,
        INFO_TOOL,
        ROOMY,
        SDK,
        call,
        role,
        scripted,
    )
    from test_research_loop_stages import PLAN, RECORD, planner_finish, record_plan

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, _ = scripted(
        [[record_plan("finish", PLAN), call("never-dispatched", INFO)]]
    )
    observed = []
    sdk = SDK(meter)
    report = role(
        meter,
        transport,
        sdk,
        tools=(INFO_TOOL,),
        finish=planner_finish(),
        tool_observer=lambda identity, name, raw: observed.append(
            (identity, name, raw)
        ),
    )
    assert report["status"] == "PLANNED"
    assert [name for _, name, _ in observed] == [RECORD, INFO]
    assert sdk.dispatched == []
    assert all(type(raw) is str for _, _, raw in observed)


def test_actual_compaction_response_calls_are_observed(tmp_path):
    from test_cw1_research_ledger import ledger
    from test_research_loop_compaction import TURNS, long_run, session
    from test_research_loop_limits import ROOMY

    meter = ledger(tmp_path, ceilings=ROOMY)
    transport, _ = long_run(TURNS)
    observed = []
    report = session(
        meter,
        transport,
        tool_observer=lambda identity, name, raw: observed.append(
            (identity, name, raw)
        ),
    )
    assert report["status"] == "SELECTED"
    compact = [
        (identity, name, raw) for identity, name, raw in observed if name == COMPACT
    ]
    assert compact and all("-compact-" in identity for identity, _, _ in compact)
    assert len({identity for identity, _, _ in observed}) == len(observed)


def test_dispatch_exception_does_not_drop_its_argument_record(tmp_path):
    class Failing(RecordingMinerTools):
        async def call(self, name, arguments, identity):
            raise RuntimeError(SECRET)

    graphite, run_id = started(
        tmp_path,
        ScriptedModel([tool(PREFIX + "get_challenge_info", {})]),
        role=RoleName.CONSTRUCTOR,
        miner_tools=Failing(),
    )
    assert graphite.run(run_id) == "failed"
    assert len(arguments(graphite, run_id)) == 1
    assert SECRET.encode() not in event_bytes(graphite, run_id)


def test_refused_name_canary_matches_original_request_without_name_in_events(tmp_path):
    canary = boundaries.make_canaries(1)[0]
    graphite, run_id = started(
        tmp_path, ScriptedModel([tool(canary, {}), text("done")])
    )
    graphite.run(run_id)
    event = next(
        event for event in graphite.events(run_id, 0) if event["kind"] == "tool_refused"
    )
    assert event["tool"] == ae.UNKNOWN_TOOL
    assert canary.encode() not in event_bytes(graphite, run_id)
    assert graphite.event_canary_hit(run_id, event, [canary]) is True


@pytest.mark.parametrize("mutation", ["shape", "duplicate", "wrong-run"])
def test_corrupt_or_cross_run_canary_intent_is_unavailable_not_false(
    tmp_path, mutation
):
    canary = boundaries.make_canaries(1)[0]
    graphite, run_id = started(
        tmp_path, ScriptedModel([tool("lit_search", {"query": canary}), text("done")])
    )
    graphite.run(run_id)
    event = next(
        event for event in graphite.events(run_id, 0) if event["kind"] == "tool_refused"
    )
    path = next(
        (graphite._dir(run_id) / "ledger").rglob(event["identity"] + "-intent.json")
    )
    if mutation == "wrong-run":
        event["run_id"] = "different-run"
    else:
        path.write_text(
            (
                '{"name":[],"arguments":{},"call_id":"a"}'
                if mutation == "shape"
                else '{"name":"lit_search","name":"lit_card","arguments":{},"call_id":"a"}'
            ),
            encoding="utf-8",
            newline="\n",
        )
    with pytest.raises(
        ProviderUnavailable, match="canary_argument_evidence_unavailable"
    ):
        graphite.event_canary_hit(run_id, event, [canary])
