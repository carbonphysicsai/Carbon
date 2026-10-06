"""PRACTICE-SAFETY-01: decision-value safety metrics beside the practice score.

The claims tested:
- the copied limits and bands are exactly their named sources';
- battery B1/B2/B3 equal the value modules' measures on the practice cases;
- each metric separates an optimistic model from the reference;
- a missing or invalid prediction makes every metric null, never clean;
- disclosure is allow-listed: any other field, label or value is refused,
  and no case id leaves;
- the practice result is versioned prospectively: without safety it is
  exactly v1, with it v2 (battery v3, B4 computed) adds only `safety`;
- the providers attach it; nothing on the official scoring path imports it.
"""

from __future__ import annotations

import ast
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon import practice_safety_feedback as ps
from carbon.battery import practice as battery_practice
from carbon.battery import practice_safety as battery_safety
from carbon.cold_plate import exam as cooling_exam
from carbon.cold_plate import practice as cooling_practice
from carbon.cold_plate import practice_safety as cooling_safety
from carbon.motor import practice as motor_practice
from carbon.motor import practice_safety as motor_safety

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def battery():
    return battery_practice.PracticeSet.load(REPO)


@pytest.fixture(scope="module")
def cooling():
    return cooling_practice.PracticeSet.load(REPO)


@pytest.fixture(scope="module")
def motor():
    return motor_practice.PracticeSet.load(REPO)


@pytest.fixture(scope="module")
def decision():
    return battery_safety.load_decision_set(REPO)


def battery_oracle(practice):
    return {r["case_id"]: dict(r["outputs"]) for r in practice.records}


def decision_oracle(decision):
    return {c: dict(decision.references[c]["outputs"]) for c in decision.case_ids}


def battery_doc(predictions, practice, decision):
    """Battery safety with `predictions` on PRACTICE and the reference's own
    outputs on the decision set."""
    return battery_safety.safety(
        {**decision_oracle(decision), **predictions}, practice, decision
    )


def cooling_oracle(practice):
    return {
        r["case_id"]: {k: r["outputs"][k] for k in cooling_exam.SHAPES}
        for r in practice.records
    }


def motor_oracle(practice):
    return {
        r["case_id"]: {"torque_nm": list(r["outputs"]["torque_nm"])}
        for r in practice.records
    }


# --- the copies are their sources' ------------------------------------------


def test_battery_rules_are_ev4_s_constraints_objective_and_bands():
    contract = json.loads((REPO / battery_safety.CONTRACT_SOURCE).read_text())
    rules = battery_safety.DECISION_RULES
    objective = contract["objective"]
    assert rules["objective"] == {
        k: objective[k] for k in ("threshold_v", "charge_start_s", "window_s")
    }
    assert rules["constraints"] == [
        {k: c[k] for k in ("id", "threshold") if k in c}
        for c in contract["constraints"]
    ]
    assert rules["reference"]["uncertainty"]["bands"] == (
        contract["reference"]["uncertainty"]["bands"]
    )


def test_cooling_and_motor_limits_are_their_studies():
    cooling = json.loads((REPO / cooling_safety.STUDY_SOURCE).read_text())["scenario"]
    assert cooling_safety.DIE_LIMIT_C == cooling["die_limit_c"] == 100.0
    assert cooling_safety.HYDRAULIC_LIMIT_W == cooling["hydraulic_limit_w"] == 0.25
    motor = json.loads((REPO / motor_safety.STUDY_SOURCE).read_text())["scenario"]
    assert motor_safety.MIN_MEAN_TORQUE_NM == motor["min_mean_torque_nm"] == 4.0
    assert motor_safety.MAX_RIPPLE_FRACTION == motor["max_ripple_fraction"] == 0.30


# --- battery: the value modules' measures, on practice ----------------------


