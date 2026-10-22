"""Cooling's sealed-exam family (owner-approved Cooling draw): the producer source.

Every value is Cooling's own (`cooling_hidden`); the generic draw, solve and seal
are `family_source.FamilySource`'s. Producer-only: no validator surface
imports it.

    python -m carbon.challenge_validator.cooling_source init --deployment FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch_source import ProducerRefused
from .family_source import FamilySource, ReferenceFamily

REPOSITORY = Path(__file__).resolve().parents[2]


def cooling_family():
    """Cooling's registration, from `cooling_hidden` (Validator, 2026-10-20)."""
    from carbon.cold_plate_exam.population import POPULATION_VERSION

    from . import cooling_hidden as hidden

    return ReferenceFamily(
        name="cooling",
        challenge_id=hidden.CHALLENGE_ID,
        challenge_version=hidden.CHALLENGE_VERSION,
        document_schema=hidden.DOCUMENT_SCHEMA,
        population_version=POPULATION_VERSION,
        kinds=hidden.KINDS,
        batch_cases=hidden.BATCH_CASES,
        every_blocks=hidden.ROTATION_EVERY_BLOCKS,
        active_batches=hidden.ACTIVE_BATCHES,
        runner=hidden.RUNNER,
        image=hidden.SOLVER_IMAGE,
        image_env="CARBON_COOLING_IMAGE",
        terminal=hidden.TERMINAL,
        error_type=hidden.CoolingFamilyError,
        population=hidden._source,
        rule=hidden.hidden_rule,
        contract_digest=hidden.contract_digest,
        load_deployment=hidden.load_deployment,
        open_store=hidden.open_store,
        check_document=hidden.check_document,
        check_reference=hidden.check_reference,
        published_keys=hidden.published_keys,
        overlap_key=hidden.overlap_key,
    )


class CoolingBatchSource(FamilySource):
    """Cooling's sealed batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(
            cooling_family(), deployment, repository=repository, runner=runner
        )

    @staticmethod
    def init(deployment):
        """Create the producer's Cooling custody once; return its public pin."""
        return FamilySource.init_custody(cooling_family(), deployment)


def main(argv=None):
    from . import cooling_hidden as hidden

    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.cooling_source")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    args = parser.parse_args(argv)
    try:
        result = CoolingBatchSource.init(args.deployment)
    except (ProducerRefused, hidden.CoolingFamilyError) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    from carbon.challenge_validator.cooling_source import main as _main

    sys.exit(_main())


__all__ = ["CoolingBatchSource", "cooling_family"]
