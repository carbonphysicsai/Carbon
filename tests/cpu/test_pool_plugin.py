"""The generic Challenge bridge for the pool grader (plan POOL_PLUGIN_WIRING_PLAN_20261024).

A toy Challenge with a fake sealed `measure`: every number is a SYNTHETIC test value.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from carbon.scoring import pool_grader
from carbon.scoring import pool_plugin as pp
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import (
    HonestyPolicy,
    Limit,
    OptimizerPolicy,
    build_target,
)

U = 0.01
INPUTS = ("cond", "x", "y")
DESIGN = ("x", "y")


def truth(row):
    return [row["x"] + row["y"], row["x"] ** 2 + row["y"] ** 2]


def derive(row, raw):
    return {"f": raw[0], "g": raw[1]}


def toy_target(name, seed):
    import random

    rng = random.Random(seed)
    pts = [(rng.random(), rng.random()) for _ in range(60)]
    pts += [
        (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
        for _ in range(40)
    ]
    rows = [{"cond": 1.0, "x": x, "y": y} for x, y in pts]
    return build_target(
        target_id=name,
        conditions={"target_id": name, "fixed": {"cond": 1.0}},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[[x, y] for x, y in pts],
        truths=[dict(zip(("f", "g"), truth(r), strict=True)) for r in rows],
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=seed,
    )


def good_serve(rows):
    # a slightly wrong model: truth plus 2 U on both outputs
    return [[v + 2 * U for v in truth(r)] for r in rows]


def default_row():
    return [0.9, 0.5]


def binding(serve_good=good_serve):
    return pp.ChallengeBinding(
        kind="toy",
        version="1",
        input_names=INPUTS,
        design_names=DESIGN,
        derive=derive,
        raw_u=lambda row, ref: [U] * len(ref),
        train_mean_row=default_row,
        serve_good=serve_good,
        serve_train=good_serve,
        train_box=lambda spec: ((0.0, 0.5), (0.0, 0.5)),
    )


def fake_measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A fake sealed measure: A = mean of four legs; the response leg and the law gate read the probe rows."""
    cells = [
        (r, o)
        for r, o in zip(bank_rows, outputs, strict=True)
        if r["reference"] is not None
    ]
    probes = [
        (r, o)
        for r, o in zip(bank_rows, outputs, strict=True)
        if r["reference"] is None
    ]
    acc = sum(
        1.0
        / (1.0 + sum(abs(a - b) for a, b in zip(o, r["reference"], strict=True)) / 0.1)
        for r, o in cells
    ) / len(cells)
    # the probes step y upward at fixed x: a model that obeys the law answers with a strictly rising f
    rising = all(b[1][0] > a[1][0] for a, b in pairwise(probes))
    response = 1.0 if rising else 0.2
    legs = {"A_acc": acc, "A_robust": 1.0, "A_law": 1.0, "A_response": response}
    finite = all(abs(v) < 1e6 for o in outputs for v in o)
    gates = {
        "finite": finite,
        "paired_repeat": repeats[0] == repeats[1],
        "physics_laws": response > 0.5,
    }
    if not finite:
        return {"A": None, "D": 0.0, "gates": gates}
    return {
        "A": sum(legs.values()) / 4,
        "D": 1.0,
        "A_legs": legs,
        "gates": gates,
        "design_fidelity": {"C": acc},
    }


def bank_rows():
    rows = []
    for i in range(4):
        row = {"cond": 1.0, "x": 0.2 + 0.1 * i, "y": 0.3}
        rows.append({"case_id": f"c{i}", "inputs": row, "reference": truth(row)})
    for i in range(3):
        row = {"cond": 1.0, "x": 0.5, "y": 0.1 * (i + 1)}
        rows.append({"case_id": f"p{i}", "inputs": row, "reference": None})
    return rows


def bank_legs(rule="perfect", the_binding=None):
    return pp.BankLegs(
        binding=the_binding or binding(),
        measure=fake_measure,
        rows=bank_rows(),
        arguments={
            "definition": {},
            "limits": {},
            "objective": {},
            "train_raw": b"",
            "names": INPUTS,
        },
        truth_probe_rule=rule,
        response_leg="A_response",
        ignored_gates=("physics_laws",),
    )


def test_a_model_input_row_is_fixed_conditions_plus_the_design_and_must_match_the_interface():
    b = binding()
    row = pp.model_input_row(b, {"target_id": "t", "fixed": {"cond": 2.0}}, [0.1, 0.2])
    assert row == {"cond": 2.0, "x": 0.1, "y": 0.2}
    with pytest.raises(pp.PluginRefused, match="fixed"):
        pp.model_input_row(b, {"target_id": "t"}, [0.1, 0.2])
    with pytest.raises(pp.PluginRefused, match="design_does_not_match"):
        pp.model_input_row(b, {"fixed": {"cond": 1.0}}, [0.1])
    with pytest.raises(pp.PluginRefused, match="input_row_does_not_match"):
        pp.model_input_row(b, {"fixed": {"other": 1.0}}, [0.1, 0.2])