@pytest.mark.parametrize(
    "kind",
    [
        "oracle",
        "conservative",
        "boundary_optimist",
        "rank_preserving_delay",
        "localized_sign_error",
    ],
)
def test_battery_b1_b2_b3_equal_the_value_modules_measures(battery, decision, kind):
    from carbon.battery.value import admissibility, false_acceptance, margins, panel

    contract = json.loads((REPO / battery_safety.CONTRACT_SOURCE).read_text())
    refs = {r["case_id"]: r for r in battery.records}
    predictions = panel.control_predictions(kind, refs)
    metrics = battery_doc(predictions, battery, decision)["metrics"]
    near = battery_safety.near_case_ids(battery)
    expected = false_acceptance.component(contract, predictions, near, refs)
    for constraint in battery_safety.CONSTRAINTS:
        row = expected["constraints"][constraint]
        assert metrics["B1"][constraint]["false_acceptance"] == row["false_acceptance"]
        assert metrics["B1"][constraint]["reference_fail"] == row["reference_fail"]
        rate = row["false_acceptance_rate"]
        assert metrics["B1"][constraint]["rate"] == (
            None if rate is None else round(rate, 6)
        )
    assert metrics["B1"]["worst"] == expected["worst_constraint"]
    optimism = admissibility.near_optimism(
        contract, predictions, battery.case_ids, refs
    )
    assert metrics["B2"]["near_optimism_bands"] == pytest.approx(optimism, abs=1e-6)
    for constraint in battery_safety.CONSTRAINTS:
        deltas = [
            margins._margins(contract, predictions[c])[constraint]
            - margins._margins(contract, refs[c]["outputs"])[constraint]
            for c in near
        ]
        b3 = metrics["B3"][constraint]
        assert b3["cases"] == len(near)
        assert b3["signed_mean_bands"] == pytest.approx(
            sum(deltas) / len(deltas), abs=1e-6
        )


def test_battery_names_the_boundary_optimist_and_clears_the_oracle(battery, decision):
    from carbon.battery.value import panel

    refs = {r["case_id"]: r for r in battery.records}
    oracle = battery_doc(battery_oracle(battery), battery, decision)["metrics"]
    assert oracle["B1"]["no_plating_onset"]["rate"] == 0.0
    assert oracle["B2"]["near_optimism_bands"] == 0.0
    optimist = battery_doc(
        panel.control_predictions("boundary_optimist", refs), battery, decision
    )
    b1 = optimist["metrics"]["B1"]
    assert b1["no_plating_onset"]["reference_fail"] > 0
    assert b1["no_plating_onset"]["rate"] == 1.0 and b1["worst"] == "no_plating_onset"
    assert optimist["metrics"]["B3"]["no_plating_onset"]["signed_mean_bands"] > 0
    assert optimist["metrics"]["B4"]["feedback_only"] is True


def test_b2_shows_the_value_and_never_the_gate_or_its_cutoff(battery, decision):
    document = battery_doc(battery_oracle(battery), battery, decision)
    assert set(document["metrics"]["B2"]) == {"near_optimism_bands", "feedback_only"}
    text = json.dumps(document)
    assert "PASS" not in text and "FAIL" not in text and "cutoff" not in text
    assert "threshold" not in text


@pytest.mark.parametrize("broken", [None, "missing", math.nan])
def test_a_missing_or_invalid_battery_prediction_is_unmeasured_never_clean(
    battery, decision, broken
):
    predictions = battery_oracle(battery)
    first = battery.case_ids[0]
    if broken == "missing":
        del predictions[first]
    elif broken is None:
        predictions[first] = None
    else:
        predictions[first] = {**predictions[first], "plating_margin_v": broken}
    document = battery_doc(predictions, battery, decision)
    assert document["unmeasured"] == 1
    assert [document["metrics"][k] for k in ("B1", "B2", "B3")] == [None] * 3
    # B4 reads only the decision set, whose predictions are all measurable.
    assert document["metrics"]["B4"]["feedback_only"] is True


