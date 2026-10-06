"""Miner research tool usability (RESEARCH-TOOL-USABILITY-01).

Found in Graphite phase-4 session 1 (OWNER-GRAPHITE-TEST-WAVE-03, test side).
Claims tested, each absence paired with the same check finding a presence:

- dry_validate answers as the named Challenge's submission path does
  (`challenge_contracts.compile_submission`): the same typed codes and paths,
  where A2's structural check alone called the strategy valid; a valid
  strategy still validates; a strategy naming another Challenge is refused
  as the compiler refuses it; and it dispatches, admits and stores nothing;
- under a plan that froze argument-normalisation.v2, a practice call's
  action and arguments sent as the string "null" build the request real null
  builds, byte for byte, through the SDK and through the miner MCP door, and
  the ledger binds what was sent;
- under a plan frozen before v2 (none, or v1), the same call is refused
  exactly as before - at the door INVALID_ARGUMENT, nothing dispatched,
  nothing bound - and the refusal now carries its registered correction, to
  Graphite's miner path and, as its field, on the MCP wire;
- frozen plans and tool surfaces replay byte for byte.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_lp_prod_research_tools import ledger, sdk_for
from test_standard_mcp_adapter import make_adapter
from test_standard_mcp_adapter import practice as door_practice

from carbon import research
from carbon.development_session import research_service, research_tools
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_catalog import RecipeRejected
from carbon.development_session.research_service import BURGERS_SCAFFOLD
from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION,
    ARGUMENT_NORMALISATION_V2,
    PREFIX,
    TOOLS,
    TOOLS_RULE,
    TOOLS_V2,
    ResearchMinerTools,
    campaign_argument_normalisation,
    frozen_argument_normalisation,
    normalised_task_arguments,
    task_correction,
    tools_for_sdk,
)
from carbon.miner_mcp import standard
from carbon.miner_mcp.standard import (
    AdapterCode,
    AdapterFailure,
    ResearchToolAdapter,
    ResearchToolRequest,
)
from carbon.reconstruction import capability_registry as registry
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

BATTERY = registry.BATTERY_CHALLENGE
OPERATION_ID = "tool-usability-operation-0001"


# ---- 1. dry_validate answers as the submission path does.


def battery(parameters, backbone="knn"):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": backbone,
        "parameters": parameters,
    }


def battery_composition(path):
    """A real battery research composition; its practice and material fail
    the test if anything reaches them."""
    from carbon.battery.research import make_battery_research_service

    meter = ledger(path / "ledger")
    composition = make_battery_research_service(
        root=path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=SimpleNamespace(root=path),
        material=lambda *a: pytest.fail("dry_validate reached public material"),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    return sdk, meter, composition


@pytest.fixture
def battery_door(tmp_path):
    sdk, meter, composition = battery_composition(tmp_path)
    try:
        yield sdk, meter, composition
    finally:
        composition.tasks.close()


def dry_validate(sdk, strategy):
    """dry_validate through the SDK's own request and the composition's real
    service; the reply's (valid, issues as (code, path))."""
    request = sdk._request(
        "dry_validate", {"strategy_json": json.dumps(strategy)}, OPERATION_ID
    )
    reply = sdk.composition.service.call(
        research.ServiceCall(research.RESEARCH_NAMESPACE, "dry_validate", request)
    )
    assert reply.status is research.ReplyStatus.OK, reply
    result = reply.result
    assert type(result) is research.DryValidationResult
    return result.valid, tuple(
        (i.code, "/" + "/".join(i.path) if i.path else "") for i in result.issues
    )


def authoritative(strategy):
    """What the submission path refuses `strategy` with: (code, path) each."""
    try:
        compile_submission(strategy)
    except SubmissionRefused as refused:
        return tuple((i.code, i.path) for i in refused.issues)
    except RecipeRejected as rejected:
        return tuple((i.code, i.path) for i in rejected.rejected.issues)
    return ()


def structural(strategy, key):
    """A2's structural verdict alone, as dry_validate answered before."""
    return research.A2ValidationProvider().dry_validate(
        research.DryValidateRequest(key, strategy)
    )


