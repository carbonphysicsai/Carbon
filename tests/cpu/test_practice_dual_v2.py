"""Practice feedback on the exam v2 legs (Validator, practice dual v2): the exam own
sealed grader runs on the FULL exposed public bank, shaped as the registered
practice grid, with public-seeded probes interleaved. One scoring code path with
the exam; aggregates only; labelled "practice (public bank)"."""

from __future__ import annotations

import io
import json

import numpy as np
import pytest

from carbon.challenge_kit import physical_pack
from carbon.scoring import cooling_physics, motor_physics, practice_dual, practice_grid
from carbon.scoring import physical_dual_pack as physical

#: kind, a served version, cells, probes, the practice grid shape
CASES = {
    "f08": ("1.4", 8, 52, (8, 1)),
    "f02": ("2.3", 8, 28, (8, 1)),
    "motor": ("1.3", 48, 76, (8, 6)),
    "cooling": ("1.2", 48, 84, (8, 6)),
}


def _public(kind, version):
    adapter = practice_grid.adapter(kind, version)
    return adapter, physical_pack.public_roles(adapter.CHALLENGE, version)


def _power_law(kind, version, public):
    """A stand-in model with exactly the registered sensitivities (the probes
    carry no references), returning one flat output row for an input row."""
    if kind == "motor":
        mean = motor_physics.registered_model(public["train"])
        from carbon.motor.domain import ANGLE_STEPS

        return lambda x: [mean(x)] * ANGLE_STEPS
    if kind == "cooling":
        return cooling_physics.registered_model(public["train"])
    if kind == "f02":
        from carbon.challenge_kit import f02_train

        train = f02_train.load_public_train("2.0")
        x = np.asarray(train["inputs"], float)
        rise = np.asarray(train["targets"], float)[:, 0] - 40.0
        design = np.column_stack([np.ones(len(x)), np.log(x)])
        coefficients, *_ = np.linalg.lstsq(design, np.log(rise), rcond=None)
        return lambda p: [
            40.0
            + float(
                np.exp(
                    np.concatenate([[1.0], np.log(np.asarray(p, float))]) @ coefficients
                )
            )
        ]
    with np.load(io.BytesIO(public["train"]), allow_pickle=False) as data:
        x, y = np.asarray(data["inputs"], float), np.asarray(data["targets"], float)
    design = np.column_stack([np.ones(len(x)), np.log(x)])
    coefficients, *_ = np.linalg.lstsq(design, np.log(y), rcond=None)
    return lambda p: [
        float(v)
        for v in np.exp(
            np.concatenate([[1.0], np.log(np.asarray(p, float))]) @ coefficients
        )
    ]


def _rows(kind, version):
    bank = practice_grid.practice_bank(kind, version)
    names = practice_grid.input_names(kind, version)
    return bank, physical.bank_rows(bank, names), names


def _truth_predict(kind, version, rows, model):
    """The references at the cells, the stand-in model at the probes."""

    def predict(inputs):
        out = []
        for row, spec in zip(inputs, rows, strict=True):
            if spec["cohort"] == "probe_response":
                out.append(list(map(float, model(list(row.values())))))
            else:
                out.append(list(map(float, spec["reference"])))
        return out

    return predict


@pytest.mark.parametrize("kind", sorted(CASES))
def test_the_practice_grid_is_the_full_public_bank_with_interleaved_public_probes(kind):
    version, cells, probes, shape = CASES[kind]
    bank, rows, _ = _rows(kind, version)
    cohorts = [r["cohort"] for r in rows]
    assert cohorts.count(practice_grid.GRID_COHORT) == cells
    assert cohorts.count("probe_response") == probes
    # interleaved, never a suffix
    assert cohorts[-cells:] != [practice_grid.GRID_COHORT] * cells
    designs = {
        r["record"]["design_id"]
        for r in rows
        if r["cohort"] == practice_grid.GRID_COHORT
    }
    conditions = {
        r["record"]["condition_id"]
        for r in rows
        if r["cohort"] == practice_grid.GRID_COHORT
    }
    assert (len(designs), len(conditions)) == shape
    # public probes: the same for everyone, and not the exam's (a distinct label)
    again, _, _ = _rows(kind, version)
    assert (np.asarray(again["inputs"]) == np.asarray(bank["inputs"])).all()
    assert bank["reference_present"] == tuple(
        c == practice_grid.GRID_COHORT for c in cohorts
    )