def test_a_reference_inside_its_band_is_unresolved_and_counted(battery, decision):
    document = battery_doc(battery_oracle(battery), battery, decision)
    resolved = sum(
        document["metrics"]["B1"][c]["reference_fail"]
        for c in battery_safety.CONSTRAINTS
    )
    assert document["unresolved"] > 0
    assert resolved + document["unresolved"] <= 2 * len(
        battery_safety.near_case_ids(battery)
    )


# --- cooling and motor -------------------------------------------------------


def test_cooling_flags_a_model_that_runs_cool_and_cheap(cooling):
    oracle = cooling_safety.safety(cooling_oracle(cooling), cooling)
    assert (
        oracle["metrics"]["C1"]["rate"] == 0.0
        and oracle["metrics"]["C2"]["rate"] == 0.0
    )
    assert oracle["metrics"]["C3"]["signed_mean_c"] == 0.0
    optimistic = {
        c: {
            "peak_c": o["peak_c"] - 5.0,
            "profile_c": [t - 5.0 for t in o["profile_c"]],
            "pressure_drop_pa": o["pressure_drop_pa"] * 0.5,
        }
        for c, o in cooling_oracle(cooling).items()
    }
    metrics = cooling_safety.safety(optimistic, cooling)["metrics"]
    assert metrics["C1"]["reference_fail"] > 0 and metrics["C1"]["false_feasible"] > 0
    assert metrics["C2"]["reference_fail"] > 0 and metrics["C2"]["false_feasible"] > 0
    assert metrics["C3"]["signed_mean_c"] == -5.0 and metrics["C3"]["cases"] > 0


def test_motor_flags_a_smooth_optimist_and_says_n_30(motor):
    oracle = motor_safety.safety(motor_oracle(motor), motor)
    assert (
        oracle["metrics"]["M1"]["rate"] == 0.0
        and oracle["metrics"]["M2"]["rate"] == 0.0
    )
    assert oracle["metrics"]["M3"]["signed_mean_nm"] == 0.0
    flat = {
        c: {
            "torque_nm": [sum(o["torque_nm"]) / len(o["torque_nm"]) + 0.5]
            * len(o["torque_nm"])
        }
        for c, o in motor_oracle(motor).items()
    }
    metrics = motor_safety.safety(flat, motor)["metrics"]
    assert metrics["M1"]["reference_fail"] > 0
    assert metrics["M1"]["false_feasible"] == metrics["M1"]["reference_fail"]
    assert metrics["M3"]["signed_mean_nm"] == 0.5 and metrics["M3"]["cases"] > 0
    for metric in metrics.values():
        assert metric["sample"] == "n = 30"


@pytest.mark.parametrize("challenge", ["cooling", "motor"])
def test_a_gate_failing_prediction_is_unmeasured(challenge, cooling, motor):
    if challenge == "cooling":
        module, practice, predictions = cooling_safety, cooling, cooling_oracle(cooling)
        first = practice.case_ids[0]
        predictions[first] = {**predictions[first], "pressure_drop_pa": -1.0}
    else:
        module, practice, predictions = motor_safety, motor, motor_oracle(motor)
        first = practice.records[0]["case_id"]
        predictions[first] = {"torque_nm": [math.inf] * 60}
    document = module.safety(predictions, practice)
    assert document["unmeasured"] == 1
    assert set(document["metrics"].values()) == {None}


def test_every_cooling_and_motor_metric_says_no_band(cooling, motor):
    for document in (
        cooling_safety.safety(cooling_oracle(cooling), cooling),
        motor_safety.safety(motor_oracle(motor), motor),
    ):
        for metric in document["metrics"].values():
            assert metric["uncertainty"] == "no uncertainty band applied"


# --- disclosure --------------------------------------------------------------


def _documents(battery, cooling, motor, decision):
    return [
        battery_doc(battery_oracle(battery), battery, decision),
        cooling_safety.safety(cooling_oracle(cooling), cooling),
        motor_safety.safety(motor_oracle(motor), motor),
    ]


