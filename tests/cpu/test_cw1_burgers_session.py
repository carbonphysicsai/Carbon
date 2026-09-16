"""Prospective session boundaries; transport mocks are never agent inference."""

from pathlib import Path

import pytest

from carbon.construction import CompileAccepted
from carbon.development_session.budget import SessionBudget
from carbon.development_session.contracts import authored_contracts, build_contracts
from carbon.development_session.data import frozen_cases, write_once
from carbon.development_session.profile import profile_document
from carbon.generators.burgers_dynamics import canonical_public_case_bytes
from carbon.reconstruction.profile import compile_development_profile


@pytest.mark.parametrize("backbone", ("fno", "deeponet"))
def test_real_causal_contract_and_registered_adapter(backbone):
    contracts = build_contracts()
    result = contracts.compile(
        {
            "schema_version": "1.0",
            "challenge_id": "burgers-dynamics-v1",
            "backbone": backbone,
            "parameters": {"steps": 32},
        }
    )
    assert type(result) is CompileAccepted
    import json
    import math

    profile = compile_development_profile(result.construction_plan)
    assert json.loads(profile.task_config_json)["domain_length"] == 2 * math.pi
    assert json.loads(profile.train_config_json)["steps"] == 32
    physical, candidate, training = authored_contracts()
    assert {f.field_id for f in candidate.candidate_inputs} == {
        "initial",
        "viscosity",
        "requested_times",
        "positions",
    }
    assert physical.time_contract.mode.value == "TRANSIENT"
    assert training.permitted_generators.kind.value == "PERMITTED"


@pytest.mark.parametrize(
    "parameters",
    (
        {"steps": 0},
        {"steps": 65},
        {"steps": 32, "seed": 1},
        {"steps": 32, "domain_length": 1.0},
        {"steps": 32, "label_path": "/private/eval"},
    ),
)
def test_unsupported_or_authority_expanding_strategy_rejects(parameters):
    result = build_contracts().compile(
        {
            "schema_version": "1.0",
            "challenge_id": "burgers-dynamics-v1",
            "backbone": "fno",
            "parameters": parameters,
        }
    )
    assert type(result) is not CompileAccepted


def test_frozen_roles_do_not_overlap_or_regenerate(tmp_path):
    first = frozen_cases(tmp_path)
    second = frozen_cases(tmp_path)
    assert len(first) == 36
    assert [canonical_public_case_bytes(c) for c in first] == [
        canonical_public_case_bytes(c) for c in second
    ]
    assert len({canonical_public_case_bytes(c) for c in first}) == 36
    for role in ("TRAIN", "EVAL", "STRESS"):
        assert {
            c.coordinates.cell for c in first if c.coordinates.role.value == role
        } == set(range(12))
    assert (
        profile_document()["sampling"]["counts"]
        != profile_document()["sampling"]["full_v1_counts"]
    )


def test_ambiguous_reservation_is_charged_and_cannot_be_retried(tmp_path):
    path = tmp_path / "budget.sqlite3"
    SessionBudget(path).reserve("attempt-one", "worker", 10.0, 10.0, 3)
    restarted = SessionBudget(path)
    with pytest.raises(ValueError, match="reconcile"):
        restarted.reserve("attempt-one", "worker", 10.0, 20.0, 3)
    with pytest.raises(ValueError, match="exhausted"):
        restarted.reserve("attempt-two", "worker", 1.0, 10.0, 3)


def test_invalid_proposals_consume_attempt_budget(tmp_path):
    budget = SessionBudget(tmp_path / "budget.sqlite3")
    for index in range(3):
        identity = f"proposal-{index}"
        budget.reserve(identity, "proposal", 1.0, 3.0, 3)
        budget.finish(identity, 1.0, "FAILED")
    with pytest.raises(ValueError, match="exhausted"):
        budget.reserve("proposal-3", "proposal", 1.0, 3.0, 3)


def test_prospective_artifacts_cannot_be_silently_changed(tmp_path):
    target = tmp_path / "frozen.json"
    write_once(target, b"first")
    write_once(target, b"first")
    with pytest.raises(ValueError, match="conflict"):
        write_once(target, b"replacement")
    assert target.read_bytes() == b"first"


def test_no_operational_module_imports_test_fixtures():
    import ast

    import carbon.development_session

    root = Path(carbon.development_session.__file__).parent
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("tests", "test_", "c02_fixtures", "b02b_fixtures")
                )


