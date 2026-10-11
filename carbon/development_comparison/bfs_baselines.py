"""Held-geometry-out PUBLIC_DEVELOPMENT BFS cheap comparisons, no solves.

Reuse #994's neutral task judge, decision report and cost/ranking export.
The cached coarse-RANS map is NOT the held-out fine reference. The sudden
expansion correlation is only a qualified-applicability control, not a
replacement for general recovery-contour RANS.
"""

from __future__ import annotations

import math
import time

from carbon.design_search import tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb

FAMILY = "backward-facing-step"


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
    return {
        "schema": "carbon.development-bfs-baseline-report.v1",
        "family": FAMILY,
        "scope": export["scope"],
        "reference_solves_launched": 0,
        "held_out_unit": "WHOLE_GEOMETRY_ALL_CONDITIONS",
        "pointwise": cb.pointwise_errors(export, predicted),
        "decision": cb.decision_report(export, predicted),
        "equal_budget_screening": pb.screening_export(export, predicted, screens),
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
