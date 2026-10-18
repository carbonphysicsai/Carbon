"""Synthetic candidate-rule tests; no Challenge policy or physical references."""

from copy import deepcopy
import math

import pytest

from carbon.scoring import dual_score as dual
from carbon.scoring.engine import ScoreEngine


def fixture():
    def component(metric):
        return {
            "metric": metric,
            "unit": "1",
            "transform": "unit_benefit",
            "scale": None,
            "weight": 1.0,
        }

    body = {
        "schema": dual.PACK_SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "challenge": "toy-dual-only",
        "physics_contract_digest": "sha256:" + "1" * 64,
        "measurement_contract_digest": "sha256:" + "2" * 64,
        "hard_gates": ["toy_physics", "toy_required_accuracy"],
        "legs": {
            name: {"components": [component(name)], "minimum": None}
            for name in ("A", "D")
        },
        "value_weight": 0.8,
        "combination": "weighted_arithmetic_mean",
        "decision_policy": {
            name: {"eligible": True, "maximum_D": 1.0}
            for name in ("VERIFIED_FEASIBLE", "MISSED_OPPORTUNITY", "NONE_FEASIBLE")
        },
    }
    benchmark = {
        "schema": dual.INPUT_SCHEMA,
        **{
            k: body[k]
            for k in (
                "scope",
                "challenge",
                "physics_contract_digest",
                "measurement_contract_digest",
            )
        },
        "population_role": "P",
        "common_mask_digest": "sha256:" + "3" * 64,
        "models": [
            {
                "artifact_digest": "sha256:" + "4" * 64,
                "gates": {name: "PASS" for name in body["hard_gates"]},
                "measurements": {
                    name: {"status": "RESOLVED", "value": value, "unit": "1"}
                    for name, value in (("A", 0.1), ("D", 1.0))
                },
                "decision_outcome": "VERIFIED_FEASIBLE",
            }
        ],
    }
    return body, benchmark


def row(body, benchmark):
    return ScoreEngine.score_dual_benchmark_v4(benchmark, dual.register_pack(body))[
        "models"
    ][0]


def test_core_entry_point_parity_visible_legs_and_explicit_formula():
    body, benchmark = fixture()
    pack = dual.register_pack(body)
    result = ScoreEngine.score_dual_benchmark_v4(benchmark, pack)
    assert result == dual.score(benchmark, pack)
    assert result["official_score"] is False
    assert result["models"][0]["legs"] == {"A": 0.1, "D": 1.0}
    assert result["models"][0]["score"] == pytest.approx(0.82)
    body["combination"] = "bottleneck_capped_geometric"
    assert row(body, benchmark)["score"] == pytest.approx(0.1 * 0.1**0.2)
    assert row(body, benchmark)["score"] <= 0.1


@pytest.mark.parametrize(
    "combination", ["weighted_arithmetic_mean", "bottleneck_capped_geometric"]
)
def test_monotonic_in_either_leg_and_capped_candidate_never_exceeds_weaker(combination):
    body, benchmark = fixture()
    body["combination"] = combination
    for a in (0.0, 0.1, 0.5, 1.0):
        for d in (0.0, 0.1, 0.5, 1.0):
            benchmark["models"][0]["measurements"]["A"]["value"] = a
            benchmark["models"][0]["measurements"]["D"]["value"] = d
            before = row(body, benchmark)["score"]
            if combination == "bottleneck_capped_geometric":
                assert 0 <= before <= min(a, d)
            for leg in ("A", "D"):
                changed = deepcopy(benchmark)
                changed["models"][0]["measurements"][leg]["value"] = 1.0
                assert row(body, changed)["score"] >= before


@pytest.mark.parametrize("gate", ["toy_physics", "toy_required_accuracy"])
def test_mandatory_gate_failure_not_compensated(gate):
    body, benchmark = fixture()
    benchmark["models"][0]["gates"][gate] = "FAIL"
    result = row(body, benchmark)
    assert result["status"] == "MANDATORY_GATE_FAILED"
    assert result["score"] is None


