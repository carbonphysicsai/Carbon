"""Machine-checkable ratification boundaries for the B-07S v2 protocol."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "Design_Specs" / "Miner_MCP_Wave_B_Service_Protocol.md"
BEGIN = "<!-- B07S-CONFORMANCE-MANIFEST-BEGIN -->"
END = "<!-- B07S-CONFORMANCE-MANIFEST-END -->"

pytestmark = pytest.mark.invariant

V2_OPERATIONS = (
    "get_challenge_info",
    "get_interaction_manifest",
    "get_prior",
    "get_mock_scaffold",
    "dry_validate",
    "compile_strategy",
    "inspect_prior_alignment",
    "inspect_resources",
    "forecast_resources",
    "start_research_task",
    "get_research_result",
    "cancel_research_task",
)


def _text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def _manifest() -> dict[str, object]:
    payload = _text().split(BEGIN, 1)[1].split(END, 1)[0].strip()
    assert payload.startswith("```json\n") and payload.endswith("```")
    return json.loads(payload[len("```json\n") : -len("```")])


def test_exact_namespaces_and_closed_operation_vocabulary() -> None:
    manifest = _manifest()
    assert manifest["namespace"] == "carbon_research_v2"
    assert manifest["official_v1_namespace"] == "carbon_protocol_v1"
    assert tuple(manifest["operations"]) == V2_OPERATIONS
    assert manifest["official_v1_operations"] == ["submit", "get_submission_result"]
    assert set(manifest["operations"]).isdisjoint(manifest["official_v1_operations"])
    assert set(manifest["operations"]).isdisjoint(manifest["reserved_operations"])


def test_every_operation_has_one_complete_owner_contract() -> None:
    manifest = _manifest()
    contracts = manifest["operation_contracts"]
    fields = manifest["request_fields"]
    assert set(contracts) == set(V2_OPERATIONS)
    assert set(fields) == set(V2_OPERATIONS)
    assert all(len(contract) == 5 for contract in contracts.values())
    owners = {contract[2] for contract in contracts.values()}
    assert owners == {"B-07A", "B-07D3", "B-07C", "A2", "B-02B", "B-07E", "B-07B"}
    assert all(contract[3] for contract in contracts.values())
    assert {contract[4] for contract in contracts.values()} == {"none", "create", "read", "cancel"}


def test_requests_cannot_select_context_provider_or_scientific_control() -> None:
    manifest = _manifest()
    all_request_fields = {
        field for fields in manifest["request_fields"].values() for field in fields
    }
    forbidden = set(manifest["forbidden_control_fields"])
    assert all_request_fields.isdisjoint(forbidden)
    for forbidden_field in (
        "context",
        "provider",
        "mode",
        "official_seed",
        "stress_set",
        "truth",
        "gate",
        "scorer",
        "qualification_label",
    ):
        assert forbidden_field in forbidden


def test_all_wire_collections_have_finite_protocol_limits() -> None:
    limits = _manifest()["limits"]
    assert limits == {
        "canonical_call_reply_bytes": 1_048_576,
        "canonical_resource_bytes": 8_388_608,
        "nesting_depth": 32,
        "default_tuple_items": 4_096,
        "prior_pack_items": 256,
        "finding_items": 256,
        "task_polls": 10_000,
    }
    assert all(type(value) is int and value > 0 for value in limits.values())


def test_task_state_machine_is_closed_and_terminal_states_have_no_exit() -> None:
    manifest = _manifest()
    states = set(manifest["task_states"])
    terminal = set(manifest["terminal_states"])
    transitions = {tuple(pair) for pair in manifest["task_transitions"]}
    assert states == {
        "QUEUED",
        "RUNNING",
        "CANCEL_REQUESTED",
        "SUCCEEDED",
        "FAILED_INFRA",
        "CANCELLED",
    }
    assert terminal == {"SUCCEEDED", "FAILED_INFRA", "CANCELLED"}
    assert manifest["task_kinds"] == [
        "RECONSTRUCTION_REHEARSAL",
        "PRACTICE",
        "PAIRED_PRACTICE",
        "RESOURCE_CALIBRATION",
    ]
    assert all(source in states and target in states for source, target in transitions)
    assert not any(source in terminal for source, _ in transitions)
    assert not any(source == target for source, target in transitions)


def test_prior_identity_preimages_are_acyclic() -> None:
    identity = _manifest()["prior_identity"]
    assert identity["publication_classes"] == [
        "TEST_ONLY",
        "BOOTSTRAP_PUBLIC",
        "LEARNED_PUBLIC",
    ]
    assert identity["genesis_previous_index"] == "PriorPreviousIndex::GENESIS"
    assert "without self-hash or PriorPackRef" in identity["pack_hash"]
    assert set(identity["transition_digest_excludes"]) == {
        "publication_receipt",
        "resulting_index_ref",
    }
    text = _text()
    assert "content hash is outside its preimage" in text
    assert "reciprocal predecessor cycle" in text


def test_fixture_capability_is_nominal_and_never_publication_authority() -> None:
    contexts = _manifest()["contexts"]
    assert contexts == {
        "external": "ExternalPublicResearchContext",
        "fixture": "FixtureResearchContext",
        "fixture_only_capability": "TEST_ONLY_FIXTURE_PRIOR",
        "fixture_ceiling": ["TEST_ONLY", "NOT_UTILITY_QUALIFIED"],
    }
    text = _text()
    assert "never a public `PriorPublicationReceipt`" in text
    assert "not wire fields" in text


def test_negative_failures_and_error_precedence_are_closed() -> None:
    manifest = _manifest()
    errors = set(manifest["errors"])
    required = {
        "CANONICAL_ENCODING_INVALID",
        "NAMESPACE_MISMATCH",
        "OPERATION_UNSUPPORTED",
        "BOUND_EXCEEDED",
        "FORBIDDEN_SCIENTIFIC_CONTROL",
        "CONTEXT_SELECTION_FORBIDDEN",
        "TEST_ONLY_AUTHORITY_INVALID",
        "PRIOR_IDENTITY_INVALID",
        "INVALID_TASK_TRANSITION",
        "IDEMPOTENCY_CONFLICT",
        "CAPABILITY_UNAVAILABLE",
        "DISCLOSURE_REJECTED",
    }
    assert required <= errors
    assert manifest["error_precedence"] == [
        "canonical",
        "namespace",
        "operation",
        "request_type",
        "bounds",
        "capability",
        "reference",
        "state",
        "provider",
        "disclosure",
    ]


def test_ratification_does_not_claim_implementation_or_qualification() -> None:
    maturity = _manifest()["maturity"]
    assert maturity["specified"] is True
    assert maturity["ratified"] is True
    for forbidden_claim in (
        "implemented",
        "scientifically_qualified",
        "security_qualified",
        "network_qualified",
        "production_qualified",
        "live",
    ):
        assert maturity[forbidden_claim] is False
