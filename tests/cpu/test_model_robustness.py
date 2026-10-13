"""Discriminating public fixture tests; no participant/model/solver execution."""

from dataclasses import replace

import pytest

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack import model_robustness as m
from carbon.agent_campaign.attack.model_robustness_demo import (
    bad_predict,
    fixture_boundary,
    fixture_policy,
    fixture_predict,
    fixture_witness,
    run_fixture,
)


def run(
    *,
    family=m.FAMILIES[1],
    boundary=None,
    negative=None,
    policy=None,
    attack=None,
    control_witness="default",
    attack_witness=None,
):
    base = m.grid(2)
    return m.probe(
        family,
        policy or fixture_policy(),
        boundary or fixture_boundary(),
        baseline=base,
        attack=attack or m.corrupt(base, "degenerate"),
        negative=negative or fixture_boundary(bad_predict, "bad-toy"),
        control_witness=(
            fixture_witness(base) if control_witness == "default" else control_witness
        ),
        attack_witness=attack_witness,
    )


def refusal(payload):
    return {"status": "REFUSE", "values": [], "reason": "no_support"}


def test_both_families_and_all_mesh_variants_have_discriminating_controls():
    rows = run_fixture()
    assert len(rows) == 7
    assert {r["family"] for r in rows} == set(m.FAMILIES)
    assert all(r["verdict"] == "HELD" for r in rows)
    assert all(r["control"]["verdict"] == "HELD" for r in rows)
    assert all(r["specimen"]["verdict"] == "BREACHED" for r in rows)
    assert all(r["calls"] == 3 and r["covered_attempts"] == 1 for r in rows)
    assert all(r["evidence_basis"] == "SYNTHETIC_FIXTURE" for r in rows)
    assert all(not r["official_eligible"] and not r["qualification"] for r in rows)
    assert rows[1]["scope"] == "OUTSIDE_ENVELOPE"
    assert rows[3]["scope"] == "OUTSIDE_RESOURCE_SUPPORT"
    assert rows[2]["measurements"]["normalized_max_displacement"] is None


def test_predictor_that_passes_submission_but_extrapolates_is_caught():
    row = run(boundary=fixture_boundary(bad_predict, "extrapolator"))
    assert row["verdict"] == "BREACHED"
    assert row["attempt"]["reason"] == "prediction_outside_supported_scope"


def test_always_refuse_cannot_pass_despite_holding_hostile_input():
    row = run(boundary=fixture_boundary(refusal, "always-refuse"))
    assert row["attempt"]["verdict"] == "HELD"
    assert row["control"]["verdict"] == "BREACHED"
    assert row["verdict"] == "BREACHED"
    assert row["reason"] == "supported_control_breached"


def test_silent_detector_cannot_pass():
    row = run(negative=fixture_boundary(fixture_predict, "not-actually-bad"))
    assert row["verdict"] == "INCONCLUSIVE"
    assert row["reason"] == "negative_control_did_not_fire"


def test_valid_irregular_mesh_is_a_model_accuracy_test_not_just_input_validation():
    mesh = m.grid(4, irregularity=0.2)
    row = run(
        attack=mesh,
        attack_witness=fixture_witness(mesh),
        boundary=fixture_boundary(bad_predict, "mesh-blind"),
    )
    assert row["scope"] == "SUPPORTED"
    assert row["attempt"]["reason"] == "witness_error"
    assert row["attempt"]["max_absolute_error"] == 100.0
    assert row["verdict"] == "BREACHED"


@pytest.mark.parametrize("field", ["bounds", "supported_nodes", "tolerance"])
def test_missing_human_policy_does_not_execute_or_pass(field):
    row = run(policy=replace(fixture_policy(), **{field: None}))
    assert row["verdict"] == "NOT_RUN"
    assert row["calls"] == row["covered_attempts"] == 0