def test_explicit_development_admission_never_qualifies_live(tmp_path):
    from carbon.development_session.service import make_mcp
    from carbon.registry import ChallengeRegistry

    _, registry = make_mcp(tmp_path)
    key = ("burgers-dynamics-v1", "1.0")
    assert registry.assess_fixture_service_eligibility(*key).eligible
    assert not registry.assess_live_eligibility(*key).eligible
    assert not registry.assess_live_eligibility(*key, fixture_mode=True).eligible
    ordinary = ChallengeRegistry(tmp_path / "registry", tmp_path / "registry-artifacts")
    assert not ordinary.assess_fixture_service_eligibility(*key).eligible
    (tmp_path / "registry-artifacts" / "development-profile.json").write_text(
        "tampered"
    )
    assert not registry.assess_fixture_service_eligibility(*key).eligible


def test_model_authority_binds_exact_proposal_expiry_and_price(tmp_path):
    from carbon.development_session.agent import check_authority, proposal
    from carbon.development_session.profile import canonical, digest

    path = tmp_path / "authority.json"
    value = {
        "schema": "carbon.burgers-session.model-run-authority.v1",
        "approved": True,
        "proposal_digest": digest(canonical(proposal())),
        "valid_from_unix": 100,
        "valid_until_unix": 200,
        "max_total_usd": 0.25,
    }
    path.write_bytes(canonical(value))
    assert check_authority(path, now=150) == value
    with pytest.raises(ValueError, match="expired"):
        check_authority(path, now=201)
    value["proposal_digest"] = "sha256:" + "0" * 64
    path.write_bytes(canonical(value))
    with pytest.raises(ValueError, match="bind"):
        check_authority(path, now=150)


def _disclosure_cohorts():
    from dataclasses import replace

    from test_c05_burgers_measurement import _inputs

    from carbon.development_session.profile import digest
    from carbon.measurement_runtime.model import execute_measurement

    _, base, candidate, reference = _inputs()
    result = execute_measurement(base, candidate, reference)
    cohorts = []
    expected = {}
    for role in ("EVAL", "STRESS"):
        cases = frozenset(
            digest(f"synthetic-{role}-{cell}".encode()) for cell in range(12)
        )
        expected[role] = cases
        pairs = []
        for case in sorted(cases):
            for index in range(3):
                request = replace(
                    base,
                    case_digest=case,
                    candidate_replica_id=f"reconstruction-replica-{index}",
                )
                pairs.append(
                    (request, replace(result, request_digest=request.request_digest))
                )
        cohorts.append((role, tuple(pairs)))
    return tuple(cohorts), expected


def test_feedback_is_aggregate_only_and_not_a_scientific_decision():
    from carbon.orchestration.development_feedback import aggregate_development_feedback

    cohorts, expected = _disclosure_cohorts()
    value = aggregate_development_feedback(cohorts, expected_cases=expected)
    assert value["score"] is None and value["accepted_improvement"] is None
    assert not any(value["eligibility"].values())
    for cohort in value["cohorts"].values():
        assert set(cohort) == {
            "parents",
            "replicas",
            "normalized_errors",
            "normalized_physics_defects",
        }
        for observations in (
            cohort["normalized_errors"],
            cohort["normalized_physics_defects"],
        ):
            assert all(
                set(item) == {"mean", "observed", "missing"}
                for item in observations.values()
            )


def test_feedback_rejects_role_swap_partial_and_duplicate_cohorts():
    from carbon.orchestration.development_feedback import aggregate_development_feedback

    cohorts, expected = _disclosure_cohorts()
    bad = (
        (("EVAL", cohorts[1][1]), ("STRESS", cohorts[0][1])),
        (("EVAL", cohorts[0][1][:-1]), cohorts[1]),
        (("EVAL", (cohorts[0][1][0],) * 36), cohorts[1]),
    )
    for value in bad:
        with pytest.raises(ValueError):
            aggregate_development_feedback(value, expected_cases=expected)


def test_engineering_fixture_cannot_be_relabelled_as_real_handoff():
    from carbon.development_session.handoff import finish_handoff
    from carbon.execution import ExecutionScope

    with pytest.raises(ValueError, match="fixture"):
        finish_handoff(
            None, None, None, {"execution_scope": ExecutionScope.FIXTURE_DEVELOPMENT}
        )


