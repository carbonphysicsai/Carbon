"""Motor 1.6: 1.5's material with the in-pack baseline's minimums graded the way miners are (the Cooling 1.7 rule).

Held here: (1) the baseline's legs are what `pool_exam.measure_pool` returns for the registered baseline over EVERY exam row,
and equality clears them exactly; (2) the baseline is the registered learned-krr-v1 (the same fit as Motor 1.5's `baseline_outputs`);
(3) `baseline_floor_total` rides in the pack when a measured number is passed and is absent (the pack bit-identical) otherwise;
(4) the registration (overlay entry, constants, published exam) is 1.5's with the new names and an unregistered s_h; (5) the
dispatch touches only Motor's sealed grader, so no other Challenge's producer digest moves.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_pack import MOTOR, NAMES, _bank, batch, material  # noqa: F401 - fixtures

from carbon.challenge_kit import physical_pack, version_overlay, version_registry
from carbon.scoring import (
    dual_score,
    motor_physics,
    pool_adapters,
    pool_exam,
    pool_version,
)
from carbon.scoring import motor_pool_baseline_dual_pack as sixteen
from carbon.scoring import motor_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

IMAGE = "sha256:" + "1" * 64


def _in_domain_target(target_id, seed, offset):
    """A synthetic pool whose designs and fixed conditions lie inside Motor's declared input box: the registered baseline
    answers only inside it (`carbon.motor.domain.check_inputs`), so a pool outside the box would refuse, as it should.
    """
    import random

    from carbon.motor import domain
    from carbon.motor_grid_exam.domain import CONDITION_INPUTS, DESIGN_INPUTS
    from carbon.scoring import pool_grader
    from carbon.scoring.pool_grader import Limit

    rng = random.Random(seed)
    n = len(DESIGN_INPUTS)
    box = tuple(domain.INPUT_BOUNDS[name] for name in DESIGN_INPUTS)
    unit = [[rng.random() for _ in range(n)] for _ in range(100)]
    designs = [
        [lo + u * (hi - lo) for u, (lo, hi) in zip(row, box, strict=True)]
        for row in unit
    ]
    truths = [{"f": sum(u), "g": sum(x * x for x in u)} for u in unit]
    fixed = {
        name: min(
            max(
                sum(domain.INPUT_BOUNDS[name]) / 2 + offset,
                domain.INPUT_BOUNDS[name][0],
            ),
            domain.INPUT_BOUNDS[name][1],
        )
        for name in CONDITION_INPUTS
    }
    return pool_grader.build_target(
        target_id=target_id,
        conditions={"target_id": target_id, "fixed": fixed},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", n * 0.45),),
        u={"f": 0.001, "g": 0.001},
        box=box,
        designs=designs,
        truths=truths,
        agen=range(92, 100),
        start=tuple(
            0.5 for _ in box
        ),  # the optimizer's start is a point of the unit box
        seed=seed,
    )


def _material_16():
    from carbon.motor_grid_exam.domain import DESIGN_INPUTS
    from carbon.scoring import pool_grader

    return {
        **copy.deepcopy(material()),
        "version": "1.6",
        "design_names": list(DESIGN_INPUTS),
        "sets": [
            [
                pool_grader.dump_pool(_in_domain_target("A1", 1, 0.0)),
                pool_grader.dump_pool(_in_domain_target("A2", 2, 1.0)),
            ]
        ],
    }


class Recorder:
    """A stand-in for `pool_exam.measure_pool`: records what it was asked and returns legs that are a deterministic function of
    the model's answers (identical answers, identical legs)."""

    def __init__(self, gates):
        self.calls = []
        self.gates = gates
        self.fail = ()

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        outputs = kwargs["outputs"]
        skew = sum(sum(row) for row in outputs) / (len(outputs) * len(outputs[0]))
        a = 0.40 + 0.2 * (1 / (1 + math.exp(-skew / 50)))
        return {
            "A": a,
            "D": a / 2,
            "gates": {g: g not in self.fail for g in self.gates},
            "decision_outcome": "VERIFIED_FEASIBLE",
        }


