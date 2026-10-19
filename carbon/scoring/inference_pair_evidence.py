"""Strict, pure reader for Platform's public source-free inference pair v1.

The caller supplies a separately trusted envelope pin and already authenticated
primary originals. Matching hashes do not authenticate a caller or execution.
This source capability grants no gate, score or scientific acceptance; normal
receipt integration and Product runtime validation remain separate work.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from carbon.development_session.research_ledger import DIMENSIONS

SCHEMA = "carbon.source-free-inference-pair.v1"
_MAX_BYTES = 4 * 1024**2
_MAX_RECEIPT = 64 * 1024
_TIMINGS = {"preprocess", "export", "inference", "postprocess"}
_EXPECTED = {
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "inference_image_id",
    "operation_ids",
    "ledger_identities",
    "controls_digests",
    "input_shape",
    "output_shape",
    "input_dtype",
    "output_dtype",
}
_ENVELOPE = {
    "schema",
    "execution_boundary",
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "inference_image_id",
    "inference_operation_attempts",
    "logical_prediction_rows_per_operation",
    "logical_prediction_row_attempts",
    "forward_calls",
    "elapsed_seconds",
    "primary",
    "repeat",
    "scientific_qualification",
    "official_eligible",
}


class PairEvidenceRefused(ValueError):
    """Unavailable or inconsistent source evidence, never a candidate verdict."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InferencePairEvidence:
    evidence: Mapping
    outputs: tuple[tuple[float, ...], tuple[float, ...]]
    accounting: tuple[Mapping, Mapping]
    timing_s: tuple[Mapping, Mapping]
    sha256: str


def _require(ok, code):
    if not ok:
        raise PairEvidenceRefused(code)


def _shape(value, fields, code):
    _require(type(value) is dict and set(value) == fields, code)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _digest(value):
    return (
        type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
    )


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _parse(raw, limit, code):
    _require(type(raw) is bytes and 0 < len(raw) <= limit, code + "_bytes")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, code + "_duplicate_key")
            value[key] = item
        return value

    def number(text):
        value = float(text)
        _require(math.isfinite(value), code + "_nonfinite")
        return value

    def constant(_text):
        raise PairEvidenceRefused(code + "_nonfinite")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=number,
            parse_constant=constant,
        )
    except PairEvidenceRefused:
        raise
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        raise PairEvidenceRefused(code + "_json") from exc


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _flat(value, shape):
    if not shape:
        _require(_finite(value), "prediction_numeric")
        return (float(value),)
    _require(type(value) is list and len(value) == shape[0], "prediction_shape")
    return tuple(number for item in value for number in _flat(item, shape[1:]))


def _original(value, limit):
    _shape(value, {"sha256", "raw_base64"}, "original_shape")
    _require(_digest(value["sha256"]), "original_digest")
    _require(type(value["raw_base64"]) is str, "original_encoding")
    try:
        raw = base64.b64decode(value["raw_base64"].encode("ascii"), validate=True)
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise PairEvidenceRefused("original_encoding") from exc
    _require(
        base64.b64encode(raw).decode("ascii") == value["raw_base64"],
        "original_encoding",
    )
    _require(0 < len(raw) <= limit, "original_bytes")
    _require(_sha(raw) == value["sha256"], "original_digest")
    return raw


def _budget(value):
    _require(type(value) is dict and set(value) <= set(DIMENSIONS), "accounting_budget")
    _require(
        all(type(v) is int and v >= 0 for v in value.values()), "accounting_budget"
    )


