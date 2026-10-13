"""Public battery-interface SYNTHETIC fixtures; never battery physics evidence.

Run `python -m carbon.product.envelope_guard.demo --iterations 500` for a
bounded toy full-query timing report. No solver, training or network I/O.
Fixture authoring/construction reads registered public code-verification links.
All numerical policies/calibrations/validity here are synthetic test inputs.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import platform
import statistics
import sys
import time

from carbon.challenge_validator import validity
from carbon.product.envelope_guard import (
    CONTRACT_SCHEMA,
    ENVELOPE_SCHEMA,
    POLICY_SCHEMA,
    REFERENCE_SCHEMA,
    EnvelopeGuard,
    ModelBinding,
    Prediction,
    development_pins,
)
from carbon.product.envelope_guard.configuration import digest
from carbon.trust_map.core import PANEL_SCHEMA

QUERY = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.25}
UNITS = {"c1": "C-rate", "c2": "C-rate", "t_amb_c": "C", "soc0": "fraction"}
CODE_VERIFICATION_IMAGE = (
    "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
)
CODE_VERIFICATION_CRITERIA = (
    "sha256:2182e04bce3612f898e00184ce1e491cca8a54334192e35c4f2cd6fc1d1870c5"
)


def toy_prediction(query):
    """Arithmetic shapes only. No electrochemistry/thermal or feasibility claim."""
    from carbon.battery.domain import CAPACITY_CYCLES, GRID_POINTS

    return Prediction(
        {
            "voltage_v": [3.0 + i * 0.001 for i in range(GRID_POINTS)],
            "temperature_c": [query["t_amb_c"] + i * 0.01 for i in range(GRID_POINTS)],
            "plating_margin_v": 0.02,
            "capacity_ah": [2.0 - i * 0.001 for i in CAPACITY_CYCLES],
        }
    )


def fixture_inputs(predict=toy_prediction, *, query=None):
    """Synthetic records around public interface constants, not an owner policy."""
    from carbon.battery.domain import INPUT_BOUNDS
    from carbon.battery.trust_map import battery_spec, build_battery_maps

    query = dict(QUERY if query is None else query)
    # Use the registered v2 metadata route; observations remain pure arithmetic.
    # Code-verification identity is not acceptance for the real battery use.
    image = CODE_VERIFICATION_IMAGE
    model = ModelBinding(
        "toy-battery-interface",
        digest({"kind": "toy-artifact-v1"}),
        digest({"kind": "toy-runtime-v1"}),
        predict,
    )
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "inputs": {
            name: {"low": low, "high": high, "unit": UNITS[name]}
            for name, (low, high) in INPUT_BOUNDS.items()
        },
    }
    reference_envelope = copy.deepcopy(envelope)
    reference_envelope["version"] = "synthetic-reference-fixture-v1"
    # A deliberately larger SYNTHETIC route tests VERIFY; no real extension.
    reference_envelope["inputs"]["c1"]["high"] = 2.5
    outputs = battery_spec()["outputs"]
    laws = []
    for name, kind, spec, unit in (
        (
            "fixture-initial-temperature",
            "initial_condition",
            {"output": "temperature_c", "input": "t_amb_c"},
            "C",
        ),
        (
            "fixture-voltage-bound",
            "bound",
            {"output": "voltage_v", "low": 2.5, "high": 4.2},
            "V",
        ),
        (
            "fixture-rest-prefix",
            "prefix_invariance",
            {"output": "temperature_c", "inputs": ["c1", "c2"], "points": 4},
            "C",
        ),
    ):
        laws.append(
            {
                "id": name,
                "type": kind,
                "status": "ADOPTED",
                "spec": spec,
                "adoption_ref": digest({"synthetic_adoption_fixture": name}),
                "calibration": {
                    "image_digest": image,
                    "record_digest": digest({"synthetic_calibration_fixture": name}),
                    "reference_error": 0.001,
                    "tolerance": 0.01,
                    "unit": unit,
                },
            }
        )
    contract = {
        "schema": CONTRACT_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "challenge": "battery-interface-fixture",
        "family": "battery-v3",
        "reference_image": image,
        "outputs": outputs,
        "laws": laws,
    }
    reference = {
        "schema": REFERENCE_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "image_digest": image,
        "code_verification_ref": digest({"synthetic_code_verification": "not-MMS"}),
        "owner_acceptance_ref": digest({"synthetic_acceptance": "not-an-owner-record"}),
        "status": "READY",
        "acceptance_scope": {
            "family": "battery-v3",
            "observables": list(outputs),
            "conditions": {},
        },
    }
    ids = ["synthetic-first", "synthetic-second"]
    observations = {i: toy_prediction(query).outputs for i in ids}
    panel = {
        "schema": PANEL_SCHEMA,
        "disclosure": {
            "kind": "PUBLIC",
            "evidence": "SYNTHETIC_FIXTURE_ONLY",
            "source_sha256": digest({"synthetic_panel": "v2"})[7:],
        },
        "reference_image": image,
        "reference_verification": {
            "family": "battery-v3",
            "criteria_digest": CODE_VERIFICATION_CRITERIA,
            "image_digest": image,
            "evidence": "SYNTHETIC_FIXTURE_ONLY; NOT_REAL_BATTERY_USE_ACCEPTANCE",
        },
        "cases": [
            {"id": i, "inputs": dict(query), "reference": observations[i]} for i in ids
        ],
        "models": {
            model.model_id: copy.deepcopy(observations),
            "toy-second": copy.deepcopy(observations),
        },
        "top_models": [model.model_id, "toy-second"],
    }
    trust_map = build_battery_maps(panel)[model.model_id]
    model_validity = validity.NoPropertyModel(
        "Synthetic arithmetic interface fixture, not a physical model"
    )
    reference_validity = validity.NoPropertyModel(
        "Synthetic fixture reference, not a solver or physical applicability record"
    )
    materials = {
        "contract": contract,
        "envelope": envelope,
        "reference_envelope": reference_envelope,
        "trust_map": trust_map,
        "reference": reference,
        "model": model,
        "model_validity": model_validity,
        "reference_validity": reference_validity,
    }
    materials["policy"] = {
        "schema": POLICY_SCHEMA,
        "scope": "DEVELOPMENT",
        "version": "fixture-v1",
        "basis": "SYNTHETIC_FIXTURE",
        "authority_ref": digest({"synthetic_policy": "v1"}),
        "pins": development_pins(**materials),
        "probe_steps": {"c1": 0.01, "c2": 0.01, "t_amb_c": 0.1, "soc0": 0.01},
        "max_model_calls": 9,
        "min_cell_count": 2,
        "map_limits": {
            name: {
                "unit": desc["unit"],
                "max_error_p90": 0.1,
                "max_disagreement_p90": 0.1,
            }
            for name, desc in outputs.items()
        },
        "uncertainty": {
            "mode": "EXPLICIT_NO_INTERVALS",
            "calibration": None,
            "max_width": None,
        },
        "laws": {"mode": "REQUIRED_ADOPTED"},
        "latency_target_ms": None,
    }
    return materials


def repin(materials):
    """Fixture authoring after an intentional mutation; not an acceptance operation."""
    if materials["policy"] is not None:
        materials["policy"]["pins"] = development_pins(
            **{key: value for key, value in materials.items() if key != "policy"}
        )
    return materials


def timing_report(iterations):
    if type(iterations) is not int or not 1 <= iterations <= 10_000:
        raise ValueError("bounded fixture iteration count required")
    inputs = fixture_inputs()
    construction_started = time.perf_counter_ns()
    guard = EnvelopeGuard(**inputs)
    construction_ms = (time.perf_counter_ns() - construction_started) / 1_000_000
    for _ in range(20):
        guard.evaluate(QUERY, units=UNITS)
    whole, model_only = [], []
    receipts = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        toy_prediction(QUERY)
        model_only.append((time.perf_counter_ns() - start) / 1_000_000)
        start = time.perf_counter_ns()
        receipt = guard.evaluate(QUERY, units=UNITS)
        whole.append((time.perf_counter_ns() - start) / 1_000_000)
        receipts.append(receipt)
    ordered = sorted(whole)
    return {
        "schema": "carbon.product.guard-toy-latency.v1",
        "scope": "DEVELOPMENT",
        "evidence_basis": "SYNTHETIC_FIXTURE",
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "machine": platform.machine(),
        "iterations": iterations,
        "warmup": 20,
        "guard_construction_ms": construction_ms,
        "construction_basis": "document snapshot/schema/identity/native-map validation and indexing, excluding fixture authoring",
        "full_query_includes": [
            "query-validation",
            "deterministic-probes",
            "model-calls",
            "map-law-interval-checks",
            "receipt-hash",
        ],
        "full_query_ms": {
            "median": statistics.median(whole),
            "p95": ordered[math.ceil(0.95 * iterations) - 1],
            "max": max(whole),
        },
        "one_toy_model_call_median_ms": statistics.median(model_only),
        "p95_method": "nearest-rank empirical sample, not an uncertainty interval",
        "model_calls_per_full_query": sorted(
            {r["probes"]["model_calls"] for r in receipts}
        ),
        "verdict_counts": {
            kind: sum(r["verdict"] == kind for r in receipts)
            for kind in ("TRUST", "VERIFY", "REFUSE")
        },
        "identities": receipts[0]["identities"],
        "decision_digest_count": len({r["decision_digest"] for r in receipts}),
        "production_latency_target_ms": None,
        "target_authority": "HUMAN_INPUT",
        "qualification_claim": False,
        "limits": "Toy adapter on this native host only; no real inference, solver, physical validation, latency promise or product qualification",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=500)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            timing_report(args.iterations), indent=2, sort_keys=True, allow_nan=False
        )
    )


if __name__ == "__main__":
    main()
