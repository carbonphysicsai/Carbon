"""The agents' tool text, by version (VALIDATOR-07).

Pins:
- v2 tool text names no Challenge; v1 is the original wording, byte for byte;
- a new brief selects v2; a session records the version it opened with, and
  every turn and every resume reads that recorded version, absent meaning v1;
- a role whose tools v2 leaves alone records exactly what it always did, so
  its records and briefs keep their bytes;
- an unknown or forged version is refused.

No pod, key, network or spend.
"""

import json

import pytest
from graphite_fixtures import (
    CHECKOUT,
    FIXTURE_COMMIT,
    provider,
    spec,
)

from carbon.agent_campaign.graphite import roles
from carbon.agent_campaign.graphite.model import ScriptedModel, text
from carbon.agent_campaign.graphite.provider import SessionBrief, tool_text_of
from carbon.agent_campaign.graphite.roles import (
    NEXT_LEVEL,
    PROPOSE,
    ROLES,
    TOOL_TEXT_V1,
    TOOL_TEXT_V2,
    RoleName,
)
from carbon.agent_campaign.provider import ProviderUnavailable

CHALLENGE_WORDS = (
    "battery",
    "cooling",
    "cold plate",
    "cold-plate",
    "motor",
    "charging",
)


def test_v2_tool_text_names_no_challenge():
    for role in ROLES.values():
        for schema in role.tool_schemas(TOOL_TEXT_V2):
            words = schema.get("description", "").lower()
            for word in CHALLENGE_WORDS:
                assert word not in words, (role.name, schema["name"], word)


def test_v1_tool_text_is_the_original_wording():
    v1 = {s["name"]: s for s in ROLES[RoleName.CONSTRUCTOR].tool_schemas()}
    assert v1[PROPOSE] is roles.PROPOSAL_TOOL
    assert v1[NEXT_LEVEL] is roles.NEXT_LEVEL_TOOL
    assert "battery TrainingStrategy" in roles.PROPOSAL_TOOL["description"]
    assert roles.TOOL_REGISTRY[PROPOSE] is roles.PROPOSAL_TOOL
    # v2 changes descriptions only: the same names and parameters.
    v2 = {s["name"]: s for s in ROLES[RoleName.CONSTRUCTOR].tool_schemas(TOOL_TEXT_V2)}
    assert list(v2) == list(v1)
    for name, schema in v1.items():
        assert {k: v for k, v in v2[name].items() if k != "description"} == {
            k: v for k, v in schema.items() if k != "description"
        }


def test_records_and_briefs_keep_their_bytes_where_v2_changes_nothing():
    constructor = ROLES[RoleName.CONSTRUCTOR]
    assert "tool_text" not in constructor.record()
    assert constructor.record(TOOL_TEXT_V2)["tool_text"] == TOOL_TEXT_V2
    assert constructor.manifest_digest(TOOL_TEXT_V2) != constructor.tool_manifest_digest
    for name in (
        RoleName.ATTACKER,
        RoleName.READER,
        RoleName.WRITER,
        RoleName.OPTIMIZER,
    ):
        role = ROLES[name]
        assert role.effective_tool_text(TOOL_TEXT_V2) == TOOL_TEXT_V1
        assert role.record(TOOL_TEXT_V2) == role.record()
        brief = _brief(name, TOOL_TEXT_V2)
        assert brief.document() == _brief(name, TOOL_TEXT_V1).document()
    v1 = _brief(RoleName.PLANNER, TOOL_TEXT_V1).document()
    v2 = _brief(RoleName.PLANNER, TOOL_TEXT_V2).document()
    assert "tool_text" not in v1 and v2["tool_text"] == TOOL_TEXT_V2
    assert v1["tool_manifest_digest"] == ROLES[RoleName.PLANNER].tool_manifest_digest