def test_source_builder_composes_real_owners_with_synthetic_test_values(
    tmp_path, monkeypatch
):
    """No model inference, public-chain observation or numerical execution."""
    import asyncio
    import time
    from types import SimpleNamespace as NS

    from test_c07_development_orchestration import _sha, _values
    from test_c08_authenticated_miner_mcp import CONTEXT, _Adapter, _Verifier

    from carbon import audit
    from carbon.chain import MetagraphSnapshot, Participant
    from carbon.development_session.handoff import finish_handoff
    from carbon.development_session.profile import CHALLENGE, canonical
    from carbon.development_session.service import (
        development_signer,
        make_mcp,
        scaffold,
    )
    from carbon.execution import DurableExecutionQueue, ExecutionScope
    from carbon.miner_mcp import AuthenticatedMinerMcpService, MinerMcpJournal
    from carbon.orchestration import DevelopmentEvaluationOrchestrator
    from carbon.transport.gateway import AuthenticatedGateway, requester_for_receipt
    from carbon.transport.models import digest, message
    from carbon.transport.store import ReceiptJournal

    now = time.time_ns()
    snapshot = MetagraphSnapshot(
        CONTEXT,
        10,
        "0x" + "2" * 64,
        now // 1_000_000,
        (Participant(0, "publisher", "owner", 1), Participant(1, "miner", "cold", 2)),
    )
    transport = ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT)
    gateway = AuthenticatedGateway(
        CONTEXT,
        CHALLENGE,
        "publisher",
        _Adapter(snapshot),
        _Verifier(),
        transport,
        clock_ns=lambda: now,
    )
    signer = development_signer(tmp_path)
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "evidence.sqlite3", (signer.verification_key,)
    )
    owner = DevelopmentEvaluationOrchestrator(
        DurableExecutionQueue(tmp_path / "orchestration.sqlite3"), ledger
    )
    mcp, _ = make_mcp(tmp_path)
    service = AuthenticatedMinerMcpService(
        gateway, mcp, owner, MinerMcpJournal(transport)
    )
    body = message(
        CONTEXT,
        snapshot.snapshot_id,
        CHALLENGE,
        session="unit-fixture",
        request="submit-1",
        tool="submit",
        fields={
            "challenge_id": CHALLENGE.challenge_id,
            "challenge_version": CHALLENGE.version,
            "strategy": scaffold(),
        },
    )
    submitted = asyncio.run(
        service.call(body, {"body": digest(body), "nonce": str(now), "hotkey": "miner"})
    )
    requester = requester_for_receipt(
        CONTEXT, transport.resolve(submitted.transport_receipt)
    )
    submission = submitted.mcp_result.status.submission_id.value
    base, repeat, receipts, prediction, reference, measurement = _values(tmp_path)
    evidence = base.evidence
    plan = NS(
        strategy_hash=base.execution.strategy_hash,
        to_ref=lambda: NS(content_digest=evidence.reconstruction_plan_digest),
    )
    profile = NS(
        profile_id="test-development",
        environment_digest=_sha("environment"),
        profile_digest=_sha("profile"),
    )
    ref_request = NS(
        request_digest=reference.request_digest,
        environment_digest=evidence.reference_environment_digest,
        document=lambda: {
            "method": {
                "implementation_digest": evidence.reference_implementation_digest
            }
        },
    )
    measurement_request = NS(
        request_digest=measurement.request_digest,
        reference_policy_digest=evidence.reference_policy_digest,
        measurement_contract_digest=evidence.measurement_contract_digest,
        implementation_digest=evidence.measurement_implementation_digest,
        measurement_environment_digest=evidence.measurement_environment_digest,
    )
    monkeypatch.setattr(
        "carbon.development_session.handoff.validate_reference_snapshot",
        lambda *_: reference,
    )
    (tmp_path / "case-manifest.json").write_bytes(
        canonical({"synthetic_test_only": True})
    )
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "strategy.json").write_bytes(canonical(scaffold()))
    (attempt / "construction-plan.json").write_bytes(b"synthetic-test-plan")
    numerical = {
        "plan": plan,
        "profile": profile,
        "image": NS(
            source_tree_digest=evidence.source_tree_digest,
            image_id=evidence.worker_image_digest,
        ),
        "worker": NS(digest=evidence.execution_policy_digest),
        "dossier": {"submission_id": submission, "synthetic_test_only": True},
        "receipts": receipts,
        "anchor": (
            prediction,
            ref_request,
            {
                "solution_path": str(tmp_path / "solution"),
                "artifact_digest": reference.artifact_digest,
            },
            measurement_request,
            measurement,
        ),
        "context": NS(pin=base.execution.handle.seed_pin),
        "archive": NS(content_digest=evidence.training_data_commitment),
        "repeat": repeat,
        "policy": NS(content_digest=evidence.resource_policy_digest),
        "attempt_root": attempt,
        "feedback": {"score": None},
        "started_at_micros": time.time_ns() // 1000,
        "execution_scope": ExecutionScope.REAL_PATH_NON_LIVE,
    }
    connection = NS(
        root=tmp_path,
        service=service,
        orchestrator=owner,
        signer=signer,
        ledger=ledger,
        transport=transport,
    )
    complete = finish_handoff(
        connection, submitted.transport_receipt, requester, numerical
    )
    assert complete.account.receipt_digest
    assert (tmp_path / f"source-{submission}.json").is_file()
    exports = tmp_path / "exports" / submission
    assert not {
        "private-evidence-signing-key.bin",
        "private-generation-entropy.bin",
        "wallet-password",
        "miner-session-key",
    } & {p.name for p in exports.iterdir()}
    _, state = ledger.resolve(
        complete.ledger_reference, verified_at_micros=time.time_ns() // 1000
    )
    assert state is audit.ReceiptLifecycleState.ACTIVE


