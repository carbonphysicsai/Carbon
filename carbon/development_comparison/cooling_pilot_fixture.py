"""Deterministic cooling wiring stand-in; no native solve or real L0 fit."""

from carbon.challenge_pipeline import cooling_readiness as cr
from carbon.cold_plate import domain, openfoam
from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import cooling_kit as ck
from carbon.development_comparison import cooling_pilot as worker


def registration():
    services = []
    for index, (name, ratio, center) in enumerate(
        (("uniform", 1, 15), ("interior", 1.5, 10), ("downstream", 2, 22))
    ):
        services.append(
            {
                "id": "fixture-" + name,
                "stratum": "fixture-" + name,
                "plane": cr.PLANE,
                "coolant": "PG25",
                "lid_id": "fixture-lid",
                "inlet_c": 40,
                "heat_load_w": 1000,
                "hotspot_ratio": ratio,
                "hotspot_center_mm": center,
                "hotspot_width_mm": 2.5,
                "map_digest": "sha256:" + str(index + 1) * 64,
                "characterization_digest": "sha256:" + "a" * 64,
                "inlet_source_digest": "sha256:" + "b" * 64,
                "tim2_m2k_w": 5e-6,
                "map_uncertainty_k": 0.1,
                "cell_pressure_limit_pa": 25000,
                "objective": "min_cell_pressure_pa",
            }
        )
    return cr.seal(
        {
            "schema": cr.SCHEMA,
            "scope": "SYNTHETIC_FIXTURE",
            "authority": "synthetic wiring only; no characterized maps",
            "pins": {
                "solver_image": openfoam.IMAGE.split("@")[1],
                "solver_source": "sha256:" + "c" * 64,
                "materials": "sha256:" + "d" * 64,
                "observer": "sha256:" + "e" * 64,
            },
            "grammar": {
                "channel_width_mm": {"min": 0.2, "max": 0.5, "step": 0.05},
                "fin_width_mm": {"min": 0.2, "max": 0.5, "step": 0.05},
                "channel_depth_mm": {"min": 1, "max": 3, "step": 0.5},
                "flow_lpm_per_kw": {"min": 1.5, "max": 1.5, "step": 0.25},
            },
            "services": services,
            **{law: {s["id"]: 1 / 3 for s in services} for law in ("P", "Q", "w")},
        }
    )


def action(width):
    return dict(zip(cr.ACTION, (width, 0.3, 2, 1.5)))


def observation(reg, a, service):
    case = cr.case(reg, a, service, resolution=2)
    area = (a["channel_width_mm"] + a["fin_width_mm"]) * 0.0005 * 0.03
    return {
        "faces": [
            {
                "x_m": x,
                "y_m": (a["channel_width_mm"] + a["fin_width_mm"]) * 0.00025,
                "area_m2": area / 2,
                "plate_c": 70 + 10 * (0.4 - a["channel_width_mm"]) + index,
                "q_w_m2": domain.heat_flux(case["inputs"], x * 1000),
            }
            for index, x in enumerate((0.0075, 0.0225))
        ],
        "numerical_uncertainty_k": 0.1,
        "pressure_drop_pa": 10000 + (0.4 - a["channel_width_mm"]) * 20000,
        "fluid_min_c": 40,
        "fluid_max_c": 42,
    }


