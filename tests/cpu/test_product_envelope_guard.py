"""Public battery-interface synthetic tests; no solver/hidden/production authority."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import replace

import pytest

from carbon.challenge_validator import validity
from carbon.product.envelope_guard import (
    EnvelopeGuard,
    GuardConfigurationError,
    Prediction,
)
from carbon.product.envelope_guard.demo import (
    QUERY,
    UNITS,
    fixture_inputs,
    repin,
    toy_prediction,
)


def build(materials):
    return EnvelopeGuard(**repin(materials))


def result(materials, query=None):
    return build(materials).evaluate(QUERY if query is None else query, units=UNITS)


def test_public_battery_interface_in_envelope_is_scoped_fixture_trust():
    from carbon.battery.domain import GRID_POINTS, INPUT_BOUNDS

    materials = fixture_inputs()
    assert {
        k: (v["low"], v["high"]) for k, v in materials["envelope"]["inputs"].items()
    } == INPUT_BOUNDS
    receipt = result(materials)
    assert receipt["verdict"] == "TRUST"
    assert receipt["scope"] == "DEVELOPMENT"
    assert receipt["evidence_basis"] == "SYNTHETIC_FIXTURE"
    assert receipt["qualification_claim"] is False
    assert receipt["independent_pick_verification_required"] is True
    assert len(receipt["prediction"]["temperature_c"]) == GRID_POINTS
    assert receipt["probes"]["model_calls"] == receipt["probes"]["planned"] == 9
    assert receipt["latency_target_ms"] is None
    assert receipt["latency_target_basis"] == "HUMAN_INPUT"
    assert any(
        c["reason"] == "GAP_EXPLICIT_NO_INTERVALS_POLICY" for c in receipt["checks"]
    )


def test_outside_surrogate_envelope_requests_reference_without_model_call():
    def forbidden(_):
        raise AssertionError("unsupported model call")

    receipt = result(fixture_inputs(forbidden), {**QUERY, "c1": 2.2})
    assert receipt["verdict"] == "VERIFY"
    assert receipt["prediction"] is None
    assert receipt["probes"]["model_calls"] == 0
    assert receipt["checks"][0]["candidate_failure"] is False


def test_outside_reference_envelope_refuses_without_model_call():
    receipt = result(fixture_inputs(), {**QUERY, "c1": 3.0})
    assert receipt["verdict"] == "REFUSE"
    assert receipt["reasons"] == ["REFERENCE_APPLICABILITY_UNRESOLVED"]
    assert receipt["probes"]["model_calls"] == 0


def test_law_violation_only_at_a_neighbor_prevents_trust():
    def bad_neighbor(query):
        prediction = toy_prediction(query)
        if query["c1"] != QUERY["c1"]:
            prediction.outputs["temperature_c"][0] += 1.0
        return prediction

    receipt = result(fixture_inputs(bad_neighbor))
    assert receipt["verdict"] == "VERIFY"
    assert "ADOPTED_LAW_VIOLATION" in receipt["reasons"]
    laws = [c for c in receipt["checks"] if c["check"].startswith("law.")]
    assert any(c["outcome"] == "FAIL" and c["residual"] >= 1 for c in laws)
    assert receipt["probes"]["model_calls"] == 9


def test_low_trust_cell_prevents_trust_without_reinterpreting_the_map():
    materials = fixture_inputs()
    cell = next(c for c in materials["trust_map"]["cells"] if c["count"])
    cell["error"]["voltage_v"]["p90"] = 0.5
    before = copy.deepcopy(materials["trust_map"])
    receipt = result(materials)
    assert receipt["verdict"] == "VERIFY"
    assert "MAP_LOW_TRUST" in receipt["reasons"]
    assert materials["trust_map"] == before


def test_no_data_missing_map_or_insufficient_count_has_no_success_default():
    for kind in ("empty-cell", "missing-map", "min-count"):
        materials = fixture_inputs()
        query = QUERY
        if kind == "empty-cell":
            query = {**QUERY, "c1": 0.6}
        elif kind == "missing-map":
            materials["trust_map"] = None
        else:
            materials["policy"]["min_cell_count"] = 3
        receipt = result(materials, query)
        assert receipt["verdict"] == "VERIFY"
        assert any(
            c["check"] == "trust_map" and c["outcome"] == "UNRESOLVED"
            for c in receipt["checks"]
        )


def test_exact_upper_edges_use_native_last_bin_and_reduced_unique_probes():
    from carbon.battery.domain import INPUT_BOUNDS

    query = {k: bounds[1] for k, bounds in INPUT_BOUNDS.items()}
    receipt = result(fixture_inputs(query=query), query)
    assert receipt["verdict"] == "TRUST"
    assert receipt["probes"]["model_calls"] == 5
    assert {tuple(c["cell"]) for c in receipt["checks"] if "cell" in c} == {(2, 6, 5)}


def test_real_battery_undeclared_validity_remains_a_hold():
    materials = fixture_inputs()
    entry = validity.declaration("battery-fastcharge-ageing-development-v1")
    assert isinstance(entry, validity.Undeclared)
    materials.update(model_validity=entry, reference_validity=entry)
    receipt = result(materials)
    assert receipt["verdict"] == "REFUSE"
    assert receipt["probes"]["model_calls"] == 0
    assert receipt["checks"][0]["candidate_failure"] is False


@pytest.mark.parametrize(
    "declaration",
    [
        validity.NoPropertyModel(True),
        validity.NoPropertyModel(" "),
        validity.Undeclared(True, True),
        validity.Declared(
            (validity.ValidityModel("fixture", (("c1", 0.5, 2.0),), " "),)
        ),
    ],
)
def test_a_malformed_validity_basis_cannot_construct_a_guard(declaration):
    materials = fixture_inputs()
    materials["model_validity"] = declaration
    with pytest.raises(GuardConfigurationError):
        build(materials)


def test_unknown_surrogate_applicability_never_trusts_a_separately_supported_route():
    materials = fixture_inputs()
    materials["model_validity"] = validity.Undeclared(
        "fixture pending", "science owner"
    )
    assert result(materials)["verdict"] == "VERIFY"


def test_probe_outside_declared_validity_is_unresolved_not_a_law_failure():
    materials = fixture_inputs()
    materials["model_validity"] = validity.Declared(
        (
            validity.ValidityModel(
                "fixture-only",
                (("c1", 1.0, 1.2),),
                "SYNTHETIC_FIXTURE_NOT_PHYSICAL_VALIDITY",
            ),
        )
    )
    receipt = result(materials)
    assert receipt["verdict"] == "VERIFY"
    assert "PROBE_OUTSIDE_VALIDITY" in receipt["reasons"]
    assert not any(c["outcome"] == "FAIL" for c in receipt["checks"])


def test_unadopted_uncalibrated_definitions_never_force_verification_or_execution():
    def only_base(query):
        assert query == QUERY
        return toy_prediction(query)

    materials = fixture_inputs(only_base)
    for law in materials["contract"]["laws"]:
        law.update(
            status="DIAGNOSTIC",
            calibration=None,
            adoption_ref=None,
            type="balance",
            spec={"expression": "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE"},
        )
    materials["policy"]["max_model_calls"] = 1
    receipt = result(materials)
    assert receipt["verdict"] == "TRUST"
    assert receipt["probes"]["model_calls"] == 1
    assert all(
        c["verdict_input"] is False
        for c in receipt["checks"]
        if c["check"].startswith("law.")
    )
    assert "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE" not in json.dumps(receipt)


def test_missing_policy_or_authority_is_refuse_before_prediction():
    for missing in ("policy", "authority"):
        materials = fixture_inputs()
        if missing == "policy":
            materials["policy"] = None
        else:
            materials["policy"]["authority_ref"] = None
        receipt = result(materials)
        assert receipt["verdict"] == "REFUSE"
        assert receipt["reasons"] == ["GUARD_POLICY_HUMAN_INPUT"]
        assert receipt["probes"]["model_calls"] == 0


@pytest.mark.parametrize("state", ["UNRESOLVED", "FAILED_REFERENCE", "FAILED_INFRA"])
def test_reference_failures_keep_their_type_and_are_never_candidate_failures(state):
    materials = fixture_inputs()
    materials["reference"]["status"] = state
    receipt = result(materials)
    assert receipt["verdict"] == "REFUSE"
    assert receipt["checks"][0]["outcome"] == state
    assert receipt["checks"][0]["candidate_failure"] is False


def test_missing_reference_cannot_create_a_solver_request():
    materials = fixture_inputs()
    materials["reference"] = None
    receipt = result(materials)
    assert receipt["verdict"] == "REFUSE"
    assert receipt["reasons"] == ["REFERENCE_ACCEPTANCE_UNAVAILABLE"]


@pytest.mark.parametrize("value", [None, True, math.inf, math.nan, 10**1000])
def test_bad_query_values_refuse_without_input_or_exception_echo(value):
    receipt = result(fixture_inputs(), {**QUERY, "c1": value})
    assert receipt["verdict"] == "REFUSE"
    assert receipt["query_digest"] is None
    json.dumps(receipt, allow_nan=False)


def test_query_fields_and_units_are_closed():
    guard = build(fixture_inputs())
    for query, units in (
        ({**QUERY, "unregistered": "SYNTHETIC_CANARY"}, UNITS),
        (QUERY, {**UNITS, "t_amb_c": "F"}),
        ({k: v for k, v in QUERY.items() if k != "c2"}, UNITS),
    ):
        receipt = guard.evaluate(query, units=units)
        assert receipt["verdict"] == "REFUSE"
        assert "SYNTHETIC_CANARY" not in json.dumps(receipt)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m["contract"].update(scope="LIVE"),
        lambda m: m["policy"].update(scope="PRODUCTION"),
        lambda m: m["contract"]["laws"][0].update(type="balance"),
        lambda m: m["contract"]["laws"][0].update(adoption_ref=None),
        lambda m: m["contract"]["laws"][0].update(calibration=None),
        lambda m: m["contract"]["laws"][0]["calibration"].update(
            image_digest="sha256:" + "f" * 64
        ),
        lambda m: m["contract"]["laws"][0]["calibration"].update(tolerance=0.0001),
        lambda m: m["contract"]["laws"][0]["calibration"].update(unit="K"),
        lambda m: m["contract"]["laws"][0]["spec"].update(input="unknown"),
        lambda m: m["trust_map"]["source"].update(kind="PROTECTED"),
        lambda m: m["trust_map"]["reference_verification"].update(
            accepted_development_pass=False
        ),
        lambda m: m["trust_map"]["basis"].update(cases=999),
        lambda m: m["trust_map"]["cells"].pop(),
        lambda m: m["trust_map"].update(model="another-model"),
        lambda m: m["trust_map"]["spec"]["marginalized"].clear(),
        lambda m: m["trust_map"]["spec"]["outputs"]["plating_margin_v"].update(
            length=True
        ),
        lambda m: m["trust_map"]["spec"]["near_limit"][0].update(
            unregistered="SYNTHETIC_CANARY"
        ),
        lambda m: m["policy"]["map_limits"]["voltage_v"].update(unit="C"),
        lambda m: m["policy"]["probe_steps"].update(c1=0),
        lambda m: m["reference"].update(image_digest="sha256:" + "f" * 64),
    ],
)
def test_invalid_or_unbound_configuration_cannot_construct_a_guard(mutation):
    materials = fixture_inputs()
    mutation(materials)
    with pytest.raises(GuardConfigurationError):
        build(materials)


def test_policy_pin_mismatch_is_refused_even_with_valid_document_content():
    materials = fixture_inputs()
    materials["contract"]["version"] = "new-v2"
    with pytest.raises(GuardConfigurationError, match="policy_identity_mismatch"):
        EnvelopeGuard(**materials)


def test_a_raw_callable_cannot_replace_the_nominal_model_binding():
    materials = fixture_inputs()
    materials["model"] = toy_prediction
    with pytest.raises(GuardConfigurationError, match="nominal_model_binding_required"):
        EnvelopeGuard(**materials)


def test_configuration_is_snapshotted_and_receipt_mutation_does_not_change_it():
    materials = fixture_inputs()
    guard = EnvelopeGuard(**materials)
    before = guard.evaluate(QUERY, units=UNITS)
    materials["contract"]["laws"][0]["calibration"]["tolerance"] = 99
    materials["policy"]["map_limits"]["voltage_v"]["max_error_p90"] = 99
    materials["trust_map"]["cells"].clear()
    before["identities"]["contract"] = "SYNTHETIC_CANARY"
    after = guard.evaluate(QUERY, units=UNITS)
    assert after["verdict"] == "TRUST"
    assert "SYNTHETIC_CANARY" not in json.dumps(after)
    assert before["decision_digest"] == after["decision_digest"]


def test_same_query_replays_seed_probes_and_decision_independent_of_timing():
    guard = build(fixture_inputs())
    first = guard.evaluate(QUERY, units=UNITS)
    for _ in range(5):
        replay = guard.evaluate(dict(reversed(list(QUERY.items()))), units=UNITS)
        assert replay["probes"] == first["probes"]
        assert replay["decision_digest"] == first["decision_digest"]
        assert replay["verdict"] == first["verdict"]
    # Prospective v2 fixture identities; historical v1 records are not rescored.
    assert (
        first["probes"]["seed"]
        == "sha256:6b9f59285631794a36183c164e821774ebd724aafb7e8c224de29a9b0a57f46d"
    )
    assert (
        first["probes"]["digest"]
        == "sha256:d38a913bf2b5cb777a7df2adfcc195722db03ff418dd53c6db07568091bba962"
    )


def test_query_policy_or_contract_changes_change_probe_identity():
    baseline = result(fixture_inputs())
    for field in ("query", "policy", "contract"):
        materials = fixture_inputs()
        query = QUERY
        if field == "query":
            query = {**QUERY, "c1": 1.01}
        else:
            materials[field]["version"] = "fixture-v2"
        receipt = result(materials, query)
        assert receipt["probes"]["seed"] != baseline["probes"]["seed"]
        assert receipt["probes"]["digest"] != baseline["probes"]["digest"]


def test_exhausted_probe_budget_is_visible_and_cannot_be_passed():
    materials = fixture_inputs()
    materials["policy"]["max_model_calls"] = 1
    receipt = result(materials)
    assert receipt["verdict"] == "VERIFY"
    assert "MODEL_CALL_BUDGET_EXHAUSTED" in receipt["reasons"]
    assert receipt["probes"]["model_calls"] == receipt["probes"]["executed"] == 1
    assert receipt["probes"]["planned"] == 9


def test_model_exception_is_typed_infra_without_disclosing_details():
    def unavailable(_):
        raise RuntimeError("SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE")

    receipt = result(fixture_inputs(unavailable))
    assert receipt["verdict"] == "VERIFY"
    assert receipt["checks"][-1]["outcome"] == "FAILED_INFRA"
    assert receipt["checks"][-1]["candidate_failure"] is False
    assert receipt["prediction"] is None
    assert "SYNTHETIC_CANARY_NOT_FOR_DISCLOSURE" not in json.dumps(receipt)


def test_missing_nonfinite_or_wrong_prediction_shape_never_trusts():
    def unavailable(query):
        value = toy_prediction(query)
        value.outputs["voltage_v"] = [math.nan]
        return value

    receipt = result(fixture_inputs(unavailable))
    assert receipt["verdict"] == "VERIFY"
    assert receipt["reasons"] == ["MODEL_OUTPUT_UNAVAILABLE_OR_MALFORMED"]


def interval_prediction(query):
    value = toy_prediction(query)
    intervals = {}
    for name, output in value.outputs.items():
        values = output if isinstance(output, list) else [output]
        intervals[name] = {
            "lower": [v - 0.01 for v in values],
            "upper": [v + 0.01 for v in values],
        }
    return Prediction(value.outputs, intervals)


def test_required_missing_or_uncalibrated_intervals_cannot_be_trusted():
    materials = fixture_inputs()
    materials["policy"]["uncertainty"]["mode"] = "REQUIRED"
    assert result(materials)["verdict"] == "VERIFY"
    assert result(fixture_inputs(interval_prediction))["verdict"] == "VERIFY"


def calibrated_intervals(materials):
    materials["policy"]["uncertainty"] = {
        "mode": "REQUIRED",
        "calibration": {
            "image_digest": materials["reference"]["image_digest"],
            "record_digest": "sha256:" + "a" * 64,
        },
        "max_width": {
            name: {"unit": desc["unit"], "value": 0.1}
            for name, desc in materials["contract"]["outputs"].items()
        },
    }
    return materials


def test_calibrated_interval_policy_checks_width_in_native_units():
    materials = calibrated_intervals(fixture_inputs(interval_prediction))
    assert result(materials)["verdict"] == "TRUST"
    materials["policy"]["uncertainty"]["max_width"]["voltage_v"]["value"] = 0.001
    assert "INTERVAL_TOO_WIDE" in result(materials)["reasons"]


def test_derived_overflow_is_unresolved_and_the_receipt_remains_finite_json():
    def huge(query):
        value = toy_prediction(query)
        value.outputs["voltage_v"] = [-1e308] * len(value.outputs["voltage_v"])
        return value

    materials = fixture_inputs(huge)
    law = materials["contract"]["laws"][1]
    law["spec"].update(low=1e308, high=None)
    receipt = result(materials)
    assert "LAW_ARITHMETIC_UNRESOLVED" in receipt["reasons"]
    assert receipt["verdict"] == "VERIFY"
    json.dumps(receipt, allow_nan=False)


def test_challenge_neutral_projection_accepts_another_registered_identity():
    materials = fixture_inputs()
    materials["contract"]["challenge"] = "synthetic-other-challenge"
    materials["model"] = replace(materials["model"], model_id="other-fixture-model")
    materials["trust_map"]["model"] = "other-fixture-model"
    assert result(materials)["verdict"] == "TRUST"


def test_interval_width_overflow_is_unresolved_without_a_nonfinite_receipt():
    def huge_interval(query):
        prediction = interval_prediction(query)
        prediction.intervals["voltage_v"] = {
            "lower": [-1e308] * len(prediction.outputs["voltage_v"]),
            "upper": [1e308] * len(prediction.outputs["voltage_v"]),
        }
        return prediction

    receipt = result(calibrated_intervals(fixture_inputs(huge_interval)))
    assert receipt["verdict"] == "VERIFY"
    assert "INTERVAL_ARITHMETIC_UNRESOLVED" in receipt["reasons"]
    json.dumps(receipt, allow_nan=False)


def test_query_path_does_not_read_files_start_processes_or_send_network(monkeypatch):
    import builtins
    import socket
    import subprocess

    guard = build(fixture_inputs())

    def forbidden(*args, **kwargs):
        raise AssertionError("external I/O in query path")

    with monkeypatch.context() as local:
        local.setattr(builtins, "open", forbidden)
        local.setattr(socket, "create_connection", forbidden)
        local.setattr(subprocess, "run", forbidden)
        receipt = guard.evaluate(QUERY, units=UNITS)
        assert receipt["verdict"] == "TRUST"
        assert receipt["probes"]["model_calls"] == 9


def test_native_battery_v2_builder_receipt_is_consumed_by_guard(monkeypatch):
    from carbon.battery import trust_map as battery_map
    from carbon.trust_map.acceptance import load_acceptance
    from carbon.trust_map.core import MAP_SCHEMA, PANEL_SCHEMA

    produce = battery_map.build_battery_maps
    panels = []

    def capture(panel):
        panels.append(copy.deepcopy(panel))
        return produce(panel)

    monkeypatch.setattr(battery_map, "build_battery_maps", capture)
    materials = fixture_inputs()
    assert len(panels) == 1
    assert panels[0]["schema"] == PANEL_SCHEMA
    assert panels[0]["reference_verification"]["family"] == "battery-v3"
    assert materials["trust_map"]["schema"] == MAP_SCHEMA
    verification = materials["trust_map"]["reference_verification"]
    assert verification == load_acceptance(
        "battery-v3",
        materials["contract"]["reference_image"],
        verification["criteria_digest"],
    )
    receipt = result(materials)
    assert receipt["verdict"] == "TRUST"
    assert receipt["evidence_basis"] == "SYNTHETIC_FIXTURE"
    assert receipt["qualification_claim"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "legacy"),
        ("scope", "PRODUCTION"),
        ("family", "motor"),
        ("image_digest", "sha256:" + "f" * 64),
        ("criteria_digest", "sha256:" + "f" * 64),
        ("link_digest", "sha256:" + "f" * 64),
        ("decision", {"decision_id": "SYNTHETIC_CANARY_NOT_AN_ACCEPTANCE"}),
        ("conditions", {"not_registered": True}),
    ],
)
def test_tampered_v2_acceptance_receipt_is_refused_after_repin(field, value):
    materials = fixture_inputs()
    materials["trust_map"]["reference_verification"][field] = value
    with pytest.raises(GuardConfigurationError) as error:
        build(materials)
    assert "SYNTHETIC_CANARY" not in str(error.value)


def test_missing_acceptance_link_refuses_an_existing_map(tmp_path, monkeypatch):
    from functools import partial

    from carbon.trust_map.acceptance import load_acceptance

    materials = fixture_inputs()
    monkeypatch.setattr(
        "carbon.product.envelope_guard.configuration.load_acceptance",
        partial(load_acceptance, root=tmp_path),
    )
    with pytest.raises(GuardConfigurationError, match="map_verification_unavailable"):
        build(materials)


@pytest.mark.parametrize("basis", ["SYNTHETIC_FIXTURE", "REGISTERED_DEVELOPMENT", None])
@pytest.mark.parametrize("legacy", ["map_schema", "verification_header"])
def test_v1_maps_and_boolean_headers_have_no_fixture_exception(basis, legacy):
    materials = fixture_inputs()
    if basis is None:
        materials["policy"] = None
    else:
        materials["policy"]["basis"] = basis
    if legacy == "map_schema":
        materials["trust_map"]["schema"] = "carbon.trust-map.v1"
    else:
        materials["trust_map"]["reference_verification"] = {
            "state": "PASS",
            "accepted_development_pass": True,
            "image_digest": materials["contract"]["reference_image"],
            "evidence": "SYNTHETIC_CANARY_LEGACY_BOOLEAN",
        }
    with pytest.raises(GuardConfigurationError):
        build(materials)
