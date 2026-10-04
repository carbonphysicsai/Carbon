from __future__ import annotations

import pytest

from carbon.design_search import aggregate_methods, experiment
from carbon.motor import customer_decision as cd


def _contract():
    return cd.contract(
        contract_id="motor-synthetic-fixture-v1",
        requirement_ref="SYNTHETIC_FIXTURE_NOT_CUSTOMER_AUTHORITY",
        min_mean_torque_nm=4.0,
        max_ripple_fraction=0.30,
    )


def _designs():
    return [
        {
            "magnet_mm": magnet,
            "embrace": 0.75,
            "airgap_mm": 0.5,
            "slot_open_deg": 3.7,
            "tooth_mm": 3.5,
            "slot_bottom_mm": 38.16,
        }
        for magnet in (2.0, 3.0)
    ]


def _conditions():
    return [
        {"current_density_a_mm2": 8.0, "current_angle_deg": 0.0},
        {"current_density_a_mm2": 15.0, "current_angle_deg": 60.0},
    ]


def _curve(mean, ripple_fraction):
    half = mean * ripple_fraction / 2
    return {"torque_nm": [mean - half, mean + half] * 30}


def _request(*, query_budget=4):
    contract = _contract()
    adapter = cd.adapter(contract)
    neutral = experiment.neutral_request(
        adapter,
        mode=cd.MODE,
        model={
            "member": "fixture-model",
            "recipe_digest": "sha256:" + "1" * 64,
            "seed": 0,
        },
        designs=_designs(),
        conditions=_conditions(),
        query_budget=query_budget,
        verification_budget=2,
        method={
            "name": "fixed_grid",
            "code_digest": "sha256:" + "2" * 64,
            "configuration_digest": "sha256:" + "3" * 64,
        },
        seed_policy="deterministic fixture",
    )
    request, space = adapter.request(neutral)
    return contract, adapter, request, space


def test_contract_has_no_implicit_scientific_limits():
    with pytest.raises(TypeError):
        cd.contract(
            contract_id="missing-limits",
            requirement_ref="SYNTHETIC_FIXTURE",
        )
    with pytest.raises(cd.DecisionError, match="mean_torque_floor_negative"):
        cd.contract(
            contract_id="bad-limit",
            requirement_ref="SYNTHETIC_FIXTURE",
            min_mean_torque_nm=-1,
            max_ripple_fraction=0.2,
        )


def test_oracle_forbids_duplicates_within_and_across_calls():
    _contract_document, adapter, request, space = _request()
    within = adapter.oracle(
        request,
        space,
        lambda inputs: {key: _curve(6, 0.2) for key in inputs},
    )
    first = (*space[0], 8.0, 0.0)
    second = (*space[0], 15.0, 60.0)
    with pytest.raises(cd.DecisionError, match="duplicate_query_forbidden"):
        within.query([first, first])
    assert within.used == 0
    with pytest.raises(cd.DecisionError, match="oracle_sealed_after_failure"):
        within.query([first])

    across = adapter.oracle(
        request,
        space,
        lambda inputs: {key: _curve(6, 0.2) for key in inputs},
    )
    across.query([first])
    with pytest.raises(cd.DecisionError, match="duplicate_query_forbidden"):
        across.query([first, second])
    assert across.used == 1
    with pytest.raises(cd.DecisionError, match="oracle_sealed_after_failure"):
        across.query([second])


def test_attempts_are_charged_and_failure_seals_the_oracle(tmp_path):
    _contract_document, adapter, request, space = _request()

    def fail(_inputs):
        raise RuntimeError("model process disappeared")

    oracle = adapter.oracle(request, space, fail)
    points = [(*space[0], 8.0, 0.0), (*space[0], 15.0, 60.0)]
    with pytest.raises(cd.ModelInfrastructureFailure):
        oracle.query(points)
    assert oracle.used == 2
    assert oracle.successful == 0
    assert oracle.terminal_failure["code"] == "model_infrastructure_failure"
    with pytest.raises(cd.DecisionError, match="oracle_sealed_after_failure"):
        oracle.query([(*space[1], 8.0, 0.0)])
    with pytest.raises(cd.DecisionError, match="oracle_sealed_after_failure"):
        adapter.commit(request, [], oracle, tmp_path)


def test_malformed_output_is_charged_classified_and_cannot_be_committed(tmp_path):
    _contract_document, adapter, request, space = _request()
    oracle = adapter.oracle(request, space, lambda _inputs: {})
    point = (*space[0], 8.0, 0.0)
    with pytest.raises(cd.DecisionError, match="malformed_model_batch"):
        oracle.query([point])
    assert oracle.used == 1
    assert oracle.successful == 0
    assert oracle.log[0]["status"] == "FAILED_PROTOCOL"
    with pytest.raises(cd.DecisionError, match="oracle_sealed_after_failure"):
        adapter.commit(request, [], oracle, tmp_path)


