"""Tiny synthetic wiring fixture; no physical solver or actual MLP fit."""

from __future__ import annotations

import copy
import json

import numpy as np

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import motor_10p12s_kit as mk
from carbon.development_comparison import motor_pilot as mp
from carbon.development_comparison import motor_pilot_kit as pk


def geometry(i):
    return {
        "magnet_mm": 2 + 0.2 * i,
        "coverage": 0.70 + 0.02 * i,
        "airgap_mm": 0.45 + 0.02 * i,
        "tooth_frac": 0.25 + 0.02 * i,
        "opening_frac": 0.05 + 0.01 * i,
        "slot_bottom_mm": 37 + 0.5 * i,
    }


def outputs(g, j, gamma):
    # Arbitrary deterministic fixture, explicitly NOT magnetostatic truth.
    theta = np.arange(48) * 0.25
    curve = (
        j * g["magnet_mm"] * 0.35 * np.cos(np.radians(gamma))
        + 0.02 * np.sin(np.radians(30 * theta))
        + 0.001 * j * np.sin(np.radians(60 * theta + gamma))
    )
    return {o: float(v) for o, v in zip(mk.OUTPUTS, curve)}


def documents():
    scope = "SYNTHETIC_FIXTURE"
    reference = ca.sha256(b"synthetic-wiring-reference-not-evidence")
    domain = {
        "schema": "carbon.motor.pilot-domain.v1",
        "scope": scope,
        "topology": "10p12s-double-layer",
        "geometry": {str(i): geometry(i + 0.5) for i in range(2)},
        "curves": {},
    }
    for index, g in domain["geometry"].items():
        domain["curves"][index] = [
            {
                "j_a_mm2": j,
                "gamma_deg": gamma,
                "outputs": outputs(g, j, gamma),
                "source_digest": reference,
            }
            for j, gamma in pk.COMMANDS
        ]
    kit = pk.kit({int(i): g for i, g in domain["geometry"].items()})
    records = [
        {
            "schema": mk.TRAIN_SCHEMA,
            "case_id": f"fixture-{i}-{j}-{gamma}",
            "inputs": {**geometry(i), "j_a_mm2": j, "gamma_deg": gamma},
            "outputs": outputs(geometry(i), j, gamma),
            "source": "SYNTHETIC_FIXTURE",
            "fixture": True,
        }
        for i in range(3)
        for j, gamma in pk.COMMANDS
    ]
    train = ("\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n").encode(
        "utf-8"
    )
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "fixture-indexed-physical-geometry-v1",
        "variables": [
            {"name": "design", "type": "integer", "min": 0, "max": 1, "step": 1},
            {"name": "skew_deg", "type": "integer", "min": 0, "max": 4, "step": 2},
        ],
        "rules": [],
    }
    actions = {
        f"g{i}-s{s}": {"design": i, "skew_deg": s} for i in range(2) for s in (0, 2, 4)
    }
    rows = []
    for c, action in actions.items():
        row = {"candidate": c, "condition": pk.CONDITION, "action": action}
        g = domain["geometry"][str(action["design"])]
        values = kit.row_values(
            row,
            [outputs(g, q["j_a_mm2"], q["gamma_deg"]) for q in kit.row_queries(row)],
        )
        rows.append({"candidate": c, "condition": pk.CONDITION, "values": values})
    questions = []
    for i in range(2):
        case = f"fixture-question-{i}"
        limits = [
            ("holding_mean_nm", ">=", 6 + i * 0.1, "N m"),
            ("peak_mean_nm", ">=", 12 + i * 0.1, "N m"),
            ("holding_pk_pk_nm", "<=", 0.30, "N m"),
            ("peak_pk_pk_nm", "<=", 0.60, "N m"),
            ("holding_ripple_fraction", "<=", 0.05, "1"),
            ("peak_ripple_fraction", "<=", 0.05, "1"),
            ("cogging_nm", "<=", 0.05, "N m"),
        ]
        task = tasks.task(
            case,
            identity={
                "challenge": "motor",
                "contract_version": "synthetic-complete-buyer-panel",
                "action_grammar": grammar,
                "optimizer": {"class": "exhaustive", "version": "v1"},
                "query_budget": len(actions),
                "seed": 0,
                "observer_version": "synthetic-gamma-5d-theta+d",
                "reference_bank": "synthetic-shared-geometry-bank",
            },
            conditions=[{"id": pk.CONDITION, "stratum": "complete_buyer_panel"}],
            strata={"complete_buyer_panel": {"p": 1, "q": 1, "w": 1}},
            candidates=list(actions),
            actions=actions,
            objective={
                "quantity": "holding_ripple_fraction",
                "unit": "1",
                "sense": "min",
                "aggregate": "worst",
            },
            limits=[
                {"quantity": q, "op": op, "value": v, "unit": unit, "band": 0.0}
                for q, op, v, unit in limits
            ],
        )
        questions.append(
            {
                "case": case,
                "support_case": "synthetic-shared-geometry-bank",
                "task": task,
                "reference": copy.deepcopy(rows),
            }
        )
    export = {
        "schema": mp.EXPORT,
        "scope": scope,
        "family": "motor",
        "questions": questions,
    }
    export["export_digest"] = ca.sha256(ca.canonical(export))
    domain_pin = ca.sha256(ca.canonical(domain))
    train_pin = ca.sha256(train)
    policy = {
        "scope": scope,
        "export_digest": export["export_digest"],
        "domain_digest": domain_pin,
        "owner_requirements_digest": reference,
        "precommit_receipt": reference,
        "question_law": {
            "P": "synthetic-requirements",
            "Q": "synthetic-panel",
            "w": "synthetic-unit",
            "panel_use": "PUBLIC_HELDOUT",
        },
        "solver_orders": {e["case"]: [0, 1] for e in questions},
        "served_decisions": [1, 12],
        "seeds": list(mp.SEEDS),
    }
    prediction = {
        "schema": ca.PREDICTIONS,
        "scope": scope,
        "export_digest": export["export_digest"],
        "model_id": "SYNTHETIC_CURVE_STAND_IN",
        "source_receipt_digest": reference,
        "rows": [
            {
                "band": None,
                "candidate": r["candidate"],
                "condition": r["condition"],
                "values": r["values"],
            }
            for r in rows
        ],
    }
    cheap = {
        "scope": scope,
        "export_digest": export["export_digest"],
        "method": "SYNTHETIC_CHEAP_STAND_IN",
        "strongest_method_receipt": reference,
        "train_digest": train_pin,
        "predictions": prediction,
        "query_costs": {e["case"]: {"wall_s": 0.2, "core_s": 0.2} for e in questions},
    }
    costs = {
        "scope": scope,
        "export_digest": export["export_digest"],
        "preparation": {
            "model": {"wall_s": 3, "core_s": 3},
            "baseline": {"wall_s": 4, "core_s": 4},
        },
        "reference": [
            {
                "design": i,
                "cost": {"wall_s": 24000, "core_s": 48000},
                "planning_bound": {"wall_s": 25000, "core_s": 50000},
                "raw_sweeps": 11,
                "field_systems": 528,
                "source_digests": [reference],
            }
            for i in range(2)
        ],
        "failed_control_cost": {"wall_s": 2, "core_s": 2},
        "source_digests": [reference],
        "new_sweep_attempts": 0,
        "new_field_attempts": 0,
    }
    ref = {
        "scope": scope,
        "export_digest": export["export_digest"],
        "domain_digest": domain_pin,
        "image_digest": mp.IMAGE_DIGEST,
        "observer": "10p12s-gamma-5d-theta+d-three-equal-slices-v1",
        "adequacy_receipt": reference,
        "uncertainty_receipt": reference,
        "source_digests": [reference],
    }
    docs = {
        "export": export,
        "train": train,
        "domain": domain,
        "policy": policy,
        "cheap": cheap,
        "costs": costs,
        "reference": ref,
    }
    pins = {
        k: ca.sha256(v if k == "train" else ca.canonical(v)) for k, v in docs.items()
    }
    return docs, pins


