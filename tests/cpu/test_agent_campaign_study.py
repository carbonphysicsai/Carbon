"""The study sheet and permission inventory take a Challenge (GRAPHITE-ADMISSION-01 slice A).

Battery's sheet and inventory are unchanged byte for byte; a synthetic second
Challenge gets its own; a capability its map does not place is refused.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from carbon.agent_campaign import study
from carbon.battery import admission_study
from carbon.challenge_readiness import admission
from carbon.reconstruction import capability_registry as cr

REPOSITORY = Path(__file__).resolve().parents[2]
LEVEL0 = REPOSITORY / "docs/development/mira/level0"
SYNTHETIC = "synthetic-heat-sink-v1"
#: The capability-to-level map study.py held before slice A, word for word.
HISTORICAL_BATTERY_MAP = {
    "model_family": 0,
    "architecture": 0,
    "physical_structure": 0,
    "batching": 2,
    "optimizer": 2,
    "schedule": 2,
    "objective": 1,
    "stages": 2,
    "training_data": 2,
    "inference": 5,
}


def _bytes(value):
    return json.dumps(value, indent=1, sort_keys=True) + "\n"


def synthetic_contract(token=SYNTHETIC):
    rebuildable = cr.Status.REBUILDABLE_DEVELOPMENT
    return cr.ChallengeContract(
        token=token,
        version="1.0",
        identity="carbon.synthetic-heat-sink.v1",
        catalog_version="carbon.synthetic-heat-sink-recipes.v1",
        capabilities=(
            cr.Capability(
                "model_family.mlp",
                cr.Dimension.MODEL_FAMILY,
                "Synthetic MLP",
                rebuildable,
                selector="mlp",
                lab_kind="synthetic_mlp",
            ),
            cr.Capability(
                "architecture.width",
                cr.Dimension.ARCHITECTURE,
                "Width",
                rebuildable,
                surface=cr.Surface("model", "uint", 2, 64, 8),
            ),
            cr.Capability(
                "optimizer.learning_rate",
                cr.Dimension.OPTIMIZER,
                "Peak rate",
                rebuildable,
                surface=cr.Surface("train", "float", 1e-5, 0.1, 1e-3),
            ),
            cr.Capability(
                "objective.loss_expressions",
                cr.Dimension.OBJECTIVE,
                "Losses as expressions",
                cr.Status.EXCLUDED,
                cr.Blocker.EXCLUDED,
                cr.Trigger.EXECUTABLE_SUBMISSION,
            ),
        ),
        envelope=(("worker_cpu", 1), ("worker_deadline_seconds", 60)),
    )


def synthetic_pins(repository):
    return {
        name: (None if name in ("budget", "population") else "sha256:" + "a" * 64)
        for name in study.ADAPTER_PINS
    }


def synthetic_study(**changes):
    fields = {
        "challenge": SYNTHETIC,
        "contract": synthetic_contract,
        "ladder": {
            "model_family": 0,
            "architecture": 0,
            "optimizer": 3,
            "objective": 1,
        },
        "pins": synthetic_pins,
        "specimens": tuple(
            {
                "check": check,
                "specimen": "synthetic specimen for " + check,
                "expected": "fires",
                "control": "synthetic control",
            }
            for check in sorted(admission.CHECKS[admission.LEDGER_TRACK])
        ),
        "attacker_feedback": "synthetic status codes only",
        "permitted_hardware": "the synthetic CPU envelope",
    }
    return study.ChallengeStudy(**{**fields, **changes})


def test_battery_inventory_is_byte_for_byte_the_committed_level0():
    committed = (LEVEL0 / "permission-inventory.json").read_text()
    assert _bytes(study.permission_inventory()) == committed
    assert study.permission_inventory() == study.permission_inventory(study.CHALLENGE)


def test_battery_sheet_is_byte_for_byte_the_committed_level0():
    committed = json.loads((LEVEL0 / "study-sheet.json").read_text())
    live = study.study_sheet(str(REPOSITORY))
    if not study.drift(LEVEL0, str(REPOSITORY)):
        # No pin has drifted, so the whole sheet must be the committed bytes.
        assert _bytes(live) == (LEVEL0 / "study-sheet.json").read_text()
    without_pins = {k: v for k, v in live.items() if k != "pins"}
    assert without_pins == {k: v for k, v in committed.items() if k != "pins"}
    assert set(live["pins"]) == set(committed["pins"]) == admission.PIN_NAMES
    assert live["pins"]["permissions"] == committed["pins"]["permissions"]


def test_the_battery_map_lives_with_battery():
    assert not hasattr(study, "_LADDER")
    assert {
        k: v for k, v in admission_study.LADDER.items() if k in HISTORICAL_BATTERY_MAP
    } == HISTORICAL_BATTERY_MAP
    # Every dimension battery's contract uses is placed.
    used = {c.dimension.value for c in cr.contract(cr.BATTERY_CHALLENGE).capabilities}
    assert used <= set(admission_study.LADDER)
    adapter, live = study.study_for()
    assert adapter is admission_study.STUDY and live is cr.contract(study.CHALLENGE)


def test_shared_study_code_names_no_challenge_outside_its_registration_hook():
    tree = ast.parse(Path(study.__file__).read_text())
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    named = set()
    for node in ast.walk(tree):
        for attribute in ("id", "attr", "name", "module"):
            value = getattr(node, attribute, None)
            if isinstance(value, str) and "battery" in value.lower():
                named.add(value)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and "battery" in node.value.lower()
        ):
            named.add(node.value)
    # The default Challenge and the one registration hook; nothing else.
    assert named == {"BATTERY_CHALLENGE", "battery", "carbon.battery.admission_study"}


def test_a_synthetic_second_challenge_gets_its_own_inventory_and_sheet():
    adapter = synthetic_study()
    inventory = study.permission_inventory(adapter)
    assert inventory["challenge"] == SYNTHETIC
    assert inventory["construction_contract_digest"] == synthetic_contract().digest
    assert [(p["id"], p["planning_level"]) for p in inventory["permitted"]] == [
        ("model_family.mlp", 0),
        ("architecture.width", 0),
        ("optimizer.learning_rate", 3),
    ]
    assert inventory["not_permitted"] == ["objective.loss_expressions"]
    assert "levels [3]" in inventory["recorded_difference_from_ladder"]
    sheet = study.study_sheet(".", adapter)
    assert sheet["challenge"] == SYNTHETIC
    assert sheet["pins"]["construction"] == synthetic_contract().digest
    assert sheet["pins"]["permissions"] == study.digest(inventory)
    assert sheet["unpinned"] == ["budget", "population"] and not sheet["freezable"]
    assert sheet["attacker"]["feedback"] == "synthetic status codes only"
    assert "rule v2" not in json.dumps(sheet)
    assert [s["check"] for s in sheet["specimens"]] == sorted(
        admission.CHECKS[admission.LEDGER_TRACK]
    )


def test_an_unmapped_capability_is_refused_not_defaulted():
    adapter = synthetic_study(ladder={"model_family": 0, "architecture": 0})
    with pytest.raises(study.StudyError) as refused:
        study.permission_inventory(adapter)
    assert refused.value.code == "capability_not_on_ladder_map"
    assert "optimizer.learning_rate" in str(refused.value)
    with pytest.raises(study.StudyError, match="capability_not_on_ladder_map"):
        study.study_sheet(".", adapter)


def test_an_unregistered_challenge_is_refused():
    for token in (SYNTHETIC, "burgers-dynamics-v1", None, 7):
        with pytest.raises(study.StudyError, match="no_study_for_challenge"):
            study.permission_inventory(token)


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"challenge": "another-token-v1"}, "contract_is_not_this_challenges"),
        ({"contract": lambda: cr.contract(cr.BATTERY_CHALLENGE)}, "contract_is_not"),
        ({"ladder": {"model_family": 0, "nonsense": 1}}, "ladder_map_malformed"),
        ({"ladder": {"model_family": 6}}, "ladder_map_malformed"),
        ({"ladder": {"model_family": True}}, "ladder_map_malformed"),
        ({"specimens": ()}, "specimens_do_not_cover"),
        ({"attacker_feedback": " "}, "sheet_text_missing"),
    ],
)
def test_a_malformed_adapter_is_refused(changes, code):
    with pytest.raises(study.StudyError, match=code):
        study.study_for(synthetic_study(**changes))


def test_adapter_pins_must_be_exactly_the_challenge_specific_pins():
    def short(repository):
        return {k: v for k, v in synthetic_pins(repository).items() if k != "score"}

    with pytest.raises(study.StudyError, match="adapter_pins_not_exactly"):
        study.scope_pins(".", synthetic_study(pins=short))

    def extra(repository):
        return {**synthetic_pins(repository), "permissions": "sha256:" + "b" * 64}

    with pytest.raises(study.StudyError, match="adapter_pins_not_exactly"):
        study.scope_pins(".", synthetic_study(pins=extra))


def test_drift_reads_the_challenge_from_the_written_sheet(tmp_path):
    study.write(tmp_path, str(REPOSITORY))
    assert study.drift(tmp_path, str(REPOSITORY)) == {}
    sheet = json.loads((tmp_path / "study-sheet.json").read_text())
    sheet["pins"]["score"] = "sha256:" + "0" * 64
    (tmp_path / "study-sheet.json").write_text(json.dumps(sheet))
    assert set(study.drift(tmp_path, str(REPOSITORY))) == {"score"}