def test_fixed_grid_uses_ripple_objective_after_all_constraints_hold(tmp_path):
    _contract_document, adapter, request, space = _request()

    def infer(inputs):
        return {
            key: _curve(6, 0.30 if row["magnet_mm"] == 2.0 else 0.20)
            for key, row in inputs.items()
        }

    oracle = adapter.oracle(request, space, infer)
    selection = adapter.baseline(oracle, request, space)
    assert len(selection) == 1
    assert selection[0]["magnet_mm"] == 3.0
    assert selection[0]["predicted_worst_ripple_fraction"] == pytest.approx(0.2)
    assert selection[0]["predicted_worst_condition_mean_torque_nm"] == pytest.approx(
        6.0
    )
    commitment = adapter.commit(request, selection, oracle, tmp_path)
    assert commitment.document["status"] == "PROPOSAL"
    assert commitment.document["queries_attempted"] == 4


def test_fixed_grid_ties_use_worst_mean_then_declared_design_order():
    _contract_document, adapter, request, space = _request()

    def different_means(inputs):
        return {
            key: _curve(5 if row["magnet_mm"] == 2.0 else 6, 0.2)
            for key, row in inputs.items()
        }

    oracle = adapter.oracle(request, space, different_means)
    selection = adapter.baseline(oracle, request, space)
    assert selection[0]["magnet_mm"] == 3.0
    assert selection[0]["predicted_worst_condition_mean_torque_nm"] == 6.0

    equal = adapter.oracle(
        request,
        space,
        lambda inputs: {key: _curve(6, 0.2) for key in inputs},
    )
    selection = adapter.baseline(equal, request, space)
    assert selection[0]["magnet_mm"] == 2.0


def test_screening_uses_the_registered_cross_condition_tie_rule():
    _contract_document, adapter, request, space = _request()

    def infer(inputs):
        outputs = {}
        for key, row in inputs.items():
            if row["magnet_mm"] == 2.0:
                mean = 5.0 if row["current_density_a_mm2"] == 8.0 else 9.0
            else:
                mean = 6.0
            outputs[key] = _curve(mean, 0.2)
        return outputs

    oracle = adapter.oracle(request, space, infer)
    selection = aggregate_methods.screen_then_confirm(
        adapter.view(request, space),
        oracle,
        screen_condition=0,
        aggregate_objective=lambda rows: (
            max(row["ripple_fraction"] for row in rows),
            -min(row["mean_nm"] for row in rows),
        ),
    )
    assert selection[0]["magnet_mm"] == 3.0
    assert selection[0]["predicted_worst_ripple_fraction"] == pytest.approx(0.2)
    assert selection[0]["predicted_worst_condition_mean_torque_nm"] == 6.0


def test_commit_rederives_the_selection_objective(tmp_path):
    _contract_document, adapter, request, space = _request()
    oracle = adapter.oracle(
        request,
        space,
        lambda inputs: {key: _curve(6, 0.2) for key in inputs},
    )
    selection = adapter.baseline(oracle, request, space)
    selection[0]["predicted_worst_ripple_fraction"] = 0.1
    with pytest.raises(cd.DecisionError, match="selection_objective_mismatch"):
        adapter.commit(request, selection, oracle, tmp_path)


def test_known_violation_survives_other_unavailable_reference(tmp_path):
    _contract_document, adapter, request, space = _request()
    oracle = adapter.oracle(
        request,
        space,
        lambda inputs: {key: _curve(6, 0.2) for key in inputs},
    )
    selection = adapter.baseline(oracle, request, space)
    commitment = adapter.commit(request, selection, oracle, tmp_path)

    def source(job):
        if job["inputs"]["current_density_a_mm2"] == 8.0:
            return {
                "status": "OK",
                "case_id": job["case_id"],
                "inputs": job["inputs"],
                "outputs": _curve(3.0, 0.2),
                "evidence_class": "ANALYTICAL_FIXTURE",
            }
        return None

    reference = cd.fixture_reference(
        source, condition_budget=2, session_id="mixed-evidence-fixture"
    )
    result = adapter.verify(commitment, reference)
    assert result["status"] == "CONFIRMED_INFEASIBLE"
    assert result["verdicts"] == {
        "FEASIBLE": 0,
        "INFEASIBLE": 1,
        "REFERENCE_UNAVAILABLE": 1,
    }
    assert result["reference_availability"] == {"available": 1, "unavailable": 1}


def test_reference_access_requires_a_persisted_commitment():
    contract = _contract()
    reference = cd.analytical_fixture_reference(condition_budget=2)
    with pytest.raises(cd.DecisionError, match="commitment_only_from_commit"):
        cd.verify(contract, {"status": "PROPOSAL"}, reference)


def test_plausible_callback_record_cannot_become_counted_getdp_evidence():
    with pytest.raises(cd.DecisionError, match="counted_getdp_.*fields"):
        cd.counted_getdp_reference(
            {
                "case": {
                    "status": "OK",
                    "inputs": {},
                    "outputs": {"torque_nm": [5.0] * 60},
                    "checks": {},
                    "provenance": {"evidence_class": "COUNTED_GETDP"},
                }
            },
            condition_budget=1,
            session_id="forged",
            construction_identity_digest="sha256:" + "a" * 64,
        )
