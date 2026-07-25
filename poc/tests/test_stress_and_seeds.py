"""Tests for stress categories, SPEC seed map, oracle, fp32 path."""

from carbon.common.seeds import (
    build_seed_bundle,
    derive_master_seed,
    derive_pipeline_seeds,
    SEED_MAP_VERSION,
)
from poc.generators.stress_categories import (
    generate_stress_suite,
    coverage_ok,
    CATEGORIES,
    COVERAGE_THRESHOLD,
)
from poc.generators.justification import justification_table
from poc.eval.oracle_check import cross_check_generator
from poc.eval.metrics import evaluate
from poc.models.fno1d import FNO1dConfig, init_params
from poc.generators.burgers1d import generate_batch


def test_stress_suite_full_coverage():
    suite = generate_stress_suite(12345, fast=True)
    ok, msg = coverage_ok(suite)
    assert ok, msg
    assert suite.coverage >= COVERAGE_THRESHOLD
    assert set(suite.categories_present) == set(CATEGORIES.keys())


def test_category_weights_sum_to_one():
    s = sum(c["weight"] for c in CATEGORIES.values())
    assert abs(s - 1.0) < 1e-9


def test_pipeline_seeds_distinct():
    master = derive_master_seed("burgers1d_v0", "0xabc", 0)
    pipe = derive_pipeline_seeds(master)
    keys = ["data_seed", "stress_seed", "init_seed", "dropout_seed", "shuffle_seed", "eval_seed"]
    vals = [pipe[k] for k in keys]
    assert len(set(vals)) == len(vals)
    assert pipe["data_seed"] != pipe["stress_seed"]
    assert pipe["eval_seed"] != pipe["stress_seed"]


def test_official_bundle_has_master():
    b = build_seed_bundle("burgers1d_v0", "0xdead", 7, local_mode=False)
    assert b["mode"] == "official"
    assert "master_seed" in b
    assert b["_seed_map_version"] == SEED_MAP_VERSION


def test_block_hash_changes_stress():
    a = build_seed_bundle("burgers1d_v0", "0x1", 0, local_mode=False)
    b = build_seed_bundle("burgers1d_v0", "0x2", 0, local_mode=False)
    assert a["stress_seed"] != b["stress_seed"]


def test_justification_table_nonempty():
    t = justification_table()
    assert len(t["parameters"]) >= 5
    assert t["physics"] == "burgers1d"


def test_oracle_cross_check_runs():
    result = cross_check_generator(n_samples=4, seed_nonce=1, fast=True)
    assert "passed" in result
    assert "mean_rel" in result
    # Should be tight vs refined same integrator
    assert result["mean_rel"] < 0.2


def test_eval_precision_tag_fp32():
    batch = generate_batch("eval", 3, "fp", fast=True)
    params = init_params(FNO1dConfig(modes=4, width=8, layers=1), seed=0)
    m = evaluate(params, FNO1dConfig(modes=4, width=8, layers=1), batch)
    assert m.get("precision") == "fp32"
