"""D menu v1 scorer (spec D_MENU_SPEC_V1_20261107 §2-3). All fixtures are SYNTHETIC: an analytic task
(max f = x0 + x1, g = x0^2 + x1^2 <= 0.5), made-up strata, quotas and arms."""

import copy
import math

import pytest

from carbon.scoring import menu_score as ms
from carbon.scoring import pool_solver_reference as psr
from carbon.scoring.pool_grader import Limit

KEY = b"m" * 32  # synthetic custody key
U = 0.01


def _problem():
    return psr.Problem(
        target_id="task-1",
        fixed={},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.5),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        start=(0.5, 0.5),
        seed=0,
    )


def _truth(x0, x1):
    return {"f": x0 + x1, "g": x0 * x0 + x1 * x1}


OPT = math.sqrt(
    0.48 / 2
)  # g = 0.48: clears the backed-off limit (0.49) and the true limit by > U


def _document():
    pool = [
        {
            "id": "opt",
            "stratum": "band",
            "design": [OPT, OPT],
            "truth": _truth(OPT, OPT),
        }
    ]
    k = 0
    for r in (
        0.62,
        0.66,
        0.69,
        0.72,
        0.75,
        0.80,
    ):  # both sides of r = 0.707 (traps beyond it)
        for t in (0.2, 0.5, 0.8, 1.1, 1.3):
            x0, x1 = r * math.cos(t), r * math.sin(t)
            if 0 <= x0 <= 1 and 0 <= x1 <= 1:
                pool.append(
                    {
                        "id": f"b{k}",
                        "stratum": "band",
                        "design": [x0, x1],
                        "truth": _truth(x0, x1),
                    }
                )
                k += 1
    for i in range(12):
        x0, x1 = (i % 4) / 4 * 0.6, (i // 4) / 3 * 0.6
        pool.append(
            {
                "id": f"s{i}",
                "stratum": "spread",
                "design": [x0, x1],
                "truth": _truth(x0, x1),
            }
        )
    s_ref = 2 * OPT
    return {
        "schema": ms.MENU_SCHEMA,
        "task_id": "task-1",
        "s_ref": s_ref,
        "s_zero": 0.6,
        "optimum": "opt",
        "quotas": {"band": 14, "spread": 8},
        "pool": pool,
        "arms": {"fit": {row["id"]: _fit(row["design"]) for row in pool}},
    }


def _fit(design):
    # a TRAIN-only fit: under-predicts g by 0.08 (optimistic about the limit), so it picks traps
    t = _truth(*design)
    return {"f": t["f"], "g": t["g"] - 0.08}


def _record(doc=None):
    return ms.menu_record(doc or _document(), _problem())


def _preds(record, fn):
    return {pid: fn(entry["design"]) for pid, entry in record.pool.items()}


# --- the record ---


def test_the_record_parses_and_hashes():
    record = _record()
    assert record.optimum == "opt" and record.size == 23 and len(record.sha256) == 64


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda d: d.update(schema="x"), "menu_schema_unknown"),
        (lambda d: d.update(task_id="t9"), "menu_task_id_mismatch"),
        (lambda d: d.update(s_zero=5.0), "menu_s_ref_not_above_s_zero"),
        (lambda d: d.update(s_ref=d["s_ref"] - 0.1), "menu_optimum_truth_is_not_s_ref"),
        (
            lambda d: d["pool"].append(
                {
                    "id": "better",
                    "stratum": "band",
                    "design": [0.5, 0.48],
                    "truth": {"f": 1.2, "g": 0.4},
                }
            ),
            "menu_design_beats_s_ref_search_failure",
        ),
        (lambda d: d["quotas"].update(spread=13), "menu_quota_above_stratum_supply"),
        (
            lambda d: d.update(quotas={"band": 2, "spread": 1}),
            "menu_smaller_than_top_five",
        ),
        (
            lambda d: d["arms"]["fit"].pop("s0"),
            "menu_arm_must_predict_every_pool_design",
        ),
        (
            lambda d: d.update(arms={}),
            "menu_arms_empty",
        ),  # CV-B 10 Nov (a): a fit in the zero
        (lambda d: d.update(arms=[]), "menu_arms_malformed"),
        (lambda d: d["pool"][1]["design"].__setitem__(0, 1.5), "menu_design_invalid"),
        (
            lambda d: d["pool"][1]["truth"].__setitem__("g", math.nan),
            "menu_truth_invalid",
        ),
        (lambda d: d["pool"].append(dict(d["pool"][1])), "menu_pool_id_invalid"),
    ],
)
def test_record_refusals(mutate, code):
    doc = copy.deepcopy(_document())
    mutate(doc)
    with pytest.raises(ms.MenuRefused) as err:
        ms.menu_record(doc, _problem())
    assert err.value.code == code


# --- the epoch's draw ---


