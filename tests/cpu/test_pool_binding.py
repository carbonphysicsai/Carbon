"""The pool-graded custody binding of the leak attack: config checks, the baseline loader, the perturbation field (a pure function of
the input row), the grade mapping, the digest. The real packs and the real grader are NOT used here: a stand-in loader supplies two
sets and a stand-in `graded` supplies calibration_grade's aggregates; the plumbing is what is tested.
"""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

PAYLOAD = Path(__file__).resolve().parents[2] / "scripts/dev/part_feedback_attack"
sys.path.insert(0, str(PAYLOAD))

import attack as at
import pool_binding as pb

WIDTH = 5


def _pack(a_components=("fid",), d_components=("val",)):
    def leg(names, minimum):
        return {
            "components": [
                {
                    "metric": n,
                    "unit": "1",
                    "transform": "unit_benefit",
                    "scale": None,
                    "weight": 1.0 / len(names),
                }
                for n in names
            ],
            "minimum": minimum,
        }

    return {
        "hard_gates": ["g1", "g2", "speed"],
        "legs": {"A": leg(a_components, 0.2), "D": leg(d_components, 0.3)},
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
    }


def _inputs(n, seed):
    rng = np.random.default_rng(seed)
    return rng.uniform(1.0, 4.0, size=(n, 3))


class AdapterStub:
    VERSION = "1.5"
    CHALLENGE = "motor"


class OtherAdapterStub(AdapterStub):
    pass


def _roles(pack, **overrides):
    roles = {
        "score_pack": pack,
        "definition": {"definition": 1},
        "limits": {"limits": 1},
        "objective": {"objective": 1},
        "train": b"train-bytes",
    }
    roles.update(overrides)
    return roles


def _make_set(
    inputs,
    truth_shift,
    pack,
    *,
    aggregates=None,
    roles=None,
    adapter=None,
    gate_fails_when_perturbed=None,
    baseline_pair=None,
):
    n = len(inputs)
    base = (
        np.tile(np.linspace(1.0, 2.0, WIDTH), (n, 1))
        + 0.1 * inputs.sum(axis=1)[:, None]
    )
    truth = base + truth_shift

    def graded(*, infer, entry_id):
        rows = np.asarray(infer(None), float)
        err = float(np.mean(np.abs(rows - truth)))
        a = max(0.0, 1.0 - err)
        d = max(0.0, 0.9 - 0.5 * err)
        out = {
            "A": a,
            "D": d,
            "total": 0.5 * a + 0.5 * d,
            "gates": {"g1": True, "g2": True},
            "A_legs": {},
            "D_parts": {},
        }
        out.update(aggregates or {})
        if gate_fails_when_perturbed and not np.array_equal(rows, base):
            out["gates"] = {**out["gates"], gate_fails_when_perturbed: False}
        return out

    return pb.GradedSet(
        bank={"inputs": inputs.tolist()},
        adapter=adapter or AdapterStub(),
        baseline_pair=baseline_pair,
        roles=roles or _roles(pack),
        names=None,
        base_rows=base,
        challenge="motor",
        graded=graded,
    )


def _loader(pack=None, aggregates=None):
    pack = pack or _pack()
    sets = {
        "sealed": _make_set(_inputs(12, 1), 0.05, pack, aggregates=aggregates),
        "fresh": _make_set(_inputs(10, 2), 0.05, pack, aggregates=aggregates),
    }

    def load(spec, config):
        side = "sealed" if spec is config["sealed"] else "fresh"
        graded = sets[side]
        return graded, np.asarray(graded.bank["inputs"], float), SnapshotStub(side)

    return load


class SnapshotStub:
    def __init__(self, side):
        self.manifest_digest = "sha256:" + ("a" if side == "sealed" else "b") * 64


CONFIG = {
    "challenge": "electric-motor-magnetics",
    "version": "1.5",
    "dim": 4,
    "amplitude": 0.05,
    "field_seed": 7,
    "copy_hotkey": "5" + "H" * 47,
    "catalog_recipe_digest": "sha256:" + "c" * 64,
    "sealed": {"pack_root": "/s", "baseline_predictions": "/s.json"},
    "fresh": {"pack_root": "/f", "baseline_predictions": "/f.json"},
}


def _binding(**kwargs):
    return pb.build(copy.deepcopy(CONFIG), loader=_loader(**kwargs))


# ---------------------------------------------------------------- config and baseline files


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda c: c.pop("amplitude"), "config_amplitude_required"),
        (lambda c: c.update(amplitude=0), "config_amplitude_required"),
        (lambda c: c.update(amplitude=float("nan")), "config_amplitude_required"),
        (lambda c: c.update(dim=0), "config_dim"),
        (lambda c: c.update(dim=65), "config_dim"),
        (lambda c: c.update(field_seed="7"), "config_field_seed"),
        (lambda c: c.pop("copy_hotkey"), "config_copy_hotkey_required"),
        (lambda c: c.update(copy_hotkey=""), "config_copy_hotkey_required"),
        (lambda c: c.update(copy_hotkey=None), "config_copy_hotkey_required"),
        (lambda c: c.pop("challenge"), "config_challenge"),
        (lambda c: c["fresh"].pop("pack_root"), "config_fresh"),
        (lambda c: c["sealed"].update(extra="x"), "config_sealed_unknown_key:extra"),
    ],
)
def test_the_config_is_refused_without_a_required_setting(tmp_path, mutate, code):
    config = copy.deepcopy(CONFIG)
    mutate(config)
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config, allow_nan=True))
    with pytest.raises(pb.BindingRefused) as refused:
        pb.load_config(path)
    assert refused.value.code == code