def stand_in(kit, export, train, *, scope, seed, backend, code):
    assert scope == "SYNTHETIC_FIXTURE" and train.fixture
    physical = cb._physical_rows(export)
    assert all(all(v == 0 for v in r["values"].values()) for r in physical)
    rows = []
    for row in physical:
        predictions = [
            outputs({n: q[n] for n in mk.GRAMMAR}, q["j_a_mm2"], q["gamma_deg"])
            for q in kit.row_queries(row)
        ]
        # One overtly unsafe proposal checks that peak cannot be compensated.
        if row["candidate"] == "g0-s0":
            for i in range(3):
                mean = float(np.mean(list(predictions[i].values())))
                predictions[i] = {o: mean for o in mk.OUTPUTS}
                predictions[i + 3] = {o: v + 2 for o, v in predictions[i + 3].items()}
        values = kit.row_values(row, predictions)
        rows.append(
            {
                "band": None,
                "candidate": row["candidate"],
                "condition": row["condition"],
                "values": values,
            }
        )
    receipt = {
        "model_id": "SYNTHETIC_CURVE_STAND_IN",
        "scope": scope,
        "stand_in": True,
        "code": code,
        "seed": seed,
        "cost": {
            "fit": {"fit_cpu_s": 1.0, "fit_wall_s": 1.0},
            "inference": {
                "cold_wall_s": 0.1,
                "cold_cpu_s": 0.1,
                "wall_s": 0.1,
                "cpu_s": 0.1,
                "decision_queries": [
                    {
                        "query": e["case"],
                        "cold_wall_s": 0.1,
                        "cold_cpu_s": 0.1,
                        "wall_s": 0.1,
                        "cpu_s": 0.1,
                    }
                    for e in export["questions"]
                ],
            },
        },
    }
    pred = {
        "schema": ca.PREDICTIONS,
        "scope": scope,
        "export_digest": export["export_digest"],
        "model_id": receipt["model_id"],
        "source_receipt_digest": ca.sha256(ca.canonical(receipt)),
        "rows": rows,
    }
    return pred, receipt


def dry_run():
    docs, pins = documents()
    return mp.execute(docs, pins, fixture=True, trainer=stand_in)
