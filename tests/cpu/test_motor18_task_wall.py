"""Motor 1.8's whole-task wall (owner, typed in mc-exam-C, Thu 12 Nov ~21:00 CST). Only the wall the quiet MGN
measurement fails rises, to 1.5 x the measured quiet time, rounded up to the next 10 s. Every other limit, and every
other version's kit bytes, stay as they are.

Claims:
- The override is Motor 1.8's alone, and its value is the rule's arithmetic on Test Lead-C's quiet full pair (1,058 s).
- Motor 1.8's published construction-limits document carries it: build and inference stay at 648 s each.
- Every other registered physical version's total is still exactly `version_registry.task_wall_seconds`.
- The override lives host-side: no worker-image input (`build_inputs.txt`) names it, and the image's
  `version_registry` constants are unchanged.
"""

from __future__ import annotations

import importlib
import math
from pathlib import Path

import pytest

# installs the overlay (Motor 1.8)
importlib.import_module("carbon.challenge_kit.version_registry")

from carbon.challenge_kit import physical_public, task_wall_overrides, version_registry

ROOT = Path(__file__).resolve().parents[2]
MOTOR_18 = ("electric-motor-magnetics", "1.8")


def test_the_override_is_motor_1_8_s_alone_and_is_the_rules_arithmetic():
    assert set(task_wall_overrides.OVERRIDES) == {MOTOR_18}
    quiet = task_wall_overrides.MOTOR_18_QUIET_FULL_PAIR_SECONDS
    assert quiet == 1058
    assert (
        task_wall_overrides.OVERRIDES[MOTOR_18]
        == math.ceil(1.5 * quiet / 10) * 10
        == 1590
    )
    # the old wall is what the quiet measurement failed: the pair did not fit it
    assert quiet > version_registry.REBUILD_TASK_WALL_SECONDS


def _policy(challenge_id, version):
    return physical_public.trusted_material(challenge_id, version)["limits_document"][
        "reconstruction_resource_policy"
    ]


def test_motor_1_8_s_published_limits_raise_only_the_total():
    policy = _policy(*MOTOR_18)
    assert policy["total_reconstruction_wall_seconds_max"] == 1590
    assert (
        policy["build_wall_seconds_max"]
        == version_registry.REBUILD_LIMIT_SECONDS
        == 648
    )
    assert (
        policy["inference_wall_seconds_max"] == version_registry.REBUILD_LIMIT_SECONDS
    )


@pytest.mark.parametrize(
    "key",
    sorted(
        k
        for k in version_registry.VERSIONS
        if k[0] in ("electric-motor-magnetics", "chip-cold-plate") and k != MOTOR_18
    ),
)
def test_every_other_physical_version_keeps_its_total(key):
    try:
        policy = _policy(*key)
    except (ValueError, OSError, KeyError):
        pytest.skip("this version publishes no physical construction kit here")
    assert policy[
        "total_reconstruction_wall_seconds_max"
    ] == version_registry.task_wall_seconds(
        version_registry.entry(*key).rebuild_wall_seconds
    )


def test_the_override_is_host_side_and_the_image_constants_are_unchanged():
    inputs = (ROOT / "carbon/reconstruction/worker/build_inputs.txt").read_text(
        encoding="utf-8"
    )
    assert "task_wall_overrides" not in inputs
    assert (
        version_registry.REBUILD_LIMIT_SECONDS,
        version_registry.REBUILD_TASK_WALL_SECONDS,
    ) == (648, 947)
