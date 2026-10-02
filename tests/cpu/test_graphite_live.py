"""What a live, staged Graphite session needs (CHALLENGE-PROTOCOL-04 slice 2).

All scripted: no live inference, no key, no network, no spend.
- `run_async` runs inside an event loop the caller already has open.
- Miner tool identities are namespaced by run.
- The research-trial cap holds across a session and is refused before
  dispatch.
- The model sees the trimmed view of a result, and the full result is kept
  by digest.
- Each role has its own call cap.
- An unstaged provider is unchanged.
"""

from __future__ import annotations

import asyncio
import json

from graphite_fixtures import RecordingMinerTools, ScriptedModel, brief, provider

from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.model import text, tool
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import TaskSpec
from carbon.development_session.research_agent_policy import MAX_RESEARCH_TRIALS
from carbon.development_session.research_tools import PREFIX

START = PREFIX + "start_research_task"
INFO = PREFIX + "get_challenge_info"


def _session(root, script, *, miner=None, key="k1", role=RoleName.CONSTRUCTOR, **kw):
    profile = stages.stage_profile("test_iterate")
    model = ScriptedModel(script)
    miner = miner if miner is not None else RecordingMinerTools()
    graphite = provider(root, model, miner_tools=miner, stage_profile=profile, **kw)
    session_brief = brief(role)
    spec = TaskSpec(
        campaign_id="c1",
        role=ROLES[role].boundary.value,
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        profile_digest=stages.profile_digest(profile),
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=3600,
    )
    run_id = graphite.start(spec, key).provider_run_id
    return graphite, run_id, model, miner


def _opened(graphite, run_id):
    return json.loads((graphite._dir(run_id) / "session-open.json").read_bytes())


def test_a_session_runs_inside_an_open_event_loop(tmp_path):
    graphite, run_id, _, miner = _session(tmp_path, [tool(INFO, {}), text("done")])

    async def inside_the_miner_path():
        return await graphite.run_async(run_id)

    assert asyncio.run(inside_the_miner_path()) == "succeeded"
    assert [c[0] for c in miner.calls] == [INFO]
    live = _opened(graphite, run_id)["live_settings"]
    assert live["parallel_calls"] == "FIRST_RUN_REST_REFUSED"
    assert live["max_research_trials"] == MAX_RESEARCH_TRIALS


def test_miner_identities_are_namespaced_by_run(tmp_path):
    miner = RecordingMinerTools()
    a, run_a, _, _ = _session(
        tmp_path / "a", [tool(INFO, {}), text("done")], miner=miner
    )
    b, run_b, _, _ = _session(
        tmp_path / "b", [tool(INFO, {}), text("done")], miner=miner, key="k2"
    )
    assert a.run(run_a) == "succeeded" and b.run(run_b) == "succeeded"
    identities = [c[2] for c in miner.calls]
    assert identities[0].startswith(run_a + ":") and identities[1].startswith(
        run_b + ":"
    )
    assert len(set(identities)) == 2


def test_the_trial_cap_is_refused_before_dispatch(tmp_path):
    trial = {"kind": "practice", "arguments_json": "{}"}
    script = [tool(START, trial) for _ in range(MAX_RESEARCH_TRIALS + 1)] + [
        text("done")
    ]
    graphite, run_id, _, miner = _session(tmp_path, script)
    assert graphite.run(run_id) == "succeeded"
    assert [c[0] for c in miner.calls] == [START] * MAX_RESEARCH_TRIALS
    refused = [
        e
        for e in graphite.events(run_id, 0)
        if e["kind"] == "tool_refused" and e["tool"] == START
    ]
    assert [e["reason_code"] for e in refused] == ["research_trial_cap_reached"]
    assert graphite._trials_started(run_id) == MAX_RESEARCH_TRIALS


def test_the_model_sees_the_trimmed_view_and_the_full_result_is_kept(tmp_path):
    answer = {"status": "OK", "value": 1, "immutable_bindings": {"long": "x" * 200}}
    miner = RecordingMinerTools({INFO: answer})
    graphite, run_id, model, _ = _session(
        tmp_path, [tool(INFO, {}), text("done")], miner=miner
    )
    assert graphite.run(run_id) == "succeeded"
    assert "immutable_bindings" not in json.dumps(model.requests[-1])
    answered = next(
        e for e in graphite.events(run_id, 0) if e["kind"] == "tool_answered"
    )
    kept = graphite._dir(run_id) / "results" / (answered["result_digest"][7:] + ".json")
    assert json.loads(kept.read_bytes()) == answer
    assert answered["model_view_digest"] != answered["result_digest"]


def test_each_role_has_its_own_call_cap(tmp_path):
    graphite, run_id, _, _ = _session(
        tmp_path,
        [text("done")],
        role_call_caps={RoleName.CONSTRUCTOR: 3, RoleName.ATTACKER: 16},
    )
    assert _opened(graphite, run_id)["caps"]["provider_attempts"] == 3
    other = provider(
        tmp_path,
        ScriptedModel([text("done")]),
        stage_profile=stages.stage_profile("test_iterate"),
        role_call_caps={RoleName.CONSTRUCTOR: 4},
    )
    assert other.run(run_id) == "failed"
    assert other._state(run_id)["failure"]["detail"] == "grant_or_caps_changed"


def test_an_unstaged_provider_is_unchanged(tmp_path):
    graphite = provider(tmp_path, ScriptedModel([text("done")]))
    session_brief = brief(RoleName.READER)
    spec = TaskSpec(
        campaign_id="c1",
        role=ROLES[RoleName.READER].boundary.value,
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        profile_digest="sha256:" + "a" * 64,
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=3600,
    )
    run_id = graphite.start(spec, "k1").provider_run_id
    opened = _opened(graphite, run_id)
    assert "stage" not in opened and "live_settings" not in opened
    assert graphite.run(run_id) == "succeeded"
