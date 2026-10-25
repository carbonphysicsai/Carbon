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


def toy_target(name, seed, shell=None):
    import random

    rng = random.Random(seed)
    if shell is None:
        pts = [(rng.random(), rng.random()) for _ in range(60)]
        pts += [
            (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
            for _ in range(40)
        ]
        bound = 0.8
    else:
        # an extended target: every point lies in the shell (x or y in 0.6..1.0), with its own looser limit
        pts = [(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0)) for _ in range(100)]
        bound = 1.2
    rows = [{"cond": 1.0, "x": x, "y": y} for x, y in pts]
    return build_target(
        target_id=name,
        conditions={"target_id": name, "fixed": {"cond": 1.0}},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", bound),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[[x, y] for x, y in pts],
        truths=[dict(zip(("f", "g"), truth(r), strict=True)) for r in rows],
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=seed,
        shell=shell,
    )


def good_serve(rows):
    # a slightly wrong model: truth plus 2 U on both outputs
    return [[v + 2 * U for v in truth(r)] for r in rows]


def default_row():
    return [0.9, 0.5]


def default_serve(rows):
    # the bound default pick: a rising but much weaker model (half the truth)
    return [[0.5 * v for v in truth(r)] for r in rows]


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
        serve_default=default_serve,
        train_box=lambda spec: ((0.0, 0.5), (0.0, 0.5)),
        probe_truth=lambda rows: [truth(r) for r in rows],
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