def test_an_unknown_tool_text_is_refused():
    with pytest.raises(ValueError, match="tool_text_unknown"):
        _brief(RoleName.PLANNER, "graphite-tool-text-v9")
    with pytest.raises(ValueError, match="tool_text_unknown"):
        ROLES[RoleName.PLANNER].tool_schemas("graphite-tool-text-v9")


def _brief(role, tool_text=TOOL_TEXT_V2):
    return SessionBrief(
        role=role,
        initial_observation={"objective": "synthetic harness fixture"},
        checkout_commit=FIXTURE_COMMIT,
        checkout_manifest_digest=CHECKOUT,
        tool_text=tool_text,
    )


def _session(tmp_path, tool_text):
    graphite = provider(tmp_path / tool_text, ScriptedModel([text("Plan written.")]))
    handle = graphite.start(
        spec(graphite, _brief(RoleName.PLANNER, tool_text)), "key-" + tool_text
    )
    return graphite, handle.provider_run_id


def _plan_tools(graphite, run_id):
    plan = json.loads(
        (graphite._dir(run_id) / "ledger" / "epoch-1" / "plan.json").read_bytes()
    )
    return {tool["name"]: tool for tool in plan["tools"]}


@pytest.mark.parametrize("tool_text", [TOOL_TEXT_V1, TOOL_TEXT_V2])
def test_a_session_runs_and_resumes_on_the_text_it_recorded(tmp_path, tool_text):
    graphite, run_id = _session(tmp_path, tool_text)
    opened = graphite._opened(run_id)
    assert tool_text_of(opened) == tool_text
    assert ("tool_text" in opened["role"]) is (tool_text == TOOL_TEXT_V2)
    assert graphite.run(run_id) == "succeeded"
    expected = ROLES[RoleName.PLANNER].tool_schemas(tool_text)
    assert (
        _plan_tools(graphite, run_id)[NEXT_LEVEL]
        == {s["name"]: s for s in expected}[NEXT_LEVEL]
    )
    request = graphite.model.requests[0]
    sent = {tool["name"]: tool for tool in request["tools"]}
    assert (
        sent[NEXT_LEVEL]["description"]
        == {s["name"]: s for s in expected}[NEXT_LEVEL]["description"]
    )


def test_a_forged_tool_text_in_a_record_stops_the_session(tmp_path):
    graphite, run_id = _session(tmp_path, TOOL_TEXT_V2)
    path = graphite._dir(run_id) / "session-open.json"
    opened = json.loads(path.read_bytes())
    opened["role"]["tool_text"] = TOOL_TEXT_V1
    path.chmod(0o600)
    path.write_text(json.dumps(opened))
    assert graphite.run(run_id) == "failed"
    state = json.loads((graphite._dir(run_id) / "state.json").read_bytes())
    assert state["failure"] == {
        "code": "session_record_mismatch",
        "detail": "role_changed",
    }


@pytest.mark.parametrize(
    ("role", "tool_text"),
    [
        # v2 changes nothing of the Reader's: a v2 brief for it is forged.
        (RoleName.READER, TOOL_TEXT_V2),
        (RoleName.PLANNER, "graphite-tool-text-v9"),
    ],
)
def test_a_forged_brief_tool_text_is_refused_before_opening(tmp_path, role, tool_text):
    from carbon.development_session.profile import canonical, digest

    graphite = provider(tmp_path, ScriptedModel([text("x")]))
    honest = _brief(role, TOOL_TEXT_V1)
    task = spec(graphite, honest)
    body = canonical({**honest.document(), "tool_text": tool_text})
    forged = digest(body)
    (graphite.root / "briefs" / (forged.removeprefix("sha256:") + ".json")).write_bytes(
        body
    )
    task = type(task)(**{**task.__dict__, "instructions_digest": forged})
    with pytest.raises(ProviderUnavailable, match="brief_tool_text_unknown"):
        graphite.start(task, "forged")
    assert not list((graphite.root / "runs").glob("*/session-open.json"))
