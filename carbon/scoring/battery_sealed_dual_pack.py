"""Battery grades a sealed exam grid (Validator rulings
VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §11; OWNER-BATTERY-EXAM-GRID-01;
evaluation version ``battery-dual-sealed-grid-4x35-v1``), and writes the
batch's receiver pack.

A sealed Battery batch is a placed grid of 4 fresh (t_amb, soc0) scenarios x
EV4's frozen 35 (c1, c2) candidates = 140 cells, each a case with a v2-labelled
mesh-160 reference. It is graded as Battery's registered dual measurement, with
the batch's own scenarios in place of EV4's development ones, and the total is
0.5 A + 0.5 D (OWNER-BATTERY-DUAL-SCORE-01):

- **A** is the registry's leg ``a`` (``ratios.legs`` over ``scoring.components``)
  over the 140 cells as the rated cases, **G-FEAS** is the registry's
  ``exceeds`` gate with plating-v2 truth, and the exam gates and exact paired
  repeat run unchanged, all by `battery_dual_measurement.practice_measures`.
- **D** is ``q = 1 / (1 + mean Q3 decision regret)`` over the batch's own 4
  scenarios (`decision_value`'s composition: `quiz.q3_measures` over the
  scenarios' `q3_judge_v2` outcomes). The one change from the development
  composition is where the reference's mesh-160 plating margin comes from: the
  pinned label record (`gate_plating_v2.m160_by_case`) covers only EV4's
  development cases, so a sealed cell takes its own recorded margin
  (``plating_margin_m160_v``) through the same pinned v2 reader, recomputed and
  never trusted.
- **B15** runs over the public probe pairs. They are public, deterministic
  and referenceless, so `with_probe_rows` appends them to the 140 cells.
- A scenario without a feasible reference candidate cannot define D; the batch
  is unusable (the family's QA), so grading refuses rather than average fewer.

This module is its own adapter so Battery's development files
(``battery_dual_pack.py``, ``battery_dual_measurement.py``) and every pack bound
to their producer digest are unchanged. Dispatch is by the bank's declared
population (`adapter_for_bank`).

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from carbon.scoring import battery_dual_measurement as bdm
from carbon.scoring import battery_dual_pack as _battery
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_grid_common as grid_common

CHALLENGE = _battery.CHALLENGE
VERSION = "2.0"
EVALUATION_VERSION = "battery-dual-sealed-grid-4x35-v1"
CASE_ID = "battery-sealed-grid-4x35"
#: 2.0, the v7 catalog version 2.1 and the launch version 2.2 grade the same sealed batches.
#: 2.2 is the launch version (2.1 + catalog): the same exam, so the same evaluation.
VERSIONS = {version: (EVALUATION_VERSION, CASE_ID) for version in ("2.0", "2.1", "2.2")}
OUTPUT = _battery.OUTPUT
FILES = (*_battery.FILES, "sealed_grid_common.py", "battery_sealed_dual_pack.py")
MINIMUM_LEGS = _battery.MINIMUM_LEGS
MANIFEST_NAME = physical.MANIFEST_NAME
#: The grid cells' cohort, as Motor's and Cooling's sealed grids name theirs
#: (Validator, 2026-10-22). The shared bank-row builder reads a ``design_id``
#: from a ``decision_*`` row, so `prepared` gives each cell one (its scenario).
COHORT = grid_common.GRID_COHORT
PROBE = "probe"
SCENARIOS, CANDIDATES = 4, 35
CELLS = SCENARIOS * CANDIDATES
DEFINITION_SCHEMA = "carbon.scoring.battery-sealed-dual-definition.v1"
METHOD = "registry-v5-g-feas-a-q-plating-v2-sealed-grid"
PACK_SUFFIX = "-sealed-grid-4x35"
Refused = bdm.BatteryMeasurementRefused
_ADAPTER = sys.modules[__name__]
_REPOSITORY = Path(__file__).resolve().parents[2]


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def input_names():
    return _battery.input_names()


def _contract():
    return _battery._contract()


# --- the bank: 140 cells and the public probe rows -------------------------------


def with_probe_rows(bank):
    """The sealed bank with the public B15 probe pairs appended (idempotent).

    The probe plan is public and the rows carry no reference, exactly as the
    development bank's; the 140 cells keep their rows and order."""
    import numpy as np

    from carbon.battery import domain
    from carbon.challenge_kit import battery_pack as bp

    if PROBE in set(bank["cohorts"]):
        return bank
    plan = json.loads(bp._pinned(bp._B15_PLAN))
    case_ids = list(bank["case_ids"])
    cohorts = list(bank["cohorts"])
    inputs = [list(map(float, row)) for row in bank["inputs"]]
    references = [list(map(float, row)) for row in bank["references"]]
    present = list(bank.get("reference_present", (True,) * len(case_ids)))
    records = list(bank["reference_records"])
    nan_row = [math.nan] * bp.OUTPUT_WIDTH
    for i, pair in enumerate(plan["pairs"]):
        for side in ("base", "partner"):
            case_ids.append(f"p{i}-{side}")
            cohorts.append(PROBE)
            inputs.append([float(pair[side][k]) for k in domain.INPUTS])
            references.append(nan_row)
            present.append(False)
            records.append(
                {
                    "case_id": f"p{i}-{side}",
                    "role": "probe",
                    "pair": i,
                    "side": side,
                    "axis": pair["axis"],
                }
            )
    x = np.asarray(inputs, dtype=np.float64)
    y = np.asarray(references, dtype=np.float64)
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        **bank,
        "case_ids": tuple(case_ids),
        "cohorts": tuple(cohorts),
        "inputs": x,
        "references": y,
        "reference_present": tuple(present),
        "reference_records": records,
    }


