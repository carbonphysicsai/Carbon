"""Tiny stand-in for f02 pilot plumbing; never a physical or trained result.

Separate schema/scope and fixture-marked TRAIN prevent promotion through the
public worker. A deterministic trainer stand-in exercises the same candidate
view, judge, costs and OPT-12 path. It reads no files and calls no solvers.
"""

from __future__ import annotations

import copy

from carbon.design_search import producer_panels
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import f02_pilot as pilot
from scripts.dev.reference_packages.elmer import f02_export, f02_menu


def documents():
    candidates, actions = f02_export._bank()
    questions, train, costs = [], [], []
    for name, base in list(f02_menu.contexts())[:2]:
        task = f02_export._task(name, candidates, actions)
        rows = []
        for candidate, action in actions.items():
            rows.append(
                {
                    "candidate": candidate,
                    "condition": name,
                    "values": {
                        "peak_top_c": 60.2
                        + 0.2 * action["peak_w"]
                        + 0.5 * action["on_time_s"],
                        "extra_energy_j": pilot.energy(action, name),
                    },
                }
            )
            costs.append(
                {
                    "candidate": candidate,
                    "condition": name,
                    "cost": {"wall_s": 10, "core_s": 10},
                    "planning_bound": {"wall_s": 12, "core_s": 12},
                    "source_digests": ["sha256:" + "1" * 64],
                }
            )
        questions.append(
            {
                "case": task["task_id"],
                "support_case": f02_export.SUPPORT,
                "task": task,
                "reference": rows,
                "close_call": False,
                "refinement_demand": False,
                "settled": [],
            }
        )
        for peak, duration in ((81.0, 5.1), (99.0, 8.1)):
            train.append(
                {
                    "schema": pilot.KIT.train_schema,
                    "fixture": True,
                    "case_id": f"fixture-{name}-{peak}",
                    "inputs": {**base, "peak_w": peak, "on_time_s": duration},
                    "outputs": {
                        "peak_top_c": 60.2 + 0.2 * peak + 0.5 * duration,
                        "extra_energy_j": pilot.energy(
                            {"peak_w": peak, "on_time_s": duration}, name
                        ),
                    },
                }
            )
    # Build a valid public-export-shaped stand-in, not a new physical bank.
    from carbon.design_search import diversity, power_accumulation

    cases = [q["case"] for q in questions]
    law = diversity.register_law(
        {
            "schema": diversity.LAW_SCHEMA_V2,
            "population_status": "UNREGISTERED",
            "kind": "grid",
            "draw_model": "iid_with_replacement",
            "batch_size": 2,
            "bins": [{"case": c, "q_mass": 0.5} for c in cases],
            "mass_l1_error_bound": 0.0,
        }
    )
    export = producer_panels.seal_export(
        {
            "schema": producer_panels.EXPORT_SCHEMA,
            "sealed": True,
            "family": "f02",
            "challenge_id": "f02",
            "exposure_unit": power_accumulation.EXPOSURE_UNIT,
            "exposure": [{"case": c, "limit": 5, "used": 0} for c in cases],
            "window_sampling": power_accumulation.register_window_sampling(
                case_strata=[{"case": c, "stratum": "all"} for c in cases],
                quotas_by_k=[
                    {"questions_per_batch": k, "quotas": {"all": k}} for k in (1, 2)
                ],
            ),
            "questions": questions,
            "laws": [law],
            "refinement_rule": f02_export.RULE,
        }
    )
    train_raw = b"\n".join(ca.canonical(r) for r in train) + b"\n"
    policy = {
        "schema": "carbon.f02.winnability-policy.v1",
        "scope": "SYNTHETIC_FIXTURE",
        "export_digest": export["export_digest"],
        "question_law": {
            "P": "fixture-P",
            "Q": "fixture-Q",
            "w": "fixture-w",
            "panel_use": "PUBLIC_HELDOUT",
        },
        "solver_orders": {
            e["case"]: sorted(
                actions,
                key=lambda c: -pilot.energy(
                    actions[c], e["task"]["conditions"][0]["id"]
                ),
            )
            for e in questions
        },
        "served_decisions": [1, 10, 100],
        "seed_policy": list(pilot.SEEDS),
        "frozen_before_heldout": True,
    }
    predicted = [
        {"band": None, **copy.deepcopy(r)} for e in questions for r in e["reference"]
    ]
    docs = {
        "export": export,
        "train": train_raw,
        "policy": policy,
        "cheap_screen": {
            "schema": pilot.SCREEN,
            "scope": "SYNTHETIC_FIXTURE",
            "method": pilot.METHOD,
            "export_digest": export["export_digest"],
            "train_sha256": ca.sha256(train_raw),
            "calibration_role": "TRAIN_ONLY",
            "policy_digest": ca.sha256(ca.canonical(policy)),
            "source_digests": ["sha256:" + "2" * 64],
            "predictions": {
                "schema": ca.PREDICTIONS,
                "scope": "SYNTHETIC_FIXTURE",
                "model_id": "fixture-spatial-rom",
                "export_digest": export["export_digest"],
                "source_receipt_digest": "sha256:" + "3" * 64,
                "rows": predicted,
            },
            "query_costs": {c: {"wall_s": 0.1, "core_s": 0.1} for c in cases},
        },
        "costs": {
            "schema": pilot.COSTS,
            "scope": "SYNTHETIC_FIXTURE",
            "export_digest": export["export_digest"],
            "reference": costs,
            "preparation": {
                "model": {"wall_s": 20, "core_s": 20},
                "baseline": {"wall_s": 30, "core_s": 30},
            },
            "acquisition_sources": ["sha256:" + "4" * 64],
            "failed_control_cost": {"wall_s": 5, "core_s": 5},
            "lifecycle": {"status": "NOT_RUN", "receipt_digest": None},
        },
        "reference_receipt": {
            "schema": "carbon.f02.pilot-reference-return.v1",
            "scope": "SYNTHETIC_FIXTURE",
            "image_digest": pilot.IMAGE,
            "export_digest": export["export_digest"],
            "observer": "sha256:" + "5" * 64,
            "convergence": "sha256:" + "6" * 64,
            "conservation": "sha256:" + "7" * 64,
            "code_verification": "sha256:" + "8" * 64,
            "reference_status": "PUBLIC_DIAGNOSTIC_ONLY",
        },
    }
    pins = {
        key: ca.sha256(value if isinstance(value, bytes) else ca.canonical(value))
        for key, value in docs.items()
    }
    return docs, pins


