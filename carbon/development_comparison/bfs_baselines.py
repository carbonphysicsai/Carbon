"""Held-geometry-out PUBLIC_DEVELOPMENT BFS cheap comparisons, no solves.

Reuse #994's neutral task judge, decision report and cost/ranking export.
The cached coarse-RANS map is NOT the held-out fine reference. The sudden
expansion correlation is only a qualified-applicability control, not a
replacement for general recovery-contour RANS.
"""

from __future__ import annotations

import math
import time
from copy import deepcopy

from carbon.design_search import tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb

FAMILY = "backward-facing-step"
DUTY_COMPILER = "carbon.bfs-duty-objective.development.v1"
DUTY_QUANTITY = "buyer_duty_loss_pa"


def duty_task(registered, weights):
    """Compile a supplied duty cycle without changing the shared task schema.

    The neutral mean of N*w_i*loss_i is exactly sum(w_i*loss_i). Hard limits
    retain the unscaled per-condition observables, including zero-duty points.
    The compiler and weights are bound into a NEW observer/task identity; no
    sealed task is reinterpreted. This does not choose or qualify the weights.
    """
    tasks._verify_task_digest(registered)
    ids = [c["id"] for c in registered["conditions"]]
    if (
        registered["schema"] != tasks.RUNNABLE_SCHEMA
        or registered["objective"]
        != {"quantity": "loss_pa", "unit": "Pa", "sense": "min", "aggregate": "mean"}
        or type(weights) is not dict
        or set(weights) != set(ids)
        or any(
            type(w) not in (int, float) or not math.isfinite(w) or w < 0
            for w in weights.values()
        )
        or not math.isclose(sum(weights.values()), 1, rel_tol=1e-12, abs_tol=1e-12)
    ):
        raise ValueError(
            "registered BFS mean loss and complete normalized duty weights required"
        )
    if any(l["quantity"] == DUTY_QUANTITY for l in registered["limits"]):
        raise ValueError("duty weighting must never scale a hard limit")
    if (
        registered["secondary"] is not None
        and registered["secondary"]["quantity"] == DUTY_QUANTITY
    ):
        raise ValueError("raw source task must not contain the compiled duty quantity")
    identity = deepcopy(registered["identity"])
    identity["observer_version"] = {
        "source": identity["observer_version"],
        "compiler": DUTY_COMPILER,
        "duty_weights": dict(weights),
    }
    return tasks.task(
        registered["task_id"] + ":duty-v1",
        identity=identity,
        conditions=registered["conditions"],
        strata=registered["strata"],
        candidates=registered["candidates"],
        actions=registered["actions"],
        objective={**registered["objective"], "quantity": DUTY_QUANTITY},
        secondary=registered["secondary"],
        limits=registered["limits"],
        tie_rule=registered["tie_rule"],
    )


def duty_values(compiled, values):
    """Apply the same registered transform to prediction OR reference values.

    No reference access, fitting, prediction repair or imputation takes place.
    Missing conditions stay missing; a zero-duty condition still needs truth
    and must satisfy every hard limit.
    """
    tasks._verify_task_digest(compiled)
    observer = compiled["identity"]["observer_version"]
    if (
        not isinstance(observer, dict)
        or observer.get("compiler") != DUTY_COMPILER
        or compiled["objective"]["quantity"] != DUTY_QUANTITY
    ):
        raise ValueError("duty-compiled task required")
    weights = observer["duty_weights"]
    result = {}
    for (candidate, condition), row in values.items():
        if candidate not in compiled["candidates"] or condition not in weights:
            raise ValueError("unregistered candidate or service condition")
        if (
            DUTY_QUANTITY in row
            or type(row.get("loss_pa")) not in (int, float)
            or not math.isfinite(row["loss_pa"])
        ):
            raise ValueError(
                "finite raw loss, not an already transformed value, required"
            )
        result[(candidate, condition)] = {
            **row,
            DUTY_QUANTITY: len(weights) * weights[condition] * row["loss_pa"],
        }
    return result


