"""Honesty-scale sheet tools: E2 (an honest model plus the truth-built control's bias), the recording, the A_gen scale
sweep and the render. All values are SYNTHETIC toy numbers (the pool proof suite's toy problem); none is a production value.
"""

from __future__ import annotations

import json
import math

import pytest

from carbon.scoring import pool_grader
from carbon.scoring import pool_proof_suite as suite
from scripts.dev import design_value_parts as parts_tool
from scripts.dev import honesty_scale_sheet as sheet
from tests.cpu import test_pool_proof_suite as toy

SPEC = {
    "budget": 40,
    "sigma0": 0.3,
    "population": None,
    "honesty_reduction": "max",
    "agen_scale_sets": [{"f": 0.1, "g": 0.1}, {"f": 0.03, "g": 0.03}],
    "a_rule": {"kind": "mean"},
    "c_rule": {"kind": "min"},
    "optimism_k": 3.0,
    "wrong_radius": 0.2,
    "wrong_k": 10.0,
    "seed": 5,
    "bases": ["good", "default"],
}


def plugin():
    base = toy.build_plugin()
    legs = base.legs

    def legs_of(descriptor, specs):
        if descriptor["kind"] == "biased":
            return legs(descriptor["base"], specs)
        out = dict(legs(descriptor, specs))
        # two legs whose mean is the toy A, so the A multiplier tightens them one by one as the exam does
        out["A_legs"] = {"x": min(1.0, out["A"] + 0.05), "y": max(0.0, out["A"] - 0.05)}
        return out

    return base.__class__(**{**base.__dict__, "legs": legs_of})


def biased(mode, base="good", **extra):
    bias = {"mode": mode, "k": 4.0, "seed": 3, **extra}
    return {"kind": "biased", "base": {"kind": base}, "bias": bias}


def all_specs(p):
    return [s for specs in p.sets for s in specs]


def test_e2_feasible_bias_moves_only_the_limit_output_toward_safe_and_is_deterministic():
    p = plugin()
    specs = all_specs(p)
    honest = suite.pool_predictor(p, {"kind": "good"}, specs)
    e2 = suite.pool_predictor(p, biased("feasible_bias"), specs)
    spec = p.sets[0][0]
    designs = [list(d) for d in spec.designs[:5]]
    for h, b, row in zip(
        honest(spec.conditions, designs), e2(spec.conditions, designs), range(5)
    ):
        assert math.isclose(b["f"], h["f"])  # the objective output is not a limit
        assert math.isclose(h["g"] - b["g"], 4.0 * toy.U)  # g <= bound: 4U safer
    assert e2(spec.conditions, designs) == e2(spec.conditions, designs)


def test_e2_wrong_near_changes_only_rows_within_the_radius_of_the_reference_optimum():
    p = plugin()
    specs = all_specs(p)
    honest = suite.pool_predictor(p, {"kind": "good"}, specs)
    e2 = suite.pool_predictor(p, biased("wrong_near", radius=0.2), specs)
    spec = p.sets[0][0]
    near = far = 0
    for index, design in enumerate(spec.designs):
        h = honest(spec.conditions, [list(design)])[0]
        b = e2(spec.conditions, [list(design)])[0]
        inside = math.dist(spec.norm[spec.reference], spec.norm[index]) <= 0.2
        if inside:
            near += 1
            assert all(
                math.isclose(abs(b[k] - h[k]), 4.0 * toy.U, rel_tol=1e-9) for k in h
            )
        else:
            far += 1
            assert b == h
    assert near and far


def test_an_unknown_bias_mode_is_refused():
    p = plugin()
    with pytest.raises(pool_grader.PoolRefused, match="unknown_bias_mode"):
        suite.pool_predictor(p, biased("shout"), all_specs(p))


