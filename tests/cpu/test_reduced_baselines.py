"""Synthetic reduced algebra, source custody and whole-geometry holdouts only."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from carbon.design_search import producer_panels, tasks
from carbon.development_comparison import reduced_baselines as rb

ROOT = Path(__file__).resolve().parents[2]


def identity_fixture():
    spec = importlib.util.spec_from_file_location(
        "portfolio_fixture", ROOT / "tests/cpu/test_portfolio_baselines.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fixture("cooling-cell")[0]


def structural_witness(model, query):
    # Independent two-DOF closed-form inverse, not comparator replay.
    k, m, c = (np.asarray(model[name]) for name in ("K", "M", "C"))
    output = []
    for omega in 2 * np.pi * np.asarray(query["frequency_hz"]):
        a, d = (
            k[0, 0] - omega**2 * m[0, 0] + 1j * omega * c[0, 0],
            k[1, 1] - omega**2 * m[1, 1] + 1j * omega * c[1, 1],
        )
        b = k[0, 1]
        output.append(
            [(d - 0.2 * b) / (a * d - b * b), (0.2 * a - b) / (a * d - b * b)]
        )
    static = [
        (k[1, 1] - 0.2 * k[0, 1]) / np.linalg.det(k),
        (0.2 * k[0, 0] - k[0, 1]) / np.linalg.det(k),
    ]
    output = np.asarray(output)
    return {
        "response_real": output.real.tolist(),
        "response_imag": output.imag.tolist(),
        "static_m_per_n": static,
    }


def fixture(family):
    export = identity_fixture()
    export.pop("export_digest")
    export["family"] = family
    reducers = (
        [
            {"quantity": "metric", "unit": "mm/N", "kind": "dynamic_peak"},
            {"quantity": "safety", "unit": "mm/N", "kind": "static_peak"},
        ]
        if family == "f08"
        else [
            {"quantity": "metric", "unit": "dB", "kind": "interval_p10_tl_db"},
            {"quantity": "safety", "unit": "dB", "kind": "minimum_tl_db"},
        ]
    )
    old = export["questions"][0]["task"]
    task = tasks.task(
        old.get("name", "synthetic-question"),
        identity=old["identity"],
        conditions=old["conditions"],
        strata=old["strata"],
        candidates=old["candidates"],
        actions=old["actions"],
        objective={**old["objective"], "unit": reducers[0]["unit"]},
        limits=[
            {
                **old["limits"][0],
                "unit": reducers[1]["unit"],
                "value": 9 if family == "f08" else 20,
            }
        ],
    )
    rows = []
    for i, candidate in enumerate(task["candidates"]):
        if family == "f08":
            model = {
                "K": [[100 + 10 * i, 3], [3, 190 - 5 * i]],
                "M": [[1, 0], [0, 1]],
                "C": [[0.4, 0], [0, 0.6]],
                "B": [[1], [0.2]],
                "L": [[1, 0], [0, 1]],
            }
            query = {"frequency_hz": [0.5, 1.2, 1.8], "input_scalars": {}}
            witness = structural_witness(model, query)
        else:
            model = {
                "K": [[4 + i, 0.4], [0.4, 6 + 0.1 * i]],
                "M": [[0.01, 0], [0, 0.02]],
                "C": [[0.1, 0], [0, 0.1]],
                "ports": [[1, 0.5, 0.4, 0.1], [0.1, 0.3, 1, 0.5]],
                "cutoff_m_inv": [0, 5, 0, 5],
                "port_sides": ["inlet", "inlet", "outlet", "outlet"],
                "rho_kg_m3": 1,
                "sound_speed_m_s": 3,
            }
            query = {
                "frequency_hz": [1, 2, 3],
                "incident_real": [[1, 0, 0, 0]] * 3,
                "incident_imag": [[0, 0, 0, 0]] * 3,
                "mean_flow_m_s": 0,
                "input_scalars": {},
            }
            witness = rb.acoustic_curve(model, query)[0]
        rows.append(
            {
                "candidate": candidate,
                "condition": "context",
                "coordinates": [i],
                "context_sha256": "0" * 64,
                "basis_sha256": "1" * 64,
                "basis_source_sha256": "4" * 64,
                "basis_training_coordinates": [],
                "observer_version": "synthetic-observer-v1",
                "calibration_source_sha256": "2" * 64,
                "query_source_sha256": "3" * 64,
                "witness_source_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                "model": model,
                "query": query,
                "witness": witness,
            }
        )
    export["questions"][0]["task"] = task
    export["questions"][0]["reference"] = [
        {
            "candidate": row["candidate"],
            "condition": "context",
            "values": rb.reduce_observables(
                family, row["query"], row["witness"], reducers
            ),
        }
        for row in rows
    ]
    export = producer_panels.seal_export(export)
    operators = rb.seal_operators(
        {
            "schema": rb.SCHEMA,
            "family": family,
            "scope": "SYNTHETIC_FIXTURE",
            "export_digest": export["export_digest"],
            "coordinate_fields": ["coordinate"],
            "reducers": reducers,
            "rows": rows,
            "costs": dict.fromkeys(rb.COST_FIELDS),
        }
    )
    return export, operators


@pytest.mark.parametrize("family", ["f08", "f13"])
def test_whole_geometry_holdout_reports_abstention_and_equal_budget(family):
    export, operators = fixture(family)
    report = rb.measure(export, operators=operators)
    assert report["held_out"]["pointwise"]["predicted_rows"] == 3
    assert report["held_out"]["pointwise"]["abstained_rows"] == 2
    assert report["held_out"]["curve_errors"]["samples"] > 0
    assert all(
        not f["held_geometry_operators_used"] for f in report["held_out"]["folds"]
    )
    assert report["reference_solves_launched"] == 0
    assert not any(report["claims"].values())
    assert report["v4_disposition"] == "UNRESOLVED_NO_MATCHED_CARBON_ARM"
    assert all(c["status"] == "NOT_MEASURED" for c in report["costs"].values())
    screen = report["equal_budget_screening"]
    assert screen["schema"] == "carbon.development-cheap-screen.v1"
    assert len(screen["query_rows"]) == 5
    assert screen["candidate_rankings"][0]["candidate_count"] == 5
    assert screen["query_cost"]["cpu_mean_s_per_attempted_query"] >= 0


def test_f08_interpolation_is_exact_for_affine_operators_not_target_cache():
    export, body = fixture("f08")
    before, _ = rb.predict(export, rb.validate_operators(export, body))
    model, used = rb.interpolate([body["rows"][1], body["rows"][3]], body["rows"][2])
    assert "design2" not in used
    assert np.allclose(model["K"], body["rows"][2]["model"]["K"])
    curve = rb.structural_curve(model, body["rows"][2]["query"])
    assert np.allclose(
        curve["response_real"], body["rows"][2]["witness"]["response_real"]
    )
    changed = copy.deepcopy(body)
    changed["rows"][2]["model"]["K"][0][0] *= 10
    changed = rb.seal_operators(
        {k: v for k, v in changed.items() if k != "operators_digest"}
    )
    after, _ = rb.predict(export, rb.validate_operators(export, changed))
    assert before[(None, "design2", "context")] == after[(None, "design2", "context")]


def test_acoustic_multimode_and_evanescent_influence_conserve_power():
    _, body = fixture("f13")
    row = body["rows"][2]
    full, diagnostic = rb.acoustic_curve(row["model"], row["query"])
    assert max(abs(x) for x in diagnostic["relative_power_residual"]) < 1e-12
    assert diagnostic["propagating_modes"] == [2, 2, 4]
    plane = copy.deepcopy(row["model"])
    plane["ports"] = np.asarray(plane["ports"])
    plane["ports"][:, [1, 3]] = 0
    restricted, _ = rb.acoustic_curve(plane, row["query"])
    assert not np.allclose(full["tl_db"], restricted["tl_db"])
    assert abs(full["tl_db"][0] - restricted["tl_db"][0]) > 1e-4
    invalid = copy.deepcopy(row["query"])
    invalid["incident_real"][0][1] = 1
    with pytest.raises(rb.cb.Unsupported, match="evanescent"):
        rb.acoustic_curve(row["model"], invalid)


@pytest.mark.parametrize("field", ["calibration_source_sha256", "query_source_sha256"])
def test_response_witness_cannot_become_calibration_or_query(field):
    export, body = fixture("f08")
    body["rows"][0][field] = body["rows"][1]["witness_source_sha256"]
    body = rb.seal_operators({k: v for k, v in body.items() if k != "operators_digest"})
    with pytest.raises(ValueError, match="independent"):
        rb.validate_operators(export, body)


def test_common_basis_not_a_mode_label_and_out_of_hull_abstains():
    export, body = fixture("f08")
    for i, row in enumerate(body["rows"]):
        row["basis_sha256"] = hashlib.sha256(str(i).encode()).hexdigest()
    body = rb.seal_operators({k: v for k, v in body.items() if k != "operators_digest"})
    report = rb.measure(export, operators=body)
    assert report["held_out"]["status"] == "HOLD_NO_SUPPORTED_PREDICTIONS"
    assert report["held_out"]["pointwise"]["predicted_rows"] == 0
    assert (
        rb.measure(export)["held_out"]["status"] == "HOLD_MISSING_PROJECTED_OPERATORS"
    )


def test_constructor_raw_material_and_nonphysical_operator_rejected():
    export, body = fixture("f08")
    with pytest.raises(TypeError):
        rb.Operators(json.dumps(body))
    with pytest.raises(TypeError):
        rb.predict(export, body)
    body["rows"][0]["model"]["M"][0][0] = -1
    body = rb.seal_operators({k: v for k, v in body.items() if k != "operators_digest"})
    with pytest.raises(ValueError, match="positive"):
        rb.validate_operators(export, body)


def test_basis_trained_on_held_geometry_is_not_independent():
    export, body = fixture("f08")
    for row in body["rows"]:
        row["basis_training_coordinates"] = [[2]]
    body = rb.seal_operators({k: v for k, v in body.items() if k != "operators_digest"})
    predictions, report = rb.predict(export, rb.validate_operators(export, body))
    assert (None, "design2", "context") not in predictions
    assert any(row["candidate"] == "design2" for row in report["abstention_reasons"])


def test_fluid_and_modal_layout_must_match_common_context():
    export, body = fixture("f13")
    body["rows"][0]["model"]["rho_kg_m3"] = 2
    body = rb.seal_operators({k: v for k, v in body.items() if k != "operators_digest"})
    with pytest.raises(ValueError, match="layout"):
        rb.validate_operators(export, body)


def test_multidimensional_simplex_weights_and_no_geometry_extrapolation():
    def row(x, stiffness):
        return {
            "coordinates": x,
            "basis_sha256": "1" * 64,
            "candidate": str(x),
            "model": {"K": [[stiffness]]},
        }

    peers = [row([0, 0], 1), row([1, 0], 2), row([0, 1], 3)]
    target = row([0.25, 0.25], 999)
    model, _ = rb.interpolate(peers, target)
    assert np.allclose(model["K"], [[1.75]])
    with pytest.raises(rb.cb.Unsupported):
        rb.interpolate(peers, row([2, 2], 999))


def test_cli_byte_pins_and_no_overwrite(tmp_path):
    export, body = fixture("f08")
    panel, operators, output = (
        tmp_path / name for name in ("panel.json", "operators.json", "report.json")
    )
    panel.write_text(json.dumps(export))
    operators.write_text(json.dumps(body))
    argv = [
        "--panel",
        str(panel),
        "--expected-sha256",
        hashlib.sha256(panel.read_bytes()).hexdigest(),
        "--operators",
        str(operators),
        "--operators-sha256",
        hashlib.sha256(operators.read_bytes()).hexdigest(),
        "--output",
        str(output),
    ]
    assert rb.main(argv) == 0
    assert json.loads(output.read_text())["reference_solves_launched"] == 0
    with pytest.raises(FileExistsError):
        rb.main(argv)
    argv[3] = "0" * 64
    with pytest.raises(ValueError, match="identity"):
        rb.main(argv)
