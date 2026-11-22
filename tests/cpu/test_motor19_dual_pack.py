"""Motor 1.9's row and sealed adapter (`carbon.motor.row19`, `carbon.scoring.motor19_dual_pack`).

1.9 = 1.8's exam with ONE interface change (``magnet_min_b_t`` at column 240 of a 241-wide row) and its own exam
identity, which comes from its overlay entry's dispatch config, so the module lands before the seal. 1.8's module and
producer identity do not move. Every row and number here is a SYNTHETIC fixture: no model, no hidden value.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from carbon.challenge_kit import local_scorer, motor_sealed_pack
from carbon.motor import row18, row19
from carbon.motor.domain import ANGLE_STEPS
from carbon.scoring import motor18_dual_pack as m18
from carbon.scoring import motor19_dual_pack as m19

SCORING = Path(m19.__file__).resolve().parent


def _row(magnet=0.42):
    torque = [5.0 + 0.1 * math.sin(k * 2 * math.pi / ANGLE_STEPS) for k in range(60)]
    phases = [
        [
            0.01 * math.sin(k * 2 * math.pi / ANGLE_STEPS + shift)
            for k in range(ANGLE_STEPS)
        ]
        for shift in (0.0, 2 * math.pi / 3, 4 * math.pi / 3)
    ]
    return [*torque, *phases[0], *phases[1], *phases[2], magnet]


# --- the row ------------------------------------------------------------------------------------------------------------


def test_the_1_9_row_is_the_1_8_row_plus_the_magnet_scalar():
    assert row19.ROW == (*row18.ROW, "magnet_min_b_t")
    assert row19.WIDTH == row18.WIDTH + 1 == 4 * ANGLE_STEPS + 1 == 241
    parts = row19.split(_row(0.37))
    assert parts["magnet_min_b_t"] == 0.37
    assert parts["torque_nm"] == row18.split(_row()[:240])["torque_nm"]
    assert row19.linkages(_row()) == row18.linkages(_row()[:240])


@pytest.mark.parametrize(
    "raw",
    [
        _row()[:240],  # a 1.8 answer is not a 1.9 answer
        [*_row(), 0.0],
        [*_row()[:240], float("nan")],
        [*_row()[:10], float("inf"), *_row()[11:]],
        ["x"] * 241,
        None,
    ],
)
def test_anything_but_a_whole_finite_241_row_is_no_1_9_answer(raw):
    assert row19.split(raw) is None and row19.linkages(raw) is None


def test_the_kit_scorer_and_the_sealed_pack_read_the_1_9_row():
    assert local_scorer.motor_torque(_row()) == row19.split(_row())["torque_nm"]
    assert local_scorer.motor_torque(_row()[:240]) == _row()[:60]  # 1.8 unchanged
    assert "carbon/motor/row19.py" in local_scorer.CODE_MODULES
    assert motor_sealed_pack._model_row_width("1.9") == row19.WIDTH
    assert motor_sealed_pack._model_row_width("1.8") == row18.WIDTH
    assert motor_sealed_pack._model_row_width("1.7") is None


# --- the dispatch config: the exam identity comes from the overlay entry --------------------------------------------


def test_the_config_names_the_pool_versions_and_may_carry_the_subset_registry_block():
    assert m19._pool_versions({"pool_versions": ["motor-pool-sealed-x", "set"]}) == (
        "motor-pool-sealed-x",
        "set",
    )
    assert m19._pool_versions(
        {"pool_versions": ["e", "c"], "subset_repeat": {"producer": "ignored here"}}
    ) == ("e", "c")


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"subset_repeat": {}},
        {"pool_versions": ["only one"]},
        {"pool_versions": ["e", ""]},
        {"pool_versions": ["e", 1]},
        {"pool_versions": "e c"},
        {"pool_versions": ["e", "c"], "region_box": {}},
    ],
)
def test_a_malformed_config_refuses(config):
    with pytest.raises(ValueError):
        m19._pool_versions(config)


def test_nothing_grades_1_9_before_its_entry_is_installed(monkeypatch):
    monkeypatch.setattr(m19, "POOL_VERSIONS", {})
    assert m19.sealed_adapter("1.9") is None
    assert m19.sealed_adapter("1.8") is None
    with pytest.raises(ValueError, match="not installed"):
        m19._writer(None, None)


def test_a_second_dispatch_with_other_pool_versions_refuses(monkeypatch):
    monkeypatch.setattr(m19, "POOL_VERSIONS", {"1.9": ("e", "c")})
    with pytest.raises(ValueError, match="other pool versions"):
        m19.dispatch({"pool_versions": ["e2", "c"]})


# --- the pool derive: 1.8's on the 1.9 row, plus the magnet scalar ----------------------------------------------------


@pytest.fixture
def adapter(monkeypatch):
    from carbon.motor import customer_decision as decision
    from carbon.scoring import pool_adapters

    names = (*decision.DESIGN_VARIABLES, *decision.CONDITION_VARIABLES)
    monkeypatch.setattr(
        pool_adapters, "_roles", lambda kind, version: (None, {}, {}, list(names))
    )
    # the torque gates are 1.8's (tested there); here every synthetic curve passes them
    monkeypatch.setattr(m18, "gates18", lambda curve, inputs: {})
    return m19.pool_adapter("1.9")


def test_the_derive_gives_1_8_s_outputs_and_the_magnet_scalar(adapter):
    assert adapter.outputs == (
        "mean_torque_nm",
        "ripple_pk_pk_nm",
        "back_emf_open_circuit",
        "ke_ll_loaded",
        "magnet_min_b_t",
    )
    derived = adapter.derive({}, _row(0.55))
    torque = _row()[:60]
    assert derived["magnet_min_b_t"] == 0.55
    assert derived["mean_torque_nm"] == pytest.approx(sum(torque) / 60)
    assert derived["ripple_pk_pk_nm"] == pytest.approx(max(torque) - min(torque))
    assert (
        derived["ke_ll_loaded"] == derived["back_emf_open_circuit"] == m19.ke_ll(_row())
    )
    assert adapter.derive({}, _row()[:240]) is None
    with pytest.raises(Exception, match="1.9_only"):
        m19.pool_adapter("1.8")


def test_a_failed_torque_gate_is_no_answer(monkeypatch, adapter):
    from carbon.motor import exam

    monkeypatch.setattr(m18, "gates18", lambda curve, inputs: {"g": exam.FAIL})
    assert m19.pool_adapter("1.9").derive({}, _row()) is None


def test_the_sealed_rows_are_the_torque_slices_and_a_malformed_row_empties_them():
    rows, repeats = m19._sealed_rows([_row(), _row()], [[_row(), _row()]])
    assert rows == [_row()[:60]] * 2 and repeats == [[_row()[:60]] * 2]
    rows, repeats = m19._sealed_rows([_row(), _row()[:240]], [[_row(), _row()]])
    assert rows == [[], []] and repeats == [[[], []]]


# --- identity: 1.9's own producer files; 1.8's unchanged ---------------------------------------------------------------


def test_1_9_s_producer_files_exist_and_1_8_s_do_not_name_1_9():
    files = m19.FILES
    assert {
        "motor18_dual_pack.py",
        "motor19_dual_pack.py",
        "pair_read_bound.py",
        "subset_repeat_registry.py",
        "producer_successor_v2.py",
    } <= set(files)
    assert all((SCORING / name).is_file() for name in files)
    assert "motor19_dual_pack.py" not in m18.FILES
    assert m19.producer_digest() != m18.producer_digest()
