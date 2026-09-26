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


def components(predictions, case_ids, store):
    """A member's exam components on the scoring set."""
    _rows, agg = exam.evaluate(predictions, case_ids, store)
    return {
        "eligible": bool(agg["eligible"]),
        "gate_failures": sorted(agg["gate_failures"]),
        "E": None if agg["score"] is None else float(agg["score"]),
        "E_important": (
            None if agg["important_score"] is None else float(agg["important_score"])
        ),
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
    for document in contract["scoring_candidates"]["weight_profiles"]:
        profile = parse(document)
        if not component["eligible"]:
            out[profile.profile_id] = 0.0  # gates are never rescued by weights
            continue
        try:
            out[profile.profile_id] = combine(profile, legs)
        except WeightProfileError as refused:
            out[profile.profile_id] = "NOT_MEASURABLE:" + refused.code
    return out


def load_predictions(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))