@pytest.mark.parametrize("kind", sorted(CASES))
def test_practice_uses_the_exams_own_grader_one_code_path(kind):
    version, *_ = CASES[kind]
    adapter, _public = _public_pair(kind, version)
    sealed = _sealed_module(kind)
    assert adapter.measure == sealed.measure
    assert adapter.EVALUATION_VERSION.endswith("-v2")


def _public_pair(kind, version):
    return _public(kind, version)


def _sealed_module(kind):
    if kind == "f08":
        from carbon.scoring import f08_sealed_dual_pack as module
    elif kind == "f02":
        from carbon.scoring import f02_sealed_dual_pack as module
    elif kind == "motor":
        from carbon.scoring import motor_sealed_dual_pack as module
    else:
        from carbon.scoring import cooling_dual_pack as module
    return module


@pytest.mark.parametrize("kind", sorted(CASES))
def test_a_model_with_the_references_scores_the_v2_legs_aggregates_only(kind):
    version, *_ = CASES[kind]
    _adapter, public = _public(kind, version)
    _bank, rows, _names = _rows(kind, version)
    model = _power_law(kind, version, public)
    doc = practice_dual.feedback_v2(
        kind, version, _truth_predict(kind, version, rows, model)
    )
    assert doc["available"] is True and doc["schema"] == practice_dual.SCHEMA_V2
    assert doc["bank"] == "practice (public bank)"
    assert doc["eligible"] is True, doc
    assert doc["accuracy_legs"]["A_acc"] == pytest.approx(1.0)
    assert doc["accuracy_legs"]["A_response"] == pytest.approx(1.0, abs=2e-3)
    assert set(doc["design_parts"]) == {"V_pair", "V_feas", "V_var", "C"}
    assert doc["design_value"] == pytest.approx(1.0, abs=1e-3)
    assert doc["total"] == pytest.approx(1.0, abs=3e-3)
    assert doc["gates"]["physics_laws"] is True
    # no leak: aggregates and gate names only, nothing per case or per probe
    text = json.dumps(doc)
    for case_id in practice_grid.practice_bank(kind, version)["case_ids"]:
        assert case_id not in text
    assert "inputs" not in doc and "predictions" not in doc and "rows" not in doc


@pytest.mark.parametrize("kind", ["f08", "f02"])
def test_the_total_equals_the_exam_graders_total_on_the_same_bank(kind):
    """One code path: the practice total is exactly 0.5 A + 0.5 D of the sealed
    grader's own measurement of the same rows."""
    version, *_ = CASES[kind]
    adapter, public = _public(kind, version)
    bank, rows, names = _rows(kind, version)
    model = _power_law(kind, version, public)
    predict = _truth_predict(kind, version, rows, model)
    outputs = predict([r["inputs"] for r in rows])
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"kind": kind, "version": version},
        "scope": practice_dual.SCOPE,
    }
    measured = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(public["important_limit_definition"]),
        objective=json.loads(public["design_objective"]),
        train_raw=public["train"],
        names=names,
    )
    doc = practice_dual.from_rows_v2(kind, version, outputs)
    assert doc["total"] == pytest.approx(0.5 * measured["A"] + 0.5 * measured["D"])
    assert doc["accuracy"] == measured["A"] and doc["design_value"] == measured["D"]


@pytest.mark.parametrize("kind", ["f08", "f02"])
def test_a_wrong_trend_model_loses_the_response_leg_in_practice_too(kind):
    version, *_ = CASES[kind]
    _adapter, public = _public(kind, version)
    _bank, rows, _names = _rows(kind, version)
    good = _power_law(kind, version, public)
    first = 0

    def flipped(point):
        moved = list(point)
        moved[first] = (
            (180.0 * 260.0) / moved[first] if kind == "f08" else 170.0 - moved[first]
        )
        return good(moved)

    doc = practice_dual.feedback_v2(
        kind, version, _truth_predict(kind, version, rows, flipped)
    )
    assert doc["accuracy_legs"]["A_response"] < 0.95
    assert doc["eligible"] is False
    assert doc["total"] is None
    assert doc["gates"]["physics_laws"] is False


