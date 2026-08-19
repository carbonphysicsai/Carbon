"""Explicit classifications for the retained, scientifically unqualified PoC."""

from pathlib import Path

import pytest

_POC_TEST_DIR = Path(__file__).resolve().parent

_INTEGRATION_FILES = {
    "test_discrimination.py",
    "test_gold_optional.py",
    "test_multiseed_variance.py",
    "test_oracle_ci.py",
    "test_reproducibility.py",
    "test_strategy_discrimination.py",
    "test_train_quality.py",
}

_INTEGRATION_TESTS = {
    ("test_category_ablation.py", "test_full_suite_passes_coverage"),
    ("test_category_ablation.py", "test_ablation_reduces_coverage"),
    ("test_category_ablation.py", "test_category_payload_hashes_distinct"),
    ("test_full_loop.py", "test_full_loop_writes_card"),
    ("test_full_loop.py", "test_broken_strategy_gate_zeros"),
    ("test_handoff.py", "test_role_seeds_distinct_local"),
    ("test_handoff.py", "test_official_seeds_depend_on_block_hash"),
    ("test_handoff.py", "test_same_inputs_reproducible"),
    ("test_loop_wiring.py", "test_stages_talk_data_only"),
    ("test_null_and_labels.py", "test_labels_pass_on_fresh_batch"),
    ("test_seed_separation.py", "test_batch_hashes_differ"),
    ("test_seed_separation.py", "test_fixed_seed_reproducible"),
    ("test_stress_and_seeds.py", "test_stress_suite_full_coverage"),
    ("test_stress_and_seeds.py", "test_oracle_cross_check_runs"),
    ("test_stress_and_seeds.py", "test_eval_precision_tag_fp32"),
}

_JAX_TESTS = {
    (
        "test_discrimination.py",
        "test_physics_not_worse_than_data_when_both_learn",
    ),
    ("test_train_quality.py", "test_jax_emits_loss_curve_fields"),
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark PoC tests by actual prerequisite without changing their assertions."""
    for item in items:
        test_path = Path(item.path).resolve()
        if not test_path.is_relative_to(_POC_TEST_DIR):
            continue

        test_id = (test_path.name, item.name)
        item.add_marker(pytest.mark.poc)

        if test_path.name in _INTEGRATION_FILES or test_id in _INTEGRATION_TESTS:
            item.add_marker(pytest.mark.poc_integration)
        if test_id in _JAX_TESTS:
            item.add_marker(pytest.mark.backend_jax)
        if test_path.name == "test_gold_optional.py":
            item.add_marker(pytest.mark.gold)