def test_every_metric_is_feedback_only_and_no_case_id_leaves(
    battery, cooling, motor, decision
):
    for document, practice in zip(
        _documents(battery, cooling, motor, decision), (battery, cooling, motor)
    ):
        assert document["schema"] == ps.SCHEMA and document["feedback_only"] is True
        assert set(document) == {
            "schema",
            "challenge",
            "feedback_only",
            "metrics",
            "unmeasured",
            "unresolved",
            "material",
        }
        # Every metric, B4 included, is computed and feedback-only.
        for metric in document["metrics"].values():
            assert metric["feedback_only"] is True
        text = json.dumps(document)
        assert not [c for c in practice.case_ids if c in text]
        assert not [c for c in decision.case_ids if c in text]


def _shape():
    return {
        "M": {"count": ps.COUNT, "label": ps.literal("fixed"), "feedback_only": ps.TRUE}
    }


def _doc(metric, **top):
    return ps.document(
        "c",
        {"M": metric},
        unmeasured=0,
        unresolved=0,
        material={"path": "p", "sha256": "s"},
        allowed=_shape(),
        **top,
    )


def test_the_allow_list_accepts_its_shape_and_null():
    assert _doc({"count": 1, "label": "fixed", "feedback_only": True})["metrics"]["M"]
    assert _doc(None)["metrics"]["M"] is None


@pytest.mark.parametrize(
    "metric",
    [
        {
            "count": 1,
            "label": "fixed",
            "feedback_only": True,
            "cases": ["practice-0001"],
        },
        {"count": 1, "label": "practice-0001", "feedback_only": True},
        {"count": True, "label": "fixed", "feedback_only": True},
        {"count": -1, "label": "fixed", "feedback_only": True},
        {"count": 1.0, "label": "fixed", "feedback_only": True},
        {"count": 1, "label": "fixed", "feedback_only": 1},
        {"count": 1, "label": "fixed"},
        "PASS",
    ],
)
def test_the_allow_list_refuses_any_other_field_label_or_value(metric):
    with pytest.raises(ps.DisclosureRefused):
        _doc(metric)


def test_the_allow_list_refuses_an_unnamed_metric_and_a_non_finite_number():
    with pytest.raises(ps.DisclosureRefused):
        ps.document(
            "c",
            {"M": None, "X": None},
            unmeasured=0,
            unresolved=0,
            material={"path": "p", "sha256": "s"},
            allowed=_shape(),
        )
    with pytest.raises(ps.DisclosureRefused):
        ps.document(
            "c",
            {"N": {"v": math.nan}},
            unmeasured=0,
            unresolved=0,
            material={"path": "p", "sha256": "s"},
            allowed={"N": {"v": ps.NUMBER}},
        )


# --- the practice result's versions ------------------------------------------


def _recipe(challenge):
    return SimpleNamespace(
        family="knn",
        settings={},
        recipe_digest="sha256:" + "0" * 64,
        document=lambda: {"challenge": challenge},
    )


V1_FIELDS = {
    "schema",
    "provenance",
    "challenge",
    "recipe_digest",
    "backbone",
    "summary",
    "fit",
    "backend",
    "worker",
    "adaptively_seen",
    "final_exam",
    "official_eligible",
    "scientific_qualification",
}


@pytest.mark.parametrize("module", [battery_practice, cooling_practice, motor_practice])
def test_without_safety_the_result_is_exactly_v1_and_with_it_v2_adds_only_safety(
    module,
):
    kwargs = {"recipe": _recipe({"id": "x"}), "backend": {"kind": "K"}, "worker": {}}
    summary = {"score": 0.5, "eligible": True}
    v1 = module.feedback(summary, {}, **kwargs)
    assert v1["schema"] == module.FEEDBACK_SCHEMA_V1 and v1["schema"].endswith(".v1")
    assert set(v1) == V1_FIELDS
    safety = {"schema": ps.SCHEMA, "feedback_only": True}
    v2 = module.feedback(summary, {}, safety=safety, **kwargs)
    # Battery's v3 has v2's fields; only its safety block's B4 differs.
    latest = ".v3" if module is battery_practice else ".v2"
    assert v2["schema"] == module.FEEDBACK_SCHEMA and v2["schema"].endswith(latest)
    assert set(v2) == V1_FIELDS | {"safety"} and v2["safety"] is safety
    assert {k: v for k, v in v2.items() if k not in ("schema", "safety")} == {
        k: v for k, v in v1.items() if k != "schema"
    }


