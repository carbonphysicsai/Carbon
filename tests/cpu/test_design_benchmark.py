"""Synthetic native-bound evidence; no Challenge model, solver or rule values."""

import hashlib
import json
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


def measurement_basis():
    return {
        "schema": "carbon.scoring.dual-measurement-contract.v1",
        "producer_digest": "sha256:" + "a" * 64,
        "accuracy_definition_sha256": "sha256:" + "b" * 64,
        "important_limit_definition_sha256": "sha256:" + "c" * 64,
        "design_objective_sha256": "sha256:" + "d" * 64,
    }


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


@pytest.mark.parametrize("normal_basis", [False, True])
def test_original_physics_gates_cost_identity_and_inputs_are_retained(normal_basis):
    args = inputs()
    args[4]["models"][1]["gates"]["toy_physics"] = "FAIL"
    before = deepcopy(args)
    receipt = provenance(args[3], args[4])
    result = adapter.score_design_benchmark(
        *args,
        provenance=receipt,
        measurement_basis=measurement_basis() if normal_basis else None,
    )
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


def test_normal_basis_has_exact_schema_newline_hash_and_separate_rich_audit():
    args = inputs()
    basis = measurement_basis()
    before = deepcopy(basis)
    output = run(args, measurement_basis=basis)
    point = output["projections"][adapter.PARTIAL_POINT_DIAGNOSTIC]
    registered = output["projections"][adapter.REGISTERED_COMPONENTS_REQUIRED]
    compact = json.dumps(basis, sort_keys=True, separators=(",", ":"), allow_nan=False)
    expected = "sha256:" + hashlib.sha256((compact + "\n").encode()).hexdigest()
    without_lf = "sha256:" + hashlib.sha256(compact.encode()).hexdigest()
    assert basis == before and registered["measurement_contract"] == before
    assert set(registered["measurement_contract"]) == set(before)
    assert registered["score_pack"]["measurement_contract_digest"] == expected
    assert registered["benchmark_input"]["measurement_contract_digest"] == expected
    assert expected != without_lf
    assert point["measurement_contract"] != before
    assert point["score_pack"]["measurement_contract_digest"] != expected
    assert point["score_pack"]["pack_digest"] != registered["score_pack"]["pack_digest"]
    audit = registered["design_audit"]
    assert audit["projection_definition"]["policy"] == args[0]
    assert (
        audit["projection_definition"]["reference_coverage_digest"]
        == output["reduction"]["reference_coverage_digest"]
    )
    assert audit["model_prediction_digests"] == {
        row["artifact_digest"]: row["prediction_digest"]
        for row in output["reduction"]["models"]
    }
    basis["producer_digest"] = "sha256:" + "e" * 64
    assert registered["measurement_contract"] == before
    assert not output["official_score"] and not output["score_adopted"]


def test_basis_affects_only_registered_contract_and_none_keeps_previous_behavior():
    args = inputs()
    default = run(args)
    assert default == run(args, measurement_basis=None)
    changed = run(args, measurement_basis=measurement_basis())
    assert changed["reduction"] == default["reduction"]
    assert (
        changed["projections"][adapter.PARTIAL_POINT_DIAGNOSTIC]
        == default["projections"][adapter.PARTIAL_POINT_DIAGNOSTIC]
    )
    original = changed["projections"][adapter.REGISTERED_COMPONENTS_REQUIRED]
    reversed_basis = dict(reversed(list(measurement_basis().items())))
    assert (
        run(args, measurement_basis=reversed_basis)["projections"][
            adapter.REGISTERED_COMPONENTS_REQUIRED
        ]
        == original
    )