def _accounting(value, ledger, operation, originals):
    _shape(
        value,
        {"ledger_identity", "state", "reservation", "actual", "worker_result"},
        "accounting_shape",
    )
    _require(value["ledger_identity"] == ledger, "accounting_identity")
    _require(value["state"] == "SUCCEEDED", "accounting_state")
    _budget(value["reservation"])
    _budget(value["actual"])
    _require("numerical_milliseconds" in value["actual"], "accounting_actual_missing")
    worker = value["worker_result"]
    full = {
        "operation",
        "files",
        "schema",
        "provenance",
        "output_digest",
        "scientific_qualification",
        "official_eligible",
    }
    _require(
        type(worker) is dict and set(worker) in (full, full | {"lane"}),
        "worker_result_shape",
    )
    _require(worker["operation"] == operation, "worker_result_operation")
    _require(
        worker["schema"] == "carbon.autoresearch.worker-result.v1"
        and type(worker["provenance"]) is str
        and worker["provenance"]
        in {"DIRECT_GRAPH_PUBLIC_INFERENCE", "DIRECT_BUNDLE_PUBLIC_INFERENCE"}
        and _digest(worker["output_digest"])
        and worker["scientific_qualification"] is False
        and worker["official_eligible"] is False,
        "worker_result_identity",
    )
    files = worker["files"]
    _require(
        type(files) is dict
        and {"predictions.json", "receipt.json"} <= set(files)
        and all(type(k) is str and bool(k) and _digest(v) for k, v in files.items()),
        "worker_result_files",
    )
    _require(
        all(files[name] == originals[name]["sha256"] for name in originals),
        "worker_result_files",
    )
    if "lane" in worker:
        _require(worker["lane"] == "MINER_RESEARCH_UNLIMITED", "worker_result_lane")
        # research_carrier._run_miner_lane uses profile.canonical(files): no LF.
        manifest = json.dumps(
            files, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        _require(
            worker["output_digest"] == _sha(manifest), "worker_result_output_digest"
        )
    # The legacy seven-field _run_locked result hashes output.read_bytes(),
    # which is not recoverable from its files map. Preserve its opaque digest;
    # its trusted envelope pin and both original file hashes remain checked.


def _expected(value):
    _shape(value, _EXPECTED, "expected_shape")
    _require(
        all(
            _digest(value[key])
            for key in (
                "recipe_digest",
                "state_digest",
                "inputs_digest",
                "inference_image_id",
            )
        ),
        "expected_digest",
    )
    for key in ("operation_ids", "ledger_identities", "controls_digests"):
        _require(type(value[key]) is list and len(value[key]) == 2, "expected_pair")
    _require(
        all(
            type(v) is str and re.fullmatch(r"operation-[0-9a-f]{64}", v) is not None
            for v in value["operation_ids"]
        )
        and value["operation_ids"][0] != value["operation_ids"][1],
        "expected_operations",
    )
    _require(
        all(type(v) is str and bool(v) for v in value["ledger_identities"])
        and value["ledger_identities"][0] != value["ledger_identities"][1],
        "expected_ledgers",
    )
    _require(all(_digest(v) for v in value["controls_digests"]), "expected_controls")
    for key in ("input_shape", "output_shape"):
        _require(
            type(value[key]) is list
            and bool(value[key])
            and all(type(v) is int and v > 0 for v in value[key]),
            "expected_shape",
        )
    _require(value["input_shape"][0] == value["output_shape"][0], "expected_rows")
    _require(
        all(
            type(value[k]) is str and bool(value[k])
            for k in ("input_dtype", "output_dtype")
        ),
        "expected_dtype",
    )


def _phase(value, expected, index):
    _shape(
        value,
        {"worker_operation", "controls_digest", "originals", "accounting"},
        "phase_shape",
    )
    _require(
        value["worker_operation"] == expected["operation_ids"][index], "phase_operation"
    )
    _require(
        value["controls_digest"] == expected["controls_digests"][index],
        "phase_controls",
    )
    originals = value["originals"]
    _shape(originals, {"predictions.json", "receipt.json"}, "originals_shape")
    prediction_raw = _original(originals["predictions.json"], _MAX_BYTES)
    receipt_raw = _original(originals["receipt.json"], _MAX_RECEIPT)
    receipt = _parse(receipt_raw, _MAX_RECEIPT, "receipt")
    _shape(
        receipt,
        {
            "schema",
            "recipe_digest",
            "state_digest",
            "inputs_digest",
            "predictions_digest",
            "measurement",
        },
        "receipt_shape",
    )
    _require(
        receipt["schema"] == "carbon.development.bundle-inference.v2"
        and all(
            receipt[k] == expected[k]
            for k in ("recipe_digest", "state_digest", "inputs_digest")
        )
        and receipt["predictions_digest"] == _sha(prediction_raw),
        "receipt_binding",
    )
    measured = receipt["measurement"]
    _shape(
        measured,
        {
            "scope",
            "timing_s",
            "input_shape",
            "input_dtype",
            "output_shape",
            "output_dtype",
        },
        "measurement_shape",
    )
    _require(
        measured["scope"]
        == "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
        and all(
            type(measured[k]) is list
            and all(type(v) is int and v > 0 for v in measured[k])
            for k in ("input_shape", "output_shape")
        )
        and all(
            measured[k] == expected[k]
            for k in ("input_shape", "output_shape", "input_dtype", "output_dtype")
        ),
        "measurement_binding",
    )
    timing = measured["timing_s"]
    _shape(timing, _TIMINGS, "timing_shape")
    _require(all(_finite(v) and v >= 0 for v in timing.values()), "timing_value")
    _require(any(v > 0 for v in timing.values()), "timing_value")
    _accounting(
        value["accounting"],
        expected["ledger_identities"][index],
        value["worker_operation"],
        originals,
    )
    try:
        outputs = _flat(
            _parse(prediction_raw, _MAX_BYTES, "prediction"), expected["output_shape"]
        )
    except RecursionError as exc:
        raise PairEvidenceRefused("prediction_shape") from exc
    return outputs, timing, receipt_raw, prediction_raw


def read_inference_pair(
    raw: bytes,
    *,
    registered_sha256: str,
    expected: dict,
) -> InferencePairEvidence:
    """Read pinned public evidence; authenticity remains the trusted caller's job.

    Both phases are fresh repeat queries of the retained model (Platform's
    `paired_inference` runs two new operations); neither is the graded
    original, so no original is compared here. Expected identities are
    independent registered inputs. Equal predictions are legitimate; this
    reader neither compares them nor selects a tolerance. All accounting and
    cold-stage timings are retained at operation granularity. Omitted budget
    dimensions are preserved, never filled with invented zeros.
    """
    _require(_digest(registered_sha256), "registered_digest")
    _require(type(raw) is bytes and 0 < len(raw) <= _MAX_BYTES, "pair_bytes")
    _require(_sha(raw) == registered_sha256, "registered_digest")
    _expected(expected)
    value = _parse(raw, _MAX_BYTES, "pair")
    _shape(value, _ENVELOPE, "pair_shape")
    _require(
        value["schema"] == SCHEMA
        and value["execution_boundary"] == "C03_DOCKER"
        and value["scientific_qualification"] is False
        and value["official_eligible"] is False,
        "pair_boundary",
    )
    _require(
        all(
            value[k] == expected[k]
            for k in (
                "recipe_digest",
                "state_digest",
                "inputs_digest",
                "inference_image_id",
            )
        ),
        "pair_binding",
    )
    rows = expected["input_shape"][0]
    _require(
        type(value["inference_operation_attempts"]) is int
        and value["inference_operation_attempts"] == 2
        and type(value["logical_prediction_rows_per_operation"]) is int
        and value["logical_prediction_rows_per_operation"] == rows
        and type(value["logical_prediction_row_attempts"]) is int
        and value["logical_prediction_row_attempts"] == 2 * rows
        and value["forward_calls"] is None,
        "pair_attempts",
    )
    _require(
        _finite(value["elapsed_seconds"]) and value["elapsed_seconds"] >= 0,
        "pair_elapsed",
    )
    primary = _phase(value["primary"], expected, 0)
    repeat = _phase(value["repeat"], expected, 1)
    return InferencePairEvidence(
        evidence=_freeze(value),
        outputs=(primary[0], repeat[0]),
        accounting=(
            _freeze(value["primary"]["accounting"]),
            _freeze(value["repeat"]["accounting"]),
        ),
        timing_s=(_freeze(primary[1]), _freeze(repeat[1])),
        sha256=registered_sha256,
    )
