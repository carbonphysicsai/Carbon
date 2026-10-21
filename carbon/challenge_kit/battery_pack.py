"""Battery's normal-construction DEVELOPMENT evaluation pack roles.

Battery is already a registered direct Challenge: the receiver's construction
material is ``carbon.battery.construction_bundle_material.bundle_material``.
Its kit, interface, train and physics contract roles are taken from that same
material, so the receiver's pack check compares identical documents, and the
scored query (its public PRACTICE inputs) is the bank's case bank.

The limit and objective roles carry the public EV4 decision contract's own
constraints and objective verbatim, and bind the sealed plating reference
battery-plating-ref-v2 (VALIDATOR-PLATING-REF-V2-02) by digest and reader.
The accuracy definition, solver evidence, score pack and source registration
belong to the scoring producer and stay HUMAN_INPUT here.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path

from carbon.battery import challenge, plating_v2, practice
from carbon.battery.construction_bundle_material import (
    PHYSICS_PATH,
    PHYSICS_SHA256,
    bundle_material,
)

_REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = challenge.CHALLENGE.challenge_id
#: -2: each PRACTICE reference row carries its battery-plating-ref-v2 label.
PACK_VERSION = "battery-normal-construction-development-2"
#: 1.0 is the registered v1 Challenge version; 2.0 (step-2 batch,
#: STEP2_BATCH_VERSIONS_20261020) adds the v2 material rows. Every caller names
#: its version.
VERSIONS = ("1.0", "2.0")
#: Battery 2.0's extra rows (REFERENCE_PRESENT_MASK_INTERFACE_20261020 §1).
_EV4_REFERENCES = (
    "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz",
    "ff10f9aea9097cd500d646ffe02f479d04401207b30a44aeee33566433e436cb",
)
_B15_PLAN = (
    "docs/development/evidence/battery-b15-public-probes-20261020/plan.json",
    "5fb7a81f057364a3c63d9b5a80c98305dc2277298adf770195ab4dc7271d63f9",
)
OUTPUT_WIDTH = 247  # voltage 121, temperature 121, plating 1, capacity 4
_EV4 = (
    "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    "fc6f504f3ff69b3add10099056b7a652a28112d3ca1d63ada2fb194aac2d3e18",
)
#: The sealed plating reference (VALIDATOR-PLATING-REF-V2-02, sealed on #1316).
_PLATING_LABELS = (
    "docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json",
    "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
)
_PLATING_READER = plating_v2.READER
PLATING_RULES = (
    "m20-above-window-r1",
    "m160-d3-r1",
    "pending-m160-r1",
    "m20-below-window",
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _pinned(path_and_sha: tuple[str, str]) -> bytes:
    path, pinned = path_and_sha
    raw = (_REPOSITORY / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned {path} differs")
    return raw


def _check(version: str) -> None:
    if version not in VERSIONS:
        raise ValueError("unknown Battery version")


def plating_reference() -> dict:
    """The sealed v2 plating reference binding; every label uses a v2 rule."""
    labels = json.loads(_pinned(_PLATING_LABELS))
    rows = labels["rows"]
    if (
        labels.get("version") != "battery-plating-ref-v2"
        or any(row["rule"] not in PLATING_RULES for row in rows)
        or labels["counts"]
        != {
            "m160-d3-r1:FEASIBLE": 114,
            "m160-d3-r1:INFEASIBLE": 447,
            "m160-d3-r1:UNRESOLVED": 108,
            "pending-m160-r1:UNRESOLVED": 103,
        }
    ):
        raise ValueError("plating reference is not sealed v2")
    by_source = {}
    for row in rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1
    return {
        "version": "battery-plating-ref-v2",
        "decision": "VALIDATOR-PLATING-REF-V2-02 (sealed on the merge of #1316)",
        "labels": {"path": _PLATING_LABELS[0], "sha256": _PLATING_LABELS[1]},
        "reader": "scripts/dev/battery/plating_rereference.py:v2_label",
        "rules": list(PLATING_RULES),
        "rows_by_source": dict(sorted(by_source.items())),
        "parameters_mv": {
            "feasible_at_m160": 1.0,
            "infeasible_below_m160": 0.0,
            "window": [-1.97, 4.5],
            "claimed_within_abs_m20": 15.0,
        },
        "scope": (
            "Adequate for DEVELOPMENT and testnet within a 1.0 mV band. Not a "
            "qualification; no claim about deep plating or |m20| >= 15 mV."
        ),
    }


def practice_plating_labels(records) -> list:
    """Each PRACTICE case's v2 plating label from its mesh-20 margin.

    No PRACTICE case has a mesh-160 re-solve, so a case inside the v2 window
    is `pending-m160-r1` UNRESOLVED and is never a mesh-20 FEASIBLE; None is
    v2's own "no claim" (|m20| >= 15 mV).
    """
    if _PLATING_READER != plating_v2.READER:
        raise ValueError("plating reader pin differs from carbon.battery.plating_v2")
    try:
        return plating_v2.labels(records, str(_REPOSITORY))
    except plating_v2.ReaderUnavailable as exc:
        raise ValueError(str(exc)) from exc


def public_roles(version: str) -> dict[str, bytes]:
    """Bound public roles' exact bytes; accuracy_definition stays HUMAN_INPUT."""
    _check(version)
    ev4 = json.loads(_pinned(_EV4))
    source = {"path": _EV4[0], "sha256": _EV4[1]}
    challenge_identity = {"id": CHALLENGE_ID, "version": version}
    limits = {
        "schema": "carbon.battery.important-limit-definition.v1",
        "challenge": challenge_identity,
        "constraints": ev4["constraints"],
        "source": source,
        "plating_reference": plating_reference(),
    }
    if version == "1.0":
        material = bundle_material(_REPOSITORY)
        physics = (_REPOSITORY / PHYSICS_PATH).read_bytes()
        if hashlib.sha256(physics).hexdigest() != PHYSICS_SHA256:
            raise ValueError("pinned Battery physics contract differs")
    else:
        # 2.0's kit, interface, TRAIN and physics envelope are its served
        # material's (Launchpad), which serves this module's own bank rows.
        from carbon.battery.construction_bundle_material import versioned_material

        material = versioned_material(version)
        physics = _canonical(material["physics_contract"])
        # The bank's extra rows, pinned the way the plating reference is.
        limits["b15_probe_plan"] = {"path": _B15_PLAN[0], "sha256": _B15_PLAN[1]}
        limits["ev4_decision_references"] = {
            "path": _EV4_REFERENCES[0],
            "sha256": _EV4_REFERENCES[1],
        }
    return {
        "construction_kit": _canonical(material["construction_kit"]),
        "interface": _canonical(material["interface_document"]),
        "train": material["train"],
        "physics_contract": physics,
        "important_limit_definition": _canonical(limits),
        "design_objective": _canonical(
            {
                "schema": "carbon.battery.design-objective.v1",
                "challenge": challenge_identity,
                "objective": ev4["objective"],
                "decision": ev4["decision"],
                "source": source,
            }
        ),
    }


