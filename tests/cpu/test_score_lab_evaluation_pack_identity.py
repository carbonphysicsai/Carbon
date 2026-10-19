"""Selected pack identity stays in trusted private evidence and cache keys."""

import json
from copy import deepcopy

import pytest
from test_public_bundle_model_custody import _json, _sha
from test_score_lab_private_evaluation_evidence import (
    _bind,
    _graph_case,
    _source_receipt,
)

from carbon.battery.pool_store import StateError
from carbon.challenge_validator.bank_promotion import private_evaluation_key
from carbon.challenge_validator.interface import digest
from carbon.scoring import private_evaluation_evidence as private


def source_for_pack(case, pin):
    raw, _ = _source_receipt(case)
    source = json.loads(raw)
    source.update(schema=private.PACK_SOURCE_SCHEMA, evaluation_pack_digest=pin)
    raw = _json(source)
    return {
        "evaluation_source_receipt_raw": raw,
        "registered_source_receipt_sha256": _sha(raw),
    }


def test_legacy_no_pack_receipt_and_cache_identity_are_preserved(tmp_path):
    case = _graph_case(tmp_path)
    sidecar = _bind(case)
    assert sidecar == _bind(case, expected_evaluation_pack_digest=None)
    assert sidecar["schema"] == private.SIDECAR_SCHEMA
    assert "evaluation_pack_digest" not in sidecar
    # The previous key's exact document is the historical compatibility rule.
    assert private_evaluation_key(sidecar) == digest(
        {
            key: sidecar[key]
            for key in (
                "challenge",
                "challenge_version",
                "evaluation_version",
                "evaluation_version_digest",
                "score_compatibility",
            )
        }
    )


def test_pack_bound_private_evidence_cannot_reuse_another_manifest(tmp_path):
    case = _graph_case(tmp_path)
    before = deepcopy(case["result"])
    pins = [_sha(b"synthetic-pack-one"), _sha(b"synthetic-pack-two")]
    sidecars = [
        _bind(case, **source_for_pack(case, pin), expected_evaluation_pack_digest=pin)
        for pin in pins
    ]
    legacy = _bind(case)
    assert len({private_evaluation_key(s) for s in [legacy, *sidecars]}) == 3
    for sidecar, pin in zip(sidecars, pins, strict=True):
        assert sidecar["schema"] == private.PACK_SIDECAR_SCHEMA
        assert sidecar["evaluation_pack_digest"] == pin
        assert sidecar["model_p"] == legacy["model_p"]
        assert sidecar["benchmark_result_digest"] == legacy["benchmark_result_digest"]
        assert sidecar["scope"] == "PRIVATE_OPERATOR_DEVELOPMENT"
    assert case["result"] == before


def test_selected_pack_requires_both_v2_source_and_independent_expected_pin(tmp_path):
    case = _graph_case(tmp_path)
    pin, other = _sha(b"selected"), _sha(b"different")
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="evaluation_pack_source_missing"
    ):
        _bind(case, expected_evaluation_pack_digest=pin)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="evaluation_pack_pin_missing"
    ):
        _bind(case, **source_for_pack(case, pin))
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="evaluation_pack_pin_mismatch"
    ):
        _bind(case, **source_for_pack(case, pin), expected_evaluation_pack_digest=other)


@pytest.mark.parametrize("pin", [True, "", "HUMAN_INPUT", "sha256:short"])
def test_untrusted_or_missing_expected_pack_labels_refuse(tmp_path, pin):
    case = _graph_case(tmp_path)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="evaluation_pack_pin_invalid"
    ):
        _bind(case, expected_evaluation_pack_digest=pin)


def test_v2_cache_key_requires_pin_and_v1_cannot_ignore_one(tmp_path):
    case = _graph_case(tmp_path)
    pin = _sha(b"selected")
    sidecar = _bind(
        case, **source_for_pack(case, pin), expected_evaluation_pack_digest=pin
    )
    without_pin = {k: v for k, v in sidecar.items() if k != "evaluation_pack_digest"}
    with pytest.raises(StateError, match="evaluation_pack_pin_missing"):
        private_evaluation_key(without_pin)
    with pytest.raises(StateError, match="evaluation_pack_source_version"):
        private_evaluation_key({**_bind(case), "evaluation_pack_digest": pin})


@pytest.mark.parametrize("schema", [[], {}, None, 5])
def test_malformed_source_schema_stays_a_typed_refusal(tmp_path, schema):
    case = _graph_case(tmp_path)
    raw, _ = _source_receipt(case)
    source = json.loads(raw)
    source["schema"] = schema
    raw = _json(source)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_receipt_shape"
    ):
        _bind(
            case,
            evaluation_source_receipt_raw=raw,
            registered_source_receipt_sha256=_sha(raw),
        )
