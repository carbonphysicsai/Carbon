"""Q4 (Miner X-C, 12 Nov): a menu task with no room above its zero must refuse on EVERY draw, never pass the guard on a
last-bit rounding. Before the fix the oracle was an fsum and a classical arm's raw a running sum, so an arm already at
the truth top five could land an ulp below the oracle, pass ``zero < oracle`` and divide by ~1e-16 (a D that jumps
between 0 and 1 on rounding noise). All fixtures are SYNTHETIC (the analytic task of test_menu_score).
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_menu_score import KEY, _document, _preds, _problem, _truth

from carbon.scoring import menu_score as ms

EPOCHS = [f"fixture-epoch-{i}" for i in range(300)]


def _oracle_arm_record():
    doc = _document()
    doc["arms"]["oracle"] = {row["id"]: _truth(*row["design"]) for row in doc["pool"]}
    return ms.menu_record(doc, _problem())


@pytest.mark.parametrize("epoch", EPOCHS)
def test_an_arm_at_the_truth_top_five_refuses_on_every_draw(epoch):
    record = _oracle_arm_record()
    with pytest.raises(ms.MenuRefused, match="menu_zero_at_oracle_task_has_no_room"):
        ms.score_task(
            _problem(),
            record,
            _preds(record, lambda d: _truth(*d)),
            key=KEY,
            epoch=epoch,
        )


def test_the_draws_exercise_unequal_running_and_exact_sums():
    """The fixture is a real regression: on some of these draws the old fsum oracle differs from the running sum."""
    record = _oracle_arm_record()
    unequal = 0
    for epoch in EPOCHS:
        menu = ms.draw_menu(record, KEY, epoch=epoch)
        ds = sorted((ms.pick_d(_problem(), record, p) for p in menu), reverse=True)
        old_oracle = math.fsum(w * d for w, d in zip(ms.WEIGHTS, ds))
        unequal += old_oracle != ms.raw_score(
            _problem(), record, menu, record.arms["oracle"]
        )
    assert unequal > 0


@pytest.mark.parametrize("epoch", EPOCHS[:50])
def test_a_perfect_model_scores_exactly_one(epoch):
    """One accumulation for raw and oracle: the truth-ordered picks are bit-equal to the oracle."""
    doc = _document()
    record = ms.menu_record(doc, _problem())
    out = ms.score_task(
        _problem(), record, _preds(record, lambda d: _truth(*d)), key=KEY, epoch=epoch
    )
    assert out["raw"] == out["oracle"] and out["d"] == 1.0


def test_a_constant_tied_group_keeps_its_value_exactly():
    for x in (0.1, 1 / 3, 0.7, 0.123456789):
        for k in range(1, 12):
            assert ms._group_d([x] * k) == x
    assert ms._group_d([0.25, 0.75]) == 0.5


def test_the_random_zero_at_the_oracle_refuses():
    """Every menu design with the same d (a synthetic constant d): the random pick is the oracle, so no room."""
    record = _oracle_arm_record()
    original = ms.pick_d
    try:
        ms.pick_d = lambda problem, rec, pid: 0.3
        with pytest.raises(
            ms.MenuRefused, match="menu_zero_at_oracle_task_has_no_room"
        ):
            ms.score_task(
                _problem(),
                record,
                {pid: None for pid in record.pool},
                key=KEY,
                epoch=EPOCHS[0],
            )
    finally:
        ms.pick_d = original
