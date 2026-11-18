"""Menu ranking rules (owner 18 Nov: rank on the original limits, prospectively). SYNTHETIC fixtures only: the
analytic task of test_menu_score (max f = x0 + x1, g = x0^2 + x1^2 <= 0.5) with the optimum at a true margin of
about U, as in a real pool (pool_solver_reference: the optimum sits at true margin ~U).
"""

import importlib.util
import math
import pathlib

import pytest

from carbon.scoring import menu_score as ms

_BASE_PATH = pathlib.Path(__file__).with_name("test_menu_score.py")
_spec = importlib.util.spec_from_file_location("_menu_score_base", _BASE_PATH)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

U = base.U
G_OPT = 0.5 - 1.01 * U  # true margin 1.01 U: the sealed optimum clears the limit by U
OPT = math.sqrt(G_OPT / 2)


def _document():
    doc = base._document()
    for row in doc["pool"]:
        if row["id"] == "opt":
            row["design"] = [OPT, OPT]
            row["truth"] = base._truth(OPT, OPT)
    doc["s_ref"] = 2 * OPT
    doc["arms"] = {"fit": {row["id"]: base._fit(row["design"]) for row in doc["pool"]}}
    return doc


def _record():
    return ms.menu_record(_document(), base._problem())


def _score(record, preds, ranking=None):
    kwargs = {} if ranking is None else {"ranking": ranking}
    return ms.score_task(
        base._problem(), record, preds, key=base.KEY, epoch="2026-W45", **kwargs
    )


def _model(error):
    """A model whose g is the truth plus `error` (f exact)."""

    def predict(record):
        return {
            pid: {
                "f": base._truth(*e["design"])["f"],
                "g": base._truth(*e["design"])["g"] + error,
            }
            for pid, e in record.pool.items()
        }

    return predict


def _first_pick(record, preds, ranking):
    menu = ms.draw_menu(record, base.KEY, epoch="2026-W45")
    return ms._slots(base._problem(), record, menu, preds, ranking)[0]


def test_the_default_ranking_is_the_old_rule_bit_identical():
    record = _record()
    preds = _model(0.0003)(record)
    old = _score(record, preds)
    assert old == _score(record, preds, ms.RANKING_BACKOFF_U)
    assert old["metric"] == "menu_top5_v1" == ms.METRIC
    assert ms.metric_for(ms.RANKING_BACKOFF_U) == "menu_top5_v1"


def test_the_new_rule_has_its_own_metric_label():
    record = _record()
    out = _score(record, _model(0.0)(record), ms.RANKING_ORIGINAL_LIMITS)
    assert out["metric"] == "menu_top5_v2" and out["state"] == ms.SCORED


def test_an_unregistered_ranking_is_refused():
    record = _record()
    with pytest.raises(ms.MenuRefused) as err:
        _score(record, _model(0.0)(record), "nope")
    assert err.value.code == "menu_ranking_unregistered"


def test_the_optimum_is_picked_for_a_small_error_of_either_sign_under_the_new_rule():
    record = _record()
    for error in (-0.4 * U, -0.1 * U, 0.0, 0.1 * U, 0.4 * U):
        out = _score(record, _model(error)(record), ms.RANKING_ORIGINAL_LIMITS)
        assert out["d"] == pytest.approx(1.0), error
        assert (
            _first_pick(record, _model(error)(record), ms.RANKING_ORIGINAL_LIMITS)
            == 1.0
        )


def test_the_old_rule_depends_on_the_sign_of_the_error():
    # a small UPWARD error in g (|e| < U) puts the optimum beyond the backed-off limit: the old rule drops it
    record = _record()
    up = _score(record, _model(0.4 * U)(record), ms.RANKING_BACKOFF_U)
    zero = _score(record, _model(0.0)(record), ms.RANKING_BACKOFF_U)
    assert zero["d"] == pytest.approx(1.0)
    assert up["d"] < 1.0


def test_an_optimistic_bias_beyond_u_is_penalised_under_the_new_rule():
    record = _record()
    biased = _score(record, _model(-20 * U)(record), ms.RANKING_ORIGINAL_LIMITS)
    exact = _score(record, _model(0.0)(record), ms.RANKING_ORIGINAL_LIMITS)
    assert biased["d"] < exact["d"]
    assert (
        _first_pick(record, _model(-20 * U)(record), ms.RANKING_ORIGINAL_LIMITS) < 1.0
    )


def test_the_arms_are_ranked_by_the_same_rule_as_the_model():
    record = _record()
    preds = _model(0.0)(record)
    v1 = _score(record, preds, ms.RANKING_BACKOFF_U)
    v2 = _score(record, preds, ms.RANKING_ORIGINAL_LIMITS)
    menu = ms.draw_menu(record, base.KEY, epoch="2026-W45")
    arm = record.arms["fit"]
    p = base._problem()
    assert ms._weighted(ms._slots(p, record, menu, arm, ms.RANKING_BACKOFF_U)) == (
        ms._weighted(ms._slots(p, record, menu, arm))
    )
    assert v1["zero"] != v2["zero"] or v1["zero_source"] == v2["zero_source"]


def test_a_pool_menu_rule_registers_the_ranking():
    from carbon.scoring import pool_exam, pool_menu

    rule = pool_menu.MenuRule(
        records_sha256=(("t1", "0" * 64), ("t2", "1" * 64), ("t3", "2" * 64)),
        epoch="e1",
        aggregate="mean",
        rotation_days=1,
        rowcheck=(0.0, 0.0, 1),
    )
    assert rule.ranking == ms.RANKING_BACKOFF_U
    assert pool_menu.check_rule(rule) is rule
    import dataclasses

    v2 = dataclasses.replace(rule, ranking=ms.RANKING_ORIGINAL_LIMITS)
    assert pool_menu.check_rule(v2) is v2
    with pytest.raises(pool_exam.ExamRefused):
        pool_menu.check_rule(dataclasses.replace(rule, ranking="nope"))


def _menu_block(**extra):
    return {
        "records_sha256": {"t1": "0" * 64, "t2": "1" * 64, "t3": "2" * 64},
        "epoch": "e1",
        "aggregate": "mean",
        "rotation_days": 1,
        "rowcheck": {"rel_tol": 0.0, "abs_tol": 0.0, "subset": 1},
        **extra,
    }


def test_a_version_registers_the_ranking_or_defaults_to_the_old_rule():
    from carbon.scoring import pool_version

    assert pool_version._menu(_menu_block()).ranking == ms.RANKING_BACKOFF_U
    new = pool_version._menu(_menu_block(ranking=ms.RANKING_ORIGINAL_LIMITS))
    assert new.ranking == ms.RANKING_ORIGINAL_LIMITS
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._menu(_menu_block(ranking="nope"))
