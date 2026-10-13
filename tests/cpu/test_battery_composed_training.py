"""CONSTRUCTION-CONTRACT-01 S1: the composed trainer (Levels 1-3 in one fit).

Claims tested:
1. With exactly one part, the composed trainer is that level's own trainer,
   bit for bit (Level 1's loss expression, Level 2's SpecMuon, Level 3's
   numerics), so composing can never change a single-level rebuild.
2. A combination trains deterministically: the same seed gives the same
   parameters.
3. Every part takes effect inside a combination: removing any one part
   changes the result. A part that was accepted and ignored would pass 1 and
   2 and fail here.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.battery import (
    composed_training,
    level1_worker,
    level2_worker,
    level3_worker,
    loss_terms,
)
from carbon.battery import level4 as battery
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction import loss_expressions as le

BATTERY = cr.BATTERY_CHALLENGE
SEED = 7
BASE = {
    "width": 16,
    "depth": 1,
    "steps": 48,
    "polish_steps": 6,
    "optimizer_family": "muon",
}
EXPRESSION = atk.VALID["valid_robust_l2"]
SPECTRAL = {"muon_spectral": True}
NUMERICS = {"quasi_newton_family": "bfgs", "line_search": "backtracking"}


def _strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {**BASE, **parameters},
    }


def _level(level, **parameters):
    """One level's compile of a single-level recipe: its Level-0 recipe and its
    development record."""
    found = dv.compile_development(_strategy(**parameters), dv.variant(BATTERY, level))
    return found.construction, found.reconstruction


@pytest.fixture(scope="module")
def material():
    m = battery.material()
    return m.train, battery.structure(m)


@pytest.fixture(scope="module")
def parts():
    recipe, l1 = _level(1, **{atk.FIELD: EXPRESSION})
    record = level1_worker.expression_record(l1)
    compiled = loss_terms.load(
        le, record["canonical"].encode("utf-8"), record["operation_set_document"]
    )
    _, l2 = _level(2, **SPECTRAL)
    _, l3 = _level(3, **NUMERICS)
    numerics = level3_worker.numerics_record(l3)
    return {
        "recipe": recipe,
        "loss": loss_terms.factory(le, compiled),
        "l1": record,
        "l2": level2_worker.level2_record(l2),
        "l3": numerics,
        "numerics": {
            "routine": numerics["routine"],
            "line_search": numerics["line_search"],
        },
    }


def _fit(model, material):
    train, structure = material
    return model.fit(train, structure, SEED)["params_sha256"]


def _composed(parts, material, *, loss=False, spectral=False, numerics=False):
    recipe = parts["recipe"]
    model = composed_training.build(
        recipe.family,
        recipe.settings,
        loss=parts["loss"] if loss else None,
        spectral=spectral,
        numerics=parts["numerics"] if numerics else None,
    )
    return _fit(model, material)


def test_one_part_is_that_levels_own_trainer_bit_for_bit(parts, material):
    recipe = parts["recipe"]
    own = {
        "loss": level1_worker.build_in_process(recipe, parts["l1"]),
        "spectral": level2_worker.build_in_process(recipe, parts["l2"]),
        "numerics": level3_worker.build_in_process(recipe, parts["l3"]),
    }
    for part, model in own.items():
        assert _composed(parts, material, **{part: True}) == _fit(model, material), part


@pytest.mark.parametrize(
    "combination",
    [
        ("spectral", "numerics"),
        ("loss", "spectral"),
        ("loss", "numerics"),
        ("loss", "spectral", "numerics"),
    ],
)
def test_a_combination_is_deterministic_and_every_part_takes_effect(
    parts, material, combination
):
    on = dict.fromkeys(combination, True)
    first = _composed(parts, material, **on)
    assert first == _composed(parts, material, **on)
    for removed in combination:
        fewer = {k: v for k, v in on.items() if k != removed}
        assert _composed(parts, material, **fewer) != first, removed