def test_the_draw_keeps_the_optimum_and_the_quotas():
    record = _record()
    menu = ms.draw_menu(record, KEY, epoch="2026-W45")
    assert "opt" in menu and len(menu) == record.size
    assert sum(1 for pid in menu if record.pool[pid]["stratum"] == "spread") == 8
    assert ms.draw_menu(record, KEY, epoch="2026-W45") == menu
    assert (
        len({ms.draw_menu(record, KEY, epoch=f"2026-W{w}") for w in range(40, 50)}) > 1
    )
    with pytest.raises(ms.MenuRefused, match="menu_draw_key_invalid"):
        ms.draw_menu(record, b"short", epoch="2026-W45")


# --- scoring ---


def _score(record, preds, epoch="2026-W45"):
    return ms.score_task(_problem(), record, preds, key=KEY, epoch=epoch)


def test_a_perfect_model_beats_the_zero_and_its_first_pick_is_the_optimum():
    record = _record()
    out = _score(record, _preds(record, lambda d: _truth(*d)))
    assert out["d"] == pytest.approx(1.0) and out["raw"] == pytest.approx(out["oracle"])
    assert out["oracle"] > out["zero"]  # the sample's oracle is the 1
    assert out["state"] == ms.SCORED
    menu = ms.draw_menu(record, KEY, epoch="2026-W45")
    assert (
        ms.raw_score(_problem(), record, menu, _preds(record, lambda d: _truth(*d)))
        >= ms.WEIGHTS[0]
    )
    assert set(out) == {
        "metric",
        "state",
        "d",
        "raw",
        "oracle",
        "zero",
        "zero_source",
        "menu_size",
    }  # numbers only


def test_a_constant_predictor_scores_exactly_zero():
    record = _record()
    for constant in ({"f": 1.0, "g": 0.1}, {"f": 1.0, "g": 9.0}):
        out = _score(record, _preds(record, lambda d, c=constant: dict(c)))
        menu = ms.draw_menu(record, KEY, epoch="2026-W45")
        mean = math.fsum(ms.pick_d(_problem(), record, p) for p in menu) / len(menu)
        assert out["raw"] == pytest.approx(mean, abs=1e-12) and out["d"] == 0.0


def test_invalid_predictions_rank_last_and_score_nothing():
    record = _record()
    out = _score(record, _preds(record, lambda d: None))
    assert out["d"] == 0.0


def test_a_truly_infeasible_pick_scores_zero():
    record = _record()
    trap = next(pid for pid, e in record.pool.items() if e["truth"]["g"] > 0.5)
    assert ms.pick_d(_problem(), record, trap) == 0.0
    assert ms.pick_d(_problem(), record, "opt") == 1.0


def test_a_classical_arm_at_the_oracle_leaves_no_room_and_refuses():
    doc = _document()
    doc["arms"]["oracle"] = {row["id"]: _truth(*row["design"]) for row in doc["pool"]}
    record = ms.menu_record(doc, _problem())
    with pytest.raises(ms.MenuRefused, match="menu_zero_at_oracle_task_has_no_room"):
        _score(record, _preds(record, lambda d: _truth(*d)))


def test_a_classical_arm_above_random_sets_the_zero():
    doc = _document()
    # an arm that ranks by the truth but sees only the spread stratum as feasible: better than random, below oracle
    doc["arms"]["spread_only"] = {
        row["id"]: (
            _truth(*row["design"])
            if row["stratum"] == "spread"
            else {"f": 0.0, "g": 9.0}
        )
        for row in doc["pool"]
    }
    record = ms.menu_record(doc, _problem())
    menu = ms.draw_menu(record, KEY, epoch="2026-W45")
    arm = ms.raw_score(_problem(), record, menu, record.arms["spread_only"])
    out = _score(record, _preds(record, lambda d: _truth(*d)))
    assert out["zero"] == max(arm, out["zero"]) and out["d"] == pytest.approx(1.0)


def test_pool_designs_within_u_of_a_limit_refuse():
    doc = _document()
    x = math.sqrt(0.497 / 2)  # g = 0.497: inside U = 0.01 of the limit 0.5
    doc["pool"].append(
        {"id": "edge", "stratum": "band", "design": [x, x], "truth": _truth(x, x)}
    )
    doc["arms"]["fit"]["edge"] = _fit([x, x])
    with pytest.raises(ms.MenuRefused, match="menu_truth_within_u_of_a_limit"):
        ms.menu_record(doc, _problem())


