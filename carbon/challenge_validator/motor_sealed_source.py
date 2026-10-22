"""Motor 1.1's sealed-exam family: the producer source, and the selector
between it and Motor 1.0's hidden pool (Validator, 2026-10-20).

The producer finds a family by Challenge id; Motor now has two, told apart
by the deployment file's schema:
- `carbon.motor.sealed-deployment.v1` -> `MotorSealedBatchSource` (1.1, the
  sealed exam graded through the private pack);
- anything else -> `motor_source.MotorBatchSource` (1.0's hidden pool,
  VALIDATOR-21, unchanged), whose own loader refuses what it cannot read.

Producer-only: no validator surface imports it.

    python -m carbon.challenge_validator.motor_sealed_source init --deployment FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch_source import ProducerRefused
from .family_source import FamilySource, ReferenceFamily

REPOSITORY = Path(__file__).resolve().parents[2]


def motor_sealed_family():
    """Motor 1.1's registration, from `motor_sealed`."""
    from carbon.motor_exam.population import POPULATION_VERSION

    from . import motor_sealed as sealed
    from .motor_source import RUN_BATCH

    return ReferenceFamily(
        name="motor-sealed",
        challenge_id=sealed.CHALLENGE_ID,
        challenge_version=sealed.CHALLENGE_VERSION,
        document_schema=sealed.DOCUMENT_SCHEMA,
        population_version=POPULATION_VERSION,
        kinds=sealed.KINDS,
        batch_cases=sealed.BATCH_CASES,
        every_blocks=sealed.ROTATION_EVERY_BLOCKS,
        active_batches=sealed.ACTIVE_BATCHES,
        runner=RUN_BATCH,
        image=sealed.SOLVER_IMAGE,
        image_env="CARBON_MOTOR_IMAGE",
        terminal=sealed.TERMINAL,
        error_type=sealed.MotorSealedError,
        population=sealed.placed_source,
        rule=sealed.hidden_rule,
        contract_digest=sealed.contract_digest,
        load_deployment=sealed.load_deployment,
        open_store=sealed.open_store,
        check_document=sealed.check_document,
        check_reference=sealed.check_reference,
        published_keys=sealed.published_keys,
        overlap_key=sealed.overlap_key,
    )


def motor_sealed_grid_family():
    """Motor's sealed-grid registration (OWNER-MOTOR-EXAM-GRID-01), from
    `motor_sealed_grid`."""
    from carbon.motor_grid_exam.population import POPULATION_VERSION

    from . import motor_sealed_grid as grid
    from .motor_source import RUN_BATCH

    return ReferenceFamily(
        name="motor-sealed-grid",
        challenge_id=grid.CHALLENGE_ID,
        challenge_version=grid.CHALLENGE_VERSION,
        document_schema=grid.DOCUMENT_SCHEMA,
        population_version=POPULATION_VERSION,
        kinds=grid.KINDS,
        batch_cases=grid.BATCH_CASES,
        every_blocks=grid.ROTATION_EVERY_BLOCKS,
        active_batches=grid.ACTIVE_BATCHES,
        runner=RUN_BATCH,
        image=grid.SOLVER_IMAGE,
        image_env="CARBON_MOTOR_IMAGE",
        terminal=grid.TERMINAL,
        error_type=grid.MotorSealedGridError,
        population=grid.grid_source,
        rule=grid.hidden_rule,
        contract_digest=grid.contract_digest,
        load_deployment=grid.load_deployment,
        open_store=grid.open_store,
        check_document=grid.check_document,
        check_reference=grid.check_reference,
        published_keys=grid.published_keys,
        overlap_key=grid.overlap_key,
    )


class MotorSealedGridBatchSource(FamilySource):
    """Motor's sealed grid batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(
            motor_sealed_grid_family(),
            deployment,
            repository=repository,
            runner=runner,
        )

    @staticmethod
    def init(deployment):
        """Create the producer's Motor grid custody once; return its public pin."""
        return FamilySource.init_custody(motor_sealed_grid_family(), deployment)


class MotorSealedBatchSource(FamilySource):
    """Motor 1.1's sealed batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(
            motor_sealed_family(), deployment, repository=repository, runner=runner
        )

    @staticmethod
    def init(deployment):
        """Create the producer's Motor 1.1 custody once; return its public pin."""
        return FamilySource.init_custody(motor_sealed_family(), deployment)


def _schema(deployment):
    try:
        document = json.loads(Path(deployment).read_text())
    except (OSError, ValueError):
        return None
    return document.get("schema") if type(document) is dict else None


def motor_source_for(deployment, *, repository=REPOSITORY, runner=None):
    """Motor's source for a deployment file: 1.1 sealed by its schema,
    otherwise 1.0's hidden pool."""
    from . import motor_sealed, motor_sealed_grid
    from .motor_source import MotorBatchSource

    if _schema(deployment) == motor_sealed_grid.DEPLOYMENT_SCHEMA:
        return MotorSealedGridBatchSource(
            deployment, repository=repository, runner=runner
        )
    if _schema(deployment) == motor_sealed.DEPLOYMENT_SCHEMA:
        return MotorSealedBatchSource(deployment, repository=repository, runner=runner)
    return MotorBatchSource(deployment, repository=repository, runner=runner)


def main(argv=None):
    from . import motor_sealed

    parser = argparse.ArgumentParser(
        prog="carbon.challenge_validator.motor_sealed_source"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--deployment", required=True)
    init.add_argument("--grid", action="store_true")
    args = parser.parse_args(argv)
    from . import motor_sealed_grid

    source = MotorSealedGridBatchSource if args.grid else MotorSealedBatchSource
    try:
        result = source.init(args.deployment)
    except (
        ProducerRefused,
        motor_sealed.MotorSealedError,
        motor_sealed_grid.MotorSealedGridError,
    ) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    from carbon.challenge_validator.motor_sealed_source import main as _main

    sys.exit(_main())


__all__ = [
    "MotorSealedBatchSource",
    "MotorSealedGridBatchSource",
    "motor_sealed_family",
    "motor_sealed_grid_family",
    "motor_source_for",
]
