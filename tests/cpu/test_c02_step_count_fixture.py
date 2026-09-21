"""The compile fixture can express a step count other than two.

Every determinism result to date - the CPU instruction-set finding, the gate
margin figures, and the GPU characterization - was measured on two training
steps and 4,696 parameters, because the fixture could not express anything else.
It pinned the count in three independent places: the parameter domain, the
compatibility rows, and the training support contract's resource lookup. Missing
any one of them fails the compile rather than silently producing a plan that
trains a different number of steps.

Widening is opt-in. The levels live in the training support contract, so changing
them changes its digest and therefore every plan digest derived from it. A caller
that asks for the default must get the contract it always got, and that is
asserted here rather than assumed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from b02b_fixtures import make_compile_fixture
from c02_fixtures import compile_c02_plan

from carbon.reconstruction.profile import compile_development_profile

# The digest the default fixture produced before it could express anything else.
# It is written down so that widening cannot quietly move it.
DEFAULT_PLAN_DIGEST = (
    "sha256:cf927795afab440a864bd9137cb5368659ec673167b0b17f990a70f98962b4b8"
)


_DEFAULT = object()


def _plan(steps=_DEFAULT, **kwargs):
    root = Path(tempfile.mkdtemp())
    if steps is _DEFAULT:
        return compile_c02_plan(root, **kwargs)
    return compile_c02_plan(root, steps=steps, **kwargs)


def test_the_default_plan_digest_is_unchanged():
    """The whole point of making it opt-in."""
    assert _plan().to_ref().content_digest == DEFAULT_PLAN_DIGEST
    assert _plan(steps=2).to_ref().content_digest == DEFAULT_PLAN_DIGEST


def test_the_default_contract_is_unchanged():
    """Callers that never asked for more steps keep their exact contract."""
    default = make_compile_fixture(Path(tempfile.mkdtemp()))
    explicit = make_compile_fixture(Path(tempfile.mkdtemp()), sampling_levels=(1, 2))
    assert (
        default.assembly.training_support_ref == explicit.assembly.training_support_ref
    )


@pytest.mark.parametrize("steps", [2, 4, 8, 32])
def test_the_compiled_plan_carries_the_requested_step_count(steps):
    profile = compile_development_profile(_plan(steps=steps))
    assert json.loads(profile.train_config_json)["steps"] == steps


def test_different_step_counts_are_different_plans():
    """A step count is part of the strategy, so it must change its identity."""
    digests = {_plan(steps=s).to_ref().content_digest for s in (2, 8, 32)}
    assert len(digests) == 3


@pytest.mark.parametrize("steps", [0, -1, "2", 2.0, None])
def test_a_malformed_step_count_is_refused(steps):
    with pytest.raises((ValueError, TypeError)):
        _plan(steps=steps)


def test_a_single_step_is_refused_by_the_training_contract():
    """Two is the floor, and it is the training contract's floor, not the fixture's.

    `DEFAULT_TRAIN_CONFIG` carries `warmup_steps: 1`, and the profile requires
    `0 <= warmup_steps < steps`. A one-step run would have to be entirely warmup.
    The fixture compiles the plan and the profile refuses it, which is the
    correct division: widening the fixture did not widen what training accepts.
    """
    from carbon.reconstruction.model import ReconstructionFailure

    with pytest.raises(ReconstructionFailure):
        compile_development_profile(_plan(steps=1))


@pytest.mark.parametrize("levels", [(), (2, 1), (1, 1), (0,), (1, "2"), [1, 2]])
def test_malformed_sampling_levels_are_refused(levels):
    with pytest.raises(ValueError):
        make_compile_fixture(Path(tempfile.mkdtemp()), sampling_levels=levels)


def test_widening_reaches_all_three_pins():
    """A domain widened without its resource lookup fails the compile.

    This is the check that the three pins move together. If only the domain and
    the rows had been widened, the compile would fail at the resource lookup -
    which is exactly what happened when this was first attempted.
    """
    profile = compile_development_profile(_plan(steps=32))
    assert json.loads(profile.train_config_json)["steps"] == 32


@pytest.mark.parametrize("backbone", ["fno", "deeponet"])
def test_both_backbones_widen(backbone):
    profile = compile_development_profile(_plan(steps=8, backbone=backbone))
    assert json.loads(profile.train_config_json)["steps"] == 8