def _cell_of(row):
    """``(scenario id, candidate id)`` a grid row's record names (the family
    writes ``scenario_id`` and ``candidate_id`` on every cell)."""
    record = row.get("record")
    scenario = record.get("scenario_id") if type(record) is dict else None
    candidate = record.get("candidate_id") if type(record) is dict else None
    bdm._require(
        type(scenario) is str and scenario and type(candidate) is str and candidate,
        "battery_sealed_grid",
    )
    return scenario, candidate


def _grid(bank_rows, contract):
    """The batch's own scenarios and cell index, or a refusal: the grid rows are
    a complete SCENARIOS x CANDIDATES grid (`sealed_grid_common.grid_layout`),
    the candidates are EV4's frozen set, each scenario's rows share one
    (t_amb, soc0), and every cell has its reference."""
    from carbon.battery.value import contract as ev

    candidates = [c["id"] for c in ev.candidates(contract)]
    bdm._require(
        all(r["cohort"] in (COHORT, PROBE) for r in bank_rows)
        and len(candidates) == CANDIDATES,
        "battery_sealed_grid",
    )
    layout = grid_common.grid_layout(
        bank_rows,
        design_of=lambda row: _cell_of(row)[1],
        condition_of=lambda row: _cell_of(row)[0],
        shape=(CANDIDATES, SCENARIOS),
        refuse=lambda code: bdm._require(False, "battery_sealed_grid"),
    )
    bdm._require(set(layout.designs) == set(candidates), "battery_sealed_grid")
    conditions = {}
    for index in layout.indices:
        row = bank_rows[index]
        bdm._require(
            row.get("reference_present") is True
            and row["record"].get("status") == "OK",
            "battery_sealed_grid",
        )
        point = (row["inputs"]["t_amb_c"], row["inputs"]["soc0"])
        bdm._require(
            conditions.setdefault(_cell_of(row)[0], point) == point,
            "battery_sealed_grid",
        )
    scenarios = [
        {"id": s, "conditions": [[float(conditions[s][0]), float(conditions[s][1])]]}
        for s in layout.conditions
    ]
    cells = {(s, c): index for (c, s), index in layout.cells.items()}
    return scenarios, list(layout.indices), cells