def test_radical_threshold_is_required_and_measured():
    mesh = m.deform(m.grid(2), stretch=1.0, shear=1.0)
    row = run(
        family=m.FAMILIES[0],
        attack=mesh,
        policy=replace(fixture_policy(), radical_displacement=None),
    )
    assert row["reason"] == "HUMAN_INPUT_radical_displacement"
    size = m.measurements(mesh, m.grid(2))["normalized_max_displacement"]
    assert size == pytest.approx(1 / 2**0.5)
    assert (
        run(
            family=m.FAMILIES[0],
            attack=mesh,
            policy=replace(fixture_policy(), radical_displacement=size),
        )["verdict"]
        == "HELD"
    )
    assert (
        run(
            family=m.FAMILIES[0],
            attack=mesh,
            policy=replace(fixture_policy(), radical_displacement=size + 0.01),
        )["verdict"]
        == "NOT_RUN"
    )
    assert run(family=m.FAMILIES[0], attack=m.grid(2))["verdict"] == "NOT_RUN"


def test_unknown_is_not_not_applicable_and_no_capability_is_not_coverage():
    unknown = run(boundary=replace(fixture_boundary(), capabilities=None))
    absent = run(boundary=replace(fixture_boundary(), capabilities=frozenset()))
    assert unknown["verdict"] == "NOT_RUN"
    assert absent["verdict"] == "NOT_APPLICABLE"
    assert absent["covered_attempts"] == absent["calls"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("mesh_digest", engine.digest("other")),
        ("unit", "wrong-unit"),
        ("values", (1.0,)),
    ],
)
def test_mismatched_reference_is_not_candidate_failure(field, value):
    witness = replace(fixture_witness(m.grid(2)), **{field: value})
    row = run(control_witness=witness)
    assert row["verdict"] == "NOT_RUN" and row["calls"] == 0


def test_missing_reference_is_never_a_pass():
    assert run(control_witness=None)["reason"] == "matched_public_reference_missing"
    assert run(attack=m.grid(4))["reason"] == "matched_public_reference_missing"


@pytest.mark.parametrize(
    "exception,expected",
    [
        (engine.InfrastructureFailure, "FAILED_INFRA"),
        (TimeoutError, "TIMEOUT"),
        (RuntimeError, "CRASHED"),
    ],
)
def test_endpoint_failure_never_scientific_breach_or_held(exception, expected):
    def fail(payload):
        raise exception("private error content")

    row = run(boundary=fixture_boundary(fail, "broken-host"))
    assert row["verdict"] == expected
    assert row["covered_attempts"] == 0
    assert "private error content" not in str(row)


def test_bad_control_crash_does_not_suppress_actual_breach():
    def fail(payload):
        raise engine.InfrastructureFailure("host")

    row = run(
        boundary=fixture_boundary(bad_predict, "bad-predictor"),
        negative=fixture_boundary(fail, "broken-negative"),
    )
    assert row["verdict"] == "BREACHED"
    assert row["specimen"]["verdict"] == "FAILED_INFRA"


@pytest.mark.parametrize(
    "exception,expected",
    [
        (engine.InfrastructureFailure, "FAILED_INFRA"),
        (TimeoutError, "TIMEOUT"),
        (RuntimeError, "CRASHED"),
    ],
)
def test_incomplete_attack_does_not_suppress_observed_supported_control_breach(
    exception, expected
):
    def wrong_control_then_fail(payload):
        if payload["cells"][0][0] == payload["cells"][0][1]:
            raise exception("private host failure")
        return bad_predict(payload)

    row = run(boundary=fixture_boundary(wrong_control_then_fail, "wrong-then-fail"))
    assert row["control"]["verdict"] == "BREACHED"
    assert row["attempt"]["verdict"] == expected
    assert row["covered_attempts"] == 0
    assert row["verdict"] == "BREACHED"
    assert row["reason"] == "supported_control_breached_attack_incomplete"


def test_identical_mesh_is_not_an_observed_attack_even_with_both_controls():
    mesh = m.grid(2)
    row = run(attack=mesh, attack_witness=fixture_witness(mesh))
    assert row["attack_digest"] == row["baseline_digest"]
    assert row["verdict"] == "NOT_RUN"
    assert row["reason"] == "mesh_perturbation_not_demonstrated"
    assert row["calls"] == row["covered_attempts"] == 0


def test_numeric_spelling_change_is_not_a_mesh_attack():
    base = m.grid(2)
    mesh = m.Mesh(
        tuple(
            tuple(int(v) if v == int(v) else v for v in point) for point in base.nodes
        ),
        base.cells,
    )
    assert mesh.identity != base.identity
    assert mesh == base
    row = run(attack=mesh, attack_witness=fixture_witness(mesh))
    assert row["verdict"] == "NOT_RUN"
    assert row["calls"] == row["covered_attempts"] == 0