def test_registered_minimum_applied_before_combination():
    body, benchmark = fixture()
    body["legs"]["A"]["minimum"] = 0.2
    result = row(body, benchmark)
    assert result["status"] == "REQUIRED_LEG_MINIMUM_FAILED"
    assert result["score"] is None
    benchmark["models"][0]["measurements"]["A"]["value"] = 0.2
    assert row(body, benchmark)["status"] == "SCORED_DEVELOPMENT_CANDIDATE"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("REFERENCE_UNRESOLVED", "INDETERMINATE_EVIDENCE"),
        ("REFERENCE_INFRA", "FAILED_INFRA"),
    ],
)
def test_reference_gap_defers_every_compared_model_not_candidate_loss(status, expected):
    body, benchmark = fixture()
    other = deepcopy(benchmark["models"][0])
    other["artifact_digest"] = "sha256:" + "5" * 64
    other["measurements"]["D"].update(status=status, value=None)
    benchmark["models"].append(other)
    result = ScoreEngine.score_dual_benchmark_v4(benchmark, dual.register_pack(body))
    assert [r["status"] for r in result["models"]] == [expected, expected]
    assert all(r["score"] is None for r in result["models"])
    assert len(result["models"]) == 2


@pytest.mark.parametrize(
    "status,expected",
    [("CANDIDATE_INVALID", "CANDIDATE_INVALID"), ("CANDIDATE_INFRA", "FAILED_INFRA")],
)
def test_candidate_failure_is_local_and_typed(status, expected):
    body, benchmark = fixture()
    other = deepcopy(benchmark["models"][0])
    other["artifact_digest"] = "sha256:" + "5" * 64
    other["measurements"]["A"].update(status=status, value=None)
    benchmark["models"].append(other)
    result = ScoreEngine.score_dual_benchmark_v4(benchmark, dual.register_pack(body))
    assert result["models"][0]["score"] is not None
    assert result["models"][1]["status"] == expected
    assert result["models"][1]["score"] is None


def test_missing_robustness_component_is_not_zero_filled_or_dropped():
    body, benchmark = fixture()
    body["legs"]["A"]["components"][0]["metric"] = "robustness"
    benchmark["models"][0]["measurements"].pop("A")
    with pytest.raises(dual.DualScoreRefused, match="model_measurements"):
        row(body, benchmark)
    benchmark["models"][0]["measurements"]["robustness"] = {
        "status": "NOT_MEASURED",
        "value": None,
        "unit": "1",
    }
    assert row(body, benchmark)["score"] is None
    assert row(body, benchmark)["legs"]["A"] is None


def test_unmeasured_decision_is_not_a_reference_failure_or_fabricated_d():
    body, benchmark = fixture()
    benchmark["models"][0]["decision_outcome"] = "NOT_MEASURED"
    result = row(body, benchmark)
    assert result["status"] == "INDETERMINATE_EVIDENCE"
    assert result["legs"]["D"] is None
    assert result["score"] is None


def test_q_never_contributes_population_total():
    body, benchmark = fixture()
    benchmark["population_role"] = "Q"
    result = row(body, benchmark)
    assert result["status"] == "DIAGNOSTIC_Q"
    assert result["legs"] == {"A": 0.1, "D": 1.0}
    assert result["score"] is None


@pytest.mark.parametrize("outcome", ["NONE_FEASIBLE", "MISSED_OPPORTUNITY"])
def test_decision_states_retained_without_inventing_reward(outcome):
    body, benchmark = fixture()
    benchmark["models"][0]["decision_outcome"] = outcome
    benchmark["models"][0]["measurements"]["D"]["value"] = 0.3
    result = row(body, benchmark)
    assert result["decision_outcome"] == outcome
    assert result["legs"]["D"] == 0.3


