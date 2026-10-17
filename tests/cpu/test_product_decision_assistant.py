"""Synthetic selected-pick, budget, provenance and hold interactions only."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from carbon.product.decision_assistant import (
    REGRET_SCHEMA,
    AssistantConfigurationError,
    DecisionAssistant,
    SearchResult,
    assess_finite_bank,
)
from carbon.product.decision_assistant.demo import demonstrate, fixture
from carbon.product.decision_assistant.public_panel import inspect_bytes
from carbon.product.envelope_guard import EnvelopeGuard, GuardConfigurationError
from carbon.product.envelope_guard.configuration import digest
from carbon.product.envelope_guard.demo import fixture_inputs, repin


def test_selected_trust_picks_are_reverified_and_adverse_results_retained():
    inputs = fixture()
    calls = []
    original = inputs["reference"].solve
    inputs["reference"] = replace(
        inputs["reference"], solve=lambda q: (calls.append(q["c1"]), original(q))[1]
    )
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    r = result.to_dict()
    assert r["provisional_top_k"] == ["fast", "base", "slow"]
    assert [p["id"] for p in r["verification_plan"]] == ["fast", "slow", "base"]
    assert calls == [1.4, 0.8, 1.0]
    base = next(row for row in r["candidates"] if row["id"] == "base")
    assert base["guard"]["verdict"] == "TRUST"
    assert base["reference"]["status"] == "INFEASIBLE"
    assert r["recommendation"] == "slow"
    assert r["selected_pick_false_feasibility"] == {
        "selected": 3,
        "resolved": 3,
        "unresolved": 0,
        "false_feasible": 2,
        "fraction_conditional_on_resolved": 2 / 3,
    }
    assert r["spent"]["model_calls"] == 27
    assert r["spent"]["reference_calls"] == 3
    assert r["expected_regret"]["value"] is None
    assessment = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert (
        assessment["complete"] is True
        and assessment["global_optimum_established"] is False
    )
    assert assessment["realized_regret"] == {
        "value": 0.0,
        "unit": "s",
        "status": "MEASURED",
    }
    assert calls == [1.4, 0.8, 1.0, 0.8, 1.0, 1.4]  # independent post-freeze calls


def test_lower_budget_keeps_adverse_solver_only_comparison_and_unknown_regret():
    report = demonstrate()
    curve = report["equal_budget_replay"]["curves"][0]
    assert report["equal_budget_replay"]["cost_basis"] == "ASSUMPTION"
    assert curve["estimates"]["solver_alone"]["feasible_pick_fraction"] == 1.0
    assert curve["estimates"]["model_then_solver"]["feasible_pick_fraction"] == 0.0
    assert curve["estimates"]["model_then_solver"]["mean_regret_conditional"] is None
    assert (
        curve["bootstrap_ci"] is None
    )  # one synthetic cluster is not independent evidence
    assert report["real_battery_comparison"]["accepted"] is False


@pytest.mark.parametrize(
    "hold", ["SOLVER_NOT_ACCEPTED", "UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"]
)
def test_reference_hold_stops_before_model_or_reference_calls(hold):
    inputs = fixture()

    def forbidden(_):
        raise AssertionError("SYNTHETIC_SECRET_CANARY")

    inputs["model"] = replace(inputs["model"], predict=forbidden)
    inputs["reference"] = replace(inputs["reference"], status=hold, solve=forbidden)
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["recommendation"] is None and hold in r["reasons"]
    assert r["spent"]["model_calls"] == r["spent"]["reference_calls"] == 0
    assert "SYNTHETIC_SECRET_CANARY" not in json.dumps(r)


def test_missing_executor_returns_plan_never_verified_recommendation():
    inputs = fixture()
    inputs["reference"] = None
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["verification_plan"] and all(
        p["must_verify"] for p in r["verification_plan"]
    )
    assert r["recommendation"] is None and not r["verification_complete"]
    assert "REFERENCE_EXECUTOR_MISSING" in r["reasons"]


@pytest.mark.parametrize(
    "hold", ["SOLVER_NOT_ACCEPTED", "UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"]
)
def test_assessment_cannot_replace_a_frozen_reference_hold_with_ready(hold):
    inputs = fixture()
    ready = inputs["reference"]
    inputs["reference"] = replace(ready, status=hold)
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    ready = replace(ready, solve=lambda _: pytest.fail("frozen hold bypassed"))
    report = assess_finite_bank(
        assistant, result, reference=ready, budget=inputs["budget"]
    )
    assert report["reference_status"] == hold and report["reference_holds"] == [hold]
    assert not report["complete"] and report["spent"]["reference_calls"] == 0
    assert (
        report["realized_regret"]["value"] is None
        and not report["none_feasible_established"]
    )
    assert report["reference_runtime"] == ready.runtime_digest


def test_assessment_preserves_the_guard_reference_hold_without_an_executor():
    inputs = fixture()
    ready = inputs["reference"]
    inputs["reference"] = None
    inputs["guard_inputs"]["reference"]["status"] = "UNRESOLVED"
    repin({**inputs["guard_inputs"], "model": inputs["model"]})
    ready = replace(
        ready,
        record_digest=digest(inputs["guard_inputs"]["reference"]),
        solve=lambda _: pytest.fail("guard hold bypassed"),
    )
    assistant = DecisionAssistant(**inputs)
    report = assess_finite_bank(
        assistant, assistant.run(), reference=ready, budget=inputs["budget"]
    )
    assert report["reference_status"] == "UNRESOLVED"
    assert (
        report["spent"]["reference_calls"] == 0
        and report["realized_regret"]["value"] is None
    )


def test_public_record_replay_cannot_be_called_fresh_verification():
    inputs = fixture()
    inputs["reference"] = replace(inputs["reference"], kind="PUBLIC_RECORD_REPLAY")
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    r = result.to_dict()
    assert r["recommendation"] is None and r["verified_order"] == []
    assert r["reference_observation_order"] == ["slow"]
    assert "REFERENCE_REPLAY_NOT_FRESH_VERIFICATION" in r["reasons"]
    report = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert report["observations_complete"] and not report["complete"]
    assert report["realized_regret"]["value"] is None


def test_synthetic_guard_cannot_be_relabelled_as_registered_search():
    inputs = fixture()
    inputs["question_law"]["basis"] = "REGISTERED_DEVELOPMENT"
    inputs["budget"]["basis"] = "MEASURED_DEVELOPMENT"
    inputs["reference"] = None
    with pytest.raises(
        AssistantConfigurationError, match="fixture_guard_scope_mismatch"
    ):
        DecisionAssistant(**inputs)


def test_exhausted_verification_budget_retains_unresolved_picks_and_abstains():
    inputs = fixture()
    inputs["budget"]["cap"]["solver_evaluations"] = 1
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["spent"]["reference_calls"] == 1 and r["recommendation"] is None
    assert not r["verification_complete"]
    assert r["selected_pick_false_feasibility"]["unresolved"] == 2
    assert "BUDGET_DEFERRED" in r["reasons"]


@pytest.mark.parametrize(
    "key,value", [("max_guard_queries", 1), ("max_model_calls", 1)]
)
def test_model_and_probe_quota_defer_unsearched_work(key, value):
    inputs = fixture()
    inputs["budget"][key] = value
    r = DecisionAssistant(**inputs).run().to_dict()
    assert not r["search_complete"] and r["recommendation"] is None
    assert r["spent"]["model_calls"] == (9 if key == "max_guard_queries" else 0)
    assert "MODEL_OR_GUARD_BUDGET_EXHAUSTED" in r["reasons"]


def test_core_budget_is_an_independent_pre_call_limit():
    inputs = fixture()
    inputs["budget"]["cap"]["core_s"] = 0.25
    inputs["budget"]["guard_bound"]["core_s"] = 0.5
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["spent"]["model_calls"] == 0 and r["recommendation"] is None
    assert "BUDGET_DEFERRED" in r["reasons"]


def test_actual_planning_overrun_retains_calls_and_prevents_action(monkeypatch):
    inputs = fixture()
    inputs["budget"]["guard_bound"] = {"wall_s": 1e-6, "core_s": 1e-6}
    assistant = DecisionAssistant(**inputs)
    clock = iter(i * 0.01 for i in range(100))
    from carbon.product.decision_assistant import core

    monkeypatch.setattr(core, "_now", lambda: (next(clock), next(clock)))
    r = assistant.run().to_dict()
    assert r["spent"]["guard_queries"] == 1 and r["spent"]["model_calls"] == 9
    assert r["spent"]["budget_or_bound_exceeded"] and r["recommendation"] is None
    assert r["spent"]["wall_s"] > inputs["budget"]["guard_bound"]["wall_s"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda x: x["question_law"].update(scope="LIVE"),
        lambda x: x["question_law"].update(basis="PRODUCTION"),
        lambda x: x["question_law"].update(k=True),
        lambda x: x["question_law"]["actions"].append(
            copy.deepcopy(x["question_law"]["actions"][0])
        ),
        lambda x: x["question_law"]["actions"][0]["query"].update(c1=float("inf")),
        lambda x: x["question_law"]["constraints"][0].update(limit=True),
        lambda x: x["question_law"]["constraints"][0].update(relation="eval"),
        lambda x: x["question_law"]["units"].update(t_amb_c="F"),
        lambda x: x["budget"].update(scope="LIVE"),
        lambda x: x["budget"]["cap"].update(core_s=0),
        lambda x: x["budget"].update(max_model_calls=False),
        lambda x: x.update(model=lambda _: None),
        lambda x: x.update(measurement=lambda _: None),
        lambda x: x.update(reference=lambda _: None),
        lambda x: x.update(
            reference=replace(x["reference"], image_digest="sha256:" + "f" * 64)
        ),
    ],
)
def test_closed_nominal_configuration_refuses_bad_or_incompatible_inputs(mutation):
    inputs = fixture()
    mutation(inputs)
    with pytest.raises(AssistantConfigurationError):
        DecisionAssistant(**inputs)


@pytest.mark.parametrize("where", ["question_law", "budget"])
def test_missing_authority_is_a_hold_not_a_default_policy(where):
    inputs = fixture()
    inputs[where]["authority_ref"] = None
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["spent"]["model_calls"] == 0 and r["recommendation"] is None
    assert "QUESTION_OR_BUDGET_HUMAN_INPUT" in r["reasons"]


def test_unknown_constraint_is_unresolved_not_feasible():
    inputs = fixture()
    inputs["question_law"]["constraints"][0]["limit"] = None
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["provisional_top_k"] == [] and r["recommendation"] is None
    assert all(row["predicted"]["status"] == "UNRESOLVED" for row in r["candidates"])


@pytest.mark.parametrize(
    "fault", ["query", "image", "shape", "failed_reference", "exception"]
)
def test_reference_faults_never_become_model_failure_or_verified_choice(fault):
    inputs = fixture()
    original = inputs["reference"].solve

    def bad(query):
        row = original(query)
        if fault == "exception":
            raise RuntimeError("SYNTHETIC_SECRET_CANARY")
        if fault == "query":
            return replace(row, query_digest="sha256:" + "f" * 64)
        if fault == "image":
            return replace(row, image_digest="sha256:" + "f" * 64)
        if fault == "failed_reference":
            return replace(row, status="FAILED_REFERENCE", prediction=None)
        row.prediction.outputs["voltage_v"].pop()
        return row

    inputs["reference"] = replace(inputs["reference"], solve=bad)
    r = DecisionAssistant(**inputs).run().to_dict()
    assert r["recommendation"] is None and not r["verification_complete"]
    assert all(
        row["reference"].get("candidate_failure") is False for row in r["candidates"]
    )
    assert "SYNTHETIC_SECRET_CANARY" not in json.dumps(r)


def test_result_and_configuration_are_snapshots_and_replay_ignores_timing():
    inputs = fixture()
    assistant = DecisionAssistant(**inputs)
    inputs["question_law"]["actions"][0]["query"]["c1"] = 2.0
    result = assistant.run()
    copy_result = result.to_dict()
    copy_result["recommendation"] = "fast"
    assert result.to_dict()["recommendation"] == "slow"
    with pytest.raises(FrozenInstanceError):
        result._body = {}
    assert assistant.run().to_dict()["audit_digest"] == result.to_dict()["audit_digest"]
    with pytest.raises(AssistantConfigurationError, match="result_digest_mismatch"):
        SearchResult(copy_result)


def test_expected_regret_requires_exact_external_assessment_and_stays_distinct():
    inputs = fixture()
    assistant = DecisionAssistant(**inputs)
    evidence = {
        "schema": REGRET_SCHEMA,
        "scope": "DEVELOPMENT",
        "role": "INDEPENDENT_ASSESSMENT",
        "pins": assistant.regret_pins,
        "source_digest": digest({"synthetic_assessment": "not-a-study"}),
        "sample_count": 20,
        "value": 2.0,
        "interval": [1.0, 3.0],
        "unit": "s",
        "method": "fixture-joint-interval",
        "confidence": 0.95,
    }
    r = assistant.run(expected_regret_evidence=evidence).to_dict()
    assert r["expected_regret"]["value"] == 2.0
    assert r["realized_regret"]["value"] is None
    assert r["qualification_claim"] is False
    evidence["pins"]["budget_digest"] = "sha256:" + "f" * 64
    with pytest.raises(AssistantConfigurationError, match="regret_identity_mismatch"):
        assistant.run(expected_regret_evidence=evidence)


def test_incomplete_or_failed_oracle_never_reports_zero_regret_or_none_feasible():
    inputs = fixture()
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    budget = copy.deepcopy(inputs["budget"])
    budget["cap"]["solver_evaluations"] = 1
    r = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=budget
    )
    assert r["complete"] is False and r["realized_regret"]["value"] is None
    assert r["none_feasible_established"] is False


def test_undeclared_reference_applicability_blocks_search_and_oracle():
    from carbon.challenge_validator.validity import Undeclared

    inputs = fixture()
    inputs["guard_inputs"]["reference_validity"] = Undeclared(
        "Actual battery physical applicability remains undeclared", "science"
    )
    inputs["reference"] = replace(
        inputs["reference"], solve=lambda _: pytest.fail("out-of-scope reference call")
    )
    repin({**inputs["guard_inputs"], "model": inputs["model"]})
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    assert result.to_dict()["verification_plan"] == []
    report = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert report["spent"]["reference_calls"] == report["observed"] == 0
    assert (
        report["realized_regret"]["value"] is None
        and not report["none_feasible_established"]
    )


def test_oracle_respects_reference_envelope_even_for_unselected_candidates():
    inputs = fixture()
    inputs["question_law"]["actions"][2]["query"]["c1"] = 3.0
    seen = []
    original = inputs["reference"].solve
    inputs["reference"] = replace(
        inputs["reference"], solve=lambda q: (seen.append(q["c1"]), original(q))[1]
    )
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    assert (
        next(r for r in result.to_dict()["candidates"] if r["id"] == "fast")["guard"][
            "verdict"
        ]
        == "REFUSE"
    )
    report = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert 3.0 not in seen and report["complete"] is False
    assert report["realized_regret"]["value"] is None


def test_none_feasible_requires_complete_resolved_finite_bank():
    inputs = fixture()
    inputs["question_law"]["constraints"][0]["limit"] = 20.0
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    assert result.to_dict()["recommendation"] is None
    report = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert report["complete"] and report["none_feasible_established"]
    assert report["realized_regret"]["value"] is None


def test_no_io_occurs_in_search_or_assessment(monkeypatch):
    import builtins
    import socket
    import subprocess

    inputs = fixture()
    assistant = DecisionAssistant(**inputs)

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = assistant.run()
    report = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert result.to_dict()["recommendation"] == "slow" and report["complete"]


def test_native_v2_map_receipt_is_revalidated_and_cannot_be_tampered():
    from carbon.trust_map.acceptance import load_acceptance

    inputs = fixture_inputs()
    image = "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
    criteria = "sha256:2182e04bce3612f898e00184ce1e491cca8a54334192e35c4f2cd6fc1d1870c5"
    # Check historical document compatibility only, with synthetic values. This
    # does not supersede the owner's current real-panel solver acceptance hold.
    receipt = load_acceptance("battery-v3", image, criteria)
    inputs["trust_map"]["schema"] = "carbon.trust-map.v2"
    inputs["trust_map"]["reference_verification"] = receipt
    inputs["reference"]["image_digest"] = inputs["contract"]["reference_image"] = image
    for law in inputs["contract"]["laws"]:
        law["calibration"]["image_digest"] = image
    EnvelopeGuard(**repin(inputs))
    inputs["trust_map"]["reference_verification"]["link_digest"] = "sha256:" + "f" * 64
    with pytest.raises(
        GuardConfigurationError, match="map_acceptance_receipt_mismatch"
    ):
        EnvelopeGuard(**repin(inputs))


@pytest.mark.parametrize("basis", ["SYNTHETIC_FIXTURE", "REGISTERED_DEVELOPMENT"])
def test_legacy_map_fixture_cannot_be_used_as_development_acceptance(basis):
    inputs = fixture_inputs()
    inputs["policy"]["basis"] = basis
    inputs["trust_map"]["schema"] = "carbon.trust-map.v1"
    inputs["trust_map"]["reference_verification"] = {
        "state": "PASS",
        "accepted_development_pass": True,
        "image_digest": inputs["contract"]["reference_image"],
        "evidence": "SYNTHETIC_LEGACY_BOOLEAN_NOT_ACCEPTANCE",
    }
    with pytest.raises(GuardConfigurationError):
        EnvelopeGuard(**repin(inputs))


def repin_assistant(inputs):
    repin({**inputs["guard_inputs"], "model": inputs["model"]})
    inputs["reference"] = replace(
        inputs["reference"], record_digest=digest(inputs["guard_inputs"]["reference"])
    )
    return inputs


@pytest.mark.parametrize(
    "conditions,observables,expected_calls",
    [
        ({"c1": 1.0}, None, [1.0]),
        ({"c1": None}, None, []),
        ({"t_end": 0.375}, None, []),
        ({}, ["voltage_v"], []),
    ],
)
def test_independent_assessment_enforces_frozen_reference_use_scope(
    conditions, observables, expected_calls
):
    inputs = fixture()
    scope = inputs["guard_inputs"]["reference"]["acceptance_scope"]
    scope["application_conditions"] = conditions
    if observables is not None:
        scope["observables"] = observables
    repin_assistant(inputs)
    calls = []
    solve = inputs["reference"].solve
    inputs["reference"] = replace(
        inputs["reference"], solve=lambda q: (calls.append(q["c1"]), solve(q))[1]
    )
    assistant = DecisionAssistant(**inputs)
    # Mutating caller-owned scope after construction cannot widen assessment.
    scope["application_conditions"] = {}
    scope["observables"] = list(inputs["guard_inputs"]["contract"]["outputs"])
    result = assistant.run()
    assert calls == expected_calls
    calls.clear()
    assessed = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert calls == expected_calls
    assert assessed["spent"]["reference_calls"] == len(expected_calls)
    assert not assessed["complete"] and not assessed["none_feasible_established"]
    assert assessed["realized_regret"]["value"] is None
    unresolved = [
        r for r in assessed["rows"] if r["reference"]["status"] == "UNRESOLVED"
    ]
    assert len(unresolved) == 3 - len(expected_calls)
    assert all(
        r["reference"]["reason"] == "REFERENCE_ACCEPTANCE_SCOPE_MISMATCH"
        and r["reference"]["candidate_failure"] is False
        for r in unresolved
    )


def test_mms_conditions_are_audited_without_restricting_independent_assessment():
    from carbon.trust_map.acceptance import load_acceptance

    inputs = fixture()
    image = "sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675"
    criteria = "sha256:ce1cdee81369d5ad21446ec8cfb165ac13f1b8c49aad0d328a0a2fcd2dab77fe"
    native = load_acceptance("f02", image, criteria)
    g = inputs["guard_inputs"]
    # Battery-shaped arithmetic around genuine public f02 metadata; no f02 solve.
    g["contract"].update(family="f02", reference_image=image)
    g["policy"]["b9"] = None
    for law in g["contract"]["laws"]:
        law["calibration"]["image_digest"] = image
    g["reference"].update(
        image_digest=image,
        criteria_digest=criteria,
        code_verification_ref=native["link_digest"],
    )
    g["reference"]["acceptance_scope"].update(
        family="f02", verification_conditions=copy.deepcopy(native["conditions"])
    )
    g["trust_map"]["reference_verification"] = native
    solve = inputs["reference"].solve
    inputs["reference"] = replace(
        inputs["reference"],
        image_digest=image,
        solve=lambda q: replace(solve(q), image_digest=image),
    )
    repin_assistant(inputs)
    assistant = DecisionAssistant(**inputs)
    result = assistant.run()
    guards = [r["guard"] for r in result.to_dict()["candidates"]]
    assert all(g["code_verification"]["conditions"] == {"t_end": 0.375} for g in guards)
    assert all(
        g["reference"]["acceptance_scope"]["application_conditions"] == {}
        for g in guards
    )
    assert all(
        g["reference"]["observables_basis"] == "HOST_DECLARED_NOT_VERIFIED_COVERAGE"
        for g in guards
    )
    assert all(not g["qualification_claim"] for g in guards)
    assessed = assess_finite_bank(
        assistant, result, reference=inputs["reference"], budget=inputs["budget"]
    )
    assert assessed["complete"] and assessed["spent"]["reference_calls"] == 3


def test_b9_guard_evidence_survives_assistant_audit_and_pick_verification():
    inputs = fixture()
    predict = inputs["model"].predict

    def below_ambient(query):
        prediction = predict(query)
        outputs = copy.deepcopy(prediction.outputs)
        outputs["temperature_c"][-1] = query["t_amb_c"] - 0.101
        return replace(prediction, outputs=outputs)

    inputs["model"] = replace(inputs["model"], predict=below_ambient)
    repin_assistant(inputs)
    result = DecisionAssistant(**inputs).run()
    body = result.to_dict()
    base = next(row for row in body["candidates"] if row["id"] == "base")
    guard = base["guard"]
    assert guard["schema"] == "carbon.product.guard-receipt.v4"
    assert guard["verdict"] == "VERIFY" and "B9_BELOW_AMBIENT" in guard["reasons"]
    assert guard["b9_policy"] == {
        "threshold_c": 0.1,
        "decision_id": "OWNER-PHYSICS-GATES-01",
    }
    check = next(c for c in guard["checks"] if c["check"] == "policy.B9")
    assert check["max_deficit_c"] == 0.101 and check["threshold_c"] == 0.1
    assert (
        check["advisory"] and not check["exam_gate"] and not check["candidate_failure"]
    )
    assert (
        guard["independent_pick_verification_required"]
        and not guard["qualification_claim"]
    )
    assert body["spent"]["reference_calls"] == 3
    assert base["reference"]["status"] == "INFEASIBLE"
    guard["b9_policy"]["threshold_c"] = 100.0
    assert (
        next(r for r in result.to_dict()["candidates"] if r["id"] == "base")["guard"][
            "b9_policy"
        ]["threshold_c"]
        == 0.1
    )


def public_source():
    image = "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:" + "a" * 64
    lock = "sha256:" + "b" * 64
    row = {
        "case_id": "public-fixture",
        "status": "OK",
        "wall_s": 12.0,
        "timing_s": {"build": 1.0, "solve": 10.0},
        "solver_provenance": {
            "solver_image": image,
            "overlay_lock_sha256": lock,
            "pybamm": "fixture-version",
        },
    }
    line = json.dumps(row, sort_keys=True).encode()
    records = line + b"\n"
    manifest = {
        "schema": "carbon.battery.physics-calibration-manifest.v1",
        "scope": "PUBLIC_DEVELOPMENT; SYNTHETIC_TEST",
        "counts": {"OK": 1},
        "missing": [],
        "plan": {},
        "records": {row["case_id"]: hashlib.sha256(line).hexdigest()},
        "records_file_sha256": hashlib.sha256(records).hexdigest(),
        "solver": {
            "image": image,
            "overlay_lock_sha256": lock,
            "overlay_verified": {"versions": {"pybamm": "fixture-version"}},
        },
    }
    return json.dumps(manifest).encode(), records


def test_public_panel_cannot_convert_wall_or_memory_into_core_or_acceptance():
    manifest, records = public_source()
    r = inspect_bytes(
        manifest, records, expected_manifest_sha256=hashlib.sha256(manifest).hexdigest()
    )
    assert r["solver_acceptance"]["status"] == "SOLVER_NOT_ACCEPTED"
    assert r["solver_acceptance"]["accepted"] is False
    assert r["wall_cost_estimate"]["median"] == 12.0
    assert (
        r["cpu_core_seconds"]["value"] is None
        and r["real_battery_comparison"]["regret"] is None
    )


@pytest.mark.parametrize("fault", ["bytes", "scope", "provenance", "row_digest"])
def test_public_panel_rejects_mismatched_or_private_inputs(fault):
    manifest, records = public_source()
    m, row = json.loads(manifest), json.loads(records)
    if fault == "bytes":
        records += b" "
    elif fault == "scope":
        m["scope"] = "PRIVATE"
    elif fault == "provenance":
        row["solver_provenance"]["solver_image"] = "SYNTHETIC_CANARY"
        line = json.dumps(row, sort_keys=True).encode()
        records = line + b"\n"
        m["records"][row["case_id"]] = hashlib.sha256(line).hexdigest()
        m["records_file_sha256"] = hashlib.sha256(records).hexdigest()
    else:
        m["records"][row["case_id"]] = "f" * 64
    manifest = json.dumps(m).encode()
    with pytest.raises(AssistantConfigurationError) as error:
        inspect_bytes(
            manifest,
            records,
            expected_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
        )
    assert "SYNTHETIC_CANARY" not in str(error.value)
