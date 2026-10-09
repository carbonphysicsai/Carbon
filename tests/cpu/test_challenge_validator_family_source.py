"""Reference family sources (VALIDATOR-28): motor's producer source,
extracted into a generic `FamilySource` and served through one registry.

Motor's own suite (`test_challenge_validator_motor_hidden.py`) is the parity
check: it draws, solves, seals, publishes and imports through the extracted
source unchanged. These tests pin the registry, motor's registration and
that the generic source takes its runner, image and refusal codes from the
registration rather than from motor. Scripted solves only: no container,
chain, network or spend.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_motor_hidden import Solver, write_deployment

from carbon.challenge_validator import motor_hidden as hidden
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.family_source import FamilySource, family_source_class
from carbon.challenge_validator.motor_source import (
    RUN_BATCH,
    MotorBatchSource,
    motor_family,
)
from carbon.reconstruction import capability_registry as registry


def test_the_producer_finds_motor_as_a_registered_family():
    assert family_source_class(registry.MOTOR_CHALLENGE) is MotorBatchSource
    assert issubclass(MotorBatchSource, FamilySource)
    # Battery keeps its own source (its quiz and duplicates).
    assert family_source_class(registry.BATTERY_CHALLENGE) is None
    assert family_source_class("no-such-challenge") is None


def test_motors_registration_is_its_hidden_rules_own_values():
    family = motor_family()
    assert family.challenge_id == registry.MOTOR_CHALLENGE
    assert family.kinds == hidden.KINDS
    assert family.batch_cases == hidden.BATCH_CASES
    assert family.every_blocks == hidden.ROTATION_EVERY_BLOCKS
    assert family.active_batches == hidden.ACTIVE_BATCHES
    assert family.terminal == hidden.TERMINAL
    assert family.image == hidden.SOLVER_IMAGE
    assert family.image_env == "CARBON_MOTOR_IMAGE"
    assert family.runner == RUN_BATCH
    assert family.document_schema == hidden.DOCUMENT_SCHEMA


def deployment(tmp_path, **fields):
    return write_deployment(
        tmp_path / "producer-etc" / "family.json",
        store=str(tmp_path / "producer-store"),
        **fields,
    )


def test_a_family_without_custody_is_refused_by_its_own_code(tmp_path):
    toy = dataclasses.replace(motor_family(), name="toy")
    with pytest.raises(ProducerRefused) as refused:
        FamilySource(toy, deployment(tmp_path), repository=REPOSITORY)
    assert refused.value.code == "producer_toy_no_custody"


def test_the_runner_and_image_come_from_the_registration(tmp_path):
    toy = dataclasses.replace(
        motor_family(), image="toy-image", image_env="CARBON_TOY_IMAGE"
    )
    path = deployment(tmp_path, custody=str(tmp_path / "producer-custody"))
    FamilySource.init_custody(toy, path)
    solver, seen = Solver(), []

    def runner(command, check, cwd, env):
        seen.append((command[1], env["CARBON_TOY_IMAGE"]))
        # The scripted solver answers as motor's pinned image would.
        as_motor = {**env, "CARBON_MOTOR_IMAGE": hidden.SOLVER_IMAGE}
        return solver(command, check, cwd, as_motor)

    source = FamilySource(toy, path, repository=REPOSITORY, runner=runner)
    producer = pr.Producer(tmp_path / "producer", [source])
    drawn = producer.draw(toy.challenge_id, "pscreen-S1", kind="screening")
    producer.solve(toy.challenge_id, drawn["fingerprint"])
    assert seen == [(str(REPOSITORY / RUN_BATCH), "toy-image")]
    producer.seal(toy.challenge_id, drawn["fingerprint"])
    assert source.sealed(drawn["fingerprint"])["cases"] == toy.batch_cases
