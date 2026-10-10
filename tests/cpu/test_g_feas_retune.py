"""No Challenge references, hidden cases or solver work."""

import copy
import json

import pytest

from scripts.dev.battery import g_feas_retune as retune


def evaluate(panel):
    return retune.evaluate(panel, bootstrap_replicates=100, seed=11)


def test_public_synthetic_curves_are_deterministic_aggregates():
    panel = retune.synthetic_fixture()
    result = evaluate(panel)
    assert result == evaluate(panel)
    assert result["status"] == "DESCRIPTIVE_ONLY"
    assert [row["threshold"] for row in result["curves"]] == panel["thresholds"]
    assert all(row["scored_members"] == 10 for row in result["curves"])
    assert "members" not in result
    assert "regret_tail-attack" not in json.dumps(result)
    assert result["curves"][0]["accepted_mean_false_feasible_rate"] == 0
    assert result["curves"][0]["good_recipe_fail_rate_any_seed"] > 0
    assert result["curves"][-1]["good_recipe_fail_rate_any_seed"] == 0


def test_strict_exceeds_cutoff_and_good_recipe_any_seed():
    panel = retune.synthetic_fixture()
    panel["thresholds"] = [0.049, 0.05]
    panel["members"][0]["g_feas"] = 0.05
    assert panel["members"][0]["recipe"] in panel["good_recipes"]
    result = evaluate(panel)
    low, at = result["curves"]
    assert low["passing_members"] == at["passing_members"] - 1
    assert low["good_recipe_fail_rate_any_seed"] > at["good_recipe_fail_rate_any_seed"]


def test_unscored_reference_or_infrastructure_never_silently_dropped():
    panel = retune.synthetic_fixture()
    panel["members"][0].update(
        state="FAILED_INFRA", a=None, q3_regret=None, g_feas=None, decision_loss=None
    )
    result = evaluate(panel)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["states"] == {"FAILED_INFRA": 1, "SCORED": 9}
    assert result["curves"] == []


def test_no_hidden_scope_or_missing_digest_accepted():
    panel = retune.synthetic_fixture()
    panel["scope"] = "HIDDEN_EXAM"
    with pytest.raises(retune.RetuneError, match="closed public/development"):
        evaluate(panel)
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    panel["registry_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(retune.RetuneError, match="registered scoring rule"):
        evaluate(panel)


def test_grid_and_good_set_are_explicit_and_validated():
    panel = retune.synthetic_fixture()
    panel["thresholds"] = [0.05, 0.02]
    with pytest.raises(retune.RetuneError, match="strictly increasing"):
        evaluate(panel)
    panel["thresholds"] = [0.02, 0.05]
    panel["good_recipes"] = ["unregistered"]
    with pytest.raises(retune.RetuneError, match="good recipes"):
        evaluate(panel)


def test_demo_cli_writes_once(tmp_path):
    out = tmp_path / "retune.json"
    args = [
        "--public-synthetic-demo",
        "--bootstrap-replicates",
        "100",
        "--seed",
        "11",
        "--output",
        str(out),
    ]
    retune.main(args)
    assert json.loads(out.read_text(encoding="utf-8"))["scope"] == "SYNTHETIC_FIXTURE"
    with pytest.raises(FileExistsError):
        retune.main(args)


def test_report_has_no_member_or_recipe_identifiers_even_for_real_input():
    panel = copy.deepcopy(retune.synthetic_fixture())
    panel["scope"] = "DEVELOPMENT_SUMMARY_ONLY"
    panel["members"][0]["member"] = "sensitive-summary-identifier"
    result = evaluate(panel)
    assert "sensitive-summary-identifier" not in json.dumps(result)
