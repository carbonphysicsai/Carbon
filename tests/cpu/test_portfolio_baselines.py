"""Synthetic arithmetic and held-out custody; no acquired physical evidence."""

from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from carbon.design_search import diversity, power_accumulation, producer_panels, tasks
from carbon.development_comparison import portfolio_baselines as pb


def fixture(family, payloads=None):
    n = 5
    if payloads is None:
        payloads = [{} for _ in range(n)]
    reducers = {
        "cooling-cell": [("metric", "surface"), ("safety", "surface")],
        "f02": [("metric", "extra_energy_j"), ("safety", "temperature_max")],
        "f08": [("metric", "dynamic_peak"), ("safety", "static_max")],
        "f13": [("metric", "interval_p10_tl_db"), ("safety", "input_scalar")],
    }[family]
    units = {
        "extra_energy_j": "J",
        "temperature_max": "degC",
        "interval_p10_tl_db": "dB",
    }
    mapped = [
        {"quantity": q, "unit": units.get(kind, "synthetic"), "kind": kind}
        for q, kind in reducers
    ]
    values = []
    for i, p in enumerate(payloads):
        if family == "cooling-cell":
            values.append({"metric": float(i), "safety": float(i)})
        else:
            curve = (
                np.asarray(p["temperature_c"])
                if family == "f02"
                else pb.modal_response(p) if family == "f08" else np.asarray(p["tl_db"])
            )
            values.append(pb._reduce(family, p, curve, mapped))
    actions = {f"design{i}": {"coordinate": i} for i in range(n)}
    task = tasks.task(
        "synthetic-question",
        identity={
            "challenge": "synthetic-challenge",
            "contract_version": "fixture-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "fixture-v1",
                "variables": [
                    {
                        "name": "coordinate",
                        "type": "integer",
                        "min": 0,
                        "max": 4,
                        "step": 1,
                    }
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": n,
            "seed": 0,
            "observer_version": "synthetic-observer-v1",
            "reference_bank": "synthetic-bank",
        },
        conditions=[{"id": "context", "stratum": "only"}],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        candidates=list(actions),
        actions=actions,
        objective={
            "quantity": "metric",
            "unit": mapped[0]["unit"],
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {"quantity": "safety", "unit": mapped[1]["unit"], "op": "<=", "value": 3.5}
        ],
    )
    case = "synthetic-question"
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 1,
            "bins": [{"case": case, "q_mass": 1.0}],
            "mass_l1_error_bound": 0.0,
        }
    )
    export = producer_panels.seal_export(
        {
            "schema": producer_panels.EXPORT_SCHEMA,
            "sealed": True,
            "family": family,
            "challenge_id": "synthetic-challenge",
            "exposure_unit": "per_question_draws",
            "exposure": [{"case": case, "limit": 2, "used": 0}],
            "window_sampling": power_accumulation.register_window_sampling(
                case_strata=[{"case": case, "stratum": "only"}],
                quotas_by_k=[
                    {"questions_per_batch": k, "quotas": {"only": k}} for k in (1, 2)
                ],
            ),
            "questions": [
                {
                    "case": case,
                    "support_case": "synthetic-bank",
                    "task": task,
                    "reference": [
                        {"candidate": c, "condition": "context", "values": v}
                        for c, v in zip(actions, values)
                    ],
                    "close_call": False,
                    "refinement_demand": False,
                }
            ],
            "laws": [law],
        }
    )
    material = pb.seal_materials(
        {
            "schema": pb.SCHEMA,
            "family": family,
            "scope": "SYNTHETIC_FIXTURE",
            "export_digest": export["export_digest"],
            "observer_versions": ["synthetic-observer-v1"],
            "settings": {
                "coordinate_fields": ["coordinate"],
                "lags": 1,
                "reducers": mapped,
            },
            "rows": [
                {
                    "candidate": c,
                    "condition": "context",
                    "coordinates": [i],
                    "context_sha256": "0" * 64,
                    "reference_source_sha256": hashlib.sha256(c.encode()).hexdigest(),
                    "calibration_source_sha256": "1" * 64,
                    "payload": p,
                }
                for i, (c, p) in enumerate(zip(actions, payloads))
            ],
            "costs": dict.fromkeys(pb.COST_FIELDS),
        }
    )
    return export, material


def thermal_payloads():
    output = []
    for i in range(5):
        # Independent two-source excitation, fixed amplitudes, varying durations.
        power = np.zeros((8, 2))
        power[1 : 3 + i, 0], power[4:6, 1] = 1, 1
        base = np.full((8, 2), 1.0)
        trace = base + pb.fir_features(power, 1) @ np.asarray([[0.2, 0.3], [0.4, 0.1]])
        output.append(
            {
                "time_s": list(range(8)),
                "extra_power_w": power.tolist(),
                "baseline_temperature_c": base.tolist(),
                "temperature_c": trace.tolist(),
            }
        )
    return output


