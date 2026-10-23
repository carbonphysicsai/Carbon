"""A receiver's rebuild reservation is the registered rebuild limit (Validator,
VALIDATOR_RULING_REBUILD_WALL_PROVISIONAL_20261022, amendment 2): 1,800 s on testnet until
the measured wall replaces it. A lower reservation silently refuses builds the limit
admits (Battery CZ003); past the limit the stop stays a typed resource refusal."""

import pytest

from carbon.development_session import local_diagnostic_plan
from carbon.reconstruction.worker import model


def test_the_reservation_equals_the_registered_limit():
    assert model.PRODUCTIVE_DEADLINE_SECONDS == model.REBUILD_LIMIT_SECONDS == 1800
    # The same number the registered total wall carries, in an independent place.
    assert local_diagnostic_plan.MAX_TASK_WALL_SECONDS == model.REBUILD_LIMIT_SECONDS


def test_a_launch_defaults_to_the_limit_and_may_only_be_narrowed():
    timing = model.WorkerTiming(100.0, 100.0 + model.REBUILD_LIMIT_SECONDS, 5.0, "boot")
    assert timing.deadline_seconds == model.REBUILD_LIMIT_SECONDS
    with pytest.raises(Exception):
        model.WorkerTiming(
            100.0,
            100.0 + model.REBUILD_LIMIT_SECONDS + 1,
            5.0,
            "boot",
            deadline_seconds=model.REBUILD_LIMIT_SECONDS + 1,
        )


def test_past_the_limit_the_stop_is_a_typed_deadline_refusal():
    assert model.WorkerCode.DEADLINE.value == "reconstruction.worker.deadline.exceeded"


def test_the_served_synthetic_policy_carries_the_same_limit():
    from carbon.challenge_kit import synthetic_linear_field_2d as kit

    source = open(kit.__file__, encoding="utf-8").read()
    policy = f'"build_wall_seconds_max": {model.REBUILD_LIMIT_SECONDS},'
    assert policy in source
    assert f'"inference_wall_seconds_max": {model.REBUILD_LIMIT_SECONDS},' in source