def test_an_unregistered_version_is_an_explicit_unavailable_not_a_silent_omission():
    doc = practice_dual.feedback_v2("f08", "9.9", lambda inputs: [])
    assert doc["available"] is False and doc["bank"] == "practice (public bank)"
    assert doc["reason"] == "practice_version_not_registered"


# --- a grid shape is bound to its population, never "either" --------------------


def _practice_definition(kind):
    version, *_ = CASES[kind]
    adapter, public = _public(kind, version)
    bank = practice_grid.practice_bank(kind, version)
    definition = adapter.definition(bank=bank, train_raw=public["train"])
    return adapter, bank, public, definition


def test_a_practice_definition_names_its_population_and_validates():
    for kind in ("motor", "cooling"):
        adapter, _bank, _public_roles, definition = _practice_definition(kind)
        assert definition["population"] == "PRACTICE_PUBLIC_BANK"
        adapter.validate_definition(definition)


def test_motor_practice_is_exactly_8x6_and_sealed_exactly_5x6():
    adapter, bank, _public_roles, definition = _practice_definition("motor")
    # a practice-shaped (8 x 6) definition without the practice population refuses
    sealed_named = {k: v for k, v in definition.items() if k != "population"}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(sealed_named)
    # a practice population with the sealed 5 x 6 shape refuses
    shrunk = {
        **definition,
        "grid": {"designs": 5, "conditions": 6},
        "cohort_counts": {"decision_sealed_grid": 30},
    }
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(shrunk)
    # a bank that is not labelled practice cannot make an 8 x 6 definition
    unlabelled = {k: v for k, v in bank.items() if k != "population"}
    with pytest.raises(adapter.Refused):
        adapter.definition(bank=unlabelled, train_raw=b"")


def test_cooling_practice_is_exactly_48_cells_and_sealed_exactly_16():
    adapter, _bank, _public_roles, definition = _practice_definition("cooling")
    sealed_named = {k: v for k, v in definition.items() if k != "population"}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(sealed_named)
    shrunk = {**definition, "cohort_counts": {"decision_sealed_grid": 16}}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(shrunk)
    odd = {**definition, "population": "SOMETHING_ELSE"}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(odd)


# --- practice is never a grade: Ladder and KOTH refuse it -----------------------


def _practice_document():
    kind = "f08"
    version, *_ = CASES[kind]
    _adapter, public = _public(kind, version)
    _bank, rows, _names = _rows(kind, version)
    model = _power_law(kind, version, public)
    predict = _truth_predict(kind, version, rows, model)
    return practice_dual.feedback_v2(kind, version, predict)


def test_the_ladder_store_refuses_a_practice_document():
    from carbon.challenge_validator import ladder_store

    doc = _practice_document()
    assert doc["schema"] == "carbon.practice.dual-feedback.v2"
    for latest in (False, True):
        with pytest.raises(ladder_store.LadderStoreRefused):
            ladder_store.checked(doc, latest=latest)


def test_the_koth_comparator_refuses_a_practice_pack_or_definition():
    from carbon.challenge_validator import koth_registry

    _adapter, _bank, _public_roles, definition = _practice_definition("motor")
    practice_pack = {
        "scope": practice_dual.SCOPE,
        "pack_digest": "sha256:" + "0" * 64,
        "legs": {"A": {"minimum": None}, "D": {"minimum": None}},
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
    }
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator("motor", practice_pack, {})
    real_pack = {**practice_pack, "scope": "DEVELOPMENT"}
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator("motor", real_pack, definition)
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator_for_set("motor", [practice_pack], [{}])
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.comparator_for_set("motor", [real_pack], [definition])