def development_bank(version: str) -> dict:
    """1.0: the public PRACTICE set the receiver scores, as the exposed bank.
    2.0: those rows, then EV4's development grid, then the B15 probe pairs,
    with the authoritative `reference_present` mask."""
    _check(version)
    practice_bank = _practice_bank()
    if version == "1.0":
        return practice_bank
    return _bank_v2(practice_bank)


def _flat(outputs) -> list[float]:
    row = [
        *outputs["voltage_v"],
        *outputs["temperature_c"],
        outputs["plating_margin_v"],
        *outputs["capacity_ah"],
    ]
    if len(row) != OUTPUT_WIDTH or not all(
        type(v) in (int, float) and math.isfinite(v) for v in row
    ):
        raise ValueError("a present Battery reference row is not 247 finite values")
    return [float(v) for v in row]


def _bank_v2(practice_bank: dict) -> dict:
    """REFERENCE_PRESENT_MASK_INTERFACE_20261020 §1, in its fixed row order."""
    import numpy as np

    from carbon.battery import domain
    from carbon.battery.value import contract as ev

    nan_row = [math.nan] * OUTPUT_WIDTH
    case_ids = list(practice_bank["case_ids"])
    cohorts = list(practice_bank["cohorts"])
    inputs = [list(map(float, row)) for row in practice_bank["inputs"]]
    references = [list(map(float, row)) for row in practice_bank["references"]]
    present = [True] * len(case_ids)
    records = list(practice_bank["reference_records"])

    contract = json.loads(_pinned(_EV4))
    by_id = {}
    with gzip.open(_REPOSITORY / _EV4_REFERENCES[0]) as stream:
        raw = stream.read()
    if hashlib.sha256((_REPOSITORY / _EV4_REFERENCES[0]).read_bytes()).hexdigest() != (
        _EV4_REFERENCES[1]
    ):
        raise ValueError(f"pinned {_EV4_REFERENCES[0]} differs")
    for line in raw.decode("utf-8").splitlines():
        record = json.loads(line)
        if record["case_id"] in by_id:
            raise ValueError("EV4 decision references repeat a case")
        by_id[record["case_id"]] = record
    for scenario in ev.scenarios(contract, "development"):
        (t_amb, soc0), *rest = scenario["conditions"]
        if rest:
            raise ValueError("an EV4 development scenario has more than one condition")
        for candidate in ev.candidates(contract):
            case_id = ev.case_id(contract, scenario, candidate, 0)
            record = by_id[case_id]
            point = {"c1": candidate["c1"], "c2": candidate["c2"],
                     "t_amb_c": t_amb, "soc0": soc0}  # fmt: skip
            if any(float(record["inputs"][k]) != float(point[k]) for k in point):
                raise ValueError(f"{case_id} inputs differ from the EV4 grid")
            case_ids.append(case_id)
            cohorts.append("decision")
            inputs.append([float(point[k]) for k in domain.INPUTS])
            ok = record.get("status") == "OK"
            references.append(_flat(record["outputs"]) if ok else nan_row)
            present.append(ok)
            records.append(record)

    plan = json.loads(_pinned(_B15_PLAN))
    for i, pair in enumerate(plan["pairs"]):
        for side in ("base", "partner"):
            case_ids.append(f"p{i}-{side}")
            cohorts.append("probe")
            inputs.append([float(pair[side][k]) for k in domain.INPUTS])
            references.append(nan_row)
            present.append(False)
            records.append({"case_id": f"p{i}-{side}", "role": "probe", "pair": i,
                            "side": side, "axis": pair["axis"]})  # fmt: skip

    x = np.asarray(inputs, dtype=np.float64)
    y = np.asarray(references, dtype=np.float64)
    n = len(case_ids)
    if (
        x.shape != (n, len(domain.INPUTS))
        or y.shape != (n, OUTPUT_WIDTH)
        or len(set(case_ids)) != n
        or not np.isfinite(x).all()
    ):
        raise ValueError("Battery v2 bank tensors differ")
    for i in range(n):
        row = y[i]
        if present[i] and not np.isfinite(row).all():
            raise ValueError("reference_invalid: a present row is not finite")
        if not present[i] and not np.isnan(row).all():
            raise ValueError("reference_invalid: an absent row is not all NaN")
    x.setflags(write=False)
    y.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "cohorts": tuple(cohorts),
        "inputs": x,
        "references": y,
        "reference_present": tuple(present),
        "reference_records": records,
        "solver_evidence": practice_bank["solver_evidence"],
    }


def _practice_bank() -> dict:
    material = bundle_material(_REPOSITORY)
    records = practice.PracticeSet.load(_REPOSITORY).records
    case_ids = tuple(material["practice_case_ids"])
    if tuple(r["case_id"] for r in records) != case_ids:
        raise ValueError("practice records differ from the material's order")
    return {
        "case_ids": case_ids,
        "cohorts": ("practice",) * len(case_ids),
        "inputs": material["practice_inputs"],
        "references": material["practice_reference"],
        # The mesh-20 record is kept as measured; the v2 label sits beside it.
        "reference_records": [
            {**record, "plating_label_v2": label}
            for record, label in zip(
                records, practice_plating_labels(records), strict=True
            )
        ],
        "solver_evidence": None,
    }
