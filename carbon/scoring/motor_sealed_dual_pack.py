"""Motor grades a sealed exam batch (Validator rulings
VALIDATOR_RULING_MOTOR_SEALED_GRADING_20261022 and MOTOR_GRID_SPLIT; evaluation
version ``motor-dual-sealed-batch-30-v1``; OWNER-MOTOR-EXAM-GRID-01), and
writes the batch's receiver pack.

A sealed Motor batch is a placed grid of 30 cells: 5 designs (Motor's six
geometry inputs) x 6 operating conditions (current density and angle), in one
cohort (``decision_sealed_grid``) whose reference records carry ``design_id``
(``design-0..4``) and ``condition_id`` (``condition-0..5``). It is graded with
Motor's registered decision measure, unchanged, and the total is 0.5 A + 0.5 D
(OWNER-BATTERY-DUAL-SCORE-01):

- **D** is Motor's native fixed-grid workflow at the registered verification
  budget (`motor_dual_measurement._decision`): the top predicted feasible
  designs are verified against the reference, and D is the benefit of the
  verified regret, with the registered ``D_scale``. The grid's design and
  condition ids come from the batch itself.
- **A** is the minimum of the registered unit benefits that exist on a single
  decision grid: the mean f0 loss over all 30 cells, the worst design's mean f0
  loss, and the median dimensionless signed-margin error, each with its
  registered scale. The development measurement's practice, pilot and two
  condition-cohort losses need cohorts a sealed batch does not have. This
  mirrors Cooling's sealed grading (all cells and worst geometry).
- The reference receipt is ``sha256(solver_evidence)`` of the batch's own
  family evidence.
- The native Motor gates run unchanged on every cell.

This module is its own adapter so Motor's development files
(``motor_dual_pack.py``, ``motor_dual_measurement.py``) and every pack bound
to their producer digest are unchanged; this adapter's producer identity covers
Motor's files and this one. Dispatch is by the bank's declared population
(`adapter_for_bank`).

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path
from statistics import fmean

from carbon.motor import customer_decision as decision
from carbon.motor import exam
from carbon.motor import score_candidates as candidates
from carbon.scoring import critical_fidelity as critical
from carbon.scoring import motor_dual_measurement as mdm
from carbon.scoring import motor_dual_pack as _motor
from carbon.scoring import motor_physics, probe_design
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_grid_common as grid_common

CHALLENGE = _motor.CHALLENGE
#: The first sealed Challenge version; 1.2 and 1.3 grade the same batches
#: (Validator, 2026-10-20: they change only the construction source).
VERSION = "1.1"
#: v2: Design is D = min(V, C), the owner's rule (critical_fidelity); v1 graded V
#: alone and stays as history under its own evaluation version, never re-scored.
EVALUATION_VERSION = "motor-dual-sealed-batch-30-v2"
CASE_ID = "motor-sealed-batch-30"
VERSIONS = {
    # 1.4 is graph route v2: construction only, 1.3's sealed batches.
    version: (EVALUATION_VERSION, CASE_ID)
    for version in ("1.1", "1.2", "1.3", "1.4")
}
OUTPUT = _motor.OUTPUT
FILES = (
    *_motor.FILES,
    "sealed_grid_common.py",
    "critical_fidelity.py",
    "design_fidelity.py",
    "physics_half.py",
    "probe_design.py",
    "motor_physics.py",
    "motor_sealed_dual_pack.py",
)
MINIMUM_LEGS = _motor.MINIMUM_LEGS
MANIFEST_NAME = physical.MANIFEST_NAME
COHORT = grid_common.GRID_COHORT
CASES = 30
DESIGNS, CONDITIONS = 5, 6
#: The registered grid shapes: the sealed exam's 5 x 6, and the practice grid of
#: the full exposed public bank (its 8 designs x 6 conditions). A definition
#: names its own shape; practice is labelled "practice (public bank)" and is never
#: comparable with a sealed grade.
SHAPES = ((DESIGNS, CONDITIONS), (8, 6))


def grid_shape(definition):
    """``(designs, conditions)`` a definition registers, or a typed refusal."""
    grid = definition.get("grid") if type(definition) is dict else None
    shape = (
        (grid.get("designs"), grid.get("conditions"))
        if type(grid) is dict and set(grid) == {"designs", "conditions"}
        else None
    )
    mdm._require(shape in SHAPES, "motor_sealed_definition")
    return shape


DEFINITION_SCHEMA = "carbon.scoring.motor-sealed-dual-accuracy.v1"
METHOD = "motor-sealed-grid-dual-from-predictions.v1"
LOSSES = (
    "sealed_all30_mean_f0",
    "sealed_worst_design_mean_f0",
    "sealed_median_dimensionless_signed_margin_error",
)
PACK_SUFFIX = "-sealed-batch-30"
#: dev1 section 3 / section 7 DEVELOPMENT normalisation scales (not physical
#: thresholds): torque margin 0.10 N.m, ripple margin one percentage point. The
#: value scale is the registered D_scale.
TORQUE_MARGIN_SCALE_NM = 0.10
RIPPLE_MARGIN_SCALE = 0.01
TORQUE_MARGIN = "mean_torque_margin_nm"
RIPPLE_MARGIN = "ripple_fraction_margin"
Refused = mdm.MotorMeasurementRefused
_ADAPTER = sys.modules[__name__]


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_definition(definition):
    """The sealed grid definition, checked for every field used."""
    mdm._require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("losses") == list(LOSSES)
        and definition.get("A_reducer") == "minimum"
        and all(
            mdm._number(definition.get(k)) and definition[k] > 0
            for k in ("f0_scale", "signed_margin_scale", "D_scale")
        )
        and type(definition.get("signed_margin_cell")) is dict
        and all(
            mdm._number(definition["signed_margin_cell"].get(k))
            and definition["signed_margin_cell"][k] > 0
            for k in ("mean_torque_nm", "ripple_fraction")
        )
        and type(definition.get("verification_budget")) is int
        and definition["verification_budget"] >= 1
        and definition.get("grid", {}).get("conditions") == CONDITIONS
        and definition.get("grid", {}).get("designs") in (DESIGNS, 8)
        and definition.get("cohort_counts")
        == {COHORT: (definition.get("grid", {}).get("designs") or 0) * CONDITIONS}
        and type(definition.get("probes")) is dict
        and definition["probes"].get("cohort") == probe_design.PROBE_COHORT
        and type(definition["probes"].get("rows")) is int
        and definition["probes"]["rows"] >= 0
        and type(definition.get("reference_receipt_sha256")) is str
        and definition["reference_receipt_sha256"].startswith("sha256:")
        and len(definition["reference_receipt_sha256"]) == 71,
        "motor_sealed_definition",
    )
    if "critical" in definition:
        try:
            critical.validate_block(definition["critical"])
        except critical.CriticalFidelityRefused as exc:
            raise Refused("motor_sealed_definition") from exc
    return definition


def definition(*, bank, train_raw):
    """The sealed accuracy definition fields (the shared module adds the
    producer, TRAIN and bank pins). Every scale and the verification budget are
    Motor's registered ones."""
    evidence = bank.get("solver_evidence") if type(bank) is dict else None
    mdm._require(
        type(evidence) is bytes and evidence, "motor_sealed_evidence_unavailable"
    )
    values = _motor._definition_values()
    probes = sum(1 for c in bank["cohorts"] if c == probe_design.PROBE_COHORT)
    cells = [
        r
        for r, c in zip(bank["reference_records"], bank["cohorts"], strict=True)
        if c == COHORT
    ]
    designs = len({r.get("design_id") for r in cells})
    conditions = len({r.get("condition_id") for r in cells})
    mdm._require((designs, conditions) in SHAPES, "motor_sealed_grid")
    return {
        "schema": DEFINITION_SCHEMA,
        "method": METHOD,
        "source_definition_sha256": _motor.SOURCE_DEFINITION_SHA256,
        "g1_measurement_contract_sha256": _motor.G1_MEASUREMENT_CONTRACT_SHA256,
        "paired_repeat_procedure": "per_case",
        "cohort_counts": {COHORT: designs * conditions},
        "grid": {"designs": designs, "conditions": conditions},
        "losses": list(LOSSES),
        "A_reducer": "minimum",
        "f0_scale": values["f0_scale"],
        "signed_margin_scale": values["signed_margin_scale"],
        "signed_margin_cell": values["signed_margin_cell"],
        "D_scale": values["D_scale"],
        "verification_budget": values["verification_budget"],
        "reference_receipt_sha256": _sha(evidence),
        "critical": critical.block(
            [
                (
                    "torque_margin",
                    "margin",
                    TORQUE_MARGIN,
                    "N.m",
                    TORQUE_MARGIN_SCALE_NM,
                ),
                ("ripple_margin", "margin", RIPPLE_MARGIN, "1", RIPPLE_MARGIN_SCALE),
            ],
            ("1", "MINIMIZE", values["D_scale"]),
            [("torque_margin", -1)],
        ),
        "probes": {"cohort": probe_design.PROBE_COHORT, "rows": probes},
        **({"physics": motor_physics.block(train_raw)} if probes else {}),
    }