# --- the providers attach it -------------------------------------------------


class _Workspace:
    def __init__(self, *args):
        pass

    def put(self, *args):
        pass


def _runner(predictions, digest, staged=None):
    def run(ledger, **kwargs):
        if staged is not None:
            staged.update(kwargs["files"])
        snapshot = ledger.root / "op-1" / "snapshot"
        snapshot.mkdir(parents=True)
        files = {}
        for name, value in (("predictions.json", predictions), ("fit.json", {"n": 1})):
            body = json.dumps(value).encode()
            (snapshot / name).write_bytes(body)
            files[name] = digest(body)
        return {"operation": "op-1", "files": files}

    return run


@pytest.mark.parametrize("challenge", ["battery", "cooling", "motor"])
def test_each_practice_provider_returns_its_latest_shape_with_its_safety(
    challenge, battery, cooling, motor, decision, tmp_path, monkeypatch
):
    from carbon.development_session import research_workspace

    monkeypatch.setattr(research_workspace, "ResearchWorkspace", _Workspace)
    ledger = SimpleNamespace(root=tmp_path)
    image = SimpleNamespace(image_id="sha256:" + "1" * 64)
    staged = {}
    if challenge == "battery":
        from carbon.battery import research

        monkeypatch.setattr(research, "image_backends", lambda image, root: ("jax",))
        provider_class, practice, predictions = (
            research.BatteryPractice,
            battery,
            {**battery_oracle(battery), **decision_oracle(decision)},
        )
    elif challenge == "cooling":
        from carbon.cold_plate import research

        provider_class, practice, predictions = (
            research.ColdPlatePractice,
            cooling,
            cooling_oracle(cooling),
        )
    else:
        from carbon.motor import research

        provider_class, practice, predictions = (
            research.MotorPractice,
            motor,
            motor_oracle(motor),
        )
    provider = provider_class(
        ledger=ledger,
        owner="o",
        image=image,
        root=REPO,
        runner=_runner(predictions, research.digest, staged),
    )
    provider.compile = lambda strategy: (None, _recipe({"id": challenge}))
    result = provider("task-1", {"strategy": "fixture"})
    assert result["schema"].endswith(".v3" if challenge == "battery" else ".v2")
    assert result["safety"]["schema"] == ps.SCHEMA
    assert result["safety"]["unmeasured"] == 0
    if challenge == "battery":
        expected = battery_safety.safety(predictions, practice, decision)
        assert result["safety"]["metrics"]["B4"] == ORACLE_B4
        # The worker is asked for PRACTICE and the decision set; the practice
        # score is PRACTICE's alone.
        inputs = json.loads(staged["practice-inputs.json"])
        assert inputs["schema"] == "carbon.battery.practice-inputs.v2"
        assert [c["case_id"] for c in inputs["cases"]] == (
            practice.case_ids + decision.case_ids
        )
        from carbon.battery.challenge import PublicMaterial

        _rows, alone = battery_practice.score_practice(
            battery_oracle(battery), battery, PublicMaterial.load(REPO), REPO
        )
        assert result["summary"] == battery_practice._summary(alone)
    else:
        expected = provider_module_safety(challenge)(predictions, practice)
    assert result["safety"] == expected
    assert result["official_eligible"] is False and result["final_exam"] is False


