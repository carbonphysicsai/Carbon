"""Menu limit band ``borderline_1u`` (menu_top5_v4; owner G-LEAD-47, 22 Nov 2026; spec
model-eval 23:02:03Z, scope v2 23:02:53Z): menus go TO the limit. Per limit, with U = that output's registered U at the
truth's own value, a true margin m > +U is feasible, -U <= m <= +U is BORDERLINE (allowed in the record, no violation, d
from regret) and m < -U is a CLEAR BREACH (a violation, d = 0); s_ref is the best non-violating design; the model's
predictions are ranked on the limits relaxed outward by U (tier 0 = predicted m >= -U). Every version registered
without it parses and scores bit for bit as before (``none``).

SYNTHETIC fixtures only: the analytic task of test_menu_score (max f = x0 + x1, g = x0^2 + x1^2 <= 0.5, U = 0.01).
"""

import dataclasses
import hashlib
import importlib.util
import math
import pathlib

import pytest

from carbon.scoring import menu_score as ms

_BASE_PATH = pathlib.Path(__file__).with_name("test_menu_score.py")
_spec = importlib.util.spec_from_file_location("_menu_borderline_base", _BASE_PATH)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
U = base.U
K = 3.0  # synthetic k (the version's registered value is the owner's)


def _on_circle(g):
    x = math.sqrt(g / 2)
    return [x, x], base._truth(x, x)


def _document():
    """The base menu plus two rows within U of the limit: 'edge' (m ~ +U/2) and 'past' (m ~ -U/2), the new optimum
    (the best non-violating design). The base's r = 0.72 / 0.75 / 0.80 rows are clear breaches (m < -U) that beat it.
    """
    doc = base._document()
    for pid, g in (("edge", 0.495), ("past", 0.505)):
        design, truth = _on_circle(g)
        doc["pool"].append(
            {"id": pid, "stratum": "band", "design": design, "truth": truth}
        )
    past = next(r for r in doc["pool"] if r["id"] == "past")
    doc["optimum"] = "past"
    doc["s_ref"] = past["truth"]["f"]
    doc["arms"] = {"fit": {r["id"]: base._fit(r["design"]) for r in doc["pool"]}}
    return doc


def _record(doc=None):
    return ms.menu_record(
        doc or _document(), base._problem(), limit_band=ms.LIMIT_BAND_BORDERLINE_1U
    )


def _score(record, preds):
    return ms.score_task(
        base._problem(),
        record,
        preds,
        key=base.KEY,
        epoch="2026-W45",
        ranking=ms.RANKING_ORIGINAL_LIMITS,
        d_form=ms.D_REGRET_U,
        k=K,
    )


# --- today's band is unchanged ---


def test_the_default_band_is_today_s_and_the_sha_does_not_depend_on_the_band():
    doc, problem = base._document(), base._problem()
    today = ms.menu_record(doc, problem)
    assert today == ms.menu_record(doc, problem, ms.LIMIT_BAND_NONE)
    assert today.limit_band == ms.LIMIT_BAND_NONE
    borderline = ms.menu_record(doc, problem, ms.LIMIT_BAND_BORDERLINE_1U)
    assert borderline.sha256 == today.sha256
    assert dataclasses.replace(borderline, limit_band=ms.LIMIT_BAND_NONE) == today


def test_band_none_still_refuses_a_truth_within_u_of_a_limit():
    with pytest.raises(ms.MenuRefused) as caught:
        ms.menu_record(_document(), base._problem())
    assert caught.value.code == "menu_truth_within_u_of_a_limit"


def test_an_unregistered_band_refuses():
    with pytest.raises(ms.MenuRefused) as caught:
        ms.menu_record(base._document(), base._problem(), limit_band="to_limit")
    assert caught.value.code == "menu_limit_band_unregistered"


# --- the borderline record ---


def test_borderline_accepts_rows_within_u_and_a_borderline_optimum():
    doc = _document()
    record = _record(doc)
    assert record.optimum == "past" and record.limit_band == ms.LIMIT_BAND_BORDERLINE_1U
    assert record.sha256 == hashlib.sha256(ms._canonical(doc)).hexdigest()
    m_past = 0.5 - record.pool["past"]["truth"]["g"]
    assert -U <= m_past < 0.0  # the optimum sits past the limit, inside the band


