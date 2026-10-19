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

import hashlib
import json
from pathlib import Path

from carbon.battery import challenge, practice
from carbon.battery.construction_bundle_material import (
    PHYSICS_PATH,
    PHYSICS_SHA256,
    bundle_material,
)

_REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = challenge.CHALLENGE.challenge_id
#: -2: each PRACTICE reference row carries its battery-plating-ref-v2 label.
PACK_VERSION = "battery-normal-construction-development-2"
_EV4 = (
    "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    "fc6f504f3ff69b3add10099056b7a652a28112d3ca1d63ada2fb194aac2d3e18",
)
#: The sealed plating reference (VALIDATOR-PLATING-REF-V2-02, sealed on #1316).
_PLATING_LABELS = (
    "docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json",
    "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069",
)
_PLATING_READER = (
    "scripts/dev/battery/plating_rereference.py",
    "dc8fe7f3f2cadb1993a9fce125ed44d292583e81576de10863e99bd5137351bc",
)
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
    if version != challenge.CHALLENGE.version:
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


def _v2_label():
    """The sealed reference's own reader, `plating_rereference.v2_label`,
    loaded from its pinned file (standard library only)."""
    import importlib.util

    _pinned(_PLATING_READER)
    spec = importlib.util.spec_from_file_location(
        "carbon_plating_rereference", _REPOSITORY / _PLATING_READER[0]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.v2_label


def practice_plating_labels(records) -> list:
    """Each PRACTICE case's v2 plating label from its mesh-20 margin.

    No PRACTICE case has a mesh-160 re-solve, so a case inside the v2 window
    is `pending-m160-r1` UNRESOLVED and is never a mesh-20 FEASIBLE; None is
    v2's own "no claim" (|m20| >= 15 mV).
    """
    v2_label = _v2_label()
    return [v2_label(float(r["outputs"]["plating_margin_v"])) for r in records]


def public_roles(version: str) -> dict[str, bytes]:
    """Bound public roles' exact bytes; accuracy_definition stays HUMAN_INPUT."""
    _check(version)
    material = bundle_material(_REPOSITORY)
    physics_raw = (_REPOSITORY / PHYSICS_PATH).read_bytes()
    if hashlib.sha256(physics_raw).hexdigest() != PHYSICS_SHA256:
        raise ValueError("pinned Battery physics contract differs")
    ev4 = json.loads(_pinned(_EV4))
    source = {"path": _EV4[0], "sha256": _EV4[1]}
    challenge_identity = {"id": CHALLENGE_ID, "version": version}
    return {
        "construction_kit": _canonical(material["construction_kit"]),
        "interface": _canonical(material["interface_document"]),
        "train": material["train"],
        "physics_contract": physics_raw,
        "important_limit_definition": _canonical(
            {
                "schema": "carbon.battery.important-limit-definition.v1",
                "challenge": challenge_identity,
                "constraints": ev4["constraints"],
                "source": source,
                "plating_reference": plating_reference(),
            }
        ),
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
    """The public PRACTICE set the receiver scores, as the exposed bank."""
    _check(version)
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
