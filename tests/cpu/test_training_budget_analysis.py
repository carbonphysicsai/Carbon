"""TRAINING-BUDGET-01 slice 5 (first part): R5-R8 bound to their frozen text."""

from __future__ import annotations

import pytest

from carbon.training_budget import analysis as an


def record(
    phase, wall, *, run_id="x", note="", concurrency=1, group=None, state="COMPLETED"
):
    return {
        "phase": phase,
        "run_id": run_id,
        "state": state,
        "run": {"note": note, "concurrency": concurrency, "group": group},
        "time": {"wall_s": wall},
    }


def held_out(measured, predicted=100.0):
    rows = [record("C", m, run_id=f"c{i}") for i, m in enumerate(measured)]
    return rows, (lambda r, f: predicted)


def test_r5_adopts_a_formula_within_25_percent_for_95_percent():
    rows, predict = held_out([100.0] * 19 + [126.0])  # 19 of 20 within 25%
    result = an.r5(rows, predict, ["F3_seconds"])
    assert result["formulas"]["F3_seconds"]["share_within_25_percent"] == 0.95
    assert result["adopted"] == "F3_seconds"
    assert result["outcome"] == "COMPUTE_COST_LIMIT"


def test_r5_fails_below_95_percent():
    rows, predict = held_out([100.0] * 18 + [130.0, 130.0])
    assert an.r5(rows, predict, ["F3_seconds"])["outcome"] == "PER_SETTING_CAPS"


def test_r5_fails_on_one_rebuild_over_one_and_a_half_times():
    rows, predict = held_out([100.0] * 39 + [151.0])
    result = an.r5(rows, predict, ["F4_seconds"])
    assert result["formulas"]["F4_seconds"]["worst_ratio"] == pytest.approx(1.51)
    assert result["adopted"] is None


def test_r5_uses_the_simpler_formula_when_both_pass():
    rows, predict = held_out([100.0] * 20)
    assert an.r5(rows, predict, ["F3_seconds", "F4_seconds"])["adopted"] == "F3_seconds"


def test_r5_reads_only_completed_phase_c_and_f_rebuilds():
    rows = [record("A", 999.0), record("C", 100.0, state="FAILED_INFRA")]
    with pytest.raises(an.AnalysisRefused) as refused:
        an.r5(rows, lambda r, f: 100.0, ["F3_seconds"])
    assert refused.value.code == "analysis_r5_needs_phase_c_and_f"


def test_r6_names_settings_slower_than_one_and_a_half_times():
    rows = [
        record("F", 160.0, note="microbatches"),
        record("F", 140.0, note="width"),
    ]
    result = an.r6(rows, lambda r, f: 100.0, "F4_seconds")
    assert result["settings_needing_a_factor"] == {"microbatches": 1.6}


def test_r7_is_three_times_the_costliest_prediction():
    assert an.r7(120.0)["time_limit_s"] == 360.0
    with pytest.raises(an.AnalysisRefused):
        an.r7(0)


def test_r8_reports_rebuilds_per_gpu_hour_alone_and_shared():
    rows = [record("E", 300.0), record("E", 300.0)]
    rows += [record("E", w, group="shared:2", concurrency=2) for w in (400.0, 450.0)]
    rows += [record("E", 600.0, group="shared:4", concurrency=4) for _ in range(4)]
    result = an.r8(rows, time_target_seconds=300)
    rates = result["rebuilds_per_gpu_hour"]
    assert rates == {"alone": 12.0, "shared_2": 16.0, "shared_4": 24.0}
    # "At 5 minutes, one GPU carries at least 288 worst-case rebuilds a day."
    assert result["worst_case_rebuilds_per_gpu_day"] == 288


def test_r8_refuses_an_incomplete_shared_group():
    rows = [record("E", 300.0), record("E", 400.0, group="shared:4", concurrency=4)]
    with pytest.raises(an.AnalysisRefused) as refused:
        an.r8(rows, 300)
    assert refused.value.code == "analysis_r8_group_incomplete"


# -- Fits ------------------------------------------------------------------------


def costed(phase, wall, cost, *, family="mlp", run_id="r"):
    row = record(phase, wall, run_id=run_id)
    row["calculated_cost"] = {"F4_flops": cost}
    row["family"] = family
    return row


def test_fit_is_ols_per_family_on_phases_a_and_b_only():
    rows = [costed("A", 10 + 2 * c, c, run_id=f"a{c}") for c in (1, 2, 3)]
    rows += [costed("B", 5 + 1 * c, c, family="knn", run_id=f"k{c}") for c in (1, 3)]
    rows += [costed("C", 999.0, 1, run_id="held-out")]
    result = an.fit(rows, "F4_flops", lambda r: r["family"])
    mlp = result["families"]["mlp"]
    assert mlp["setup_s"] == pytest.approx(10) and mlp["per_unit_s"] == pytest.approx(2)
    assert mlp["points"] == 3 and mlp["residual_sd"] == pytest.approx(0)
    assert mlp["share_outside_1_5"] == 0
    assert result["families"]["knn"]["per_unit_s"] == pytest.approx(1)
    predict = an.predictor({"F4_flops": result}, lambda r: r["family"])
    assert predict(costed("C", 0, 5), "F4_flops") == pytest.approx(20)


# -- Plateaus --------------------------------------------------------------------