def test_borderline_refuses_an_optimum_at_a_clear_breach():
    doc = _document()
    past = next(r for r in doc["pool"] if r["id"] == "past")
    past["truth"] = {**past["truth"], "g": 0.5 + 2 * U}
    with pytest.raises(ms.MenuRefused) as caught:
        _record(doc)
    assert caught.value.code == "menu_optimum_truth_is_not_s_ref"


def test_borderline_refuses_a_non_violating_design_beating_s_ref_but_not_a_breach():
    doc = _document()
    # a clear breach that beats s_ref is a violation, not a search failure (the base r = 0.72 rows already do)
    s_ref = doc["s_ref"]
    assert any(
        r["truth"]["f"] > s_ref + U and 0.5 - r["truth"]["g"] < -U for r in doc["pool"]
    )
    _record(doc)
    doc["pool"].append(
        {
            "id": "missed",
            "stratum": "spread",
            "design": [0.5, 0.5],
            "truth": {
                "f": s_ref + 2 * U,
                "g": 0.5 + U / 2,
            },  # borderline, beats s_ref by 2 U
        }
    )
    doc["arms"]["fit"]["missed"] = {"f": s_ref + 2 * U, "g": 0.5}
    with pytest.raises(ms.MenuRefused) as caught:
        _record(doc)
    assert caught.value.code == "menu_design_beats_s_ref_search_failure"


# --- the band itself, on exact binary values ---


@pytest.mark.parametrize(
    "u, g, band, violates",
    [
        (0.25, 0.75, ms.LIMIT_BAND_BORDERLINE_1U, False),  # m = -U exactly: borderline
        (
            0.25,
            0.75 + 2**-20,
            ms.LIMIT_BAND_BORDERLINE_1U,
            True,
        ),  # m < -U: clear breach
        (0.25, 0.5, ms.LIMIT_BAND_BORDERLINE_1U, False),  # m = 0
        (0.25, 0.75, ms.LIMIT_BAND_NONE, True),  # today: any true margin < 0
        (0.25, 0.5, ms.LIMIT_BAND_NONE, False),
        (
            {"relative": 0.5},
            1.0,
            ms.LIMIT_BAND_BORDERLINE_1U,
            False,
        ),  # U at the truth's own value: 0.5 x 1.0
        ({"relative": 0.5}, 1.0 + 2**-20, ms.LIMIT_BAND_BORDERLINE_1U, True),
        (0.0, 0.5 + 2**-20, ms.LIMIT_BAND_BORDERLINE_1U, True),  # U 0: no band
    ],
)
def test_the_band_is_exactly_one_u_at_the_truth_s_own_value(u, g, band, violates):
    problem = dataclasses.replace(base._problem(), u={"f": U, "g": u})
    assert ms._violates(problem, {"f": 1.0, "g": g}, band) is violates


# --- the borderline d ---


def test_borderline_picks_score_on_regret_and_only_a_clear_breach_scores_zero():
    record, problem = _record(), base._problem()
    assert ms.pick_d(problem, record, "past", ms.D_REGRET_U, K) == 1.0
    seen = {"borderline_1u": 0, "breach": 0}
    for pid, entry in record.pool.items():
        truth = entry["truth"]
        m = 0.5 - truth["g"]
        d = ms.pick_d(problem, record, pid, ms.D_REGRET_U, K)
        if m < -U:
            seen["breach"] += 1
            assert d == 0.0
            continue
        if -U <= m <= U:
            seen["borderline_1u"] += 1
        regret = record.s_ref - truth["f"]
        assert d == pytest.approx(min(1.0, max(0.0, 1.0 - regret / (K * U))))
    assert seen["borderline_1u"] == 2 and seen["breach"] > 0
    # 'edge' is a borderline pick with a positive regret: under today's band its d would have been its regret's too,
    # but 'past' (true margin < 0) would have scored 0
    assert 0.0 < ms.pick_d(problem, record, "edge", ms.D_REGRET_U, K) < 1.0


