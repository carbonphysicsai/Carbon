"""Menu D form ``regret_u`` (menu_top5_v3; owner MOTOR19-D-SAT-PICK (B), 22 Nov 2026; form: exam-motor 03:09:23Z).

Per slot d = 0 for a truly infeasible pick, else clip(1 - regret / (k x U_obj), 0, 1), regret = s_ref - s_pick in the
objective's units, U_obj = the task's U of the objective at the pick's true value, k = the version's registered value.
The zero, the oracle and the no-room check use the same d. Every version registered without it scores bit for bit as
before. SYNTHETIC fixtures only (the analytic task of test_menu_score / test_menu_score_ranking).
"""

import dataclasses
import importlib.util
import pathlib

import pytest

from carbon.scoring import menu_score as ms

_RANKING_PATH = pathlib.Path(__file__).with_name("test_menu_score_ranking.py")
_spec = importlib.util.spec_from_file_location("_menu_ranking_base", _RANKING_PATH)
ranking = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ranking)
base = ranking.base
U = base.U


def _score(record, preds, **kwargs):
    return ms.score_task(
        base._problem(),
        record,
        preds,
        key=base.KEY,
        epoch="2026-W45",
        ranking=ms.RANKING_ORIGINAL_LIMITS,
        **kwargs,
    )


def test_the_default_d_form_is_today_s_bit_identical():
    record = ranking._record()
    preds = ranking._model(0.0003)(record)
    old = _score(record, preds)
    assert old == _score(record, preds, d_form=ms.D_SHARE, k=None)
    assert old["metric"] == "menu_top5_v2"
    assert ms.metric_for(ms.RANKING_ORIGINAL_LIMITS) == "menu_top5_v2"


def test_pick_d_in_regret_units():
    record = ranking._record()
    problem = base._problem()
    k = 3.0
    assert ms.pick_d(problem, record, record.optimum, ms.D_REGRET_U, k) == 1.0
    for pid, entry in record.pool.items():
        truth = entry["truth"]
        if any(m < 0.0 for m in ms._margins(problem, truth).values()):
            assert ms.pick_d(problem, record, pid, ms.D_REGRET_U, k) == 0.0
            continue
        regret = record.s_ref - truth["f"]
        want = min(1.0, max(0.0, 1.0 - regret / (k * U)))
        assert ms.pick_d(problem, record, pid, ms.D_REGRET_U, k) == pytest.approx(want)


def test_a_wrong_pick_costs_more_in_regret_units_than_as_a_share():
    """The point of (B): today's share divides a regret by (s_ref - s_zero), many U on a real menu, so a few-U miss
    costs ~nothing; in U it costs regret / (k U)."""
    record = ranking._record()
    problem = base._problem()
    feasible = [
        pid
        for pid, e in record.pool.items()
        if pid != record.optimum
        and all(m >= 0.0 for m in ms._margins(problem, e["truth"]).values())
    ]
    pid = max(feasible, key=lambda p: record.pool[p]["truth"]["f"])
    regret_u = ms.pick_d(problem, record, pid, ms.D_REGRET_U, 1.0)
    share = ms.pick_d(problem, record, pid)
    assert regret_u <= share


def test_the_score_uses_the_same_d_for_raw_zero_oracle_and_labels_v3():
    record = ranking._record()
    preds = ranking._model(0.0)(record)
    out = _score(record, preds, d_form=ms.D_REGRET_U, k=1000.0)
    assert out["metric"] == ms.METRIC_REGRET_U == "menu_top5_v3"
    assert out["state"] == ms.SCORED and 0.0 <= out["d"] <= 1.0
    menu = ms.draw_menu(record, base.KEY, epoch="2026-W45")
    assert out["oracle"] == ms.oracle_score(
        base._problem(), record, menu, ms.D_REGRET_U, 1000.0
    )


@pytest.mark.parametrize(
    "d_form, k, ranking_rule",
    [
        (ms.D_REGRET_U, None, ms.RANKING_ORIGINAL_LIMITS),
        (ms.D_REGRET_U, 0.0, ms.RANKING_ORIGINAL_LIMITS),
        (ms.D_REGRET_U, -1.0, ms.RANKING_ORIGINAL_LIMITS),
        (ms.D_REGRET_U, True, ms.RANKING_ORIGINAL_LIMITS),
        (ms.D_REGRET_U, float("nan"), ms.RANKING_ORIGINAL_LIMITS),
        (ms.D_REGRET_U, 3.0, ms.RANKING_BACKOFF_U),
        (ms.D_SHARE, 3.0, ms.RANKING_ORIGINAL_LIMITS),
        ("regret", 3.0, ms.RANKING_ORIGINAL_LIMITS),
    ],
)
def test_an_unregistered_d_form_or_k_refuses(d_form, k, ranking_rule):
    record = ranking._record()
    preds = ranking._model(0.0)(record)
    with pytest.raises(ms.MenuRefused):
        ms.score_task(
            base._problem(),
            record,
            preds,
            key=base.KEY,
            epoch="2026-W45",
            ranking=ranking_rule,
            d_form=d_form,
            k=k,
        )


def test_a_pool_menu_rule_and_a_registration_carry_the_d_form():
    from carbon.scoring import pool_exam, pool_menu, pool_version

    rule = pool_menu.MenuRule(
        records_sha256=(("t1", "0" * 64), ("t2", "1" * 64), ("t3", "2" * 64)),
        epoch="e1",
        aggregate="mean",
        rotation_days=1,
        rowcheck=(0.0, 0.0, 1),
        ranking=ms.RANKING_ORIGINAL_LIMITS,
    )
    assert (rule.d_form, rule.k) == (ms.D_SHARE, None)
    v3 = dataclasses.replace(rule, d_form=ms.D_REGRET_U, k=3.0)
    assert pool_menu.check_rule(v3) is v3
    for bad in (
        dataclasses.replace(rule, d_form=ms.D_REGRET_U),
        dataclasses.replace(rule, k=3.0),
        dataclasses.replace(v3, ranking=ms.RANKING_BACKOFF_U),
    ):
        with pytest.raises(pool_exam.ExamRefused):
            pool_menu.check_rule(bad)
    block = ranking._menu_block(
        ranking=ms.RANKING_ORIGINAL_LIMITS, d_form="regret_u", k=3.0
    )
    parsed = pool_version._menu(block)
    assert (parsed.d_form, parsed.k) == (ms.D_REGRET_U, 3.0)
    assert pool_version._menu(ranking._menu_block()).d_form == ms.D_SHARE
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._menu({**block, "k": "HUMAN_INPUT"})
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._menu({k: v for k, v in block.items() if k != "k"})
