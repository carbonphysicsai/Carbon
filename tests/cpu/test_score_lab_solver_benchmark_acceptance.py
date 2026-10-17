"""One synthetic acceptance workload for ScoreLab's model-versus-solver seam.

Numbers here are toy engineering fixtures, not battery physics, solver runs,
production tolerances, or a qualified Challenge.
"""

from copy import deepcopy

import pytest

from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import (
    BenchmarkScoreRefused,
    register_pack,
)
from scripts.dev.score_lab import solver_benchmark as bench

TOY_PHYSICS = {
    "version": "synthetic-charge-v1",
    "definition": {
        "scope": "synthetic-charge-time",
        "governing_relation": "toy minutes",
        "assumptions": ["synthetic only"],
        "initial_conditions": {"charge": 0},
        "boundary_conditions": {"charge": 1},
        "constraints": {"duration": "nonnegative"},
        "output_units": {"charging_minutes": "min"},
        "reference_applicability": "toy-applicability",
        "acceptance_rules": {"synthetic_physics": "toy boolean fixture"},
    },
}
TOY_PHYSICS_ID = bench.physics_contract_identity(TOY_PHYSICS)


def _toy_workload():
    registration = bench.register(
        {
            "schema": bench.SCHEMA,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "synthetic-charge-time",
            "job_digest": "sha256:synthetic-job",
            "train_digest": "sha256:fixed-synthetic-train",
            "physics_contract": TOY_PHYSICS,
            "output": {
                "quantity": "charging_minutes",
                "unit": "min",
                "size": 1,
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": "sha256:toy-solver",
                "fidelity_digest": "sha256:toy-fidelity",
                "applicability_digest": "sha256:toy-applicability",
            },
            "cases": [
                {"id": "p-cool", "role": "P", "weight": 1},
                {"id": "p-warm", "role": "P", "weight": 3},
                {"id": "q-stress", "role": "Q", "weight": 9},
            ],
            "mandatory_gates": ["synthetic_physics"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "fixture-device",
                "solver_device": "fixture-device",
                "batch_size": 1,
            },
        }
    )
    references = [
        {
            "id": cid,
            "status": "RESOLVED",
            "outputs": [answer],
            "elapsed_s": seconds,
            "source": "MEASURED_SOLVER_RUN",
            "solver_digest": "sha256:toy-solver",
            "fidelity_digest": "sha256:toy-fidelity",
            "applicability_digest": "sha256:toy-applicability",
            "physics_contract_digest": TOY_PHYSICS_ID["definition_digest"],
            "peak_memory_bytes": 2048,
        }
        for cid, answer, seconds in (
            ("p-cool", 10.0, 8.0),
            ("p-warm", 20.0, 12.0),
            ("q-stress", 30.0, 15.0),
        )
    ]

    def model(name, predictions, seconds, *, unsafe_case=None):
        return {
            "artifact_digest": f"sha256:{name}",
            "job_digest": "sha256:synthetic-job",
            "train_digest": "sha256:fixed-synthetic-train",
            "physics_contract_digest": TOY_PHYSICS_ID["definition_digest"],
            "build_seconds": 60.0,
            "cases": [
                {
                    "id": cid,
                    "status": "OK",
                    "source": "MEASURED_INFERENCE_RUN",
                    "outputs": [prediction],
                    "gates": {"synthetic_physics": cid != unsafe_case},
                    "timing_s": {
                        "preprocess": 0.1,
                        "export": 0.1,
                        "inference": elapsed - 0.3,
                        "postprocess": 0.1,
                    },
                    "peak_memory_bytes": 128,
                }
                for (cid, prediction), elapsed in zip(
                    zip(
                        ("p-cool", "p-warm", "q-stress"),
                        predictions,
                        strict=True,
                    ),
                    seconds,
                    strict=True,
                )
            ],
        }

    models = [
        model("accurate-slower", (11.0, 18.0, 35.0), (2.0, 3.0, 2.0)),
        model("less-accurate-faster", (12.0, 23.0, 30.0), (1.0, 1.0, 1.0)),
        model(
            "unsafe-fastest",
            (10.0, 20.0, 30.0),
            (0.5, 0.5, 0.5),
            unsafe_case="p-warm",
        ),
    ]
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v3",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "synthetic-charge-time",
            "benchmark_registration_digest": registration["registration_digest"],
            "physics_contract": TOY_PHYSICS_ID,
            "output": {
                "quantity": "charging_minutes",
                "unit": "min",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["synthetic_physics"],
            "accuracy_ceiling": 3.0,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    return registration, references, models, pack


def test_complete_synthetic_workload_accuracy_gates_speed_and_engine_parity():
    registration, references, models, pack = _toy_workload()
    workbench = bench.compare(registration, references, models, score_pack=pack)
    direct = ScoreEngine.score_solver_benchmark_v3(
        bench.compare(registration, references, models), pack
    )
    assert workbench["scoring"] == direct
    assert workbench["ranking"] is None  # Only the registered v2 pack may rank.
    assert workbench["output"] == {
        "quantity": "charging_minutes",
        "unit": "min",
        "metric": "mean_absolute_error",
    }
    accurate, fast, unsafe = workbench["models"]
    accurate_p, fast_p, unsafe_p = (
        member["by_role"]["P"] for member in (accurate, fast, unsafe)
    )
    assert (accurate_p["attempted"], accurate_p["counts"]["resolved"]) == (2, 2)
    assert accurate_p["mean_absolute_error"] == pytest.approx(1.75)
    assert accurate["by_role"]["Q"]["mean_absolute_error"] == pytest.approx(5.0)
    assert fast_p["mean_absolute_error"] == pytest.approx(2.75)
    assert fast["by_role"]["Q"]["mean_absolute_error"] == pytest.approx(0.0)
    assert accurate_p["solver_seconds"] == fast_p["solver_seconds"] == 20.0
    assert accurate_p["model_seconds"] == pytest.approx(5.0)
    assert fast_p["model_seconds"] == pytest.approx(2.0)
    assert (accurate_p["paired_speedup"], fast_p["paired_speedup"]) == (4.0, 10.0)
    assert unsafe_p["paired_speedup"] == 20.0  # Measured, never rewarded.
    assert unsafe_p["status"] == "SCIENTIFIC_INADMISSIBLE"
    assert unsafe_p["gate_failures"] == {"synthetic_physics": 1}
    assert unsafe["pareto_p"] is None
    assert direct["ranking"] == [
        "sha256:less-accurate-faster",
        "sha256:accurate-slower",
    ]
    assert [row["status"] for row in direct["models"]] == [
        "SCORED_DEVELOPMENT",
        "SCORED_DEVELOPMENT",
        "SCIENTIFIC_INADMISSIBLE",
    ]
    assert all(member["build_seconds"] == 60.0 for member in workbench["models"])


def test_one_unresolved_reference_withholds_common_p_comparison():
    registration, references, models, pack = _toy_workload()
    references[1] = {"id": "p-warm", "status": "UNRESOLVED"}
    result = bench.compare(registration, references, models, score_pack=pack)
    for member in result["models"]:
        p = member["by_role"]["P"]
        assert p["attempted"] == 2
        assert p["counts"]["reference_unresolved"] == 1
        assert p["mean_absolute_error"] is None
        assert p["paired_speedup"] is None
        assert p["status"] == "INDETERMINATE_EVIDENCE"
    assert result["scoring"]["ranking"] == []
    assert {row["status"] for row in result["scoring"]["models"]} == {
        "INDETERMINATE_EVIDENCE"
    }
    assert result["models"][0]["by_role"]["Q"]["status"] == "MEASURED_DEVELOPMENT"


def test_synthetic_acceptance_requires_exact_source_and_identity_bindings():
    registration, references, models, pack = _toy_workload()
    cached = deepcopy(references)
    cached[0]["source"] = "CACHED_REFERENCE_LOOKUP"
    with pytest.raises(bench.BenchmarkRefused, match="solver_measurement_required"):
        bench.compare(registration, cached, models)
    wrong_fidelity = deepcopy(references)
    wrong_fidelity[0]["fidelity_digest"] = "sha256:other-fidelity"
    with pytest.raises(bench.BenchmarkRefused, match="solver_measurement_required"):
        bench.compare(registration, wrong_fidelity, models)
    wrong_train = deepcopy(models)
    wrong_train[0]["train_digest"] = "sha256:other-train"
    with pytest.raises(bench.BenchmarkRefused, match="model_train_identity"):
        bench.compare(registration, references, wrong_train)
    changed_pack = deepcopy(pack)
    changed_pack["benchmark_registration_digest"] = "sha256:other-job"
    with pytest.raises(BenchmarkScoreRefused, match="pack_digest"):
        ScoreEngine.score_solver_benchmark_v3(
            bench.compare(registration, references, models), changed_pack
        )


def test_same_gate_names_cannot_reuse_evidence_under_different_physics():
    registration, references, models, old_pack = _toy_workload()
    changed = deepcopy(registration)
    changed.pop("registration_digest")
    changed["physics_contract"]["definition"][
        "governing_relation"
    ] = "different toy relation"
    updated = bench.register(changed)
    updated_id = bench.physics_contract_identity(updated["physics_contract"])
    assert updated["mandatory_gates"] == registration["mandatory_gates"]
    assert updated_id != old_pack["physics_contract"]
    with pytest.raises(bench.BenchmarkRefused, match="solver_measurement_required"):
        bench.compare(updated, references, models)
    for row in references:
        row["physics_contract_digest"] = updated_id["definition_digest"]
    with pytest.raises(bench.BenchmarkRefused, match="model_physics_contract_identity"):
        bench.compare(updated, references, models)
    for row in models:
        row["physics_contract_digest"] = updated_id["definition_digest"]
    new_result = bench.compare(updated, references, models)
    with pytest.raises(BenchmarkScoreRefused, match="benchmark_binding"):
        ScoreEngine.score_solver_benchmark_v3(new_result, old_pack)
    stale_physics = deepcopy(old_pack)
    stale_physics.pop("pack_digest")
    stale_physics["benchmark_registration_digest"] = updated["registration_digest"]
    stale_physics = register_pack(stale_physics)
    with pytest.raises(BenchmarkScoreRefused, match="benchmark_binding"):
        ScoreEngine.score_solver_benchmark_v3(new_result, stale_physics)


def test_missing_physics_contract_is_unready_not_a_candidate_failure():
    registration, references, models, _ = _toy_workload()
    missing = deepcopy(registration)
    missing.pop("registration_digest")
    missing.pop("physics_contract")
    with pytest.raises(bench.BenchmarkRefused, match="registration_shape"):
        bench.register(missing)
    missing["physics_contract"] = {"version": "toy", "definition": {}}
    with pytest.raises(bench.BenchmarkRefused, match="physics_contract_missing"):
        bench.register(missing)
    unresolved = deepcopy(references)
    unresolved[0] = {"id": "p-cool", "status": "UNRESOLVED"}
    result = bench.compare(registration, unresolved, models[:2])
    assert all(
        row["by_role"]["P"]["status"] == "INDETERMINATE_EVIDENCE"
        for row in result["models"]
    )
    assert all(
        row["by_role"]["P"]["counts"]["scientific_inadmissible"] == 0
        for row in result["models"]
    )


def test_earlier_development_wire_versions_are_not_reinterpreted():
    registration, references, models, pack = _toy_workload()
    old_registration = deepcopy(registration)
    old_registration.pop("registration_digest")
    old_registration["schema"] = "carbon.score-lab.solver-benchmark.v1"
    with pytest.raises(bench.BenchmarkRefused, match="registration_scope"):
        bench.register(old_registration)
    old_pack = deepcopy(pack)
    old_pack.pop("pack_digest")
    old_pack["schema"] = "carbon.scoring.solver-benchmark-pack.v2"
    with pytest.raises(BenchmarkScoreRefused, match="pack_identity"):
        register_pack(old_pack)
    old_result = bench.compare(registration, references, models)
    old_result["schema"] = "carbon.score-lab.solver-benchmark-result.v1"
    with pytest.raises(BenchmarkScoreRefused, match="benchmark_binding"):
        ScoreEngine.score_solver_benchmark_v3(old_result, pack)
