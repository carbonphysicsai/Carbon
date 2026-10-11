"""Motor's hidden batches for the producer (VALIDATOR-21;
OWNER-MOTOR-HIDDEN-POOL-01). Producer-only: no validator surface imports it.

Motor is the first registered reference family (VALIDATOR-28): its source is
the generic `family_source.FamilySource` with motor's registration, and
draws, commits, solves and seals exactly as before.

- **Custody (WRAP).** The producer's motor root and append-only journal are a
  `confirmation.ConfirmationCustody` of their own, separate from battery's
  root and from every confirmation set's. Its root commitment is the
  commitment's public `seed_pin`.
- **Draw (WRAP).** `confirmation.make_batch` with motor's
  `PopulationSource`: uniform draws (Q = P) keyed by the root and the role,
  with opaque case ids, no strata and no hidden duplicates. The batch is
  committed to the journal before any use. A role is never redrawn
  differently, and a case that repeats a published motor case is refused.
- **Solve.** `scripts/dev/motor/reference/run_batch.py` in the image pinned
  by OWNER-DATA-MOTOR-01, only for cases with no terminal record yet, into a
  fresh `solve-<n>/` directory whose records are appended to
  `records.jsonl`. A rerun therefore resumes. `FAILED_INFRA` is retried,
  never stored.
- **Seal.** The terminal records are checked (their own inputs, the pinned
  image, an `OK` record's curve) and stored once. The references digest is
  the validator's own (`hidden_batch_store.references_digest`).

    python -m carbon.challenge_validator.motor_source init --deployment DEPLOYMENT.json

`init` creates the custody once and prints only its public `seed_pin`.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .batch_source import ProducerRefused
from .family_source import FamilySource, ReferenceFamily
from .motor import MotorAdapterError

REPOSITORY = Path(__file__).resolve().parents[2]
RUN_BATCH = Path("scripts/dev/motor/reference/run_batch.py")


def motor_family():
    """Motor's registration: every value is motor's own, as VALIDATOR-21
    pinned it (its hidden rule, population, runner and image)."""
    from carbon.motor.challenge import CHALLENGE, PublicMaterial
    from carbon.motor.population import POPULATION_VERSION
    from carbon.reconstruction.capability_registry import contract

    from . import motor_hidden as hidden
    from .confirmation_sources import source_for

    return ReferenceFamily(
        name="motor",
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        document_schema=hidden.DOCUMENT_SCHEMA,
        population_version=POPULATION_VERSION,
        kinds=hidden.KINDS,
        batch_cases=hidden.BATCH_CASES,
        every_blocks=hidden.ROTATION_EVERY_BLOCKS,
        active_batches=hidden.ACTIVE_BATCHES,
        runner=RUN_BATCH,
        image=hidden.SOLVER_IMAGE,
        image_env="CARBON_MOTOR_IMAGE",
        terminal=hidden.TERMINAL,
        error_type=MotorAdapterError,
        population=lambda: source_for(CHALLENGE.challenge_id),
        rule=lambda repository: hidden.hidden_rule(PublicMaterial.load(repository)),
        contract_digest=lambda: contract(CHALLENGE.challenge_id).digest,
        load_deployment=hidden.load_deployment,
        open_store=hidden.open_store,
        check_document=hidden.check_document,
        check_reference=hidden.check_reference,
        published_keys=hidden.published_keys,
        overlap_key=hidden.overlap_key,
    )


class MotorBatchSource(FamilySource):
    """Motor's hidden batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(
            motor_family(), deployment, repository=repository, runner=runner
        )

    @staticmethod
    def init(deployment):
        """Create the producer's motor custody once; return its public pin."""
        return FamilySource.init_custody(motor_family(), deployment)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.motor_source")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    args = parser.parse_args(argv)
    try:
        result = MotorBatchSource.init(args.deployment)
    except (ProducerRefused, MotorAdapterError) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.challenge_validator.motor_source import main as _main

    sys.exit(_main())


__all__ = ["MotorBatchSource", "motor_family"]
