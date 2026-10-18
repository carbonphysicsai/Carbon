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
from carbon.scoring import private_evaluation_source as producer_source
from carbon.scoring.dual_score import INPUT_SCHEMA, PACK_SCHEMA, register_pack
from carbon.scoring.private_evaluation_source import (
    DUAL_MEASUREMENT_CONTRACT_SCHEMA,
    DUAL_MEASUREMENT_SCHEMA,
    PACK_SOURCE_SCHEMA,
    PrivateEvaluationSourceRefused,
    build_dual_measurement_receipt,
    build_pack_source_receipt,
    produce_registered_dual_measurement,
)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _selected_pack(
    case, *, version="1", incomplete=False, wrong_train=False, unbound_source=False
):
    public = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PUBLIC_ROLES
    }
    public["train"]["sha256"] = (
        _sha(b"wrong-train") if wrong_train else case["entry"]["train_digest"]
    )
    for role in (
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
    ):
        public[role] = UNAVAILABLE
    private = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PRIVATE_ROLES
    }
    if incomplete:
        private["solver_evidence"] = UNAVAILABLE
    if unbound_source:
        private["source_registration"] = UNAVAILABLE
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


def test_unapplied_public_rule_documents_do_not_gate_v3_source(tmp_path):
    case = _graph_case(tmp_path)
    selected = _selected_pack(case)
    assert set(selected.missing_roles()["public"]) == {
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
    }
    assert _build(case, selected).evaluation_pack_digest == selected.manifest_digest


def test_optional_unbound_registration_does_not_change_explicit_source_builder(
    tmp_path,
):
    case = _graph_case(tmp_path)
    selected = _selected_pack(case, unbound_source=True)
    assert "source_registration" in selected.missing_roles()["private"]
    assert _build(case, selected).evaluation_pack_digest == selected.manifest_digest


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