def test_the_pool_predictor_derives_the_graders_quantities_from_raw_rows():
    predict = pp.pool_predictor(binding(), good_serve)
    out = predict({"fixed": {"cond": 1.0}}, [[0.3, 0.4]])
    assert out == [{"f": pytest.approx(0.7 + 2 * U), "g": pytest.approx(0.25 + 2 * U)}]
    with pytest.raises(pp.PluginRefused, match="one_row_per_input"):
        pp.pool_predictor(binding(), lambda rows: [])(
            {"fixed": {"cond": 1.0}}, [[0.3, 0.4]]
        )


def test_a_cached_predictor_asks_the_model_once_per_point():
    calls = []

    def predict(conditions, designs):
        calls.append(len(designs))
        return [{"f": d[0]} for d in designs]

    cached_predict, stats = pp.cached(predict)
    conditions = {"fixed": {"cond": 1.0}}
    assert cached_predict(conditions, [[1.0, 2.0], [3.0, 4.0]]) == [
        {"f": 1.0},
        {"f": 3.0},
    ]
    assert cached_predict(conditions, [[3.0, 4.0], [5.0, 6.0]]) == [
        {"f": 3.0},
        {"f": 5.0},
    ]
    assert calls == [2, 1] and stats == {"calls": 2, "points_computed": 3}


def test_truth_models_are_perfect_on_the_probe_rows_only_by_the_explicit_rule():
    legs = bank_legs("perfect").legs({"kind": "oracle"})
    assert (
        legs["A"] == pytest.approx(1.0)
        and legs["C"] == pytest.approx(1.0)
        and legs["gates_ok"] is True
    )
    measured = bank_legs("measured").legs({"kind": "oracle"})
    assert (
        measured["A"] < 0.95 and measured["gates_ok"] is False
    ), "graded as it stands, probes answered by TRAIN mean"
    with pytest.raises(pp.PluginRefused, match="truth_probe_rule"):
        bank_legs("whatever").legs({"kind": "oracle"})


def test_the_descriptor_models_order_as_the_suite_expects_on_the_bank():
    b = bank_legs("perfect")
    oracle = b.legs({"kind": "oracle"})["A"]
    small = b.legs({"kind": "noisy", "k": 1.0, "mode": "random", "seed": 3})["A"]
    large = b.legs({"kind": "noisy", "k": 20.0, "mode": "random", "seed": 3})["A"]
    default = b.legs({"kind": "default"})
    good = b.legs({"kind": "good"})
    assert oracle >= small >= large
    assert default["A"] < good["A"] <= oracle and default["gates_ok"] is False
    layered = b.legs(
        {"kind": "perturbed", "base": {"kind": "good"}, "layers": [[1, 5.0]]}
    )
    assert layered["A"] <= good["A"] + 1e-9
    assert b.legs({"kind": "wrong_near_optimum", "radius": 0.1, "k": 3.0}) == b.legs(
        {"kind": "oracle"}
    )
    with pytest.raises(pp.PluginRefused, match="unknown_model_descriptor"):
        b.legs({"kind": "mystery"})


def test_an_A_that_is_not_the_mean_of_its_legs_is_refused_rather_than_recomputed_on_a_guess():
    b = bank_legs("perfect")

    def odd_measure(**kwargs):
        measured = fake_measure(**kwargs)
        measured["A"] = 0.5
        return measured

    odd = pp.BankLegs(**{**b.__dict__, "measure": odd_measure})
    with pytest.raises(pp.PluginRefused, match="A_is_not_the_mean"):
        odd.legs({"kind": "oracle"})


def test_a_measure_with_no_finite_legs_is_refused_not_scored():
    b = bank_legs("measured")
    broken = pp.BankLegs(
        **{**b.__dict__, "measure": lambda **kw: {"A": None, "gates": {}}}
    )
    with pytest.raises(pp.PluginRefused, match="no_finite"):
        broken.legs({"kind": "default"})