def prepared(bank):
    """The sealed bank as the shared pack machinery takes it: each cell's record
    carries a ``design_id`` (its scenario id; the shared bank-row builder reads
    one from every ``decision_*`` row and would otherwise parse the case id), and
    the public probe pairs are appended. Idempotent; the cells, their order and
    their references are unchanged."""
    cohorts = bank["cohorts"]
    records = [
        _shared_fields(record) if cohort == COHORT and type(record) is dict else record
        for cohort, record in zip(cohorts, bank["reference_records"], strict=True)
    ]
    return with_probe_rows({**bank, "reference_records": records})


def _shared_fields(record):
    """A cell record with the two fields the shared pack machinery reads: a
    ``design_id`` (the scenario), and a ``wall_s`` totalling the family's
    per-solve walls (``solves``: the standard and the mesh-160 solve) when the
    record has no single wall."""
    out = {**record}
    out["design_id"] = record.get("design_id") or record.get("scenario_id")
    if "wall_s" not in out and type(record.get("solves")) is dict:
        walls = [
            solve.get("wall_s")
            for solve in record["solves"].values()
            if type(solve) is dict
        ]
        bdm._require(
            walls
            and all(
                type(w) in (int, float) and math.isfinite(w) and w >= 0 for w in walls
            ),
            "battery_sealed_walls",
        )
        out["wall_s"] = float(math.fsum(walls))
    return out


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares the sealed Battery population: 140 ``sealed_grid``
    cells (and only the public probe rows besides)."""
    cohorts = bank.get("cohorts") if type(bank) is dict else None
    return (
        type(cohorts) in (tuple, list)
        and sum(c == COHORT for c in cohorts) == CELLS
        and all(c in (COHORT, PROBE) for c in cohorts)
    )


# --- v2 truth for a sealed cell ---------------------------------------------------


def _labels(contract, records):
    """``{case_id: v2 label or None}``: the pinned v2 reader's label for each
    cell, recomputed from its recorded mesh-20 outputs and mesh-160 margin."""
    from carbon.battery import plating_v2
    from carbon.battery.value import decision as d
    from carbon.battery.value import gate_plating_v2 as gp

    reader = plating_v2.reader(str(_REPOSITORY))
    out = {}
    for record in records:
        m160 = record.get("plating_margin_m160_v")
        bdm._require(
            type(m160) in (int, float) and math.isfinite(m160), "battery_sealed_m160"
        )
        margin = d.measure(contract, record["outputs"])["plating_margin_v"]
        out[record["case_id"]] = gp.plating_label(reader, margin, float(m160))
    return out


def _assess_reference(contract, scenario, candidates, references, case_ids, labels):
    """`gate_plating_v2.assess_reference` with each cell's v2 label taken from
    its own mesh-160 margin (``labels``, `_labels`) instead of the pinned
    development record. Everything else is the pinned function's composition."""
    from carbon.battery.value import decision as d
    from carbon.battery.value import gate_plating_v2 as gp

    bands = contract["reference"]["uncertainty"]["bands"]
    out = {}
    for candidate in candidates:
        key = (candidate["id"], 0)
        record = references.get(key)
        if record is None or record.get("status") != "OK":
            out[candidate["id"]] = {"status": d.UNAVAILABLE, "objective": None}
            continue
        quantities = d.measure(contract, record["outputs"])
        label = labels[case_ids[key]]
        checks = gp.check(contract, quantities, bands, label)
        values = list(checks.values())
        status = (
            d.INFEASIBLE
            if d.FAIL in values
            else d.UNRESOLVED if d.UNRESOLVED in values else d.FEASIBLE
        )
        out[candidate["id"]] = {
            "status": status,
            "objective": d._objective([quantities]),
            "checks": [checks],
            "violations": [d._violations(contract, quantities)],
            "quantities": [quantities],
            "plating_v2": [label],
        }
    return out