def modal_payloads():
    output = []
    for i in range(5):
        p = {
            "frequency_hz": [1, 2, 3],
            "mode_hz": [2],
            "damping_ratio": 0.05,
            "residue_real": [[i + 1]],
            "residue_imag": [[0]],
            "static_residual_real": [0],
            "static_residual_imag": [0],
            "static_compliance": [0.1],
            "input_scalars": {},
        }
        response = pb.modal_response(p)
        output.append(
            {
                **p,
                "response_real": response.real.tolist(),
                "response_imag": response.imag.tolist(),
            }
        )
    return output


def acoustic_payloads():
    output = []
    for i in range(5):
        p = {
            "frequency_hz": [500, 600, 900],
            "rho_kg_m3": 1.2,
            "sound_speed_m_s": 343,
            "port_radius_m": 0.005,
            "coaxial": True,
            "mean_flow_m_s": 0,
            "segments": [{"length_m": 0.05, "radius_m": 0.01 + i * 0.002}],
            "input_scalars": {"safety": 1},
        }
        output.append({**p, "tl_db": pb.transfer_curve(p).tolist()})
    return output


def test_cooling_holdout_boundaries_abstain_and_no_toy_v4():
    export, material = fixture("cooling-cell")
    report = pb.measure(export, material=material)
    assert report["held_out"]["pointwise"]["predicted_rows"] == 3
    assert len(report["held_out"]["folds"]) == 5
    assert report["held_out"]["pointwise"]["abstained_rows"] == 2
    assert (
        report["closed_bank"]["decision"]["summary"]["exact_pick_agreement_rate"] == 1
    )
    assert report["v4_disposition"] == "UNRESOLVED_NO_MATCHED_CARBON_ARM"
    assert all(c["status"] == "NOT_MEASURED" for c in report["costs"].values())
    assert report["reference_solves_launched"] == 0


@pytest.mark.parametrize(
    "family,maker",
    [("f02", thermal_payloads), ("f08", modal_payloads), ("f13", acoustic_payloads)],
)
def test_ready_command_methods_reproduce_synthetic_arithmetic(family, maker):
    export, material = fixture(family, maker())
    result = pb.measure(export, material=material)
    assert result["held_out"]["pointwise"]["predicted_rows"] == 5
    assert result["held_out"]["curve_errors"]["max_abs"] < 1e-10
    assert result["held_out"]["decision"]["summary"]["exact_pick_agreement_rate"] == 1
    assert result["claims"]["tested_challenge"] is False


@pytest.mark.parametrize(
    "family,maker",
    [
        ("cooling-cell", None),
        ("f02", thermal_payloads),
        ("f08", modal_payloads),
        ("f13", acoustic_payloads),
    ],
)
def test_equal_budget_screen_exports_physical_query_cost_and_rankings(family, maker):
    export, material = fixture(family, maker() if maker else None)
    report = pb.measure(export, material=material)
    screen = report["equal_budget_screening"]
    assert screen["export_digest"] == export["export_digest"]
    assert screen["materials_digest"] == material["materials_digest"]
    assert screen["status"] == "DESCRIPTIVE_HELD_OUT_NOT_EQUAL_BUDGET_RUN"
    assert len(screen["query_rows"]) == 5
    assert screen["query_cost"]["samples"] == 5
    assert screen["query_cost"]["cpu_mean_s_per_attempted_query"] >= 0
    assert screen["fold_fit_cost"]["samples"] == 5
    ranks = screen["candidate_rankings"][0]
    ranked = ranks["ranked_feasible"] + ranks["ranked_infeasible"]
    assert len(ranked) + len(ranks["unranked_abstentions"]) == 5
    assert ranks["task_digest"] == export["questions"][0]["task"]["task_digest"]
    assert all(r["feasible"] is True for r in ranks["ranked_feasible"])
    assert all(r["feasible"] is False for r in ranks["ranked_infeasible"])
    if family == "cooling-cell":
        assert [r["candidate"] for r in ranks["ranked_feasible"]] == [
            "design1",
            "design2",
            "design3",
        ]
        assert len(ranks["unranked_abstentions"]) == 2


def test_screen_ranking_never_uses_reference_truth_and_keeps_ties():
    export, _ = fixture("cooling-cell")
    predicted = {
        (None, f"design{i}", "context"): {"metric": 1, "safety": 1} for i in range(5)
    }
    result = pb.screening_export(export, predicted, [])
    assert [
        r["candidate"] for r in result["candidate_rankings"][0]["ranked_feasible"]
    ] == [f"design{i}" for i in range(5)]
    changed = copy.deepcopy(export)
    for row in changed["questions"][0]["reference"]:
        row["values"] = {"metric": 9999, "safety": 9999}
    assert (
        result["candidate_rankings"]
        == pb.screening_export(changed, predicted, [])["candidate_rankings"]
    )
    assert result["query_cost"]["cpu_mean_s_per_attempted_query"] is None


def test_failed_fit_is_not_zero_cost_query_or_feasible_rank():
    export, material = fixture("cooling-cell")
    for i, row in enumerate(material["rows"]):
        row["context_sha256"] = hashlib.sha256(str(i).encode()).hexdigest()
    material = pb.seal_materials(
        {k: v for k, v in material.items() if k != "materials_digest"}
    )
    screen = pb.measure(export, material=material)["equal_budget_screening"]
    assert screen["query_cost"]["samples"] == 0
    assert screen["query_cost"]["wall_mean_s_per_attempted_query"] is None
    assert all(r["query_cost"] is None for r in screen["query_rows"])
    assert all(r["fit_cost"] is not None for r in screen["query_rows"])
    assert len(screen["candidate_rankings"][0]["unranked_abstentions"]) == 5