def test_the_plugin_runs_the_proof_suite_end_to_end_and_a_failed_gate_gives_no_score():
    sets = tuple(
        tuple(toy_target(f"s{s}t{t}", 10 * s + t) for t in range(3)) for s in range(2)
    )
    fresh = tuple(toy_target(f"f{t}", 900 + t) for t in range(3))
    b = binding()
    plugin = pp.make_plugin(b, bank_legs("perfect", b), sets, lambda draw: fresh)
    policies = suite.Policies(
        optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
        honesty=HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={"f": 0.1, "g": 0.1},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )
    params = suite.SuiteParams(
        oracle_tolerance=1e-9,
        k_grid=(0.0, 2.0, 6.0),
        monotone_tolerance=0.05,
        optimism_k=30.0,
        wrong_radius=0.15,
        wrong_k=12.0,
        leak_rounds=4,
        leak_step=1.0,
        ladder_decimals=2,
        koth_margin=0.02,
        near_optimum_radius=0.15,
        near_limit_u=10.0,
        bins=5,
        separation_target=0.95,
        seed=7,
        resamples=20,
    )
    oracle = suite.check_oracle_is_perfect(plugin, policies, params)
    assert oracle["verdict"] == "PASS", oracle
    # The default model's gate fails on the bank (law gate), so its total is exactly 0.
    assert suite.version_total(plugin, {"kind": "default"}, policies) == 0.0
    good = suite.version_total(plugin, {"kind": "good"}, policies)
    assert 0.0 < good < 1.0
    report = suite.run_suite(plugin, policies, params)
    assert set(report) >= {"1_oracle", "6_separation", "all_pass"}
    assert pool_grader.REASONS  # the module is the one the suite grades with


def _grid_plugin():
    sets = tuple(
        tuple(toy_target(f"s{s}t{t}", 10 * s + t) for t in range(3)) for s in range(2)
    )
    b = binding()
    return pp.make_plugin(b, bank_legs("perfect", b), sets, lambda draw: ())


def _grid_spec(**changes):
    from carbon.scoring import pool_proof_grid as grid

    base = {
        "budgets": (60, 90),
        "honesty_scales": (2.0, 10.0),
        "honesty_reduction": "max",
        "a_multipliers": (1.0, 3.0),
        "agen_scale_sets": ({"f": 0.1, "g": 0.1}, {"f": 0.02, "g": 0.02}),
        "a_rules": ({"kind": "min"}, {"kind": "mean"}),
        "c_rule": {"kind": "min"},
        "sigma0": 0.3,
        "population": None,
        "good_target": 0.95,
        "koth_margin": 0.02,
        "optimism_k": 30.0,
        "wrong_radius": 0.15,
        "wrong_k": 12.0,
        "oracle_tolerance": 1e-9,
        "seed": 7,
    }
    return grid.GridSpec(**{**base, **changes})


def test_the_owner_sheet_sweeps_every_constant_and_reports_aggregates_only():
    from carbon.scoring import pool_proof_grid as grid

    result = grid.run_grid(_grid_plugin(), _grid_spec())
    rows = result["rows"]
    assert len(rows) == 2 * 2 * 2 * 2 * 2 and result["meta"]["rows"] == 32
    keys = {
        "B",
        "s_h",
        "A_multiplier",
        "A_gen_scales",
        "A_gen_rule",
        "good",
        "default",
        "H",
        "S",
        "controls",
        "controls_margin",
        "oracle_reaches_all_references",
        "oracle_total",
        "meets_all",
    }
    assert all(set(r) == keys for r in rows)
    # Everything in it is a number or a label: no design, truth or pick.
    text = grid.dump(result)
    assert "designs" not in text and "truths" not in text and "pick" not in text
    assert all(
        abs(r["H"] - (1.0 - r["good"])) < 1e-12
        and abs(r["S"] - (r["good"] - r["default"])) < 1e-12
        for r in rows
    )
    assert (
        grid.dump(grid.run_grid(_grid_plugin(), _grid_spec())) == text
    ), "deterministic"


def test_a_tighter_a_scale_lowers_the_good_model_and_a_larger_honesty_scale_raises_it():
    from carbon.scoring import pool_proof_grid as grid

    rows = grid.run_grid(_grid_plugin(), _grid_spec())["rows"]

    def good(**where):
        picked = [r["good"] for r in rows if all(r[k] == v for k, v in where.items())]
        return statistics_mean(picked)

    from statistics import fmean as statistics_mean

    assert good(A_multiplier=3.0) < good(A_multiplier=1.0)
    assert good(s_h=10.0) > good(s_h=2.0)