def test_an_exact_predictor_reaches_the_oracle_and_the_score_is_menu_top5_v4():
    """model-eval 23:02:03Z (5): with the ranking relaxed by U, a model predicting the borderline optimum exactly ranks
    it in tier 0 and picks it: raw = oracle, D = 1."""
    record = _record()
    truth_model = {pid: dict(e["truth"]) for pid, e in record.pool.items()}
    out = _score(record, truth_model)
    assert out["metric"] == ms.METRIC_BORDERLINE == "menu_top5_v4"
    assert out["state"] == ms.SCORED
    menu = ms.draw_menu(record, base.KEY, epoch="2026-W45")
    assert "past" in menu
    assert out["oracle"] == ms.oracle_score(
        base._problem(), record, menu, ms.D_REGRET_U, K
    )
    assert out["raw"] == out["oracle"] and out["d"] == 1.0


def test_the_borderline_optimum_ranks_in_tier_0_on_the_relaxed_limits():
    problem = base._problem()
    record = _record()
    past = record.pool["past"]["truth"]
    assert -U <= 0.5 - past["g"] < 0.0
    on_relaxed = ms.relaxed(problem)
    assert ms._key(on_relaxed, ms._point(on_relaxed, past))[0] == 0
    assert (
        ms._key(problem, ms._point(problem, past))[0] == 1
    )  # the original limits would bury it (the defect)
    breach = next(
        e["truth"] for e in record.pool.values() if 0.5 - e["truth"]["g"] < -U
    )
    assert ms._key(on_relaxed, ms._point(on_relaxed, breach))[0] == 1


def test_relaxed_is_the_mirror_of_backed_off():
    problem = dataclasses.replace(
        base._problem(),
        limits=(
            ms.Limit("g", "<=", 0.5),
            ms.Limit("f", ">=", 0.25),
        ),
    )
    assert [lim.bound for lim in ms.relaxed(problem).limits] == [0.5 + U, 0.25 - U]
    assert [lim.bound for lim in ms.backed_off(problem).limits] == [0.5 - U, 0.25 + U]


def test_a_borderline_record_ranked_on_another_rule_refuses():
    record = _record()
    menu = ms.draw_menu(record, base.KEY, epoch="2026-W45")
    preds = {pid: dict(e["truth"]) for pid, e in record.pool.items()}
    with pytest.raises(ms.MenuRefused) as caught:
        ms.raw_score(
            base._problem(), record, menu, preds, ms.RANKING_BACKOFF_U, ms.D_REGRET_U, K
        )
    assert caught.value.code == "menu_limit_band_unregistered"


# --- registration ---


@pytest.mark.parametrize(
    "ranking, d_form",
    [
        (ms.RANKING_BACKOFF_U, ms.D_REGRET_U),
        (ms.RANKING_ORIGINAL_LIMITS, ms.D_SHARE),
        (ms.RANKING_BACKOFF_U, ms.D_SHARE),
    ],
)
def test_borderline_is_registered_with_original_limits_and_regret_u_only(
    ranking, d_form
):
    with pytest.raises(ms.MenuRefused) as caught:
        ms.metric_for(ranking, d_form, ms.LIMIT_BAND_BORDERLINE_1U)
    assert caught.value.code == "menu_limit_band_unregistered"
    record = _record()
    with pytest.raises(ms.MenuRefused):
        ms.score_task(
            base._problem(),
            record,
            {pid: None for pid in record.pool},
            key=base.KEY,
            epoch="2026-W45",
            ranking=ranking,
            d_form=d_form,
            k=None if d_form == ms.D_SHARE else K,
        )


def test_metric_for_today_s_combinations_is_unchanged():
    for ranking in ms.RANKINGS:
        assert ms.metric_for(ranking) == ms.metric_for(
            ranking, ms.D_SHARE, ms.LIMIT_BAND_NONE
        )
    assert (
        ms.metric_for(ms.RANKING_ORIGINAL_LIMITS, ms.D_REGRET_U) == ms.METRIC_REGRET_U
    )
    with pytest.raises(ms.MenuRefused):
        ms.metric_for(ms.RANKING_ORIGINAL_LIMITS, ms.D_SHARE, "to_limit")


