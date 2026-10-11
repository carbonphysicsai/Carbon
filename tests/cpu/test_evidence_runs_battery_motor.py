"""EVIDENCE-ENTRYPOINTS-01, battery v3 and motor 10p/12s: committed plans
bound by sha256, image pins, and the kits' TRAIN formats."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.dev.evidence_runs import battery_v3, common, motor_10p12s

ROOT = Path(__file__).resolve().parents[2]
PHASES = ("cc1", "cc2", "cv", "rest_after_charge", "discharge", "rest_after_discharge")


@pytest.mark.parametrize("module", [battery_v3, motor_10p12s])
def test_registered_plans_are_committed_with_their_sha256(module):
    for path, sha in module.PLANS.values():
        assert common.require_plan(path, sha).exists()


def test_a_changed_plan_is_refused(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"jobs": []}))
    with pytest.raises(common.Refused) as refused:
        common.require_plan(plan, "0" * 64)
    assert refused.value.code == "PLAN_SHA256_MISMATCH"


@pytest.mark.parametrize("module", [battery_v3, motor_10p12s])
def test_check_refuses_an_absent_or_different_image(module):
    absent = lambda ref: subprocess.CompletedProcess([], 1, "", "no such image")
    with pytest.raises(common.Refused) as refused:
        module.check(next(iter(module.PLANS)), inspect=absent)
    assert refused.value.code == "IMAGE_ABSENT"
    other = json.dumps([{"Id": "sha256:" + "1" * 64, "RepoDigests": []}])
    with pytest.raises(common.Refused) as refused:
        module.check(
            next(iter(module.PLANS)),
            inspect=lambda ref: subprocess.CompletedProcess([], 0, other, ""),
        )
    assert refused.value.code == "IMAGE_DIGEST_MISMATCH"


def _battery_record(i):
    phase = {"t_max_c": 30.0 + i, "plating_min_v": 0.01}
    return {
        "schema": "carbon.battery.feasibility02-record.v1", "case_id": f"v3train:case{i}", "status": "OK",
        "c1": 1.0 + 0.1 * i, "c2": 0.5, "switch_voltage_v": 4.05, "h_multiplier": 2.0, "t_amb_c": 25.0, "soc0": 0.2,
        "per_cycle": [{"phases": {p: dict(phase) for p in PHASES}} for _ in range(2)],
        "initial_rest": {"t_max_c": 25.0}, "whole_programme": {"v_max_v": 4.2, "t_max_c": 31.0 + i},
        "q30_over_q1": 0.995, "soc_clock": {"status": "REACHED", "minutes": 40.0 - i},
    }  # fmt: skip


def test_battery_train_records_load_in_the_battery_kit():
    arm = pytest.importorskip("carbon.development_comparison.carbon_arm")
    kit = pytest.importorskip("carbon.development_comparison.battery_v3_kit").KIT
    rows = [battery_v3.train_record(_battery_record(i)) for i in range(4)]
    assert rows[0]["inputs"]["cooling"] == 2 and rows[0]["inputs"]["switch_v"] == 4.05
    data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    assert len(arm.load_train(kit, data, arm.sha256(data)).records) == 4


def test_battery_non_ok_records_are_not_exported():
    assert (
        battery_v3.train_record({**_battery_record(0), "status": "FAILED_INFRA"})
        is None
    )


def _motor_record(i, samples=48):
    design = {"magnet_mm": 3.0, "coverage": 0.9, "airgap_mm": 0.4, "tooth_frac": 0.35, "opening_frac": 0.05,
              "slot_bottom_mm": 41.0 + 0.1 * i}  # fmt: skip
    curve = [6.0 + 0.1 * ((k + i) % 7) for k in range(samples)]
    return {"case_id": f"mtrain-t{i:03d}-j10g0", "status": "OK", "design": design, "j_a_mm2": 10.0, "gamma_deg": 0.0,
            "outputs": {"torque_nm": curve}}  # fmt: skip


def test_motor_train_record_shape_and_grid():
    row = motor_10p12s.train_record(_motor_record(0))
    assert set(row["inputs"]) == {*motor_10p12s.GRAMMAR, "j_a_mm2", "gamma_deg"}
    assert list(row["outputs"]) == [f"t{k:02d}" for k in range(48)]
    rung2 = motor_10p12s.train_record(_motor_record(0, samples=96))
    assert (
        rung2["outputs"]["t01"]
        == _motor_record(0, samples=96)["outputs"]["torque_nm"][2]
    )
    assert motor_10p12s.train_record(_motor_record(0, samples=50)) is None


def test_motor_train_records_load_in_the_motor_kit():
    arm = pytest.importorskip("carbon.development_comparison.carbon_arm")
    mk = pytest.importorskip("carbon.development_comparison.motor_10p12s_kit")
    rows = [motor_10p12s.train_record(_motor_record(i)) for i in range(4)]
    data = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    kit = mk.kit({0: {k: v for k, v in _motor_record(0)["design"].items()}})
    assert len(arm.load_train(kit, data, arm.sha256(data)).records) == 4