@pytest.mark.parametrize(
    ("label", "strategy", "expected"),
    [
        (
            "neighbours_out_of_domain",
            battery({"neighbours": -5}),
            (("parameter.domain_mismatch", "/parameters/neighbours"),),
        ),
        (
            "family_settings_nested_under_the_family",
            battery({"knn": {"neighbours": 5}}),
            (("parameter.unknown", "/parameters/knn"),),
        ),
        (
            "value_wrapped_parameter",
            battery({"neighbours": {"value": 5}}),
            (("strategy.parameter_shape_invalid", "/parameters"),),
        ),
        (
            "unknown_parameter",
            battery({"neighbors_count": 5}),
            (("parameter.unknown", "/parameters/neighbors_count"),),
        ),
        (
            "excluded_parameter",
            battery({"label_method": "x"}, "mlp"),
            (("parameter.not_rebuildable", "/parameters/label_method"),),
        ),
        (
            "research_only_parameter",
            battery({"heads": 2}, "mlp"),
            (("parameter.not_rebuildable", "/parameters/heads"),),
        ),
        (
            "research_only_family",
            battery({}, "gino"),
            (("backbone.not_rebuildable", "/backbone"),),
        ),
    ],
)
def test_dry_validate_refuses_what_the_submission_path_refuses(
    battery_door, label, strategy, expected
):
    sdk, _, composition = battery_door
    # The finding: A2's structural check alone called these valid (an
    # unknown key is the one it already named by itself).
    if label not in ("unknown_parameter",):
        assert structural(strategy, composition.challenge).valid is True, label
    assert authoritative(strategy) == expected
    assert dry_validate(sdk, strategy) == (False, expected)


@pytest.mark.parametrize(
    "strategy",
    [
        battery({"neighbours": 5}),
        battery({"steps": 2000, "width": 64, "depth": 3}, "mlp"),
    ],
)
def test_a_valid_strategy_still_validates(battery_door, strategy):
    sdk, _, _ = battery_door
    assert authoritative(strategy) == ()
    assert dry_validate(sdk, strategy) == (True, ())


def test_a_strategy_naming_another_challenge_is_refused_as_the_compiler_refuses_it(
    battery_door,
):
    sdk, _, composition = battery_door
    # Valid under its own (Burgers) contract, so never compiled under it here.
    assert authoritative(BURGERS_SCAFFOLD) == ()
    valid, issues = dry_validate(sdk, BURGERS_SCAFFOLD)
    assert (valid, issues) == (
        False,
        (("strategy.challenge_mismatch", "/challenge_id"),),
    )
    # The composition's own compile_strategy names the same code and path.
    compiled = composition.service.call(
        research.ServiceCall(
            research.RESEARCH_NAMESPACE,
            "compile_strategy",
            sdk._request(
                "compile_strategy",
                {"strategy_json": json.dumps(BURGERS_SCAFFOLD)},
                OPERATION_ID,
            ),
        )
    ).result
    assert [(i.code, "/" + "/".join(i.path)) for i in compiled.issues] == [
        ("strategy.challenge_mismatch", "/challenge_id")
    ]


def test_a_malformed_challenge_id_is_named_by_the_contracts_structural_check(
    battery_door,
):
    sdk, _, _ = battery_door
    strategy = {**battery({"neighbours": 5}), "challenge_id": "Not An Id"}
    expected = authoritative(strategy)
    assert expected == (("identifier.invalid", "/challenge_id"),)
    assert dry_validate(sdk, strategy) == (False, expected)


def test_the_burgers_composition_answers_with_its_own_contract(tmp_path):
    sdk, _, composition = sdk_for(tmp_path)
    try:
        assert dry_validate(sdk, BURGERS_SCAFFOLD) == (True, ())
        odd = {
            **BURGERS_SCAFFOLD,
            "parameters": {**BURGERS_SCAFFOLD["parameters"], "n_modes": 15},
        }
        expected = authoritative(odd)
        assert expected == (("parameter.domain_mismatch", "/parameters/n_modes"),)
        assert structural(odd, composition.challenge).valid is True
        assert dry_validate(sdk, odd) == (False, expected)
    finally:
        composition.tasks.close()


def test_the_gpu_practice_composition_keeps_the_structural_check(tmp_path):
    """GPU practice recipes are its own catalogue's, not Challenge
    submissions: its composition keeps A2 (`contract_validation=False`)."""
    from dataclasses import replace

    from carbon.battery.research import challenge_parts

    parts = challenge_parts()
    assert parts.contract_validation is True
    meter = ledger(tmp_path / "ledger")
    structural_only = research_service.compose_research_service(
        replace(parts, contract_validation=False),
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=SimpleNamespace(),
    )
    try:
        provider = structural_only.service._context.validation_provider
        assert type(provider) is research.A2ValidationProvider
    finally:
        structural_only.tasks.close()


