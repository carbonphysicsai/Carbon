"""Motor 1.1's sealed exam batches, producer side (Validator, 2026-10-20:
VALIDATOR_MAINNET_RECAL_DECISIONS_20261020 §4).

The F02/F08 pattern for Motor: the producer draws and solves each sealed
batch once in AX42 custody; the sealed batch becomes a private evaluation
pack in the development pack's format (`carbon.challenge_kit.motor_sealed_pack`)
graded by the dual adapter's sealed version `motor-dual-sealed-batch-30-v1`.
There is no second scoring path.

Motor 1.0's hidden pool (VALIDATOR-21, `motor_hidden`) is unchanged: its
validator answer-key path keeps 1.0. This module only adds 1.1 beside it;
`motor_source.motor_source_for` picks by the deployment file's schema.

Values: the population, solver image, terminal statuses, kinds and batch size
are Motor's own (`motor_hidden`), unchanged; three active batches; rotation
at the cadence record's 90-day maximum (OWNER-CADENCE-AND-ROTATION-02). The
rule cites the pack and evaluation versions and never restates scoring.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from . import motor_hidden

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE_ID = "electric-motor-magnetics"
CHALLENGE_VERSION = "1.1"
#: Challenge versions whose evaluation packs are built from these 1.1 sealed
#: batches: 1.1, and the backbone catalog 1.2, which changes only the
#: construction source (Validator, 2026-10-20). The batches stay 1.1's.
SERVED_VERSIONS = (CHALLENGE_VERSION, "1.2")
RULE_SCHEMA = "carbon.motor.sealed-batch-rule.v1"
DOCUMENT_SCHEMA = "carbon.motor.sealed-batch.v1"
DEPLOYMENT_SCHEMA = "carbon.motor.sealed-deployment.v1"
STORE_SCHEMA = "carbon.motor.sealed-store.v1"
AUTHORITY = "OWNER-CADENCE-AND-ROTATION-02"
SOLVER_IMAGE = motor_hidden.SOLVER_IMAGE
TERMINAL = motor_hidden.TERMINAL
KINDS = motor_hidden.KINDS
BATCH_CASES = motor_hidden.BATCH_CASES
ACTIVE_BATCHES = 3
ROTATION_EVERY_BLOCKS = 648_000  # the 90-day maximum
PACK_VERSION = "motor-normal-construction-development-2"
EVALUATION_VERSION = "motor-dual-sealed-batch-30-v1"


class MotorSealedError(ValueError):
    """Typed operator/store refusal; the code contains no submitted content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def contract_digest():
    """Motor 1.1's served construction-kit digest."""
    from carbon.challenge_kit import physical_material

    from .interface import digest

    kit = physical_material.bundle_material(CHALLENGE_ID, CHALLENGE_VERSION)[
        "construction_kit"
    ]
    return digest(kit)


def hidden_rule(repository=REPOSITORY):
    """The family's rule document; its digest is every commitment's."""
    from carbon.motor.population import POPULATION_VERSION

    return {
        "schema": RULE_SCHEMA,
        "authority": AUTHORITY,
        "status": "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING",
        "challenge": {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION},
        # Cited, never restated: the scoring producer owns the exam rule.
        "exam": {
            "pack_version": PACK_VERSION,
            "evaluation_version": EVALUATION_VERSION,
        },
        "population": {
            "version": POPULATION_VERSION,
            "law": "uniform",
            "q_equals_p": True,
        },
        "solver_image": SOLVER_IMAGE,
        "references": {"terminal": list(TERMINAL), "scored": ["OK"]},
        "kinds": list(KINDS),
        "hidden_duplicates": 0,
        "batch_cases": BATCH_CASES,
        "rotation": {"basis": "finalized_block", "every_blocks": ROTATION_EVERY_BLOCKS},
        "active_batches": ACTIVE_BATCHES,
    }


def check_document(document):
    """A sealed batch document: Motor's own case checks, at version 1.1."""
    if (
        type(document) is not dict
        or document.get("schema") != DOCUMENT_SCHEMA
        or document.get("challenge")
        != {"id": CHALLENGE_ID, "version": CHALLENGE_VERSION}
        or type(document.get("cases")) is not list
        or len(document["cases"]) != BATCH_CASES
    ):
        raise ValueError("document")
    from .motor import CHALLENGE

    # motor_hidden's checks, with the 1.0 identity it expects in place of
    # 1.1's (the inputs, population and admission are the same).
    as_hidden = dict(
        document,
        schema=motor_hidden.DOCUMENT_SCHEMA,
        challenge={"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
    )
    return motor_hidden.check_document(as_hidden)


check_reference = motor_hidden.check_reference
published_keys = motor_hidden.published_keys
overlap_key = motor_hidden.overlap_key


def load_deployment(path):
    """`{"schema", "store"}`, plus `"custody"` for the producer. Owner-only."""
    path = Path(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise MotorSealedError("motor_sealed_deployment_missing") from None
    # Checked outside the parse's `except ValueError`, which the typed error
    # (a ValueError) would otherwise be relabelled by.
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise MotorSealedError("motor_sealed_deployment_not_owner_only")
    try:
        config = json.loads(path.read_text())
    except ValueError:
        raise MotorSealedError("motor_sealed_deployment_malformed") from None
    if (
        type(config) is not dict
        or config.get("schema") != DEPLOYMENT_SCHEMA
        or not {"schema", "store"} <= set(config)
        or set(config) - {"schema", "store", "custody"}
        or not all(type(v) is str and v for v in config.values())
    ):
        raise MotorSealedError("motor_sealed_deployment_malformed")
    return config


def open_store(directory):
    from .hidden_batch_store import HiddenBatchStore

    return HiddenBatchStore(
        directory, name="motor-sealed", schema=STORE_SCHEMA, error_type=MotorSealedError
    )