@pytest.mark.parametrize("gap", ["unknown_interval", "missing_reference"])
def test_normal_basis_does_not_resolve_missing_reference_evidence(gap):
    args = inputs()
    if gap == "unknown_interval":
        args[1]["cases"]["c0"]["margin"]["interval"] = None
    else:
        del args[1]["cases"]["c1"]
    output = run(args, measurement_basis=measurement_basis())
    registered = output["projections"][adapter.REGISTERED_COMPONENTS_REQUIRED]
    assert registered["measurement_contract"] == measurement_basis()
    assert all(row["registered_D"] is None for row in output["reduction"]["models"])
    assert all(not row["candidate_issues"] for row in output["reduction"]["models"])
    assert all(row["score"] is None for row in registered["score_result"]["models"])
    assert all(
        row["measurements"]["rich_design_benefit"]
        == {"status": "REFERENCE_UNRESOLVED", "value": None, "unit": "1"}
        for row in registered["benchmark_input"]["models"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "container",
        "missing",
        "extra",
        "schema",
        "bare",
        "uppercase",
        "short",
        "empty",
        "type",
    ],
)
def test_malformed_normal_measurement_basis_is_refused(mutation):
    basis = measurement_basis()
    if mutation == "container":
        basis = list(basis.items())
    elif mutation == "missing":
        del basis["design_objective_sha256"]
    elif mutation == "extra":
        basis["score_adopted"] = True
    elif mutation == "schema":
        basis["schema"] = "unregistered-contract"
    else:
        basis["producer_digest"] = {
            "bare": "a" * 64,
            "uppercase": "sha256:" + "A" * 64,
            "short": "sha256:" + "a" * 63,
            "empty": "",
            "type": 0,
        }[mutation]
    with pytest.raises(adapter.DesignBenchmarkRefused, match="measurement_basis_"):
        run(inputs(), measurement_basis=basis)


def point_inputs():
    args = inputs()
    for row in args[1]["cases"].values():
        for atom in row.values():
            atom["interval"] = None
    for row in args[1]["actions"].values():
        row["objective"]["interval"] = None
    # The complete native finite task has no negative-side observation.
    args[1]["cases"]["c1"]["margin"]["value"] = 0.2
    for model in args[2]:
        model["cases"]["c1"]["margin"]["value"] = 0.2
    return args


def finite_registration(args):
    policy, reference = args[:2]
    return {
        "schema": "carbon.scoring.finite-task-point-registration.v1",
        "scope": "DEVELOPMENT",
        "mode": adapter.FINITE_TASK_POINT_REFERENCE,
        "policy_digest": design_fidelity.digest(design_fidelity.typed_identity(policy)),
        "reference_digest": design_fidelity.digest(
            design_fidelity.typed_identity(reference)
        ),
        "source_acceptance_digest": "sha256:" + "e" * 64,
        "native_point_contract_digest": "sha256:" + "f" * 64,
        "action_ids": list(policy["action_ids"]),
        "case_ids": list(policy["case_ids"]),
        "mandatory_condition_ids": ["condition"],
        "action_condition_case_ids": {
            "a": {"condition": "c0"},
            "b": {"condition": "c1"},
        },
    }


def finite(args, **kwargs):
    return run(args, finite_task_registration=finite_registration(args), **kwargs)