def test_validation_refuses_a_request_bound_to_another_challenge(battery_door):
    _, _, composition = battery_door
    provider = composition.service._context.validation_provider
    assert type(provider) is research_service.ChallengeContractValidation
    other = research.DryValidateRequest(
        research_service.CHALLENGE, battery({"neighbours": 5})
    )
    with pytest.raises(ValueError, match="validation binding differs"):
        provider.dry_validate(other)
    # The service answers it as a public error, never as a verdict.
    reply = composition.service.call(
        research.ServiceCall(research.RESEARCH_NAMESPACE, "dry_validate", other)
    )
    assert reply.status is research.ReplyStatus.ERROR


def ledger_rows(meter):
    """Every row of every ledger table: what a dispatch, admission, charge
    or note would change."""
    with meter.db() as db:
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {t: db.execute(f"SELECT * FROM {t}").fetchall() for t in tables}


def files(root):
    return sorted(
        (str(p.relative_to(root)), p.stat().st_size)
        for p in root.rglob("*")
        if p.is_file()
    )


def test_dry_validate_dispatches_admits_and_stores_nothing(
    battery_door, tmp_path, monkeypatch
):
    sdk, meter, composition = battery_door
    compiled = []
    original = research_service.submission_issues

    def spy(strategy, challenge):
        compiled.append(challenge)
        return original(strategy, challenge)

    monkeypatch.setattr(research_service, "submission_issues", spy)
    touched = []
    tasks = type(composition.tasks)
    for name in (
        "start_research_task",
        "run_queued_task",
        "get_research_result",
        "cancel_research_task",
    ):
        monkeypatch.setattr(
            tasks,
            name,
            lambda *a, _name=name, **k: touched.append(_name),
        )
    executor = type(composition.executor)
    for name in ("_workspace_action", "public_result"):
        if hasattr(executor, name):
            monkeypatch.setattr(
                executor, name, lambda *a, _name=name, **k: touched.append(_name)
            )
    rows, tree = ledger_rows(meter), files(tmp_path)
    for strategy in (battery({"neighbours": -5}), battery({"neighbours": 5})):
        dry_validate(sdk, strategy)
    # The authoritative compile ran, for this Challenge, twice ...
    assert compiled == [BATTERY, BATTERY]
    # ... and nothing was dispatched, admitted, charged, noted or written.
    assert touched == []
    assert ledger_rows(meter) == rows
    assert files(tmp_path) == tree
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


# ---- 2. Practice "null" under the frozen argument normalisation.

NORMALISING_V2 = {
    "agent": "graphite",
    "research_tools": TOOLS_RULE,
    "argument_normalisation": ARGUMENT_NORMALISATION_V2,
}
NORMALISING_V1 = {
    "agent": "graphite",
    "research_tools": TOOLS_RULE,
    "argument_normalisation": ARGUMENT_NORMALISATION,
}
FROZEN_BEFORE = {"agent": "graphite", "research_tools": TOOLS_RULE}
OLDER_PLANS = [None, "test-only", FROZEN_BEFORE, NORMALISING_V1]


def sdk_practice(action=None, arguments_json=None):
    return {
        "kind": "practice",
        "strategy_json": json.dumps(BURGERS_SCAFFOLD),
        "action": action,
        "arguments_json": arguments_json,
        "hypothesis": "a bounded practice run",
        "expected_effect": "a practice result",
    }


@pytest.mark.parametrize(
    ("action", "arguments_json"),
    [("null", None), (None, "null"), ("null", "null")],
)
def test_a_practice_null_string_builds_the_real_null_request_under_v2(
    tmp_path, action, arguments_json
):
    sdk, _, composition = sdk_for(tmp_path, provider=NORMALISING_V2)
    try:
        assert campaign_argument_normalisation(sdk.ledger) == ARGUMENT_NORMALISATION_V2
        sent = sdk_practice(action, arguments_json)
        before = json.loads(canonical(sent))
        request = sdk._request("start_research_task", sent, OPERATION_ID)
        assert research.canonical_bytes(request) == research.canonical_bytes(
            sdk._request("start_research_task", sdk_practice(), OPERATION_ID)
        )
        # What was sent is unchanged: it is what the ledger binds.
        assert sent == before
    finally:
        composition.tasks.close()


