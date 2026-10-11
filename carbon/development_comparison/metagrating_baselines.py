"""Held-pattern-out library/map comparisons. No reference solves or hidden data.

Library retrieval and an interpolated full-output map are admitted competitors.
Published efficiency alone cannot stand in for missing safety/order outputs.
"""

from __future__ import annotations

import math
import time

from carbon.design_search import tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb

FAMILY = "metagrating-3d"


def validate(export, material):
    if (
        export.get("scope") not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or export.get("family") != FAMILY
    ):
        raise ValueError("explicit public/fixture MG export required")
    if export.get("export_digest") != tasks.digest(
        {k: v for k, v in export.items() if k != "export_digest"}
    ):
        raise ValueError("sealed physical export required")
    if material.get("export_digest") != export["export_digest"]:
        raise ValueError("matched library material required")
    fields = material.get("coordinate_fields")
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("registered ordered physical descriptors required")
    radius = material.get("maximum_distance")
    if type(radius) not in (int, float) or not math.isfinite(radius) or radius <= 0:
        raise ValueError("measured/fixture library support radius required")
    for entry in export["questions"]:
        tasks._verify_task_digest(entry["task"])
        if entry["task"]["schema"] != tasks.RUNNABLE_SCHEMA:
            raise ValueError("runnable neutral task required")
    physical = cb._physical_rows(export)
    index = {(r["candidate"], r["condition"]): r for r in physical}
    rows, seen, groups = material["rows"], set(), {}
    if len(rows) != len(index):
        raise ValueError("complete library inventory required")
    for r in rows:
        key = (r["candidate"], r["condition"])
        if key not in index or key in seen:
            raise ValueError("duplicate/unmatched library material")
        seen.add(key)
        coordinates = [index[key]["action"][f] for f in fields]
        if r["coordinates"] != coordinates or any(
            not math.isfinite(v) for v in coordinates
        ):
            raise ValueError(
                "physical descriptors must match action, not candidate IDs"
            )
        if (
            not r.get("pattern_group")
            or groups.setdefault(r["pattern_group"], coordinates) != coordinates
        ):
            raise ValueError("equivalent patterns must share a holdout group")
        if (
            not r.get("library_source")
            or not r.get("fine_source")
            or r["library_source"] == r["fine_source"]
        ):
            raise ValueError("separate library/fine evidence required")
        if set(r["library_values"]) != set(index[key]["values"]) or any(
            not math.isfinite(v) for v in r["library_values"].values()
        ):
            raise ValueError(
                "complete order/decision observables required, never efficiency-only safety"
            )
    if len({tuple(v) for v in groups.values()}) != len(groups):
        raise ValueError("one physical pattern cannot split fold groups")
    fine = {r["fine_source"] for r in rows}
    if any(r["library_source"] in fine for r in rows):
        raise ValueError("library may not borrow any fine panel source")
    return rows


def measure(export, *, material, method="library_lookup"):
    if method not in ("library_lookup", "library_rbf"):
        raise ValueError("registered lookup or full-output map required")
    rows = validate(export, material)
    predictions, screens, fits = {}, [], []
    for target in rows:
        train = [
            r
            for r in rows
            if r["pattern_group"] != target["pattern_group"]
            and r["condition"] == target["condition"]
        ]
        quantities = sorted(target["library_values"])
        start, cpu = time.perf_counter(), time.process_time()
        model = None
        if method == "library_rbf":
            try:
                model = cb.CurveSurface(
                    [r["coordinates"] for r in train],
                    [[r["library_values"][q] for q in quantities] for r in train],
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
        nearest = sorted(
            (math.dist(target["coordinates"], r["coordinates"]), i)
            for i, r in enumerate(train)
        )
        if nearest and nearest[0][0] <= material["maximum_distance"]:
            if method == "library_lookup":
                # Average exactly equidistant library entries; don't choose a
                # reference-aware winner from an arbitrary candidate-ID tie.
                neighbors = [
                    train[i]
                    for d, i in nearest
                    if math.isclose(d, nearest[0][0], rel_tol=1e-12, abs_tol=0)
                ]
                predictions[key] = {
                    q: sum(r["library_values"][q] for r in neighbors) / len(neighbors)
                    for q in quantities
                }
            elif model is not None:
                try:
                    predictions[key] = dict(
                        zip(
                            quantities,
                            map(float, model.predict([target["coordinates"]])[0]),
                        )
                    )
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
                "status": "PREDICTED" if key in predictions else "ABSTAINED",
                "fit_cost": fit,
                "query_cost": query,
            }
        )
    return {
        "schema": "carbon.development-metagrating-baseline-report.v1",
        "family": FAMILY,
        "scope": export["scope"],
        "method": method,
        "reference_solves_launched": 0,
        "held_out_unit": "WHOLE_CANONICAL_PATTERN_ALL_CONDITIONS",
        "pointwise": cb.pointwise_errors(export, predictions),
        "decision": cb.decision_report(export, predictions),
        "equal_budget_screening": pb.screening_export(export, predictions, screens),
        "fit_cost": cb._cost(fits),
        "retained_costs": material.get("costs"),
        "unknown_costs": (
            [
                "image_startup",
                "library_acquisition",
                "reference_refinement",
                "retained_verification",
                "money",
            ]
            if material.get("costs") is None
            else []
        ),
        "v4": "UNRESOLVED_NO_MATCHED_CARBON_ARM",
        "uncertainty": "NOT_QUALIFIED_SAFETY_BOUNDS",
    }