def test_registered_outcome_policy_caps_missed_opportunity_without_hiding_raw_d():
    body, benchmark = fixture()
    body["decision_policy"]["MISSED_OPPORTUNITY"]["maximum_D"] = 0.0
    benchmark["models"][0]["decision_outcome"] = "MISSED_OPPORTUNITY"
    result = row(body, benchmark)
    assert result["legs"]["D"] == 0.0
    assert result["measured_legs_before_outcome_policy"]["D"] == 1.0
    body["decision_policy"]["MISSED_OPPORTUNITY"]["eligible"] = False
    assert row(body, benchmark)["status"] == "DECISION_OUTCOME_INELIGIBLE"
    assert row(body, benchmark)["score"] is None


@pytest.mark.parametrize("value", [0.0, 1.0, 1e308])
def test_explicit_reciprocal_normalization_is_stable(value):
    body, benchmark = fixture()
    body["legs"]["A"]["components"][0].update(transform="reciprocal_loss", scale=1e-308)
    benchmark["models"][0]["measurements"]["A"]["value"] = value
    result = row(body, benchmark)
    assert math.isfinite(result["legs"]["A"])
    assert 0 <= result["legs"]["A"] <= 1


def test_units_pack_digest_and_contract_are_bound():
    body, benchmark = fixture()
    pack = dual.register_pack(body)
    pack["value_weight"] = 0.5
    with pytest.raises(dual.DualScoreRefused, match="pack_digest"):
        dual.score(benchmark, pack)
    benchmark["models"][0]["measurements"]["A"]["unit"] = "K"
    with pytest.raises(dual.DualScoreRefused, match="measurement_contract"):
        row(body, benchmark)
    benchmark["models"][0]["measurements"]["A"]["unit"] = "1"
    benchmark["measurement_contract_digest"] = "sha256:" + "9" * 64
    with pytest.raises(dual.DualScoreRefused, match="benchmark_binding"):
        row(body, benchmark)


@pytest.mark.parametrize("weight", [0, 1])
def test_endpoints_only_arithmetic_diagnostic_not_joint(weight):
    body, benchmark = fixture()
    body["value_weight"] = weight
    assert row(body, benchmark)["score"] in (0.1, 1.0)
    body["combination"] = "bottleneck_capped_geometric"
    with pytest.raises(dual.DualScoreRefused, match="joint_weight_requires_both_legs"):
        row(body, benchmark)


def test_out_of_range_resolved_benefit_is_candidate_invalid():
    body, benchmark = fixture()
    benchmark["models"][0]["measurements"]["A"]["value"] = 1.01
    assert row(body, benchmark)["status"] == "CANDIDATE_INVALID"


def test_registration_detaches_nested_caller_data():
    body, _ = fixture()
    pack = dual.register_pack(body)
    body["legs"]["A"]["components"][0]["weight"] = 0.5
    assert pack["legs"]["A"]["components"][0]["weight"] == 1


@pytest.mark.parametrize("field", ["scope", "population_role", "decision_outcome"])
def test_malformed_container_values_are_typed_refusals(field):
    body, benchmark = fixture()
    if field == "scope":
        body[field] = []
    elif field == "population_role":
        benchmark[field] = []
    else:
        benchmark["models"][0][field] = []
    with pytest.raises(dual.DualScoreRefused):
        row(body, benchmark)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), [1, 2]])
def test_invalid_candidate_value_does_not_erase_peers(value):
    body, benchmark = fixture()
    other = deepcopy(benchmark["models"][0])
    other["artifact_digest"] = "sha256:" + "5" * 64
    other["measurements"]["A"]["value"] = value
    benchmark["models"].append(other)
    result = dual.score(benchmark, dual.register_pack(body))
    assert result["models"][0]["score"] is not None
    assert result["models"][1]["status"] == "CANDIDATE_INVALID"
    assert result["models"][1]["score"] is None
    assert result["evidence_digest"].startswith("sha256:")


def test_deep_malformed_candidate_value_is_typed_without_recursive_hashing():
    body, benchmark = fixture()
    value = []
    for _ in range(1500):
        value = [value]
    benchmark["models"][0]["measurements"]["A"]["value"] = value
    assert row(body, benchmark)["status"] == "CANDIDATE_INVALID"