def test_v2_keeps_v1s_workspace_reading_and_refuses_a_practice_strategy_null():
    workspace = {"kind": "workspace", "strategy_json": "null", "action": "inventory"}
    assert normalised_task_arguments(workspace, ARGUMENT_NORMALISATION_V2) == {
        **workspace,
        "strategy_json": None,
    }
    # A practice recipe is required: its "null" is never read as null.
    recipe = {"kind": "practice", "strategy_json": "null", "action": None}
    assert normalised_task_arguments(recipe, ARGUMENT_NORMALISATION_V2) is recipe


@pytest.mark.parametrize("provider", OLDER_PLANS)
@pytest.mark.parametrize("field", ["action", "arguments_json"])
def test_an_older_plan_refuses_a_practice_null_in_the_sdk_as_before(
    tmp_path, provider, field
):
    sdk, meter, composition = sdk_for(tmp_path, provider=provider)
    sdk.connection = RefusingConnection()
    try:
        sent = {**sdk_practice(), field: "null"}
        result = asyncio.run(
            sdk.call(PREFIX + "start_research_task", sent, OPERATION_ID)
        )
        assert result["status"] == "REJECTED_BEFORE_DISPATCH"
        assert (result["correction_code"], result["field"]) == (
            "practice_recipe_required",
            field,
        )
        assert result["correction"] == task_correction(
            "practice_recipe_required", field, "null", tool="start_research_task"
        )
        assert meter.status(owner="alice")["used"]["research_trials"] == 0
    finally:
        composition.tasks.close()


class RefusingConnection:
    """The campaign's connection: its admission check runs after the request
    is built and refuses, so nothing is ever signed or dispatched."""

    async def check_registration(self):
        raise ValueError("campaign admission stopped")


def door_for(path, provider):
    """The miner MCP door over a real SDK, a real Burgers composition and a
    ledger whose run plan is `provider`, capturing each request the SDK
    builds."""
    sdk, meter, composition = sdk_for(path, provider=provider)
    sdk.connection = RefusingConnection()
    sdk.wrapper = object()
    built = []
    build = sdk._request

    def capture(operation, args, identity):
        request = build(operation, args, identity)
        built.append(request)
        return request

    sdk._request = capture
    return ResearchToolAdapter(sdk, principal="alice"), meter, composition, built


def door_args(**fields):
    return {
        "kind": "practice",
        "strategy": BURGERS_SCAFFOLD,
        "action": None,
        "arguments": None,
        "hypothesis": "a bounded practice run",
        "expected_effect": "a practice result",
        **fields,
    }


def bound_digest(meter, identity):
    with meter.db() as db:
        row = db.execute(
            "SELECT request_digest FROM operations WHERE id=?",
            ("task-request-" + identity,),
        ).fetchone()
    return None if row is None else row[0]


def through_door(adapter, arguments):
    with pytest.raises(AdapterFailure) as raised:
        asyncio.run(
            adapter.call(
                ResearchToolRequest("start_research_task", OPERATION_ID, arguments)
            )
        )
    return raised.value


@pytest.mark.parametrize(
    "nulls",
    [
        {"action": "null"},
        {"arguments": "null"},
        {"action": "null", "arguments": "null"},
    ],
)
def test_a_practice_null_string_passes_the_door_under_v2(tmp_path, nulls):
    adapter, meter, composition, built = door_for(tmp_path / "null", NORMALISING_V2)
    real, real_meter, real_composition, real_built = door_for(
        tmp_path / "real", NORMALISING_V2
    )
    try:
        stopped = through_door(adapter, door_args(**nulls))
        # Refused only at the admission check, after the request was built:
        # nothing was signed or dispatched.
        assert stopped.code is AdapterCode.CAMPAIGN_ADMISSION_STOPPED
        assert stopped.dispatch_may_have_occurred is False
        through_door(real, door_args())
        # The request is the one real null builds, byte for byte ...
        assert len(built) == len(real_built) == 1
        assert research.canonical_bytes(built[0]) == research.canonical_bytes(
            real_built[0]
        )
        # ... and the ledger bound what was sent, not the normalised request.
        sent = {
            "kind": "practice",
            "strategy_json": canonical(BURGERS_SCAFFOLD).decode(),
            "action": nulls.get("action"),
            "arguments_json": nulls.get("arguments"),
            "hypothesis": "a bounded practice run",
            "expected_effect": "a practice result",
        }
        assert bound_digest(meter, OPERATION_ID) == digest(canonical(sent))
        assert bound_digest(real_meter, OPERATION_ID) != bound_digest(
            meter, OPERATION_ID
        )
    finally:
        composition.tasks.close()
        real_composition.tasks.close()


