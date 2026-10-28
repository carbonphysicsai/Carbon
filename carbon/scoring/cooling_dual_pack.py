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
  ``scale_status`` is provenance, not a control: nothing reads it to gate
  anything; DEVELOPMENT confinement is the binder's.
- The score pack's leg minimums follow that packet's rule: the rebuilt
  learned-krr-v1 baseline's own legs when it scores, else none.

It is a new evaluation version; its results are not compared with the
historical replay. A and D are measured by ``cooling_dual_measurement``.
"""

from __future__ import annotations

import functools
import hashlib
import io
import json
import math
import sys
from pathlib import Path

from carbon.scoring import cooling_dual_measurement as cdm
from carbon.scoring import cooling_physics, probe_design
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring.physical_dual_pack import sha as _sha

CHALLENGE = "chip-cold-plate"
VERSION = "1.0"
CASE_ID = "cooling-development-bank-48"
#: v2: the paired repeat is the identical graded procedure (per-case pairs,
#: Validator 2026-10-19), the registered repeat tolerance unchanged; v1 packs
#: (batched repeats) stay as history and are not re-scored.
EVALUATION_VERSION = "cooling-dual-development-bank-48-v2"
#: Every registered Challenge version: its evaluation version and case id
#: (step-2 batch, STEP2_BATCH_VERSIONS_20261020: 1.1 serves allowlist v6 with no
#: step caps; measurement unchanged). No default version.
VERSIONS = {
    "1.0": (EVALUATION_VERSION, CASE_ID),
    "1.1": ("cooling-dual-development-bank-48-v3", CASE_ID),
    # Allowlist v7's catalog version (Validator, 2026-10-20): the predecessor's
    # measurement under its evaluation version; only the served allowlist differs.
    "1.2": ("cooling-dual-development-bank-48-v3", CASE_ID),
}
#: A sealed exam batch's evaluation version, per Challenge version (Validator,
#: 2026-10-20): Cooling 1.1's sealed batches, served on 1.1 and 1.2.
#: v2: Design is D = min(V, C) with the physics half; v1 stays as history.
SEALED_EVALUATION_VERSION = "cooling-dual-sealed-batch-16-v2"
#: Versions whose output interface is Cooling's own graded by the raw sealed adapter.
#: 1.3 changes the output interface (the law-safe encoding), so it is graded by
#: `cooling_encoded_dual_pack.sealed_adapter`, which decodes first: an interface change
#: never rides in this table.
SEALED_VERSIONS = {version: SEALED_EVALUATION_VERSION for version in ("1.1", "1.2")}
OUTPUT = {"quantity": "peak_c,profile_c[30],pressure_drop_pa", "unit": "degC,degC,Pa"}
FILES = (
    "cooling_dual_pack.py",
    "cooling_dual_measurement.py",
    "critical_fidelity.py",
    "design_fidelity.py",
    "physics_half.py",
    "probe_design.py",
    "cooling_physics.py",
)
#: Legs a measured baseline run sets minimums for (default rule).
MINIMUM_LEGS = ("A", "D")
Refused = cdm.CoolingMeasurementRefused
validate_definition = cdm.validate_definition
_ADAPTER = sys.modules[__name__]
_ROOT = Path(__file__).resolve().parents[2]
#: The counted-dual packet this adapter ports, committed byte-identical as
#: carbon/challenge_kit/data/optimizer-counted-dual-packets-20261018.py.txt
#: (data, never imported or executed; a test checks the values below).
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
#: Leg-minimum rules, each its own evaluation version (so its own bank key).
#: ``baseline_legs`` is the packet's rule and the reproduced default (the same
#: rule as Motor); ``baseline_a_no_d_minimum`` is the Validator's DEVELOPMENT
#: comparison variant (2026-10-19). Adopting either is the owner's call.
LEG_MINIMUM_RULES = {
    "baseline_legs": (
        EVALUATION_VERSION,
        (
            "The rebuilt learned-krr-v1 baseline's A and D are the leg minimums. "
            "Its D is 1.0, so the D leg is pass/fail: any verified-feasible pick "
            "with positive regret (a safe but suboptimal design) fails "
            "REQUIRED_LEG_MINIMUM_FAILED."
        ),
    ),
    "baseline_a_no_d_minimum": (
        EVALUATION_VERSION + "-no-d-minimum",
        (
            "DEVELOPMENT comparison variant: the baseline's A is the A minimum "
            "and D has no minimum, so a safe but suboptimal verified pick keeps "
            "its continuous D. Not adopted."
        ),
    ),
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


def definition(*, bank, train_raw, rule="baseline_legs"):
    """Cooling's registered accuracy definition fields (the shared module adds
    the producer, TRAIN and bank pins)."""
    from carbon.challenge_kit import physical_public_train
    from carbon.cold_plate import exam

    slices = physical_public_train.numeric_interface_document(CHALLENGE)[
        "target_slices"
    ]
    # The bank says which it is: a sealed batch is one decision_sealed_grid
    # cohort; anything else is checked against the development cohorts.
    probes = sum(1 for c in bank["cohorts"] if c == probe_design.PROBE_COHORT)
    sealed = {c for c in bank["cohorts"] if c != probe_design.PROBE_COHORT} == {
        cdm.SEALED_COHORT
    }
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
        **(
            {
                "bank_kind": "sealed_batch",
                "reference_evidence_sha256": "sha256:"
                + hashlib.sha256(bank["solver_evidence"]).hexdigest(),
                "reductions": list(cdm._SEALED_REDUCTIONS),
                "cohort_counts": {
                    cdm.SEALED_COHORT: sum(
                        1 for c in bank["cohorts"] if c == cdm.SEALED_COHORT
                    )
                },
                **(
                    {"population": cdm.PRACTICE_POPULATION}
                    if bank.get("population") == cdm.PRACTICE_POPULATION
                    else {}
                ),
                "critical": cdm.critical_block(_MEASUREMENT["D_scale_W"]),
                "probes": {"cohort": probe_design.PROBE_COHORT, "rows": probes},
                **({"physics": cooling_physics.block(train_raw)} if probes else {}),
            }
            if sealed
            else {
                "reductions": ["all48", "worst_geometry", "boundary"],
                "cohort_counts": dict(cdm.COHORT_COUNTS),
            }
        ),
        "A_reducer": "minimum",
        "target_slices": {k: list(v) for k, v in slices.items()},
        "leg_minimum_rule": rule,
        "paired_repeat_procedure": "per_case",
        "leg_minimum_note": LEG_MINIMUM_RULES[rule][1],
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
    if "probes" not in definition:
        return cdm.measure(
            bank=bank_rows,
            outputs=outputs,
            repeats=repeats,
            definition=definition,
            contract=contract,
            train=_train_records(train_raw, names),
        )
    cells = [
        i for i, r in enumerate(bank_rows) if r["cohort"] != probe_design.PROBE_COHORT
    ]
    probes = [
        i for i, r in enumerate(bank_rows) if r["cohort"] == probe_design.PROBE_COHORT
    ]
    if (
        len(probes) != definition["probes"]["rows"]
        or len(outputs) != len(bank_rows)
        or not all(len(r) == len(bank_rows) for r in repeats)
    ):
        raise Refused("cooling_bank_cohort")
    measured = cdm.measure(
        bank=[bank_rows[i] for i in cells],
        outputs=[outputs[i] for i in cells],
        repeats=[[r[i] for i in cells] for r in repeats],
        definition=definition,
        contract=contract,
        train=_train_records(train_raw, names),
    )
    internal = measured.pop("_cells", None)
    if internal is None:
        return measured
    return cooling_physics.apply(
        measured,
        a_scale=definition["A_scale"],
        cell_rows=[bank_rows[i] for i in cells],
        cell_outputs=[outputs[i] for i in cells],
        definition=definition,
        train_raw=train_raw,
        probe_rows=[bank_rows[i] for i in probes],
        probe_outputs=[outputs[i] for i in probes],
        **internal,
    )


def _baseline_outputs(bank_rows, train):
    """The packet's learned-krr-v1 baseline, rebuilt from public TRAIN, on the
    bank (log-rise/log-pressure targets, the study's length and ridge), with
    its linear algebra pinned to one thread."""
    return physical.single_threaded(
        "carbon.scoring.cooling_dual_pack:_baseline_here",
        cases=[row["inputs"] for row in bank_rows],
        train=train,
    )


def _baseline_here(*, cases, train):
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
        "hard_gates": list(cdm.gates_for(definition)),
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
                        k: "PASS" if measured["gates"][k] else "FAIL"
                        for k in cdm.gates_for(definition)
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
    rule = definition.get("leg_minimum_rule")
    if rule not in LEG_MINIMUM_RULES:
        raise Refused("cooling_leg_minimum_rule")
    if row["status"] == "SCORED_DEVELOPMENT_CANDIDATE":
        for leg in ("A", "D") if rule == "baseline_legs" else ("A",):
            body["legs"][leg]["minimum"] = row["legs"][leg]
    return body


class _Variant:
    """This adapter under a non-default leg-minimum rule: its own evaluation
    version and definition; everything else (measurement, producer) is the
    default adapter's."""

    #: The calibration run is graded under the default rule's calibration
    #: pack; its legs serve every rule.
    CALIBRATION_ADAPTER = _ADAPTER

    def __init__(self, rule):
        self.rule = rule
        self.EVALUATION_VERSION = LEG_MINIMUM_RULES[rule][0]
        self.MINIMUM_LEGS = ("A", "D") if rule == "baseline_legs" else ("A",)

    def definition(self, **kwargs):
        return definition(**kwargs, rule=self.rule)

    def __getattr__(self, name):
        return getattr(_ADAPTER, name)


def adapter(rule="baseline_legs"):
    if rule not in LEG_MINIMUM_RULES:
        raise ValueError("unknown cooling leg-minimum rule")
    return _ADAPTER if rule == "baseline_legs" else _Variant(rule)


def sealed_adapter(version):
    """The adapter for a sealed exam batch of exactly Challenge ``version``
    (``SEALED_VERSIONS``), or None: no default. The definition reads the bank
    kind from the bank's cohort, so measurement is this module's.

    Cooling 1.3 changes the output interface (the law-safe encoding), so its sealed
    adapter is the one that decodes first (``cooling_encoded_dual_pack``): the one
    dispatch point stays here, and no shared producer file routes it."""
    if version in ("1.3", "1.5", "1.6"):
        from carbon.scoring import cooling_encoded_dual_pack

        return cooling_encoded_dual_pack.sealed_adapter(version)
    if type(version) is not str or version not in SEALED_VERSIONS:
        return None
    return physical.Variant(_ADAPTER, version, SEALED_VERSIONS[version], CASE_ID)


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(*, rule="baseline_legs", **kwargs):
    return physical.pack_documents(adapter(rule), **kwargs)


def write_development_pack(root, rule="baseline_legs", **platform):
    return physical.write_development_pack(adapter(rule), root, **platform)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete Cooling DEVELOPMENT evaluation pack."
    )
    physical.add_builder_arguments(parser)
    parser.add_argument(
        "--leg-minimum-rule", choices=sorted(LEG_MINIMUM_RULES), default="baseline_legs"
    )
    args = parser.parse_args(argv)
    print(
        write_development_pack(
            args.root.resolve(), args.leg_minimum_rule, **physical.builder_options(args)
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
