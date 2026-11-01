"""Cooling 1.7: the baseline's leg minimums are graded the way miners are (COOLING_BASELINE_FAIRNESS_20261101).

Claims: (1) a model whose outputs are identical to the in-pack baseline's clears the minimums exactly (equality passes) and one a
hair worse does not; (2) 1.6's modules and pack are byte-identical to before (pinned digests); (3) the minimum source is
`pool_exam.measure_pool`, asserted structurally: the minimums are the values that function returns for the baseline over EVERY
exam row, and they differ from 1.6's separately-measured ones. Synthetic pools on Cooling's real interface (as
test_pool_pack_cooling) with `measure_pool` replaced by a recording stand-in: the real pool measurement of this material is
the box run, not this test."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_pack_cooling import (  # noqa: F401 - the fixtures and builders
    COOLING,
    NAMES,
    _bank,
    batch,
    material,
)

from carbon.challenge_kit import physical_pack
from carbon.cold_plate.output_encoding import decode_flat
from carbon.scoring import (
    cooling_dual_measurement as cdm,
)
from carbon.scoring import (
    cooling_hotspot_dual_pack as hotspot,
)
from carbon.scoring import (
    cooling_physics,
    dual_score,
    pool_adapters,
    pool_exam,
    pool_version,
)
from carbon.scoring import (
    cooling_pool_baseline_dual_pack as seventeen,
)
from carbon.scoring import physical_dual_pack as physical

IMAGE = "sha256:" + "1" * 64

# sha256 of each 1.6 module (CRLF read as LF), as of the commit that added 1.7: none of them is edited by it
PINNED_16 = {
    "cooling_dual_pack.py": "e64b9b9ff3cf97b6b9c885457cb82ee8554251acbeb231a91da0b405c8615a81",
    "cooling_encoded_dual_pack.py": "056f2837d6dc9b20fa45a0d7f1453f53b7d4132224f3a0f6564e06b69f62b8e0",
    "cooling_hotspot_dual_pack.py": "bc8d8c9d78bbed58c8295e43177d9a71313f3815cf2cd7f4fa90c578b8153478",
}


def _inputs():
    public = physical_pack.public_roles(COOLING, "1.6")
    return {
        "physics": physical_pack.physics_contract(COOLING, "1.6"),
        "interface_raw": public["interface"],
        "train_raw": public["train"],
        "limits_raw": public["important_limit_definition"],
        "objective_raw": public["design_objective"],
    }


class Recorder:
    """A stand-in for `pool_exam.measure_pool`: records what it was asked and returns legs that are a deterministic function of
    the model's answers, so two models with identical outputs get identical legs and a worse one lower legs.
    """

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
    bank = _bank(batch, material("1.6"), "1.6")
    adapter = seventeen.sealed_adapter("1.7")
    adapter.bank = bank
    inputs = _inputs()
    platform = physical.leg_minimum_platform(IMAGE, physical.DEVICE_CLASS)
    definition = {
        **adapter.definition(bank=bank, train_raw=inputs["train_raw"]),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "leg_minimum_platform": physical.leg_minimum_platform(**platform),
    }
    names = physical.input_names(adapter)
    gates = [
        *cdm.gates_for(definition),
        *([cooling_physics.GATE] if "physics" in definition else []),
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
        "limits": json.loads(inputs["limits_raw"]),
        "objective": json.loads(inputs["objective_raw"]),
        "train_raw": inputs["train_raw"],
        "names": names,
    }
    return adapter, kwargs, recorder, bank


def test_the_minimums_are_what_measure_pool_returns_for_the_baseline_over_every_exam_row(
    scene,
):
    adapter, kwargs, recorder, bank = scene
    applied = adapter.applied_pack(**kwargs)
    (call,) = recorder.calls  # one grade of the baseline, through the miners' function
    rows = kwargs["bank_rows"]
    assert len(call["outputs"]) == len(call["bank_rows"]) == len(rows)
    assert any(
        r.get("cohort") == pool_version.POOL_COHORT for r in call["bank_rows"]
    )  # the pool rows too
    assert call["repeats"] == [call["outputs"], call["outputs"]]
    assert call["a_multiplier"] == 3.0  # the version's own registered multiplier
    assert len(call["speed_call_seconds"]) == pool_exam.SPEED_SAMPLE
    assert all(s > 0 and math.isfinite(s) for s in call["speed_call_seconds"])
    assert call["input_dtype"] == "<f8" and call["capture"] is None
    expected = recorder(
        **{**call, "bank_rows": call["bank_rows"]}
    )  # the stand-in is deterministic: the same answers, the same legs
    assert applied["legs"]["A"]["minimum"] == pytest.approx(expected["A"], abs=1e-15)
    assert applied["legs"]["D"]["minimum"] == pytest.approx(expected["D"], abs=1e-15)
    assert applied["hard_gates"][-2:] == [pool_exam.PHYSICS_GATE, pool_exam.SPEED_GATE]
    # 1.6's own measurement of its baseline (the old metric) gives other minimums: that was the mismatch
    old = hotspot.sealed_adapter("1.6")
    old.bank = bank
    assert (
        old.applied_pack(**kwargs)["legs"]["A"]["minimum"]
        != applied["legs"]["A"]["minimum"]
    )


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
    assert graded(a, d)["status"] == "SCORED_DEVELOPMENT_CANDIDATE"  # equality passes
    assert graded(math.nextafter(a, 0.0), d)["status"] == "REQUIRED_LEG_MINIMUM_FAILED"
    assert graded(a, math.nextafter(d, 0.0))["status"] == "REQUIRED_LEG_MINIMUM_FAILED"


def test_a_baseline_that_fails_a_gate_or_a_missing_pool_sets_no_minimums(scene):
    adapter, kwargs, recorder, _unused = scene
    recorder.fail = (pool_exam.PHYSICS_GATE,)
    with pytest.raises(cdm.CoolingMeasurementRefused, match="fails:.*physics"):
        adapter.applied_pack(**kwargs)
    recorder.fail = ()
    adapter.bank = None
    with pytest.raises(
        cdm.CoolingMeasurementRefused, match="cooling_pool_material_missing"
    ):
        adapter.applied_pack(**kwargs)


def test_the_baseline_answers_in_the_encoded_space_of_the_same_model_as_1_6(scene):
    _adapter, kwargs, _recorder, _unused = scene
    outputs, seconds = seventeen.pool_baseline(
        bank_rows=kwargs["bank_rows"], names=kwargs["names"], sample_count=20
    )
    assert len(outputs) == len(kwargs["bank_rows"]) and all(
        len(r) == 32 for r in outputs
    )
    from carbon.scoring import cooling_dual_pack as cooling
    from carbon.scoring import cooling_encoded_dual_pack as encoded

    native = cooling._baseline_outputs(
        kwargs["bank_rows"],
        cooling._train_records(encoded._native_train(), kwargs["names"]),
    )
    for row, expected in zip(outputs[:6], native[:6], strict=True):
        assert decode_flat(row) == pytest.approx(
            expected, rel=1e-5
        )  # the same fit, encoded as a miner's are
    assert len(seconds) == 20 and all(s > 0 for s in seconds)


def _sha(path):
    raw = (
        (REPOSITORY / "carbon" / "scoring" / path).read_bytes().replace(b"\r\n", b"\n")
    )
    return hashlib.sha256(raw).hexdigest()


def test_cooling_1_6_is_byte_identical_modules_and_pack(scene):
    _adapter, kwargs, _recorder, bank = scene
    for name, pinned in PINNED_16.items():
        assert _sha(name) == pinned, name
    old = hotspot.sealed_adapter("1.6")
    old.bank = bank
    body = json.dumps(old.applied_pack(**kwargs), sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(body.encode()).hexdigest() == PINNED_16_PACK
    assert not hasattr(hotspot.sealed_adapter("1.6"), "IN_PACK_BASELINE")
    assert (
        seventeen.sealed_adapter("1.6") is None
        and hotspot.sealed_adapter("1.7") is None
    )


PINNED_16_PACK = "16ea3ed6ecafa926e848c27ab0fd8901a46821ba82e61098dbf9240028151203"


# --- the calibration build ---------------------------------------------------------------------------------------------


def _toy_grading(recorder, monkeypatch):
    """Make the stand-in measure_pool grade two toy targets with the real grader, so the calibration sees real per-target e."""
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
    assert len(report["e_list_sha256"]) == 64
    # a build that is not calibrating records nothing
    other = seventeen.sealed_adapter("1.7")
    other.bank = adapter.bank
    other.applied_pack(**kwargs)
    assert other.calibration is None


def test_the_error_recorder_restores_the_grader_and_the_report_refuses_unusable_errors():
    from carbon.scoring import pool_grader

    real = pool_grader.grade_set
    with seventeen._recording_target_errors([]):
        assert pool_grader.grade_set is not real
    assert pool_grader.grade_set is real
    for bad in ([], [float("inf")], [float("nan")], [1]):
        with pytest.raises(cdm.CoolingMeasurementRefused, match="calibration_errors"):
            seventeen.calibration_report(bad)
    assert seventeen.calibration_report([2.0, 4.0, 3.0])["median_e"] == 3.0


def test_an_unregistered_s_h_reads_as_the_placeholder_only_while_calibrating(tmp_path):
    document = json.loads(pool_version.CONSTANTS.read_bytes())
    entry = json.loads(json.dumps(document["versions"]["chip-cold-plate 1.6"]))
    entry["honesty"]["scale"] = pool_version.HUMAN_INPUT
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps({**document, "versions": {"chip-cold-plate 1.7": entry}})
    )
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies("chip-cold-plate", "1.7", path=path)
    with seventeen._calibration_policies():
        policies = pool_version.registered_policies("chip-cold-plate", "1.7", path=path)
        assert policies.honesty.scale == seventeen.CALIBRATION_PLACEHOLDER_S_H
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version.registered_policies("chip-cold-plate", "1.7", path=path)
    # any OTHER unregistered constant still refuses, calibrating or not
    entry["optimizer"]["budget"] = pool_version.HUMAN_INPUT
    path.write_text(
        json.dumps({**document, "versions": {"chip-cold-plate 1.7": entry}})
    )
    with (
        seventeen._calibration_policies(),
        pytest.raises(pool_version.PoolConstantsNotRegistered),
    ):
        pool_version.registered_policies("chip-cold-plate", "1.7", path=path)


# --- 1.7's own producer identity -------------------------------------------------------------------------------------


def test_1_7s_producer_identity_covers_its_module_and_routing_and_1_3_to_1_6_are_unmoved(
    tmp_path, monkeypatch
):
    import shutil

    from carbon.scoring import (
        cooling_dual_pack,
        cooling_encoded_dual_pack,
    )

    new = {"cooling_pool_baseline_dual_pack.py", "physical_adapters.py"}
    assert new <= set(seventeen.FILES)
    for older in (cooling_dual_pack, cooling_encoded_dual_pack, hotspot):
        assert not (
            new & set(older.FILES)
        ), older.__name__  # 1.3-1.6 never name the new files
    scoring = Path(physical.__file__).parent
    names = sorted(
        {*physical._SHARED_FILES, *seventeen.FILES, *hotspot.FILES, *encoded_files()}
    )

    def digests(root):
        monkeypatch.setattr(physical, "__file__", str(root / "physical_dual_pack.py"))
        return {
            "1.7": physical.producer_digest(seventeen),
            "1.6": physical.producer_digest(hotspot),
            "1.5": physical.producer_digest(cooling_encoded_dual_pack),
            "1.0": physical.producer_digest(cooling_dual_pack),
        }

    base = tmp_path / "base"
    base.mkdir()
    for name in names:
        shutil.copy(scoring / name, base / name)
    reference = digests(base)
    assert len(set(reference.values())) == 4
    for touched in sorted(new):
        copy = tmp_path / touched.replace(".py", "")
        shutil.copytree(base, copy)
        (copy / touched).write_bytes((copy / touched).read_bytes() + b"\n# changed\n")
        moved = digests(copy)
        assert moved["1.7"] != reference["1.7"], touched  # 1.7 moves with either file
        assert {k: v for k, v in moved.items() if k != "1.7"} == {
            k: v for k, v in reference.items() if k != "1.7"
        }  # 1.0-1.6 are byte-identical


def encoded_files():
    from carbon.scoring import cooling_dual_pack, cooling_encoded_dual_pack

    return (*cooling_encoded_dual_pack.FILES, *cooling_dual_pack.FILES)


def test_cooling_1_7_is_routed_to_its_own_module_by_the_development_selector():
    from carbon.scoring import physical_adapters

    chosen = physical_adapters._static()["chip-cold-plate"]
    assert chosen("1.7") is seventeen
    assert chosen("1.6") is not seventeen
