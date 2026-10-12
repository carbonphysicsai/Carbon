"""Public-only screening and provenance regressions; no solver or model training."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import physics_contract as pc
from scripts.dev.battery import physics_calibration as calibration
from scripts.dev.battery import physics_screen as screen

ROOT = Path(__file__).resolve().parents[2]


def contract():
    return pc.load(ROOT / "carbon/battery/physics_contract.v1.json")


def prediction(ambient=25, dip=0):
    return {
        "voltage_v": [3.6] * 121,
        "temperature_c": [ambient] + [ambient - dip] * 120,
        "plating_margin_v": 0.01,
        "capacity_ah": [5.0, 4.9, 4.8, 4.7],
    }


def fixture_panel():
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    names = ["good1", "good2", "neutral", "control-bad"]
    return {
        "store": SimpleNamespace(
            refs={
                "public-fixture": {
                    "status": "OK",
                    "inputs": inputs,
                    "outputs": prediction(),
                }
            }
        ),
        "ids": ["public-fixture"],
        "names": names,
        "predictions": {
            m: {
                "public-fixture": prediction(
                    dip=2 if m in ("good1", "control-bad") else 0
                )
            }
            for m in names
        },
        "values": dict(zip(names, [0.1, 0.2, 0.9, 1.0])),
    }


@pytest.fixture
def simple_screen(monkeypatch):
    monkeypatch.setattr(screen, "_ocv", lambda: lambda soc: 3.6)
    monkeypatch.setattr(screen, "_taus", lambda panel, names: {"A": len(names) / 10})


def test_uncalibrated_pair_diagnostics_never_become_reference_tolerances(simple_screen):
    result = screen.screen(
        fixture_panel(),
        {"known_bad": ["control-bad"]},
        contract(),
        pair_residuals={"B5a": {"good1": [0], "good2": [0], "control-bad": [1]}},
    )
    law = result["laws"]["B5a"]
    assert law["calibration"].startswith("UNRESOLVED")
    assert law["reference_points"] == 0 and law["gate_state"] == "UNRESOLVED"
    assert law["screen"][0]["false_rejection"] == "0/2"
    assert law["screen"][0]["catch"] == "1/1"
    assert law["screen"][0]["reference_quantile"] is None
    assert result["registered_margin"] == "HUMAN_INPUT"
    text = screen.markdown(result)
    assert "UNRESOLVED" in text and "B5a" in text and "Tau before / after" in text


def test_reference_pair_residuals_and_role_coverage_are_reported(simple_screen):
    result = screen.screen(
        fixture_panel(),
        {"known_bad": ["control-bad"], "adversarial": ["absent"]},
        contract(),
        pair_residuals={"B5a": {"good1": [0], "good2": [0], "control-bad": [1]}},
        reference_pairs={"B5a": {"residuals": [0.2, 0.4], "unresolved": 0}},
        provenance={"fixture": True},
    )
    law = result["laws"]["B5a"]
    row = next(
        r
        for r in law["screen"]
        if r["reference_quantile"] == 1 and r["max_violation_rate"] == 0
    )
    assert row["tolerance"] == 0.4 and row["reference_violation_rate"] == 0
    assert row["catch_by_role"]["adversarial"] == {
        "caught": 0,
        "resolved": 0,
        "unresolved": 1,
    }
    assert law["gate_state"] == "UNRESOLVED"


def test_b9_diagnosis_is_paired_raw_data_not_a_tolerance_artefact(simple_screen):
    result = screen.screen(fixture_panel(), {"known_bad": ["control-bad"]}, contract())
    diagnosis = result["b9_diagnosis"]
    assert diagnosis["good_members_with_excess_subambient_predictions"] == 1
    assert diagnosis["member_case_comparisons"] == 2
    assert diagnosis["predicted_deficit_c"]["max"] == 2
    assert diagnosis["reference_deficit_c"]["max"] == 0
    assert diagnosis["excess_over_reference_c"]["max"] == 2
    assert diagnosis["descriptive_tail_counts"]["0.1"]["good_members_above"] == 1


def test_missing_member_predictions_never_count_as_gate_passes(simple_screen):
    panel = fixture_panel()
    panel["predictions"]["good2"] = {}
    result = screen.screen(panel, {"known_bad": ["control-bad"]}, contract())
    assert result["laws"]["B2"]["unresolved_members"] == ["good2"]
    assert result["laws"]["B2"]["screen"][0]["false_rejection"] == "0/1"


def write_panel(tmp_path):
    inputs = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}
    records = {}
    for cid, p in [("base", inputs), ("partner", {**inputs, "c1": 1.075})]:
        body = json.dumps(
            {"case_id": cid, "status": "OK", "inputs": p, "outputs": prediction()}
        ).encode()
        name = cid + ".json"
        (tmp_path / name).write_bytes(body)
        records[name] = hashlib.sha256(body).hexdigest()
    plan_body = json.dumps(
        {
            "pairs": [
                {
                    "law_id": "B5a",
                    "along": "c1",
                    "base_id": "base",
                    "partner_id": "partner",
                }
            ]
        }
    ).encode()
    (tmp_path / "plan.json").write_bytes(plan_body)
    manifest = {
        "visibility": "PUBLIC",
        "image_digest": calibration.IMAGE,
        "overlay_lock_sha256": hashlib.sha256(
            (ROOT / calibration.OVERLAY).read_bytes()
        ).hexdigest(),
        "plan_sha256": hashlib.sha256(plan_body).hexdigest(),
        "records": records,
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    return manifest


def test_manifest_hashes_image_overlay_plan_and_every_record(tmp_path):
    write_panel(tmp_path)
    readings, provenance = calibration.load_directory(
        tmp_path, contract(), repository=ROOT
    )
    assert readings["B5a"] == {"residuals": [0.0], "unresolved": 0}
    assert not readings["B10"]["residuals"]
    assert provenance["records"] == 2 and provenance["pairs"] == 1
    (tmp_path / "partner.json").write_text("{}")
    with pytest.raises(calibration.CalibrationRefused, match="record_hash"):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("image_digest", "sha256:other", "reference_image"),
        ("overlay_lock_sha256", "wrong", "overlay_hash"),
        ("plan_sha256", "wrong", "plan_hash"),
        ("visibility", "SEALED", "not_public"),
    ],
)
def test_manifest_mismatch_is_refused_before_using_references(
    tmp_path, field, value, reason
):
    manifest = write_panel(tmp_path)
    manifest[field] = value
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    with pytest.raises(calibration.CalibrationRefused, match=reason):
        calibration.load_directory(tmp_path, contract(), repository=ROOT)


def test_outside_range_and_reference_failures_are_unresolved():
    base = {"status": "REFERENCE_SOLVER_FAILED"}
    readings = calibration.readings(
        {"pairs": [{"law_id": "B5a", "base": base, "partner": base}]}, contract()
    )
    assert readings["B5a"] == {"residuals": [], "unresolved": 1}


def test_pair_geometry_cannot_calibrate_a_different_law_step():
    base = {
        "status": "OK",
        "inputs": {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2},
        "outputs": prediction(),
    }
    partner = copy.deepcopy(base)
    partner["inputs"]["c1"] += 0.15
    with pytest.raises(calibration.CalibrationRefused, match="pair_step"):
        calibration.readings(
            {
                "pairs": [
                    {"law_id": "B5a", "along": "c1", "base": base, "partner": partner}
                ]
            },
            contract(),
        )


def test_data_collection_jsonl_plan_and_per_record_hashes(tmp_path):
    manifest = write_panel(tmp_path)
    records = [
        json.loads((tmp_path / name).read_bytes())
        for name in ("base.json", "partner.json")
    ]
    lines = [json.dumps(r, sort_keys=True).encode() for r in records]
    (tmp_path / "records.jsonl").write_bytes(b"\n".join(lines) + b"\n")
    manifest["record_sha256"] = {
        r["case_id"]: hashlib.sha256(line).hexdigest()
        for r, line in zip(records, lines)
    }
    del manifest["records"]
    jobs = [{"case_id": r["case_id"], **r["inputs"]} for r in records]
    jobs_body = json.dumps({"jobs": jobs}).encode()
    (tmp_path / "jobs.json").write_bytes(jobs_body)
    plan = {
        "schema": "carbon.battery.physics-calibration-plan.v1",
        "scope": "PUBLIC_DEVELOPMENT synthetic",
        "contract": {"probe_region": contract()["probe_region"]},
        "jobs_sha256": hashlib.sha256(jobs_body).hexdigest(),
        "pairs": [
            {
                "base": "base",
                "partner": "partner",
                "input": "c1",
                "step": 0.075,
                "step_fraction": 0.05,
                "laws": ["B5a", "B6"],
            }
        ],
    }
    plan_body = json.dumps(plan).encode()
    (tmp_path / "plan.json").write_bytes(plan_body)
    manifest["plan_sha256"] = hashlib.sha256(plan_body).hexdigest()
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    readings, provenance = calibration.load_directory(
        tmp_path, contract(), repository=ROOT
    )
    assert readings["B5a"]["residuals"] == [0] and readings["B6"]["residuals"] == [0]
    assert provenance["pairs"] == 2
    plan_loaded, public_jobs, identity = calibration.public_plan(tmp_path, contract())
    assert (
        plan_loaded == plan
        and public_jobs == jobs
        and identity == manifest["plan_sha256"]
    )
