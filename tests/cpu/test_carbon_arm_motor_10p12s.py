"""MODEL-PREDICTIONS-FOR-EVIDENCE-01: the motor 10p/12s kit, on a synthetic
sidecar. Its step-skew reduction is the registered observer's; its TRAIN never
includes a panel design; a row outside TRAIN's support abstains."""

from __future__ import annotations

import json

import numpy as np
import pytest

from carbon.development_comparison import carbon_arm as arm
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import motor_10p12s_kit as mk

QUICK = {"steps": 300, "width": 32, "depth": 2}
GRID = list(np.arange(48) * 0.25)


def toy_curve(design, j, gamma, samples=48):
    """A smooth synthetic curve (never solver output)."""
    theta = np.arange(samples) * (12.0 / samples)
    m = design["magnet_mm"]
    return list(
        j * m * np.cos(np.radians(gamma)) / 4
        + 0.05 * m * np.sin(np.radians(30 * theta))
        + 0.01 * j * np.sin(np.radians(60 * theta + gamma))
    )


def grammar(i):
    return {
        "magnet_mm": 2.0 + 0.1 * i,
        "coverage": 0.7 + 0.01 * i,
        "airgap_mm": 0.4 + 0.02 * i,
        "tooth_frac": 0.3 + 0.005 * i,
        "opening_frac": 0.05 + 0.002 * i,
        "slot_bottom_mm": 39.0 + 0.1 * i,
    }


def sidecar(study=6, panel=2):
    designs = {}
    for i in range(study + panel):
        # Panel design 0 inside the study designs' range, design 1 beyond it.
        g = grammar(i if i < study else (1.5, 9.0)[i - study])
        tags = [f"s1-d{i - study:02d}"] if i >= study else [f"pkr-r{i:02d}"]
        cases = []
        for j, gamma in [(0.0, 0.0)] + [(10.0, x) for x in (-10, -5, 0, 5, 10)]:
            samples = 96 if (i, j, gamma) == (0, 10.0, 0) else 48
            cases.append(
                {
                    "case_id": f"c{i}-{j}-{gamma}",
                    "j_a_mm2": j,
                    "gamma_deg": gamma,
                    "status": "OK" if (i, gamma) != (1, 5) else "REFERENCE_INVALID",
                    "angle_deg": list(np.arange(samples) * (12.0 / samples)),
                    "torque_nm": toy_curve(g, j, gamma, samples),
                }
            )
        designs[f"design{i}"] = {"tags": tags, "grammar": g, "cases": cases}
    return json.dumps(
        {"schema": mk.SIDECAR_SCHEMA, "designs": designs, "mapping": "", "skew": ""}
    ).encode()


def row(design, skew, condition="J10-g0"):
    return {
        "band": None,
        "candidate": f"d{design:02d}-skew{skew}",
        "condition": condition,
        "action": {"design": design, "skew_deg": skew},
        "values": {q: 0.0 for q in mk.OBSERVABLES},
    }


def test_train_holds_only_study_designs_on_the_48_sample_grid():
    data = sidecar()
    records = [
        json.loads(line) for line in data and mk.train_from_sidecar(data).splitlines()
    ]
    assert {r["case_id"].split(":")[0] for r in records} == {
        f"design{i}" for i in range(6)
    }
    assert len(records) == 6 * 6 - 1  # one case is not OK
    assert all(len(r["outputs"]) == 48 for r in records)
    assert all(r["source"] == mk.STUDY_SOURCE for r in records)
    [wide] = [r for r in records if r["case_id"] == "design0:c0-10.0-0"]
    expected = toy_curve(grammar(0), 10.0, 0, 96)[::2]
    assert [wide["outputs"][o] for o in mk.OUTPUTS] == pytest.approx(expected)


def test_the_step_skew_queries_and_reduction_follow_the_registered_observer():
    kit = mk.kit_from_bytes(sidecar())
    r = row(0, 4)
    queries = kit.row_queries(r)
    assert [q["gamma_deg"] for q in queries] == [10.0, 0.0, -10.0, 0.0]
    assert [q["j_a_mm2"] for q in queries] == [10.0, 10.0, 10.0, 0.0]
    assert {k: queries[0][k] for k in mk.GRAMMAR} == grammar(1.5)
    curves = [
        {o: float(v) for o, v in zip(mk.OUTPUTS, np.arange(48.0) * (k + 1))}
        for k in range(4)
    ]
    loaded = np.mean(
        [np.roll(np.arange(48.0) * (k + 1), -s) for k, s in zip(range(3), (-8, 0, 8))],
        0,
    )
    cogging = np.mean([np.roll(np.arange(48.0) * 4, -s) for s in (-8, 0, 8)], 0)
    assert kit.row_values(r, curves) == cb.curve_observables(loaded, cogging)


def test_a_skew_off_the_sample_grid_or_an_unknown_design_is_refused():
    kit = mk.kit_from_bytes(sidecar())
    curves = [{o: 1.0 + i for i, o in enumerate(mk.OUTPUTS)}] * 4
    with pytest.raises(arm.ArmRefused) as off_grid:
        kit.row_values(row(0, 0.3), curves)
    assert off_grid.value.code == "SKEW_NOT_ON_THE_SAMPLE_GRID"
    with pytest.raises(arm.ArmRefused) as unknown:
        kit.row_queries(row(7, 0))
    assert unknown.value.code == "PANEL_DESIGN_UNKNOWN"
    with pytest.raises(arm.ArmRefused) as unreadable:
        kit.row_queries(row(0, 0, condition="loaded"))
    assert unreadable.value.code == "CONDITION_UNREADABLE"


def test_the_arm_predicts_supported_rows_and_abstains_outside(monkeypatch):
    data = sidecar()
    kit = mk.kit_from_bytes(data)
    body = mk.train_from_sidecar(data)
    train = arm.load_train(kit, body, arm.sha256(body))
    # Panel design 0 sits inside the study designs' range; design 1 does not.
    rows = [row(0, 0), row(0, 2), row(1, 0)]
    monkeypatch.setattr(cb, "_physical_rows", lambda export: rows)
    export = {"family": "motor", "export_digest": "sha256:" + "1" * 64}
    predictions, receipt = arm.run(
        kit, export, train, scope="PUBLIC_DEVELOPMENT", settings=QUICK
    )
    values = [r["values"] for r in predictions["rows"]]
    assert values[2] is None and receipt["abstained"] == 1
    assert all(set(v) == set(mk.OBSERVABLES) for v in values[:2])
    assert receipt["cost"]["inference"]["model_queries"] == 12
    assert receipt["train"]["sources"] == [mk.STUDY_SOURCE]


def test_the_command_needs_the_pinned_sidecar(tmp_path, capsys):
    data = sidecar()
    (tmp_path / "sidecar.json").write_bytes(data)
    out = tmp_path / "train.jsonl"
    argv = ["--sidecar", str(tmp_path / "sidecar.json"), "--out", str(out)]
    assert mk.main([*argv, "--sidecar-sha256", "sha256:" + "0" * 64]) == 2
    assert not out.exists()
    assert mk.main([*argv, "--sidecar-sha256", arm.sha256(data)]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["sha256"] == arm.sha256(
        out.read_bytes()
    )
    with pytest.raises(arm.ArmRefused):
        mk.kit_from_bytes(None)