def _dual_case(tmp_path):
    case = _graph_case(tmp_path)
    producer = _sha(b"synthetic-carbon-producer")
    public = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PUBLIC_ROLES
    }
    public["train"]["sha256"] = case["entry"]["train_digest"]
    definitions = {
        "accuracy_definition": {"producer_digest": producer, "metric": "toy-A"},
        "important_limit_definition": {"limit": "toy-only"},
        "design_objective": {"objective": "toy-only"},
    }
    for role, value in definitions.items():
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if role == "important_limit_definition":
            (tmp_path / "important_limit_definition.json").write_bytes(raw)
            public[role] = {
                "path": "important_limit_definition.json",
                "sha256": _sha(raw),
            }
        else:
            public[role] = {"inline": value, "sha256": _sha(raw)}
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": producer,
        "accuracy_definition_sha256": public["accuracy_definition"]["sha256"],
        "important_limit_definition_sha256": public["important_limit_definition"][
            "sha256"
        ],
        "design_objective_sha256": public["design_objective"]["sha256"],
    }
    contract_digest = _sha(
        (json.dumps(basis, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    physics = case["result"]["physics_contract"]["definition_digest"]
    pack = register_pack(
        {
            "schema": PACK_SCHEMA,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": case["entry"]["challenge"],
            "physics_contract_digest": physics,
            "measurement_contract_digest": contract_digest,
            "hard_gates": ["toy_gate"],
            "legs": {
                name: {
                    "components": [
                        {
                            "metric": "toy-" + name,
                            "unit": "toy-unit",
                            "transform": "unit_benefit",
                            "scale": None,
                            "weight": 1.0,
                        }
                    ],
                    "minimum": None,
                }
                for name in ("A", "D")
            },
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
            "decision_policy": {
                "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
                "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
                "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
            },
        }
    )
    private = {
        role: {"path": role + ".bin", "sha256": _sha(role.encode())}
        for role in PRIVATE_ROLES
    }
    pack_raw = (json.dumps(pack, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (tmp_path / "score_pack.json").write_bytes(pack_raw)
    private["score_pack"] = {"path": "score_pack.json", "sha256": _sha(pack_raw)}
    manifest = {
        "schema": SCHEMA,
        "challenge": {
            "id": case["entry"]["challenge"],
            "version": case["entry"]["challenge_version"],
        },
        "pack_version": "synthetic-dual-v1",
        "public": public,
        "private": private,
    }
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    selected = parse_pack(
        raw,
        expected_digest=_sha(raw),
        challenge_id=case["entry"]["challenge"],
        challenge_version=case["entry"]["challenge_version"],
    )
    source_raw = _build(case, selected).raw
    source = json.loads(source_raw)
    benchmark = {
        "schema": INPUT_SCHEMA,
        "scope": pack["scope"],
        "challenge": pack["challenge"],
        "physics_contract_digest": physics,
        "measurement_contract_digest": contract_digest,
        "population_role": "P",
        "common_mask_digest": _sha(
            (
                json.dumps(source["cases"], sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
        ),
        "models": [
            {
                "artifact_digest": case["entry"]["entry_id"],
                "gates": {"toy_gate": "PASS"},
                "measurements": {
                    name: {"status": "RESOLVED", "value": 0.5, "unit": "toy-unit"}
                    for name in ("toy-A", "toy-D")
                },
                "decision_outcome": "VERIFIED_FEASIBLE",
            }
        ],
    }
    args = {
        "selected_pack": selected,
        "public_root": tmp_path,
        "private_root": tmp_path,
        "entry": case["entry"],
        "measured_model": case["measured"],
        "graph_originals": case["graph_originals"],
        "evaluation_source_receipt_raw": source_raw,
        "benchmark": benchmark,
        "producer_digest": producer,
    }
    return args


def test_dual_measurement_receipt_binds_selected_roles_source_and_originals(tmp_path):
    args = _dual_case(tmp_path)
    prepared = build_dual_measurement_receipt(**args)
    body = json.loads(prepared.raw)
    assert body["schema"] == DUAL_MEASUREMENT_SCHEMA
    assert body["source_receipt_sha256"] == _sha(args["evaluation_source_receipt_raw"])
    assert body["evaluation_pack_digest"] == args["selected_pack"].manifest_digest
    assert body["entry_id"] == args["entry"]["entry_id"]
    assert body["state_digest"] == args["entry"]["state_digest"]
    assert body["measurement_contract"]["schema"] == (DUAL_MEASUREMENT_CONTRACT_SCHEMA)
    assert body["measurement_contract"]["producer_digest"] == args["producer_digest"]
    assert body["benchmark"] == args["benchmark"]
    assert prepared.sha256 == _sha(prepared.raw)
    assert prepared.measured_model == args["measured_model"]
    assert prepared.measured_model is not args["measured_model"]
    assert (
        "outputs" not in json.loads(args["evaluation_source_receipt_raw"])["cases"][0]
    )


def test_dual_measurement_receipt_refuses_source_mask_and_producer_substitution(
    tmp_path,
):
    args = _dual_case(tmp_path)
    for change, expected in (
        ({"producer_digest": _sha(b"other")}, "dual_producer_pin"),
        ({"evaluation_source_receipt_raw": b"{}\n"}, "dual_source_shape"),
        (
            {
                "benchmark": {
                    **args["benchmark"],
                    "common_mask_digest": _sha(b"different-mask"),
                }
            },
            "dual_common_mask",
        ),
    ):
        with pytest.raises(PrivateEvaluationSourceRefused) as raised:
            build_dual_measurement_receipt(**{**args, **change})
        assert raised.value.code == expected


def test_dual_measurement_receipt_refuses_cross_challenge_and_changed_pack(tmp_path):
    args = _dual_case(tmp_path)
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        build_dual_measurement_receipt(
            **{**args, "entry": {**args["entry"], "challenge": "other-challenge"}}
        )
    assert raised.value.code == "dual_model_identity"

    limits = tmp_path / "important_limit_definition.json"
    original_limits = limits.read_bytes()
    limits.write_bytes(b"{}")
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        build_dual_measurement_receipt(**args)
    assert raised.value.code == "dual_pack_role"
    limits.write_bytes(original_limits)

    (tmp_path / "score_pack.json").write_bytes(b"{}\n")
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        build_dual_measurement_receipt(**args)
    assert raised.value.code == "dual_pack_role"


def test_actual_challenge_has_no_implicit_dual_producer(tmp_path):
    args = _dual_case(tmp_path)
    with pytest.raises(PrivateEvaluationSourceRefused) as raised:
        produce_registered_dual_measurement(
            selected_pack=args["selected_pack"],
            public_root=tmp_path,
            private_root=tmp_path,
            entry=args["entry"],
            trusted_job={},
            registration={},
            references=[],
            graph_originals=args["graph_originals"],
            evaluation_source_receipt_raw=args["evaluation_source_receipt_raw"],
        )
    assert raised.value.code == "dual_measurement_producer_unavailable"


def test_fixture_producer_uses_real_receipt_builder(monkeypatch, tmp_path):
    args = _dual_case(tmp_path)
    monkeypatch.setattr(
        producer_source,
        "produce_dual_benchmark_input",
        lambda **_kwargs: (
            args["measured_model"],
            args["benchmark"],
            args["producer_digest"],
        ),
    )
    prepared = produce_registered_dual_measurement(
        selected_pack=args["selected_pack"],
        public_root=tmp_path,
        private_root=tmp_path,
        entry=args["entry"],
        trusted_job={},
        registration={},
        references=[],
        graph_originals=args["graph_originals"],
        evaluation_source_receipt_raw=args["evaluation_source_receipt_raw"],
    )
    assert json.loads(prepared.raw)["benchmark"] == args["benchmark"]
    assert prepared.sha256 == _sha(prepared.raw)
    assert prepared.measured_model == args["measured_model"]
