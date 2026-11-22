"""Custody accepts a trainer-v3 ensemble's fit receipt with its training curve (DATA D2), and nothing looser.

`physical_graph_adapter_v2.fit` adds ``curve`` (`physical_graph_trainer_v3.curve_block`) to the fit receipt of a v3-trainer
graph. ScoreLab custody (`public_unbound_custody._graph_fit_ok`) required the exact pre-D2 key set, so the first served
v3-trainer version (Motor 1.9) would have had every graded retention refused (`graph_build_receipt`). Every value here is
a SYNTHETIC fixture: no model, no training, no grade.
"""

from __future__ import annotations

import json

import pytest

from carbon.development_session import graph_state_contract
from carbon.development_session import physical_graph_trainer_v3 as trainer
from scripts.dev.score_lab import public_unbound_custody as custody

RECIPE = "sha256:" + "1" * 64
HEADER = {"schema": custody.GRAPH_ENSEMBLE_STATE_SCHEMA, "members": 2, "decoder": {}}


def _fit(**extra):
    return {
        "adapter_id": "synthetic-fixture",
        "trainer_sha256": "sha256:" + "2" * 64,
        "members": 2,
        "steps": [3, 3],
        "train_cases": 4,
        "train_loss": 0.5,
        "member_losses": [0.5, 0.25],
        "params_sha256": "sha256:" + "3" * 64,
        "recipe_digest": RECIPE,
        **extra,
    }


def _curve():
    # the trainer's own block from synthetic per-step losses (one diverged step, one member with a polish curve)
    fitted = [
        {"curve": [1.0, 0.5, float("nan"), 0.25], "polish_curve": None},
        {"curve": [2.0, 1.0, 0.5, 0.25], "polish_curve": [0.25, 0.2]},
    ]
    return trainer.curve_block(fitted)


def test_the_constants_are_the_trainer_s():
    assert custody.GRAPH_CURVE_SCHEMA == trainer.CURVE_SCHEMA
    assert custody.GRAPH_CURVE_POINTS == trainer.CURVE_POINTS
    assert custody.GRAPH_CURVE_BYTES_MAX == trainer.CURVE_BYTES_MAX
    # the curve rides only the plain ensemble layout (a trust state's fit is its own head's, H3g R1)
    assert (
        custody.GRAPH_ENSEMBLE_STATE_SCHEMA
        == graph_state_contract.GRAPH_ENSEMBLE_STATE_SCHEMA
    )


def test_a_pre_d2_fit_is_unchanged_and_a_trainer_curve_is_accepted():
    assert custody._graph_fit_ok(_fit(), HEADER, RECIPE)
    assert custody._graph_fit_ok(_fit(curve=_curve()), HEADER, RECIPE)


def test_a_long_real_curve_is_still_within_the_bounds():
    losses = [1.0 / (1 + k) for k in range(5000)]
    block = trainer.curve_block(
        [
            {"curve": losses, "polish_curve": losses[:700]},
            {"curve": losses, "polish_curve": None},
        ]
    )
    assert custody._graph_fit_ok(_fit(curve=block), HEADER, RECIPE)


def _mutated(change):
    curve = _curve()
    change(curve)
    return curve


@pytest.mark.parametrize(
    "curve",
    [
        None,
        [],
        _mutated(lambda c: c.update(schema="carbon.graph-training-curve.v2")),
        _mutated(lambda c: c.update(stride=0)),
        _mutated(lambda c: c.update(stride=True)),
        _mutated(lambda c: c.update(extra=1)),
        _mutated(lambda c: c.pop("polish")),
        _mutated(lambda c: c["members"].pop()),
        _mutated(lambda c: c["polish"].append(None)),
        _mutated(lambda c: c["members"][0].append("0.1")),
        _mutated(lambda c: c["members"][0].append(True)),
        _mutated(lambda c: c["members"][0].append(float("inf"))),
        _mutated(lambda c: c["members"].__setitem__(0, [0.1] * 258)),
        _mutated(lambda c: c["polish"].__setitem__(0, "none")),
    ],
)
def test_a_malformed_curve_refuses(curve):
    assert not custody._graph_fit_ok(_fit(curve=curve), HEADER, RECIPE)


def test_a_curve_over_the_byte_bound_refuses():
    members = 4
    header = {**HEADER, "members": members}
    fit = _fit(steps=[3] * members, member_losses=[0.5] * members, members=members)
    long_value = 1.2345678901234567e-300  # 23 characters: 8 x 257 values exceed 32 KiB
    curve = {
        "schema": custody.GRAPH_CURVE_SCHEMA,
        "stride": 1,
        "members": [[long_value] * 257 for _ in range(members)],
        "polish": [[long_value] * 257 for _ in range(members)],
    }
    assert len(json.dumps(curve, separators=(",", ":"))) > custody.GRAPH_CURVE_BYTES_MAX
    assert not custody._graph_fit_ok({**fit, "curve": curve}, header, RECIPE)
    small = {**curve, "members": [[0.5]] * members, "polish": [None] * members}
    assert custody._graph_fit_ok({**fit, "curve": small}, header, RECIPE)


def test_only_an_ensemble_fit_may_carry_a_curve():
    decoded = {
        "schema": "carbon.development.graph-decoded-state.synthetic",
        "decoder": {},
    }
    fit = _fit()
    del fit["members"], fit["member_losses"]
    fit["steps"] = 3
    assert custody._graph_fit_ok(fit, decoded, RECIPE)
    assert not custody._graph_fit_ok({**fit, "curve": _curve()}, decoded, RECIPE)
