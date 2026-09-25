"""Adaptive-agent extension: prepared, NOT RUN.

Replay with scripted candidates does not measure what an adaptive agent would do
with screening feedback. This module fixes the harness an adaptive run would
use, so the only missing input is authority to spend on a model provider:

* The agent may submit a recipe config (from ``recipes.RECIPES`` with bounded
  hyperparameters) and receives, per admitted submission, exactly what the exam
  returns: eligibility, the aggregate pool score and the ``pool_version``. It
  never receives per-case errors, case inputs of private batches, references or
  gate details beyond the gate names that failed.
* Rotation, pool versions and stored-model inference are the ``exam`` module's.
* Every submission is reconstructed on TRAIN v1 only, like every scripted one.

It refuses to start unless ``CARBON_EXAM_AGENT_BUDGET_USD`` names a positive
amount **and** ``CARBON_EXAM_AGENT_AUTHORITY`` names the owner record that
authorizes it. No such budget exists for campaign 1, so it has not run, and no
result in the campaign report comes from it.
"""

from __future__ import annotations

import os

ALLOWED_KEYS = {
    "recipe",
    "width",
    "depth",
    "steps",
    "lr",
    "wd",
    "pca",
    "important_weight",
    "seed",
}
BOUNDS = {
    "width": (32, 512),
    "depth": (1, 6),
    "steps": (500, 12000),
    "lr": (1e-4, 1e-2),
    "wd": (0.0, 1e-2),
    "pca": (0, 32),
    "important_weight": (0.05, 5.0),
    "seed": (0, 2**31 - 1),
}


class NotAuthorized(RuntimeError):
    pass


def authorize() -> float:
    budget = float(os.environ.get("CARBON_EXAM_AGENT_BUDGET_USD", "0") or 0)
    authority = os.environ.get("CARBON_EXAM_AGENT_AUTHORITY", "")
    if budget <= 0 or not authority:
        raise NotAuthorized(
            "adaptive-agent runs need an owner-authorized model-provider budget; none exists"
        )
    return budget


def validate_submission(sub: dict) -> dict:
    extra = set(sub) - ALLOWED_KEYS
    if extra:
        raise ValueError(f"unknown submission keys: {sorted(extra)}")
    for k, (lo, hi) in BOUNDS.items():
        if k in sub and not (lo <= sub[k] <= hi):
            raise ValueError(f"{k}={sub[k]} outside [{lo}, {hi}]")
    return sub


def feedback(score_record: dict) -> dict:
    """What the agent sees after an admitted submission - nothing per case."""
    return {
        "eligible": score_record["eligible"],
        "score": score_record["score"],
        "pool_version": score_record["pool_version"],
        "failed_gates": sorted(score_record.get("gate_failures", {})),
    }
