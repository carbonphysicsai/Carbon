# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Scoring rules under test, computed on a fixed scoring set.

Components, with the metric definitions and transforms held fixed across
every weight profile (changing them is a separate experimental factor):

- **physics**: NOT_MEASURABLE for battery. The exam's gates (bounds,
  initial values, determinism) are mandatory checks, not a physics score,
  and no defensible physics measurement exists. A profile that gives physics
  positive weight is therefore reported NOT_MEASURABLE, never computed with a
  constant.
- **robustness**: `1/(1+E_important)`, where `E_important` is the mean
  normalized case error over the published important region (reference
  plating margin within 5 mV, or peak temperature at or above 55 °C). It
  needs every output; it differs from accuracy by weighting only the
  constraint-relevant region. A model cannot satisfy it by construction: it
  is an error against the reference.
- **accuracy**: `1/(1+E)`, where `E` is the mean normalized case error over
  all scorable cases (the exam's `score`).

Gates are mandatory under every rule. An ineligible model scores 0 under
every profile and ranks last under the control.

The control is the approved `carbon.battery.exam.v1` rule: gates, then the
lowest mean normalized case error.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.scoring.weight_profile import WeightProfileError, combine, parse

from .. import exam
from ..calibration import SHAPES, frozen_calibration
from ..challenge import PublicMaterial
from . import decision as d

SCORING_REFERENCES = (
    "docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/"
    "records.jsonl"
)
CONTROL = "control-exam-v1"


def scoring_set(repository):
    """The fixed scoring set and its identity: the retained private-role
    references, unrefined, one record per case."""
    path = Path(repository) / SCORING_REFERENCES
    body = path.read_bytes()
    refs = {}
    for line in body.splitlines():
        if line.strip():
            record = json.loads(line)
            if not record.get("refined"):
                refs[record["case_id"]] = record
    material = PublicMaterial.load(repository)
    ocv = {
        c: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for c, r in refs.items()
        if r.get("inputs")
    }
    tol, scales = frozen_calibration(repository)
    store = exam.CaseStore(refs, ocv, tol, scales, SHAPES, {})
    identity = {
        "path": SCORING_REFERENCES,
        "sha256": hashlib.sha256(body).hexdigest(),
        "cases": len(refs),
        "note": "hidden duplicates are not in this set, so the paired_repeat "
        "gate is not exercised here",
    }
    return store, sorted(refs), identity


def batches(case_ids):
    """Scoring-set batches, by case-id role prefix (for stability checks)."""
    out = {}
    for c in case_ids:
        out.setdefault(c.rsplit("-", 1)[0], []).append(c)
    return out


def components(predictions, case_ids, store, contract=None):
    """A member's exam components on the scoring set; with a contract that
    declares decision-aware profiles, also its decision agreement."""
    _rows, agg = exam.evaluate(predictions, case_ids, store)
    out = {
        "eligible": bool(agg["eligible"]),
        "gate_failures": sorted(agg["gate_failures"]),
        "E": None if agg["score"] is None else float(agg["score"]),
        "E_important": (
            None if agg["important_score"] is None else float(agg["important_score"])
        ),
    }
    if contract is not None and contract["scoring_candidates"].get(
        "decision_aware_profiles"
    ):
        out["decision"] = decision_agreement(contract, predictions, case_ids, store)
    return out


def decision_agreement(contract, predictions, case_ids, store):
    """Does the model make the contract's constraint calls correctly?

    For every scoring-set case and every contract constraint, the model's
    call (PASS or FAIL, from its own predictions, no band) is compared with
    the reference's (with the contract's uncertainty bands; an UNRESOLVED
    reference call is excluded, never forced). A false acceptance (model
    PASS, reference FAIL) costs the contract's `false_acceptance`; a false
    rejection costs its `missed_opportunity`. The component is
    1/(1 + mean cost per resolved call), in (0, 1]. No new number is chosen
    here: the constraints, bands and costs are the contract's.
    """
    bands = contract["reference"]["uncertainty"]["bands"]
    costs = contract["mistake_costs"]
    total = calls = false_acceptances = false_rejections = 0
    for case_id in case_ids:
        outputs = predictions.get(case_id)
        reference = store.refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        said = d.check(contract, d.measure(contract, outputs))
        truth = d.check(contract, d.measure(contract, reference), bands)
        for constraint, verdict in truth.items():
            if verdict == d.UNRESOLVED:
                continue
            calls += 1
            if said[constraint] == d.PASS and verdict == d.FAIL:
                false_acceptances += 1
                total += costs["false_acceptance"]
            elif said[constraint] == d.FAIL and verdict == d.PASS:
                false_rejections += 1
                total += costs["missed_opportunity"]
    if calls == 0:
        return None
    return {
        "score": 1.0 / (1.0 + total / calls),
        "calls": calls,
        "false_acceptances": false_acceptances,
        "false_rejections": false_rejections,
    }


def rule_scores(contract, component):
    """Every candidate rule's score for one member (higher is better)."""
    out = {}
    if component["eligible"] and component["E"] is not None:
        out[CONTROL] = -component["E"]
    else:
        out[CONTROL] = None  # ineligible: ranked last under the control
    legs = {
        "physics": None,  # NOT_MEASURABLE for battery
        "robustness": (
            None
            if component["E_important"] is None
            else 1.0 / (1.0 + component["E_important"])
        ),
        "accuracy": None if component["E"] is None else 1.0 / (1.0 + component["E"]),
    }
    decision = component.get("decision")
    decision_legs = {
        **legs,
        # Decision-aware profiles: the robustness leg is the decision
        # agreement instead of the important-region error (a separate
        # experimental factor; the weights keep their meaning).
        "robustness": None if decision is None else decision["score"],
    }
    families = (
        (contract["scoring_candidates"]["weight_profiles"], legs),
        (
            contract["scoring_candidates"].get("decision_aware_profiles", []),
            decision_legs,
        ),
    )
    for documents, measured in families:
        for document in documents:
            profile = parse(document)
            if not component["eligible"]:
                out[profile.profile_id] = 0.0  # gates are never rescued by weights
                continue
            try:
                out[profile.profile_id] = combine(profile, measured)
            except WeightProfileError as refused:
                out[profile.profile_id] = "NOT_MEASURABLE:" + refused.code
    return out


def load_predictions(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))