def test_a_valid_config_loads(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps(CONFIG))
    assert pb.load_config(path)["dim"] == 4


def test_the_baseline_predictions_load_from_worker_evidence_or_rows_and_must_fit(
    tmp_path,
):
    values = np.arange(12, dtype="<f8").reshape(3, 4)
    evidence = tmp_path / "e.json"
    evidence.write_text(
        json.dumps(
            {"predictions_raw_base64": base64.b64encode(values.tobytes()).decode()}
        )
    )
    assert np.array_equal(pb.load_predictions(evidence, 3, 4, "<f8"), values)
    rows = tmp_path / "r.json"
    rows.write_text(json.dumps({"rows": values.tolist()}))
    assert np.array_equal(pb.load_predictions(rows, 3, 4, "<f8"), values)
    for bad_rows, bad_width in ((4, 4), (3, 5)):
        with pytest.raises(pb.BindingRefused, match="baseline_predictions_size"):
            pb.load_predictions(rows, bad_rows, bad_width, "<f8")
    nan = tmp_path / "n.json"
    nan.write_text(json.dumps({"rows": [[float("nan")] * 4] * 3}, allow_nan=True))
    with pytest.raises(pb.BindingRefused, match="baseline_predictions_finite"):
        pb.load_predictions(nan, 3, 4, "<f8")
    other = tmp_path / "o.json"
    other.write_text(json.dumps({"x": 1}))
    with pytest.raises(pb.BindingRefused, match="baseline_predictions_format"):
        pb.load_predictions(other, 3, 4, "<f8")


# ---------------------------------------------------------------- the perturbation field


def test_theta_zero_reproduces_the_baseline_rows_exactly_and_the_field_is_linear():
    binding = _binding()
    for which in ("sealed", "fresh"):
        assert np.array_equal(
            np.asarray(binding.rows([0.0] * 4, which)), binding.sets[which].base_rows
        )
    inputs = binding.sets["sealed"].bank["inputs"]
    one = binding.field.delta(inputs, [1.0, 0.0, 0.0, 0.0])
    two = binding.field.delta(inputs, [0.0, 2.0, 0.0, 0.0])
    both = binding.field.delta(inputs, [1.0, 2.0, 0.0, 0.0])
    assert np.allclose(one + two, both)
    assert np.abs(both).max() > 0


def test_the_perturbation_is_a_pure_function_of_the_input_row_not_of_its_position():
    binding = _binding()
    inputs = np.asarray(binding.sets["sealed"].bank["inputs"], float)
    theta = [0.3, -0.2, 0.5, 0.1]
    delta = binding.field.delta(inputs, theta)
    order = np.random.default_rng(0).permutation(len(inputs))
    assert np.array_equal(binding.field.delta(inputs[order], theta), delta[order])
    # a design appearing in both sets is perturbed identically
    shared = np.vstack(
        [inputs[:1], np.asarray(binding.sets["fresh"].bank["inputs"], float)[:3]]
    )
    again = binding.field.delta(shared, theta)
    assert np.array_equal(again[0], delta[0])


def test_the_field_is_deterministic_in_its_seed_and_changes_with_it():
    one, two = _binding(), _binding()
    inputs = one.sets["sealed"].bank["inputs"]
    theta = [1.0, 1.0, 1.0, 1.0]
    assert np.array_equal(
        one.field.delta(inputs, theta), two.field.delta(inputs, theta)
    )
    config = copy.deepcopy(CONFIG)
    config["field_seed"] = 8
    other = pb.build(config, loader=_loader())
    assert not np.array_equal(
        other.field.delta(inputs, theta), one.field.delta(inputs, theta)
    )
    with pytest.raises(pb.BindingRefused, match="theta_dimension"):
        one.field.delta(inputs, [1.0])


# ---------------------------------------------------------------- the grade mapping


def test_grade_returns_the_shape_attack_needs_and_drops_the_speed_placeholder():
    binding = _binding()
    zero = [0.0] * 4
    graded = binding.grade(zero, "sealed")
    assert graded["status"] == "SCORED"
    assert set(graded) == {"status", "total", "legs", "components", "gates"}
    assert set(graded["gates"]) == {"g1", "g2"} == set(binding.gate_names())
    assert graded["components"] == {
        "fid": graded["legs"]["A"],
        "val": graded["legs"]["D"],
    }
    assert binding.parts_registry() == {"A": ("fid",), "D": ("val",)}
    assert binding.dim == 4


