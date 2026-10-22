"""The plating-v2 gate's reference assessment, importable by a miner-reachable
module (Phase A; Validator ruling on Battery's public measure).

``gate_plating_v2`` imports ``margins`` (for one constant), and ``margins``
imports the battery panel, whose attack harness no miner-reachable module may
import (OWNER-GRAPHITE-ATTACKER-01). This module carries the functions Battery's
public practice measure needs, byte-for-byte the same logic and pins, without
that edge. ``tests/cpu/test_battery_public_dual.py`` pins every function equal to
``gate_plating_v2``'s on fixtures. DEVELOPMENT only; it reads the same pinned
label record and reader, never anything the exam keeps private.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from carbon.battery import plating_v2

from . import decision as d

GATE_VERSION = "battery-gate-plating-v2"
PLATING = "no_plating_onset"
_REPOSITORY = Path(__file__).resolve().parents[3]
LABELS = (
    "docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json",
    "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
)
M20_BINDING_TOLERANCE_MV = 1e-9
_VERDICT = {"FEASIBLE": d.PASS, "INFEASIBLE": d.FAIL, "UNRESOLVED": d.UNRESOLVED}


class M160BindingRefused(plating_v2.ReaderUnavailable):
    """A label row's case id matched but its mesh-20 margin did not."""

    code = "plating_v2_m20_mismatch"


@lru_cache(maxsize=4)
def m160_by_case(root: str = str(_REPOSITORY)) -> dict:
    """Case id -> (recorded mesh-20 margin in mV, mesh-160 margin in volts)."""
    raw = (Path(root) / LABELS[0]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LABELS[1]:
        raise plating_v2.ReaderUnavailable(f"pinned {LABELS[0]} differs")
    record = json.loads(raw)
    if record.get("version") != plating_v2.VERSION:
        raise plating_v2.ReaderUnavailable("plating label record version differs")
    out = {}
    for row in record["rows"]:
        if row.get("m160_mv") is not None:
            if row["case_id"] in out:
                raise plating_v2.ReaderUnavailable("plating label case id repeats")
            out[row["case_id"]] = (float(row["m20_mv"]), row["m160_mv"] / 1000.0)
    return out


def bound_m160(entry, margin_v):
    """The mesh-160 margin of a matched label row, or None without a row; a row
    binds only if its recorded m20 equals the measured margin."""
    if entry is None:
        return None
    m20_mv, m160_v = entry
    measured_mv = float(margin_v) * 1000.0
    if m20_mv != measured_mv and abs(m20_mv - measured_mv) > M20_BINDING_TOLERANCE_MV:
        raise M160BindingRefused(M160BindingRefused.code)
    return m160_v


def plating_label(v2_label, margin_v, m160_v=None):
    """The v2 label for one condition, or None (v2's no claim)."""
    return v2_label(float(margin_v), None if m160_v is None else float(m160_v))


def check(contract, quantities, band, label):
    """`decision.check` with the plating verdict taken from `label` when v2 makes
    a claim; temperature and CV are unchanged."""
    result = d.check(contract, quantities, band)
    if label is not None:
        result[PLATING] = _VERDICT[label["label"]]
    return result


def assess_reference(
    contract, scenario, candidates, references, case_ids=None, *, root=None
):
    """`decision.assess_reference` under the plating-v2 gate."""
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
            plating_label(
                v2_label,
                q["plating_margin_v"],
                bound_m160(m160.get(case_ids.get(key)), q["plating_margin_v"]),
            )
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