def _duty_reports(export, predicted, screens):
    """Per-brief matched neutral reports; physical errors remain unweighted."""
    decisions, screening = [], []
    for entry in export["questions"]:
        if "duty_weights" not in entry:
            if export["scope"] != "SYNTHETIC_FIXTURE":
                raise ValueError(
                    "public BFS buyer comparison requires each brief's duty weights"
                )
            single = {**export, "questions": [entry]}
            predictions = predicted
        else:
            compiled = duty_task(entry["task"], entry["duty_weights"])
            references = duty_values(
                compiled,
                {
                    (r["candidate"], r["condition"]): r["values"]
                    for r in entry["reference"]
                },
            )
            prediction_rows = duty_values(
                compiled,
                {
                    (c, cond): v
                    for (band, c, cond), v in predicted.items()
                    if band is None
                    and c in compiled["candidates"]
                    and cond in entry["duty_weights"]
                },
            )
            predictions = {
                (None, c, cond): v for (c, cond), v in prediction_rows.items()
            }
            transformed = {
                **entry,
                "task": compiled,
                "reference": [
                    {**r, "values": references[(r["candidate"], r["condition"])]}
                    for r in entry["reference"]
                ],
            }
            if "settled" in entry:
                raise ValueError(
                    "settled reference receipt must be regenerated for the new task identity"
                )
            single = {**export, "questions": [transformed]}
        single.pop("export_digest")
        single["export_digest"] = tasks.digest(single)
        decisions.append(cb.decision_report(single, predictions))
        screened = pb.screening_export(single, predictions, screens)
        screened["source_export_digest"] = export["export_digest"]
        screened["cache_cost_accounting"] = (
            "SHARED_PANEL_FIT_AND_QUERY_COST_DO_NOT_SUM_ACROSS_REQUIREMENT_DRAWS"
        )
        screening.append(screened)
    return decisions, screening


def validate_materials(export, material):
    if (
        export.get("scope") not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or export.get("family") != FAMILY
    ):
        raise ValueError("explicit public/fixture BFS export required")
    if export.get("export_digest") != tasks.digest(
        {k: v for k, v in export.items() if k != "export_digest"}
    ):
        raise ValueError("sealed export digest required")
    if material.get("export_digest") != export["export_digest"]:
        raise ValueError("matched comparator material required")
    fields = material.get("coordinate_fields")
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("registered ordered geometry coordinates required")
    for e in export["questions"]:
        tasks._verify_task_digest(e["task"])
        if e["task"]["schema"] != tasks.RUNNABLE_SCHEMA:
            raise ValueError("runnable neutral plain task required")
    actual = cb._physical_rows(export)
    index = {(r["candidate"], r["condition"]): r for r in actual}
    rows = material.get("rows", [])
    if len(rows) != len(index):
        raise ValueError("complete coarse material inventory required")
    seen, groups = set(), {}
    for r in rows:
        key = (r["candidate"], r["condition"])
        if key not in index or key in seen:
            raise ValueError("duplicate/unmatched coarse material")
        seen.add(key)
        if (
            not r.get("geometry_id")
            or not r.get("coarse_source")
            or not r.get("fine_source")
            or r["coarse_source"] == r["fine_source"]
        ):
            raise ValueError(
                "separate coarse/fine provenance and holdout groups required"
            )
        expected = [index[key]["action"][f] for f in fields]
        if r["coordinates"] != expected or any(not math.isfinite(x) for x in expected):
            raise ValueError(
                "registered geometry coordinates, never identifiers, required"
            )
        if groups.setdefault(r["geometry_id"], expected) != expected:
            raise ValueError("sibling contexts must share one geometry")
        if set(r["coarse_values"]) != set(index[key]["values"]) or any(
            not math.isfinite(v) for v in r["coarse_values"].values()
        ):
            raise ValueError("all decision quantities from coarse reference required")
    if len({tuple(v) for v in groups.values()}) != len(groups):
        raise ValueError("one physical geometry cannot split holdout groups")
    fine_sources = {r["fine_source"] for r in rows}
    if any(r["coarse_source"] in fine_sources for r in rows):
        raise ValueError("coarse cache cannot borrow any fine reference source")
    return rows