def test_a_leg_with_several_components_needs_their_values_by_name():
    pack = _pack(a_components=("fid", "law"))
    with pytest.raises(pb.BindingRefused, match="component_values_unavailable:fid"):
        _binding(pack=pack).grade([0.0] * 4, "sealed")
    graded = _binding(pack=pack, aggregates={"A_legs": {"fid": 0.7, "law": 0.8}}).grade(
        [0.0] * 4, "sealed"
    )
    assert graded["components"]["fid"] == 0.7 and graded["components"]["law"] == 0.8


def test_a_result_without_a_total_is_not_scored_and_a_candidate_refusal_is_not_scored():
    binding = _binding(aggregates={"total": None})
    assert binding.grade([0.0] * 4, "sealed") == {"status": "NOT_SCORED"}

    from carbon.challenge_validator import calibration_grade as cg

    binding = _binding()

    def refuse(code):
        def graded(*, infer, entry_id):
            raise cg.CalibrationRefused(code)

        return graded

    binding.sets["sealed"].graded = refuse("dual_native_candidate_invalid")
    assert binding.grade([0.0] * 4, "sealed")["status"] == "NOT_SCORED"
    # any other refusal means the BINDING is broken, not the model: it is raised, never turned into a score
    binding.sets["sealed"].graded = refuse("calibration_pool_material_missing")
    with pytest.raises(cg.CalibrationRefused):
        binding.grade([0.0] * 4, "sealed")


def test_a_failed_hard_gate_is_not_scored_and_names_the_gate():
    binding = _binding(aggregates={"gates": {"g1": True, "g2": False, "speed": True}})
    assert binding.grade([0.0] * 4, "sealed") == {
        "status": "NOT_SCORED",
        "reason": "gate:g2",
    }
    # the first failed gate in sorted order, the speed placeholder never counted
    both = _binding(aggregates={"gates": {"g1": False, "g2": False, "speed": False}})
    assert both.grade([0.0] * 4, "sealed")["reason"] == "gate:g1"
    only_speed = _binding(
        aggregates={"gates": {"g1": True, "g2": True, "speed": False}}
    )
    assert only_speed.grade([0.0] * 4, "sealed")["status"] == "SCORED"


def test_a_model_that_fails_a_gate_on_fresh_data_only_makes_the_attack_fail():
    pack = _pack()
    sets = {
        "sealed": _make_set(_inputs(12, 1), 0.05, pack),
        "fresh": _make_set(_inputs(10, 2), 0.05, pack, gate_fails_when_perturbed="g2"),
    }

    def load(spec, config):
        side = "sealed" if spec is config["sealed"] else "fresh"
        return (
            sets[side],
            np.asarray(sets[side].bank["inputs"], float),
            SnapshotStub(side),
        )

    config = copy.deepcopy(CONFIG)
    config["amplitude"] = (
        3.0  # moves large enough to clear the Ladder step in this fake
    )
    binding = pb.build(config, loader=load)
    assert (
        binding.grade([0.0] * 4, "fresh")["status"] == "SCORED"
    )  # the unperturbed model passes every gate
    assert binding.grade([0.7, 0.1, -0.4, 0.2], "fresh") == {
        "status": "NOT_SCORED",
        "reason": "gate:g2",
    }
    result = at.attack(
        binding,
        rounds=40,
        seeds=3,
        margin=0.01,
        margin_source="registered",
        sigma0=0.5,
    )
    failed = [
        r
        for r in result["attackers"]
        if r["reason"] == "fresh_unscored_while_sealed_scores"
    ]
    assert failed and not result["all_pass"]
    assert all(r["outcome"] == "FAIL" for r in failed)


def test_the_attack_runs_on_this_binding_and_its_output_holds_no_row_or_model():
    binding = _binding()
    result = at.attack(
        binding,
        rounds=12,
        seeds=2,
        margin=0.01,
        margin_source="provisional_sheet",
        sigma0=0.5,
    )
    assert result["config"]["dim"] == 4 and result["config"]["components"] == [
        "fid",
        "val",
    ]
    blob = json.dumps(result)
    for forbidden in ("theta", "inputs", "base_rows", "pack_root"):
        assert forbidden not in blob


# ---------------------------------------------------------------- check and digest


def test_check_reports_status_total_and_the_difference_from_the_baseline_total():
    binding = _binding()
    out = pb.check(binding)
    assert set(out) == {
        "schema",
        "sealed",
        "fresh",
        "baseline_total",
        "sealed_minus_baseline_total",
    }
    assert out["sealed"]["status"] == out["fresh"]["status"] == "SCORED"
    assert out["baseline_total"] == pytest.approx(0.5 * 0.2 + 0.5 * 0.3)
    assert out["sealed_minus_baseline_total"] == pytest.approx(
        out["sealed"]["total"] - out["baseline_total"]
    )
    assert "rows" not in json.dumps(out)


