"""Inert public Platform-shaped records; no worker, model or scientific gate."""

import base64
import hashlib
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from carbon.scoring.inference_pair_evidence import (
    PairEvidenceRefused,
    read_inference_pair,
)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def original(raw):
    return {"sha256": sha(raw), "raw_base64": base64.b64encode(raw).decode()}


def fixture(
    repeat=None, *, miner_lane=False, provenance="DIRECT_GRAPH_PUBLIC_INFERENCE"
):
    expected = {
        "recipe_digest": sha(b"inert-recipe"),
        "state_digest": sha(b"inert-state"),
        "inputs_digest": sha(b"inert-inputs"),
        "inference_image_id": sha(b"inert-image"),
        "operation_ids": ["operation-" + digit * 64 for digit in ("1", "2")],
        "ledger_identities": ["inert-primary-ledger", "inert-repeat-ledger"],
        "controls_digests": [
            sha(b"inert-primary-controls"),
            sha(b"inert-repeat-controls"),
        ],
        "input_shape": [3, 2],
        "output_shape": [3, 1],
        "input_dtype": "float32",
        "output_dtype": "float32",
    }
    phases = []
    for index, predictions in enumerate(
        ([[1.0], [2.0], [3.0]], repeat or [[1.0], [2.0], [3.0]])
    ):
        prediction_raw = encode(predictions)
        receipt = {
            "schema": "carbon.development.bundle-inference.v2",
            **{
                k: expected[k]
                for k in ("recipe_digest", "state_digest", "inputs_digest")
            },
            "predictions_digest": sha(prediction_raw),
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": {
                    "preprocess": 0.01,
                    "export": 0.02,
                    "inference": 0.03,
                    "postprocess": 0.04,
                },
                **{
                    k: deepcopy(expected[k])
                    for k in (
                        "input_shape",
                        "output_shape",
                        "input_dtype",
                        "output_dtype",
                    )
                },
            },
        }
        receipt_raw = encode(receipt)
        operation = expected["operation_ids"][index]
        phases.append(
            {
                "worker_operation": operation,
                "controls_digest": expected["controls_digests"][index],
                "originals": {
                    "predictions.json": original(prediction_raw),
                    "receipt.json": original(receipt_raw),
                },
                "accounting": {
                    "ledger_identity": expected["ledger_identities"][index],
                    "state": "SUCCEEDED",
                    "reservation": {
                        "numerical_milliseconds": 600000,
                        "research_trials": 1,
                    },
                    "actual": {
                        "numerical_milliseconds": 101 + index,
                        "retained_bytes": 0,
                    },
                    "worker_result": {
                        "schema": "carbon.autoresearch.worker-result.v1",
                        "provenance": provenance,
                        "output_digest": sha(b"inert-carrier-output"),
                        "operation": operation,
                        "files": {
                            "predictions.json": sha(prediction_raw),
                            "receipt.json": sha(receipt_raw),
                        },
                        "scientific_qualification": False,
                        "official_eligible": False,
                    },
                },
            }
        )
        if miner_lane:
            worker = phases[-1]["accounting"]["worker_result"]
            worker["lane"] = "MINER_RESEARCH_UNLIMITED"
            worker["output_digest"] = sha(
                json.dumps(
                    worker["files"],
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
    packet = {
        "schema": "carbon.source-free-inference-pair.v1",
        "execution_boundary": "C03_DOCKER",
        **{
            k: expected[k]
            for k in (
                "recipe_digest",
                "state_digest",
                "inputs_digest",
                "inference_image_id",
            )
        },
        "inference_operation_attempts": 2,
        "logical_prediction_rows_per_operation": 3,
        "logical_prediction_row_attempts": 6,
        "forward_calls": None,
        "elapsed_seconds": 0.3,
        "primary": phases[0],
        "repeat": phases[1],
        "scientific_qualification": False,
        "official_eligible": False,
    }
    kwargs = {"expected": expected}
    return packet, kwargs


def read(packet, kwargs):
    raw = encode(packet)
    return read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)


def change_receipt(phase, update):
    receipt = json.loads(
        base64.b64decode(phase["originals"]["receipt.json"]["raw_base64"])
    )
    update(receipt)
    raw = encode(receipt)
    phase["originals"]["receipt.json"] = original(raw)
    phase["accounting"]["worker_result"]["files"]["receipt.json"] = sha(raw)


def change_predictions(phase, raw):
    phase["originals"]["predictions.json"] = original(raw)
    phase["accounting"]["worker_result"]["files"]["predictions.json"] = sha(raw)
    change_receipt(phase, lambda r: r.update(predictions_digest=sha(raw)))


def test_equal_predictions_are_two_operations_with_real_costs_and_cold_timings():
    packet, kwargs = fixture()
    before = deepcopy((packet, kwargs))
    result = read(packet, kwargs)
    assert result.outputs == ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
    assert result.sha256 == sha(encode(packet))
    assert result.evidence["forward_calls"] is None
    assert result.evidence["logical_prediction_row_attempts"] == 6
    assert [row["actual"]["numerical_milliseconds"] for row in result.accounting] == [
        101,
        102,
    ]
    assert result.timing_s[0]["preprocess"] == 0.01
    assert result.timing_s[1]["postprocess"] == 0.04
    assert "research_trials" not in result.accounting[0]["actual"]
    assert result.accounting[0]["reservation"]["research_trials"] == 1
    assert (packet, kwargs) == before
    assert result.evidence["official_eligible"] is False


def test_genuine_different_predictions_are_preserved_without_a_gate_verdict():
    packet, kwargs = fixture([[1.0], [2.1], [3.0]])
    result = read(packet, kwargs)
    assert result.outputs[0] != result.outputs[1]
    assert result.outputs[1] == (1.0, 2.1, 3.0)
    assert not hasattr(result, "passed")


def test_explicit_zero_actual_cost_is_retained_without_filling_omitted_resources():
    packet, kwargs = fixture()
    packet["repeat"]["accounting"]["actual"] = {"numerical_milliseconds": 0}
    result = read(packet, kwargs)
    assert dict(result.accounting[1]["actual"]) == {"numerical_milliseconds": 0}


def test_detached_immutable_result_with_maintained_worker_accounting():
    packet, kwargs = fixture()
    result = read(packet, kwargs)
    packet["primary"]["accounting"]["actual"]["numerical_milliseconds"] = 999
    assert result.accounting[0]["actual"]["numerical_milliseconds"] == 101
    with pytest.raises(TypeError):
        result.evidence["primary"]["controls_digest"] = "changed"
    with pytest.raises(TypeError):
        result.accounting[0]["actual"]["numerical_milliseconds"] = 0
    with pytest.raises(FrozenInstanceError):
        result.sha256 = "changed"


@pytest.mark.parametrize("miner_lane", [False, True])
@pytest.mark.parametrize(
    "provenance", ["DIRECT_GRAPH_PUBLIC_INFERENCE", "DIRECT_BUNDLE_PUBLIC_INFERENCE"]
)
def test_both_maintained_worker_formats_and_inference_provenances(
    miner_lane, provenance
):
    packet, kwargs = fixture(miner_lane=miner_lane, provenance=provenance)
    result = read(packet, kwargs)
    assert result.outputs[0] == result.outputs[1]
    for accounting in result.accounting:
        worker = accounting["worker_result"]
        assert worker["provenance"] == provenance
        assert len(worker) == (8 if miner_lane else 7)
        if miner_lane:
            assert worker["lane"] == "MINER_RESEARCH_UNLIMITED"
            raw_files = json.dumps(
                dict(worker["files"]), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            assert worker["output_digest"] == sha(raw_files)
        else:
            # Legacy digest binds a separate carrier output, not its files JSON.
            assert worker["output_digest"] == sha(b"inert-carrier-output")


@pytest.mark.parametrize("mutation", ["lane", "digest", "newline_digest"])
def test_miner_lane_and_manifest_output_digest_are_verified(mutation):
    packet, kwargs = fixture(miner_lane=True)
    worker = packet["repeat"]["accounting"]["worker_result"]
    if mutation == "lane":
        worker["lane"] = "TEST_ONLY"
    elif mutation == "digest":
        worker["output_digest"] = sha(b"changed")
    else:
        worker["output_digest"] = sha(encode(worker["files"]))
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


def test_minimal_fixture_worker_metadata_is_not_c03_evidence():
    packet, kwargs = fixture()
    worker = packet["repeat"]["accounting"]["worker_result"]
    packet["repeat"]["accounting"]["worker_result"] = {
        key: worker[key] for key in ("operation", "files")
    }
    with pytest.raises(PairEvidenceRefused, match="worker_result_shape"):
        read(packet, kwargs)


@pytest.mark.parametrize("provenance", ["INERT_ONLY", "TEST_ONLY", "", None, []])
def test_c03_worker_requires_exact_maintained_inference_provenance(provenance):
    packet, kwargs = fixture()
    packet["repeat"]["accounting"]["worker_result"]["provenance"] = provenance
    with pytest.raises(PairEvidenceRefused, match="worker_result_identity"):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "field", ["recipe_digest", "state_digest", "inputs_digest", "inference_image_id"]
)
def test_repinned_envelope_cannot_change_registered_identity(field):
    packet, kwargs = fixture()
    packet[field] = sha(b"changed")
    with pytest.raises(PairEvidenceRefused, match="pair_binding"):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "mutation",
    ["same_operation", "wrong_operation", "ledger", "controls", "null_controls"],
)
def test_repinned_phase_cannot_replace_actual_registered_operations(mutation):
    packet, kwargs = fixture()
    phase = packet["repeat"]
    if mutation == "same_operation":
        phase["worker_operation"] = packet["primary"]["worker_operation"]
    elif mutation == "wrong_operation":
        phase["worker_operation"] = "operation-" + "a" * 64
    elif mutation == "ledger":
        phase["accounting"]["ledger_identity"] = "changed-ledger"
    else:
        phase["controls_digest"] = (
            None if mutation == "null_controls" else sha(b"changed")
        )
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "unknown",
        "none",
        "bool",
        "negative",
        "float",
        "extra",
        "worker_none",
        "worker_operation",
        "worker_files",
        "reservation",
    ],
)
def test_unknown_or_inconsistent_costs_are_not_zero_filled(mutation):
    packet, kwargs = fixture()
    cost = packet["repeat"]["accounting"]
    if mutation == "missing":
        del cost["actual"]["numerical_milliseconds"]
    elif mutation == "unknown":
        cost["state"] = "UNKNOWN"
    elif mutation == "none":
        cost["actual"] = None
    elif mutation in ("bool", "negative", "float"):
        cost["actual"]["numerical_milliseconds"] = {
            "bool": True,
            "negative": -1,
            "float": 1.0,
        }[mutation]
    elif mutation == "extra":
        cost["actual"]["invented_resource"] = 0
    elif mutation == "worker_none":
        cost["worker_result"] = None
    elif mutation == "worker_operation":
        cost["worker_result"]["operation"] = packet["primary"]["worker_operation"]
    elif mutation == "worker_files":
        cost["worker_result"]["files"]["receipt.json"] = sha(b"wrong")
    else:
        cost["reservation"]["research_trials"] = False
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "mutation",
    [
        "boundary",
        "qualification",
        "official",
        "rows",
        "attempts",
        "forward",
        "elapsed",
        "extra",
        "phase_extra",
    ],
)
def test_invalid_boundary_counts_or_extra_fields_refuse(mutation):
    packet, kwargs = fixture()
    changes = {
        "boundary": ("execution_boundary", "TEST_ONLY_LOCAL_RUNNER"),
        "qualification": ("scientific_qualification", True),
        "official": ("official_eligible", True),
        "rows": ("logical_prediction_rows_per_operation", 2),
        "attempts": ("logical_prediction_row_attempts", 2),
        "forward": ("forward_calls", 2),
        "elapsed": ("elapsed_seconds", -1),
        "extra": ("unexpected", 1),
    }
    if mutation == "phase_extra":
        packet["repeat"]["unexpected"] = 1
    else:
        key, value = changes[mutation]
        packet[key] = value
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "input",
        "state",
        "scope",
        "shape",
        "shape_bool",
        "dtype",
        "timing",
        "extra",
    ],
)
def test_receipt_binding_survives_repinning_all_its_raw_hashes(mutation):
    packet, kwargs = fixture()

    def update(receipt):
        if mutation == "schema":
            receipt["schema"] = "wrong"
        elif mutation in ("input", "state"):
            receipt[{"input": "inputs_digest", "state": "state_digest"}[mutation]] = (
                sha(b"changed")
            )
        elif mutation == "extra":
            receipt["unexpected"] = 0
        else:
            key, value = {
                "scope": ("scope", "FIXTURE_ONLY"),
                "shape": ("output_shape", [2, 1]),
                "shape_bool": ("output_shape", [3, True]),
                "dtype": ("output_dtype", "float64"),
                "timing": ("timing_s", {"inference": 0.1}),
            }[mutation]
            receipt["measurement"][key] = value

    change_receipt(packet["repeat"], update)
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