def q3_judge_sealed(contract, scenario, grid_predictions, grid_refs, labels):
    """`battery_dual_measurement.q3_judge_v2` for a sealed scenario: the same
    composition with `_assess_reference`; None for a scenario whose reference
    grid holds no feasible design."""
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d

    candidates = ev.candidates(contract)
    keys = {(c["id"], 0): ev.case_id(contract, scenario, c, 0) for c in candidates}
    refs = {key: grid_refs[cid] for key, cid in keys.items() if cid in grid_refs}
    reference = _assess_reference(contract, scenario, candidates, refs, keys, labels)
    best = d.best_in_set(candidates, reference)
    if best is None:
        return None
    quantities = {}
    for candidate in candidates:
        outputs = grid_predictions.get(keys[(candidate["id"], 0)])
        if outputs is None:
            return {
                "kind": "MODEL_OUTPUT_MISSING",
                "selected": None,
                "decision_loss": contract["mistake_costs"]["missed_opportunity"],
            }
        quantities[(candidate["id"], 0)] = d.measure(contract, outputs)
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    selection = d.select(candidates, predicted)
    baseline_id = ev.candidate_id(contract["baseline"]["protocol"])
    result = d.outcome(contract, candidates, selection, reference, baseline_id)
    return {
        "kind": result["kind"],
        "selected": result.get("selected"),
        "decision_loss": result["decision_loss"],
    }


def decision_value_sealed(contract, scenarios, grid_predictions, grid_refs, labels):
    """Registry leg ``q`` over the batch's own scenarios (`decision_value`)."""
    from carbon.battery.value import quiz

    outcomes = []
    for entry in scenarios:
        scenario = quiz.q3_scenario(entry["id"], entry["conditions"][0])
        judged = q3_judge_sealed(
            contract, scenario, grid_predictions, grid_refs, labels
        )
        if judged is not None:
            outcomes.append(judged)
    measures = quiz.q3_measures(outcomes, contract)
    regret = measures["regret"]
    return (None if regret is None else 1.0 / (1.0 + regret)), {
        **measures,
        "scenarios": len(outcomes),
    }


# --- definition, pack, measure -----------------------------------------------------


def validate_definition(definition):
    """The sealed grid definition, checked for every field used."""
    bdm._require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("registry")
        == {
            "path": bdm.REGISTRY[0],
            "sha256": bdm.REGISTRY[1],
            "candidate": bdm.CANDIDATE,
        }
        and definition.get("g_feas") == bdm.registry_gate()
        and definition.get("paired_repeat") == {"procedure": "per_case", "floor": 0}
        and type(definition.get("unresolved_mask")) is dict
        and definition["unresolved_mask"].get("reason") == bdm.UNRESOLVED_REASON
        and type(definition["unresolved_mask"].get("case_ids")) is list
        and all(type(c) is str for c in definition["unresolved_mask"]["case_ids"])
        and definition.get("grid") == {"scenarios": SCENARIOS, "candidates": CANDIDATES}
        and type(definition.get("decision_scenarios")) is list
        and len(definition["decision_scenarios"]) == SCENARIOS
        and definition.get("b15_probe_plan") == bdm.pinned("b15_probe_plan")
        and type(definition.get("reference_receipt_sha256")) is str
        and definition["reference_receipt_sha256"].startswith("sha256:")
        and len(definition["reference_receipt_sha256"]) == 71,
        "battery_sealed_definition",
    )
    return definition