def applied_pack(**_):
    """Motor's applied pack with no registered leg minimums: they were measured
    on the development bank. A sealed pack's minimums come from the baseline's
    own run on the same batch (`physical.baseline_minimums`)."""
    pack = _motor._applied_pack()
    return {
        **pack,
        "hard_gates": [*pack["hard_gates"], motor_physics.GATE],
        "legs": {leg: {**body, "minimum": None} for leg, body in pack["legs"].items()},
    }


def physics_contract():
    return _motor.physics_contract()


def baseline_outputs(cases):
    return _motor.baseline_outputs(cases)


def _benefit(loss, scale):
    return mdm._benefit(loss, scale)


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A, D, native gates and the decision outcome for one model on a sealed
    5 x 6 grid, by Motor's registered decision measure (see the module
    docstring), then the physics half from the private probes."""
    validate_definition(definition)
    cells = [i for i, row in enumerate(bank_rows) if row.get("cohort") == COHORT]
    probes = [
        i
        for i, row in enumerate(bank_rows)
        if row.get("cohort") == probe_design.PROBE_COHORT
    ]
    designs, conditions = grid_shape(definition)
    mdm._require(
        len(cells) == designs * conditions
        and len(cells) + len(probes) == len(bank_rows)
        and len(probes) == definition["probes"]["rows"]
        and type(outputs) is list
        and len(outputs) == len(bank_rows)
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == len(bank_rows) for r in repeats),
        "motor_bank_cohort",
    )
    measured = _measure_cells(
        bank_rows=[bank_rows[i] for i in cells],
        outputs=[outputs[i] for i in cells],
        repeats=[[r[i] for i in cells] for r in repeats],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )
    internal = measured.pop("_cells")
    if "physics" not in definition:
        return measured
    return motor_physics.apply(
        measured,
        f0=internal["f0"],
        nearness=internal["nearness"],
        condition_cells=internal["condition_cells"],
        f0_scale=definition["f0_scale"],
        cell_curves=internal["curves"],
        cell_density=internal["density"],
        definition=definition,
        spread=motor_physics.train_spread(train_raw),
        probe_rows=[bank_rows[i] for i in probes],
        probe_curves=[outputs[i] for i in probes],
    )


def _measure_cells(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    del names
    n = len(bank_rows)
    shape = grid_shape(definition)
    cases = shape[0] * shape[1]
    mdm._require(
        type(outputs) is list
        and len(outputs) == n == cases
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == n for r in repeats),
        "motor_prediction_roster",
    )
    mdm._require(
        all(row.get("cohort") == COHORT for row in bank_rows), "motor_bank_cohort"
    )
    layout = grid_common.grid_layout(
        bank_rows,
        design_of=lambda row: row.get("design_id"),
        condition_of=lambda row: row.get("condition_id"),
        shape=shape,
        refuse=lambda code: mdm._require(False, "motor_sealed_grid"),
    )
    designs = sorted(layout.designs)
    constraints = limits.get("constraints") if type(limits) is dict else None
    contract = (objective or {}).get("decision_contract")
    mdm._require(
        type(constraints) is dict
        and type(contract) is dict
        and contract.get("constraints") == constraints,
        "motor_limit_or_objective",
    )
    # The grid's own ids, from the batch itself; the contract is the registered one.
    grid_objective = grid_common.decision_objective(layout, contract)
    train = _motor._train_records(train_raw)
    exam_scales = exam.scales_from_train(train)
    component_scales = candidates.scales(train)
    predictions = [mdm._curve(v) for v in outputs]
    twins = [[mdm._curve(v) for v in repeat] for repeat in repeats]
    references = [{**row["record"], "inputs": row["inputs"]} for row in bank_rows]

    gate_failed = []
    for i, prediction in enumerate(predictions):
        verdicts = [
            exam.gates(prediction, twins[0][i]),
            exam.gates(prediction, twins[1][i]),
            exam.gates(twins[0][i], twins[1][i]),
        ]
        if any(exam.FAIL in v.values() for v in verdicts):
            gate_failed.append(bank_rows[i]["case_id"])
    grid_rows = [
        exam.score_case(predictions[i], references[i], exam_scales, twin=twins[0][i])
        for i in range(n)
    ]
    grid = exam.aggregate(grid_rows)
    coverage_ok = grid["n_scored"] == grid["n_cases"] == cases
    native_ok = (
        not gate_failed
        and grid["eligible"] is True
        and all(r["state"] == exam.SCORABLE for r in grid_rows)
    )
    gates = {"native_motor_valid": native_ok, "complete_fixed_coverage": coverage_ok}

    index = list(range(n))
    try:
        reference_quantities = {
            bank_rows[i]["case_id"]: decision.quantities(
                contract, references[i]["outputs"]
            )
            for i in index
        }
    except decision.DecisionError as exc:
        raise Refused("motor_reference_quantities") from exc
    try:
        quantities = {
            bank_rows[i]["case_id"]: decision.quantities(contract, predictions[i])
            for i in index
        }
    except decision.DecisionError:
        # The model's own curve failed Motor's validity gates.
        quantities = None

    a = losses = None
    f0 = {}
    if coverage_ok and native_ok and quantities is not None:
        for i in index:
            parts = candidates.components(
                predictions[i], references[i], component_scales
            )
            f0[bank_rows[i]["case_id"]] = (parts["mean"] + parts["shape"]) / 2
        per_design = [
            fmean(f0[row["case_id"]] for row in bank_rows if row["design_id"] == design)
            for design in designs
        ]
        cell = definition["signed_margin_cell"]
        losses = {
            LOSSES[0]: fmean(f0.values()),
            LOSSES[1]: max(per_design),
            LOSSES[2]: statistics.median(
                max(
                    abs(
                        quantities[k]["mean_torque_margin_nm"]
                        - reference_quantities[k]["mean_torque_margin_nm"]
                    )
                    / cell["mean_torque_nm"],
                    abs(
                        quantities[k]["ripple_fraction_margin"]
                        - reference_quantities[k]["ripple_fraction_margin"]
                    )
                    / cell["ripple_fraction"],
                )
                for k in quantities
            ),
        }
        a = min(
            _benefit(losses[LOSSES[0]], definition["f0_scale"]),
            _benefit(losses[LOSSES[1]], definition["f0_scale"]),
            _benefit(losses[LOSSES[2]], definition["signed_margin_scale"]),
        )
    outcome, d, regret, selected = mdm._decision(
        bank_rows, index, quantities, reference_quantities, grid_objective, definition
    )
    fidelity = None
    if "critical" in definition and quantities is not None:
        # D = min(V, C): C is the worst signed torque/ripple margin error over
        # every cell, the unselected designs included; V is the mean of the
        # pair-ordering, accept/reject and nearby-variant measures.
        cells_of = {
            design: [bank_rows[i]["case_id"] for i in layout.rows_of_design(design)]
            for design in designs
        }
        reference = {
            "cases": {
                k: {q: v[q] for q in (TORQUE_MARGIN, RIPPLE_MARGIN)}
                for k, v in reference_quantities.items()
            },
            "actions": {
                design: {
                    "feasible": all(
                        reference_quantities[cid]["feasible"] for cid in cells
                    ),
                    "objective": max(
                        reference_quantities[cid]["ripple_fraction"] for cid in cells
                    ),
                }
                for design, cells in cells_of.items()
            },
        }
        prediction = {
            "cases": {
                k: {q: v[q] for q in (TORQUE_MARGIN, RIPPLE_MARGIN)}
                for k, v in quantities.items()
            },
            "selected": selected,
            "objective": {
                design: max(quantities[cid]["ripple_fraction"] for cid in cells)
                for design, cells in cells_of.items()
            },
        }
        v_total, v_record = critical.value(
            definition["critical"],
            cells_of=cells_of,
            reference=reference,
            prediction=prediction,
            base_v=d if d is not None else 0.0,
            limits={"torque_margin": constraints["min_mean_torque_nm"]},
        )
        d, fidelity = critical.design(
            v_total,
            critical.reduce(
                definition["critical"],
                case_ids=[row["case_id"] for row in bank_rows],
                action_ids=designs,
                reference=reference,
                prediction=prediction,
            ),
        )
        fidelity["value"] = v_record
    return {
        "A": a,
        "D": d,
        "design_fidelity": fidelity,
        "losses": losses,
        "gates": gates,
        "gate_failed_cases": gate_failed,
        "decision_outcome": outcome,
        "verified_regret": regret,
        "selected_design": selected,
        "_cells": {
            "f0": f0,
            "nearness": {
                k: min(
                    abs(v["mean_torque_margin_nm"]) / TORQUE_MARGIN_SCALE_NM,
                    abs(v["ripple_fraction_margin"]) / RIPPLE_MARGIN_SCALE,
                )
                for k, v in reference_quantities.items()
            },
            "condition_cells": [
                [bank_rows[i]["case_id"] for i in layout.rows_of_condition(c)]
                for c in layout.conditions
            ],
            "curves": {bank_rows[i]["case_id"]: outputs[i] for i in range(n)},
            "density": {
                bank_rows[i]["case_id"]: bank_rows[i]["inputs"]["current_density_a_mm2"]
                for i in range(n)
            },
        },
    }


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares the sealed Motor population: 30 cells, every
    cohort ``decision_sealed_grid``, each a distinct design x condition cell of
    the 5 x 6 grid."""
    if type(bank) is not dict:
        return False
    cohorts, records = bank.get("cohorts"), bank.get("reference_records")
    if (
        type(cohorts) not in (tuple, list)
        or type(records) not in (tuple, list)
        or len(cohorts) != len(records)
    ):
        return False
    keep = [i for i, c in enumerate(cohorts) if c != probe_design.PROBE_COHORT]
    return grid_common.is_grid_bank(
        [cohorts[i] for i in keep],
        [records[i] for i in keep],
        shape=(DESIGNS, CONDITIONS),
        design_of=lambda r: r.get("design_id"),
        condition_of=lambda r: r.get("condition_id"),
    )


