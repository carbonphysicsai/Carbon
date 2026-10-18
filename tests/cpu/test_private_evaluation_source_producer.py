"""The private v2 receipt is derived from selected pack and saved originals."""

import hashlib
import json
from copy import deepcopy

import pytest
from test_score_lab_private_evaluation_evidence import _graph_case, _source_receipt

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    UNAVAILABLE,
    parse_pack,
)
from carbon.scoring.private_evaluation_source import (
    PACK_SOURCE_SCHEMA,
    PrivateEvaluationSourceRefused,
    build_pack_source_receipt,
)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _selected_pack(case, *, version="1", incomplete=False, wrong_train=False):
    public = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PUBLIC_ROLES
    }
    public["train"]["sha256"] = (
        _sha(b"wrong-train") if wrong_train else case["entry"]["train_digest"]
    )
    private = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PRIVATE_ROLES
    }
    if incomplete:
        private["solver_evidence"] = UNAVAILABLE
    manifest = {
        "schema": SCHEMA,
        "challenge": {
            "id": case["entry"]["challenge"],
            "version": case["entry"]["challenge_version"],
        },
        "pack_version": version,
        "public": public,
        "private": private,
    }
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return parse_pack(
        raw,
        expected_digest=_sha(raw),
        challenge_id=manifest["challenge"]["id"],
        challenge_version=manifest["challenge"]["version"],
    )


def _build(case, selected_pack, **overrides):
    arguments = {
        "selected_pack": selected_pack,
        "entry": case["entry"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "ordered_query_bytes": case["ordered_query_bytes"],
        "evaluation_version": "synthetic-eval-v1",
    }
    arguments.update(overrides)
    return build_pack_source_receipt(**arguments)


def test_v2_source_is_v1_original_binding_plus_selected_pack(tmp_path):
    case = _graph_case(tmp_path)
    selected = _selected_pack(case)
    prepared = _build(case, selected)
    legacy_raw, _legacy_pin = _source_receipt(case)
    expected = json.loads(legacy_raw)
    expected["schema"] = PACK_SOURCE_SCHEMA
    expected["evaluation_pack_digest"] = selected.manifest_digest
    expected_raw = (
        json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert prepared.raw == expected_raw
    assert prepared.sha256 == _sha(expected_raw)
    assert prepared.evaluation_pack_digest == selected.manifest_digest
    assert "outputs" not in expected["cases"][0]
    assert "reference" not in expected["cases"][0]


def test_new_pack_changes_prospective_source_identity_without_rewriting_old(tmp_path):
    case = _graph_case(tmp_path)
    old = _build(case, _selected_pack(case, version="1"))
    new = _build(case, _selected_pack(case, version="2"))
    assert old.evaluation_pack_digest != new.evaluation_pack_digest
    assert old.sha256 != new.sha256
    assert json.loads(old.raw)["evaluation_pack_digest"] == old.evaluation_pack_digest


def test_unfinished_or_wrong_train_pack_refuses_same_challenge(tmp_path):
    case = _graph_case(tmp_path)
    for selected, code in (
        (_selected_pack(case, incomplete=True), "selected_pack_incomplete"),
        (_selected_pack(case, wrong_train=True), "selected_pack_train_mismatch"),
    ):
        with pytest.raises(PrivateEvaluationSourceRefused) as raised:
            _build(case, selected)
        assert raised.value.code == code


def test_cross_challenge_or_wrong_case_originals_refuse(tmp_path):
    case = _graph_case(tmp_path)
    selected = _selected_pack(case)
    wrong_entry = {**case["entry"], "challenge": "another-challenge"}
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        _build(case, selected, entry=wrong_entry)
    assert raised.value.code == "source_identity"

    references = deepcopy(case["references"])
    references[0]["id"] = "another-case"
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        _build(case, selected, references=references)
    assert raised.value.code == "source_case"

    for malformed_status in ([], {}):
        references = deepcopy(case["references"])
        references[0]["status"] = malformed_status
        with pytest.raises(PrivateEvaluationSourceRefused) as raised:
            _build(case, selected, references=references)
        assert raised.value.code == "source_case"

    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        _build(case, selected, ordered_query_bytes=[b""])
    assert raised.value.code == "source_case"