@pytest.mark.parametrize("provider", OLDER_PLANS)
@pytest.mark.parametrize(
    ("field", "sdk_field"), [("action", "action"), ("arguments", "arguments_json")]
)
def test_an_older_plan_refuses_a_practice_null_at_the_door_with_a_correction(
    tmp_path, provider, field, sdk_field
):
    adapter, meter, composition, built = door_for(tmp_path, provider)
    try:
        refused = through_door(adapter, door_args(**{field: "null"}))
        # Exactly as before: INVALID_ARGUMENT, nothing dispatched, the SDK
        # never reached and nothing bound ...
        assert refused.code is AdapterCode.INVALID_ARGUMENT
        assert refused.dispatch_may_have_occurred is False
        assert built == []
        assert bound_digest(meter, OPERATION_ID) is None
        # ... and now with its registered correction, in object terms.
        assert refused.correction == {
            "correction_code": "practice_recipe_required",
            "field": field,
            "correction": standard.object_wording(
                task_correction(
                    "practice_recipe_required",
                    sdk_field,
                    "null",
                    tool="start_research_task",
                )
            ),
        }
        assert 'It holds the string "null".' in refused.correction["correction"]
        assert refused.field == field
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"strategy": None}, "strategy"),
        ({"action": "inventory"}, "action"),
        ({"arguments": {}}, "arguments"),
    ],
)
def test_every_practice_refusal_at_the_door_carries_its_correction(fields, field):
    _, adapter = make_adapter()
    refused = through_door(adapter, door_args(**fields))
    assert refused.code is AdapterCode.INVALID_ARGUMENT
    assert refused.dispatch_may_have_occurred is False
    assert refused.correction["correction_code"] == "practice_recipe_required"
    assert refused.correction["field"] == field
    assert "_json" not in refused.correction["correction"]


def test_an_unknown_frozen_rule_reads_no_null(tmp_path):
    adapter, meter, composition, built = door_for(
        tmp_path, {"agent": "graphite", "argument_normalisation": "v9"}
    )
    try:
        refused = through_door(adapter, door_args(action="null"))
        assert refused.code is AdapterCode.INVALID_ARGUMENT
        assert refused.field == "action"
        assert built == []
        assert bound_digest(meter, OPERATION_ID) is None
    finally:
        composition.tasks.close()


def test_a_valid_practice_still_reaches_the_sdk_under_every_plan(tmp_path):
    for name, provider in (
        ("none", None),
        ("v1", NORMALISING_V1),
        ("v2", NORMALISING_V2),
    ):
        adapter, _, composition, built = door_for(tmp_path / name, provider)
        try:
            stopped = through_door(adapter, door_args())
            assert stopped.code is AdapterCode.CAMPAIGN_ADMISSION_STOPPED
            assert len(built) == 1
        finally:
            composition.tasks.close()


# ---- 3. The refusal's correction reaches Graphite's miner path and the wire.


def test_graphite_s_miner_path_receives_the_correction(tmp_path):
    from carbon.agent_campaign.graphite.miner_path import MinerPathTools

    adapter, _, composition, _ = door_for(tmp_path, FROZEN_BEFORE)
    try:
        tools = MinerPathTools(adapter, session="usability")
        result = asyncio.run(
            tools.call(
                PREFIX + "start_research_task",
                sdk_practice(action="null", arguments_json="null"),
                "start-0001",
            )
        )
        assert result["status"] == "MINER_PATH_REFUSED"
        assert result["reason_code"] == "INVALID_ARGUMENT"
        assert result["dispatch_may_have_occurred"] is False
        assert result["requires_reconciliation"] is False
        assert result["correction_code"] == "practice_recipe_required"
        assert result["field"] == "action"
        assert 'not the string "null"' in result["correction"]
    finally:
        composition.tasks.close()


def test_graphite_s_miner_path_passes_a_practice_null_under_v2(tmp_path):
    from carbon.agent_campaign.graphite.miner_path import MinerPathTools

    adapter, _, composition, built = door_for(tmp_path, NORMALISING_V2)
    try:
        tools = MinerPathTools(adapter, session="usability")
        result = asyncio.run(
            tools.call(
                PREFIX + "start_research_task",
                sdk_practice(action="null", arguments_json="null"),
                "start-0001",
            )
        )
        # Stopped only at admission, after the request was built.
        assert result["reason_code"] == "CAMPAIGN_ADMISSION_STOPPED"
        assert len(built) == 1
    finally:
        composition.tasks.close()