def test_record_holds_q_and_e_and_d_at_any_scale_equals_the_grader_at_that_scale():
    p = plugin()
    dump = sheet.record(p, SPEC, "toy", "1.0", a_multiplier=1.0)
    assert {"oracle", "good", "default", "floor", "in_distribution_only"} <= set(
        dump["models"]
    )
    assert (
        "e2_optimistic[good]" in dump["models"]
        and "e2_wrong_near[default]" in dump["models"]
    )
    json.dumps(dump, allow_nan=False)  # aggregates only, finite
    optimizer = pool_grader.OptimizerPolicy(budget=40, sigma0=0.3, population=None)
    predict = suite.pool_predictor(p, {"kind": "good"}, all_specs(p))
    for s_h in (1.0, 5.0, 30.0):
        honesty = pool_grader.HonestyPolicy(scale=s_h, reduction="max")
        grades = [
            pool_grader.grade_set(specs, predict, optimizer, honesty)
            for specs in p.sets
        ]
        model = dump["models"]["good"]
        expected = sum(min(g.d, model["C"]) for g in grades) / len(grades)
        assert math.isclose(sheet.model_d(model, s_h), expected, rel_tol=1e-12)


def test_a_gen_at_a_stricter_scale_is_lower_and_the_sweep_uses_the_graders_own_functions():
    p = plugin()
    specs = p.sets[0]
    predict = suite.pool_predictor(p, {"kind": "good"}, all_specs(p))
    optimizer = pool_grader.OptimizerPolicy(budget=20, sigma0=0.3, population=None)
    honesty = pool_grader.HonestyPolicy(scale=1.0, reduction="max")
    sets = [{"f": 0.1, "g": 0.1}, {"f": 0.01, "g": 0.01}]
    rule = {"kind": "mean"}
    with parts_tool.recording(sets) as recorder:
        pool_grader.grade_set(specs, predict, optimizer, honesty)
        gen = pool_grader.agen_accuracy(specs, predict, sets[0])
        pool_grader.combine_a(0.8, gen, rule)
    sweep = parts_tool.agen_sweep(recorder, sets)
    assert sweep[0]["A"] == pool_grader.combine_a(0.8, gen, rule)
    stricter = pool_grader.agen_accuracy(specs, predict, sets[1])
    assert sweep[1]["A"] == pool_grader.combine_a(0.8, stricter, rule)
    assert stricter < gen and sweep[1]["A"] < sweep[0]["A"]
    # recording restored the grader's functions
    assert pool_grader.agen_accuracy.__module__ == "carbon.scoring.pool_grader"


def test_without_a_sweep_the_recording_changes_nothing_and_the_sweep_refuses():
    p = plugin()
    with parts_tool.recording() as recorder:
        assert pool_grader.agen_accuracy.__module__ == "carbon.scoring.pool_grader"
    with pytest.raises(parts_tool.PartsError, match="no A_gen sweep"):
        parts_tool.agen_sweep(recorder, SPEC["agen_scale_sets"])
    assert p


def parts_file(tmp_path, name, errors, a):
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "regraded_a": a,
                "sets": [
                    {
                        "C": 0.9,
                        "targets": [{"q": 0.9, "e": e} for e in errors],
                    }
                ],
            }
        )
    )
    return str(path)


def test_render_writes_the_candidates_and_flags_a_gaming_control_above_its_honest_base(
    tmp_path,
):
    p = plugin()
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps(sheet.record(p, SPEC, "toy", "1.0", a_multiplier=1.0)))
    out = tmp_path / "sheet.md"
    spec = {
        "out": str(out),
        "ks": [0.25, 0.5, 1.0],
        "challenges": [
            {
                "key": "toy",
                "name": "Toy",
                "dump": str(dump),
                "baseline_parts": parts_file(
                    tmp_path, "b.json", [4, 20, 30, 40, 60], 0.6
                ),
                "crown_parts": parts_file(tmp_path, "c.json", [1, 2, 3, 5, 20], 0.9),
            }
        ],
    }
    spec_path = tmp_path / "render.json"
    spec_path.write_text(json.dumps(spec))
    assert sheet.main(["render", "--spec", str(spec_path)]) == 0
    text = out.read_text()
    assert "0 (keep s_h = 1)" in text and "k=0.25" in text and "k=1" in text
    assert "e2_optimistic[good]" in text and "A at stricter A_gen scales" in text
    # the median baseline error is 30, so k=0.5 is s_h 15
    assert "| k=0.5 | 15 |" in text
    assert "PASS" in text or "FAIL" in text