def measure(export, *, material):
    rows = validate_materials(export, material)
    predicted, screens, fits = {}, [], []
    for target in rows:
        train = [
            r
            for r in rows
            if r["geometry_id"] != target["geometry_id"]
            and r["condition"] == target["condition"]
        ]
        start, cpu = time.perf_counter(), time.process_time()
        quantities = sorted(target["coarse_values"])
        model = None
        try:
            model = cb.CurveSurface(
                [r["coordinates"] for r in train],
                [[r["coarse_values"][q] for q in quantities] for r in train],
            )
        except (ValueError, cb.Unsupported):
            pass
        fit = {
            "wall_s": time.perf_counter() - start,
            "cpu_s": time.process_time() - cpu,
        }
        fits.append(fit)
        start, cpu = time.perf_counter(), time.process_time()
        key = (None, target["candidate"], target["condition"])
        if model is not None:
            try:
                pred = model.predict([target["coordinates"]])[0]
                predicted[key] = dict(zip(quantities, map(float, pred)))
            except cb.Unsupported:
                pass
        query = {
            "wall_s": time.perf_counter() - start,
            "cpu_s": time.process_time() - cpu,
        }
        screens.append(
            {
                "candidate": target["candidate"],
                "condition": target["condition"],
                "status": "PREDICTED" if key in predicted else "ABSTAINED",
                "fit_cost": fit,
                "query_cost": query,
            }
        )
    if (
        any("duty_weights" in e for e in export["questions"])
        or export["scope"] != "SYNTHETIC_FIXTURE"
    ):
        decisions, screening = _duty_reports(export, predicted, screens)
        decision_report = {"questions": len(decisions), "per_brief": decisions}
        screening_report = {"per_brief": screening}
        objective_coverage = "REGISTERED_DUTY_WEIGHTED_COMPLETE_BRIEF"
    else:
        decision_report = cb.decision_report(export, predicted)
        screening_report = pb.screening_export(export, predicted, screens)
        objective_coverage = "UNWEIGHTED_SYNTHETIC_DIAGNOSTIC_ONLY"
    return {
        "schema": "carbon.development-bfs-baseline-report.v1",
        "family": FAMILY,
        "scope": export["scope"],
        "reference_solves_launched": 0,
        "held_out_unit": "WHOLE_GEOMETRY_ALL_CONDITIONS",
        "pointwise": cb.pointwise_errors(export, predicted),
        "decision": decision_report,
        "equal_budget_screening": screening_report,
        "objective_coverage": objective_coverage,
        "fit_cost": cb._cost(fits),
        "retained_costs": material.get("costs"),
        "unknown_costs": (
            [
                "image_startup",
                "reference_acquisition",
                "reference_refinement",
                "retained_verification",
                "money",
            ]
            if material.get("costs") is None
            else []
        ),
        "v4": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
        "uncertainty": "POINT_PREDICTIONS_NOT_QUALIFIED_SAFETY_BOUNDS",
    }


def sudden_expansion_loss(*, area_ratio, dynamic_pressure_pa, applicability):
    """Borda-Carnot control; not an arbitrary planar diffuser correlation.

    Caller supplies registered source/applicability. Separation, finite
    recovery length or differing contour support must not be silently ignored.
    This scalar alone cannot supply all task limits: it must abstain there.
    """
    if applicability.get("geometry") != "abrupt_expansion" or not applicability.get(
        "source"
    ):
        raise cb.Unsupported("correlation does not cover the recovery-contour task")
    if (
        not math.isfinite(area_ratio)
        or area_ratio < 1
        or not math.isfinite(dynamic_pressure_pa)
        or dynamic_pressure_pa <= 0
    ):
        raise ValueError("positive physical expansion inputs required")
    return {
        "loss_pa": dynamic_pressure_pa * (1 - 1 / area_ratio) ** 2,
        "reattachment_over_H": None,
        "exit_reverse_flow": None,
        "full_decision": "ABSTAIN_MISSING_SEPARATION_OBSERVABLES",
    }
