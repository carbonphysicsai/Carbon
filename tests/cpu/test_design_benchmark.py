"""Synthetic native-bound evidence; no Challenge model, solver or rule values."""

from copy import deepcopy

import pytest
from test_design_fidelity import fixture as design_fixture
from test_dual_score import fixture as dual_fixture

from carbon.scoring import design_benchmark as adapter
from carbon.scoring import design_fidelity, dual_score
from carbon.scoring.engine import ScoreEngine


def inputs():
    policy, reference, model = design_fixture()
    body, benchmark = dual_fixture()
    body["value_weight"] = 0.5
    pack = dual_score.register_pack(body)
    model["artifact_digest"] = benchmark["models"][0]["artifact_digest"]
    second = deepcopy(model)
    second["artifact_digest"] = "sha256:" + "5" * 64
    second["cases"]["c0"]["margin"]["value"] = 1.1
    native_second = deepcopy(benchmark["models"][0])
    native_second["artifact_digest"] = second["artifact_digest"]
    native_second["measurements"]["A"]["value"] = 0.9
    benchmark["models"].append(native_second)
    return policy, reference, [model, second], pack, benchmark


def provenance(pack, benchmark):
    return {
        "original_pack_digest": pack["pack_digest"],
        "original_benchmark_digest": design_fidelity.digest(
            design_fidelity.typed_identity(benchmark)
        ),
        "native_workflow_cost": {"cpu_s": 17.0, "wall_s": 10.0},
        "source": "SYNTHETIC_ONLY_NO_SCIENTIFIC_ACCEPTANCE",
    }


def run(args, **kwargs):
    return adapter.score_design_benchmark(
        *args, provenance=provenance(args[3], args[4]), **kwargs
    )


def test_same_core_two_models_and_fixed_reference_pack_across_subsets():
    args = inputs()
    full = run(args)
    for index in (0, 1):
        subset = deepcopy(args)
        subset[2][:] = [subset[2][index]]
        subset[4]["models"][:] = [subset[4]["models"][index]]
        single = run(subset)
        assert (
            full["reduction"]["reference_coverage_digest"]
            == single["reduction"]["reference_coverage_digest"]
        )
        for mode, projection in full["projections"].items():
            other = single["projections"][mode]
            assert projection["score_pack"] == other["score_pack"]
            assert (
                projection["score_result"]["models"][index]
                == other["score_result"]["models"][0]
            )
            assert projection["score_result"] == ScoreEngine.score_dual_benchmark_v4(
                projection["benchmark_input"], projection["score_pack"]
            )


def test_original_physics_gates_cost_identity_and_inputs_are_retained():
    args = inputs()
    args[4]["models"][1]["gates"]["toy_physics"] = "FAIL"
    before = deepcopy(args)
    receipt = provenance(args[3], args[4])
    result = adapter.score_design_benchmark(*args, provenance=receipt)
    assert args == before and result["provenance"] == receipt
    assert result["original"]["score_pack"] == args[3]
    assert result["original"]["benchmark_input"] == args[4]
    for projection in result["projections"].values():
        pack = projection["score_pack"]
        assert pack["legs"]["A"] == args[3]["legs"]["A"]
        for key in ("hard_gates", "value_weight", "combination", "decision_policy"):
            assert pack[key] == args[3][key]
        for old, new in zip(
            args[4]["models"], projection["benchmark_input"]["models"], strict=True
        ):
            for key in ("artifact_digest", "gates", "decision_outcome"):
                assert old[key] == new[key]
            assert old["measurements"]["A"] == new["measurements"]["A"]
        assert projection["score_result"]["models"][1]["score"] is None
    result["provenance"]["native_workflow_cost"]["cpu_s"] = 999
    assert receipt["native_workflow_cost"]["cpu_s"] == 17


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "malformed"])
def test_exact_paired_artifact_mask_is_required(mutation):
    args = inputs()
    if mutation == "missing":
        args[2].pop()
    elif mutation == "extra":
        extra = deepcopy(args[2][0])
        extra["artifact_digest"] = "sha256:" + "6" * 64
        args[2].append(extra)
    elif mutation == "duplicate":
        args[2][1]["artifact_digest"] = args[2][0]["artifact_digest"]
    else:
        args[2][0]["artifact_digest"] = ["invalid"]
    with pytest.raises(adapter.DesignBenchmarkRefused, match="paired_model_identity"):
        run(args)