def test_the_recorded_a_with_the_registered_multiplier_equals_the_proof_grids_cell():
    from carbon.scoring import pool_proof_grid as grid_module

    p = plugin()
    scales = SPEC["agen_scale_sets"][0]
    dump = sheet.record(p, SPEC, "toy", "1.0", a_multiplier=3.0)
    assert dump["a_multiplier"] == 3.0
    spec = grid_module.GridSpec(
        in_distribution_is_pass_criterion=False,
        budgets=(SPEC["budget"],),
        honesty_scales=(1.0,),
        honesty_reduction="max",
        a_multipliers=(3.0,),
        agen_scale_sets=(scales,),
        a_rules=(SPEC["a_rule"],),
        c_rule=SPEC["c_rule"],
        sigma0=SPEC["sigma0"],
        population=SPEC["population"],
        good_target=0.99,
        koth_margin=0.01,
        optimism_k=SPEC["optimism_k"],
        wrong_radius=SPEC["wrong_radius"],
        wrong_k=SPEC["wrong_k"],
        oracle_tolerance=1e-9,
        seed=SPEC["seed"],
    )
    (row,) = grid_module.run_grid(p, spec)["rows"]
    for name in ("good", "default"):
        model = dump["models"][name]
        legs = row["legs"][name]
        assert math.isclose(model["A"], legs["A"], rel_tol=1e-12)
        assert math.isclose(
            sheet.model_a(model, 0, SPEC["a_rule"]), legs["A_all"], rel_tol=1e-12
        )
        assert math.isclose(sheet.model_d(model, 1.0), legs["D"], rel_tol=1e-12)
        assert math.isclose(
            sheet.model_total(model, 1.0, 0, SPEC["a_rule"]), row[name], rel_tol=1e-12
        )
    # and the multiplier really tightens: A at 3 is below A at 1
    base = sheet.record(p, SPEC, "toy", "1.0", a_multiplier=1.0)
    assert dump["models"]["good"]["A"] < base["models"]["good"]["A"]


def test_the_multiplier_is_required_positive_and_never_taken_from_the_spec():
    p = plugin()
    for bad in (0, -1.0, float("nan"), True, "3", None):
        with pytest.raises(sheet.SheetError, match="a_multiplier_must_be"):
            sheet.record(p, SPEC, "toy", "1.0", a_multiplier=bad)
    with pytest.raises(sheet.SheetError, match="comes_from_the_registered_version"):
        sheet.record(p, {**SPEC, "a_multiplier": 3.0}, "toy", "1.0", a_multiplier=3.0)


def test_registered_inputs_reads_the_registered_multiplier_and_refuses_a_differing_spec():
    f08 = {
        "budget": 80,
        "sigma0": 0.25,
        "population": None,
        "honesty_reduction": "max",
        "a_rule": {"kind": "mean"},
        "c_rule": {"kind": "min"},
    }
    assert sheet.registered_inputs("f08", "1.7", f08) == 3.0
    with pytest.raises(
        sheet.SheetError, match="spec_differs_from_the_registered_version: budget"
    ):
        sheet.registered_inputs("f08", "1.7", {**f08, "budget": 60})
    with pytest.raises(sheet.SheetError, match="version_not_registered"):
        sheet.registered_inputs("f08", "1.6", f08)  # HUMAN_INPUT: refuses
    with pytest.raises(sheet.SheetError, match="not_a_registered_pool_kind"):
        sheet.registered_inputs("nonsense", "1.0", f08)


def test_the_regrade_sets_file_must_name_the_version_and_kind_it_regrades(tmp_path):
    from scripts.dev import design_value_parts_regrade as regrade

    path = tmp_path / "sets.json"
    path.write_text(
        json.dumps(
            {
                "kind": "f08",
                "version": "1.7",
                "agen_scale_sets": [{"a": 1.0}, {"a": 0.5}],
            }
        )
    )
    assert regrade.load_agen_sets(path, "f08-ribbed-bracket", "1.7") == [
        {"a": 1.0},
        {"a": 0.5},
    ]
    with pytest.raises(regrade.RegradeError, match="built for version '1.7'"):
        regrade.load_agen_sets(path, "f08-ribbed-bracket", "1.6")
    with pytest.raises(regrade.RegradeError, match="not for the challenge"):
        regrade.load_agen_sets(path, "f02", "1.7")
    path.write_text("[]")
    with pytest.raises(regrade.RegradeError, match="not a recorder sets file"):
        regrade.load_agen_sets(path, "f08-ribbed-bracket", "1.7")
