"""A versioned trained-state digest for the battery KNN (KNN-STATE-DIGEST-01).

`recipes.KNN.fit` reports `params_sha256` as the digest of the stored TRAIN
targets only. It is held bit-identical to the exam-design campaign's research
KNN, so its meaning never changes (invariant 10). The neighbour count changes
predictions but not that digest, so two different KNNs shared one
trained-parameter identity (NOOP-CAPABILITY-AUDIT-01 §6).

`state_sha256` (schema `carbon.battery.knn-state.v1`) binds everything a
fitted KNN predicts from: `k`, `train_fraction`, the unit inputs and the
targets. `compile.rebuild` emits it beside `params_sha256`.

This module is outside `contracts.IMPLEMENTATION_MODULES` and outside the
practice worker's staged modules, so it moves no Level-0 implementation,
recipe, built-record or program digest. Carbon's pods stage it for a KNN only,
under GPU program v2 (`battery_gpu.KNN_GPU_PROGRAM`, KNN-STATE-GPU-01). A
worker that does not stage it (GPU program v1) emits no `state_sha256`, and a
record without the field keeps its meaning: `trained_identity` falls back to
`params_sha256`.
"""

from __future__ import annotations

import hashlib
import json
import operator

import numpy as np

from .recipes import KNN

SCHEMA = "carbon.battery.knn-state.v1"
#: The identity scheme of a record without a versioned state digest.
PARAMS = "params_sha256"


def _array(value):
    return np.ascontiguousarray(value, dtype="<f8")


def state_sha256(model):
    """The `carbon.battery.knn-state.v1` digest of a fitted KNN."""
    if type(model) is not KNN:
        raise TypeError("a battery KNN is required")
    if not hasattr(model, "y"):
        raise ValueError("an unfitted KNN has no state")
    inputs, targets = _array(model.u), _array(model.y)
    header = {
        "schema": SCHEMA,
        "k": operator.index(model.k),
        "train_fraction": float(model.fraction),
        "inputs": {"dtype": "<f8", "shape": list(inputs.shape)},
        "targets": {"dtype": "<f8", "shape": list(targets.shape)},
    }
    body = hashlib.sha256(
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    )
    body.update(b"\0")
    body.update(inputs.tobytes())
    body.update(targets.tobytes())
    return body.hexdigest()


def with_state(model, stats):
    """Fit statistics with the versioned state digest added for a KNN;
    every other family's statistics are returned unchanged."""
    if type(model) is not KNN:
        return stats
    return {**stats, "state_schema": SCHEMA, "state_sha256": state_sha256(model)}


def trained_identity(stats):
    """(scheme, digest): the trained-artifact identity of one fit.

    A KNN fit carrying the versioned state digest is identified by it. Any
    other fit, and any record written before the digest existed, keeps its
    `params_sha256` identity. An unknown state schema is refused rather than
    read as a different scheme.
    """
    if "state_sha256" in stats:
        if stats.get("state_schema") != SCHEMA:
            raise ValueError("unknown KNN state schema")
        return SCHEMA, stats["state_sha256"]
    return PARAMS, stats["params_sha256"]