@pytest.fixture
def scene(batch, monkeypatch):  # noqa: F811 - the imported fixture
    bank = _bank(batch, _material_16(), "1.6")
    adapter = sixteen.sealed_adapter("1.6")
    adapter.bank = bank
    public = physical_pack.public_roles(MOTOR, "1.6")
    names = physical.input_names(adapter)
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "leg_minimum_platform": physical.leg_minimum_platform(
            **physical.leg_minimum_platform(IMAGE, physical.DEVICE_CLASS)
        ),
    }
    gates = [
        *sealed.applied_pack()["hard_gates"],
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
    ]
    recorder = Recorder(gates)
    monkeypatch.setattr(pool_exam, "measure_pool", recorder)
    monkeypatch.setattr(pool_version, "registered_policies", lambda *a, **k: object())
    monkeypatch.setattr(pool_version, "registered_a_multiplier", lambda *a, **k: 3.0)
    monkeypatch.setattr(pool_adapters, "official_binding", lambda *a, **k: object())
    kwargs = {
        "bank_rows": physical.bank_rows(bank, names),
        "definition": definition,
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
        "train_raw": public["train"],
        "names": names,
    }
    return adapter, kwargs, recorder, bank


def test_the_minimums_are_what_measure_pool_returns_for_the_baseline_over_every_exam_row(
    scene,
):
    adapter, kwargs, recorder, _bank_unused = scene
    applied = adapter.applied_pack(**kwargs)
    (call,) = recorder.calls  # one grade of the baseline, through the miners' function
    rows = kwargs["bank_rows"]
    assert len(call["outputs"]) == len(call["bank_rows"]) == len(rows)
    assert any(r.get("cohort") == pool_version.POOL_COHORT for r in call["bank_rows"])
    assert call["repeats"] == [call["outputs"], call["outputs"]]
    assert call["a_multiplier"] == 3.0
    assert len(call["speed_call_seconds"]) == pool_exam.SPEED_SAMPLE
    assert all(s > 0 and math.isfinite(s) for s in call["speed_call_seconds"])
    expected = recorder(**call)
    assert applied["legs"]["A"]["minimum"] == pytest.approx(expected["A"], abs=1e-15)
    assert applied["legs"]["D"]["minimum"] == pytest.approx(expected["D"], abs=1e-15)
    assert applied["hard_gates"][-2:] == [pool_exam.PHYSICS_GATE, pool_exam.SPEED_GATE]
    assert motor_physics.GATE in applied["hard_gates"]
    assert (
        "baseline_floor_total" not in applied
    )  # absent unless a measured floor is passed