def test_the_digest_covers_the_module_the_config_the_baselines_and_the_packs(tmp_path):
    for side in ("sealed", "fresh"):
        (tmp_path / f"{side}.json").write_text(json.dumps({"rows": [[1.0]]}))
    config = copy.deepcopy(CONFIG)
    for side in ("sealed", "fresh"):
        config[side]["baseline_predictions"] = str(tmp_path / f"{side}.json")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    binding = pb.build(config, loader=_loader())
    one = pb.binding_digest(path, binding)
    assert one["binding_digest"].startswith("sha256:")
    assert one["pack_manifest_digests"] == {
        "sealed": "sha256:" + "a" * 64,
        "fresh": "sha256:" + "b" * 64,
    }
    assert set(one["baseline_predictions_sha256"]) == {"sealed", "fresh"}
    assert pb.binding_digest(path, binding) == one  # deterministic
    config["amplitude"] = 0.06  # a changed setting is another binding
    path.write_text(json.dumps(config))
    assert pb.binding_digest(path, binding)["binding_digest"] != one["binding_digest"]


# ---------------------------------------------------------------- the fresh set is graded by the same formula


def _two_pack_loader(sealed_pack, fresh_pack):
    sets = {
        "sealed": _make_set(_inputs(12, 1), 0.05, sealed_pack),
        "fresh": _make_set(_inputs(10, 2), 0.05, fresh_pack),
    }

    def load(spec, config):
        side = "sealed" if spec is config["sealed"] else "fresh"
        return (
            sets[side],
            np.asarray(sets[side].bank["inputs"], float),
            SnapshotStub(side),
        )

    return load


def test_a_fresh_pack_with_other_minimums_is_allowed_but_any_other_formula_difference_is_refused():
    base = _pack()
    other_minimums = copy.deepcopy(base)
    other_minimums["legs"]["A"]["minimum"] = 0.25
    pb.build(copy.deepcopy(CONFIG), loader=_two_pack_loader(base, other_minimums))
    changes = {
        "hard_gates": lambda p: p.update(hard_gates=["g1", "speed"]),
        "combination": lambda p: p.update(combination="bottleneck_capped_geometric"),
        "value_weight": lambda p: p.update(value_weight=0.4),
        "legs.A.components": lambda p: p["legs"]["A"]["components"][0].update(
            weight=0.5
        ),
        "legs.D.components": lambda p: p["legs"]["D"]["components"][0].update(
            transform="reciprocal_loss"
        ),
        "decision_policy": lambda p: p.update(decision_policy={"x": 1}),
    }
    for field, mutate in changes.items():
        fresh = copy.deepcopy(base)
        mutate(fresh)
        with pytest.raises(pb.BindingRefused) as refused:
            pb.build(copy.deepcopy(CONFIG), loader=_two_pack_loader(base, fresh))
        assert refused.value.code == f"fresh_pack_differs:{field}"