def test_the_optimum_must_clear_every_limit_by_u():
    doc = _document()
    x = math.sqrt(
        0.485 / 2
    )  # g = 0.485: feasible but only 0.015 > U clear; then 0.495 is within U
    y = math.sqrt(0.488 / 2)
    for row in doc["pool"]:
        if row["id"] == "opt":
            row["design"], row["truth"] = [y, y], _truth(y, y)
    doc["s_ref"] = 2 * y
    doc["arms"]["fit"]["opt"] = _fit([y, y])
    assert ms.menu_record(doc, _problem()).s_ref == 2 * y  # 0.012 clear: allowed
    problem = _problem()
    tight = psr.Problem(**{**problem.__dict__, "u": {"f": U, "g": 0.02}})
    with pytest.raises(ms.MenuRefused):
        ms.menu_record(doc, tight)  # with U = 0.02 the optimum is not +U clear
    assert x < y


def test_a_row_dependent_model_scores_zero_typed():
    record = _record()

    def predict_menu(menu):
        raise ms.ModelRowDependent()

    out = ms.score_task_live(
        _problem(), record, predict_menu, key=KEY, epoch="2026-W45"
    )
    assert out["state"] == ms.MODEL_ROW_DEPENDENT and out["d"] == 0.0
    ok = ms.score_task_live(
        _problem(),
        record,
        lambda menu: {pid: _truth(*record.pool[pid]["design"]) for pid in menu},
        key=KEY,
        epoch="2026-W45",
    )
    assert ok["state"] == ms.SCORED and ok["d"] == pytest.approx(1.0)


def test_the_optimistic_fit_arm_falls_for_the_traps():
    record = _record()
    menu = ms.draw_menu(record, KEY, epoch="2026-W45")
    fit = ms.raw_score(_problem(), record, menu, record.arms["fit"])
    perfect = ms.raw_score(
        _problem(), record, menu, _preds(record, lambda d: _truth(*d))
    )
    assert fit < perfect


def test_predictions_must_cover_the_menu():
    record = _record()
    with pytest.raises(ms.MenuRefused, match="menu_predictions_missing_a_design"):
        _score(record, {"opt": _truth(OPT, OPT)})


def test_backed_off_moves_each_limit_inward_by_u():
    assert ms.backed_off(_problem()).limits == (Limit("g", "<=", 0.49),)


# --- row independence ---


def _row_model(rows):
    return [{"f": r[0] + r[1], "g": r[0] ** 2 + r[1] ** 2} for r in rows]


def _density_gamer(rows):
    # no physics: 'best' where the batch it is shown is densest (it sees the whole batch)
    cx = sum(r[0] for r in rows) / len(rows)
    return [{"f": -abs(r[0] - cx), "g": 0.0} for r in rows]


ROWS = [[i / 10, (9 - i) / 10] for i in range(10)]


def test_a_row_model_passes_in_any_batching_and_keeps_the_callers_order():
    for batch in (1, 3, 10):
        wrapped = ms.RowIndependentPredict(
            _row_model, batch_size=batch, recheck=4, seed=7, rel_tol=0.0, abs_tol=0.0
        )
        assert wrapped(ROWS) == _row_model(ROWS)
    one = ms.RowIndependentPredict(
        _row_model, batch_size=1, recheck=0, seed=7, rel_tol=0.0, abs_tol=0.0
    )
    one(ROWS)
    assert one.calls == len(ROWS)  # one row per call, nothing re-checked


def test_a_batch_dependent_model_is_caught():
    wrapped = ms.RowIndependentPredict(
        _density_gamer, batch_size=5, recheck=3, seed=7, rel_tol=1e-9, abs_tol=1e-12
    )
    with pytest.raises(ms.ModelRowDependent):
        wrapped(ROWS)
    # one row per call: the gamer sees only itself, so it cannot use the menu's density
    single = ms.RowIndependentPredict(
        _density_gamer, batch_size=1, recheck=0, seed=7, rel_tol=0.0, abs_tol=0.0
    )
    assert all(p["f"] == 0.0 for p in single(ROWS))


def test_batching_without_a_recheck_refuses():
    with pytest.raises(ms.MenuRefused, match="menu_batched_without_recheck"):
        ms.RowIndependentPredict(
            _row_model, batch_size=4, recheck=0, seed=1, rel_tol=0.0, abs_tol=0.0
        )


# --- two duties (Motor) ---


def test_two_duties_merge_into_prefixed_outputs():
    record = _record()
    menu = ("opt", "s0")
    duties = (("overload", {"load": 2.0}), ("rated", {"load": 1.0}))
    rows, index = ms.menu_rows(record, menu, duties, ("load", "x0", "x1"), ("x0", "x1"))
    assert len(rows) == 4 and index[0] == ("opt", "overload") and rows[0][0] == 2.0
    preds = [{"f": r[0] * (r[1] + r[2])} for r in rows]
    preds[3] = None  # s0 at the rated duty: invalid
    merged = ms.merge_duties(index, preds, duties)
    assert merged["opt"] == {"overload/f": 2.0 * 2 * OPT, "rated/f": 2 * OPT}
    assert merged["s0"] is None
