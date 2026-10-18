"""The public rule describes actual v3 grading, without private bank material."""

import json
from copy import deepcopy

import pytest
from test_score_lab_solver_benchmark_acceptance import _toy_workload

from carbon.scoring import benchmark_evidence as bench
from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import (
    BenchmarkScoreRefused,
    public_rule_definition,
    register_pack,
)


def _repack(pack, **changes):
    return register_pack(
        {**{k: v for k, v in pack.items() if k != "pack_digest"}, **changes}
    )


def test_public_definition_matches_shared_rule_and_keeps_unapplied_legs_explicit():
    registration, references, models, pack = _toy_workload()
    before = deepcopy((registration, pack))
    view = ScoreEngine.public_solver_benchmark_rule_v3(registration, pack)
    assert view == public_rule_definition(registration, pack)
    assert view["status"] == "DEVELOPMENT_RULE"
    assert view["output"] == registration["output"]
    assert view["hard_gates"] == {
        "ids": pack["hard_gates"],
        "requirement": "ALL_PASS_ON_ALL_P_QUERIES",
        "predicate_authority": "CHALLENGE_MEASUREMENT_IMPLEMENTATION",
    }
    assert view["population"] == {"scored_role": "P", "Q": "DIAGNOSTIC_ONLY"}
    assert view["accuracy_definition"] == {
        "metric": "mean_absolute_error",
        "per_query_reduction": "MEAN_ABSOLUTE_ERROR_OVER_ALL_OUTPUT_ELEMENTS",
        "population_reduction": "REGISTERED_WEIGHTED_MEAN_OVER_P_QUERIES",
        "ceiling": 3.0,
        "ceiling_comparison": "LESS_THAN_OR_EQUAL",
        "mandatory": True,
    }
    assert view["important_limit_definition"] == {"status": "NOT_APPLIED"}
    assert view["design_objective"] == {"status": "NOT_APPLIED"}
    result = bench.compare(registration, references, models, score_pack=pack)
    # One output per toy query: errors 1, 2; registered P weights 1, 3.
    assert result["models"][0]["by_role"]["P"]["mean_absolute_error"] == 1.75
    assert result["models"][0]["by_role"]["P"]["paired_speedup"] == 20.0 / 5.0
    assert view["performance"]["model_query_phases"] == [
        "preprocess", "export", "inference", "postprocess"
    ]
    assert view["performance"]["build_cost_in_score"] is False
    assert result["scoring"]["models"][2]["status"] == "SCIENTIFIC_INADMISSIBLE"
    assert (registration, pack) == before


def test_ceiling_equality_and_missing_value_match_actual_scorer():
    registration, references, models, pack = _toy_workload()
    pack = _repack(pack, accuracy_ceiling=1.75)
    view = public_rule_definition(registration, pack)
    result = bench.compare(registration, references, models, score_pack=pack)
    assert view["accuracy_definition"]["ceiling"] == 1.75
    assert result["scoring"]["models"][0]["status"] == "SCORED_DEVELOPMENT"
    assert result["scoring"]["models"][1]["status"] == "ACCURACY_INELIGIBLE"
    pending = _repack(pack, accuracy_ceiling=None)
    assert public_rule_definition(registration, pending)["status"] == "PACK_NOT_READY"
    assert bench.compare(registration, references, models, score_pack=pending)[
        "scoring"
    ]["status"] == "PACK_NOT_READY"


def test_projection_omits_private_material_even_when_same_rule_has_a_new_bank():
    registration, _, _, pack = _toy_workload()
    original = public_rule_definition(registration, pack)
    body = {k: v for k, v in deepcopy(registration).items() if k != "registration_digest"}
    body["cases"] = [{"id": "private-draw-sentinel", "role": "P", "weight": 71}]
    body["job_digest"] = "private-job-sentinel"
    body["train_digest"] = "private-train-sentinel"
    body["timing_profile"]["model_device"] = "private-host-sentinel"
    changed = bench.register(body)
    changed_pack = _repack(pack, benchmark_registration_digest=changed["registration_digest"])
    projected = public_rule_definition(changed, changed_pack)
    assert projected == original
    encoded = json.dumps(projected)
    for private_value in (
        "private-", registration["registration_digest"], pack["pack_digest"],
        pack["physics_contract"]["definition_digest"],
    ):
        assert private_value not in encoded
    assert set(projected) == {
        "schema", "score_schema", "scope", "challenge", "status", "output",
        "population", "hard_gates", "accuracy_definition", "performance",
        "incomplete_reference_evidence", "important_limit_definition", "design_objective",
    }
    projected["hard_gates"]["ids"].append("not-an-input-mutation")
    assert pack["hard_gates"] == ["synthetic_physics"]


def test_complete_batch_contract_is_public_but_host_profiles_are_not():
    registration, _, _, pack = _toy_workload()
    body = {k: v for k, v in registration.items() if k != "registration_digest"}
    body["schema"] = bench.SCHEMA_V3
    body["output"] = {**body["output"], "size": 2, "shape": [2, 1]}
    body["reference"] = {**body["reference"], "evidence_kind": bench.ENGINEERING_REFERENCE}
    body["timing_profile"] = {
        **body["timing_profile"], "batch_size": 2,
        "query_unit": "complete_batch", "input_shape": [2, 3],
    }
    registration = bench.register(body)
    pack = _repack(pack, benchmark_registration_digest=registration["registration_digest"])
    view = public_rule_definition(registration, pack)
    assert view["output"]["shape"] == [2, 1]
    assert view["performance"]["query_unit"] == "complete_batch"
    assert view["performance"]["batch_size"] == 2
    assert "model_device" not in view["performance"]
    assert "solver_device" not in view["performance"]


@pytest.mark.parametrize("field", ["scope", "challenge", "output", "physics_contract", "hard_gates"])
def test_registered_but_mismatched_pack_cannot_describe_another_rule(field):
    registration, _, _, pack = _toy_workload()
    replacements = {
        "scope": "PUBLIC_DEVELOPMENT", "challenge": "other-challenge",
        "output": {**pack["output"], "unit": "other-unit"},
        "physics_contract": {**pack["physics_contract"], "definition_digest": "sha256:" + "f" * 64},
        "hard_gates": ["other-gate"],
    }
    mismatched = _repack(pack, **{field: replacements[field]})
    with pytest.raises(BenchmarkScoreRefused, match="benchmark_binding"):
        public_rule_definition(registration, mismatched)


def test_mutated_or_unknown_rule_inputs_refuse_instead_of_becoming_public():
    registration, _, _, pack = _toy_workload()
    with pytest.raises(BenchmarkScoreRefused, match="pack_digest"):
        public_rule_definition(registration, {**pack, "accuracy_ceiling": 99})
    with pytest.raises(BenchmarkScoreRefused, match="registration_digest"):
        public_rule_definition({**registration, "job_digest": "changed"}, pack)
    with pytest.raises(bench.BenchmarkRefused, match="registration_shape"):
        public_rule_definition({**registration, "private_secret": "drop-me"}, pack)
