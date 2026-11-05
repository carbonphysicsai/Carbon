"""The custody V_var report (`scripts/dev/pool_variant_report.py`): D per contender with and without the variants.

Claims: without a rule the report's base D is the grader's D bit for bit; the with-variants D is the grader's with the rule;
each slot reports its state and whether the shifted question's best design differs; the CLI reads the documented files and
refuses a policies file that already carries a rule. SYNTHETIC toy values only.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_pool_grader import HONESTY, OPTIMIZER, oracle, toy_target

from carbon.scoring.pool_grader import (
    attach_variants,
    dump_pool,
    grade_set,
    variant_slots,
)

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "dev" / "pool_variant_report.py"
)
RULE = {
    "kind": "limit_shift",
    "limits": ["g"],
    "shifts": [-0.99, -0.05, 0.05],
    "min_valid": 1,
    "aggregate": "mean",
}


def _module():
    spec = importlib.util.spec_from_file_location("pool_variant_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _setup():
    specs = [toy_target("t0"), toy_target("t1", seed=12, pool_seed=4)]
    starts = {
        s.target_id: [
            {"start": [0.5, 0.5], "seed": 300 + n}
            for n in range(len(variant_slots(RULE)))
        ]
        for s in specs
    }
    exact = oracle(specs)
    contenders = {
        "exact": {s.target_id: exact(s.conditions, list(s.designs)) for s in specs},
        "biased": {
            s.target_id: [
                {"f": r["f"], "g": r["g"] - 0.03}
                for r in exact(s.conditions, list(s.designs))
            ]
            for s in specs
        },
    }
    return specs, starts, contenders


def test_the_report_matches_the_grader_with_and_without_the_rule():
    specs, starts, contenders = _setup()
    out = _module().report(specs, RULE, starts, contenders, OPTIMIZER, HONESTY)
    attached = [attach_variants(s, RULE, starts[s.target_id]) for s in specs]
    for row in out["contenders"]:
        predict = _module()._predictor(specs, contenders[row["contender"]])
        assert row["d_base"] == grade_set(specs, predict, OPTIMIZER, HONESTY).d
        assert (
            row["d_with_variants"]
            == grade_set(
                attached, predict, replace(OPTIMIZER, variant_rule=RULE), HONESTY
            ).d
        )
        assert row["wall_seconds_with_variants"] > 0
    for target in out["targets"]:
        states = [slot["state"] for slot in target["slots"]]
        assert states.count("graded") == 2
        assert any(
            s.startswith("degenerate_reference") for s in states
        )  # the -0.99 slot
        assert all(
            type(slot["best_design_changed"]) is bool
            for slot in target["slots"]
            if slot["state"] == "graded"
        )
    assert out["custody_only"] is True


def test_the_cli_reads_the_files_and_refuses_a_rule_inside_the_policies(
    tmp_path, capsys
):
    specs, starts, contenders = _setup()
    policies = {
        "optimizer": {
            "budget": OPTIMIZER.budget,
            "sigma0": OPTIMIZER.sigma0,
            "population": OPTIMIZER.population,
        },
        "honesty": {"scale": HONESTY.scale, "reduction": HONESTY.reduction},
    }
    files = {
        "pool": [dump_pool(s) for s in specs],
        "policies": policies,
        "rule": RULE,
        "starts": starts,
        "a": contenders["exact"],
    }
    for name, value in files.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
    args = [
        "--pool", str(tmp_path / "pool.json"),
        "--policies", str(tmp_path / "policies.json"),
        "--rule", str(tmp_path / "rule.json"),
        "--starts", str(tmp_path / "starts.json"),
        "--contender", f"a={tmp_path / 'a.json'}",
    ]  # fmt: skip
    assert _module().main(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert [r["contender"] for r in printed["contenders"]] == ["a"]
    policies["optimizer"]["variant_rule"] = RULE
    (tmp_path / "policies.json").write_text(json.dumps(policies), encoding="utf-8")
    with pytest.raises(SystemExit):
        _module().main(args)
