"""Cooling's adapter for the shared physical dual pack and producer.

DEVELOPMENT only, exposed 48-cell development bank: never a hidden-exam or
paying claim. Ported from the counted-dual Cooling packet
(OPTIMIZER_COUNTED_DUAL_PACKETS_20261018, ``cooling``, sha256 b6a1ce3e...) and
regenerated from committed sources; no operator output is copied.

- The physics contract is that packet's exact native source binding (the
  periodic straight-channel cell, its native outputs, the sha256 of
  ``domain``/``exam``/``openfoam`` and the reference solver image) in the
  ``{version, definition}`` envelope.
- The accuracy definition carries that packet's measurement: its scales are
  PROSPECTIVE_EXPERIMENT_NOT_ADOPTED values, a development candidate.
- The score pack's leg minimums follow that packet's rule: the rebuilt
  learned-krr-v1 baseline's own legs when it scores, else none.

It is a new evaluation version; its results are not compared with the
historical replay. A and D are measured by ``cooling_dual_measurement``.
"""

from __future__ import annotations

import functools
import io
import json
import math
import sys
from pathlib import Path

from carbon.scoring import cooling_dual_measurement as cdm
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring.physical_dual_pack import sha as _sha

CHALLENGE = "chip-cold-plate"
VERSION = "1.0"
CASE_ID = "cooling-development-bank-48"
EVALUATION_VERSION = "cooling-dual-development-bank-48-v1"
OUTPUT = {"quantity": "peak_c,profile_c[30],pressure_drop_pa", "unit": "degC,degC,Pa"}
FILES = ("cooling_dual_pack.py", "cooling_dual_measurement.py")
Refused = cdm.CoolingMeasurementRefused
validate_definition = cdm.validate_definition
_ADAPTER = sys.modules[__name__]
_ROOT = Path(__file__).resolve().parents[2]
#: The counted-dual packet this adapter ports (operator material, not copied).
SOURCE_SCRIPT_SHA256 = (
    "sha256:b6a1ce3e5c242dbe3595e84d31fd0a0586f6b48baa3ed9eb92bf7a43ab0d6917"
)
STUDY_CONFIG = "docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json"
REFERENCE_REPLAY = "docs/development/evidence/track-b-replay/ai-cooling-counted-v1.json"
PHYSICS_VERSION = "cooling-counted-dual-physics-binding-20261018"
#: The packet's measurement values, verbatim (its ``measurement`` document):
#: A = min 1/(1+e/A_scale); D = 1/(1+regret_W/D_scale_W); six verification
#: condition lookups. Prospective, not adopted.
_MEASUREMENT = {
    "A_scale": 1.0,
    "D_scale_W": 0.025,
    "verification_condition_budget": 6,
    "query_budget_including_repeats": 96,
    "scale_status": "PROSPECTIVE_EXPERIMENT_NOT_ADOPTED",
}


def _file_sha(relative):
    return _sha((_ROOT / relative).read_bytes())


@functools.cache
def _replay():
    return json.loads((_ROOT / REFERENCE_REPLAY).read_bytes())


def physics_contract():
    """The packet's exact native source binding, enveloped."""
    return {
        "version": PHYSICS_VERSION,
        "definition": {
            "scope": "periodic-straight-channel-cell-v1",
            "definition_kind": "EXACT_EXISTING_NATIVE_SOURCE_BINDING_NOT_QUALIFICATION",
            "native_outputs": {
                "peak_c": ["C", []],
                "profile_c": ["C", [30]],
                "pressure_drop_pa": ["Pa", []],
            },
            "source_sha256": {
                relative: _file_sha(relative)
                for relative in (
                    "carbon/cold_plate/domain.py",
                    "carbon/cold_plate/exam.py",
                    "carbon/cold_plate/openfoam.py",
                )
            },
            "reference_solver_image": _replay()["solver_image"],
        },
    }


def definition(*, bank, train_raw):
    """Cooling's registered accuracy definition fields (the shared module adds
    the producer, TRAIN and bank pins)."""
    from carbon.challenge_kit import physical_public_train
    from carbon.cold_plate import exam

    slices = physical_public_train.numeric_interface_document(CHALLENGE)[
        "target_slices"
    ]
    return {
        "schema": cdm.DEFINITION_SCHEMA,
        "method": cdm.METHOD,
        "source_script_sha256": SOURCE_SCRIPT_SHA256,
        "native_error_source_sha256": _file_sha("carbon/cold_plate/exam.py"),
        "native_observer_source_sha256": _file_sha(
            "carbon/cold_plate/customer_decision.py"
        ),
        "study_config_sha256": _file_sha(STUDY_CONFIG),
        "source_replay_sha256": _file_sha(REFERENCE_REPLAY),
        "components": list(exam.COMPONENTS),
        "reductions": ["all48", "worst_geometry", "boundary"],
        "A_reducer": "minimum",
        "cohort_counts": dict(cdm.COHORT_COUNTS),
        "target_slices": {k: list(v) for k, v in slices.items()},
        **_MEASUREMENT,
    }


