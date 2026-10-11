"""Toy-only prospective verified-search scoring; no Challenge solver material."""

from __future__ import annotations

import copy

import pytest

from carbon.design_search import verify_aware as v


def rule(**changes):
    body = {
        "schema": v.RULE_SCHEMA,
        "rule_id": "toy-verify-r-v1",
        "evidence_class": "DEVELOPMENT",
        "selector_version": "toy-predicted-order-v1",
        "k": 3,
        "budget": {"complete_panels": 3, "wall_s": 12.0, "core_s": 12.0},
        "objective": {"direction": "min", "unit": "minutes"},
        "regret_unit": {"value": 10.0, "unit": "minutes"},
        "reference_policy_id": "toy-settled-panel-v1",
        "eligibility_policy_id": "toy-mandatory-gates-v1",
        "population_id": "toy-P",
        "proposal_id": "toy-Q",
        "weight_law_id": "toy-w",
    }
    body.update(changes)
    return v.register_rule(body)


def action(name, status, value=None, cost=2.0):
    return {
        "action_id": name,
        "action_family_id": "toy-family",
        "reference": {"status": status, "value": value},
        "planning_bound": {"wall_s": cost, "core_s": cost},
        "actual_cost": {"wall_s": cost, "core_s": cost},
    }


def question(registered, bank=None, **changes):
    body = {
        "schema": v.QUESTION_SCHEMA,
        "question_id": "q1",
        "action_family_id": "toy-family",
        "rule_digest": registered["rule_digest"],
        "reference_policy_id": registered["reference_policy_id"],
        "population_id": registered["population_id"],
        "proposal_id": registered["proposal_id"],
        "weight_law_id": registered["weight_law_id"],
        "weight": 2.0,
        "objective": registered["objective"],
        "bank": bank
        or [
            action("bad", "INFEASIBLE"),
            action("good", "FEASIBLE", 7.0),
            action("best", "FEASIBLE", 5.0),
        ],
    }
    body.update(changes)
    return v.seal_question(body)


def commitment(actions, **changes):
    body = {
        "schema": v.COMMIT_SCHEMA,
        "model_id": "toy-model",
        "question_id": "q1",
        "action_family_id": "toy-family",
        "selector_version": "toy-predicted-order-v1",
        "ordered_actions": actions,
        "commitment_receipt_id": "toy-before-reference-receipt",
    }
    body.update(changes)
    return v.commit_list(body)


def receipt(committed, *, startup=1.0, search=1.0):
    return {
        "origin": "independent_verifier",
        "commitment_digest": committed["commitment_digest"],
        "startup_cost": {"wall_s": startup, "core_s": startup},
        "search_cost": {"wall_s": search, "core_s": search},
    }


def eligibility(registered):
    return {"policy_id": registered["eligibility_policy_id"], "verdict": "PASS"}


def run(registered, q, ordered, **costs):
    committed = commitment(ordered)
    return v.evaluate_question(
        registered, q, committed, receipt(committed, **costs), eligibility(registered)
    )


def test_best_of_all_verified_and_rejected_attempt_is_charged():
    registered = rule()
    result = run(registered, question(registered), ["bad", "good", "best"])
    assert result["attempt_statuses"] == ["INFEASIBLE", "FEASIBLE", "FEASIBLE"]
    assert result["picked_action"] == "best"
    assert result["score"] == 0
    assert result["spent"] == {"complete_panels": 3, "wall_s": 8.0, "core_s": 8.0}


def test_complete_panel_budget_stops_before_unaffordable_action():
    registered = rule(budget={"complete_panels": 3, "wall_s": 5.0, "core_s": 5.0})
    result = run(registered, question(registered), ["bad", "good", "best"])
    assert result["attempted"] == ["bad"]
    assert result["budget_stopped"] is True
    assert result["score"] == 1.0
    assert result["spent"]["wall_s"] == 4.0


def test_unresolved_consumes_slot_and_no_return_is_service_loss():
    registered = rule(budget={"complete_panels": 1, "wall_s": 12, "core_s": 12})
    q = question(registered, [action("x", "UNRESOLVED"), action("best", "FEASIBLE", 5)])
    result = run(registered, q, ["x", "best"])
    assert result["status"] == "BEST_KNOWN_ONLY"
    assert result["attempt_statuses"] == ["UNRESOLVED"]
    assert result["score"] == 1.0
    assert result["best_known_only"] is True


def test_none_feasible_and_correct_abstention_are_distinct_from_infeasible_label():
    registered = rule()
    q = question(registered, [action("bad", "INFEASIBLE")])
    result = run(registered, q, [])
    assert result["status"] == "NONE_FEASIBLE"
    assert result["correct_abstention"] is True
    assert result["score"] == 1.0
    assert result["buyer_unit_gap"] is None


def test_all_band_unresolved_has_full_service_loss_without_a_fake_optimum():
    registered = rule()
    q = question(registered, [action("uncertain", "UNRESOLVED")])
    result = run(registered, q, ["uncertain"])
    assert result["status"] == "UNRESOLVED_FAMILY"
    assert result["score"] == 1.0
    assert result["buyer_unit_gap"] is None
    assert v.aggregate(registered, [result])["unresolved_family"] == 1