def definition(*, bank, train_raw):
    """The sealed accuracy definition fields (the shared module adds the
    producer, TRAIN and bank pins): the batch's own scenarios and unresolved
    mask, Battery's registered gate, plan and registry."""
    del train_raw
    evidence = bank.get("solver_evidence") if type(bank) is dict else None
    bdm._require(
        type(evidence) is bytes and evidence, "battery_sealed_evidence_unavailable"
    )
    contract = _contract()
    names = input_names()
    rows = physical.bank_rows(prepared(bank), names)
    scenarios, grid, _cells = _grid(rows, contract)
    records = [rows[i]["record"] for i in grid]
    labels = _labels(contract, records)
    unresolved = [
        case_id
        for case_id, label in labels.items()
        if type(label) is dict and label.get("label") == "UNRESOLVED"
    ]
    return {
        "schema": DEFINITION_SCHEMA,
        "method": METHOD,
        "registry": {
            "path": bdm.REGISTRY[0],
            "sha256": bdm.REGISTRY[1],
            "candidate": bdm.CANDIDATE,
        },
        "g_feas": bdm.registry_gate(),
        "paired_repeat_procedure": "per_case",
        "paired_repeat": {"procedure": "per_case", "floor": 0},
        "unresolved_mask": {"case_ids": unresolved, "reason": bdm.UNRESOLVED_REASON},
        "grid": {"scenarios": SCENARIOS, "candidates": CANDIDATES},
        "decision_scenarios": scenarios,
        "b15_probe_plan": bdm.pinned("b15_probe_plan"),
        "reference_receipt_sha256": _sha(evidence),
    }


def applied_pack(**_):
    """Battery's applied pack, unchanged: 0.5 A + 0.5 D, the four gates, and
    D = q (q prices every pick, so the one outcome reported is eligible)."""
    return _battery.applied_pack()


def physics_contract():
    return _battery.physics_contract()