def trainer(kit, export, train, *, scope, seed, backend):
    assert scope == "SYNTHETIC_FIXTURE" and train.fixture
    assert kit == pilot.KIT and backend == "jax"
    # Assert the worker passed only the candidate view, never reference labels.
    assert all(
        set(r["values"].values()) == {0.0}
        for e in export["questions"]
        for r in e["reference"]
    )
    rows = []
    for e in export["questions"]:
        for r in e["reference"]:
            action = e["task"]["actions"][r["candidate"]]
            rows.append(
                {
                    "band": None,
                    "candidate": r["candidate"],
                    "condition": r["condition"],
                    "values": {
                        "peak_top_c": 60.2
                        + 0.2 * action["peak_w"]
                        + 0.5 * action["on_time_s"]
                        + 1,
                        "extra_energy_j": -999,
                    },
                }
            )  # objective must be overridden identically
    receipt = {
        "scope": scope,
        "model_id": kit.model_id,
        "train": {"fixture": True},
        "seed": seed,
        "cost": {
            "fit": {"fit_wall_s": 1, "fit_cpu_s": 1},
            "inference": {
                "cold_wall_s": 0.3,
                "cold_cpu_s": 0.3,
                "wall_s": 0.2,
                "cpu_s": 0.2,
                "decision_queries": [
                    {
                        "query": e["case"],
                        "wall_s": 0.2,
                        "cpu_s": 0.2,
                        "cold_wall_s": 0.1,
                        "cold_cpu_s": 0.1,
                    }
                    for e in export["questions"]
                ],
            },
        },
    }
    return {
        "schema": ca.PREDICTIONS,
        "scope": scope,
        "model_id": kit.model_id,
        "export_digest": export["export_digest"],
        "source_receipt_digest": ca.sha256(ca.canonical(receipt)),
        "rows": rows,
    }, receipt


def dry_run():
    docs, pins = documents()
    return pilot.execute(docs, pins, fixture=True, trainer=trainer)
