"""The compile fixture can express a model size, not only a step count.

C-CORE-19's N3 widened the *training length*. Every determinism result Carbon
holds was still measured on one model shape - `width=8`, `n_modes=8`, 4,696
parameters - because the fixture could express no other.

Those are different dimensions and only one of them changes kernels. With
`--xla_gpu_autotune_level=0` pinned, the kernel is fixed **per shape**: a larger
step count runs the *same* kernel more times, while a different width or mode
count selects a **different fixed kernel whose determinism is untested**. A
determinism result at `width=8` therefore says little about the kernels a real
workload takes.

Widening is opt-in for the same reason it was for steps: the surfaces live in the
parameter catalog, so adding them changes its digest and therefore every plan
digest derived from it. A caller that does not ask gets exactly the contract it
always got, and that is asserted here rather than assumed.

Bounds come from the registered catalog `carbon.burgers-autoresearch-recipes.v1`
(`research_catalog.SURFACES`), not from this file's judgement.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from c02_fixtures import compile_c02_plan

from carbon.reconstruction.profile import compile_development_profile

# The digest the fixture produced before it could express a model size. Written
# down so that widening cannot quietly move it.
DEFAULT_PLAN_DIGEST = (
    "sha256:cf927795afab440a864bd9137cb5368659ec673167b0b17f990a70f98962b4b8"
)


def _plan(**kwargs):
    return compile_c02_plan(Path(tempfile.mkdtemp()), **kwargs)


def _model(**kwargs):
    return json.loads(compile_development_profile(_plan(**kwargs)).model_config_json)


# --- the default is untouched --------------------------------------------------


def test_the_default_plan_digest_is_unchanged():
    """The whole point of making it opt-in."""
    assert _plan().to_ref().content_digest == DEFAULT_PLAN_DIGEST
    assert _plan(steps=2).to_ref().content_digest == DEFAULT_PLAN_DIGEST


def test_the_default_model_shape_is_unchanged():
    """4,696 parameters, which every prior determinism result was measured on."""
    model = _model()
    assert model["width"] == 8
    assert model["n_modes"] == 8


# --- the requested shape reaches the model -------------------------------------


@pytest.mark.parametrize(
    "width,n_modes",
    [(24, 16), (32, 16), (32, 32), (64, 32), (128, 64), (2, 2)],
)
def test_the_requested_shape_reaches_the_model_config(width, n_modes):
    model = _model(width=width, n_modes=n_modes)
    assert model["width"] == width
    assert model["n_modes"] == n_modes


@pytest.mark.parametrize("backbone", ["fno", "deeponet"])
def test_both_backbones_take_the_widened_catalog(backbone):
    model = _model(backbone=backbone, width=32, n_modes=16)
    assert model["width"] == 32


def test_the_model_scale_composes_with_the_step_count():
    """The two widenings are independent and must not interfere."""
    profile = compile_development_profile(_plan(steps=32, width=32, n_modes=16))
    assert json.loads(profile.train_config_json)["steps"] == 32
    model = json.loads(profile.model_config_json)
    assert (model["width"], model["n_modes"]) == (32, 16)


def test_different_shapes_are_different_plans():
    """A model shape is part of the strategy, so it must change its identity."""
    digests = {
        _plan(width=w, n_modes=m).to_ref().content_digest
        for w, m in ((8, 8), (24, 16), (32, 16), (32, 32))
    }
    assert len(digests) == 4


def test_widening_the_shape_changes_the_digest_away_from_the_default():
    assert _plan(width=32, n_modes=16).to_ref().content_digest != DEFAULT_PLAN_DIGEST


# --- the registered bounds are enforced, not reinterpreted ----------------------


@pytest.mark.parametrize("width", [1, 0, -2, 130, 3, 25, "32", 32.0, None])
def test_a_malformed_width_is_refused(width):
    with pytest.raises((ValueError, TypeError)):
        _plan(width=width, n_modes=16)


@pytest.mark.parametrize("n_modes", [1, 0, -2, 66, 3, 15, "16", 16.0])
def test_a_malformed_mode_count_is_refused(n_modes):
    with pytest.raises((ValueError, TypeError)):
        _plan(width=32, n_modes=n_modes)


def test_odd_values_are_refused_rather_than_silently_aliased():
    """`n_modes` allocates floor(n/2)+1 modes, so an odd value aliases the even
    one below it - an ignored degree of freedom the registered catalog rejects.
    Accepting it here would mean running a model the caller did not ask for.
    """
    with pytest.raises(ValueError):
        _plan(width=32, n_modes=15)
    with pytest.raises(ValueError):
        _plan(width=31, n_modes=16)


@pytest.mark.parametrize("pair", [(32, None), (None, 16)])
def test_the_two_surfaces_must_be_widened_together(pair):
    """One alone would produce a shape no registered recipe describes."""
    width, n_modes = pair
    with pytest.raises(ValueError):
        _plan(width=width, n_modes=n_modes)


def test_the_bounds_match_the_registered_catalog():
    """Read from the catalog rather than restated, so a change there fails here."""
    from carbon.development_session.research_catalog import SURFACES

    _group, _type, width_min, width_max, _default, _arch = SURFACES["width"]
    assert (width_min, width_max) == (2, 128)
    _group, _type, mode_min, mode_max, _default, _arch = SURFACES["n_modes"]
    assert (mode_min, mode_max) == (2, 64)

    # The extremes the catalog admits must actually compile.
    assert _model(width=width_max, n_modes=mode_max)["width"] == width_max
    assert _model(width=width_min, n_modes=mode_min)["width"] == width_min
