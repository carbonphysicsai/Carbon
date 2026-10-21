"""Step-2 batch: every scoring adapter registers each Challenge version by its
exact string, with its own evaluation version and no default
(STEP2_BATCH_VERSIONS_20261020)."""

import pytest

from carbon.scoring import battery_dual_pack as battery
from carbon.scoring import cooling_dual_pack as cooling
from carbon.scoring import f02_dual_pack as f02
from carbon.scoring import f08_dual_pack as f08
from carbon.scoring import motor_dual_pack as motor
from carbon.scoring import physical_adapters
from carbon.scoring import physical_dual_pack as physical

EVALUATION_VERSIONS = {
    (motor.CHALLENGE, "1.0"): "motor-dual-development-bank-90-v2",
    (motor.CHALLENGE, "1.1"): "motor-dual-development-bank-90-v3",
    (motor.CHALLENGE, "1.2"): "motor-dual-development-bank-90-v3",
    (cooling.CHALLENGE, "1.0"): "cooling-dual-development-bank-48-v2",
    (cooling.CHALLENGE, "1.1"): "cooling-dual-development-bank-48-v3",
    (f08.CHALLENGE, "1.0"): "f08-dual-accepted-bank-8-v1",
    (f08.CHALLENGE, "1.1"): "f08-dual-near-limit-bank-8-v1",
    (f08.CHALLENGE, "1.2"): "f08-dual-near-limit-bank-8-v2",
    (f02.CHALLENGE, "2.0"): "f02-dual-development-bank-8-v1",
    (f02.CHALLENGE, "2.1"): "f02-dual-development-bank-8-v2",
    (battery.CHALLENGE, "2.0"): "battery-dual-development-bank-v2",
    # Allowlist v7's catalog versions: each its predecessor's.
    (motor.CHALLENGE, "1.3"): "motor-dual-development-bank-90-v3",
    (cooling.CHALLENGE, "1.2"): "cooling-dual-development-bank-48-v3",
    (f08.CHALLENGE, "1.3"): "f08-dual-near-limit-bank-8-v2",
    (f02.CHALLENGE, "2.2"): "f02-dual-development-bank-8-v2",
    (battery.CHALLENGE, "2.1"): "battery-dual-development-bank-v2",
}


@pytest.mark.parametrize("key", sorted(EVALUATION_VERSIONS))
def test_each_registered_version_has_its_own_evaluation_version(key):
    physical_adapters.register(battery)
    challenge, version = key
    chosen = physical_adapters.adapter(challenge, version)
    assert chosen is not None
    assert (chosen.CHALLENGE, chosen.VERSION) == key
    assert chosen.EVALUATION_VERSION == EVALUATION_VERSIONS[key]


#: Versions the Validator ruled are one measurement under one name (Motor 1.2
#: is 1.1's bank, physics and roles with only the construction kit changed).
SHARED = {
    (motor.CHALLENGE, "1.2"): (motor.CHALLENGE, "1.1"),
    # Allowlist v7's catalog versions differ only in the served allowlist.
    (motor.CHALLENGE, "1.3"): (motor.CHALLENGE, "1.2"),
    (cooling.CHALLENGE, "1.2"): (cooling.CHALLENGE, "1.1"),
    (f08.CHALLENGE, "1.3"): (f08.CHALLENGE, "1.2"),
    (f02.CHALLENGE, "2.2"): (f02.CHALLENGE, "2.1"),
    (battery.CHALLENGE, "2.1"): (battery.CHALLENGE, "2.0"),
}


def test_evaluation_versions_repeat_only_where_ruled_shared():
    values = [v for k, v in EVALUATION_VERSIONS.items() if k not in SHARED]
    assert len(values) == len(set(values))
    for key, same in SHARED.items():
        assert EVALUATION_VERSIONS[key] == EVALUATION_VERSIONS[same]


def test_motor_1_2_is_1_1s_measurement():
    one_two = physical_adapters.adapter(motor.CHALLENGE, "1.2")
    one_one = physical_adapters.adapter(motor.CHALLENGE, "1.1")
    assert one_two.CASE_ID == one_one.CASE_ID
    assert one_two.measure is one_one.measure


@pytest.mark.parametrize(
    "challenge, version",
    [
        (motor.CHALLENGE, "1.4"),
        (motor.CHALLENGE, None),
        (cooling.CHALLENGE, "2.0"),
        (f08.CHALLENGE, "1.4"),
        (f02.CHALLENGE, "1.0"),
        (battery.CHALLENGE, "1.0"),
        ("unregistered-challenge", "1.0"),
    ],
)
def test_an_unregistered_version_is_unavailable_never_a_default(challenge, version):
    physical_adapters.register(battery)
    assert physical_adapters.adapter(challenge, version) is None


def test_a_version_variant_measures_with_its_adapters_own_files():
    variant = physical_adapters.adapter(motor.CHALLENGE, "1.1")
    assert type(variant) is physical.Variant
    assert variant.FILES == motor.FILES
    assert variant.measure is motor.measure
    assert physical.producer_digest(variant) == physical.producer_digest(motor)


@pytest.mark.parametrize("key", sorted(SHARED))
def test_a_shared_version_is_its_predecessors_measurement(key):
    physical_adapters.register(battery)
    one, same = physical_adapters.adapter(*key), physical_adapters.adapter(*SHARED[key])
    assert one.CASE_ID == same.CASE_ID
    assert one.measure is same.measure
    assert physical.producer_digest(one) == physical.producer_digest(same)