@pytest.mark.parametrize(
    "raw", [b"[[1],[2]]", b"[[true],[2],[3]]", b"[[NaN],[2],[3]]", b"[[1e999],[2],[3]]"]
)
def test_wrong_tensor_shape_or_non_numeric_output_is_refused(raw):
    packet, kwargs = fixture()
    change_predictions(packet["repeat"], raw)
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


def test_both_phases_are_fresh_repeats_and_a_changed_pair_needs_a_new_pin():
    """Both phases are new queries, never the graded original (the producer
    compares them with it). Changed bytes only read under a new trusted pin."""
    packet, kwargs = fixture()
    pinned = encode(packet)
    change_predictions(packet["primary"], encode([[9.0], [2.0], [3.0]]))
    with pytest.raises(PairEvidenceRefused, match="registered_digest"):
        read_inference_pair(encode(packet), registered_sha256=sha(pinned), **kwargs)
    evidence = read(packet, kwargs)
    assert evidence.outputs[0] == (9.0, 2.0, 3.0)


@pytest.mark.parametrize("mutation", ["schema", "official", "qualification", "extra"])
def test_worker_result_metadata_cannot_change_its_scope(mutation):
    packet, kwargs = fixture()
    worker = packet["repeat"]["accounting"]["worker_result"]
    key, value = {
        "schema": ("schema", "wrong-worker-result"),
        "official": ("official_eligible", True),
        "qualification": ("scientific_qualification", True),
        "extra": ("unexpected", 1),
    }[mutation]
    worker[key] = value
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