def test_fir_never_uses_target_temperature_and_requires_two_sources():
    rows = thermal_payloads()
    prediction = pb.fit_impulse(rows[1:], rows[0], 1)
    rows[0]["temperature_c"] = np.full((8, 2), 999).tolist()
    np.testing.assert_allclose(prediction, pb.fit_impulse(rows[1:], rows[0], 1))
    for row in rows[1:]:
        row["extra_power_w"] = np.zeros((8, 2)).tolist()
    with pytest.raises(pb.cb.Unsupported, match="rank deficient"):
        pb.fit_impulse(rows[1:], rows[0], 1)


def test_f13_straight_pipe_and_explicit_unsupported_physics():
    p = acoustic_payloads()[0]
    p["segments"][0]["radius_m"] = p["port_radius_m"]
    np.testing.assert_allclose(pb.transfer_curve(p), 0, atol=1e-12)
    for changes in (
        {"coaxial": False},
        {"mean_flow_m_s": 1},
        {"frequency_hz": [500, 40000]},
    ):
        with pytest.raises(pb.cb.Unsupported):
            pb.transfer_curve({**p, **changes})


def test_interval_quantile_not_adaptive_sample_count():
    assert pb.interval_p10([0, 1, 2, 100], [0, 0, 10, 10]) == 10
    assert np.quantile([0, 0, 10, 10], 0.1) == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(scope="HIDDEN_EVAL"),
        lambda m: m.update(export_digest="0" * 64),
        lambda m: m["rows"][0].update(coordinates=[999]),
        lambda m: m["rows"][0].update(payload={"private_seed": 4}),
        lambda m: m["settings"]["reducers"][0].update(unit="wrong-unit"),
        lambda m: m["costs"].update(money_eur=-1),
    ],
)
def test_closed_pins_units_coordinates_and_costs(change):
    export, material = fixture("cooling-cell")
    change(material)
    material = pb.seal_materials(
        {k: v for k, v in material.items() if k != "materials_digest"}
    )
    with pytest.raises(ValueError):
        pb.measure(export, material=material)


def test_curve_observer_alignment_and_calibration_custody():
    export, material = fixture("f08", modal_payloads())
    for mutate in (
        lambda m: m["rows"][0]["payload"]["response_real"][0].__setitem__(0, 999),
        lambda m: m["rows"][0].update(
            calibration_source_sha256=m["rows"][1]["reference_source_sha256"]
        ),
    ):
        altered = copy.deepcopy(material)
        mutate(altered)
        altered = pb.seal_materials(
            {k: v for k, v in altered.items() if k != "materials_digest"}
        )
        with pytest.raises(ValueError):
            pb.measure(export, material=altered)


def test_materials_cannot_be_raw_constructed():
    export, material = fixture("cooling-cell")
    with pytest.raises(TypeError):
        pb.Materials(json.dumps(material))
    with pytest.raises(TypeError):
        pb._predict(export, material)
    assert (
        pb.measure(export)["held_out"]["status"] == "HOLD_MISSING_COMPARATOR_MATERIALS"
    )


def test_mismatched_context_never_trains_a_cooling_prediction():
    export, material = fixture("cooling-cell")
    for i, row in enumerate(material["rows"]):
        row["context_sha256"] = hashlib.sha256(str(i).encode()).hexdigest()
    material = pb.seal_materials(
        {k: v for k, v in material.items() if k != "materials_digest"}
    )
    result = pb.measure(export, material=material)
    assert result["held_out"]["status"] == "HOLD_NO_SUPPORTED_PREDICTIONS"
    assert result["held_out"]["pointwise"]["predicted_rows"] == 0
    assert len(result["held_out"]["abstention_reasons"]) == 5


def test_cli_pins_and_never_overwrites(tmp_path):
    export, material = fixture("cooling-cell")
    panel, sidecar, output = [
        tmp_path / n for n in ("panel.json", "materials.json", "report.json")
    ]
    panel.write_text(json.dumps(export), encoding="utf-8")
    sidecar.write_text(json.dumps(material), encoding="utf-8")
    args = [
        "--panel",
        str(panel),
        "--expected-sha256",
        hashlib.sha256(panel.read_bytes()).hexdigest(),
        "--materials",
        str(sidecar),
        "--materials-sha256",
        hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        "--output",
        str(output),
    ]
    assert pb.main(args) == 0
    saved = output.read_bytes()
    assert b"\r" not in saved
    report = json.loads(saved)
    assert report["environment"]["canonical"] is False
    assert report["held_out"]["fit_reduction_query_cost"]["samples"] == 5
    with pytest.raises(FileExistsError):
        pb.main(args)
    assert output.read_bytes() == saved
    args[3] = "0" * 64
    with pytest.raises(ValueError, match="byte identity"):
        pb.main(args)
