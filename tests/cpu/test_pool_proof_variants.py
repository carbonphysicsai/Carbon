"""The proof paths with a neighbour-task rule (V_var; Validator 4 Nov 21:40 (1): a MUST before the first pack that registers
a rule, Motor 1.7).

Claims: a plugin built with a version's rule and sealed variant starts carries the variants on every set and every fresh
(leak-attack) set; the suite grades a plugin only with a policy naming the SAME rule; the owner-sheet grid and the official
exam grade with the plugin's rule; without a rule every proof path is unchanged. SYNTHETIC toy values only.
"""

from __future__ import annotations

import dataclasses

import pytest
from test_pool_exam import POLICIES
from test_pool_plugin import _grid_spec, bank_legs, binding, toy_target

from carbon.scoring import pool_exam, pool_grader
from carbon.scoring import pool_plugin as pp
from carbon.scoring import pool_proof_grid as grid
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.pool_grader import PoolRefused, variant_slots

RULE = {
    "kind": "limit_shift",
    "limits": ["g"],
    "shifts": [-0.05, 0.05],
    "min_valid": 1,
    "aggregate": "mean",
}


def _sets():
    return tuple(
        tuple(toy_target(f"s{s}t{t}", 10 * s + t) for t in range(3)) for s in range(2)
    )


def _starts(sets):
    return {
        spec.target_id: [
            {"start": [0.5, 0.5], "seed": 500 + n}
            for n in range(len(variant_slots(RULE)))
        ]
        for group in sets
        for spec in group
    }


def _plugin(rule=RULE, starts="auto", fresh=None):
    sets = _sets()
    b = binding()
    return pp.make_plugin(
        b,
        bank_legs("perfect", b),
        sets,
        fresh or (lambda draw: ()),
        pool_gates=False,
        variant_rule=rule,
        variant_starts=_starts(sets) if starts == "auto" else starts,
    )


def _with_rule(policies=POLICIES, rule=RULE):
    return dataclasses.replace(
        policies, optimizer=dataclasses.replace(policies.optimizer, variant_rule=rule)
    )


def test_the_plugin_carries_the_variants_on_every_set_and_refuses_half_material():
    plugin = _plugin()
    assert plugin.variant_rule == RULE
    assert all(len(s.variants) == 2 for group in plugin.sets for s in group)
    with pytest.raises(pool_exam.ExamRefused, match="missing"):
        _plugin(starts=None)
    with pytest.raises(pool_exam.ExamRefused, match="without_a_variant_rule"):
        _plugin(rule=None)
    plain = _plugin(rule=None, starts=None)
    assert plain.variant_rule is None
    assert all(s.variants is None for group in plain.sets for s in group)


def test_a_fresh_set_gets_its_own_variants_derived_from_its_draw():
    plugin = _plugin(
        fresh=lambda draw: (toy_target("f0", 900 + draw), toy_target("f1", 950 + draw))
    )
    first, again, other = plugin.fresh_set(1), plugin.fresh_set(1), plugin.fresh_set(2)
    assert all(len(s.variants) == 2 for s in first)
    assert first == again  # deterministic per draw
    seeds = [v.seed for s in first for v in s.variants]
    assert len(set(seeds)) == len(seeds)
    assert seeds != [v.seed for s in other for v in s.variants]


def test_the_suite_grades_only_with_the_plugins_own_rule():
    plugin = _plugin()
    descriptor = {"kind": "good"}
    with pytest.raises(PoolRefused, match="variant_rules_differ"):
        suite.version_total(plugin, descriptor, POLICIES)
    with pytest.raises(PoolRefused, match="variant_rules_differ"):
        suite.extended_d(plugin, descriptor, POLICIES)
    with pytest.raises(PoolRefused, match="variant_rules_differ"):
        suite.version_total(_plugin(rule=None, starts=None), descriptor, _with_rule())
    total = suite.version_total(plugin, descriptor, _with_rule())
    assert 0.0 < total <= 1.0
    # with the rule, the graded D is the mean over base and variants (not the base alone)
    all_specs = [s for group in plugin.sets for s in group]
    _t, grade, _g, _l = suite.score_specs(
        plugin, plugin.sets[0], descriptor, _with_rule(), all_specs
    )
    assert all(t.base_d is not None and len(t.variants) == 2 for t in grade.targets)


def test_the_owner_sheet_grid_grades_with_the_plugins_rule():
    with_rule = grid.run_grid(_plugin(), _grid_spec())
    plain = grid.run_grid(_plugin(rule=None, starts=None), _grid_spec())
    assert with_rule["meta"]["rows"] == plain["meta"]["rows"]
    # same grid, different D question: the rows are graded, not refused, and not silently the base D
    assert [r["good"] for r in with_rule["rows"]] != [r["good"] for r in plain["rows"]]


def test_the_strictness_spec_carries_the_rule_into_its_policy():
    import importlib.util
    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "dev" / "pool_proof_grid.py"
    )
    spec = importlib.util.spec_from_file_location("pool_proof_grid_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    document = {
        "budget": 60,
        "sigma0": 0.3,
        "population": None,
        "honesty_scale": 5.0,
        "honesty_reduction": "max",
        "agen_scales": {"f": 0.1, "g": 0.1},
        "a_rule": {"kind": "min"},
        "c_rule": {"kind": "min"},
        "k_grid": [0.0, 2.0],
        "monotone_tolerance": 0.05,
        "seed": 7,
        "wrong_k": 12.0,
        "wrong_radius": 0.15,
        "variant_rule": RULE,
    }
    policies, _params = module.strictness_inputs(document)
    assert policies.optimizer.variant_rule == RULE
    assert pool_grader._valid_variant_rule(policies.optimizer.variant_rule)


def test_the_official_exam_grades_d_with_the_registered_rule():
    from test_pool_exam import ARGUMENTS, CEILING, FAST, exam_rows, toy_binding
    from test_pool_plugin import fake_measure, good_serve

    sets = _sets()
    rows = exam_rows(sets)
    outputs = good_serve([r["inputs"] for r in rows])

    def measure(policies, **material):
        return pool_exam.measure_pool(
            binding=toy_binding(),
            sets=sets,
            policies=policies,
            bank_rows=rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            base_measure=fake_measure,
            base_arguments=ARGUMENTS,
            speed_call_seconds=FAST,
            ceiling_seconds=CEILING,
            **material,
        )

    plain = measure(POLICIES)
    varied = measure(_with_rule(), variant_starts=_starts(sets))
    assert plain["A"] == varied["A"]
    assert varied["D"] != plain["D"]
    with pytest.raises(pool_exam.ExamRefused, match="missing"):
        measure(_with_rule())


def test_a_fresh_target_with_a_shortcut_zero_refuses_derived_variant_starts():
    from types import SimpleNamespace

    with_zero = SimpleNamespace(
        target_id="f0", start=(0.5, 0.5), zero={"kind": "engineer_shortcut"}
    )
    with pytest.raises(pp.PluginRefused, match="needs_its_own_variant_zeros"):
        pp.fresh_variant_starts(with_zero, RULE, 1)
    plain = SimpleNamespace(target_id="f0", start=(0.5, 0.5), zero=None)
    assert len(pp.fresh_variant_starts(plain, RULE, 1)) == len(variant_slots(RULE))