@pytest.mark.parametrize(
    "binding", ["original_pack_digest", "original_benchmark_digest"]
)
def test_original_provenance_binding_is_checked(binding):
    args = inputs()
    receipt = provenance(args[3], args[4])
    receipt[binding] = "sha256:" + "0" * 64
    with pytest.raises(adapter.DesignBenchmarkRefused, match="original_.*binding"):
        adapter.score_design_benchmark(*args, provenance=receipt)


def test_optional_original_result_replays_and_wrong_result_is_refused():
    args = inputs()
    replay = ScoreEngine.score_dual_benchmark_v4(args[4], args[3])
    assert run(args, original_result=replay)["original"]["score_result"] == replay
    replay["models"][0]["score"] = -1
    with pytest.raises(adapter.DesignBenchmarkRefused, match="original_result_replay"):
        run(args, original_result=replay)


def test_native_pack_and_benchmark_must_be_valid_and_match():
    args = inputs()
    args[4]["physics_contract_digest"] = "sha256:" + "0" * 64
    with pytest.raises(dual_score.DualScoreRefused, match="benchmark_binding"):
        run(args)


def test_preserve_half_weight_without_silently_changing_other_pack():
    args = inputs()
    body = {k: v for k, v in args[3].items() if k != "pack_digest"}
    body["value_weight"] = 0.8
    args = (*args[:3], dual_score.register_pack(body), args[4])
    with pytest.raises(adapter.DesignBenchmarkRefused, match="original_50_50_required"):
        run(args)


def test_unknown_intervals_allow_only_explicitly_partial_point_projection():
    args = inputs()
    args[1]["cases"]["c0"]["margin"]["interval"] = None
    result = run(args)
    point = result["projections"][adapter.PARTIAL_POINT_DIAGNOSTIC]
    registered = result["projections"][adapter.REGISTERED_COMPONENTS_REQUIRED]
    assert point["diagnostic_only"] is True
    assert point["label"] == adapter.PARTIAL_POINT_DIAGNOSTIC
    assert point["score_result"]["models"][0]["score"] is not None
    assert registered["diagnostic_only"] is False
    assert all(row["score"] is None for row in registered["score_result"]["models"])
    assert all(row["registered_D"] is None for row in result["reduction"]["models"])
    assert all(not row["candidate_issues"] for row in result["reduction"]["models"])
    for projection in result["projections"].values():
        assert not projection["official_score"] and not projection["score_adopted"]


def test_missing_reference_is_common_deferral_without_candidate_penalty():
    args = inputs()
    del args[1]["cases"]["c1"]
    result = run(args)
    assert all(not row["candidate_issues"] for row in result["reduction"]["models"])
    registered = result["projections"][adapter.REGISTERED_COMPONENTS_REQUIRED]
    assert all(
        row["status"] == "INDETERMINATE_EVIDENCE" and row["score"] is None
        for row in registered["score_result"]["models"]
    )


def test_bad_candidate_prediction_is_local_not_reference_failure():
    args = inputs()
    args[2][1]["cases"]["c1"]["margin"]["value"] = float("nan")
    result = run(args)
    assert not result["reduction"]["models"][0]["candidate_issues"]
    assert result["reduction"]["models"][1]["candidate_issues"]
    for projection in result["projections"].values():
        good, bad = projection["score_result"]["models"]
        assert good["score"] is not None
        assert bad["status"] == "CANDIDATE_INVALID" and bad["score"] is None


def test_unsafe_pick_retains_native_failure_and_cannot_gain_a_registered_score():
    args = inputs()
    args[1]["actions"]["b"] = {"feasibility": "INFEASIBLE", "objective": None}
    args[0]["components"][2]["pairs"] = []
    args[2][1]["selected_action"] = "b"
    args[4]["models"][1]["gates"]["toy_physics"] = "FAIL"
    result = run(args)
    unsafe = result["reduction"]["models"][1]
    assert unsafe["candidate_status"] == "PROVEN_UNSAFE_SELECTION"
    assert unsafe["registered_D"] is None
    for projection in result["projections"].values():
        row = projection["score_result"]["models"][1]
        assert row["gates"]["toy_physics"] == "FAIL" and row["score"] is None
    args[4]["models"][1]["gates"]["toy_physics"] = "PASS"
    with pytest.raises(
        adapter.DesignBenchmarkRefused, match="unsafe_selection_missing"
    ):
        run(args)