def _menu_block(**extra):
    return {
        "records_sha256": {"t1": "0" * 64, "t2": "1" * 64, "t3": "2" * 64},
        "epoch": "e1",
        "aggregate": "mean",
        "rotation_days": 1,
        "rowcheck": {"rel_tol": 0.0, "abs_tol": 0.0, "subset": 1},
        **extra,
    }


def test_a_pool_menu_rule_and_a_registration_carry_the_band():
    from carbon.scoring import pool_exam, pool_menu, pool_version

    v3 = pool_version._menu(
        _menu_block(ranking="original_limits", d_form="regret_u", k=K)
    )
    assert v3.limit_band == ms.LIMIT_BAND_NONE
    v4 = pool_version._menu(
        _menu_block(
            ranking="original_limits",
            d_form="regret_u",
            k=K,
            limit_band="borderline_1u",
        )
    )
    assert v4.limit_band == ms.LIMIT_BAND_BORDERLINE_1U
    assert pool_menu.check_rule(v4) is v4
    for bad in (
        dataclasses.replace(v4, d_form=ms.D_SHARE, k=None),
        dataclasses.replace(v4, ranking=ms.RANKING_BACKOFF_U),
        dataclasses.replace(v4, limit_band="to_limit"),
    ):
        with pytest.raises(pool_exam.ExamRefused):
            pool_menu.check_rule(bad)
    for bad_block in (
        _menu_block(limit_band="borderline_1u"),
        _menu_block(
            ranking="original_limits",
            d_form="regret_u",
            k=K,
            limit_band="HUMAN_INPUT",
        ),
        _menu_block(ranking="original_limits", d_form="regret_u", k=K, limit_band=None),
    ):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._menu(bad_block)


def _door_pair(doc):
    """`_document` in design-optimum's own naming (one duty 'd'): the pair `pool_menu.menu_material` takes."""

    def at(truth):
        return {"f@d": truth["f"], "g@d": truth["g"]}

    record = {
        **doc,
        "pool": [{**row, "truth": at(row["truth"])} for row in doc["pool"]],
        "arms": {
            arm: {pid: (None if o is None else at(o)) for pid, o in preds.items()}
            for arm, preds in doc["arms"].items()
        },
    }
    problem = {
        "target_id": "task-1",
        "outputs": ["f@d", "g@d"],
        "objective": "f@d",
        "sense": "max",
        "limits": [["g@d", "<=", 0.5]],
        "u": {"f@d": U, "g@d": U},
        "box": [[0.0, 1.0], [0.0, 1.0]],
        "duties": {"d": {"cond": 1.0}},
    }
    return problem, record


def test_menu_material_and_load_tasks_check_under_the_registered_band():
    from carbon.scoring import pool_exam, pool_menu

    pair = _door_pair(_document())
    names = {"input_names": ("cond", "x", "y"), "design_names": ("x", "y")}
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.menu_material([pair], **names)
    assert caught.value.code == "menu_truth_within_u_of_a_limit"
    material, shas = pool_menu.menu_material(
        [pair], limit_band=ms.LIMIT_BAND_BORDERLINE_1U, **names
    )
    rule = pool_menu.MenuRule(
        records_sha256=tuple(sorted(shas.items())),
        epoch="e1",
        aggregate="mean",
        rotation_days=1,
        rowcheck=(0.0, 0.0, 1),
        min_tasks_exception="synthetic-one-task",
        ranking=ms.RANKING_ORIGINAL_LIMITS,
        d_form=ms.D_REGRET_U,
        k=K,
        limit_band=ms.LIMIT_BAND_BORDERLINE_1U,
    )
    (task,) = pool_menu.load_tasks(material, rule, **names)
    assert task.record.limit_band == ms.LIMIT_BAND_BORDERLINE_1U
    assert task.record.sha256 == shas["task-1"]
    # the same material under a version registered with today's band refuses at load, before any grade
    with pytest.raises(pool_exam.ExamRefused) as caught:
        pool_menu.load_tasks(
            material,
            dataclasses.replace(rule, limit_band=ms.LIMIT_BAND_NONE),
            **names,
        )
    assert caught.value.code == "menu_truth_within_u_of_a_limit"
