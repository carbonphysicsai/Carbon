"""F02's sealed-exam family (OWNER-F02-F08-EXAM-DRAW-01): the producer source.

Every value is F02's own (`f02_hidden`); the generic draw, solve and seal
are `family_source.FamilySource`'s. Producer-only: no validator surface
imports it.

    python -m carbon.challenge_validator.f02_source init --deployment FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch_source import ProducerRefused
from .family_source import FamilySource, ReferenceFamily

REPOSITORY = Path(__file__).resolve().parents[2]


def f02_family():
    """F02's registration, from `f02_hidden` (Validator, 2026-10-20)."""
    from carbon.f02.population import POPULATION_VERSION

    from . import f02_hidden as hidden
    from .confirmation_sources import source_for

    return ReferenceFamily(
        name="f02",
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
        image_env="CARBON_F02_IMAGE",
        terminal=hidden.TERMINAL,
        error_type=hidden.F02FamilyError,
        population=lambda: source_for(hidden.CHALLENGE_ID),
        rule=hidden.hidden_rule,
        contract_digest=hidden.contract_digest,
        load_deployment=hidden.load_deployment,
        open_store=hidden.open_store,
        check_document=hidden.check_document,
        check_reference=hidden.check_reference,
        published_keys=hidden.published_keys,
        overlap_key=hidden.overlap_key,
    )


class F02BatchSource(FamilySource):
    """F02's sealed batches, drawn and solved once on the producer."""

    def __init__(self, deployment, *, repository=REPOSITORY, runner=None):
        super().__init__(f02_family(), deployment, repository=repository, runner=runner)

    @staticmethod
    def init(deployment):
        """Create the producer's F02 custody once; return its public pin."""
        return FamilySource.init_custody(f02_family(), deployment)


def main(argv=None):
    from . import f02_hidden as hidden

    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.f02_source")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init").add_argument("--deployment", required=True)
    args = parser.parse_args(argv)
    try:
        result = F02BatchSource.init(args.deployment)
    except (ProducerRefused, hidden.F02FamilyError) as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    from carbon.challenge_validator.f02_source import main as _main

    sys.exit(_main())


__all__ = ["F02BatchSource", "f02_family"]
