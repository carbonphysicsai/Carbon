"""Battery gate version plating-v2: EV5's gate with battery-plating-ref-v2 plating truth.

OWNER-BATTERY-GATE-PLATING-V2-01 (2026-10-20). A new gate version beside EV5;
EV5 stays frozen and nothing here changes it. The decision quantities, the
temperature and CV checks and EV4's uncertainty bands are `decision`'s,
unchanged. Only the reference's plating verdict changes:

- the plating label comes from the sealed reference's own reader
  (`carbon.battery.plating_v2`, pinned bytes, never reimplemented); an
  unavailable or changed reader refuses the whole assessment (fail closed);
- |m20| >= 15 mV is v2's "no claim": the mesh-20 verdict (`decision.check`
  with EV4's band) is kept;
- inside the window, v2 FEASIBLE is PASS and INFEASIBLE is FAIL;
- v2 UNRESOLVED (including `pending-m160-r1`, every case without a mesh-160
  re-solve) is UNRESOLVED: it enters no plating measure, is never counted
  safe, and is counted and reported.

The mesh-160 margins come only from the pinned v2 label record
(`labels-v2-r1.json`), by case id. EV5's population has no rows there, so its
in-window cases are `pending-m160-r1` UNRESOLVED (the named coverage gap).

Public DEVELOPMENT evidence: no qualification, reward or LIVE change.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from carbon.battery import plating_v2

from . import decision as d
from .margins import CONSTRAINTS

GATE_VERSION = "battery-gate-plating-v2"
DECISION = "OWNER-BATTERY-GATE-PLATING-V2-01"
PLATING = "no_plating_onset"
_REPOSITORY = Path(__file__).resolve().parents[3]
#: The v2 label record whose mesh-160 margins the gate reads (sealed with
#: VALIDATOR-PLATING-REF-V2-02).
LABELS = (
    "docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json",
    "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
)
_VERDICT = {"FEASIBLE": d.PASS, "INFEASIBLE": d.FAIL, "UNRESOLVED": d.UNRESOLVED}


@lru_cache(maxsize=4)
def m160_by_case(root: str = str(_REPOSITORY)) -> dict:
    """Case id -> mesh-160 plating margin in volts, from the pinned record."""
    raw = (Path(root) / LABELS[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LABELS[1]:
        raise plating_v2.ReaderUnavailable(f"pinned {LABELS[0]} differs")
    record = json.loads(raw)
    if record.get("version") != plating_v2.VERSION:
        raise plating_v2.ReaderUnavailable("plating label record version differs")
    out = {}
    for row in record["rows"]:
        if row.get("m160_mv") is not None:
            out[row["case_id"]] = row["m160_mv"] / 1000.0
    return out


def plating_label(v2_label, margin_v, m160_v=None):
    """The v2 label for one condition, or None (v2's no claim)."""
    return v2_label(float(margin_v), None if m160_v is None else float(m160_v))


def check(contract, quantities, band, label):
    """`decision.check` with the plating verdict taken from `label` when v2
    makes a claim; temperature and CV are unchanged."""
    result = d.check(contract, quantities, band)
    if label is not None:
        result[PLATING] = _VERDICT[label["label"]]
    return result


def assess_reference(
    contract, scenario, candidates, references, case_ids=None, *, root=None
):
    """`decision.assess_reference` under the plating-v2 gate.

    `case_ids[(candidate, index)]` names each reference case for its mesh-160
    lookup; a case without one (or without an id) has no mesh-160 margin. The
    reader is loaded before any case is read, so a missing or changed reader
    refuses everything.
    """
    root = str(_REPOSITORY if root is None else root)
    v2_label = plating_v2.reader(root)
    m160 = m160_by_case(root)
    case_ids = case_ids or {}
    bands = contract["reference"]["uncertainty"]["bands"]
    out = {}
    for candidate in candidates:
        keys = [(candidate["id"], i) for i in range(len(scenario["conditions"]))]
        records = [references.get(key) for key in keys]
        if any(r is None or r.get("status") != "OK" for r in records):
            out[candidate["id"]] = {"status": d.UNAVAILABLE, "objective": None}
            continue
        per = [d.measure(contract, r["outputs"]) for r in records]
        labels = [
            plating_label(v2_label, q["plating_margin_v"], m160.get(case_ids.get(key)))
            for q, key in zip(per, keys, strict=True)
        ]
        checks = [
            check(contract, q, bands, lab) for q, lab in zip(per, labels, strict=True)
        ]
        values = [v for c in checks for v in c.values()]
        status = (
            d.INFEASIBLE
            if d.FAIL in values
            else d.UNRESOLVED if d.UNRESOLVED in values else d.FEASIBLE
        )
        out[candidate["id"]] = {
            "status": status,
            "objective": d._objective(per),
            "checks": checks,
            "violations": [d._violations(contract, q) for q in per],
            "quantities": per,
            "plating_v2": labels,
        }
    return out


def false_acceptance(contract, predictions, case_ids, refs, *, root=None):
    """`false_acceptance.component` under the plating-v2 truth.

    A reference verdict of UNRESOLVED (any constraint) is counted in
    `reference_unresolved` and enters neither rate. None when a prediction or
    reference is missing, as in EV5.
    """
    root = str(_REPOSITORY if root is None else root)
    v2_label = plating_v2.reader(root)
    m160 = m160_by_case(root)
    bands = contract["reference"]["uncertainty"]["bands"]
    counts = {
        c: {
            "reference_fail": 0,
            "false_acceptance": 0,
            "reference_pass": 0,
            "false_rejection": 0,
            "reference_unresolved": 0,
        }
        for c in CONSTRAINTS
    }
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        quantities = d.measure(contract, reference)
        label = plating_label(
            v2_label, quantities["plating_margin_v"], m160.get(case_id)
        )
        truth = check(contract, quantities, bands, label)
        said = d.check(contract, d.measure(contract, outputs))
        for constraint in CONSTRAINTS:
            row = counts[constraint]
            if truth[constraint] == d.FAIL:
                row["reference_fail"] += 1
                row["false_acceptance"] += said[constraint] == d.PASS
            elif truth[constraint] == d.PASS:
                row["reference_pass"] += 1
                row["false_rejection"] += said[constraint] == d.FAIL
            else:
                row["reference_unresolved"] += 1
    rates = {}
    for constraint, row in counts.items():
        rate = (
            row["false_acceptance"] / row["reference_fail"]
            if row["reference_fail"]
            else None
        )
        row["false_acceptance_rate"] = rate
        if rate is not None:
            rates[constraint] = rate
    worst = max(rates, key=lambda c: (rates[c], c)) if rates else None
    return {
        "gate_version": GATE_VERSION,
        "constraints": counts,
        "worst_constraint": worst,
        "worst_false_acceptance_rate": None if worst is None else rates[worst],
    }


def label_counts(contract, refs, case_ids, *, root=None):
    """How the plating-v2 truth labels `case_ids`: counts by rule and label,
    the cases v2 leaves to mesh-20, and the in-window UNRESOLVED case ids."""
    root = str(_REPOSITORY if root is None else root)
    v2_label = plating_v2.reader(root)
    m160 = m160_by_case(root)
    counts, unresolved = {}, []
    for case_id in case_ids:
        margin = d.measure(contract, refs[case_id]["outputs"])["plating_margin_v"]
        label = plating_label(v2_label, margin, m160.get(case_id))
        key = (
            "mesh20-no-v2-claim"
            if label is None
            else f"{label['rule']}:{label['label']}"
        )
        counts[key] = counts.get(key, 0) + 1
        if label is not None and label["label"] == "UNRESOLVED":
            unresolved.append(case_id)
    return {
        "gate_version": GATE_VERSION,
        "cases": len(case_ids),
        "counts": dict(sorted(counts.items())),
        "unresolved_case_ids": unresolved,
    }