def test_a_model_identical_to_the_baseline_clears_the_minimums_exactly_and_a_hair_worse_does_not(
    scene,
):
    adapter, kwargs, _recorder, _unused = scene
    applied = adapter.applied_pack(**kwargs)
    provisional = "sha256:" + "0" * 64
    pack = dual_score.register_pack(
        {
            **applied,
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
        }
    )

    def graded(a, d):
        return dual_score.score(
            {
                "schema": dual_score.INPUT_SCHEMA,
                "scope": applied["scope"],
                "challenge": applied["challenge"],
                "physics_contract_digest": provisional,
                "measurement_contract_digest": provisional,
                "population_role": "P",
                "common_mask_digest": provisional,
                "models": [
                    {
                        "artifact_digest": provisional,
                        "gates": {g: "PASS" for g in applied["hard_gates"]},
                        "measurements": {
                            physical.METRICS["A"]: {
                                "status": "RESOLVED",
                                "value": a,
                                "unit": "1",
                            },
                            physical.METRICS["D"]: {
                                "status": "RESOLVED",
                                "value": d,
                                "unit": "1",
                            },
                        },
                        "decision_outcome": "VERIFIED_FEASIBLE",
                    }
                ],
            },
            pack,
        )["models"][0]

    a, d = applied["legs"]["A"]["minimum"], applied["legs"]["D"]["minimum"]
    assert graded(a, d)["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert graded(math.nextafter(a, 0.0), d)["status"] == "REQUIRED_LEG_MINIMUM_FAILED"
    assert graded(a, math.nextafter(d, 0.0))["status"] == "REQUIRED_LEG_MINIMUM_FAILED"


def test_a_baseline_that_fails_a_gate_or_a_missing_pool_sets_no_minimums(scene):
    adapter, kwargs, recorder, _unused = scene
    recorder.fail = (pool_exam.PHYSICS_GATE,)
    with pytest.raises(sealed.Refused, match="fails:.*physics"):
        adapter.applied_pack(**kwargs)
    recorder.fail = ()
    adapter.bank = None
    with pytest.raises(sealed.Refused, match="motor_pool_material_missing"):
        adapter.applied_pack(**kwargs)


def test_the_baseline_floor_rides_in_the_pack_only_when_a_measured_number_is_passed(
    scene, monkeypatch
):
    adapter, kwargs, recorder, _unused = scene
    plain = adapter.applied_pack(**kwargs)
    derived = dual_score.minimums_total(
        {
            **plain,
            "physics_contract_digest": "x",
            "measurement_contract_digest": "x",
        }
    )
    assert derived is not None
    adapter.baseline_floor_total = derived + 0.05
    with_floor = adapter.applied_pack(**kwargs)
    assert with_floor["baseline_floor_total"] == derived + 0.05
    assert {k: v for k, v in with_floor.items() if k != "baseline_floor_total"} == plain
    provisional = "sha256:" + "0" * 64
    registered = dual_score.register_pack(
        {
            **with_floor,
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
        }
    )
    assert registered["baseline_floor_total"] == derived + 0.05
    # a floor below the minimums' total is refused by the pack registrar, never written
    adapter.baseline_floor_total = derived - 0.05
    below = adapter.applied_pack(**kwargs)
    with pytest.raises(dual_score.DualScoreRefused, match="below_minimums"):
        dual_score.register_pack(
            {
                **below,
                "physics_contract_digest": provisional,
                "measurement_contract_digest": provisional,
            }
        )
    # the calibration build never carries a floor (it has no minimums)
    adapter.baseline_floor_total = 0.9
    adapter.calibrating = True
    _toy_grading(recorder, monkeypatch)
    assert "baseline_floor_total" not in adapter.applied_pack(**kwargs)


def test_the_baseline_is_the_registered_fit_of_motor_1_5(scene):
    from carbon.scoring import motor_dual_pack

    _adapter, kwargs, _recorder, _unused = scene
    rows = kwargs["bank_rows"][:6]
    outputs, seconds = sixteen.pool_baseline(bank_rows=rows, sample_count=2)
    expected = motor_dual_pack.baseline_outputs([r["inputs"] for r in rows])
    assert outputs == expected  # exactly 1.5's registered model, one BLAS thread
    assert len(outputs[0]) == 60 and len(seconds) == 2 and all(s > 0 for s in seconds)


# --- the calibration build ------------------------------------------------------------------------------------------


def _toy_grading(recorder, monkeypatch):
    from test_pool_grader import HONESTY, OPTIMIZER, oracle, toy_target

    from carbon.scoring import pool_grader

    specs = [toy_target(f"t{i}", seed=i) for i in range(2)]
    truth = oracle(specs)

    def predict(conditions, designs):
        return [
            {k: v + 3 * 0.01 for k, v in row.items()}
            for row in truth(conditions, designs)
        ]

    inner = recorder.__call__

    def grading(**kwargs):
        pool_grader.grade_set(specs, predict, OPTIMIZER, HONESTY)
        return inner(**kwargs)

    monkeypatch.setattr(pool_exam, "measure_pool", grading)


def test_the_calibration_build_reports_only_the_count_the_digest_and_the_median(
    scene, monkeypatch
):
    adapter, kwargs, recorder, _unused = scene
    _toy_grading(recorder, monkeypatch)
    adapter.calibrating = True
    adapter.applied_pack(**kwargs)
    report = adapter.calibration
    assert set(report) == {
        "schema",
        "targets",
        "e_list_sha256",
        "median_e",
        "strict_s_h_proposal",
    }
    assert report["targets"] == 2 and report["median_e"] == pytest.approx(3.0, rel=1e-6)
    assert report["strict_s_h_proposal"] == pytest.approx(0.25 * report["median_e"])
    other = sixteen.sealed_adapter("1.6")
    other.bank = adapter.bank
    other.applied_pack(**kwargs)
    assert other.calibration is None


def test_the_error_recorder_restores_the_grader_and_the_report_refuses_unusable_errors():
    from carbon.scoring import pool_grader

    real = pool_grader.grade_set
    with sixteen._recording_target_errors([]):
        assert pool_grader.grade_set is not real
    assert pool_grader.grade_set is real
    for bad in ([], [float("inf")], [float("nan")], [1]):
        with pytest.raises(sealed.Refused, match="calibration_errors"):
            sixteen.calibration_report(bad)
    assert sixteen.calibration_report([2.0, 4.0, 3.0])["median_e"] == 3.0


def test_1_6s_s_h_is_unregistered_so_it_grades_nothing_and_reads_as_a_placeholder_only_while_calibrating():
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies(MOTOR, "1.6")
    with sixteen._calibration_policies():
        policies = pool_version.registered_policies(MOTOR, "1.6")
        assert policies.honesty.scale == sixteen.CALIBRATION_PLACEHOLDER_S_H
        assert policies.optimizer.pick_rule == {"kind": "top_k", "k": 3} or str(
            policies.optimizer.pick_rule
        )  # the registered pick rule is carried
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies(MOTOR, "1.6")


# --- registration and identity --------------------------------------------------------------------------------------


def test_the_overlay_entry_is_1_5s_with_the_new_names_only():
    new, old = (version_registry.entry(MOTOR, v) for v in ("1.6", "1.5"))
    own = {
        "version",
        "sealed_evaluation",
        "predecessor",
        "catalog_entries_from",
        "facts",
    }
    for field in new.__dataclass_fields__:
        if field not in own:
            assert getattr(new, field) == getattr(old, field), field
    assert new.sealed_evaluation == "motor-pool-sealed-v2" != old.sealed_evaluation
    assert new.predecessor == "1.5" and new.catalog_entries_from == (
        "1.5",
        "1.4",
        "1.3",
    )
    assert (MOTOR, "1.6") in version_overlay.install()
    assert (
        sealed.POOL_VERSIONS["1.6"]
        == sixteen.POOL_VERSIONS["1.6"]
        == (
            new.sealed_evaluation,
            "motor-sealed-pool-set",
        )
    )


def test_1_6_shares_1_5s_construction_so_the_catalog_carries_1_5s_entries():
    from carbon.backbone_catalog import carries

    old, new = (physical_pack_kit(v) for v in ("1.5", "1.6"))
    assert new["train_digest"] == old["train_digest"]
    assert new["interface_digest"] == old["interface_digest"]
    assert carries is not None


def physical_pack_kit(version):
    from carbon.challenge_kit import physical_material

    return physical_material.construction_kit(MOTOR, version)


def test_the_constants_name_the_scoring_and_leave_s_h_to_the_calibration():
    document = json.loads(pool_version.CONSTANTS.read_bytes())["versions"]
    new, old = document[f"{MOTOR} 1.6"], document[f"{MOTOR} 1.5"]
    assert new["optimizer"]["pick_rule"] == {"kind": "top_k", "k": 3}
    assert new["optimizer"]["d_aggregate"] == "balanced_region_mean"
    assert new["honesty"]["scale"] == pool_version.HUMAN_INPUT  # measured, not typed
    for key in ("a_multiplier", "a_rule", "agen_scales", "c_rule"):
        assert new[key] == old[key]


def test_the_published_exam_registers_no_constants_for_1_6_until_s_h_exists():
    from carbon.challenge_registry import published_exam

    assert (MOTOR, "1.6") in published_exam._POOL_VERSIONS
    assert (MOTOR, "1.6") not in published_exam._REGISTERED_POOL


def test_the_definition_refuses_a_missing_or_changed_registration_digest():
    adapter = sixteen.sealed_adapter("1.6")
    with pytest.raises(sealed.Refused, match="motor_registration_digest"):
        adapter.validate_definition({})
    bound = version_overlay.entry_digest(MOTOR, "1.6")
    with pytest.raises(sealed.Refused):
        adapter.validate_definition(
            {sixteen.REGISTRATION_KEY: bound}
        )  # bound, but not a Motor definition


# --- the dispatch and the producer identities --------------------------------------------------------------------------


def test_1_6_is_routed_to_its_own_module_and_1_5_is_not():
    chosen = sealed.adapter("1.6")
    assert chosen._module is sixteen and chosen.POOL_GRADED and chosen.IN_PACK_BASELINE
    assert getattr(sealed.adapter("1.5"), "IN_PACK_BASELINE", False) is False
    assert sixteen.sealed_adapter("1.5") is None
    assert sealed.adapter_for_bank is not None


def test_1_6_producer_identity_names_its_module_and_no_older_version_does():
    assert "motor_pool_baseline_dual_pack.py" in sixteen.FILES
    assert "motor_pool_baseline_dual_pack.py" not in sealed.FILES
    assert "motor_pool_baseline_dual_pack.py" not in sealed._motor.FILES
    assert set(sealed.FILES) <= set(sixteen.FILES)


#: Producer digests of every non-Motor-sealed adapter on the base (e0e3471e): the Motor 1.6 dispatch edits only
#: motor_sealed_dual_pack.py and adds a module, so no other Challenge's identity (and not Motor's development adapter) moves.
UNMOVED = {
    "motor_dual_pack": "sha256:3089b982651cd1b158affd8e145ad544a80d6be26d1e6ba01e9323bc502762b9",
    "f02_dual_pack": "sha256:60861496cb77682c25e338d75744a99161cc830ac94ded9c75d54890d7a00c9b",
    "f02_sealed_dual_pack": "sha256:4c49041bb04d0971d25f896899f83f122082a24fc252210733c1f5d67d909263",
    "f08_dual_pack": "sha256:1d244cf56dd30de4a7b6e3961cd4f6c4e9c007487941ae0dcd2de46e4cf0e29e",
    "f08_sealed_dual_pack": "sha256:43847f922bb63e7f72136c67c2c3da74600c71485452e5f19f19228c36baaefb",
    "battery_dual_pack": "sha256:852fb21427ba7fec8c635fc588834455f1d55e91f3b4dfa5b925bea2b7924e22",
    "battery_sealed_dual_pack": "sha256:e8d450a427d5c7572c9e1d41d070719bdc9ee10830e4eb41f09c5f8cabdaf45c",
    "cooling_dual_pack": "sha256:c29704e900c345d1fc81653f78afc796ed91861370a584d7660a7f3dbeb5b0d0",
    "cooling_encoded_dual_pack": "sha256:a468a5110c8245fa1c7e1ffb812cf9c78ecacc7b4ef1a245e02832da53ea3699",
    "cooling_hotspot_dual_pack": "sha256:df9e5d27d3959d017b9aae7243a5846c74234a3825c376d9183f9d6e60451dca",
    "cooling_pool_baseline_dual_pack": "sha256:8b33a0ee4098b7a92e81adb6cebc12600599893a88d1f9c8f683a753a1e2b0a2",
    # the live Motor 1.1-1.5 sealed producer: Motor 1.6 is reached through the overlay dispatch, never by editing it
    "motor_sealed_dual_pack": "sha256:3d45a99670763e003a6fa43393730ab7518e004c2a32a5ae80ef1b91e7b678f4",
}


def test_no_other_producer_identity_moves():
    from carbon.scoring import (
        battery_dual_pack,
        battery_sealed_dual_pack,
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        cooling_hotspot_dual_pack,
        f02_dual_pack,
        f02_sealed_dual_pack,
        f08_dual_pack,
        f08_sealed_dual_pack,
        motor_dual_pack,
        motor_sealed_dual_pack,
    )
    from carbon.scoring import cooling_pool_baseline_dual_pack as cooling_17

    modules = {
        "motor_dual_pack": motor_dual_pack,
        "motor_sealed_dual_pack": motor_sealed_dual_pack,
        "f02_dual_pack": f02_dual_pack,
        "f02_sealed_dual_pack": f02_sealed_dual_pack,
        "f08_dual_pack": f08_dual_pack,
        "f08_sealed_dual_pack": f08_sealed_dual_pack,
        "battery_dual_pack": battery_dual_pack,
        "battery_sealed_dual_pack": battery_sealed_dual_pack,
        "cooling_dual_pack": cooling_dual_pack,
        "cooling_encoded_dual_pack": cooling_encoded_dual_pack,
        "cooling_hotspot_dual_pack": cooling_hotspot_dual_pack,
        "cooling_pool_baseline_dual_pack": cooling_17,
    }
    assert set(modules) == set(UNMOVED)
    for name, expected in UNMOVED.items():
        assert physical.producer_digest(modules[name]) == expected, name


# --- the writer's plumbing ----------------------------------------------------------------------------------------


def test_the_hooked_sealed_writer_routes_1_6_to_the_in_pack_writer_and_refuses_a_retained_binding(
    monkeypatch, tmp_path
):
    seen = {}

    def fake(root, bank, **kwargs):
        seen.update(kwargs)
        return "manifest"

    monkeypatch.setattr(sixteen, "write_sealed_pack", fake)
    out = sealed.write_sealed_pack(
        tmp_path, {}, version="1.6", baseline_floor_total=0.7, calibration=True
    )
    assert out == "manifest"
    assert seen["baseline_floor_total"] == 0.7 and seen["calibration"] is True
    assert seen["version"] == "1.6"
    with pytest.raises(ValueError, match="in-pack baseline"):
        sealed.write_sealed_pack(
            tmp_path, {}, version="1.6", baseline_binding_raw=b"{}"
        )
    # the image-registered 1.5 delegates to the file's own writer, which knows no crown floor
    with pytest.raises(TypeError, match="baseline_floor_total"):
        sealed.write_sealed_pack(tmp_path, {}, version="1.5", baseline_floor_total=0.7)


# --- the dispatch hook and the signed extended region ---------------------------------------------------------------


def test_the_dispatch_block_pins_the_module_file_and_the_signed_region():
    import hashlib

    entry = json.loads(version_overlay.OVERLAY_PATH.read_bytes())["versions"][
        f"{MOTOR} 1.6"
    ]
    block = entry["dispatch"]
    assert block["module"] == "carbon.scoring.motor_pool_baseline_dual_pack"
    module = Path(sixteen.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert block["sha256"] == hashlib.sha256(module).hexdigest()
    config = block["config"]
    assert config["region_file_sha256"] == (
        "c3e41b52242f476ecc7252869b092b142d4112f06281bad1bd3d1817c806bfcd"
    )
    assert config["region_sha256"] == (
        "248460a61ec806ea6756b1a453e5e15890e69f4a6bc30814b11c6d53686a8b4c"
    )
    assert set(config["baseline_box"]) == set(NAMES)
    assert sixteen._BOX == sixteen._check_region(config)


def test_the_live_motor_sealed_module_is_byte_identical_to_the_image_move_base():
    import hashlib

    raw = Path(sealed.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == MOTOR_SEALED_FILE_SHA256


#: sha256 of carbon/scoring/motor_sealed_dual_pack.py at image-move3c (e0e3471e): 1.6 never edits it.
MOTOR_SEALED_FILE_SHA256 = (
    "d5c6d57806e70c05e9af9a9122d443c2bb469ce53bb9d1c999cc1b2b6306d2aa"
)


def _row(**over):
    from carbon.motor import domain

    row = {name: sum(domain.INPUT_BOUNDS[name]) / 2 for name in domain.INPUTS}
    row.update(over)
    return row


def test_the_baseline_answers_a_shell_row_outside_train_and_refuses_one_outside_the_signed_region():
    from carbon.motor import domain
    from carbon.scoring import motor_dual_pack

    low, _high = domain.INPUT_BOUNDS["magnet_mm"]
    box_low = sixteen._BOX["magnet_mm"][0]
    assert box_low < low  # the signed region reaches below TRAIN
    shell = _row(magnet_mm=(low + box_low) / 2)
    inside = _row()
    outputs, seconds = sixteen.pool_baseline(
        bank_rows=[{"inputs": inside}, {"inputs": shell}], sample_count=1
    )
    assert len(outputs) == 2 and all(len(r) == 60 for r in outputs) and seconds
    # a row inside TRAIN is bit-equal to the registered baseline; the shell row is answered, not refused
    assert outputs[0] == motor_dual_pack.baseline_outputs([inside])[0]
    assert all(math.isfinite(v) for v in outputs[1])
    for bad in (
        _row(magnet_mm=box_low - 1e-6),
        _row(embrace=sixteen._BOX["embrace"][1] + 1e-6),
        {k: v for k, v in inside.items() if k != "tooth_mm"},
        _row(airgap_mm=float("nan")),
    ):
        with pytest.raises(sealed.Refused, match="motor_baseline_row"):
            sixteen.pool_baseline(bank_rows=[{"inputs": bad}], sample_count=1)


def test_the_baseline_refuses_to_run_with_no_registered_region(monkeypatch):
    monkeypatch.setattr(sixteen, "_BOX", None)
    with pytest.raises(sealed.Refused, match="motor_baseline_region_unregistered"):
        sixteen.pool_baseline(bank_rows=[{"inputs": _row()}], sample_count=1)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: {**c, "extra": 1},
        lambda c: {k: v for k, v in c.items() if k != "region_sha256"},
        lambda c: {**c, "region_sha256": "xyz"},
        lambda c: {**c, "baseline_box": {**c["baseline_box"], "tooth_mm": [5.0, 1.0]}},
        lambda c: {
            **c,
            "baseline_box": {
                k: v for k, v in c["baseline_box"].items() if k != "tooth_mm"
            },
        },
    ],
)
def test_a_malformed_region_config_is_refused(mutate):
    entry = json.loads(version_overlay.OVERLAY_PATH.read_bytes())["versions"][
        f"{MOTOR} 1.6"
    ]
    with pytest.raises(sealed.Refused):
        sixteen._check_region(mutate(copy.deepcopy(entry["dispatch"]["config"])))
