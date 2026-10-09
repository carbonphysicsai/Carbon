"""Motor passes the reference family conformance kit (VALIDATOR-28 slice 4).

Motor is the reference family: the kit's every check runs on motor's own
registration, validator and scripted runner. A new family's test module is
this file with its own pieces.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from family_conformance import CHECKS, FamilyUnderTest, check_family
from test_challenge_validator_motor_hidden import Solver, validator, write_deployment

from carbon.challenge_validator.motor_source import motor_family

MOTOR = FamilyUnderTest(
    family=motor_family(),
    deployment=write_deployment,
    validator=validator,
    runner=lambda fail=(): Solver(fail=fail),
)


@pytest.mark.parametrize("check", CHECKS, ids=lambda check: check.__name__)
def test_motor_passes_each_conformance_check(check, tmp_path):
    check(MOTOR, tmp_path)


def test_the_kit_runs_every_check(tmp_path, monkeypatch):
    import family_conformance

    ran = []
    monkeypatch.setattr(
        family_conformance,
        "CHECKS",
        tuple(lambda fut, d, name=c.__name__: ran.append(name) for c in CHECKS),
    )
    check_family(MOTOR, tmp_path)
    assert ran == [check.__name__ for check in CHECKS]
