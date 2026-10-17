"""SYNTHETIC public battery-interface workflow; no real solver or training."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

from carbon.battery.value import decision
from carbon.design_search import equal_budget
from carbon.product.envelope_guard import Prediction
from carbon.product.envelope_guard.configuration import digest
from carbon.product.envelope_guard.demo import QUERY, UNITS, fixture_inputs, repin

from . import (
    BUDGET_SCHEMA,
    QUESTION_SCHEMA,
    DecisionAssistant,
    Measurement,
    MeasurementBinding,
    ReferenceBinding,
    ReferenceObservation,
    assess_finite_bank,
)

MEASUREMENT_CONTRACT = {
    "objective": {"threshold_v": 4.0, "charge_start_s": 120, "window_s": 3600}
}


def synthetic_prediction(query, *, reference=False):
    """Shapes and optimizer failure only; these are not battery equations."""
    from carbon.battery.domain import CAPACITY_CYCLES, GRID_POINTS

    c1, ambient = query["c1"], query["t_amb_c"]
    return Prediction(
        {
            "voltage_v": [
                min(4.2, 3.5 + 0.8 * c1 * i / (GRID_POINTS - 1))
                for i in range(GRID_POINTS)
            ],
            "temperature_c": [
                ambient + (20.0 if reference else 4.0) * c1 * i / (GRID_POINTS - 1)
                for i in range(GRID_POINTS)
            ],
            "plating_margin_v": 0.02,
            "capacity_ah": [2.0 - 0.001 * i for i in CAPACITY_CYCLES],
        }
    )


def battery_measure(outputs):
    # KEEP the public battery observer, separate from all protected question
    # loaders. Limits below are explicitly synthetic test inputs.
    normalized = dict(outputs)
    margin = normalized["plating_margin_v"]
    normalized["plating_margin_v"] = (
        margin[0] if isinstance(margin, (list, tuple)) else margin
    )
    quantities = decision.measure(MEASUREMENT_CONTRACT, normalized)
    return Measurement(
        quantities["time_to_cv_onset_s"],
        {
            "temperature": quantities["peak_temperature_c"],
            "plating": quantities["plating_margin_v"],
            "reach_cv": float(quantities["time_to_cv_onset_s"] is not None),
        },
        {"objective": "s", "temperature": "C", "plating": "V", "reach_cv": "fraction"},
    )


def fixture():
    """All limits, costs, policies, artifact identities and references are toys."""
    materials = fixture_inputs(synthetic_prediction)
    model = replace(
        materials.pop("model"),
        artifact_digest=digest({"synthetic_model": "optimistic-temperature-v1"}),
    )
    repin({**materials, "model": model})
    measurement = MeasurementBinding(
        "fixture-battery-measure-v1", digest(MEASUREMENT_CONTRACT), battery_measure
    )
    q = {
        "schema": QUESTION_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "basis": "SYNTHETIC_FIXTURE",
        "authority_ref": digest({"fixture_authority": "not-owner"}),
        "question_id": "synthetic-public-battery-interface",
        "population_ref": digest({"fixture_population": "finite-bank"}),
        "proposal_ref": digest({"fixture_proposal": "declared-order"}),
        "weighting_ref": digest({"fixture_weights": "no-population-claim"}),
        "measurement_id": measurement.measurement_id,
        "measurement_digest": measurement.code_digest,
        "objective": {"direction": "min", "unit": "s"},
        "units": dict(UNITS),
        "constraints": [
            {
                "id": "temperature",
                "relation": "le",
                "limit": 44.0,
                "unit": "C",
                "reference_band": 0.0,
            },
            {
                "id": "plating",
                "relation": "ge",
                "limit": 0.0,
                "unit": "V",
                "reference_band": 0.0,
            },
            {
                "id": "reach_cv",
                "relation": "ge",
                "limit": 1.0,
                "unit": "fraction",
                "reference_band": 0.0,
            },
        ],
        "actions": [
            {"id": name, "query": {**QUERY, "c1": rate}}
            for name, rate in (("slow", 0.8), ("base", 1.0), ("fast", 1.4))
        ],
        "k": 3,
        "search_policy": "FINITE_BANK_DECLARED_ORDER_V1",
    }
    b = {
        "schema": BUDGET_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "basis": "SYNTHETIC_FIXTURE",
        "authority_ref": digest({"fixture_budget": "not-production"}),
        "cap": {"solver_evaluations": 3, "wall_s": 30.0, "core_s": 30.0},
        "max_guard_queries": 3,
        "max_model_calls": 27,
        "guard_bound": {"wall_s": 1.0, "core_s": 1.0},
        "reference_bound": {"wall_s": 1.0, "core_s": 1.0},
        "startup_cost": {"wall_s": 0.0, "core_s": 0.0},
    }
    image = materials["reference"]["image_digest"]

    def solve(query):
        query_hash = digest({"query": query, "units": UNITS})
        return ReferenceObservation(
            "OK",
            synthetic_prediction(query, reference=True),
            query_hash,
            image,
            digest({"synthetic_reference": query_hash, "version": "v1"}),
        )

    reference = ReferenceBinding(
        image,
        digest(materials["reference"]),
        digest({"synthetic_reference_runtime": "v1"}),
        "SYNTHETIC_FIXTURE",
        "READY",
        solve,
    )
    return {
        "question_law": q,
        "model": model,
        "guard_inputs": materials,
        "measurement": measurement,
        "budget": b,
        "reference": reference,
    }


def comparison_replay(result, assessment):
    """KEEP native equal-budget comparison; explicitly assumed toy costs.

    Five replicated synthetic bands exercise its battery route's shape. They
    are not the actual v3 question law, five independent observations, or an
    executed physics/latency experiment. Frozen verification order is the arm.
    """
    rows = result["candidates"]
    order = [r["id"] for r in result["verification_plan"]]
    truth = {r["id"]: r["reference"] for r in assessment["rows"]}
    actions = []
    for i, row in enumerate(rows):
        observed = truth[row["id"]]
        value = observed.get("objective") if observed["status"] == "FEASIBLE" else None
        native_ref = {"status": observed["status"], "value": value}
        actions.append(
            {
                "design_id": row["id"],
                "reference": {
                    **native_ref,
                    "per_index": {
                        band: dict(native_ref) for band in ("5", "15", "25", "35", "40")
                    },
                },
                "solve_cost": {"wall_s": 2.0, "core_s": 2.0},
                "planning_bound": {"wall_s": 2.0, "core_s": 2.0},
                "screen_rank": {"model": order.index(row["id"]), "baseline": i},
            }
        )
    panel = equal_budget.seal(
        {
            "schema": equal_budget.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": "battery-v3",
            "source_digest": result["search_commitment_digest"],
            "decision_rule_id": "synthetic-assistant-interface-replay-v1",
            "objective": {
                "direction": "min",
                "unit": "s",
                "index_weights": {band: 0.2 for band in ("5", "15", "25", "35", "40")},
            },
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "budgets": [{"wall_s": v, "core_s": v} for v in (2.1, 4.1, 6.1)],
            "registrations": {
                "solver_search": "fixture-declared-order",
                "model_screen": "fixture-frozen-verification-order",
                "baseline_screen": "fixture-declared-order",
                "cost_plan": "fixture-assumed-costs",
            },
            "jobs": [
                {
                    "job_id": "synthetic-question",
                    "cluster_id": "synthetic-single-cluster",
                    "candidates": actions,
                    "solver_order": [r["id"] for r in rows],
                    "screen_cost": {
                        "model": {"wall_s": 0.1, "core_s": 0.1},
                        "baseline": {"wall_s": 0.1, "core_s": 0.1},
                    },
                }
            ],
        }
    )
    return equal_budget.compare(
        panel, bootstrap_replicates=100, confidence=0.95, seed=0
    )


def demonstrate():
    inputs = fixture()
    assistant = DecisionAssistant(**inputs)
    frozen_result = assistant.run()
    result = frozen_result.to_dict()
    assessment = assess_finite_bank(
        assistant, frozen_result, reference=inputs["reference"], budget=inputs["budget"]
    )
    return {
        "scope": "DEVELOPMENT",
        "basis": "SYNTHETIC_FIXTURE_PUBLIC_BATTERY_INTERFACE",
        "result": result,
        "assessment": assessment,
        "equal_budget_replay": comparison_replay(result, assessment),
        "real_battery_comparison": {
            "status": "GAP",
            "reasons": ["SOLVER_NOT_ACCEPTED", "CPU_CORE_SECONDS_MISSING"],
            "regret": None,
            "accepted": False,
        },
        "qualification_claim": False,
    }


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    print(json.dumps(demonstrate(), sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