def documents():
    reg = registration()
    actions = {"H" + str(i): action(width) for i, width in enumerate((0.2, 0.3, 0.4))}
    services = [s["id"] for s in reg["services"]]
    rows, witnesses, reference_costs = [], [], []
    for candidate, a in actions.items():
        for service in services:
            raw = observation(reg, a, service)
            observed = cr.observe(reg, a, service, **raw)
            rows.append(
                {
                    "candidate": candidate,
                    "condition": service,
                    "values": {k: observed[k] for k in ck.OBSERVABLES},
                }
            )
            witnesses.append(
                {
                    "candidate": candidate,
                    "condition": service,
                    **raw,
                    "pressure_uncertainty_pa": 0,
                }
            )
            reference_costs.append(
                {
                    "candidate": candidate,
                    "condition": service,
                    "cost": {"wall_s": 10, "core_s": 20},
                    "planning_bound": {"wall_s": 12, "core_s": 24},
                    "source_digests": ["sha256:" + "f" * 64],
                }
            )
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "fixture-only",
        "variables": [
            {"name": n, "type": "number", **rule} for n, rule in reg["grammar"].items()
        ],
        "rules": [],
    }
    questions = []
    for index, ceiling in enumerate((85, 82)):
        task = tasks.task(
            "fixture-Q" + str(index),
            identity={
                "challenge": ck.FAMILY,
                "contract_version": "fixture-only",
                "action_grammar": grammar,
                "optimizer": {"class": "exhaustive", "version": "v1"},
                "query_budget": 3,
                "seed": 0,
                "observer_version": cr.OBSERVER + ":" + reg["digest"],
                "reference_bank": "fixture-one-physical-bank",
            },
            conditions=[{"id": s, "stratum": s} for s in services],
            strata={s: {"p": 1 / 3, "q": 1 / 3, "w": 1 / 3} for s in services},
            candidates=list(actions),
            actions=actions,
            objective={
                "quantity": "cell_pressure_drop_pa",
                "unit": "Pa",
                "sense": "min",
                "aggregate": "worst",
            },
            limits=[
                {
                    "quantity": "peak_case_c",
                    "unit": "degC",
                    "op": "<=",
                    "value": ceiling,
                    "band": 0.2,
                },
                {
                    "quantity": "cell_pressure_drop_pa",
                    "unit": "Pa",
                    "op": "<=",
                    "value": 25000,
                    "band": 0,
                },
                {
                    "quantity": "cell_pressure_drop_pa",
                    "unit": "Pa",
                    "op": ">=",
                    "value": 0,
                    "band": 0,
                },
            ],
        )
        questions.append(
            {"case": "fixture-Q" + str(index), "task": task, "reference": rows}
        )
    body = {
        "schema": worker.EXPORT,
        "scope": "SYNTHETIC_FIXTURE",
        "family": ck.FAMILY,
        "questions": questions,
    }
    export = {**body, "export_digest": ca.sha256(ca.canonical(body))}
    records = []
    for width in (0.25, 0.35):
        for service in services:
            raw = observation(reg, action(width), service)
            observed = cr.observe(reg, action(width), service, **raw)
            records.append(
                {
                    "schema": ck.TRAIN_SCHEMA,
                    "fixture": True,
                    "inputs": {**action(width), "service": service},
                    "outputs": {k: observed[k] for k in ck.OUTPUTS},
                    "registration_digest": reg["digest"],
                    "observer_version": cr.OBSERVER + ":" + reg["digest"],
                    "observation": raw,
                }
            )
    train = b"\n".join(ca.canonical(r) for r in records) + b"\n"
    shared = {
        "scope": "SYNTHETIC_FIXTURE",
        "export_digest": export["export_digest"],
        "registration_digest": reg["digest"],
    }
    predictions = {
        "schema": ca.PREDICTIONS,
        "scope": "SYNTHETIC_FIXTURE",
        "export_digest": export["export_digest"],
        "model_id": "fixture-cheap",
        "source_receipt_digest": "sha256:" + "1" * 64,
        "rows": [{"band": None, **r} for r in rows],
    }
    policy = {
        "schema": "carbon.cooling-cell.pilot-policy.v1",
        **shared,
        "precommit_receipt": "sha256:" + "2" * 64,
        "question_law": {
            "P": "fixture-P",
            "Q": "fixture-Q",
            "w": "fixture-w",
            "panel_use": "PUBLIC_HELDOUT",
        },
        "solver_orders": {e["case"]: list(actions) for e in questions},
        "served_decisions": [1, 10, 100],
        "seed_policy": list(worker.SEEDS),
    }
    docs = {
        "registration": reg,
        "train": train,
        "export": export,
        "policy": policy,
        "reference": {
            "schema": "carbon.cooling-cell.pilot-reference.v1",
            **shared,
            "native_acceptance_receipt": "sha256:" + "3" * 64,
            "source_digests": ["sha256:" + "4" * 64],
            "observations": witnesses,
        },
        "cheap": {
            "schema": "carbon.cooling-cell.strongest-cheap-screen.v1",
            **shared,
            "train_sha256": ca.sha256(train),
            "precommit_receipt": policy["precommit_receipt"],
            "method": "same-map-rbf-kriging",
            "calibration_role": "TRAIN_WHOLE_GEOMETRY_ONLY",
            "predictions": predictions,
            "query_costs": {
                e["case"]: {"wall_s": 0.1, "core_s": 0.2} for e in questions
            },
            "source_digests": ["sha256:" + "5" * 64],
        },
        "costs": {
            "schema": "carbon.cooling-cell.pilot-costs.v1",
            **shared,
            "preparation": {
                arm: {"wall_s": 20, "core_s": 40} for arm in ("model", "baseline")
            },
            "failed_control_cost": {"wall_s": 5, "core_s": 10},
            "reference": reference_costs,
            "source_digests": ["sha256:" + "6" * 64],
            "new_attempts": 0,
        },
    }
    pins = {
        k: ca.sha256(v if isinstance(v, bytes) else ca.canonical(v))
        for k, v in docs.items()
    }
    return docs, pins


def trainer(kit, export, train, *, scope, seed, backend, code):
    assert scope == "SYNTHETIC_FIXTURE" and train.fixture and backend == "jax"
    reg = registration()
    rows = []
    for row in cb._physical_rows(export):
        assert set(row["values"].values()) == {0.0}
        observed = cr.observe(
            reg,
            row["action"],
            row["condition"],
            **observation(reg, row["action"], row["condition"]),
        )
        predicted = {
            k: observed[k] + (0.1 if k == "peak_case_c" else 100) for k in ck.OUTPUTS
        }
        rows.append(
            {
                "band": None,
                "candidate": row["candidate"],
                "condition": row["condition"],
                "values": kit.row_values(row, [predicted]),
            }
        )
    receipt = {
        "scope": scope,
        "model_id": kit.model_id,
        "fixture": True,
        "code": code,
        "seed": seed,
        "cost": {
            "fit": {"fit_wall_s": 1, "fit_cpu_s": 1},
            "inference": {
                "cold_wall_s": 0.3,
                "cold_cpu_s": 0.6,
                "wall_s": 0.2,
                "cpu_s": 0.4,
                "decision_queries": [
                    {
                        "query": e["case"],
                        "wall_s": 0.2,
                        "cpu_s": 0.4,
                        "cold_wall_s": 0.1,
                        "cold_cpu_s": 0.2,
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
    result = worker.execute(docs, pins, fixture=True, trainer=trainer)
    result["basis"] = (
        "DETERMINISTIC_TRAINER_STAND_IN; no real MLP fit or native reference"
    )
    return result