def test_service_discovery_validation_and_estimate_use_actual_tool_schemas(tmp_path):
    from carbon import mcp
    from carbon.development_session.service import make_mcp, scaffold
    from carbon.fees import RequesterIdentity

    service, _ = make_mcp(tmp_path)
    base = {"challenge_id": "burgers-dynamics-v1", "challenge_version": "1.0"}
    for tool in (
        "get_challenge_info",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "estimate",
    ):
        fields = dict(base)
        if tool == "dry_validate":
            fields = {}
        if tool in ("dry_validate", "estimate"):
            fields["strategy"] = scaffold()
        result = service.call(
            mcp.McpCall(
                "1.0", tool, tuple(mcp.McpField(k, v) for k, v in fields.items())
            ),
            RequesterIdentity("synthetic-tool-test"),
        )
        assert result is not None


def test_external_miner_key_loader_boundary(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from carbon.chain import auth

    key_file = tmp_path / "encrypted-key"
    password_file = tmp_path / "password"
    key_file.write_bytes(b"encrypted-test-fixture")
    password_file.write_text("fixture-password")
    opened = []

    class FakeKeyfile:
        def __init__(self, path):
            opened.append(path)

        def get_keypair(self, *, password):
            assert password == "fixture-password"
            return SimpleNamespace(ss58_address="expected-test-hotkey")

    monkeypatch.setattr(
        auth,
        "_sdk",
        lambda: SimpleNamespace(keyfiles=SimpleNamespace(Keyfile=FakeKeyfile)),
    )
    assert (
        auth.open_external_hotkey(
            key_file, password_file, "expected-test-hotkey"
        ).ss58_address
        == "expected-test-hotkey"
    )
    with pytest.raises(auth.AuthFailure) as caught:
        auth.open_external_hotkey(key_file, password_file, "wrong-hotkey")
    assert str(caught.value) == "AUTH_UNAVAILABLE"
    assert caught.value.__context__ is None
    opened.clear()
    link = tmp_path / "key-link"
    link.symlink_to(key_file)
    for invalid in (link, Path("relative-key"), tmp_path / "missing"):
        with pytest.raises(auth.AuthFailure):
            auth.open_external_hotkey(invalid, password_file, "expected-test-hotkey")
    password_file.write_bytes(b"x" * 1025)
    with pytest.raises(auth.AuthFailure):
        auth.open_external_hotkey(key_file, password_file, "expected-test-hotkey")
    assert opened == []


def test_strict_named_tools_match_all_seven_actual_mcp_calls(tmp_path):
    """Offline protocol regression; no agent inference or numerical execution."""
    from carbon import mcp
    from carbon.development_session.agent import TOOLS
    from carbon.development_session.service import make_mcp, scaffold
    from carbon.fees import RequesterIdentity

    service, _ = make_mcp(tmp_path)
    requester = RequesterIdentity("synthetic-seven-tool-test")
    definitions = {item["name"]: item for item in TOOLS}
    assert set(definitions) == {item.value for item in mcp.McpTool}
    base = {"challenge_id": "burgers-dynamics-v1", "challenge_version": "1.0"}
    submission = None
    for name in (
        "get_challenge_info",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "estimate",
        "submit",
        "get_submission_result",
    ):
        fields = dict(base)
        if name == "dry_validate":
            fields = {"strategy": scaffold()}
        elif name in ("estimate", "submit"):
            fields["strategy"] = scaffold()
        elif name == "get_submission_result":
            fields = {"submission_id": submission}
        schema = definitions[name]["parameters"]
        assert definitions[name]["strict"] is True
        assert set(fields) == set(schema["properties"]) == set(schema["required"])
        assert schema["additionalProperties"] is False
        result = service.call(
            mcp.McpCall(
                "1.0", name, tuple(mcp.McpField(k, v) for k, v in fields.items())
            ),
            requester,
        )
        if name == "submit":
            submission = result.status.submission_id.value
        assert result is not None

    def closed_objects(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
            for child in schema["properties"].values():
                closed_objects(child)

    for tool in TOOLS:
        closed_objects(tool["parameters"])
    assert "tool" not in definitions["dry_validate"]["parameters"]["properties"]
    assert "arguments_json" not in repr(TOOLS)


@pytest.mark.parametrize("malformed", (False, True))
def test_agent_direct_tool_dispatch_and_retained_malformed_stop(
    tmp_path, monkeypatch, malformed
):
    """Synthetic transport replies test routing only; never empirical inference."""
    import asyncio
    import json
    import time

    from carbon.development_session import agent
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.service import scaffold

    called = []
    fields = {"strategy": scaffold()}
    if malformed:
        # Exact shape emitted by the stopped real run's nested argument string.
        fields["tool"] = "dry_validate"
    responses = iter(
        [
            {
                "id": "synthetic-1",
                "model": agent.MODEL,
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "output": [
                    {
                        "type": "function_call",
                        "name": "dry_validate",
                        "call_id": "synthetic-call",
                        "arguments": json.dumps(fields),
                    }
                ],
            },
            {
                "id": "synthetic-2",
                "model": agent.MODEL,
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "output": [],
            },
        ]
    )
    monkeypatch.setattr(
        agent.ResponsesTransport, "__call__", lambda *_: next(responses)
    )

    class Connection:
        def __init__(self):
            self.root = tmp_path
            self.budget = SessionBudget(tmp_path / "budget.sqlite3")
            self.proposals = {}
            self.completed = {}

        async def check_registration(self):
            pass

        async def call(self, tool, arguments):
            called.append((tool, arguments))
            return {"valid": True}

    authority = tmp_path / "authority.json"
    authority.write_bytes(
        canonical(
            {
                "schema": "carbon.burgers-session.model-run-authority.v1",
                "proposal_digest": digest(canonical(agent.proposal())),
                "approved": True,
                "valid_from_unix": time.time() - 10,
                "valid_until_unix": time.time() + 60,
                "max_total_usd": 0.25,
            }
        )
    )
    connection = Connection()
    if malformed:
        with pytest.raises(ValueError, match="invalid agent tool arguments"):
            asyncio.run(agent.run(connection, authority, tmp_path / "unused-key"))
        assert called == []
        assert (tmp_path / "provider-1-response.json").is_file()
        assert (tmp_path / "agent-stopped-report.json").is_file()
        assert not (tmp_path / "provider-2-request.json").exists()
        assert connection.budget.summary()[0]["state"] == "COMPLETE"
    else:
        report = asyncio.run(agent.run(connection, authority, tmp_path / "unused-key"))
        assert called == [("dry_validate", {"strategy": scaffold()})]
        assert report["calls"][0]["tool"] == "dry_validate"
        assert (tmp_path / "provider-1-tool-result.json").is_file()
    # A second process cannot replace the retained campaign, even in this fixture.
    with pytest.raises(ValueError):
        asyncio.run(agent._run(connection, authority, tmp_path / "unused-key"))