def test_complete_finite_point_task_scores_without_intervals_or_sign_sides():
    args = point_inputs()
    before = deepcopy(args)
    result = finite(args)
    projection = result["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    assert args == before
    assert all(row["score"] is not None for row in projection["score_result"]["models"])
    assert all(row["registered_D"] is None for row in result["reduction"]["models"])
    assert projection["score_result"] == ScoreEngine.score_dual_benchmark_v4(
        projection["benchmark_input"], projection["score_pack"]
    )
    audit = projection["finite_task_audit"]
    assert audit["reference_issues"] == [] and audit["uncertainty"] == "UNMEASURED"
    assert audit["interval_boundary_or_ood_qualified"] is False
    assert audit["source_acceptance_authenticated_by_this_library"] is False
    for row, reduced in zip(
        projection["score_result"]["models"], result["reduction"]["models"], strict=True
    ):
        assert row["legs"]["D"] == reduced["point_estimate_D"]
    assert not projection["official_score"] and not projection["score_adopted"]


def test_finite_option_leaves_old_outputs_byte_identical_and_defaults_unchanged():
    args = point_inputs()
    old = run(args)
    assert old == run(args, finite_task_registration=None)
    new = finite(args)
    for mode, projection in old["projections"].items():
        assert json.dumps(projection, sort_keys=True) == json.dumps(
            new["projections"][mode], sort_keys=True
        )
    for key in set(old) - {"projections"}:
        assert old[key] == new[key]


@pytest.mark.parametrize(
    "gap", ["case", "action", "status", "nonfinite", "unit", "quantity", "atom_shape"]
)
def test_finite_reference_gaps_defer_whole_common_roster_without_candidate_penalty(gap):
    args = point_inputs()
    if gap == "case":
        del args[1]["cases"]["c1"]
    elif gap == "action":
        del args[1]["actions"]["b"]
    elif gap == "quantity":
        del args[1]["cases"]["c1"]["margin"]
    elif gap == "atom_shape":
        del args[1]["cases"]["c1"]["margin"]["status"]
    else:
        args[1]["cases"]["c1"]["margin"].update(
            {
                "status": {"status": "UNRESOLVED"}.get(gap, "RESOLVED"),
                "value": float("nan") if gap == "nonfinite" else 0.2,
                "unit": "INVALID" if gap == "unit" else "W",
            }
        )
    result = finite(args)
    p = result["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    assert p["finite_task_audit"]["reference_issues"]
    assert all(
        not issues for issues in p["finite_task_audit"]["candidate_issues"].values()
    )
    assert all(
        row["score"] is None and row["status"] == "INDETERMINATE_EVIDENCE"
        for row in p["score_result"]["models"]
    )


@pytest.mark.parametrize(
    "gap", ["case", "quantity", "action", "objective", "nonfinite"]
)
def test_finite_incomplete_candidate_is_local_ineligible_not_mask_drop(gap):
    args = point_inputs()
    bad = args[2][1]
    if gap == "case":
        del bad["cases"]["c1"]
    elif gap == "quantity":
        del bad["cases"]["c1"]["margin"]
    elif gap == "action":
        del bad["actions"]["b"]
    elif gap == "objective":
        del bad["actions"]["b"]["objective"]
    else:
        bad["cases"]["c1"]["margin"]["value"] = float("inf")
    p = finite(args)["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    good, bad_result = p["score_result"]["models"]
    assert good["score"] is not None
    assert bad_result["score"] is None and bad_result["status"] == "CANDIDATE_INVALID"
    assert len(p["score_result"]["models"]) == 2


@pytest.mark.parametrize("missing_reference", ["case", "action"])
def test_finite_missing_reference_does_not_hide_independent_candidate_failure(
    missing_reference,
):
    args = point_inputs()
    if missing_reference == "case":
        del args[1]["cases"]["c1"]
    else:
        del args[1]["actions"]["b"]
    del args[2][1]["cases"]["c1"]
    p = finite(args)["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    good, bad = p["score_result"]["models"]
    assert good["status"] == "INDETERMINATE_EVIDENCE"
    assert bad["status"] == "CANDIDATE_INVALID"
    assert good["score"] is None and bad["score"] is None


@pytest.mark.parametrize("selected", ["a", None])
def test_finite_source_deferral_preserves_nullable_reducer_row_contract(selected):
    args = point_inputs()
    standard = finite(args)["reduction"]["models"][0]
    del args[1]["actions"]["b"]
    for model in args[2]:
        model["selected_action"] = selected
    output = finite(args)
    rows = output["reduction"]["models"]
    for row in rows:
        assert set(row) == set(standard)
        assert row["V"]["V"] is None and row["V"]["regret"] is None
        assert row["V"]["selected_action"] == selected
        assert row["V"]["reference_feasible_set_is_settled"] is False
        assert row["C"] is None and row["C_bounds"] is None
        assert row["D_bounds"] is None and row["registered_D"] is None
        assert row["earns_full_credit"] is False
        assert row["coverage_slot_errors"] == {} and row["limiting_components"] == []
        assert row["candidate_status"] == (
            "ABSTAIN" if selected is None else "VALID_PREDICTIONS"
        )


def test_finite_unrelated_source_gap_does_not_hide_malformed_frozen_gap_pairs():
    args = point_inputs()
    del args[1]["cases"]["c1"]
    args[0]["components"][2]["pairs"] = []
    with pytest.raises(
        design_fidelity.ReductionRefused,
        match="gap_requires_every_settled_feasible_pair",
    ):
        finite(args)


def test_finite_missing_action_cannot_hide_missing_known_settled_feasible_pair():
    args = point_inputs()
    args[0]["action_ids"].append("c")
    args[0]["case_ids"].append("c2")
    args[0]["components"][2]["pairs"] = [["a", "c"], ["b", "c"]]
    args[1]["cases"]["c2"] = deepcopy(args[1]["cases"]["c0"])
    for model in args[2]:
        model["cases"]["c2"] = deepcopy(model["cases"]["c0"])
        model["actions"]["c"] = deepcopy(model["actions"]["a"])
    registration = finite_registration(args)
    registration["action_condition_case_ids"]["c"] = {"condition": "c2"}
    with pytest.raises(
        design_fidelity.ReductionRefused,
        match="gap_requires_every_settled_feasible_pair",
    ):
        run(args, finite_task_registration=registration)


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "scope",
        "mode",
        "source",
        "native",
        "policy",
        "reference",
        "extra",
        "roster",
        "mapping",
        "condition",
    ],
)
def test_invalid_finite_registration_is_refused(mutation):
    args = point_inputs()
    registration = finite_registration(args)
    if mutation in ("schema", "scope", "mode"):
        registration[mutation] = "INVALID"
    elif mutation in ("source", "native"):
        registration[
            {
                "source": "source_acceptance_digest",
                "native": "native_point_contract_digest",
            }[mutation]
        ] = "not-a-digest"
    elif mutation in ("policy", "reference"):
        registration[mutation + "_digest"] = "sha256:" + "0" * 64
    elif mutation == "extra":
        registration["qualified"] = True
    elif mutation == "roster":
        registration["case_ids"] = ["c0"]
    elif mutation == "mapping":
        registration["action_condition_case_ids"]["b"]["condition"] = "c0"
    else:
        registration["action_condition_case_ids"]["b"] = {}
    with pytest.raises(adapter.DesignBenchmarkRefused, match="finite_registration_"):
        run(args, finite_task_registration=registration)


def test_finite_normal_basis_distinguishes_producer_and_definition_roles():
    args = point_inputs()
    basis = measurement_basis()
    with pytest.raises(adapter.DesignBenchmarkRefused, match="roles_must_be_distinct"):
        finite(args, measurement_basis=basis, finite_task_measurement_basis=basis)
    other = {
        **basis,
        "producer_digest": "sha256:" + "e" * 64,
        "design_objective_sha256": "sha256:" + "f" * 64,
    }
    result = finite(args, measurement_basis=basis, finite_task_measurement_basis=other)
    point = result["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    assert point["measurement_contract"] == other
    assert (
        len({p["score_pack"]["pack_digest"] for p in result["projections"].values()})
        == 3
    )
    # Across calls even identical normal-contract bytes cannot alias the stronger pack.
    interval = run(args, measurement_basis=basis)["projections"][
        adapter.REGISTERED_COMPONENTS_REQUIRED
    ]
    finite_same = finite(args, finite_task_measurement_basis=basis)["projections"][
        adapter.FINITE_TASK_POINT_REFERENCE
    ]
    assert (
        finite_same["score_pack"]["measurement_contract_digest"]
        == interval["score_pack"]["measurement_contract_digest"]
    )
    assert (
        finite_same["score_pack"]["pack_digest"]
        != interval["score_pack"]["pack_digest"]
    )


def test_finite_scope_uses_points_not_interval_allowances_and_preserves_gates():
    args = inputs()
    args[1]["cases"]["c0"]["margin"]["interval"].update(lower=0.0, upper=1.0)
    args[2][0]["cases"]["c0"]["margin"]["value"] = 0.5
    args[4]["models"][1]["gates"]["toy_physics"] = "FAIL"
    result = finite(args)
    point = result["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    partial = result["projections"][adapter.PARTIAL_POINT_DIAGNOSTIC]
    assert (
        point["score_result"]["models"][0]["legs"]["D"]
        < partial["score_result"]["models"][0]["legs"]["D"]
    )
    assert point["score_result"]["models"][1]["score"] is None
    assert point["score_pack"]["legs"]["A"] == args[3]["legs"]["A"]
    assert point["score_pack"]["value_weight"] == 0.5


def test_finite_unsafe_selection_keeps_native_gate_and_requires_inadmissibility():
    args = point_inputs()
    args[1]["actions"]["b"] = {"feasibility": "INFEASIBLE", "objective": None}
    args[0]["components"][2]["pairs"] = []
    args[2][1]["selected_action"] = "b"
    args[4]["models"][1]["gates"]["toy_physics"] = "FAIL"
    p = finite(args)["projections"][adapter.FINITE_TASK_POINT_REFERENCE]
    assert p["score_result"]["models"][1]["score"] is None
    assert p["score_result"]["models"][1]["status"] == "MANDATORY_GATE_FAILED"
    assert p["benchmark_input"]["models"][1]["gates"]["toy_physics"] == "FAIL"
    args[4]["models"][1]["gates"]["toy_physics"] = "PASS"
    with pytest.raises(
        adapter.DesignBenchmarkRefused, match="unsafe_selection_missing"
    ):
        finite(args)