def baseline_outputs(cases):
    return _battery.baseline_outputs(cases)


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A, D and the gates for one model on a sealed grid (see the module
    docstring), or a refusal."""
    from carbon.battery import construction_material as cm

    del limits, objective, train_raw, names
    validate_definition(definition)
    contract = _contract()
    scenarios, grid, cells = _grid(bank_rows, contract)
    bdm._require(
        definition["decision_scenarios"] == scenarios, "battery_sealed_scenarios"
    )
    bdm._require(
        type(outputs) is list
        and len(outputs) == len(bank_rows)
        and type(repeats) in (list, tuple)
        and len(repeats) == 2
        and all(type(r) is list and len(r) == len(bank_rows) for r in repeats),
        "battery_prediction_tensor",
    )
    records = [bank_rows[i]["record"] for i in grid]
    labels = _labels(contract, records)
    # A, the exam gates, G-FEAS and the exact paired repeat run through the
    # registered practice measure, the 140 cells as the rated cases with their
    # recomputed v2 label beside the record.
    as_practice = [
        (
            {
                **row,
                "cohort": "practice",
                "record": {**row["record"], "plating_label_v2": labels[row["case_id"]]},
            }
            if row["cohort"] == COHORT
            else row
        )
        for row in bank_rows
    ]
    practice = bdm.practice_measures(
        bank=as_practice,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        contract=contract,
    )
    try:
        by_bank_id = cm.output_predictions(
            [outputs[i] for i in grid], [bank_rows[i]["case_id"] for i in grid]
        )
        probe_rows = [i for i, row in enumerate(bank_rows) if row["cohort"] == PROBE]
        bdm._require(probe_rows, "battery_probe_rows")
        probe_predictions = cm.output_predictions(
            [outputs[i] for i in probe_rows],
            [bank_rows[i]["case_id"] for i in probe_rows],
        )
    except ValueError as exc:
        raise Refused("battery_prediction_tensor") from exc
    # The decision composition names a cell by EV4's contract.case_id; the
    # family's own case ids are opaque, so re-key by the cell's scenario and
    # candidate (the ids the record names).
    from carbon.battery.value import contract as ev

    keyed = {(s, c): ev.case_id(contract, {"id": s}, {"id": c}, 0) for (s, c) in cells}
    grid_predictions, grid_refs, keyed_labels = {}, {}, {}
    for cell, i in cells.items():
        bank_id = bank_rows[i]["case_id"]
        grid_predictions[keyed[cell]] = by_bank_id[bank_id]
        grid_refs[keyed[cell]] = bank_rows[i]["record"]
        keyed_labels[keyed[cell]] = labels[bank_id]
    d, decision = decision_value_sealed(
        contract,
        definition["decision_scenarios"],
        grid_predictions,
        grid_refs,
        keyed_labels,
    )
    # A scenario with no feasible reference cannot define D; the family's QA
    # refuses such a batch, so it is a reference limitation, never a verdict.
    bdm._require(
        d is not None and decision["scenarios"] == SCENARIOS,
        "battery_d_reference_unresolved",
    )
    b15 = bdm.physics_b15(probe_predictions)
    return {
        "A": practice["A"],
        "D": d,
        "gates": {
            "exam_gates": practice["gates"]["exam_gates"],
            "g_feas": practice["gates"]["g_feas"],
            "physics_b15": b15["eligible"] is True,
            "paired_repeat": practice["gates"]["paired_repeat"],
        },
        # D is the quiz's q, which already prices every pick.
        "decision_outcome": "VERIFIED_FEASIBLE",
        "false_feasible_rate": practice["false_feasible_rate"],
        "unresolved_mask": practice["unresolved_mask"],
        "decision": decision,
        "b15": b15,
    }


# --- dispatch, producer, pack writer ------------------------------------------------


def adapter(version):
    """The sealed adapter for exactly ``version``, or None."""
    return physical.versioned(_ADAPTER, version)


def adapter_for_bank(bank, version):
    """Dispatch by the bank's declared population: a sealed grid bank gets the
    sealed adapter, a Battery 2.0 development bank its own, any other refuses."""
    if is_sealed_bank(bank):
        return adapter(version)
    cohorts = bank.get("cohorts") if type(bank) is dict else None
    if cohorts and set(cohorts) <= {"practice", "decision", PROBE}:
        return physical.versioned(_battery, version)
    raise Refused("battery_bank_population")


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
    seals is ``root / MANIFEST_NAME``): Battery's public roles, the sealed
    batch's private roles, and this producer's accuracy_definition,
    reference_rows, solver_evidence, score_pack and source_registration.

    Mirrors `physical.write_development_pack` (and Motor's sealed writer):
    ``calibration`` writes the minimum-free calibration pack for
    ``inference_image_id``; ``baseline_binding_raw`` with
    ``calibration_pack_root`` writes the per-image pack from the baseline's
    graded run on this batch. Without either, the pack carries no leg
    minimums (none were measured on this batch). The public probe rows are
    appended to the bank (`with_probe_rows`)."""
    from carbon.challenge_kit import f02_sealed_pack, physical_pack

    chosen = adapter(version)
    if chosen is None:
        raise ValueError("no sealed Battery adapter for this Challenge version")
    if not is_sealed_bank(bank):
        raise Refused("battery_bank_population")
    bank = prepared(bank)
    public = physical_pack.public_roles(CHALLENGE, version)
    # Battery's physics role is the served material's own, carried in the
    # public roles (`physical_pack.physics_contract` binds none for it).
    physics = physical_pack.physics_contract(CHALLENGE, version)
    if physics is None and "physics_contract" in public:
        physics = json.loads(public["physics_contract"])
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
    draft = json.loads(manifest_path.read_bytes())
    (root / "private").mkdir(mode=0o700, exist_ok=True)
    for role, body in f02_sealed_pack.private_roles(bank).items():
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
    "CELLS",
    "COHORT",
    "EVALUATION_VERSION",
    "VERSIONS",
    "adapter",
    "adapter_for_bank",
    "decision_value_sealed",
    "definition",
    "is_sealed_bank",
    "measure",
    "prepared",
    "producer_digest",
    "with_probe_rows",
    "write_sealed_pack",
]