#: B4 when the model predicts the reference itself: at five conditions it
#: chooses a reference-FEASIBLE protocol; at the sixth it predicts no
#: protocol feasible, and abstains.
ORACLE_B4 = {
    "feasible_choice": 5,
    "chosen": 5,
    "rate": 1.0,
    "abstained": 1,
    "unresolved": 0,
    "feedback_only": True,
}


def provider_module_safety(challenge):
    return {
        "cooling": cooling_safety.safety,
        "motor": motor_safety.safety,
    }[challenge]


# --- the official scoring path is unchanged ----------------------------------

SAFETY_MODULES = {
    "carbon.practice_safety_feedback",
    "carbon.battery.practice_safety",
    "carbon.cold_plate.practice_safety",
    "carbon.motor.practice_safety",
}
#: The only modules that may import the safety code: the three practice
#: research providers, and the safety modules themselves.
IMPORTERS = {
    "carbon/battery/research.py",
    "carbon/cold_plate/research.py",
    "carbon/motor/research.py",
    "carbon/battery/practice_safety.py",
    "carbon/cold_plate/practice_safety.py",
    "carbon/motor/practice_safety.py",
}


def _imports_safety(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names = (
                [base]
                + [f"{base}.{a.name}" for a in node.names]
                + [a.name for a in node.names]
            )
        else:
            continue
        if any(
            n.split(".")[-1] in ("practice_safety", "practice_safety_feedback")
            for n in names
        ):
            return True
    return False


def test_only_the_practice_providers_import_the_safety_code():
    found = {
        path.relative_to(REPO).as_posix()
        for root in ("carbon", "scripts")
        for path in (REPO / root).rglob("*.py")
        if _imports_safety(path)
    }
    assert found == IMPORTERS


def _safety_calls(path):
    """Each `practice_safety.<name>(...)` call in `path`, as (class, function)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scopes = [(None, tree)] + [
        (node.name, node) for node in tree.body if isinstance(node, ast.ClassDef)
    ]
    calls = []
    for owner, scope in scopes:
        for function in scope.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "practice_safety"
                ):
                    calls.append((owner, function.name, node.func.attr))
    # Anything outside a function or class method is a call at import time.
    total = sum(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "practice_safety"
        for n in ast.walk(tree)
    )
    assert total == len(calls)
    return calls


@pytest.mark.parametrize(
    ("module", "provider"),
    [
        ("carbon/battery/research.py", "BatteryPractice"),
        ("carbon/cold_plate/research.py", "ColdPlatePractice"),
        ("carbon/motor/research.py", "MotorPractice"),
    ],
)
def test_a_provider_calls_the_safety_code_only_inside_its_practice_trial(
    module, provider
):
    # The battery validator daemon imports research.py for its feedback field
    # names, so the module is loaded there; it is called only here. Battery
    # also loads its practice decision set there, for B4.
    expected = [(provider, "__call__", "safety")]
    if provider == "BatteryPractice":
        expected = [(provider, "__call__", "decision_set")] + expected
    assert _safety_calls(REPO / module) == expected


def test_official_scoring_rank_and_reward_code_loads_no_safety_module():
    probe = (
        "import json, sys\n"
        "import carbon.battery.exam, carbon.battery.value.scoring\n"
        "import carbon.cold_plate.exam, carbon.cold_plate.track_b\n"
        "import carbon.motor.exam, carbon.motor.track_b\n"
        "import carbon.scoring, carbon.challenge_validator\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    assert not set(json.loads(out.stdout)) & SAFETY_MODULES


def test_the_practice_score_is_the_same_with_and_without_safety(battery, decision):
    from carbon.battery.challenge import PublicMaterial

    material = PublicMaterial.load(REPO)
    predictions = battery_oracle(battery)
    _rows, before = battery_practice.score_practice(
        predictions, battery, material, REPO
    )
    battery_doc(predictions, battery, decision)
    _rows, after = battery_practice.score_practice(predictions, battery, material, REPO)
    assert before == after
