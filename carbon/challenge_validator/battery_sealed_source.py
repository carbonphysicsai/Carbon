"""Battery's sealed-exam family (VALIDATOR_BATTERY_SEALED_RULINGS_20261022): the producer source.

Every value is Battery's own (`battery_sealed_hidden`); the generic draw, solve
and seal are `family_source.FamilySource`'s. Producer-only: no validator
surface imports it.

    python -m carbon.challenge_validator.battery_sealed_source init --deployment FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch_source import ProducerRefused
from .family_source import FamilySource, ReferenceFamily

REPOSITORY = Path(__file__).resolve().parents[2]


def battery_sealed_family():
    """Battery's sealed registration, from `battery_sealed_hidden`."""
    from carbon.battery_sealed.population import POPULATION_VERSION

    from . import battery_sealed_hidden as hidden

    return ReferenceFamily(
        name="battery_sealed",
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
        image_env="CARBON_BATTERY_SEALED_IMAGE",
        terminal=hidden.TERMINAL,
        error_type=hidden.BatterySealedError,
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


class BatterySealedSource(FamilySource):
    """Battery's sealed batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(
            battery_sealed_family(), deployment, repository=repository, runner=runner
        )

    @staticmethod
    def init(deployment):
        """Create the producer's Battery custody once; return its public pin."""
        return FamilySource.init_custody(battery_sealed_family(), deployment)


def main(argv=None):
    from . import battery_sealed_hidden as hidden

    parser = argparse.ArgumentParser(
        prog="carbon.challenge_validator.battery_sealed_source"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    args = parser.parse_args(argv)
    try:
        result = BatterySealedSource.init(args.deployment)
    except (ProducerRefused, hidden.BatterySealedError) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    from carbon.challenge_validator.battery_sealed_source import main as _main

    sys.exit(_main())


__all__ = ["BatterySealedSource", "battery_sealed_family"]