def _train_records(train_raw, names):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        inputs = np.asarray(data["inputs"], dtype=float)
        targets = np.asarray(data["targets"], dtype=float)
    return [
        {
            "status": "OK",
            "inputs": dict(zip(names, (float(v) for v in x), strict=True)),
            "outputs": {
                "peak_c": float(t[0]),
                "profile_c": [float(v) for v in t[1:31]],
                "pressure_drop_pa": float(t[31]),
            },
        }
        for x, t in zip(inputs, targets, strict=True)
    ]


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    contract = (objective or {}).get("decision_contract")
    if (
        type(contract) is not dict
        or type(limits) is not dict
        or limits.get("constraints") != contract.get("constraints")
    ):
        raise Refused("cooling_limit_or_objective")
    return cdm.measure(
        bank=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        contract=contract,
        train=_train_records(train_raw, names),
    )


def _baseline_outputs(bank_rows, train):
    """The packet's learned-krr-v1 baseline, rebuilt from public TRAIN, on the
    bank (log-rise/log-pressure targets, the study's length and ridge)."""
    import numpy as np

    from carbon import learned_baseline
    from carbon.cold_plate import domain

    spec = json.loads((_ROOT / STUDY_CONFIG).read_bytes())["models"]["learned-krr-v1"]
    x = learned_baseline.scale(
        [r["inputs"] for r in train], domain.INPUTS, domain.INPUT_BOUNDS
    )
    targets = []
    for row in train:
        inlet = row["inputs"]["inlet_c"]
        out = row["outputs"]
        targets.append(
            [math.log(out["peak_c"] - inlet)]
            + [math.log(v - inlet) for v in out["profile_c"]]
            + [math.log(out["pressure_drop_pa"])]
        )
    krr = learned_baseline.KernelRidge(
        x, np.asarray(targets), spec["length"], spec["ridge"]
    )
    cases = [row["inputs"] for row in bank_rows]
    rows = krr.predict(
        learned_baseline.scale(cases, domain.INPUTS, domain.INPUT_BOUNDS)
    )
    flat = []
    for case, y in zip(cases, rows, strict=True):
        inlet = case["inlet_c"]
        profile = [inlet + math.exp(float(v)) for v in y[1:-1]]
        peak = max(inlet + math.exp(float(y[0])), max(profile))
        flat.append([peak, *profile, math.exp(float(y[-1]))])
    return flat


def applied_pack(*, bank_rows, definition, limits, objective, train_raw, names):
    """The packet's dual pack; leg minimums are the rebuilt baseline's own legs
    when it scores as a development candidate, else none."""
    from carbon.scoring import dual_score

    body = {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": CHALLENGE,
        "hard_gates": list(cdm.GATES),
        "legs": {
            leg: {
                "components": [
                    {
                        "metric": physical.METRICS[leg],
                        "unit": "1",
                        "transform": "unit_benefit",
                        "scale": None,
                        "weight": 1.0,
                    }
                ],
                "minimum": None,
            }
            for leg in ("A", "D")
        },
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
        "decision_policy": {
            "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
            "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
            "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        },
    }
    baseline = _baseline_outputs(bank_rows, _train_records(train_raw, names))
    measured = measure(
        bank_rows=bank_rows,
        outputs=baseline,
        repeats=[baseline, baseline],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )
    # Score the baseline under the minimum-free pack with provisional digests;
    # only its status and legs are read.
    provisional = "sha256:" + "0" * 64
    pack = dual_score.register_pack(
        {
            **body,
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
        }
    )
    row = dual_score.score(
        {
            "schema": dual_score.INPUT_SCHEMA,
            "scope": body["scope"],
            "challenge": CHALLENGE,
            "physics_contract_digest": provisional,
            "measurement_contract_digest": provisional,
            "population_role": "P",
            "common_mask_digest": provisional,
            "models": [
                {
                    "artifact_digest": provisional,
                    "gates": {
                        k: "PASS" if measured["gates"][k] else "FAIL" for k in cdm.GATES
                    },
                    "measurements": {
                        physical.METRICS[leg]: (
                            {"status": "RESOLVED", "value": measured[leg], "unit": "1"}
                            if measured[leg] is not None
                            else {
                                "status": "CANDIDATE_INVALID",
                                "value": None,
                                "unit": "1",
                            }
                        )
                        for leg in ("A", "D")
                    },
                    "decision_outcome": measured["decision_outcome"],
                }
            ],
        },
        pack,
    )["models"][0]
    if row["status"] == "SCORED_DEVELOPMENT_CANDIDATE":
        for leg in ("A", "D"):
            body["legs"][leg]["minimum"] = row["legs"][leg]
    return body


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def write_development_pack(root):
    return physical.write_development_pack(_ADAPTER, root)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete Cooling DEVELOPMENT evaluation pack."
    )
    parser.add_argument("root", type=Path, help="new or empty pack directory")
    args = parser.parse_args(argv)
    print(write_development_pack(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