def test_the_mcp_tool_names_the_refused_practice_field(tmp_path):
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.standard_server import _create_server

    _, adapter = make_adapter()
    server = _create_server(adapter)
    with pytest.raises(ToolError) as raised:
        asyncio.run(
            server.call_tool(
                PREFIX + "start_research_task",
                {**door_practice(), "arguments": {}, "operation_id": OPERATION_ID},
            )
        )
    assert (
        "INVALID_ARGUMENT; dispatch_may_have_occurred=false; field=arguments; "
        "next_action="
    ) in str(raised.value)


def test_the_tasks_start_names_the_refused_practice_field(monkeypatch):
    from test_lp_prod_mcp_door import start, tasks_extension

    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)
    text = start(extension, ctx, {**door_practice(), "action": "inventory"})
    assert text.startswith(
        "INVALID_ARGUMENT; dispatch_may_have_occurred=false; field=action; "
    )


def test_a_refusal_without_a_correction_names_no_field():
    assert AdapterFailure(AdapterCode.INVALID_ARGUMENT).field is None
    with pytest.raises(AdapterFailure) as raised:
        standard._arguments("start_research_task", {**door_practice(), "kind": "x"})
    assert raised.value.correction is None


# ---- 4. Frozen plans and tool surfaces replay byte for byte.

#: canonical(TOOLS_V2) and a new Graphite plan with its rule set back to v1,
#: each as the base commit (b327ac12) computed them from its own modules.
TOOLS_V2_DIGEST = (
    "sha256:ffca9d1bad52aa4b8df367c85c5e1b38fbc599102d43fbbcf30e717decb442df"
)
HISTORICAL_TOOLS_DIGEST = (
    "sha256:1666c0e6eb1334b1d99e48a9ce9495327c7616878829bc141cca43497b329edc"
)
GRAPHITE_PLAN_V1_DIGEST = (
    "sha256:32251687587a288057a218830a47020ad1b8f60d16b5a383ee6986a12cce344b"
)


def test_frozen_plans_and_tool_surfaces_replay_unchanged(tmp_path):
    import test_battery_graphite_plan as plans

    from carbon.battery import campaign as battery_campaign
    from carbon.challenge_registry import agent_plan

    frozen = plans.block(
        mode="FULL",
        research_share=0.25,
        hunt={"queries": ["fast charge ageing"]},
        limits={"calls_per_epoch": 200, "trials_per_epoch": 20, "planner_calls": 30},
    )
    for new in (
        battery_campaign.provider_plan("graphite", plans.BUDGET, None, graphite=frozen),
        agent_plan.graphite_plan(plans.BUDGET, None, frozen),
    ):
        # A new plan freezes v2; with v1 in its place it is byte for byte the
        # plan the base commit froze: v2 is the only prospective change.
        assert new["argument_normalisation"] == ARGUMENT_NORMALISATION_V2
        old = {**new, "argument_normalisation": ARGUMENT_NORMALISATION}
        assert digest(canonical(old)) == GRAPHITE_PLAN_V1_DIGEST
    # A manifest frozen with v1, or with no rule, reads as it was frozen:
    # v1 stays registered, so its campaigns replay and continue under v1.
    for name, provider, rule in (
        ("v1", NORMALISING_V1, ARGUMENT_NORMALISATION),
        ("before", FROZEN_BEFORE, None),
        ("v2", NORMALISING_V2, ARGUMENT_NORMALISATION_V2),
    ):
        meter = ledger(tmp_path / name, provider=provider)
        with meter.db() as db:
            stored = db.execute("SELECT manifest FROM campaign").fetchone()
        assert frozen_argument_normalisation(json.loads(stored[0])) == rule
        assert campaign_argument_normalisation(meter) == rule
        # The tools offered are the ones the plan froze, byte for byte.
        assert tools_for_sdk(SimpleNamespace(ledger=meter)) is TOOLS_V2
    assert digest(canonical(TOOLS)) == HISTORICAL_TOOLS_DIGEST
    assert digest(canonical(TOOLS_V2)) == TOOLS_V2_DIGEST
    assert research_tools.ARGUMENT_NORMALISATIONS == (
        ARGUMENT_NORMALISATION,
        ARGUMENT_NORMALISATION_V2,
    )
