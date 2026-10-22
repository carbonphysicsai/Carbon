"""Motor's sealed-grid exam batches, producer side (OWNER-MOTOR-EXAM-GRID-01;
VALIDATOR_RULING_MOTOR_GRID_SPLIT_20261022).

Motor 1.1's sealed exam as a placed design x condition grid (5 x 6), so design
value (D, half the dual score) is defined. Everything but the population is
`motor_sealed`'s own (solver image, terminal statuses, kinds, rotation, the
pack and evaluation versions): the evaluation version stays
`motor-dual-sealed-batch-30-v1`, whose definition states that it is
grid-based (A and D). A grid deployment has its own schemas, so the placed-30
custody (`motor_sealed`) is never read as a grid one.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from . import motor_sealed

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = motor_sealed.CHALLENGE_ID
CHALLENGE_VERSION = motor_sealed.CHALLENGE_VERSION
SERVED_VERSIONS = motor_sealed.SERVED_VERSIONS
RULE_SCHEMA = "carbon.motor.sealed-grid-rule.v1"
DOCUMENT_SCHEMA = "carbon.motor.sealed-grid-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.motor.sealed-grid-deployment.v1"
STORE_SCHEMA = "carbon.motor.sealed-grid-store.v1"
AUTHORITY = "OWNER-MOTOR-EXAM-GRID-01"
SOLVER_IMAGE = motor_sealed.SOLVER_IMAGE
TERMINAL = motor_sealed.TERMINAL
KINDS = motor_sealed.KINDS
BATCH_CASES = motor_sealed.BATCH_CASES
ACTIVE_BATCHES = motor_sealed.ACTIVE_BATCHES
ROTATION_EVERY_BLOCKS = motor_sealed.ROTATION_EVERY_BLOCKS
PACK_VERSION = motor_sealed.PACK_VERSION
EVALUATION_VERSION = motor_sealed.EVALUATION_VERSION


class MotorSealedGridError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


contract_digest = motor_sealed.contract_digest
check_reference = motor_sealed.check_reference
published_keys = motor_sealed.published_keys
overlap_key = motor_sealed.overlap_key


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.motor_grid_exam.population import (
        CONDITIONS,
        DESIGNS,
        POPULATION_VERSION,
        WINDOW,
    )

    rule = motor_sealed.hidden_rule(repository)
    rule.update(
        schema=RULE_SCHEMA,
        population={
            "version": POPULATION_VERSION,
            "law": "placed grid",
            "grid": {"designs": DESIGNS, "conditions": CONDITIONS},
            "candidates": "carbon.motor.development-population.v1 (uniform, buildable)",
            "placement": {
                "predictor": "kernel ridge fitted on public TRAIN motor-pools-v1",
                "predicted_feasible_per_limit": list(WINDOW),
                "limits": {"mean_torque_nm": ">= 4.0", "ripple_fraction": "<= 0.30"},
                "decision": {
                    "designs_feasible_at_every_condition": [1, 3],
                    "every_condition_has_a_feasible_design": True,
                    "no_condition_where_every_design_is_feasible": True,
                },
            },
            "authority": AUTHORITY,
        },
        authority=AUTHORITY,
    )
    return rule


def check_document(document):
    """A sealed grid batch document: Motor's own case checks, and the 30 cases
    form a full 5 x 6 design x condition grid."""
    from carbon.motor_grid_exam.population import grid_of

    if type(document) is not dict or document.get("schema") != DOCUMENT_SCHEMA:
        raise ValueError("document")
    as_placed = dict(document, schema=motor_sealed.DOCUMENT_SCHEMA)
    cases = motor_sealed.check_document(as_placed)
    grid_of(list(cases.values()))
    return cases


def grid_source():
    """The grid population's draw source (OWNER-MOTOR-EXAM-GRID-01)."""
    from .confirmation_sources import PopulationSource

    return PopulationSource(CHALLENGE_ID, "motor_grid_exam", ("motor-*",))


def load_deployment(path):
    """`{"schema", "store"}`, plus `"custody"` for the producer. Owner-only."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise MotorSealedGridError("motor_sealed_grid_deployment_missing") from None
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise MotorSealedGridError("motor_sealed_grid_deployment_not_owner_only")
    try:
        config = json.loads(path.read_text())
    except ValueError:
        raise MotorSealedGridError("motor_sealed_grid_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise MotorSealedGridError("motor_sealed_grid_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory,
        name="motor-sealed-grid",
        schema=STORE_SCHEMA,
        error_type=MotorSealedGridError,
    )


__all__ = [
    "BATCH_CASES",
    "CHALLENGE_ID",
    "DEPLOYMENT_SCHEMA",
    "MotorSealedGridError",
    "check_document",
    "check_reference",
    "grid_source",
    "hidden_rule",
    "load_deployment",
    "open_store",
]