def test_the_sheet_marks_rows_meeting_every_condition_and_refuses_a_bad_reduction():
    from carbon.scoring import pool_proof_grid as grid

    strict = grid.run_grid(_grid_plugin(), _grid_spec(good_target=0.0))
    assert strict["meta"]["rows_meeting_all"] == 0 and not any(
        r["meets_all"] for r in strict["rows"]
    )
    text = grid.sheet_markdown("Toy", strict)
    assert (
        text.startswith("# Toy: the owner's scoring sheet")
        and "0 of 32 grid points" in text
    )
    loose = grid.run_grid(_grid_plugin(), _grid_spec(good_target=1.0, koth_margin=0.0))
    assert loose["meta"]["needed_separation"] == pytest.approx(0.10)
    with pytest.raises(pool_grader.PoolRefused, match="honesty_reduction"):
        grid.run_grid(_grid_plugin(), _grid_spec(honesty_reduction="mean"))
    assert (
        grid.tighten(0.5, 3.0) == pytest.approx(0.25) and grid.tighten(0.0, 3.0) == 0.0
    )


def _source_document(name, seed):
    """Data Collection's custody document for a toy target (build_target inputs plus design_names)."""
    spec = toy_target(name, seed)
    return {
        "target_id": name,
        "conditions": spec.conditions,
        "design_names": list(DESIGN),
        "outputs": list(spec.outputs),
        "objective": spec.objective,
        "sense": "max",
        "limits": [["g", "<=", 0.8]],
        "u": spec.u,
        "box": [list(b) for b in spec.box],
        "designs": [list(d) for d in spec.designs],
        "truths": list(spec.truths),
        "agen": list(spec.agen),
        "start": list(spec.start),
        "seed": spec.seed,
    }


def test_a_custody_pool_source_loads_only_with_the_bindings_design_names():
    document = _source_document("src", 3)
    spec = pp.spec_from_source(document, binding())
    assert spec.target_id == "src" and len(spec.designs) > 90
    dict_limits = dict(document, limits=[{"output": "g", "kind": "<=", "bound": 0.8}])
    assert pp.spec_from_source(dict_limits, binding()).digest == spec.digest
    with pytest.raises(pp.PluginRefused, match="design_names_differ"):
        pp.spec_from_source(dict(document, design_names=["y", "x"]), binding())
    with pytest.raises(pp.PluginRefused, match="conditions_must_be"):
        pp.spec_from_source(dict(document, conditions={"fixed": {}}), binding())


def test_the_grid_script_writes_an_owner_sheet_from_custody_documents(
    tmp_path, monkeypatch
):
    import importlib.util
    import json
    from pathlib import Path

    path = Path(pp.__file__).resolve().parents[2] / "scripts/dev/pool_proof_grid.py"
    spec = importlib.util.spec_from_file_location("pool_proof_grid_script", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    pools = tmp_path / "pools"
    pools.mkdir()
    names = {"A": ["a1", "a2"], "B": ["b1", "b2"]}
    for i, tid in enumerate(t for ts in names.values() for t in ts):
        (pools / f"pool-source-{tid}.json").write_text(
            json.dumps(_source_document(tid, i))
        )
    (tmp_path / "sets.json").write_text(json.dumps(names))
    grid_doc = {
        "budgets": [60],
        "honesty_scales": [2.0, 10.0],
        "honesty_reduction": "max",
        "a_multipliers": [1.0],
        "agen_scale_sets": [{"f": 0.1, "g": 0.1}],
        "a_rules": [{"kind": "min"}],
        "c_rule": {"kind": "min"},
        "sigma0": 0.3,
        "population": None,
        "good_target": 0.95,
        "koth_margin": 0.02,
        "optimism_k": 30.0,
        "wrong_radius": 0.15,
        "wrong_k": 12.0,
        "oracle_tolerance": 1e-9,
        "seed": 7,
    }
    (tmp_path / "grid.json").write_text(json.dumps(grid_doc))
    b = binding()
    monkeypatch.setattr(script, "_binding", lambda path, kind, version: b)
    monkeypatch.setattr(
        pp,
        "practice_bank_legs",
        lambda bound, **kw: bank_legs(kw["truth_probe_rule"], bound),
    )
    code = script.main(
        [
            "--kind",
            "toy",
            "--version",
            "1",
            "--binding",
            "x:y",
            "--pools-dir",
            str(pools),
            "--sets",
            str(tmp_path / "sets.json"),
            "--grid",
            str(tmp_path / "grid.json"),
            "--out-dir",
            str(tmp_path / "out"),
            "--truth-probe-rule",
            "perfect",
            "--response-leg",
            "A_response",
            "--ignored-gates",
            "physics_laws",
        ]
    )
    assert code == 0
    result = json.loads((tmp_path / "out/owner-sheet-toy-1.json").read_text())
    assert result["meta"]["rows"] == 2 and len(result["rows"]) == 2
    assert (
        (tmp_path / "out/owner-sheet-toy-1.md")
        .read_text()
        .startswith("# toy 1: the owner's scoring sheet")
    )
