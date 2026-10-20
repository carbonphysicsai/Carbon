"""A direct campaign's practice names what it needs (BUG
GRAPHITE_PRACTICE_CALL_REFUSED_20261020).

Every new Launchpad campaign is direct: kind=practice takes a
carbon.construction-recipe.v1 document in strategy_json. Graphite sent a
Level 0 strategy, the recipe refused it, and research_tools' catch-all
answered tool_value_invalid on `arguments`, naming nothing the agent could
correct; it then spent ~50 calls guessing encodings. The refusal now names
strategy_json, says what a direct recipe holds, and lists the recipe's own
refusal code. Driven through the Chat Completions encoding: the arguments
arrive as one JSON string, decoded as Graphite's provider decodes them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_lp_prod_research_tools import ledger, refused

from carbon.battery import construction_kit
from carbon.battery.research import SCAFFOLD, make_battery_research_service
from carbon.development_session import construction_recipe
from carbon.development_session.research_tools import (
    RECIPE_REFUSAL_CODES,
    ResearchMinerTools,
)

IDENTITY = "lp-direct-practice-0001"


@pytest.fixture
def direct_door(tmp_path):
    meter = ledger(tmp_path / "ledger")
    composition = make_battery_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=SimpleNamespace(root=tmp_path, construction_mode="direct"),
        material=lambda *a: pytest.fail("a refused practice reached material"),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    try:
        yield sdk, meter
    finally:
        composition.tasks.close()


def chat_completions(arguments: dict) -> dict:
    """A Chat Completions tool call carries its arguments as one JSON string."""
    return json.loads(json.dumps(arguments))


def practice(strategy_json):
    return chat_completions(
        {
            "kind": "practice",
            "strategy_json": strategy_json,
            "action": None,
            "arguments_json": None,
            "hypothesis": "a baseline practice",
            "expected_effect": "a practice score",
        }
    )


def test_a_level0_strategy_is_refused_naming_strategy_json_and_the_recipe(direct_door):
    sdk, meter = direct_door
    result = refused(sdk, meter, practice(json.dumps(SCAFFOLD)), IDENTITY)
    assert result["correction_code"] == "direct_recipe_required"
    assert result["field"] == "strategy_json"
    assert "carbon.construction-recipe.v1" in result["correction"]
    assert "construction_recipe_malformed" in result["correction"]


def test_a_direct_recipe_builds_its_practice_request(direct_door):
    sdk, _ = direct_door
    kit = construction_kit.construction_kit()
    recipe = {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
        "procedure": {
            "entrypoint": None,
            "configuration": {"training": {"steps": 2000}},
            "train_use": {
                "dataset": "battery-pinned-train-v1",
                "train_fraction": 1.0,
                "curriculum": "none",
            },
            "initial_state": None,
        },
        "output": {
            "format": "carbon.battery.raw-numeric.v1",
            "interface_digest": kit["interface_digest"],
        },
    }
    request = sdk._request(
        "start_research_task", practice(json.dumps(recipe)), IDENTITY
    )
    assert type(request.task_spec).__name__ == "DirectPracticeTaskSpecV1"


def test_the_listed_codes_are_exactly_the_recipes_own():
    source = Path(construction_recipe.__file__).read_text(encoding="utf-8")
    assert RECIPE_REFUSAL_CODES == set(
        re.findall(r'RecipeRefused\("(construction_recipe_[a-z_]+)"\)', source)
    )


# --- BUG GRAPHITE_SCAFFOLD_UNREACHABLE_20261020 --------------------------------
# Battery run 21e560f0: Graphite was refused public_material_unknown on
# arguments_json.name and never reached scaffold_recipe, which Battery's
# discovery listed but the door refused.


@pytest.fixture
def material_door(tmp_path):
    from carbon.battery.research import BatteryPublicMaterial

    meter = ledger(tmp_path / "ledger")
    composition = make_battery_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=SimpleNamespace(root=tmp_path, construction_mode="direct"),
        material=BatteryPublicMaterial(Path(__file__).resolve().parents[2]),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    try:
        yield sdk, meter
    finally:
        composition.tasks.close()


def material(name):
    return chat_completions(
        {
            "kind": "workspace",
            "strategy_json": None,
            "action": "public_material",
            "arguments_json": json.dumps({"name": name}),
            "hypothesis": "read the public material",
            "expected_effect": "a document in the workspace",
        }
    )


def test_the_scaffold_recipe_passes_the_material_door(material_door):
    sdk, _ = material_door
    request = sdk._request("start_research_task", material("scaffold_recipe"), IDENTITY)
    assert request.task_spec.action == "public_material"


def test_an_unknown_material_lists_every_name_discovery_lists(material_door):
    from carbon.battery.research import BatteryPublicMaterial

    sdk, meter = material_door
    result = refused(sdk, meter, material("simple bundle string"), IDENTITY)
    assert result["correction_code"] == "public_material_unknown"
    assert (
        "Allowed here: " + ", ".join(BatteryPublicMaterial.NAMES) + "."
        in result["correction"]
    )
    assert "scaffold_recipe" in BatteryPublicMaterial.NAMES


def test_the_recipe_correction_says_how_to_get_the_scaffold(direct_door):
    sdk, meter = direct_door
    result = refused(
        sdk,
        meter,
        practice(json.dumps({"source": "resolved_plan_ref as source bundle"})),
        IDENTITY,
    )
    assert result["correction_code"] == "direct_recipe_required"
    for words in ("action=public_material", "scaffold_recipe", "kind=workspace"):
        assert words in result["correction"]


def test_the_scaffold_name_is_batterys():
    from carbon.battery.research import BatteryPublicMaterial
    from carbon.development_session.research_tasks import SCAFFOLD_RECIPE

    assert SCAFFOLD_RECIPE in BatteryPublicMaterial.NAMES