def test_receipt_original_has_independent_64k_byte_limit():
    packet, kwargs = fixture()
    raw = b" " * (64 * 1024 + 1)
    phase = packet["repeat"]
    phase["originals"]["receipt.json"] = original(raw)
    phase["accounting"]["worker_result"]["files"]["receipt.json"] = sha(raw)
    with pytest.raises(PairEvidenceRefused, match="original_bytes"):
        read(packet, kwargs)


@pytest.mark.parametrize("where", ["envelope", "receipt"])
def test_duplicate_keys_refuse_even_when_repinned(where):
    packet, kwargs = fixture()
    if where == "envelope":
        raw = encode(packet).rstrip()[:-1] + b',"schema":"duplicate"}'
        with pytest.raises(PairEvidenceRefused, match="duplicate_key"):
            read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)
    else:
        phase = packet["repeat"]
        old = base64.b64decode(phase["originals"]["receipt.json"]["raw_base64"])
        raw = old.rstrip()[:-1] + b',"schema":"duplicate"}'
        phase["originals"]["receipt.json"] = original(raw)
        phase["accounting"]["worker_result"]["files"]["receipt.json"] = sha(raw)
        with pytest.raises(PairEvidenceRefused, match="duplicate_key"):
            read(packet, kwargs)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "duplicate_operation", "duplicate_ledger", "null_controls"],
)
def test_expected_contract_is_closed_and_requires_actual_distinct_identities(mutation):
    packet, kwargs = fixture()
    expected = kwargs["expected"]
    if mutation == "missing":
        del expected["inputs_digest"]
    elif mutation == "extra":
        expected["unexpected"] = 1
    elif mutation == "duplicate_operation":
        expected["operation_ids"][1] = expected["operation_ids"][0]
    elif mutation == "duplicate_ledger":
        expected["ledger_identities"][1] = expected["ledger_identities"][0]
    else:
        expected["controls_digests"][0] = None
    with pytest.raises(PairEvidenceRefused):
        read(packet, kwargs)


