"""Deterministic stand-in only; no native physics or real L0 training."""

import copy

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import solenoid_kit as sk
from carbon.development_comparison import solenoid_pilot as worker


def raw_values(action, stratum):
    force = (
        5
        + action["tip_radius_over_Ra"]
        + {"nominal": 0, "hot": 0.2, "gap": 0.4}[stratum]
    )
    return {
        f"{quantity}_{j:02d}": force if quantity == "force_closing_n" else 0.1
        for quantity in sk.QUANTITIES
        for j in range(27)
    }


def documents():
    domain = {
        "schema": sk.SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "anchor_digest": "sha256:" + "a" * 64,
        "material_digest": "sha256:" + "b" * 64,
        "coil_digest": "sha256:" + "c" * 64,
        "domain_digest": "sha256:" + "d" * 64,
        "conditions": {s: s for s in sk.STRATA},
        "strata": list(sk.STRATA),
        "coordinate_bounds": {n: list(b) for n, b in sk.COORDS},
        "current_fractions": list(sk.CURRENTS),
        "stroke_fractions": list(sk.STROKES),
        "force_targets_n": {s: [6.0] * 27 for s in sk.STRATA},
    }
    kit = sk.kit_from_bytes(ca.canonical(domain))
    action = lambda tip: dict(zip((n for n, _b in sk.COORDS), (tip, 0.2, 1.2, 0.55)))
    actions = {f"S{i}": action(tip) for i, tip in enumerate((0.6, 0.8, 1.0))}
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "fixture-solenoid.v1",
        "variables": [
            {"name": n, "type": "number", "min": lo, "max": hi, "step": 0.01}
            for n, (lo, hi) in sk.COORDS
        ],
        "rules": [],
    }
    questions, reference_cost = [], []
    for index in range(2):
        task = tasks.task(
            f"fixture-{index}",
            identity={
                "challenge": sk.FAMILY,
                "contract_version": "fixture-only",
                "action_grammar": grammar,
                "optimizer": {"class": "exhaustive", "version": "v1"},
                "query_budget": 3,
                "seed": 0,
                "observer_version": "synthetic-27-state-only",
                "reference_bank": "fixture-one-package",
            },
            conditions=[{"id": s, "stratum": s} for s in sk.STRATA],
            strata={s: {"p": 1 / 3, "q": 1 / 3, "w": 1 / 3} for s in sk.STRATA},
            candidates=list(actions),
            actions=actions,
            objective={
                "quantity": "force_envelope_error_n",
                "unit": "N",
                "sense": "min",
                "aggregate": "worst",
            },
            limits=[
                {
                    "quantity": f"force_closing_n_{j:02d}",
                    "unit": "N",
                    "op": ">=",
                    "value": 5.72 + index * 0.1,
                    "band": 0.01,
                }
                for j in range(27)
            ],
        )
        rows = []
        for candidate, a in actions.items():
            for s in sk.STRATA:
                row = {"candidate": candidate, "condition": s, "action": a}
                rows.append(
                    {
                        "candidate": candidate,
                        "condition": s,
                        "values": kit.row_values(row, [raw_values(a, s)]),
                    }
                )
                if index == 0:
                    reference_cost.append(
                        {
                            "candidate": candidate,
                            "condition": s,
                            "cost": {"wall_s": 10, "core_s": 10},
                            "planning_bound": {"wall_s": 12, "core_s": 12},
                            "field_states": 27,
                            "source_digests": ["sha256:" + "e" * 64],
                        }
                    )
        questions.append(
            {
                "case": f"fixture-{index}",
                "support_case": "same-package-not-two-independent-buyers",
                "task": task,
                "reference": rows,
            }
        )
    body = {"schema": worker.EXPORT, "family": sk.FAMILY, "questions": questions}
    export = {**body, "export_digest": ca.sha256(ca.canonical(body))}
    train = []
    for tip in (0.65, 0.75):
        for s in sk.STRATA:
            train.append(
                {
                    "schema": sk.TRAIN_SCHEMA,
                    "fixture": True,
                    "case_id": f"train-{tip}-{s}",
                    "inputs": {**action(tip), "stratum": s},
                    "outputs": raw_values(action(tip), s),
                }
            )
    train_raw = b"\n".join(ca.canonical(r) for r in train) + b"\n"
    model = {
        "schema": ca.PREDICTIONS,
        "scope": "SYNTHETIC_FIXTURE",
        "model_id": "fixture-cheap",
        "export_digest": export["export_digest"],
        "source_receipt_digest": "sha256:" + "1" * 64,
        "rows": [{"band": None, **copy.deepcopy(r)} for r in questions[0]["reference"]],
    }
    policy = {
        "schema": "carbon.solenoid-pole.pilot-policy.v1",
        "scope": "SYNTHETIC_FIXTURE",
        "export_digest": export["export_digest"],
        "domain_digest": ca.sha256(ca.canonical(domain)),
        "owner_requirements_digest": "sha256:" + "2" * 64,
        "question_law": {
            "P": "fixture-P",
            "Q": "fixture-Q",
            "w": "fixture-w",
            "panel_use": "PUBLIC_HELDOUT",
        },
        "solver_orders": {e["case"]: list(actions) for e in questions},
        "served_decisions": [1, 10, 100],
        "seed_policy": list(worker.SEEDS),
        "precommit_receipt": "sha256:" + "3" * 64,
    }
    docs = {
        "domain": domain,
        "train": train_raw,
        "export": export,
        "policy": policy,
        "cheap": {
            "schema": "carbon.solenoid-pole.strongest-cheap-screen.v1",
            "scope": "SYNTHETIC_FIXTURE",
            "method": "nonlinear-reluctance-fringing-calibrated",
            "export_digest": export["export_digest"],
            "train_sha256": ca.sha256(train_raw),
            "domain_digest": policy["domain_digest"],
            "precommit_receipt": policy["precommit_receipt"],
            "calibration_role": "TRAIN_WHOLE_GEOMETRY_ONLY",
            "predictions": model,
            "query_costs": {
                e["case"]: {"wall_s": 0.1, "core_s": 0.1} for e in questions
            },
            "source_digests": ["sha256:" + "4" * 64],
        },
        "reference": {
            "schema": "carbon.solenoid-pole.pilot-reference-return.v1",
            "scope": "SYNTHETIC_FIXTURE",
            "export_digest": export["export_digest"],
            "domain_digest": policy["domain_digest"],
            "image_digest": "sha256:" + "5" * 64,
            "formulation": "AXISYMMETRIC_APHI",
            "observer_scope": "MAXWELL_FORCE_NONLINEAR_COENERGY_VIRTUAL_WORK",
            "source_digests": ["sha256:" + "6" * 64],
            "native_acceptance_receipt": "sha256:" + "7" * 64,
        },
        "costs": {
            "schema": "carbon.solenoid-pole.pilot-costs.v1",
            "scope": "SYNTHETIC_FIXTURE",
            "export_digest": export["export_digest"],
            "preparation": {
                arm: {"wall_s": 20, "core_s": 20} for arm in ("model", "baseline")
            },
            "reference": reference_cost,
            "failed_control_cost": {"wall_s": 5, "core_s": 5},
            "source_digests": ["sha256:" + "8" * 64],
            "new_curve_attempts": 0,
            "new_field_attempts": 0,
        },
    }
    pins = {
        key: ca.sha256(value if isinstance(value, bytes) else ca.canonical(value))
        for key, value in docs.items()
    }
    return docs, pins


def trainer(kit, export, train, *, scope, seed, backend, code=None):
    assert scope == "SYNTHETIC_FIXTURE" and train.fixture and backend == "jax"
    rows = cb_physical(export)
    assert all(set(row["values"].values()) == {0.0} for row in rows)
    predictions = []
    for row in rows:
        raw = raw_values(row["action"], row["condition"])
        for key in raw:
            if key.startswith("force_closing_n"):
                raw[key] += 0.2
        predictions.append(
            {
                "band": None,
                "candidate": row["candidate"],
                "condition": row["condition"],
                "values": kit.row_values(row, [raw]),
            }
        )
    receipt = {
        "scope": scope,
        "model_id": kit.model_id,
        "train": {"fixture": True},
        "seed": seed,
        "code": code,
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
        "rows": predictions,
    }, receipt


def cb_physical(export):
    from carbon.development_comparison.cheap_baselines import _physical_rows

    return _physical_rows(export)


def dry_run():
    docs, pins = documents()
    return worker.execute(docs, pins, fixture=True, trainer=trainer)
