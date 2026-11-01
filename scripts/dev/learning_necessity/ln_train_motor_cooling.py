"""The learning-necessity harness's PUBLIC TRAIN for Motor and Cooling (Validator ruling, 1 Nov ~15:10 CST).

``load_train(challenge_id, version)`` returns the version's public TRAIN ``(inputs, targets)`` for
``electric-motor-magnetics`` and ``chip-cold-plate``, the two Challenges `ln_harness.load_train` dispatches here. The
TRAIN a version uses is the one its own `version_registry` entry declares (Motor's native TRAIN; Cooling's native or,
from 1.3, its law-safe encoded TRAIN), loaded by `challenge_kit.physical_public_train`, which checks every byte against
its pin. A version the registry does not hold is refused, never mapped to a guessed TRAIN: Motor 1.7 and Cooling 1.8
load once their registration lands.

Public TRAIN only: nothing here reads a sealed, pool, exam or custody path (the test pins the import closure).
"""

from __future__ import annotations

CHALLENGES = ("electric-motor-magnetics", "chip-cold-plate")


class Refused(ValueError):
    """The Challenge or version has no registered public TRAIN here."""


def train_name(challenge_id, version):
    """The registered TRAIN name the version declares, or a refusal."""
    from carbon.challenge_kit import version_registry

    if challenge_id not in CHALLENGES:
        raise Refused("train_not_registered_for_this_challenge")
    declared = version_registry.find(challenge_id, version)
    if declared is None:
        raise Refused("version_not_registered")
    known = {
        "electric-motor-magnetics": (version_registry.MOTOR_TRAIN,),
        "chip-cold-plate": (
            version_registry.COOLING_TRAIN,
            version_registry.COOLING_TRAIN_ENCODED,
        ),
    }[challenge_id]
    if declared.train not in known:
        raise Refused("train_not_a_public_numeric_train")
    return declared.train


def load_train(challenge_id, version):
    """The version's PUBLIC TRAIN ``(inputs, targets)``, as `physical_public_train` loads and checks it."""
    from carbon.challenge_kit import physical_public_train

    train_name(challenge_id, version)
    data = physical_public_train.load_public_train(challenge_id, version)
    return data["inputs"], data["targets"]