def test_wrong_pin_original_hash_or_noncanonical_base64_refuses():
    packet, kwargs = fixture()
    raw = encode(packet)
    with pytest.raises(PairEvidenceRefused, match="registered_digest"):
        read_inference_pair(raw, registered_sha256=sha(b"wrong"), **kwargs)
    packet["repeat"]["originals"]["predictions.json"]["sha256"] = sha(b"wrong")
    with pytest.raises(PairEvidenceRefused, match="original_digest"):
        read(packet, kwargs)
    packet, kwargs = fixture()
    packet["repeat"]["originals"]["predictions.json"]["raw_base64"] += "\n"
    with pytest.raises(PairEvidenceRefused, match="original_encoding"):
        read(packet, kwargs)


@pytest.mark.parametrize("raw", [b"", b" " * (4 * 1024**2 + 1), b'{"x":NaN}'])
def test_raw_byte_bounds_and_nonfinite_json(raw):
    _packet, kwargs = fixture()
    with pytest.raises(PairEvidenceRefused):
        read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)


def per_case(packet):
    """The same pair as two runs of the graded per-case procedure: unmeasured
    v1 receipts (Validator, 2026-10-19: a repeat is the identical procedure)."""
    for name in ("primary", "repeat"):

        def unmeasured(receipt):
            receipt.pop("measurement")
            receipt["schema"] = "carbon.development.bundle-inference.v1"

        change_receipt(packet[name], unmeasured)
    return packet


def test_a_per_case_pair_repeats_the_graded_procedure_and_carries_no_timing():
    packet, kwargs = fixture()
    result = read(per_case(packet), {**kwargs, "procedure": "per_case"})
    assert result.outputs == ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
    assert result.timing_s == (None, None)


def test_a_pair_of_the_other_procedure_is_refused():
    packet, kwargs = fixture()
    with pytest.raises(PairEvidenceRefused, match="receipt_shape"):
        read(packet, {**kwargs, "procedure": "per_case"})
    packet, kwargs = fixture()
    with pytest.raises(PairEvidenceRefused, match="receipt_shape"):
        read(per_case(packet), kwargs)
    with pytest.raises(PairEvidenceRefused, match="pair_procedure"):
        read(fixture()[0], {**fixture()[1], "procedure": "interleaved"})