def adapter(version):
    """The sealed adapter for exactly ``version``, or None."""
    return physical.versioned(_ADAPTER, version)


def adapter_for_bank(bank, version):
    """Dispatch by the bank's declared population: a sealed grid bank gets the
    sealed adapter, a development bank Motor's own, any other refuses."""
    if is_sealed_bank(bank):
        return adapter(version)
    cohorts = bank.get("cohorts") if type(bank) is dict else None
    development = {
        "practice",
        "pilot_ordinary",
        "pilot_difficult",
        "decision_representative",
        "decision_boundary_stress",
    }
    if cohorts and set(cohorts) <= development:
        return physical.versioned(_motor, version)
    raise Refused("motor_bank_population")


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def write_sealed_pack(
    root,
    bank,
    *,
    version=VERSION,
    inference_image_id=None,
    device_class=None,
    calibration=False,
    baseline_binding_raw=None,
    calibration_pack_root=None,
):
    """Write a sealed batch's complete receiver pack under a new, empty
    ``root`` (the pack, public and private root; the manifest the receiver
    seals is ``root / MANIFEST_NAME``): Motor's public roles, the sealed
    batch's private roles (``motor_sealed_pack.private_roles``, from Data
    Collection's bank) and this producer's accuracy_definition,
    reference_rows, solver_evidence, score_pack and source_registration.

    Mirrors `physical.write_development_pack`: ``calibration`` writes the
    minimum-free calibration pack for ``inference_image_id``;
    ``baseline_binding_raw`` with ``calibration_pack_root`` writes the per-image
    pack from the baseline's graded run on this batch. Without either the pack
    carries no leg minimums (none were measured on this batch)."""
    from carbon.challenge_kit import motor_sealed_pack, physical_pack

    chosen = adapter(version)
    if chosen is None:
        raise ValueError("no sealed Motor adapter for this Challenge version")
    if not is_sealed_bank(bank):
        raise Refused("motor_bank_population")
    physics = physical_pack.physics_contract(CHALLENGE, version)
    if type(physics) is not dict or set(physics) != {"version", "definition"}:
        raise ValueError(
            "pack physics role is not in its {version, definition} envelope"
        )
    generated = chosen.physics_contract()
    if generated is not None and generated != physics:
        raise ValueError("pack physics role differs from the generated contract")
    root = Path(root)
    manifest_path = physical_pack.write_public_pack(
        root, CHALLENGE, version, exposed_development_bank=False
    )
    public = physical_pack.public_roles(CHALLENGE, version)
    draft = json.loads(manifest_path.read_bytes())
    (root / "private").mkdir(mode=0o700, exist_ok=True)
    for role, body in motor_sealed_pack.private_roles(bank).items():
        name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
        (root / name).write_bytes(body)
        draft["private"][role] = {"path": name}
    draft["pack_version"] = draft["pack_version"] + PACK_SUFFIX
    inputs = {
        "bank": bank,
        "physics": physics,
        "interface_raw": public["interface"],
        "train_raw": public["train"],
        "limits_raw": public["important_limit_definition"],
        "objective_raw": public["design_objective"],
    }
    if calibration and baseline_binding_raw is not None:
        raise ValueError("a calibration pack takes no baseline binding")
    minimums = "calibration" if calibration else None
    if baseline_binding_raw is not None:
        if calibration_pack_root is None:
            raise ValueError("a baseline binding needs its calibration pack")
        platform, calibration_documents = physical._calibration_platform(
            chosen, calibration_pack_root, baseline_binding_raw, inputs
        )
        if (
            inference_image_id is not None
            and inference_image_id != platform["inference_image_id"]
        ) or (device_class is not None and device_class != platform["device_class"]):
            raise ValueError("inference platform differs from the baseline run's")
        minimums = physical.baseline_minimums(
            chosen, baseline_binding_raw, calibration_documents=calibration_documents
        )
    else:
        platform = physical.leg_minimum_platform(
            inference_image_id, device_class or physical.DEVICE_CLASS
        )
    documents = physical.pack_documents(
        chosen, minimums=minimums, platform=platform, **inputs
    )
    for role, body in documents.items():
        scope = "public" if role == "accuracy_definition" else "private"
        name = f"{scope}/{role}.json"
        (root / name).write_bytes(body)
        draft[scope][role] = {"path": name}
    manifest_path.write_bytes(physical.canonical(draft))
    return manifest_path


__all__ = [
    "CASES",
    "COHORT",
    "EVALUATION_VERSION",
    "VERSIONS",
    "adapter",
    "adapter_for_bank",
    "definition",
    "is_sealed_bank",
    "measure",
    "producer_digest",
    "write_sealed_pack",
]
