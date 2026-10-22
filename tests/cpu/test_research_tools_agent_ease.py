"""Research tools an agent can use without stalling on the tool contract
(M1 Launchpad test run, 2026-10-22: G4, G5).

Claims tested, each absence paired with the same check finding a presence:

- G4: under a plan that froze argument-normalisation.v5, a start_research_task
  field its kind takes only as JSON null may be left out - a workspace read
  without strategy_json passes the SDK, Graphite's miner path and the MCP
  server, and builds the request explicit null builds - while a plan that
  froze v4 (or none) still refuses it tool_field_missing and replays as it
  was; new Graphite plans freeze v5, and the external MCP server's own schema
  defaults the field to null under every plan;
- G5a: a construction recipe refused on a catalog version lists the source
  kinds the version takes (source.<kind>) beside the recipe's own code;
- G5b: every catalog version serves scaffold_recipe - one ready recipe or
  template per source kind it takes - and lists it in its description;
- G5c: dry_validate and compile_strategy name strategy_json, and a key the
  research wire refuses in a strategy (a graph recipe's dataset) is named
  strategy_control_field_forbidden with the forms it matched;
- G5d: a correction naming arguments_json.files says what files is.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from test_agent_door_usability import refused_text, server_for
from test_lp_prod_research_tools import sdk_for
from test_research_tool_usability import (
    OPERATION_ID,
    RefusingConnection,
    door_for,
)

from carbon import research
from carbon.development_session import research_tools
from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION_V4,
    ARGUMENT_NORMALISATION_V5,
    ARGUMENT_NORMALISATIONS,
    FIELD_HINTS,
    PREFIX,
    TOOLS_RULE,
    TaskContractMismatch,
    correction_parts,
    filled_task_arguments,
    forbidden_strategy_forms,
    task_correction,
)

START = PREFIX + "start_research_task"
V5 = {
    "agent": "graphite",
    "research_tools": TOOLS_RULE,
    "argument_normalisation": ARGUMENT_NORMALISATION_V5,
}
V4 = {**V5, "argument_normalisation": ARGUMENT_NORMALISATION_V4}
READ = {
    "kind": "workspace",
    "action": "public_material",
    "arguments_json": json.dumps({"name": "objective"}),
    "hypothesis": "read the objective",
    "expected_effect": "the objective document",
}


# ---- G4. An omitted null-only field is JSON null under v5.


def test_v5_is_registered_last_and_new_graphite_plans_freeze_it():
    from carbon.battery.campaign import graphite_plan as battery_plan
    from carbon.challenge_registry.agent_plan import graphite_plan

    assert ARGUMENT_NORMALISATIONS[-1] == ARGUMENT_NORMALISATION_V5
    assert ARGUMENT_NORMALISATIONS[-2] == ARGUMENT_NORMALISATION_V4
    # Both builders name the one constant they freeze.
    for builder in (graphite_plan, battery_plan):
        names = builder.__code__.co_names
        assert "ARGUMENT_NORMALISATION_V5" in names
        assert "ARGUMENT_NORMALISATION_V4" not in names


def test_v5_fills_only_a_left_out_field_the_kind_takes_as_null():
    read = filled_task_arguments(READ, ARGUMENT_NORMALISATION_V5)
    assert read == {**READ, "strategy_json": None}
    assert "strategy_json" not in READ  # what was sent is unchanged
    practice = {"kind": "practice", "strategy_json": "{}"}
    assert filled_task_arguments(practice, ARGUMENT_NORMALISATION_V5) == {
        **practice,
        "action": None,
        "arguments_json": None,
    }
    # A practice recipe is never filled: it stays missing, and refused.
    assert filled_task_arguments({"kind": "practice"}, ARGUMENT_NORMALISATION_V5) == {
        "kind": "practice",
        "action": None,
        "arguments_json": None,
    }
    # A field sent is kept as sent, null or not.
    sent = {**READ, "strategy_json": "{}"}
    assert filled_task_arguments(sent, ARGUMENT_NORMALISATION_V5) is sent
    # Every older rule, and no rule, fills nothing.
    for rule in (None, *ARGUMENT_NORMALISATIONS[:-1]):
        assert filled_task_arguments(READ, rule) is READ


def _sdk_call(sdk, args):
    return asyncio.run(sdk.call(START, args, OPERATION_ID))


def test_a_workspace_read_without_strategy_json_passes_the_sdk_under_v5(tmp_path):
    sdk, meter, composition = sdk_for(tmp_path / "v5", provider=V5)
    real, _, real_composition = sdk_for(tmp_path / "real", provider=V5)
    try:
        for tools in (sdk, real):
            tools.connection = RefusingConnection()
        built = sdk._request(
            "start_research_task",
            filled_task_arguments(READ, ARGUMENT_NORMALISATION_V5),
            OPERATION_ID,
        )
        explicit = real._request(
            "start_research_task", {**READ, "strategy_json": None}, OPERATION_ID
        )
        assert research.canonical_bytes(built) == research.canonical_bytes(explicit)
        # Through the SDK's own call: past every field check, stopped only
        # by the campaign's admission, after the request was built.
        with pytest.raises(ValueError, match="campaign admission stopped"):
            _sdk_call(sdk, dict(READ))
        assert meter.status(owner="alice")["used"]["research_trials"] == 0
    finally:
        composition.tasks.close()
        real_composition.tasks.close()


@pytest.mark.parametrize("provider", [V4, None])
def test_an_older_plan_still_refuses_the_left_out_field(tmp_path, provider):
    sdk, _, composition = sdk_for(tmp_path, provider=provider)
    sdk.connection = RefusingConnection()
    try:
        result = _sdk_call(sdk, dict(READ))
        assert result["status"] == "REJECTED_BEFORE_DISPATCH"
        assert (result["correction_code"], result["field"]) == (
            "tool_field_missing",
            "strategy_json",
        )
    finally:
        composition.tasks.close()


def test_graphite_s_miner_path_reads_the_left_out_field_as_null_under_v5(tmp_path):
    from carbon.agent_campaign.graphite.miner_path import MinerPathTools

    adapter, _, composition, built = door_for(tmp_path / "v5", V5)
    old, _, old_composition, old_built = door_for(tmp_path / "v4", V4)
    try:
        result = asyncio.run(
            MinerPathTools(adapter, session="ease").call(START, dict(READ), "read-1")
        )
        assert result["reason_code"] == "CAMPAIGN_ADMISSION_STOPPED", result
        assert len(built) == 1
        # A v4 plan's Graphite is refused as before, naming the field.
        result = asyncio.run(
            MinerPathTools(old, session="ease").call(START, dict(READ), "read-1")
        )
        assert result["reason_code"] == "INVALID_ARGUMENT"
        assert (result["correction_code"], result["field"]) == (
            "tool_field_missing",
            "strategy",
        )
        assert old_built == []
    finally:
        composition.tasks.close()
        old_composition.tasks.close()


@pytest.mark.parametrize("provider", [V5, V4])
def test_the_mcp_server_defaults_strategy_to_null_under_every_plan(tmp_path, provider):
    adapter, _, composition, built = door_for(tmp_path, provider)
    try:
        arguments = {
            "kind": "workspace",
            "action": "public_material",
            "arguments": {"name": "objective"},
            "hypothesis": "read the objective",
            "expected_effect": "the objective document",
        }
        text = refused_text(server_for(adapter), arguments)
        assert "CAMPAIGN_ADMISSION_STOPPED" in text, text
        assert "tool_field_missing" not in text
        assert len(built) == 1
    finally:
        composition.tasks.close()


# ---- G5a. A refused recipe lists the source kinds the version takes.


def _direct_key(challenge_id, version):
    return research.ChallengeKey(challenge_id, version)


@pytest.mark.parametrize(
    ("challenge_id", "version"), [("f08-ribbed-bracket", "1.4"), ("f02", "2.3")]
)
def test_the_direct_versions_take_graph_and_catalog_recipes(challenge_id, version):
    from carbon.backbone_catalog import listing
    from carbon.development_session.research_service import recipe_source_kinds

    kinds = recipe_source_kinds(_direct_key(challenge_id, version))
    assert "graph" in kinds and "bundle" not in kinds
    assert ("catalog" in kinds) == bool(listing.entries(challenge_id, version))


def test_a_direct_recipe_refusal_lists_the_source_kinds():
    choices = ("construction_recipe_source_invalid", "source.graph", "source.catalog")
    refused = TaskContractMismatch("direct_recipe_required", "strategy_json", choices)
    text = task_correction(
        "direct_recipe_required", "strategy_json", None, choices=refused.choices
    )
    assert "Allowed here: construction_recipe_source_invalid, source.graph" in text
    parts = correction_parts(
        {
            "correction_code": "direct_recipe_required",
            "field": "strategy_json",
            "correction": text,
        }
    )
    assert parts is not None and parts.choices == choices
    # A kind outside the closed list is never listed.
    with pytest.raises(TypeError):
        TaskContractMismatch("direct_recipe_required", "strategy_json", ("source.x",))


# ---- G5b. Every catalog version serves a ready recipe per source kind.


class Workspace:
    def __init__(self):
        self.files = {}

    def put(self, name, body):
        self.files[name] = body


def _catalog_materials():
    from carbon.challenge_kit.served_versions import CATALOG, MOTOR
    from carbon.cold_plate.research import CoolingCatalogMaterial
    from carbon.direct_campaign.research import DirectPublicMaterial
    from carbon.direct_campaign.spec import SPECS
    from carbon.motor.research import MotorCatalogMaterial

    for challenge_id, version in sorted(CATALOG):
        if challenge_id in SPECS:
            yield challenge_id, version, DirectPublicMaterial(
                SPECS[challenge_id], version
            )
        elif challenge_id == MOTOR:
            yield challenge_id, version, MotorCatalogMaterial(version=version)
        else:
            yield challenge_id, version, CoolingCatalogMaterial(".", version)


def test_every_catalog_version_serves_scaffold_recipe():
    from carbon.development_session.research_service import recipe_source_kinds

    served = list(_catalog_materials())
    assert len(served) >= 4
    for challenge_id, version, material in served:
        assert "scaffold_recipe" in material.NAMES
        workspace = Workspace()
        reply = material("scaffold_recipe", workspace)
        document = reply["document"]
        kinds = recipe_source_kinds(_direct_key(challenge_id, version))
        assert document["source_kinds"] == list(kinds), challenge_id
        assert list(document["recipes"]) == list(kinds)
        assert workspace.files[reply["file"]]
        for kind, recipe in document["recipes"].items():
            assert recipe["schema"] == "carbon.construction-recipe.v1"
            assert recipe["source"]["kind"] == kind
        if "catalog" in kinds:
            catalog = material("catalog", Workspace())["document"]
            assert document["recipes"]["catalog"] == catalog["ready_recipe"]


def test_the_scaffold_names_are_in_the_door_s_closed_list():
    from carbon.development_session.research_tasks import public_material_names

    for _, _, material in _catalog_materials():
        assert "scaffold_recipe" in public_material_names(material)


def test_a_version_taking_no_source_kind_says_so(monkeypatch):
    from carbon.development_session import research_service, research_tasks

    monkeypatch.setattr(research_service, "recipe_source_kinds", lambda key: ())
    document = research_tasks.ready_recipes("motor", "1.2", {"catalog": dict})
    assert document["source_kinds"] == [] and document["recipes"] == {}
    assert "nothing can be practised" in document["use"]


# ---- G5c. dry_validate and compile_strategy name strategy_json.


def test_a_graph_recipe_s_dataset_is_named_as_a_forbidden_strategy_form():
    from carbon.challenge_registry.direct import graph_recipe
    from carbon.direct_campaign.spec import SPECS

    recipe = graph_recipe(SPECS["f02"], "sha256:" + "a" * 64, version="2.3")
    assert forbidden_strategy_forms(recipe) == ("dataset",)
    key = _direct_key("f02", "2.3")
    for constructor in (research.DryValidateRequest,):
        with pytest.raises(TaskContractMismatch) as raised:
            research_tools._strategy_request(constructor, key, recipe)
        assert raised.value.args == (
            "strategy_control_field_forbidden",
            "strategy_json",
        )
        assert raised.value.choices == ("dataset",)
    # A strategy with no refused key builds as before.
    assert forbidden_strategy_forms({"backbone": "fno"}) == ()


def test_the_catch_all_names_strategy_json_on_a_strategy_tool(tmp_path, monkeypatch):
    sdk, _, composition = sdk_for(tmp_path, provider=V5)
    try:

        def broken(*args):
            raise ValueError("not a request")

        for operation, name in (
            ("dry_validate", "DryValidateRequest"),
            ("compile_strategy", "CompileStrategyRequest"),
        ):
            monkeypatch.setattr(research, name, broken)
            result = asyncio.run(
                sdk.call(PREFIX + operation, {"strategy_json": "{}"}, OPERATION_ID)
            )
            assert (result["correction_code"], result["field"]) == (
                "tool_value_invalid",
                "strategy_json",
            )
            monkeypatch.undo()
        # A forbidden key reaches the agent with its own code and forms.
        result = asyncio.run(
            sdk.call(
                PREFIX + "dry_validate",
                {"strategy_json": json.dumps({"procedure": {"dataset": "x"}})},
                OPERATION_ID,
            )
        )
        assert result["correction_code"] == "strategy_control_field_forbidden"
        assert result["field"] == "strategy_json"
        assert "Allowed here: dataset." in result["correction"]
    finally:
        composition.tasks.close()


# ---- G5d. A correction naming files says what files is.


def test_a_correction_naming_files_says_what_files_is():
    text = task_correction(
        "workspace_field_missing",
        "arguments_json.files",
        None,
        tool="start_research_task",
    )
    assert FIELD_HINTS["arguments_json.files"] in text
    assert "[] stages none" in text
    # The door verifies it with the builder's own rule.
    assert (
        correction_parts(
            {
                "correction_code": "workspace_field_missing",
                "field": "arguments_json.files",
                "correction": text,
            }
        ).field
        == "arguments_json.files"
    )
    # A field without a hint is told nothing more.
    plain = task_correction("workspace_field_missing", "arguments_json.source", None)
    assert not any(hint in plain for hint in FIELD_HINTS.values())