def bank_legs(rule="perfect", the_binding=None, verified=True):
    legs = pp.BankLegs(
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
        truth_tolerance=1e-5,
        state={},
    )
    if rule == "perfect" and verified:
        legs.verify_truth_rows()
    return legs


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
    floor = b.legs({"kind": "floor"})
    assert default["A"] < good["A"] <= oracle
    assert (
        floor["gates_ok"] is False
    ), "the TRAIN-mean floor fails the law gate on the bank"
    assert (
        floor["A"] < default["A"]
    ), "the floor is its own, lower row, never the default"
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
    plugin = pp.make_plugin(
        b, bank_legs("perfect", b), sets, lambda draw: fresh, pool_gates=False
    )
    policies = suite.Policies(
        optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
        honesty=HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={"f": 0.1, "g": 0.1},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )
    params = suite.SuiteParams(
        in_distribution_is_pass_criterion=False,
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
    # The floor's law gate fails on the bank, so its total is exactly 0; the bound default pick is a real model.
    assert suite.version_total(plugin, {"kind": "floor"}, policies) == 0.0
    assert 0.0 < suite.version_total(plugin, {"kind": "default"}, policies)
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
    return pp.make_plugin(
        b, bank_legs("perfect", b), sets, lambda draw: (), pool_gates=False
    )


def _grid_spec(**changes):
    from carbon.scoring import pool_proof_grid as grid

    base = {
        "in_distribution_is_pass_criterion": False,
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
        "registered",
        "extended",
        "in_distribution_ood_margin",
        "pool_gate_failures",
        "speed_gate_failed",
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
        lambda bound, **kw: bank_legs(kw["truth_probe_rule"], bound, verified=False),
    )
    args = [
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
        "--truth-tolerance",
        "1e-5",
        "--pool-gates",
        "off",
        "--in-distribution",
        "reported",
    ]
    code = script.main(args)
    assert code == 0
    result = json.loads((tmp_path / "out/owner-sheet-toy-1.json").read_text())
    assert result["meta"]["rows"] == 2 and len(result["rows"]) == 2
    assert (
        (tmp_path / "out/owner-sheet-toy-1.md")
        .read_text()
        .startswith("# toy 1: the owner's scoring sheet")
    )
    # A binding that cannot supply true probe outputs STOPS the run, back to the Validator, with no sheet.
    none = pp.ChallengeBinding(**{**b.__dict__, "probe_truth": None})
    monkeypatch.setattr(script, "_binding", lambda path, kind, version: none)
    monkeypatch.setattr(
        pp,
        "practice_bank_legs",
        lambda bound, **kw: bank_legs(kw["truth_probe_rule"], bound, verified=False),
    )
    stop_args = list(args)
    stop_args[stop_args.index(str(tmp_path / "out"))] = str(tmp_path / "out2")
    assert script.main(stop_args) == 3
    assert not (tmp_path / "out2").exists()
    # Data Collection's solved probe truths, by case id, unblock it (here the toy truth at each probe).
    solved = {
        r["case_id"]: truth(r["inputs"]) for r in bank_rows() if r["reference"] is None
    }
    (tmp_path / "probe.json").write_text(json.dumps(solved))
    with_file = [*stop_args, "--probe-truth-file", str(tmp_path / "probe.json")]
    with_file[with_file.index(str(tmp_path / "out2"))] = str(tmp_path / "out3")
    assert script.main(with_file) == 0
    assert (tmp_path / "out3/owner-sheet-toy-1.json").exists()


def test_the_perfect_rule_needs_the_truth_row_check_and_the_check_stops_on_failure():
    unchecked = bank_legs("perfect", verified=False)
    with pytest.raises(pp.PluginRefused, match="truth_row_check_required"):
        unchecked.legs({"kind": "oracle"})
    # Models that are not truth models never need it (and never get the rule).
    assert unchecked.legs({"kind": "good"})["gates_ok"] is True
    record = unchecked.verify_truth_rows()
    assert record["response_leg"] == pytest.approx(1.0)
    assert unchecked.legs({"kind": "oracle"})["gates_ok"] is True
    # Truth that breaks the law (probe answers not rising) is a STOP, not a pass.
    wrong = pp.ChallengeBinding(
        **{**binding().__dict__, "probe_truth": lambda rows: [[0.5, 0.5]] * len(rows)}
    )
    with pytest.raises(pp.TruthCheckStop, match="fail_the_checks"):
        bank_legs("perfect", wrong, verified=False).verify_truth_rows()
    none = pp.ChallengeBinding(**{**binding().__dict__, "probe_truth": None})
    with pytest.raises(pp.TruthCheckStop, match="supplies_no_probe_truth"):
        bank_legs("perfect", none, verified=False).verify_truth_rows()
    short = pp.ChallengeBinding(
        **{**binding().__dict__, "probe_truth": lambda rows: []}
    )
    with pytest.raises(pp.TruthCheckStop, match="one_row_per_probe"):
        bank_legs("perfect", short, verified=False).verify_truth_rows()


def test_a_submitted_model_cannot_use_the_perfect_rule_even_when_built_on_the_oracle():
    b = bank_legs("perfect")
    oracle = b.legs({"kind": "oracle"})
    assert oracle["gates_ok"] is True and oracle["A"] == pytest.approx(1.0)
    # A perturbed model (what a miner submits) is graded as it stands on the probe rows, never credited.
    layered = b.legs(
        {"kind": "perturbed", "base": {"kind": "oracle"}, "layers": [[1, 0.0]]}
    )
    assert layered["gates_ok"] is False and layered["A"] < 0.95
    for kind in ("good", "default", "in_distribution"):
        assert b.legs({"kind": kind})["A_legs"]["A_response"] in (0.2, 1.0)


def test_the_model_space_hook_converts_the_references_the_truth_models_use():
    converted = pp.ChallengeBinding(
        **{**binding().__dict__, "to_model_space": lambda row: [v * 10.0 for v in row]}
    )
    plain = bank_legs("measured", binding(), verified=False)
    scaled = pp.BankLegs(**{**plain.__dict__, "binding": converted})
    native = plain.outputs_for({"kind": "oracle"})
    modelled = scaled.outputs_for({"kind": "oracle"})
    for row, ref, native_row, model_row in zip(
        plain.rows, plain.rows, native, modelled, strict=True
    ):
        if ref["reference"] is not None:
            assert model_row == pytest.approx([v * 10.0 for v in ref["reference"]])
            assert native_row == pytest.approx(ref["reference"])


def test_the_grid_script_expands_a_gen_fractions_of_the_train_spread_and_logs_it(
    tmp_path, monkeypatch
):
    import importlib.util
    import json
    from pathlib import Path

    path = Path(pp.__file__).resolve().parents[2] / "scripts/dev/pool_proof_grid.py"
    loaded = importlib.util.spec_from_file_location("pool_proof_grid_script2", path)
    script = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(script)
    pools = tmp_path / "pools"
    pools.mkdir()
    for i, tid in enumerate(("a1", "b1")):
        (pools / f"pool-source-{tid}.json").write_text(
            json.dumps(_source_document(tid, i))
        )
    (tmp_path / "sets.json").write_text(json.dumps({"A": ["a1"], "B": ["b1"]}))
    grid_doc = {
        "_note": "ignored",
        "budgets": [60],
        "honesty_scales": [3.0],
        "honesty_reduction": "max",
        "a_multipliers": [1.0],
        "agen_scale_sets_train_spread_fractions": [1.0, 0.1],
        "a_rules": [{"kind": "min"}],
        "c_rule": {"kind": "min"},
        "sigma0": 0.25,
        "population": None,
        "good_target": 0.75,
        "koth_margin": 0.01,
        "optimism_k": 3.0,
        "wrong_radius": 0.1,
        "wrong_k": 10.0,
        "oracle_tolerance": 1e-5,
        "seed": 1,
    }
    (tmp_path / "grid.json").write_text(json.dumps(grid_doc))
    b = pp.ChallengeBinding(
        **{**binding().__dict__, "train_spread": lambda: {"f": 1.0, "g": 4.0}}
    )
    monkeypatch.setattr(script, "_binding", lambda path, kind, version: b)
    monkeypatch.setattr(
        pp,
        "practice_bank_legs",
        lambda bound, **kw: bank_legs(kw["truth_probe_rule"], bound, verified=False),
    )
    probe = {
        r["case_id"]: truth(r["inputs"]) for r in bank_rows() if r["reference"] is None
    }
    (tmp_path / "probe.json").write_text(json.dumps(probe))
    args = [
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
        "--truth-tolerance",
        "1e-5",
        "--pool-gates",
        "off",
        "--in-distribution",
        "reported",
        "--probe-truth-file",
        str(tmp_path / "probe.json"),
    ]
    assert script.main(args) == 0
    log = json.loads((tmp_path / "out/agen-expansion-toy-1.json").read_text())
    assert log["scale_sets"] == [{"f": 1.0, "g": 4.0}, {"f": 0.1, "g": 0.4}]
    sheet = json.loads((tmp_path / "out/owner-sheet-toy-1.json").read_text())
    assert len(sheet["meta"]["agen_scale_sets"]) == 2
    # No spread supplied, or both forms given: refused.
    bare = pp.ChallengeBinding(**{**binding().__dict__, "train_spread": None})
    monkeypatch.setattr(script, "_binding", lambda path, kind, version: bare)
    with pytest.raises(SystemExit, match="train_spread"):
        script.main(args)


def test_the_default_is_the_bound_pick_the_floor_is_its_own_row_and_serve_default_is_required():
    from carbon.scoring import pool_proof_grid as grid

    with pytest.raises(TypeError):
        pp.ChallengeBinding(
            **{k: v for k, v in binding().__dict__.items() if k != "serve_default"}
        )
    result = grid.run_grid(_grid_plugin(), _grid_spec())
    row = result["rows"][0]
    assert {"floor", "default_model", "in_distribution_only"} <= set(row["controls"])
    # S uses the bound default pick, not the floor; the floor is a separate (lower) control.
    assert row["default"] > row["controls"]["floor"] == 0.0
    # The in-distribution control is reported, and judged only when the spec says so.
    reported = grid.run_grid(_grid_plugin(), _grid_spec())["rows"]
    judged = grid.run_grid(
        _grid_plugin(), _grid_spec(in_distribution_is_pass_criterion=True)
    )["rows"]
    assert all(
        r["controls_margin"] >= j["controls_margin"]
        for r, j in zip(reported, judged, strict=True)
    )


# TRAIN edges 0.1..0.2 on both toy inputs and an approved extension of 0.8 above: the shell is x or y in 0.6..1.0.
SHELL = {"mode": "designs", "inputs": ((0.1, 0.2, 0.0, 0.8), (0.1, 0.2, 0.0, 0.8))}


def _mixed_plugin(train_serve, train_box=None):
    sets = tuple(
        (
            toy_target(f"s{s}r", 10 * s + 1),
            toy_target(f"s{s}x", 10 * s + 2, shell=SHELL),
        )
        for s in range(2)
    )
    changes = {"serve_train": train_serve}
    if train_box is not None:
        changes["train_box"] = train_box
    b = pp.ChallengeBinding(**{**binding().__dict__, **changes})
    return pp.make_plugin(
        b, bank_legs("perfect", b), sets, lambda draw: (), pool_gates=False
    )


def test_extended_targets_are_reported_apart_and_the_train_fit_row_must_lose_on_them():
    from carbon.scoring import pool_proof_grid as grid

    # A TRAIN-fit model as good as the good model does not lose out of range: the criterion fails.
    def wide_box(spec):
        return ((0.0, 1.0), (0.0, 1.0))  # the clamp changes nothing

    same = grid.run_grid(
        _mixed_plugin(good_serve, wide_box),
        _grid_spec(in_distribution_is_pass_criterion=True),
    )
    assert same["meta"]["extended_targets"] == 2
    row = same["rows"][0]
    assert set(row["registered"]) == set(row["extended"]) == set(grid.SPLIT_MODELS)
    assert all({"D", "A_gen"} == set(v) for v in row["extended"].values())
    assert row["in_distribution_ood_margin"] == pytest.approx(0.0)
    assert not any(r["meets_all"] for r in same["rows"])

    def clamped_badly(rows):
        return [
            [v + 40 * U for v in truth(r)] for r in rows
        ]  # a TRAIN-fit model that is wrong far from TRAIN

    worse = grid.run_grid(
        _mixed_plugin(clamped_badly), _grid_spec(in_distribution_is_pass_criterion=True)
    )
    assert all(r["in_distribution_ood_margin"] > 0.0 for r in worse["rows"])
    # Reported only (Phase 1): the margin is shown but never judged.
    reported = grid.run_grid(
        _mixed_plugin(good_serve, wide_box),
        _grid_spec(in_distribution_is_pass_criterion=False),
    )
    assert reported["rows"][0]["in_distribution_ood_margin"] == pytest.approx(0.0)
    # With no extended target the sheet has no extended block.
    plain = grid.run_grid(_grid_plugin(), _grid_spec())
    assert (
        plain["meta"]["extended_targets"] == 0 and plain["rows"][0]["extended"] is None
    )
    assert "T5/T6 TRAIN-fit margin" in grid.sheet_markdown("Toy", worse)
    assert "T5/T6" not in grid.sheet_markdown("Toy", plain)


def test_the_suite_judges_the_clamp_on_the_extended_targets():
    sets = tuple(
        (
            toy_target(f"q{s}r", 10 * s + 1),
            toy_target(f"q{s}x", 10 * s + 2, shell=SHELL),
        )
        for s in range(2)
    )
    b = binding()
    plugin = pp.make_plugin(
        b, bank_legs("perfect", b), sets, lambda draw: (), pool_gates=False
    )
    policies = suite.Policies(
        optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
        honesty=HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={"f": 0.1, "g": 0.1},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )
    fields = {
        "oracle_tolerance": 1e-9,
        "k_grid": (0.0,),
        "monotone_tolerance": 0.05,
        "optimism_k": 30.0,
        "wrong_radius": 0.15,
        "wrong_k": 12.0,
        "leak_rounds": 1,
        "leak_step": 1.0,
        "ladder_decimals": 2,
        "koth_margin": 0.02,
        "near_optimum_radius": 0.15,
        "near_limit_u": 10.0,
        "bins": 5,
        "separation_target": 0.95,
        "seed": 7,
        "resamples": 10,
    }
    judged = suite.check_gaming_controls_lose(
        plugin,
        policies,
        suite.SuiteParams(in_distribution_is_pass_criterion=True, **fields),
    )
    numbers = judged["numbers"]["in_distribution_on_extended_targets"]
    assert set(numbers) == {"good_D", "in_distribution_D"}
    # The suite's in-distribution control clamps designs into the TRAIN box, so out of range it loses.
    assert judged["verdict"] == "PASS", judged
    assert numbers["in_distribution_D"] < numbers["good_D"]
    reported = suite.check_gaming_controls_lose(
        plugin,
        policies,
        suite.SuiteParams(in_distribution_is_pass_criterion=False, **fields),
    )
    assert reported["numbers"]["in_distribution_judged"] is False


class ToyGates:
    """A toy physics contract: the first raw output (f) must be positive."""

    gate_names = ("positive_f",)

    @staticmethod
    def failed(inputs_row, raw_row):
        return ("positive_f",) if raw_row[0] < 0 else ()


def raw_in_original_order(spec, raw_of=None):
    """The runner's raw rows in the ORIGINAL pool order: kept rows at their origin, excluded rows any filler."""
    raw_of = raw_of or (lambda d: truth({"x": d[0], "y": d[1]}))
    rows = [[0.0, 0.0] for _ in range(spec.pool_size)]
    for origin, design in zip(spec.origin, spec.designs, strict=True):
        rows[origin] = raw_of(design)
    return rows


def gated_binding(serve_good=good_serve):
    return pp.ChallengeBinding(
        **{**binding(serve_good).__dict__, "physics_gates": ToyGates()}
    )


def _raw_truths(spec, raw_of):
    """Raw rows in the ORIGINAL pool order, as the runner writes them, for a toy spec built without exclusion."""
    return [raw_of(d) for d in spec.designs]


def test_every_pool_answer_is_gated_and_a_violation_gives_names_only():
    from carbon.scoring import pool_gates

    specs = [toy_target("g1", 1), toy_target("g2", 2)]
    b = gated_binding()
    rows = pool_gates.pool_rows(b, specs)
    assert len(rows) == sum(
        len(s.designs) for s in specs
    ), "queryable and A_gen rows alike"
    ok = pool_gates.pool_gate_result(b, specs, {"kind": "good"})
    assert ok == {"status": "PASSED", "gates": []}

    def one_bad_row(rows_in):
        out = good_serve(rows_in)
        out[3] = [
            -1.0,
            out[3][1],
        ]  # a single violated answer anywhere breaks the whole submission
        return out

    broken = pool_gates.pool_gate_result(
        gated_binding(one_bad_row), specs, {"kind": "good"}
    )
    assert broken == {"status": "GATE_FAILED", "gates": ["positive_f"]}
    text = repr(broken)
    assert (
        "g1" not in text
        and "g2" not in text
        and "3" not in text.replace("GATE_FAILED", "")
    )
    with pytest.raises(pp.PluginRefused, match="no_physics_gates"):
        pool_gates.pool_gate_result(binding(), specs, {"kind": "good"})


def test_the_truths_must_pass_every_gate_on_every_pool_row_or_it_is_a_stop():
    from carbon.scoring import pool_gates
    from carbon.scoring.pool_grader import attach_raw

    spec = toy_target("t", 5)
    raw_ok = raw_in_original_order(spec)
    assert spec.pool_size == 100 and len(spec.origin) == len(spec.designs)
    attached = attach_raw(spec, raw_ok)
    assert pool_gates.check_truths_pass_gates(gated_binding(), [attached])[
        "rows"
    ] == len(spec.designs)
    # raw rows attach by ORIGIN: a pool whose exclusion dropped rows still lines up with the runner's order.
    assert attached.raw[0] == tuple(raw_ok[spec.origin[0]])
    assert attached.raw[0] == tuple(
        truth({"x": spec.designs[0][0], "y": spec.designs[0][1]})
    )
    with pytest.raises(pp.TruthCheckStop, match="needs_the_raw_truths"):
        pool_gates.check_truths_pass_gates(gated_binding(), [spec])
    bad = [list(r) for r in raw_ok]
    bad[spec.origin[7]] = [-0.5, 0.0]
    with pytest.raises(pp.TruthCheckStop, match="pool_truths_fail_gates"):
        pool_gates.check_truths_pass_gates(gated_binding(), [attach_raw(spec, bad)])
    with pytest.raises(pool_grader.PoolRefused, match="raw_rows_must_match"):
        attach_raw(spec, raw_ok[:-1])


def test_a_gate_failure_on_any_pool_answer_gives_the_model_no_score_in_the_suite_and_the_grid():
    from carbon.scoring import pool_proof_grid as grid
    from carbon.scoring.pool_grader import attach_raw

    def with_raw(spec):
        return attach_raw(spec, raw_in_original_order(spec))

    sets = tuple(
        (
            with_raw(toy_target(f"w{s}a", 10 * s + 1)),
            with_raw(toy_target(f"w{s}b", 10 * s + 2)),
        )
        for s in range(2)
    )

    def good_with_bad_row(rows_in):
        out = good_serve(rows_in)
        out[0] = [-1.0, out[0][1]]
        return out

    clean = gated_binding()
    plugin_clean = pp.make_plugin(
        clean, bank_legs("perfect", clean), sets, lambda draw: (), pool_gates=True
    )
    broken = gated_binding(good_with_bad_row)
    plugin_broken = pp.make_plugin(
        broken, bank_legs("perfect", broken), sets, lambda draw: (), pool_gates=True
    )
    policies = suite.Policies(
        optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
        honesty=HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={"f": 0.1, "g": 0.1},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )
    assert suite.version_total(plugin_clean, {"kind": "good"}, policies) > 0.0
    assert suite.version_total(plugin_broken, {"kind": "good"}, policies) == 0.0
    result = grid.run_grid(plugin_broken, _grid_spec())
    assert result["meta"]["pool_gates"] == "checked"
    # (other synthetic models, such as the large-noise optimist, may also break the toy gate: names only)
    assert all(
        r["pool_gate_failures"].get("good") == ["positive_f"] for r in result["rows"]
    )
    assert all(r["good"] == 0.0 for r in result["rows"])
    # No physics gates in the binding with pool gates required is refused at build time.
    with pytest.raises(pp.PluginRefused, match="no_physics_gates"):
        pp.make_plugin(
            binding(), bank_legs("perfect"), sets, lambda draw: (), pool_gates=True
        )
    assert (
        grid.run_grid(_grid_plugin(), _grid_spec())["meta"]["pool_gates"]
        == "not checked"
    )


def test_the_speed_gate_is_a_pass_fail_on_seconds_per_design_against_the_solver_over_the_factor():
    from carbon.scoring import pool_gates

    # 190 s per design (a recorded solver time) over 500 = 0.38 s per design.
    ok = pool_gates.speed_gate(
        300.0, 1000, solver_seconds_per_design=190.0, factor=500.0
    )
    assert ok["passed"] and ok["code"] is None
    assert ok["seconds_per_design"] == pytest.approx(0.3)
    assert ok["ceiling_seconds_per_design"] == pytest.approx(0.38)
    slow = pool_gates.speed_gate(
        500.0, 1000, solver_seconds_per_design=190.0, factor=500.0
    )
    assert not slow["passed"] and slow["code"] == "GATE_FAILED (speed)"
    edge = pool_gates.speed_gate(
        380.0, 1000, solver_seconds_per_design=190.0, factor=500.0
    )
    assert edge["passed"], "exactly at the ceiling passes"
    for bad in (
        {"measured_seconds": 0.0},
        {"measured_seconds": float("nan")},
        {"solver_seconds_per_design": -1.0},
        {"factor": 0.0},
        {"rows": 0},
    ):
        kwargs = {
            "measured_seconds": 1.0,
            "rows": 10,
            "solver_seconds_per_design": 190.0,
            "factor": 500.0,
            **bad,
        }
        with pytest.raises(pp.PluginRefused):
            pool_gates.speed_gate(
                kwargs["measured_seconds"],
                kwargs["rows"],
                solver_seconds_per_design=kwargs["solver_seconds_per_design"],
                factor=kwargs["factor"],
            )
    # In the plugin: a model that fails the speed gate scores nothing, one that passes scores as before.
    sets = ((toy_target("sp1", 1), toy_target("sp2", 2)),)
    b = binding()
    policies = suite.Policies(
        optimizer=OptimizerPolicy(budget=90, sigma0=0.3, population=None),
        honesty=HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={"f": 0.1, "g": 0.1},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )

    def plugin_with_speed(seconds):
        return pp.make_plugin(
            b,
            bank_legs("perfect", b),
            sets,
            lambda draw: (),
            pool_gates=False,
            speed={
                "measured": lambda descriptor: (
                    seconds if descriptor["kind"] == "good" else None
                ),
                "solver_seconds_per_design": 190.0,
                "factor": 500.0,
            },
        )

    assert suite.version_total(plugin_with_speed(1.0), {"kind": "good"}, policies) > 0.0
    assert (
        suite.version_total(plugin_with_speed(1e6), {"kind": "good"}, policies) == 0.0
    )