@pytest.mark.parametrize(
    "answer",
    [
        True,
        {},
        {"status": "PREDICT", "values": [True], "reason": ""},
        {"status": "REFUSE", "values": [1.0], "reason": "no"},
        {"status": "ABSTAIN", "values": [], "reason": ""},
        {"status": [], "values": [], "reason": ""},
    ],
)
def test_malformed_predictions_and_refusals_are_caught(answer):
    row = run(boundary=fixture_boundary(lambda payload: answer, "malformed"))
    assert row["verdict"] == "BREACHED"


def test_nonfinite_supported_prediction_is_caught():
    mesh = m.grid(4)

    def nan(payload):
        return {
            "status": "PREDICT",
            "values": [float("nan")] * len(payload["nodes"]),
            "reason": "",
        }

    row = run(
        attack=mesh,
        attack_witness=fixture_witness(mesh),
        boundary=fixture_boundary(nan, "nan"),
    )
    assert row["attempt"]["reason"] == "prediction_shape_or_nonfinite"


def test_mutating_callback_cannot_change_next_role_or_saved_input_identity():
    base = m.grid(2)
    attack = m.corrupt(base, "degenerate")
    seen = []

    def mutate(payload):
        answer = fixture_predict(payload)
        seen.append(payload["nodes"][0][0])
        payload["nodes"][0][0] = 999
        payload["cells"].clear()
        return answer

    row = run(boundary=fixture_boundary(mutate, "mutating"), attack=attack)
    assert row["verdict"] == "HELD"
    assert seen == [0, 0]
    assert row["baseline_digest"] == base.identity
    assert row["attack_digest"] == attack.identity


def test_identity_binds_policy_reference_negative_and_artifact():
    a, b = run(), run()
    assert a["record_digest"] == b["record_digest"]
    assert (
        run(policy=replace(fixture_policy(), policy_ref="other"))["record_digest"]
        != a["record_digest"]
    )
    assert (
        run(negative=fixture_boundary(bad_predict, "different-bad"))["record_digest"]
        != a["record_digest"]
    )
    witness = replace(
        fixture_witness(m.grid(2)), reference_digest=engine.digest("new-reference")
    )
    assert run(control_witness=witness)["record_digest"] != a["record_digest"]


def test_challenge_and_control_basis_cannot_be_crossed():
    with pytest.raises(ValueError, match="challenge_mismatch"):
        run(boundary=replace(fixture_boundary(), challenge="battery"))
    assert (
        run(
            negative=replace(
                fixture_boundary(bad_predict, "bad"), basis="HOST_DECLARED_PUBLIC"
            )
        )["verdict"]
        == "NOT_RUN"
    )
    assert (
        run(negative=fixture_boundary(bad_predict, "correct-toy"))["verdict"]
        == "NOT_RUN"
    )


@pytest.mark.parametrize(
    "kind,key",
    [
        ("degenerate", "degenerate_elements"),
        ("inverted", "inverted_elements"),
        ("invalid_index", "invalid_connectivity"),
    ],
)
def test_metrics_read_connectivity_and_orientation(kind, key):
    base = m.grid(2)
    assert m.measurements(m.corrupt(base, kind), base)[key] == 1


@pytest.mark.parametrize("value", [0, 65, True])
def test_harness_grid_bound(value):
    with pytest.raises(ValueError):
        m.grid(value)


def test_structural_input_limits_and_missing_science():
    with pytest.raises(ValueError):
        m.Mesh(((float("inf"), 0.0),) * 3, ((0, 1, 2),))
    with pytest.raises(ValueError):
        replace(fixture_policy(), tolerance=True)
    with pytest.raises(ValueError):
        replace(fixture_policy(), supported_nodes=m.MAX_NODES + 1)
    with pytest.raises(ValueError):
        replace(fixture_boundary(), artifact_digest="unbound")
    with pytest.raises(ValueError):
        replace(fixture_boundary(), basis="QUALIFIED")
    collapsed = m.deform(m.grid(2), stretch=0, shear=0)
    assert run(attack=collapsed)["verdict"] == "HELD"