def test_plateau_is_where_every_further_doubling_gains_under_half_the_margin():
    # Higher is better, margin 0.1: gains per doubling 0.2, 0.1, 0.04, 0.01.
    points = [(1, 0.5), (2, 0.7), (4, 0.8), (8, 0.84), (16, 0.85)]
    assert an.plateau(points, 0.1, True) == 4
    assert an.plateau(points, 0.5, True) == 1


def test_a_curve_still_improving_at_its_top_has_no_plateau():
    assert an.plateau([(1, 0.5), (2, 0.6), (4, 0.7)], 0.1, True) is None


def test_lower_is_better_and_uneven_budget_steps():
    # Error falls 0.4 over a 4x step: 0.2 per doubling, more than half of 0.1.
    assert an.plateau([(1, 1.0), (4, 0.6), (8, 0.58)], 0.1, False) == 4


def sweep(recipe, setting, scores, base=1.0):
    rows = []
    for i, values in enumerate(scores):
        for seed, s in enumerate(values):
            row = record("B", 1.0, run_id=f"{recipe}{setting}{i}{seed}", note=setting)
            row["run"]["recipe"] = recipe
            row["calculated_cost"] = {"F4_flops": base * 2**i}
            row["score"] = {"exam_score": s}
            rows.append(row)
    return rows


def exam(r):
    return r["score"]["exam_score"]


def test_r2_takes_the_largest_curve_plateau_and_reports_curves_without_one():
    rows = sweep("a", "steps", [[0.5, 0.5], [0.8, 0.8], [0.81, 0.81]])
    rows += sweep("a", "width", [[0.5], [0.7], [0.9], [0.91]])
    rows += sweep("b", "steps", [[0.3], [0.5], [0.7]])
    result = an.r2(rows, "F4_flops", exam, 0.1, True)
    a = result["recipes"]["a"]
    assert a["curves"]["steps"]["plateau"] == 2 and a["curves"]["width"]["plateau"] == 4
    assert a["plateau"] == 4 and a["score_at_plateau"] == 0.9
    assert result["recipes"]["b"]["no_plateau"] == ["steps"]


def test_r3_doubles_the_largest_best_plateau_and_blocks_on_a_missing_one():
    rows = []
    for name, top in (("a", 0.9), ("b", 0.8), ("c", 0.7)):
        rows += sweep(name, "steps", [[top - 0.3], [top], [top + 0.01]], base=3)
    r2 = an.r2(rows, "F4_flops", exam, 0.1, True)
    assert an.best(r2, True) == ["a", "b", "c"]
    result = an.r3(r2, ["a", "b", "c"])
    assert result["limit"] == 12 and result["owner_chooses"] is None
    rows += sweep("c", "width", [[0.1], [0.5], [0.9]])
    blocked = an.r3(an.r2(rows, "F4_flops", exam, 0.1, True), ["a", "b", "c"])
    assert blocked["limit"] is None
    assert blocked["blocked_by_curves_without_plateau"] == ["c:width"]


def test_r9_sets_d_and_says_when_data_binds():
    rows = []
    for name in ("a", "b", "c"):
        for size, s in ((100, 0.5), (200, 0.7), (400, 0.72), (800, 0.73)):
            row = record("G", 1.0, run_id=f"{name}{size}")
            row["run"].update(recipe=name, train_size=size)
            row["score"] = {"exam_score": s}
            rows.append(row)
    result = an.r9(rows, exam, 0.1, True, ["a", "b", "c"], [100, 200, 400, 800], 800)
    assert result["D"] == 200 and result["data_binds"] is False
    for row in rows:
        if row["run"]["train_size"] == 800:
            row["score"]["exam_score"] = 0.9
    binding = an.r9(rows, exam, 0.1, True, ["a", "b", "c"], [100, 200, 400, 800], 800)
    assert binding["D"] == 800 and binding["data_binds"] is True


# -- Finalists --------------------------------------------------------------------


def test_r4_doubles_l_on_an_improvement_and_warns_on_a_quiet_change():
    improved = an.r4(
        {"best_at_L": "a", "best_at_4L": "b", "classification": "IMPROVEMENT"}
    )
    assert improved["l_binds_on_quality"] and improved["warning"] is None
    quiet = an.r4({"best_at_L": "a", "best_at_4L": "b", "classification": "EQUIVALENT"})
    assert not quiet["l_binds_on_quality"] and quiet["warning"]
    with pytest.raises(an.AnalysisRefused):
        an.r4({"best_at_L": "a"})


def test_r10_takes_the_smallest_safe_fraction_with_its_smallest_k():
    fractions = [1 / 16, 1 / 4, 1]
    rankings = {
        0: {1 / 16: ["c", "a", "d", "b"], 1 / 4: ["a", "b", "c", "d"]},
        1: {1 / 16: ["a", "d", "b", "c"], 1 / 4: ["b", "a", "c", "d"]},
    }
    finalists = {0: ["a", "b"], 1: ["a", "b"]}
    # 1/16 needs all 4 (screens nothing); 1/4 keeps both finalists in the top 2.
    assert an.r10(rankings, finalists, fractions)["screen"] == {
        "fraction": 1 / 4,
        "survivors": 2,
    }
    tight = {0: {1 / 16: ["c", "d", "a", "b"]}, 1: {1 / 16: ["d", "c", "b", "a"]}}
    assert an.r10(tight, finalists, [1 / 16, 1])["screen"] is None