def test_the_digest_records_each_sets_score_pack_digest(tmp_path):
    sealed, fresh = _pack(), _pack()
    sealed["pack_digest"], fresh["pack_digest"] = (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    for side in ("sealed", "fresh"):
        (tmp_path / f"{side}.json").write_text(json.dumps({"rows": [[1.0]]}))
    config = copy.deepcopy(CONFIG)
    for side in ("sealed", "fresh"):
        config[side]["baseline_predictions"] = str(tmp_path / f"{side}.json")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    binding = pb.build(config, loader=_two_pack_loader(sealed, fresh))
    digest = pb.binding_digest(path, binding)
    assert digest["score_pack_digests"] == {
        "sealed": "sha256:" + "1" * 64,
        "fresh": "sha256:" + "2" * 64,
    }


# ---------------------------------------------------------------- the rest of the grading material is byte-identical


def _material_loader(**fresh_overrides):
    pack = _pack()
    fresh_adapter = fresh_overrides.pop("adapter", None)
    sets = {
        "sealed": _make_set(_inputs(12, 1), 0.05, pack),
        "fresh": _make_set(
            _inputs(10, 2),
            0.05,
            pack,
            roles=_roles(pack, **fresh_overrides),
            adapter=fresh_adapter,
        ),
    }

    def load(spec, config):
        side = "sealed" if spec is config["sealed"] else "fresh"
        return (
            sets[side],
            np.asarray(sets[side].bank["inputs"], float),
            SnapshotStub(side),
        )

    return load


@pytest.mark.parametrize(
    ("role", "value"),
    [
        ("definition", {"definition": 2}),
        ("limits", {"limits": 2}),
        ("objective", {"objective": 2}),
        ("train", b"other-train-bytes"),
    ],
)
def test_a_fresh_set_with_another_accuracy_definition_limit_objective_or_train_is_refused(
    role, value
):
    with pytest.raises(pb.BindingRefused) as refused:
        pb.build(copy.deepcopy(CONFIG), loader=_material_loader(**{role: value}))
    assert refused.value.code == f"fresh_differs:{role}"


def test_a_fresh_set_graded_by_another_adapter_class_or_version_is_refused():
    with pytest.raises(pb.BindingRefused) as refused:
        pb.build(
            copy.deepcopy(CONFIG), loader=_material_loader(adapter=OtherAdapterStub())
        )
    assert refused.value.code == "fresh_differs:adapter"
    newer = AdapterStub()
    newer.VERSION = "1.6"
    with pytest.raises(pb.BindingRefused, match="fresh_differs:adapter"):
        pb.build(copy.deepcopy(CONFIG), loader=_material_loader(adapter=newer))
    pb.build(
        copy.deepcopy(CONFIG), loader=_material_loader()
    )  # identical material builds


def test_the_digest_records_the_role_digests_and_both_sets_leg_minimums(tmp_path):
    sealed, fresh = _pack(), _pack()
    fresh["legs"]["A"]["minimum"] = 0.25
    for side in ("sealed", "fresh"):
        (tmp_path / f"{side}.json").write_text(json.dumps({"rows": [[1.0]]}))
    config = copy.deepcopy(CONFIG)
    for side in ("sealed", "fresh"):
        config[side]["baseline_predictions"] = str(tmp_path / f"{side}.json")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    binding = pb.build(config, loader=_two_pack_loader(sealed, fresh))
    digest = pb.binding_digest(path, binding)
    assert digest["leg_minimums"] == {
        "sealed": {"A": 0.2, "D": 0.3},
        "fresh": {"A": 0.25, "D": 0.3},
    }
    assert digest["role_digests"]["sealed"] == digest["role_digests"]["fresh"]
    assert set(digest["role_digests"]["sealed"]) == {
        "definition",
        "limits",
        "objective",
        "train",
    }


# ---------------------------------------------------------------- the retained inference-pair.json (Motor 1.5's only carrier)

PAIR_ROWS = np.arange(12, dtype=float).reshape(3, 4) / 7.0
PAIR_INPUTS = np.arange(9, dtype="<f8").reshape(3, 3) + 1.0


def _pair(
    rows=PAIR_ROWS, *, repeat=None, inputs=PAIR_INPUTS, recipe="sha256:" + "9" * 64
):
    def phase(body):
        raw = json.dumps(np.asarray(body).tolist(), separators=(",", ":")).encode()
        return {
            "worker_operation": "operation-" + "0" * 64,
            "originals": {
                "predictions.json": {
                    "sha256": "sha256:" + pb._sha(raw),
                    "raw_base64": base64.b64encode(raw).decode(),
                }
            },
        }

    return {
        "schema": "carbon.source-free-inference-pair.v1",
        "recipe_digest": recipe,
        "state_digest": "sha256:" + "8" * 64,
        "inputs_digest": pb.inputs_digest(inputs, "<f8"),
        "primary": phase(rows),
        "repeat": phase(rows if repeat is None else repeat),
    }


def _write(tmp_path, document):
    path = tmp_path / "pair.json"
    path.write_text(json.dumps(document))
    return path


def test_the_inputs_digest_is_the_receivers_own_computation():
    from carbon.development_session.bundle_construction_worker import _digest, _tensors

    expected = _digest(_tensors(inputs=np.asarray(PAIR_INPUTS, dtype="<f8")))
    assert pb.inputs_digest(PAIR_INPUTS, "<f8") == expected
    assert (
        pb.inputs_digest(PAIR_INPUTS.tolist(), "<f8") == expected
    )  # a bank holds lists
    assert pb.inputs_digest(PAIR_INPUTS + 1.0, "<f8") != expected
    assert (
        pb.inputs_digest(PAIR_INPUTS, "<f4") != expected
    )  # the dtype is part of the query


def test_the_primary_of_a_valid_pair_loads(tmp_path):
    path = _write(tmp_path, _pair())
    values = pb.load_predictions(
        path, 3, 4, "<f8", inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8")
    )
    assert np.array_equal(values, PAIR_ROWS)
    pinned = pb.load_predictions(
        path,
        3,
        4,
        "<f8",
        inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8"),
        recipe_digest="sha256:" + "9" * 64,
    )
    assert np.array_equal(pinned, PAIR_ROWS)


def test_a_pair_whose_repeat_differs_from_its_primary_by_one_bit_is_refused(tmp_path):
    other = PAIR_ROWS.copy()
    other[1, 2] = np.nextafter(other[1, 2], np.inf)
    path = _write(tmp_path, _pair(repeat=other))
    with pytest.raises(pb.BindingRefused) as refused:
        pb.load_predictions(
            path, 3, 4, "<f8", inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8")
        )
    assert refused.value.code == "pair_primary_differs_from_repeat"


def test_a_pair_run_on_other_inputs_is_refused_and_so_is_a_missing_digest(tmp_path):
    path = _write(tmp_path, _pair())
    with pytest.raises(pb.BindingRefused) as refused:
        pb.load_predictions(
            path, 3, 4, "<f8", inputs_digest=pb.inputs_digest(PAIR_INPUTS + 1.0, "<f8")
        )
    assert refused.value.code == "pair_inputs_digest_differs"
    with pytest.raises(pb.BindingRefused, match="pair_needs_inputs_digest"):
        pb.load_predictions(path, 3, 4, "<f8")


def test_a_pair_whose_bytes_changed_after_recording_or_with_the_wrong_recipe_is_refused(
    tmp_path,
):
    document = _pair()
    document["primary"]["originals"]["predictions.json"]["sha256"] = (
        "sha256:" + "0" * 64
    )
    with pytest.raises(pb.BindingRefused, match="pair_primary_changed"):
        pb.load_predictions(
            _write(tmp_path, document), 3, 4, "<f8",
            inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8"),
        )  # fmt: skip
    path = _write(tmp_path, _pair())
    with pytest.raises(pb.BindingRefused, match="pair_recipe_digest_differs"):
        pb.load_predictions(
            path, 3, 4, "<f8",
            inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8"),
            recipe_digest="sha256:" + "1" * 64,
        )  # fmt: skip
    wrong = _pair()
    wrong["schema"] = "other"
    with pytest.raises(pb.BindingRefused, match="pair_schema"):
        pb.load_predictions(
            _write(tmp_path, wrong), 3, 4, "<f8",
            inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8"),
        )  # fmt: skip
    broken = _pair()
    del broken["repeat"]["originals"]
    with pytest.raises(pb.BindingRefused, match="pair_repeat_unreadable"):
        pb.load_predictions(
            _write(tmp_path, broken), 3, 4, "<f8",
            inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8"),
        )  # fmt: skip


def test_a_pair_of_the_wrong_size_is_refused_and_the_summary_records_its_digests(
    tmp_path,
):
    path = _write(tmp_path, _pair())
    with pytest.raises(pb.BindingRefused, match="baseline_predictions_size"):
        pb.load_predictions(
            path, 4, 4, "<f8", inputs_digest=pb.inputs_digest(PAIR_INPUTS, "<f8")
        )
    summary = pb.pair_summary(path)
    assert summary["recipe_digest"] == "sha256:" + "9" * 64
    assert summary["inputs_digest"] == pb.inputs_digest(PAIR_INPUTS, "<f8")
    assert pb.pair_summary(_write(tmp_path, {"rows": [[1.0]]})) is None


def test_the_config_may_pin_the_baseline_recipe_digest_and_nothing_else_extra(tmp_path):
    config = copy.deepcopy(CONFIG)
    config["sealed"]["baseline_recipe_digest"] = "sha256:" + "9" * 64
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    assert pb.load_config(path)["sealed"]["baseline_recipe_digest"].startswith(
        "sha256:"
    )
    config["sealed"]["other"] = "x"
    path.write_text(json.dumps(config))
    with pytest.raises(pb.BindingRefused, match="config_sealed_unknown_key:other"):
        pb.load_config(path)


def test_the_digest_records_the_pairs_recipe_and_inputs_digests(tmp_path):
    pair_path = _write(tmp_path, _pair())
    (tmp_path / "fresh.json").write_text(json.dumps({"rows": [[1.0]]}))
    config = copy.deepcopy(CONFIG)
    config["sealed"]["baseline_predictions"] = str(pair_path)
    config["fresh"]["baseline_predictions"] = str(tmp_path / "fresh.json")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    document = pb.binding_digest(path)
    assert document["baseline_pairs"]["sealed"]["recipe_digest"] == "sha256:" + "9" * 64
    assert document["baseline_pairs"]["fresh"] is None


# ---------------------------------------------------------------- every registered hard gate must be PRESENT


def test_a_registered_gate_missing_from_the_aggregates_is_not_scored_never_a_silent_pass():
    binding = _binding(aggregates={"gates": {"g1": True}})  # g2 is absent
    assert binding.grade([0.0] * 4, "sealed") == {
        "status": "NOT_SCORED",
        "reason": "gate_missing:g2",
    }
    nothing = _binding(aggregates={"gates": {}})
    assert nothing.grade([0.0] * 4, "sealed")["reason"] == "gate_missing:g1"
    # the speed placeholder is never required, and an extra unregistered gate does not hide a missing one
    assert (
        _binding(aggregates={"gates": {"g1": True, "g2": True}}).grade(
            [0.0] * 4, "sealed"
        )["status"]
        == "SCORED"
    )
    extra = _binding(aggregates={"gates": {"g1": True, "zz": True}})
    assert extra.grade([0.0] * 4, "sealed")["reason"] == "gate_missing:g2"


# ---------------------------------------------------------------- the pack is read in the validator's copy form


def test_the_sealed_pack_is_resolved_with_the_configured_copy_hotkey_for_both_sets(
    monkeypatch,
):
    from carbon.challenge_validator import calibration_grade_run as run

    seen = []

    class Stop(Exception):
        pass

    def resolve(snapshot, pack_root, challenge, version, copy_hotkey=None):
        seen.append((str(pack_root), challenge, version, copy_hotkey))
        raise Stop

    monkeypatch.setattr(run, "prepare", lambda *args: object())
    monkeypatch.setattr(run, "resolve_bank", resolve)
    for side in ("sealed", "fresh"):
        with pytest.raises(Stop):
            pb._load_set(CONFIG[side], CONFIG)
    assert [entry[3] for entry in seen] == [
        "5" + "H" * 47
    ] * 2  # never None: a copy pack read plainly grades differently
    assert [entry[0] for entry in seen] == [str(Path("/s")), str(Path("/f"))]


def test_the_digest_records_the_copy_hotkey(tmp_path):
    for side in ("sealed", "fresh"):
        (tmp_path / f"{side}.json").write_text(json.dumps({"rows": [[1.0]]}))
    config = copy.deepcopy(CONFIG)
    for side in ("sealed", "fresh"):
        config[side]["baseline_predictions"] = str(tmp_path / f"{side}.json")
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    one = pb.binding_digest(path)
    assert one["copy_hotkey"] == "5" + "H" * 47
    config["copy_hotkey"] = "5" + "J" * 47
    path.write_text(json.dumps(config))
    other = pb.binding_digest(path)
    assert (
        other["binding_digest"] != one["binding_digest"]
        and other["config_sha256"] != one["config_sha256"]
    )


# ---------------------------------------------------------------- no copy batch for the hotkey: refuse, never fall back


@pytest.mark.parametrize("side", ["sealed", "fresh"])
@pytest.mark.parametrize(
    "code", ["copy_header_missing", "copy_header_mismatch", "copy_hotkey_missing"]
)
def test_a_pack_with_no_copy_batch_for_the_hotkey_is_refused_as_copy_batch_missing(
    monkeypatch, side, code
):
    from carbon.challenge_validator import calibration_grade as cg
    from carbon.challenge_validator import calibration_grade_run as run

    calls = []

    def resolve(snapshot, pack_root, challenge, version, copy_hotkey=None):
        calls.append(copy_hotkey)
        raise cg.CalibrationRefused(code)

    monkeypatch.setattr(run, "prepare", lambda *args: object())
    monkeypatch.setattr(run, "resolve_bank", resolve)
    with pytest.raises(pb.BindingRefused) as refused:
        pb._load_set(CONFIG[side], CONFIG)
    assert refused.value.code == "copy_batch_missing"
    assert calls == [
        "5" + "H" * 47
    ]  # the copy path was asked for, once; no plain read followed


@pytest.mark.parametrize(
    "code",
    [
        "copy_header_malformed",
        "copy_batch_malformed",
        "copy_digest_mismatch",
        "canonical_digest_mismatch",
        "copy_challenge_unregistered",
    ],
)
def test_a_copy_that_does_not_verify_is_refused_with_its_code(monkeypatch, code):
    from carbon.challenge_validator import calibration_grade as cg
    from carbon.challenge_validator import calibration_grade_run as run

    def resolve(*args, **kwargs):
        raise cg.CalibrationRefused(code)

    monkeypatch.setattr(run, "prepare", lambda *args: object())
    monkeypatch.setattr(run, "resolve_bank", resolve)
    with pytest.raises(pb.BindingRefused) as refused:
        pb._load_set(CONFIG["sealed"], CONFIG)
    assert refused.value.code == f"copy_batch_invalid:{code}"


def test_any_other_pack_refusal_is_not_relabelled_as_a_copy_problem(monkeypatch):
    from carbon.challenge_validator import calibration_grade as cg
    from carbon.challenge_validator import calibration_grade_run as run

    def resolve(*args, **kwargs):
        raise cg.CalibrationRefused("sealed_bank_mismatch")

    monkeypatch.setattr(run, "prepare", lambda *args: object())
    monkeypatch.setattr(run, "resolve_bank", resolve)
    with pytest.raises(cg.CalibrationRefused) as refused:
        pb._load_set(CONFIG["sealed"], CONFIG)
    assert refused.value.code == "sealed_bank_mismatch"


# ---------------------------------------------------------------- unknown keys, per-side pins, one trained state on both sides


def _config_file(tmp_path, mutate):
    config = copy.deepcopy(CONFIG)
    mutate(config)
    path = tmp_path / "c.json"
    path.write_text(json.dumps(config))
    return path


def test_any_unknown_key_is_refused_at_the_top_level_and_in_each_side(tmp_path):
    # the TL's recipe pin sat at the top level and was silently ignored: never again
    with pytest.raises(pb.BindingRefused) as refused:
        pb.load_config(
            _config_file(
                tmp_path,
                lambda c: c.update(baseline_recipe_digest="sha256:" + "9" * 64),
            )
        )
    assert refused.value.code == "config_unknown_key:baseline_recipe_digest"
    for side in ("sealed", "fresh"):
        with pytest.raises(pb.BindingRefused) as refused:
            pb.load_config(
                _config_file(tmp_path, lambda c, s=side: c[s].update(typo=1))
            )
        assert refused.value.code == f"config_{side}_unknown_key:typo"


def test_the_pins_live_per_side_and_must_be_digests(tmp_path):
    def pinned(config):
        config["sealed"]["baseline_recipe_digest"] = "sha256:" + "8" * 64
        config["sealed"]["baseline_state_digest"] = "sha256:" + "7" * 64
        config["fresh"]["baseline_recipe_digest"] = "sha256:" + "8" * 64

    loaded = pb.load_config(_config_file(tmp_path, pinned))
    assert loaded["sealed"]["baseline_state_digest"].endswith("7" * 64)
    with pytest.raises(pb.BindingRefused, match="config_sealed_baseline_state_digest"):
        pb.load_config(
            _config_file(
                tmp_path, lambda c: c["sealed"].update(baseline_state_digest="nope")
            )
        )


def test_the_catalog_recipe_digest_is_required_and_recorded_in_the_digest(tmp_path):
    with pytest.raises(
        pb.BindingRefused, match="config_catalog_recipe_digest_required"
    ):
        pb.load_config(_config_file(tmp_path, lambda c: c.pop("catalog_recipe_digest")))
    with pytest.raises(
        pb.BindingRefused, match="config_catalog_recipe_digest_required"
    ):
        pb.load_config(
            _config_file(tmp_path, lambda c: c.update(catalog_recipe_digest="988900c9"))
        )
    for side in ("sealed", "fresh"):
        (tmp_path / f"{side}.json").write_text(json.dumps({"rows": [[1.0]]}))

    def point(config):
        for side in ("sealed", "fresh"):
            config[side]["baseline_predictions"] = str(tmp_path / f"{side}.json")

    path = _config_file(tmp_path, point)
    assert pb.binding_digest(path)["catalog_recipe_digest"] == "sha256:" + "c" * 64


def test_the_state_and_recipe_pins_are_applied_to_the_pair_and_a_mismatch_is_refused(
    tmp_path,
):
    path = _write(tmp_path, _pair())
    digest = pb.inputs_digest(PAIR_INPUTS, "<f8")
    ok = pb.read_baseline(
        path, 3, 4, "<f8", inputs_digest=digest,
        recipe_digest="sha256:" + "9" * 64, state_digest="sha256:" + "8" * 64,
    )  # fmt: skip
    assert ok[1]["state_digest"] == "sha256:" + "8" * 64
    with pytest.raises(pb.BindingRefused, match="pair_state_digest_differs"):
        pb.read_baseline(
            path, 3, 4, "<f8", inputs_digest=digest, state_digest="sha256:" + "1" * 64
        )
    with pytest.raises(pb.BindingRefused, match="pair_recipe_digest_differs"):
        pb.read_baseline(
            path, 3, 4, "<f8", inputs_digest=digest, recipe_digest="sha256:" + "1" * 64
        )


def test_a_pin_on_a_file_that_is_not_a_pair_is_refused_not_ignored(tmp_path):
    rows = tmp_path / "r.json"
    rows.write_text(json.dumps({"rows": PAIR_ROWS.tolist()}))
    for pins in (
        {"recipe_digest": "sha256:" + "9" * 64},
        {"state_digest": "sha256:" + "8" * 64},
    ):
        with pytest.raises(pb.BindingRefused, match="baseline_pin_unverifiable"):
            pb.read_baseline(rows, 3, 4, "<f8", **pins)
    assert pb.read_baseline(rows, 3, 4, "<f8")[1] is None  # unpinned rows still load


def _pair_sets(sealed_pair, fresh_pair):
    pack = _pack()
    sets = {
        "sealed": _make_set(_inputs(12, 1), 0.05, pack, baseline_pair=sealed_pair),
        "fresh": _make_set(_inputs(10, 2), 0.05, pack, baseline_pair=fresh_pair),
    }

    def load(spec, config):
        side = "sealed" if spec is config["sealed"] else "fresh"
        return (
            sets[side],
            np.asarray(sets[side].bank["inputs"], float),
            SnapshotStub(side),
        )

    return load


def _summary(**overrides):
    base = {"recipe_digest": "sha256:" + "9" * 64, "state_digest": "sha256:" + "8" * 64}
    return {**base, **overrides}


def test_the_fresh_baseline_must_come_from_the_same_recipe_and_trained_state(tmp_path):
    pb.build(copy.deepcopy(CONFIG), loader=_pair_sets(_summary(), _summary()))
    for field in ("recipe_digest", "state_digest"):
        other = _summary(**{field: "sha256:" + "0" * 64})
        with pytest.raises(pb.BindingRefused) as refused:
            pb.build(copy.deepcopy(CONFIG), loader=_pair_sets(_summary(), other))
        assert refused.value.code == f"fresh_pair_differs:{field}"
    # a pair on one side and plain rows on the other cannot show a shared state
    for sealed, fresh in ((_summary(), None), (None, _summary())):
        with pytest.raises(pb.BindingRefused, match="fresh_baseline_not_a_pair"):
            pb.build(copy.deepcopy(CONFIG), loader=_pair_sets(sealed, fresh))
    pb.build(
        copy.deepcopy(CONFIG), loader=_pair_sets(None, None)
    )  # no pair anywhere: nothing to compare