@pytest.mark.parametrize(
    "status,expected",
    [("MISSING", "INSUFFICIENT_REFERENCE"), ("FAILED_INFRA", "FAILED_INFRA")],
)
def test_reference_failure_withholds_score_instead_of_penalizing(status, expected):
    registered = rule()
    q = question(registered, [action("missing", status)])
    result = run(registered, q, ["missing"])
    assert result["status"] == expected
    assert result["score"] is None
    assert result["attempted"] == ["missing"]


def test_missing_model_output_withholds_aggregate_on_all_offered_questions():
    registered = rule()
    q = question(registered)
    missing = v.evaluate_question(registered, q, None, None, eligibility(registered))
    report = v.aggregate(registered, [missing])
    assert report == {
        "schema": v.RESULT_SCHEMA,
        "rule_digest": registered["rule_digest"],
        "status": "INCOMPLETE_LEGS",
        "v": None,
        "offered": 1,
        "unscored": 1,
    }


def test_duplicate_spoof_and_digest_tamper_refused():
    registered = rule()
    with pytest.raises(v.VerifyAwareError):
        commitment(["good", "good"])
    with pytest.raises(v.VerifyAwareError):
        run(registered, question(registered), ["outside"])
    forged = question(registered)
    forged["weight"] = 99
    with pytest.raises(v.VerifyAwareError, match="digest"):
        run(registered, forged, ["good"])


def test_p_q_w_and_objective_units_are_separate_registration_bindings():
    registered = rule()
    for field in ("population_id", "proposal_id", "weight_law_id"):
        altered = question(registered, **{field: "wrong"})
        with pytest.raises(v.VerifyAwareError, match="decision law"):
            run(registered, altered, ["good"])
    with pytest.raises(v.VerifyAwareError, match="objective unit"):
        rule(regret_unit={"value": 10, "unit": "seconds"})


def test_prospective_candidate_uses_v_and_is_invariant_to_unused_predictions():
    registered = rule()
    q = question(registered)
    committed = commitment(["good", "best"])
    verifier = receipt(committed)
    report = v.score_model(
        registered,
        "toy-model",
        [q],
        {"q1": committed},
        {"q1": verifier},
        {"q1": eligibility(registered)},
    )
    assert report["aggregate"]["v"] == 1.0
    candidate = v.register_candidate(
        {
            "schema": v.CANDIDATE_SCHEMA,
            "candidate_id": "VERIFY-R",
            "rule_digest": registered["rule_digest"],
            "weights": {"v": 1.0},
            "gate_policy_id": registered["eligibility_policy_id"],
        }
    )
    assert v.candidate_score(candidate, registered, report["aggregate"]) == 1.0
    foreign = dict(report["aggregate"], rule_digest="sha256:foreign")
    with pytest.raises(v.VerifyAwareError, match="aggregate"):
        v.candidate_score(candidate, registered, foreign)
    assert (
        v.candidate_score(candidate, registered, report["aggregate"], accuracy=0.01)
        == 1.0
    )
    scored, verdicts = v.prospective_score_map(
        candidate,
        registered,
        {"passing": report["aggregate"], "gated": report["aggregate"]},
        {"passing": None, "gated": None},
        {"passing": "PASS", "gated": "FAIL"},
    )
    assert scored["passing"] == 1.0
    assert scored["gated"] < scored["passing"]
    assert verdicts["gated"] == "FAIL"
    blend = v.register_candidate(
        {
            "schema": v.CANDIDATE_SCHEMA,
            "candidate_id": "A-VERIFY-R",
            "rule_digest": registered["rule_digest"],
            "weights": {"a": 0.5, "v": 0.5},
            "gate_policy_id": registered["eligibility_policy_id"],
        }
    )
    assert (
        v.candidate_score(blend, registered, report["aggregate"], accuracy=None) is None
    )
    assert v.candidate_score(
        blend, registered, report["aggregate"], accuracy=0.25
    ) == pytest.approx(0.5)
    tampered = copy.deepcopy(candidate)
    tampered["weights"]["v"] = 0.5
    with pytest.raises(v.VerifyAwareError):
        v.candidate_score(tampered, registered, report["aggregate"])


def test_weighted_aggregate_and_normalized_gap():
    registered = rule()
    q = question(registered)
    good = run(registered, q, ["good"])
    assert good["buyer_unit_gap"] == 2
    assert good["score"] == 0.2
    q2 = question(registered, question_id="q2", weight=1.0)
    empty = v.evaluate_question(
        registered,
        q2,
        commitment([], question_id="q2"),
        receipt(commitment([], question_id="q2")),
        eligibility(registered),
    )
    aggregate = v.aggregate(registered, [good, empty])
    assert aggregate["mean_service_regret"] == pytest.approx(0.4666666666666666)


def test_receipt_binding_and_model_identity_are_required():
    registered = rule()
    q = question(registered)
    committed = commitment(["good"])
    forged = receipt(committed)
    forged["commitment_digest"] = "sha256:wrong"
    with pytest.raises(v.VerifyAwareError, match="bind commitment"):
        v.evaluate_question(registered, q, committed, forged, eligibility(registered))
    with pytest.raises(v.VerifyAwareError, match="model identity"):
        v.score_model(
            registered,
            "other-model",
            [q],
            {"q1": committed},
            {"q1": receipt(committed)},
            {"q1": eligibility(registered)},
        )
